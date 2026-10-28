"""Exercise the actual dbt fulfillment test SQL with disposable literal inputs."""
import copy
import json
from pathlib import Path
import uuid
from psycopg.types.json import Jsonb
from transformation.batch import connect

root = Path(__file__).resolve().parents[1]
base = json.loads((root/'fixtures/s01/source_states/ebay/0912.json').read_text())
query = (root/'transformations/tests/ebay_fulfillment_integrity.sql').read_text().replace(
    "{{ ref('stg_ebay_observations') }}", 'observations')


def failures(conn, values):
    inputs = []
    params = []
    for value in values:
        inputs.append("SELECT %s::UUID AS raw_record_id,'seller_sim_01'::TEXT AS source_account_id,%s::JSONB AS order_json,%s::JSONB AS shipping_json,decode('00','hex') AS content_fingerprint")
        params.extend((uuid.uuid4(),Jsonb(value['order']),Jsonb({'fulfillments':value['fulfillments']})))
    sql = 'WITH observations AS (' + ' UNION ALL '.join(inputs) + ') SELECT * FROM (' + query + ') checks'
    return conn.execute(sql,params).fetchall()


with connect() as conn:
    assert not failures(conn,[base])
    over = copy.deepcopy(base)
    over['fulfillments'][0]['lineItems'][0]['quantity']=3
    assert failures(conn,[over])
    unknown = copy.deepcopy(base)
    unknown['fulfillments'][0]['lineItems'][0]['lineItemId']='not-in-order'
    assert failures(conn,[unknown])
    future = copy.deepcopy(base)
    future['fulfillments'][0]['shippedDate']='2026-10-17T09:14:00Z'
    assert failures(conn,[future])
    conflict = copy.deepcopy(base)
    conflict['order']['lineItems'][0]['lineItemFulfillmentStatus']='NOT_STARTED'
    assert failures(conn,[conflict])
    inconsistent = copy.deepcopy(base)
    inconsistent['fulfillments']=[]
    assert failures(conn,[base,inconsistent])
    split = copy.deepcopy(base)
    other=copy.deepcopy(split['fulfillments'][0])
    other['fulfillmentId']='FUL002'
    other['lineItems'][0]['quantity']=1
    split['fulfillments'].append(other)
    assert failures(conn,[split])  # Aggregate across distinct parcels, not per parcel.
print('M05 fulfillment SQL constraints PASS: valid baseline + 6 invalid evidence cases')
