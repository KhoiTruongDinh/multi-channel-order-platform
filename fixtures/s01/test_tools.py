"""Focused tests for fixture utilities; NOT full pipeline acceptance tests."""
import copy
import json
import unittest
from fixture_tools import fingerprint, resolve_mapping, sign, verify_signature
from verify import etsy_money, load, positive_integer, verify


class FixtureTests(unittest.TestCase):
    def test_complete_offline_fixture_validation(self):
        self.assertEqual(verify()['result'], 'PASS')

    def test_known_unordered_lines_hash_identically(self):
        a = {'lineItems': [{'lineItemId': 'b', 'quantity': 1}, {'lineItemId': 'a', 'quantity': 2}]}
        b = {'lineItems': list(reversed(a['lineItems']))}
        self.assertEqual(fingerprint(a, 'ebay_order'), fingerprint(b, 'ebay_order'))

    def test_missing_and_null_are_different(self):
        self.assertNotEqual(fingerprint({}, 'etsy_receipt'), fingerprint({'sku': None}, 'etsy_receipt'))

    def test_timestamp_aliases_collapse_only_if_consistent(self):
        a = {'created_timestamp': 1792227840, 'updated_timestamp': 1792227900}
        b = dict(a, create_timestamp=1792227840, update_timestamp=1792227900)
        self.assertEqual(fingerprint(a, 'etsy_receipt'), fingerprint(b, 'etsy_receipt'))
        with self.assertRaises(ValueError):
            fingerprint(dict(a, update_timestamp=1792227840), 'etsy_receipt')

    def test_quantity_change_changes_fingerprint(self):
        a = {'lineItems': [{'lineItemId': 'a', 'quantity': 1}]}
        b = {'lineItems': [{'lineItemId': 'a', 'quantity': 2}]}
        self.assertNotEqual(fingerprint(a, 'ebay_order'), fingerprint(b, 'ebay_order'))

    def test_duplicate_line_ids_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint({'lineItems': [{'lineItemId': 'a'}, {'lineItemId': 'a'}]}, 'ebay_order')

    def test_non_business_array_order_is_not_arbitrarily_sorted(self):
        self.assertNotEqual(fingerprint({'unknown': [1, 2]}, 'order'), fingerprint({'unknown': [2, 1]}, 'order'))

    def test_signing_exact_bytes_and_freshness(self):
        raw = b'{"shop_id":7001}'
        headers = {'webhook-id': 'test-id', 'webhook-timestamp': '1792227840',
                   'webhook-signature': sign('test-id', 1792227840, raw)}
        verify_signature(headers, raw, 1792227960)
        with self.assertRaises(ValueError):
            verify_signature(headers, b'{ "shop_id":7001}', 1792227960)
        with self.assertRaises(ValueError):
            verify_signature(headers, raw, 1792228141)

    def test_divisor_and_local_quantity_validation(self):
        with self.assertRaises(ValueError):
            etsy_money({'amount': 2200, 'divisor': 0, 'currency_code': 'USD'})
        with self.assertRaises(ValueError):
            positive_integer(True, 'quantity')
        with self.assertRaises(ValueError):
            positive_integer(0, 'quantity')

    def test_mapping_identity_conflict_and_scope(self):
        mappings = load('config/product_mapping.json')['mappings']
        self.assertEqual(resolve_mapping(mappings, 'ebay_sim', 'seller_sim_01', '510001', '610001', 'EB-BLUE-350'), 'V001')
        with self.assertRaises(ValueError):
            resolve_mapping(mappings, 'ebay_sim', 'wrong-account', '510001', '610001', 'EB-BLUE-350')
        with self.assertRaises(ValueError):
            resolve_mapping(mappings, 'ebay_sim', 'seller_sim_01', '510001', '610001', 'EB-WHITE-350')


if __name__ == '__main__':
    unittest.main(verbosity=2)
