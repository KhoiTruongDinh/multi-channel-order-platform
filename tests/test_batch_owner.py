"""Transform owner must be visible in the transaction that exposes FROZEN."""
import argparse
import unittest
from unittest.mock import MagicMock, patch

from transformation import batch
from orchestration import website_workflow as workflow


class OwnerTests(unittest.TestCase):
    def args(self, **changes):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.rowcount = 1
        values = dict(batch_id='batch',run_id='transform',source='etsy_sim',
                      mapping_version='mapping',transformation_version='version',
                      validation_mode='runtime',connection=conn,
                      airflow_dag_id='etsy_inbox',airflow_run_id='actual-airflow-run')
        values.update(changes)
        return argparse.Namespace(**values)

    def test_owner_in_initial_insert_before_commit(self):
        args = self.args()
        batch.freeze(args)
        calls = args.connection.execute.call_args_list
        insert = next(c for c in calls if 'INSERT INTO ops.pipeline_runs' in c.args[0])
        self.assertIn('airflow_dag_id, airflow_run_id', insert.args[0])
        self.assertEqual(insert.args[1][-2:], ('etsy_inbox','actual-airflow-run'))
        args.connection.commit.assert_called_once()

    def test_manual_cli_has_no_fabricated_owner(self):
        args = self.args(airflow_dag_id=None,airflow_run_id=None)
        batch.freeze(args)
        insert = next(c for c in args.connection.execute.call_args_list
                      if 'INSERT INTO ops.pipeline_runs' in c.args[0])
        self.assertEqual(insert.args[1][-2:], (None,None))

    def test_partial_owner_rejected_before_db_write(self):
        for dag, run in ((None,'run'),('dag',None)):
            args = self.args(airflow_dag_id=dag,airflow_run_id=run)
            with self.assertRaisesRegex(ValueError,'both DAG and run'):
                batch.freeze(args)
            args.connection.execute.assert_not_called()

    def test_workflow_passes_real_owner_for_both_freeze_paths(self):
        for direct in (True,False):
            args = self.args()
            args.dag_id='etsy_inbox'
            args.execution_id='derived:poll:run:drain'
            args.workflow_id='workflow'
            args.fault_after_freeze_once=False
            args.freeze_connection=args.connection if direct else None
            with patch.object(workflow,'batch_state',return_value=None), \
                 patch.object(batch,'freeze') as freeze, patch.object(workflow,'command') as command:
                workflow.perform(MagicMock(),args,'freeze',1)
            if direct:
                frozen = freeze.call_args.args[0]
                self.assertEqual((frozen.airflow_dag_id,frozen.airflow_run_id),
                                 ('etsy_inbox','actual-airflow-run'))
            else:
                arguments=command.call_args.args
                self.assertEqual(arguments[arguments.index('--airflow-run-id')+1], 'actual-airflow-run')


if __name__ == '__main__':
    unittest.main(verbosity=2)
