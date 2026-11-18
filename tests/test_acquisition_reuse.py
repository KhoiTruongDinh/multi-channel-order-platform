"""Focused acquisition control-flow tests. No warehouse or runtime parity claim."""
import copy
from datetime import datetime,timezone
import threading
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import Mock,patch

from ingestion import acquisition,etsy
from ingestion.ebay import Collector
from ingestion.ebay_reuse import ReuseCollector,EnrichmentChanged

def order():
    return dict(orderId='o1',sellerId='seller_sim_01',creationDate='2026-10-17T09:00:00Z',
        lastModifiedDate='2026-10-17T09:01:00Z',lineItems=[dict(lineItemId='l1',quantity=1,lineItemCost={'value':'1','currency':'USD'})],
        orderPaymentStatus='PAID',orderFulfillmentStatus='NOT_STARTED',pricingSummary={
            'priceSubtotal':{'value':'1','currency':'USD'},'total':{'value':'1','currency':'USD'}},
        fulfillmentHrefs=[],cancelStatus=dict(cancelState='NONE_REQUESTED',cancelRequests=[]))


def receipt(identity=1):
    return dict(receipt_id=identity,created_timestamp=10,updated_timestamp=20,is_paid=True,
        is_shipped=False,status='paid',transactions=[],shipments=[],subtotal={},discount_amt={},
        total_shipping_cost={},total_tax_cost={},grandtotal={})


def collector():
    conn=Mock()
    conn.execute.return_value.fetchone.return_value=('PENDING',)
    args=SimpleNamespace(origin='http://ebay-sim',page_size=1,detail_workers=2,
        window_start=datetime(2026,10,17,9,tzinfo=timezone.utc),
        window_end=datetime(2026,10,17,10,tzinfo=timezone.utc),
        observed_at=datetime(2026,10,17,11,tzinfo=timezone.utc),fail_after_page=False)
    c=ReuseCollector(conn,args,uuid.uuid4()); c.scan=1
    return c


class PolicyTests(unittest.TestCase):
    def test_policy_rejects_unbounded_or_implicit_concurrency(self):
        for mode,workers in (('legacy',2),('page-reuse',3),('page-reuse',True),('unknown',1)):
            with self.assertRaises(ValueError): acquisition.policy(mode,workers)
        self.assertEqual(acquisition.policy('page-reuse',2),('page-reuse',2))

    def test_two_workers_overlap_and_parent_joins(self):
        barrier=threading.Barrier(2); lock=threading.Lock(); active=0; maximum=0; done=[]
        def worker(next_job):
            nonlocal active,maximum
            while (job:=next_job()) is not None:
                with lock: active+=1; maximum=max(maximum,active)
                barrier.wait(timeout=3)
                with lock: done.append(job); active-=1
        acquisition.bounded_jobs(range(4),2,worker)
        self.assertEqual(maximum,2)
        self.assertCountEqual(done,range(4))

    def test_worker_failure_propagates_and_stops_allocation(self):
        seen=[]
        def worker(next_job):
            seen.append(next_job()); raise RuntimeError('injected worker failure')
        with self.assertRaisesRegex(RuntimeError,'worker failure'):
            acquisition.bounded_jobs(range(100),2,worker)
        self.assertLessEqual(len(seen),2)

    def test_options_cannot_change_on_retry(self):
        conn=Mock(); conn.execute.return_value.fetchone.return_value=({'mode':'page-reuse','workers':1,'page_size':50},)
        with self.assertRaisesRegex(ValueError,'options differ'):
            acquisition.pin_options(conn,uuid.uuid4(),'page-reuse',2,50)

    def test_business_invalid_money_not_silently_filtered(self):
        value=receipt(); value['grandtotal']={'amount':-100,'divisor':0,'currency_code':'USD'}
        self.assertTrue(acquisition.etsy_complete(value))  # dbt owns Money validation.
        del value['transactions']
        self.assertFalse(acquisition.etsy_complete(value))


