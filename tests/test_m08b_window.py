"""No Docker: maintenance authority and finally restoration regression."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import m08b_window as window


class WindowTests(unittest.TestCase):
    def test_mutually_exclusive_clocks_refused_before_docker(self):
        with patch.object(window.guard,'docker') as docker:
            with self.assertRaises(window.guard.SafetyError):
                window.run_window(True,local_replay=True,local_realtime=True)
            docker.assert_not_called()

    def test_no_confirmation_never_calls_docker(self):
        with patch.object(window.guard,'docker') as docker:
            with self.assertRaises(window.guard.SafetyError): window.run_window(False)
            docker.assert_not_called()

    def test_initialization_failure_still_restores_exact_airflow_only(self):
        with tempfile.TemporaryDirectory() as directory:
            def docker(*args,**kwargs):
                if args[0]=='ps': return 'owner-airflow'
                if args[:3]==('stop','--timeout','30'):
                    self.assertEqual(args[3],'owner-airflow'); return 'owner-airflow'
                raise AssertionError('Unexpected Docker mutation: '+str(args))
            with patch.object(window.guard,'ROOT',Path(directory)), \
                 patch.object(window.guard,'owner_container',return_value='owner-postgres'), \
                 patch.object(window.guard,'owner_idle'), \
                 patch.object(window.guard,'protected_signature',return_value='protected'), \
                 patch.object(window.guard,'owner_sql',return_value='system-id'), \
                 patch.object(window,'pauses',return_value=[dict(dag_id='x',is_paused=True)]), \
                 patch.object(window,'state',return_value={'Running':True,'Health':{'Status':'healthy'}}), \
                 patch.object(window.guard,'docker',side_effect=docker), \
                 patch.object(window.guard,'init',side_effect=window.guard.SafetyError('init failed')), \
                 patch.object(window,'restore') as restore:
                with self.assertRaisesRegex(window.guard.SafetyError,'init failed'): window.run_window(True)
                restore.assert_called_once_with('owner-airflow')
            evidence=list(Path(directory).glob('runtime/isolated/window-*/owner-window.json'))
            self.assertEqual(len(evidence),1)
            result=json.loads(evidence[0].read_text())
            self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['owner_restore'],'HEALTHY')
            self.assertEqual(result['owner_protection'],'PASS')
            start=evidence[0].with_name('owner-window-start.json')
            snapshot=json.loads(start.read_text())
            self.assertEqual(snapshot['owner_airflow'],'owner-airflow')
            self.assertEqual(snapshot['protected_before'],'protected')
            self.assertEqual(snapshot['pauses_before'],[dict(dag_id='x',is_paused=True)])


if __name__=='__main__': unittest.main(verbosity=2)
