"""Explicit local activation and source-only tick; never generates new purchases."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import subprocess
import time
from urllib.request import Request,urlopen

from tools.s02_data.config import parse_time
from tools.s02_data.load import ROOT, query
from test_support.s02_plan import literal


def overlay(db,campaign):
    env=dict(os.environ,S02_CAMPAIGN_ID=campaign)
    return db.base+['--file',str(ROOT/'infra/compose.s02.yaml'),'--profile','*'],env


def run_overlay(db,campaign,args):
    command,env=overlay(db,campaign)
    result=subprocess.run(command+args,env=env,capture_output=True,text=True,timeout=600,cwd=ROOT)
    if result.returncode: raise RuntimeError('S02 Compose operation failed (secrets suppressed)')
    return result.stdout


def model(db,campaign):
    return json.loads(run_overlay(db,campaign,['config','--format','json']))


def activate(db,name,mode,at,confirmed):
    if not confirmed: raise ValueError('explicit --confirm-local required before activating local services')
    if mode not in ('realtime','replay') or (mode=='realtime' and at):
        raise ValueError('choose realtime without --at, or replay with an explicit --at')
    rows=query(db,"SELECT d.campaign_id,d.state,c.config FROM s02.local_datasets d JOIN s02.campaigns c ON c.id=d.campaign_id WHERE d.name="+literal(name))
    if not rows or rows[0]['state']!='READY': raise ValueError('prepared READY dataset required')
    row=rows[0]; campaign=row['campaign_id']
    existing=query(db,'SELECT * FROM s02.playback')
    if existing: raise ValueError('playback already initialized; no implicit restart/rewind or dataset replacement')
    counts=query(db,'SELECT count(*) AS n FROM public.orders','website_source')
    occupied=query(db,'SELECT (SELECT count(*) FROM raw.raw_records)+(SELECT count(*) FROM core.orders_current)+(SELECT count(*) FROM ops.extraction_checkpoints) AS n','data_platform')
    active=query(db,"SELECT count(*) AS n FROM dag_run WHERE state IN ('queued','running')",'airflow_meta')
    unpaused=query(db,"SELECT dag_id FROM dag WHERE NOT is_paused AND dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')",'airflow_meta')
    if counts[0]['n'] or occupied[0]['n'] or active[0]['n'] or unpaused:
        raise ValueError('local data/checkpoints or active/unpaused scheduled DAGs exist; no automatic S01 transition/reset')
    now=datetime.now(timezone.utc)
    start=parse_time(at) if mode=='replay' and at else now
    if mode=='replay' and not at: raise ValueError('replay requires --at with offset')
    if start>now: raise ValueError('future replay observation clocks are not supported')
    config=model(db,campaign)
    for kind in ('ebay','etsy'):
        password=config['services'][kind+'-sim']['environment']['S02_DB_PASSWORD']
        if not password: raise ValueError('configure stable S02 reader passwords in .env')
        db.sql(f'ALTER ROLE s02_{kind}_reader PASSWORD '+literal(password)+';')
    db.sql('INSERT INTO s02.playback(singleton,campaign_id,mode,logical_start,real_start,stopped_at) VALUES (TRUE,'+
           ','.join(map(literal,(campaign,mode,start.isoformat(),now.isoformat(),now.isoformat())))+');')
    # Startup does not unpause DAGs: owner can inspect sources before enabling pipeline.
    run_overlay(db,campaign,['build','ebay-sim','etsy-sim','airflow'])
    run_overlay(db,campaign,['up','--detach','--wait','--wait-timeout','420','ebay-sim','etsy-sim','etsy-receiver','airflow'])
    db.sql('UPDATE s02.playback SET real_start=clock_timestamp(),stopped_at=NULL;')
    return dict(campaign_id=campaign,mode=mode,logical_start=start.isoformat(),pipeline='DAGs remain paused; enable explicitly after source inspection')


def tick(db):
    rows=query(db,'SELECT * FROM s02.playback_clock')
    if not rows: raise ValueError('no initialized playback')
    clock=rows[0]
    if clock['stopped_at']: return False
    campaign=clock['campaign_id']; t=literal(clock['logical_now'])
    dataset=query(db,'SELECT "references",coverage FROM s02.local_datasets WHERE campaign_id='+literal(campaign))[0]
    # Keyset pages bound memory while observing one captured source time.
    after=''
    committed=0
    while True:
        due=query(db,'SELECT * FROM (SELECT DISTINCT ON(order_id) order_id,visible_at,payload FROM s02.website_versions WHERE campaign_id='+literal(campaign)+
            ' AND visible_at<='+t+' AND order_id>'+literal(after)+' ORDER BY order_id,visible_at DESC) d ORDER BY order_id LIMIT 100')
        if not due: break
        for event in due:
            prior=query(db,'SELECT updated_at FROM public.orders WHERE order_id='+literal(event['order_id']),'website_source')
            if prior and parse_time(prior[0]['updated_at'])>=parse_time(event['visible_at']): continue
            data=event['payload']
            # Idempotent source references, not warehouse rows; transactional writer owns FK order.
            for key in ('customers','products','product_variants'): data[key]=dataset['references'][key]
            db.command(['run','--rm','-T','--no-deps','--entrypoint','python','website-simulator',
                '-m','simulator.website_s02'],json.dumps(data),timeout=180)
            committed+=1
        after=due[-1]['order_id']
    receiver=db.model()['services']['etsy-receiver']
    port=receiver['ports'][0]['published']
    key=base64.b64decode(receiver['environment']['ETSY_SIGNING_SECRET'].removeprefix('whsec_'))
    messages=query(db,'SELECT * FROM s02.deliveries WHERE campaign_id='+literal(campaign)+
        ' AND due_at<='+t+' AND NOT omitted AND delivered_at IS NULL ORDER BY due_at,message_id LIMIT 100')
    channel=dataset['coverage']['config']['channels']['etsy_sim']
    base=int(campaign[:6],16)*100000
    for message in messages:
        index=int(message['receipt_id'])-base
        repeat=channel['notifications']['omit']<=index<sum(channel['notifications'].values())
        body=json.dumps(dict(event_type=message['event_type'],shop_id=7001,
            resource_url='http://etsy-sim/v3/application/shops/7001/receipts/'+message['receipt_id']),separators=(',',':')).encode()
        for _ in range(2 if repeat else 1):
            when=str(int(time.time())); identity=message['message_id']
            sig='v1,'+base64.b64encode(hmac.new(key,(identity+'.'+when+'.').encode()+body,hashlib.sha256).digest()).decode()
            db.sql('UPDATE s02.deliveries SET attempts=attempts+1 WHERE campaign_id='+literal(campaign)+' AND message_id='+literal(identity)+';')
            with urlopen(Request(f'http://127.0.0.1:{port}/webhooks/etsy',data=body,headers={
                    'Content-Type':'application/json','webhook-id':identity,'webhook-timestamp':when,'webhook-signature':sig}),timeout=15) as response:
                if not 200<=response.status<300: raise ValueError('notification was not durably accepted')
                status=response.status
        db.sql('UPDATE s02.deliveries SET delivered_at=clock_timestamp(),last_status='+str(status)+
               ' WHERE campaign_id='+literal(campaign)+' AND message_id='+literal(message['message_id'])+';')
    print(json.dumps(dict(source_time=clock['logical_now'],website_updates=committed,notifications=len(messages))),flush=True)
    return True


def stop(db):
    db.sql('UPDATE s02.playback SET stopped_at=clock_timestamp() WHERE stopped_at IS NULL;')
    return dict(status='FROZEN',containers='retained',data='retained',note='polling skips new cycles; in-flight work is not killed')


def resume(db):
    rows=query(db,'SELECT * FROM s02.playback')
    if not rows or not rows[0]['stopped_at']: raise ValueError('a stopped playback is required')
    db.sql("UPDATE s02.playback SET real_start=CASE WHEN mode='replay' THEN real_start+(clock_timestamp()-stopped_at) ELSE real_start END,stopped_at=NULL WHERE stopped_at IS NOT NULL;")
    return dict(status='RUNNING',note='replay resumes without rewinding; realtime catches up to wallclock')
