"""Disposable PostgreSQL + real SIM HTTP sender check. Never targets owner DBs."""
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request,urlopen

import psycopg
from psycopg.rows import dict_row
from tools.s02_data.config import validate
from tools.s02_data.load import prepare,query
from tools.s02_data.generate import events,campaign_id
from tools.s02_data.delivery import sql as delivery_sql,plan
from test_support.s02_plan import prepare_sql,literal
from simulator.delivery_sender import dispatch
from simulator.s02_temporal import LivePostgresStore
from simulator.etsy_api import State,handlers

ROOT=Path('/repo')


def connect(db='marketplace_sim',**kwargs):
    # Fixed disposable-only hostname; the wrapper creates a private network.
    return psycopg.connect(host='sim-delivery-pg',dbname=db,user='postgres',autocommit=True,**kwargs)


def migration(path,db):
    sql='\n'.join(line for line in (ROOT/path).read_text().splitlines() if not line.startswith('\\'))
    with connect(db) as conn: conn.execute(sql)


class DB:
    def sql(self,text,db='marketplace_sim'):
        text='\n'.join(line for line in text.splitlines() if not line.startswith('\\set'))
        with connect(db) as conn:
            def execute(chunk):
                cursor=conn.execute(chunk); values=[]
                while True:
                    if cursor.description: values=[row[0] for row in cursor.fetchall()]
                    if not cursor.nextset(): break
                return values
            chunks=text.split('\\gexec')
            for chunk in chunks[:-1]:
                for command in execute(chunk): conn.execute(command)
            values=execute(chunks[-1])
            return '\n'.join(json.dumps(value,default=str) if isinstance(value,(list,dict)) else str(value) for value in values)


