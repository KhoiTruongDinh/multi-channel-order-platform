"""Acceptance-only probes for Airflow metadata and published platform state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import psycopg
from ingestion.website import db_kwargs
from orchestration.website_workflow import identity

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=('preflight', 'trigger', 'status', 'collect_retry', 'freeze_retry',
                                      'checkpoint', 'manifest', 'signature', 'publication',
                                      'check_success', 'check_failure', 'budget', 'clear', 'cleared_status'))
parser.add_argument('--execution-id', default='unused')
parser.add_argument('--faults', action='store_true')
parser.add_argument('--test-failure', action='store_true')
args = parser.parse_args()
workflow_id = identity(args.execution_id, 'workflow')
batch_id = identity(args.execution_id, 'batch')


def platform(user='platform_ingest'):
    return psycopg.connect(**db_kwargs('PLATFORM', 'data_platform', user))


def metadata():
    return psycopg.connect(host='postgres', dbname='airflow_meta', user='airflow_app',
                           password=os.environ['AIRFLOW_APP_PASSWORD'])


def signature():
    payload = {}
    with platform('platform_publisher') as conn:
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for table in ('core.order_snapshot_history', 'core.order_line_snapshot_history',
                      'core.orders_current', 'core.order_lines_current',
                      'mart.order_activity_daily', 'mart.product_activity_daily', 'mart.order_status_current'):
            payload[table] = [row[0] for row in conn.execute(
                f"SELECT to_jsonb(t)-'batch_id'-'published_batch_id' FROM {table} t ORDER BY (to_jsonb(t)-'batch_id'-'published_batch_id')::text"
            ).fetchall()]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


if args.action == 'preflight':
    with psycopg.connect(**db_kwargs('WEBSITE','website_source','website_reader')) as conn:
        assert conn.execute("SELECT cancellation_status FROM orders WHERE order_id='W1001'").fetchone() == ('CANCELED',), 'Run complete M02 source scenario first'
    with platform('platform_publisher') as conn:
        assert conn.execute("SELECT count(*) FROM core.order_snapshot_history WHERE source_system='internal_web'").fetchone()[0] == 3, 'Run M03 first'
        assert conn.execute("SELECT count(*),sum(quantity),sum(line_gross_amount) FROM core.order_lines_current WHERE source_system='internal_web'").fetchone() == (1, 2, 40)
    print('preflight PASS')
elif args.action == 'trigger':
    conf = {'fault_after_raw_once': args.faults, 'fault_after_freeze_once': args.faults,
            'inject_test_failure': args.test_failure}
    subprocess.run(['airflow','dags','trigger','website_orders','--run-id',args.execution_id,
                    '--logical-date',datetime.now(timezone.utc).isoformat(),'--conf',json.dumps(conf)],
                   check=True, stdout=sys.stderr)
    print(args.execution_id)
elif args.action in ('status', 'collect_retry', 'freeze_retry', 'cleared_status'):
    with metadata() as conn:
        if args.action == 'status':
            row = conn.execute("SELECT state FROM dag_run WHERE dag_id='website_orders' AND run_id=%s", (args.execution_id,)).fetchone()
        elif args.action == 'cleared_status':
            row = conn.execute("""SELECT d.state FROM dag_run d JOIN task_instance t
                                  ON t.dag_id=d.dag_id AND t.run_id=d.run_id
                                  WHERE d.dag_id='website_orders' AND d.run_id=%s
                                  AND t.task_id='build_and_test' AND t.try_number >= 6""", (args.execution_id,)).fetchone()
        else:
            task = 'collect' if args.action == 'collect_retry' else 'freeze'
            row = conn.execute("SELECT state FROM task_instance WHERE dag_id='website_orders' AND run_id=%s AND task_id=%s", (args.execution_id,task)).fetchone()
    print(row[0] if row else 'waiting')
elif args.action == 'signature':
    print(signature())
elif args.action == 'clear':
    with metadata() as conn:
        logical_date = conn.execute("SELECT logical_date FROM dag_run WHERE dag_id='website_orders' AND run_id=%s", (args.execution_id,)).fetchone()[0]
        end_date = logical_date + timedelta(seconds=1)
        assert conn.execute("SELECT count(*) FROM dag_run WHERE dag_id='website_orders' AND logical_date >= %s AND logical_date < %s", (logical_date,end_date)).fetchone()[0] == 1
    assert logical_date is not None
    subprocess.run(['airflow','tasks','clear','website_orders','--start-date',logical_date.isoformat(),
                    '--end-date',end_date.isoformat(),'--task-regex','build_and_test','--downstream','--yes'],
                   check=True,stdout=sys.stderr)
    with metadata() as conn:
        state, number = conn.execute("SELECT state,try_number FROM task_instance WHERE dag_id='website_orders' AND run_id=%s AND task_id='build_and_test'", (args.execution_id,)).fetchone()
        assert state != 'failed' or number >= 6, 'clear selected no task instances'
    print('cleared only the exhausted run build/publish/failure tasks')
elif args.action == 'publication':
    with platform('platform_publisher') as conn:
        print(conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0])
elif args.action == 'checkpoint':
    with platform() as conn:
        print(conn.execute("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system='internal_web' AND source_account_id='WEB01' AND stream_name='orders'").fetchone()[0])
elif args.action == 'manifest':
    with platform() as conn:
        rows = conn.execute('SELECT raw_record_id FROM ops.batch_inputs WHERE batch_id=%s ORDER BY raw_record_id', (batch_id,)).fetchall()
        assert rows, 'manifest missing'
        print(hashlib.sha256(','.join(str(row[0]) for row in rows).encode()).hexdigest())
elif args.action == 'check_success':
    with platform() as conn:
        counts = dict(conn.execute('SELECT task_name,count(*) FROM ops.task_attempts WHERE run_id=%s GROUP BY task_name', (workflow_id,)).fetchall())
        assert counts == {'collect': 2, 'freeze': 2, 'build_and_test': 1, 'publish': 1}, counts
        assert conn.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s', (workflow_id,)).fetchone() == ('SUCCEEDED',)
        assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (batch_id,)).fetchone() == ('PUBLISHED',)
        raw_states = dict(conn.execute("SELECT p.status,count(*) FROM raw.raw_records r JOIN ops.pipeline_runs p USING(run_id) WHERE r.metadata->>'execution_id'=%s GROUP BY p.status", (f'm04-{args.execution_id}',)).fetchall())
        assert raw_states == {'FAILED': 1,'SUCCEEDED': 1}, raw_states
        assert conn.execute("SELECT count(*) FROM ops.pipeline_runs WHERE airflow_dag_id='website_orders' AND airflow_run_id=%s", (args.execution_id,)).fetchone()[0] >= 4
    print(f'M04 retry/restart audit PASS batch={batch_id}')
elif args.action in ('check_failure','budget'):
    artifact = json.loads((Path('/opt/project/transformations/target') / str(batch_id) / 'run_results.json').read_text())
    failures = [row for row in artifact['results'] if row['status'] not in ('success','pass')]
    assert len(failures) == 1 and failures[0]['unique_id'] == 'test.multi_channel_orders.injected_failure' and failures[0]['status'] == 'fail', failures
    with platform() as conn:
        attempts = conn.execute("SELECT attempt_number,status FROM ops.task_attempts WHERE run_id=%s AND task_name='build_and_test' ORDER BY attempt_number", (workflow_id,)).fetchall()
        assert attempts == [(1,'RETRYABLE'),(2,'RETRYABLE'),(3,'RETRYABLE'),(4,'RETRYABLE'),(5,'FAILED')], attempts
        assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (batch_id,)).fetchone() == ('FAILED',)
        assert conn.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s', (workflow_id,)).fetchone() == ('FAILED',)
    if args.action == 'budget':
        result = subprocess.run([sys.executable,'-m','orchestration.website_workflow','--stage','build_and_test',
                                 '--execution-id',args.execution_id,'--dag-id','website_orders',
                                 '--window-start','2026-10-17T09:09:00Z','--window-end','2026-10-17T09:15:00Z',
                                 '--observed-at','2026-10-17T09:15:00Z'],capture_output=True,text=True)
        assert result.returncode != 0 and 'budget exhausted' in result.stderr, result.stderr
        with platform() as conn:
            assert conn.execute("SELECT count(*) FROM ops.task_attempts WHERE run_id=%s AND task_name='build_and_test'", (workflow_id,)).fetchone()[0] == 5
    print(f'M04 {args.action} PASS batch={batch_id}')
