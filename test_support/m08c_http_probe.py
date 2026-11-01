"""Real PostgreSQL checkpoint/raw assertions through the production HTTP collector."""
import json
import subprocess
import sys
import uuid
from urllib.request import Request, urlopen

from ingestion.website import db_kwargs
import psycopg


def rows(sql, params=()):
    with psycopg.connect(**db_kwargs('PLATFORM', 'data_platform', 'platform_ingest')) as conn:
        return conn.execute(sql, params).fetchall()


def checkpoint():
    return rows("SELECT * FROM ops.extraction_checkpoints WHERE source_system='ebay_sim' AND stream_name='orders_polling'")


def configure(**fault):
    with urlopen(Request('http://ebay-sim:8081/state', data=json.dumps(dict(state='0902', **fault)).encode()), timeout=30) as response:
        assert response.status == 200


def acquire(success):
    identity = 'm08c-http-' + uuid.uuid4().hex
    result = subprocess.run([sys.executable, '-m', 'ingestion.ebay', '--execution-id', identity,
        '--window-start', '2026-10-17T09:00:00Z', '--window-end', '2026-10-17T09:03:00Z',
        '--observed-at', '2026-10-17T09:03:00Z', '--checkpoint-stream', 'orders_polling'],
        capture_output=True, text=True, timeout=150)
    assert (result.returncode == 0) == success, 'unexpected collector exit; inspect case audit ' + identity
    audit = rows("SELECT response_status,raw_bytes,metadata->>'http_attempt',resource_type FROM raw.raw_records WHERE metadata->>'execution_id'=%s ORDER BY acquired_at,raw_record_id", (identity,))
    assert audit, 'no raw acquisition audit'
    return identity, audit


def main():
    results = []
    try:
        configure(fail_offset=0, errors_left=2, error_status=429)
        identity, audit = acquire(True)
        assert sum(r[0] == 429 for r in audit) == 2
        results.append(dict(case='429-retry-after', execution_id=identity, raw=len(audit)))
        for kind, fault in (
            ('500-exhaustion', dict(fail_offset=0, errors_left=5)),
            ('malformed', dict(transport_fault=dict(kind='malformed', count=1))),
            ('mid-page', dict(extra_order=True, fail_offset=1, errors_left=5)),
            ('hostile-next', dict(repeat_page=True, bad_next=True)),
        ):
            before = checkpoint()
            configure(**fault)
            identity, audit = acquire(False)
            assert checkpoint() == before, 'failed window advanced checkpoint'
            if kind == '500-exhaustion':
                assert len(audit) == 5 and all(r[0] == 500 for r in audit)
            if kind == 'malformed':
                assert any(bytes(r[1]) == b'{intentional-malformed-json' for r in audit)
            if kind == 'mid-page':
                assert any(r[0] == 200 for r in audit) and sum(r[0] == 500 for r in audit) == 5
            configure()
            replay, recovered = acquire(True)
            results.append(dict(case=kind, execution_id=identity, replay_id=replay,
                                raw=len(audit), recovery_raw=len(recovered), checkpoint_held=True))
        configure(transport_fault=dict(kind='timeout', count=1, delay_seconds=11))
        identity, audit = acquire(True)
        assert any(r[0] is None and bytes(r[1]) == b'' for r in audit), 'no retained timeout'
        results.append(dict(case='timeout-retry', execution_id=identity, raw=len(audit)))
        configure(repeat_page=True)
        identity, audit = acquire(True)
        work = rows("""SELECT count(*) FROM ops.processing_work w WHERE EXISTS
            (SELECT FROM raw.raw_records r WHERE r.metadata->>'execution_id'=%s
             AND w.dedupe_key LIKE 'm05:'||r.run_id::text||':%%')""", (identity,))
        assert work[0][0] == 1 and len(audit) == 4
        results.append(dict(case='repeated-page', execution_id=identity, raw=len(audit)))
    finally:
        with urlopen(Request('http://ebay-sim:8081/state', data=b'{"state":"0912"}'), timeout=30) as response:
            assert response.status == 200
    print(json.dumps(dict(status='PASS', scope='real HTTP/raw/checkpoint; not live-PG visibility proof', cases=results)))


if __name__ == '__main__':
    main()
