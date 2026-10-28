"""HTTP-only bounded eBay acquisition. Business transformation belongs to dbt."""
import argparse
import copy
import hashlib
import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

import psycopg
from psycopg.types.json import Jsonb
from ingestion.website import db_kwargs, parse_time

SOURCE = 'ebay_sim'
ACCOUNT = 'seller_sim_01'
ROOT = '/sell/fulfillment/v1/order'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def safe_url(url, origin, path=None):
    actual, allowed = urlsplit(url), urlsplit(origin)
    if (actual.scheme, actual.netloc) != (allowed.scheme, allowed.netloc) or actual.username or actual.password or actual.fragment:
        raise ValueError('untrusted resource origin')
    if path is not None and actual.path != path:
        raise ValueError('unexpected resource path')
    return url


def page_url(origin, start, end, offset=0):
    return origin + ROOT + '?' + urlencode({'filter': f'lastmodifieddate:[{start.isoformat()}..{end.isoformat()}]',
                                           'limit': 1, 'offset': offset})


def comparison_order(value):
    """Compare list/detail without treating documented representation gaps as changes.

    List cancelRequests is always empty; detail remains the authoritative raw.
    Fingerprinting and business transformations still belong exclusively to dbt.
    """
    result = copy.deepcopy(value)
    result.get('cancelStatus', {}).pop('cancelRequests', None)
    result['lineItems'] = sorted(result['lineItems'], key=lambda line: line['lineItemId'])
    return result


