"""Read-only M05 assertions; only tests may inspect golden fixtures."""
import argparse
import hashlib
import json
import os
import psycopg
from transformation.publish import connect

p = argparse.ArgumentParser()
p.add_argument('action', choices=('preflight','website','checkpoint','check','audit','publication'))
p.add_argument('--execution-id', default='')
a = p.parse_args()
connection = (psycopg.connect(host=os.environ.get('PLATFORM_DB_HOST','postgres'),dbname='data_platform',
    user='platform_ingest',password=os.environ['PLATFORM_INGEST_PASSWORD'])
    if a.action in ('checkpoint','audit') else connect())
with connection as conn:
    conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    if a.action in ('website','preflight'):
        assert conn.execute("SELECT count(*) FROM core.order_snapshot_history WHERE source_system='internal_web'").fetchone()[0] == 3
        tables = ('core.order_snapshot_history','core.order_line_snapshot_history','core.orders_current',
                  'core.order_lines_current','mart.order_activity_daily','mart.product_activity_daily','mart.order_status_current')
        payload = {}
        for table in tables:
            condition = "snapshot_id IN (SELECT snapshot_id FROM core.order_snapshot_history WHERE source_system='internal_web')" if table == 'core.order_line_snapshot_history' else "source_system='internal_web'"
            payload[table] = [r[0] for r in conn.execute(f'SELECT to_jsonb(t) FROM {table} t WHERE {condition} ORDER BY to_jsonb(t)::TEXT').fetchall()]
        print(hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest())
    elif a.action == 'checkpoint':
        row = conn.execute("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system='ebay_sim' AND source_account_id='seller_sim_01' AND stream_name='orders'").fetchone()
        print(str(row[0]) if row else 'none')
    elif a.action == 'publication':
        row = conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='ebay_orders'").fetchone()
        print(str(row[0]) if row else 'none')
    elif a.action == 'audit':
        runs = conn.execute("SELECT run_id,status FROM ops.pipeline_runs WHERE log_reference LIKE %s",(f'm05:{a.execution_id}%',)).fetchall()
        assert runs and any(status=='FAILED' for _,status in runs)
        failed_ids = [r for r,s in runs if s=='FAILED']
        assert conn.execute('SELECT count(*) FROM raw.raw_records WHERE run_id=ANY(%s)',(failed_ids,)).fetchone()[0] > 0
        assert not conn.execute('SELECT 1 FROM ops.extraction_checkpoints WHERE successful_run_id=ANY(%s)',(failed_ids,)).fetchone()
        assert conn.execute("SELECT count(*) FROM raw.raw_records WHERE run_id=ANY(%s) AND response_status=500",([r for r,s in runs],)).fetchone()[0] >= 5
        bad = conn.execute("SELECT r.metadata->>'http_attempt' FROM raw.raw_records r JOIN ops.pipeline_runs p USING(run_id) WHERE p.log_reference=%s AND r.response_status=500 ORDER BY (r.metadata->>'http_attempt')::INTEGER",(f'm05:{a.execution_id}-badpage',)).fetchall()
        assert bad==[(str(i),) for i in range(1,6)], bad
        pages = conn.execute("SELECT r.parsed_payload->>'offset' FROM raw.raw_records r JOIN ops.pipeline_runs p USING(run_id) WHERE p.log_reference=%s AND r.resource_type='ebay_orders' AND r.response_status=200 ORDER BY (r.parsed_payload->>'offset')::INTEGER",(f'm05:{a.execution_id}-paged',)).fetchall()
        assert pages==[('0',),('1',)], pages
        assert conn.execute("SELECT count(*) FROM ops.processing_work w JOIN ops.pipeline_runs p ON w.dedupe_key LIKE 'm05:'||p.run_id::TEXT||':%%' WHERE p.log_reference=%s AND w.state='SUCCEEDED'",(f'm05:{a.execution_id}-paged',)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM ops.processing_work w JOIN ops.pipeline_runs p ON w.dedupe_key LIKE 'm05:'||p.run_id::TEXT||':%%' WHERE p.log_reference=%s AND w.state='FAILED'",(f'm05:{a.execution_id}-interrupted',)).fetchone()[0]==1
        for raw, checksum, headers in conn.execute('SELECT raw_bytes,byte_sha256,sanitized_headers FROM raw.raw_records WHERE run_id=ANY(%s)',([r for r,s in runs],)):
            assert hashlib.sha256(raw).digest()==checksum
            assert not any(k.lower()=='authorization' for k in headers)
        print('M05 raw failure/checkpoint audit PASS')
    elif a.action == 'check':
        assert conn.execute("SELECT count(*) FROM core.order_snapshot_history WHERE source_system='ebay_sim'").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM core.order_line_snapshot_history l JOIN core.order_snapshot_history h USING(snapshot_id) WHERE h.source_system='ebay_sim'").fetchone()[0] == 4
        assert conn.execute("SELECT payment_state,fulfillment_state,cancellation_state,source_order_total_amount,currency FROM core.orders_current WHERE source_system='ebay_sim'").fetchall() == [('PAID','PARTIALLY_SHIPPED','NOT_REQUESTED',62,'USD')]
        assert conn.execute("SELECT count(*),sum(quantity),sum(line_gross_amount) FROM core.order_lines_current WHERE source_system='ebay_sim'").fetchone() == (2,3,62)
        # M05 owns website/eBay totals; M06 independently checks all three channels.
        assert conn.execute("SELECT count(*) FROM core.orders_current WHERE source_system IN ('internal_web','ebay_sim')").fetchone()[0] == 2
        assert conn.execute("SELECT sum(quantity),sum(line_gross_amount) FROM core.order_lines_current WHERE source_system IN ('internal_web','ebay_sim')").fetchone() == (5,102)
        histories = conn.execute("SELECT source_updated_at,first_observed_at,fulfillment_state FROM core.order_snapshot_history WHERE source_system='ebay_sim' ORDER BY source_updated_at").fetchall()
        assert [r[2] for r in histories] == ['NOT_STARTED','PARTIALLY_SHIPPED']
        assert [r[1].isoformat() for r in histories] == ['2026-10-17T09:03:00+00:00','2026-10-17T09:13:00+00:00']
        for updated,_,state in histories:
            rows = conn.execute("SELECT l.source_line_id,l.fulfillment_evidence FROM core.order_line_snapshot_history l JOIN core.order_snapshot_history h USING(snapshot_id) WHERE h.source_system='ebay_sim' AND h.source_updated_at=%s",(updated,)).fetchall()
            evidence = dict(rows)
            if state=='PARTIALLY_SHIPPED':
                f = evidence['10001001']['fulfillments']
                assert len(f)==1 and f[0]['fulfillmentId']=='FUL001' and f[0]['lineItems']==[{'lineItemId':'10001001','quantity':2}]
            else:
                assert evidence['10001001']['fulfillments']==[]
            assert evidence['10001002']['fulfillments']==[]
        assert conn.execute("SELECT count(*) FROM core.snapshot_evidence e JOIN core.order_snapshot_history h USING(snapshot_id) WHERE h.source_system='ebay_sim' AND e.evidence_role='EBAY_FULFILLMENT'").fetchone()[0] >= 1
        print('M05 eBay observed history/current/allocation + website totals PASS')
