"""Offline probe assertion boundaries; not database/runtime recovery proof."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import m08c_pipeline_probe as probe
from tools.s02_data import live
from test_support import m08c_source_worker_probe as worker_probe


class SignatureTests(unittest.TestCase):
    def test_published_assertions_use_existing_publisher_and_readonly_snapshot(self):
        connection = MagicMock()
        connection.execute.return_value.fetchone.side_effect = [(3, 'a'), (6, 'b')]
        with patch.object(probe, 'publication_connect') as publisher, \
                patch.object(probe, 'connect') as transform:
            publisher.return_value.__enter__.return_value = connection
            result = probe.business_signature(('core.orders_current', 'ops.publication_state'))
        transform.assert_not_called()
        publisher.assert_called_once_with()
        self.assertEqual(result, ((3, 'a'), (6, 'b')))
        calls = connection.execute.call_args_list
        self.assertEqual(calls[0].args, ('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY',))
        self.assertTrue(calls[1].args[0].endswith('core.orders_current t'))
        self.assertTrue(calls[2].args[0].endswith('ops.publication_state t'))

    def test_assertion_query_errors_are_not_counted_as_expected_faults(self):
        connection = MagicMock()
        connection.execute.side_effect = [None, RuntimeError('read denied')]
        with patch.object(probe, 'publication_connect') as publisher:
            publisher.return_value.__enter__.return_value = connection
            with self.assertRaisesRegex(RuntimeError, 'read denied'):
                probe.business_signature(('core.orders_current',))
        self.assertEqual(publisher.return_value.__exit__.call_args.args[0], RuntimeError)

    def test_operational_reads_keep_transform_connection(self):
        with patch.object(probe, 'connect') as transform, \
                patch.object(probe, 'publication_connect') as publisher:
            transform.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (4,)
            self.assertEqual(probe.value('SELECT count(*) FROM ops.task_attempts'), 4)
        publisher.assert_not_called()


class WorkerBoundaryTests(unittest.TestCase):
    def test_ready_marker_uses_actual_worker_tick_heartbeat(self):
        from simulator import live_worker as source
        token = 'a' * 32
        seen = []
        with patch.object(source, 'HEARTBEAT'), \
                patch.object(source, 'main', side_effect=lambda: seen.append(source.HEARTBEAT)):
            worker_probe.worker(False, token)
        self.assertEqual(seen, [Path('/tmp/m08c-worker-ready-' + token)])

    def test_source_worker_environment_excludes_platform_and_admin_credentials(self):
        contents = '\n'.join(k + '=test-value' for k in ('MARKETPLACE_WRITER_PASSWORD',
            'WEBSITE_WRITER_PASSWORD', 'ETSY_SIGNING_SECRET', 'PLATFORM_PUBLISHER_PASSWORD',
            'POSTGRES_SUPERUSER_PASSWORD', 'AIRFLOW_APP_PASSWORD'))
        with patch.object(Path, 'read_text', return_value=contents):
            env = worker_probe.environment()
        self.assertEqual({k for k in env if k.endswith('PASSWORD') or k.endswith('SECRET')},
                         {'MARKETPLACE_WRITER_PASSWORD','WEBSITE_WRITER_PASSWORD','ETSY_SIGNING_SECRET'})


class DrainTests(unittest.TestCase):
    def test_public_entrypoint_still_targets_only_four_live_dags(self):
        db = MagicMock()
        with patch.object(live, '_drain_schedules') as algorithm:
            live.drain(db, timeout=10)
        algorithm.assert_called_once_with(db, 10, live.DAGS)

    def test_disposable_dag_drain_does_not_pause_other_dags(self):
        db = MagicMock()
        with patch.object(live, 'query', side_effect=[
            [dict(dag_id='test_only', is_paused=False), dict(dag_id='website_polling', is_paused=False)], [], []]):
            live._drain_schedules(db, timeout=10, dags=('test_only',))
        pauses = [call.args[0][-1] for call in db.command.call_args_list if 'pause' in call.args[0]]
        self.assertEqual(pauses, ['test_only'])

    def test_actual_algorithm_timeout_keeps_active_task_runnable(self):
        db = MagicMock()
        with patch.object(live, 'query', side_effect=[
            [dict(dag_id='test_only', is_paused=False)], [dict(dag_id='test_only')], [dict(dag_id='test_only')]]):
            with self.assertRaisesRegex(RuntimeError, 'Drain timeout'):
                live._drain_schedules(db, timeout=0, dags=('test_only',))
        self.assertFalse(any('pause' in call.args[0] for call in db.command.call_args_list))

    def test_foreign_active_dag_refuses_before_mutation(self):
        db = MagicMock()
        with patch.object(live, 'query', side_effect=[[], [dict(dag_id='unrelated')]]):
            with self.assertRaisesRegex(ValueError, 'manual/replay DAG active'):
                live._drain_schedules(db, timeout=10, dags=('test_only',))
        db.command.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
