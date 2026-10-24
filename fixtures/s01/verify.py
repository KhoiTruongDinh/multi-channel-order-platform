"""Check fixture integrity, source contracts and S01 golden answers offline.

This does not launch HTTP services, run a database, or test a real DE pipeline.
"""
import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from fixture_tools import fingerprint, resolve_mapping, utc_seconds, verify_signature

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive_integer(value, label):
    require(type(value) is int and value > 0, f'{label}: positive integer required')


def etsy_money(value):
    positive_integer(value['divisor'], 'Money.divisor')
    require(type(value['amount']) is int, 'Money.amount: integer required')
    require(isinstance(value['currency_code'], str) and len(value['currency_code']) == 3,
            'Money.currency_code invalid')
    return Decimal(value['amount']) / Decimal(value['divisor'])


def amount(value):
    require(isinstance(value['value'], str), 'eBay Amount.value must remain string')
    result = Decimal(value['value'])
    require(result.is_finite(), 'Non-finite source amount')
    return result


def source_observation(acq, mappings, acquisitions):
    payload = load(acq['response_file'])
    source = acq['source_system']
    account = acq['context']['source_account_id']
    lines = []
    if source == 'internal_web':
        require(set(payload) == {'customers', 'products', 'product_variants', 'orders',
                                 'order_items', 'payment_transactions', 'cancellation_requests',
                                 'shipments', 'shipment_items'}, 'Website table set mismatch')
        order = payload['orders'][0]
        by_variant = {v['variant_id']: v for v in payload['product_variants']}
        require(order['customer_id'] in {x['customer_id'] for x in payload['customers']},
                'Website customer FK missing')
        for item in payload['order_items']:
            require(item['order_id'] == order['order_id'], 'Website line FK mismatch')
            require(item['variant_id'] in by_variant, 'Website variant FK mismatch')
            positive_integer(item['quantity'], 'Website quantity')
            gross = Decimal(item['unit_price']) * item['quantity']
            variant = resolve_mapping(mappings, source, account, variant=item['variant_id'], sku=item['sku_at_purchase'])
            lines.append((str(item['order_item_id']), variant, item['quantity'], gross))
        require(sum(x[3] for x in lines) == Decimal(order['items_gross_amount']), 'Website gross mismatch')
        require(Decimal(order['discount_amount']) == sum(Decimal(x['line_discount_amount']) for x in payload['order_items']), 'Website discount sum mismatch')
        require(Decimal(order['tax_amount']) == sum(Decimal(x['line_tax_amount']) for x in payload['order_items']), 'Website tax sum mismatch')
        total = Decimal(order['items_gross_amount']) - Decimal(order['discount_amount']) + Decimal(order['shipping_amount']) + Decimal(order['tax_amount'])
        require(total == Decimal(order['order_total_amount']), 'Website total formula mismatch')
        for transaction in payload['payment_transactions']:
            require(transaction['order_id'] == order['order_id'], 'Payment FK mismatch')
            require(transaction['currency'] == order['currency'], 'Payment currency mismatch')
        for request in payload['cancellation_requests']:
            require(request['order_id'] == order['order_id'], 'Cancellation FK mismatch')
            resolved = request['resolved_at']
            require((request['status'] == 'PENDING') == (resolved is None), 'Cancellation resolved_at consistency')
            if resolved:
                require(utc_seconds(resolved) >= utc_seconds(request['requested_at']), 'Cancellation time order invalid')
        state = (order['payment_status'], order['fulfillment_status'], order['cancellation_status'])
        oid, updated = order['order_id'], order['updated_at']
        kind, business = 'website_order', {k: payload[k] for k in ['orders', 'order_items', 'payment_transactions', 'cancellation_requests', 'shipments', 'shipment_items']}
    elif source == 'ebay_sim':
        require(acq['business_kind'] == 'ebay_order_page', 'Not an order acquisition')
        require(payload['total'] == 1 and len(payload['orders']) == 1, 'S01 eBay envelope mismatch')
        require(payload['limit'] == 1 and payload['offset'] == 0, 'S01 page parameters mismatch')
        order = payload['orders'][0]
        require(order['sellerId'] == account, 'eBay seller scope mismatch')
        require('tax' not in order['pricingSummary'], 'Tax-free S01 must omit tax container')
        for item in order['lineItems']:
            positive_integer(item['quantity'], 'eBay quantity')
            variant = resolve_mapping(mappings, source, account, item['legacyItemId'],
                                      item.get('legacyVariationId'), item.get('sku'))
            lines.append((item['lineItemId'], variant, item['quantity'], amount(item['lineItemCost'])))
        require(sum(x[3] for x in lines) == amount(order['pricingSummary']['priceSubtotal']), 'eBay subtotal mismatch')
        total = amount(order['pricingSummary']['total'])
        fulfillments = []
        for other in acquisitions:
            if other['business_kind'] == 'ebay_fulfillment_page' and other['observed_at'] == acq['observed_at']:
                require(other['context']['order_id'] == order['orderId'], 'Fulfillment order scope mismatch')
                fulfillments = load(other['response_file'])['fulfillments']
        quantities = {item['lineItemId']: item['quantity'] for item in order['lineItems']}
        allocated = Counter()
        for parcel in fulfillments:
            require(bool(parcel.get('shippedDate')), 'Shipment date evidence missing')
            for line in parcel['lineItems']:
                positive_integer(line['quantity'], 'Fulfillment quantity')
                require(line['lineItemId'] in quantities, 'Fulfillment references unknown line')
                allocated[line['lineItemId']] += line['quantity']
        require(all(q <= quantities[k] for k, q in allocated.items()), 'Shipment allocation exceeds ordered quantity')
        shipped = sum(allocated.values())
        fulfillment = 'NOT_STARTED' if not shipped else 'PARTIALLY_SHIPPED' if shipped < sum(quantities.values()) else 'SHIPPED'
        state = (order['orderPaymentStatus'], fulfillment, 'NOT_REQUESTED')
        require(order['cancelStatus']['cancelState'] == 'NONE_REQUESTED', 'Unsupported S01 cancellation state')
        oid, updated = order['orderId'], order['lastModifiedDate']
        kind, business = 'ebay_order_and_shipments', {'order': order, 'fulfillments': fulfillments}
    else:
        require(source == 'etsy_sim', 'Unknown source')
        order = payload
        positive_integer(order['receipt_id'], 'receipt_id')
        require(type(order['is_paid']) is bool and type(order['is_shipped']) is bool, 'Etsy flag types invalid')
        for item in order['transactions']:
            require(item['receipt_id'] == order['receipt_id'], 'Etsy transaction receipt FK mismatch')
            positive_integer(item['quantity'], 'Etsy quantity')
            variant = resolve_mapping(mappings, source, account, item.get('listing_id'), item.get('product_id'), item.get('sku'))
            lines.append((str(item['transaction_id']), variant, item['quantity'], etsy_money(item['price']) * item['quantity']))
        require(sum(x[3] for x in lines) == etsy_money(order['total_price']), 'Etsy gross mismatch')
        total = etsy_money(order['grandtotal'])
        state = ('PAID' if order['is_paid'] else 'UNPAID', 'SHIPPED' if order['is_shipped'] else 'NOT_STARTED', 'UNKNOWN')
        oid, updated = str(order['receipt_id']), order['updated_timestamp']
        kind, business = 'etsy_receipt', order
    require(utc_seconds(acq['observed_at']) >= utc_seconds(updated), 'Snapshot observed before source update')
    return {'source': source, 'account': account, 'order': str(oid), 'updated': utc_seconds(updated),
            'observed': acq['observed_at'], 'state': state, 'lines': lines, 'total': total,
            'fingerprint': fingerprint(business, kind)}


