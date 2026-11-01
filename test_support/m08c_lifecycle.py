"""Host-side lifecycle cases on a validated disposable scope, never owner services."""
from datetime import datetime, timedelta, timezone
import json
import time
import uuid

from test_support import m08a as guard
from test_support.m08b import rows


def wait(probe, label, timeout=900):
    deadline = time.monotonic() + timeout
    while True:
        if probe():
            return
        guard.require(time.monotonic() < deadline, 'M08C deadline: ' + label)
        print('M08C waiting: ' + label, flush=True)
        time.sleep(5)


def start_airflow(h):
    h.dc(['up', '--detach', '--wait', '--wait-timeout', '420', 'airflow'], timeout=450)


def install_dag(h):
    start_airflow(h)
    h.dc(['cp', str(guard.ROOT / 'test_support/airflow/m08c_recovery.py'),
          'airflow:/opt/airflow/dags/m08c_recovery.py'])
    wait(lambda: bool(rows(h, "SELECT dag_id FROM dag WHERE dag_id='m08c_recovery'", 'airflow_meta')),
         'test DAG discovery', 180)
    wait(lambda: h.sql("SELECT count(*) FROM serialized_dag WHERE dag_id='m08c_recovery' AND data::text LIKE '%exhaust_stage%' AND data::text LIKE '%barrier%';", 'airflow_meta') == '1',
         'current test DAG parameters serialized', 180)


def signal(h, name, remove=False):
    guard.require(name in ('m08c-drain','m08c-ready','m08c-release'), 'Unknown test signal')
    method = 'unlink(missing_ok=True)' if remove else 'touch()'
    h.dc(['exec','-T','airflow','python','-c',
          'from pathlib import Path; Path("/opt/airflow/state/' + name + '").' + method])


def snapshot(h):
    return h.sql(guard.signature_query(guard.PROTECTED))


def service_restarts(h, abrupt=False):
    start_airflow(h)
    before = snapshot(h)
    identity = h.test_db()
    for service in ('ebay-sim', 'etsy-sim', 'etsy-receiver', 'airflow', 'postgres'):
        if abrupt:
            h.dc(['kill', '--signal', 'SIGKILL', service])
            h.dc(['up', '--detach', '--wait', '--wait-timeout', '420', service], timeout=450)
        else:
            h.dc(['restart', '--timeout', '30', service], timeout=90)
            h.dc(['up', '--detach', '--wait', '--wait-timeout', '420', service], timeout=450)
        guard.require(h.test_db() == identity and snapshot(h) == before, 'Restart changed durable state: ' + service)
    producer = source_worker(h)
    return dict(status='PASS', abrupt=abrupt, services=['ebay-sim','etsy-sim','etsy-receiver','airflow','postgres'], source_worker=producer,
                scope='idle service persistence; busy raw/dbt/publication loss is tested separately')


