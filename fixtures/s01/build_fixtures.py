"""Deterministic S01 materialization from the reviewed workbook snapshot.

This authoring script may read golden answers. A future pipeline MUST NOT.
Only the Python standard library is required.
"""
import copy
import hashlib
import json
from pathlib import Path
from fixture_tools import fingerprint, iso, json_bytes, sign, utc_seconds

ROOT = Path(__file__).resolve().parent


def write(path, value):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def build():
    book = json.loads((ROOT / 'references/review_snapshot.json').read_text(encoding='utf-8'))
    def data(tab):
        return book[tab][1:]

    def web_state(column):
        tables = {}
        for row in data('03_Website'):
            row = row + [''] * (7 - len(row))
            table, key, field = row[:3]
            if 'row count' in field:
                tables.setdefault(table, {})
                continue
            value = row[column]
            if value == 'NO_RECORD':
                tables.setdefault(table, {})
                continue
            value = None if value == 'NULL' else value
            if field == 'attributes' and isinstance(value, str):
                value = json.loads(value)
            if field in {'current_price', 'items_gross_amount', 'discount_amount',
                         'shipping_amount', 'tax_amount', 'order_total_amount',
                         'unit_price', 'line_discount_amount', 'line_tax_amount', 'amount'}:
                value = f'{value:.2f}'
            tables.setdefault(table, {}).setdefault(key, {})[field] = value
        return {name: list(records.values()) for name, records in tables.items()}

    # Full selected relational rows at observed source states, not warehouse rows.
    states = {}
    for label, col in [('0901', 3), ('0910', 4), ('0914', 5)]:
        states[label] = web_state(col)
        write(f'source_states/website/{label}.json', states[label])
    created = copy.deepcopy(states['0901'])
    created['orders'][0].update(payment_status='UNPAID', updated_at='2026-10-17T09:00:00Z')
    created['payment_transactions'] = []
    write('source_states/website/0900.json', created)

    def ebay_order(shipped):
        lines = []
        for line_id, variation, sku, title, qty, cost in [
            ('10001001', '610001', 'EB-BLUE-350', 'Blue ceramic mug 350 ml', 2, '40.00'),
            ('10001002', '610002', 'EB-WHITE-350', 'White ceramic mug 350 ml', 1, '22.00')]:
            lines.append({'lineItemId': line_id, 'legacyItemId': '510001',
                          'legacyVariationId': variation, 'sku': sku, 'title': title,
                          'quantity': qty, 'lineItemCost': {'value': cost, 'currency': 'USD'},
                          'lineItemFulfillmentStatus': 'FULFILLED' if shipped and line_id == '10001001' else 'NOT_STARTED'})
        return {'orderId': '12-10001-10001', 'sellerId': 'seller_sim_01',
                'creationDate': '2026-10-17T09:02:00Z',
                'lastModifiedDate': '2026-10-17T09:12:00Z' if shipped else '2026-10-17T09:02:00Z',
                'orderPaymentStatus': 'PAID',
                'orderFulfillmentStatus': 'IN_PROGRESS' if shipped else 'NOT_STARTED',
                'cancelStatus': {'cancelState': 'NONE_REQUESTED', 'cancelRequests': []},
                'pricingSummary': {'priceSubtotal': {'value': '62.00', 'currency': 'USD'},
                                   'deliveryCost': {'value': '0.00', 'currency': 'USD'},
                                   'total': {'value': '62.00', 'currency': 'USD'}},
                'lineItems': lines,
                'fulfillmentHrefs': ['http://ebay-sim/sell/fulfillment/v1/order/12-10001-10001/shipping_fulfillment/FUL001'] if shipped else []}

    fulfillment = {'fulfillmentId': 'FUL001', 'shippedDate': '2026-10-17T09:12:00Z',
                   'shippingCarrierCode': 'USPS', 'shipmentTrackingNumber': 'SIMTRACK001',
                   'lineItems': [{'lineItemId': '10001001', 'quantity': 2}]}
    for suffix, shipped in [('0902', False), ('0912', True)]:
        order = ebay_order(shipped)
        write(f'source_states/ebay/{suffix}.json', {'order': order, 'fulfillments': [fulfillment] if shipped else []})

    def money(amount):
        return {'amount': amount, 'divisor': 100, 'currency_code': 'USD'}

    receipt = {'receipt_id': 9001001, 'seller_user_id': 7001001, 'buyer_user_id': 7002001,
               'created_timestamp': 1792227840, 'updated_timestamp': 1792227900,
               'status': 'completed', 'is_paid': True, 'is_shipped': True, 'payment_method': 'cc',
               'transactions': [{'transaction_id': 8001001, 'receipt_id': 9001001,
                                 'listing_id': 520001, 'product_id': 620002,
                                 'sku': 'ET-WHITE-350', 'title': 'White ceramic mug 350 ml',
                                 'quantity': 1, 'price': money(2200), 'shipping_cost': money(0),
                                 'paid_timestamp': 1792227840, 'shipped_timestamp': 1792227900,
                                 'is_digital': False, 'variations': []}],
               'shipments': [{'receipt_shipping_id': 630001,
                              'shipment_notification_timestamp': 1792227900,
                              'carrier_name': 'USPS', 'tracking_code': 'SIMETSY001'}],
               'refunds': []}
    for field, amount in [('total_price', 2200), ('subtotal', 2200), ('grandtotal', 2200),
                          ('discount_amt', 0), ('total_shipping_cost', 0), ('total_tax_cost', 0),
                          ('total_vat_cost', 0), ('gift_wrap_price', 0)]:
        receipt[field] = money(amount)
    write('source_states/etsy/0905.json', receipt)
    paid = copy.deepcopy(receipt)
    paid.update(status='paid', is_shipped=False, updated_timestamp=1792227840, shipments=[])
    paid['transactions'][0]['shipped_timestamp'] = None
    write('source_states/etsy/0904.json', paid)

    mappings = []
    for row in data('02_Catalog'):
        source, account = row[:2]
        mappings.append({'source_system': source, 'source_account_id': str(account),
                         'source_listing_id': None if source == 'internal_web' else str(row[5]),
                         'source_variant_id': str(row[6]), 'source_sku': row[4],
                         'canonical_variant_id': row[7], 'mapping_status': 'CONFIRMED'})
    write('config/product_mapping.json', {'mapping_version': 's01-v1', 'mappings': mappings})

    acquisitions = []
    def acquire(aid, source, at, response, request, kind, headers=None, context=None):
        response_path = write(f'responses/{source}/{aid}.json', response)
        req_path = write(f'requests/{aid}.json', request)
        acquisitions.append({'acquisition_id': aid, 'source_system': source,
                             'observed_at': at, 'request_file': req_path,
                             'response_file': response_path, 'business_kind': kind,
                             'response_headers': headers or {'content-type': 'application/json'},
                             'context': context or {}})

    def get(path, query=None):
        return {'method': 'GET', 'path': path, 'query': query or {},
                'headers': {'Authorization': 'Bearer LOCAL_TEST_TOKEN'}}

    for aid, at, label in [('WEB_R1', '09:03', '0901'), ('WEB_R2', '09:11', '0910'), ('WEB_R3', '09:15', '0914')]:
        acquire(aid, 'internal_web', f'2026-10-17T{at}:00Z', states[label],
                {'interface': 'consistent_relational_read', 'store_id': 'WEB01',
                 'order_ids': ['W1001'], 'read_only': True}, 'website_tables',
                context={'source_account_id': 'WEB01'})
    previous_upper = '2026-10-17T09:03:00Z'
    for aid, at, shipped in [('EB_R1', '09:03', False), ('EB_R2', '09:13', True)]:
        upper = f'2026-10-17T{at}:00Z'
        lower = '2026-10-17T09:00:00Z' if not shipped else iso(utc_seconds(previous_upper) - 120)
        query = {'filter': f'lastmodifieddate:[{lower}..{upper}]', 'limit': '1', 'offset': '0'}
        order = ebay_order(shipped)
        from urllib.parse import urlencode
        href = 'http://ebay-sim/sell/fulfillment/v1/order?' + urlencode(query)
        acquire(aid, 'ebay_sim', upper,
                {'href': href, 'total': 1, 'limit': 1, 'offset': 0, 'orders': [order]},
                get('/sell/fulfillment/v1/order', query), 'ebay_order_page',
                context={'source_account_id': 'seller_sim_01'})
        if shipped:
            acquire('EB_F1', 'ebay_sim', upper, {'total': 1, 'fulfillments': [fulfillment]},
                    get('/sell/fulfillment/v1/order/12-10001-10001/shipping_fulfillment'),
                    'ebay_fulfillment_page', context={'source_account_id': 'seller_sim_01', 'order_id': order['orderId']})
        write(f'interface_examples/ebay/{aid}_detail.json', order)
    write('interface_examples/ebay/empty_orders.json', {'href': 'http://ebay-sim/sell/fulfillment/v1/order?limit=1&offset=0',
                                                     'total': 0, 'limit': 1, 'offset': 0, 'orders': []})
    write('interface_examples/ebay/empty_fulfillments.json', {'total': 0, 'fulfillments': []})
    write('interface_examples/ebay/fulfillment_detail.json', fulfillment)
    for aid, at in [('ET_R1', '09:06'), ('ET_R2', '09:07')]:
        acquire(aid, 'etsy_sim', f'2026-10-17T{at}:00Z', receipt,
                get('/v3/application/shops/7001/receipts/9001001'), 'etsy_receipt',
                context={'source_account_id': '7001'})
    write('interface_examples/etsy/receipt_list.json', {'count': 1, 'results': [receipt]})
    write('interface_examples/etsy/empty_receipt_list.json', {'count': 0, 'results': []})
    write('interface_examples/etsy/receipt_list_request.json',
          get('/v3/application/shops/7001/receipts', {'min_last_modified': 1792227600,
              'max_last_modified': 1792227960, 'limit': 1, 'offset': 0,
              'sort_on': 'updated', 'sort_order': 'asc'}))

    deliveries = []
    for did, mid, event, emitted, received, fetch in [
        ('D1', 'msg_paid_001', 'order.paid', '09:04', '09:06', 'ET_R1'),
        ('D2', 'msg_shipped_001', 'order.shipped', '09:05', '09:07', 'ET_R2'),
        ('D3', 'msg_paid_001', 'order.paid', '09:04', '09:08', None)]:
        body = {'event_type': event, 'resource_url': 'http://etsy-sim/v3/application/shops/7001/receipts/9001001', 'shop_id': 7001}
        raw = json_bytes(body)
        path = ROOT / f'webhooks/{did}.body.json'
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        epoch = utc_seconds(f'2026-10-17T{emitted}:00Z')
        headers = {'content-type': 'application/json', 'webhook-id': mid,
                   'webhook-timestamp': str(epoch), 'webhook-signature': sign(mid, epoch, raw)}
        write(f'webhooks/{did}.headers.json', headers)
        deliveries.append({'attempt_id': did, 'body_file': f'webhooks/{did}.body.json',
                           'headers_file': f'webhooks/{did}.headers.json',
                           'received_at': f'2026-10-17T{received}:00Z', 'receipt_fetch': fetch})
    write('webhooks/deliveries.json', deliveries)
    write('acquisitions.json', sorted(acquisitions, key=lambda a: (a['observed_at'], a['acquisition_id'])))
    write('scenario.json', {'scenario_id': 'S01', 'fixture_version': '1.0.0',
                           'scenario_date': '2026-10-17', 'timezone': 'UTC',
                           'mapping_version': 's01-v1', 'transformation_version': 's01-v1',
                           'signature_tolerance_seconds': 300, 'overlap_seconds': 120,
                           'max_attempts_per_cycle': 5,
                           'timeline': [dict(zip(book['01_Timeline'][0], row)) for row in data('01_Timeline')]})

    # Golden answers are authored from reviewed output tables, not produced by ingestion.
    orders = []
    for row in data('07_CurrentOrders'):
        orders.append(dict(zip(['source_system', 'source_account_id', 'source_order_id',
            'source_created_at', 'source_updated_at', 'source_snapshot_observed_at',
            'payment_state', 'fulfillment_state', 'cancellation_state', 'currency',
            'source_order_total_amount', 'history_id'], row)))
        orders[-1]['source_order_total_amount'] = f"{row[10]:.2f}"
        orders[-1]['source_account_id'] = str(row[1])
    write('expected/orders_current.json', orders)
    lines = []
    for row in data('08_CurrentLines'):
        item = dict(zip(['source_system', 'source_account_id', 'source_order_id', 'source_line_id',
                         'canonical_variant_id', 'source_sku', 'quantity', 'unit_gross_amount',
                         'line_gross_amount', 'evidence_note'], row))
        item.update(currency='USD', unit_gross_amount=f'{row[7]:.2f}', line_gross_amount=f'{row[8]:.2f}')
        for k in ['source_account_id', 'source_order_id', 'source_line_id']:
            item[k] = str(item[k])
        lines.append(item)
    write('expected/order_lines_current.json', lines)
    history = [dict(zip(['history_id', 'source_system', 'source_order_id', 'source_updated_at',
                         'source_snapshot_observed_at', 'payment_state', 'fulfillment_state',
                         'cancellation_state', 'fixture_evidence_note'], row)) for row in data('09_History')]
    write('expected/order_snapshot_history.json', history)
    # Every observed order version has a corresponding observed line snapshot set.
    line_history = []
    for version in history:
        for line in lines:
            if line['source_system'] == version['source_system'] and line['source_order_id'] == version['source_order_id']:
                x = copy.deepcopy(line)
                x.update(order_history_id=version['history_id'],
                         source_snapshot_observed_at=version['source_snapshot_observed_at'])
                line_history.append(x)
    write('expected/order_line_snapshot_history.json', line_history)
    evidence = {'WEB_H1': ['WEB_R1'], 'WEB_H2': ['WEB_R2'], 'WEB_H3': ['WEB_R3'],
                'EB_H1': ['EB_R1'], 'EB_H2': ['EB_R2', 'EB_F1'], 'ET_H1': ['ET_R1']}
    write('expected/snapshot_evidence.json', [{'history_id': h, 'acquisition_id': a}
          for h, values in evidence.items() for a in values])
    write('expected/webhook_inbox.json', [
        {'source_system': 'etsy_sim', 'subscription_id': 's01-order-events', 'webhook_id': 'msg_paid_001',
         'event_type': 'order.paid', 'first_received_at': '2026-10-17T09:06:00Z', 'attempt_count': 2},
        {'source_system': 'etsy_sim', 'subscription_id': 's01-order-events', 'webhook_id': 'msg_shipped_001',
         'event_type': 'order.shipped', 'first_received_at': '2026-10-17T09:07:00Z', 'attempt_count': 1}])
    write('expected/exceptions.json', [])
    write('expected/summary.json', {'orders': 3, 'order_lines': 4, 'ordered_units': 6,
        'gross_merchandise_usd': '124.00', 'source_order_totals_usd': '124.00',
        'order_history_versions': 6, 'observed_line_history_rows': 8,
        'logical_webhook_messages': 2, 'webhook_delivery_attempts': 3,
        'confirmed_canceled_orders': 1, 'confirmed_refund_transactions': 0,
        'delivered_orders': 0, 'exceptions': 0})
    files = {}
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and p.suffix in {'.json', '.md', '.py'} and '__pycache__' not in p.parts and p.name not in {'checksums.json', 'verification_report.json'}:
            files[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    write('checksums.json', files)
    print(f'Built S01: {len(acquisitions)} scheduled acquisitions; 3 webhook attempts; {len(files)} checksummed files')


if __name__ == '__main__':
    build()
