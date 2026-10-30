"""Coordinator ordering plus real rollback-only measurement/lock invariants."""
from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration import polling,telemetry,website_workflow as workflow
from transformation.batch import connect as release_connection


class CoordinatorTests(unittest.TestCase):
    def test_collect_precedes_global_barrier(self):
        events=[]
        @contextmanager
        def connection():
            yield object()
        def slot(lock,args,source_slot=False):
            events.append('source_slot' if source_slot else 'release_slot')
        args=Namespace(abort=False,execution_id='ordering',workflow_id=uuid.uuid4(),batch_id=uuid.uuid4(),source='ebay_sim')
        with patch.object(polling,'release_connection',connection),patch.object(polling,'claim_slot',side_effect=slot),patch.object(workflow,'run_stage',side_effect=lambda a,s:events.append(s)):
            polling.coordinate(args)
        self.assertEqual(events,['source_slot','collect','release_slot','freeze','build_and_test','publish'])

    def test_real_slot_timeout_no_business_attempt(self):
        execution='m07-slot-'+uuid.uuid4().hex
        args=Namespace(execution_id=execution,workflow_id=workflow.identity(execution,'workflow'),batch_id=workflow.identity(execution,'batch'),
            source='ebay_sim',validation_mode='runtime',window_start=None,window_end=None,dag_id=None,wait_seconds=0)
        # A real parent audit is intentionally retained; it is explicitly failed below.
        with workflow.connect() as c:
            workflow.ensure_run(c,args)
        with release_connection() as blocker,release_connection() as contender:
            blocker.execute("SELECT pg_advisory_lock(hashtext('platform-release'))")
            blocker.commit()
            try:
                with self.assertRaises(TimeoutError):
                    polling.claim_slot(contender,args)
                # A different-source acquisition slot is available even while release is busy.
                polling.claim_slot(contender,args,source_slot=True)
            finally:
                blocker.execute("SELECT pg_advisory_unlock(hashtext('platform-release'))")
                blocker.commit()
        with workflow.connect() as c:
            rows=c.execute('SELECT stage,outcome,duration_ms FROM ops.execution_measurements WHERE run_id=%s ORDER BY stage',(args.workflow_id,)).fetchall()
            self.assertEqual([(r[0],r[1]) for r in rows],[('release_slot','TIMED_OUT'),('source_slot','SUCCEEDED')])
            self.assertTrue(all(r[2]>=0 for r in rows))
            self.assertEqual(c.execute('SELECT count(*) FROM ops.task_attempts WHERE run_id=%s',(args.workflow_id,)).fetchone()[0],0)
            c.execute("UPDATE ops.pipeline_runs SET status='FAILED',finished_at=clock_timestamp(),error_code='M07_SLOT_PROBE' WHERE run_id=%s",(args.workflow_id,))

    def test_terminal_measurement_immutable(self):
        with workflow.connect() as c:
            # Use an existing run solely for FK context, then roll back all new measurements.
            run=c.execute("SELECT run_id FROM ops.pipeline_runs WHERE source_system='ebay_sim' LIMIT 1").fetchone()[0]
            key=uuid.uuid4()
            c.execute('''INSERT INTO ops.execution_measurements(measurement_id,run_id,source_system,source_account_id,
                validation_mode,stage,started_at,finished_at,duration_ms,outcome)
                VALUES(%s,%s,'ebay_sim','seller_sim_01','runtime','collect',%s,%s,0,'SUCCEEDED')''',
                (key,run,datetime.now(timezone.utc),datetime.now(timezone.utc)))
            with self.assertRaises(Exception):
                c.execute("UPDATE ops.execution_measurements SET outcome='FAILED' WHERE measurement_id=%s",(key,))
            c.rollback()


if __name__=='__main__':
    unittest.main(verbosity=2)
