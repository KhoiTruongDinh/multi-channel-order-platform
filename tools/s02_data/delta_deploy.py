"""Explicit, guarded local delta rollout. Never reset raw, budgets or volumes."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

from tools.s02_data.load import LocalDB,ROOT,query
from tools.s02_data.live import compose,drain,startup_lock,DAGS,require_no_orphaned_source_owners
from test_support.s02_plan import literal
from transformation.delta_plan import load,source_hash
from transformation.source_config import SOURCES


def plan_folder(directory):
    prefix='/opt/airflow/state/delta-plans/'
    if not directory.startswith(prefix) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',directory[len(prefix):]):
        raise ValueError('use /opt/airflow/state/delta-plans/<explicit-release>')
    return ROOT/'runtime/airflow/state/delta-plans'/directory[len(prefix):]


def require_ready(db,directory):
    if not directory:
        return
    folder=plan_folder(directory)
    if not query(db,"SELECT to_regclass('ops.delta_batches') AS name",'data_platform')[0]['name']:
        raise ValueError('explicit verified delta deployment required before enabling LIVE_DELTA_PLAN_DIR')
    for source in SOURCES:
        plan=load(folder/(source+'.json'))
        if plan['source']!=source or plan['mapping_version']!='local-live-v1':
            raise ValueError('deployment source/mapping release mismatch')
        rows=query(db,'''SELECT d.plan_sha256 FROM ops.publication_state p
            JOIN ops.delta_batches d USING(batch_id) WHERE p.publication_name='''+
            literal(SOURCES[source][2]),'data_platform')
        if not rows or rows[0]['plan_sha256']!=plan['plan_sha256']:
            raise ValueError('active publication needs explicit bootstrap for '+source)


def run(db,startup_report,report,confirmed=False):
    if not confirmed:
        raise ValueError('explicit --confirm-local required; main Airflow is replaced only after gates pass')
    gate=json.loads(startup_report.read_text(encoding='utf-8'))
    if gate.get('status')!='PASS' or gate.get('mapping_gate',{}).get('status')!='PASS':
        raise ValueError('passing strict restart AND mapping/full-dbt report required')
    cycles=[t for t in gate.get('final_airflow_tasks',[]) if t['task_id']=='cycle']
    if not cycles or any(t['try_number']!=2 or t['state']!='success' for t in cycles):
        raise ValueError('strict exactly-two-try restart gate required')
    restored=gate.get('owner_restored',{})
    if not all(restored.get(name) for name in ('healthy','pause_states_unchanged','drain_signal_restored')):
        raise ValueError('main restoration must pass before retained rollout')
    probe_plan=Path(gate['task_logs_archive']).parent/'plans/internal_web.json'
    load(probe_plan)  # Refuse a gate for different business/runtime code.
    model=json.loads(compose(db,['config','--format','json']))
    directory=model['services']['airflow']['environment'].get('POLLING_DELTA_PLAN_DIR','')
    if not directory:
        raise ValueError('set the explicit LIVE_DELTA_PLAN_DIR release path before rollout')
    folder=plan_folder(directory)
    if folder.exists() or report.exists():
        raise ValueError('use a new release/report; retained failed bootstrap identities must be resumed explicitly')
    original=query(db,'SELECT dag_id,is_paused FROM dag ORDER BY dag_id','airflow_meta')
    if not set(DAGS)<={r['dag_id'] for r in original if not r['is_paused']}:
        raise ValueError('all four live DAGs must be enabled before the scheduled rollout gate')
    if (ROOT/'runtime/airflow/state/polling-drain').exists():
        raise ValueError('another maintenance drain is present; do not replace its signal')
    owner=json.loads(subprocess.run(['docker','inspect','multi-channel-order-platform-airflow-1'],
        capture_output=True,text=True,check=True).stdout)[0]
    labels=owner['Config']['Labels']
    assert labels.get('com.docker.compose.project')=='multi-channel-order-platform'
    assert labels.get('com.docker.compose.service')=='airflow'
    assert owner['State']['Running'] and owner['State'].get('Health',{}).get('Status')=='healthy'
    result=dict(status='RUNNING',source_hash=source_hash(),release=directory,
        owner_before=dict(id=owner['Id'],image=owner['Image'],pause_states=original),bootstraps={})
    stopped=False; activated=False

    def save():
        result['updated_at']=datetime.now(timezone.utc).isoformat()
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,indent=2),encoding='utf-8')

    def docker(*args):
        done=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=450)
        if done.returncode:
            raise RuntimeError('guarded Docker action failed (details suppressed)')
        return done.stdout

    def restore_pause():
        current={r['dag_id']:r['is_paused'] for r in query(db,'SELECT dag_id,is_paused FROM dag','airflow_meta')}
        for row in original:
            if current.get(row['dag_id'])==row['is_paused']:
                continue
            db.command(['exec','-T','airflow','airflow','dags',
                'pause' if row['is_paused'] else 'unpause',row['dag_id']],timeout=120)

    save()
    try:
        result['phase']='draining-main'; save()
        drain(db,guard=lambda:require_no_orphaned_source_owners(db))
        active=query(db,"SELECT batch_id FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')",'data_platform')
        assert not active,'finish retained batches before deployment; no automatic abort'
        assert not query(db,"SELECT run_id FROM dag_run WHERE state IN ('queued','running')",'airflow_meta')
        print('Delta deploy: main idle; building image, retaining PostgreSQL/SIM/raw',flush=True)
        compose(db,['build','airflow'],timeout=900)
        stopped=True  # Restore by exact ID even if Docker times out after stop.
        docker('stop','--time','30',owner['Id'])
        assert not query(db,"SELECT run_id FROM dag_run WHERE state IN ('queued','running')",'airflow_meta')
        db.sql((ROOT/'migrations/platform/012_delta_runtime.sql').read_text(),'data_platform')
        db.sql((ROOT/'migrations/platform/013_daily_scope_access.sql').read_text(),'data_platform')
        db.sql((ROOT/'migrations/platform/014_acquisition_elements.sql').read_text(),'data_platform')
        result['phase']='verified-cold-bootstrap'; save()
        for source in SOURCES:
            print('Delta deploy: compile and full-dbt verified cold bootstrap '+source,flush=True)
            path=directory+'/'+source+'.json'
            compile_out=compose(db,['run','--rm','-T','--no-deps','--entrypoint',
                '/opt/airflow/project-venv/bin/python','airflow','-m','transformation.delta_plan',
                '--source',source,'--output',path],timeout=900)
            batch,run_id,publisher=(str(uuid.uuid4()) for _ in range(3))
            result['bootstraps'][source]=dict(plan=path,plan_sha256=compile_out.splitlines()[-1],
                batch_id=batch,run_id=run_id,publish_run_id=publisher)
            save()
            out=compose(db,['run','--rm','-T','--no-deps','--entrypoint',
                '/opt/airflow/project-venv/bin/python','airflow','-m','transformation.delta_bootstrap',
                '--plan',path,'--batch-id',batch,'--run-id',run_id,'--publish-run-id',publisher],timeout=1800)
            result['bootstraps'][source]['result']=json.loads(out.splitlines()[-1]); save()
        require_ready(db,directory)
        result['phase']='activating-verified-plans'; save()
        activated=True  # Compose may replace the old ID before reporting failure.
        compose(db,['up','--detach','--no-deps','--wait','--wait-timeout','420','airflow'],timeout=450)
        restore_pause()
        db.command(['exec','-T','airflow','python','-c',
            'from pathlib import Path; Path("/opt/airflow/state/polling-drain").unlink(missing_ok=True)'])
        result['activated_at']=datetime.now(timezone.utc).isoformat()
        result['phase']='scheduled-warm-observation'; save()
        deadline=time.monotonic()+600
        while True:
            rows=query(db,"SELECT dag_id,count(*) AS successes FROM dag_run WHERE run_type='scheduled' AND state='success' AND start_date>="+
                literal(result['activated_at'])+'::timestamptz GROUP BY dag_id','airflow_meta')
            result['scheduled_successes']=rows
            needed=[r['dag_id'] for r in original if r['dag_id'] in DAGS and not r['is_paused']]
            if all(next((r['successes'] for r in rows if r['dag_id']==name),0)>=2 for name in needed): break
            if time.monotonic()>deadline: raise TimeoutError('two scheduled warm successes per originally active DAG not observed')
            time.sleep(5)
        require_ready(db,directory)
        after=json.loads(docker('inspect','multi-channel-order-platform-airflow-1'))[0]
        assert after['State'].get('Health',{}).get('Status')=='healthy'
        result['owner_after']=dict(id=after['Id'],image=after['Image'],healthy=True)
        assert query(db,'SELECT dag_id,is_paused FROM dag ORDER BY dag_id','airflow_meta')==original
        result['status']='PASS'; result['phase']='retained-delta-active-and-scheduled'
    except BaseException as error:
        result['status']='FAIL'; result['error']=type(error).__name__+': '+str(error)
        # Never abort a bootstrap or resume over an active manual batch.
        # Before publication failure, original image can still be started by ID.
        if stopped and not activated:
            docker('start',owner['Id'])
            result['recovery']='original container started; drain retained, schedules stay paused; inspect exact bootstrap identities'
        raise
    finally:
        save()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-report',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--confirm-local',action='store_true')
    args=parser.parse_args()
    with startup_lock():
        print(json.dumps(run(LocalDB(),args.startup_report,args.report,args.confirm_local)))
