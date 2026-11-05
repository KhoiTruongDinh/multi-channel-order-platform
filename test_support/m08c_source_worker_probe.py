"""Source worker commit/progress crash, SIGTERM drain and SIGKILL restart on test PG."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from unittest.mock import patch

import psycopg


def environment():
    values = dict(line.split('=', 1) for line in Path('/m08c/private.env').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    # The actual worker never receives warehouse/Airflow/admin credentials.
    keys = ('MARKETPLACE_WRITER_PASSWORD','WEBSITE_WRITER_PASSWORD','ETSY_SIGNING_SECRET')
    return dict({k: values[k] for k in keys}, PATH=os.environ['PATH'], PYTHONPATH='/opt/project',
                WEBSITE_DB_HOST='postgres', S02_DB_HOST='postgres')


def worker(crash, ready=None):
    from simulator import live_worker as source
    if ready:
        # A heartbeat from a completed real tick proves signal handlers were
        # installed. Do not terminate a just-spawned interpreter at import time.
        source.HEARTBEAT = Path('/tmp/m08c-worker-ready-' + ready)
    if crash:
        real = source.apply

        def commit_then_lose(payload):
            real(payload)
            os._exit(97)

        with patch.object(source, 'apply', side_effect=commit_then_lose):
            source.main()
    else:
        source.main()


def http_roles():
    from datetime import datetime, timezone
    from simulator.s02_temporal import LivePostgresStore
    from simulator import ebay_api, etsy_api
    values = dict(line.split('=', 1) for line in Path('/m08c/private.env').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    for kind, module in (('ebay', ebay_api), ('etsy', etsy_api)):
        def connect(kind=kind):
            return psycopg.connect(host='postgres',dbname='marketplace_sim',user='s02_' + kind + '_reader',
                password=values['S02_' + kind.upper() + '_READER_PASSWORD'],
                options='-c default_transaction_read_only=on -c statement_timeout=10000')
        with connect() as conn:
            assert conn.execute('SELECT DISTINCT source FROM s02.orders').fetchall() == [(kind + '_sim',)]
            assert not conn.execute("SELECT has_database_privilege(current_user,'data_platform','CONNECT')").fetchone()[0]
        store = LivePostgresStore(kind, connect=connect)
        with patch.object(module, 'make_store', return_value=store):
            state = module.State('/missing-fixtures-not-used')
        handler, _ = module.handlers(state)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        now = datetime.now(timezone.utc)
        if kind == 'ebay':
            path = '/sell/fulfillment/v1/order?' + urlencode(dict(filter='lastmodifieddate:[2026-01-08T00:00:00Z..' + now.isoformat() + ']', limit=1, offset=0))
            state.configure(dict(fail_offset=0, errors_left=1, error_status=429))
        else:
            path = '/v3/application/shops/7001/receipts?' + urlencode(dict(min_last_modified=1767830400,
                max_last_modified=int(now.timestamp()),limit=1,offset=0,sort_on='updated',sort_order='asc'))
            state.configure(dict(errors_left=1, error_status=429))
        request = Request('http://127.0.0.1:' + str(server.server_port) + path,
                          headers={'Authorization':'Bearer ' + os.environ[kind.upper() + '_SIM_TOKEN']})
        try:
            try:
                urlopen(request, timeout=10)
            except HTTPError as error:
                assert error.code == 429
            else:
                raise AssertionError('live-PG fault control was ignored')
            with urlopen(request, timeout=10) as response:
                payload = json.load(response)
                assert payload['orders' if kind == 'ebay' else 'results']
            if kind == 'ebay':
                state.configure(dict(repeat_page=True))
                with urlopen(request, timeout=10) as response:
                    first = json.load(response)
                second = Request(request.full_url.replace('offset=0','offset=1'),headers=dict(request.headers))
                with urlopen(second, timeout=10) as response:
                    repeated = json.load(response)
                assert first['orders'][0]['orderId'] == repeated['orders'][0]['orderId']
                assert first['total'] >= 2 and repeated['offset'] == 1
        finally:
            server.shutdown()
            server.server_close()
            thread.join(10)


def main(campaign):
    env = environment()
    def rows(sql, params=(), database='marketplace_sim'):
        user = 'marketplace_writer' if database == 'marketplace_sim' else 'website_writer'
        password = env['MARKETPLACE_WRITER_PASSWORD' if database == 'marketplace_sim' else 'WEBSITE_WRITER_PASSWORD']
        with psycopg.connect(host='postgres',dbname=database,user=user,password=password) as conn:
            return conn.execute(sql, params).fetchall()

    command = [sys.executable, '-m', 'test_support.m08c_source_worker_probe', 'worker']
    # Include test module import path, not credentials of the test controller.
    env['PYTHONPATH'] = '/repo:/opt/project'
    crash = subprocess.Popen(command + ['crash'], env=env)
    try:
        assert crash.wait(timeout=90) == 97, 'source commit/progress boundary not reached'
    finally:
        if crash.poll() is None:
            crash.kill()
            crash.wait()
    assert rows('SELECT count(*) FROM s02.live_website_progress WHERE campaign_id=%s', (campaign,))[0][0] == 0
    order = rows('SELECT DISTINCT order_id FROM s02.website_versions WHERE campaign_id=%s', (campaign,))[0][0]
    assert rows('SELECT count(*) FROM public.orders WHERE order_id=%s', (order,), 'website_source')[0][0] == 1
    for abrupt in (False, True, False):
        token = uuid.uuid4().hex
        ready = Path('/tmp/m08c-worker-ready-' + token)
        process = subprocess.Popen(command + ['normal', token], env=env)
        try:
            deadline = time.monotonic() + 100
            while not ready.is_file():
                assert process.poll() is None and time.monotonic() < deadline, 'worker did not finish a ready tick'
                time.sleep(.2)
            while True:
                due = rows('''SELECT count(*) FROM s02.website_versions v
                    JOIN s02.live_batches b USING(campaign_id)
                    LEFT JOIN s02.live_website_progress p USING(campaign_id,order_id)
                    WHERE v.campaign_id=%s AND v.sequence>coalesce(p.sequence,0)''', (campaign,))[0][0]
                if due == 0:
                    break
                assert process.poll() is None and time.monotonic() < deadline, 'worker did not recover progress'
                time.sleep(.5)
            process.kill() if abrupt else process.terminate()
            code = process.wait(timeout=30)
            assert code == (-9 if abrupt else 0), 'unexpected worker signal exit: ' + str(code)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            ready.unlink(missing_ok=True)
    assert rows('SELECT count(*) FROM public.orders WHERE order_id=%s', (order,), 'website_source')[0][0] == 1
    deadline = time.monotonic() + 90
    while rows('''SELECT count(*) FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
        WHERE v.campaign_id=%s AND v.visible_at+make_interval(secs=>b.shift_seconds::double precision)>clock_timestamp()''', (campaign,))[0][0]:
        assert time.monotonic() < deadline, 'marketplace initial visibility deadline'
        time.sleep(.5)
    http_roles()
    print(json.dumps(dict(status='PASS', campaign_id=campaign, order_id=order,
        assertions='commit/progress crash repaired; SIGTERM drains; SIGKILL restart; one source order; actual live-PG HTTP/RLS/429')))


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        worker(sys.argv[2] == 'crash', sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        main(sys.argv[1])