class Collector:
    def __init__(self, conn, args, run_id):
        self.conn, self.args, self.run_id = conn, args, run_id
        self.opener = build_opener(NoRedirect())

    def raw(self, url, kind, body, status, headers, metadata):
        raw_id = uuid.uuid4()
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            payload = None
        self.conn.execute('''INSERT INTO raw.raw_records
            (raw_record_id,run_id,source_system,source_account_id,resource_type,resource_locator,
             request_method,request_window_start,request_window_end,response_status,acquired_at,
             raw_bytes,parsed_payload,byte_sha256,contract_version,sanitized_headers,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,'GET',%s,%s,%s,%s,%s,%s,%s,'ebay-v0.1',%s,%s)''',
            (raw_id,self.run_id,SOURCE,ACCOUNT,kind,url,self.args.window_start,self.args.window_end,
             status,self.args.observed_at,body,Jsonb(payload),hashlib.sha256(body).digest(),
             Jsonb({k: v for k,v in headers.items() if k.lower() in ('content-type','retry-after')}),
             Jsonb(dict(metadata, execution_id=self.args.execution_id,
                        fetched_at=datetime.now(timezone.utc).isoformat()))))
        self.conn.commit()
        return raw_id, payload

    def get(self, url, kind, metadata=None):
        safe_url(url, self.args.origin)
        for attempt in range(1, 6):
            headers, status, body = {}, None, b''
            try:
                request = Request(url, headers={'Authorization': 'Bearer ' + os.environ.get('EBAY_SIM_TOKEN','local-s01-test-token')})
                with self.opener.open(request, timeout=10) as response:
                    body, status, headers = response.read(), response.status, dict(response.headers)
            except HTTPError as error:
                body, status, headers = error.read(), error.code, dict(error.headers)
            except (URLError, TimeoutError) as error:
                # No received body: retain the failed request with empty exact bytes.
                body = b''
            raw_id, payload = self.raw(url, kind, body, status, headers, dict(metadata or {}, http_attempt=attempt))
            if status == 200:
                if not isinstance(payload, dict):
                    raise ValueError('response is not a JSON object')
                return raw_id, payload
            if status not in (None,429,500,502,503,504) or attempt == 5:
                raise RuntimeError(f'HTTP acquisition failed status={status} raw={raw_id}')
            retry = headers.get('Retry-After')
            if retry is not None:
                try:
                    delay = float(retry)
                except ValueError:
                    delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                if delay > 60:
                    raise RuntimeError('Retry-After exceeds this bounded cycle; replay later')
            else:
                delay = min(2 ** (attempt-1), 30) + random.uniform(0, 0.25)
            time.sleep(max(0, delay))

    def order(self, value):
        if not isinstance(value, dict) or not isinstance(value.get('orderId'), str) or value.get('sellerId') != ACCOUNT:
            raise ValueError('missing order identity or seller mismatch')
        created, updated = parse_time(value['creationDate']), parse_time(value['lastModifiedDate'])
        if not created <= updated <= self.args.observed_at:
            raise ValueError('invalid source time')
        lines = value.get('lineItems')
        if not isinstance(lines, list) or not lines:
            raise ValueError('missing lines')
        ids = set()
        for line in lines:
            identity = line.get('lineItemId')
            if not isinstance(identity, str) or not identity or identity in ids:
                raise ValueError('missing or duplicate line identity')
            ids.add(identity)
            if type(line.get('quantity')) is not int or line['quantity'] <= 0:
                raise ValueError('invalid quantity')
        return value['orderId']

    def acquire(self):
        url = page_url(self.args.origin, self.args.window_start, self.args.window_end)
        offset, total, seen = 0, None, set()
        for page_number in range(1000):
            page_id, page = self.get(url, 'ebay_orders')
            if (type(page.get('total')) is not int or page['total'] < 0 or page.get('limit') != 1
                    or page.get('offset') != offset or not isinstance(page.get('orders'), list)):
                raise ValueError('malformed page envelope')
            safe_url(page['href'], self.args.origin, ROOT)
            if total is not None and total != page['total']:
                raise ValueError('mutable page total; reconcile window')
            total = page['total']
            if len(page['orders']) != min(1, max(0, total-offset)):
                raise ValueError('page count does not agree with total')
            jobs = []
            for order in page['orders']:
                order_id = self.order(order)
                if not self.args.window_start <= parse_time(order['lastModifiedDate']) <= self.args.window_end:
                    raise ValueError('order outside requested window')
                if order_id in seen:
                    continue
                seen.add(order_id)
                work_id = uuid.uuid4()
                self.conn.execute('''INSERT INTO ops.processing_work
                    (work_id,dedupe_key,work_type,source_system,source_account_id,source_entity_id,
                     trigger_raw_record_id,state,created_at,updated_at)
                    VALUES (%s,%s,'EBAY_ORDER_DETAILS',%s,%s,%s,%s,'PENDING',%s,%s)''',
                    (work_id,f'm05:{self.run_id}:{order_id}',SOURCE,ACCOUNT,order_id,page_id,
                     self.args.observed_at,self.args.observed_at))
                jobs.append((work_id,order_id,order))
            self.conn.commit()  # Durable identified work before the next page.
            if self.args.fail_after_page and page_number == 0:
                raise RuntimeError('intentional interruption after durable page/work')
            for work_id, order_id, listed in jobs:
                self.details(work_id, order_id, listed)
            offset += 1
            if offset >= total:
                if 'next' in page:
                    raise ValueError('unexpected next link')
                return
            next_url = safe_url(page['next'], self.args.origin, ROOT)
            if next_url != page_url(self.args.origin,self.args.window_start,self.args.window_end,offset):
                # Compare decoded query: percent-encoding alone is not a semantic difference.
                expected = urlsplit(page_url(self.args.origin,self.args.window_start,self.args.window_end,offset))
                actual = urlsplit(next_url)
                if parse_qs(actual.query) != parse_qs(expected.query):
                    raise ValueError('next link changed bounds/offset')
            url = next_url
        raise ValueError('page budget exhausted')

    def details(self, work_id, order_id, listed):
        path = ROOT + '/' + quote(order_id, safe='')
        order_raw_id, order = self.get(self.args.origin + path, 'ebay_order', {'order_id': order_id})
        if self.order(order) != order_id or comparison_order(order) != comparison_order(listed):
            raise ValueError('list/detail changed; reconcile rather than synthesize snapshot')
        metadata = {'order_id': order_id, 'order_raw_id': str(order_raw_id)}
        _, shipping = self.get(self.args.origin + path + '/shipping_fulfillment', 'ebay_fulfillments', metadata)
        fulfillments = shipping.get('fulfillments')
        if not isinstance(fulfillments, list) or shipping.get('total') != len(fulfillments):
            raise ValueError('malformed shipping envelope')
        ids = [f['fulfillmentId'] for f in fulfillments]
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate fulfillment identity')
        expected_hrefs = {self.args.origin + path + '/shipping_fulfillment/' + quote(x,safe='') for x in ids}
        if set(order.get('fulfillmentHrefs', [])) != expected_hrefs:
            raise ValueError('inconsistent fulfillment references')
        for href in order.get('fulfillmentHrefs', []):
            safe_url(href,self.args.origin)
            _, fulfillment = self.get(href,'ebay_fulfillment',metadata)
            if fulfillment not in fulfillments:
                raise ValueError('shipping list/detail changed')
        self.conn.execute("UPDATE ops.processing_work SET state='SUCCEEDED',cycle_attempts=1,updated_at=%s WHERE work_id=%s",
                          (self.args.observed_at,work_id))
        self.conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', default=os.environ.get('EBAY_ORIGIN','http://ebay-sim'))
    parser.add_argument('--window-start', type=parse_time)
    parser.add_argument('--window-end', required=True, type=parse_time)
    parser.add_argument('--observed-at', required=True, type=parse_time)
    parser.add_argument('--execution-id', required=True)
    parser.add_argument('--checkpoint-stream', choices=('orders','orders_polling'), default='orders')
    parser.add_argument('--overlap-seconds', type=int, default=120)
    parser.add_argument('--fail-after-page', action='store_true')
    args = parser.parse_args()
    if args.overlap_seconds < 0:
        parser.error('overlap must be nonnegative')
    with psycopg.connect(**db_kwargs('PLATFORM','data_platform','platform_ingest')) as conn:
        if args.window_start is None:
            prior = conn.execute('SELECT completed_window_end FROM ops.extraction_checkpoints WHERE source_system=%s AND source_account_id=%s AND stream_name=%s', (SOURCE,ACCOUNT,args.checkpoint_stream)).fetchone()
            if prior is None:
                parser.error('first acquisition requires --window-start')
            args.window_start = prior[0] - timedelta(seconds=args.overlap_seconds)
        if not args.window_start <= args.window_end <= args.observed_at:
            parser.error('require start <= end <= observed time')
        run_id = uuid.uuid4()
        conn.execute('''INSERT INTO ops.pipeline_runs
            (run_id,stage,source_system,source_account_id,stream_name,requested_window_start,
             requested_window_end,started_at,status,log_reference)
            VALUES (%s,'ACQUIRE',%s,%s,'orders',%s,%s,%s,'RUNNING',%s)''',
            (run_id,SOURCE,ACCOUNT,args.window_start,args.window_end,args.observed_at,f'm05:{args.execution_id}'))
        conn.commit()
        try:
            Collector(conn,args,run_id).acquire()
            conn.execute('''INSERT INTO ops.extraction_checkpoints
                (source_system,source_account_id,stream_name,completed_window_end,successful_run_id,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_system,source_account_id,stream_name) DO UPDATE
                SET completed_window_end=EXCLUDED.completed_window_end,successful_run_id=EXCLUDED.successful_run_id,updated_at=EXCLUDED.updated_at
                WHERE EXCLUDED.completed_window_end >= ops.extraction_checkpoints.completed_window_end''',
                (SOURCE,ACCOUNT,args.checkpoint_stream,args.window_end,run_id,args.observed_at))
            conn.execute("UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=%s WHERE run_id=%s", (args.observed_at,run_id))
            conn.commit()
            print(f'M05 acquire PASS run={run_id} execution={args.execution_id}')
        except Exception as error:
            conn.rollback()
            conn.execute("UPDATE ops.pipeline_runs SET status='FAILED',finished_at=%s,error_code=%s,error_message=%s WHERE run_id=%s",
                         (args.observed_at,type(error).__name__,str(error)[:1000],run_id))
            conn.execute("UPDATE ops.processing_work SET state='FAILED',last_error_code=%s,last_error_message=%s WHERE dedupe_key LIKE %s AND state='PENDING'",
                         (type(error).__name__,str(error)[:1000],f'm05:{run_id}:%'))
            conn.commit()
            raise


if __name__ == '__main__':
    main()
