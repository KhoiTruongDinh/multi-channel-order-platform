"""Guarded temporal S02 preparation/storage checks. Never alters owner services."""
import argparse
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json
import sys
from pathlib import Path
import time

from test_support import m08a as isolation
from test_support.s02_plan import plan,checksum,prepare_sql,mapping_sql,literal,latest
from test_support.m08b import Campaign,rows
from test_support.m08b import reconcile,snapshot,business_signature,DAGS,clock
from test_support.s02_oracle import facts
from test_support.s02_inputs import stamp,ACCOUNTS


def load_prepared(h):
    path=h.root/'evidence/prepared-source.json'
    value=json.loads(path.read_text(encoding='utf-8'))
    isolation.require(value['id']==h.marker['id'],'Prepared dataset identity mismatch')
    expected=(h.root/'evidence/prepared-source.sha256').read_text().strip()
    isolation.require(checksum(value)==expected==h.marker.get('dataset_sha256'),'Prepared dataset changed/unbound')
    return value


def prepare(h,seed,count,duration,start=None):
    h.check()
    value=plan(seed,h.marker['id'],start or datetime.now(timezone.utc),count,duration)
    for name,body in [('prepared-source.json',json.dumps(value,indent=2)),('prepared-source.sha256',checksum(value))]:
        with (h.root/'evidence'/name).open('x',encoding='utf-8') as handle: handle.write(body)
    h.marker['dataset_sha256']=checksum(value)
    isolation.save_marker(h.marker)
    print(f"S02 prepared: {count*3} orders, {len(value['events'])} source versions, {duration}s workload; not pipeline acceptance")
    return value


def install(h,value):
    h.sql('\\i /migrations/marketplace_sim/001_s02_temporal.sql','marketplace_sim')
    for kind in ('ebay','etsy'):
        password=h.model['services'][kind+'-sim']['environment']['S02_DB_PASSWORD']
        h.sql(f'ALTER ROLE s02_{kind}_reader PASSWORD {literal(password)};','marketplace_sim')
    h.sql(prepare_sql(value),'marketplace_sim')
    h.sql(mapping_sql(value))


def probe(h,value):
    """Run assertions against real PG/HTTP. All source access is test-only here."""
    api=object.__new__(Campaign); api.h=h
    for kind in ('ebay','etsy'):
        source=kind+'_sim'
        op=next(e for e in value['events'] if e['source']==source)
        token=h.model['services'][kind+'-sim']['environment'][kind.upper()+'_SIM_TOKEN']
        path=('/sell/fulfillment/v1/order/' if kind=='ebay' else '/v3/application/shops/7001/receipts/')+op['order_id']
        found=api.http(kind+'-sim',80,path,headers={'Authorization':'Bearer '+token})
        expected=op['payload']['order'] if kind=='ebay' else op['payload']
        isolation.require(found==expected,'Pending order HTTP reconstruction mismatch')
        # Reader role must see its source only; credentials never enter command args.
        role='s02_'+kind+'_reader'
        result=json.loads(h.sql(f"SET ROLE {role}; SELECT json_build_object('sources',(SELECT json_agg(DISTINCT source) FROM s02.orders),'write',has_table_privilege(current_user,'s02.versions','INSERT'),'platform',has_database_privilege(current_user,'data_platform','CONNECT'));",'marketplace_sim').splitlines()[-1])
        isolation.require(result==dict(sources=[source],write=False,platform=False),'Reader privileges/source boundary mismatch')
    # Exact boundary semantics using the same SQL selection as the adapter, before
    # window filters; check all prepared order versions without moving wall clock.
    checks=[]
    for e in value['events']:
        if e['source']=='internal_web': continue
        keys=(value['id'],e['source'],e['order_id'])
        query=f"SELECT sequence FROM s02.versions WHERE campaign_id={literal(keys[0])} AND source={literal(keys[1])} AND order_id={literal(keys[2])} AND visible_at<={literal(e['visible_at'])} ORDER BY visible_at DESC,sequence DESC LIMIT 1"
        checks.append(f'({query})={e["sequence"]}')
    result=h.sql('SELECT '+ ' AND '.join(checks)+';','marketplace_sim')
    isolation.require(result=='t','Exact visibility boundaries failed')
    # Savepoint proves trigger refusal without treating expected errors as command failure.
    h.sql("""DO $$ BEGIN
      BEGIN UPDATE s02.versions SET header=header; RAISE EXCEPTION 'immutability missing';
      EXCEPTION WHEN raise_exception THEN IF SQLERRM<>'sealed source is immutable' THEN RAISE; END IF; END;
    END $$;""",'marketplace_sim')
    h.sql('\\i /migrations/marketplace_sim/001_s02_temporal.sql','marketplace_sim')
    return dict(storage='PASS',reader_isolation='PASS',http_reconstruction='PASS',boundaries='PASS',sealed_immutable='PASS',migration_rerun='PASS')


