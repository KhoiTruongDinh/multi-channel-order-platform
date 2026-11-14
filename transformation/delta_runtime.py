"""Experimental affected-order dbt execution; not enabled in live orchestration.

The caller must retain the source advisory lock across freeze/build/publication.
All business queries and quality assertions come from the validated dbt plan.
"""
from contextlib import contextmanager
import time

from psycopg.types.json import Jsonb

from transformation.batch import connect
from transformation.delta_plan import mapping_hash, validate
from transformation.source_config import SOURCES


@contextmanager
def source_lock(plan):
    """Non-waiting experimental fence; callers may not bypass the live owner fence.

    Deliberately refuses a live source owner: this path is for disposable probes
    until the existing durable Airflow coordinator is integrated.
    """
    validate(plan)
    source = plan['source']
    account = SOURCES[source][0]
    key = f'source-cycle:{source}:{account}'
    with connect() as conn:
        # Share the actual fence with existing live/manual acquisition, not a
        # separate delta-only lock that could race the legacy workflow.
        if not conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (key,)).fetchone()[0]:
            raise RuntimeError('delta source is busy')
        conn.commit()
        try:
            if conn.execute('''SELECT 1 FROM ops.source_cycle_owners o
                JOIN ops.pipeline_runs p USING(run_id) WHERE o.source_system=%s
                AND o.source_account_id=%s AND p.status NOT IN ('SUCCEEDED','FAILED')''',
                            (source,account)).fetchone():
                raise RuntimeError('live source ownership exists; delta probe refused')
            conn.commit()
            yield conn
        finally:
            # An SQL exception may leave the transaction aborted. Preserve the
            # original error and never commit an unfinished stage during cleanup.
            conn.rollback()
            conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (key,))
            conn.commit()


def _assert_config(conn, plan):
    validate(plan)
    if mapping_hash(conn, plan['source'], plan['mapping_version']) != plan['mapping_hash']:
        raise RuntimeError('mapping changed; compile and bootstrap a new plan')


def expected_nodes(plan):
    return {kind: [node['id'] for node in plan[kind]] for kind in ('models', 'tests')}


