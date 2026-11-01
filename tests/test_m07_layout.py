"""Offline presentation checks using explicit UI data, not warehouse evidence."""
import copy
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'reports' / 'app.py')


class LayoutTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.options = dict(scopes=[dict(source_system='internal_web', source_account_id='WEB01')],
                            currencies=['USD'], dates=dict(first=date(2026, 11, 1), last=date(2026, 11, 1)))
        self.panel = dict(metadata=dict(read_at=now), reset=False, signature='layout-only',
            summary=dict(orders=12, reviews=4, canceled=2, data_issues=0, order_amount=Decimal('123456789.12')),
            lines=dict(units=24, merchandise=Decimal('123456780.12')),
            channels=[dict(source_system='internal_web', orders=12, units=24, reviews=4)],
            series=[dict(day=date(2026, 11, 1), source_system='internal_web', orders=12)],
            products=[dict(product='V001', units=24)],
            versions=[dict(source_system='internal_web', versions=18)],
            reasons=[], fulfillment=[], rows=[], detail=None, next_cursor=None,
            publications=[], health=[])

    def run_app(self, check):
        with patch('reports.data.options', return_value=copy.deepcopy(self.options)), \
                patch('reports.data.business', side_effect=lambda *a, **k: copy.deepcopy(self.panel)):
            app = AppTest.from_file(APP, default_timeout=30).run()
            self.assertFalse(app.exception)
            check(app)

    def test_business_metrics_and_fixed_charts(self):
        def check(app):
            values = {m.label: m.value for m in app.metric}
            self.assertEqual(set(values), {'Published orders', 'Orders to review', 'Ordered units',
                                           'Original merchandise', 'Original order total'})
            self.assertEqual(values['Original order total'], 'USD 123,456,789.12')
            self.assertEqual(values['Original merchandise'], 'USD 123,456,780.12')
            self.assertFalse(app.text_input)
            self.assertNotIn('channel_metric', [item.key for item in app.selectbox])
            self.assertEqual([h.value for h in app.subheader], ['Orders by channel',
                'Order activity over time', 'Ordered units by channel', 'Top products by ordered units'])
            columns = app.get('column')
            self.assertEqual([m.label for c in columns[:3] for m in c.metric],
                             ['Published orders', 'Orders to review', 'Ordered units'])
            self.assertEqual([m.label for c in columns[3:5] for m in c.metric],
                             ['Original merchandise', 'Original order total'])
        self.run_app(check)

    def test_supporting_evidence_is_last_and_keeps_versions(self):
        def check(app):
            footer = list(app.main.children.values())[-1]
            self.assertEqual(footer.type, 'expander')
            self.assertEqual(footer.label, 'Data availability and source publications')
            self.assertFalse(footer.proto.expanded)
            self.assertTrue(any('Observed versions' in c.value for c in footer.caption))
            self.assertEqual(len(footer.dataframe), 3)
        self.run_app(check)

    def test_unknown_money_is_not_zero_and_failure_warning_is_retained(self):
        self.panel['summary']['order_amount'] = None
        self.panel['lines']['merchandise'] = None
        self.panel['health'] = [dict(source_system='internal_web', source_account_id='WEB01',
            publication_name='website_orders', last_failed_at=None, last_successful_acquisition_at=None)]
        def check(app):
            values = {m.label: m.value for m in app.metric}
            self.assertEqual(values['Original merchandise'], 'Unknown')
            self.assertEqual(values['Original order total'], 'Unknown')
            self.assertTrue(any('unpublished' in w.value for w in app.warning))
        self.run_app(check)

    def test_order_operations_keeps_search_and_detail_controls(self):
        def check(app):
            app.sidebar.radio(key='workspace').set_value('Order Operations').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input(key='exact').label, 'Exact order ID (optional)')
            self.assertEqual(len(app.selectbox(key='inspect_page').options), 1)
            self.assertEqual(list(app.main.children.values())[-1].label,
                             'Data availability and source publications')
        self.run_app(check)


if __name__ == '__main__':
    unittest.main(verbosity=2)
