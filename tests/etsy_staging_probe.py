"""Offline SQL builder + opt-in disposable PostgreSQL parity/profile probe.

No owner database, network, credentials, volumes or running services are used.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
BATCH = '00000000-0000-0000-0000-000000000001'


def render(text,version='a'*32):
    text=text.replace('{{ batch_uuid() }}',"'"+BATCH+"'::UUID")
    cache=(ROOT/'transformations/macros/etsy_cache.sql').read_text()
    inputs=re.search(r'{% macro etsy_cache_inputs\(\) %}(.*?){% endmacro %}',cache,re.S).group(1)
    inputs=inputs.replace('{{ batch_uuid() }}',"'"+BATCH+"'::UUID")
    text=text.replace('{{ config(pre_hook=populate_etsy_cache()) }}','')
    text=text.replace('{{ config(pre_hook="{{ populate_etsy_cache() }}") }}','')
    text=text.replace('{{ etsy_cache_inputs() }}',inputs)
    text=text.replace('{{ etsy_cache_version() }}',version)
    text=text.replace("{{ source('canonical_cache','etsy_payloads') }}",'cache.etsy_payloads')
    text = re.sub(r"{{\s*source\('acquisition','raw_records'\)\s*}}", 'probe_raw', text)
    text = re.sub(r"{{\s*source\('operations','batch_inputs'\)\s*}}", 'probe_inputs', text)
    return re.sub(r'{{\s*var\("batch_id"\)\s*}}', BATCH, text)


def model_sql(version='a'*32):
    return render((ROOT/'transformations/models/etsy/stg_etsy_observations.sql').read_text(),version)


def cache_sql(version='a'*32):
    text=(ROOT/'transformations/macros/etsy_cache.sql').read_text()
    return render(re.search(r'{% macro populate_etsy_cache\(\) %}(.*?){% endmacro %}',text,re.S).group(1),version)


BASELINE = """SELECT r.*, build.etsy_canonical_json(r.parsed_payload) AS order_json,
sha256(convert_to(build.canonical_jsonb_text(build.etsy_canonical_json(r.parsed_payload)), 'UTF8')) AS content_fingerprint
FROM probe_raw r JOIN probe_inputs i USING(raw_record_id)
WHERE i.batch_id='%s'::uuid AND r.source_system='etsy_sim'
AND r.source_account_id='7001' AND r.resource_type='etsy_receipt' AND r.response_status=200""" % BATCH


def literal(value):
    return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"


def canonical(value):
    """Independent fixture-compatible alias/collection normalization."""
    value = copy.deepcopy(value)
    for alias, main in (('create_timestamp', 'created_timestamp'), ('update_timestamp', 'updated_timestamp')):
        if alias in value:
            if main in value and value[alias] != value[main]:
                raise ValueError('Conflicting Etsy timestamp alias')
            value[main] = value.pop(alias)

    def visit(node):
        if isinstance(node, list):
            return [visit(child) for child in node]
        if not isinstance(node, dict):
            return node
        result = {}
        for key, child in node.items():
            child = visit(child)
            identity = {'transactions': 'transaction_id', 'lineItems': 'lineItemId',
                        'fulfillments': 'fulfillmentId'}.get(key)
            if identity and isinstance(child, list):
                child = sorted(child, key=lambda item: str(item[identity]))
            result[key] = child
        return result
    return visit(value)


def setup_sql():
    functions = []
    for path in ('canonical_jsonb.sql', 'ebay_canonical.sql', 'etsy.sql'):
        text = (ROOT / 'transformations/macros' / path).read_text()
        functions.append(text.split('%}', 1)[1].split('{% endmacro %}', 1)[0])
    return 'CREATE SCHEMA build;\n' + '\n'.join(functions) + """
