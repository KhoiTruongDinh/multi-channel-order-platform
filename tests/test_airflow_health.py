"""Live health probe component checks; no running scheduler required."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration import airflow_health as h


class HealthTests(unittest.TestCase):
    def sample(self): return {name:dict(status='healthy') for name in h.REQUIRED}

    def test_all_required_components_healthy(self):
        self.assertTrue(h.healthy(self.sample()))

    def test_missing_or_invalid_payload_refused(self):
        for value in (None,[],True,{},dict(scheduler='healthy')):
            with self.subTest(value=value): self.assertFalse(h.healthy(value))

    def test_http_success_alone_does_not_hide_bad_heartbeat(self):
        for name in h.REQUIRED:
            value=self.sample(); value[name]['status']='unhealthy'
            with self.subTest(name=name): self.assertFalse(h.healthy(value))

    def test_bounded_local_probe_succeeds(self):
        with patch.object(h,'urlopen',return_value=io.StringIO(json.dumps(self.sample()))) as request:
            self.assertEqual(h.main(),0)
        request.assert_called_once_with(h.URL,timeout=8)

    def test_transport_error_fails_without_leaking_error_body(self):
        output=io.StringIO()
        with patch.object(h,'urlopen',side_effect=TimeoutError('private-value')),redirect_stdout(output):
            self.assertEqual(h.main(),1)
        self.assertNotIn('private-value',output.getvalue())

    def test_malformed_response_fails(self):
        with patch.object(h,'urlopen',return_value=io.StringIO('not JSON')),redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(),1)


if __name__=='__main__': unittest.main(verbosity=2)
