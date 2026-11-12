"""Host-side finite baseline observer/oracle. Never imported by SIMs or DAGs."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import time

from tools.s02_data.load import ROOT,query
from tools.s02_data.generate import events
from tools.s02_data.references import references
from test_support.s02_oracle import facts
from test_support.s02_plan import literal

MIB=1048576
SERVICES=('postgres','airflow','ebay-sim','etsy-sim','etsy-receiver','live-source','report','scheduler-observer')


class SafetyCeiling(RuntimeError): pass


def at(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def memory_bytes(value):
    match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(B|KiB|MiB|GiB|TiB|kB|KB|MB|GB|TB)',value.strip())
    if not match: raise ValueError('invalid Docker memory sample')
    units={'B':1,'KiB':1024,'MiB':1024**2,'GiB':1024**3,'TiB':1024**4,
           'kB':1000,'KB':1000,'MB':1000**2,'GB':1000**3,'TB':1000**4}
    return int(Decimal(match[1])*units[match[2]])


def command(args):
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=60,cwd=ROOT)
    if result.returncode: raise RuntimeError('measurement command failed; private output suppressed')
    return result.stdout.strip()


def finite_plan(config,limits):
    total=sum(c['orders'] for c in config['channels'].values())
    if not 1<=total<=limits['max_orders']: raise ValueError('measurement order ceiling exceeded')
    versions=0; size=0; digest=hashlib.sha256(); expected={}; per_source={}
    mapping=references()['mapping']; buckets={}
    active=[c for c in config['channels'].values() if c['orders']]
    origin=min(at(c['start_at']) for c in active)
    for batch in events(config):
        encoded=json.dumps(batch,sort_keys=True,separators=(',',':')).encode()
        versions+=len(batch); size+=len(encoded); digest.update(encoded)
        if versions>limits['max_source_versions'] or size>limits['max_generated_bytes']:
            raise ValueError('measurement source version/byte ceiling exceeded')
        for index,op in enumerate(batch):
            f=facts(op,mapping); key=(f['source'],f['account'],f['order_id'])
            expected.setdefault(key,[]).append(f)
            per_source[f['source']]=per_source.get(f['source'],0)+1
            minute=int((at(op['visible_at'])-origin).total_seconds()//60)
            bucket=buckets.setdefault((f['source'],minute),dict(orders=0,versions=0))
            bucket['versions']+=1; bucket['orders']+=int(index==0)
    seconds=(max(at(c['end_at']) for c in active)-min(at(c['start_at']) for c in active)).total_seconds()
    return dict(orders=total,versions=versions,generated_bytes=size,sha256=digest.hexdigest(),
                versions_by_source=per_source,source_interval_seconds=seconds,
                offered_orders_per_second=total/seconds,
                minute_buckets=[dict(source=s,minute_offset=m,**v) for (s,m),v in sorted(buckets.items())]),expected


def wanted(expected):
    return ','.join('('+','.join(literal(v) for v in key)+')' for key in sorted(expected))


def warehouse(db,expected):
    cte='WITH wanted(source_system,source_account_id,source_order_id) AS (VALUES '+wanted(expected)+'),'
    cte+=' histories AS (SELECT h.*,b.status AS batch_status FROM core.order_snapshot_history h JOIN wanted USING(source_system,source_account_id,source_order_id) JOIN ops.transform_batches b USING(batch_id)) '
    selections={
        'orders':'SELECT o.* FROM core.orders_current o JOIN wanted USING(source_system,source_account_id,source_order_id)',
        'lines':'SELECT l.* FROM core.order_lines_current l JOIN wanted USING(source_system,source_account_id,source_order_id)',
        'history':'SELECT * FROM histories',
        'history_lines':'SELECT l.* FROM core.order_line_snapshot_history l JOIN histories USING(snapshot_id)',
        'evidence':'''SELECT h.snapshot_id,count(e.raw_record_id) n,
          count(*) FILTER(WHERE (r.source_system,r.source_account_id) IS DISTINCT FROM
          (h.source_system,h.source_account_id)) wrong_scope,
          count(*) FILTER(WHERE e.raw_record_id IS NOT NULL AND NOT EXISTS(
            SELECT FROM ops.batch_inputs i WHERE i.batch_id=h.batch_id AND i.raw_record_id=e.raw_record_id)) missing_manifest
          FROM histories h
          LEFT JOIN core.snapshot_evidence e USING(snapshot_id)
          LEFT JOIN raw.raw_records r USING(raw_record_id) GROUP BY h.snapshot_id'''}
    fields=["'observed_at',statement_timestamp()"]
    for name,sql in selections.items():
        fields.append(literal(name)+",(SELECT coalesce(json_agg(t),'[]') FROM ("+sql+") t)")
    return json.loads(db.sql(cte+'SELECT json_build_object('+','.join(fields)+');','data_platform'),parse_float=Decimal)


def key(row): return tuple(row[k] for k in ('source_system','source_account_id','source_order_id'))


def reconcile(actual,expected,shift):
    errors=[]
    def check_header(row,f):
        identity=key(row)
        for field,desired in zip(('payment_state','fulfillment_state','cancellation_state'),f['states']):
            if row[field]!=desired: errors.append([identity,field])
        for field,desired in (('currency',f['currency']),('items_gross_amount',f['gross']),('source_order_total_amount',f['total'])):
            if row[field]!=desired: errors.append([identity,field])
        for field,desired in (('source_created_at',f['created']),('source_updated_at',f['updated'])):
            if at(row[field])!=at(desired)+timedelta(seconds=shift): errors.append([identity,field])
    def check_lines(rows,f,snapshot_id):
        desired=sorted((identity,q,p,p*q,variant,f['currency'],'CONFIRMED') for identity,q,p,variant in f['lines'])
        found=sorted((r['source_line_id'],r['quantity'],r['unit_gross_amount'],r['line_gross_amount'],
                      r['canonical_variant_id'],r['currency'],r['mapping_status']) for r in rows)
        if found!=desired or any(r['snapshot_id']!=snapshot_id for r in rows):
            errors.append([(f['source'],f['account'],f['order_id']),'line_content_or_grain'])
    current={key(o):o for o in actual['orders']}
    if len(current)!=len(actual['orders']) or set(current)!=set(expected): errors.append(['current','identity_set'])
    for identity,versions in expected.items():
        row=current.get(identity)
        if row:
            check_header(row,versions[-1])
            lines=[r for r in actual['lines'] if key(r)==identity]
            check_lines(lines,versions[-1],row['snapshot_id'])
            if any(r['published_batch_id']!=row['published_batch_id'] for r in lines):
                errors.append([identity,'line_publication_link'])
    histories={r['snapshot_id']:r for r in actual['history']}
    evidence={r['snapshot_id']:r for r in actual['evidence']}
    seen=set()
    for h in actual['history']:
        identity=key(h); stamp=at(h['source_updated_at'])
        if (identity,stamp) in seen: errors.append([identity,'duplicate_observed_version'])
        seen.add((identity,stamp))
        candidates=[f for f in expected.get(identity,[]) if at(f['updated'])+timedelta(seconds=shift)==stamp]
        if len(candidates)!=1: errors.append([identity,'unplanned_history_timestamp']); continue
        check_header(h,candidates[0])
        check_lines([r for r in actual['history_lines'] if r['snapshot_id']==h['snapshot_id']],candidates[0],h['snapshot_id'])
        e=evidence.get(h['snapshot_id'])
        if not e or not e['n'] or e['wrong_scope'] or e['missing_manifest']:
            errors.append([identity,'missing_or_wrong_scope_raw_evidence'])
        if h['batch_status']!='PUBLISHED': errors.append([identity,'unpublished_history_batch'])
    for o in actual['orders']:
        h=histories.get(o['snapshot_id'])
        if not h or key(h)!=key(o) or at(h['source_updated_at'])!=at(o['source_updated_at']) or h['batch_id']!=o['published_batch_id']:
            errors.append([key(o),'current_history_link'])
    return dict(status='FAIL' if errors else 'PASS',orders=len(actual['orders']),lines=len(actual['lines']),
                observed_versions=len(actual['history']),planned_versions=sum(map(len,expected.values())),
                errors=errors[:100],error_count=len(errors),
                history_policy='observed versions checked; missed planned snapshots NOT required')


def quantile(values,fraction):
    return sorted(values)[max(0,math.ceil(len(values)*fraction)-1)] if values else None


class Monitor:
    def __init__(self,db,config,limits,report):
        self.db=db; self.limits=limits; self.report=report
        self.plan,self.expected=finite_plan(config,limits)
        self.value=dict(status='PREFLIGHT',source_plan=self.plan,samples=[],final_observations={},
            exact_commit_to_first_publication_latency='NOT_MEASURED',milestone_complete=False)
        report['measurement']=self.value
        self.value['final_progress']=[]
        self.envelope=None
        if 'load' in config.get('campaign',{}):
            from test_support.m08d_envelope import Envelope
            self.envelope=Envelope(config,self.value)
        self.initial_sizes=None; self.ids=[]; self.shift=None; self.since=None

    def before_prepare(self,config):
        from tools.s02_data.campaign import service
        from tools.s02_data.live import compose
        class Discovery:
            def command(_,args): return compose(self.db,args)
        self.plan,self.expected=finite_plan(config,self.limits)
        self.value['source_plan']=self.plan
        hardware=json.loads(command(['docker','info','--format',
            '{"memory_bytes":{{.MemTotal}},"cpu_count":{{.NCPU}},"server_version":"{{.ServerVersion}}"}']))
        if hardware['memory_bytes']<=0 or hardware['cpu_count']<=0: raise ValueError('missing Docker resource limits')
        self.hardware=hardware
        identities={}
        for name in SERVICES:
            row=service(Discovery(),name)
            if not row or row['State']!='running' or row.get('Health') not in ('healthy','',None):
                raise ValueError('measurement requires running healthy '+name)
            self.ids.append(row['ID'])
            settings=json.loads(command(['docker','inspect','--format',
                '{"image":"{{.Image}}","memory_limit_bytes":{{.HostConfig.Memory}},"nano_cpus":{{.HostConfig.NanoCpus}}}',row['ID']]))
            identities[name]=dict(container=row['ID'],**settings)
        self.value['frozen']=dict(config=config,limits=self.limits,hardware=hardware,services=identities,
            host_python=platform.python_version(),host_system=platform.system(),
            git_head=command(['git','rev-parse','HEAD']),scope='warm shared local stack; no exclusive campaign CPU attribution')
        env=json.loads(command(['docker','inspect','--format','{{json .Config.Env}}',identities['airflow']['container']]))
        allowed={'WEBSITE_POLL_INTERVAL_SECONDS','EBAY_POLL_INTERVAL_SECONDS',
                 'ETSY_INBOX_INTERVAL_SECONDS','ETSY_RECOVERY_INTERVAL_SECONDS','AIRFLOW__CORE__PARALLELISM',
                 'EBAY_PAGE_SIZE','ETSY_RECOVERY_PAGE_SIZE'}
        self.value['frozen']['scheduler_settings']={k:v for e in env for k,v in [e.split('=',1)] if k in allowed}
        self.sample()
        self.value['frozen']['retained']=query(self.db,'''SELECT
          (SELECT count(*) FROM core.orders_current) current_orders,
          (SELECT count(*) FROM core.order_lines_current) current_lines,
          (SELECT count(*) FROM core.order_snapshot_history) observed_versions,
          (SELECT count(*) FROM raw.raw_records) raw_records''','data_platform')[0]
        self.preparing=time.monotonic()

    def admitted(self,identity):
        row=query(self.db,'SELECT published_at,shift_seconds FROM s02.live_batches WHERE campaign_id='+literal(identity))[0]
        self.shift=row['shift_seconds']; self.since=row['published_at']
        self.value.update(status='OBSERVING',preparation_and_admission_seconds=time.monotonic()-self.preparing,admission=row)
        if self.envelope: self.envelope.admitted(self.since,self.shift)

    def ready(self):
        return self.envelope is None or self.envelope.ready()

    def sample(self,pending=0):
        begin=datetime.now(timezone.utc).isoformat()
        rows=[json.loads(line) for line in command(['docker','stats','--no-stream','--format','{{json .}}',*self.ids]).splitlines()]
        if len(rows)!=len(self.ids): raise ValueError('incomplete Docker resource sample')
        containers=[]
        for row in rows:
            used=memory_bytes(row['MemUsage'].split('/')[0]); cpu=float(row['CPUPerc'].removesuffix('%'))
            if not math.isfinite(cpu) or cpu<0: raise ValueError('invalid CPU sample')
            containers.append(dict(name=row['Name'],memory_bytes=used,cpu_percent=cpu))
        sizes=query(self.db,"SELECT datname,pg_database_size(oid) size_bytes FROM pg_database WHERE datname IN ('marketplace_sim','website_source','data_platform','airflow_meta') ORDER BY datname",'data_platform')
        if len(sizes)!=4: raise ValueError('missing database size sample')
        total=sum(r['size_bytes'] for r in sizes)
        if self.initial_sizes is None: self.initial_sizes=total
        disk=self.db.command(['exec','-T','postgres','df','-Pk','/var/lib/postgresql/data'])
        pg_free=int(disk.splitlines()[-1].split()[3])*1024
        sample=dict(started_at=begin,finished_at=datetime.now(timezone.utc).isoformat(),containers=containers,
            stack_memory_bytes=sum(r['memory_bytes'] for r in containers),databases=sizes,
            db_growth_bytes=total-self.initial_sizes,workspace_free_bytes=shutil.disk_usage(ROOT).free,
            pg_volume_free_bytes=pg_free,pending_sends=pending)
        self.value['samples'].append(sample)
        reasons=[]; l=self.limits
        if sample['stack_memory_bytes']>self.hardware['memory_bytes']*l['max_docker_memory_percent']/100: reasons.append('stack_memory')
        if any(r['memory_bytes']>l['max_container_memory_mb']*MIB for r in containers): reasons.append('container_memory')
        if min(sample['workspace_free_bytes'],pg_free)<l['min_free_disk_mb']*MIB: reasons.append('free_disk')
        if sample['db_growth_bytes']>l['max_db_growth_mb']*MIB: reasons.append('database_growth')
        if pending>l['max_pending_sends']: reasons.append('pending_sends')
        if reasons:
            self.value.update(status='CEILING_REACHED',ceiling_reasons=reasons)
            raise SafetyCeiling('measurement safety ceiling: '+','.join(reasons))

    def observe(self,state):
        self.sample(state['pending_sends'])
        # One SQL statement supplies the observation clock and the matched rows.
        rows=query(self.db,'''WITH wanted(source_system,source_account_id,source_order_id) AS (VALUES '''+wanted(self.expected)+''')
          SELECT w.source_system,w.source_account_id,w.source_order_id,c.source_updated_at,
          statement_timestamp() observed_at FROM wanted w LEFT JOIN core.orders_current c
          USING(source_system,source_account_id,source_order_id)''','data_platform')
        for row in rows:
            identity=key(row); expected_at=at(self.expected[identity][-1]['updated'])+timedelta(seconds=self.shift)
            if row['source_updated_at'] is None or at(row['source_updated_at'])!=expected_at: continue
            name=json.dumps(identity)
            self.value['final_observations'].setdefault(name,dict(source=identity[0],account=identity[1],order=identity[2],
                eligible_at=expected_at.isoformat(),first_sql_observed_at=row['observed_at'],
                observed_delay_seconds=(at(row['observed_at'])-expected_at).total_seconds()))
        from test_support.m08d_envelope import progress
        current=progress(self.expected,rows,self.shift)
        self.value['final_progress'].append(current)
        if self.envelope: self.envelope.observe(self.db,state,current)

    def finish(self):
        result=reconcile(warehouse(self.db,self.expected),self.expected,self.shift)
        self.value['reconciliation']=result
        observations=list(self.value['final_observations'].values())
        delays=[r['observed_delay_seconds'] for r in observations]
        missing=len(self.expected)-len(observations)
        budget=not missing and all(0<=delay<=self.limits['max_final_observed_delay_seconds'] for delay in delays)
        self.value['observed_delay']=dict(metric='scheduled final eligibility to first matching SQL observation; NOT exact commit/publication',
            samples=len(delays),censored=missing,p50_seconds=quantile(delays,.5),p95_seconds=quantile(delays,.95),
            quantile_method='nearest-rank',budget_seconds=self.limits['max_final_observed_delay_seconds'],status='PASS' if budget else 'FAIL')
        self.value['actual_website_commit_operations']='NOT_MEASURED: latest source progress is not a commit ledger'
        self.value['raw_window']=query(self.db,'''SELECT source_system,resource_type,response_status,
          count(*) physical_audits,sum(octet_length(raw_bytes)) received_bytes FROM raw.raw_records
          WHERE coalesce((metadata->>'fetched_at')::timestamptz,acquired_at)>='''+literal(self.since)+
          '''::timestamptz GROUP BY 1,2,3 ORDER BY 1,2,3''','data_platform')
        self.value['stage_summary']=query(self.db,'''SELECT source_system,stage,outcome,count(*) attempts,
          count(duration_ms) duration_samples,percentile_cont(.5) WITHIN GROUP(ORDER BY duration_ms) p50_ms,
          percentile_cont(.95) WITHIN GROUP(ORDER BY duration_ms) p95_ms FROM ops.execution_measurements
          WHERE started_at>='''+literal(self.since)+'''::timestamptz GROUP BY 1,2,3 ORDER BY 1,2,3''','data_platform')
        passed=result['status']=='PASS' and budget and self.ready()
        self.value.update(status='BASELINE_PASS' if passed else 'BASELINE_FAIL',
            attribution='Stage/resource samples cover concurrent stack work, not only campaign orders')
        if self.value['status']!='BASELINE_PASS': raise RuntimeError('bounded baseline reconciliation/observation budget failed')
        return self.value['status']


def inspect_report(db,path):
    from pathlib import Path
    from tools.s02_data.campaign_config import validate_measurement
    from tools.s02_data.config import validate
    from tools.s02_data.generate import campaign_id
    path=Path(path).resolve()
    if ROOT/'runtime' not in path.parents: raise ValueError('inspection report must be inside runtime')
    report=json.loads(path.read_text(encoding='utf-8'))
    config=validate(report['source_manifest']['config'])
    if campaign_id(config['dataset'])!=report['campaign_id']: raise ValueError('report source identity mismatch')
    _,expected=finite_plan(config,validate_measurement(config.get('campaign',{}).get('measurement',{})))
    row=query(db,'SELECT shift_seconds FROM s02.live_batches WHERE campaign_id='+literal(report['campaign_id']))
    if len(row)!=1: raise ValueError('report source batch is not admitted')
    return reconcile(warehouse(db,expected),expected,row[0]['shift_seconds'])


if __name__=='__main__':
    import argparse
    from tools.s02_data.load import LocalDB
    parser=argparse.ArgumentParser(description='Read-only reconciliation of one retained local campaign report')
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--report')
    actions.add_argument('--preflight-config')
    args=parser.parse_args()
    if args.preflight_config:
        from pathlib import Path
        from tools.s02_data.config import validate
        config=validate(json.loads(Path(args.preflight_config).read_text(encoding='utf-8')))
        report={}; monitor=Monitor(LocalDB(),config,config['campaign']['measurement'],report)
        monitor.before_prepare(config)
        result=dict(status='PASS',scope='read-only preflight, NOT runtime load acceptance',measurement=report['measurement'])
    else: result=inspect_report(LocalDB(),args.report)
    print(json.dumps(result,indent=2,default=str))
    raise SystemExit(0 if result['status']=='PASS' else 1)
