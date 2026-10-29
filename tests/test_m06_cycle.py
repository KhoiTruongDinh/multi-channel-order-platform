"""Windowless cycles and persisted settings after environment/config changes."""
import argparse
import unittest
from unittest.mock import MagicMock,patch
from orchestration.polling import prepare


class CycleTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(source='etsy_sim',execution_id='cycle-unit:drain',dag_id='etsy_replay',
            collection_mode='drain',window_end=None,initial_start=None,checkpoint_stream='receipts_polling',
            mapping_version='s01-v1',transformation_version='m06-v1',overlap_seconds=120,
            fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False,
            reuse_cycle_config=True)

    def test_windowless_retry_restores_bound_settings(self):
        args=self.args()
        c=MagicMock()
        settings={'collection_mode':'drain','checkpoint_stream':'receipts_polling',
                  'fault_after_raw_once':False,'fault_after_freeze_once':False,'inject_test_failure':True}
        c.execute.return_value.fetchone.return_value=(None,None,'etsy_replay','runtime','current',
            's01-v1','m06-original',120,settings)
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            prepare(args)
        self.assertIsNone(args.window_start)
        self.assertEqual(args.transformation_version,'m06-original')
        self.assertTrue(args.inject_test_failure)
        self.assertFalse(any('extraction_checkpoints' in call.args[0] for call in c.execute.call_args_list))

    def test_reuse_never_changes_dag_context(self):
        args=self.args()
        c=MagicMock()
        c.execute.return_value.fetchone.return_value=(None,None,'another_dag','runtime','current',
            's01-v1','m06-v1',120,{})
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            with self.assertRaisesRegex(ValueError,'different bounds/context'):
                prepare(args)

    def test_persisted_settings_cannot_override_source(self):
        args=self.args()
        c=MagicMock()
        c.execute.return_value.fetchone.return_value=(None,None,'etsy_replay','runtime','current',
            's01-v1','m06-v1',120,{'source':'ebay_sim'})
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            with self.assertRaisesRegex(ValueError,'unsupported persisted'):
                prepare(args)

    def test_reuse_never_relabels_airflow_run(self):
        args=self.args()
        c=MagicMock()
        c.execute.return_value.fetchone.return_value=(None,None,'etsy_replay','runtime','current',
            's01-v1','m06-v1',120,{},'another_airflow_run')
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            with self.assertRaisesRegex(ValueError,'different bounds/context'):
                prepare(args)


if __name__=='__main__':
    unittest.main(verbosity=2)
