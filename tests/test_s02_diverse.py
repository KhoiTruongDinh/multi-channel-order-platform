"""Offline diversity/reference checks; no claim of Docker/warehouse acceptance."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support.s02_diverse import catalog, references, diverse_inputs
from simulator.s02_store import Store

AT = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
RUN = '123456abcdef'


class DiversityTests(unittest.TestCase):
    def test_reference_keys_and_mapping(self):
        ref = references()
        self.assertEqual(len(catalog()['products']), 30)
        self.assertEqual(len(ref['customers']), 100)
        self.assertEqual(len(ref['products']), 30)
        self.assertEqual(len(ref['product_variants']), 30)
        self.assertEqual(len(ref['mapping']), 90)
        self.assertEqual(len({r['mapping_id'] for r in ref['mapping']}), 90)
        self.assertEqual({r['mapping_version'] for r in ref['mapping']}, {'s02-catalog-v1'})
        for source in ('internal_web', 'ebay_sim', 'etsy_sim'):
            rows = [r for r in ref['mapping'] if r['source_system'] == source]
            self.assertEqual(len({r['canonical_variant_id'] for r in rows}), 30)
            self.assertEqual(len({(r['source_listing_id'], r['source_variant_id']) for r in rows}), 30)
        self.assertTrue(all(r['email'].endswith('@example.test') for r in ref['customers']))

    def test_seed_reproducibility_and_variety(self):
        first = diverse_inputs(17, 1, AT, RUN)
        self.assertEqual(first, diverse_inputs(17, 1, AT, RUN))
        self.assertNotEqual(first, diverse_inputs(18, 1, AT, RUN))
        self.assertEqual(len(first), 12)
        sizes, quantities, products, buyers = set(), set(), set(), set()
        for seed in range(10):
            for op in diverse_inputs(seed, 1, AT, RUN):
                p, source = op['payload'], op['source']
                lines = p['order_items'] if source == 'internal_web' else p['order']['lineItems'] if source == 'ebay_sim' else p['transactions']
                sizes.add(len(lines))
                quantities.update(l['quantity'] for l in lines)
                if source == 'internal_web':
                    products.update(l['variant_id'] for l in lines)
                    buyers.add(p['orders'][0]['customer_id'])
        self.assertEqual(sizes, set(range(1, 9)))
        self.assertEqual(quantities, set(range(1, 6)))
        self.assertEqual(len(products), 30)
        self.assertGreater(len(buyers), 10)

    def test_source_money_fk_mapping_and_wave_invariants(self):
        mapping = references()['mapping']
        for count in (2, 4, 30):
            first = diverse_inputs(17, 1, AT, RUN, orders_per_channel=count)
            final = diverse_inputs(17, 2, AT, RUN, AT+timedelta(seconds=10), count)
            self.assertEqual(len(first), count*3)
            self.assertEqual(len({(o['source'], o['order_id']) for o in final}), count*3)
            for old, new in zip(first, final):
                self.assertEqual(old['order_id'], new['order_id'])
                p, source = new['payload'], new['source']
                if source == 'internal_web':
                    order, lines = p['orders'][0], p['order_items']
                    self.assertIn(order['customer_id'], {c['customer_id'] for c in p['customers']})
                    gross = sum(Decimal(l['unit_price'])*l['quantity'] for l in lines)
                    self.assertEqual(gross, Decimal(order['order_total_amount']))
                    self.assertEqual(gross, Decimal(p['payment_transactions'][0]['amount']))
                    self.assertEqual(order['payment_status'], 'PAID')
                    self.assertEqual(order['cancellation_status'], 'CANCELED')
                    self.assertEqual(lines, old['payload']['order_items'])
                    identifiers = [l['variant_id'] for l in lines]
                    for l in lines:
                        self.assertEqual(l['order_id'], order['order_id'])
                        self.assertEqual(sum(m['source_system'] == source and m['source_variant_id'] == l['variant_id'] for m in mapping), 1)
                elif source == 'ebay_sim':
                    order, lines = p['order'], p['order']['lineItems']
                    self.assertEqual(sum(Decimal(l['lineItemCost']['value']) for l in lines), Decimal(order['pricingSummary']['total']['value']))
                    self.assertEqual(order['pricingSummary'], old['payload']['order']['pricingSummary'])
                    self.assertEqual([(l['lineItemId'], l['quantity'], l['legacyVariationId'], l['lineItemCost']) for l in lines],
                        [(l['lineItemId'], l['quantity'], l['legacyVariationId'], l['lineItemCost']) for l in old['payload']['order']['lineItems']])
                    identifiers = [l['legacyVariationId'] for l in lines]
                    fulfillment = p['fulfillments'][0]
                    self.assertEqual(fulfillment['lineItems'], [dict(lineItemId=lines[0]['lineItemId'], quantity=lines[0]['quantity'])])
                    for l in lines:
                        self.assertEqual(sum(m['source_system'] == source and m['source_listing_id'] == l['legacyItemId'] and m['source_variant_id'] == l['legacyVariationId'] for m in mapping), 1)
                    self.assertEqual(order['orderFulfillmentStatus'], 'FULFILLED' if len(lines) == 1 else 'IN_PROGRESS')
                    store = Store('ebay')
                    store.upsert(old['payload']); store.upsert(p)
                else:
                    lines = p['transactions']
                    self.assertEqual(sum(l['price']['amount']*l['quantity'] for l in lines), p['grandtotal']['amount'])
                    self.assertEqual(p['grandtotal'], old['payload']['grandtotal'])
                    self.assertTrue(p['is_paid'] and p['is_shipped'])
                    self.assertEqual(p['buyer_user_id'], old['payload']['buyer_user_id'])
                    self.assertEqual([(l['transaction_id'], l['product_id'], l['quantity'], l['price']) for l in lines],
                        [(l['transaction_id'], l['product_id'], l['quantity'], l['price']) for l in old['payload']['transactions']])
                    identifiers = [l['product_id'] for l in lines]
                    for l in lines:
                        self.assertEqual(l['receipt_id'], p['receipt_id'])
                        self.assertEqual(sum(m['source_system'] == source and m['source_listing_id'] == str(l['listing_id']) and m['source_variant_id'] == str(l['product_id']) for m in mapping), 1)
                    store = Store('etsy')
                    store.upsert(old['payload']); store.upsert(p)
                self.assertEqual(len(identifiers), len(set(identifiers)))
                self.assertTrue(all(1 <= l['quantity'] <= 5 for l in lines))

    def test_reject_invalid_config(self):
        for count in (True, 1, 10001, 4.0):
            with self.assertRaises(ValueError):
                diverse_inputs(17, 1, AT, RUN, orders_per_channel=count)
        for seed, wave in ((True, 1), (-1, 1), (17, 0), (17, 3), (17, True)):
            with self.assertRaises(ValueError):
                diverse_inputs(seed, wave, AT, RUN)
        with self.assertRaises(ValueError):
            diverse_inputs(17, 1, AT, '../owner')
        with self.assertRaises(ValueError):
            diverse_inputs(17, 1, AT, RUN, AT-timedelta(seconds=1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
