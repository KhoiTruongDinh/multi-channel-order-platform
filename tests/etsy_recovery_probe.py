"""Real local HTTP + PostgreSQL, all probe writes rolled back; no main SIM controls.

Run in the project Python environment with /repo mounted read-only. Not a dbt
publication or scheduler acceptance test. Source lists/detail are synthetic HTTP.
"""
import argparse
from datetime import datetime,timezone,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from unittest.mock import patch
import uuid
from psycopg.errors import CheckViolation

from ingestion import etsy
from ingestion.etsy_common import connect,start_run,raw_record,now,enqueue
from ingestion.etsy_recovery import PageSetChanged,begin_scan,page_history


class RollbackOnly:
    def __init__(self,conn): self.conn=conn
    def execute(self,*args): return self.conn.execute(*args)
    def commit(self): pass
    def rollback(self): pass


class Source(BaseHTTPRequestHandler):
    changing=True
    duplicate=False
    calls=[]
    receipt_reads=0
    total=2
    def log_message(self,*args): pass
    def do_GET(self):
        from urllib.parse import urlsplit,parse_qs
        q=parse_qs(urlsplit(self.path).query)
        if q:
            offset=int(q['offset'][0]); type(self).calls.append(offset)
            limit=int(q['limit'][0])
            count=1 if self.changing and offset==1 else self.total
            body=dict(count=count,results=[dict(receipt_id=100000000000+(0 if self.duplicate else n),
                updated_timestamp=stamp+n) for n in range(offset,min(offset+limit,self.total))])
        else:
            type(self).receipt_reads+=1
            body=json.loads((Path('/repo/fixtures/s01/source_states/etsy/0905.json')).read_text())
            body['receipt_id']=int(self.path.rsplit('/',1)[1])
            for transaction in body['transactions']: transaction['receipt_id']=body['receipt_id']
        raw=json.dumps(body).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)


def count(c,sql,run): return c.execute(sql,(run,)).fetchone()[0]


stamp=int((datetime.now(timezone.utc)-timedelta(minutes=1)).timestamp())
server=ThreadingHTTPServer(('127.0.0.1',0),Source)
thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
c=connect(); proxy=RollbackOnly(c)
identity='reconcile-probe-'+uuid.uuid4().hex; run=uuid.uuid4()
args=argparse.Namespace(execution_id=identity,window_start=datetime.fromtimestamp(stamp,timezone.utc),
    window_end=datetime.fromtimestamp(stamp+5,timezone.utc),observed_at=None,
    checkpoint_stream='receipts_test_'+uuid.uuid4().hex)
