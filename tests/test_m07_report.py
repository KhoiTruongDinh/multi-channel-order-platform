"""Real report-role bounded SQL and Streamlit interactions on retained S01."""
from dataclasses import replace
import copy
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reports import data
from reports.operations import order_key,review_reasons
from streamlit.testing.v1 import AppTest


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opts=data.options()
        cls.f=data.Filters(tuple(data.scope(r) for r in cls.opts['scopes']),'USD',date(2026,10,17),date(2026,10,17))
        cls.panel=data.business(cls.f)

    def test_golden_metrics_and_grain(self):
        p=self.panel
        self.assertEqual((p['summary']['orders'],p['summary']['order_amount'],p['lines']['lines'],p['lines']['units'],p['lines']['merchandise']),
            (3,Decimal(124),4,6,Decimal(124)))
        self.assertEqual(sum(r['versions'] for r in p['versions']),6)
        self.assertEqual({r['product']:r['units'] for r in p['products']},{'V001':4,'V002':2})
        self.assertEqual((p['summary']['reviews'],p['summary']['canceled'],p['summary']['data_issues']),(1,1,0))
        self.assertEqual(p['reasons'],[dict(reason='Partial fulfillment',orders=1)])
        self.assertEqual(sum(r['orders'] for r in p['fulfillment']),2)

    def test_product_scope_empty_and_currency(self):
        p=data.business(replace(self.f,product='V002'))
        self.assertEqual((p['summary']['orders'],p['lines']['units'],p['lines']['merchandise']),(3,2,44))
        p=data.business(replace(self.f,scopes=('etsy_sim / 7001',)))
        self.assertEqual((p['summary']['orders'],p['lines']['units']),(1,1))
        for f in (replace(self.f,scopes=()),replace(self.f,currency='EUR'),replace(self.f,order_id="' OR TRUE --")):
            p=data.business(f)
            self.assertEqual((p['summary']['orders'],p['lines']['merchandise'],p['rows']),(0,0,[]))

    def test_pagination_all_match_and_cursor_invalidation(self):
        a=data.business(self.f,size=1)
        b=data.business(self.f,a['next_cursor'],size=1)
        self.assertEqual(a['summary']['orders'],3)
        self.assertNotEqual(order_key(a['rows'][0]),order_key(b['rows'][0]))
        c=data.business(self.f,b['next_cursor'],size=1)
        self.assertIsNone(c['next_cursor'])
        self.assertEqual(len({order_key(r) for p in (a,b,c) for r in p['rows']}),3)
        changed=dict(a['next_cursor'],signature='old-publication')
        reset=data.business(self.f,changed,selected=order_key(a['rows'][0]),size=1)
        self.assertTrue(reset['reset'])
        self.assertIsNone(reset['detail'])
        self.assertEqual(reset['rows'],a['rows'])
        self.assertTrue(data.business(replace(self.f,group='review'),a['next_cursor'])['reset'])
        with self.assertRaises(ValueError):
            data.business(self.f,size=101)
        with self.assertRaises(ValueError):
            replace(self.f,end=self.f.start+timedelta(days=366))

    def test_detail_history_allocations_scope_and_exact_search(self):
        for o in self.panel['rows']:
            p=data.business(self.f,selected=order_key(o))
            d=p['detail']
            self.assertEqual(len(d['history']),{'internal_web':3,'ebay_sim':2,'etsy_sim':1}[o['source_system']])
            if o['source_system']=='ebay_sim':
                self.assertEqual((d['allocations'][0]['fulfillment_id'],d['allocations'][0]['allocated_quantity']),('FUL001',2))
            else:
                self.assertEqual(d['allocations'],[])
            self.assertTrue(all(len(d[k])<=100 and not d[k+'_truncated'] for k in ('lines','history','allocations')))
            self.assertEqual(data.business(replace(self.f,order_id=o['source_order_id']))['summary']['orders'],1)
            self.assertIsNone(data.business(replace(self.f,scopes=()),selected=order_key(o))['detail'])

    def test_sql_rule_oracle_parity(self):
        with data.connect() as c:
            for payment,fulfillment,cancellation in product(('PAID','UNPAID','UNKNOWN',None),
                    ('NOT_STARTED','PARTIALLY_SHIPPED','SHIPPED','DELIVERED','UNKNOWN',None),('NOT_REQUESTED','REQUESTED','CANCELED','UNKNOWN',None)):
                expected=review_reasons(dict(payment_state=payment,fulfillment_state=fulfillment,cancellation_state=cancellation))
                actual=c.execute('SELECT report.review_reasons(%s,%s,%s) AS reasons',(payment,fulfillment,cancellation)).fetchone()['reasons']
                self.assertEqual(actual,expected)

    def test_readonly_repeatable_read_boundaries(self):
        self.assertEqual((self.panel['metadata']['isolation'],self.panel['metadata']['read_only']),('repeatable read','on'))
        with data.connect() as c:
            for name in ('core.orders_current','raw.raw_records','ops.execution_measurements','ops.scheduler_observations'):
                schema,relation=name.split('.')
                self.assertFalse(c.execute("""SELECT has_table_privilege(current_user,t.oid,'SELECT') AS allowed
                    FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
                    WHERE n.nspname=%s AND t.relname=%s""",(schema,relation)).fetchone()['allowed'])
            self.assertFalse(c.execute("SELECT has_table_privilege(current_user,'report.operations_orders','UPDATE') AS allowed").fetchone()['allowed'])
        self.assertEqual({r['coverage_state'] for r in self.panel['health']},{'UNKNOWN'})

    def test_monitor_bounds_clock_and_stale_status(self):
        m=data.monitoring(self.f.scopes,168)
        for key in ('measurements','scheduler','backlog','runs','tests','exceptions'):
            self.assertLessEqual(len(m[key]),100)
            for r in m[key]:
                self.assertNotIn('error_message',r)
                self.assertNotIn('details',r)
        self.assertEqual(data.monitoring((),1)['aggregate'],[])
        row=dict(observed_at=m['now'],scheduler_heartbeat_at=m['now'],is_paused=True)
        self.assertEqual(data.scheduler_status(row,m['now']),'Paused')
        row['observed_at']-=timedelta(seconds=91)
        self.assertIn('stale',data.scheduler_status(row,m['now']))

    def test_ui_three_screens_filters_and_detail(self):
        app=AppTest.from_file('/app/reports/app.py',default_timeout=30).run()
        self.assertFalse(app.exception)
        values=lambda:{m.label:m.value for m in app.metric}
        self.assertEqual(values()['Published orders'],'3')
        app.text_input(key='product').set_value('V002').run()
        self.assertEqual(values()['Ordered units'],'2')
        self.assertEqual(values()['Published orders'],'3')
        app.sidebar.radio(key='workspace').set_value('Order Operations').run()
        self.assertFalse(app.exception)
        self.assertEqual(values()['Orders to review'],'1')
        etsy=next(o for o in self.panel['rows'] if o['source_system']=='etsy_sim')
        app.selectbox(key='inspect_page').set_value(order_key(etsy)).run()
        self.assertFalse(app.exception)
        self.assertEqual(values()['Cancellation'],'Not reported')
        app.text_input(key='exact').set_value('NO_SUCH_ORDER').run()
        self.assertFalse(app.exception)
        self.assertEqual(values()['Matching orders'],'0')
        app.sidebar.radio(key='workspace').set_value('Pipeline Monitoring').run()
        self.assertFalse(app.exception)
        app.sidebar.button(key='refresh').click().run()
        self.assertFalse(app.exception)

    def test_ui_sanitized_unavailable(self):
        with patch('reports.data.options',side_effect=RuntimeError('password=SECRET_SENTINEL')):
            app=AppTest.from_file('/app/reports/app.py',default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertNotIn('SECRET_SENTINEL',app.error[0].value)
        self.assertFalse(app.metric)

    def test_ui_bounded_next_previous_large_count(self):
        base=copy.deepcopy(self.panel)
        template=base['rows'][0]
        pages=[]
        for number in range(2):
            panel=copy.deepcopy(base)
            panel['rows']=[dict(template,source_order_id=f'PAGE_{number}_{i}') for i in range(50)]
            panel['summary']['orders']=1000000
            panel['next_cursor']=dict(signature=panel['signature'],after=('page2',)) if number==0 else None
            pages.append(panel)
        def read(f,cursor=None,selected=None,**kwargs):
            return pages[1 if cursor else 0]
        with patch('reports.data.business',side_effect=read):
            app=AppTest.from_file('/app/reports/app.py',default_timeout=30).run()
            app.sidebar.radio(key='workspace').set_value('Order Operations').run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.selectbox(key='inspect_page').options),51)  # placeholder +50, not million IDs
            app.button(key='next_page').click().run()
            self.assertFalse(app.exception)
            self.assertIn('PAGE_1_',app.selectbox(key='inspect_page').options[1])
            app.button(key='previous_page').click().run()
            self.assertFalse(app.exception)
            self.assertIn('PAGE_0_',app.selectbox(key='inspect_page').options[1])


if __name__=='__main__':
    unittest.main(verbosity=2)
