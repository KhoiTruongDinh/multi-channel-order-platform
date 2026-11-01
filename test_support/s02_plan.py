"""Prepare source-only lifecycle schedules before playback; no DB/HTTP writes."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import random

from test_support.s02_diverse import diverse_inputs, references
from test_support.s02_inputs import stamp, ACCOUNTS
from simulator.s02_temporal import split_document

VERSION = 's02-temporal-v1'


def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def moment(op):
    p=op['payload']
    if op['source']=='internal_web': return p['orders'][0]['updated_at']
    if op['source']=='ebay_sim': return p['order']['lastModifiedDate']
    return stamp(datetime.fromtimestamp(p['updated_timestamp'],timezone.utc))


def plan(seed, identity, start, orders_per_channel=4, duration_seconds=86400):
    if type(duration_seconds) is not int or not 30 <= duration_seconds <= 86400:
        raise ValueError('duration must be integer30..86400 seconds')
    if start.tzinfo is None:
        raise ValueError('aware UTC start required')
    start=start.astimezone(timezone.utc).replace(microsecond=0)
    initial=diverse_inputs(seed,1,start,identity,orders_per_channel=orders_per_channel)
    final_templates=diverse_inputs(seed,2,start,identity,start+timedelta(seconds=duration_seconds),orders_per_channel)
    rng=random.Random(seed)
    events=[]
    for position,template in enumerate(initial):
        index=position//3
        # Initial data and independent arrivals; do not force every order per tick.
        arrival=0 if index==0 else rng.randint(1,max(1,duration_seconds//3))
        first=start+timedelta(seconds=arrival)
        second=first+timedelta(seconds=rng.randint(1,max(1,duration_seconds//4)))
        last=second+timedelta(seconds=rng.randint(1,max(1,duration_seconds//4)))
        if index==1:
            # One progressing sentinel/source remains observable through cold
            # Airflow startup + first serialized releases. Others stay independent.
            first=start+timedelta(seconds=rng.randint(1,max(1,duration_seconds//20)))
            second=start+timedelta(seconds=duration_seconds*2//3+rng.randint(0,max(1,duration_seconds//12)))
            last=start+timedelta(seconds=duration_seconds*5//6+rng.randint(1,max(1,duration_seconds//12)))
        candidates=[]
        op=copy.deepcopy(template)
        source=op['source']
        if source=='internal_web':
            op['payload']['orders'][0]['cancellation_status']='NOT_REQUESTED'
            op['payload']['cancellation_requests']=[]
        candidates.append((first,op))
        # Guarantee one initial pending order and one progressing order per source;
        # remaining branch choices are seeded rather than tied to every wave.
        progress=index!=0 and (index==1 or rng.random()>=0.25)
        if progress:
            intermediate=copy.deepcopy(template)
            final=copy.deepcopy(final_templates[position])
            if source=='internal_web':
                for candidate in (intermediate,final):
                    candidate['payload']['cancellation_requests'][0]['requested_at']=stamp(second)
                candidates.extend(((second,intermediate),(last,final)))
            elif source=='ebay_sim':
                candidates.append((second if len(final['payload']['order']['lineItems'])>1 else last,final))
                if len(final['payload']['order']['lineItems'])>1:
                    complete=copy.deepcopy(final)
                    order=complete['payload']['order']
                    order['orderFulfillmentStatus']='FULFILLED'
                    for line in order['lineItems']: line['lineItemFulfillmentStatus']='FULFILLED'
                    fulfillment=copy.deepcopy(complete['payload']['fulfillments'][0])
                    fulfillment.update(fulfillmentId=fulfillment['fulfillmentId']+'-REST',
                        lineItems=[dict(lineItemId=l['lineItemId'],quantity=l['quantity']) for l in order['lineItems'][1:]])
                    complete['payload']['fulfillments'].append(fulfillment)
                    order['fulfillmentHrefs'].append(order['fulfillmentHrefs'][0]+'-REST')
                    candidates.append((last,complete))
            else:
                candidates.append((last,final))
        for sequence,(visible,op) in enumerate(candidates,1):
            p=op['payload']; updated=stamp(visible)
            # Mix old initial orders with genuinely new arrivals, not one shared
            # creation timestamp. Purchase time stays fixed through all versions.
            created=start-timedelta(days=7) if index==0 else first
            if source=='internal_web':
                p['orders'][0].update(created_at=stamp(created),updated_at=updated)
                for item in p['order_items']:
                    item.update(created_at=stamp(created),updated_at=stamp(created))
                for payment in p['payment_transactions']:
                    payment.update(occurred_at=stamp(created),updated_at=stamp(created))
                for row in p['cancellation_requests']:
                    row['updated_at']=updated
                    if row['status']=='APPROVED': row['resolved_at']=updated
            elif source=='ebay_sim':
                p['order']['creationDate']=stamp(created)
                p['order']['lastModifiedDate']=updated
                for f in p['fulfillments']:
                    # Earlier shipment dates stay stable in the cumulative collection.
                    f['shippedDate']=stamp(second if len(p['order']['lineItems'])>1 and not f['fulfillmentId'].endswith('-REST') else last)
            else:
                p['created_timestamp']=int(created.timestamp())
                for transaction in p['transactions']: transaction['paid_timestamp']=int(created.timestamp())
                p['updated_timestamp']=int(visible.timestamp())
                if p['is_shipped']:
                    p['shipments'][0]['shipment_notification_timestamp']=int(visible.timestamp())
                    for t in p['transactions']: t['shipped_timestamp']=int(visible.timestamp())
            events.append(dict(sequence=sequence,visible_at=updated,**op))
    events.sort(key=lambda e:(e['visible_at'],e['source'],e['order_id'],e['sequence']))
    value=dict(version=VERSION,id=identity,seed=seed,start=stamp(start),
        duration_seconds=duration_seconds,orders_per_channel=orders_per_channel,
        mapping_version='s02-catalog-v1',references=references(),events=events)
    return value


def latest(value, at):
    result={}
    for e in value['events']:
        if datetime.fromisoformat(e['visible_at'].replace('Z','+00:00'))<=at:
            result[e['source'],e['order_id']]=e
    return list(result.values())


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value,bool): return 'TRUE' if value else 'FALSE'
    return "'"+str(value).replace("'","''")+"'"


def prepare_sql(value):
    """Atomic insert+seal. Scope checks must be enforced by the host harness first."""
    config={k:v for k,v in value.items() if k not in ('events','references')}
    cid=literal(value['id'])
    statements=['BEGIN;',f"INSERT INTO s02.campaigns(id,seed,config,checksum) VALUES ({cid},{value['seed']},{literal(json.dumps(config))}::jsonb,{literal(checksum(value))});"]
    seen_orders,seen_components={},set()
    for e in value['events']:
        if e['source']=='internal_web': continue
        source=e['source']; base,header,components=split_document(source,e['payload'])
        key=(value['id'],source,ACCOUNTS[source],e['order_id'])
        keys=','.join(map(literal,key))
        digest=checksum(components)
        if key not in seen_orders:
            statements.append(f'INSERT INTO s02.orders VALUES ({keys},{literal(json.dumps(base))}::jsonb);')
            seen_orders[key]=base
        elif seen_orders[key]!=base:
            raise ValueError('purchase/base changed without a base revision')
        if (key,digest) not in seen_components:
            statements.append(f'INSERT INTO s02.components VALUES ({keys},{literal(digest)},{literal(json.dumps(components))}::jsonb);')
            seen_components.add((key,digest))
        statements.append(f"INSERT INTO s02.versions VALUES ({keys},{e['sequence']},{literal(e['visible_at'])},{literal(moment(e))},{literal(json.dumps(header))}::jsonb,{literal(digest)});")
        if source=='etsy_sim':
            message=f"s02-{value['id']}-{e['order_id']}-{e['sequence']}"
            kind='order.shipped' if e['payload']['is_shipped'] else 'order.paid'
            statements.append(f"INSERT INTO s02.deliveries(campaign_id,message_id,receipt_id,due_at,event_type,omitted) VALUES ({cid},{literal(message)},{literal(e['order_id'])},{literal(e['visible_at'])},{literal(kind)},{literal(not e['notify'])});")
    statements.extend([f'UPDATE s02.campaigns SET sealed=TRUE WHERE id={cid};','COMMIT;'])
    return '\n'.join(statements)


def mapping_sql(value):
    fields=list(value['references']['mapping'][0])
    values=[ '('+','.join(literal(r[k]) for k in fields)+')' for r in value['references']['mapping'] ]
    return 'BEGIN; INSERT INTO config.product_mapping ('+','.join(fields)+') VALUES '+','.join(values)+'; COMMIT;'