CREATE TABLE probe_raw(raw_record_id uuid PRIMARY KEY, source_system text,
source_account_id text, acquired_at timestamptz, byte_sha256 bytea,
parsed_payload jsonb, resource_type text, response_status integer, audit_note text);
CREATE TABLE probe_inputs(batch_id uuid,raw_record_id uuid);
"""


def load_sql(payloads):
    sql = 'TRUNCATE probe_raw,probe_inputs;\n'
    for index, payload in enumerate(payloads):
        rid = uuid.UUID(int=index + 10)
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        sql += f"INSERT INTO probe_raw VALUES ('{rid}','etsy_sim','7001','2026-11-12T00:00:00Z',decode('{digest}','hex'),{literal(payload)},'etsy_receipt',200,'retained');\n"
        sql += f"INSERT INTO probe_inputs VALUES ('{BATCH}','{rid}');\n"
    return sql


def run():
    name = 'etsy-staging-probe-' + uuid.uuid4().hex[:12]
    label = 'de.probe=etsy-staging'

    def docker(*args, **kwargs):
        return subprocess.run(['docker', *args], check=True, text=True, encoding='utf-8',
                              capture_output=True, timeout=120, **kwargs).stdout

    def query(sql):
        return docker('exec', '-i', name, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                      '-U', 'postgres', input="SET statement_timeout='30s';\n" + sql).strip()

    result = {'scope': 'disposable SQL only; NOT full dbt/cadence/load acceptance',
              'benchmark_scope': 'warm cached SELECT only; cache population and full workflow excluded',
              'parity': [], 'errors': [], 'benchmarks': []}
    try:
        docker('run', '--detach', '--name', name, '--label', label, '--network', 'none',
               '--memory', '512m', '--cpus', '1', '--tmpfs', '/var/lib/postgresql/data',
               '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
               '--health-cmd', 'pg_isready -h 127.0.0.1 -U postgres', '--health-interval', '1s',
               '--health-retries', '30', 'postgres:16.15-bookworm')
        # Poll readiness without starting or changing the owner's stack.
        import time
        for _ in range(40):
            if docker('inspect', '--format', '{{.State.Health.Status}}', name).strip() == 'healthy':
                break
            time.sleep(1)
        else:
            raise RuntimeError('disposable PostgreSQL did not become healthy')
        query(setup_sql())
        query('CREATE ROLE platform_owner; CREATE ROLE platform_transform; CREATE TABLE public.schema_migrations(migration_name text PRIMARY KEY);')
        query((ROOT/'migrations/platform/010_etsy_payload_cache.sql').read_text())
        query((ROOT/'migrations/platform/010_etsy_payload_cache.sql').read_text())
        fixtures = [json.loads(p.read_text()) for p in sorted((ROOT / 'fixtures/s01/source_states/etsy').glob('*.json'))]
        aliases = copy.deepcopy(fixtures[0])
        aliases['create_timestamp'] = aliases['created_timestamp']
        aliases['update_timestamp'] = aliases.pop('updated_timestamp')
        aliases['transactions'].reverse()
        aliases['probe_unicode'] = 'Mug / \u2615'
        empty = copy.deepcopy(fixtures[0]); empty['transactions'] = []
        missing = copy.deepcopy(fixtures[0]); missing.pop('transactions', None)
        cases = [('s01', fixtures), ('aliases-order-unicode', [aliases]),
                 ('empty', [empty]), ('missing', [missing]), ('repeated', fixtures * 2)]
        for case, payloads in cases:
            query(load_sql(payloads))
            query('BEGIN; '+cache_sql()+' COMMIT;')
            before=query('SELECT count(*) FROM cache.etsy_payloads')
            query('BEGIN; '+cache_sql()+' COMMIT;')
            assert query('SELECT count(*) FROM cache.etsy_payloads')==before, 'warm reuse inserted more rows'
            query('DROP TABLE IF EXISTS old_result,new_result; CREATE TABLE old_result AS ' + BASELINE +
                  '; CREATE TABLE new_result AS ' + model_sql())
            assert query('SELECT NOT EXISTS((TABLE old_result EXCEPT ALL TABLE new_result) UNION ALL '
                         '(TABLE new_result EXCEPT ALL TABLE old_result));') == 't', case
            actual = json.loads(query("SELECT json_agg(json_build_object('payload',order_json,'hash',encode(content_fingerprint,'hex')) ORDER BY raw_record_id) FROM new_result"))
            for payload, row in zip(payloads, actual, strict=True):
                expected = canonical(payload)
                assert row['payload'] == expected, case
                digest = hashlib.sha256(json.dumps(expected, ensure_ascii=False, sort_keys=True,
                                                   separators=(',', ':')).encode()).hexdigest()
                assert row['hash'] == digest, case
            result['parity'].append({'case': case, 'rows': len(actual)})
        # Only eligible, manifested, successful receipts are shaped.
        query(load_sql(fixtures))
        query("UPDATE probe_raw SET source_account_id='other';")
        assert query('SELECT count(*) FROM (' + model_sql() + ') q') == '0'
        result['parity'].append({'case': 'wrong-account-excluded', 'rows': 0})
        conflict = copy.deepcopy(fixtures[0]); conflict['update_timestamp'] = -1
        duplicate = copy.deepcopy(fixtures[0]); duplicate['transactions'] *= 2
        for case, payload in [('conflicting-alias', conflict), ('duplicate-line-id', duplicate)]:
            query(load_sql([payload]))
            errors = []
            for sql in (BASELINE, model_sql()):
                try:
                    if sql != BASELINE: query('BEGIN; '+cache_sql()+' COMMIT;')
                    query('SELECT count(*) FROM (' + sql + ') q WHERE order_json IS NOT NULL')
                except subprocess.CalledProcessError as error:
                    errors.append(error.stderr.split('ERROR:', 1)[-1].splitlines()[0].strip())
                else:
                    raise AssertionError('invalid payload was accepted: ' + case)
            assert errors[0] == errors[1], errors
            result['errors'].append({'case': case, 'message': errors[0]})
        for size in (10, 100, 300):
            query(load_sql([fixtures[0]] * size))
            query('BEGIN; '+cache_sql()+' COMMIT;')
            times = {'old': [], 'new': []}
            for trial in range(4):
                for key in (('old', 'new') if trial % 2 == 0 else ('new', 'old')):
                    sql = BASELINE if key == 'old' else model_sql()
                    plan = json.loads(query('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + sql))[0]
                    times[key].append(plan['Execution Time'])
            result['benchmarks'].append({'raw_receipts': size, 'milliseconds': times,
                                        'median_ms': {key: statistics.median(values) for key, values in times.items()}})
        query(load_sql(fixtures))
        query('BEGIN; '+cache_sql()+' COMMIT;')
        old_count=int(query('SELECT count(*) FROM cache.etsy_payloads'))
        query('BEGIN; '+cache_sql('b'*32)+' COMMIT;')
        assert int(query('SELECT count(*) FROM cache.etsy_payloads'))==old_count+2
        assert query('SELECT count(*) FROM ('+model_sql('b'*32)+') q')=='2'
        result['parity'].append({'case':'new-code-version','rows':2})
        # A populated cache entry outside the manifest must not leak into staging.
        query("DELETE FROM probe_inputs WHERE raw_record_id='00000000-0000-0000-0000-00000000000b'")
        assert query('SELECT count(*) FROM ('+model_sql()+') q')=='1'
        query("INSERT INTO probe_inputs VALUES ('"+BATCH+"','00000000-0000-0000-0000-00000000000b')")
        assert query('SELECT count(*) FROM ('+model_sql()+') q')=='2'
        result['parity'].append({'case':'manifest-isolation-and-late-membership','rows':2})
        # Never trust only a byte hash if its parsed representation differs.
        query("UPDATE probe_raw SET parsed_payload=parsed_payload||'{\"probe_collision\":true}'::jsonb")
        try:
            query('BEGIN; '+cache_sql()+' COMMIT;')
        except subprocess.CalledProcessError as error:
            assert 'cache payload identity mismatch' in error.stderr
        else:
            raise AssertionError('cache identity mismatch accepted')
        result['errors'].append({'case':'cache-payload-mismatch','message':'rejected'})
        # JSONB equality treats1 and1.0 as equal; canonical text does not. Guard
        # the actual representation so a changed decoder cannot reuse a stale hash.
        numeric=copy.deepcopy(fixtures[0]); numeric['probe_numeric']=1
        query(load_sql([numeric])); query('BEGIN; '+cache_sql()+' COMMIT;')
        query("UPDATE probe_raw SET parsed_payload=jsonb_set(parsed_payload,'{probe_numeric}','1.0')")
        try:
            query('BEGIN; '+cache_sql()+' COMMIT;')
        except subprocess.CalledProcessError as error:
            assert 'cache payload identity mismatch' in error.stderr
        else:
            raise AssertionError('numeric representation mismatch accepted')
        result['errors'].append({'case':'numeric-representation-mismatch','message':'rejected'})
        result['status'] = 'PASS'
        return result
    finally:
        # Refuse cleanup unless this exact generated container has our probe label.
        try:
            actual = docker('inspect', '--format', '{{index .Config.Labels "de.probe"}}', name).strip()
        except subprocess.CalledProcessError:
            actual = None
        if actual == 'etsy-staging':
            docker('rm', '--force', name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('choose a new report path')
    result = run()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
