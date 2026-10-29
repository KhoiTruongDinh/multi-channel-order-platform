"""Etsy HTTP/raw/operational helpers; business normalization belongs to dbt."""
import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import psycopg
from psycopg.types.json import Jsonb
from ingestion.website import db_kwargs

SOURCE = 'etsy_sim'


def now():
    return datetime.now(timezone.utc)


def uid(value):
    return uuid.uuid5(uuid.NAMESPACE_URL, 'm06:' + str(value))


def connect():
    return psycopg.connect(**db_kwargs('PLATFORM', 'data_platform', 'platform_ingest'),
                           connect_timeout=5,options='-c statement_timeout=15000 -c lock_timeout=10000')


def shop():
    value = os.environ.get('ETSY_SHOP_ID', '7001')
    if not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('invalid configured shop')
    if value != '7001':
        raise ValueError('the fixed local Etsy subset supports shop 7001 only')
    return value


def origin():
    return os.environ.get('ETSY_ORIGIN', 'http://etsy-sim').rstrip('/')


def receipt_url(receipt_id):
    return f'{origin()}/v3/application/shops/{shop()}/receipts/{receipt_id}'


def validate_url(url, account):
    if not re.fullmatch(r'[0-9]+',str(account)) or int(account)<=0:
        raise ValueError('invalid shop identity')
    account=str(int(account))
    parsed, allowed = urlsplit(url), urlsplit(origin())
    match = re.fullmatch(r'/v3/application/shops/([1-9][0-9]*)/receipts/([1-9][0-9]*)', parsed.path)
    if (parsed.scheme, parsed.netloc) != (allowed.scheme, allowed.netloc) or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('resource URL outside configured origin')
    if not match or match[1] != account or account != shop():
        raise ValueError('resource URL/shop mismatch')
    return match[2]


def secret():
    encoded = os.environ['ETSY_SIGNING_SECRET']
    if not encoded.startswith('whsec_'):
        raise ValueError('expected whsec_ encoded local signing secret')
    key = base64.b64decode(encoded[6:], validate=True)
    if not key:
        raise ValueError('empty signing secret')
    return key


def signature(message_id, timestamp, raw, key):
    digest = hmac.new(key, f'{message_id}.{timestamp}.'.encode() + raw, hashlib.sha256).digest()
    return 'v1,' + base64.b64encode(digest).decode()


def decode_json(body):
    return json.loads(body,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def verify(headers, raw, received, key, tolerance=300):
    try:
        message, stamp = headers['webhook-id'], headers['webhook-timestamp']
        if not message or len(message) > 200 or not re.fullmatch(r'[0-9]{1,12}', stamp):
            return False, False
        expected = signature(message, stamp, raw, key)
        valid = any(hmac.compare_digest(expected, entry) for entry in headers['webhook-signature'].split())
        return valid, abs(received.timestamp() - int(stamp)) <= tolerance
    except (KeyError, ValueError, TypeError):
        return False, False


def start_run(conn, run, stream, reference, bounds=(None, None)):
    conn.execute('''INSERT INTO ops.pipeline_runs
        (run_id,stage,source_system,source_account_id,stream_name,requested_window_start,
         requested_window_end,started_at,status,log_reference)
        VALUES (%s,'ACQUIRE',%s,%s,%s,%s,%s,%s,'RUNNING',%s) ON CONFLICT DO NOTHING''',
        (run, SOURCE, shop(), stream, *bounds, now(), reference))


def finish_run(conn, run, success, error=None):
    conn.execute('''UPDATE ops.pipeline_runs SET status=%s,finished_at=GREATEST(%s,started_at),error_code=%s,error_message=%s
        WHERE run_id=%s''', ('SUCCEEDED' if success else 'FAILED', now(),
        None if success else 'ETSY_ACQUISITION_FAILED', str(error)[:500] if error else None, run))


def raw_record(conn, run, kind, url, method, status, body, headers, observed=None, metadata=None):
    raw_id = uuid.uuid4()
    try:
        payload = decode_json(body)
    except (ValueError, UnicodeError):
        payload = None
    safe = {k.lower(): str(v)[:1000] for k, v in headers.items()
            if k.lower() in ('content-type', 'content-length', 'retry-after', 'webhook-id', 'webhook-timestamp', 'webhook-signature')}
    meta = dict(metadata or {}, fetched_at=now().isoformat(), observation_clock='s01' if observed else 'current')
    conn.execute('''INSERT INTO raw.raw_records
        (raw_record_id,run_id,source_system,source_account_id,resource_type,resource_locator,
         request_method,response_status,acquired_at,raw_bytes,parsed_payload,byte_sha256,
         contract_version,sanitized_headers,metadata)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'etsy-v0.1',%s,%s)''',
        (raw_id, run, SOURCE, shop(), kind, url, method, status, observed or now(), body,
         Jsonb(payload) if payload is not None else None, hashlib.sha256(body).digest(), Jsonb(safe), Jsonb(meta)))
    return raw_id, payload


def enqueue(conn, key, receipt_id, trigger_raw, inbox=None, replay_of=None):
    work, run = uid('work:' + key), uid('receipt-run:' + key)
    existing = conn.execute('SELECT work_id FROM ops.processing_work WHERE work_id=%s', (work,)).fetchone()
    if existing:
        return work
    start_run(conn, run, 'receipt_work', key)
    conn.execute('''INSERT INTO ops.processing_work
        (work_id,dedupe_key,work_type,source_system,source_account_id,source_entity_id,
         trigger_raw_record_id,inbox_id,state,created_at,updated_at)
        VALUES (%s,%s,'ETSY_RECEIPT',%s,%s,%s,%s,%s,'PENDING',%s,%s) ON CONFLICT DO NOTHING''',
        (work, 'm06:' + key, SOURCE, shop(), str(receipt_id), trigger_raw, inbox, now(), now()))
    conn.execute('''INSERT INTO ops.etsy_work_context(work_id,run_id,resource_url,cycle_id,replay_of_work_id)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (work, run, receipt_url(receipt_id), key,replay_of))
    return work
