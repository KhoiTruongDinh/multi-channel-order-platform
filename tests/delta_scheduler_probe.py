"""Opt-in real scheduler/retry/restart gate; never activates delta on main."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'multi-channel-order-platform-airflow-1'
OWNER_PG = 'multi-channel-order-platform-postgres-1'
LABEL = 'delta-scheduler'


def sdk_check():
    import runpy
    from airflow.serialization.serialized_objects import DagSerialization
    dags=runpy.run_path(str(ROOT/'tests/dags/delta_scheduled.py'))
    dag=dags['website_polling']
    fault=os.environ.get('DELTA_SCHEDULER_ALL_SOURCES')!='true'
    assert dag.get_task('cycle').mode=='reschedule'
    for value in (dag,DagSerialization.from_dict(DagSerialization.to_dict(dag))):
        assert value.params['fault_after_freeze_once'] is fault
        assert all(task.params['fault_after_freeze_once'] is fault for task in value.tasks)
    if not fault:
        for name in ('ebay_polling','etsy_inbox','etsy_recovery'):
            assert dags[name].get_task('cycle').mode=='reschedule'
            for value in (dags[name],DagSerialization.from_dict(DagSerialization.to_dict(dags[name]))):
                assert not any(value.params[key] for key in ('fault_after_raw_once','fault_after_freeze_once','inject_test_failure'))
                assert all(not any(task.params[key] for key in ('fault_after_raw_once','fault_after_freeze_once','inject_test_failure')) for task in value.tasks)
    print(json.dumps(dict(status='PASS',scope='real SDK test-DAG fault params survive task precedence and serialization')))


def prepare():
    assert os.environ['PLATFORM_DB_HOST'].startswith('delta-sched-pg-')
    import psycopg
    from simulator.website_playback import TABLES, DELETE_ORDER, insert_rows, validate
    from transformation.delta_plan import compile_plan, load
    from transformation.delta_runtime import source_lock, freeze, build
    from transformation.delta_publish import audited_publish
    stamp = datetime.now(timezone.utc)
    value = json.loads((ROOT/'fixtures/s01/source_states/website/0901.json').read_text())
    for order in value['orders']:
        order['updated_at'] = (stamp-timedelta(seconds=1)).isoformat()
    validate(value)
    with psycopg.connect(host=os.environ['PLATFORM_DB_HOST'], dbname='website_source', user='postgres') as conn:
        with conn.cursor() as cursor:
            for table in DELETE_ORDER:
                cursor.execute('DELETE FROM public.'+table)
            for table in TABLES:
                insert_rows(cursor, table, value[table])
    subprocess.run([sys.executable, '-m', 'ingestion.website', '--window-start',
        (stamp-timedelta(hours=1)).isoformat(), '--window-end', stamp.isoformat(),
        '--observed-at', stamp.isoformat(), '--checkpoint-stream', 'orders_polling',
        '--execution-id', 'delta-scheduler-bootstrap'], check=True)
    sources=('internal_web','ebay_sim','etsy_sim') if os.environ.get('DELTA_SCHEDULER_ALL_SOURCES')=='true' else ('internal_web',)
    plans={}
    for source in sources:
        path = Path('/tmp/delta-plans')/(source+'.json')
        compile_plan(source, 's01-v1', 'delta-scheduler-v1', path)
        plan = load(path)
        batch = uuid.uuid4()
        with source_lock(plan) as conn:
            freeze(conn, plan, batch, uuid.uuid4(), bootstrap=True)
            build(conn, plan, batch)
            audited_publish(plan, batch, uuid.uuid4())
        plans[source]=dict(plan_sha256=plan['plan_sha256'], bootstrap=str(batch))
    print(json.dumps(dict(**plans['internal_web'],plans=plans)))


def run_all_sources(docker,query,wait,pg,scheduler,source_service,result,save):
    """Use a physical Etsy source fence to prove worker-free real reschedule."""
    names=('website_polling','ebay_polling','etsy_inbox','etsy_recovery')
    wait(lambda:len(query(pg,'airflow_meta',
        "SELECT dag_id FROM dag WHERE dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')"))==4,
        'four production scheduled DAGs discovered')
    # Hold only the disposable Etsy source. Actual sensor pokes must reschedule,
    # leaving executor capacity for Website/eBay; never alter task state in SQL.
    hold=("import os,time; from pathlib import Path; import psycopg; "
          "c=psycopg.connect(host=os.environ['PLATFORM_DB_HOST'],dbname='data_platform',user='postgres',application_name='delta-scheduled-fence'); "
          "c.execute(\"SELECT pg_advisory_lock(hashtextextended('source-cycle:etsy_sim:7001',0))\"); c.commit(); "
          "deadline=time.monotonic()+240\n"
          "while not Path('/tmp/release-etsy-fence').exists() and time.monotonic()<deadline: time.sleep(1)\n"
          "c.close()")
    docker('exec','-d',scheduler,'/opt/airflow/project-venv/bin/python','-c',hold)
    wait(lambda:bool(query(pg,'data_platform',
        "SELECT pid FROM pg_stat_activity WHERE application_name='delta-scheduled-fence' AND state='idle'")),
        'disposable physical Etsy source fence held',30)
    docker('exec',scheduler,'python','-c',
        "from urllib.request import Request,urlopen; "
        "r=urlopen(Request('http://"+source_service+":18084/advance',data=b''),timeout=20); assert r.status==204")
    for name in names:
        docker('exec',scheduler,'airflow','dags','unpause',name,timeout=90)
    def contention_seen():
        waits=query(pg,'data_platform',"SELECT p.airflow_dag_id,w.task_try_number,m.outcome FROM ops.coordinator_waits w JOIN ops.pipeline_runs p USING(run_id) JOIN ops.execution_measurements m USING(measurement_id) WHERE w.wait_kind='source_slot' AND p.airflow_dag_id IN ('etsy_inbox','etsy_recovery')")
        reschedules=query(pg,'airflow_meta',"SELECT t.dag_id,t.try_number,r.start_date,r.end_date FROM task_reschedule r JOIN task_instance t ON t.id=r.ti_id WHERE t.dag_id IN ('etsy_inbox','etsy_recovery')")
        independent=query(pg,'airflow_meta',"SELECT dag_id,run_id FROM dag_run WHERE dag_id IN ('website_polling','ebay_polling') AND state='success'")
        blocked=query(pg,'data_platform',"SELECT t.run_id FROM ops.task_attempts t JOIN ops.pipeline_runs p USING(run_id) WHERE p.airflow_dag_id IN ('etsy_inbox','etsy_recovery') AND t.task_name='collect'")
        result['contention']=dict(waits=waits,reschedules=reschedules,independent_successes=independent,etsy_collects_while_fenced=blocked)
        return ({r['airflow_dag_id'] for r in waits}=={'etsy_inbox','etsy_recovery'}
            and {r['dag_id'] for r in reschedules}=={'etsy_inbox','etsy_recovery'}
            and {r['dag_id'] for r in independent}=={'website_polling','ebay_polling'})
    wait(contention_seen,'both Etsy sensors reschedule while Website/eBay publish',180)
    assert not result['contention']['etsy_collects_while_fenced']
    assert query(pg,'data_platform',"SELECT pid FROM pg_stat_activity WHERE application_name='delta-scheduled-fence'"), 'fence expired before assertions'
    save()
    docker('exec',scheduler,'python','-c',"from pathlib import Path; Path('/tmp/release-etsy-fence').touch()")
    def completed():
        rows=query(pg,'airflow_meta',"SELECT dag_id,count(*) AS successes FROM dag_run WHERE state='success' GROUP BY dag_id")
        result['scheduled_success_counts']=rows
        return all(next((r['successes'] for r in rows if r['dag_id']==name),0)>=2 for name in names)
    wait(completed,'two actual scheduled successes for each of four DAGs',600)
    docker('exec',scheduler,'python','-c',
        'from pathlib import Path; p=Path("/opt/airflow/state/polling-drain"); p.parent.mkdir(parents=True,exist_ok=True); p.touch()')
    wait(lambda:not query(pg,'airflow_meta',"SELECT run_id FROM dag_run WHERE state IN ('queued','running')"),
         'all test schedules drained',300)
    result['final_airflow_runs']=query(pg,'airflow_meta','SELECT dag_id,run_id,state,start_date,end_date FROM dag_run ORDER BY start_date')
    assert all(r['state']=='success' for r in result['final_airflow_runs'])
    result['final_airflow_tasks']=query(pg,'airflow_meta','SELECT dag_id,run_id,task_id,state,try_number FROM task_instance ORDER BY start_date')
    cycles=query(pg,'data_platform',"SELECT p.run_id,p.airflow_dag_id,p.airflow_run_id,p.source_system,p.status,p.batch_id,c.settings FROM ops.pipeline_runs p JOIN ops.polling_cycles c USING(run_id) ORDER BY p.finished_at,p.started_at")
    result['cycles']=cycles
    assert cycles and all(c['status']=='SUCCEEDED' for c in cycles)
    assert all(c['settings']['delta_plan_sha256']==result['bootstrap']['plans'][c['source_system']]['plan_sha256'] for c in cycles)
    result['attempts']=query(pg,'data_platform',"SELECT t.run_id,t.task_name,t.attempt_number,t.status FROM ops.task_attempts t JOIN ops.pipeline_runs p USING(run_id) WHERE p.airflow_dag_id IS NOT NULL ORDER BY t.started_at")
    assert all(t['attempt_number']==1 and t['status']=='SUCCEEDED' for t in result['attempts'])
    assert all(t['try_number']==1 for t in result['final_airflow_tasks'] if t['task_id']=='cycle')
    for cycle in cycles:
        tasks=[t for t in result['attempts'] if t['run_id']==cycle['run_id']]
        for stage in ('collect','freeze','build_and_test','publish'):
            assert len([t for t in tasks if t['task_name']==stage and t['status']=='SUCCEEDED'])==1,(cycle,stage,tasks)
    result['orders']=query(pg,'data_platform','SELECT source_system,source_order_id FROM core.orders_current ORDER BY source_system,source_order_id')
    assert sum(r['source_system']=='ebay_sim' for r in result['orders'])==1
    assert sum(r['source_system']=='etsy_sim' for r in result['orders'])==2
    result['webhook_deliveries']=query(pg,'data_platform','SELECT accepted,response_status,signature_valid FROM ops.webhook_delivery_attempts')
    assert len(result['webhook_deliveries'])==1 and result['webhook_deliveries'][0]['accepted']
    # Validated receipt evidence is a separate raw row from the HTTP audit.
    # Follow the collector's explicit http_raw_id link, not equality of raw IDs.
    result['etsy_detail_work']=query(pg,'data_platform',"SELECT a.airflow_dag_id,count(*) AS details FROM raw.raw_records r JOIN ops.etsy_http_attempts h ON h.raw_record_id=(r.metadata->>'http_raw_id')::uuid JOIN ops.pipeline_runs a ON a.run_id=h.collection_run_id WHERE r.resource_type='etsy_receipt' GROUP BY a.airflow_dag_id")
    assert {r['airflow_dag_id'] for r in result['etsy_detail_work']}=={'etsy_inbox','etsy_recovery'}
    # Verify actual HTTP detail acquisitions through the retained work ledger,
    # including the receipt omitted from webhook notification.
    result['etsy_receipt_raw']=query(pg,'data_platform',"SELECT parsed_payload->>'receipt_id' AS receipt_id,count(*) AS observations FROM raw.raw_records WHERE resource_type='etsy_receipt' GROUP BY parsed_payload->>'receipt_id'")
    assert len(result['etsy_receipt_raw'])==2
    result['snapshot_counts']=query(pg,'data_platform',"SELECT source_system,source_order_id,count(*) AS snapshots FROM core.order_snapshot_history GROUP BY source_system,source_order_id ORDER BY source_system,source_order_id")
    assert all(r['snapshots']==1 for r in result['snapshot_counts'] if r['source_system'] in ('ebay_sim','etsy_sim')), 'duplicate acquisition fabricated source snapshots'
    result['unconsumed_frozen_inputs']=query(pg,'data_platform',"SELECT i.batch_id,i.raw_record_id FROM ops.delta_new_inputs i JOIN ops.delta_batches d USING(batch_id) LEFT JOIN ops.delta_seen_raw s ON s.plan_sha256=d.plan_sha256 AND s.raw_record_id=i.raw_record_id WHERE s.raw_record_id IS NULL")
    assert not result['unconsumed_frozen_inputs']
    result['publication_pointers']=query(pg,'data_platform','SELECT publication_name,batch_id FROM ops.publication_state ORDER BY publication_name')
    for source,publication in (('internal_web','website_orders'),('ebay_sim','ebay_orders'),('etsy_sim','etsy_orders')):
        latest=next(c for c in reversed(cycles) if c['source_system']==source)
        assert next(r['batch_id'] for r in result['publication_pointers'] if r['publication_name']==publication)==latest['batch_id']
    result['source_waits']=query(pg,'data_platform',"SELECT p.airflow_dag_id,w.task_try_number,m.outcome FROM ops.coordinator_waits w JOIN ops.pipeline_runs p USING(run_id) JOIN ops.execution_measurements m USING(measurement_id)")
    assert all(r['task_try_number']==1 and r['outcome']=='SUCCEEDED' for r in result['source_waits'])


def run_probe(report, allow_owner_stop, all_sources=False, mapping_check=False):
    if not allow_owner_stop:
        raise ValueError('explicit --allow-owner-idle-stop is required for this 4GB topology')
    token = uuid.uuid4().hex[:12]
    pg, net, worker, scheduler = ('delta-sched-'+name+'-'+token for name in ('pg','net','prepare','airflow'))
    source_service='delta-sched-sources-'+token
    evidence = ROOT/'runtime'/('delta-scheduler-'+token)
    evidence.mkdir(parents=True, exist_ok=False)
    result = dict(status='RUNNING', identity=token, scope='one real Website scheduled DAG/retry/container restart; not load or all-source scheduler acceptance')
    if all_sources:
        result['scope']='four production scheduled DAGs, HTTP marketplaces, signed webhook and same-source reschedule; not load acceptance'
    owner = None
    owner_stopped = False
    drain_created = False
    pause_before = None

    def save():
        result['updated_at']=datetime.now(timezone.utc).isoformat()
        (evidence/'journal.json').write_text(json.dumps(result, indent=2), encoding='utf-8')

    def docker(*args, payload=None, timeout=90):
        done = subprocess.run(['docker', *map(str,args)], input=payload, capture_output=True,
                              text=True, encoding='utf-8', timeout=timeout)
        if done.returncode:
            # No owner environment or unfiltered container logs in exceptions.
            raise RuntimeError('Docker command failed: '+str(args[:3])+' '+done.stderr[-1500:])
        return done.stdout.strip()

    def inspect(name):
        return json.loads(docker('inspect',name))[0]

    def owner_identity():
        current=inspect(OWNER)
        labels=current['Config']['Labels']
        assert labels.get('com.docker.compose.project')=='multi-channel-order-platform'
        assert labels.get('com.docker.compose.service')=='airflow'
        if owner:
            assert current['Id']==owner['Id'] and current['Image']==owner['Image']
        return current

    def query(container, database, statement):
        text=docker('exec',container,'psql','-XAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',database,
                    '-c','SELECT coalesce(json_agg(t),\'[]\'::json) FROM ('+statement+') t')
        return json.loads(text)

    def main_idle():
        runs=query(OWNER_PG,'airflow_meta',"SELECT dag_id,run_id FROM dag_run WHERE state IN ('queued','running')")
        batches=query(OWNER_PG,'data_platform',"SELECT batch_id,status FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')")
        owners=query(OWNER_PG,'data_platform',"SELECT o.run_id FROM ops.source_cycle_owners o JOIN ops.pipeline_runs p USING(run_id) WHERE p.status NOT IN ('SUCCEEDED','FAILED')")
        result['last_owner_idle_check']=dict(active_runs=runs,active_batches=batches,nonterminal_owners=owners)
        return not (runs or batches or owners)

    def wait(predicate, description, seconds=420):
        deadline=time.monotonic()+seconds
        while True:
            if predicate():
                return
            if time.monotonic()>deadline:
                raise TimeoutError(description)
            time.sleep(3)

    def common(name, memory):
        args=['run','--name',name,'--label','de.probe='+LABEL,'--network',net,
              '--memory',memory,'--workdir','/review']
        for folder in ('transformation','transformations','orchestration','ingestion','simulator','infra/dbt','tests','fixtures/s01'):
            args+=['--mount','type=bind,src='+str(ROOT/folder)+',dst=/review/'+folder+',readonly']
        for key,value in dict(PROJECT_ROOT='/review',PYTHONPATH='/review',PYTHONDONTWRITEBYTECODE='1',
                PLATFORM_DB_HOST=pg,PLATFORM_INGEST_PASSWORD='disposable',
                PLATFORM_TRANSFORM_PASSWORD='disposable',PLATFORM_PUBLISHER_PASSWORD='disposable',
                WEBSITE_DB_HOST=pg,WEBSITE_READER_PASSWORD='disposable').items():
            args+=['-e',key+'='+value]
        if all_sources:
            from delta_scheduler_sources import SECRET
            for key,value in dict(DELTA_SCHEDULER_ALL_SOURCES='true',
                EBAY_ORIGIN='http://'+source_service+':18081',
                EBAY_PUBLIC_ORIGIN='http://'+source_service+':18081',EBAY_SIM_TOKEN='disposable',
                ETSY_ORIGIN='http://'+source_service+':18082',ETSY_SIM_TOKEN='disposable',
                ETSY_SIGNING_SECRET=SECRET).items():
                args+=['-e',key+'='+value]
        return args

    def diagnostics():
        """Keep private task logs on success too: retries must be explainable."""
        current=inspect(scheduler)
        assert current['Config']['Labels'].get('de.probe')==LABEL
        result['task_reschedules']=query(pg,'airflow_meta',
            'SELECT * FROM task_reschedule ORDER BY start_date')
        result['task_instance_history']=query(pg,'airflow_meta',
            'SELECT dag_id,run_id,task_id,try_number,state,start_date,end_date,retry_reason '
            'FROM task_instance_history ORDER BY start_date')
        # Native run IDs contain ':' and cannot be extracted as Windows paths.
        # Archive inside the disposable container; copy a single portable file.
        docker('exec',scheduler,'tar','-C','/opt/airflow','-czf','/tmp/delta-task-logs.tar.gz','logs',timeout=60)
        docker('cp',scheduler+':/tmp/delta-task-logs.tar.gz',evidence/'test-task-logs.tar.gz',timeout=60)
        with tarfile.open(evidence/'test-task-logs.tar.gz','r:gz') as archive:
            task_logs=[entry for entry in archive.getmembers() if entry.isfile() and '/task_id=' in entry.name]
            assert task_logs, 'private task log archive is empty'
            result['archived_task_log_files']=len(task_logs)
        logged=subprocess.run(['docker','logs','--tail','2000',scheduler],capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert logged.returncode==0
        (evidence/'test-standalone-tail.txt').write_text('\n'.join(
            line for line in (logged.stdout+'\n'+logged.stderr).splitlines()
            if not any(word in line.lower() for word in ('password','token','secret'))),encoding='utf-8')
        result['task_logs_archive']=str(evidence/'test-task-logs.tar.gz')
        save()

    try:
        owner=owner_identity()
        assert owner['State']['Running'], 'owner must initially be running'
        assert owner['State'].get('Health',{}).get('Status')=='healthy', 'owner must initially be healthy'
        pause_before=query(OWNER_PG,'airflow_meta','SELECT dag_id,is_paused FROM dag ORDER BY dag_id')
        result['owner_before']=dict(id=owner['Id'],image=owner['Image'],pause_states=pause_before)
        signal=docker('exec',owner['Id'],'python','-c',
            'from pathlib import Path; print(Path("/opt/airflow/state/polling-drain").is_file())')
        result['owner_drain_before']=signal
        save()
        if signal=='False':
            drain_created=True
            docker('exec',owner['Id'],'python','-c',
                'from pathlib import Path; p=Path("/opt/airflow/state/polling-drain"); p.parent.mkdir(parents=True,exist_ok=True); '
                'f=p.open("x"); f.write("'+token+'"); f.close()')
        result['phase']='owner-draining-with-retries-runnable'
        save()
        print('Waiting for main idle; no task state or pause changes', flush=True)
        quiet_since=None
        def quiet_owner():
            nonlocal quiet_since
            if not main_idle():
                quiet_since=None
                return False
            if quiet_since is None:
                quiet_since=time.monotonic()
            # A scheduler may materialize an interval already computed before
            # drain. Require quiet across parser/scheduler ticks, within600s.
            return time.monotonic()-quiet_since>=15
        wait(quiet_owner,'owner did not reach stable idle; no automatic abort',seconds=600)
        assert main_idle()
        owner_identity()
        owner_stopped=True  # Restore even if Docker reports a timeout after stop.
        result['phase']='owner-idle-stop-intent'
        save()
        docker('stop','--time','30',owner['Id'],timeout=60)
        assert main_idle(), 'work arrived at owner stop; restore immediately'
        result['phase']='owner-stopped-idle'
        save()

        docker('network','create','--internal','--label','de.probe='+LABEL,net)
        docker('run','-d','--name',pg,'--label','de.probe='+LABEL,'--network',net,
               '--memory','384m','--cpus','1','--tmpfs','/var/lib/postgresql/data',
               '-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:16.15-bookworm')
        wait(lambda:subprocess.run(['docker','exec',pg,'pg_isready','-U','postgres'],capture_output=True).returncode==0,
             'test PostgreSQL readiness',60)
        roles=('platform_owner','platform_ingest','platform_transform','platform_publisher','platform_report','website_owner','website_reader','airflow_app')
        docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres',payload=
            ';'.join('CREATE ROLE '+r+' LOGIN' for r in roles)+'; CREATE DATABASE data_platform OWNER platform_owner; CREATE DATABASE website_source OWNER website_owner; CREATE DATABASE airflow_meta OWNER airflow_app;')
        def migrate(path,db='data_platform'):
            docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres','-d',db,payload=path.read_text())
        migrate(ROOT/'migrations/bootstrap/002_database_baseline.sql')
        migrate(ROOT/'migrations/bootstrap/002_database_baseline.sql','website_source')
        migrate(ROOT/'migrations/website_source/001_schema.sql','website_source')
        for path in sorted((ROOT/'migrations/platform').glob('*.sql')):
            migrate(path)
        if all_sources:
            docker(*common(source_service,'192m'),'-d','--entrypoint','/opt/airflow/project-venv/bin/python',
                owner['Image'],'/review/tests/delta_scheduler_sources.py')
        output=docker(*common(worker,'512m'),'--entrypoint','/opt/airflow/project-venv/bin/python',
                      owner['Image'],'/review/tests/delta_scheduler_probe.py','--prepare',timeout=360)
        result['bootstrap']=json.loads(output.splitlines()[-1])
        docker('cp',worker+':/tmp/delta-plans',evidence/'plans')
        # Stop the exited preparation container before starting the scheduler.
        args=common(scheduler,'1536m')
        args+=['-d','--mount','type=bind,src='+str(evidence/'plans')+',dst=/delta-plans,readonly',
               '--mount','type=bind,src='+str(ROOT/'tests/dags')+',dst=/opt/airflow/dags,readonly']
        environment=dict(AIRFLOW__DATABASE__SQL_ALCHEMY_CONN='postgresql+psycopg2://airflow_app:disposable@'+pg+':5432/airflow_meta',
            AIRFLOW__CORE__EXECUTOR='LocalExecutor',AIRFLOW__CORE__PARALLELISM='1',
            AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG='1',AIRFLOW__CORE__LOAD_EXAMPLES='false',
            AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION='true',AIRFLOW__API__WORKERS='1',
            AIRFLOW__DAG_PROCESSOR__PARSING_PROCESSES='1',AIRFLOW__DAG_PROCESSOR__MIN_FILE_PROCESS_INTERVAL='5',
            POLLING_NONBLOCKING='true',POLLING_LIVE_CURRENT_TIME='true',POLLING_SLOT_WAIT_SECONDS='300',
            POLLING_DELTA_PLAN_DIR='/delta-plans',POLLING_MAPPING_VERSION='s01-v1',
            WEBSITE_POLL_INTERVAL_SECONDS='15',POLL_OVERLAP_SECONDS='3600',
            WEBSITE_POLL_INITIAL_START=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
        if all_sources:
            environment.update(AIRFLOW__CORE__PARALLELISM='2',
                EBAY_POLL_INTERVAL_SECONDS='15',ETSY_INBOX_INTERVAL_SECONDS='15',
                ETSY_RECOVERY_INTERVAL_SECONDS='15',
                EBAY_POLL_INITIAL_START=environment['WEBSITE_POLL_INITIAL_START'],
                ETSY_RECOVERY_INITIAL_START=environment['WEBSITE_POLL_INITIAL_START'])
        for key,value in environment.items():
            args+=['-e',key+'='+value]
        docker(*args,'--entrypoint','python',owner['Image'],'-m','orchestration.airflow_local')
        result['phase']='test-scheduler-started'
        save()
        def healthy():
            check=subprocess.run(['docker','exec',scheduler,'python','-m','orchestration.airflow_health'],capture_output=True)
            return check.returncode==0
        wait(healthy,'test Airflow health',420)
        docker('exec',scheduler,'python','/review/tests/delta_scheduler_probe.py','--sdk-check',timeout=90)
        wait(lambda:bool(query(pg,'airflow_meta',"SELECT dag_id FROM dag WHERE dag_id='website_polling'")),
             'test DAG discovery')
        # Source change only in the disposable DB. Collector remains read-only.
        docker('exec',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres','-d','website_source','-c',
               'UPDATE public.orders SET updated_at=clock_timestamp()')
        if all_sources:
            run_all_sources(docker,query,wait,pg,scheduler,source_service,result,save)
            diagnostics()
            result['status']='PASS'
            result['phase']='all-source-scheduled-and-contention-verified'
            return result
        docker('exec',scheduler,'airflow','dags','unpause','website_polling',timeout=90)
        def failed_freeze():
            rows=query(pg,'data_platform',"SELECT p.run_id,p.airflow_run_id,p.batch_id FROM ops.pipeline_runs p JOIN ops.task_attempts t USING(run_id) WHERE p.airflow_dag_id='website_polling' AND t.task_name='freeze' AND t.status<>'SUCCEEDED'")
            if not rows:
                return False
            row=rows[0]
            waiting=query(pg,'airflow_meta',"SELECT state,try_number FROM task_instance WHERE dag_id='website_polling' AND task_id='cycle' AND run_id='"+row['airflow_run_id']+"' AND state='up_for_retry'")
            if waiting:
                result['interrupted_cycle']=row
                result['retry_before_restart']=waiting
                return True
            return False
        wait(failed_freeze,'scheduled freeze fault reached real Airflow retry',300)
        docker('stop','--time','30',scheduler,timeout=60)
        docker('start',scheduler)
        result['restart_started_at']=datetime.now(timezone.utc).isoformat()
        result['phase']='test-scheduler-restarted-between-real-attempts'
        save()
        wait(healthy,'restarted test Airflow health',420)
        def completed():
            runs=query(pg,'airflow_meta',"SELECT run_id,state,end_date FROM dag_run WHERE dag_id='website_polling' AND run_type='scheduled' AND state='success' AND end_date>='"+result['restart_started_at']+"' ORDER BY start_date")
            result['scheduled_successes_after_restart']=runs
            return len(runs)>=2
        wait(completed,'two real scheduled successes after restart',420)
        docker('exec',scheduler,'python','-c',
               'from pathlib import Path; p=Path("/opt/airflow/state/polling-drain"); p.parent.mkdir(parents=True,exist_ok=True); p.touch()')
        wait(lambda:not query(pg,'airflow_meta',"SELECT run_id FROM dag_run WHERE dag_id='website_polling' AND state IN ('queued','running')"),
             'test schedules drained',240)
        cycles=query(pg,'data_platform',"SELECT p.run_id,p.airflow_run_id,p.status,p.batch_id,c.settings FROM ops.pipeline_runs p JOIN ops.polling_cycles c USING(run_id) WHERE p.airflow_dag_id='website_polling' ORDER BY p.started_at")
        result['cycles']=cycles
        result['final_airflow_runs']=query(pg,'airflow_meta',"SELECT run_id,state,end_date FROM dag_run WHERE dag_id='website_polling' ORDER BY start_date")
        assert result['final_airflow_runs'] and all(r['state']=='success' for r in result['final_airflow_runs']), 'test DAG has a non-success terminal run'
        assert any(r['run_id']==result['interrupted_cycle']['airflow_run_id'] and r['state']=='success' for r in result['final_airflow_runs']), 'interrupted DAG itself did not succeed'
        result['final_airflow_tasks']=query(pg,'airflow_meta',"SELECT run_id,task_id,state,try_number FROM task_instance WHERE dag_id='website_polling' ORDER BY start_date")
        assert all(t['try_number']==2 for t in result['final_airflow_tasks'] if t['task_id']=='cycle'), 'restart consumed an unexpected infrastructure retry'
        assert cycles and all(c['status']=='SUCCEEDED' for c in cycles), 'non-success workflow after drain'
        assert all(c['settings']['delta_plan_sha256']==result['bootstrap']['plan_sha256'] for c in cycles)
        result['attempts']=query(pg,'data_platform',"SELECT t.run_id,t.task_name,t.attempt_number,t.status FROM ops.task_attempts t JOIN ops.pipeline_runs p USING(run_id) WHERE p.airflow_dag_id='website_polling' ORDER BY t.started_at")
        original=result['interrupted_cycle']['run_id']
        attempts=[a for a in result['attempts'] if a['run_id']==original]
        assert len([a for a in attempts if a['task_name']=='collect'])==1
        assert [a['attempt_number'] for a in attempts if a['task_name']=='freeze']==[1,2]
        assert any(a['task_name']=='publish' and a['status']=='SUCCEEDED' for a in attempts)
        pointer=query(pg,'data_platform',"SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'")
        assert pointer[0]['batch_id']==cycles[-1]['batch_id'], 'publication pointer not latest scheduled cycle'
        diagnostics()
        if mapping_check:
            # Finish the real scheduler gate before the independent full-dbt
            # mapping oracle. Do not run a second scheduler on the4GB topology.
            docker('stop','--time','30',scheduler,timeout=60)
            result['phase']='private-mapping-and-full-dbt-gate'
            save()
            mapping_report=evidence/'mapping-report.json'
            done=subprocess.run([sys.executable,str(ROOT/'tests/delta_runtime_probe.py'),
                '--docker','--report',str(mapping_report)],capture_output=True,text=True,
                encoding='utf-8',timeout=1800,cwd=ROOT)
            if done.returncode:
                (evidence/'mapping-failure.txt').write_text(done.stderr[-6000:]+done.stdout[-6000:],encoding='utf-8')
                raise RuntimeError('private mapping/full-dbt gate failed; inspect scoped evidence')
            checked=json.loads(mapping_report.read_text(encoding='utf-8'))
            assert checked['status']=='PASS'
            case=next(c for c in checked['checks'] if isinstance(c,dict) and 'retained_source_snapshots' in c)
            assert case['status']=='PASS'
            result['mapping_gate']=dict(report=str(mapping_report),**case)
        result['status']='PASS'
        result['phase']='test-scheduled-retry-and-restart-verified'
    except Exception as error:
        result['status']='FAIL'
        result['error']=type(error).__name__+': '+str(error)
        save()
        # Preserve bounded scope-local diagnostics before cleanup; never owner logs.
        try:
            current=inspect(scheduler)
            if current['Config']['Labels'].get('de.probe')==LABEL:
                out=docker('logs','--tail','200',scheduler)
                (evidence/'test-standalone-tail.txt').write_text('\n'.join(
                    line for line in out.splitlines() if not any(word in line.lower() for word in ('password','token','secret'))),encoding='utf-8')
                docker('exec',scheduler,'tar','-C','/opt/airflow','-czf','/tmp/delta-task-logs.tar.gz','logs',timeout=60)
                docker('cp',scheduler+':/tmp/delta-task-logs.tar.gz',evidence/'test-task-logs.tar.gz',timeout=60)
        except Exception as diagnostic_error:
            result['diagnostic_error']=type(diagnostic_error).__name__
        raise
    finally:
        try:
            for name in (scheduler,source_service,worker,pg):
                found=subprocess.run(['docker','inspect','--format','{{index .Config.Labels "de.probe"}}',name],capture_output=True,text=True)
                if found.returncode==0 and found.stdout.strip()==LABEL:
                    docker('rm','-f',name,timeout=60)
            found=subprocess.run(['docker','network','inspect','--format','{{index .Labels "de.probe"}}',net],capture_output=True,text=True)
            if found.returncode==0 and found.stdout.strip()==LABEL:
                docker('network','rm',net)
        except Exception as error:
            result['status']='FAIL'
            result['cleanup_error']=type(error).__name__+': '+str(error)
            raise
        finally:
            try:
                if owner:
                    owner_identity()
                    if owner_stopped:
                        docker('start',owner['Id'])
                        wait(lambda:inspect(owner['Id'])['State'].get('Health',{}).get('Status')=='healthy',
                             'owner health restoration',360)
                    if drain_created:
                        docker('exec',owner['Id'],'python','-c',
                            'from pathlib import Path; p=Path("/opt/airflow/state/polling-drain"); '
                            'assert not p.exists() or p.read_text()=="'+token+'", "drain signal changed externally"; '
                            'p.unlink(missing_ok=True)')
                    restored=query(OWNER_PG,'airflow_meta','SELECT dag_id,is_paused FROM dag ORDER BY dag_id')
                    assert restored==pause_before, 'owner pause states changed'
                    result['owner_restored']=dict(healthy=inspect(owner['Id'])['State'].get('Health',{}).get('Status')=='healthy',pause_states_unchanged=True,drain_signal_restored=True)
            except Exception as error:
                result['status']='FAIL'
                result['restoration_error']=type(error).__name__+': '+str(error)
                raise
            finally:
                save()
                report.parent.mkdir(parents=True,exist_ok=True)
                with report.open('x',encoding='utf-8') as stream:
                    json.dump(result,stream,indent=2)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--sdk-check',action='store_true')
    parser.add_argument('--allow-owner-idle-stop',action='store_true')
    parser.add_argument('--all-sources',action='store_true')
    parser.add_argument('--mapping-check',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.sdk_check:
        sdk_check()
    elif args.prepare:
        prepare()
    else:
        if not args.report or args.report.exists():
            parser.error('choose a new --report path')
        if args.all_sources and args.mapping_check:
            parser.error('run restart/mapping gate separately from the four-source gate')
        print(json.dumps(run_probe(args.report,args.allow_owner_idle_stop,args.all_sources,args.mapping_check)))
