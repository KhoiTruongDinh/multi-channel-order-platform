"""Real CLI-equivalent recovery probes, only invoked in verified disposable storage."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from orchestration import polling, website_workflow as workflow
from transformation.batch import connect


def value(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchone()[0]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def arguments(case):
    return argparse.Namespace(source='internal_web', execution_id='m08c-'+case+'-'+uuid.uuid4().hex,
        dag_id=None, airflow_run_id=None, collection_mode='recovery', checkpoint_stream=None,
        reuse_cycle_config=False, window_end=datetime.now(timezone.utc),
        initial_start=datetime(2026, 10, 17, tzinfo=timezone.utc), overlap_seconds=120,
        wait_seconds=0, mapping_version='s01-v1', transformation_version='m05b-v1',
        abort=False, fault_after_raw_once=False, fault_after_freeze_once=False,
        inject_test_failure=False)


def publication():
    return value("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'")


def business_signature(tables):
    # Internal allowlisted relations only; unlike psql, fetchone cannot consume a
    # multi-statement BEGIN/SELECT/COMMIT script as a scalar result.
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return tuple(conn.execute(
            "SELECT count(*),md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) FROM "
            + table + ' t').fetchone() for table in tables)


def manifest(batch):
    with connect() as conn:
        return conn.execute('SELECT raw_record_id FROM ops.batch_inputs WHERE batch_id=%s ORDER BY raw_record_id',
                            (batch,)).fetchall()


def stage_resume():
    args = arguments('resume')
    args.fault_after_raw_once = args.fault_after_freeze_once = True
    polling.prepare(args)
    raw_before = value('SELECT count(*) FROM raw.raw_records')
    checkpoint_sql = "SELECT coalesce(json_agg(t ORDER BY source_system,source_account_id,stream_name)::text,'[]') FROM ops.extraction_checkpoints t"
    checkpoint_before = value(checkpoint_sql)
    good = publication()
    try:
        polling.coordinate(args)
    except Exception:
        # Do not accept a generic failed command alone as a successful injection.
        require(value('SELECT status FROM ops.task_attempts WHERE run_id=%s AND task_name=\'collect\' AND attempt_number=1',
                      (args.workflow_id,)) == 'RETRYABLE', 'missing interrupted collection audit')
        require(value('SELECT count(*) FROM raw.raw_records') > raw_before, 'fault did not retain durable raw')
        require(value("""SELECT count(*) FROM raw.raw_records r JOIN ops.pipeline_runs p USING(run_id)
            WHERE r.metadata->>'execution_id'=%s AND p.status='FAILED'
              AND p.error_message='intentional M02 interruption after durable raw write'""",
                      ('m04-' + args.execution_id,)) == 1, 'failure was not the exact durable raw hook')
        require(value(checkpoint_sql) == checkpoint_before, 'failed Website window advanced checkpoint')
        require(publication() == good, 'failed acquisition changed publication')
    else:
        raise AssertionError('raw interruption was not exercised')
    try:
        polling.coordinate(args)
    except RuntimeError as error:
        require(str(error) == 'intentional M04 failure after durable manifest freeze',
                'unexpected failure instead of freeze hook')
    else:
        raise AssertionError('freeze interruption was not exercised')
    frozen = manifest(args.batch_id)
    require(bool(frozen), 'empty frozen manifest')
    require(publication() == good, 'frozen untested batch changed publication')
    polling.coordinate(args)
    require(manifest(args.batch_id) == frozen, 'retry replaced frozen raw manifest')
    require(publication() == args.batch_id, 'resumed batch was not published')
    attempts = value('SELECT count(*) FROM ops.task_attempts WHERE run_id=%s', (args.workflow_id,))
    polling.coordinate(args)
    require(value('SELECT count(*) FROM ops.task_attempts WHERE run_id=%s', (args.workflow_id,)) == attempts,
            'idempotent replay consumed new business attempts')
    return dict(workflow_id=str(args.workflow_id), batch_id=str(args.batch_id),
                frozen_inputs=len(frozen), assertions='raw retained/checkpoint held/manifest reused/published/idempotent')


def failed_gate():
    args = arguments('failed-gate')
    args.inject_test_failure = True
    polling.prepare(args)
    good = publication()
    tables = ('core.orders_current', 'core.order_lines_current', 'core.order_snapshot_history',
              'core.order_line_snapshot_history', 'core.snapshot_evidence', 'ops.publication_state',
              'mart.order_activity_daily','mart.product_activity_daily','mart.order_status_current','mart.source_health')
    before = business_signature(tables)
    try:
        polling.coordinate(args)
    except Exception:
        artifact = Path(workflow.ROOT) / 'transformations/target' / str(args.batch_id) / 'run_results.json'
        report = json.loads(artifact.read_text())
        failures = [r for r in report['results'] if r['status'] not in ('success', 'pass')]
        require(len(failures) == 1 and failures[0]['status'] == 'fail'
                and failures[0]['unique_id'] == 'test.multi_channel_orders.injected_failure',
                'failure was not exactly the deliberate dbt test')
        workflow.run_stage(args, 'abort')
    else:
        raise AssertionError('injected dbt failure published successfully')
    require(value('SELECT status FROM ops.transform_batches WHERE batch_id=%s', (args.batch_id,)) == 'FAILED',
            'operator abort did not fail batch')
    require(publication() == good and business_signature(tables) == before,
            'failed gate changed last-good publication or business data')
    return dict(workflow_id=str(args.workflow_id), batch_id=str(args.batch_id),
                assertions='exact injected test/explicit abort/last-good facts and pointer unchanged')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=('stage_resume', 'failed_gate'))
    args = parser.parse_args()
    require(not value("SELECT count(*) FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')"),
            'active test batch: inspect before replay; no automatic reset')
    result = stage_resume() if args.case == 'stage_resume' else failed_gate()
    print(json.dumps(dict(status='PASS', case=args.case, **result)))


if __name__ == '__main__':
    main()
