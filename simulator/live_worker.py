"""Persistent source writer/webhook sender. No generator, warehouse or Docker access."""
import base64
import hashlib
import hmac
import json
import os
import signal
import threading
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

import psycopg
from psycopg.rows import dict_row
from simulator.live_source import translate
from simulator.website_s02 import apply

HEARTBEAT=Path('/tmp/live-source-heartbeat')
STOP=threading.Event()


def connection():
    return psycopg.connect(host=os.environ.get('S02_DB_HOST','postgres'),dbname='marketplace_sim',
        user='marketplace_writer',password=os.environ['MARKETPLACE_WRITER_PASSWORD'],
        connect_timeout=5,row_factory=dict_row)


def tick(conn):
    # A session lock prevents two senders. Crash releases it; a restarted worker
    # recognizes committed Website timestamps and retained delivery progress.
    with conn.transaction():
        web=conn.execute('''SELECT * FROM (
          SELECT DISTINCT ON(v.campaign_id,v.order_id)
          v.campaign_id,v.order_id,v.sequence,v.visible_at,v.payload,b.shift_seconds
          FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
          LEFT JOIN s02.live_website_progress p USING(campaign_id,order_id)
          WHERE v.visible_at+make_interval(secs=>b.shift_seconds::double precision)<=statement_timestamp()
            AND v.sequence>coalesce(p.sequence,0)
          ORDER BY v.campaign_id,v.order_id,v.visible_at DESC
          ) due ORDER BY visible_at,campaign_id,order_id LIMIT 100''').fetchall()
    from simulator.website_playback import connection_kwargs
    written=0
    for row in web:
        if STOP.is_set():
            break
        payload=translate(row['payload'],row['shift_seconds'])
        for table in ('customers','products','product_variants'):
            payload[table]=row['payload'][table]
        with psycopg.connect(**connection_kwargs()) as website:
            prior=website.execute('SELECT updated_at FROM public.orders WHERE order_id=%s',(row['order_id'],)).fetchone()
        from datetime import datetime
        updated=datetime.fromisoformat(payload['orders'][0]['updated_at'])
        if not prior or prior[0]<updated:
            apply(payload); written+=1
        with conn.transaction():
            conn.execute('''INSERT INTO s02.live_website_progress VALUES(%s,%s,%s)
              ON CONFLICT(campaign_id,order_id) DO UPDATE SET sequence=EXCLUDED.sequence
              WHERE EXCLUDED.sequence>s02.live_website_progress.sequence''',
              (row['campaign_id'],row['order_id'],row['sequence']))
    with conn.transaction():
        deliveries=conn.execute('''SELECT d.*,b.shift_seconds,
          l.coverage->'config'->'channels'->'etsy_sim'->'notifications' AS faults
          FROM s02.deliveries d JOIN s02.live_batches b USING(campaign_id)
          JOIN s02.local_datasets l USING(campaign_id)
          WHERE d.due_at+make_interval(secs=>b.shift_seconds::double precision)<=statement_timestamp()
            AND NOT d.omitted AND d.delivered_at IS NULL ORDER BY d.due_at,d.message_id LIMIT 100''').fetchall()
    sent=0
    for row in deliveries:
        if STOP.is_set():
            break
        index=int(row['receipt_id'])-int(row['campaign_id'][:6],16)*100000
        faults=row['faults']
        repeats=2 if faults['omit']<=index<faults['omit']+faults['duplicate'] else 1
        body=json.dumps(dict(event_type=row['event_type'],shop_id=7001,
            resource_url='http://etsy-sim/v3/application/shops/7001/receipts/'+row['receipt_id']),separators=(',',':')).encode()
        for _ in range(repeats):
            identity=row['message_id']; stamp=str(int(time.time()))
            secret=base64.b64decode(os.environ['ETSY_SIGNING_SECRET'].removeprefix('whsec_'))
            signature='v1,'+base64.b64encode(hmac.new(secret,(identity+'.'+stamp+'.').encode()+body,hashlib.sha256).digest()).decode()
            with conn.transaction():
                conn.execute('UPDATE s02.deliveries SET attempts=attempts+1 WHERE campaign_id=%s AND message_id=%s',
                             (row['campaign_id'],identity))
            try:
                with urlopen(Request(os.environ.get('ETSY_RECEIVER_URL','http://etsy-receiver:8000/webhooks/etsy'),
                    data=body,headers={'Content-Type':'application/json','webhook-id':identity,
                        'webhook-timestamp':stamp,'webhook-signature':signature}),timeout=15) as response:
                    status=response.status
                    if not 200<=status<300: raise RuntimeError('notification not accepted')
            except HTTPError as error:
                with conn.transaction():
                    conn.execute('UPDATE s02.deliveries SET last_status=%s WHERE campaign_id=%s AND message_id=%s',
                                 (error.code,row['campaign_id'],identity))
                raise
        with conn.transaction():
            conn.execute('UPDATE s02.deliveries SET delivered_at=clock_timestamp(),last_status=%s WHERE campaign_id=%s AND message_id=%s',
                         (status,row['campaign_id'],identity))
        sent+=1
    return dict(website_updates=written,notifications=sent)


def main():
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    while not STOP.is_set():
        try:
            with connection() as conn:
                conn.autocommit=True
                if not conn.execute("SELECT pg_try_advisory_lock(hashtext('live-source-worker')) AS locked").fetchone()['locked']:
                    raise RuntimeError('another live source worker is active')
                while not STOP.is_set():
                    progress=tick(conn)
                    HEARTBEAT.write_text(str(time.time()))
                    if any(progress.values()): print(json.dumps(progress),flush=True)
                    STOP.wait(2)
        except Exception as error:
            # Do not print connection strings, secrets, payloads or webhook URLs.
            print('Live source tick failed: '+type(error).__name__+'; retained progress, retrying',flush=True)
            STOP.wait(5)


if __name__=='__main__': main()
