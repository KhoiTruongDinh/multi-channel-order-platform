"""Explicit fresh isolated source-storage/HTTP probe; never changes owner services."""
import json
from pathlib import Path
import sys
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import m08a as guard
from tools.s02_data.config import validate
from tools.s02_data.load import prepare,query,ROOT
from test_support.s02_plan import literal


class Adapter:
    def __init__(self,h): self.h=h
    def sql(self,sql,db='marketplace_sim'): return self.h.sql(sql,db)
    def command(self,args,body=None,timeout=180): return self.h.dc(args,payload=body,timeout=timeout)
    def model(self): return self.h.model


def run():
    identity=guard.init(profile='m08b',backend='s02-pg')
    h=guard.Harness(identity); db=Adapter(h)
    guard.resource_preflight(h.marker,scheduled=False)
    owner=guard.owner_container(); guard.owner_idle(owner)
    protected=guard.protected_signature(owner)
    names=['tools/s02_data/config.py','tools/s02_data/generate.py','tools/s02_data/references.py',
           'tools/s02_data/load.py','tools/s02_data/playback.py','orchestration/polling.py',
           'orchestration/source_clock.py','simulator/s02_temporal.py',
           'migrations/marketplace_sim/002_local_playback.sql','tests/m08b_local_probe.py']
    result=dict(id=identity,status='RUNNING',started_at=guard.utc(),
        scope='source storage/HTTP and CLI pipeline, NOT real scheduled acceptance',checks=[],
        code_hashes={name:guard.digest(ROOT/name) for name in names})
    try:
        h.dc(['build','ebay-sim','etsy-sim'])
        h.dc(['up','--detach','--wait','--wait-timeout','180','postgres'])
        h.test_db(first=True)
        config=validate(json.loads((ROOT/'tools/s02_data/config/coverage.json').read_text()))
        # Source campaign must match the guarded model, while the friendly name stays explicit.
        import tools.s02_data.load as loading
        original=loading.campaign_id
        loading.campaign_id=lambda name:identity
        # Generation and loading share the same namespace in this isolated probe.
        import tools.s02_data.generate as generation
        gen_original=generation.campaign_id; generation.campaign_id=lambda name:identity
        try: prepared=prepare(db,config)
        finally: loading.campaign_id=original; generation.campaign_id=gen_original
        result['manifest']=prepared['manifest']
        result['checks'].append('prepare READY with six orders per channel and required lifecycle cases')
        ref_counts=query(db,'SELECT (SELECT count(*) FROM public.customers) AS customers,(SELECT count(*) FROM public.products) AS products,(SELECT count(*) FROM public.product_variants) AS variants','website_source')[0]
        assert ref_counts==dict(customers=100,products=30,variants=30)
        result['checks'].append('Website references materialized during manual preparation')
        counts=query(db,'SELECT (SELECT count(*) FROM s02.website_versions) AS web_versions,(SELECT count(*) FROM s02.orders) AS marketplace_orders')
        assert counts[0]['web_versions']>=6 and counts[0]['marketplace_orders']==12
        # Seal, role and immutable Website plan checks via real PostgreSQL.
        db.sql("DO $$ BEGIN BEGIN UPDATE s02.website_versions SET sequence=999; RAISE EXCEPTION 'mutation succeeded'; EXCEPTION WHEN raise_exception THEN IF SQLERRM='mutation succeeded' THEN RAISE; END IF; END; END $$;")
        for source in ('ebay','etsy'):
            password=h.model['services'][source+'-sim']['environment']['S02_DB_PASSWORD']
            db.sql('ALTER ROLE s02_'+source+'_reader PASSWORD '+literal(password)+';')
        db.sql("INSERT INTO s02.playback VALUES(TRUE,"+literal(identity)+",'replay','2026-10-19T00:00:00Z',clock_timestamp(),NULL);")
        h.dc(['up','--detach','--wait','--wait-timeout','180','ebay-sim','etsy-sim'])
        def get(kind,path):
            service=h.model['services'][kind+'-sim']
            port=next(p['published'] for p in service['ports'] if p['target']==80)
            token=service['environment'][kind.upper()+'_SIM_TOKEN']
            with urlopen(Request(f'http://127.0.0.1:{port}'+path,headers={'Authorization':'Bearer '+token}),timeout=15) as response:
                return json.load(response)
        clock=get('ebay','/s02/clock')
        assert clock['mode']=='replay' and clock['campaign_id']==identity
        empty=get('ebay','/sell/fulfillment/v1/order?filter=lastmodifieddate:[2026-01-01T00:00:00Z..2026-12-01T00:00:00Z]')
        assert empty['total']==0
        result['checks'].append('HTTP replay clock and no-future visibility')
        db.sql("UPDATE s02.playback SET logical_start='2026-10-31T00:00:00Z',real_start=clock_timestamp();")
        current=get('ebay','/sell/fulfillment/v1/order?filter=lastmodifieddate:[2026-01-01T00:00:00Z..2026-12-01T00:00:00Z]')
        assert current['total']==6
        result['checks'].append('HTTP final source reconstruction, six eBay orders')
        db.sql('UPDATE s02.playback SET stopped_at=clock_timestamp();')
        assert not get('ebay','/s02/clock')['running']
        result['checks'].append('frozen clock visible over authenticated HTTP')
        # CLI pipeline uses the SAME logical HTTP clock without a second scheduler.
        guard.resource_preflight(h.marker,scheduled=False)
        h.dc(['build','airflow','website-simulator'])
        h.dc(['up','--detach','--wait','--wait-timeout','120','etsy-receiver'])
        from tools.s02_data.playback import resume,tick
        resume(db); tick(db)
        for source,mode in (('internal_web','recovery'),('ebay_sim','recovery'),('etsy_sim','drain'),('etsy_sim','recovery')):
            h.dc(['run','--rm','-T','--no-deps','--env','S02_LOCAL_PLAYBACK=true','--env','S02_CAMPAIGN_ID='+identity,
                '--entrypoint','/opt/airflow/project-venv/bin/python','airflow','-m','orchestration.polling',
                '--source',source,'--collection-mode',mode,'--execution-id','local-clock-probe-'+source+'-'+mode,
                '--window-end','2026-10-31T00:00:00Z','--initial-start','2026-10-01T00:00:00Z'],timeout=600)
        counts=query(db,'SELECT source_system,count(*) AS n FROM core.orders_current GROUP BY source_system','data_platform')
        assert {r['source_system']:r['n'] for r in counts}==dict(internal_web=6,ebay_sim=6,etsy_sim=6)
        assert query(db,"SELECT count(*) AS n FROM ops.polling_cycles WHERE settings->'logical_clock'->>'campaign_id'="+literal(identity),'data_platform')[0]['n']==4
        result['checks'].append('three-source CLI acquisition/dbt/publication with immutable persisted replay bounds')
        result['status']='PASS'
    except BaseException as error:
        result.update(status='FAIL',error=type(error).__name__+': '+str(error)); raise
    finally:
        try:
            h.dc(['down','--remove-orphans','--timeout','30'])
            result['teardown']='PASS'
        finally:
            result['owner_unchanged']=guard.protected_signature(owner)==protected
            result['finished_at']=guard.utc()
            result['steps']=h.steps
            (h.root/'evidence/local-probe.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k not in ('manifest','steps')},indent=2))
    assert result['owner_unchanged']


if __name__=='__main__': run()
