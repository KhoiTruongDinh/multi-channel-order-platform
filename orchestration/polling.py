"""Persist current-clock cycles and serialize complete source releases."""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb
from orchestration import website_workflow as workflow
from ingestion.website import parse_time
from transformation.batch import connect as release_connection
from transformation.source_config import SOURCES


def prepare(args):
    args.airflow_run_id=getattr(args,'airflow_run_id',None) or args.execution_id
    args.execution_id = f'poll:{args.source}:{args.execution_id}'
    args.workflow_id=workflow.identity(args.execution_id,'workflow')
    args.batch_id=workflow.identity(args.execution_id,'batch')
    args.validation_mode='runtime'
    args.checkpoint_stream=(getattr(args,'checkpoint_stream',None) or 'receipts_polling') if args.source=='etsy_sim' else 'orders_polling'
    args.observed_at=datetime.now(timezone.utc)
    account=SOURCES[args.source][0]
    settings={k:getattr(args,k) for k in ('fault_after_raw_once','fault_after_freeze_once','inject_test_failure')}
    drain = args.source=='etsy_sim' and args.collection_mode=='drain'
    if args.source=='etsy_sim':
        settings['collection_mode']=args.collection_mode
        settings['checkpoint_stream']=args.checkpoint_stream
    config=('runtime','current',args.mapping_version,args.transformation_version,args.overlap_seconds,settings)
    with workflow.connect() as conn:
        # Same-cycle preparation must not race checkpoint advancement or itself.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(str(args.workflow_id),))
        prior=conn.execute('''SELECT p.requested_window_start,p.requested_window_end,p.airflow_dag_id,
            c.validation_mode,c.clock_mode,c.mapping_version,c.transformation_version,c.overlap_seconds,c.settings,p.airflow_run_id
            FROM ops.polling_cycles c JOIN ops.pipeline_runs p USING(run_id) WHERE c.run_id=%s''',(args.workflow_id,)).fetchone()
        if prior:
            if len(prior)>9 and prior[9] != (args.airflow_run_id if args.dag_id else None):
                raise ValueError('existing cycle has different bounds/context/configuration')
            if getattr(args,'reuse_cycle_config',False):
                if prior[1]!=args.window_end or prior[2]!=args.dag_id:
                    raise ValueError('existing cycle has different bounds/context/configuration')
                args.mapping_version,args.transformation_version,args.overlap_seconds=prior[5:8]
                if set(prior[8])-{'fault_after_raw_once','fault_after_freeze_once','inject_test_failure','collection_mode','checkpoint_stream'}:
                    raise ValueError('unsupported persisted cycle settings')
                for key,value in prior[8].items():
                    setattr(args,key,value)
                args.window_start=prior[0]
                return
            if prior[1]!=args.window_end or prior[2]!=args.dag_id or tuple(prior[3:9])!=config:
                raise ValueError('existing cycle has different bounds/context/configuration')
            args.window_start=prior[0]
            return
        checkpoint=conn.execute('''SELECT completed_window_end FROM ops.extraction_checkpoints
            WHERE source_system=%s AND source_account_id=%s AND stream_name=%s ''',(args.source,account,args.checkpoint_stream)).fetchone()
        if drain:
            args.window_start=args.window_end=None
        elif args.window_end is None:
            raise ValueError('recovery/polling requires a fixed upper bound')
        elif checkpoint:
            args.window_start=checkpoint[0]-timedelta(seconds=args.overlap_seconds)
        elif args.initial_start is not None:
            args.window_start=args.initial_start
        else:
            raise ValueError('first polling cycle requires explicit initial start')
        if not drain and (args.window_end>args.observed_at or args.window_start>args.window_end):
            raise ValueError('require initial/checkpoint start <= fixed upper bound <= current time')
        # ensure_run commits; keep creation and config in one transaction here instead.
        conn.execute('''INSERT INTO ops.pipeline_runs
            (run_id,stage,source_system,source_account_id,stream_name,requested_window_start,
             requested_window_end,airflow_dag_id,airflow_run_id,started_at,status,log_reference)
            VALUES (%s,'RECOVER',%s,%s,%s,%s,%s,%s,%s,%s,'RUNNING',%s)''',
            (args.workflow_id,args.source,account,SOURCES[args.source][3],
             args.window_start,args.window_end,args.dag_id,args.airflow_run_id if args.dag_id else None,
             args.observed_at,f'm04:{args.execution_id}'))
        conn.execute('''INSERT INTO ops.polling_cycles
            (run_id,validation_mode,clock_mode,mapping_version,transformation_version,overlap_seconds,settings)
            VALUES (%s,%s,%s,%s,%s,%s,%s)''',(args.workflow_id,*config[:-1],Jsonb(settings)))


