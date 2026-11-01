"""Actual local HTTP + production collector; audit DB is a test double, not PG proof."""
import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.ebay import Collector, parse_time
from simulator.ebay_api import State, handlers, ROOT
from simulator.http_faults import Faults


class Audit:
    def __init__(self):
        self.writes = []
        self.commits = 0

    def execute(self, sql, params):
        self.writes.append((sql, params))

    def commit(self):
        self.commits += 1

    def raws(self):
        return [p for sql, p in self.writes if 'INSERT INTO raw.raw_records' in sql]


@contextmanager
def server(handler):
    http = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(http.server_port)
    try:
        with patch.dict(os.environ, EBAY_PUBLIC_ORIGIN=origin):
            yield origin
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)


def collector(origin):
    audit = Audit()
    args = argparse.Namespace(origin=origin, window_start=parse_time('2026-10-17T09:00:00Z'),
        window_end=parse_time('2026-10-17T09:03:00Z'), observed_at=parse_time('2026-10-17T09:03:00Z'),
        execution_id='m08c-http', fail_after_page=False)
    return Collector(audit, args, uuid.uuid4()), audit


class FaultTests(unittest.TestCase):
    def test_fault_config_is_bounded_and_health_never_consumes_it(self):
        for bad in (True, 'malformed', dict(kind='unknown'), dict(kind='timeout',count=6),
                    dict(kind='timeout',delay_seconds=float('inf')), dict(kind='malformed',offset=1001)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    Faults(bad)
        fault = Faults(dict(kind='malformed',count=1,offset=1))
        self.assertIsNone(fault.response('/health',200))
        self.assertIsNone(fault.response('/orders?offset=0',200))
        self.assertIsNone(fault.response('/orders?offset=1',500))
        self.assertEqual(fault.response('/orders?offset=1',200),b'{intentional-malformed-json')
        self.assertIsNone(fault.response('/orders?offset=1',200))

    def test_real_simulator_malformed_control_is_opt_in_and_resets(self):
        self.state.configure(dict(state='0902',transport_fault=dict(kind='malformed',count=1)))
        api, _ = handlers(self.state)
        with server(api) as origin:
            worker, audit = collector(origin)
            with self.assertRaises(ValueError):
                worker.acquire()
            self.assertEqual(audit.raws()[0][10],b'{intentional-malformed-json')
            self.state.configure(dict(state='0902'))
            worker.acquire()

    def setUp(self):
        self.state = State(Path(__file__).resolve().parents[1] / 'fixtures/s01/source_states/ebay')

    def test_transient_429_and_500_preserve_each_response(self):
        for status in (429, 500):
            with self.subTest(status=status):
                self.state.configure(dict(state='0902', fail_offset=0, errors_left=2, error_status=status))
                api, _ = handlers(self.state)
                with server(api) as origin, patch('ingestion.ebay.time.sleep'):
                    worker, audit = collector(origin)
                    worker.acquire()
                    self.assertEqual([p[8] for p in audit.raws()][:3], [status, status, 200])
                    self.assertEqual(len(audit.raws()), 5)
                    self.assertGreaterEqual(audit.commits, 5)

    def test_retry_exhaustion_stops_at_five_attempts(self):
        self.state.configure(dict(state='0902', fail_offset=0, errors_left=9, error_status=500))
        api, _ = handlers(self.state)
        with server(api) as origin, patch('ingestion.ebay.time.sleep'):
            worker, audit = collector(origin)
            with self.assertRaisesRegex(RuntimeError, 'status=500'):
                worker.acquire()
            self.assertEqual(len(audit.raws()), 5)
            self.assertEqual(self.state.errors_left, 4)
            self.assertFalse(any('extraction_checkpoints' in sql for sql, _ in audit.writes))

    def test_mid_page_failure_keeps_first_page_and_replay_audits(self):
        self.state.configure(dict(state='0902', extra_order=True, fail_offset=1, errors_left=5))
        api, _ = handlers(self.state)
        with server(api) as origin, patch('ingestion.ebay.time.sleep'):
            worker, audit = collector(origin)
            with self.assertRaises(RuntimeError):
                worker.acquire()
            before = len(audit.raws())
            self.assertEqual(before, 8)  # page/detail/fulfillments, then five failing next pages
            worker.acquire()
            self.assertEqual(len(audit.raws()), before + 6)
            self.assertTrue(all('extraction_checkpoints' not in sql for sql, _ in audit.writes))

    def test_malformed_200_retains_exact_bytes_before_rejection(self):
        class Broken(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = b'{not-json'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with server(Broken) as origin:
            worker, audit = collector(origin)
            with self.assertRaisesRegex(ValueError, 'JSON object'):
                worker.get(origin + ROOT, 'ebay_orders')
            self.assertEqual(len(audit.raws()), 1)
            self.assertEqual(audit.raws()[0][10], b'{not-json')
            self.assertEqual(audit.commits, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
