"""Maintenance must disable interval creation without changing normal defaults."""
import os
from pathlib import Path
import sys
from datetime import timedelta
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestration.scheduling import periodic_schedule


class SchedulingTests(unittest.TestCase):
    def test_default_keeps_interval(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(periodic_schedule(timedelta(seconds=30)), timedelta(seconds=30))

    def test_drain_disables_periodic_schedule(self):
        with patch.dict(os.environ, {'POLLING_DRAIN_MODE': 'true'}):
            self.assertIsNone(periodic_schedule(timedelta(seconds=30)))

    def test_manual_stays_manual(self):
        with patch.dict(os.environ, {'POLLING_DRAIN_MODE': 'false'}):
            self.assertIsNone(periodic_schedule(timedelta(seconds=30), manual=True))

    def test_invalid_mode_rejected(self):
        with patch.dict(os.environ, {'POLLING_DRAIN_MODE': 'typo'}):
            with self.assertRaises(ValueError):
                periodic_schedule(timedelta(seconds=30))


if __name__ == '__main__':
    unittest.main(verbosity=2)
