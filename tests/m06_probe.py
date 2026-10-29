"""Read-only S01 and operational acceptance probes for retained local data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import psycopg

from ingestion.etsy_common import connect
from transformation.publish import connect as published

p=argparse.ArgumentParser()
p.add_argument('action',choices=('check','signature','deliveries','work','scheduled','idle','publication','preflight','drain_ready','schedule_ready'))
p.add_argument('--since',default='1970-01-01T00:00:00Z')
a=p.parse_args()

if a.action=='preflight':
    with connect() as c:
        assert c.execute("SELECT count(*) FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchone()[0]==0,'Finish/explicitly fail active batch first'
        assert c.execute("SELECT count(*) FROM ops.pipeline_runs WHERE status='RUNNING' AND stage='RECOVER' AND airflow_dag_id IS NOT NULL").fetchone()[0]==0,'Active workflow exists'
    with psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD']) as c:
        assert not c.execute("SELECT dag_id FROM dag WHERE dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery') AND NOT is_paused").fetchall(),'Pause schedules before S01 runner'
    print('M06 S01 preflight PASS')
elif a.action=='publication':
    with published() as c:
        print(c.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='etsy_orders'").fetchone()[0])
elif a.action=='signature':
    with published() as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        output={}
        for table in ('core.orders_current','core.order_lines_current','core.order_snapshot_history','mart.order_activity_daily'):
            output[table]=[r[0] for r in c.execute(f"SELECT to_jsonb(t)-'batch_id'-'published_batch_id' FROM {table} t WHERE source_system<>'etsy_sim' ORDER BY (to_jsonb(t)-'batch_id'-'published_batch_id')::TEXT")]
        print(hashlib.sha256(json.dumps(output,sort_keys=True).encode()).hexdigest())
elif a.action=='check':
    with published() as c:
        assert c.execute("SELECT count(*) FROM core.order_snapshot_history WHERE source_system='etsy_sim'").fetchone()[0]==1
        assert c.execute("SELECT source_order_id,payment_state,fulfillment_state,cancellation_state,source_order_total_amount FROM core.orders_current WHERE source_system='etsy_sim'").fetchone()==('9001001','PAID','SHIPPED','UNKNOWN',22)
        assert c.execute("SELECT source_line_id,canonical_variant_id,quantity,line_gross_amount FROM core.order_lines_current WHERE source_system='etsy_sim'").fetchone()==('8001001','V002',1,22)
        assert c.execute('SELECT count(*) FROM core.orders_current').fetchone()[0]==3
        assert c.execute('SELECT count(*),sum(quantity),sum(line_gross_amount) FROM core.order_lines_current').fetchone()==(4,6,124)
        assert c.execute('SELECT count(*) FROM core.order_snapshot_history').fetchone()[0]==6
        assert c.execute('SELECT count(*) FROM core.order_line_snapshot_history').fetchone()[0]==8
    with connect() as c:
        subscription=os.environ.get('ETSY_SUBSCRIPTION_ID','local-s01')
        inbox=c.execute("SELECT webhook_id,fetch_state FROM ops.webhook_inbox WHERE source_system='etsy_sim' AND subscription_id=%s AND webhook_id IN ('msg_paid_001','msg_shipped_001')",(subscription,)).fetchall()
        assert sorted(inbox)==[('msg_paid_001','SUCCEEDED'),('msg_shipped_001','SUCCEEDED')],inbox
        for message,_ in inbox:
            assert c.execute('SELECT count(*) FROM ops.etsy_work_context WHERE cycle_id=%s',(f'inbox:{subscription}:{message}',)).fetchone()[0]==1
    print('M06 S01 PASS: 3 orders / 4 lines / 6 units / USD124 / 6 observed versions')
elif a.action in ('deliveries','work'):
    with connect() as c:
        if a.action=='deliveries':
            print(c.execute("SELECT count(*) FROM ops.webhook_delivery_attempts WHERE source_system='etsy_sim' AND accepted").fetchone()[0])
        else:
            for row in c.execute("SELECT state,cycle_attempts,count(*) FROM ops.processing_work WHERE work_type='ETSY_RECEIPT' GROUP BY state,cycle_attempts ORDER BY 1,2"):
                print(row)
elif a.action=='scheduled':
    with psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD']) as c:
        rows=dict(c.execute("SELECT dag_id,count(*) FROM dag_run WHERE dag_id IN ('etsy_inbox','etsy_recovery') AND run_type='scheduled' AND state='success' AND start_date>=%s GROUP BY dag_id",(a.since,)))
    complete=all(rows.get(d,0)>=2 for d in ('etsy_inbox','etsy_recovery'))
    if complete:
        with connect() as c:
            assert c.execute("""SELECT count(*) FROM ops.transform_batches a JOIN ops.transform_batches b
                ON a.batch_id<>b.batch_id WHERE a.status='PUBLISHED' AND b.status='PUBLISHED'
                AND a.manifest_frozen_at < b.published_at AND b.manifest_frozen_at < a.published_at""").fetchone()[0]==0
            windows=c.execute("""SELECT p.requested_window_start,p.requested_window_end,x.overlap_seconds
                FROM ops.polling_cycles x JOIN ops.pipeline_runs p USING(run_id)
                WHERE p.airflow_dag_id='etsy_recovery' AND p.status='SUCCEEDED' AND p.started_at>=%s
                ORDER BY p.requested_window_end""",(a.since,)).fetchall()
            assert len(windows)>=2
            from datetime import timedelta
            assert windows[1][0]==windows[0][1]-timedelta(seconds=windows[1][2])
            assert not c.execute("""SELECT 1 FROM ops.pipeline_runs WHERE airflow_dag_id='etsy_inbox'
                AND (requested_window_start IS NOT NULL OR requested_window_end IS NOT NULL)""").fetchone()
            assert c.execute("""SELECT 1 FROM ops.processing_work w JOIN ops.etsy_work_context x USING(work_id)
                JOIN ops.pipeline_runs p ON p.run_id=x.run_id WHERE w.state='SUCCEEDED'
                AND w.inbox_id IS NULL AND x.cycle_id LIKE 'recovery:%%' AND p.started_at>=%s""",(a.since,)).fetchone()
            assert c.execute("""SELECT 1 FROM ops.webhook_inbox i JOIN ops.processing_work w USING(inbox_id)
                WHERE i.webhook_id LIKE 'm06_schedule_%%-inbox' AND i.first_received_at>=%s
                  AND i.fetch_state='SUCCEEDED' AND w.state='SUCCEEDED'""",(a.since,)).fetchone(),'fresh scheduled inbox work not drained'
        with psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD']) as c:
            assert c.execute("""SELECT 1 FROM dag_run a JOIN dag_run b ON a.dag_id<>b.dag_id
                WHERE a.dag_id IN ('etsy_inbox','etsy_recovery') AND b.dag_id IN ('website_polling','ebay_polling')
                  AND a.run_type='scheduled' AND b.run_type='scheduled' AND a.state='success' AND b.state='success'
                  AND a.start_date>=%s AND b.start_date>=%s AND a.start_date<b.end_date AND b.start_date<a.end_date LIMIT 1""",(a.since,a.since)).fetchone()
    print('success' if complete else 'waiting')
elif a.action in ('drain_ready','schedule_ready'):
    with psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD']) as c:
        rows=c.execute("""SELECT DISTINCT ON (dag_id) dag_id,data->'dag'->'timetable'->>'__type'
            FROM serialized_dag WHERE dag_id IN ('etsy_inbox','etsy_recovery','website_polling','ebay_polling')
            ORDER BY dag_id,created_at DESC""").fetchall()
    expected='NullTimetable' if a.action=='drain_ready' else 'DeltaTriggerTimetable'
    print('ready' if len(rows)==4 and all(kind and kind.endswith('.'+expected) for _,kind in rows) else 'waiting')
elif a.action=='idle':
    with connect() as c:
        count=c.execute("SELECT count(*) FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchone()[0]
        count+=c.execute("SELECT count(*) FROM ops.pipeline_runs WHERE status='RUNNING' AND airflow_dag_id IN ('etsy_inbox','etsy_recovery','etsy_replay','website_polling','ebay_polling')").fetchone()[0]
    # A queued run or retry may not have allocated a platform parent/batch yet.
    with psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD']) as c:
        count+=c.execute("""SELECT count(*) FROM dag_run WHERE state IN ('queued','running')
            AND dag_id IN ('etsy_inbox','etsy_recovery','etsy_replay','website_polling','ebay_polling')""").fetchone()[0]
    print('waiting' if count else 'idle')
