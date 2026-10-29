"""Bounded Etsy inbox worker and independent HTTP recovery-list acquisition."""
import argparse
import json
import os
import re
import random
import math
import time
import uuid
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ingestion.website import parse_time
from ingestion.etsy_common import (connect, now, uid, shop, origin, validate_url,
                                   start_run, finish_run, raw_record, enqueue)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def retry_after_seconds(headers, reference):
    value=headers.get('Retry-After',headers.get('retry-after'))
    if not value:
        return 0
    try:
        delay=float(value)
    except ValueError:
        try:
            delay=(parsedate_to_datetime(value)-reference).total_seconds()
        except (ValueError,TypeError):
            return 0
    if not math.isfinite(delay) or delay>31536000:
        raise ValueError('unsupported Retry-After; retain response and review source configuration')
    return max(0,delay)


def require_source_ready(conn):
    row=conn.execute('''SELECT r.sanitized_headers,a.recorded_at
        FROM ops.etsy_http_attempts a JOIN raw.raw_records r USING(raw_record_id)
        WHERE r.source_system='etsy_sim' AND r.source_account_id=%s AND r.response_status IN (429,503)
          AND r.sanitized_headers ? 'retry-after' ORDER BY a.recorded_at DESC LIMIT 1''',(shop(),)).fetchone()
    if row and (now()-row[1]).total_seconds()<retry_after_seconds(row[0],row[1]):
        raise RuntimeError('source Retry-After cooldown not elapsed; no new HTTP attempt allocated')


def require_recovery_allowed(conn, receipt):
    failed=conn.execute('''SELECT w.work_id FROM ops.processing_work w
        WHERE w.source_system='etsy_sim' AND w.source_account_id=%s AND w.work_type='ETSY_RECEIPT'
          AND w.source_entity_id=%s AND w.state='FAILED' AND NOT EXISTS (
              SELECT 1 FROM ops.etsy_work_context x JOIN ops.processing_work replay ON replay.work_id=x.work_id
              WHERE x.replay_of_work_id=w.work_id AND replay.state='SUCCEEDED') LIMIT 1''',(shop(),str(receipt))).fetchone()
    if failed:
        raise RuntimeError('receipt has unresolved failed work; explicit controlled replay required')


def fetch(url):
    request = Request(url, headers={'Authorization': 'Bearer ' + os.environ['ETSY_SIM_TOKEN']})
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            body = response.read(2097153)
            return response.status, body, dict(response.headers)
    except HTTPError as error:
        return error.code, error.read(2097153), dict(error.headers)
    except (URLError, TimeoutError, OSError):
        return 599, b'', {'_transport_error':'network_or_timeout'}


def claim(conn, only=None, collection_run=None):
    require_source_ready(conn)
    row = conn.execute('''SELECT w.work_id,c.run_id,c.resource_url,w.cycle_attempts,w.inbox_id
        FROM ops.processing_work w JOIN ops.etsy_work_context c USING(work_id)
        WHERE w.work_type='ETSY_RECEIPT' AND w.source_account_id=%s
          AND w.cycle_attempts<5 AND (%s::UUID[] IS NULL OR w.work_id=ANY(%s::UUID[]))
          AND ((w.state='PENDING' AND (w.next_attempt_at IS NULL OR w.next_attempt_at<=now()))
               OR (w.state='LEASED' AND w.lease_until<=clock_timestamp()))
        ORDER BY w.created_at,w.work_id FOR UPDATE OF w SKIP LOCKED LIMIT 1''', (shop(), only, only)).fetchone()
    if not row:
        conn.commit()
        return None
    work, run, url, attempts, inbox = row
    token, number = uuid.uuid4(), attempts + 1
    conn.execute('''UPDATE ops.task_attempts SET status='FAILED',finished_at=GREATEST(%s,started_at),error_code='LEASE_EXPIRED'
        WHERE run_id=%s AND status='RUNNING' ''', (now(), run))
    conn.execute('''UPDATE ops.processing_work SET state='LEASED',lease_token=%s,
        lease_until=%s,cycle_attempts=%s,updated_at=%s WHERE work_id=%s''',
        (token, now() + timedelta(seconds=int(os.environ.get('ETSY_LEASE_SECONDS', '60'))), number, now(), work))
    conn.execute('''INSERT INTO ops.task_attempts(attempt_id,run_id,task_name,attempt_number,started_at,status,log_reference)
        VALUES (%s,%s,'receipt_http',%s,%s,'RUNNING',%s)''',
        (uid(f'{work}:attempt:{number}'), run, number, now(), f'm06:collector:{collection_run}' if collection_run else None))
    if inbox:
        conn.execute("UPDATE ops.webhook_inbox SET fetch_state='LEASED' WHERE inbox_id=%s", (inbox,))
    conn.commit()
    return work, run, url, number, inbox, collection_run, token


