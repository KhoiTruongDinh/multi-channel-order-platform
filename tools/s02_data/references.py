"""Shared source-shaped reference/payload construction; no warehouse answers."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import json
import random
import re
from uuid import NAMESPACE_URL, uuid5

from test_support.s02_inputs import ACCOUNTS, inputs

CATALOG = Path(__file__).resolve().parents[2] / 'fixtures/s02/catalog.json'
VALID_FROM = '2026-01-01T00:00:00Z'
VERSION = 's02-diverse-v1'


def catalog():
    """Fixed synthetic purchase inputs, never warehouse expectations."""
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if data['version'] != 's02-catalog-v1' or data['currency'] != 'USD':
        raise ValueError('unsupported catalog version/currency')
    rows = data['products']
    if len(rows) != 30 or {r[0] for r in rows} != set(range(1, 31)):
        raise ValueError('catalog must contain thirty distinct numbered products')
    for number, title, category, cents in rows:
        if type(number) is not int or not title.strip() or not category.strip() or type(cents) is not int or cents <= 0:
            raise ValueError('invalid catalog row')
    return data


def money(cents):
    return f'{cents // 100}.{cents % 100:02d}'


def references():
    """Return source catalog/customers and independent mapping seed rows, no IO writes."""
    data = catalog()
    result = dict(customers=[], products=[], product_variants=[], mapping=[])
    for number in range(1, 101):
        result['customers'].append(dict(customer_id=f'S02-C{number:03d}',
            display_name=f'Synthetic Customer {number:03d}', email=f's02-customer-{number:03d}@example.test',
            created_at=VALID_FROM, updated_at=VALID_FROM))
    for number, title, category, cents in data['products']:
        variant, sku = f'S02-V{number:03d}', f'S02-SKU-{number:03d}'
        result['products'].append(dict(product_id=f'S02-P{number:03d}', product_name=title,
            category=category, is_active=True, created_at=VALID_FROM, updated_at=VALID_FROM))
        result['product_variants'].append(dict(variant_id=variant, product_id=f'S02-P{number:03d}',
            sku=sku, attributes={'synthetic': True}, current_price=money(cents), currency='USD',
            is_active=True, updated_at=VALID_FROM))
        for source, account in ACCOUNTS.items():
            listing, source_variant, source_sku = (None, variant, sku) if source == 'internal_web' else (
                (str(710000+number), str(810000+number), f'EB-S02-{number:03d}') if source == 'ebay_sim'
                else (str(720000+number), str(820000+number), f'ET-S02-{number:03d}'))
            result['mapping'].append(dict(mapping_id=str(uuid5(NAMESPACE_URL, f'{data["version"]}/{source}/{number}')),
                mapping_version=data['version'], source_system=source, source_account_id=account,
                source_listing_id=listing, source_variant_id=source_variant, source_sku=source_sku,
                canonical_variant_id=variant, mapping_status='CONFIRMED', valid_from=VALID_FROM,
                valid_to=None, created_at=VALID_FROM))
    return result


def diverse_inputs(seed, wave, at, run_id, updated_at=None, orders_per_channel=4,
                   *, selection=None):
    """Pure bounded generation: caller must explicitly commit these source documents.

    Uses existing source lifecycle templates, not the v1 warehouse oracle. No
    Docker/DB/API call, background thread or production pipeline import occurs.
    """
    if type(orders_per_channel) is not int or not 2 <= orders_per_channel <= 10000:
        raise ValueError('orders_per_channel must be integer2..10000')
    if type(wave) is not int or wave not in (1, 2):
        raise ValueError('wave must be integer1 or2')
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{12}', run_id):
        raise ValueError('expected twelve lowercase hex test ID')
    current = updated_at or at
    minimum = datetime(2026, 1, 8, tzinfo=timezone.utc)
    if at.tzinfo is None or current.tzinfo is None or at < minimum or current < at:
        raise ValueError('aware campaign time after reference creation and nondecreasing update required')
    prototypes = {op['source']: op for op in inputs(seed, wave, at, run_id, current)[:3]}
    rng, ref, out = random.Random(seed), references() if selection is None else selection['references'], []
    products = catalog()['products']
    base = int(run_id[:8], 16) % 10000000 + 10000000 if selection is None else selection['base']
    indices = range(orders_per_channel) if selection is None else (selection['index'],)
    sources = ACCOUNTS if selection is None else (selection['source'],)
    bounds = dict(lines_min=1,lines_max=8,quantity_min=1,quantity_max=5) if selection is None else selection['basket']
    for index in indices:
        for source in sources:
            op = copy.deepcopy(prototypes[source])
            payload = op['payload']
            buyer = rng.randint(1, 100)
            chosen = rng.sample(products, rng.randint(bounds['lines_min'], bounds['lines_max']))
            purchases = [(p, rng.randint(bounds['quantity_min'], bounds['quantity_max'])) for p in chosen]
            total = sum(p[3]*quantity for p, quantity in purchases)
            numeric_id = base+index
            identity = str(numeric_id) if source == 'etsy_sim' else f'12-{numeric_id:08d}-10001'
            op['order_id'] = identity
            if source == 'internal_web':
                order = payload['orders'][0]
                order.update(order_id=identity, order_number=identity, customer_id=f'S02-C{buyer:03d}',
                    items_gross_amount=money(total), order_total_amount=money(total))
                template = payload['order_items'][0]
                payload['order_items'] = [dict(template, order_item_id=f'{identity}-L{n}', order_id=identity,
                    variant_id=f'S02-V{p[0]:03d}', sku_at_purchase=f'S02-SKU-{p[0]:03d}',
                    title_at_purchase=p[1], unit_price=money(p[3]), quantity=q)
                    for n, (p, q) in enumerate(purchases)]
                selected = {p[0] for p, _ in purchases}
                payload['customers'] = [copy.deepcopy(ref['customers'][buyer-1])]
                payload['products'] = [copy.deepcopy(ref['products'][n-1]) for n in sorted(selected)]
                payload['product_variants'] = [copy.deepcopy(ref['product_variants'][n-1]) for n in sorted(selected)]
                payload['payment_transactions'][0].update(payment_transaction_id=identity+'-PAY',
                    order_id=identity, amount=money(total), provider_reference=identity+'-PROVIDER')
                payload['cancellation_requests'][0].update(cancellation_id=identity+'-CAN', order_id=identity)
            elif source == 'ebay_sim':
                order = payload['order']
                order['orderId'] = identity
                template = order['lineItems'][0]
                order['lineItems'] = [dict(copy.deepcopy(template), lineItemId=str(base*1000000+index*10+n),
                    legacyItemId=str(710000+p[0]), legacyVariationId=str(810000+p[0]),
                    sku=f'EB-S02-{p[0]:03d}', title=p[1], quantity=q,
                    lineItemCost=dict(value=money(q*p[3]), currency='USD'),
                    lineItemFulfillmentStatus='FULFILLED' if wave == 2 and n == 0 else 'NOT_STARTED')
                    for n, (p, q) in enumerate(purchases)]
                for key in ('priceSubtotal', 'total'):
                    order['pricingSummary'][key]['value'] = money(total)
                if wave == 2:
                    order['orderFulfillmentStatus'] = 'FULFILLED' if len(purchases) == 1 else 'IN_PROGRESS'
                    fulfillment = payload['fulfillments'][0]
                    fulfillment.update(fulfillmentId=f'FUL{numeric_id}', shipmentTrackingNumber=f'S02-EB-{numeric_id}',
                        lineItems=[dict(lineItemId=order['lineItems'][0]['lineItemId'], quantity=purchases[0][1])])
                    order['fulfillmentHrefs'] = [f'http://ebay-sim/sell/fulfillment/v1/order/{identity}/shipping_fulfillment/{fulfillment["fulfillmentId"]}']
            else:
                payload.update(receipt_id=numeric_id, buyer_user_id=900000+buyer)
                template = payload['transactions'][0]
                payload['transactions'] = [dict(copy.deepcopy(template), transaction_id=base*1000000+index*10+n,
                    receipt_id=numeric_id, listing_id=720000+p[0], product_id=820000+p[0],
                    sku=f'ET-S02-{p[0]:03d}', title=p[1], quantity=q,
                    price=dict(amount=p[3], divisor=100, currency_code='USD'))
                    for n, (p, q) in enumerate(purchases)]
                for key in ('total_price', 'subtotal', 'grandtotal'):
                    payload[key]['amount'] = total
                if wave == 2:
                    payload['shipments'][0].update(receipt_shipping_id=numeric_id, tracking_code=f'S02-ET-{numeric_id}')
                op['notify'] = index % 2 == 0
            out.append(op)
    return out