def verify(checksums=True):
    checks = []
    def passed(name):
        checks.append({'check': name, 'result': 'PASS', 'scope': 'offline fixture validation'})
    if checksums:
        for path, expected in load('checksums.json').items():
            require(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, f'Checksum changed: {path}')
        passed('All packaged file checksums')
    acquisitions = load('acquisitions.json')
    mappings = load('config/product_mapping.json')['mappings']
    require(len(mappings) == 4, 'S01 mapping seed must have exactly4 sold references')
    passed('Standalone scoped mapping seed')
    observations = [source_observation(a, mappings, acquisitions) for a in acquisitions
                    if a['business_kind'] != 'ebay_fulfillment_page']
    passed('Source types, quantities, monetary conversion, FK and shipment evidence')
    versions = {}
    for x in observations:
        key = (x['source'], x['account'], x['order'], x['updated'], x['fingerprint'])
        versions.setdefault(key, x)
    history = load('expected/order_snapshot_history.json')
    require(len(versions) == len(history) == 6, 'Expected6 observed order versions')
    require(Counter(x['source'] for x in versions.values()) == {'internal_web': 3, 'ebay_sim': 2, 'etsy_sim': 1}, 'History source distribution mismatch')
    for h in history:
        match = [x for x in versions.values() if x['source'] == h['source_system']
                 and x['order'] == h['source_order_id'] and x['updated'] == utc_seconds(h['source_updated_at'])]
        require(len(match) == 1, f'History evidence mismatch: {h["history_id"]}')
        require(match[0]['state'] == (h['payment_state'], h['fulfillment_state'], h['cancellation_state']), 'History state mismatch')
        require(match[0]['observed'] == h['source_snapshot_observed_at'], 'First-observed time mismatch')
    passed('Six history versions from actual observed payloads, not source truth ledger')
    latest = {}
    for x in versions.values():
        k = (x['source'], x['account'], x['order'])
        if k not in latest or x['updated'] > latest[k]['updated']:
            latest[k] = x
    current = load('expected/orders_current.json')
    require(len(current) == len(latest) == 3, 'Current order count mismatch')
    for order in current:
        x = latest[(order['source_system'], order['source_account_id'], order['source_order_id'])]
        require(x['state'] == (order['payment_state'], order['fulfillment_state'], order['cancellation_state']), 'Current states mismatch')
        require(x['total'] == Decimal(order['source_order_total_amount']), 'Current order amount mismatch')
        require(x['observed'] == order['source_snapshot_observed_at'], 'Current version observation mismatch')
    passed('Three current orders match latest source-derived states and totals')
    expected_lines = load('expected/order_lines_current.json')
    derived_lines = {(x['source'], x['account'], x['order'], line[0]): line[1:]
                     for x in latest.values() for line in x['lines']}
    require(len(derived_lines) == len(expected_lines) == 4, 'Current line count mismatch')
    for line in expected_lines:
        k = (line['source_system'], line['source_account_id'], line['source_order_id'], line['source_line_id'])
        require(derived_lines[k] == (line['canonical_variant_id'], line['quantity'], Decimal(line['line_gross_amount'])), 'Mapped source line differs from golden answer')
    require(sum(x[1] for x in derived_lines.values()) == 6, 'Expected6 units')
    require(sum(x[2] for x in derived_lines.values()) == Decimal('124.00'), 'Expected124 USD gross')
    require(sum(x['total'] for x in latest.values()) == Decimal('124.00'), 'Expected124 USD order totals')
    passed('Four mapped source lines, six units, USD124 independently recomputed')
    deliveries = load('webhooks/deliveries.json')
    messages = {}
    for delivery in deliveries:
        raw = (ROOT / delivery['body_file']).read_bytes()
        headers = load(delivery['headers_file'])
        verify_signature(headers, raw, delivery['received_at'])
        body = json.loads(raw)
        require(body['shop_id'] == 7001, 'Webhook shop mismatch')
        require(body['resource_url'] == 'http://etsy-sim/v3/application/shops/7001/receipts/9001001', 'Webhook resource origin/path mismatch')
        mid = headers['webhook-id']
        if mid in messages:
            require(messages[mid] == raw, 'Conflicting duplicate webhook ID')
        messages[mid] = raw
    require(len(deliveries) == 3 and len(messages) == 2, 'Webhook cardinalities mismatch')
    require((ROOT / 'webhooks/D1.body.json').read_bytes() == (ROOT / 'webhooks/D3.body.json').read_bytes(), 'Duplicate body differs')
    passed('Three real test signatures and freshness checks; two logical webhook messages')
    require(load('responses/etsy_sim/ET_R1.json') == load('responses/etsy_sim/ET_R2.json'), 'Receipt version unexpectedly changed')
    passed('Repeated receipt payload equality')
    evidence = load('expected/snapshot_evidence.json')
    require(all(e['acquisition_id'] in {a['acquisition_id'] for a in acquisitions} for e in evidence), 'Unresolvable evidence reference')
    require({e['acquisition_id'] for e in evidence if e['history_id'] == 'EB_H2'} == {'EB_R2', 'EB_F1'}, 'Derived eBay snapshot needs two evidence resources')
    passed('Multi-resource snapshot evidence links')
    require(len(load('expected/order_line_snapshot_history.json')) == 8, 'Expected8 archived line rows across6 parent snapshots')
    require(load('expected/exceptions.json') == [], 'Baseline exceptions must be empty')
    require(not any(x['fulfillment_state'] == 'DELIVERED' for x in current), 'No delivered evidence inS01')
    final_web = load('responses/internal_web/WEB_R3.json')
    require(not any(x['transaction_type'] == 'REFUND' and x['status'] == 'SUCCEEDED' for x in final_web['payment_transactions']), 'No completed refund inS01')
    passed('Archived line snapshots, no baseline exceptions/delivered/refund claims')
    return {'scenario_id': 'S01', 'result': 'PASS', 'verification_scope': 'offline fixtures only',
            'runtime_pipeline_tested': False, 'checks': checks, 'summary': load('expected/summary.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = verify()
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
