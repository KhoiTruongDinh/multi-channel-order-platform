"""Windowless cycles and persisted settings after environment/config changes."""
import argparse
import os
import unittest
from unittest.mock import MagicMock,patch
from orchestration.polling import prepare


class CycleTests(unittest.TestCase):
    def test_page_size_is_persisted_on_new_cycles(self):
        args = self.args()
        c = MagicMock(); c.execute.return_value.fetchone.return_value = None
        with patch('orchestration.polling.workflow.connect') as factory, \
                patch.dict(os.environ, {'ETSY_RECOVERY_PAGE_SIZE': '50'}):
            factory.return_value.__enter__.return_value = c
            prepare(args)
        settings = c.execute.call_args.args[1][-1].obj
        self.assertEqual(settings['page_size'], 50)

    def test_retry_keeps_saved_page_size_despite_new_environment(self):
        for saved, expected in (({}, 1), ({'page_size': 20}, 20)):
            args = self.args(); c = MagicMock()
            c.execute.return_value.fetchone.return_value = (None,None,'etsy_replay','runtime','current',
                's01-v1','m06-v1',120,saved)
            with patch('orchestration.polling.workflow.connect') as factory, \
                    patch.dict(os.environ, {'ETSY_RECOVERY_PAGE_SIZE': '50'}):
                factory.return_value.__enter__.return_value = c
                prepare(args)
            self.assertEqual(args.page_size, expected)

    def test_retry_ignores_invalid_replacement_environment(self):
        args = self.args(); c = MagicMock()
        c.execute.return_value.fetchone.return_value = (None,None,'etsy_replay','runtime','current',
            's01-v1','m06-v1',120,{'page_size':20})
        with patch('orchestration.polling.workflow.connect') as factory, \
                patch.dict(os.environ, {'ETSY_RECOVERY_PAGE_SIZE':'invalid'}):
            factory.return_value.__enter__.return_value = c
            prepare(args)
        self.assertEqual(args.page_size,20)

    def test_invalid_persisted_page_size_is_rejected(self):
        for value in (True, '50', 0, 101):
            args = self.args(); c = MagicMock()
            c.execute.return_value.fetchone.return_value = (None,None,'etsy_replay','runtime','current',
                's01-v1','m06-v1',120,{'page_size': value})
            with patch('orchestration.polling.workflow.connect') as factory:
                factory.return_value.__enter__.return_value = c
                with self.assertRaises(ValueError): prepare(args)

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
