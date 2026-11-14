"""Offline deployment admission; actual cold/main gates are separate."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools.s02_data import delta_deploy as deploy


class DeploymentTests(unittest.TestCase):
    def test_release_path_is_confined(self):
        for path in ('/tmp/plan','/opt/airflow/state/delta-plans/../x',
                     '/opt/airflow/state/delta-plans/a/b','/opt/airflow/state/delta-plans/'):
            with self.assertRaises(ValueError): deploy.plan_folder(path)
        self.assertEqual(deploy.plan_folder('/opt/airflow/state/delta-plans/review-v1'),
                         deploy.ROOT/'runtime/airflow/state/delta-plans/review-v1')

    def test_disabled_flag_has_no_database_side_effect(self):
        with patch.object(deploy,'query') as query:
            deploy.require_ready(object(),'')
            query.assert_not_called()

    def test_missing_migration_refuses(self):
        with patch.object(deploy,'query',return_value=[{'name':None}]):
            with self.assertRaises(ValueError):
                deploy.require_ready(object(),'/opt/airflow/state/delta-plans/review')

    def test_stale_pointer_refuses_before_any_source_switch(self):
        plan=dict(source='internal_web',mapping_version='local-live-v1',plan_sha256='a'*64)
        with patch.object(deploy,'load',return_value=plan),patch.object(deploy,'query',
                side_effect=([{'name':'ops.delta_batches'}],[{'plan_sha256':'b'*64}])):
            with self.assertRaises(ValueError):
                deploy.require_ready(object(),'/opt/airflow/state/delta-plans/review')

    def test_confirmation_precedes_all_actions(self):
        with self.assertRaises(ValueError): deploy.run(None,None,None,False)

    def test_failed_gates_precede_docker_actions(self):
        report=SimpleNamespace(read_text=lambda **kwargs:json.dumps({'status':'FAIL'}))
        with patch.object(deploy.subprocess,'run') as command:
            with self.assertRaises(ValueError): deploy.run(None,report,None,True)
            command.assert_not_called()

    def test_non_cycle_tasks_cannot_satisfy_restart_gate(self):
        report=SimpleNamespace(read_text=lambda **kwargs:json.dumps(dict(
            status='PASS',mapping_gate={'status':'PASS'},
            final_airflow_tasks=[dict(task_id='failed_workflow',state='skipped',try_number=0)])))
        with patch.object(deploy.subprocess,'run') as command:
            with self.assertRaisesRegex(ValueError,'exactly-two-try'):
                deploy.run(None,report,None,True)
            command.assert_not_called()

    def test_unrestored_owner_refuses_even_with_passing_root(self):
        report=SimpleNamespace(read_text=lambda **kwargs:json.dumps(dict(
            status='PASS',mapping_gate={'status':'PASS'},
            final_airflow_tasks=[dict(task_id='cycle',state='success',try_number=2)],
            owner_restored={'healthy':False})))
        with patch.object(deploy.subprocess,'run') as command:
            with self.assertRaisesRegex(ValueError,'main restoration'):
                deploy.run(None,report,None,True)
            command.assert_not_called()


if __name__=='__main__': unittest.main()
