"""Offline durable scan/cache budgets; network and SQL semantics have a separate probe."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.etsy_recovery import begin_scan, finish_scan, page_history


class Scans(unittest.TestCase):
    def test_first_scan_commits_identity(self):
        db=Mock(); db.execute.return_value.fetchone.return_value=None
        self.assertEqual(begin_scan(db,'run'),(1,'RUNNING'))
        self.assertEqual(db.execute.call_args.args[1],('run',1)); db.commit.assert_called_once()

    def test_restart_and_validated_processing_keep_scan(self):
        for status in ('RUNNING','VALIDATED'):
            db=Mock(); db.execute.return_value.fetchone.return_value=(3,status)
            self.assertEqual(begin_scan(db,'run'),(3,status))
            self.assertEqual(db.execute.call_count,1); db.commit.assert_not_called()

    def test_only_invalid_scan_allocates_successor(self):
        db=Mock(); db.execute.return_value.fetchone.return_value=(2,'INVALID')
        self.assertEqual(begin_scan(db,'run'),(3,'RUNNING'))

    def test_scan_limit_survives_restart(self):
        db=Mock(); db.execute.return_value.fetchone.return_value=(5,'INVALID')
        with self.assertRaisesRegex(RuntimeError,'budget exhausted'): begin_scan(db,'run')
        self.assertEqual(db.execute.call_count,1); db.commit.assert_not_called()

    def test_legacy_cache_is_adopted_only_by_scan_one(self):
        legacy=(200,{},'raw',None,20)
        db=Mock(); db.execute.return_value.fetchall.return_value=[legacy]
        self.assertEqual(page_history(db,'run','url',1),(1,legacy))
        self.assertEqual(page_history(db,'run','url',2),(1,None))

    def test_new_scan_does_not_reset_url_budget_or_reuse_invalid_pages(self):
        old=(200,{},'old',1,20); failed=(503,None,'failed',2,0)
        db=Mock(); db.execute.return_value.fetchall.return_value=[failed,old,old,old,old]
        self.assertEqual(page_history(db,'run','url',2),(5,failed))
        self.assertEqual(page_history(db,'run','url',3),(5,None))

    def test_overfull_legacy_budget_refuses(self):
        db=Mock(); db.execute.return_value.fetchall.return_value=[(200,{},'raw',None,1)]*6
        with self.assertRaisesRegex(RuntimeError,'HTTP budget'): page_history(db,'run','url',1)

    def test_finish_is_guarded_and_committed(self):
        for valid in (True,False):
            db=Mock(); finish_scan(db,'run',2,valid)
            sql,args=db.execute.call_args.args
            self.assertIn("status='RUNNING'",sql)
            self.assertEqual(args,('VALIDATED' if valid else 'INVALID',None if valid else 'PAGE_SET_CHANGED','run',2))
            db.commit.assert_called_once()


if __name__=='__main__': unittest.main(verbosity=2)
