"""Abrupt process exit at durable boundaries; PostgreSQL/production workflow are real."""
from argparse import Namespace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch
import uuid

from test_support.m08c_pipeline_probe import arguments, publication, manifest, business_signature, value
from orchestration import polling, website_workflow as workflow

TABLES = ('core.orders_current', 'core.order_lines_current', 'core.order_snapshot_history',
          'core.order_line_snapshot_history', 'core.snapshot_evidence', 'ops.publication_state',
          'mart.order_activity_daily','mart.product_activity_daily','mart.order_status_current','mart.source_health')


def child(phase, raw):
    args = Namespace(**json.loads(raw))
    for key in ('workflow_id', 'batch_id'):
        setattr(args, key, uuid.UUID(getattr(args, key)))
    for key in ('window_start', 'window_end', 'observed_at'):
        if getattr(args, key, None):
            setattr(args, key, datetime.fromisoformat(getattr(args, key)))
    if phase == 'raw':
        import ingestion.website as source
        real = source.psycopg.connect

        class Connection:
            def __init__(self, conn):
                self.conn = conn

            def __getattr__(self, key):
                return getattr(self.conn, key)

            def __enter__(self):
                self.conn.__enter__()
                return self

            def __exit__(self, *exc):
                return self.conn.__exit__(*exc)

            def commit(self):
                self.conn.commit()
                found = self.conn.execute("SELECT count(*) FROM raw.raw_records WHERE metadata->>'execution_id'=%s",
                                          ('m04-' + args.execution_id,)).fetchone()[0]
                if found:
                    os._exit(97)

        def connect(**kwargs):
            conn = real(**kwargs)
            return Connection(conn) if kwargs.get('dbname') == 'data_platform' else conn

        with patch.object(source.psycopg, 'connect', side_effect=connect), \
             patch.object(sys, 'argv', ['ingestion.website', '--window-start', args.window_start.isoformat(),
                 '--window-end', args.window_end.isoformat(), '--observed-at', args.observed_at.isoformat(),
                 '--execution-id', 'm04-' + args.execution_id, '--checkpoint-stream', args.checkpoint_stream]):
            source.main()
    elif phase == 'freeze':
        workflow.run_stage(args, 'freeze')
        os._exit(97)
    elif phase == 'dbt':
        real = subprocess.run

        def run(command, **kwargs):
            if Path(str(command[0])).name != 'dbt':
                return real(command, **kwargs)
            process = subprocess.Popen(command, start_new_session=True)
            artifact = workflow.ROOT / 'transformations/target' / str(args.batch_id) / 'manifest.json'
            deadline = time.monotonic() + 120
            while not artifact.is_file():
                if process.poll() is not None:
                    raise RuntimeError('dbt exited before durable parse barrier')
                if time.monotonic() >= deadline:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise RuntimeError('dbt barrier timeout')
                time.sleep(.1)
            os.killpg(process.pid, signal.SIGKILL)
            assert process.wait(timeout=10) == -signal.SIGKILL
            os._exit(97)

        with patch.object(workflow.subprocess, 'run', side_effect=run):
            workflow.run_stage(args, 'build_and_test')
    else:
        from transformation import publish
        real = publish.connect

        class Connection:
            def __init__(self):
                self.conn = real()
                self.changed = False

            def __enter__(self):
                self.conn.__enter__()
                return self

            def execute(self, sql, params=()):
                result = self.conn.execute(sql, params)
                if sql.startswith('DELETE FROM '):
                    self.changed = True
                    if phase == 'publish':
                        os._exit(97)  # Transaction is uncommitted; kernel closes socket.
                return result

            def __exit__(self, *exc):
                result = self.conn.__exit__(*exc)
                if self.changed and exc[0] is None and phase == 'ack':
                    os._exit(97)  # Publication is committed; caller never gets ACK.
                return result

        run_id = uuid.uuid4()
        with patch.object(publish, 'connect', side_effect=Connection), patch.object(sys, 'argv',
            ['transformation.publish', '--batch-id', str(args.batch_id), '--run-id', str(run_id)]):
            publish.main()
    raise AssertionError('process-loss boundary was not reached')


