"""Cycle bootstrap and retry binding without mutating a real checkpoint."""
import argparse
from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import MagicMock,patch

from orchestration.polling import prepare


class CycleTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(source='ebay_sim',execution_id='unit-cycle',dag_id='ebay_polling',
            window_end=datetime.now(timezone.utc)-timedelta(seconds=1),initial_start=None,
            mapping_version='s01-v1',transformation_version='m05b-v1',overlap_seconds=120,
            fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False)

    def test_missing_bootstrap_does_not_open_a_window(self):
        c=MagicMock()
        c.execute.return_value.fetchone.side_effect=[None,None]
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            with self.assertRaisesRegex(ValueError,'explicit initial start'):
                prepare(self.args())
        self.assertFalse(any('INSERT' in call.args[0] for call in c.execute.call_args_list))

    def test_retry_uses_original_window(self):
        args=self.args()
        original_start=args.window_end-timedelta(minutes=4)
        settings={'fault_after_raw_once':False,'fault_after_freeze_once':False,'inject_test_failure':False}
        c=MagicMock()
        c.execute.return_value.fetchone.return_value=(original_start,args.window_end,args.dag_id,
            'runtime','current','s01-v1','m05b-v1',120,settings)
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            prepare(args)
        self.assertEqual(args.window_start,original_start)
        self.assertFalse(any('extraction_checkpoints' in call.args[0] for call in c.execute.call_args_list))

    def test_retry_cannot_switch_configuration(self):
        args=self.args()
        c=MagicMock()
        c.execute.return_value.fetchone.return_value=(args.window_end-timedelta(minutes=2),args.window_end,
            args.dag_id,'runtime','current','s01-v1','other-version',120,{})
        with patch('orchestration.polling.workflow.connect') as factory:
            factory.return_value.__enter__.return_value=c
            with self.assertRaisesRegex(ValueError,'different bounds/context/configuration'):
                prepare(args)


if __name__=='__main__':
    unittest.main(verbosity=2)
