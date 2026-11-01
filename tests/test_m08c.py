"""Offline M08C target/evidence guards; no Docker mutation or runtime PASS claims."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import ExitStack

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import m08c as c


class GuardTests(unittest.TestCase):
    def execute_case(self, fail_probe=False, fail_cleanup=False, case='lease_fencing'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            h = Mock(root=root, marker=dict(id='abc', project='m08a-abc', db_system_id='123'), steps=[],
                     model=dict(services={name:dict(image='test-'+name) for name in (*c.RUNTIME_SERVICES[1:],'airflow')}))
            calls = []

            def command(args, **kwargs):
                calls.append(args)
                if args[0] == 'run' and fail_probe:
                    raise c.guard.SafetyError('probe failed')
                if args[0] == 'stop' and fail_cleanup:
                    raise c.guard.SafetyError('cleanup failed')
                return 'probe PASS'

            h.dc.side_effect = command
            with ExitStack() as stack:
                stack.enter_context(patch.object(c, 'ROOT', root))
                stack.enter_context(patch.object(c, 'inventory', return_value=[
                    dict(id=case, runner='test_m06_receiver.py' if case=='receiver_audit' else 'test_m06_leases.py', scope='rollback-only')]))
                stack.enter_context(patch.object(c, 'target', return_value={'postgres'}))
                stack.enter_context(patch.object(c, 'idle'))
                stack.enter_context(patch.object(c.guard, 'resource_preflight'))
                stack.enter_context(patch.object(c.guard, 'execute', return_value='test-sha'))
                stack.enter_context(patch.object(c.guard, 'digest', return_value='test-hash'))
                stack.enter_context(patch.object(c.guard, 'docker', return_value=''))
                if fail_probe or fail_cleanup:
                    with self.assertRaises(c.guard.SafetyError):
                        c.run_case(h, case)
                else:
                    c.run_case(h, case)
            report = json.loads(next((root / 'evidence').glob('m08c-*.json')).read_text())
            return calls, report, (root / 'evidence/m08c.running').exists()

    def test_success_stops_only_services_started_by_case(self):
        calls, report, latch = self.execute_case()
        stop = next(args for args in calls if args[0] == 'stop')
        self.assertNotIn('postgres', stop)
        self.assertNotIn('airflow', stop)
        self.assertEqual(report['status'], 'PASS')
        self.assertFalse(report['milestone_complete'])
        self.assertFalse(latch)

    def test_receiver_key_is_a_private_controller_mount_not_airflow_env(self):
        calls, report, _ = self.execute_case(case='receiver_audit')
        run = next(args for args in calls if args[0] == 'run')
        self.assertTrue(any(arg.endswith(':/m08c/private.env:ro') for arg in run))
        self.assertIn('test_support.m08c_probe_entry', run)
        self.assertFalse(any(arg.startswith('ETSY_SIGNING_SECRET=') for arg in run))
        self.assertEqual(report['status'], 'PASS')

    def test_failed_probe_retains_failure_evidence_and_stops_started_services(self):
        calls, report, latch = self.execute_case(fail_probe=True)
        self.assertTrue(any(args[0] == 'stop' for args in calls))
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['cleanup'], 'PASS')
        self.assertFalse(latch)

    def test_failed_cleanup_retains_latch_and_cannot_report_pass(self):
        _, report, latch = self.execute_case(fail_cleanup=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['cleanup'], 'FAIL')
        self.assertTrue(latch)

    def test_inventory_keeps_unimplemented_required_cases_visible(self):
        cases = c.inventory()
        self.assertEqual(len({r['id'] for r in cases}), len(cases))
        required = {r['id'] for r in cases}
        self.assertIn('publish_atomicity', required)
        self.assertIn('scheduled_pause_resume', required)
        self.assertIn('abrupt_service_loss', required)

    def test_unsupported_case_never_checks_docker(self):
        h = Mock()
        with patch.object(c, 'inventory', return_value=[dict(id='blocked', runner=None)]):
            with self.assertRaises(c.guard.SafetyError):
                c.run_case(h, 'blocked')
        h.check.assert_not_called()
        h.dc.assert_not_called()

    def test_reject_owner_or_unbound_or_b_marker_before_check(self):
        for marker in (dict(project=c.guard.OWNER, db_system_id='123'),
                       dict(project='m08a-test', db_system_id=None),
                       dict(project='m08a-test', db_system_id='123', profile='m08b')):
            with self.subTest(marker=marker):
                h = Mock(marker=marker)
                with self.assertRaises(c.guard.SafetyError):
                    c.target(h)
                h.check.assert_not_called()

    def test_baseline_identity_and_active_services_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            result = root / 'evidence/result.json'
            result.write_text(json.dumps(dict(id='abc', status='PASS', test_db_system_id='123')))
            h = Mock(root=root, marker=dict(id='abc', project='m08a-abc', db_system_id='123'))
            h.dc.return_value = 'postgres\nairflow'
            with self.assertRaisesRegex(c.guard.SafetyError, 'Stop test Airflow'):
                c.target(h)
            h.dc.return_value = 'postgres'
            self.assertEqual(c.target(h), {'postgres'})
            result.write_text(json.dumps(dict(id='foreign', status='PASS', test_db_system_id='123')))
            with self.assertRaisesRegex(c.guard.SafetyError, 'baseline did not pass'):
                c.target(h)

    def test_active_batch_refused_without_clear_or_abort(self):
        h = Mock()
        h.sql.side_effect = ['0', '1']
        with self.assertRaisesRegex(c.guard.SafetyError, 'Active/orphaned'):
            c.idle(h)
        h.dc.assert_not_called()

    def test_failed_preflight_never_starts_services(self):
        h = Mock()
        with patch.object(c, 'target', return_value=set()), \
             patch.object(c.guard, 'resource_preflight', side_effect=c.guard.SafetyError('memory')):
            with self.assertRaisesRegex(c.guard.SafetyError, 'memory'):
                c.run_case(h, 'stage_resume')
        h.dc.assert_not_called()

    def test_run_requires_explicit_disposable_confirmation(self):
        with patch.object(sys, 'argv', ['m08c', 'run', '--id', 'abcdef123456', '--case', 'lease_fencing']), \
             patch.object(c.guard, 'Harness') as harness:
            with self.assertRaises(c.guard.SafetyError):
                c.main()
        harness.assert_not_called()

    def test_run_refuses_unimplemented_before_loading_target(self):
        with patch.object(sys, 'argv', ['m08c', 'run', '--id', 'abcdef123456', '--case',
                                       'blocked', '--confirm-disposable']), \
             patch.object(c.guard, 'Harness') as harness, \
             patch.object(c, 'inventory', return_value=[dict(id='blocked', runner=None)]):
            with self.assertRaises(c.guard.SafetyError):
                c.main()
        harness.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
