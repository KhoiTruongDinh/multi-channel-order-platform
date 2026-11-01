"""Read-only final live-batch/source/core reconciliation. Never starts a service."""
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import json
import time
from urllib.request import Request,urlopen

from tools.s02_data.load import LocalDB,ROOT,query
from tools.s02_data.live import DAGS,require_live
from simulator.s02_temporal import assemble
from simulator.live_source import translate
from test_support.m08b import reconcile,dt
from test_support.s02_oracle import facts
from tools.s02_data.references import references


def rows(db,sql,database='data_platform'):
    return json.loads(db.sql("SELECT coalesce(json_agg(t),'[]') FROM ("+sql+") t;",database),parse_float=Decimal)


def check(db):
    batches=rows(db,'SELECT * FROM s02.live_batches','marketplace_sim')
    if not batches: return dict(status='WAIT',reason='no admitted live batch')
    not_due=rows(db,'''SELECT count(*) AS n FROM (
      SELECT v.visible_at+make_interval(secs=>b.shift_seconds::double precision) AS due
      FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
      UNION ALL SELECT v.visible_at+make_interval(secs=>b.shift_seconds::double precision)
      FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
    ) events WHERE due>statement_timestamp()''','marketplace_sim')[0]['n']
    if not_due: return dict(status='WAIT',reason='source timeline still advancing',future_versions=not_due)
    expected=[]
    for row in rows(db,'''SELECT DISTINCT ON(v.order_id) v.order_id,v.payload,b.shift_seconds
      FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
      ORDER BY v.order_id,v.sequence DESC''','marketplace_sim'):
        expected.append(dict(source='internal_web',order_id=row['order_id'],payload=translate(row['payload'],row['shift_seconds'])))
    for row in rows(db,'''SELECT DISTINCT ON(v.source,v.order_id)
      v.source,v.order_id,o.base,v.header,c.body,b.shift_seconds
      FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
      JOIN s02.orders o USING(campaign_id,source,account_id,order_id)
      JOIN s02.components c ON (c.campaign_id,c.source,c.account_id,c.order_id,c.digest)=
        (v.campaign_id,v.source,v.account_id,v.order_id,v.component_digest)
      ORDER BY v.source,v.order_id,v.sequence DESC''','marketplace_sim'):
        expected.append(dict(source=row['source'],order_id=row['order_id'],
            payload=translate(assemble(row['source'],row['base'],row['header'],row['body']),row['shift_seconds'])))
    actual=dict(orders=rows(db,'SELECT * FROM core.orders_current'),lines=rows(db,'SELECT * FROM core.order_lines_current'))
    mapping=references()['mapping']
    if not reconcile(actual,expected,subset=True,facts_fn=lambda op:facts(op,mapping)):
        found={(o['source_system'],o['source_account_id'],o['source_order_id']):o for o in actual['orders']}
        mismatches=[]
        for op in expected:
            fact=facts(op,mapping); current=found.get((fact['source'],fact['account'],fact['order_id']))
            if not current:
                mismatches.append(dict(source=fact['source'],order=fact['order_id'],reason='missing'))
            elif (tuple(current[k] for k in ('payment_state','fulfillment_state','cancellation_state'))!=fact['states']
                  or dt(current['source_updated_at'])!=dt(fact['updated'])):
                mismatches.append(dict(source=fact['source'],order=fact['order_id'],
                    expected_states=fact['states'],actual_states=[current[k] for k in ('payment_state','fulfillment_state','cancellation_state')],
                    expected_updated=fact['updated'],actual_updated=current['source_updated_at']))
        return dict(status='WAIT',reason='final source/core reconciliation pending',expected_orders=len(expected),current_orders=len(actual['orders']),mismatches=mismatches[:8])
    # Source authority: marketplace HTTP, Website source SQL, never only plan vs warehouse.
    model=db.model()
    for op in expected:
        source=op['source']; identity=op['order_id']
        if source=='internal_web':
            from test_support.s02_plan import literal
            found=rows(db,'SELECT * FROM public.orders WHERE order_id='+literal(identity),'website_source')
            if not found or found[0]['cancellation_status']!=op['payload']['orders'][0]['cancellation_status']:
                return dict(status='WAIT',reason='Website source has not reached planned final state')
        else:
            kind='ebay' if source=='ebay_sim' else 'etsy'
            service=model['services'][kind+'-sim']; port=next(p['published'] for p in service['ports'] if p['target']==80)
            path='/sell/fulfillment/v1/order/'+identity if kind=='ebay' else '/v3/application/shops/7001/receipts/'+identity
            token=service['environment'][kind.upper()+'_SIM_TOKEN']
            with urlopen(Request(f'http://127.0.0.1:{port}'+path,headers={'Authorization':'Bearer '+token}),timeout=15) as response:
                body=json.load(response)
            header=op['payload']['order'] if kind=='ebay' else op['payload']
            if body!=header: return dict(status='WAIT',reason='HTTP source differs from final prepared source')
    since=min(b['published_at'] for b in batches)
    from test_support.s02_plan import literal
    schedules=rows(db,"SELECT dag_id,state,count(*) AS n FROM dag_run WHERE run_type='scheduled' AND start_date>="+
        literal(since)+"::timestamptz GROUP BY dag_id,state",'airflow_meta')
    if not all(sum(r['n'] for r in schedules if r['dag_id']==d and r['state']=='success')>=2 for d in DAGS):
        return dict(status='WAIT',reason='need two real scheduled successes per path',scheduled=schedules)
    if any(r['state']=='failed' for r in schedules if r['dag_id'] in DAGS):
        raise AssertionError('a post-admission scheduled run failed; inspect retained audit')
    missing=rows(db,'''SELECT h.snapshot_id FROM core.order_snapshot_history h
      LEFT JOIN core.snapshot_evidence e USING(snapshot_id)
      GROUP BY h.snapshot_id HAVING count(e.raw_record_id)=0''')
    assert not missing,'history missing raw evidence'
    deliveries=rows(db,'''SELECT d.* FROM s02.deliveries d
      JOIN s02.live_batches b USING(campaign_id)''','marketplace_sim')
    omitted=0; duplicate=0
    for delivery in deliveries:
        identity=literal(delivery['message_id'])
        inbox=rows(db,'SELECT count(*) AS n FROM ops.webhook_inbox WHERE webhook_id='+identity)[0]['n']
        if delivery['omitted']:
            assert inbox==0 and delivery['attempts']==0,'omitted notification was sent'
            omitted+=1
        else:
            if delivery['delivered_at'] is None or inbox!=1:
                return dict(status='WAIT',reason='source notification delivery/inbox pending')
            if delivery['attempts']>=2:
                accepted=rows(db,'SELECT count(*) AS n FROM ops.webhook_delivery_attempts WHERE accepted AND webhook_id='+identity)[0]['n']
                assert accepted>=2,'duplicate attempts not retained'
                duplicate+=1
    keys={(op['source'],op['order_id']) for op in expected}
    selected=[o for o in actual['orders'] if (o['source_system'],o['source_order_id']) in keys]
    changed={s:0 for s in ('internal_web','ebay_sim','etsy_sim')}
    for row in rows(db,'SELECT source_system,source_order_id,count(*) AS versions FROM core.order_snapshot_history GROUP BY source_system,source_order_id HAVING count(*)>1'):
        if (row['source_system'],row['source_order_id']) in keys: changed[row['source_system']]+=1
    return dict(status='PASS',scope='final live source/core reconciliation + scheduled successes; reread only if separately reported; NOT full M08C/D',
        batches=len(batches),orders=len(selected),scheduled=schedules,
        omitted_notifications=omitted,duplicate_message_ids=duplicate,
        observed_live_changed_orders=changed,
        observed_history=rows(db,'SELECT source_system,count(*) FROM core.order_snapshot_history GROUP BY source_system'))


