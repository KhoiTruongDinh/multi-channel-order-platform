"""Opt-in deployment plan selection and durable-workflow delta stage dispatch."""
import os
from pathlib import Path
import re

from transformation.batch import connect
from transformation.delta_plan import load
from transformation.delta_runtime import _assert_config


def configure(args, persisted=None, *, published=False):
    """Resolve before collection; persisted cycles never silently switch modes."""
    args.delta_plan=None
    identity=persisted.get('delta_plan_sha256') if persisted is not None else None
    directory=os.environ.get('POLLING_DELTA_PLAN_DIR','')
    if persisted is not None and 'delta_plan_sha256' not in persisted:
        args.delta_plan_sha256=None
        return
    if persisted is not None and (not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity)):
        raise ValueError('invalid persisted delta plan identity')
    if persisted is None and not directory:
        args.delta_plan_sha256=None
        return
    if not getattr(args,'nonblocking',False) or args.validation_mode!='runtime':
        raise ValueError('delta requires the nonblocking runtime coordinator')
    if getattr(args,'logical_clock',None):
        raise ValueError('delta deployment option is not a replay clock selector')
    args.delta_plan_sha256=identity
    # Operator abort must remain available after a lost/changed deployment file.
    if identity and (args.abort or published):
        return
    if not directory:
        raise ValueError('pinned delta plan directory is unavailable; no legacy fallback')
    plan=load(Path(directory)/(args.source+'.json'))
    if plan['source']!=args.source or (identity and plan['plan_sha256']!=identity):
        raise ValueError('deployment plan differs from persisted cycle')
    if args.mapping_version!=plan['mapping_version']:
        raise ValueError('mapping release differs from deployment plan')
    if persisted is not None and args.transformation_version!=plan['transformation_version']:
        raise ValueError('transformation version differs from persisted cycle')
    with connect() as conn:
        _assert_config(conn,plan)
        ready=conn.execute('''SELECT 1 FROM ops.delta_batches d JOIN ops.transform_batches b USING(batch_id)
            WHERE d.plan_sha256=%s AND d.bootstrap AND b.status='PUBLISHED' LIMIT 1''',
                           (plan['plan_sha256'],)).fetchone()
        if not ready:
            raise ValueError('deployment plan needs explicit successful bootstrap before polling')
        from transformation.source_config import SOURCES
        active=conn.execute('''SELECT d.plan_sha256 FROM ops.publication_state p
            LEFT JOIN ops.delta_batches d USING(batch_id) WHERE p.publication_name=%s''',
                            (SOURCES[args.source][2],)).fetchone()
        if not active or active[0]!=plan['plan_sha256']:
            raise ValueError('active publication uses another plan; compile/bootstrap a new release')
    args.transformation_version=plan['transformation_version']
    args.delta_plan_sha256=plan['plan_sha256']
    args.delta_plan=plan


def perform(conn,args,stage,number,state):
    from orchestration.website_workflow import identity
    from transformation import delta_runtime,delta_publish
    plan=args.delta_plan
    worker=args.delta_connection
    if stage=='freeze':
        if state is None:
            delta_runtime.freeze(worker,plan,args.batch_id,identity(args.execution_id,'transform'),
                owner_workflow_id=args.workflow_id,airflow_dag_id=args.dag_id,
                airflow_run_id=args.airflow_run_id if args.dag_id else None)
        elif state=='FAILED':
            raise RuntimeError('failed batch requires an explicit new execution')
        conn.execute('UPDATE ops.pipeline_runs SET batch_id=%s WHERE run_id=%s',
                     (args.batch_id,args.workflow_id))
        conn.commit()
        if args.fault_after_freeze_once and number==1:
            raise RuntimeError('intentional interruption after durable delta freeze')
    elif stage=='build_and_test':
        delta_runtime.build(worker,plan,args.batch_id,attempt=number,inject_failure=args.inject_test_failure)
    elif stage=='publish':
        if state!='PUBLISHED':
            delta_publish.audited_publish(plan,args.batch_id,identity(args.execution_id,f'publish:{number}'),
                airflow_dag_id=args.dag_id,airflow_run_id=args.airflow_run_id if args.dag_id else None)
    else:
        raise ValueError('unknown delta stage')