class CyclePolicyTests(unittest.TestCase):
    def check_retry(self,stored,expected):
        from orchestration import polling,delta_workflow
        from unittest.mock import MagicMock
        stamp=datetime(2026,10,17,10,tzinfo=timezone.utc)
        args=SimpleNamespace(source='ebay_sim',execution_id='cycle',airflow_run_id='airflow-cycle',
            dag_id='ebay_polling',window_end=stamp,reuse_cycle_config=True,
            mapping_version='current',transformation_version='current',overlap_seconds=120,
            fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False)
        settings=dict(fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False,page_size=50)
        settings.update(stored)
        prior=(stamp,stamp,'ebay_polling','runtime','current','mapping','transform',120,settings,'airflow-cycle',False)
        manager=MagicMock(); conn=manager.__enter__.return_value
        conn.execute.return_value.fetchone.return_value=prior
        def configure(a,*values,**kwargs): a.delta_plan_sha256=None
        with patch.object(polling.workflow,'connect',return_value=manager), \
                patch.object(delta_workflow,'configure',side_effect=configure), \
                patch.dict(polling.os.environ,EBAY_ACQUISITION_MODE='page-reuse',EBAY_DETAIL_WORKERS='2'):
            polling.prepare(args)
        self.assertEqual((args.acquisition_mode,args.detail_workers),expected)
        self.assertEqual(args.page_size,50)

    def test_missing_old_settings_keep_legacy_even_when_environment_enables_reuse(self):
        self.check_retry({},('legacy',1))

    def test_existing_reuse_cycle_keeps_its_worker_count(self):
        self.check_retry({'acquisition_mode':'page-reuse','detail_workers':1},('page-reuse',1))