def main():
    with connect('postgres') as conn:
        for role in ('marketplace_owner','website_owner','platform_owner','website_reader','marketplace_writer'):
            conn.execute('CREATE ROLE '+role)
        conn.execute('GRANT marketplace_owner TO marketplace_writer')
        conn.execute('ALTER DATABASE marketplace_sim OWNER TO marketplace_owner')
        for db,owner in (('website_source','website_owner'),('data_platform','platform_owner')):
            conn.execute('CREATE DATABASE '+db+' OWNER '+owner)
    for db in ('marketplace_sim','website_source','data_platform'):
        migration(Path('migrations/bootstrap/002_database_baseline.sql'),db)
    migration(Path('migrations/website_source/001_schema.sql'),'website_source')
    migration(Path('migrations/platform/001_foundation.sql'),'data_platform')
    config=json.loads((ROOT/'tools/s02_data/config/sim_delivery_demo.json').read_text())
    config.update(start_at='2026-11-01T00:00:00Z',end_at='2026-11-01T00:02:00Z')
    result=prepare(DB(),validate(config)); identity=result['campaign_id']
    for _ in range(2):
        migration(Path('migrations/marketplace_sim/004_delivery_schedule.sql'),'marketplace_sim')
    migration(Path('migrations/marketplace_sim/003_live_batches.sql'),'marketplace_sim')
    with connect() as conn:
        conn.execute('INSERT INTO s02.live_batches VALUES(%s,clock_timestamp(),0)',(identity,))
    counts=query(DB(),'''SELECT
      (SELECT count(*) FROM s02.deliveries) messages,
      (SELECT count(*) FROM s02.delivery_schedule) sends,
      (SELECT count(*) FROM s02.deliveries WHERE omitted) omitted''')[0]
    assert counts==dict(messages=8,sends=10,omitted=2),counts
    assert len(result['manifest']['delivery_plan']['reordered_orders'])==2
    def refused(text,expected):
        with connect() as connection:
            try:
                with connection.transaction(): connection.execute(text)
            except psycopg.Error as error:
                assert expected in str(error),str(error)
                return
        raise AssertionError('unsafe SQL accepted')
    # Pending rows also enforce seal protection, not only completed-row guards.
    refused("UPDATE s02.delivery_schedule SET due_at=due_at+interval '1 second'",'sealed send plan immutable')
    refused('UPDATE s02.delivery_schedule SET attempt_no=attempt_no+100','send identity immutable')
    # An unsealed, unadmitted source plan isolates FK/visibility/seal checks.
    extra=json.loads(json.dumps(validate(config))); extra['dataset']='unsealed-guard-check'
    batch=[b for b in events(extra) if b[0]['source']=='etsy_sim'][2]
    cid=campaign_id(extra['dataset'])
    DB().sql('INSERT INTO s02.campaigns(id,seed,config,checksum) VALUES ('+literal(cid)+",1,'{}',repeat('0',64));")
    DB().sql('BEGIN;\n'+'\n'.join(prepare_sql(dict(id=cid,seed=1,events=batch)).splitlines()[2:-2])+'\n'+
             '\n'.join(delivery_sql(cid,batch,plan(batch,extra)))+'\nCOMMIT;')
    refused('UPDATE s02.deliveries SET source_sequence=999 WHERE campaign_id='+literal(cid),'delivery_source_version')
    refused('INSERT INTO s02.delivery_schedule(campaign_id,message_id,attempt_no,due_at) '+
            "SELECT campaign_id,message_id,2,'2026-01-01T00:00:00Z'::timestamptz FROM s02.deliveries WHERE campaign_id="+literal(cid),
            'send precedes source visibility')
    DB().sql("INSERT INTO s02.local_datasets VALUES ("+literal(cid)+",'unsealed-guard-check','LOADING','{}','{\"delivery_plan\":{\"version\":1}}');")
    DB().sql('INSERT INTO s02.delivery_schedule(campaign_id,message_id,attempt_no,due_at) '+
             "SELECT campaign_id,message_id,3,due_at+interval '10 seconds' FROM s02.deliveries WHERE campaign_id="+literal(cid))
    refused('UPDATE s02.campaigns SET sealed=true WHERE id='+literal(cid),'invalid send timeline')
    # Fresh loading is exercised without resetting the first dataset.
    legacy=validate(json.loads((ROOT/'tools/s02_data/config/sim_delivery_demo.json').read_text()))
    legacy.update(dataset='legacy-delivery-probe',start_at='2026-11-01T00:00:00Z',end_at='2026-11-01T00:02:00Z')
    legacy['channels']['etsy_sim'].pop('delivery_plan')
    prepare(DB(),legacy)
    secret=b'disposable-http-key'; received=[]
    os.environ['ETSY_SIM_TOKEN']='disposable-api-token'
    state=State(str(ROOT/'fixtures/s01/source_states/etsy'))
    state.s02=LivePostgresStore('etsy',connect=lambda:connect(options='-c role=s02_etsy_reader -c default_transaction_read_only=on'))
    api=ThreadingHTTPServer(('127.0.0.1',0),handlers(state)[0])
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            message=self.headers['webhook-id']; stamp=self.headers['webhook-timestamp']
            expected='v1,'+base64.b64encode(hmac.new(secret,(message+'.'+stamp+'.').encode()+body,hashlib.sha256).digest()).decode()
            assert hmac.compare_digest(expected,self.headers['webhook-signature'])
            assert abs(int(stamp)-int(time.time()))<30
            value=json.loads(body)
            path=value['resource_url'].split('http://etsy-sim',1)[1]
            with urlopen(Request('http://127.0.0.1:'+str(api.server_port)+path,
                                 headers={'Authorization':'Bearer disposable-api-token'})) as response:
                receipt=json.load(response)
            assert receipt['is_shipped'] is True
            received.append(message)
            self.send_response(500 if len(received)==1 else 202); self.end_headers()
    receiver=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
    threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (api,receiver)]
    for thread in threads: thread.start()
    os.environ.update(ETSY_SIGNING_SECRET='whsec_'+base64.b64encode(secret).decode(),
                      ETSY_RECEIVER_URL='http://127.0.0.1:'+str(receiver.server_port))
    real=urlopen; requests=0
    def ambiguous(*args,**kwargs):
        nonlocal requests
        requests+=1
        response=real(*args,**kwargs)
        if requests==2:
            response.close()
            raise URLError('simulated ACK loss after receiver accepted')
        return response
    try:
        with connect(row_factory=dict_row,options='-c role=marketplace_writer') as conn:
            with patch('simulator.delivery_sender.urlopen',side_effect=ambiguous):
                assert dispatch(conn,threading.Event())==8
            assert dispatch(conn,threading.Event())==0
            time.sleep(5.1)
            assert dispatch(conn,threading.Event())==2
            assert dispatch(conn,threading.Event())==0
    finally:
        for server in (receiver,api): server.shutdown(); server.server_close()
        for thread in threads: thread.join()
    assert len(received)==12 and len(set(received))==6,(len(received),len(set(received)))
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM s02.delivery_schedule WHERE completed_at IS NOT NULL').fetchone()[0]==10
        assert conn.execute('SELECT sum(send_count) FROM s02.delivery_schedule').fetchone()[0]==12
        for text in (
            "UPDATE s02.delivery_schedule SET due_at=due_at+interval '1 second'",
            'UPDATE s02.delivery_schedule SET send_count=0',
            'DELETE FROM s02.delivery_schedule',
            "INSERT INTO s02.delivery_schedule SELECT campaign_id,message_id,99,due_at,0,NULL,NULL,NULL,NULL,NULL FROM s02.delivery_schedule WHERE campaign_id='"+identity+"' LIMIT 1",
            'UPDATE s02.deliveries SET source_sequence=999999',
            "SET ROLE s02_etsy_reader; SELECT * FROM s02.delivery_schedule",
        ):
            try:
                with conn.transaction(): conn.execute(text)
            except psycopg.Error: pass
            else: raise AssertionError('unsafe mutation/read allowed: '+text)
    assert DB().sql((ROOT/'tools/s02_data/inspect_delivery.sql').read_text())=='8'
    print(json.dumps(dict(status='PASS',scope='SIM only; NOT warehouse/Airflow campaign acceptance',
        planned=counts,actual_sends=12,logical_messages=6,completed=10,
        checks=['full loader','migration reapply','legacy load','signed real HTTP',
                'current receipt API/RLS','500 retry','ACK ambiguity','completed no-resend','seal/FK/role guards'])))


if __name__=='__main__': main()
