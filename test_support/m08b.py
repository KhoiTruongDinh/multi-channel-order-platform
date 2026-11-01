"""Finite S02 driver/oracle. No source generator or truth ledger enters a DAG."""
import argparse
import base64
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import sys
import time
from urllib.request import Request, urlopen

from test_support import m08a as isolation
from test_support.s02_inputs import inputs, purchase_facts, stamp, VERSION, ACCOUNTS

DAGS = ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')


def clock():
    return datetime.now(timezone.utc).replace(microsecond=0)


def dt(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def rows(h, query, db='data_platform'):
    return json.loads(h.sql("SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM ("+query+") t;", db),
                      parse_float=Decimal)


def snapshot(h):
    query = """SELECT json_build_object(
      'orders',(SELECT coalesce(json_agg(t),'[]') FROM core.orders_current t),
      'lines',(SELECT coalesce(json_agg(t),'[]') FROM core.order_lines_current t),
      'history',(SELECT coalesce(json_agg(t),'[]') FROM core.order_snapshot_history t),
      'evidence',(SELECT count(*) FROM core.snapshot_evidence),
      'raw',(SELECT count(*) FROM raw.raw_records),
      'exceptions',(SELECT count(*) FROM ops.data_exceptions WHERE resolved_at IS NULL),
      'pending',(SELECT count(*) FROM ops.processing_work WHERE state<>'SUCCEEDED'),
      'publications',(SELECT coalesce(json_agg(t),'[]') FROM ops.publication_state t))"""
    return json.loads(h.sql(query), parse_float=Decimal)


def reconcile(actual, operations, subset=False, facts_fn=purchase_facts):
    expected = [facts_fn(op) for op in operations]
    found = {(o['source_system'],o['source_account_id'],o['source_order_id']):o for o in actual['orders']}
    if not subset and len(found) != len(expected):
        return False
    for fact in expected:
        key = fact['source'],fact['account'],fact['order_id']
        o = found.get(key)
        if not o or tuple(o[k] for k in ('payment_state','fulfillment_state','cancellation_state')) != fact['states']:
            return False
        if o['currency'] != fact['currency'] or o['items_gross_amount'] != fact['gross'] or o['source_order_total_amount'] != fact['total']:
            return False
        if dt(o['source_created_at']) != dt(fact['created']) or dt(o['source_updated_at']) != dt(fact['updated']):
            return False
        lines = [r for r in actual['lines'] if (r['source_system'],r['source_account_id'],r['source_order_id']) == key]
        desired = sorted((identity,q,price,price*q,variant,'USD') for identity,q,price,variant in fact['lines'])
        got = sorted((r['source_line_id'],r['quantity'],r['unit_gross_amount'],r['line_gross_amount'],
                      r['canonical_variant_id'],r['currency']) for r in lines)
        if got != desired or any(r['snapshot_id'] != o['snapshot_id'] or r['published_batch_id'] != o['published_batch_id'] for r in lines):
            return False
    return True


def business_signature(actual):
    def clean(values):
        return sorted((json.dumps({k:v for k,v in r.items() if k not in ('published_batch_id','batch_id')},
                                  sort_keys=True,default=str) for r in values))
    return clean(actual['orders']),clean(actual['lines']),clean(actual['history'])


class Campaign:
    def __init__(self, h, seed, profile):
        self.h, self.seed, self.profile = h, seed, profile
        self.epoch = clock()
        self.deadline = time.monotonic()+1800
        self.operations = []
        self.result = dict(scenario_version=VERSION, seed=seed, profile=profile,
            interval_seconds=int(h.model['services']['airflow']['environment']['WEBSITE_POLL_INTERVAL_SECONDS']),
            slot_wait_seconds=int(h.model['services']['airflow']['environment']['POLLING_SLOT_WAIT_SECONDS']),
            deadline_seconds=1800, started_at=isolation.utc(), phases=[],status='RUNNING',
            source_mix=list(ACCOUNTS),initial_target_orders=0,orders_per_channel=2,lines_per_order=2,
            max_source_operations=12,epoch=stamp(self.epoch),currency='USD')
        self.result['config_sha256']=hashlib.sha256(json.dumps(self.result,sort_keys=True).encode()).hexdigest()
        h.report['s02'] = self.result
        self.ledger = (h.root/'evidence/s02-ledger.jsonl').open('x', encoding='utf-8')
        self.sequence = 0

    def record(self, **value):
        self.sequence += 1
        self.ledger.write(json.dumps(dict(sequence=self.sequence,at=isolation.utc(),**value),default=str)+'\n')
        self.ledger.flush()

    def wait(self, probe, label):
        while True:
            isolation.require(time.monotonic()<self.deadline, 'S02 deadline exceeded: '+label)
            if probe():
                print('M08B '+label+' PASS',flush=True)
                return
            print('M08B waiting: '+label,flush=True)
            time.sleep(5)

    def url(self, service, target, path):
        port = next(p['published'] for p in self.h.model['services'][service]['ports'] if p['target']==target)
        return f'http://127.0.0.1:{port}{path}'

    def http(self, service, target, path, data=None, headers=None):
        self.h.check()
        request = Request(self.url(service,target,path), data=None if data is None else json.dumps(data).encode(),
                          headers={'Content-Type':'application/json',**(headers or {})})
        with urlopen(request,timeout=15) as response:
            isolation.require(response.status==200, 'S02 HTTP request not acknowledged')
            return json.loads(response.read(1048577))

    def generate(self, wave):
        operations = []
        for index in range(6):
            self.h.check()
            op = inputs(self.seed,wave,self.epoch,self.h.marker['id'],clock())[index]
            self.record(wave=wave,outcome='intended',**op)
            if op['source']=='internal_web':
                self.h.dc(['run','--rm','-T','--no-deps','--entrypoint','python','website-simulator',
                    '-m','simulator.website_s02'],payload=json.dumps(op['payload']))
            else:
                service = 'ebay-sim' if op['source']=='ebay_sim' else 'etsy-sim'
                token = self.h.model['services'][service]['environment']['S02_CONTROL_TOKEN']
                reply = self.http(service,8081,'/s02/upsert',op['payload'],{'X-S02-Control-Token':token})
                isolation.require(reply==dict(committed=True,identity=op['order_id']), 'Control commit identity mismatch')
            self.record(wave=wave,outcome='committed',**op)
            operations.append(op)
            self.operations.append(op)
            if op['source']=='etsy_sim':
                self.deliver(op,wave)
        self.result['phases'].append(dict(wave=wave,committed_at=isolation.utc(),orders=6))
        return operations

    def deliver(self, op, wave, message_id=None):
        message = message_id or f"s02-{self.h.marker['id']}-{wave}-{op['order_id']}"
        if not op['notify']:
            self.record(wave=wave,source='etsy_sim',order_id=op['order_id'],outcome='notification_omitted')
            return
        self.h.check()
        body = json.dumps(dict(event_type='order.paid' if wave==1 else 'order.shipped',shop_id=7001,
            resource_url=f"http://etsy-sim/v3/application/shops/7001/receipts/{op['order_id']}"),separators=(',',':')).encode()
        stamp_now = str(int(time.time()))
        key = self.h.model['services']['etsy-receiver']['environment']['ETSY_SIGNING_SECRET']
        signature = 'v1,'+base64.b64encode(hmac.new(base64.b64decode(key.removeprefix('whsec_')),
            message.encode()+b'.'+stamp_now.encode()+b'.'+body,hashlib.sha256).digest()).decode()
        request = Request(self.url('etsy-receiver',8000,'/webhooks/etsy'),data=body,headers={
            'Content-Type':'application/json','webhook-id':message,'webhook-timestamp':stamp_now,'webhook-signature':signature})
        with urlopen(request,timeout=15) as response:
            isolation.require(200<=response.status<300,'Notification not durably acknowledged')
            response.read()
            self.record(wave=wave,source='etsy_sim',order_id=op['order_id'],outcome='delivered',
                        message_id=message,response_status=response.status)
            return response.status

    def dag(self, action, names):
        for name in names:
            isolation.require(name in DAGS,'Unexpected B DAG target')
            self.h.dc(['exec','-T','airflow','airflow','dags',action,name])

    def scheduled(self):
        return rows(self.h,"SELECT dag_id,run_id,state,start_date,end_date FROM dag_run WHERE run_type='scheduled' ORDER BY dag_id,start_date",'airflow_meta')

    def terminal_schedules(self):
        runs=self.scheduled()
        isolation.require(all(r['state']=='success' for r in runs), 'Non-success scheduled run after drain')
        isolation.require(all(sum(r['dag_id']==d for r in runs)>=2 for d in DAGS), 'Missing terminal scheduled successes')
        self.result['scheduled_runs']=runs
        return runs

    def finish_schedules(self):
        self.h.dc(['exec','-T','airflow','python','-c',
            "from pathlib import Path; Path('/opt/airflow/state/polling-drain').touch(exist_ok=False)"])
        def null_timetables():
            timetable=rows(self.h,"""SELECT DISTINCT ON (dag_id) dag_id,
                data->'dag'->'timetable'->>'__type' AS kind FROM serialized_dag
                WHERE dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')
                ORDER BY dag_id,created_at DESC""",'airflow_meta')
            return len(timetable)==4 and all((r['kind'] or '').endswith('.NullTimetable') for r in timetable)
        self.wait(null_timetables,'no new intervals (serialized NullTimetables)')
        self.wait(lambda:not rows(self.h,"SELECT run_id FROM dag_run WHERE state IN ('queued','running')",'airflow_meta'),
                  'test scheduled work terminal')
        self.terminal_schedules()
        self.dag('pause',DAGS)

    def wait_wave(self, operations, wave):
        self.wait(lambda:reconcile(snapshot(self.h),operations),f'wave{wave} published current facts')
        phase = self.result['phases'][-1]
        phase['published_at'] = isolation.utc()
        phase['publication'] = snapshot(self.h)['publications']
        def correlated():
            successes = {(r['dag_id'],r['run_id']) for r in self.scheduled() if r['state']=='success'}
            parents = rows(self.h,"""SELECT p.airflow_dag_id,p.airflow_run_id,p.run_id,p.batch_id,b.published_at
                FROM ops.pipeline_runs p JOIN ops.transform_batches b ON b.batch_id=p.batch_id
                WHERE p.status='SUCCEEDED' AND b.status='PUBLISHED' AND p.airflow_dag_id IS NOT NULL
                  AND b.published_at >= '"""+phase['committed_at']+"'::timestamptz")
            matches=[p for p in parents if (p['airflow_dag_id'],p['airflow_run_id']) in successes]
            if set(p['airflow_dag_id'] for p in matches) >= set(DAGS):
                phase['scheduled_publications'] = matches
                return True
            return False
        self.wait(correlated,f'wave{wave} scheduled publication lineage')

    def cli(self, source, mode='recovery'):
        self.h.run('airflow','-m','orchestration.polling','--source',source,
            '--collection-mode',mode,'--execution-id',f"s02-{self.h.marker['id']}-{len(self.h.steps)}",
            '--window-end',stamp(clock()),'--initial-start',stamp(self.epoch-timedelta(days=1)),
            '--wait-seconds','120',entrypoint='/opt/airflow/project-venv/bin/python',timeout=300)

    def cli_wave(self):
        for source in ACCOUNTS:
            if source=='etsy_sim':
                self.cli(source,'drain')  # Recovery intentionally drains only its own list work.
            self.cli(source)

    def empty_acquisitions(self):
        """Explicit empty-window audit after scheduled phases, never a manual assist."""
        point=stamp(clock())
        execution='s02-empty-'+self.h.marker['id']
        for service in ('website-collector','ebay-collector'):
            self.h.run(service,'--window-start',point,'--window-end',point,'--observed-at',point,
                       '--execution-id',execution)
        self.h.run('airflow','-m','ingestion.etsy','recovery','--window-start',point,'--window-end',point,
                   '--execution-id',execution,entrypoint='/opt/airflow/project-venv/bin/python')
        counts=rows(self.h,"""SELECT source_system,count(*) AS pages FROM raw.raw_records
            WHERE parsed_payload->'orders'='[]'::jsonb OR parsed_payload->'results'='[]'::jsonb
            GROUP BY source_system""")
        isolation.require(set(r['source_system'] for r in counts)==set(ACCOUNTS), 'Empty source acquisitions not audited')
        self.result['empty_acquisitions']=counts

    def authority(self, final):
        authoritative = []
        for op in final:
            source=op['source']
            if source=='internal_web':
                payload = json.loads(self.h.dc(['run','--rm','-T','--no-deps','--entrypoint','python',
                    'website-collector','-c',"import json; from ingestion.website import acquire_source,parse_time; print(json.dumps(acquire_source(parse_time('2000-01-01T00:00:00Z'),parse_time('"+stamp(clock())+"'))))"]))
                identity=op['order_id']
                selected={k:[] for k in payload}
                selected['orders']=[r for r in payload['orders'] if r['order_id']==identity]
                for k in ('order_items','payment_transactions','cancellation_requests','shipments'):
                    selected[k]=[r for r in payload[k] if r['order_id']==identity]
                authoritative.append(dict(op,payload=selected))
            elif source=='ebay_sim':
                token=self.h.model['services']['ebay-sim']['environment']['EBAY_SIM_TOKEN']
                path='/sell/fulfillment/v1/order/'+op['order_id']
                order=self.http('ebay-sim',80,path,headers={'Authorization':'Bearer '+token})
                fulfillments=self.http('ebay-sim',80,path+'/shipping_fulfillment',headers={'Authorization':'Bearer '+token})['fulfillments']
                authoritative.append(dict(op,payload=dict(order=order,fulfillments=fulfillments)))
            else:
                token=self.h.model['services']['etsy-sim']['environment']['ETSY_SIM_TOKEN']
                receipt=self.http('etsy-sim',80,'/v3/application/shops/7001/receipts/'+op['order_id'],headers={'Authorization':'Bearer '+token})
                authoritative.append(dict(op,payload=receipt))
        isolation.require([purchase_facts(o) for o in authoritative]==[purchase_facts(o) for o in final],
                          'Authoritative source differs from acknowledged generator facts')
        isolation.require(reconcile(snapshot(self.h),authoritative),'Final source/warehouse reconciliation failed')

    def history(self, actual, expected_count=12):
        raw = rows(self.h,"SELECT source_system,source_account_id,parsed_payload FROM raw.raw_records WHERE response_status=200 OR request_method='SQL_READ_ONLY'")
        observed=set()
        for r in raw:
            p=r['parsed_payload'] or {}
            source=r['source_system']; account=r['source_account_id']
            if source=='internal_web':
                observed.update((source,account,o['order_id'],dt(o['updated_at'])) for o in p.get('orders',[]))
            elif source=='ebay_sim':
                values=p.get('orders',[]) if 'orderId' not in p else [p]
                observed.update((source,account,o['orderId'],dt(o['lastModifiedDate'])) for o in values)
            elif source=='etsy_sim':
                values=p.get('results',[]) if 'receipt_id' not in p else [p]
                observed.update((source,account,str(o['receipt_id']),datetime.fromtimestamp(o['updated_timestamp'],timezone.utc)) for o in values)
        history={(r['source_system'],r['source_account_id'],r['source_order_id'],dt(r['source_updated_at'])) for r in actual['history']}
        isolation.require(history==observed and len(history)==len(actual['history'])
            and (expected_count is None or len(history)==expected_count),'History not equal to distinct retained observations')
        missing=rows(self.h,"""SELECT h.snapshot_id FROM core.order_snapshot_history h
          LEFT JOIN core.snapshot_evidence e USING(snapshot_id) LEFT JOIN raw.raw_records r USING(raw_record_id)
          GROUP BY h.snapshot_id HAVING count(r.raw_record_id)=0 OR bool_or(r.source_system<>h.source_system OR r.source_account_id<>h.source_account_id)""")
        isolation.require(not missing,'Missing/cross-scoped history evidence')
        self.result['observed_versions']=len(history)

    def run(self):
        h=self.h
        try:
            h.sql((isolation.ROOT/'tests/m01_acceptance.sql').read_text())
            h.dc(['up','--detach','--wait','--wait-timeout','180','ebay-sim','etsy-sim','etsy-receiver'])
            # B uses fresh EMPTY source/warehouse, never S01 seed in this scope.
            isolation.require(not snapshot(h)['orders'],'S02 scope must start empty')
            if self.profile=='continuous':
                h.dc(['up','--detach','--wait','--wait-timeout','420','airflow'],timeout=450)
                errors=h.dc(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json'])
                isolation.require(json.loads(errors)==[],'DAG import errors')
                self.wait(lambda:len(rows(h,'SELECT dag_id FROM dag','airflow_meta'))==7,'DAG discovery')
            first=self.generate(1)
            if self.profile=='baseline':
                self.cli_wave()
                isolation.require(reconcile(snapshot(h),first),'Baseline wave1 mismatch')
            else:
                self.dag('unpause',DAGS[:3])
                notified=[op for op in first if op.get('notify')]
                omitted=next(op for op in first if op['source']=='etsy_sim' and not op['notify'])
                self.wait(lambda:reconcile(snapshot(h),notified,subset=True),'scheduled inbox notification publication')
                isolation.require(not any(r['source_system']=='etsy_sim' and r['source_order_id']==omitted['order_id'] for r in snapshot(h)['orders']),
                                  'Omitted receipt unexpectedly published before recovery')
                self.result['omitted_absent_before_recovery']=True
                self.dag('unpause',('etsy_recovery',))
                self.wait_wave(first,1)
            final=self.generate(2)
            if self.profile=='baseline':
                self.cli_wave()
                isolation.require(reconcile(snapshot(h),final),'Baseline wave2 mismatch')
            else:
                self.wait_wave(final,2)
                def two_cycles():
                    successes=self.scheduled()
                    return all(sum(r['dag_id']==d and r['state']=='success' for r in successes)>=2 for d in DAGS)
                self.wait(two_cycles,'two real scheduled successes per path')
                self.result['scheduled_runs']=self.scheduled()
                isolation.require(not any(r['state']=='failed' for r in self.result['scheduled_runs']),'Unexpected failed scheduled run')
                self.finish_schedules()
                # No silent reset/clear/unpause if pausing strands an actual failure.
            self.authority(final)
            actual=snapshot(h)
            isolation.require(actual['exceptions']==0 and actual['pending']==0,'Unresolved exceptions/work')
            recovered=rows(h,"""SELECT w.source_entity_id,w.work_id,c.run_id FROM ops.processing_work w
                JOIN ops.etsy_work_context c USING(work_id) WHERE w.source_system='etsy_sim'
                AND w.inbox_id IS NULL AND w.state='SUCCEEDED' AND c.cycle_id LIKE 'recovery:%'""")
            omitted_id=next(o['order_id'] for o in final if o['source']=='etsy_sim' and not o['notify'])
            isolation.require(any(r['source_entity_id']==omitted_id for r in recovered),'No notification-free recovery work evidence')
            inbox=rows(h,"""SELECT i.webhook_id,w.source_entity_id,w.work_id FROM ops.webhook_inbox i
                JOIN ops.processing_work w USING(inbox_id) WHERE i.fetch_state='SUCCEEDED' AND w.state='SUCCEEDED'""")
            isolation.require(len(inbox)==2,'Notified receipt waves not durably processed')
            self.result.update(recovered_work=recovered,inbox_work=inbox)
            self.history(actual)
            # Explicit repeated source observations, then runtime CLI releases from
            # retained raw. This phase is replay evidence, NOT scheduler evidence.
            before=business_signature(actual)
            start=stamp(self.epoch-timedelta(minutes=1)); end=stamp(clock())
            for service in ('website-collector','ebay-collector'):
                h.run(service,'--window-start',start,'--window-end',end,'--observed-at',end,
                    '--execution-id','s02-reobserve-'+h.marker['id'])
            self.deliver(next(o for o in final if o.get('notify')),2)
            h.run('airflow','-m','ingestion.etsy','recovery','--window-start',start,'--window-end',end,
                '--execution-id','s02-reobserve-'+h.marker['id'],entrypoint='/opt/airflow/project-venv/bin/python')
            self.empty_acquisitions()
            for source in ACCOUNTS:
                self.cli(source)
            after=snapshot(h)
            isolation.require(after['raw']>actual['raw'],'Physical replay audit did not grow')
            isolation.require(business_signature(after)==before,'Replay inflated/regressed logical data')
            self.history(after)
            delivery=rows(h,"""SELECT (SELECT count(*) FROM ops.webhook_inbox) AS logical_messages,
                (SELECT count(*) FROM ops.webhook_delivery_attempts WHERE accepted) AS physical_deliveries""")[0]
            isolation.require(delivery==dict(logical_messages=2,physical_deliveries=3),'Repeated signed delivery audit/dedupe mismatch')
            report=json.loads(h.dc(['exec','-T','postgres','psql','-XAt','--set','ON_ERROR_STOP=1',
                '-U','platform_report','-d','data_platform','-c',"""SELECT json_build_object(
                'orders',(SELECT count(*) FROM report.orders_current),
                'lines',(SELECT count(*) FROM report.order_lines_current),
                'units',(SELECT sum(quantity) FROM report.order_lines_current),
                'gross',(SELECT sum(line_gross_amount) FROM report.order_lines_current),
                'total',(SELECT sum(source_order_total_amount) FROM report.orders_current));"""]),parse_float=Decimal)
            facts=[purchase_facts(o) for o in final]
            expected_report=dict(orders=6,lines=12,units=sum(q for f in facts for _,q,_,_ in f['lines']),
                gross=sum(f['gross'] for f in facts),total=sum(f['total'] for f in facts))
            isolation.require(report==expected_report,'Read-only report totals differ from authoritative source facts')
            for test in ('test_m05_http.py','test_m06_unit.py'):
                h.run('airflow',f'/repo/tests/{test}',reads=True,entrypoint='/opt/airflow/project-venv/bin/python')
            h.run('airflow','-c',"import os; assert all(not os.path.exists('/repo/'+p) for p in ('runtime','.env','.git')); print('S02 narrow test-mount boundary PASS')",
                  reads=True,entrypoint='/opt/airflow/project-venv/bin/python')
            self.result.update(status='PASS',final_orders=len(after['orders']),final_lines=len(after['lines']),
                raw_before_replay=actual['raw'],raw_after_replay=after['raw'],evidence=after['evidence'],
                delivery=delivery,report_totals=report,operations_committed=len(self.operations),finished_at=isolation.utc())
            print('M08B finite S02 '+self.profile+' correctness PASS',flush=True)
        finally:
            if self.result['status']=='RUNNING':
                self.result.update(status='FAIL',finished_at=isolation.utc())
            self.ledger.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('init','check','accept','stop'))
    p.add_argument('--id')
    p.add_argument('--seed',type=int,default=17)
    p.add_argument('--profile',choices=('baseline','continuous'),default='continuous')
    p.add_argument('--ci',action='store_true')
    a=p.parse_args()
    isolation.require(0<=a.seed<=2147483647,'Seed out of bounds')
    if a.action=='init':
        isolation.require(a.id is None,'Init allocates its own ID')
        isolation.init(profile='m08b')
        return
    isolation.require(a.id is not None,'Explicit test ID required')
    h=isolation.Harness(a.id)
    isolation.require(h.marker.get('profile')=='m08b','Not a B environment; create a fresh B ID')
    if a.action=='check':
        h.check()
        print('M08B preflight PASS (not runtime acceptance)')
    elif a.action=='stop':
        isolation.require(not (h.root/'evidence/accept.started').exists() or (h.root/'evidence/accept.finished').exists(),
                          'Acceptance active/interrupted; inspect before recovery')
        h.dc(['down','--remove-orphans','--timeout','30'])
    else:
        isolation.accept(h,baseline_fn=lambda harness:Campaign(harness,a.seed,a.profile).run(),ci=a.ci)


if __name__=='__main__':
    try:
        main()
    except isolation.SafetyError as error:
        print('M08B refused/failed: '+str(error)+'. No automatic reset.',file=sys.stderr)
        sys.exit(1)
