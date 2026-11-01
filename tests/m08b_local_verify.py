"""Read-only source-shaped final reconciliation of a completed local probe."""
import json
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import m08a as guard
from test_support.m08b import reconcile
from test_support.s02_oracle import facts
from tools.s02_data.references import references
from simulator.s02_temporal import assemble


def run(identity):
    h=guard.Harness(identity)
    evidence=json.loads((h.root/'evidence/local-probe.json').read_text())
    guard.require(evidence['status']=='PASS','completed PASS probe required')
    owner=guard.owner_container(); protected=guard.protected_signature(owner)
    result=dict(id=identity,scope='retained read-only final source/current reconciliation',status='RUNNING')
    def rows(sql,db='data_platform'):
        return json.loads(h.sql("SELECT coalesce(json_agg(t),'[]') FROM ("+sql+") t;",db),parse_float=Decimal)
    try:
        h.dc(['up','--detach','--wait','--wait-timeout','180','postgres']); h.test_db()
        actual=dict(orders=rows('SELECT * FROM core.orders_current'),lines=rows('SELECT * FROM core.order_lines_current'))
        ops=[]
        for row in rows('SELECT DISTINCT ON(order_id) order_id,payload FROM s02.website_versions ORDER BY order_id,sequence DESC','marketplace_sim'):
            ops.append(dict(source='internal_web',order_id=row['order_id'],payload=row['payload']))
        for row in rows('SELECT DISTINCT ON(v.source,v.order_id) v.source,v.order_id,o.base,v.header,c.body FROM s02.versions v JOIN s02.orders o USING(campaign_id,source,account_id,order_id) JOIN s02.components c ON c.campaign_id=v.campaign_id AND c.source=v.source AND c.account_id=v.account_id AND c.order_id=v.order_id AND c.digest=v.component_digest ORDER BY v.source,v.order_id,v.sequence DESC','marketplace_sim'):
            ops.append(dict(source=row['source'],order_id=row['order_id'],payload=assemble(row['source'],row['base'],row['header'],row['body'])))
        assert reconcile(actual,ops,facts_fn=lambda op:facts(op,references()['mapping'])),'source/current facts differ'
        assert rows("SELECT count(*) AS n FROM ops.processing_work WHERE state<>'SUCCEEDED'")[0]['n']==0
        assert rows('SELECT count(*) AS n FROM ops.data_exceptions WHERE resolved_at IS NULL')[0]['n']==0
        assert not rows('SELECT h.snapshot_id FROM core.order_snapshot_history h LEFT JOIN core.snapshot_evidence e USING(snapshot_id) GROUP BY h.snapshot_id HAVING count(e.raw_record_id)=0')
        result.update(status='PASS',orders=len(actual['orders']),lines=len(actual['lines']),
            units=sum(l['quantity'] for l in actual['lines']),gross=str(sum(l['line_gross_amount'] for l in actual['lines'])))
    except BaseException as error:
        result.update(status='FAIL',error=str(error)); raise
    finally:
        h.dc(['down','--remove-orphans','--timeout','30'])
        result['owner_unchanged']=guard.protected_signature(owner)==protected
        result['steps']=h.steps
        (h.root/'evidence/local-final-readonly.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='steps'}))
    assert result['owner_unchanged']


if __name__=='__main__': run(sys.argv[1])
