"""Finite rate gates/real SQL observation clocks; no Docker or runtime claims."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import m08d_envelope as e
from test_support import m08d_measure as m
from tools.s02_data.campaign_config import validate_campaign
from tools.s02_data.config import validate


class EnvelopeTests(unittest.TestCase):
    def config(self,kind='website'):
        raw=json.loads((m.ROOT/f'tools/s02_data/config/campaign_rate_{kind}.json').read_text())
        raw.update(start_at='2026-11-07T00:00:00Z',end_at='2026-11-07T00:06:00Z')
        return validate(raw)

    def envelope(self,kind='website'):
        result=e.Envelope(self.config(kind),{})
        result.admitted('2026-11-07T00:00:00Z',0)
        return result

    def runs(self,dag='website_polling',end='2026-11-07T00:05:00Z',state='success'):
        return [dict(dag_id=dag,run_id='scheduled-'+str(i),state=state,
                     start_date='2026-11-07T00:01:00Z',end_date=end) for i in range(2)]

    def observe(self,envelope,clock,runs=None,complete=True):
        current=dict(observed_at=clock,eligible_not_current=0 if complete else 1)
        with patch.object(e,'query',return_value=self.runs() if runs is None else runs) as q:
            envelope.observe(Mock(),dict(reached_final_versions=complete),current)
        return q

    def test_load_settings_require_measurement_and_strict_known_fields(self):
        for setting in ({'load':{}},{'measurement':{},'load':{'bad':1}},
                        {'measurement':{},'load':{'min_scheduled_successes':True}},
                        {'measurement':{},'load':{'max_drain_seconds':0}}):
            with self.subTest(setting=setting),self.assertRaises(ValueError): validate_campaign(setting)
        config=self.config(); config['campaign']['fault']=dict(kind='ebay_pause')
        with self.assertRaises(ValueError): validate_campaign(config['campaign'])

    def test_short_intervals_and_impossible_deadline_refuse_before_runtime(self):
        for bad in ('duration','timeout','profile'):
            config=self.config()
            if bad=='duration': config['channels']['internal_web']['end_at']='2026-11-07T00:05:00Z'
            if bad=='timeout': config['campaign']['timeout_seconds']=100
            if bad=='profile': config['profile']='faults'
            with self.subTest(bad=bad),self.assertRaises(ValueError): e.Envelope(config,{})

    def test_minute_buckets_keep_offered_orders_distinct_from_updates(self):
        config=self.config('mixed'); limits=config['campaign']['measurement']
        plan,_=m.finite_plan(config,limits)
        self.assertEqual(sum(b['orders'] for b in plan['minute_buckets']),72)
        self.assertEqual(sum(b['versions'] for b in plan['minute_buckets']),plan['versions'])
        self.assertEqual(plan['offered_orders_per_second'],.2)
        self.assertEqual(plan,m.finite_plan(config,limits)[0])

    def test_larger_profiles_bound_counts_without_relaxing_resource_budgets(self):
        baseline=self.config()['campaign']['measurement']
        for count in (144,300,600,900):
            raw=json.loads((m.ROOT/f'tools/s02_data/config/campaign_rate_{count}.json').read_text())
            raw['start_at']='2026-11-07T00:00:00Z'
            config=validate(raw); limits=config['campaign']['measurement']
            plan,_=m.finite_plan(config,limits); e.Envelope(config,{})
            self.assertEqual(plan['orders'],count)
            self.assertLessEqual(plan['versions'],limits['max_source_versions'])
            self.assertLessEqual(plan['generated_bytes'],limits['max_generated_bytes'])
            for field in ('min_free_disk_mb','max_db_growth_mb','max_docker_memory_percent',
                          'max_container_memory_mb','max_final_observed_delay_seconds'):
                self.assertEqual(limits[field],baseline[field])
            self.assertIsNone(config['campaign']['fault'])

    def test_early_completion_does_not_skip_configured_window(self):
        env=self.envelope(); self.observe(env,'2026-11-07T00:05:30Z')
        self.assertFalse(env.ready()); self.assertIsNone(env.value['first_observed_drain_at'])
        self.observe(env,'2026-11-07T00:06:10Z')
        self.assertTrue(env.ready()); self.assertEqual(env.value['observed_drain_seconds'],10)

    def test_missing_or_running_scheduled_cycles_never_pass(self):
        for runs in ([],self.runs(state='running'),self.runs()[:1]):
            env=self.envelope(); self.observe(env,'2026-11-07T00:06:10Z',runs)
            self.assertFalse(env.ready())
            with self.assertRaisesRegex(RuntimeError,'budget'):
                self.observe(env,'2026-11-07T00:21:01Z',runs)
            self.assertEqual(env.value['status'],'FAIL')

    def test_query_scopes_scheduled_runs_to_fixed_admission_window(self):
        env=self.envelope(); q=self.observe(env,'2026-11-07T00:06:10Z')
        sql=q.call_args.args[1]
        self.assertIn("run_type='scheduled'",sql)
        self.assertIn('start_date>=',sql); self.assertIn('start_date<=',sql)
        self.assertEqual(q.call_args.args[2],'airflow_meta')

    def test_late_success_and_late_source_drain_are_failures(self):
        for runs,complete in ((self.runs(end='2026-11-07T00:21:01Z'),True),(self.runs(),True)):
            env=self.envelope()
            with self.assertRaises(RuntimeError): self.observe(env,'2026-11-07T00:21:01Z',runs,complete)

    def test_mixed_requires_both_etsy_dags_not_just_any_source_success(self):
        env=self.envelope('mixed')
        runs=sum((self.runs(d) for d in ('website_polling','ebay_polling','etsy_inbox')),[])
        self.observe(env,'2026-11-07T00:06:10Z',runs)
        self.assertFalse(env.ready())
        self.observe(env,'2026-11-07T00:06:20Z',runs+self.runs('etsy_recovery'))
        self.assertTrue(env.ready())

    def test_nonzero_source_shift_moves_window_not_admission_clock(self):
        env=e.Envelope(self.config(),{}); env.admitted('2026-11-07T01:00:00Z',3600)
        self.assertEqual(env.end.isoformat(),'2026-11-07T01:06:00+00:00')
        self.assertEqual(env.since,'2026-11-07T01:00:00Z')

    def test_progress_reports_missing_due_and_future_versions_without_fabrication(self):
        config=self.config(); _,expected=m.finite_plan(config,config['campaign']['measurement'])
        identity,versions=next(iter(expected.items())); expected={identity:versions}
        clock=e.at(versions[-1]['updated'])+timedelta(seconds=10)
        row=dict(zip(('source_system','source_account_id','source_order_id'),identity),
                 source_updated_at=None,observed_at=clock.isoformat())
        p=e.progress(expected,[row],0); c=p['by_source']['internal_web']
        self.assertEqual(c['eligible_not_current'],1); self.assertEqual(c['oldest_pending_seconds'],10)
        row['source_updated_at']=versions[-1]['updated']
        self.assertEqual(e.progress(expected,[row],0)['matching_final'],1)
        row.update(observed_at=(clock-timedelta(seconds=20)).isoformat(),source_updated_at=None)
        self.assertEqual(e.progress(expected,[row],0)['eligible_not_current'],0)


if __name__=='__main__': unittest.main(verbosity=2)
