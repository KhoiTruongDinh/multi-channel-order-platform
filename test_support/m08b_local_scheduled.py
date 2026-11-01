"""Fresh isolated, real-scheduled acceptance of manual local clock modes."""
from datetime import datetime,timezone,timedelta
import json
import time

from test_support import m08a as guard
from test_support.m08b import Campaign,DAGS,rows,snapshot,business_signature
from test_support.m08b_temporal import TemporalCampaign
from test_support.s02_inputs import stamp
from test_support.s02_plan import literal,checksum
from tools.s02_data.config import validate,parse_time,zone
from tools.s02_data.load import prepare,query
from tools.s02_data.references import references
from tools.s02_data.playback import tick


def workload(seed=17,mode='replay'):
    if mode not in ('realtime','replay'): raise ValueError('unsupported local acceptance clock')
    value=dict(dataset='local-scheduled-replay',timezone='Asia/Bangkok',
        start_at='2026-10-20T01:00:00+07:00',end_at='2026-10-20T01:30:00+07:00',
        order_seed=seed,event_seed=91,profile='faults',channels={})
    for source,branch in [('internal_web','cancel'),('ebay_sim','ship'),('etsy_sim','ship')]:
        value['channels'][source]=dict(orders=2,required={'pending':1,branch:1},
            delay_seconds=[540,660],peak_hours=[dict(start='01:00',end='01:02',weight=100)])
    value['channels']['ebay_sim']['basket']=dict(lines_min=2,lines_max=8,quantity_min=1,quantity_max=5)
    value['channels']['etsy_sim']['notifications']=dict(omit=1,duplicate=0)
    if mode=='replay': return validate(value)
    # Exercise actual missing-date defaults, after the cold scheduler is healthy.
    value.pop('start_at'); value.pop('end_at')
    for source,c in value['channels'].items():
        c['orders']=6
        if source=='internal_web': c['required']['request']=1
        if source=='ebay_sim': c['required']['partial']=1
    value['dataset']='local-scheduled-realtime'
    value=validate(value)
    start=parse_time(value['start_at']).astimezone(zone(value['timezone']))
    minute=start.replace(second=0,microsecond=0)
    peak=dict(start=minute.strftime('%H:%M'),end=(minute+timedelta(minutes=2)).strftime('%H:%M'),weight=100000)
    for c in value['channels'].values(): c['peak_hours']=[dict(peak)]
    return validate(value)


class Adapter:
    def __init__(self,h): self.h=h
    def sql(self,sql,db='marketplace_sim'): return self.h.sql(sql,db)
    def command(self,args,body=None,timeout=180): return self.h.dc(args,payload=body,timeout=timeout)
    def model(self): return self.h.model


