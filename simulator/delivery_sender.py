"""Dispatch prepared live sends with durable progress and no warehouse access."""
import base64
import hashlib
import hmac
import json
import os
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def dispatch(conn, stopped):
    with conn.transaction():
        if not conn.execute("SELECT to_regclass('s02.delivery_schedule')").fetchone()['to_regclass']:
            return 0
        rows=conn.execute('''SELECT s.*,d.event_type,d.receipt_id,d.account_id
          FROM s02.delivery_schedule s JOIN s02.deliveries d USING(campaign_id,message_id)
          JOIN s02.live_batches b USING(campaign_id)
          WHERE s.completed_at IS NULL AND NOT d.omitted
            AND s.due_at+make_interval(secs=>b.shift_seconds::double precision)<=statement_timestamp()
            AND (s.next_retry_at IS NULL OR s.next_retry_at<=statement_timestamp())
          ORDER BY s.due_at+make_interval(secs=>b.shift_seconds::double precision),s.campaign_id,s.message_id,s.attempt_no
          LIMIT 100''').fetchall()
    sent=0
    for row in rows:
        if stopped.is_set(): break
        key=(row['campaign_id'],row['message_id'],row['attempt_no'])
        body=json.dumps(dict(event_type=row['event_type'],shop_id=int(row['account_id']),
            resource_url='http://etsy-sim/v3/application/shops/'+row['account_id']+'/receipts/'+row['receipt_id']),separators=(',',':')).encode()
        stamp=str(int(time.time())); identity=row['message_id']
        secret=base64.b64decode(os.environ['ETSY_SIGNING_SECRET'].removeprefix('whsec_'))
        signature='v1,'+base64.b64encode(hmac.new(secret,(identity+'.'+stamp+'.').encode()+body,hashlib.sha256).digest()).decode()
        with conn.transaction():
            conn.execute('''UPDATE s02.delivery_schedule SET send_count=send_count+1,last_attempt_at=clock_timestamp()
              WHERE campaign_id=%s AND message_id=%s AND attempt_no=%s''',key)
            conn.execute('UPDATE s02.deliveries SET attempts=attempts+1 WHERE campaign_id=%s AND message_id=%s',key[:2])
        status=None; error=None
        try:
            with urlopen(Request(os.environ.get('ETSY_RECEIVER_URL','http://etsy-receiver:8000/webhooks/etsy'),
                data=body,headers={'Content-Type':'application/json','webhook-id':identity,
                    'webhook-timestamp':stamp,'webhook-signature':signature}),timeout=15) as response:
                status=response.status
                if not 200<=status<300: error='HTTP'
        except HTTPError as failure: status=failure.code; error='HTTP'
        except (TimeoutError,socket.timeout): error='TIMEOUT'
        except URLError as failure: error='TIMEOUT' if isinstance(failure.reason,TimeoutError) else 'CONNECT'
        except OSError: error='TRANSPORT'
        with conn.transaction():
            conn.execute('''UPDATE s02.delivery_schedule SET last_http_status=%s,last_error_code=%s,
              completed_at=CASE WHEN %s THEN clock_timestamp() ELSE NULL END,
              next_retry_at=CASE WHEN %s THEN NULL ELSE clock_timestamp()+interval '5 seconds' END
              WHERE campaign_id=%s AND message_id=%s AND attempt_no=%s''',
              (status,error,error is None,error is None)+key)
            conn.execute('''UPDATE s02.deliveries SET last_status=%s,
              delivered_at=CASE WHEN %s THEN coalesce(delivered_at,clock_timestamp()) ELSE delivered_at END
              WHERE campaign_id=%s AND message_id=%s''',(status,error is None)+key[:2])
        sent+=int(error is None)
    return sent
