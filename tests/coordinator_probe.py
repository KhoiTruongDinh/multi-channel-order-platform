"""Disposable SQL coordinator recovery checks; never targets owner databases."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]


def inner():
    assert os.environ['PLATFORM_DB_HOST'].startswith('reuse-pg-'), 'disposable host required'
    from unittest.mock import patch
    from orchestration import coordinator as c
    from orchestration import website_workflow as w
    from transformation.batch import connect
    completed=set(); calls=[]; checks=[]
    official_stage=w.run_stage

    def args(name,source='etsy_sim',attempt=1,wait=300):
        execution='reuse-probe:'+name
        a=argparse.Namespace(source=source,execution_id=execution,
            workflow_id=w.identity(execution,'workflow'),batch_id=w.identity(execution,'batch'),
            window_start=None,window_end=None,dag_id=None,airflow_run_id=None,
            validation_mode='runtime',coordinator_attempt=attempt,wait_seconds=wait,
            observed_at=datetime.now(timezone.utc),abort=False)
        with w.connect() as conn: w.ensure_run(conn,a)
        return a

    def stage(a,stage):
        # Test double for business work; only coordination/ownership/wait SQL is real.
        key=(a.workflow_id,stage)
        if key not in completed:
            completed.add(key); calls.append(key)
        if stage=='publish':
            with w.connect() as conn:
                conn.execute("UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=clock_timestamp() WHERE run_id=%s",(a.workflow_id,))

    def expect(error,fn):
        try: fn()
        except error: return
        raise AssertionError('expected '+error.__name__)

    def waits(a,kind):
        with w.connect() as conn:
            return conn.execute('''SELECT w.measurement_id,m.started_at,m.outcome
                FROM ops.coordinator_waits w JOIN ops.execution_measurements m USING(measurement_id)
                WHERE w.run_id=%s AND w.wait_kind=%s ORDER BY w.task_try_number''',
                                (a.workflow_id,kind)).fetchall()

    first=args('first'); second=args('second'); unrelated=args('unrelated','ebay_sim')
    with patch.object(w,'run_stage',side_effect=stage):
        with connect() as release:
            assert release.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0]
            release.commit()
            expect(c.CoordinatorBusy,lambda:c.coordinate(first))
            before=waits(first,'release_slot')
            # Reschedule closes session locks but preserves source ownership.
            fresh=args('first')
            expect(c.CoordinatorBusy,lambda:c.coordinate(fresh))
            assert waits(first,'release_slot')==before
            expect(c.CoordinatorBusy,lambda:c.coordinate(second))
            assert (second.workflow_id,'collect') not in completed
            with connect() as legacy:
                assert not c.source_available(legacy,second)
                from orchestration.polling import claim_slot
                import copy
                legacy_args=copy.copy(second);legacy_args.wait_seconds=0
                expect(TimeoutError,lambda:claim_slot(legacy,legacy_args,source_slot=True))
            expect(c.CoordinatorBusy,lambda:c.coordinate(unrelated))
            assert (unrelated.workflow_id,'collect') in completed
            assert calls.count((first.workflow_id,'collect'))==1
        # Global lock is free, but a later ready source must not overtake first.
        expect(c.CoordinatorBusy,lambda:c.coordinate(unrelated))
        c.coordinate(first)
        assert waits(first,'release_slot')[0][2]=='SUCCEEDED'
        c.coordinate(unrelated)
        c.coordinate(second)
        old_calls=len(calls)
        c.coordinate(first)
        assert len(calls)==old_calls
        checks.extend(['busy-release-frees-session','same-owner-restart','durable-source-exclusion',
                       'independent-source-collection','stage-idempotent-reentry','terminal-owner-handoff',
                       'release-fifo-no-overtaking'])

        expired=args('expired-ticket','ebay_sim',wait=1)
        progress=args('progress-after-expiry','internal_web',wait=1)
        with connect() as release:
            release.execute("SELECT pg_advisory_lock(hashtext('platform-release'))"); release.commit()
            expect(c.CoordinatorBusy,lambda:c.coordinate(expired))
        time.sleep(1.1)
        c.coordinate(progress)
        # Expiry discards release priority, NOT ownership of the failed source.
        with w.connect() as conn:
            assert conn.execute("SELECT run_id FROM ops.source_cycle_owners WHERE source_system='ebay_sim'").fetchone()[0]==expired.workflow_id
        official_stage(expired,'abort')
        checks.append('expired-ticket-no-global-block-or-source-steal')

        timed=args('timed',wait=0)
        with connect() as release:
            release.execute("SELECT pg_advisory_lock(hashtext('platform-release'))"); release.commit()
            expect(TimeoutError,lambda:c.coordinate(timed))
        expect(TimeoutError,lambda:c.coordinate(timed))
        assert waits(timed,'release_slot')[0][2]=='TIMED_OUT'
        resumed=args('timed',attempt=2,wait=0)
        c.coordinate(resumed)
        assert calls.count((resumed.workflow_id,'collect'))==1
        checks.extend(['wait-budget-not-reset','real-retry-new-wait-clock-no-new-business-work'])

        # Interrupted acquisition retains RUNNING owner; never steal it.
        broken=args('broken'); successor=args('successor')
        def interrupted(a,phase):
            if phase=='collect': raise RuntimeError('intentional process interruption')
            stage(a,phase)
        with patch.object(w,'run_stage',side_effect=interrupted):
            expect(RuntimeError,lambda:c.coordinate(broken))
        expect(c.CoordinatorBusy,lambda:c.coordinate(successor))
        # Existing official operator abort, not manual status repair.
    w.run_stage(broken,'abort')
    with patch.object(w,'run_stage',side_effect=stage):
        c.coordinate(successor)
    checks.extend(['interrupted-owner-not-stolen','official-abort-unblocks-successor'])
    with connect() as conn:
        # Reentry cannot bypass an actually active same-source process lock.
        conn.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))',('source-cycle:etsy_sim:7001',));conn.commit()
        expect(c.CoordinatorBusy,lambda:c.coordinate(args('source-fence')))
    checks.append('active-process-source-fencing')
    with w.connect() as conn:
        assert not conn.execute("SELECT 1 FROM raw.raw_records LIMIT 1").fetchone()
    return dict(status='PASS',scope='real coordination SQL; business stages test-double, not load acceptance',checks=checks)


def sensor_check():
    from unittest.mock import patch
    from types import SimpleNamespace
    import pendulum
    from orchestration.dags import polling_orders,etsy_orders
    from orchestration.polling_sensor import PollingCycleSensor
    from airflow.serialization.serialized_objects import DagSerialization
    dags=[polling_orders.website_polling,polling_orders.ebay_polling,etsy_orders.etsy_inbox,etsy_orders.etsy_recovery]
    for dag in dags:
        sensor=dag.get_task('cycle')
        assert isinstance(sensor,PollingCycleSensor) and sensor.mode=='reschedule'
        restored=DagSerialization.from_dict(DagSerialization.to_dict(dag)).get_task('cycle')
        assert restored.source==sensor.source and restored.collection_mode==sensor.collection_mode
        ctx=dict(dag=dag,run_id='scheduled__probe',data_interval_end=pendulum.now('UTC'),
                 ti=SimpleNamespace(try_number=3),params=dict(fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False))
        for code,desired in ((75,False),(0,True)):
            with patch('orchestration.polling_sensor.subprocess.run',return_value=SimpleNamespace(
                    returncode=code,check_returncode=lambda:None)) as run:
                assert sensor.poke(ctx) is desired
                command=run.call_args.args[0]
                assert '--nonblocking' in command and command[command.index('--coordinator-attempt')+1]=='3'
    assert not isinstance(etsy_orders.etsy_replay.get_task('cycle'),PollingCycleSensor)
    assert not isinstance(polling_orders.ebay_polling_replay.get_task('cycle'),PollingCycleSensor)
    return dict(status='PASS',scope='installed Airflow SDK DAG/sensor import and poke; not scheduler runtime',dags=[d.dag_id for d in dags])


def docker_probe():
    token=uuid.uuid4().hex[:12]; pg='reuse-pg-'+token; net='reuse-net-'+token
    worker='reuse-worker-'+token; label='de.probe=reuse-coordinator'
    def docker(*argv,**kwargs):
        r=subprocess.run(['docker',*argv],text=True,encoding='utf-8',capture_output=True,timeout=180,**kwargs)
        if r.returncode:
            raise RuntimeError('disposable Docker command failed: '+r.stderr[-1800:])
        return r.stdout
    try:
        docker('network','create','--internal','--label',label,net)
        docker('run','-d','--name',pg,'--label',label,'--network',net,'--memory','512m','--cpus','1',
               '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:16.15-bookworm')
        for _ in range(40):
            check=subprocess.run(['docker','exec',pg,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True)
            if check.returncode==0: break
            time.sleep(1)
        else: raise RuntimeError('disposable PG startup failed')
        roles=('platform_owner','platform_ingest','platform_transform','platform_publisher','platform_report')
        sql=';'.join('CREATE ROLE '+r+' LOGIN' for r in roles)+'; CREATE DATABASE data_platform OWNER platform_owner;'
        docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres',input=sql)
        def migration(path):
            docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres','-d','data_platform',input=path.read_text())
        migration(ROOT/'migrations/bootstrap/002_database_baseline.sql')
        for path in sorted((ROOT/'migrations/platform').glob('*.sql')): migration(path)
        # Reapply new migrations to prove additive/idempotent setup.
        for name in ('010_etsy_payload_cache.sql','011_coordinator_waits.sql'): migration(ROOT/'migrations/platform'/name)
        image=docker('inspect','--format','{{.Image}}','multi-channel-order-platform-airflow-1').strip()
        common=['run','--rm','--name',worker,'--label',label,'--memory','384m','--network',net]
        # Select code/config directories only: never expose .env or owner runtime.
        for directory in ('orchestration','transformation','transformations','ingestion','infra/dbt','tests'):
            common+=['--mount','type=bind,src='+str(ROOT/directory)+',dst=/review/'+directory+',readonly']
        common+=['-e','PYTHONPATH=/review','-e','PYTHONDONTWRITEBYTECODE=1']
        env=[]
        for key,value in dict(PLATFORM_DB_HOST=pg,PLATFORM_DB_PORT='5432',PLATFORM_INGEST_PASSWORD='disposable',PLATFORM_TRANSFORM_PASSWORD='disposable').items():
            env+=['-e',key+'='+value]
        output=docker(*common,*env,'--entrypoint','/opt/airflow/project-venv/bin/python',image,'/review/tests/coordinator_probe.py','--inner')
        sql_result=json.loads(output.splitlines()[-1])
        # Compile real Jinja/macros/source dependencies using the pinned dbt venv.
        # Artifacts/logs exist only in this disposable worker's /tmp.
        variables=json.dumps(dict(batch_id=str(uuid.UUID(int=1)),mapping_version='s01-v1',
                                  transformation_version='probe',validation_mode='runtime',release_source='etsy_sim'))
        docker(*common,*env,'--entrypoint','/opt/airflow/project-venv/bin/dbt',image,'compile',
               '--project-dir','/review/transformations','--profiles-dir','/review/infra/dbt',
               '--target-path','/tmp/dbt-review','--log-path','/tmp/dbt-logs','--vars',variables)
        # Actually execute pre-hooks/materializations, not just compile their text.
        docker(*common,*env,'--entrypoint','/opt/airflow/project-venv/bin/dbt',image,'build',
               '--project-dir','/review/transformations','--profiles-dir','/review/infra/dbt',
               '--target-path','/tmp/dbt-build-review','--log-path','/tmp/dbt-logs','--vars',variables)
        output=docker(*common,'-e','POLLING_NONBLOCKING=true','--entrypoint','python',image,'/review/tests/coordinator_probe.py','--sensor-check')
        sdk_result=json.loads(output.splitlines()[-1])
        return dict(status='PASS',coordination=sql_result,dbt_compile='PASS',dbt_empty_build='PASS',airflow_sdk=sdk_result)
    finally:
        for name in (worker,pg):
            inspected=subprocess.run(['docker','inspect','--format','{{index .Config.Labels "de.probe"}}',name],capture_output=True,text=True)
            if inspected.returncode==0 and inspected.stdout.strip()=='reuse-coordinator':
                docker('rm','-f',name)
        inspected=subprocess.run(['docker','network','inspect','--format','{{index .Labels "de.probe"}}',net],capture_output=True,text=True)
        if inspected.returncode==0 and inspected.stdout.strip()=='reuse-coordinator': docker('network','rm',net)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--docker',action='store_true');mode.add_argument('--inner',action='store_true');mode.add_argument('--sensor-check',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.report and args.report.exists(): parser.error('choose a new report path')
    result=inner() if args.inner else sensor_check() if args.sensor_check else docker_probe()
    if args.report:
        args.report.parent.mkdir(exist_ok=True,parents=True)
        with args.report.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    print(json.dumps(result))
