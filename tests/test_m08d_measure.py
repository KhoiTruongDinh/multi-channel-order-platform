"""Finite baseline oracle/limits/clock checks; no Docker runtime claims."""
import copy
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import m08d_measure as m
from tools.s02_data.config import validate
from tools.s02_data.campaign_config import validate_measurement


class MeasurementTests(unittest.TestCase):
    def config(self):
        value=json.loads((m.ROOT/'tools/s02_data/config/campaign_baseline.json').read_text())
        value.update(start_at='2026-11-06T00:00:00Z',end_at='2026-11-06T00:03:00Z')
        return validate(value)

    def data(self):
        config=self.config(); limits=config['campaign']['measurement']
        plan,all_expected=m.finite_plan(config,limits)
        identity,versions=next(iter(all_expected.items())); f=versions[-1]
        expected={identity:versions}
        header=dict(zip(('source_system','source_account_id','source_order_id'),identity),snapshot_id='s1',
            source_created_at=f['created'],source_updated_at=f['updated'],currency=f['currency'],
            payment_state=f['states'][0],fulfillment_state=f['states'][1],cancellation_state=f['states'][2],
            items_gross_amount=f['gross'],source_order_total_amount=f['total'],published_batch_id='b1')
        lines=[dict(zip(('source_system','source_account_id','source_order_id'),identity),source_line_id=i,
                    quantity=q,unit_gross_amount=p,line_gross_amount=p*q,canonical_variant_id=v,currency='USD',
                    mapping_status='CONFIRMED',snapshot_id='s1',published_batch_id='b1') for i,q,p,v in f['lines']]
        history=dict(header,batch_id='b1',batch_status='PUBLISHED')
        return dict(orders=[header],lines=lines,history=[history],history_lines=copy.deepcopy(lines),
                    evidence=[dict(snapshot_id='s1',n=1,wrong_scope=0,missing_manifest=0)]),expected

    def test_bounded_plan_seed_and_limits(self):
        config=self.config(); limits=config['campaign']['measurement']
        first=m.finite_plan(config,limits); self.assertEqual(first,m.finite_plan(config,limits))
        self.assertEqual(first[0]['orders'],12)
        for field in ('max_orders','max_source_versions','max_generated_bytes'):
            low=dict(limits,**{field:1})
            with self.subTest(field=field),self.assertRaises(ValueError): m.finite_plan(config,low)

    def test_invalid_safety_options_rejected(self):
        for value in ({'unknown':1},{'max_orders':True},{'max_docker_memory_percent':100},
                      {'max_db_growth_mb':0},{'max_pending_sends':-1}):
            with self.subTest(value=value),self.assertRaises(ValueError): validate_measurement(value)

    def test_memory_units_and_bad_samples(self):
        self.assertEqual(m.memory_bytes('1.5GiB'),1610612736)
        self.assertEqual(m.memory_bytes('2 MB'),2000000)
        for value in ('NaNMiB','-1MB','infinity B','1%'):
            with self.assertRaises(ValueError): m.memory_bytes(value)

    def test_reconcile_accepts_only_observed_history_not_all_planned(self):
        actual,expected=self.data()
        result=m.reconcile(actual,expected,0)
        self.assertEqual(result['status'],'PASS')
        self.assertGreater(result['planned_versions'],result['observed_versions'])

    def test_header_money_status_and_identity_mutations_fail(self):
        for field,value in (('payment_state','UNKNOWN'),('currency','EUR'),('source_order_total_amount',Decimal('0')),
                            ('source_order_id','foreign'),('snapshot_id','foreign')):
            actual,expected=self.data(); actual['orders'][0][field]=value
            with self.subTest(field=field): self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')

    def test_line_quantity_mapping_batch_and_missing_line_fail(self):
        for field,value in (('quantity',99),('canonical_variant_id','bad'),('published_batch_id','foreign'),
                            ('line_gross_amount',Decimal('0')),('mapping_status','UNMAPPED')):
            actual,expected=self.data(); actual['lines'][0][field]=value
            with self.subTest(field=field): self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')
        actual,expected=self.data(); actual['lines'].pop()
        self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')

    def test_evidence_scope_manifest_and_publish_state_fail(self):
        for field in ('wrong_scope','missing_manifest'):
            actual,expected=self.data(); actual['evidence'][0][field]=1
            self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')
        actual,expected=self.data(); actual['history'][0]['batch_status']='BUILDING'
        self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')

    def test_unplanned_and_duplicate_history_fail(self):
        actual,expected=self.data(); actual['history'].append(copy.deepcopy(actual['history'][0]))
        self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')
        actual,expected=self.data(); actual['history'][0]['source_updated_at']='2026-11-06T22:00:00Z'
        self.assertEqual(m.reconcile(actual,expected,0)['status'],'FAIL')

    def test_nonzero_admission_clock_shift(self):
        actual,expected=self.data()
        for row in actual['orders']+actual['history']:
            for field in ('source_created_at','source_updated_at'):
                row[field]=(m.at(row[field])+timedelta(seconds=123)).isoformat()
        self.assertEqual(m.reconcile(actual,expected,123)['status'],'PASS')

    def test_quantile_and_empty_censoring(self):
        self.assertIsNone(m.quantile([], .95))
        self.assertEqual(m.quantile(list(range(1,21)),.95),19)

    def test_resource_ceiling_retains_failed_sample(self):
        config=self.config(); report={}; monitor=m.Monitor(Mock(),config,config['campaign']['measurement'],report)
        monitor.hardware=dict(memory_bytes=1000); monitor.ids=['one']; monitor.db.command.return_value='fs 10000 1 9999 1% /'
        stats=json.dumps(dict(Name='one',MemUsage='1MiB / 2GiB',CPUPerc='0.1%'))
        sizes=[dict(datname=str(i),size_bytes=100) for i in range(4)]
        with patch.object(m,'command',return_value=stats),patch.object(m,'query',return_value=sizes):
            with self.assertRaises(m.SafetyCeiling): monitor.sample()
        self.assertEqual(report['measurement']['status'],'CEILING_REACHED')
        self.assertEqual(len(report['measurement']['samples']),1)

    def test_missing_final_observation_is_censored_not_a_false_pass(self):
        config=self.config(); report={}; monitor=m.Monitor(Mock(),config,config['campaign']['measurement'],report)
        actual,expected=self.data(); monitor.expected=expected; monitor.shift=0; monitor.since='2026-11-06T00:00:00Z'
        with patch.object(m,'warehouse',return_value=actual),patch.object(m,'query',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'baseline'): monitor.finish()
        self.assertEqual(monitor.value['reconciliation']['status'],'PASS')
        self.assertEqual(monitor.value['observed_delay']['censored'],1)
        self.assertEqual(monitor.value['status'],'BASELINE_FAIL')
        self.assertEqual(monitor.value['exact_commit_to_first_publication_latency'],'NOT_MEASURED')


if __name__=='__main__': unittest.main(verbosity=2)
