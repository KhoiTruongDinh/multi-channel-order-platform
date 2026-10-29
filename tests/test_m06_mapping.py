"""Evaluate the compiled dbt line model with literal nullable-product inputs only."""
import copy
import json
from pathlib import Path
import re
import uuid
from psycopg.types.json import Jsonb
from transformation.batch import connect

with connect() as c:
    batch=c.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='etsy_orders'").fetchone()[0]
    root=Path('/app/transformations/target')
    sql=(root/str(batch)/'compiled/multi_channel_orders/models/etsy/etsy_candidate_order_line_snapshot_history.sql').read_text()
    replacement="(SELECT %s::JSONB AS order_json,%s::UUID AS snapshot_id,'etsy_sim'::TEXT AS source_system,'7001'::TEXT AS source_account_id)"
    sql,count=re.subn(r'"[^"]+"\."build"\."int_etsy_versions"',replacement,sql)
    assert count==1,'compiled source reference changed; inspect before testing'
    base=json.loads(Path('/repo/fixtures/s01/source_states/etsy/0905.json').read_text())
    for keep_sku,expected in ((True,'CONFIRMED'),(False,'UNMAPPED')):
        value=copy.deepcopy(base)
        for key in ('listing_id','product_id','title'):
            value['transactions'][0][key]=None
        if not keep_sku:
            value['transactions'][0]['sku']=None
        row=c.execute(sql,(Jsonb(value),uuid.uuid4())).fetchone()
        assert row[7]==expected and row[8]==1 and row[10]==22,row
        assert row[2] is None and row[3] is None and row[5] is None
print('M06 actual dbt model nullable-product / scoped SKU fallback / UNMAPPED line preservation PASS')
