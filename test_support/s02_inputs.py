"""Seeded source inputs, not warehouse answers; host/test-only module."""
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1] / 'fixtures/s01/source_states'
VERSION = 's02-v1'
ACCOUNTS = {'internal_web':'WEB01', 'ebay_sim':'seller_sim_01', 'etsy_sim':'7001'}


def stamp(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def inputs(seed, wave, at, run_id, updated_at=None):
    if type(seed) is not int or not 0 <= seed <= 2147483647 or wave not in (1, 2):
        raise ValueError('invalid bounded seed/wave')
    rng = random.Random(seed)
    clock = updated_at or at
    created, updated = stamp(at-timedelta(days=7)), stamp(clock)
    # Stable purchase time across both waves; source ordering time advances.
    out = []
    base = int(run_id[:8], 16) % 10000000 + 10000000
    for index in range(2):
        quantities = [rng.randint(1,3), rng.randint(1,3)]
        web = json.loads((ROOT/'website/0910.json').read_text())
        order = web['orders'][0]
        identity = f'12-{base+index:08d}-10001'  # Deliberately collides across channels, never within one.
        order.update(order_id=identity, order_number=identity, created_at=created, updated_at=updated,
            items_gross_amount=str(20*sum(quantities)), order_total_amount=str(20*sum(quantities)),
            cancellation_status='REQUESTED' if wave==1 else 'CANCELED')
        item = web['order_items'][0]
        web['order_items'] = [dict(item, order_item_id=f'{identity}-L{n}', order_id=identity,
            quantity=q, created_at=created, updated_at=created) for n,q in enumerate(quantities)]
        web['payment_transactions'][0].update(payment_transaction_id=identity+'-PAY', order_id=identity,
            amount=str(20*sum(quantities)), occurred_at=created, updated_at=created)
        web['cancellation_requests'][0].update(cancellation_id=identity+'-CAN', order_id=identity,
            status='PENDING' if wave==1 else 'APPROVED', requested_at=stamp(at-timedelta(seconds=2)),
            resolved_at=None if wave==1 else updated, updated_at=updated)
        # Stable request/purchase facts across waves are supplied by caller's epoch.
        out.append(dict(source='internal_web', order_id=identity, payload=web))

        ebay = json.loads((ROOT/'ebay/0912.json').read_text())
        order = ebay['order']; identity = f'12-{base+index:08d}-10001'
        order.update(orderId=identity, creationDate=created, lastModifiedDate=updated,
            orderFulfillmentStatus='NOT_STARTED' if wave==1 else 'IN_PROGRESS')
        for n,(line,q,price) in enumerate(zip(order['lineItems'], quantities, (20,22))):
            line.update(lineItemId=str(base*10+index*2+n), quantity=q,
                lineItemFulfillmentStatus='FULFILLED' if wave==2 and n==0 else 'NOT_STARTED')
            line['lineItemCost']['value'] = str(q*price)
        total = str(quantities[0]*20 + quantities[1]*22)
        order['pricingSummary']['priceSubtotal']['value'] = total
        order['pricingSummary']['total']['value'] = total
        if wave==1:
            ebay['fulfillments'], order['fulfillmentHrefs'] = [], []
        else:
            f = ebay['fulfillments'][0]
            f.update(fulfillmentId=f'FUL{base+index}', shippedDate=updated,
                     lineItems=[dict(lineItemId=order['lineItems'][0]['lineItemId'],quantity=quantities[0])])
            order['fulfillmentHrefs'] = [f'http://ebay-sim/sell/fulfillment/v1/order/{identity}/shipping_fulfillment/{f["fulfillmentId"]}']
        out.append(dict(source='ebay_sim', order_id=identity, payload=ebay))

        etsy = json.loads((ROOT/'etsy/0905.json').read_text())
        identity = base+index
        etsy.update(receipt_id=identity, created_timestamp=int((at-timedelta(days=7)).timestamp()),
            updated_timestamp=int(clock.timestamp()), is_shipped=wave==2,
            status='paid' if wave==1 else 'completed')
        transaction = etsy['transactions'][0]
        etsy['transactions'] = [dict(copy.deepcopy(transaction), transaction_id=base*10+index*2+n,
            receipt_id=identity, quantity=q, paid_timestamp=etsy['created_timestamp'],
            shipped_timestamp=None if wave==1 else int(clock.timestamp())) for n,q in enumerate(quantities)]
        for key in ('total_price','subtotal','grandtotal'):
            etsy[key]['amount'] = 2200*sum(quantities)
        if wave==1:
            etsy['shipments'] = []
        else:
            etsy['shipments'][0].update(receipt_shipping_id=base+index, shipment_notification_timestamp=int(clock.timestamp()))
        out.append(dict(source='etsy_sim', order_id=str(identity), payload=etsy, notify=index==0))
    return out


def purchase_facts(operation):
    """Independent test oracle: does not call dbt/production normalization code."""
    source, p = operation['source'], operation['payload']
    if source=='internal_web':
        o=p['orders'][0]
        lines=[(r['order_item_id'],r['quantity'],Decimal(r['unit_price']),'V001') for r in p['order_items']]
        states=('PAID','NOT_STARTED',o['cancellation_status'])
        total=Decimal(o['order_total_amount'])
        created, updated=o['created_at'],o['updated_at']
    elif source=='ebay_sim':
        o=p['order']
        lines=[(r['lineItemId'],r['quantity'],Decimal(r['lineItemCost']['value'])/r['quantity'],
                'V001' if r['legacyVariationId']=='610001' else 'V002') for r in o['lineItems']]
        states=('PAID','PARTIALLY_SHIPPED' if p['fulfillments'] else 'NOT_STARTED','NOT_REQUESTED')
        total=Decimal(o['pricingSummary']['total']['value']); created,updated=o['creationDate'],o['lastModifiedDate']
    else:
        lines=[(str(r['transaction_id']),r['quantity'],Decimal(r['price']['amount'])/r['price']['divisor'],'V002') for r in p['transactions']]
        states=('PAID','SHIPPED' if p['is_shipped'] else 'NOT_STARTED','UNKNOWN')
        total=Decimal(p['grandtotal']['amount'])/p['grandtotal']['divisor']
        created,updated=(stamp(datetime.fromtimestamp(p[k],timezone.utc)) for k in ('created_timestamp','updated_timestamp'))
    gross=sum(q*price for _,q,price,_ in lines)
    return dict(source=source,account=ACCOUNTS[source],order_id=operation['order_id'],lines=lines,
                states=states,total=total,gross=gross,created=created,updated=updated,currency='USD')
