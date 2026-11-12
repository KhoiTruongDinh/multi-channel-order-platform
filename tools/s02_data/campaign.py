"""Observable local campaigns and opt-in bounded baseline; no destructive reset."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

from tools.s02_data.campaign_config import validate_campaign,timeline
from tools.s02_data.load import ROOT,prepare,admit_live,query
from tools.s02_data.live import startup_lock,up,require_live,compose
from test_support.s02_plan import literal

PROJECT='multi-channel-order-platform'


def utc(): return datetime.now(timezone.utc).isoformat()


def no_disposable_services():
    result=subprocess.run(['docker','ps','-q','--filter','label=local.m08a.identity'],
                          capture_output=True,text=True,check=True)
    if result.stdout.strip(): raise ValueError('stop the active disposable test scope before the local campaign')


def write_report(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
    temporary.replace(path)


def service(db,name):
    text=db.command(['ps','--all','--format','json',name])
    if not text.strip(): return None
    rows=json.loads(text)
    if isinstance(rows,list):
        if len(rows)!=1: raise ValueError('expected exactly one local '+name)
        rows=rows[0]
    inspected=subprocess.run(['docker','inspect',rows['ID']],capture_output=True,text=True,check=True)
    actual=json.loads(inspected.stdout)[0]
    labels=actual['Config']['Labels']
    if labels.get('com.docker.compose.project')!=PROJECT or labels.get('com.docker.compose.service')!=name:
        raise ValueError('unexpected Compose service identity')
    rows['State']='paused' if actual['State']['Paused'] else actual['State']['Status']
    return rows


def resume_retained_airflow(db):
    """Recover an existing stopped LIVE scheduler before live-up drains old runs."""
    row=service(db,'airflow')
    if not row or row['State']=='running': return
    if row['State']!='exited': raise ValueError('inspect existing Airflow state before startup')
    inspected=subprocess.run(['docker','inspect',row['ID']],capture_output=True,text=True,check=True)
    container=json.loads(inspected.stdout)[0]
    labels=container['Config']['Labels']; env=dict(v.split('=',1) for v in container['Config']['Env'] if '=' in v)
    if labels.get('com.docker.compose.project')!=PROJECT or labels.get('com.docker.compose.service')!='airflow' or \
       env.get('POLLING_LIVE_CURRENT_TIME')!='true' or env.get('POLLING_MAPPING_VERSION')!='local-live-v1':
        raise ValueError('stopped Airflow is not a retained live scheduler; inspect before switching sources')
    # Write the existing parse-time drain flag BEFORE starting its scheduler.
    # No metadata/task/budget state is forged; existing runs remain runnable.
    compose(db,['run','--rm','-T','--no-deps','--entrypoint','python','airflow','-c',
        'from pathlib import Path; Path("/opt/airflow/state/polling-drain").touch()'])
    compose(db,['up','--detach','--no-deps','--no-recreate','--wait','--wait-timeout','420','airflow'],timeout=450)


def require_no_orphaned_release(db):
    batches=query(db,'''SELECT b.batch_id,p.airflow_dag_id,p.airflow_run_id
      FROM ops.transform_batches b JOIN ops.pipeline_runs p USING(run_id)
      WHERE b.status IN ('FROZEN','BUILDING','TESTED')''','data_platform')
    for batch in batches:
        states=query(db,'SELECT state FROM dag_run WHERE dag_id='+literal(batch['airflow_dag_id'])+
                     ' AND run_id='+literal(batch['airflow_run_id']),'airflow_meta') if batch['airflow_dag_id'] else []
        if not states or states[0]['state'] not in ('running','queued'):
            # The initial cross-database snapshot can outlive publication or
            # finally-time annotation in older workers. Recheck the exact
            # barrier before declaring an orphan; never abort it automatically.
            current=query(db,'''SELECT b.batch_id,p.airflow_dag_id,p.airflow_run_id
              FROM ops.transform_batches b JOIN ops.pipeline_runs p USING(run_id)
              WHERE b.status IN ('FROZEN','BUILDING','TESTED') AND b.batch_id='''+
              literal(str(batch['batch_id']))+'::uuid','data_platform')
            if not current:
                continue
            owner=current[0]
            if (owner['airflow_dag_id'],owner['airflow_run_id']) != (batch['airflow_dag_id'],batch['airflow_run_id']):
                states=query(db,'SELECT state FROM dag_run WHERE dag_id='+literal(owner['airflow_dag_id'])+
                             ' AND run_id='+literal(owner['airflow_run_id']),'airflow_meta') if owner['airflow_dag_id'] else []
                if states and states[0]['state'] in ('running','queued'):
                    continue
            raise ValueError('operator recovery required for retained batch '+str(batch['batch_id'])+'; no automatic abort/reset')


def restore_fault(db,target):
    if not target: return 'NOT_APPLIED'
    if target.get('project')!=PROJECT or target.get('service')!='ebay-sim' or not re.fullmatch('[a-f0-9]{12,64}',target.get('id','')):
        raise ValueError('invalid campaign restoration target')
    row=service(db,'ebay-sim')
    if not row or row['ID']!=target['id']: raise ValueError('eBay container changed; inspect before restoring')
    if row['State']=='paused': compose(db,['unpause','ebay-sim'])
    elif row['State']!='running': raise ValueError('eBay is not running; no automatic replacement/restart')
    final=service(db,'ebay-sim')
    if not final or final['ID']!=target['id'] or final['State']!='running': raise ValueError('eBay unpause not confirmed')
    return 'RESTORED'


def expected_orders(db,identity):
    key=literal(identity)
    return query(db,'''SELECT source,account_id,order_id,expected_at FROM (
      SELECT DISTINCT ON(v.order_id) 'internal_web'::text source,'WEB01'::text account_id,v.order_id,
        (v.payload#>>'{orders,0,updated_at}')::timestamptz+make_interval(secs=>b.shift_seconds::double precision) expected_at
      FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
      WHERE v.campaign_id='''+key+''' ORDER BY v.order_id,v.sequence DESC
      ) website UNION ALL SELECT source,account_id,order_id,expected_at FROM (
      SELECT DISTINCT ON(v.source,v.account_id,v.order_id) v.source,v.account_id,v.order_id,
        v.source_updated_at+make_interval(secs=>b.shift_seconds::double precision) expected_at
      FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
      WHERE v.campaign_id='''+key+''' ORDER BY v.source,v.account_id,v.order_id,v.sequence DESC) marketplace''')


def snapshot(db,identity,expected,since,planned):
    key=literal(identity)
    future=query(db,'''SELECT count(*) n FROM (
      SELECT visible_at,campaign_id FROM s02.website_versions UNION ALL
      SELECT visible_at,campaign_id FROM s02.versions) v JOIN s02.live_batches b USING(campaign_id)
      WHERE v.campaign_id='''+key+''' AND visible_at+make_interval(secs=>b.shift_seconds::double precision)>statement_timestamp()''')[0]['n']
    if planned:
        pending=query(db,'SELECT count(*) n FROM s02.delivery_schedule WHERE campaign_id='+key+' AND completed_at IS NULL')[0]['n']
    else:
        pending=query(db,'SELECT count(*) n FROM s02.deliveries WHERE campaign_id='+key+' AND NOT omitted AND delivered_at IS NULL')[0]['n']
    values=','.join('('+','.join(literal(row[k]) for k in ('source','account_id','order_id'))+','+literal(row['expected_at'])+'::timestamptz)' for row in expected)
    coverage=query(db,'''WITH wanted(source,account_id,order_id,updated_at) AS (VALUES '''+values+''')
      SELECT w.source,count(*) expected,count(c.source_order_id) found,
        count(*) FILTER(WHERE c.source_updated_at=w.updated_at) current
      FROM wanted w LEFT JOIN core.orders_current c ON
        (c.source_system,c.source_account_id,c.source_order_id)=(w.source,w.account_id,w.order_id)
      GROUP BY w.source ORDER BY w.source''','data_platform')
    errors=query(db,"SELECT count(*) n FROM raw.raw_records WHERE source_system='ebay_sim' AND acquired_at>="+
                 literal(since)+"::timestamptz AND (response_status IS NULL OR response_status>=400)",'data_platform')[0]['n']
    return dict(future_source_versions=future,pending_sends=pending,core=coverage,
                ebay_error_audits_since_admission=errors,
                reached_final_versions=not future and not pending and all(r['current']==r['expected'] for r in coverage))


def run(db,config,confirmed=False,allow_faults=False):
    if not confirmed: raise ValueError('campaign requires --confirm-local: starts live services and schedules')
    settings=validate_campaign(config.get('campaign',{})); fault=timeline(settings)
    if fault and not allow_faults: raise ValueError('configured outage requires --allow-faults')
    total=sum(c['orders'] for c in config['channels'].values())
    if not 1<=total<=1000: raise ValueError('observation campaign supports1..1000 orders; load phase is deferred')
    run_id='campaign-'+uuid.uuid4().hex
    directory=ROOT/'runtime'/run_id; directory.mkdir(parents=True)
    report=dict(id=run_id,status='RUNNING',scope='observable local campaign; NOT M08D load acceptance',
                performance_assessment='DEFERRED',started_at=utc(),timeline=fault,events=[],fault_target=None,fault_active=False)
    source_root=Path(__file__).resolve().parents[2]
    report['hashes']={name:hashlib.sha256((source_root/name).read_bytes()).hexdigest() for name in (
        'tools/s02_data/campaign.py','tools/s02_data/campaign_config.py','tools/s02_data/config.py',
        'tools/s02_data/live.py','tools/s02_data/load.py','tools/s02_data/__main__.py')}
    monitor=None
    if 'measurement' in settings:
        from test_support.m08d_measure import Monitor
        # Finite source ceilings are checked before Docker/startup or SQL writes.
        monitor=Monitor(db,config,settings['measurement'],report)
        report['performance_assessment']='BOUNDED_BASELINE_NOT_FULL_M08D'
        if 'load' in settings: report['performance_assessment']='FINITE_RATE_STEP_NOT_FULL_M08D'
        for name in ('test_support/m08d_measure.py','test_support/s02_oracle.py','test_support/s02_inputs.py',
                     'tools/s02_data/generate.py','tools/s02_data/references.py','tools/s02_data/delivery.py',
                     'test_support/s02_plan.py','infra/compose.yaml','infra/compose.live.yaml',
                     'ingestion/etsy.py','ingestion/etsy_recovery.py','ingestion/ebay.py','ingestion/pagination.py',
                     'migrations/platform/009_etsy_recovery_scans.sql'):
            report['hashes'][name]=hashlib.sha256((source_root/name).read_bytes()).hexdigest()
        name='test_support/m08d_envelope.py'
        report['hashes'][name]=hashlib.sha256((source_root/name).read_bytes()).hexdigest()
        # Freeze the executed transformation plan too, not only observer code.
        files=[source_root/name for name in ('transformations/dbt_project.yml','infra/dbt/profiles.yml',
               'orchestration/website_workflow.py','orchestration/polling.py',
               'transformation/batch.py','transformation/publish.py')]
        for folder in ('models','macros','tests'):
            files.extend(p for p in (source_root/'transformations'/folder).rglob('*')
                         if p.is_file() and p.suffix in ('.sql','.yml','.yaml'))
        for path in sorted(files):
            report['hashes'][path.relative_to(source_root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    output=directory/'report.json'
    def save(): write_report(output,report)
    def event(name,**details):
        row=dict(at=utc(),event=name,**details); report['events'].append(row); save()
        print(json.dumps(row),flush=True)
    restored=False
    with startup_lock():
        try:
            no_disposable_services()
            model=db.model()
            if model['name']!=PROJECT: raise ValueError('campaign requires the explicit local owner project')
            existing=service(db,'ebay-sim')
            if existing and existing['State']=='paused': raise ValueError('eBay is already paused; no campaign ownership assumed')
            event('STARTUP',note='retaining existing data; no checkpoint/budget reset',timeline=fault,
                  performance_assessment=report['performance_assessment'])
            compose(db,['up','--detach','--wait','--wait-timeout','180',
                        'postgres','ebay-sim','etsy-sim','etsy-receiver'],timeout=210)
            require_no_orphaned_release(db)
            resume_retained_airflow(db)
            # Restart can turn an old RUNNING owner terminal after initial preflight.
            # Refuse that orphan during drain too; never repair it automatically.
            up(db,drain_guard=lambda:require_no_orphaned_release(db)); require_live(db)
            for name,target in (('airflow',8080),('report',8501)):
                ports=model['services'][name].get('ports',[])
                port=next((p['published'] for p in ports if p['target']==target),None)
                if port: event('OPEN_UI',service=name,url='http://localhost:'+str(port))
            pg_port=next((p['published'] for p in model['services']['postgres'].get('ports',[]) if p['target']==5432),None)
            if pg_port: event('DATABASE',host='127.0.0.1',port=pg_port,
                              databases=['marketplace_sim','website_source','data_platform'],credentials='existing .env; never printed')
            config=json.loads(json.dumps(config))
            config['dataset']=config['dataset'][:48]+'-'+uuid.uuid4().hex[:12]
            if monitor: monitor.before_prepare(config)
            prepared=prepare(db,config)
            if monitor: monitor.sample()  # Refuse admission after an unsafe preparation.
            admitted=admit_live(db,config['dataset'])
            if monitor: monitor.admitted(prepared['campaign_id'])
            report.update(dataset=config['dataset'],campaign_id=prepared['campaign_id'],admission=admitted,
                          source_manifest=prepared['manifest'])
            expected=expected_orders(db,prepared['campaign_id'])
            if not expected: raise ValueError('campaign prepared no orders')
            since=utc(); begin=time.monotonic(); deadline=begin+settings['timeout_seconds']
            event('ADMITTED',dataset=config['dataset'],orders=len(expected),report=str(output.relative_to(ROOT)))
            while True:
                elapsed=time.monotonic()-begin
                if fault and report['fault_target'] is None and elapsed>=fault['start_after_seconds']:
                    row=service(db,'ebay-sim')
                    if not row or row['State']!='running': raise ValueError('eBay must be running and unpaused before outage')
                    report['fault_target']=dict(project=PROJECT,service='ebay-sim',id=row['ID'])
                    report['fault_active']=True
                    event('OUTAGE_INTENT',target=report['fault_target'])
                    compose(db,['pause','ebay-sim'])
                    paused=service(db,'ebay-sim')
                    if not paused or paused['ID']!=row['ID'] or paused['State']!='paused': raise ValueError('pause not confirmed')
                    report['fault_started_monotonic']=time.monotonic()
                    event('OUTAGE_STARTED',service='ebay-sim')
                if fault and report['fault_target'] and not restored and time.monotonic()-report['fault_started_monotonic']>=fault['duration_seconds']:
                    restore_fault(db,report['fault_target']); restored=True; report['fault_active']=False; event('OUTAGE_RESTORED')
                state=snapshot(db,prepared['campaign_id'],expected,since,bool(prepared['manifest'].get('delivery_plan')))
                if monitor: monitor.observe(state)
                report['latest']=state; event('OBSERVATION',**state)
                fault_done=not fault or restored
                if fault_done and state['reached_final_versions'] and (not monitor or monitor.ready()):
                    if monitor: event('BASELINE_RESULT',result=monitor.finish())
                    report['status']='READY_FOR_REVIEW'
                    event('READY_FOR_REVIEW',note='bounded checks recorded separately when enabled; NOT full load/soak certification')
                    break
                if time.monotonic()>=deadline: raise TimeoutError('campaign wait budget exceeded; inspect report, not a latency SLA verdict')
                time.sleep(settings['poll_seconds'])
        except BaseException as error:
            if monitor and monitor.value['status'] not in ('CEILING_REACHED','BASELINE_FAIL'):
                monitor.value.update(status='INCOMPLETE',error_type=type(error).__name__)
            report.update(status='INTERRUPTED' if isinstance(error,KeyboardInterrupt) else 'FAILED',error_type=type(error).__name__)
            event('STOPPED',reason=type(error).__name__)
            raise
        finally:
            try:
                report['fault_cleanup']=restore_fault(db,report['fault_target']) if report['fault_active'] else ('RESTORED' if restored else 'NOT_APPLIED')
                report['fault_active']=False
            except Exception:
                report.update(status='RESTORE_REQUIRED',fault_cleanup='FAILED')
                print('RESTORE REQUIRED: python -m tools.s02_data campaign-restore --report '+str(output)+' --confirm-local',flush=True)
                raise
            finally:
                report['finished_at']=utc(); save()
                print('Campaign report: '+str(output),flush=True)
    return report


def restore(db,path,confirmed=False):
    if not confirmed: raise ValueError('restore requires --confirm-local')
    path=Path(path).resolve()
    if ROOT/'runtime' not in path.parents: raise ValueError('report must be inside repository runtime')
    report=json.loads(path.read_text(encoding='utf-8'))
    if not report.get('fault_active'): return dict(status='NO_ACTIVE_FAULT')
    if not report.get('fault_target'): raise ValueError('active-fault journal lacks a restoration target')
    with startup_lock(): result=restore_fault(db,report.get('fault_target'))
    report.update(fault_active=False,fault_cleanup=result)
    write_report(path,report)
    return dict(status=result,note='only same campaign-owned paused eBay container is unpaused')
