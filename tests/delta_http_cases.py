"""Real SQL/HTTP collector-to-publication probes in disposable PostgreSQL only."""
import argparse
import copy
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import pstats
import subprocess
import sys
import threading
import time
from unittest.mock import patch


def check(plans,root,admin,rounds=1):
    import psycopg
    from orchestration import polling,coordinator
    from simulator import ebay_api,etsy_api
    from simulator.s02_store import Store
    from simulator.website_playback import TABLES,DELETE_ORDER,insert_rows,validate
    assert os.environ['PLATFORM_DB_HOST'].startswith('delta-pg-')
    # `python -m` puts cwd before PYTHONPATH. Refuse measuring image-baked
    # collectors while the coordinator imports the read-only review mount.
    subprocess.run([sys.executable,'-c',
        'from pathlib import Path; from ingestion import website,ebay,etsy; '
        'assert all(Path(m.__file__).resolve().is_relative_to(Path("/review")) '
        'for m in (website,ebay,etsy)), "collector source path mismatch"'],
        check=True)
    states=root/'fixtures/s01/source_states'
    with patch.dict(os.environ,{'SIMULATOR_MODE':'s01'}):
        ebay=ebay_api.State(states/'ebay')
        etsy=etsy_api.State(states/'etsy')
    servers=[]; counts={'ebay':0,'etsy':0}
    def serve(kind,handler):
        class Counted(handler):
            def do_GET(self):
                counts[kind]+=1
                return super().do_GET()
        server=ThreadingHTTPServer(('127.0.0.1',0),Counted)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        servers.append(server)
        return 'http://127.0.0.1:'+str(server.server_port)
    ebay_origin=serve('ebay',ebay_api.handlers(ebay)[0])
    etsy_origin=serve('etsy',etsy_api.handlers(etsy)[0])
    samples=[]
    with admin() as conn:
        baseline=dict(conn.execute('SELECT source_system,count(*) FROM core.orders_current GROUP BY source_system').fetchall())
    generated=0
    try:
        with patch.dict(os.environ,dict(POLLING_DELTA_PLAN_DIR='/tmp/delta-plans',
                EBAY_ORIGIN=ebay_origin,EBAY_PUBLIC_ORIGIN=ebay_origin,
                ETSY_ORIGIN=etsy_origin,ETSY_SIM_TOKEN='disposable',
                WEBSITE_DB_HOST=os.environ['PLATFORM_DB_HOST'],WEBSITE_READER_PASSWORD='disposable')):
            for wave,n in enumerate((1,10,100)*rounds,1):
                generated+=n
                stamp=datetime.now(timezone.utc)
                iso=stamp.isoformat()
                # Test setup only: source current-state documents, no warehouse
                # expected answers. Prior warehouse/raw history remains retained.
                web_base=json.loads((states/'website/0901.json').read_text())
                web={table:copy.deepcopy(web_base[table]) if table in ('customers','products','product_variants') else [] for table in TABLES}
                ebay.s02=Store('ebay'); etsy.s02=Store('etsy')
                for i in range(n):
                    identity=f'LOAD{wave}_{i}'
                    order=copy.deepcopy(web_base['orders'][0]); order.update(order_id=identity,order_number=identity,updated_at=iso)
                    item=copy.deepcopy(web_base['order_items'][0]); item.update(order_id=identity,order_item_id='I'+identity)
                    payment=copy.deepcopy(web_base['payment_transactions'][0]); payment.update(order_id=identity,payment_transaction_id='P'+identity,provider_reference='REF'+identity)
                    web['orders'].append(order); web['order_items'].append(item); web['payment_transactions'].append(payment)
                    doc=json.loads((states/'ebay/0902.json').read_text())
                    doc['order']['orderId']=f'12-80{wave:02}{i:05}-10001'
                    doc['order']['lastModifiedDate']=iso
                    for j,line in enumerate(doc['order']['lineItems']): line['lineItemId']=str(80000000+wave*100000+i*10+j)
                    ebay.s02.upsert(doc)
                    receipt=copy.deepcopy(etsy.receipt)
                    receipt['receipt_id']=80000000+wave*100000+i
                    receipt['updated_timestamp']=int(stamp.timestamp())
                    for j,line in enumerate(receipt['transactions']):
                        line['receipt_id']=receipt['receipt_id']; line['transaction_id']=70000000+wave*100000+i*10+j
                    for j,shipment in enumerate(receipt['shipments']):
                        shipment['receipt_shipping_id']=60000000+wave*100000+i*10+j
                    etsy.s02.upsert(receipt)
                validate(web)
                with psycopg.connect(host=os.environ['PLATFORM_DB_HOST'],dbname='website_source',user='postgres') as source:
                    with source.cursor() as cursor:
                        for table in DELETE_ORDER: cursor.execute('DELETE FROM public.'+table)
                        for table in TABLES: insert_rows(cursor,table,web[table])
                for source in plans:
                    # Etsy API uses integer seconds; include this wave without
                    # relying on sub-second timestamp precision or sleeping.
                    end=datetime.now(timezone.utc)
                    a=argparse.Namespace(source=source,execution_id=f'http-wave-{wave}-{source}',dag_id='delta_http_probe',
                        airflow_run_id=f'scheduled__wave_{wave}',window_end=end,initial_start=end-timedelta(hours=1),
                        mapping_version='s01-v1',transformation_version='legacy',overlap_seconds=1,
                        wait_seconds=60,nonblocking=True,reuse_cycle_config=True,abort=False,
                        coordinator_attempt=1,page_size=50,fault_after_raw_once=False,
                        fault_after_freeze_once=False,inject_test_failure=False,collection_mode='recovery',checkpoint_stream=None)
                    polling.prepare(a)
                    before=dict(counts)
                    start=time.monotonic()
                    profile=None
                    if source=='etsy_sim' and n==100 and os.environ.get('DELTA_PROFILE_ETSY')=='1':
                        from orchestration import website_workflow as workflow
                        original=workflow.command
                        profile=Path('/tmp/delta-etsy-100.pstats')
                        def profiled(module,*argv):
                            if module=='ingestion.etsy':
                                subprocess.run([sys.executable,'-m','cProfile','-o',str(profile),'-m',module,*map(str,argv)],check=True)
                            else: original(module,*argv)
                        # Instrument the real CLI only; all HTTP, SQL, raw/work
                        # writes and checkpoints remain the actual collector.
                        with patch.object(workflow,'command',side_effect=profiled): coordinator.coordinate(a)
                    else:
                        coordinator.coordinate(a)
                    with admin() as conn:
                        publication={'internal_web':'website_orders','ebay_sim':'ebay_orders','etsy_sim':'etsy_orders'}[source]
                        assert conn.execute('SELECT batch_id FROM ops.publication_state WHERE publication_name=%s',(publication,)).fetchone()[0]==a.batch_id
                        dirty=conn.execute('SELECT count(*) FROM ops.delta_batch_keys WHERE batch_id=%s',(a.batch_id,)).fetchone()[0]
                        assert dirty==n,(source,n,dirty)
                        retained=conn.execute('SELECT count(*) FROM core.orders_current WHERE source_system=%s',
                                              (source,)).fetchone()[0]
                        assert retained==baseline.get(source,0)+generated,(source,retained,generated)
                        clock=conn.execute('''SELECT extract(epoch FROM
                            max(finished_at) FILTER(WHERE stage='publish' AND outcome='SUCCEEDED')-
                            min(started_at) FILTER(WHERE stage='collect')) FROM ops.execution_measurements
                            WHERE run_id=%s''',(a.workflow_id,)).fetchone()[0]
                        phases=conn.execute('''SELECT stage,duration_ms FROM ops.execution_measurements
                            WHERE run_id=%s AND outcome='SUCCEEDED' ORDER BY started_at''',(a.workflow_id,)).fetchall()
                    samples.append(dict(source=source,changed_orders=n,wall_upper_bound_seconds=time.monotonic()-start,
                        retained_source_orders=retained,
                        collect_to_publish_stage_seconds=float(clock),phase_ms=dict(phases),
                        http_requests={k:counts[k]-before[k] for k in counts},
                        scope='real collectors + coordinator + compiled dbt + observed publication; disposable source/warehouse'))
                    if profile:
                        stats=pstats.Stats(str(profile)).stats
                        hot=sorted(((key,value) for key,value in stats.items() if '/ingestion/' in key[0]),key=lambda item:item[1][3],reverse=True)[:14]
                        samples[-1]['collector_profile']=[dict(function=key[2],file=Path(key[0]).name,calls=value[1],self_seconds=value[2],cumulative_seconds=value[3]) for key,value in hot]
                        for key,value in stats.items():
                            if key[2]=='execute' and key[0].endswith('psycopg/connection.py'):
                                samples[-1]['sql_by_caller']=[dict(function=caller[2],file=Path(caller[0]).name,calls=data[0],cumulative_seconds=data[-1]) for caller,data in value[4].items() if '/ingestion/' in caller[0]]
                        samples[-1]['instrumented']=True
    finally:
        for server in servers: server.shutdown(); server.server_close()
    maximum=max(sample['wall_upper_bound_seconds'] for sample in samples)
    return dict(status='PASS',samples=samples,
        latency=dict(status='PASS' if maximum<=10 else 'FAIL',target_seconds=10,
                     maximum_wall_upper_bound_seconds=maximum,
                     violations=sum(sample['wall_upper_bound_seconds']>10 for sample in samples),
                     scope='these finite healthy samples only; not sustained/owner900/scheduler acceptance'),
        qualification='correctness/profiling only; finite small retained test history, not owner 900 workload or Airflow scheduler')
