"""Explicit owner-authorized Airflow maintenance window for temporal M08B only."""
import argparse
import json
import time
import uuid

from test_support import m08a as guard
from test_support.m08b_temporal import TemporalCampaign


def pauses(postgres):
    return json.loads(guard.owner_sql(postgres,
        "SELECT coalesce(json_agg(t ORDER BY dag_id),'[]') FROM (SELECT dag_id,is_paused FROM dag) t;",
        'airflow_meta'))


def state(identity):
    value=json.loads(guard.docker('inspect',identity))[0]
    guard.require(value['Config']['Labels'].get('com.docker.compose.project')==guard.OWNER,
        'Not the owner project')
    guard.require(value['Config']['Labels'].get('com.docker.compose.service')=='airflow',
        'Not owner Airflow')
    return value['State']


def restore(identity, timeout=300):
    guard.docker('start',identity)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        current=state(identity)
        if current.get('Running') and current.get('Health',{}).get('Status')=='healthy':
            print('Owner Airflow restored healthy: '+identity[:12],flush=True)
            return
        time.sleep(10)
    raise guard.SafetyError('Owner Airflow restoration did not become healthy; inspect exact container '+identity)


def run_window(confirmed, seed=17, count=4, local_replay=False, local_realtime=False):
    guard.require(confirmed,'Explicit current-task owner maintenance permission/flag required')
    guard.require(not (local_replay and local_realtime),'Choose one local clock mode')
    postgres=guard.owner_container()
    guard.owner_idle(postgres)
    ids=guard.docker('ps','-q','--filter','label=com.docker.compose.project='+guard.OWNER,
        '--filter','label=com.docker.compose.service=airflow').split()
    guard.require(len(ids)==1,'Exactly one running owner Airflow required')
    airflow=ids[0]
    current=state(airflow)
    guard.require(current.get('Running') and current.get('Health',{}).get('Status')=='healthy',
        'Owner Airflow must be healthy before maintenance')
    root=guard.ROOT/'runtime/isolated'/('window-'+uuid.uuid4().hex)
    guard.exact_path(root,root)
    root.mkdir(parents=True,exist_ok=False)
    report=dict(started_at=guard.utc(),owner_airflow=airflow,owner_postgres=postgres,
        protected_before=guard.protected_signature(postgres),pauses_before=pauses(postgres),
        postgres_system_before=guard.owner_sql(postgres,'SELECT system_identifier FROM pg_control_system();','postgres'),
        status='RUNNING',owner_restore='NOT_RUN')
    # Durable pre-stop snapshot survives external process-tree termination.
    with (root/'owner-window-start.json').open('x',encoding='utf-8') as handle:
        json.dump(report,handle,indent=2)
    # From the stop ATTEMPT onward, restoration runs even on init/preflight/test failure.
    try:
        print('Stopping ONLY idle owner Airflow '+airflow,flush=True)
        guard.docker('stop','--timeout','30',airflow)
        identity=(guard.init(profile='m08b',backend='s02-pg',local_playback=True) if local_replay or local_realtime
                  else guard.init(profile='m08b',backend='s02-pg'))
        report['test_id']=identity
        h=guard.Harness(identity)
        if local_replay or local_realtime:
            from test_support.m08b_local_scheduled import LocalScheduledCampaign
            guard.accept(h,baseline_fn=lambda env:LocalScheduledCampaign(env,seed,'realtime' if local_realtime else 'replay').run())
        else:
            guard.accept(h,baseline_fn=lambda env:TemporalCampaign(env,seed,'continuous',count).run())
        report['status']='PASS'
    except BaseException as error:
        report.update(status='FAIL',failure=type(error).__name__+': '+str(error))
        raise
    finally:
        try:
            restore(airflow)
            report['owner_restore']='HEALTHY'
            guard.owner_idle(postgres)
            report['protected_after']=guard.protected_signature(postgres)
            report['pauses_after']=pauses(postgres)
            report['postgres_system_after']=guard.owner_sql(postgres,
                'SELECT system_identifier FROM pg_control_system();','postgres')
            guard.require(report['protected_after']==report['protected_before'],'Owner data signature changed')
            guard.require(report['pauses_after']==report['pauses_before'],'Owner DAG pause states changed')
            guard.require(report['postgres_system_after']==report['postgres_system_before'],'Owner PostgreSQL identity changed')
            report['owner_protection']='PASS'
        except BaseException as error:
            report.update(status='FAIL',owner_protection='FAIL',restore_failure=str(error))
            raise
        finally:
            report['finished_at']=guard.utc()
            with (root/'owner-window.json').open('x',encoding='utf-8') as handle:
                json.dump(report,handle,indent=2)
            print('Owner window evidence: '+str(root.relative_to(guard.ROOT)),flush=True)
    print('M08B scheduled window PASS; owner restored, pause/data/system identities unchanged',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-owner-airflow-window',action='store_true')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--local-replay',action='store_true',help='Test the local logical-clock replay path')
    mode.add_argument('--local-realtime',action='store_true',help='Test rolling-date preparation and actual-clock schedules')
    args=parser.parse_args()
    run_window(args.confirm_owner_airflow_window,local_replay=args.local_replay,local_realtime=args.local_realtime)