class EbayReuseTests(unittest.TestCase):
    def test_enrichment_conflict_records_restart_without_rewriting_validated_scan(self):
        c=collector(); c.conn.execute.return_value.fetchone.return_value=None
        with patch.object(c,'discover',return_value=[]), \
                patch('ingestion.ebay_reuse.bounded_jobs',side_effect=EnrichmentChanged('changed')):
            with self.assertRaises(EnrichmentChanged): c.acquire()
        statements=[call.args[0] for call in c.conn.execute.call_args_list]
        self.assertTrue(any('INSERT INTO ops.ebay_scan_restarts' in s for s in statements))
        self.assertFalse(any("SET status='INVALID'" in s for s in statements))

    def test_complete_page_skips_order_and_individual_fulfillment_gets(self):
        c=collector(); raw=uuid.uuid4(); value=order()
        with patch.object(c,'get',return_value=(uuid.uuid4(),dict(total=0,fulfillments=[]))) as get, \
                patch('ingestion.ebay_reuse.accept_element') as accept:
            c.enrich(uuid.uuid4(),'o1',value,raw,3)
        self.assertEqual(get.call_count,1)
        self.assertTrue(get.call_args.args[0].endswith('/o1/shipping_fulfillment'))
        self.assertEqual(get.call_args.args[2]['order_raw_id'],str(raw))
        self.assertEqual(get.call_args.args[2]['order_id'],'o1')
        accept.assert_called_once_with(c.conn,raw,'o1',3,c.run_id,1)

    def test_unknown_cancellation_uses_authoritative_detail(self):
        c=collector(); value=order(); value['cancelStatus']['cancelState']='IN_PROGRESS'
        full=copy.deepcopy(value); full['cancelStatus']['cancelRequests']=[{'cancelRequestId':'c1'}]
        with patch.object(c,'get',side_effect=[(uuid.uuid4(),full),(uuid.uuid4(),dict(total=0,fulfillments=[]))]) as get, \
                patch('ingestion.ebay_reuse.accept_element') as accept:
            c.enrich(uuid.uuid4(),'o1',value,uuid.uuid4(),0)
        self.assertEqual(get.call_count,2); accept.assert_not_called()
        self.assertEqual(value['cancelStatus']['cancelRequests'],[])

    def test_missing_list_field_is_filled_by_actual_detail_not_synthetic_order(self):
        c=collector(); value=order(); full=copy.deepcopy(value); del value['pricingSummary']
        raw=uuid.uuid4()
        with patch.object(c,'get',side_effect=[(raw,full),(uuid.uuid4(),dict(total=0,fulfillments=[]))]) as get, \
                patch('ingestion.ebay_reuse.accept_element') as accept:
            c.enrich(uuid.uuid4(),'o1',value,uuid.uuid4(),0)
        accept.assert_not_called()
        self.assertEqual(get.call_args.args[2]['order_raw_id'],str(raw))

    def test_cooldown_keeps_longest_shared_retry_after(self):
        c=collector(); stamp=datetime.now(timezone.utc).isoformat()
        c.conn.execute.return_value.fetchall.return_value=[({'retry-after':'40'},stamp),({'retry-after':'0'},stamp)]
        with patch('ingestion.ebay_reuse.time.sleep') as sleep:
            c.cooldown()
            self.assertGreater(sleep.call_args.args[0],38)

    def test_changed_detail_never_fabricates_a_combined_snapshot(self):
        c=collector(); value=order(); value['cancelStatus']['cancelState']='UNKNOWN'
        changed=copy.deepcopy(value); changed['orderPaymentStatus']='UNPAID'
        with patch.object(c,'get',return_value=(uuid.uuid4(),changed)), \
                patch('ingestion.ebay_reuse.accept_element') as accept:
            with self.assertRaisesRegex(ValueError,'version conflict'):
                c.enrich(uuid.uuid4(),'o1',value,uuid.uuid4(),0)
            accept.assert_not_called()

    def test_durable_attempt_budget_is_not_reset(self):
        c=collector(); c.conn.execute.return_value.fetchall.return_value=[(uuid.uuid4(),{},503,{})]*5
        with patch.object(Collector,'get') as request:
            with self.assertRaisesRegex(RuntimeError,'budget exhausted'):
                c.get('http://ebay-sim/detail','ebay_order')
            request.assert_not_called()

    def test_cached_page_is_scoped_to_scan(self):
        c=collector(); raw=uuid.uuid4()
        payload=dict(orders=[],total=0,limit=1,offset=0)
        c.conn.execute.return_value.fetchall.return_value=[(raw,payload,200,dict(request_phase='discovery',collection_scan=1))]
        with patch.object(Collector,'get',return_value=(raw,{})) as request,patch.object(c,'cooldown'):
            self.assertEqual(c.get('http://ebay-sim/page','ebay_orders'),(raw,payload))
            request.assert_not_called()
            c.scan=2; c.get('http://ebay-sim/page','ebay_orders')
            request.assert_called_once(); self.assertEqual(c.prior_attempts,1)

    def test_malformed_200_response_does_not_poison_retained_success_cache(self):
        c=collector()
        for bad in (None,[],{},dict(total=0,orders=[])):
            c.conn.execute.return_value.fetchall.return_value=[(uuid.uuid4(),bad,200,dict(request_phase='discovery',collection_scan=1))]
            with patch.object(Collector,'get',return_value=(uuid.uuid4(),{})) as request,patch.object(c,'cooldown'):
                c.get('http://ebay-sim/page','ebay_orders')
                request.assert_called_once(); self.assertEqual(c.prior_attempts,1)

    def test_discovery_finishes_all_pages_before_enrichment(self):
        c=collector(); values=[order(),order()]; values[1]['orderId']='o2'
        from ingestion.ebay import page_url
        urls=[page_url(c.args.origin,c.args.window_start,c.args.window_end,i,1) for i in range(2)]
        pages=[(uuid.uuid4(),dict(total=2,limit=1,offset=i,orders=[values[i]],href=urls[i],
                **({'next':urls[i+1]} if i==0 else {}))) for i in range(2)]
        with patch.object(c,'get',side_effect=pages) as get,patch.object(c,'enrich') as enrich:
            jobs=c.discover()
            self.assertEqual(get.call_count,2); self.assertEqual(len(jobs),2)
            enrich.assert_not_called()

    def test_duplicate_discovery_refuses_even_with_equal_total(self):
        c=collector(); c.page_size=2
        from ingestion.ebay import page_url
        p=dict(total=2,limit=2,offset=0,orders=[order(),order()],href=page_url(c.args.origin,c.args.window_start,c.args.window_end,0,2))
        with patch.object(c,'get',return_value=(uuid.uuid4(),p)):
            with self.assertRaisesRegex(ValueError,'duplicate discovery'):
                c.discover()

    def test_grouped_lookup_validates_membership_without_position_assumption(self):
        c=collector(); b=order(); b['orderId']='o2'
        with patch.object(c,'get',return_value=(uuid.uuid4(),{'orders':[b,order()]})) as get:
            c.lookup_ids(['o1','o2'])
            self.assertIn('orderIds=',get.call_args.args[0])
            self.assertNotIn('filter=',get.call_args.args[0])
        with self.assertRaises(ValueError): c.lookup_ids(['o1']*2)


