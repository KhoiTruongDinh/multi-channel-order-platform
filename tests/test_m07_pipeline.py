"""Real current-code CLI-equivalent pipeline: barrier wait, resume, failed release.

Retains explicit audit/artifacts, never resets sources or deletes evidence.
Run against paused disposable local S01 pipeline, not during active publication.
"""
from argparse import Namespace
from datetime import datetime,timezone
import uuid
from orchestration import polling,website_workflow as workflow
from transformation.batch import connect as release_connection
from transformation.publish import connect as published


def arguments(execution,fail=False):
    return Namespace(source='internal_web',execution_id=execution,dag_id=None,airflow_run_id=None,
        collection_mode='recovery',checkpoint_stream=None,reuse_cycle_config=False,
        window_end=datetime.now(timezone.utc),initial_start=datetime(2026,10,17,tzinfo=timezone.utc),
        overlap_seconds=120,wait_seconds=0,mapping_version='s01-v1',transformation_version='m05b-v1',
        abort=False,fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=fail)


def publication():
    with published() as c:
        return c.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0]


with release_connection() as c:
    assert not c.execute("SELECT batch_id FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchall(),'Active batch; stop before test'
args=arguments('m07-measured-'+uuid.uuid4().hex)
polling.prepare(args)
with release_connection() as blocker:
    blocker.execute("SELECT pg_advisory_lock(hashtext('platform-release'))")
    blocker.commit()
    try:
        polling.coordinate(args)
    except TimeoutError:
        pass
    else:
        raise AssertionError('Expected busy release timeout after real collection')
    finally:
        blocker.execute("SELECT pg_advisory_unlock(hashtext('platform-release'))")
        blocker.commit()
with workflow.connect() as c:
    assert c.execute("SELECT status FROM ops.task_attempts WHERE run_id=%s AND task_name='collect'",(args.workflow_id,)).fetchone()[0]=='SUCCEEDED'
    assert c.execute("SELECT count(*) FROM ops.task_attempts WHERE run_id=%s AND task_name<>'collect'",(args.workflow_id,)).fetchone()[0]==0
polling.coordinate(args)
assert publication()==args.batch_id
with workflow.connect() as c:
    before=c.execute('SELECT count(*) FROM ops.task_attempts WHERE run_id=%s',(args.workflow_id,)).fetchone()[0]
polling.coordinate(args)
with workflow.connect() as c:
    assert c.execute('SELECT count(*) FROM ops.task_attempts WHERE run_id=%s',(args.workflow_id,)).fetchone()[0]==before==4
    assert c.execute("SELECT count(*) FROM ops.execution_measurements WHERE run_id=%s AND stage IN ('collect','freeze','build_and_test','publish') AND outcome='SUCCEEDED' AND duration_ms>=0",(args.workflow_id,)).fetchone()[0]==4
    assert c.execute("SELECT min(started_at) FROM ops.execution_measurements WHERE run_id=%s AND stage='collect'",(args.workflow_id,)).fetchone()[0] < c.execute("SELECT min(started_at) FROM ops.execution_measurements WHERE run_id=%s AND stage='release_slot'",(args.workflow_id,)).fetchone()[0]
failed=arguments('m07-failed-gate-'+uuid.uuid4().hex,True)
polling.prepare(failed)
good=publication()
try:
    polling.coordinate(failed)
except Exception:
    workflow.run_stage(failed,'abort')
else:
    raise AssertionError('Injected dbt test failure was accepted')
assert publication()==good
with workflow.connect() as c:
    assert c.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(failed.batch_id,)).fetchone()[0]=='FAILED'
    assert c.execute("SELECT outcome FROM ops.execution_measurements WHERE run_id=%s AND stage='build_and_test'",(failed.workflow_id,)).fetchone()[0]=='FAILED'
print(f'M07 actual pipeline PASS successful_run={args.workflow_id} failed_run={failed.workflow_id}; real collection before held barrier, resume/no extra business attempts, failed gate retains good publication')
