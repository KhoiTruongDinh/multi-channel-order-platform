"""Terminal-DAG audit reconciliation delegates abort, never resets or fakes success."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestration import draining as d
from orchestration.website_workflow import identity


class DrainTests(unittest.TestCase):
    def row(self):
        execution = 'scheduled__test:recovery'
        return (identity('poll:etsy_sim:'+execution, 'workflow'), 'etsy_sim',
                'etsy_recovery', 'scheduled__test', 'm04:poll:etsy_sim:'+execution, None)

    def run_case(self, dag_state, live=None, parent_state='FAILED'):
        parent, final, meta = MagicMock(), MagicMock(), MagicMock()
        parent.__enter__.return_value.execute.return_value.fetchall.return_value = [self.row()]
        final.__enter__.return_value.execute.return_value.fetchone.return_value = (parent_state,)
        meta.__enter__.return_value.execute.side_effect = [
            MagicMock(**{'fetchone.return_value': dag_state}),
            MagicMock(**{'fetchone.return_value': live})]
        with patch.object(d, 'connect', side_effect=[parent, final]), \
             patch.object(d.psycopg, 'connect', return_value=meta), \
             patch.object(d.subprocess, 'run') as invoke, \
             patch.dict(d.os.environ, {'AIRFLOW_APP_PASSWORD': 'test-only'}):
            d.main()
            return invoke

    def test_only_terminal_failed_delegates_abort(self):
        invoke = self.run_case(('failed',))
        invoke.assert_called_once()
        command = invoke.call_args.args[0]
        self.assertIn('--abort', command)
        self.assertIn('--reuse-cycle-config', command)
        self.assertNotIn('clear', command)

    def test_live_or_success_or_missing_dag_is_untouched(self):
        for state in (('running',), ('queued',), ('success',), None):
            with self.subTest(state=state):
                self.run_case(state).assert_not_called()

    def test_live_task_is_untouched_even_if_dag_failed(self):
        self.run_case(('failed',), live=(1,)).assert_not_called()

    def test_failed_abort_is_not_accepted(self):
        with self.assertRaises(RuntimeError):
            self.run_case(('failed',), parent_state='RUNNING')

    def test_identity_mismatch_rejected(self):
        row = list(self.row())
        row[4] += '-tampered'
        with self.assertRaises(ValueError):
            d.abort_command(row)


if __name__ == '__main__':
    unittest.main(verbosity=2)