def storage(h):
    """Small isolated backend test, not Airflow/warehouse acceptance."""
    owner=isolation.owner_container(); isolation.owner_idle(owner)
    before=isolation.protected_signature(owner)
    h.check()
    isolation.require(h.marker['project']+'_postgres_data' not in isolation.docker('volume','ls','--format','{{.Name}}').splitlines(),'Storage check requires fresh ID/volume')
    report=dict(status='RUNNING',profile='temporal-storage',started_at=isolation.utc(),protected_before=before)
    with (h.root/'evidence/accept.started').open('x',encoding='utf-8') as f: f.write(isolation.utc())
    try:
        total=int(isolation.docker('info','--format','{{.MemTotal}}'))
        isolation.require(total>=3.5*1024**3,'Storage probe requires >=3.5GiB Docker RAM')
        h.dc(['build','ebay-sim','etsy-sim'],timeout=600)
        h.dc(['up','--detach','--wait','--wait-timeout','180','postgres'])
        report['db_system_id']=h.test_db(first=True)
        h.migration_rerun()
        value=prepare(h,17,4,86400,datetime.now(timezone.utc)-timedelta(seconds=60))
        install(h,value)
        h.dc(['up','--detach','--wait','--wait-timeout','120','ebay-sim','etsy-sim'])
        report.update(probe(h,value))
        # Restart ONLY validated test source processes; PG persistence must serve
        # the same pending orders without reseeding/source UPDATE.
        h.dc(['restart','ebay-sim','etsy-sim'])
        h.dc(['up','--detach','--wait','--wait-timeout','120','ebay-sim','etsy-sim'])
        probe(h,value)
        report.update(status='PASS',restart='PASS',dataset_sha256=checksum(value))
    except Exception as error:
        report.update(status='FAIL',failure=type(error).__name__+': '+str(error))
        raise
    finally:
        try:
            h.dc(['down','--remove-orphans','--timeout','30'])
            report['teardown']='PASS'
        except Exception:
            report.update(status='FAIL',teardown='FAIL')
            raise
        finally:
            after=isolation.protected_signature(owner)
            report['protected_after']=after
            report['protected_check']='PASS' if before==after else 'FAIL'
            if before!=after: report['status']='FAIL'
            report.update(finished_at=isolation.utc(),steps=h.steps)
            (h.root/'evidence/temporal-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            (h.root/'evidence/accept.finished').write_text(isolation.utc(),encoding='utf-8')
    isolation.require(report['status']=='PASS','Temporal storage check failed')
    print('M08B temporal storage PASS (not scheduled/pipeline acceptance); owner unchanged')


class TemporalCampaign(Campaign):
    """Real1x finite coordinator. PG GETs do not consume events or change source."""
    def __init__(self,h,seed,profile,count):
        super().__init__(h,seed,profile)
        self.deadline=time.monotonic()+3600
        self.count=count
        self.applied={}
        self.result.update(scenario_version='s02-temporal-v1',backend='s02-pg',
            mapping_version='s02-catalog-v1',deadline_seconds=3600,orders_per_channel=count,
            lines_per_order='seeded1..8',max_source_operations='prepared finite schedule')

    def expected(self):
        return latest(self.value,datetime.now(timezone.utc)+timedelta(days=2))

    def match(self,actual,ops):
        return reconcile(actual,ops,facts_fn=lambda op:facts(op,self.value['references']['mapping']))

    def tick(self):
        """Website writer and Etsy delivery only; PG marketplace versions never UPDATE."""
        now=datetime.now(timezone.utc)
        for e in latest(self.value,now):
            if e['source']!='internal_web' or self.applied.get(e['order_id'],0)>=e['sequence']: continue
            payload=e['payload']
            if not self.applied:
                payload=dict(payload,**{key:self.value['references'][key] for key in ('customers','products','product_variants')})
            self.h.dc(['run','--rm','-T','--no-deps','--entrypoint','python',
                'website-simulator','-m','simulator.website_s02'],payload=json.dumps(payload))
            self.applied[e['order_id']]=e['sequence']
            self.record(outcome='website_committed',source_sequence=e['sequence'],
                **{k:v for k,v in e.items() if k!='sequence'})
        due=rows(self.h,"SELECT * FROM s02.deliveries WHERE campaign_id="+literal(self.h.marker['id'])+
            " AND due_at<=clock_timestamp() AND NOT omitted AND delivered_at IS NULL ORDER BY due_at,message_id",'marketplace_sim')
        for message in due:
            e=next(e for e in self.value['events'] if e['source']=='etsy_sim' and
                e['order_id']==message['receipt_id'] and e['sequence']==int(message['message_id'].rsplit('-',1)[1]))
            # Attempt is persisted before network; stable IDs permit safe redelivery.
            key='campaign_id='+literal(self.h.marker['id'])+' AND message_id='+literal(message['message_id'])
            self.h.sql('UPDATE s02.deliveries SET attempts=attempts+1 WHERE '+key+';','marketplace_sim')
            status=self.deliver(e,e['sequence'],message_id=message['message_id'])
            self.h.sql('UPDATE s02.deliveries SET delivered_at=clock_timestamp(),last_status='+str(int(status))+' WHERE '+key+';','marketplace_sim')

    def cli(self,source,mode='recovery'):
        self.h.run('airflow','-m','orchestration.polling','--source',source,
            '--mapping-version','s02-catalog-v1','--collection-mode',mode,
            '--execution-id',f"temporal-{self.h.marker['id']}-{len(self.h.steps)}",
            '--window-end',stamp(clock()),'--initial-start',stamp(datetime.fromisoformat(self.value['start'].replace('Z','+00:00'))-timedelta(days=1)),
            '--wait-seconds','300',entrypoint='/opt/airflow/project-venv/bin/python',timeout=600)

    def verify_authority(self):
        final=self.expected()
        for e in final:
            source=e['source']
            if source=='internal_web': continue
            kind='ebay' if source=='ebay_sim' else 'etsy'
            token=self.h.model['services'][kind+'-sim']['environment'][kind.upper()+'_SIM_TOKEN']
            path=('/sell/fulfillment/v1/order/' if kind=='ebay' else '/v3/application/shops/7001/receipts/')+e['order_id']
            found=self.http(kind+'-sim',80,path,headers={'Authorization':'Bearer '+token})
            expected=e['payload']['order'] if kind=='ebay' else e['payload']
            isolation.require(found==expected,'Authoritative current source differs from prepared visible source')
            if kind=='ebay':
                shipping=self.http(kind+'-sim',80,path+'/shipping_fulfillment',headers={'Authorization':'Bearer '+token})
                isolation.require(shipping['fulfillments']==e['payload']['fulfillments'],'Shipping authority mismatch')
        # Website authority uses the existing read-only source query.
        payload=json.loads(self.h.dc(['run','--rm','-T','--no-deps','--entrypoint','python','website-collector','-c',
            "import json; from ingestion.website import acquire_source,parse_time; print(json.dumps(acquire_source(parse_time('2026-01-01T00:00:00Z'),parse_time('"+stamp(clock())+"'))))"]))
        for e in final:
            if e['source']!='internal_web': continue
            expected=e['payload']; identity=e['order_id']
            for key in ('orders','order_items','payment_transactions','cancellation_requests','shipments'):
                selected=[r for r in payload[key] if r['order_id']==identity]
                isolation.require(selected==expected[key],'Website source authority mismatch: '+key)

    def verify_report(self):
        data=json.loads(self.h.dc(['exec','-T','postgres','psql','-XAt','--set','ON_ERROR_STOP=1',
            '-U','platform_report','-d','data_platform','-c',"""SELECT json_build_object(
            'orders',(SELECT count(*) FROM report.orders_current),
            'lines',(SELECT count(*) FROM report.order_lines_current),
            'units',(SELECT sum(quantity) FROM report.order_lines_current),
            'gross',(SELECT sum(line_gross_amount) FROM report.order_lines_current),
            'total',(SELECT sum(source_order_total_amount) FROM report.orders_current));"""]),parse_float=Decimal)
        expected=[facts(e,self.value['references']['mapping']) for e in self.expected()]
        totals=dict(orders=len(expected),lines=sum(len(f['lines']) for f in expected),
            units=sum(l[1] for f in expected for l in f['lines']),
            gross=sum(f['gross'] for f in expected),total=sum(f['total'] for f in expected))
        isolation.require(data==totals,'Report-role totals differ from independent purchase facts')
        self.result['report_totals']=data

    def reobserve(self):
        """Explicit full source reread, not just an incremental empty polling cycle."""
        start=stamp(datetime.fromisoformat(self.value['start'].replace('Z','+00:00'))-timedelta(seconds=1))
        end=stamp(clock())
        execution='temporal-reobserve-'+self.h.marker['id']+'-'+str(time.time_ns())
        for service in ('website-collector','ebay-collector'):
            self.h.run(service,'--window-start',start,'--window-end',end,
                '--observed-at',end,'--execution-id',execution)
        self.h.run('airflow','-m','ingestion.etsy','recovery','--window-start',start,'--window-end',end,
            '--execution-id',execution,entrypoint='/opt/airflow/project-venv/bin/python')
        self.repeat_notification()
        self.cli_wave()

    def repeat_notification(self):
        """Use an actually retained message, preserving body/event/identity on replay."""
        e=next(e for e in reversed(self.value['events']) if e['source']=='etsy_sim' and e['notify'])
        prior=rows(self.h,"SELECT i.webhook_id,r.parsed_payload->>'event_type' AS event_type FROM ops.webhook_inbox i "
            "JOIN raw.raw_records r ON r.raw_record_id=i.first_raw_record_id "
            "JOIN ops.processing_work w USING(inbox_id) WHERE w.source_system='etsy_sim' AND w.source_entity_id="+
            literal(e['order_id'])+" AND w.state='SUCCEEDED' ORDER BY i.first_received_at DESC LIMIT 1")
        isolation.require(bool(prior),'No completed notification to replay')
        count_sql="SELECT (SELECT count(*) FROM ops.webhook_inbox) AS logical,(SELECT count(*) FROM ops.webhook_delivery_attempts WHERE accepted) AS accepted"
        before=rows(self.h,count_sql)[0]
        event_wave=1 if prior[0]['event_type']=='order.paid' else 2
        for _ in range(2): self.deliver(e,event_wave,message_id=prior[0]['webhook_id'])
        after=rows(self.h,count_sql)[0]
        isolation.require(after['logical']==before['logical'] and after['accepted']==before['accepted']+2,
            'Duplicate signed notification logical/physical audit mismatch')
        self.result['duplicate_notification']=dict(before=before,after=after)

    def run(self):
        h=self.h
        try:
            h.sql((isolation.ROOT/'tests/m01_acceptance.sql').read_text())
            if (h.root/'evidence/prepared-source.json').exists():
                self.value=load_prepared(h)
            else:
                # Baseline all-due initial load; scheduled case contains actual future changes.
                duration=30 if self.profile=='baseline' else 1200
                start=clock()-timedelta(seconds=duration+60 if self.profile=='baseline' else 60)
                self.value=prepare(h,self.seed,self.count,duration,start)
            # A separately prepared immutable workload, not CLI defaults, owns its
            # actual seed/cardinality. Bind truthful metadata and history thresholds.
            self.seed=self.value['seed']; self.count=self.value['orders_per_channel']
            self.result.update(seed=self.seed,orders_per_channel=self.count)
            end=max(e['visible_at'] for e in self.value['events'])
            end_dt=datetime.fromisoformat(end.replace('Z','+00:00'))
            isolation.require(end_dt<clock()+timedelta(seconds=1800),'Prepared correctness schedule exceeds wait budget; load/one-day playback is separate')
            if self.profile=='baseline': isolation.require(end_dt<clock(),'Baseline requires all source versions already due')
            else: isolation.require(end_dt>clock()+timedelta(seconds=180),'Continuous requires future changes, not already-completed playback')
            self.result.update(dataset_sha256=checksum(self.value),prepared_versions=len(self.value['events']),
                config=self.value['version'],last_source_change=end)
            self.result['config_sha256']=checksum({k:v for k,v in self.result.items() if k not in ('config_sha256','phases')})
            install(h,self.value)
            h.dc(['up','--detach','--wait','--wait-timeout','180','ebay-sim','etsy-sim','etsy-receiver'])
            isolation.require(not snapshot(h)['orders'],'Temporal scope must start empty')
            self.tick()
            if self.profile=='baseline':
                self.cli_wave()
                isolation.require(self.match(snapshot(h),self.expected()),'Temporal baseline source/warehouse mismatch')
            else:
                h.dc(['up','--detach','--wait','--wait-timeout','420','airflow'],timeout=450)
                errors=h.dc(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json'])
                isolation.require(json.loads(errors)==[],'DAG import errors')
                self.wait(lambda:len(rows(h,'SELECT dag_id FROM dag','airflow_meta'))==7,'DAG discovery')
                self.dag('unpause',DAGS[:3])
                # Omitted receipt must remain absent before enabling recovery.
                def omission_barrier():
                    self.tick()
                    notified=[e for e in latest(self.value,datetime.now(timezone.utc)) if e['source']=='etsy_sim' and e['notify']]
                    actual=snapshot(h)
                    return bool(notified) and all(any(o['source_system']=='etsy_sim' and o['source_order_id']==e['order_id'] for o in actual['orders']) for e in notified)
                self.wait(omission_barrier,'scheduled notified Etsy orders')
                omitted={e['order_id'] for e in self.value['events'] if e['source']=='etsy_sim' and not e['notify']}
                isolation.require(not any(o['source_system']=='etsy_sim' and o['source_order_id'] in omitted for o in snapshot(h)['orders']),'Omitted Etsy receipt visible before recovery')
                self.result['omitted_absent_before_recovery']=True
                self.dag('unpause',('etsy_recovery',))
                def complete():
                    self.tick()
                    return clock()>=end_dt and self.match(snapshot(h),self.expected())
                self.wait(complete,'temporal final published source facts')
                self.wait(lambda:all(sum(r['dag_id']==d and r['state']=='success' for r in self.scheduled())>=2 for d in DAGS),'two real scheduled successes per path')
                self.finish_schedules()
            self.verify_authority()
            self.verify_report()
            before=snapshot(h)
            isolation.require(before['exceptions']==0 and before['pending']==0,'Unresolved temporal exceptions/work')
            self.history(before,expected_count=None)
            # Reuse observation-aware SQL evidence check, but no fixed v1 history12.
            history=rows(h,"SELECT source_system,count(*) AS versions FROM core.order_snapshot_history GROUP BY source_system")
            isolation.require(set(r['source_system'] for r in history)==set(ACCOUNTS),'Missing source history')
            missing=rows(h,"SELECT h.snapshot_id FROM core.order_snapshot_history h LEFT JOIN core.snapshot_evidence e USING(snapshot_id) GROUP BY h.snapshot_id HAVING count(e.raw_record_id)=0")
            isolation.require(not missing,'History missing raw evidence')
            if self.profile=='continuous':
                isolation.require(all(r['versions']>self.count for r in history),'Scheduled case did not observe source changes for every source')
                self.result['observed_versions_by_source']=history
            self.reobserve()
            after=snapshot(h)
            isolation.require(self.match(after,self.expected()) and business_signature(before)==business_signature(after),'Temporal replay changed logical facts/history')
            isolation.require(after['raw']>before['raw'],'Replay lost physical raw audit')
            for test in ('test_m05_http.py','test_m06_unit.py'):
                h.run('airflow','/repo/tests/'+test,reads=True,
                    entrypoint='/opt/airflow/project-venv/bin/python')
            self.result['legacy_regressions']=['test_m05_http.py','test_m06_unit.py']
            self.result.update(status='PASS',final_orders=len(after['orders']),final_lines=len(after['lines']),
                observed_versions=len(after['history']),raw_before_replay=before['raw'],raw_after_replay=after['raw'],finished_at=isolation.utc())
            print('M08B temporal '+self.profile+' correctness PASS',flush=True)
        finally:
            if self.result['status']=='RUNNING': self.result.update(status='FAIL',finished_at=isolation.utc())
            self.ledger.close()


def verify_retained(h, replay=False, notification=False):
    """Completed retained checks, optionally scoped replay; never a cold-run claim."""
    original=json.loads((h.root/'evidence/result.json').read_text(encoding='utf-8'))
    isolation.require(original.get('status')=='PASS' and (h.root/'evidence/accept.finished').exists(),
        'Read-only retained verification requires completed PASS')
    owner=isolation.owner_container(); isolation.owner_idle(owner)
    before=isolation.protected_signature(owner)
    campaign=object.__new__(TemporalCampaign)
    campaign.h=h; campaign.value=load_prepared(h); campaign.result={}
    result=dict(status='RUNNING',scope='retained duplicate notification' if notification else 'retained source replay' if replay else 'retained read-only history/report; not a cold rerun',
        code_hash=isolation.digest(Path(__file__)),started_at=isolation.utc())
    try:
        h.dc(['up','--detach','--wait','--wait-timeout','120','postgres'])
        if replay or notification:
            isolation.resource_preflight(h.marker,scheduled=False)
            services=['etsy-receiver'] if notification else ['ebay-sim','etsy-sim','etsy-receiver']
            h.dc(['up','--detach','--wait','--wait-timeout','180',*services])
            campaign.count=campaign.value['orders_per_channel']
            campaign.sequence=0
            with (h.root/'evidence'/('retained-replay-'+str(time.time_ns())+'.jsonl')).open('x',encoding='utf-8') as ledger:
                campaign.ledger=ledger
                original_snapshot=snapshot(h)
                if notification: campaign.repeat_notification()
                else: campaign.reobserve()
                after=snapshot(h)
                isolation.require(campaign.match(after,campaign.expected()) and
                    business_signature(original_snapshot)==business_signature(after),'Retained source replay changed logical data')
                isolation.require(after['raw']>original_snapshot['raw'],'Retained replay audit did not grow')
                result.update(raw_before=original_snapshot['raw'],raw_after=after['raw'])
        campaign.history(snapshot(h),expected_count=None)
        campaign.verify_report()
        result.update(status='PASS',**campaign.result)
    except Exception as error:
        result.update(status='FAIL',failure=str(error)); raise
    finally:
        try: h.dc(['down','--remove-orphans','--timeout','30']); result['teardown']='PASS'
        except Exception: result.update(status='FAIL',teardown='FAIL'); raise
        finally:
            after=isolation.protected_signature(owner)
            result['protected_check']='PASS' if before==after else 'FAIL'
            if before!=after: result['status']='FAIL'
            result.update(protected_before=before,protected_after=after,steps=h.steps,finished_at=isolation.utc())
            prefix='temporal-notification-' if notification else 'temporal-replay-' if replay else 'temporal-readonly-'
            path=h.root/'evidence'/(prefix+str(time.time_ns())+'.json')
            with path.open('x',encoding='utf-8') as handle: json.dump(result,handle,indent=2,default=str)
    isolation.require(result['status']=='PASS','Retained final-code check failed')
    label='duplicate notification/history/report' if notification else 'source replay/history/report' if replay else 'history/report'
    print('Temporal retained '+label+' PASS; not a cold/scheduled rerun')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('init','check','prepare','storage','accept','verify-retained','replay-retained','notification-retained','stop'))
    p.add_argument('--id'); p.add_argument('--seed',type=int,default=17)
    p.add_argument('--orders-per-channel',type=int,default=4)
    p.add_argument('--duration-seconds',type=int,default=86400)
    p.add_argument('--start-delay-seconds',type=int,default=0)
    p.add_argument('--profile',choices=('baseline','continuous'),default='continuous')
    p.add_argument('--ci',action='store_true')
    a=p.parse_args()
    isolation.require(not a.ci or a.action=='accept','CI mode is only for acceptance on owner-absent runners')
    if a.action=='init':
        isolation.require(a.id is None,'Init allocates ID')
        isolation.init(profile='m08b',backend='s02-pg'); return
    isolation.require(a.id is not None,'Explicit ID required')
    h=isolation.Harness(a.id)
    isolation.require(h.marker.get('backend')=='s02-pg','Not a temporal environment')
    if a.action=='check': h.check(); print('Temporal preflight PASS (not runtime acceptance)')
    elif a.action=='prepare': prepare(h,a.seed,a.orders_per_channel,a.duration_seconds,
        datetime.now(timezone.utc)+timedelta(seconds=a.start_delay_seconds))
    elif a.action=='storage': storage(h)
    elif a.action=='verify-retained': verify_retained(h)
    elif a.action=='replay-retained': verify_retained(h,replay=True)
    elif a.action=='notification-retained': verify_retained(h,notification=True)
    elif a.action=='accept':
        isolation.accept(h,baseline_fn=lambda harness:TemporalCampaign(harness,a.seed,a.profile,a.orders_per_channel).run(),
            scheduled=a.profile=='continuous',ci=a.ci)
    else:
        isolation.require(not (h.root/'evidence/accept.started').exists() or (h.root/'evidence/accept.finished').exists(),'Acceptance active/interrupted; inspect before recovery')
        h.dc(['down','--remove-orphans','--timeout','30'])


if __name__=='__main__':
    try: main()
    except isolation.SafetyError as error:
        print('M08B temporal refused/failed: '+str(error)+'. No automatic reset.',file=sys.stderr)
        sys.exit(1)
