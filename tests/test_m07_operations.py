"""Offline review contract/precedence tests, not generated source acquisitions."""
import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reports.operations import review_reasons, summarize, order_rows, availability


class OperationsTests(unittest.TestCase):
    def order(self, **changes):
        row = dict(source_system='internal_web', source_account_id='WEB01', source_order_id='SAME',
                   payment_state='PAID', fulfillment_state='NOT_STARTED', cancellation_state='NOT_REQUESTED',
                   source_created_at=datetime(2026,10,17,tzinfo=timezone.utc),
                   source_order_total_amount=40, currency='USD')
        return dict(row,**changes)

    def test_canceled_suppresses_every_operational_rule(self):
        for payment in ('PAID','UNPAID','UNKNOWN',None):
            for fulfillment in ('NOT_STARTED','PARTIALLY_SHIPPED','UNKNOWN'):
                self.assertEqual(review_reasons(self.order(payment_state=payment,
                    fulfillment_state=fulfillment,cancellation_state='CANCELED')),[])

    def test_requested_suppresses_fulfillment_but_not_information_review(self):
        self.assertEqual(review_reasons(self.order(cancellation_state='REQUESTED')),['Cancellation requested'])
        reasons = review_reasons(self.order(cancellation_state='REQUESTED', payment_state='UNKNOWN'))
        self.assertEqual(reasons,['Cancellation requested','Payment status verification'])

    def test_fulfillment_requires_confirmed_payment_and_no_cancel_request(self):
        self.assertEqual(review_reasons(self.order()),['Fulfillment not started'])
        self.assertEqual(review_reasons(self.order(fulfillment_state='PARTIALLY_SHIPPED')),['Partial fulfillment'])
        self.assertEqual(review_reasons(self.order(payment_state='UNPAID')),['Payment pending'])

    def test_unknown_cancellation_is_not_standalone_task(self):
        self.assertEqual(review_reasons(self.order(fulfillment_state='SHIPPED',cancellation_state='UNKNOWN')),[])
        self.assertEqual(review_reasons(self.order(cancellation_state='UNKNOWN')),['Cancellation status verification'])
        self.assertEqual(review_reasons(self.order(fulfillment_state='DELIVERED',cancellation_state=None)),[])

    def test_missing_states_are_explicit_verification_not_ship_instruction(self):
        reasons = review_reasons(self.order(payment_state=None,fulfillment_state=None,cancellation_state=None))
        self.assertEqual(reasons,['Payment status verification','Fulfillment status verification'])

    def test_multiple_reasons_one_order_and_account_identity(self):
        first = self.order(payment_state='UNKNOWN',fulfillment_state='UNKNOWN')
        second = self.order(source_account_id='WEB02')
        result = summarize([first,second],[])
        self.assertEqual(len(result['reviews']),2)
        self.assertEqual(sum(r['Orders'] for r in result['reason_counts']),3)
        self.assertEqual(len(order_rows(result['reviews'],include_review=True)),2)

    def test_mapping_is_separate_from_operational_review(self):
        order = self.order(cancellation_state='CANCELED')
        line = dict(order,canonical_variant_id=None,mapping_status='UNMAPPED')
        result = summarize([order],[line])
        self.assertEqual(len(result['reviews']),0)
        self.assertEqual(len(result['data_issues']),1)
        self.assertEqual(result['fulfillment_counts'],[])

    def test_sort_uses_creation_then_composite_key_not_urgency(self):
        newer = self.order(source_created_at=datetime(2026,10,18,tzinfo=timezone.utc))
        older = self.order(source_account_id='WEB02')
        result = summarize([newer,older],[])
        self.assertEqual(result['reviews'],[older,newer])

    def test_availability_does_not_call_historical_failure_current_outage(self):
        at = datetime(2026,10,17,tzinfo=timezone.utc)
        snapshot = dict(publications=[dict(publication_name='website_orders',published_at=at)],
            health=[dict(source_system='internal_web',source_account_id='WEB01',publication_name='website_orders',
                         last_failed_at=at-timedelta(seconds=1),last_successful_acquisition_at=None)])
        self.assertEqual(availability(snapshot,{('internal_web','WEB01')})[0]['Data status'],'Published')
        changed = copy.deepcopy(snapshot)
        changed['health'][0]['last_failed_at'] = at+timedelta(seconds=1)
        self.assertEqual(availability(changed,{('internal_web','WEB01')})[0]['Data status'],'Newer processing failure')
        self.assertEqual(availability(changed,set()),[])
        changed['publications'] = []
        self.assertEqual(availability(changed,{('internal_web','WEB01')})[0]['Data status'],'Not published')


if __name__=='__main__':
    unittest.main(verbosity=2)
