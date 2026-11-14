"""Real child-process death and parallel SQL checks; disposable database only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid


def require_scope():
    assert os.environ['PLATFORM_DB_HOST'].startswith('delta-pg-')


def child(args):
    require_scope()
    from unittest.mock import patch
    from transformation.delta_plan import load
    from transformation import delta_runtime as runtime, delta_publish as publisher
    plan = load(args.plan)
    marker = Path(args.marker)

    def pause():
        marker.touch(exist_ok=False)
        time.sleep(120)  # Parent must kill this child, never wait for success.
        raise AssertionError('parent did not kill armed child')

    with runtime.source_lock(plan) as conn:
        if args.mode == 'build':
            runtime.freeze(conn, plan, args.batch, args.run)

            class ArmedConnection:
                def execute(self, statement, *params):
                    cursor = conn.execute(statement, *params)
                    if isinstance(statement, str) and statement.startswith('CREATE TABLE '):
                        pause()  # Real candidate DDL is not committed yet.
                    return cursor

                def commit(self):
                    conn.commit()

                def rollback(self):
                    conn.rollback()

            runtime.build(ArmedConnection(), plan, args.batch)
        elif args.mode == 'publish':
            original = publisher._merge_mart

            def armed(*values, **options):
                original(*values, **options)
                pause()  # Real deletes/inserts/merge are still uncommitted.

            with patch.object(publisher, '_merge_mart', side_effect=armed):
                publisher.audited_publish(plan, args.batch, args.run)
        elif args.mode == 'parallel':
            runtime.freeze(conn, plan, args.batch, args.run)
            marker.touch(exist_ok=False)
            deadline = time.monotonic() + 30
            while not Path(args.release).exists():
                if time.monotonic() > deadline:
                    raise TimeoutError('parallel source barrier')
                time.sleep(.02)
            runtime.build(conn, plan, args.batch)
            publisher.audited_publish(plan, args.batch, uuid.uuid4())


def check(plans, acquire, admin, fixture):
    require_scope()
    from transformation.delta_runtime import source_lock, freeze, build
    from transformation.delta_publish import audited_publish
    from transformation.source_config import SOURCES
    checks = []
    payload = json.loads((fixture/'internal_web/WEB_R1.json').read_text())

    with tempfile.TemporaryDirectory(prefix='delta-process-') as directory:
        root = Path(directory)

        def start(mode, source, batch, run, marker, release=None):
            argv = [sys.executable, '-m', 'tests.delta_process_cases', '--mode', mode,
                    '--plan', '/tmp/delta-plans/'+source+'.json', '--batch', str(batch),
                    '--run', str(run), '--marker', str(marker)]
            if release:
                argv += ['--release', str(release)]
            return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def armed(process, marker):
            deadline = time.monotonic()+40
            while not marker.exists():
                if process.poll() is not None:
                    out, err = process.communicate()
                    raise AssertionError('child failed before barrier: '+out[-1000:]+err[-2000:])
                if time.monotonic() > deadline:
                    raise TimeoutError('child did not reach real SQL barrier')
                time.sleep(.02)

        def stop(process):
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=15)

        raw, _ = acquire('internal_web', payload, 'website_order_window')
        plan = plans['internal_web']
        batch, run = uuid.uuid4(), uuid.uuid4()
        marker = root/'build-ready'
        process = start('build', 'internal_web', batch, run, marker)
        try:
            armed(process, marker)
        finally:
            stop(process)
        assert process.returncode == -9, process.returncode
        with source_lock(plan) as conn:
            assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (batch,)).fetchone()[0] == 'BUILDING'
            assert conn.execute('SELECT count(*) FROM ops.delta_results WHERE batch_id=%s', (batch,)).fetchone()[0] == 0
            assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE raw_record_id=%s', (raw,)).fetchone()[0] == 0
            conn.commit()
            build(conn, plan, batch, attempt=2)
            audited_publish(plan, batch, uuid.uuid4())
        checks.append('SIGKILL-during-real-CTAS; lock-released; no-result-or-consumption; attempt2-published')

        raw, _ = acquire('internal_web', payload, 'website_order_window')
        batch, run, failed = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with source_lock(plan) as conn:
            freeze(conn, plan, batch, run)
            build(conn, plan, batch)
        with admin() as conn:
            pointer = conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0]
            before = conn.execute('SELECT to_jsonb(t) FROM core.orders_current t ORDER BY source_system,source_order_id').fetchall()
        marker = root/'publish-ready'
        process = start('publish', 'internal_web', batch, failed, marker)
        try:
            armed(process, marker)
            with admin() as conn:
                assert conn.execute('SELECT to_jsonb(t) FROM core.orders_current t ORDER BY source_system,source_order_id').fetchall() == before
        finally:
            stop(process)
        assert process.returncode == -9, process.returncode
        with source_lock(plan) as conn:
            assert conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0] == pointer
            assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (batch,)).fetchone()[0] == 'TESTED'
            assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE raw_record_id=%s', (raw,)).fetchone()[0] == 0
            conn.commit()
            audited_publish(plan, batch, uuid.uuid4())
        with admin() as conn:
            assert conn.execute('SELECT status,error_code FROM ops.pipeline_runs WHERE run_id=%s', (failed,)).fetchone() == ('FAILED', 'INTERRUPTED')
            assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE raw_record_id=%s', (raw,)).fetchone()[0] == 1
        checks.append('SIGKILL-during-publication; reader-last-good; rollback; interrupted-audit; retry-published')

        # Both real source sessions reach FROZEN before either starts building.
        # Actual builds/publish race; only the short publisher lock serializes.
        acquire('internal_web', payload, 'website_order_window')
        ebay_raw, ebay_run = acquire('ebay_sim',
            json.loads((fixture/'ebay_sim/EB_R2.json').read_text())['orders'][0], 'ebay_order')
        acquire('ebay_sim', json.loads((fixture/'ebay_sim/EB_F1.json').read_text()),
                'ebay_fulfillments', {'order_raw_id': str(ebay_raw)}, ebay_run)
        processes = []
        batches = {}
        release = root/'release'
        try:
            for source in ('internal_web', 'ebay_sim'):
                batch, run = uuid.uuid4(), uuid.uuid4()
                batches[source] = batch
                marker = root/source
                process = start('parallel', source, batch, run, marker, release)
                processes.append(process)
                armed(process, marker)
            release.touch()
            for process in processes:
                out, err = process.communicate(timeout=60)
                assert process.returncode == 0, out[-1000:]+err[-2000:]
        finally:
            for process in processes:
                stop(process)
        with admin() as conn:
            for source, batch in batches.items():
                assert conn.execute('SELECT batch_id FROM ops.publication_state WHERE publication_name=%s', (SOURCES[source][2],)).fetchone()[0] == batch
                assert conn.execute('SELECT count(*) FROM ops.delta_batch_keys WHERE batch_id=%s', (batch,)).fetchone()[0] > 0
        checks.append('two-process-source-private-build-and-publication; both-pointers-committed')
    return dict(status='PASS', scope='real process kill/concurrency SQL, not Airflow scheduler or load SLA', checks=checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('build', 'publish', 'parallel'), required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--batch', type=uuid.UUID, required=True)
    parser.add_argument('--run', type=uuid.UUID, required=True)
    parser.add_argument('--marker', required=True)
    parser.add_argument('--release')
    child(parser.parse_args())
