"""Local UI provisioning tests; no real credentials or runtime files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration.ui_credentials import provision


class CredentialsTests(unittest.TestCase):
    def test_empty_password_preserves_generated_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'passwords.json'
            path.write_text('{"admin":"synthetic-generated"}')
            original=path.read_bytes()
            provision(path,'admin','')
            self.assertEqual(path.read_bytes(),original)

    def test_explicit_password_and_username(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state/passwords.json'
            provision(path,'local_user','synthetic-test-only')
            self.assertEqual(json.loads(path.read_text()),{'local_user':'synthetic-test-only'})
            self.assertEqual(list(path.parent.glob('.passwords-*')),[])

    def test_invalid_user_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                provision(Path(folder)/'unused','admin:admin','test')


if __name__=='__main__':
    unittest.main(verbosity=2)
