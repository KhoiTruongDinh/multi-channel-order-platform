"""Offline guard for report meaning; not UI or database integration."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReportClockTests(unittest.TestCase):
    def test_creation_cohort_and_attempts_are_explicit(self):
        app = (ROOT/'reports/app.py').read_text(encoding='utf-8')
        self.assertIn('Orders by source creation date', app)
        self.assertIn('Pipeline attempts by channel', app)
        self.assertIn('not received-data or processing volume', app)
        self.assertIn('not recognized revenue or ingestion throughput', app)

    def test_daily_scope_does_not_discard_late_dates(self):
        sql = (ROOT/'transformations/macros/delta.sql').read_text(encoding='utf-8')
        self.assertNotIn('CURRENT_DATE', sql.upper())
        self.assertIn('macro activity_scope', sql)
        self.assertIn("platform.delta_bootstrap", sql)
        self.assertIn('INNER JOIN ops.delta_batch_keys', sql)
        self.assertIn('d.activity_date+1', sql)


if __name__ == '__main__':
    unittest.main()