def coordinate(args):
    deadline=time.monotonic()+args.wait_seconds
    with release_connection() as lock:
        if args.abort:
            own = lock.execute("SELECT status FROM ops.transform_batches WHERE batch_id=%s", (args.batch_id,)).fetchone()
            lock.commit()
            if not own or own[0] not in ('FROZEN','BUILDING','TESTED'):
                # Closing a windowless/contended parent cannot touch another source's batch.
                workflow.run_stage(args,'abort')
                return
        while True:
            got_lock=lock.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0]
            lock.commit()
            if got_lock:
                active=lock.execute("SELECT batch_id FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchall()
                lock.commit()
                if not active or active==[(args.batch_id,)]:
                    break
                lock.execute("SELECT pg_advisory_unlock(hashtext('platform-release'))")
                lock.commit()
            if time.monotonic()>=deadline:
                # Contention has not allocated a stage attempt; retry is safe.
                raise TimeoutError('release coordinator busy; no business attempt consumed')
            time.sleep(2)
        args.freeze_connection=lock
        if args.abort:
            workflow.run_stage(args,'abort')
            return
        for stage in workflow.STAGES:
            args.observed_at=datetime.now(timezone.utc)
            workflow.run_stage(args,stage)
        print(f'POLL PASS source={args.source} cycle={args.workflow_id} batch={args.batch_id}')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',choices=tuple(SOURCES),required=True)
    p.add_argument('--collection-mode',choices=('drain','recovery'),default='recovery')
    p.add_argument('--checkpoint-stream')
    p.add_argument('--reuse-cycle-config',action='store_true')
    p.add_argument('--execution-id',required=True)
    p.add_argument('--dag-id')
    p.add_argument('--airflow-run-id')
    p.add_argument('--window-end',type=parse_time)
    p.add_argument('--initial-start',type=parse_time)
    p.add_argument('--overlap-seconds',type=int,default=120)
    p.add_argument('--wait-seconds',type=int,default=600)
    p.add_argument('--mapping-version',default='s01-v1')
    p.add_argument('--transformation-version')
    p.add_argument('--abort',action='store_true')
    for flag in ('fault-after-raw-once','fault-after-freeze-once','inject-test-failure'):
        p.add_argument('--'+flag,action='store_true')
    args=p.parse_args()
    if args.transformation_version is None:
        args.transformation_version='m06-v1' if args.source=='etsy_sim' else 'm05b-v1'
    if args.source=='etsy_sim' and args.checkpoint_stream is not None and not re.fullmatch(r'receipts(?:_polling|_test_[0-9a-f]{32})?',args.checkpoint_stream):
        p.error('invalid Etsy checkpoint scope')
    if args.overlap_seconds<0 or args.wait_seconds<0:
        p.error('overlap/wait must be nonnegative')
    prepare(args)
    coordinate(args)


if __name__=='__main__':
    try:
        main()
    except workflow.AttemptBudgetExhausted as error:
        print(str(error),file=sys.stderr)
        sys.exit(42)