def freeze(conn, plan, batch_id, run_id, *, bootstrap=False,
           owner_workflow_id=None, airflow_dag_id=None, airflow_run_id=None):
    """Freeze unseen raw IDs, dirty keys and their complete acquired evidence."""
    _assert_config(conn, plan)
    if bool(airflow_dag_id)!=bool(airflow_run_id):
        raise ValueError('Airflow owner requires both DAG and run IDs')
    source = plan['source']
    from transformation.admission import admit
    admit(conn,source,owner_workflow_id)
    account, _, publication, _ = SOURCES[source]
    existing = conn.execute('''SELECT d.plan_sha256,b.run_id FROM ops.delta_batches d
        JOIN ops.transform_batches b USING(batch_id) WHERE d.batch_id=%s''', (batch_id,)).fetchone()
    if existing:
        if existing != (plan['plan_sha256'], run_id):
            raise RuntimeError('batch identity/configuration mismatch')
        return
    if conn.execute('''SELECT 1 FROM ops.transform_batches b JOIN ops.pipeline_runs p ON p.run_id=b.run_id
        WHERE p.source_system=%s AND p.source_account_id=%s
        AND b.status IN ('FROZEN','BUILDING','TESTED')''', (source,account)).fetchone():
        raise RuntimeError('finish or explicitly abort the existing source delta batch')
    ready = conn.execute('''SELECT 1 FROM ops.delta_batches d JOIN ops.transform_batches b USING(batch_id)
        WHERE d.plan_sha256=%s AND d.bootstrap AND b.status='PUBLISHED' LIMIT 1''',
                         (plan['plan_sha256'],)).fetchone()
    if not ready and not bootstrap:
        raise RuntimeError('explicit bootstrap is required for this compiled plan')
    if ready and bootstrap:
        raise RuntimeError('plan already bootstrapped; use an ordinary delta cycle')
    if ready and not bootstrap:
        active=conn.execute('''SELECT d.plan_sha256 FROM ops.publication_state p
            LEFT JOIN ops.delta_batches d USING(batch_id) WHERE p.publication_name=%s''',
                            (publication,)).fetchone()
        if not active or active[0]!=plan['plan_sha256']:
            raise RuntimeError('active publication uses another plan; compile/bootstrap a new release')
    base = conn.execute('SELECT batch_id FROM ops.publication_state WHERE publication_name=%s',
                        (publication,)).fetchone()
    conn.execute('''INSERT INTO ops.pipeline_runs
        (run_id,stage,source_system,source_account_id,stream_name,batch_id,started_at,status,log_reference,
         airflow_dag_id,airflow_run_id)
        VALUES(%s,'TRANSFORM',%s,%s,'orders',%s,clock_timestamp(),'RUNNING','m08d:delta',%s,%s)''',
                 (run_id, source, account, batch_id,airflow_dag_id,airflow_run_id))
    conn.execute('''INSERT INTO ops.transform_batches
        (batch_id,run_id,mapping_version,transformation_version,manifest_frozen_at,status,validation_mode)
        VALUES(%s,%s,%s,%s,clock_timestamp(),'FROZEN','runtime')''',
                 (batch_id, run_id, plan['mapping_version'], plan['transformation_version']))
    conn.execute('''INSERT INTO ops.delta_batches
        (batch_id,source_system,source_account_id,plan_sha256,build_schema,base_batch_id,bootstrap,expected_nodes)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',
                 (batch_id, source, account, plan['plan_sha256'], plan['schema'],
                  base[0] if base else None, bootstrap, Jsonb(expected_nodes(plan))))
    conn.execute(plan['hooks']['route'])
    conn.execute('''INSERT INTO ops.batch_inputs(batch_id,raw_record_id)
        SELECT DISTINCT %s,k.raw_record_id FROM ops.delta_raw_keys k
        WHERE k.source_system=%s AND k.source_account_id=%s AND NOT EXISTS
          (SELECT 1 FROM ops.delta_seen_raw s WHERE s.plan_sha256=%s AND s.raw_record_id=k.raw_record_id)''',
                 (batch_id, source, account, plan['plan_sha256']))
    conn.execute('''INSERT INTO ops.delta_new_inputs SELECT batch_id,raw_record_id
        FROM ops.batch_inputs WHERE batch_id=%s''', (batch_id,))
    conn.execute('''INSERT INTO ops.delta_batch_keys
        SELECT DISTINCT %s,k.source_order_id FROM ops.delta_raw_keys k
        JOIN ops.delta_new_inputs i USING(raw_record_id)
        WHERE i.batch_id=%s AND k.source_order_id IS NOT NULL''', (batch_id, batch_id))
    conn.execute('''INSERT INTO ops.batch_inputs(batch_id,raw_record_id)
        SELECT DISTINCT %s,r.raw_record_id FROM ops.delta_raw_keys r
        JOIN ops.delta_batch_keys k ON k.source_order_id=r.source_order_id
        WHERE k.batch_id=%s AND r.source_system=%s AND r.source_account_id=%s
        ON CONFLICT DO NOTHING''', (batch_id, batch_id, source, account))
    conn.commit()


def build(conn, plan, batch_id, *, attempt=1, inject_failure=False):
    """Execute the complete source-local compiled graph and its required tests.

    DDL, tests, cache/exception hooks, successful result and TESTED state commit
    together. Failure rolls these back, then records one immutable failed attempt.
    """
    if not 1 <= attempt <= 5:
        raise ValueError('attempt must be between 1 and 5')
    validation_start = time.perf_counter()
    _assert_config(conn, plan)
    validation_seconds = time.perf_counter()-validation_start
    state = conn.execute('''SELECT b.status,d.plan_sha256,d.bootstrap FROM ops.transform_batches b
        JOIN ops.delta_batches d USING(batch_id) WHERE b.batch_id=%s''', (batch_id,)).fetchone()
    if not state or state[1] != plan['plan_sha256']:
        raise RuntimeError('unknown batch or plan mismatch')
    if state[0] in ('TESTED', 'PUBLISHED'):
        return
    if state[0] not in ('FROZEN', 'BUILDING'):
        raise RuntimeError('batch is not buildable')
    used = conn.execute('''SELECT coalesce(max(attempt_number),0) FROM ops.delta_results
        WHERE batch_id=%s''', (batch_id,)).fetchone()[0]
    # Process death can leave no result row. The workflow's durable task ledger
    # owns the attempt budget; never require it to reuse an interrupted number.
    if attempt <= used:
        raise RuntimeError('attempt must advance the retained attempt ledger')
    conn.execute("UPDATE ops.transform_batches SET status='BUILDING' WHERE batch_id=%s", (batch_id,))
    conn.commit()
    results = {'models': [], 'tests': [], 'phases': {'config_validation': validation_seconds}}
    try:
        # Short affected-order queries can have inflated JSON cardinality costs.
        # Real EXPLAIN evidence showed seconds of LLVM compilation for sub-ms SQL.
        # Scope this policy to this transaction; full dbt/server settings stay intact.
        conn.execute('SET LOCAL jit=off')
        conn.execute("SELECT set_config('platform.batch_id',%s,true)", (str(batch_id),))
        conn.execute("SELECT set_config('platform.delta_bootstrap',%s,true)",
                     ('true' if state[2] else 'false',))
        conn.execute("SELECT set_config('platform.inject_test_failure',%s,true)",
                     ('true' if inject_failure else 'false',))
        if state[2]:
            conn.execute(plan['hooks']['functions'])
        phase_start = time.perf_counter()
        conn.execute(plan['hooks']['prepare'])
        results['phases']['prepare_hook'] = time.perf_counter()-phase_start
        # Private schemas contain tables only: reverse-order drops need no CASCADE.
        phase_start = time.perf_counter()
        for node in reversed(plan['models']):
            conn.execute('DROP TABLE IF EXISTS ' + node['relation'])
        results['phases']['drop_candidates'] = time.perf_counter()-phase_start
        for node in plan['models']:
            start = time.perf_counter()
            cursor = conn.execute('CREATE TABLE ' + node['relation'] + ' AS ' + node['sql'].rstrip(';'))
            ctas_seconds = time.perf_counter()-start
            analyze_start = time.perf_counter()
            conn.execute('ANALYZE ' + node['relation'])
            results['models'].append(dict(id=node['id'],status='pass',rows=cursor.rowcount,
                                          seconds=time.perf_counter()-start,
                                          ctas_seconds=ctas_seconds,
                                          analyze_seconds=time.perf_counter()-analyze_start))
        for node in plan['tests']:
            start = time.perf_counter()
            count = conn.execute('SELECT count(*) FROM (' + node['sql'].rstrip(';') + ') failures').fetchone()[0]
            results['tests'].append(dict(id=node['id'],status='fail' if count else 'pass',
                                         failures=count,seconds=time.perf_counter()-start))
        if any(node['status'] != 'pass' for node in results['tests']):
            raise RuntimeError('compiled dbt quality gate failed')
        phase_start = time.perf_counter()
        conn.execute(plan['hooks']['finish'])
        results['phases']['finish_hook'] = time.perf_counter()-phase_start
        conn.execute('''INSERT INTO ops.delta_results VALUES(%s,%s,%s,true,%s,DEFAULT)''',
                     (batch_id, attempt, plan['plan_sha256'], Jsonb(results)))
        conn.execute('''UPDATE ops.transform_batches SET status='TESTED',test_artifact_reference=%s
            WHERE batch_id=%s''', ('ops.delta_results:' + str(batch_id) + ':' + str(attempt), batch_id))
        conn.execute('''UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=clock_timestamp()
            WHERE batch_id=%s AND stage='TRANSFORM' ''', (batch_id,))
        conn.commit()
    except Exception as error:
        conn.rollback()
        results['error_code'] = type(error).__name__
        conn.execute('''INSERT INTO ops.delta_results VALUES(%s,%s,%s,false,%s,DEFAULT)''',
                     (batch_id, attempt, plan['plan_sha256'], Jsonb(results)))
        conn.commit()
        raise


if __name__=='__main__':
    import argparse
    import uuid
    from transformation.delta_plan import load
    from transformation.delta_publish import audited_publish
    parser=argparse.ArgumentParser(description='Explicit cold bootstrap; never an automatic polling fallback')
    parser.add_argument('--plan',required=True)
    parser.add_argument('--bootstrap',action='store_true',required=True)
    parser.add_argument('--batch-id',type=uuid.UUID,required=True)
    parser.add_argument('--run-id',type=uuid.UUID,required=True)
    parser.add_argument('--publish-run-id',type=uuid.UUID,required=True)
    parser.add_argument('--attempt',type=int,choices=range(1,6),default=1,
                        help='Advance after a failed/interrupted build; never reset the retained ledger')
    args=parser.parse_args()
    plan=load(args.plan)
    with source_lock(plan) as connection:
        freeze(connection,plan,args.batch_id,args.run_id,bootstrap=True)
        build(connection,plan,args.batch_id,attempt=args.attempt)
        state=connection.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',
                                 (args.batch_id,)).fetchone()[0]
        connection.commit()
        if state!='PUBLISHED':
            audited_publish(plan,args.batch_id,args.publish_run_id)
    print('DELTA_BOOTSTRAP_PUBLISHED batch='+str(args.batch_id))
