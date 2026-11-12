"""Drain control-flow regression; run with the project psycopg environment."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion import etsy


class WorkDB:
    """Only the selection/count interface; not a PostgreSQL correctness proof."""

    def __init__(self, count):
        self.states = {n: 'PENDING' for n in range(count)}
        self.attempts = {n: 0 for n in self.states}
        self.selected = []
        self.completed = []

    def execute(self, sql, params):
        result = Mock()
        if 'SELECT work_id' in sql:
            result.__iter__ = Mock(return_value=iter(
                (n,) for n, state in self.states.items() if state in ('PENDING', 'LEASED')))
        elif 'SELECT count(*)' in sql:
            scope = params[1]
            result.fetchone.return_value = (sum(
                state != 'SUCCEEDED' for n, state in self.states.items() if n in scope),)
        else:
            raise AssertionError('unexpected SQL')
        return result

    def commit(self):
        pass

    def claim(self, conn, only, collection_run):
        self.selected.append(tuple(only))
        for work in only:
            if self.states.get(work) == 'PENDING':
                self.states[work] = 'LEASED'
                self.attempts[work] += 1
                return (work,)
        return None

    def process(self, conn, work, observed):
        self.states[work] = 'SUCCEEDED'
        self.completed.append(work)
        return True


class DrainTests(unittest.TestCase):
    def run_drain(self, db, only=None, process=None, claim=None):
        acquire = process or db.process
        with patch.object(etsy, 'expire_exhausted'), patch.object(etsy, 'shop', return_value='7001'), \
                patch.object(etsy, 'claim', side_effect=claim or db.claim), \
                patch.object(etsy, 'process', side_effect=lambda conn, lease, observed:
                             acquire(conn, lease[0], observed)):
            etsy.drain(db, only=only, collection_run='collection')

    def test_250_successes_finish_one_invocation(self):
        db = WorkDB(250)
        self.run_drain(db)
        self.assertEqual(db.completed, list(range(250)))
        self.assertEqual(set(db.attempts.values()), {1})

    def test_explicit_recovery_scope_larger_than_100(self):
        db = WorkDB(300)
        self.run_drain(db, only=list(range(250)))
        self.assertEqual(len(db.completed), 250)
        self.assertTrue(all(db.states[n] == 'PENDING' for n in range(250, 300)))

    def test_arrivals_do_not_extend_current_invocation(self):
        db = WorkDB(125)

        def process(conn, work, observed):
            db.states[1000 + work] = 'PENDING'
            return db.process(conn, work, observed)

        self.run_drain(db, process=process)
        self.assertEqual(db.completed, list(range(125)))
        self.assertTrue(all(db.states[n] == 'PENDING' for n in range(1000, 1125)))

    def test_interruption_after_120_resumes_without_refetch(self):
        db = WorkDB(250)

        def process(conn, work, observed):
            result = db.process(conn, work, observed)
            if len(db.completed) == 120:
                raise RuntimeError('interrupted after durable completion')
            return result

        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            self.run_drain(db, process=process)
        self.run_drain(db)
        self.assertEqual(db.completed, list(range(250)))
        self.assertEqual(set(db.attempts.values()), {1})

    def test_http_failure_stops_without_spinning_or_reset(self):
        db = WorkDB(250)

        def failed(conn, work, observed):
            db.states[work] = 'PENDING'
            return False

        with self.assertRaisesRegex(RuntimeError, 'receipt work incomplete'):
            self.run_drain(db, process=failed)
        self.assertEqual(db.attempts[0], 1)
        self.assertEqual(len(db.selected), 1)
        self.assertEqual(db.completed, [])

    def test_no_claimable_work_is_not_false_success(self):
        db = WorkDB(2)
        with self.assertRaisesRegex(RuntimeError, '2 receipt work items unresolved'):
            self.run_drain(db, claim=lambda *args: None)
        self.assertEqual(db.completed, [])

    def test_claim_loop_is_finite_even_without_expected_progress(self):
        db = WorkDB(3)
        calls = []

        def repeated_claim(*args):
            calls.append(0)
            return (0,)

        with self.assertRaisesRegex(RuntimeError, '2 receipt work items unresolved'):
            self.run_drain(db, claim=repeated_claim)
        self.assertEqual(len(calls), 3)

    def test_terminal_work_in_explicit_scope_remains_unresolved(self):
        db = WorkDB(1)
        db.states[0] = 'FAILED'
        with self.assertRaisesRegex(RuntimeError, '1 receipt work items unresolved'):
            self.run_drain(db, only=[0])
        self.assertEqual(db.attempts[0], 0)

    def test_completed_explicit_scope_does_not_refetch(self):
        db = WorkDB(2)
        db.states[0] = 'SUCCEEDED'
        self.run_drain(db, only=[0])
        self.assertEqual(db.completed, [])
        self.assertEqual(db.states[1], 'PENDING')

    def test_empty_scope_does_not_claim(self):
        db = WorkDB(1)
        self.run_drain(db, only=[])
        self.assertEqual(db.selected, [])

    def test_recovery_does_not_checkpoint_incomplete_drain(self):
        db = Mock()
        db.execute.return_value.fetchall.return_value = []
        args = Mock(execution_id='recovery', page_size=1)
        with patch.object(etsy, 'begin_scan', return_value=(1, 'VALIDATED')), \
                patch.object(etsy, 'recovery_pages', return_value=[(123, 'raw')]), \
                patch.object(etsy, 'require_recovery_allowed'), \
                patch.object(etsy, 'enqueue', return_value='work'), \
                patch.object(etsy, 'drain', side_effect=RuntimeError('incomplete')):
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                etsy.recover(db, args, 'run')
        self.assertFalse(any('extraction_checkpoints' in call.args[0]
                             for call in db.execute.call_args_list))


if __name__ == '__main__':
    unittest.main(verbosity=2)
