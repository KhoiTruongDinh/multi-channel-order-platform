"""Real local HTTP pagination; SQL is a test double, not PostgreSQL evidence."""
import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion import etsy
from ingestion.ebay import Collector, ROOT
from ingestion.pagination import page_size


@contextmanager
def source(count=51, fault=None):
    template = json.loads((Path(__file__).resolve().parents[1] /
                          'fixtures/s01/source_states/ebay/0902.json').read_text())['order']
    calls = []
    orders = []
    for n in range(count):
        order = copy.deepcopy(template)
        order['orderId'] = 'page-test-' + str(n)
        orders.append(order)

    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = urlsplit(self.path); q = parse_qs(path.query)
            calls.append((path.path, q))
            if path.query:
                limit, offset = int(q['limit'][0]), int(q['offset'][0])
                total = count + (1 if fault == 'count' and offset else 0)
                if path.path == ROOT:
                    origin = f'http://127.0.0.1:{self.server.server_port}'
                    def href(at, size=limit):
                        return origin + ROOT + '?' + urlencode(dict(
                            filter=q['filter'][0], limit=size, offset=at))
                    value = dict(total=total, limit=limit, offset=offset, href=href(offset),
                                 orders=orders[offset:offset+limit])
                    if fault == 'envelope': value['limit'] = limit + 1
                    if offset + limit < total:
                        value['next'] = href(offset+limit, limit+1 if fault == 'next' else limit)
                else:
                    values = [dict(receipt_id=200000000000+n, updated_timestamp=1000+n)
                              for n in range(offset, min(offset+limit, count))]
                    if fault == 'duplicate' and offset and values:
                        values[0] = dict(receipt_id=200000000000, updated_timestamp=1000)
                    value = dict(count=total, results=values)
            elif path.path.endswith('/shipping_fulfillment'):
                value = dict(total=0, fulfillments=[])
            else:
                value = copy.deepcopy(orders[int(path.path.rsplit('-', 1)[1])])
                if fault == 'detail': value['lastModifiedDate'] = '2026-10-17T09:02:01Z'
            raw = json.dumps(value).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), API)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


class PaginationTests(unittest.TestCase):
    def ebay(self, origin, size=None):
        args = argparse.Namespace(origin=origin, execution_id='pagination-test', fail_after_page=False,
            window_start=datetime(2026,10,17,9,tzinfo=timezone.utc),
            window_end=datetime(2026,10,17,9,3,tzinfo=timezone.utc),
            observed_at=datetime(2026,10,17,9,3,tzinfo=timezone.utc))
        if size is not None: args.page_size = size
        return Collector(Mock(), args, uuid.uuid4())

    def etsy_pages(self, origin, size=1):
        args = argparse.Namespace(page_size=size, observed_at=None,
            window_start=datetime.fromtimestamp(1000,timezone.utc),
            window_end=datetime.fromtimestamp(2000,timezone.utc))
        db = Mock()
        with patch.dict(os.environ, ETSY_ORIGIN=origin, ETSY_SIM_TOKEN='synthetic-local'), \
                patch.object(etsy, 'require_source_ready'), \
                patch.object(etsy, 'page_history', return_value=(0,None)), \
                patch.object(etsy, 'raw_record', side_effect=lambda *a:
                             (uuid.uuid4(), json.loads(a[6]))):
            return etsy.recovery_pages(db, args, uuid.uuid4(), 1)

    def test_page_size_bounds_and_types(self):
        for maximum in (100, 200):
            self.assertEqual(page_size('50', maximum), 50)
            for bad in (True, 0, -1, maximum+1, 1.5, '1.5', '', None):
                with self.subTest(bad=bad, maximum=maximum):
                    with self.assertRaises(ValueError): page_size(bad, maximum)

    def test_ebay_51_orders_use_three_list_pages_but_same_detail_calls(self):
        for size, expected in ((None,51), (20,3)):
            with source() as (origin,calls): self.ebay(origin,size).acquire()
            pages = [q for p,q in calls if p == ROOT]
            self.assertEqual(len(pages), expected)
            self.assertEqual(len(calls)-len(pages), 102)
            if size == 20: self.assertEqual([q['offset'] for q in pages], [['0'],['20'],['40']])

    def test_ebay_changed_next_limit_or_response_limit_is_rejected(self):
        for fault in ('next','envelope','count'):
            with source(5,fault) as (origin,calls):
                with self.assertRaises(ValueError): self.ebay(origin,2).acquire()

    def test_larger_pages_do_not_accept_changed_order_details(self):
        with source(5,'detail') as (origin,calls):
            with self.assertRaisesRegex(ValueError, 'list/detail changed'):
                self.ebay(origin,2).acquire()

    def test_ebay_empty_window_is_one_page(self):
        with source(0) as (origin,calls): self.ebay(origin,20).acquire()
        self.assertEqual(len(calls), 1)

    def test_larger_page_does_not_increase_order_budget(self):
        with source(1001) as (origin,calls):
            with self.assertRaisesRegex(ValueError, 'order budget exhausted'):
                self.ebay(origin,200).acquire()
        self.assertEqual(len(calls), 1)

    def test_etsy_51_receipts_use_three_list_pages(self):
        for size, expected in ((1,51), (20,3)):
            with source() as (origin,calls): rows = self.etsy_pages(origin,size)
            self.assertEqual(len(rows), 51)
            self.assertEqual(len(calls), expected)
            self.assertEqual(len({row[0] for row in rows}), 51)

    def test_etsy_count_drift_and_reordered_identity_still_fail(self):
        for fault in ('count','duplicate'):
            with source(5,fault) as (origin,calls):
                with self.assertRaises(etsy.PageSetChanged): self.etsy_pages(origin,2)

    def test_etsy_empty_window(self):
        with source(0) as (origin,calls): rows = self.etsy_pages(origin,20)
        self.assertEqual(rows, []); self.assertEqual(len(calls), 1)

    def test_etsy_direct_retry_cannot_change_retained_limit(self):
        db = Mock()
        db.execute.return_value.fetchall.return_value = [('http://source/receipts?limit=1&offset=0',)]
        with patch.object(etsy,'begin_scan') as begin:
            with self.assertRaisesRegex(ValueError, 'page size differs'):
                etsy.recover(db, argparse.Namespace(page_size=20), uuid.uuid4())
        begin.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)
