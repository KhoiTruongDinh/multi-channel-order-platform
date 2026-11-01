"""Offline source/HTTP/oracle checks. No Docker or platform writes."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch, Mock, call
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simulator import ebay_api, etsy_api
from simulator.s02_store import Store
from test_support.s02_inputs import inputs, purchase_facts, ROOT
from test_support.m08b import reconcile, business_signature, Campaign, DAGS
from test_support import m08a
from orchestration.scheduling import slot_wait_seconds
from orchestration import scheduling

AT=datetime(2026,10,30,12,tzinfo=timezone.utc)


class InputTests(unittest.TestCase):
    def test_test_only_drain_signal_stops_intervals_without_pausing_tasks(self):
        with patch.dict(os.environ,{'POLLING_DRAIN_MODE':'false','POLLING_DRAIN_FILE':'/opt/airflow/state/polling-drain'}):
            with patch.object(scheduling.Path,'is_file',return_value=False):
                self.assertEqual(scheduling.periodic_schedule(timedelta(seconds=180)),timedelta(seconds=180))
            with patch.object(scheduling.Path,'is_file',return_value=True):
                self.assertIsNone(scheduling.periodic_schedule(timedelta(seconds=180)))
        with patch.dict(os.environ,{'POLLING_DRAIN_FILE':'owner/path'}),self.assertRaises(ValueError):
            scheduling.periodic_schedule(timedelta(seconds=180))

    def test_late_terminal_failure_cannot_hide_behind_prior_successes(self):
        campaign=object.__new__(Campaign)
        campaign.result={}
        good=[dict(dag_id=d,state='success') for d in DAGS for _ in range(2)]
        campaign.scheduled=Mock(return_value=good)
        self.assertEqual(campaign.terminal_schedules(),good)
        for state in ('running','queued','failed'):
            campaign.scheduled=Mock(return_value=good+[dict(dag_id='website_polling',state=state)])
            with self.assertRaises(m08a.SafetyError): campaign.terminal_schedules()

    def test_b_test_mounts_cannot_expose_host_ledger_or_credentials(self):
        h=object.__new__(m08a.Harness)
        h.marker=dict(profile='m08b')
        h.dc=Mock()
        h.run('airflow','-c','pass',reads=True)
        args=h.dc.call_args.args[0]
        self.assertIn(str(m08a.ROOT/'tests')+':/repo/tests:ro',args)
        self.assertNotIn(str(m08a.ROOT)+':/repo:ro',args)
        self.assertFalse(any(str(m08a.ROOT/'runtime') in arg for arg in args))

    def test_bounded_slot_wait_preserves_default(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(slot_wait_seconds(),15)
        for text,expected in [('0',0),('300',300),('600',600)]:
            with patch.dict(os.environ,{'POLLING_SLOT_WAIT_SECONDS':text}):
                self.assertEqual(slot_wait_seconds(),expected)
        for text in ('-1','601','bad','NaN'):
            with patch.dict(os.environ,{'POLLING_SLOT_WAIT_SECONDS':text}),self.assertRaises(ValueError):
                slot_wait_seconds()

    def test_baseline_drains_inbox_and_recovery_separately(self):
        campaign=object.__new__(Campaign)
        campaign.cli=Mock()
        campaign.cli_wave()
        self.assertEqual(campaign.cli.call_args_list,[call('internal_web'),call('ebay_sim'),
            call('etsy_sim','drain'),call('etsy_sim')])

    def test_seed_reproducibility_and_bounds(self):
        a=inputs(17,1,AT,'123456abcdef')
        self.assertEqual(a,inputs(17,1,AT,'123456abcdef'))
        self.assertNotEqual(a,inputs(18,1,AT,'123456abcdef'))
        self.assertEqual(len(a),6)
        for seed,wave in [(-1,1),(2**31,1),(17,0),(17,3)]:
            with self.assertRaises(ValueError): inputs(seed,wave,AT,'123456abcdef')

    def test_purchase_identity_money_and_independent_states(self):
        first=inputs(17,1,AT,'123456abcdef')
        final=inputs(17,2,AT,'123456abcdef',AT+timedelta(minutes=2))
        for a,b in zip(first,final):
            a,b=purchase_facts(a),purchase_facts(b)
            self.assertEqual(a['lines'],b['lines'])
            self.assertEqual(a['created'],b['created'])
            self.assertNotEqual(a['updated'],b['updated'])
            self.assertEqual(a['total'],a['gross'])
            self.assertEqual(a['states'][0],b['states'][0])
        self.assertEqual(final[0]['order_id'],final[1]['order_id'])
        self.assertEqual(purchase_facts(final[0])['states'],('PAID','NOT_STARTED','CANCELED'))
        self.assertEqual(purchase_facts(final[1])['states'][1],'PARTIALLY_SHIPPED')
        self.assertEqual(purchase_facts(final[2])['states'],('PAID','SHIPPED','UNKNOWN'))
        self.assertFalse(final[-1]['notify'])

    def test_monotonic_atomic_store_and_no_shared_payload(self):
        for kind,position in [('ebay',1),('etsy',2)]:
            store=Store(kind)
            old=inputs(17,1,AT,'123456abcdef')[position]['payload']
            newer=inputs(17,2,AT,'123456abcdef',AT+timedelta(seconds=1))[position]['payload']
            store.upsert(old); store.upsert(old); store.upsert(newer)
            with self.assertRaises(ValueError): store.upsert(old)
            conflict=copy.deepcopy(newer)
            if kind=='ebay': conflict['order']['orderPaymentStatus']='UNKNOWN'
            else: conflict['is_paid']=False
            with self.assertRaises(ValueError): store.upsert(conflict)
            self.assertEqual(len(store.rows),1)
            newer.clear()
            self.assertTrue(next(iter(store.rows.values())))

    def test_oracle_rejects_wrong_scope_state_quantity_and_money(self):
        op=inputs(17,2,AT,'123456abcdef')[0]
        f=purchase_facts(op)
        order=dict(source_system=f['source'],source_account_id=f['account'],source_order_id=f['order_id'],
            payment_state=f['states'][0],fulfillment_state=f['states'][1],cancellation_state=f['states'][2],
            currency='USD',items_gross_amount=f['gross'],source_order_total_amount=f['total'],
            source_created_at=f['created'],source_updated_at=f['updated'],snapshot_id='snap',published_batch_id='batch')
        lines=[dict(source_system=f['source'],source_account_id=f['account'],source_order_id=f['order_id'],
            source_line_id=i,quantity=q,unit_gross_amount=p,line_gross_amount=q*p,canonical_variant_id=v,
            currency='USD',snapshot_id='snap',published_batch_id='batch') for i,q,p,v in f['lines']]
        actual=dict(orders=[order],lines=lines,history=[])
        self.assertTrue(reconcile(actual,[op]))
        for key,value in [('source_account_id','other'),('payment_state','UNPAID'),('items_gross_amount',1)]:
            bad=copy.deepcopy(actual); bad['orders'][0][key]=value
            self.assertFalse(reconcile(bad,[op]))
        bad=copy.deepcopy(actual); bad['lines'][0]['quantity']+=1
        self.assertFalse(reconcile(bad,[op]))
        bad=copy.deepcopy(actual); bad['orders'][0]['published_batch_id']='new'; bad['lines'][0]['published_batch_id']='new'
        self.assertEqual(business_signature(actual),business_signature(bad))

    def test_profile_and_ci_guards(self):
        marker=dict(format_version=1,id='123456abcdef',profile='m08b',project='m08a-123456abcdef',
            root=str(m08a.root_for('123456abcdef')),repository=str(m08a.ROOT))
        base=dict(services={name:dict(environment={},healthcheck={}) for name in m08a.SERVICES})
        model=m08a.make_model(base,marker)
        m08a.validate_model(model,marker)
        legacy=copy.deepcopy(model)
        legacy['services']['airflow']['environment']['POLLING_DRAIN_MODE']='true'
        with self.assertRaises(m08a.SafetyError): m08a.validate_model(legacy,marker|dict(profile='m08a'))
        model['services']['airflow']['environment']['S02_CONTROL_TOKEN']='leak'
        with self.assertRaises(m08a.SafetyError): m08a.validate_model(model,marker)
        with patch.object(m08a,'docker',return_value='owner-resource'),self.assertRaises(m08a.SafetyError):
            m08a.owner_absent()
        with patch.object(m08a,'docker',side_effect=['','','',m08a.OWNER+'-airflow-1']),self.assertRaises(m08a.SafetyError):
            m08a.owner_absent()


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SIMULATOR_MODE':'s02','S02_CONTROL_TOKEN':'test-control',
            'EBAY_SIM_TOKEN':'api-token','ETSY_SIM_TOKEN':'api-token'})
        self.env.start()
        self.servers=[]

    def tearDown(self):
        for server,thread in self.servers:
            server.shutdown(); server.server_close(); thread.join()
        self.env.stop()

    def start(self,handler):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.servers.append((server,thread))
        return f'http://127.0.0.1:{server.server_port}'

    def request(self,url,data=None,token='api-token',control=False):
        headers={'Authorization':'Bearer '+token}
        if control: headers['X-S02-Control-Token']=token
        with urlopen(Request(url,data=None if data is None else json.dumps(data).encode(),headers=headers),timeout=3) as r:
            return json.loads(r.read())

    def test_ebay_control_separation_paging_details_and_empty(self):
        state=ebay_api.State(ROOT/'ebay'); api,control=ebay_api.handlers(state)
        origin,admin=self.start(api),self.start(control)
        os.environ['EBAY_PUBLIC_ORIGIN']=origin
        self.addCleanup(os.environ.pop,'EBAY_PUBLIC_ORIGIN',None)
        payload=inputs(17,2,AT,'123456abcdef')[1]['payload']
        with self.assertRaises(HTTPError) as error: self.request(admin+'/s02/upsert',payload)
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError): self.request(origin+'/s02/upsert',payload,'test-control',True)
        for op in inputs(17,2,AT,'123456abcdef'):
            if op['source']=='ebay_sim': self.request(admin+'/s02/upsert',op['payload'],'test-control',True)
        from urllib.parse import urlencode
        query=urlencode(dict(filter='lastmodifieddate:[2026-10-30T11:00:00Z..2026-10-30T13:00:00Z]',limit=1,offset=0))
        page=self.request(origin+ebay_api.ROOT+'?'+query)
        self.assertEqual(page['total'],2); self.assertIn('next',page)
        second=self.request(page['next']); self.assertNotEqual(page['orders'][0]['orderId'],second['orders'][0]['orderId'])
        detail=self.request(origin+ebay_api.ROOT+'/'+payload['order']['orderId'])
        self.assertEqual(detail,payload['order'])
        self.assertEqual(len(self.request(detail['fulfillmentHrefs'][0].replace('http://ebay-sim',origin))['lineItems']),1)
        empty=query.replace('2026-10-30','2026-10-29')
        self.assertEqual(self.request(origin+ebay_api.ROOT+'?'+empty)['orders'],[])

    def test_etsy_ordered_pages_detail_and_s01_control_disabled(self):
        state=etsy_api.State(ROOT/'etsy'); api,control=etsy_api.handlers(state)
        origin,admin=self.start(api),self.start(control)
        for op in reversed(inputs(17,1,AT,'123456abcdef')):
            if op['source']=='etsy_sim': self.request(admin+'/s02/upsert',op['payload'],'test-control',True)
        path='/v3/application/shops/7001/receipts'
        query=f'?min_last_modified={int(AT.timestamp())}&max_last_modified={int(AT.timestamp())}&limit=1&offset=0&sort_on=updated&sort_order=asc'
        first=self.request(origin+path+query); second=self.request(origin+path+query.replace('offset=0','offset=1'))
        self.assertEqual(first['count'],2)
        self.assertLess(first['results'][0]['receipt_id'],second['results'][0]['receipt_id'])
        receipt=first['results'][0]
        self.assertEqual(self.request(origin+path+'/'+str(receipt['receipt_id'])),receipt)
        empty_query=query.replace(str(int(AT.timestamp())),str(int(AT.timestamp())+1))
        self.assertEqual(self.request(origin+path+empty_query),dict(count=0,results=[]))
        with patch.dict(os.environ,{'SIMULATOR_MODE':'s01'}):
            fixed=etsy_api.State(ROOT/'etsy')
        _,fixed_control=etsy_api.handlers(fixed)
        with self.assertRaises(HTTPError) as error:
            self.request(self.start(fixed_control)+'/s02/upsert',receipt,'test-control',True)
        self.assertEqual(error.exception.code,403)


if __name__=='__main__':
    unittest.main(verbosity=2)