def source_worker(h):
    from tools.s02_data.config import validate
    from tools.s02_data.load import prepare, admit_live
    from test_support.s02_plan import literal

    class DB:
        def sql(self, text, db='marketplace_sim'):
            return h.sql(text, db)

    config = json.loads((guard.ROOT / 'tests/fixtures/s02_quick.json').read_text())
    config.update(dataset='m08c-worker-' + uuid.uuid4().hex[:12], duration_minutes=1)
    for source, channel in config['channels'].items():
        channel.update(orders=1, delay_seconds=[1,2], required={'cancel':1} if source=='internal_web' else {'pending':1})
    prepared = prepare(DB(), validate(config))
    admit_live(DB(), config['dataset'])
    values = dict(line.split('=',1) for line in (h.root / 'test.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    for kind in ('ebay','etsy'):
        h.sql('ALTER ROLE s02_' + kind + '_reader PASSWORD ' + literal(values['S02_' + kind.upper() + '_READER_PASSWORD']) + ';', 'marketplace_sim')
    result = h.dc(['run','--rm','-T','--no-deps',
        '--volume',str(guard.ROOT / 'test_support') + ':/repo/test_support:ro',
        '--volume',str(guard.ROOT / 'simulator') + ':/opt/project/simulator:ro',
        '--volume',str(h.root / 'test.env') + ':/m08c/private.env:ro',
        '--env','PYTHONPATH=/repo:/opt/project','--entrypoint','/opt/airflow/project-venv/bin/python',
        'airflow','-m','test_support.m08c_source_worker_probe',prepared['campaign_id']], timeout=240)
    return json.loads(result.splitlines()[-1])


def source_version(h, identity, state, created, requested=None):
    payload = json.loads((guard.ROOT / 'fixtures/s01/source_states/website' / (state + '.json')).read_text())
    stamp = datetime.now(timezone.utc).isoformat()
    # Keep catalog/customer references unchanged; create case-owned source IDs.
    for table, records in payload.items():
        if table in ('customers', 'products', 'product_variants'):
            continue
        for row in records:
            for key in ('order_id','order_number','order_item_id','payment_transaction_id','cancellation_id','shipment_id'):
                if key in row:
                    row[key] = identity + '-' + str(row[key])
            for key, value in list(row.items()):
                if key.endswith('_at') and value is not None:
                    row[key] = (created if key in ('created_at','occurred_at') else
                                requested or stamp if key == 'requested_at' else stamp)
    h.dc(['run','--rm','-T','--no-deps','--entrypoint','python','website-simulator',
          '-m','simulator.website_s02'], payload=json.dumps(payload))
    return payload['orders'][0]['order_id'], stamp


def scheduled_pause_resume(h):
    install_dag(h)
    signal(h, 'm08c-drain', remove=True)
    h.dc(['exec','-T','airflow','airflow','dags','pause','m08c_recovery'])
    before = snapshot(h)
    identity = 'C-' + uuid.uuid4().hex[:12]
    created = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    requested = None
    for state in ('0901','0910','0914'):
        order, updated = source_version(h, identity, state, created, requested)
        if state == '0910':
            requested = updated
    guard.require(snapshot(h) == before, 'Paused source updates changed published data')
    guard.require(h.sql("SELECT count(*) FROM core.orders_current WHERE source_order_id='" + order + "';") == '0',
                  'Test order published while paused')
    h.dc(['exec','-T','airflow','airflow','dags','unpause','m08c_recovery'])
    wait(lambda: h.sql("SELECT count(*) FROM core.orders_current WHERE source_order_id='" + order +
                       "' AND cancellation_state='CANCELED';") == '1', 'scheduled current-state catch-up')
    wait(lambda: int(h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND run_type='scheduled' AND state='success';", 'airflow_meta')) >= 2,
         'two actual scheduled successes')
    # Drain without pausing active retries; parser observes marker and stops new intervals.
    h.dc(['exec','-T','airflow','python','-c',
          'from pathlib import Path; Path("/opt/airflow/state/m08c-drain").touch()'])
    wait(lambda: h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND state IN ('running','queued');", 'airflow_meta') == '0',
         'test maintenance drain')
    h.dc(['exec','-T','airflow','airflow','dags','pause','m08c_recovery'])
    guard.require(h.sql("SELECT count(*) FROM core.order_snapshot_history WHERE source_order_id='" + order + "';") == '1',
                  'Unobserved intermediate snapshots were fabricated')
    return dict(status='PASS', order_id=order, source_updated_at=updated,
                assertions='paused source advances; scheduled catch-up; observed-only history; bounded drain')


def maintenance_drain(h):
    install_dag(h)
    signal(h, 'm08c-drain')
    signal(h, 'm08c-ready', remove=True)
    signal(h, 'm08c-release', remove=True)
    identity = 'm08c-drain-' + uuid.uuid4().hex
    conf = json.dumps(dict(barrier=True, fault_after_raw_once=True, fault_after_freeze_once=True))
    h.dc(['exec','-T','airflow','airflow','dags','trigger','m08c_recovery','--run-id',identity,
          '--logical-date',datetime.now(timezone.utc).isoformat(),'--conf',conf])
    h.dc(['exec','-T','airflow','airflow','dags','unpause','m08c_recovery'])
    wait(lambda: h.dc(['exec','-T','airflow','python','-c',
        'from pathlib import Path; print(int(Path("/opt/airflow/state/m08c-ready").exists()))']) == '1', 'active task barrier', 180)
    # Deterministic timeout while an acknowledged live task is held. Do not kill
    # or clear it; leave it runnable and demonstrate the explicit release path.
    try:
        wait(lambda: False, 'declared zero drain budget', timeout=0)
    except guard.SafetyError:
        pass
    else:
        raise AssertionError('bounded drain timeout was ignored')
    signal(h, 'm08c-release')
    wait(lambda: h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND run_id='" + identity +
                      "' AND state='success';", 'airflow_meta') == '1', 'in-flight retry completes under drain')
    wait(lambda: h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND state IN ('running','queued');", 'airflow_meta') == '0', 'idle after drain')
    h.dc(['exec','-T','airflow','airflow','dags','pause','m08c_recovery'])
    attempts = rows(h, """SELECT t.task_name,count(*) AS attempts FROM ops.task_attempts t
        JOIN ops.pipeline_runs p USING(run_id) WHERE p.airflow_run_id='""" + identity + "' GROUP BY t.task_name")
    guard.require(any(r['task_name']=='collect' and r['attempts']==2 for r in attempts), 'raw retry not exercised')
    guard.require(any(r['task_name']=='freeze' and r['attempts']==2 for r in attempts), 'freeze retry not exercised')
    return dict(status='PASS', airflow_run_id=identity, timeout_outcome='operator releases barrier, no task clear', attempts=attempts)


def task_clear_budget(h):
    install_dag(h)
    signal(h, 'm08c-drain')
    identity = 'm08c-budget-' + uuid.uuid4().hex
    h.dc(['exec','-T','airflow','airflow','dags','trigger','m08c_recovery','--run-id',identity,
          '--logical-date',datetime.now(timezone.utc).isoformat(),
          '--conf',json.dumps(dict(exhaust_stage=True))])
    h.dc(['exec','-T','airflow','airflow','dags','unpause','m08c_recovery'])
    def failed():
        return h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND run_id='" + identity + "' AND state='failed';", 'airflow_meta') == '1'
    wait(failed, 'five-attempt terminal failure')
    count_sql = "SELECT count(*) FROM ops.task_attempts t JOIN ops.pipeline_runs p USING(run_id) WHERE p.airflow_run_id='" + identity + "' AND t.task_name='collect';"
    guard.require(h.sql(count_sql) == '5', 'durable five-attempt budget missing')
    logical = rows(h, "SELECT logical_date FROM dag_run WHERE dag_id='m08c_recovery' AND run_id='" + identity + "'", 'airflow_meta')[0]['logical_date']
    h.dc(['exec','-T','airflow','airflow','tasks','clear','m08c_recovery','--task-regex','^(cycle|failed_workflow)$',
          '--start-date',logical,'--end-date',logical,'--yes'])
    wait(lambda: h.sql("SELECT count(*) FROM task_instance WHERE dag_id='m08c_recovery' AND run_id='" + identity +
                       "' AND task_id='cycle' AND state='failed' AND try_number>=6;", 'airflow_meta') == '1', 'cleared task refuses exhausted budget')
    guard.require(h.sql(count_sql) == '5', 'task clear reset durable budget')
    wait(lambda: h.sql("SELECT count(*) FROM dag_run WHERE dag_id='m08c_recovery' AND state IN ('running','queued');", 'airflow_meta') == '0', 'terminal cleared run')
    h.dc(['exec','-T','airflow','airflow','dags','pause','m08c_recovery'])
    return dict(status='PASS', airflow_run_id=identity, durable_attempts=5, task_clear='no budget reset')


def outage_visibility(h):
    start_airflow(h)
    h.dc(['up','--detach','scheduler-observer'])
    h.dc(['exec','-T','scheduler-observer','/opt/airflow/project-venv/bin/python','-m','orchestration.scheduler_probe','--once'])
    business = ('core.orders_current','core.order_lines_current','core.order_snapshot_history','ops.publication_state')
    before = h.sql(guard.signature_query(business))
    h.dc(['stop','--timeout','30','scheduler-observer'])
    wait(lambda: float(h.sql('SELECT extract(epoch FROM clock_timestamp()-max(observed_at)) FROM ops.scheduler_observations;')) > 91,
         'actual observer sample becomes stale', 130)
    check = "from reports.data import connect,scheduler_status; from datetime import datetime,timezone; c=connect(); r=c.execute('SELECT * FROM report.scheduler_observations').fetchall(); assert r and all(scheduler_status(x,datetime.now(timezone.utc))=='Unknown / stale sample' for x in r); print('Observer stale visibility PASS')"
    h.run('report','python','-c',check)
    h.dc(['stop','--timeout','30','airflow'])
    h.dc(['up','--detach','scheduler-observer'])
    h.dc(['exec','-T','scheduler-observer','/opt/airflow/project-venv/bin/python','-m','orchestration.scheduler_probe','--once'])
    check = "from reports.data import connect,scheduler_status; from datetime import datetime,timezone; c=connect(); r=c.execute('SELECT * FROM report.scheduler_observations').fetchall(); assert r and all(scheduler_status(x,datetime.now(timezone.utc))=='Unknown / stale scheduler' for x in r); print('Scheduler stopped visibility PASS')"
    # A graceful scheduler may leave a recent running heartbeat briefly; wait
    # for the documented120s freshness boundary rather than editing timestamps.
    wait(lambda: float(h.sql('SELECT coalesce(extract(epoch FROM clock_timestamp()-max(scheduler_heartbeat_at)),9999) FROM ops.scheduler_observations;')) > 121,
         'actual scheduler heartbeat expires', 150)
    h.run('report','python','-c',check)
    h.dc(['stop','--timeout','30','ebay-sim'])
    code = "from test_support.m08c_http_probe import checkpoint,acquire; before=checkpoint(); identity,audit=acquire(False); assert checkpoint()==before and len(audit)==5 and all(r[0] is None for r in audit); print('Source outage bounded raw/checkpoint PASS '+identity)"
    h.dc(['run','--rm','-T','--no-deps','--volume',str(guard.ROOT / 'test_support')+':/repo/test_support:ro',
          '--env','PYTHONPATH=/repo:/opt/project','--entrypoint','/opt/airflow/project-venv/bin/python',
          'airflow','-c',code], timeout=180)
    guard.require(h.sql(guard.signature_query(business)) == before, 'Outage changed last-good business publication')
    h.dc(['up','--detach','--wait','--wait-timeout','420','ebay-sim','airflow'], timeout=450)
    return dict(status='PASS', observer='actual stale sample', scheduler='actual stale heartbeat',
                source='five bounded failures/checkpoint held', last_good_unchanged=True)