class LocalScheduledCampaign(TemporalCampaign):
    def __init__(self,h,seed=17,mode='replay'):
        if mode not in ('realtime','replay'): raise ValueError('unsupported local acceptance clock')
        super().__init__(h,seed,'continuous',6 if mode=='realtime' else 2)
        self.mode=mode
        self.db=Adapter(h)
        self.deadline=time.monotonic()+3600
        self.result.update(scenario_version='s02-local-scheduled-v2',deadline_seconds=3600,
                           backend='s02-local-'+mode,scope='real scheduled changing-source '+mode+', then explicit CLI dedupe')

    def advance_sources(self):
        tick(self.db)

    def start_scheduler(self):
        h=self.h
        h.dc(['up','--detach','--wait','--wait-timeout','420','airflow'],timeout=450)
        assert json.loads(h.dc(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json']))==[]
        self.wait(lambda:len(rows(h,'SELECT dag_id FROM dag','airflow_meta'))==7,'local DAG discovery')
        assert not rows(h,"SELECT dag_id FROM dag WHERE NOT is_paused AND dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')",'airflow_meta')

    def warm_sources(self,config):
        """Match the manual runbook: materialize initial source data before polling."""
        last_initial=max(parse_time(e['visible_at']) for e in self.value['events'] if e['sequence']==1)
        first_change=min(parse_time(e['visible_at']) for e in self.value['events'] if e['sequence']>1)
        def ready():
            self.advance_sources()
            now=parse_time(query(self.db,'SELECT logical_now FROM s02.playback_clock')[0]['logical_now'])
            assert now<first_change,'source warmup exceeded the initial-state observation budget'
            if now<last_initial: return False
            web=query(self.db,'SELECT count(*) AS n FROM public.orders','website_source')[0]['n']
            pending=query(self.db,'SELECT count(*) AS n FROM s02.deliveries WHERE campaign_id='+literal(self.h.marker['id'])+' AND NOT omitted AND due_at<='+literal(now.isoformat())+' AND delivered_at IS NULL')[0]['n']
            return web==config['channels']['internal_web']['orders'] and pending==0
        self.wait(ready,'initial source data ready before enabling polling')
        self.result['initial_sources_ready_at']=guard.utc()

    def run(self):
        h=self.h
        try:
            h.sql((guard.ROOT/'tests/m01_acceptance.sql').read_text())
            # Realtime is never frozen/rewound to compensate for cold startup.
            if self.mode=='realtime': self.start_scheduler()
            resolved_before=datetime.now(timezone.utc).replace(microsecond=0)
            config=workload(self.seed,self.mode)
            resolved_after=datetime.now(timezone.utc)
            if self.mode=='realtime':
                assert resolved_before<=parse_time(config['start_at'])<=resolved_after
                assert parse_time(config['end_at'])-parse_time(config['start_at'])==timedelta(hours=5)
            # Namespace adaptation is test-only: resource identity remains guard-owned.
            import tools.s02_data.load as loading
            import tools.s02_data.generate as generation
            load_id,gen_id=loading.campaign_id,generation.campaign_id
            loading.campaign_id=generation.campaign_id=lambda name:h.marker['id']
            try:
                self.value=dict(id=h.marker['id'],start=stamp(parse_time(config['start_at'])),
                    references=references(),events=[e for batch in generation.events(config) for e in batch])
                if self.mode=='realtime':
                    assert max(parse_time(e['visible_at']) for e in self.value['events'])<parse_time(config['start_at'])+timedelta(minutes=30),'finite correctness profile generated a late event'
                prepared=prepare(self.db,config)
            finally:
                loading.campaign_id,generation.campaign_id=load_id,gen_id
            self.result.update(manifest=prepared['manifest'],dataset_sha256=checksum(self.value),
                prepared_versions=len(self.value['events']),actual_order_count=sum(c['orders'] for c in config['channels'].values()))
            stored=query(self.db,'SELECT d.state,c.config FROM s02.local_datasets d JOIN s02.campaigns c ON c.id=d.campaign_id WHERE d.campaign_id='+literal(h.marker['id']))[0]
            assert stored['state']=='READY' and stored['config']==config
            counts=query(self.db,'SELECT source,count(DISTINCT order_id) AS orders FROM s02.versions WHERE campaign_id='+literal(h.marker['id'])+' GROUP BY source UNION ALL SELECT \'internal_web\',count(DISTINCT order_id) FROM s02.website_versions WHERE campaign_id='+literal(h.marker['id']))
            assert {r['source']:r['orders'] for r in counts}=={s:c['orders'] for s,c in config['channels'].items()}
            self.result['stored_config_and_order_counts']=counts
            self.result['rolling_five_hour_default_verified']=self.mode=='realtime'
            self.result['config_sha256']=checksum(config)
            self.result['code_hashes']={name:guard.digest(guard.ROOT/name) for name in (
                'test_support/m08b_local_scheduled.py','test_support/m08b_window.py','tools/s02_data/generate.py',
                'tools/s02_data/config.py','tools/s02_data/references.py','tools/s02_data/load.py',
                'tools/s02_data/playback.py','orchestration/polling.py','orchestration/source_clock.py',
                'simulator/s02_temporal.py','migrations/marketplace_sim/002_local_playback.sql')}
            for kind in ('ebay','etsy'):
                password=h.model['services'][kind+'-sim']['environment']['S02_DB_PASSWORD']
                self.db.sql('ALTER ROLE s02_'+kind+'_reader PASSWORD '+literal(password)+';')
            logical=parse_time(config['start_at']); identity=literal(h.marker['id'])
            self.db.sql("INSERT INTO s02.playback VALUES(TRUE,"+identity+","+literal(self.mode)+","+
                literal(logical.isoformat())+',clock_timestamp(),clock_timestamp());')
            h.dc(['up','--detach','--wait','--wait-timeout','180','ebay-sim','etsy-sim','etsy-receiver'])
            if self.mode=='replay': self.start_scheduler()
            assert not snapshot(h)['orders'],'fresh scope is not empty'
            # Source time starts only after cold startup; no fast-forward/time rewind.
            self.db.sql('UPDATE s02.playback SET real_start=clock_timestamp(),stopped_at=NULL;')
            self.result['playback_started_at']=guard.utc()
            if self.mode=='realtime':
                delta=query(self.db,'SELECT abs(extract(epoch FROM (logical_now-clock_timestamp()))) AS delta FROM s02.playback_clock')[0]['delta']
                assert delta<2,'realtime source clock differs from actual PostgreSQL clock'
                self.result['realtime_clock_delta_seconds']=delta
            self.warm_sources(config)
            self.dag('unpause',DAGS[:3])
            def notified_published():
                self.advance_sources()
                clock=query(self.db,'SELECT logical_now FROM s02.playback_clock')[0]['logical_now']
                due=[e for e in self.value['events'] if e['source']=='etsy_sim' and e['notify'] and parse_time(e['visible_at'])<=parse_time(clock)]
                actual=snapshot(h)
                return bool(due) and all(any(o['source_system']=='etsy_sim' and o['source_order_id']==e['order_id'] for o in actual['orders']) for e in due)
            self.wait(notified_published,'local notified Etsy orders published by schedules')
            omitted={e['order_id'] for e in self.value['events'] if e['source']=='etsy_sim' and not e['notify']}
            assert not any(o['source_system']=='etsy_sim' and o['source_order_id'] in omitted for o in snapshot(h)['orders'])
            self.result['omitted_absent_before_recovery']=True
            self.dag('unpause',('etsy_recovery',))
            last=max(parse_time(e['visible_at']) for e in self.value['events'])
            def final_published():
                self.advance_sources()
                t=parse_time(query(self.db,'SELECT logical_now FROM s02.playback_clock')[0]['logical_now'])
                return t>=last and self.match(snapshot(h),self.expected())
            self.wait(final_published,'local final facts published through real schedules')
            self.wait(lambda:all(sum(r['dag_id']==d and r['state']=='success' for r in self.scheduled())>=2 for d in DAGS),
                      'local two real scheduled successes per path')
            self.finish_schedules()
            self.verify_authority(); self.verify_report()
            before=snapshot(h)
            assert before['pending']==0 and before['exceptions']==0
            self.history(before,expected_count=None)
            observed=rows(h,'SELECT source_system,count(*) AS versions FROM core.order_snapshot_history GROUP BY source_system')
            assert len(observed)==3 and all(r['versions']>self.count for r in observed),'a source did not observe a change'
            self.result['observed_versions_by_source']=observed
            bounds=rows(h,"SELECT c.settings->'logical_clock' AS clock,p.requested_window_start,p.requested_window_end,p.airflow_dag_id,p.airflow_run_id FROM ops.polling_cycles c JOIN ops.pipeline_runs p USING(run_id)")
            assert bounds and all(r['clock'] and r['clock']['campaign_id']==h.marker['id'] and r['clock']['mode']==self.mode for r in bounds)
            self.result['logical_cycles']=bounds
            # This phase is explicitly after scheduled reconciliation, never assistance.
            self.reobserve()
            after=snapshot(h)
            assert self.match(after,self.expected()) and business_signature(before)==business_signature(after)
            assert after['raw']>before['raw']
            self.result.update(status='PASS',final_orders=len(after['orders']),final_lines=len(after['lines']),
                raw_before_replay=before['raw'],raw_after_replay=after['raw'],finished_at=guard.utc())
            print('M08B local scheduled '+self.mode+' correctness PASS',flush=True)
        finally:
            if self.result['status']=='RUNNING': self.result.update(status='FAIL',finished_at=guard.utc())
            self.ledger.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','check','accept'))
    parser.add_argument('--id')
    parser.add_argument('--mode',choices=('replay','realtime'),default='replay')
    parser.add_argument('--ci',action='store_true')
    args=parser.parse_args()
    if args.action=='init':
        print('M08B initialized id='+guard.init(profile='m08b',backend='s02-pg',local_playback=True))
    else:
        h=guard.Harness(args.id)
        guard.require(h.marker.get('local_playback') is True,'Local-playback marker required')
        if args.action=='check': h.check(); print('M08B local preflight PASS (not acceptance)')
        else: guard.accept(h,ci=args.ci,baseline_fn=lambda env:LocalScheduledCampaign(env,mode=args.mode).run())
