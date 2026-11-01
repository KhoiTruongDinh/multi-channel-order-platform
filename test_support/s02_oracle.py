"""Test-only catalog lookup and source facts; never imported by a simulator/DAG."""
from test_support.s02_inputs import purchase_facts


def facts(operation, mapping):
    value=purchase_facts(operation)
    source,p=operation['source'],operation['payload']
    if source=='internal_web':
        identifiers=[(None,l['variant_id'],l['sku_at_purchase']) for l in p['order_items']]
    elif source=='ebay_sim':
        identifiers=[(l['legacyItemId'],l['legacyVariationId'],l['sku']) for l in p['order']['lineItems']]
        ordered={l['lineItemId']:l['quantity'] for l in p['order']['lineItems']}
        allocated={key:0 for key in ordered}
        for f in p['fulfillments']:
            for l in f['lineItems']: allocated[l['lineItemId']]+=l['quantity']
        if any(allocated[k]>ordered[k] for k in ordered): raise ValueError('over-allocated shipment')
        sent=sum(allocated.values())
        fulfillment='NOT_STARTED' if sent==0 else 'SHIPPED' if sent==sum(ordered.values()) else 'PARTIALLY_SHIPPED'
        value['states']=(value['states'][0],fulfillment,value['states'][2])
    else:
        identifiers=[(str(l['listing_id']),str(l['product_id']),l['sku']) for l in p['transactions']]
    lines=[]
    for line,identity in zip(value['lines'],identifiers):
        matches=[r for r in mapping if r['source_system']==source and r['source_account_id']==value['account']
            and (r['source_listing_id'],r['source_variant_id'],r['source_sku'])==identity]
        if len(matches)!=1: raise ValueError('normal dataset requires one confirmed mapping')
        lines.append((*line[:3],matches[0]['canonical_variant_id']))
    value['lines']=lines
    return value
