"""Explicit, disposable collect-only PostgreSQL/HTTP qualification.

Host command: python tests/acquisition_db_probe.py
No Compose, owner credentials, published ports, dbt, Airflow or load campaign.
"""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit, urlencode
import uuid

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'de.probe=acquisition-db'


def host():
    name = 'collect-db-' + uuid.uuid4().hex[:12]
    report = ROOT / 'runtime' / (name + '.json')
    result = dict(scope='collect-only; NOT dbt parity, rollout, load or SLA',
                  container=name, status='FAILED', commands=[])

    def docker(*args, timeout=120):
        result['commands'].append(['docker', *args])
        completed = subprocess.run(['docker', *args], capture_output=True, text=True,
                                   encoding='utf-8', timeout=timeout)
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        return completed.stdout.strip()

    created = False
    runner = name + '-client'
    try:
        # Mark creation before the call: even a timed-out docker run needs cleanup.
        created = True
        docker('run', '--detach', '--name', name, '--label', LABEL, '--network', 'none',
               '--memory', '512m', '--cpus', '1', '--tmpfs', '/var/lib/postgresql/data',
               '--mount', f'type=bind,source={ROOT}/migrations,target=/migrations,readonly',
               '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:16.15-bookworm')
        for _ in range(40):
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'],
                                   capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('disposable PostgreSQL readiness timeout')
        roles = ('platform_owner', 'platform_ingest', 'platform_transform',
                 'platform_publisher', 'platform_report')
        docker('exec', name, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
               '-c', ';'.join(f'CREATE ROLE {role} LOGIN' for role in roles))
        docker('exec', name, 'createdb', '-U', 'postgres', '-O', 'platform_owner', 'data_platform')
        files = ['bootstrap/002_database_baseline.sql']
        files += ['platform/' + p.name for p in sorted((ROOT / 'migrations/platform').glob('*.sql'))
                  if int(p.name[:3]) <= 11 or p.name.startswith('014_')]
        for migration in files + ['platform/014_acquisition_elements.sql']:
            docker('exec', name, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
                   '-U', 'postgres', '-d', 'data_platform', '-f', '/migrations/' + migration)
        result['migrations'] = files
        result['migration014_second_apply'] = 'PASS'
        mounts = []
        for folder in ('ingestion', 'tests'):
            mounts += ['--mount', f'type=bind,source={ROOT}/{folder},target=/review/{folder},readonly']
        output = docker('run', '--rm', '--name', runner, '--label', LABEL,
                        '--network', 'container:' + name, '--read-only',
                        '--memory', '512m', '--cpus', '1', '--tmpfs', '/tmp',
                        '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/review',
                        '--workdir', '/review', *mounts,
                        '--entrypoint', '/opt/airflow/project-venv/bin/python',
                        'multi-channel-order-platform-airflow',
                        'tests/acquisition_db_probe.py', '--inside', timeout=240)
        result['test_output'] = output
        print(output)
        result['status'] = 'PASS'
    except Exception as error:
        result['error'] = str(error)
        print(str(error), file=sys.stderr)
    finally:
        if created:
            try:
                # A CLI timeout can leave its container alive. Stop only our
                # labelled runner before removing its labelled tmpfs database.
                pending = subprocess.run(['docker', 'inspect', '--format',
                                          '{{index .Config.Labels "de.probe"}}', runner],
                                         capture_output=True, text=True, timeout=15)
                if pending.returncode == 0:
                    if pending.stdout.strip() != 'acquisition-db':
                        raise RuntimeError('runner cleanup label mismatch')
                    docker('rm', '--force', runner)
                # Never remove an arbitrary container; exact fresh name AND label.
                actual = docker('inspect', '--format', '{{index .Config.Labels "de.probe"}}', name)
                if actual != 'acquisition-db':
                    raise RuntimeError('cleanup label mismatch')
                docker('rm', '--force', name)
                result['cleanup'] = 'PASS (only fresh tmpfs test DB removed)'
            except Exception as error:
                result['cleanup'] = str(error)
                result['status'] = 'FAILED'
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f"Collect DB probe {result['status']}; report={report}")
    return 0 if result['status'] == 'PASS' else 1


class CollectDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.pg = psycopg
        os.environ.update(PLATFORM_DB_HOST='127.0.0.1', PLATFORM_DB_PORT='5432',
                          PLATFORM_INGEST_PASSWORD='disposable-only', ETSY_SIM_TOKEN='probe-token')
        cls.admin = psycopg.connect(host='127.0.0.1', dbname='data_platform',
                                   user='postgres', autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        from tests.test_acquisition_reuse import order, receipt
        self.requests = []
        self.lock = threading.Lock()
        self.barrier = None
        self.barrier_paths = set()
        self.overlaps = set()
        self.failed_id = None
        self.orders = []
        self.receipts = []
        for index in range(4):
            value = order()
            value['orderId'] = 'db-order-' + str(index)
            value['lineItems'][0]['lineItemId'] = 'line-' + str(index)
            self.orders.append(value)
            value = receipt(8000 + index)
            value.update(created_timestamp=1792227600, updated_timestamp=1792227660 + index)
            self.receipts.append(value)
        owner = self

        class API(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parts = urlsplit(self.path)
                query = parse_qs(parts.query)
                with owner.lock:
                    owner.requests.append(parts.path)
                if parts.path in owner.barrier_paths:
                    owner.barrier.wait(timeout=10)
                    with owner.lock:
                        owner.overlaps.add(parts.path)
                code = 200
                if parts.path.endswith('/' + str(owner.failed_id)):
                    code, value = 403, {'error': 'intentional permanent source failure'}
                elif parts.path == '/sell/fulfillment/v1/order':
                    offset, limit = int(query['offset'][0]), int(query['limit'][0])
                    values = copy.deepcopy(owner.orders[offset:offset + limit])
                    for value in values:
                        value['cancelStatus']['cancelRequests'] = []
                        if value['orderId'] in getattr(owner, 'missing_orders', set()):
                            del value['pricingSummary']
                    value = dict(orders=values, total=len(owner.orders), offset=offset,
                                 limit=limit, href=owner.base + self.path)
                    if offset + limit < len(owner.orders):
                        value['next'] = owner.base + parts.path + '?' + urlencode(
                            {key: str(offset + limit) if key == 'offset' else item[0]
                             for key, item in query.items()})
                elif parts.path.startswith('/sell/fulfillment/v1/order/'):
                    identity = parts.path.split('/')[5]
                    value = next(copy.deepcopy(o) for o in owner.orders if o['orderId'] == identity)
                    if parts.path.endswith('/shipping_fulfillment'):
                        value = dict(total=0, fulfillments=[])
                elif parts.path == '/v3/application/shops/7001/receipts':
                    offset, limit = int(query['offset'][0]), int(query['limit'][0])
                    values = copy.deepcopy(owner.receipts[offset:offset + limit])
                    for value in values:
                        if value['receipt_id'] in getattr(owner, 'missing_receipts', set()):
                            del value['transactions']
                    value = dict(count=len(owner.receipts), results=values)
                else:
                    value = next(copy.deepcopy(r) for r in owner.receipts
                                 if str(r['receipt_id']) == parts.path.rsplit('/', 1)[1])
                body = json.dumps(value).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), API)
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        os.environ['ETSY_ORIGIN'] = self.base
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def scalar(self, sql, args=()):
        return self.admin.execute(sql, args).fetchone()[0]

    def cli(self, source, identity, success=True, end='2026-10-17T10:00:00Z'):
        args = [sys.executable, '-m', 'ingestion.' + source]
        if source == 'etsy':
            args += ['recovery']
        else:
            args += ['--origin', self.base]
        args += ['--execution-id', identity, '--window-start', '2026-10-17T09:00:00Z',
                 '--window-end', end, '--observed-at', '2026-10-17T11:00:00Z',
                 '--page-size', '2', '--acquisition-mode', 'page-reuse', '--detail-workers', '2']
        done = subprocess.run(args, capture_output=True, text=True, timeout=40)
        self.assertEqual(done.returncode == 0, success, done.stdout + done.stderr)
        if source == 'ebay':
            return uuid.uuid5(uuid.NAMESPACE_URL, 'ebay:page-reuse:' + identity)
        from ingestion.etsy_common import uid
        return uid('collection:' + identity)

    def denied(self, statement, args=(), role='postgres', sqlstate='P0001'):
        with self.pg.connect(host='127.0.0.1', dbname='data_platform', user=role) as conn:
            with self.assertRaises(self.pg.Error) as error:
                conn.execute(statement, args)
            conn.rollback()
            self.assertEqual(error.exception.sqlstate, sqlstate)

    def test_ebay_reuse_fallback_two_workers_retry_and_failure_barrier(self):
        root = '/sell/fulfillment/v1/order/'
        self.orders[2]['cancelStatus'] = dict(cancelState='CANCEL_REQUESTED',
                                             cancelRequests=[dict(cancelRequestId='request-1')])
        self.missing_orders = {'db-order-3'}
        self.barrier = threading.Barrier(2)
        self.barrier_paths = {root + 'db-order-0/shipping_fulfillment', root + 'db-order-1/shipping_fulfillment'}
        identity = 'ebay-db-' + uuid.uuid4().hex
        run = self.cli('ebay', identity)
        self.assertEqual(self.overlaps, self.barrier_paths)
        self.assertEqual(self.scalar('SELECT count(1) FROM ops.acquisition_elements WHERE collection_run_id=%s', (run,)), 2)
        self.assertEqual(self.scalar("SELECT count(1) FROM raw.raw_records WHERE run_id=%s AND resource_type='ebay_order'", (run,)), 2)
        self.assertEqual(self.scalar("SELECT count(1) FROM ops.processing_work WHERE dedupe_key LIKE %s AND state='SUCCEEDED'", (f'm05:{run}:%',)), 4)
        raw_count = self.scalar('SELECT count(1) FROM raw.raw_records WHERE run_id=%s', (run,))
        self.cli('ebay', identity)
        self.assertEqual(self.scalar('SELECT count(1) FROM raw.raw_records WHERE run_id=%s', (run,)), raw_count)
        self.assertEqual(self.scalar("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system='ebay_sim' AND stream_name='orders'"), run)
        self.barrier_paths = set()
        self.failed_id = 'db-order-2'
        failed = self.cli('ebay', identity + '-failed', success=False, end='2026-10-17T10:01:00Z')
        self.assertEqual(self.scalar('SELECT status FROM ops.pipeline_runs WHERE run_id=%s', (failed,)), 'FAILED')
        self.assertEqual(self.scalar("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system='ebay_sim' AND stream_name='orders'"), run)
        self.assertEqual(self.scalar('SELECT count(1) FROM raw.raw_records WHERE run_id=%s AND response_status=403', (failed,)), 1)
        self.assertEqual(self.scalar('SELECT count(1) FROM raw.raw_records WHERE byte_sha256<>sha256(raw_bytes)'), 0)
        self.assert_element_guards(run)

    def assert_element_guards(self, run):
        row = self.admin.execute('SELECT raw_record_id,source_entity_id,element_index,scan_number FROM ops.acquisition_elements WHERE collection_run_id=%s LIMIT 1', (run,)).fetchone()
        raw, entity, index, scan = row
        sql = 'INSERT INTO ops.acquisition_elements(raw_record_id,source_entity_id,element_index,collection_run_id,scan_number) VALUES(%s,%s,%s,%s,%s)'
        self.denied(sql, (raw, 'wrong-entity', 99, run, scan), 'platform_ingest')
        self.denied(sql, (raw, entity + '-wrong', index, run, 5), 'platform_ingest')
        self.denied('UPDATE ops.acquisition_elements SET recorded_at=clock_timestamp() WHERE raw_record_id=%s', (raw,))
        self.denied('DELETE FROM ops.collection_options WHERE run_id=%s', (run,))
        self.denied("UPDATE ops.ebay_collection_scans SET status='INVALID' WHERE run_id=%s", (run,))
        self.denied('SELECT raw_record_id FROM ops.acquisition_elements', role='platform_report', sqlstate='42501')
        self.assertTrue(self.scalar("SELECT has_table_privilege('platform_transform','cache.etsy_elements','INSERT')"))
        self.assertFalse(self.scalar("SELECT has_table_privilege('platform_ingest','cache.etsy_elements','INSERT')"))

    def test_etsy_reuse_fallback_two_workers_retry_and_failure_barrier(self):
        self.missing_receipts = {8002, 8003}
        self.barrier = threading.Barrier(2)
        self.barrier_paths = {f'/v3/application/shops/7001/receipts/{i}' for i in self.missing_receipts}
        identity = 'etsy-db-' + uuid.uuid4().hex
        run = self.cli('etsy', identity)
        self.assertEqual(self.overlaps, self.barrier_paths)
        self.assertEqual(self.scalar('SELECT count(1) FROM ops.acquisition_elements WHERE collection_run_id=%s', (run,)), 2)
        self.assertEqual(self.scalar("SELECT count(1) FROM raw.raw_records WHERE resource_type='etsy_receipt' AND metadata->>'collection_run_id'=%s", (str(run),)), 2)
        self.assertEqual(self.scalar('SELECT count(1) FROM ops.etsy_http_attempts WHERE collection_run_id=%s AND work_id IS NOT NULL', (run,)), 2)
        self.assertEqual(self.scalar('SELECT count(DISTINCT lease_token) FROM ops.etsy_http_attempts WHERE collection_run_id=%s AND work_id IS NOT NULL', (run,)), 2)
        before = len(self.requests)
        self.cli('etsy', identity)
        self.assertEqual(len(self.requests), before)
        self.barrier_paths = set()
        self.failed_id = 8002
        failed = self.cli('etsy', identity + '-failed', success=False, end='2026-10-17T10:01:00Z')
        self.assertEqual(self.scalar('SELECT status FROM ops.pipeline_runs WHERE run_id=%s', (failed,)), 'FAILED')
        self.assertEqual(self.scalar("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system='etsy_sim' AND stream_name='receipts'"), run)
        self.assertEqual(self.scalar('SELECT count(1) FROM ops.etsy_http_attempts a INNER JOIN raw.raw_records r USING(raw_record_id) WHERE a.collection_run_id=%s AND r.response_status=403', (failed,)), 1)
        row = self.admin.execute('SELECT raw_record_id,source_entity_id,element_index FROM ops.acquisition_elements WHERE collection_run_id=%s LIMIT 1', (run,)).fetchone()
        self.denied('INSERT INTO ops.acquisition_elements(raw_record_id,source_entity_id,element_index,collection_run_id,scan_number) VALUES(%s,%s,%s,%s,5)', (*row, run), 'platform_ingest')

    def test_options_constraints_and_stale_lease_response_fencing(self):
        from psycopg.types.json import Jsonb
        from ingestion import etsy
        from ingestion.etsy_common import connect, start_run, raw_record, enqueue
        run = uuid.uuid4()
        with connect() as conn:
            start_run(conn, run, 'receipt_work', 'collect-db-fencing')
            trigger, _ = raw_record(conn, run, 'etsy_receipts', self.base, 'GET', 200,
                                    json.dumps(dict(results=self.receipts)).encode(), {})
            work = enqueue(conn, 'fencing-' + str(run), 8000, trigger)
            conn.commit()
            lease = etsy.claim(conn, [work], run)
            self.assertIsNotNone(lease)
            stale = (*lease[:-1], uuid.uuid4())
            with self.assertRaisesRegex(RuntimeError, 'lease lost'):
                etsy.process(conn, stale)
        self.assertEqual(self.scalar("SELECT count(1) FROM raw.raw_records WHERE resource_type='etsy_receipt' AND metadata->>'collection_run_id'=%s", (str(run),)), 0)
        self.assertEqual(self.scalar('SELECT count(1) FROM ops.etsy_http_attempts WHERE collection_run_id=%s', (run,)), 1)
        self.assertEqual(self.scalar('SELECT state FROM ops.processing_work WHERE work_id=%s', (work,)), 'LEASED')
        good = dict(mode='page-reuse', workers=2, page_size=2)
        for changes in (dict(mode=None), dict(workers=None), dict(page_size=None),
                        dict(mode='legacy'), dict(workers=3), dict(page_size=0)):
            self.denied('INSERT INTO ops.collection_options(run_id,settings) VALUES(%s,%s)',
                        (run, Jsonb(dict(good, **changes))), 'platform_ingest', sqlstate='23514')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectDB)
        outcome = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
        sys.exit(0 if outcome.wasSuccessful() else 1)
    sys.exit(host())
