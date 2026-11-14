"""Opt-in disposable PostgreSQL/dbt parity and rollback probe, never owner data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def inner(http_rounds=1):
    assert os.environ['PLATFORM_DB_HOST'].startswith('delta-pg-'), 'disposable host required'
    from transformation.batch import connect
    from transformation.delta_plan import compile_plan, load
    from transformation.delta_runtime import source_lock, freeze, build
    from transformation.delta_publish import publish
    from transformation.source_config import SOURCES
    from psycopg.types.json import Jsonb
    import psycopg
    timings = []

    def admin():
        return psycopg.connect(host=os.environ['PLATFORM_DB_HOST'],dbname='data_platform',user='postgres')

    def acquire(source, payload, resource, metadata=None, run=None):
        run = run or uuid.uuid4()
        raw = uuid.uuid4()
        data = json.dumps(payload,separators=(',',':')).encode()
        with admin() as conn:
            conn.execute('''INSERT INTO ops.pipeline_runs(run_id,stage,source_system,source_account_id,
                stream_name,started_at,finished_at,status) VALUES(%s,'ACQUIRE',%s,%s,'orders',
                '2026-10-17T10:00Z','2026-10-17T10:01Z','SUCCEEDED') ON CONFLICT DO NOTHING''',
                         (run,source,SOURCES[source][0]))
            conn.execute('''INSERT INTO raw.raw_records(raw_record_id,run_id,source_system,
                source_account_id,resource_type,response_status,acquired_at,raw_bytes,parsed_payload,
                byte_sha256,contract_version,metadata) VALUES(%s,%s,%s,%s,%s,200,
                '2026-10-17T10:01Z',%s,%s,%s,'s01-v1',%s)''',
                         (raw,run,source,SOURCES[source][0],resource,data,Jsonb(payload),
                          hashlib.sha256(data).digest(),Jsonb(metadata or {})))
        return raw,run

    def cycle(plan, *, bootstrap=False, fail_build=False, fail_publish=False):
        batch,run = uuid.uuid4(),uuid.uuid4()
        started = time.monotonic()
        phases = {}
        nodes = []
        with source_lock(plan) as conn:
            phases['source_lock_and_validation'] = time.monotonic()-started
            phase = time.monotonic()
            freeze(conn,plan,batch,run,bootstrap=bootstrap)
            phases['freeze'] = time.monotonic()-phase
            phase = time.monotonic()
            if fail_build:
                try: build(conn,plan,batch,inject_failure=True)
                except RuntimeError: pass
                else: raise AssertionError('injected test did not fail')
                assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE processed_batch_id=%s',
                                    (batch,)).fetchone()[0] == 0
                build(conn,plan,batch,attempt=2)
            else:
                build(conn,plan,batch)
            phases['build_and_test'] = time.monotonic()-phase
            phase = time.monotonic()
            if fail_publish:
                try: publish(plan,batch,inject_failure=True)
                except RuntimeError: pass
                else: raise AssertionError('injected publication did not fail')
                assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',
                                    (batch,)).fetchone()[0] == 'TESTED'
                assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE processed_batch_id=%s',
                                    (batch,)).fetchone()[0] == 0
                conn.commit()
            publish(plan,batch)
            phases['publish'] = time.monotonic()-phase
            assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',
                                (batch,)).fetchone()[0] == 'PUBLISHED'
            conn.commit()
            stored = conn.execute('''SELECT results FROM ops.delta_results WHERE batch_id=%s
                AND passed ORDER BY attempt_number DESC LIMIT 1''',(batch,)).fetchone()[0]
            nodes = sorted(stored['models']+stored['tests'],key=lambda row:row['seconds'],reverse=True)[:3]
            conn.commit()
        timings.append(dict(source=plan['source'],bootstrap=bootstrap,
                            injected_failure=fail_build or fail_publish,
                            scope='freeze/build/test/publish only; excludes acquisition',
                            seconds=time.monotonic()-started,phases=phases,slowest_nodes=nodes))
        return batch

    fixture = ROOT/'fixtures/s01/responses'
    web = json.loads((fixture/'internal_web/WEB_R1.json').read_text())
    ebay = json.loads((fixture/'ebay_sim/EB_R1.json').read_text())['orders'][0]
    etsy = json.loads((fixture/'etsy_sim/ET_R1.json').read_text())
    acquire('internal_web',web,'website_order_window')
    ebay_raw,run = acquire('ebay_sim',ebay,'ebay_order')
    acquire('ebay_sim',{'fulfillments':[],'total':0},'ebay_fulfillments',
            {'order_raw_id':str(ebay_raw)},run)
    acquire('etsy_sim',etsy,'etsy_receipt')
    checks = []
    plans = {}
    for source in SOURCES:
        path = Path('/tmp/delta-plans')/(source+'.json')
        compile_plan(source,'s01-v1','delta-probe',path)
        plan = plans[source] = load(path)
        batch = cycle(plan,bootstrap=True)
        with connect() as conn:
            assert conn.execute('SELECT count(*) FROM core.orders_current WHERE source_system=%s',
                                (source,)).fetchone()[0] == 1
        checks.append({'source':source,'bootstrap':str(batch),'models':len(plan['models']),'tests':len(plan['tests'])})
    # Duplicate acquisition is audit/evidence, not another logical snapshot.
    with connect() as conn:
        before = conn.execute('SELECT count(*) FROM core.order_snapshot_history').fetchone()[0]
    acquire('internal_web',web,'website_order_window')
    cycle(plans['internal_web'],fail_build=True,fail_publish=True)
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM core.order_snapshot_history').fetchone()[0] == before
        assert conn.execute("SELECT count(*) FROM core.snapshot_evidence e JOIN core.order_snapshot_history h USING(snapshot_id) WHERE h.source_system='internal_web'").fetchone()[0] == 2
    checks.append('duplicate-raw-retained-without-duplicate-snapshot; failed-gate-and-publication-retry')
    # A no-input tick must not erase history or consume invented inputs.
    empty = cycle(plans['internal_web'])
    with admin() as conn:
        assert conn.execute('SELECT count(*) FROM ops.delta_new_inputs WHERE batch_id=%s',(empty,)).fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM core.order_snapshot_history').fetchone()[0] == before
        assert conn.execute("SELECT sum(order_count) FROM mart.order_activity_daily").fetchone()[0] == 3
    checks.append('empty-tick-retains-core-and-mart-totals')
    # Healthy warm affected-order cycles for both marketplace graphs too.
    changed_ebay = json.loads((fixture/'ebay_sim/EB_R2.json').read_text())['orders'][0]
    raw,run = acquire('ebay_sim',changed_ebay,'ebay_order')
    shipping = json.loads((fixture/'ebay_sim/EB_F1.json').read_text())
    acquire('ebay_sim',shipping,'ebay_fulfillments',{'order_raw_id':str(raw)},run)
    ebay_batch = cycle(plans['ebay_sim'])
    # Diagnose the measured slowest eBay SELECT with actual plans. JIT is a
    # session-only comparison here, not an unmeasured global server change.
    ebay_plan = plans['ebay_sim']
    slowest = timings[-1]['slowest_nodes'][0]['id']
    node = next(n for n in ebay_plan['models']+ebay_plan['tests'] if n['id']==slowest)
    profiles = []
    with source_lock(ebay_plan) as conn:
        conn.execute("SELECT set_config('platform.batch_id',%s,true)",(str(ebay_batch),))
        conn.execute("SELECT set_config('platform.inject_test_failure','false',true)")
        for mode in ('on','off'):
            conn.execute("SELECT set_config('jit',%s,true)",(mode,))
            explained = conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+node['sql'].rstrip(';')).fetchone()[0][0]
            profiles.append(dict(node=slowest,jit=mode,execution_ms=explained['Execution Time'],
                                 planning_ms=explained['Planning Time'],
                                 estimated_cost=explained['Plan']['Total Cost'],
                                 jit_details=explained.get('JIT')))
    checks.append({'ebay_slowest_select_profiles':profiles,'scope':'disposable diagnostic; not SLA'})
    acquire('etsy_sim',json.loads((fixture/'etsy_sim/ET_R2.json').read_text()),'etsy_receipt')
    cycle(plans['etsy_sim'])
    # Add another order, then update only the first one. Unaffected row lineage
    # and aggregate totals must survive the affected-order replacement.
    other = json.loads(json.dumps(web).replace('W1001','W1002'))
    acquire('internal_web',other,'website_order_window')
    other_batch = cycle(plans['internal_web'])
    updated = json.loads((fixture/'internal_web/WEB_R2.json').read_text())
    acquire('internal_web',updated,'website_order_window')
    cycle(plans['internal_web'])
    with admin() as conn:
        assert conn.execute("SELECT published_batch_id FROM core.orders_current WHERE source_system='internal_web' AND source_order_id='W1002'").fetchone()[0] == other_batch
        assert conn.execute("SELECT sum(order_count) FROM mart.order_activity_daily").fetchone()[0] == 4
    checks.append('unaffected-order-lineage-and-effective-mart-totals')
    # A previously unseen intermediate state arrives after the terminal state.
    terminal = json.loads(json.dumps(json.loads((fixture/'internal_web/WEB_R3.json').read_text())).replace('W1001','W1002'))
    intermediate = json.loads(json.dumps(updated).replace('W1001','W1002'))
    acquire('internal_web',terminal,'website_order_window')
    cycle(plans['internal_web'])
    acquire('internal_web',intermediate,'website_order_window')
    late_batch = cycle(plans['internal_web'])
    with admin() as conn:
        assert conn.execute("SELECT cancellation_state FROM core.orders_current WHERE source_system='internal_web' AND source_order_id='W1002'").fetchone()[0] == 'CANCELED'
        assert conn.execute("SELECT count(*) FROM core.order_snapshot_history WHERE source_system='internal_web' AND source_order_id='W1002'").fetchone()[0] == 3
        assert conn.execute('SELECT count(*) FROM ops.delta_batch_keys WHERE batch_id=%s',(late_batch,)).fetchone()[0] == 1
    checks.append('late-unseen-intermediate-version-retained-without-current-regression; one-dirty-order')
    with source_lock(plans['internal_web']):
        with connect() as peer:
            assert not peer.execute("SELECT pg_try_advisory_lock(hashtextextended('source-cycle:internal_web:WEB01',0))").fetchone()[0]
    checks.append('same-physical-source-fence-as-legacy')
    owner = uuid.uuid4()
    with admin() as conn:
        conn.execute('''INSERT INTO ops.pipeline_runs(run_id,stage,source_system,source_account_id,
            stream_name,started_at,status) VALUES(%s,'RECOVER','ebay_sim','seller_sim_01',
            'orders',clock_timestamp(),'RUNNING')''',(owner,))
        conn.execute("INSERT INTO ops.source_cycle_owners(source_system,source_account_id,run_id) VALUES('ebay_sim','seller_sim_01',%s)",(owner,))
    try:
        with source_lock(plans['ebay_sim']):
            raise AssertionError('live owner was bypassed')
    except RuntimeError as error:
        assert 'ownership' in str(error)
    with admin() as conn:
        conn.execute("UPDATE ops.pipeline_runs SET status='FAILED',finished_at=clock_timestamp() WHERE run_id=%s",(owner,))
    with source_lock(plans['ebay_sim']): pass
    checks.append('nonterminal-source-owner-refused; retained-terminal-owner-allows-probe')

    # Interrupt Python unwinding after real candidate DDL (not a process-kill
    # claim). The context must roll back DDL and release its source session lock.
    # A durable workflow retry can have attempt2 without an attempt1 result row.
    from unittest.mock import patch
    acquire('internal_web',web,'website_order_window')
    interrupted,run = uuid.uuid4(),uuid.uuid4()
    plan = plans['internal_web']
    execute = psycopg.Connection.execute
    def interrupt_after_ddl(connection,query,*args,**kwargs):
        result = execute(connection,query,*args,**kwargs)
        if isinstance(query,str) and query.startswith('CREATE TABLE "data_platform"."build_delta_web"'):
            raise KeyboardInterrupt('probe interruption after real DDL')
        return result
    try:
        with source_lock(plan) as conn:
            freeze(conn,plan,interrupted,run)
            with patch.object(psycopg.Connection,'execute',new=interrupt_after_ddl):
                build(conn,plan,interrupted)
    except KeyboardInterrupt: pass
    else: raise AssertionError('interruption did not happen')
    with source_lock(plan) as conn:
        assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(interrupted,)).fetchone()[0] == 'BUILDING'
        assert conn.execute('SELECT count(*) FROM ops.delta_results WHERE batch_id=%s',(interrupted,)).fetchone()[0] == 0
        conn.commit()
        build(conn,plan,interrupted,attempt=2)
        publish(plan,interrupted)
    checks.append('DDL-interruption-unwind-rolls-back-and-unlocks; attempt2-without-result1')
    from tests.delta_coordinator_cases import check as coordinator_check
    checks.append(coordinator_check(plans,acquire,admin,fixture))
    from tests.delta_process_cases import check as process_check
    checks.append(process_check(plans,acquire,admin,fixture))
    from tests.delta_http_cases import check as http_check
    checks.append(http_check(plans,ROOT,admin,rounds=http_rounds))
    from tests.delta_daily_cases import check as daily_check
    checks.append(daily_check(plans['internal_web'],acquire,admin,cycle,web))
    from tests.website_staging_probe import run as staging_check
    checks.append(staging_check(
        (ROOT/'transformations/models/staging/stg_website_observations.sql').read_text(),
        (ROOT/'tests/sql/website_staging_before.sql').read_text(),
        [json.loads(p.read_text()) for p in sorted((ROOT/'fixtures/s01/source_states/website').glob('*.json'))],
        (ROOT/'transformations/macros/canonical_jsonb.sql').read_text(),sizes=(1,10,100)))

    # Full ordinary dbt build is an independent execution path/oracle over all
    # acquired evidence. Compare every published business field, not row counts.
    from transformation.batch import freeze as full_freeze
    from transformation.publish import COPIES
    from psycopg import sql
    import sys
    full = uuid.uuid4()
    full_freeze(argparse.Namespace(batch_id=full,run_id=uuid.uuid4(),source='etsy_sim',
                                  mapping_version='s01-v1',transformation_version='delta-probe',validation_mode='runtime'))
    variables = dict(batch_id=str(full),mapping_version='s01-v1',transformation_version='delta-probe',
                     release_source='etsy_sim',validation_mode='runtime')
    result = subprocess.run([str(Path(sys.executable).with_name('dbt')),'build',
                             '--project-dir',str(ROOT/'transformations'),
                             '--profiles-dir',str(ROOT/'infra/dbt'),
                             '--target-path','/tmp/dbt-full-oracle','--log-path','/tmp/dbt-full-log',
                             '--vars',json.dumps(variables)],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('full dbt oracle failed: '+result.stdout[-6000:]+result.stderr[-1000:])
    run_results = json.loads(Path('/tmp/dbt-full-oracle/run_results.json').read_text())
    assert all(row['status'] in ('success','pass') for row in run_results['results'])
    with admin() as conn:
        for target,base in COPIES:
            candidates = [base.replace('build.','build.'+SOURCES[source][1]) for source in SOURCES]
            # Snapshot evidence has no source column; UNION across each source
            # candidate yields the complete warehouse population.
            left = sql.SQL("SELECT to_jsonb(t)-'batch_id'-'published_batch_id' AS row FROM {} t").format(sql.Identifier(*target.split('.')))
            right = sql.SQL(' UNION ALL ').join(sql.SQL("SELECT to_jsonb(t)-'batch_id'-'published_batch_id' AS row FROM {} t").format(sql.Identifier(*c.split('.'))) for c in candidates)
            mismatch = conn.execute(sql.SQL('SELECT count(*) FROM ((({}) EXCEPT ALL ({})) UNION ALL (({}) EXCEPT ALL ({}))) differences').format(left,right,right,left)).fetchone()[0]
            assert mismatch == 0, (target,mismatch)
    checks.append({'full_dbt_oracle':'PASS','nodes':len(run_results['results']),
                   'compared':'all eight core/mart outputs; batch lineage intentionally excluded'})
    from tests.delta_mapping_cases import check as mapping_check
    checks.append(mapping_check(plans['ebay_sim'],admin))
    # Genuine business-rule failure, not just the synthetic injected-failure test.
    bad = json.loads(json.dumps(web))
    bad['orders'][0]['order_total_amount'] = '9999.00'
    raw,_ = acquire('internal_web',bad,'website_order_window')
    batch,run = uuid.uuid4(),uuid.uuid4()
    plan = plans['internal_web']
    with admin() as conn:
        good = conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0]
    with source_lock(plan) as conn:
        freeze(conn,plan,batch,run)
        try: build(conn,plan,batch)
        except RuntimeError: pass
        else: raise AssertionError('invalid business money was accepted')
        assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE raw_record_id=%s',(raw,)).fetchone()[0] == 0
        report = conn.execute('SELECT results FROM ops.delta_results WHERE batch_id=%s',(batch,)).fetchone()[0]
        assert any('website_constraints' in row['id'] and row['status']=='fail' for row in report['tests'])
        assert conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0] == good
    checks.append('real-money-invariant-refusal-retains-last-good-and-unconsumed-raw')
    return {'status':'PASS','scope':'disposable compiled dbt/runtime SQL; NOT collection-to-publication SLA',
            'checks':checks,'timings':timings}


def docker_probe(http_rounds=1):
    token = uuid.uuid4().hex[:12]
    pg,net,worker = 'delta-pg-'+token,'delta-net-'+token,'delta-worker-'+token
    label = 'de.probe=delta-runtime'

    def docker(*args,**kwargs):
        result = subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',timeout=1200,**kwargs)
        if result.returncode:
            raise RuntimeError('disposable Docker command failed: '+result.stdout[-6000:]+result.stderr[-6000:])
        return result.stdout

    try:
        docker('network','create','--internal','--label',label,net)
        docker('run','-d','--name',pg,'--label',label,'--network',net,'--memory','384m','--cpus','1',
               '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:16.15-bookworm')
        for _ in range(40):
            ready = subprocess.run(['docker','exec',pg,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True)
            if ready.returncode == 0: break
            time.sleep(1)
        else: raise RuntimeError('disposable PostgreSQL not ready')
        roles = ('platform_owner','platform_ingest','platform_transform','platform_publisher','platform_report',
                 'website_owner','website_reader')
        docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres',
               input=';'.join('CREATE ROLE '+r+' LOGIN' for r in roles)+'; CREATE DATABASE data_platform OWNER platform_owner; CREATE DATABASE website_source OWNER website_owner;')
        def migrate(path,database='data_platform'):
            docker('exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres','-d',database,input=path.read_text())
        migrate(ROOT/'migrations/bootstrap/002_database_baseline.sql')
        migrate(ROOT/'migrations/bootstrap/002_database_baseline.sql','website_source')
        migrate(ROOT/'migrations/website_source/001_schema.sql','website_source')
        for path in sorted((ROOT/'migrations/platform').glob('*.sql')): migrate(path)
        migrate(ROOT/'migrations/platform/012_delta_runtime.sql')
        image = docker('inspect','--format','{{.Image}}','multi-channel-order-platform-airflow-1').strip()
        args = ['run','--rm','--name',worker,'--label',label,'--memory','512m','--network',net,
                '--workdir','/review']
        for directory in ('transformation','transformations','orchestration','ingestion','simulator','infra/dbt','tests','fixtures/s01'):
            args += ['--mount','type=bind,src='+str(ROOT/directory)+',dst=/review/'+directory+',readonly']
        args += ['-e','PROJECT_ROOT=/review','-e','PYTHONPATH=/review','-e','PYTHONDONTWRITEBYTECODE=1',
                 '-e','PLATFORM_DB_HOST='+pg,'-e','PLATFORM_TRANSFORM_PASSWORD=disposable',
                 '-e','PLATFORM_INGEST_PASSWORD=disposable',
                 '-e','PLATFORM_PUBLISHER_PASSWORD=disposable']
        # Compile artifacts live on this worker, not the read-only source mounts.
        args += ['--tmpfs','/review/runtime:uid=50000,gid=0,mode=1777',
                 '--entrypoint','/opt/airflow/project-venv/bin/python',image,
                 '/review/tests/delta_runtime_probe.py','--inner','--http-rounds',str(http_rounds)]
        output = docker(*args)
        return json.loads(output.splitlines()[-1])
    finally:
        for name in (worker,pg):
            check = subprocess.run(['docker','inspect','--format','{{index .Config.Labels "de.probe"}}',name],capture_output=True,text=True)
            if check.returncode == 0 and check.stdout.strip() == 'delta-runtime': docker('rm','-f',name)
        check = subprocess.run(['docker','network','inspect','--format','{{index .Labels "de.probe"}}',net],capture_output=True,text=True)
        if check.returncode == 0 and check.stdout.strip() == 'delta-runtime': docker('network','rm',net)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--docker',action='store_true')
    group.add_argument('--inner',action='store_true')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--http-rounds',type=int,choices=range(1,4),default=1,
                        help='Repeat 1/10/100-order waves with warehouse/raw history retained (max3)')
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error('choose a new report path')
    result = inner(args.http_rounds) if args.inner else docker_probe(args.http_rounds)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2)
    print(json.dumps(result))