def lose(phase, args):
    env = {key: value for key, value in os.environ.items() if key not in
           ('ETSY_SIGNING_SECRET','MARKETPLACE_WRITER_PASSWORD','WEBSITE_WRITER_PASSWORD')}
    result = subprocess.run([sys.executable, '-m', 'test_support.m08c_loss_probe',
        'child', phase, json.dumps(vars(args), default=str)], timeout=240, env=env)
    assert result.returncode == 97, 'wrong process-loss outcome: ' + phase


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'child':
        child(sys.argv[2], sys.argv[3])
        return
    case = sys.argv[1]
    args = arguments('loss-' + case)
    polling.prepare(args)
    args.observed_at = datetime.now(timezone.utc)
    good = publication()
    before = business_signature(TABLES)
    if case == 'abrupt_raw_inbox':
        checkpoint = value("SELECT coalesce(json_agg(t)::text,'[]') FROM ops.extraction_checkpoints t WHERE source_system='internal_web'")
        lose('raw', args)
        assert value("SELECT count(*) FROM raw.raw_records WHERE metadata->>'execution_id'=%s", ('m04-' + args.execution_id,)) == 1
        assert value("SELECT coalesce(json_agg(t)::text,'[]') FROM ops.extraction_checkpoints t WHERE source_system='internal_web'") == checkpoint
        workflow.run_stage(args, 'collect')
        assert publication() == good and business_signature(TABLES) == before
        # Explicitly close the dead acquisition audit, preserving its raw bytes.
        with workflow.connect() as conn:
            conn.execute("""UPDATE ops.pipeline_runs p SET status='FAILED',finished_at=clock_timestamp(),
                error_code='PROCESS_LOSS',error_message='M08C child exit97 verified; raw retained'
                WHERE p.status='RUNNING' AND EXISTS(SELECT FROM raw.raw_records r WHERE r.run_id=p.run_id
                AND r.metadata->>'execution_id'=%s)""", ('m04-' + args.execution_id,))
        workflow.run_stage(args, 'abort')
        from test_support.m08c_worker_probe import lost_ack
        ack = lost_ack()
    else:
        workflow.run_stage(args, 'collect')
        if case == 'abrupt_freeze_dbt':
            lose('freeze', args)
            frozen = manifest(args.batch_id)
            assert frozen
            workflow.run_stage(args, 'freeze')
            assert manifest(args.batch_id) == frozen
            lose('dbt', args)
            assert value('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (args.batch_id,)) == 'BUILDING'
            assert publication() == good and business_signature(TABLES) == before
            # Both killed subprocesses have been wait()ed; now operator abort is safe.
            workflow.run_stage(args, 'abort')
            assert value('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (args.batch_id,)) == 'FAILED'
        elif case == 'publish_atomicity':
            workflow.run_stage(args, 'freeze')
            workflow.run_stage(args, 'build_and_test')
            lose('publish', args)
            assert publication() == good and business_signature(TABLES) == before
            assert value('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (args.batch_id,)) == 'TESTED'
            lose('ack', args)
            assert publication() == args.batch_id
            committed = business_signature(TABLES)
            workflow.run_stage(args, 'publish')
            assert business_signature(TABLES) == committed
            with workflow.connect() as conn:
                conn.execute("""UPDATE ops.pipeline_runs SET status='FAILED',finished_at=clock_timestamp(),
                    error_code='PROCESS_LOSS' WHERE batch_id=%s AND stage='PUBLISH' AND status='RUNNING'""", (args.batch_id,))
        else:
            raise ValueError('unknown loss case')
    print(json.dumps(dict(status='PASS', case=case, workflow_id=str(args.workflow_id), batch_id=str(args.batch_id),
                          boundary='actual child exit97/SIGKILL and production PostgreSQL transactions')))


if __name__ == '__main__':
    main()
