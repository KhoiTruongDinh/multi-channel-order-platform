"""Offline prepared source tests. SQL/HTTP integration has a separate guarded runner."""
import copy
import io
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,Mock,MagicMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support.s02_plan import plan,latest,checksum,prepare_sql
from simulator.s02_temporal import split_document,assemble,make_store,PostgresStore
from simulator.s02_store import control
from test_support.s02_oracle import facts
from test_support import m08a
from test_support.m08b_temporal import TemporalCampaign

AT=datetime(2026,10,31,12,tzinfo=timezone.utc)


class TemporalTests(unittest.TestCase):
    def test_bound_prepared_workload_owns_seed_and_cardinality_not_cli_defaults(self):
        campaign=object.__new__(TemporalCampaign)
        campaign.h=Mock(); campaign.h.root=MagicMock()
        campaign.value=None; campaign.seed=17; campaign.count=4; campaign.profile='baseline'
        campaign.result={'status':'RUNNING'}; campaign.ledger=Mock()
        prepared=plan(99,'123456abcdef',AT-timedelta(days=2),2,30)
        with patch('test_support.m08b_temporal.load_prepared',return_value=prepared), \
             patch('test_support.m08b_temporal.install',side_effect=RuntimeError('stop before DB')):
            with self.assertRaisesRegex(RuntimeError,'stop before DB'): campaign.run()
        self.assertEqual((campaign.seed,campaign.count),(99,2))
        self.assertEqual((campaign.result['seed'],campaign.result['orders_per_channel']),(99,2))

    def test_website_source_sequence_does_not_collide_with_ledger_sequence(self):
        campaign=object.__new__(TemporalCampaign)
        campaign.h=Mock()
        campaign.h.marker={'id':'123456abcdef'}
        campaign.value=plan(17,'123456abcdef',AT-timedelta(days=2))
        campaign.applied={}; campaign.sequence=0; campaign.ledger=io.StringIO()
        with patch('test_support.m08b_temporal.rows',return_value=[]): campaign.tick()
        self.assertEqual(len(campaign.applied),4)
        self.assertIn('source_sequence',campaign.ledger.getvalue())

    def test_replay_rereads_sources_and_preserves_existing_message_identity(self):
        campaign=object.__new__(TemporalCampaign)
        campaign.h=Mock(); campaign.h.marker={'id':'123456abcdef'}
        campaign.value=plan(17,'123456abcdef',AT); campaign.result={}
        campaign.deliver=Mock(); campaign.cli_wave=Mock()
        with patch('test_support.m08b_temporal.rows',side_effect=[
            [dict(webhook_id='existing-message',event_type='order.paid')],
            [dict(logical=3,accepted=3)],[dict(logical=3,accepted=5)]]):
            campaign.reobserve()
        self.assertEqual(campaign.h.run.call_count,3)
        self.assertEqual(campaign.deliver.call_count,2)
        for invocation in campaign.deliver.call_args_list:
            self.assertEqual(invocation.kwargs,dict(message_id='existing-message'))
            self.assertEqual(invocation.args[1],1)
        campaign.cli_wave.assert_called_once()

    def test_delivery_progress_records_actual_http_ack_status(self):
        campaign=object.__new__(TemporalCampaign)
        campaign.h=Mock(); campaign.h.marker={'id':'123456abcdef'}
        campaign.value=plan(17,'123456abcdef',AT-timedelta(days=2))
        campaign.applied={}; campaign.sequence=0; campaign.ledger=io.StringIO()
        campaign.deliver=Mock(return_value=202)
        e=next(e for e in campaign.value['events'] if e['source']=='etsy_sim' and e['notify'])
        message=dict(receipt_id=e['order_id'],message_id=f"s02-123456abcdef-{e['order_id']}-{e['sequence']}")
        with patch('test_support.m08b_temporal.rows',return_value=[message]): campaign.tick()
        self.assertTrue(any('last_status=202' in c.args[0] for c in campaign.h.sql.call_args_list))

    def test_roundtrip_and_source_identity_purchase_stability(self):
        data=plan(17,'123456abcdef',AT)
        self.assertEqual(data,plan(17,'123456abcdef',AT))
        self.assertNotEqual(checksum(data),checksum(plan(18,'123456abcdef',AT)))
        previous={}
        for e in data['events']:
            key=e['source'],e['order_id']
            if key in previous:
                self.assertGreater(e['visible_at'],previous[key]['visible_at'])
                self.assertEqual(e['sequence'],previous[key]['sequence']+1)
            previous[key]=e
            if e['source']=='internal_web': continue
            before=copy.deepcopy(e['payload'])
            base,header,collections=split_document(e['source'],e['payload'])
            self.assertEqual(assemble(e['source'],base,header,collections),before)
            self.assertEqual(e['payload'],before)
        self.assertEqual(len(previous),12)
        # One source's changes never advance another order's own source timestamp.
        counts={k:sum((e['source'],e['order_id'])==k for e in data['events']) for k in previous}
        self.assertIn(1,counts.values()); self.assertIn(3,counts.values())

    def test_boundaries_and_no_future_current_state(self):
        data=plan(17,'123456abcdef',AT,duration_seconds=30)
        self.assertEqual(latest(data,AT-timedelta(seconds=1)),[])
        at=latest(data,AT)
        self.assertEqual(len(at),3)
        final=latest(data,AT+timedelta(days=1))
        self.assertEqual(len(final),12)
        created_dates={facts(e,data['references']['mapping'])['created'] for e in final}
        self.assertGreater(len(created_dates),1)
        for e in final:
            if e['source']=='internal_web':
                p=e['payload']
                self.assertEqual(p['orders'][0]['payment_status'],'PAID')
                self.assertEqual(len(p['shipments']),0)
            if e['source']=='ebay_sim' and e['sequence']>1:
                p=e['payload']; ordered={l['lineItemId']:l['quantity'] for l in p['order']['lineItems']}
                shipped={k:0 for k in ordered}
                for f in p['fulfillments']:
                    self.assertLessEqual(f['shippedDate'],e['visible_at'])
                    for l in f['lineItems']: shipped[l['lineItemId']]+=l['quantity']
                self.assertEqual(shipped,ordered)
            if e['source']=='etsy_sim' and e['sequence']>1:
                self.assertTrue(e['payload']['is_shipped'])

    def test_each_source_has_a_late_progressing_sentinel_without_global_waves(self):
        data=plan(17,'123456abcdef',AT,duration_seconds=1200)
        for source in ('internal_web','ebay_sim','etsy_sim'):
            changes=[e for e in data['events'] if e['source']==source and e['sequence']>1]
            self.assertTrue(any(datetime.fromisoformat(e['visible_at'].replace('Z','+00:00'))>=AT+timedelta(seconds=1000) for e in changes))
        self.assertTrue(all(datetime.fromisoformat(e['visible_at'].replace('Z','+00:00'))<=AT+timedelta(seconds=1200) for e in data['events']))

    def test_preparation_sql_is_atomic_and_content_addressed(self):
        data=plan(17,'123456abcdef',AT)
        sql=prepare_sql(data)
        self.assertTrue(sql.startswith('BEGIN;'))
        self.assertTrue(sql.endswith('COMMIT;'))
        self.assertIn(checksum(data),sql)
        self.assertEqual(sql.count('INSERT INTO s02.orders '),8)
        self.assertIn('SET sealed=TRUE',sql)
        self.assertNotIn('DELETE ',sql)

    def test_oracle_full_shipping_and_mapping_are_independent(self):
        data=plan(17,'123456abcdef',AT)
        states=set()
        for e in data['events']:
            result=facts(e,data['references']['mapping'])
            self.assertTrue(all(l[3].startswith('S02-V') for l in result['lines']))
            if e['source']=='ebay_sim': states.add(result['states'][1])
        self.assertEqual(states,{'NOT_STARTED','PARTIALLY_SHIPPED','SHIPPED'})
        with self.assertRaises(ValueError): facts(data['events'][0],[])
        broken=copy.deepcopy(data)
        event=next(e for e in broken['events'] if e['source']=='ebay_sim' and e['sequence']>1)
        event['payload']['order']['pricingSummary']['total']['value']='999.00'
        with self.assertRaises(ValueError): prepare_sql(broken)

    def test_guards_and_no_credentials_in_pipeline(self):
        marker=dict(format_version=1,id='123456abcdef',project='m08a-123456abcdef',
            root=str(m08a.root_for('123456abcdef')),repository=str(m08a.ROOT),profile='m08b',
            backend='s02-pg',interval_seconds=180,slot_wait_seconds=300,drain_signal=True)
        base=dict(services={n:dict(environment={},healthcheck={}) for n in m08a.SERVICES})
        model=m08a.make_model(base,marker)
        m08a.validate_model(model,marker)
        model['services']['airflow']['environment']['S02_DB_PASSWORD']='leak'
        with self.assertRaises(m08a.SafetyError): m08a.validate_model(model,marker)
        handler=Mock(); handler.path='/s02/upsert'
        state=Mock(); state.s02=object.__new__(PostgresStore)
        self.assertTrue(control(handler,state))
        handler.send_json.assert_called_once_with(403,{'error':'S02 control disabled/unauthorized'})
        with patch.dict('os.environ',{'SIMULATOR_MODE':'bad'}):
            with self.assertRaises(ValueError): make_store('ebay')
        for kwargs in (dict(duration_seconds=0),dict(orders_per_channel=10001)):
            with self.assertRaises(ValueError): plan(17,'123456abcdef',AT,**kwargs)


if __name__=='__main__': unittest.main(verbosity=2)
