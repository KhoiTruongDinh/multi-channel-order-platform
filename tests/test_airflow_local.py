"""Offline readiness/shutdown contract; real restart gate is separate."""
import io
import threading
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from orchestration import airflow_local as local


class StartupTests(unittest.TestCase):
    def test_key_persists_across_parent_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            first={}; second={}
            local.configure_jwt(directory,first)
            local.configure_jwt(directory,second)
            self.assertEqual(first,second)
            self.assertGreaterEqual(len(first['AIRFLOW__API_AUTH__JWT_SECRET']),64)

    def test_explicit_environment_key_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            environment={'AIRFLOW__API_AUTH__JWT_SECRET':'x'*64}
            local.configure_jwt(directory,environment)
            self.assertFalse((Path(directory)/'execution-jwt.key').exists())

    def test_invalid_retained_key_refuses_without_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'execution-jwt.key'
            path.write_text('short',encoding='utf-8')
            with self.assertRaises(ValueError): local.configure_jwt(directory,{})
            self.assertEqual(path.read_text(),'short')

    def test_api_readiness_does_not_require_scheduler(self):
        with patch.object(local,'urlopen',return_value=io.BytesIO(
                b'{"metadatabase":{"status":"healthy"},"scheduler":{"status":"unhealthy"}}')):
            self.assertTrue(local.api_ready())

    def test_bad_response_refuses(self):
        for body in (b'[]',b'{}',b'bad',b'{"metadatabase":null}'):
            with patch.object(local,'urlopen',return_value=io.BytesIO(body)):
                self.assertFalse(local.api_ready())

    def test_connection_refusal(self):
        with patch.object(local,'urlopen',side_effect=ConnectionRefusedError):
            self.assertFalse(local.api_ready())

    def test_timeout_is_failure_not_ready(self):
        with self.assertRaises(TimeoutError):
            local.wait_for_api(threading.Event(),timeout=0,ready=lambda:False)

    def test_cancel_does_not_dispatch(self):
        cancel=threading.Event(); cancel.set()
        self.assertFalse(local.wait_for_api(cancel,ready=lambda:True))

    def test_subcommand_gate_and_shutdown(self):
        events=[]; cancel=threading.Event()
        class Base:
            name='scheduler'
            def run(self):
                events.append('dispatch'); cancel.set()
            def stop(self):
                events.append('stop')
        with patch.object(local,'wait_for_api',side_effect=lambda event:events.append('ready') or True):
            command=local.gated_subcommand(Base,cancel,lambda:self.fail('unexpected failure'))()
            command.run(); command.stop()
        self.assertEqual(events,['ready','dispatch','stop'])

    def test_gate_failure_never_dispatches(self):
        events=[]
        class Base:
            name='scheduler'
            def run(self): events.append('dispatch')
        with patch.object(local,'wait_for_api',side_effect=TimeoutError):
            local.gated_subcommand(Base,threading.Event(),lambda:events.append('fail'))().run()
        self.assertEqual(events,['fail'])


if __name__=='__main__': unittest.main()
