"""Finite fixed S01 orchestration using existing commands, not S02 generation."""
import json
import time
import uuid

from test_support.m08a import ROOT, SafetyError, require, signature_query, PROTECTED


def seed_and_check(h):
    h.sql((ROOT / 'tests/m01_acceptance.sql').read_text())
    h.dc(['up', '--detach', '--wait', '--wait-timeout', '180', 'ebay-sim', 'etsy-sim', 'etsy-receiver'])
    for state, start, end in [('0901','08:58','09:03'), ('0910','09:01','09:11'), ('0914','09:09','09:15')]:
        h.run('website-simulator', state)
        h.run('website-collector', '--window-start', f'2026-10-17T{start}:00Z',
            '--window-end', f'2026-10-17T{end}:00Z', '--observed-at', f'2026-10-17T{end}:00Z',
            '--execution-id', h.marker['id'] + '-web-' + state)
    h.sql((ROOT / 'tests/m02_source_boundary.sql').read_text(), 'website_source')
    for state, end in [('0902','09:03'), ('0912','09:13')]:
        config = json.dumps(dict(state=state))
        code = "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://localhost:8081/state',data=" + repr(config.encode()) + ")).read()"
        h.dc(['exec','-T','ebay-sim','python','-c',code])
        h.run('ebay-collector', '--execution-id', h.marker['id'] + '-ebay-' + state,
            '--window-start','2026-10-17T08:58:00Z','--window-end',f'2026-10-17T{end}:00Z',
            '--observed-at',f'2026-10-17T{end}:00Z')
    for delivery, observed in [('D1','09:06'),('D2','09:07'),('D3',None)]:
        header = json.loads((ROOT / f'fixtures/s01/webhooks/{delivery}.headers.json').read_text())
        h.run('etsy-receiver', 'python','-m','simulator.etsy_sender',
            '--body-file',f'/fixtures/s01/webhooks/{delivery}.body.json','--message-id',header['webhook-id'], reads=True)
        if observed:
            h.run('airflow','-m','ingestion.etsy','drain','--execution-id',h.marker['id'] + '-' + delivery,
                '--observed-at',f'2026-10-17T{observed}:00Z',entrypoint='/opt/airflow/project-venv/bin/python')
    for source, version in [('internal_web','m03-v1'),('ebay_sim','m05-v1'),('etsy_sim','m06-v1')]:
        batch = str(uuid.uuid4())
        h.run('dbt-transform','python','-m','transformation.batch','freeze','--source',source,
            '--batch-id',batch,'--run-id',str(uuid.uuid4()),'--mapping-version','s01-v1','--transformation-version',version)
        h.run('dbt-transform','python','-m','transformation.batch','building','--batch-id',batch)
        variables = json.dumps(dict(batch_id=batch,mapping_version='s01-v1',transformation_version=version,
                                   release_source=source,inject_test_failure=False))
        h.run('dbt-transform','dbt','build','--profiles-dir','/app/infra/dbt','--project-dir','/app/transformations',
              '--target-path',f'target/{batch}','--vars',variables,timeout=300)
        h.run('dbt-transform','python','-m','transformation.batch','tested','--batch-id',batch,
              '--artifact',f'/app/transformations/target/{batch}/run_results.json')
        h.run('platform-publisher','python','-m','transformation.publish','--source',source,
              '--batch-id',batch,'--run-id',str(uuid.uuid4()))
    h.run('airflow','/repo/tests/m06_probe.py','check',reads=True,entrypoint='/opt/airflow/project-venv/bin/python')
    h.sql((ROOT / 'tests/m07_acceptance.sql').read_text())
    before = h.sql(signature_query(PROTECTED))
    h.dc(['restart','postgres'])
    # Read-only readiness polling, not fault injection or a new mutation.
    deadline = time.monotonic() + 60
    while True:
        try:
            h.test_db()
            break
        except SafetyError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    h.migration_rerun()
    require(h.sql(signature_query(PROTECTED)) == before, 'Restart/migration changed stable test state')
    print('M08A test PostgreSQL identity/persistence/migration rerun PASS',flush=True)
    # No dbt builds run alongside a second Airflow standalone on the small laptop.
    h.dc(['up','--detach','--wait','--wait-timeout','420','airflow'],timeout=450)
    imports=h.dc(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json'])
    require(json.loads(imports) == [], 'Airflow DAG import errors')
    deadline = time.monotonic() + 120
    while h.sql('SELECT count(*) FROM dag;', 'airflow_meta') != '7':
        require(time.monotonic() < deadline, 'Isolated DAG serialization timeout')
        time.sleep(2)
    require(h.sql('SELECT dag_id FROM dag ORDER BY dag_id;', 'airflow_meta').splitlines() ==
        sorted(['website_orders','website_polling','ebay_polling','ebay_polling_replay',
                'etsy_inbox','etsy_recovery','etsy_replay']), 'Unexpected isolated DAG IDs')
    require(h.sql("SELECT count(*) FROM dag WHERE NOT is_paused AND dag_id<>'website_orders';", 'airflow_meta') == '0', 'Unexpected enabled test DAG')
    require(h.sql("SELECT count(*) FROM dag_run WHERE state IN ('queued','running');", 'airflow_meta') == '0', 'Unexpected automatic test runs')
    h.dc(['up','--detach','scheduler-observer'])
    h.dc(['exec','-T','scheduler-observer','/opt/airflow/project-venv/bin/python','-m','orchestration.scheduler_probe','--once'])
    require(h.sql('SELECT count(*) FROM ops.scheduler_observations;') == '7', 'Scheduler sample count')
    h.dc(['stop','--timeout','30','airflow','scheduler-observer'])
    h.dc(['up','--detach','--wait','--wait-timeout','180','report'])
    h.dc(['exec','-T','report','python','-m','pip','check'])
    boundary = "import os; forbidden=('PLATFORM_INGEST_PASSWORD','PLATFORM_TRANSFORM_PASSWORD','PLATFORM_PUBLISHER_PASSWORD','AIRFLOW_APP_PASSWORD','ETSY_SIGNING_SECRET'); assert not any(k in os.environ for k in forbidden); assert not os.path.exists('/fixtures'); assert not os.path.exists('/var/run/docker.sock'); print('M08A report boundaries PASS')"
    h.dc(['exec','-T','report','python','-c',boundary])
    for test in ('test_m07_operations.py','test_m07_report.py'):
        h.run('report','python',f'/repo/tests/{test}',reads=True,timeout=180)
    h.dc(['exec','-T','report','python','-c',"import urllib.request; assert urllib.request.urlopen('http://localhost:8501/_stcore/health',timeout=5).read()==b'ok'"])
    print('M08A isolated fixed S01 + real report/UI checks PASS',flush=True)
