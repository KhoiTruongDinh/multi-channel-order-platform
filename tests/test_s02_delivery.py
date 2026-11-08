"""Prepared delivery plans: offline invariants, not pipeline acceptance."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.s02_data.config import validate,parse_time
from tools.s02_data.generate import events
from tools.s02_data.delivery import plan,sql
from tools.s02_data.load import prepare

ROOT=Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def config(self):
        c=json.loads((ROOT/'tools/s02_data/config/sim_delivery_demo.json').read_text())
        c['start_at']='2026-11-05T00:00:00Z'
        return validate(c)

    def test_repeat_and_omission_do_not_change_source(self):
        c=self.config(); batches=[b for b in events(c) if b[0]['source']=='etsy_sim']
        self.assertEqual([len(plan(b,c)) for b in batches],[0,6,2,2])
        original=copy.deepcopy(batches)
        for batch in batches: plan(batch,c)
        self.assertEqual(batches,original)

    def test_reorder_causal_source_and_repeat_gap(self):
        c=self.config(); b=[b for b in events(c) if b[0]['source']=='etsy_sim'][1]
        rows=plan(b,c,True)
        self.assertGreater(rows[0]['due_at'],rows[3]['due_at'])
        self.assertLess(b[0]['visible_at'],b[1]['visible_at'])
        for row in rows:
            self.assertGreaterEqual(parse_time(row['due_at']),parse_time(b[row['sequence']-1]['visible_at']))
        self.assertEqual([r['attempt_no'] for r in rows],[1,2,3,1,2,3])

    def test_deterministic_and_seed_independent_of_source_generation(self):
        c=self.config(); source=list(events(c)); batch=source[-1]
        self.assertEqual(plan(batch,c,True),plan(batch,c,True))
        c['channels']['etsy_sim']['delivery_plan']['seed']+=1
        self.assertEqual(source,list(events(c)))

    def test_invalid_plan_settings(self):
        for key,value in [('repeat_count',1),('reorder',4),('delay_seconds',[-1,2]),
                          ('late_gap_seconds',[0,0]),('repeat_gap_seconds',[1]),('seed',True)]:
            c=self.config(); c['channels']['etsy_sim']['delivery_plan'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate(c)

    def test_reorder_requires_fault_profile(self):
        c=self.config(); c['profile']='normal'; c['channels']['etsy_sim']['notifications']={'omit':0,'duplicate':0}
        with self.assertRaisesRegex(ValueError,'faults'): validate(c)

    def test_infeasible_quota_fails_before_any_db_write(self):
        c=self.config(); e=c['channels']['etsy_sim']; e['required']={}; e['branches']={'pending':1}
        from unittest.mock import Mock
        db=Mock()
        with self.assertRaisesRegex(ValueError,'not enough'): prepare(db,c)
        db.sql.assert_not_called()

    def test_legacy_sql_does_not_require_new_columns(self):
        from test_support.s02_plan import prepare_sql
        c=self.config(); b=[b for b in events(c) if b[0]['source']=='etsy_sim'][1]
        old=prepare_sql(dict(id='abcdef123456',seed=17,events=b))
        self.assertNotIn('source_sequence',old)
        new='\n'.join(sql('abcdef123456',b,plan(b,c)))
        self.assertIn('source_sequence=',new)
        self.assertEqual(new.count('INSERT INTO s02.delivery_schedule'),6)

    def test_old_worker_refused_before_preparation(self):
        from tools.s02_data import __main__ as cli
        from unittest.mock import Mock
        db=Mock(); db.command.side_effect=RuntimeError('old image')
        with patch.object(sys,'argv',['s02','generate','--config',str(ROOT/'tools/s02_data/config/sim_delivery_demo.json')]), \
             patch.object(cli,'LocalDB',return_value=db),patch.object(cli,'prepare') as loader, \
             patch('tools.s02_data.live.require_live_storage'):
            with self.assertRaisesRegex(ValueError,'updated live-source'): cli.main()
        loader.assert_not_called()

    def test_new_plan_refuses_legacy_activation_before_mutation(self):
        from tools.s02_data import playback
        from unittest.mock import Mock
        db=Mock()
        with patch.object(playback,'query',return_value=[dict(campaign_id='abcdef123456',state='READY',config=self.config())]), \
             patch.object(playback,'run_overlay') as control:
            with self.assertRaisesRegex(ValueError,'live-source'):
                playback.activate(db,'demo','replay','2026-11-05T00:00:00Z',True)
        control.assert_not_called(); db.sql.assert_not_called()


if __name__=='__main__': unittest.main(verbosity=2)