def signature(db):
    # Publication lineage changes each release; business/source identity must not.
    values=[]
    for table in ('orders_current','order_lines_current','order_snapshot_history','order_line_snapshot_history'):
        values.append(rows(db,"SELECT md5(coalesce(string_agg((to_jsonb(r)-ARRAY['batch_id','published_batch_id'])::text,'' ORDER BY (to_jsonb(r)-ARRAY['batch_id','published_batch_id'])::text),'')) AS digest FROM core."+table+' r')[0]['digest'])
    return values


def reread(db,result,seconds):
    before=signature(db)
    raw_before=rows(db,'SELECT count(*) AS n FROM raw.raw_records')[0]['n']
    baseline={d:sum(r['n'] for r in result['scheduled'] if r['dag_id']==d and r['state']=='success') for d in DAGS}
    since=rows(db,'SELECT min(published_at) AS first_admission FROM s02.live_batches','marketplace_sim')[0]['first_admission']
    from test_support.s02_plan import literal
    deadline=time.monotonic()+seconds
    while True:
        schedules=rows(db,"SELECT dag_id,state,count(*) AS n FROM dag_run WHERE run_type='scheduled' AND start_date>="+
            literal(since)+"::timestamptz GROUP BY dag_id,state",'airflow_meta')
        if all(sum(r['n'] for r in schedules if r['dag_id']==d and r['state']=='success')>baseline[d] for d in DAGS):
            current=check(db)
            assert current['status']=='PASS','source reconciliation changed during reread'
            assert current['batches']==result['batches'],'new batch arrived during dedupe check'
            assert signature(db)==before,'natural reread changed business/history signature'
            raw_after=rows(db,'SELECT count(*) AS n FROM raw.raw_records')[0]['n']
            assert raw_after>raw_before,'physical acquisition audits did not increase'
            current['natural_reread']=dict(status='PASS',raw_before=raw_before,raw_after=raw_after,logical_signature_unchanged=True)
            return current
        if time.monotonic()>=deadline: raise AssertionError('natural scheduled reread deadline exceeded')
        print(json.dumps(dict(status='WAIT',reason='waiting for one additional scheduled success per path')),flush=True)
        time.sleep(10)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-seconds',type=int,default=0)
    parser.add_argument('--verify-reread-seconds',type=int,default=0)
    parser.add_argument('--require-observed-changes',action='store_true')
    args=parser.parse_args()
    if not 0<=args.wait_seconds<=1800: parser.error('wait-seconds must be0..1800')
    if not 0<=args.verify_reread_seconds<=600: parser.error('verify-reread-seconds must be0..600')
    db=LocalDB(); require_live(db)
    deadline=time.monotonic()+args.wait_seconds
    while True:
        result=check(db)
        if result['status']=='PASS' and args.require_observed_changes and not all(result['observed_live_changed_orders'].values()):
            result=dict(status='WAIT',reason='need observed state changes per live source; use observe_6min profile',
                        observed_live_changed_orders=result['observed_live_changed_orders'])
        print(json.dumps(result,default=str),flush=True)
        if result['status']=='PASS' or time.monotonic()>=deadline: break
        time.sleep(10)
    if result['status']=='PASS' and args.verify_reread_seconds:
        result=reread(db,result,args.verify_reread_seconds)
        print(json.dumps(result,default=str),flush=True)
    path=ROOT/'runtime'/('m08b-live-check-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print('Evidence: '+str(path.relative_to(ROOT)))
    if result['status']!='PASS': raise SystemExit(1)


if __name__=='__main__':
    try: main()
    except Exception as error:
        result=dict(status='FAIL',exception=type(error).__name__,reason=str(error))
        path=ROOT/'runtime'/('m08b-live-check-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-failure.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
        print('Evidence: '+str(path.relative_to(ROOT)))
        raise SystemExit(1)