class EtsyReuseTests(unittest.TestCase):
    def test_detail_workers_have_distinct_connections_and_parent_waits(self):
        parent=Mock(); parent.execute.return_value.fetchone.return_value=(0,)
        contexts=[]; owned=[]; completed=[]; queue=iter([1,2]); lock=threading.Lock(); barrier=threading.Barrier(2)
        def connect():
            context=Mock(); connection=Mock(); context.__enter__=Mock(return_value=connection)
            context.__exit__=Mock(return_value=False); contexts.append(context); return context
        def claim(connection,only,collection_run):
            with lock:
                identity=next(queue,None); owned.append(connection)
            return (identity,) if identity else None
        def process(connection,lease,observed):
            barrier.wait(timeout=3)
            with lock: completed.append(lease[0])
            return True
        with patch.object(etsy,'expire_exhausted'),patch.object(etsy,'connect',side_effect=connect), \
                patch.object(etsy,'claim',side_effect=claim),patch.object(etsy,'process',side_effect=process):
            etsy.drain(parent,only=[1,2],collection_run='run',workers=2)
        self.assertCountEqual(completed,[1,2]); self.assertEqual(len(contexts),2)
        self.assertIsNot(owned[0],owned[1]); self.assertNotIn(parent,owned)

    def test_newer_shorter_cooldown_does_not_cancel_earlier_long_cooldown(self):
        conn=Mock(); stamp=datetime.now(timezone.utc)
        conn.execute.return_value.fetchall.return_value=[({'retry-after':'60'},stamp),({'retry-after':'0'},stamp)]
        with self.assertRaisesRegex(RuntimeError,'cooldown'):
            etsy.require_source_ready(conn)

    def test_complete_recovery_accepts_page_elements_without_detail_work(self):
        conn=Mock(); conn.execute.return_value.fetchall.return_value=[]
        run,raw=uuid.uuid4(),uuid.uuid4()
        args=SimpleNamespace(page_size=50,acquisition_mode='page-reuse',detail_workers=2,
            execution_id='reuse',observed_at=None,checkpoint_stream='receipts',window_end=datetime.now(timezone.utc))
        with patch.object(etsy,'begin_scan',return_value=(1,'RUNNING')), \
                patch.object(etsy,'recovery_pages',return_value=[(1,raw,0,receipt(1)),(2,raw,1,receipt(2))]), \
                patch.object(etsy,'finish_scan'),patch.object(etsy,'require_recovery_allowed'), \
                patch.object(etsy,'accept_element') as accept,patch.object(etsy,'enqueue') as enqueue, \
                patch.object(etsy,'drain') as drain:
            etsy.recover(conn,args,run)
        self.assertEqual(accept.call_count,2); enqueue.assert_not_called(); drain.assert_not_called()
        self.assertEqual([call.args[3] for call in accept.call_args_list],[0,1])

    def test_missing_fields_fall_back_without_marking_page_element_eligible(self):
        conn=Mock(); conn.execute.return_value.fetchall.return_value=[]
        args=SimpleNamespace(page_size=50,acquisition_mode='page-reuse',detail_workers=2,
            execution_id='reuse',observed_at=None,checkpoint_stream='receipts',window_end=datetime.now(timezone.utc))
        with patch.object(etsy,'begin_scan',return_value=(1,'VALIDATED')), \
                patch.object(etsy,'recovery_pages',return_value=[(1,uuid.uuid4(),0,{'receipt_id':1})]), \
                patch.object(etsy,'require_recovery_allowed'),patch.object(etsy,'accept_element') as accept, \
                patch.object(etsy,'enqueue',return_value='work'),patch.object(etsy,'drain') as drain:
            etsy.recover(conn,args,uuid.uuid4())
        accept.assert_not_called(); self.assertEqual(drain.call_args.kwargs['workers'],2)


if __name__=='__main__': unittest.main()
