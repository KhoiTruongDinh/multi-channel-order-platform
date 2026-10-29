"""HTTP rejection and concurrent-duplicate tests; creates audit, never new business facts."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import uuid

from ingestion.etsy_common import secret,signature,connect,receipt_url

url='http://etsy-receiver:8000/webhooks/etsy'
body=json.dumps({'shop_id':7001,'event_type':'order.delivered','resource_url':receipt_url(9001001)}).encode()
prefix='m06-security-'+uuid.uuid4().hex


def send(raw,identity,stamp=None,broken=False):
    stamp=str(stamp or int(time.time()))
    headers={'webhook-id':identity,'webhook-timestamp':stamp,
             'webhook-signature':signature(identity,stamp,raw,secret())}
    if broken:
        headers['webhook-signature']='v1,invalid'
    try:
        with urlopen(Request(url,data=raw,headers=headers),timeout=20) as r:
            return r.status
    except HTTPError as r:
        return r.code


assert send(body,prefix+'-bad',broken=True)==401
outside=int(os.environ.get('ETSY_FRESHNESS_SECONDS','300'))+1000
assert send(body,prefix+'-old',int(time.time())-outside)==401
assert send(body,prefix+'-future',int(time.time())+outside)==401
foreign=json.dumps({'shop_id':7001,'event_type':'order.paid','resource_url':'http://evil/receipt'}).encode()
assert send(foreign,prefix+'-url')==400
assert send(b'{"shop_id":NaN}',prefix+'-json')==400
with ThreadPoolExecutor(max_workers=4) as pool:
    assert list(pool.map(lambda _:send(body,prefix+'-duplicate'),range(4)))==[202]*4
changed=body.replace(b'order.delivered',b'order.canceled')
assert send(changed,prefix+'-duplicate')==409
supported=body.replace(b'order.delivered',b'order.paid')
with ThreadPoolExecutor(max_workers=4) as pool:
    assert list(pool.map(lambda _:send(supported,prefix+'-supported'),range(4)))==[202]*4
# Run this probe with schedules paused: callback ACK must not wait for publication.
with connect() as lock:
    assert lock.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0], 'Pause/finish active releases before this probe'
    assert send(body,prefix+'-busy')==202
with connect() as c:
    rows=c.execute("SELECT inbox_id,fetch_state FROM ops.webhook_inbox WHERE webhook_id=%s",(prefix+'-duplicate',)).fetchall()
    assert len(rows)==1 and rows[0][1]=='IGNORED',rows
    assert c.execute('SELECT count(*) FROM ops.processing_work WHERE inbox_id=%s',(rows[0][0],)).fetchone()[0]==0
    accepted=c.execute("SELECT inbox_id FROM ops.webhook_inbox WHERE webhook_id=%s",(prefix+'-supported',)).fetchone()[0]
    assert c.execute('SELECT count(*) FROM ops.processing_work WHERE inbox_id=%s',(accepted,)).fetchone()[0]==1
    assert c.execute("SELECT count(*) FROM ops.webhook_delivery_attempts WHERE webhook_id LIKE %s",(prefix+'%',)).fetchone()[0]==15
    assert not c.execute('''SELECT 1 FROM ops.webhook_delivery_attempts d JOIN raw.raw_records r USING(raw_record_id)
        WHERE d.webhook_id LIKE %s AND d.response_status<>r.response_status''',(prefix+'%',)).fetchone()
print('M06 HTTP security/concurrent duplicate + busy-coordinator ACK PASS: 15 attempts / 3 inbox / exactly 1 supported work')
