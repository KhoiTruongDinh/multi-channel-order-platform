"""Opt-in dbt legacy/page-input parity on a disposable PostgreSQL database.

No collection, scheduler, publication, owner credentials or performance campaign.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'dbt-acquisition'


def host():
    name = 'dbt-acquisition-' + uuid.uuid4().hex[:12]
    client = name + '-client'
    report = ROOT / 'runtime' / (name + '.json')
    result = dict(status='FAILED', scope='dbt input parity only; no collect/publish/scheduler/load',
                  commands=[], container=name)

    def docker(*args, timeout=120):
        result['commands'].append(['docker', *args])
        completed = subprocess.run(['docker', *args], capture_output=True, text=True,
                                   encoding='utf-8', timeout=timeout)
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        return completed.stdout.strip()

    try:
        docker('run', '--detach', '--name', name, '--label', 'de.probe=' + LABEL,
               '--network', 'none', '--memory', '512m', '--cpus', '1',
               '--tmpfs', '/var/lib/postgresql/data',
               '--mount', f'type=bind,source={ROOT}/migrations,target=/migrations,readonly',
               '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:16.15-bookworm')
        for _ in range(40):
            # The image briefly starts a socket-only initialization server.
            # Wait for final TCP readiness, not that temporary bootstrap server.
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'],
                                   capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('test PostgreSQL readiness timeout')
        docker('exec', name, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
               '-c', ';'.join(f'CREATE ROLE {role} LOGIN' for role in (
                   'platform_owner', 'platform_ingest', 'platform_transform',
                   'platform_publisher', 'platform_report')))
        docker('exec', name, 'createdb', '-U', 'postgres', '-O', 'platform_owner', 'data_platform')
        files = ['bootstrap/002_database_baseline.sql']
        files += ['platform/' + p.name for p in sorted((ROOT / 'migrations/platform').glob('*.sql'))
                  if int(p.name[:3]) <= 11 or p.name.startswith('014_')]
        for migration in files:
            docker('exec', name, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
                   '-U', 'postgres', '-d', 'data_platform', '-f', '/migrations/' + migration)
        mounts = []
        for folder in ('tests', 'ingestion', 'transformation', 'transformations',
                       'orchestration', 'infra/dbt', 'fixtures/s01'):
            mounts += ['--mount', f'type=bind,source={ROOT}/{folder},target=/review/{folder},readonly']
        output = docker('run', '--rm', '--name', client, '--label', 'de.probe=' + LABEL,
                        '--network', 'container:' + name, '--read-only',
                        '--memory', '768m', '--cpus', '1', '--tmpfs', '/tmp',
                        '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/review',
                        '-e', 'PROJECT_ROOT=/review', '--workdir', '/review', *mounts,
                        '--entrypoint', '/opt/airflow/project-venv/bin/python',
                        'multi-channel-order-platform-airflow',
                        'tests/dbt_acquisition_probe.py', '--inside', timeout=480)
        result['checks'] = json.loads(output)
        result['status'] = 'PASS'
    except Exception as error:
        result['error'] = str(error)
    finally:
        result['cleanup'] = []
        for target in (client, name):
            try:
                found = subprocess.run(['docker', 'inspect', '--format',
                                        '{{index .Config.Labels "de.probe"}}', target],
                                       capture_output=True, text=True, timeout=15)
                if found.returncode == 0:
                    if found.stdout.strip() != LABEL:
                        raise RuntimeError('cleanup label mismatch: ' + target)
                    docker('rm', '--force', target)
                elif 'no such' not in found.stderr.lower():
                    raise RuntimeError('cannot confirm cleanup: ' + found.stderr)
                result['cleanup'].append(dict(container=target, status='PASS'))
            except Exception as error:
                result['cleanup'].append(dict(container=target, status='FAILED', error=str(error)))
                result['status'] = 'FAILED'
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        if result.get('checks'):
            proof = result['checks']
            print(json.dumps(dict(builds=[dict(branch=b['branch'], nodes=b['nodes'])
                                          for b in proof['builds']],
                                  business_comparisons=len(proof['parity']),
                                  evidence_checks=len(proof['evidence']),
                                  fingerprint_checks=len(proof['fingerprints']),
                                  element_cache=proof['element_cache']), indent=2))
        else:
            print(result.get('error'), file=sys.stderr)
        print(f"dbt acquisition probe {result['status']}; report={report}")
    return 0 if result['status'] == 'PASS' else 1


def inside():
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    from transformation.publish import COPIES
    from transformation.source_config import SOURCES
    from transformation.delta_plan import source_hash
    from fixtures.s01.fixture_tools import fingerprint
    os.environ.update(PLATFORM_DB_HOST='127.0.0.1', PLATFORM_TRANSFORM_PASSWORD='disposable-only',
                      DBT_SEND_ANONYMOUS_USAGE_STATS='false', DBT_PARTIAL_PARSE='false')
    admin = psycopg.connect(host='127.0.0.1', user='postgres', dbname='data_platform', autocommit=True)
    manifests = dict(legacy=[], page=[])
    expected = dict(ebay_sim={}, etsy_sim={})
    evidence = dict(legacy={}, page={})
    checks = dict(source_hash=source_hash(), builds=[], parity=[], evidence=[], fingerprints=[])

    def run(source, stage='ACQUIRE'):
        identity = uuid.uuid4()
        admin.execute('''INSERT INTO ops.pipeline_runs(run_id,stage,source_system,source_account_id,
            stream_name,started_at,finished_at,status) VALUES(%s,%s,%s,%s,'probe',clock_timestamp(),
            CASE WHEN %s='ACQUIRE' THEN clock_timestamp() ELSE NULL END,%s)''',
                      (identity, stage, source, SOURCES[source][0], stage,
                       'SUCCEEDED' if stage == 'ACQUIRE' else 'RUNNING'))
        return identity

    def raw(branch, source, payload, resource, owner=None, metadata=None, accepted=()):
        owner = owner or run(source)
        identity = uuid.uuid4()
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        admin.execute('''INSERT INTO raw.raw_records(raw_record_id,run_id,source_system,
            source_account_id,resource_type,response_status,acquired_at,raw_bytes,parsed_payload,
            byte_sha256,contract_version,metadata) VALUES(%s,%s,%s,%s,%s,200,
            '2026-10-17T10:01:00Z',%s,%s,%s,'s01-v1',%s)''',
                      (identity, owner, source, SOURCES[source][0], resource, body,
                       Jsonb(payload), hashlib.sha256(body).digest(), Jsonb(metadata or {})))
        manifests[branch].append(identity)
        if accepted:
            table = 'ops.ebay_collection_scans' if source == 'ebay_sim' else 'ops.etsy_recovery_scans'
            admin.execute(sql.SQL('INSERT INTO {}(run_id,scan_number) VALUES(%s,1)').format(sql.SQL(table)), (owner,))
            admin.execute(sql.SQL("UPDATE {} SET status='VALIDATED',finished_at=clock_timestamp() WHERE run_id=%s").format(sql.SQL(table)), (owner,))
            if source == 'etsy_sim':
                admin.execute('''INSERT INTO ops.etsy_http_attempts(attempt_id,run_id,attempt_number,
                    raw_record_id,recorded_at,collection_run_id,recovery_scan_number)
                    VALUES(%s,%s,1,%s,clock_timestamp(),%s,1)''', (uuid.uuid4(), owner, identity, owner))
            for index, entity in accepted:
                admin.execute('''INSERT INTO ops.acquisition_elements(raw_record_id,source_entity_id,
                    element_index,collection_run_id,scan_number) VALUES(%s,%s,%s,%s,1)''',
                              (identity, str(entity), index, owner))
        return identity, owner

    fixtures = ROOT / 'fixtures/s01/responses'
    read = lambda path: json.loads((fixtures / path).read_text())
    ebay_a = read('ebay_sim/EB_R1.json')['orders'][0]
    ebay_b = copy.deepcopy(ebay_a)
    ebay_b['orderId'] = '12-10002-10001'
    ebay_b['cancelStatus'] = dict(cancelState='CANCEL_REQUESTED', cancelRequests=[dict(cancelRequestId='c-probe')])
    ebay_v2 = read('ebay_sim/EB_R2.json')['orders'][0]
    etsy_a = read('etsy_sim/ET_R1.json')
    etsy_b = copy.deepcopy(etsy_a)
    etsy_b['receipt_id'] += 1
    for transaction in etsy_b['transactions']:
        transaction['receipt_id'] = etsy_b['receipt_id']
    etsy_v2 = copy.deepcopy(etsy_a)
    etsy_v2['updated_timestamp'] += 60
    full_shipping = read('ebay_sim/EB_F1.json')

    def remember(source, value, kind):
        entity = str(value['orderId'] if source == 'ebay_sim' else value['receipt_id'])
        version = value['lastModifiedDate'] if source == 'ebay_sim' else value['updated_timestamp']
        expected[source][(entity, str(version))] = fingerprint(value, kind)

    for value in (ebay_a, ebay_b, ebay_v2):
        remember('ebay_sim', value, 'ebay_order')
    for value in (etsy_a, etsy_b, etsy_v2):
        remember('etsy_sim', value, 'etsy_receipt')

    def shipping(branch, parent, owner, order, partial=False):
        payload = full_shipping if order == ebay_v2 else dict(total=0, fulfillments=[])
        metadata = dict(order_raw_id=str(parent), order_id=order['orderId'])
        if branch == 'page':
            metadata['request_phase'] = 'fulfillment_collection'
        if partial:
            raw(branch, 'ebay_sim', dict(total=1, fulfillments=[dict(fulfillmentId='FUL001')]),
                'ebay_fulfillments', owner, metadata)
            raw(branch, 'ebay_sim', full_shipping['fulfillments'][0], 'ebay_fulfillment', owner,
                dict(metadata, request_phase='fulfillment_detail'))
        else:
            raw(branch, 'ebay_sim', payload, 'ebay_fulfillments', owner, metadata)

    for branch in manifests:
        raw(branch, 'internal_web', read('internal_web/WEB_R1.json'), 'website_order_window')
        if branch == 'legacy':
            for value in (ebay_a, ebay_b, ebay_v2, ebay_v2):
                parent, owner = raw(branch, 'ebay_sim', value, 'ebay_order')
                shipping(branch, parent, owner, value)
            for value in (etsy_a, etsy_b, etsy_v2, etsy_v2):
                raw(branch, 'etsy_sim', value, 'etsy_receipt')
        else:
            # An unaccepted third entity must not become an observed snapshot.
            hidden = copy.deepcopy(ebay_a)
            hidden['orderId'] = '12-unaccepted-10001'
            listed_b = copy.deepcopy(ebay_b)
            listed_b['cancelStatus']['cancelRequests'] = []
            parent, owner = raw(branch, 'ebay_sim', dict(orders=[ebay_a, listed_b, hidden]),
                                'ebay_orders', metadata=dict(collection_scan=1),
                                accepted=[(0, ebay_a['orderId'])])
            shipping(branch, parent, owner, ebay_a)
            detail, _ = raw(branch, 'ebay_sim', ebay_b, 'ebay_order', owner)
            shipping(branch, detail, owner, ebay_b)
            for _ in range(2):
                parent, owner = raw(branch, 'ebay_sim', dict(orders=[ebay_v2]), 'ebay_orders',
                                    metadata=dict(collection_scan=1), accepted=[(0, ebay_v2['orderId'])])
                shipping(branch, parent, owner, ebay_v2, partial=True)
            hidden = copy.deepcopy(etsy_a)
            hidden['receipt_id'] = 9999999
            listed_b = copy.deepcopy(etsy_b)
            del listed_b['transactions']
            raw(branch, 'etsy_sim', dict(count=3, results=[etsy_a, listed_b, hidden]),
                'etsy_receipts', accepted=[(0, etsy_a['receipt_id'])])
            raw(branch, 'etsy_sim', etsy_b, 'etsy_receipt')
            for _ in range(2):
                raw(branch, 'etsy_sim', dict(count=1, results=[etsy_v2]), 'etsy_receipts',
                    accepted=[(0, etsy_v2['receipt_id'])])

    def build(branch):
        batch = uuid.uuid4()
        owner = run('etsy_sim', 'TRANSFORM')
        # Test-owned manifests isolate representations without deleting raw or
        # invoking a production collection/publish workflow.
        admin.execute('''INSERT INTO ops.transform_batches(batch_id,run_id,mapping_version,
            transformation_version,manifest_frozen_at,status,validation_mode)
            VALUES(%s,%s,'s01-v1','acquisition-dbt-probe',clock_timestamp(),'FROZEN','runtime')''', (batch, owner))
        with admin.transaction():
            for identity in manifests[branch]:
                admin.execute('INSERT INTO ops.batch_inputs(batch_id,raw_record_id) VALUES(%s,%s)', (batch, identity))
        target = Path('/tmp') / ('dbt-acquisition-' + branch)
        variables = dict(batch_id=str(batch), mapping_version='s01-v1',
                         transformation_version='acquisition-dbt-probe', release_source='etsy_sim',
                         validation_mode='runtime')
        command = [str(Path(sys.executable).with_name('dbt')), 'build',
                   '--project-dir', str(ROOT / 'transformations'), '--profiles-dir', str(ROOT / 'infra/dbt'),
                   '--target-path', str(target), '--log-path', str(target / 'logs'), '--vars', json.dumps(variables)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=150)
        if completed.returncode:
            raise RuntimeError(branch + ' dbt failed: ' + completed.stdout[-10000:] + completed.stderr[-2000:])
        artifact = json.loads((target / 'run_results.json').read_text())
        assert artifact['results'] and all(r['status'] in ('success', 'pass') for r in artifact['results'])
        checks['builds'].append(dict(branch=branch, command=command, nodes=len(artifact['results']),
                                     results=[dict(id=r['unique_id'], status=r['status']) for r in artifact['results']]))
        print(f"{branch}: dbt {len(artifact['results'])} nodes success/pass", file=sys.stderr)
        for source, (_, prefix, _, _) in SOURCES.items():
            for _, base in COPIES:
                relation = base.replace('build.', 'build.' + prefix)
                rows = admin.execute(sql.SQL("SELECT to_jsonb(t)-'batch_id'-'published_batch_id' FROM {} t").format(sql.Identifier(*relation.split('.')))).fetchall()
                key = source + ':' + base
                if base.endswith('snapshot_evidence'):
                    evidence[branch][source] = rows
                elif branch == 'legacy':
                    checks.setdefault('_baseline', {})[key] = sorted(json.dumps(r[0], sort_keys=True) for r in rows)
                else:
                    actual = sorted(json.dumps(r[0], sort_keys=True) for r in rows)
                    assert actual == checks['_baseline'][key], ('business mismatch', key)
                    checks['parity'].append(dict(source=source, output=base, rows=len(rows), status='PASS'))
            if source != 'internal_web':
                staged = admin.execute(sql.SQL('SELECT order_json,encode(content_fingerprint,\'hex\') FROM {}').format(sql.Identifier('build', 'stg_' + source.split('_')[0] + '_observations'))).fetchall()
                for value, digest in staged:
                    entity = str(value['orderId'] if source == 'ebay_sim' else value['receipt_id'])
                    version = value['lastModifiedDate'] if source == 'ebay_sim' else value['updated_timestamp']
                    assert expected[source][(entity, str(version))] == digest
                assert len(staged) == 4, (source, 'expected all repeated observations', len(staged))
                checks['fingerprints'].append(dict(source=source, branch=branch, observations=len(staged), status='PASS'))
        # Every evidence row must retain actual membership, bytes and resource role.
        for source, rows in evidence[branch].items():
            for (row,) in rows:
                identity = uuid.UUID(row['raw_record_id'])
                assert identity in manifests[branch]
                resource, digest = admin.execute('SELECT upper(resource_type),byte_sha256 FROM raw.raw_records WHERE raw_record_id=%s', (identity,)).fetchone()
                expected_role = 'WEBSITE_RELATIONAL_SNAPSHOT' if source == 'internal_web' else resource
                assert row['evidence_role'] == expected_role, (source, row['evidence_role'], expected_role)
                assert row['resource_fingerprint'] == '\\x' + bytes(digest).hex()
            assert rows, ('missing evidence', source)
            checks['evidence'].append(dict(source=source, branch=branch, rows=len(rows), status='PASS'))

    build('legacy')
    cache_before = admin.execute('SELECT count(1) FROM cache.etsy_elements').fetchone()[0]
    build('page')
    cache_after = admin.execute('SELECT count(1) FROM cache.etsy_elements').fetchone()[0]
    assert cache_before == 0 and cache_after == 2, (cache_before, cache_after)
    checks['element_cache'] = dict(rows=cache_after, duplicate_pages_share_entry=True)
    assert admin.execute('SELECT count(1) FROM core.orders_current').fetchone()[0] == 0
    del checks['_baseline']
    admin.close()
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    if parser.parse_args().inside:
        print(json.dumps(inside()))
    else:
        sys.exit(host())
