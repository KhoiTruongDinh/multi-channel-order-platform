"""Offline acceptance-workload checks; these do not replace real scheduler evidence."""
from pathlib import Path
from datetime import datetime,timedelta
import sys
import unittest
from unittest.mock import patch,Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support.m08b_local_scheduled import workload,LocalScheduledCampaign
from tools.s02_data.config import parse_time
from tools.s02_data.generate import events
from tools.s02_data.load import validate_order


class ScheduledWorkloadTests(unittest.TestCase):
    def test_deterministic_six_order_source_valid_workload(self):
        config=workload()
        batches=list(events(config))
        self.assertEqual(batches,list(events(workload())))
        self.assertEqual(len(batches),6)
        for batch in batches:
            validate_order(batch,config)
        self.assertEqual({source:sum(b[0]['source']==source for b in batches)
                          for source in config['channels']},
                         {'internal_web':2,'ebay_sim':2,'etsy_sim':2})

    def test_each_source_has_pending_and_causal_change(self):
        batches=list(events(workload()))
        for source,branch in [('internal_web','cancel'),('ebay_sim','ship'),('etsy_sim','ship')]:
            selected=[b for b in batches if b[0]['source']==source]
            self.assertEqual({b[0]['case'] for b in selected},{'pending',branch})
            self.assertEqual(len(next(b for b in selected if b[0]['case']=='pending')),1)
            changed=next(b for b in selected if b[0]['case']==branch)
            self.assertGreater(len(changed),1)
            for first,second in zip(changed,changed[1:]):
                delay=(parse_time(second['visible_at'])-parse_time(first['visible_at'])).total_seconds()
                self.assertTrue(540<=delay<=660,delay)

    def test_omitted_etsy_order_is_distinct_from_notified_progressing_order(self):
        etsy=[b for b in events(workload()) if b[0]['source']=='etsy_sim']
        omitted=[b for b in etsy if not b[0]['notify']]
        notified=[b for b in etsy if b[0]['notify']]
        self.assertEqual(len(omitted),1)
        self.assertEqual(omitted[0][0]['case'],'pending')
        self.assertEqual(len(notified),1)
        self.assertEqual(notified[0][0]['case'],'ship')
        self.assertTrue(all(e['notify'] and not e['duplicate'] for e in notified[0]))

    def test_profile_finishes_within_real_replay_budget(self):
        config=workload()
        start=parse_time(config['start_at']); end=parse_time(config['end_at'])
        batches=list(events(config))
        for batch in batches:
            self.assertLess((parse_time(batch[0]['visible_at'])-start).total_seconds(),120)
            self.assertLess(parse_time(batch[-1]['visible_at']),end)
        self.assertLessEqual(max((parse_time(b[-1]['visible_at'])-start).total_seconds()
                                 for b in batches),1216)

    def test_realtime_default_range_counts_coverage_and_bounded_changes(self):
        # Includes local midnight crossing and end-of-minute sampling boundaries.
        for text in ('2026-10-31T00:00:00Z','2026-10-31T00:00:59Z',
                     '2026-10-31T16:59:00Z','2026-10-31T16:59:59Z',
                     '2026-10-31T13:12:17Z','2026-12-31T16:58:59Z'):
            at=parse_time(text)
            with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
                clock.now.return_value=at
                config=workload(mode='realtime')
                clock.now.assert_called_once()
            self.assertEqual(parse_time(config['start_at']),at)
            self.assertEqual(parse_time(config['end_at'])-at,timedelta(hours=5))
            batches=list(events(config))
            self.assertEqual(len(batches),18)
            for source,c in config['channels'].items():
                selected=[b for b in batches if b[0]['source']==source]
                self.assertEqual(len(selected),6)
                for branch,n in c['required'].items():
                    self.assertGreaterEqual(sum(b[0]['case']==branch for b in selected),n)
            for batch in batches:
                validate_order(batch,config)
                self.assertLess((parse_time(batch[0]['visible_at'])-at).total_seconds(),120)
                self.assertLess((parse_time(batch[-1]['visible_at'])-at).total_seconds(),1440)

    def test_unknown_clock_mode_is_refused(self):
        with self.assertRaisesRegex(ValueError,'unsupported local acceptance clock'):
            workload(mode='fast-forward')

    def test_source_warmup_materializes_data_without_enabling_pipeline(self):
        config=workload(); batch=[e for b in events(config) for e in b]
        campaign=object.__new__(LocalScheduledCampaign)
        campaign.value={'events':batch}; campaign.h=Mock(marker={'id':'abcdef123456'})
        campaign.db=Mock(); campaign.result={}; campaign.advance_sources=Mock(); campaign.dag=Mock()
        campaign.wait=lambda probe,label:self.assertTrue(probe())
        at=max(parse_time(e['visible_at']) for e in batch if e['sequence']==1)+timedelta(seconds=1)
        with patch('test_support.m08b_local_scheduled.query',side_effect=[
            [dict(logical_now=at.isoformat())],[dict(n=2)],[dict(n=0)]
        ]): campaign.warm_sources(config)
        campaign.advance_sources.assert_called_once()
        campaign.dag.assert_not_called()
        self.assertIn('initial_sources_ready_at',campaign.result)

    def test_slow_source_warmup_fails_before_pipeline_enable(self):
        config=workload(); batch=[e for b in events(config) for e in b]
        campaign=object.__new__(LocalScheduledCampaign)
        campaign.value={'events':batch}; campaign.h=Mock(marker={'id':'abcdef123456'})
        campaign.db=Mock(); campaign.result={}; campaign.advance_sources=Mock(); campaign.dag=Mock()
        campaign.wait=lambda probe,label:probe()
        at=min(parse_time(e['visible_at']) for e in batch if e['sequence']>1)
        with patch('test_support.m08b_local_scheduled.query',return_value=[dict(logical_now=at.isoformat())]):
            with self.assertRaisesRegex(AssertionError,'source warmup exceeded'):
                campaign.warm_sources(config)
        campaign.dag.assert_not_called()


if __name__=='__main__': unittest.main(verbosity=2)
