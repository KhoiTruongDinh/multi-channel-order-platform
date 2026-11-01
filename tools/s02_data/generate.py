"""Order-first, independently seeded, causal lifecycle generation; bounded per order."""
import copy
import hashlib
from datetime import timedelta

from tools.s02_data.config import BRANCHES, parse_time, sample_time, segments, stream, validate, zone
from tools.s02_data.references import diverse_inputs, references
from test_support.s02_inputs import stamp


def campaign_id(name):
    return hashlib.sha256(name.encode()).hexdigest()[:12]


def order_events(config,source,index,ref):
    c=config['channels'][source]
    identity=campaign_id(config['dataset'])
    rng=stream(config['order_seed'],source,index,'purchase')
    erng=stream(config['event_seed'],source,index,'lifecycle')
    reserved=index<sum(c['required'].values())
    offset=index
    branch=None
    for candidate,n in c['required'].items():
        if offset<n:
            branch=candidate; break
        offset-=n
    if branch is None:
        branch=erng.choices(list(c['branches']),weights=list(c['branches'].values()))[0]
    start,end=map(parse_time,(c['start_at'],c['end_at']))
    # Required cases reserve feasible time. All other arrivals retain full distribution.
    bound=end-timedelta(seconds=BRANCHES[source][branch]*c['delay_seconds'][1]) if reserved else end
    created=sample_time(segments(start,bound,zone(c['timezone']),c['peak_hours']),rng)
    seed=rng.randrange(2147483648)
    selection=dict(source=source,index=index,base=int(identity[:6],16)*100000,
                   basket=c['basket'],references=ref)
    first=diverse_inputs(seed,1,created,identity,orders_per_channel=2,selection=selection)[0]
    final=diverse_inputs(seed,2,created,identity,orders_per_channel=2,selection=selection)[0]
    if source=='internal_web':
        first['payload']['orders'][0]['cancellation_status']='NOT_REQUESTED'
        first['payload']['cancellation_requests']=[]
    candidates=[first]
    if branch!='pending':
        if source=='internal_web':
            requested=copy.deepcopy(final)
            requested['payload']['orders'][0]['cancellation_status']='REQUESTED'
            requested['payload']['cancellation_requests'][0].update(status='PENDING',resolved_at=None)
            candidates.append(requested)
            if branch=='cancel': candidates.append(final)
        elif source=='ebay_sim':
            if len(final['payload']['order']['lineItems'])>1: candidates.append(copy.deepcopy(final))
            if branch=='ship':
                full=copy.deepcopy(final); order=full['payload']['order']
                order['orderFulfillmentStatus']='FULFILLED'
                for line in order['lineItems']: line['lineItemFulfillmentStatus']='FULFILLED'
                if len(order['lineItems'])>1:
                    rest=copy.deepcopy(full['payload']['fulfillments'][0])
                    rest['fulfillmentId']+='-REST'
                    rest['lineItems']=[dict(lineItemId=l['lineItemId'],quantity=l['quantity']) for l in order['lineItems'][1:]]
                    full['payload']['fulfillments'].append(rest)
                    order['fulfillmentHrefs'].append(order['fulfillmentHrefs'][0]+'-REST')
                candidates.append(full)
        else: candidates.append(final)
    at=created; emitted=[]; request_at=None; first_shipped=None
    for sequence,op in enumerate(candidates,1):
        if sequence>1: at+=timedelta(seconds=erng.randint(*c['delay_seconds']))
        if at>=end: break
        p=op['payload']; updated=stamp(at); born=stamp(created)
        if source=='internal_web':
            p['orders'][0].update(created_at=born,updated_at=updated)
            for row in p['order_items']: row.update(created_at=born,updated_at=born)
            for row in p['payment_transactions']: row.update(occurred_at=born,updated_at=born)
            for row in p['cancellation_requests']:
                request_at=request_at or updated
                row.update(requested_at=request_at,updated_at=updated,resolved_at=updated if row['status']=='APPROVED' else None)
        elif source=='ebay_sim':
            p['order'].update(creationDate=born,lastModifiedDate=updated)
            for f in p['fulfillments']:
                first_shipped=first_shipped or updated
                f['shippedDate']=updated if f['fulfillmentId'].endswith('-REST') else first_shipped
        else:
            p.update(created_timestamp=int(created.timestamp()),updated_timestamp=int(at.timestamp()))
            for row in p['transactions']:
                row.update(paid_timestamp=int(created.timestamp()),shipped_timestamp=int(at.timestamp()) if p['is_shipped'] else None)
            for row in p['shipments']: row['shipment_notification_timestamp']=int(at.timestamp())
            op['notify']=index>=c['notifications'].get('omit',0)
        op.update(sequence=sequence,visible_at=updated,case=branch,
                  duplicate=source=='etsy_sim' and c['notifications'].get('omit',0)<=index<sum(c['notifications'].values()))
        emitted.append(op)
    return emitted


def events(config):
    ref=references()
    for source,c in config['channels'].items():
        for index in range(c['orders']):
            yield order_events(config,source,index,ref)


def normalized(value):
    return validate(value)
