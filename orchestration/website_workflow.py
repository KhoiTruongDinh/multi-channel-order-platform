"""Durable stage lifecycle shared by CLI and Airflow; no business transformations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import psycopg
from ingestion.website import db_kwargs, parse_time

MAX_ATTEMPTS = 5
STAGES = ('collect', 'freeze', 'build_and_test', 'publish')
ROOT = Path(os.environ.get('PROJECT_ROOT', '/opt/project'))


class AttemptBudgetExhausted(RuntimeError):
    """Permanent within one explicit replay cycle, including Airflow clears."""


def identity(execution_id, component):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'm04:website:{execution_id}:{component}')


def connect():
    return psycopg.connect(**db_kwargs('PLATFORM', 'data_platform', 'platform_ingest'))


def command(*arguments):
    subprocess.run([sys.executable, '-m', *map(str, arguments)], check=True)


def batch_state(conn, batch_id):
    row = conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (batch_id,)).fetchone()
    conn.commit()
    return row[0] if row else None


def ensure_run(conn, args):
    conn.execute(
        """INSERT INTO ops.pipeline_runs
        (run_id,stage,source_system,source_account_id,stream_name,requested_window_start,
         requested_window_end,airflow_dag_id,airflow_run_id,started_at,status,log_reference)
        VALUES (%s,'RECOVER',%s,%s,%s,%s,%s,%s,%s,%s,'RUNNING',%s)
        ON CONFLICT (run_id) DO NOTHING""",
        (args.workflow_id,args.source,'WEB01' if args.source=='internal_web' else 'seller_sim_01',
         'website_workflow' if args.source=='internal_web' else 'ebay_workflow', args.window_start, args.window_end, args.dag_id,
         getattr(args,'airflow_run_id',args.execution_id) if args.dag_id else None, datetime.now(timezone.utc), f'm04:{args.execution_id}'),
    )
    row = conn.execute(
        'SELECT requested_window_start,requested_window_end,airflow_dag_id FROM ops.pipeline_runs WHERE run_id=%s',
        (args.workflow_id,),
    ).fetchone()
    if row != (args.window_start, args.window_end, args.dag_id):
        raise RuntimeError('execution identity already exists with different window/context')
    conn.commit()


def begin_attempt(conn, args, stage):
    conn.execute('SELECT run_id FROM ops.pipeline_runs WHERE run_id=%s FOR UPDATE', (args.workflow_id,))
    attempts = conn.execute(
        'SELECT attempt_number,status FROM ops.task_attempts WHERE run_id=%s AND task_name=%s ORDER BY attempt_number',
        (args.workflow_id, stage),
    ).fetchall()
    if any(status == 'SUCCEEDED' for _, status in attempts):
        conn.commit()
        return None
    if len(attempts) >= MAX_ATTEMPTS:
        conn.rollback()
        raise AttemptBudgetExhausted(f'{stage}: durable five-attempt budget exhausted; use an explicit new execution for replay')
    now = datetime.now(timezone.utc)
    conn.execute(
        """UPDATE ops.task_attempts SET status='FAILED',finished_at=%s,error_code='INTERRUPTED',
            error_message='Prior process ended before attempt completion'
            WHERE run_id=%s AND task_name=%s AND status='RUNNING'""",
        (now, args.workflow_id, stage),
    )
    number = len(attempts) + 1
    attempt_id = identity(args.execution_id, f'{stage}:{number}')
    conn.execute(
        """INSERT INTO ops.task_attempts
        (attempt_id,run_id,task_name,attempt_number,started_at,status,log_reference)
        VALUES (%s,%s,%s,%s,%s,'RUNNING',%s)""",
        (attempt_id, args.workflow_id, stage, number, now, f'm04:{args.execution_id}:{stage}:{number}'),
    )
    conn.commit()
    return attempt_id, number


def annotate_children(conn, args):
    conn.execute(
        """UPDATE ops.pipeline_runs SET airflow_dag_id=%s,airflow_run_id=%s
        WHERE log_reference=%s OR (batch_id=%s AND stream_name='orders')""",
        (args.dag_id, getattr(args,'airflow_run_id',args.execution_id) if args.dag_id else None,
         child_locator(args), args.batch_id),
    )
    conn.commit()


def child_locator(args):
    return (f'm02:m04-{args.execution_id}:scheduled' if args.source=='internal_web'
            else f'm05:m04-{args.execution_id}')


def perform(conn, args, stage, number):
    state = batch_state(conn, args.batch_id)
    if stage == 'collect':
        locator = child_locator(args)
        succeeded = conn.execute(
            "SELECT 1 FROM ops.pipeline_runs WHERE log_reference=%s AND status='SUCCEEDED' LIMIT 1", (locator,),
        ).fetchone()
        if succeeded:
            conn.commit()
            return
        conn.execute(
            """UPDATE ops.pipeline_runs SET status='FAILED',finished_at=%s,error_code='INTERRUPTED'
            WHERE log_reference=%s AND status='RUNNING'""", (datetime.now(timezone.utc), locator),
        )
        conn.commit()
        arguments = ['ingestion.website' if args.source=='internal_web' else 'ingestion.ebay', '--window-start', args.window_start.isoformat(),
                     '--window-end', args.window_end.isoformat(), '--observed-at', args.observed_at.isoformat(),
                     '--execution-id', f'm04-{args.execution_id}', '--checkpoint-stream', args.checkpoint_stream]
        if args.fault_after_raw_once and number == 1:
            arguments.append('--fail-after-raw' if args.source=='internal_web' else '--fail-after-page')
        command(*arguments)
    elif stage == 'freeze':
        if state is None:
            if getattr(args,'freeze_connection',None) is not None:
                from transformation.batch import freeze
                freeze(argparse.Namespace(batch_id=args.batch_id,run_id=identity(args.execution_id,'transform'),
                    source=args.source,mapping_version=args.mapping_version,transformation_version=args.transformation_version,
                    validation_mode=args.validation_mode,connection=args.freeze_connection))
            else:
                command('transformation.batch', 'freeze', '--batch-id', args.batch_id,
                        '--run-id', identity(args.execution_id, 'transform'), '--source', args.source,
                        '--mapping-version', args.mapping_version, '--transformation-version', args.transformation_version,
                        '--validation-mode',args.validation_mode)
        elif state == 'FAILED':
            raise RuntimeError('failed batch requires an explicit new replay execution')
        conn.execute('UPDATE ops.pipeline_runs SET batch_id=%s WHERE run_id=%s', (args.batch_id, args.workflow_id))
        conn.commit()
        if args.fault_after_freeze_once and number == 1:
            raise RuntimeError('intentional M04 failure after durable manifest freeze')
    elif stage == 'build_and_test':
        if state in ('TESTED', 'PUBLISHED'):
            return
        if state == 'FROZEN':
            command('transformation.batch', 'building', '--batch-id', args.batch_id)
        elif state != 'BUILDING':
            raise RuntimeError(f'cannot build batch in state {state}')
        variables = {'batch_id': str(args.batch_id), 'mapping_version': args.mapping_version,
                     'transformation_version': args.transformation_version,'release_source':args.source,
                     'validation_mode':args.validation_mode,'inject_test_failure': args.inject_test_failure}
        subprocess.run([
            str(Path(sys.executable).with_name('dbt')), 'build',
            '--profiles-dir', str(ROOT / 'infra/dbt'), '--project-dir', str(ROOT / 'transformations'),
            '--target-path', f'target/{args.batch_id}', '--vars', json.dumps(variables),
        ], check=True)
        command('transformation.batch', 'tested', '--batch-id', args.batch_id,
                '--artifact', ROOT / 'transformations/target' / str(args.batch_id) / 'run_results.json')
    elif stage == 'publish':
        if state != 'PUBLISHED':
            command('transformation.publish', '--batch-id', args.batch_id,
                    '--run-id', identity(args.execution_id, f'publish:{number}'), '--source',args.source)


def abort(conn, args):
    state = batch_state(conn, args.batch_id)
    if state == 'PUBLISHED':
        return
    if state in ('FROZEN', 'BUILDING', 'TESTED'):
        command('transformation.batch', 'failed', '--batch-id', args.batch_id,
                '--expected-status', state,
                '--artifact', ROOT / 'transformations/target' / str(args.batch_id) / 'run_results.json')
    conn.execute(
        """UPDATE ops.pipeline_runs SET status='FAILED',finished_at=%s,
           error_code='WORKFLOW_FAILED',error_message='Required task failed; inspect durable task attempts'
           WHERE run_id=%s""", (datetime.now(timezone.utc), args.workflow_id),
    )
    conn.commit()


def run_stage(args, stage):
    with connect() as conn:
        ensure_run(conn, args)
        locked = conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))',
                              (f'm04:{args.execution_id}:{stage}',)).fetchone()[0]
        conn.commit()
        if not locked:
            raise RuntimeError('same workflow stage is already running')
        if stage == 'abort':
            abort(conn, args)
            return
        attempt = begin_attempt(conn, args, stage)
        if attempt is None:
            print(f'execution={args.execution_id} stage={stage} already succeeded')
            return
        attempt_id, number = attempt
        try:
            perform(conn, args, stage, number)
            conn.execute("UPDATE ops.task_attempts SET status='SUCCEEDED',finished_at=%s WHERE attempt_id=%s",
                         (datetime.now(timezone.utc), attempt_id))
            if stage == 'publish':
                conn.execute("UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=%s WHERE run_id=%s",
                             (datetime.now(timezone.utc), args.workflow_id))
            conn.commit()
        except Exception as error:
            conn.rollback()
            conn.execute(
                """UPDATE ops.task_attempts SET status=%s,finished_at=%s,error_code=%s,error_message=%s
                   WHERE attempt_id=%s""",
                ('RETRYABLE' if number < MAX_ATTEMPTS else 'FAILED', datetime.now(timezone.utc),
                 type(error).__name__, str(error)[:1000], attempt_id),
            )
            conn.commit()
            raise
        finally:
            annotate_children(conn, args)
        print(f'execution={args.execution_id} batch={args.batch_id} stage={stage} attempt={number} succeeded')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=(*STAGES, 'abort', 'all'), required=True)
    parser.add_argument('--execution-id', required=True)
    parser.add_argument('--dag-id')
    parser.add_argument('--source', choices=('internal_web','ebay_sim'),default='internal_web')
    parser.add_argument('--validation-mode',choices=('s01','runtime'),default='s01')
    parser.add_argument('--checkpoint-stream',choices=('orders','orders_polling'),default='orders')
    parser.add_argument('--mapping-version',default='s01-v1')
    parser.add_argument('--transformation-version',default='m03-v1')
    parser.add_argument('--window-start', type=parse_time, required=True)
    parser.add_argument('--window-end', type=parse_time, required=True)
    parser.add_argument('--observed-at', type=parse_time, required=True)
    for flag in ('fault-after-raw-once', 'fault-after-freeze-once', 'inject-test-failure'):
        parser.add_argument('--' + flag, action='store_true')
    args = parser.parse_args()
    if args.window_start > args.window_end or args.observed_at < args.window_end:
        parser.error('require window_start <= window_end <= observed_at')
    args.workflow_id = identity(args.execution_id, 'workflow')
    args.batch_id = identity(args.execution_id, 'batch')
    if args.stage == 'all':
        try:
            for stage in STAGES:
                run_stage(args, stage)
        except Exception:
            run_stage(args, 'abort')
            raise
    else:
        run_stage(args, args.stage)


if __name__ == '__main__':
    try:
        main()
    except AttemptBudgetExhausted as error:
        print(str(error), file=sys.stderr)
        sys.exit(42)
