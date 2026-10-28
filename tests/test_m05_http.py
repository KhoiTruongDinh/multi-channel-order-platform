"""Real HTTP traversal with disposable in-memory source; no platform mutations."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simulator.ebay_api import State, handlers, ROOT
from ingestion.ebay import Collector, parse_time, safe_url


class AuditConnection:
    def __init__(self):
        self.writes = []
        self.commits = 0

    def execute(self, sql, params):
        self.writes.append((sql,params))

    def commit(self):
        self.commits += 1


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = State(Path(__file__).resolve().parents[1] / 'fixtures/s01/source_states/ebay')
        api,_ = handlers(cls.state)
        cls.server = ThreadingHTTPServer(('127.0.0.1',0),api)
        cls.origin = 'http://127.0.0.1:' + str(cls.server.server_port)
        os.environ['EBAY_PUBLIC_ORIGIN'] = cls.origin
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        os.environ.pop('EBAY_PUBLIC_ORIGIN',None)

    def setUp(self):
        self.state.configure({'state':'0902'})
        self.conn = AuditConnection()
        self.args = argparse.Namespace(origin=self.origin,window_start=parse_time('2026-10-17T09:00:00Z'),
            window_end=parse_time('2026-10-17T09:03:00Z'), observed_at=parse_time('2026-10-17T09:03:00Z'),
            execution_id='unit-http',fail_after_page=False)

    def collector(self):
        return Collector(self.conn,self.args,uuid.uuid4())

    def test_two_distinct_order_pages(self):
        self.state.configure({'state':'0902','extra_order':True})
        self.collector().acquire()
        jobs = [params for sql,params in self.conn.writes if 'INSERT INTO ops.processing_work' in sql]
        self.assertEqual({j[4] for j in jobs},{'12-10001-10001','12-10001-10002'})
        raws = [p for sql,p in self.conn.writes if 'INSERT INTO raw.raw_records' in sql]
        self.assertEqual(len(raws),6)  # Two pages, two details, two empty fulfillment collections.

    def test_repeat_page_retained_but_one_work(self):
        self.state.configure({'state':'0902','repeat_page':True})
        self.collector().acquire()
        self.assertEqual(sum('INSERT INTO ops.processing_work' in sql for sql,_ in self.conn.writes),1)
        self.assertEqual(sum('INSERT INTO raw.raw_records' in sql for sql,_ in self.conn.writes),4)

    def test_list_cancellation_gap_preserves_detail(self):
        self.state.data['order']['cancelStatus']['cancelRequests']=[{'cancelRequestId':'test-request'}]
        self.collector().acquire()
        detail = [p[11].obj for sql,p in self.conn.writes if 'INSERT INTO raw.raw_records' in sql and p[4]=='ebay_order']
        self.assertEqual(detail[0]['cancelStatus']['cancelRequests'],[{'cancelRequestId':'test-request'}])

    def test_untrusted_next_fails_after_durable_page(self):
        self.state.configure({'state':'0902','repeat_page':True,'bad_next':True})
        with self.assertRaisesRegex(ValueError,'untrusted'):
            self.collector().acquire()
        self.assertGreater(self.conn.commits,0)

    def test_empty_window_success(self):
        self.args.window_start=parse_time('2026-10-17T09:04:00Z')
        self.args.window_end=self.args.observed_at=parse_time('2026-10-17T09:05:00Z')
        self.collector().acquire()
        self.assertEqual(sum('INSERT INTO raw.raw_records' in sql for sql,_ in self.conn.writes),1)
        self.assertFalse(any('processing_work' in sql for sql,_ in self.conn.writes))

    def test_origin_guard(self):
        for value in ('http://untrusted.invalid/x',self.origin+'@untrusted.invalid/x',self.origin+'/x#secret'):
            with self.assertRaises(ValueError):
                safe_url(value,self.origin)

    def test_invalid_limit_and_no_shipping_pagination(self):
        collector=self.collector()
        with self.assertRaisesRegex(RuntimeError,'status=400'):
            collector.get(self.origin+ROOT+'?filter=lastmodifieddate:[2026-10-17T09:00:00Z..2026-10-17T09:03:00Z]&limit=201','ebay_orders')
        _,response=collector.get(self.origin+ROOT+'/12-10001-10001/shipping_fulfillment','ebay_fulfillments')
        self.assertEqual(response,{'total':0,'fulfillments':[]})


if __name__=='__main__':
    unittest.main(verbosity=2)
