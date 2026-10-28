"""Real-scheduler polling probes; fixture/golden data is not an acquisition input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime,timezone,timedelta

import psycopg
from ingestion.website import db_kwargs
from orchestration.website_workflow import identity

p=argparse.ArgumentParser()
p.add_argument('action',choices=('scheduled','idle','publication','signature','checkpoint','trigger','state','retry','manifest','check_retry','check_failed','clear','cleared','budget','artifact'))
p.add_argument('--source',choices=('internal_web','ebay_sim'),default='ebay_sim')
p.add_argument('--execution-id',default='unused')
p.add_argument('--test-failure',action='store_true')
p.add_argument('--since',default='1970-01-01T00:00:00+00:00')
a=p.parse_args()
dag='website_polling' if a.source=='internal_web' else 'ebay_polling_replay'
workflow=identity(f'poll:{a.source}:{a.execution_id}','workflow')
batch=identity(f'poll:{a.source}:{a.execution_id}','batch')


def db(user='platform_ingest'):
    return psycopg.connect(**db_kwargs('PLATFORM','data_platform',user))


def meta():
    return psycopg.connect(host='postgres',dbname='airflow_meta',user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD'])


if a.action=='scheduled':
    with meta() as m:
        rows=m.execute("SELECT dag_id,run_id FROM dag_run WHERE dag_id IN ('website_polling','ebay_polling') AND run_type='scheduled' AND state='success' AND start_date >= %s ORDER BY logical_date",(datetime.fromisoformat(a.since.replace('Z','+00:00')),)).fetchall()
    for d in ('website_polling','ebay_polling'):
        successful=[run for name,run in rows if name==d]
        if len(successful)<2:
            print('waiting');break
    else:
        with meta() as m:
            assert m.execute("""SELECT count(*) FROM dag_run a JOIN dag_run b ON a.dag_id<>b.dag_id
                WHERE a.dag_id='website_polling' AND b.dag_id='ebay_polling'
                  AND a.run_type='scheduled' AND b.run_type='scheduled'
                  AND a.state='success' AND b.state='success' AND a.start_date >= %s AND b.start_date >= %s
                  AND a.start_date < b.end_date AND b.start_date < a.end_date""",(a.since,a.since)).fetchone()[0]>0, 'no overlapping DAG runs observed'
        with db() as c:
            cycles=c.execute('''SELECT p.run_id,p.source_system,p.airflow_dag_id,p.airflow_run_id,
                p.requested_window_start,p.requested_window_end,c.validation_mode,p.batch_id,c.overlap_seconds
                FROM ops.polling_cycles c JOIN ops.pipeline_runs p USING(run_id) WHERE p.status='SUCCEEDED' ''').fetchall()
            scheduled=[row for row in cycles if (row[2],row[3]) in rows]
            for source in ('internal_web','ebay_sim'):
                source_cycles=sorted([row for row in scheduled if row[1]==source],key=lambda row:row[5])
                assert len(source_cycles)>=2
                assert all(row[6]=='runtime' and row[4]<row[5] for row in source_cycles)
                for row in source_cycles:
                    assert c.execute('SELECT validation_mode,status FROM ops.transform_batches WHERE batch_id=%s',(row[7],)).fetchone()==('runtime','PUBLISHED')
                # Checkpoint overlap survives later scheduled intervals.
                assert source_cycles[1][4] == source_cycles[0][5]-timedelta(seconds=source_cycles[1][8])
            assert c.execute("""SELECT count(*) FROM ops.transform_batches a JOIN ops.transform_batches b
                ON a.batch_id<>b.batch_id WHERE a.status='PUBLISHED' AND b.status='PUBLISHED'
                AND a.manifest_frozen_at < b.published_at AND b.manifest_frozen_at < a.published_at""").fetchone()[0]==0, 'release critical sections interleaved'
        print('success')
elif a.action=='idle':
    with meta() as m:
        active=m.execute("SELECT count(*) FROM task_instance WHERE dag_id IN ('website_polling','ebay_polling') AND state='running'").fetchone()[0]
    with db() as c:
        active+=c.execute("SELECT count(*) FROM ops.pipeline_runs WHERE airflow_dag_id IN ('website_polling','ebay_polling') AND status='RUNNING'").fetchone()[0]
    print('waiting' if active else 'idle')
elif a.action=='publication':
    with db('platform_publisher') as c:
        print(c.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='ebay_orders'").fetchone()[0])
elif a.action=='signature':
    result={}
    with db('platform_publisher') as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for table in ('core.order_snapshot_history','core.order_line_snapshot_history','core.orders_current','core.order_lines_current','mart.order_activity_daily','mart.product_activity_daily','mart.order_status_current'):
            result[table]=[r[0] for r in c.execute(f"SELECT to_jsonb(t)-'batch_id'-'published_batch_id' FROM {table} t ORDER BY (to_jsonb(t)-'batch_id'-'published_batch_id')::TEXT")]
    print(hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest())
elif a.action=='checkpoint':
    with db() as c:
        print(c.execute("SELECT successful_run_id FROM ops.extraction_checkpoints WHERE source_system=%s AND stream_name='orders'",(a.source,)).fetchone()[0])
elif a.action=='trigger':
    conf={'inject_test_failure':a.test_failure,'fault_after_raw_once':not a.test_failure,'fault_after_freeze_once':not a.test_failure}
    subprocess.run(['airflow','dags','trigger',dag,'--run-id',a.execution_id,'--logical-date',datetime.now(timezone.utc).isoformat(),'--conf',json.dumps(conf)],check=True)
elif a.action in ('state','retry','cleared'):
    with meta() as m:
        if a.action=='state':
            row=m.execute('SELECT state FROM dag_run WHERE dag_id=%s AND run_id=%s',(dag,a.execution_id)).fetchone()
        else:
            row=m.execute("SELECT state,try_number FROM task_instance WHERE dag_id=%s AND run_id=%s AND task_id='cycle'",(dag,a.execution_id)).fetchone()
            if a.action=='cleared' and (not row or row[1]<6):
                row=None
    print(row[0] if row else 'waiting')
elif a.action=='manifest':
    with db() as c:
        ids=c.execute('SELECT raw_record_id FROM ops.batch_inputs WHERE batch_id=%s ORDER BY 1',(batch,)).fetchall()
        print(hashlib.sha256(','.join(str(r[0]) for r in ids).encode()).hexdigest() if ids else 'waiting')
elif a.action in ('check_retry','check_failed','budget','artifact'):
    with db() as c:
        counts=dict(c.execute('SELECT task_name,count(*) FROM ops.task_attempts WHERE run_id=%s GROUP BY task_name',(workflow,)).fetchall())
        bounds=c.execute('SELECT requested_window_start,requested_window_end FROM ops.pipeline_runs WHERE run_id=%s',(workflow,)).fetchone()
        assert bounds and bounds[0]<=bounds[1]
        if a.action=='check_retry':
            assert counts=={'collect':2,'freeze':2,'build_and_test':1,'publish':1},counts
            assert c.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(batch,)).fetchone()==('PUBLISHED',)
        elif a.action in ('check_failed','budget'):
            assert counts['build_and_test']==5,counts
            assert c.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(batch,)).fetchone()==('FAILED',)
            report=json.loads((Path('/opt/project/transformations/target')/str(batch)/'run_results.json').read_text())
            failures=[r for r in report['results'] if r['status'] not in ('pass','success')]
            assert len(failures)==1 and failures[0]['unique_id']=='test.multi_channel_orders.injected_failure',failures
    if a.action=='artifact':
        artifact=json.loads((Path('/opt/project/transformations/target')/str(batch)/'run_results.json').read_text())
        assert artifact['args']['vars']['validation_mode']=='runtime'
    print('PASS')
elif a.action=='clear':
    with meta() as m:
        date=m.execute('SELECT logical_date FROM dag_run WHERE dag_id=%s AND run_id=%s',(dag,a.execution_id)).fetchone()[0]
        end=date+timedelta(seconds=1)
        assert m.execute('SELECT count(*) FROM dag_run WHERE dag_id=%s AND logical_date >=%s AND logical_date <%s',(dag,date,end)).fetchone()[0]==1
    subprocess.run(['airflow','tasks','clear',dag,'--start-date',date.isoformat(),'--end-date',end.isoformat(),'--task-regex','cycle','--downstream','--yes'],check=True)
    print('cleared')