def process(conn, lease, observed=None):
    work, run, url, number, inbox, collection_run, token = lease
    receipt = validate_url(url, shop())
    status, body, headers = fetch(url)
    http_raw, payload = raw_record(conn, run, 'etsy_http', url, 'GET', None if '_transport_error' in headers else status, body, headers, observed,
                                   {'work_id': str(work), 'lease_token': str(token), 'attempt': number,
                                    'collection_run_id': str(collection_run) if collection_run else None,
                                    'transport_error':headers.get('_transport_error'),'body_truncated':len(body)>2097152})
    conn.execute('''INSERT INTO ops.etsy_http_attempts
        (attempt_id,work_id,run_id,lease_token,attempt_number,raw_record_id,recorded_at,collection_run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (uuid.uuid4(), work, run, token, number, http_raw, now(),collection_run))
    conn.commit()  # Preserve even an old owner's HTTP audit; fence business eligibility below.
    valid = (status == 200 and len(body) <= 2097152 and isinstance(payload, dict)
             and str(payload.get('receipt_id')) == receipt and isinstance(payload.get('transactions'), list))
    owned = conn.execute('''SELECT 1 FROM ops.processing_work WHERE work_id=%s AND state='LEASED'
        AND lease_token=%s AND lease_until>clock_timestamp() FOR UPDATE''', (work, token)).fetchone()
    if not owned:
        conn.rollback()
        raise RuntimeError('lease lost; response audited but not eligible for business publication')
    if valid:
        raw_record(conn, run, 'etsy_receipt', url, 'GET', status, body, headers, observed,
                   {'work_id': str(work), 'http_raw_id': str(http_raw),
                    'collection_run_id':str(collection_run) if collection_run else None})
    permanent = status in (400, 401, 403) or (status == 200 and not valid)
    terminal = not valid and (number == 5 or permanent)
    delay = min(2 ** number, 60) + random.uniform(0,0.25)
    if not valid:
        delay=max(delay,retry_after_seconds(headers,now()))
    conn.execute('''UPDATE ops.processing_work SET state=%s,lease_token=NULL,lease_until=NULL,
        next_attempt_at=%s,updated_at=%s,last_error_code=%s WHERE work_id=%s''',
        ('SUCCEEDED' if valid else 'FAILED' if terminal else 'PENDING',
         None if valid or terminal else now() + timedelta(seconds=delay), now(),
         None if valid else f'HTTP_{status}', work))
    conn.execute('''UPDATE ops.task_attempts SET status=%s,finished_at=GREATEST(%s,started_at),error_code=%s
        WHERE run_id=%s AND task_name='receipt_http' AND attempt_number=%s''',
        ('SUCCEEDED' if valid else 'FAILED' if terminal else 'RETRYABLE', now(),
         None if valid else f'HTTP_{status}', run, number))
    if inbox:
        conn.execute('UPDATE ops.webhook_inbox SET fetch_state=%s WHERE inbox_id=%s',
                     ('SUCCEEDED' if valid else 'FAILED' if terminal else 'PENDING', inbox))
    if valid or terminal:
        finish_run(conn, run, valid, None if valid else f'receipt HTTP {status}; unresolved, controlled replay required')
    conn.commit()
    return valid


def expire_exhausted(conn):
    rows = conn.execute('''UPDATE ops.processing_work SET state='FAILED',lease_token=NULL,lease_until=NULL,
        updated_at=clock_timestamp(),last_error_code='LEASE_EXHAUSTED' WHERE work_type='ETSY_RECEIPT'
        AND state='LEASED' AND lease_until<=clock_timestamp() AND cycle_attempts>=5 RETURNING work_id,inbox_id''').fetchall()
    for work, inbox in rows:
        run = conn.execute('SELECT run_id FROM ops.etsy_work_context WHERE work_id=%s', (work,)).fetchone()[0]
        finish_run(conn, run, False, 'exhausted interrupted lease')
        conn.execute("UPDATE ops.task_attempts SET status='FAILED',finished_at=GREATEST(clock_timestamp(),started_at),error_code='LEASE_EXHAUSTED' WHERE run_id=%s AND status='RUNNING'", (run,))
        if inbox:
            conn.execute("UPDATE ops.webhook_inbox SET fetch_state='FAILED' WHERE inbox_id=%s", (inbox,))
    conn.commit()


def drain(conn, observed=None, only=None, collection_run=None):
    expire_exhausted(conn)
    if only is None:
        only = [r[0] for r in conn.execute('''SELECT work_id FROM ops.processing_work
            WHERE work_type='ETSY_RECEIPT' AND source_account_id=%s AND state IN ('PENDING','LEASED')''', (shop(),))]
        conn.commit()
    if not only:
        return
    for _ in range(100):
        lease = claim(conn, only, collection_run)
        if not lease:
            break
        if not process(conn, lease, observed):
            raise RuntimeError('receipt work incomplete; attempts retained for next scheduled invocation')
    unfinished = conn.execute('''SELECT count(*) FROM ops.processing_work WHERE work_type='ETSY_RECEIPT'
        AND source_account_id=%s AND state<>'SUCCEEDED'
        AND (%s::UUID[] IS NULL OR work_id=ANY(%s::UUID[]))''', (shop(), only, only)).fetchone()[0]
    conn.commit()
    if unfinished:
        raise RuntimeError(f'{unfinished} receipt work items unresolved; no complete processing claim')


def recover(conn, args, run):
    offset, expected, works, seen, previous = 0, None, [], set(), None
    while True:
        url = origin() + f'/v3/application/shops/{shop()}/receipts?' + urlencode({
            'min_last_modified': int(args.window_start.timestamp()),
            'max_last_modified': int(args.window_end.timestamp()), 'limit': 1, 'offset': offset,
            'sort_on': 'updated', 'sort_order': 'asc'})
        prior = conn.execute('''SELECT r.response_status,r.parsed_payload,r.raw_record_id,
            count(*) OVER () FROM ops.etsy_http_attempts a JOIN raw.raw_records r USING(raw_record_id)
            WHERE a.run_id=%s AND a.work_id IS NULL AND r.resource_locator=%s
            ORDER BY a.recorded_at DESC LIMIT 1''', (run, url)).fetchone()
        success = bool(prior and prior[0] == 200)
        if success:
            status, payload, raw = prior[:3]
        for attempt in range((prior[3] if prior else 0) + 1, 6) if not success else ():
            require_source_ready(conn)
            status, body, headers = fetch(url)
            raw, payload = raw_record(conn, run, 'etsy_receipts', url, 'GET', None if '_transport_error' in headers else status, body, headers, args.observed_at,
                {'transport_error':headers.get('_transport_error'),'body_truncated':len(body)>2097152})
            conn.execute('''INSERT INTO ops.etsy_http_attempts
                (attempt_id,run_id,attempt_number,raw_record_id,recorded_at,collection_run_id) VALUES (%s,%s,%s,%s,%s,%s)''',
                (uuid.uuid4(), run, attempt, raw, now(),run))
            conn.commit()
            if status == 200 and len(body) <= 2097152:
                success = True
                break
            if status not in (429, 500, 502, 503, 504, 599) or attempt == 5:
                break
            delay=min(2 ** attempt,30)+random.uniform(0,0.25)
            delay=max(delay,retry_after_seconds(headers,now()))
            if delay>30:
                raise RuntimeError('recovery retry deferred; durable source Retry-After cooldown retained')
            time.sleep(delay)
        if not success or not isinstance(payload, dict):
            raise RuntimeError('recovery page failed; checkpoint unchanged')
        count, results = payload.get('count'), payload.get('results')
        if type(count) is not int or count < 0 or not isinstance(results, list) or len(results) > 1:
            raise ValueError('invalid count/results recovery envelope')
        if expected is not None and expected != count:
            raise ValueError('changing recovery count; retry/reconcile window')
        expected = count
        if count > 10000 or offset+len(results)>count:
            raise ValueError('invalid recovery page cardinality')
        for receipt in results:
            receipt_id = receipt.get('receipt_id')
            if type(receipt_id) is not int or receipt_id <= 0:
                raise ValueError('missing receipt identity')
            modified = receipt.get('updated_timestamp', receipt.get('update_timestamp'))
            if type(modified) is not int or not int(args.window_start.timestamp()) <= modified <= int(args.window_end.timestamp()):
                raise ValueError('receipt outside requested recovery window')
            order = (modified,receipt_id)
            if receipt_id in seen or (previous is not None and order <= previous):
                raise ValueError('duplicate or unsorted recovery page; reconcile window')
            seen.add(receipt_id)
            previous = order
            require_recovery_allowed(conn,receipt_id)
            works.append(enqueue(conn, f'recovery:{args.execution_id}:{receipt_id}', receipt_id, raw))
        conn.commit()
        offset += len(results)
        if offset >= count:
            break
        if not results or offset > 10000:
            raise ValueError('incomplete or excessive recovery paging')
    if works:
        drain(conn, args.observed_at, works, run)
    conn.execute('''INSERT INTO ops.extraction_checkpoints
        (source_system,source_account_id,stream_name,completed_window_end,successful_run_id,updated_at)
        VALUES ('etsy_sim',%s,%s,%s,%s,%s) ON CONFLICT (source_system,source_account_id,stream_name)
        DO UPDATE SET completed_window_end=EXCLUDED.completed_window_end,successful_run_id=EXCLUDED.successful_run_id,
            updated_at=EXCLUDED.updated_at WHERE ops.extraction_checkpoints.completed_window_end<=EXCLUDED.completed_window_end''',
        (shop(), args.checkpoint_stream, args.window_end, run, now()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('drain', 'recovery', 'replay'))
    p.add_argument('--work-id', type=uuid.UUID)
    p.add_argument('--execution-id', required=True)
    p.add_argument('--window-start', type=parse_time)
    p.add_argument('--window-end', type=parse_time)
    p.add_argument('--observed-at', type=parse_time)
    p.add_argument('--checkpoint-stream', default='receipts')
    args = p.parse_args()
    if not re.fullmatch(r'receipts(?:_polling|_test_[0-9a-f]{32})?',args.checkpoint_stream):
        p.error('invalid receipt checkpoint scope')
    if args.mode == 'replay' and args.work_id is None:
        p.error('explicit replay requires --work-id and a new execution identity')
    if args.observed_at is not None and args.observed_at > now():
        p.error('observation time cannot be in the future')
    if args.mode == 'recovery' and (args.window_start is None or args.window_end is None or args.window_start > args.window_end):
        p.error('recovery requires ordered explicit window bounds')
    if args.mode == 'recovery' and args.window_end > (args.observed_at or now()):
        p.error('recovery upper bound cannot exceed observation time')
    run = uid('collection:' + args.execution_id)
    with connect() as conn:
        conn.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))', (str(run),))
        prior = conn.execute('SELECT status,requested_window_start,requested_window_end FROM ops.pipeline_runs WHERE run_id=%s', (run,)).fetchone()
        bounds = (args.window_start, args.window_end) if args.mode == 'recovery' else (None, None)
        if prior and prior[1:] != bounds:
            raise ValueError('collection identity already bound to another window')
        if prior and prior[0] == 'SUCCEEDED':
            return
        start_run(conn, run, args.checkpoint_stream if args.mode == 'recovery' else 'inbox', f'm06:{args.execution_id}', bounds)
        conn.execute("UPDATE ops.pipeline_runs SET status='RUNNING',finished_at=NULL WHERE run_id=%s", (run,))
        conn.commit()
        try:
            if args.mode == 'recovery':
                recover(conn, args, run)
            elif args.mode == 'replay':
                old = conn.execute('''SELECT source_entity_id,trigger_raw_record_id,inbox_id FROM ops.processing_work
                    WHERE work_id=%s AND source_system='etsy_sim' AND source_account_id=%s AND work_type='ETSY_RECEIPT' ''', (args.work_id,shop())).fetchone()
                if not old:
                    raise ValueError('unknown Etsy work for replay')
                work = enqueue(conn, f'replay:{args.execution_id}:{args.work_id}', old[0], old[1], old[2],args.work_id)
                conn.commit()
                drain(conn, args.observed_at, [work], run)
            else:
                drain(conn, args.observed_at, collection_run=run)
            finish_run(conn, run, True)
            conn.commit()
        except Exception as error:
            conn.rollback()
            finish_run(conn, run, False, error)
            conn.commit()
            raise
    print(f'M06 {args.mode} PASS execution={args.execution_id}')


if __name__ == '__main__':
    main()
