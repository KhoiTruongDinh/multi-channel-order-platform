"""Rollback-only eBay evidence parity and execution plans; no shared writes."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BATCH = '00000000-0000-0000-0000-000000000001'


def render(sql):
    from jinja2 import Environment, StrictUndefined
    return Environment(undefined=StrictUndefined).from_string(sql).render(
        ref=lambda name: {'int_ebay_versions': 'pg_temp.probe_versions',
                          'stg_ebay_observations': 'pg_temp.probe_observations'}[name],
        source=lambda schema, name: {'raw_records': 'pg_temp.probe_raw',
                                    'batch_inputs': 'pg_temp.probe_inputs'}[name],
        var=lambda name, default=None: False if name=='delta_mode' else BATCH,
        batch_uuid=lambda: "'"+BATCH+"'::UUID")


def compare(conn, queries):
    for name, sql in queries.items():
        conn.execute(f'DROP TABLE IF EXISTS pg_temp.result_{name}')
        conn.execute(f'CREATE TEMP TABLE result_{name} AS '+sql)
    assert not conn.execute('''SELECT EXISTS(
        (SELECT * FROM result_old EXCEPT ALL SELECT * FROM result_new)
        UNION ALL (SELECT * FROM result_new EXCEPT ALL SELECT * FROM result_old))''').fetchone()[0], 'evidence multiset mismatch'
    return conn.execute('SELECT count(*) FROM result_new').fetchone()[0]


def run(old, new, retained_limit=600, samples=4):
    import os
    import psycopg
    from psycopg.types.json import Jsonb
    import uuid
    from datetime import datetime, timezone
    result = {'scope': 'rollback temp SQL; not full dbt/load acceptance',
              'hashes': {k: hashlib.sha256(v.encode()).hexdigest() for k,v in [('old',old),('new',new)]},
              'retained_limit':retained_limit,'samples':samples,'parity': [], 'benchmarks': []}
    queries = {'old': render(old), 'new': render(new)}
    with psycopg.connect(host=os.environ.get('PLATFORM_DB_HOST','postgres'),
                        port=int(os.environ.get('PLATFORM_DB_PORT','5432')),
                        dbname='data_platform',user='platform_transform',
                        password=os.environ['PLATFORM_TRANSFORM_PASSWORD']) as conn:
        try:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            conn.execute("SET LOCAL statement_timeout='60s'")
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute('''CREATE TEMP TABLE probe_raw(raw_record_id uuid PRIMARY KEY,
                run_id uuid,resource_type text,byte_sha256 bytea,acquired_at timestamptz,
                metadata jsonb,parsed_payload jsonb,response_status integer)''')
            conn.execute('CREATE TEMP TABLE probe_inputs(batch_id uuid,raw_record_id uuid PRIMARY KEY)')
            conn.execute('''CREATE TEMP TABLE probe_observations(snapshot_id uuid,source_account_id text,
                order_json jsonb,content_fingerprint bytea,run_id uuid,raw_record_id uuid)''')
            conn.execute('CREATE TEMP TABLE probe_versions AS SELECT * FROM probe_observations WITH NO DATA')
            now=datetime.now(timezone.utc)
            def synthetic(size):
                conn.execute('TRUNCATE probe_raw,probe_inputs,probe_observations,probe_versions')
                run_id=uuid.UUID(int=1)
                for n in range(size):
                    rid=uuid.UUID(int=n+100); sid=uuid.UUID(int=n+100000)
                    payload={'orderId':str(n),'lastModifiedDate':'2026-11-12T00:00:00Z'}
                    values=(sid,'seller_sim_01',Jsonb(payload),b'x'*32,run_id,rid)
                    conn.execute('INSERT INTO probe_versions VALUES(%s,%s,%s,%s,%s,%s)',values)
                    # Repeated acquisitions and a different account/fingerprint must not lose scope.
                    conn.execute('INSERT INTO probe_observations VALUES(%s,%s,%s,%s,%s,%s)',values)
                    conn.execute('INSERT INTO probe_observations VALUES(%s,%s,%s,%s,%s,%s)',values)
                    for raw_id,resource,metadata,data,status in (
                        (rid,'ebay_order',{},payload,200),
                        (uuid.UUID(int=n+10000),'ebay_fulfillments',{'order_raw_id':str(rid)},{},200),
                        (uuid.UUID(int=n+20000),'ebay_orders',{}, {'orders':[payload,payload]},200),
                        (uuid.UUID(int=n+30000),'ebay_order',{'order_raw_id':str(rid)},payload,500)):
                        conn.execute('INSERT INTO probe_raw VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                                     (raw_id,run_id,resource,b'x'*32,now,Jsonb(metadata),Jsonb(data),status))
                conn.execute('INSERT INTO probe_inputs SELECT %s,raw_record_id FROM probe_raw',(BATCH,))
                conn.execute('ANALYZE probe_raw'); conn.execute('ANALYZE probe_observations')
                conn.execute('ANALYZE probe_versions'); conn.execute('ANALYZE probe_inputs')
            for size in (0,1,20,100,300):
                synthetic(size)
                rows=compare(conn,queries)
                assert rows==size*3, (size,rows)
                result['parity'].append({'case':f'synthetic-{size}','rows':rows})
                if size not in (100,300): continue
                times={'old':[],'new':[]}; plans={}
                for trial in range(samples):
                    for name in (('old','new') if trial%2==0 else ('new','old')):
                        plan=conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+queries[name]).fetchone()[0][0]
                        times[name].append(plan['Execution Time']); plans[name]=plan
                result['benchmarks'].append({'orders':size,'milliseconds':times,
                    'median_ms':{k:statistics.median(v) for k,v in times.items()},'plans':plans})
            synthetic(2)
            # The OR branches may overlap; final DISTINCT must still emit each link once.
            conn.execute("UPDATE probe_raw SET metadata=jsonb_build_object('order_raw_id',raw_record_id::text) WHERE resource_type='ebay_order'")
            conn.execute("INSERT INTO probe_observations SELECT snapshot_id,'wrong-account',order_json,content_fingerprint,run_id,raw_record_id FROM probe_versions")
            conn.execute("INSERT INTO probe_observations SELECT snapshot_id,source_account_id,order_json,decode(repeat('00',32),'hex'),run_id,raw_record_id FROM probe_versions")
            assert compare(conn,queries)==6
            result['parity'].append({'case':'overlapping-branches-account-hash-scope','rows':6})
            conn.execute("DELETE FROM probe_inputs WHERE raw_record_id IN (SELECT raw_record_id FROM probe_raw WHERE resource_type='ebay_fulfillments')")
            assert compare(conn,queries)==4
            result['parity'].append({'case':'missing-manifest-members','rows':4})
            conn.execute("UPDATE probe_raw SET parsed_payload='{}'::jsonb WHERE resource_type='ebay_orders'")
            assert compare(conn,queries)==2
            result['parity'].append({'case':'missing-list-array','rows':2})
            conn.execute("UPDATE probe_raw SET parsed_payload='{\"orders\":{}}'::jsonb WHERE resource_type='ebay_orders'")
            errors=[]
            for sql in queries.values():
                try:
                    with conn.transaction(): conn.execute(sql).fetchall()
                except psycopg.Error as error: errors.append(error.sqlstate)
                else: errors.append(None)
            assert errors==['22023','22023'],errors
            result['parity'].append({'case':'invalid-list-array','sqlstates':errors})
            synthetic(1)
            # Unrelated collection pages, even malformed ones, are outside this evidence join.
            conn.execute("INSERT INTO probe_raw VALUES(%s,%s,'ebay_orders',%s,%s,'{}','{\"orders\":{}}',200)",
                         (uuid.UUID(int=999999),uuid.UUID(int=999999),b'x'*32,now))
            conn.execute('INSERT INTO probe_inputs VALUES(%s,%s)',(BATCH,uuid.UUID(int=999999)))
            assert compare(conn,queries)==3
            result['parity'].append({'case':'unrelated-run-malformed-page-excluded','rows':3})
            # Use immutable published raw/manifest, not shared build tables:
            # other source cycles legitimately rebuild eBay staging as empty.
            conn.execute('TRUNCATE probe_raw,probe_inputs,probe_observations,probe_versions')
            retained_batch=conn.execute('''SELECT b.batch_id FROM ops.transform_batches b
                JOIN ops.pipeline_runs p USING(run_id)
                WHERE p.source_system='ebay_sim' AND b.status='PUBLISHED'
                ORDER BY b.manifest_frozen_at DESC LIMIT 1''').fetchone()
            assert retained_batch, 'a published retained eBay batch is required'
            conn.execute('''INSERT INTO probe_observations
                SELECT NULL::uuid,r.source_account_id,r.parsed_payload,
                       sha256(convert_to(build.canonical_jsonb_text(build.ebay_canonical_json(r.parsed_payload)),'UTF8')),
                       r.run_id,r.raw_record_id
                  FROM raw.raw_records r JOIN ops.batch_inputs i USING(raw_record_id)
                 WHERE i.batch_id=%s AND r.source_system='ebay_sim'
                   AND r.source_account_id='seller_sim_01' AND r.resource_type='ebay_order'
                   AND r.response_status=200 AND EXISTS (
                       SELECT 1 FROM raw.raw_records f JOIN ops.batch_inputs fi USING(raw_record_id)
                        WHERE fi.batch_id=i.batch_id AND f.run_id=r.run_id
                          AND f.resource_type='ebay_fulfillments' AND f.response_status=200
                          AND f.metadata->>'order_raw_id'=r.raw_record_id::text)
                 ORDER BY r.acquired_at DESC,r.raw_record_id LIMIT %s''',(retained_batch[0],retained_limit))
            assert conn.execute('SELECT count(*) FROM probe_observations').fetchone()[0]>0, 'retained eBay input is empty; do not claim parity'
            conn.execute('''INSERT INTO probe_versions
                SELECT DISTINCT ON (source_account_id,order_json->>'orderId',order_json->>'lastModifiedDate',content_fingerprint)
                    md5(concat_ws(chr(31),'ebay_sim',source_account_id,order_json->>'orderId',
                    order_json->>'lastModifiedDate',encode(content_fingerprint,'hex')))::uuid,
                    source_account_id,order_json,content_fingerprint,run_id,raw_record_id
                FROM probe_observations ORDER BY source_account_id,order_json->>'orderId',
                    order_json->>'lastModifiedDate',content_fingerprint,raw_record_id''')
            conn.execute('''INSERT INTO probe_raw
                SELECT r.raw_record_id,r.run_id,r.resource_type,r.byte_sha256,r.acquired_at,
                       r.metadata,r.parsed_payload,r.response_status FROM raw.raw_records r
                 WHERE r.run_id IN (SELECT run_id FROM probe_observations)
                   AND EXISTS (SELECT 1 FROM ops.batch_inputs i
                                WHERE i.raw_record_id=r.raw_record_id AND i.batch_id=%s)''',(retained_batch[0],))
            conn.execute('INSERT INTO probe_inputs SELECT %s,raw_record_id FROM probe_raw',(BATCH,))
            # TRUNCATE preserves old statistics. Refresh after replacing synthetic
            # rows with retained inputs so planner estimates describe this sample.
            for relation in ('probe_raw','probe_inputs','probe_observations','probe_versions'):
                conn.execute('ANALYZE '+relation)
            retained=compare(conn,queries)
            result['parity'].append({'case':'retained-observations','rows':retained,
                'observations':conn.execute('SELECT count(*) FROM probe_observations').fetchone()[0],
                'frozen_batch':str(retained_batch[0])})
            times={'old':[],'new':[]}; plans={}
            for trial in range(samples):
                for name in (('old','new') if trial%2==0 else ('new','old')):
                    plan=conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+queries[name]).fetchone()[0][0]
                    times[name].append(plan['Execution Time']); plans[name]=plan
            result['benchmarks'].append({'orders':'retained','milliseconds':times,
                'median_ms':{k:statistics.median(v) for k,v in times.items()},'plans':plans})
            # Reproduce the low cardinality estimate of a rank=1 version view;
            # a perfectly analyzed versions table alone can hide bad join choices.
            conn.execute('''CREATE TEMP VIEW probe_ranked_versions AS SELECT * FROM (
                SELECT v.*,row_number() OVER (PARTITION BY snapshot_id ORDER BY raw_record_id) AS rank
                FROM probe_versions v) x WHERE rank=1''')
            view_queries={k:v.replace('pg_temp.probe_versions','pg_temp.probe_ranked_versions') for k,v in queries.items()}
            assert compare(conn,view_queries)==retained
            times={'old':[],'new':[]}; plans={}
            for trial in range(samples):
                for name in (('old','new') if trial%2==0 else ('new','old')):
                    plan=conn.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+view_queries[name]).fetchone()[0][0]
                    times[name].append(plan['Execution Time']); plans[name]=plan
            result['benchmarks'].append({'orders':'retained-ranked-view','milliseconds':times,
                'median_ms':{k:statistics.median(v) for k,v in times.items()},'plans':plans})
            result['status']='PASS'
        finally:
            conn.rollback()
    print(json.dumps(result),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container',required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--retained-limit',type=int,default=600)
    parser.add_argument('--samples',type=int,default=4)
    args=parser.parse_args()
    if args.report.exists(): parser.error('report exists; choose a new path')
    if not 1<=args.retained_limit<=4000 or not 1<=args.samples<=4:
        parser.error('retained-limit must be1..4000 and samples1..4')
    payload={'old':(ROOT/'tests/sql/ebay_evidence_before.sql').read_text(),
             'new':(ROOT/'transformations/models/ebay/ebay_candidate_snapshot_evidence.sql').read_text(),
             'script':Path(__file__).read_text(),'retained_limit':args.retained_limit,'samples':args.samples}
    bootstrap="import json,sys; p=json.load(sys.stdin); n={'__name__':'probe','__file__':'/opt/project/tests/ebay_evidence_probe.py'}; exec(compile(p.pop('script'),n['__file__'],'exec'),n); n['run'](**p)"
    done=subprocess.run(['docker','exec','-i',args.container,'/opt/airflow/project-venv/bin/python','-c',bootstrap],
                        input=json.dumps(payload),text=True,capture_output=True,timeout=600)
    if done.returncode: raise RuntimeError(done.stdout+done.stderr)
    result=json.loads(done.stdout.splitlines()[-1])
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='benchmarks'}))
    for row in result['benchmarks']: print(json.dumps({'orders':row['orders'],'median_ms':row['median_ms']}))


if __name__=='__main__': main()