try:
    with patch.dict(os.environ,ETSY_ORIGIN='http://127.0.0.1:'+str(server.server_port)):
        start_run(proxy,run,args.checkpoint_stream,identity,(args.window_start,args.window_end))
        try: etsy.recover(proxy,args,run)
        except PageSetChanged: pass
        else: raise AssertionError('inconsistent count accepted')
        assert count(c,"SELECT count(*) FROM ops.etsy_recovery_scans WHERE run_id=%s AND status='INVALID'",run)==1
        assert count(c,"SELECT count(*) FROM raw.raw_records WHERE run_id=%s",run)==2
        assert c.execute('SELECT count(*) FROM ops.processing_work WHERE dedupe_key LIKE %s',('m06:recovery:'+identity+':%',)).fetchone()[0]==0
        assert count(c,'SELECT count(*) FROM ops.extraction_checkpoints WHERE successful_run_id=%s',run)==0
        Source.changing=False
        real_drain=etsy.drain
        with patch.object(etsy,'drain',side_effect=RuntimeError('probe processing interruption')):
            try: etsy.recover(proxy,args,run)
            except RuntimeError as error: assert str(error)=='probe processing interruption'
            else: raise AssertionError('processing interruption not exercised')
        assert count(c,"SELECT count(*) FROM ops.etsy_recovery_scans WHERE run_id=%s AND status='VALIDATED'",run)==1
        assert count(c,'SELECT count(*) FROM ops.extraction_checkpoints WHERE successful_run_id=%s',run)==0
        assert Source.calls==[0,1,0,1]
        # Actual HTTP receipt processing; successful list pages must not be fetched again.
        etsy.recover(proxy,args,run)
        assert Source.calls==[0,1,0,1] and Source.receipt_reads==2
        assert count(c,'SELECT count(*) FROM ops.extraction_checkpoints WHERE successful_run_id=%s',run)==1
        assert c.execute('SELECT max(attempt_number),count(*) FROM ops.etsy_http_attempts WHERE run_id=%s',(run,)).fetchone()==(2,4)
        assert c.execute("SELECT count(*) FROM ops.processing_work WHERE dedupe_key LIKE %s AND state='SUCCEEDED'",('m06:recovery:'+identity+':%',)).fetchone()[0]==2
        # A successful scan at a later source time cannot bypass the lifetime URL
        # budget: exhausted old-scan responses are NOT a fresh cache hit.
        from urllib.parse import urlencode
        limited=uuid.uuid4(); start_run(proxy,limited,args.checkpoint_stream,identity+'-limited')
        c.execute("INSERT INTO ops.etsy_recovery_scans(run_id,scan_number,status,finished_at,error_code) VALUES(%s,1,'INVALID',clock_timestamp(),'PAGE_SET_CHANGED')",(limited,))
        url=etsy.origin()+'/v3/application/shops/7001/receipts?'+urlencode(dict(
            min_last_modified=stamp,max_last_modified=stamp+5,limit=1,offset=0,sort_on='updated',sort_order='asc'))
        for attempt in range(1,6):
            raw,_=raw_record(proxy,limited,'etsy_receipts',url,'GET',200,b'{"count":2,"results":[]}',{})
            c.execute('''INSERT INTO ops.etsy_http_attempts(attempt_id,run_id,attempt_number,raw_record_id,
                recorded_at,collection_run_id,recovery_scan_number) VALUES(%s,%s,%s,%s,%s,%s,1)''',
                (uuid.uuid4(),limited,attempt,raw,now(),limited))
        with patch.object(etsy,'fetch',side_effect=AssertionError('HTTP budget reset')):
            for _ in range(2):
                try: etsy.recover(proxy,args,limited)
                except RuntimeError as error: assert 'recovery page failed' in str(error)
                else: raise AssertionError('exhausted URL accepted')
        assert count(c,'SELECT count(*) FROM ops.etsy_http_attempts WHERE run_id=%s',limited)==5
        assert count(c,'SELECT count(*) FROM ops.extraction_checkpoints WHERE successful_run_id=%s',limited)==0
        assert begin_scan(proxy,limited)==(2,'RUNNING')
        # Same-count duplicate/reordered identities require reconciliation too.
        Source.duplicate=True
        unsorted=uuid.uuid4(); start_run(proxy,unsorted,args.checkpoint_stream,identity+'-unsorted')
        try: etsy.recover(proxy,args,unsorted)
        except PageSetChanged as error: assert 'duplicate or unsorted' in str(error)
        else: raise AssertionError('duplicate recovery identity accepted')
        assert count(c,"SELECT count(*) FROM ops.etsy_recovery_scans WHERE run_id=%s AND status='INVALID'",unsorted)==1
        Source.duplicate=False
        # Legacy successful prefixes (no scan column) retain approved resume:
        # adopt once in scan1, fetch only the missing page, then real receipt work.
        legacy=uuid.uuid4(); legacy_args=argparse.Namespace(**vars(args))
        legacy_args.execution_id=identity+'-legacy'
        start_run(proxy,legacy,args.checkpoint_stream,legacy_args.execution_id)
        body=json.dumps(dict(count=2,results=[dict(receipt_id=100000000000,updated_timestamp=stamp)])).encode()
        raw,_=raw_record(proxy,legacy,'etsy_receipts',url,'GET',200,body,{})
        c.execute('''INSERT INTO ops.etsy_http_attempts(attempt_id,run_id,attempt_number,raw_record_id,
            recorded_at,collection_run_id) VALUES(%s,%s,1,%s,%s,%s)''',(uuid.uuid4(),legacy,raw,now(),legacy))
        before_calls=len(Source.calls)
        etsy.recover(proxy,legacy_args,legacy)
        assert Source.calls[before_calls:]==[1]
        assert count(c,"SELECT count(*) FROM ops.etsy_http_attempts WHERE run_id=%s AND recovery_scan_number IS NULL",legacy)==1
        # Interruption during paging resumes RUNNING, not an automatic fresh scan.
        interrupted=uuid.uuid4(); interrupted_args=argparse.Namespace(**vars(args))
        interrupted_args.execution_id=identity+'-interrupted'
        start_run(proxy,interrupted,args.checkpoint_stream,interrupted_args.execution_id)
        real_fetch=etsy.fetch
        def interrupt(url):
            if 'offset=1&' in url: raise RuntimeError('probe process interruption')
            return real_fetch(url)
        with patch.object(etsy,'fetch',side_effect=interrupt):
            try: etsy.recover(proxy,interrupted_args,interrupted)
            except RuntimeError as error: assert str(error)=='probe process interruption'
            else: raise AssertionError('paging interruption was not exercised')
        assert begin_scan(proxy,interrupted)==(1,'RUNNING')
        before_calls=len(Source.calls)
        etsy.recover(proxy,interrupted_args,interrupted)
        assert Source.calls[before_calls:]==[1]
        assert count(c,'SELECT count(*) FROM ops.etsy_recovery_scans WHERE run_id=%s',interrupted)==1
        # SQL NULL must not pass a CHECK as UNKNOWN for an INVALID scan.
        bad_error=uuid.uuid4(); start_run(proxy,bad_error,args.checkpoint_stream,identity+'-null-error')
        c.execute('SAVEPOINT missing_error')
        try:
            c.execute("""INSERT INTO ops.etsy_recovery_scans(run_id,scan_number,status,started_at,finished_at)
                VALUES(%s,1,'INVALID',clock_timestamp()-interval '1 second',clock_timestamp())""",(bad_error,))
        except CheckViolation: c.execute('ROLLBACK TO SAVEPOINT missing_error')
        else: raise AssertionError('INVALID scan accepted without error code')
        c.execute('RELEASE SAVEPOINT missing_error')
        # DB fences reject terminal audit mutation, deletion and a sixth scan.
        for sql in ("UPDATE ops.etsy_recovery_scans SET status='RUNNING',finished_at=NULL WHERE run_id=%s AND scan_number=2",
                    'DELETE FROM ops.etsy_recovery_scans WHERE run_id=%s'):
            c.execute('SAVEPOINT audit_fence')
            try: c.execute(sql,(run,))
            except Exception: c.execute('ROLLBACK TO SAVEPOINT audit_fence')
            else: raise AssertionError('terminal scan audit was mutable')
            c.execute('RELEASE SAVEPOINT audit_fence')
        exhausted=uuid.uuid4(); start_run(proxy,exhausted,args.checkpoint_stream,identity+'-exhausted')
        for n in range(1,6):
            c.execute("INSERT INTO ops.etsy_recovery_scans(run_id,scan_number,status,finished_at,error_code) VALUES(%s,%s,'INVALID',clock_timestamp(),'PAGE_SET_CHANGED')",(exhausted,n))
        try: begin_scan(proxy,exhausted)
        except RuntimeError as error: assert 'budget exhausted' in str(error)
        else: raise AssertionError('sixth scan allocated')
        # Real SQL cache/checkpoint semantics also support multiple receipts/page.
        Source.total=3
        paged=uuid.uuid4(); paged_args=argparse.Namespace(**vars(args))
        paged_args.execution_id=identity+'-paged'; paged_args.page_size=2
        start_run(proxy,paged,args.checkpoint_stream,paged_args.execution_id)
        before_pages=len(Source.calls)
        etsy.recover(proxy,paged_args,paged)
        assert Source.calls[before_pages:]==[0,2]
        assert count(c,'SELECT count(*) FROM ops.extraction_checkpoints WHERE successful_run_id=%s',paged)==1
        paged_args.page_size=1
        try: etsy.recover(proxy,paged_args,paged)
        except ValueError as error: assert 'page size differs' in str(error)
        else: raise AssertionError('collection page size changed across retry')
        assert Source.calls[before_pages:]==[0,2]
        Source.total=2
        # More than 100 successful receipt GETs must finish in one drain call.
        # Scope is explicit and all writes remain in this rollback-only transaction.
        large=uuid.uuid4(); start_run(proxy,large,args.checkpoint_stream,identity+'-large')
        work_ids=[enqueue(proxy,identity+'-large:'+str(n),200000000000+n,None) for n in range(250)]
        before_reads=Source.receipt_reads
        etsy.drain(proxy,only=work_ids,collection_run=large)
        assert Source.receipt_reads-before_reads==250
        assert c.execute("SELECT count(*),max(cycle_attempts) FROM ops.processing_work WHERE work_id=ANY(%s) AND state='SUCCEEDED'",(work_ids,)).fetchone()==(250,1)
        assert c.execute("SELECT count(*) FROM raw.raw_records WHERE resource_type='etsy_receipt' AND metadata->>'collection_run_id'=%s",(str(large),)).fetchone()[0]==250
        # Re-entering the same completed scope performs no additional HTTP.
        etsy.drain(proxy,only=work_ids,collection_run=large)
        assert Source.receipt_reads-before_reads==250
    print(json.dumps(dict(status='PASS',scope='rollback-only real HTTP/SQL recovery and drain',
        list_calls=Source.calls,receipt_reads=Source.receipt_reads,
        checks=['count drift invalidates scan','fresh scan retains URL budgets',
                'no partial enqueue/checkpoint','validated processing resume reuses pages',
                'real receipt work succeeds','terminal audit fences','scan budget bounded',
                'five HTTP attempts across scans survive retry','same-count duplicate invalidates scan',
                'legacy successful prefix reused','interrupted scan resumes without resetting identity',
                'SQL rejects NULL error for INVALID scan',
                '250 receipt GETs finish one drain invocation with one attempt each',
                'all 250 receipts retain raw and collection lineage',
                'completed drain scope re-entry performs no HTTP',
                'multi-receipt pages retain checkpoint semantics',
                'changed direct recovery limit refuses before new HTTP'])))
finally:
    c.rollback(); c.close(); server.shutdown(); server.server_close(); thread.join(timeout=5)
