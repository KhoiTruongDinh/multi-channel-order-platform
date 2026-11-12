"""Bounded PostgreSQL staging parity/profile; session-temp writes, rollback only.

Run in the project Python environment with PLATFORM_* connection variables.
No dbt build, shared function replacement, publication or scheduler mutation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
BATCH = '00000000-0000-0000-0000-000000000001'


def render(text):
    from jinja2 import Environment, StrictUndefined
    return Environment(undefined=StrictUndefined).from_string(text).render(
        source=lambda schema, table: {'raw_records': 'pg_temp.probe_raw',
                                     'batch_inputs': 'pg_temp.probe_inputs'}[table],
        var=lambda name: BATCH,
    ).replace('build.canonical_jsonb_text', 'pg_temp.canonical_jsonb_text').strip().rstrip(';')


def synthetic(count):
    result = {key: [] for key in ('orders', 'order_items', 'payment_transactions',
                                 'cancellation_requests', 'shipments', 'shipment_items')}
    for n in range(count):
        order = f'order-{n}'
        result['orders'].append({'order_id': order, 'updated_at': '2026-11-08T00:00:00Z'})
        for line in range(3):
            result['order_items'].append({'order_id': order, 'order_item_id': f'{order}-{line}',
                                          'quantity': line + 1, 'unit_price': '12.30'})
            result['shipment_items'].append({'shipment_id': order, 'order_item_id': f'{order}-{line}'})
        result['payment_transactions'].append({'order_id': order, 'amount': '73.80'})
        result['shipments'].append({'order_id': order, 'shipment_id': order})
    return result


def reference(payload):
    """Independent shaping oracle; retain order, duplicates and SQL NULL matching."""
    result = []
    for order in payload.get('orders', []):
        oid = order.get('order_id')
        children = {'orders': [order]}
        for key in ('order_items', 'payment_transactions', 'cancellation_requests', 'shipments'):
            children[key] = [x for x in payload.get(key, []) if oid is not None and x.get('order_id') == oid]
        shipments = {x.get('shipment_id') for x in children['shipments'] if x.get('shipment_id') is not None}
        children['shipment_items'] = [x for x in payload.get('shipment_items', [])
                                      if x.get('shipment_id') is not None and x.get('shipment_id') in shipments]
        result.append(children)
    return result


def load(conn, payloads):
    from psycopg.types.json import Jsonb
    conn.execute('TRUNCATE pg_temp.probe_raw, pg_temp.probe_inputs')
    for index, payload in enumerate(payloads):
        rid = uuid.UUID(int=index + 10)
        conn.execute("""INSERT INTO pg_temp.probe_raw VALUES
            (%s,'internal_web','WEB01','2026-11-08T00:00:00Z',%s,%s,'website_order_window')""",
                     (rid, b'x' * 32, Jsonb(payload)))
        conn.execute('INSERT INTO pg_temp.probe_inputs VALUES (%s,%s)', (BATCH, rid))


def compare(conn, old, new):
    for name, sql in (('old', old), ('new', new)):
        conn.execute(f'DROP TABLE IF EXISTS pg_temp.probe_{name}')
        conn.execute(f'CREATE TEMP TABLE probe_{name} AS ' + sql)
    mismatch = conn.execute('''SELECT EXISTS(
        (SELECT * FROM pg_temp.probe_old EXCEPT ALL SELECT * FROM pg_temp.probe_new)
        UNION ALL
        (SELECT * FROM pg_temp.probe_new EXCEPT ALL SELECT * FROM pg_temp.probe_old))''').fetchone()[0]
    assert not mismatch, 'full staging multiset/fingerprint mismatch'
    return conn.execute('SELECT count(*) FROM pg_temp.probe_new').fetchone()[0]


def run(model, baseline, fixtures, canonical):
    import os
    import psycopg
    from jinja2 import Environment
    conn = psycopg.connect(host=os.environ.get('PLATFORM_DB_HOST', 'postgres'),
                           port=int(os.environ.get('PLATFORM_DB_PORT', '5432')),
                           dbname='data_platform', user='platform_transform',
                           password=os.environ['PLATFORM_TRANSFORM_PASSWORD'])
    result = {'scope': 'session-temp SQL only, not full dbt/load acceptance',
              'model_sha256': hashlib.sha256(model.encode()).hexdigest(),
              'baseline_sha256': hashlib.sha256(baseline.encode()).hexdigest(),
              'parity': [], 'invalid_arrays': [], 'benchmarks': []}
    try:
        conn.execute("SET LOCAL statement_timeout='90s'")
        conn.execute("SET LOCAL lock_timeout='2s'")
        conn.execute('''CREATE TEMP TABLE probe_raw(raw_record_id uuid PRIMARY KEY,
            source_system text,source_account_id text,acquired_at timestamptz,
            byte_sha256 bytea,parsed_payload jsonb,resource_type text)''')
        conn.execute('CREATE TEMP TABLE probe_inputs(batch_id uuid,raw_record_id uuid)')
        macro = Environment().from_string(canonical).module.create_canonical_jsonb_function()
        conn.execute(str(macro).replace('build.canonical_jsonb_text', 'pg_temp.canonical_jsonb_text'))
        old, new = render(baseline), render(model)
        edge = synthetic(3)
        edge['orders'].append(copy.deepcopy(edge['orders'][0]))
        edge['orders'].append({'order_id': None})
        edge['order_items'].extend([{'order_id': None}, {'order_id': 'orphan'}])
        edge['shipments'].append(copy.deepcopy(edge['shipments'][0]))
        edge['shipments'].append({'order_id': 'order-1', 'shipment_id': 'order-0'})
        edge['shipment_items'].extend([{'shipment_id': None}, {'shipment_id': 'orphan'}])
        for key in ('order_items', 'shipments', 'shipment_items'):
            edge[key].reverse()
        unicode_case = synthetic(1)
        unicode_case['order_items'][0]['title'] = 'Mug / ceramic \u2615'
        cases = [('s01', fixtures), ('edge-cases', [edge]),
                 ('missing-children', [{'orders': [{'order_id': 'empty'}]}]),
                 ('empty-orders', [synthetic(0)]), ('repeated-acquisition', [edge, edge]),
                 ('unicode', [unicode_case])]
        for label, payloads in cases:
            load(conn, payloads)
            count = compare(conn, old, new)
            expected = [child for payload in payloads for child in reference(payload)]
            actual = [row[0] for row in conn.execute('SELECT business_payload FROM pg_temp.probe_new')]
            normalize = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
            assert normalize(actual) == normalize(expected), 'independent payload oracle mismatch'
            # Check both SQL variants against the canonical Python fixture utility convention.
            for payload, fingerprint in conn.execute('SELECT business_payload,content_fingerprint FROM pg_temp.probe_new'):
                encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
                assert hashlib.sha256(encoded).digest() == bytes(fingerprint), 'canonical fingerprint mismatch'
            result['parity'].append({'case': label, 'rows': count})
        for value in (None, {}, 'invalid'):
            invalid = synthetic(1)
            invalid['order_items'] = value
            load(conn, [invalid])
            errors = []
            for sql in (old, new):
                try:
                    with conn.transaction():
                        conn.execute(sql).fetchall()
                except psycopg.Error as error:
                    errors.append(error.sqlstate)
                else:
                    errors.append(None)
            assert errors == ['22023', '22023'], f'invalid array handling changed: {errors}'
            result['invalid_arrays'].append({'value': value, 'sqlstates': errors})
        for size in (1, 10, 100, 300, 600):
            load(conn, [synthetic(size)])
            compare(conn, old, new)
            times = {'old': [], 'new': []}
            plans = {}
            # Alternate execution order to reduce a systematic first-run cache advantage.
            for trial in range(4):
                for name in (('old', 'new') if trial % 2 == 0 else ('new', 'old')):
                    sql = old if name == 'old' else new
                    plan = conn.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql).fetchone()[0][0]
                    times[name].append(plan['Execution Time'])
                    plans[name] = plan
            result['benchmarks'].append({'orders_per_raw': size, 'milliseconds': times,
                'median_ms': {key: statistics.median(value) for key, value in times.items()},
                'plans': plans})
            print(json.dumps({'benchmark_orders': size,
                              'median_ms': result['benchmarks'][-1]['median_ms']}), flush=True)
        # Bounded snapshot of actual raw; no shared candidate or operational writes.
        conn.execute('TRUNCATE pg_temp.probe_raw,pg_temp.probe_inputs')
        conn.execute('''INSERT INTO pg_temp.probe_raw
            SELECT raw_record_id,source_system,source_account_id,acquired_at,
                   byte_sha256,parsed_payload,resource_type
              FROM raw.raw_records WHERE source_system='internal_web'
               AND resource_type='website_order_window'
             ORDER BY acquired_at DESC,raw_record_id LIMIT 200''')
        conn.execute('INSERT INTO pg_temp.probe_inputs SELECT %s,raw_record_id FROM pg_temp.probe_raw', (BATCH,))
        result['parity'].append({'case': 'retained-raw-max200', 'rows': compare(conn, old, new),
                                'raw_records': conn.execute('SELECT count(*) FROM pg_temp.probe_raw').fetchone()[0]})
        result['status'] = 'PASS'
        print(json.dumps(result), flush=True)
        return result
    finally:
        conn.rollback()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', help='Existing project Airflow container; no restart/build')
    parser.add_argument('--report', type=Path, help='New local JSON evidence file; refuses overwrite')
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error('report already exists; choose a new evidence path')
    payload = dict(model=(ROOT / 'transformations/models/staging/stg_website_observations.sql').read_text(),
        baseline=(ROOT / 'tests/sql/website_staging_before.sql').read_text(),
        fixtures=[json.loads(p.read_text()) for p in sorted((ROOT / 'fixtures/s01/source_states/website').glob('*.json'))],
        canonical=(ROOT / 'transformations/macros/canonical_jsonb.sql').read_text())
    if args.container:
        payload['script'] = Path(__file__).read_text()
        bootstrap = ("import json,sys; p=json.load(sys.stdin); "
                     "n={'__name__':'probe','__file__':'/opt/project/tests/website_staging_probe.py'}; "
                     "exec(compile(p.pop('script'),n['__file__'],'exec'),n); n['run'](**p)")
        completed = subprocess.run(['docker', 'exec', '-i', args.container,
            '/opt/airflow/project-venv/bin/python', '-c', bootstrap],
            input=json.dumps(payload), text=True, capture_output=True, timeout=600)
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        result = json.loads(completed.stdout.splitlines()[-1])
    else:
        result = run(**payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key != 'benchmarks'}))
    for row in result['benchmarks']:
        print(json.dumps({'orders_per_raw': row['orders_per_raw'], 'median_ms': row['median_ms']}))


if __name__ == '__main__':
    main()
