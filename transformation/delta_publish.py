"""Experimental atomic delta promotion; only copy/merge, never business SQL."""
import time

from psycopg import sql

from transformation.delta_plan import validate
from transformation.delta_runtime import expected_nodes
from transformation.publish import COPIES, connect
from transformation.source_config import SOURCES


MART_KEYS = {
    'order_activity_daily': ('activity_date','source_system','source_account_id','currency'),
    'product_activity_daily': ('activity_date','source_system','source_account_id',
                             'product_bucket_key','mapping_status','currency'),
    'order_status_current': ('source_system','source_account_id','payment_state',
                            'fulfillment_state','cancellation_state'),
}


def _columns(conn, schema, table):
    return tuple(row[0] for row in conn.execute('''SELECT column_name FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position''', (schema,table)))


def _merge_mart(conn, table, candidate, source, account, *, batch_id=None, scope=None):
    """Source-local effective aggregates were computed by dbt, not Python."""
    keys = MART_KEYS[table]
    columns = _columns(conn, 'mart', table)
    measures = tuple(c for c in columns if c not in keys and c != 'published_batch_id')
    target = sql.Identifier('mart', table)
    equal = sql.SQL(' AND ').join(sql.SQL('t.{}=c.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in keys)
    params = [source,account]
    scoped = sql.SQL('')
    if 'activity_date' in keys:
        if scope is None or batch_id is None:
            raise RuntimeError('daily publication requires explicit batch/date scope')
        invalid = conn.execute(sql.SQL('SELECT 1 FROM {} c WHERE NOT EXISTS('
            'SELECT 1 FROM {} s WHERE s.batch_id=%s AND s.source_system=c.source_system '
            'AND s.source_account_id=c.source_account_id AND s.activity_date=c.activity_date) LIMIT 1'
            ).format(candidate,scope),(batch_id,)).fetchone()
        if invalid:
            raise RuntimeError('daily candidate outside tested activity scope')
        scoped = sql.SQL('AND EXISTS(SELECT 1 FROM {} s WHERE s.batch_id=%s '
            'AND s.source_system=t.source_system AND s.source_account_id=t.source_account_id '
            'AND s.activity_date=t.activity_date) ').format(scope)
        params.append(batch_id)
    conn.execute(sql.SQL('DELETE FROM {} t WHERE t.source_system=%s AND t.source_account_id=%s '
                         '{}AND NOT EXISTS(SELECT 1 FROM {} c WHERE {})').format(target,scoped,candidate,equal),
                 params)
    updates = tuple(c for c in columns if c not in keys)
    conn.execute(sql.SQL('INSERT INTO {} AS t ({}) SELECT {} FROM {} ON CONFLICT ({}) DO UPDATE SET {} '
                         'WHERE ({}) IS DISTINCT FROM ({})').format(
        target,sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(map(sql.Identifier,columns)),
        candidate,sql.SQL(',').join(map(sql.Identifier,keys)),
        sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in updates),
        sql.SQL(',').join(sql.SQL('t.{}').format(sql.Identifier(c)) for c in measures),
        sql.SQL(',').join(sql.SQL('EXCLUDED.{}').format(sql.Identifier(c)) for c in measures)))


def publish(plan, batch_id, *, inject_failure=False, run_id=None):
    """Commit affected business rows, source pointer and exact raw consumption.

    Caller retains source_lock across the entire freeze/build/publish sequence.
    Commit return is measured, not a publisher-supplied timestamp masquerading as
    commit visibility. Production workflow integration is deliberately absent.
    """
    validate(plan)
    source = plan['source']
    account,prefix,publication,_ = SOURCES[source]
    schema = plan['schema']
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('website-publication'))")
        # Prevent concurrent DDL. ACCESS SHARE does not block mapping DML:
        # the hash verifies the mapping visible at this publication check.
        conn.execute('LOCK TABLE config.product_mapping IN ACCESS SHARE MODE')
        from transformation.delta_runtime import _assert_config
        _assert_config(conn, plan)
        batch = conn.execute('''SELECT b.status,d.plan_sha256,d.base_batch_id,d.expected_nodes
            FROM ops.transform_batches b JOIN ops.delta_batches d USING(batch_id)
            WHERE b.batch_id=%s FOR UPDATE OF b''', (batch_id,)).fetchone()
        if not batch or batch[1] != plan['plan_sha256']:
            raise RuntimeError('batch/plan mismatch')
        if batch[0] == 'PUBLISHED':
            if run_id:
                conn.execute("UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=clock_timestamp() WHERE run_id=%s",(run_id,))
            return
        if batch[0] != 'TESTED' or batch[3] != expected_nodes(plan):
            raise RuntimeError('only the exact tested source graph can publish')
        report = conn.execute('''SELECT results FROM ops.delta_results
            WHERE batch_id=%s AND plan_sha256=%s AND passed ORDER BY attempt_number DESC LIMIT 1''',
                              (batch_id,plan['plan_sha256'])).fetchone()
        if not report or any(sorted(n['id'] for n in report[0][kind] if n['status']=='pass') !=
                             sorted(expected_nodes(plan)[kind]) for kind in ('models','tests')):
            raise RuntimeError('missing or incomplete passing node evidence')
        pointer = conn.execute('SELECT batch_id FROM ops.publication_state WHERE publication_name=%s',
                               (publication,)).fetchone()
        if (pointer[0] if pointer else None) != batch[2]:
            raise RuntimeError('source publication changed since freeze; refusing stale promotion')
        candidates = [(target, sql.Identifier(schema,candidate.split('.')[1].replace('candidate_',prefix+'candidate_',1)))
                      for target,candidate in COPIES]
        activity_scope = sql.Identifier(schema,prefix+'candidate_activity_scope')
        conn.execute(sql.SQL('LOCK TABLE {} IN ACCESS SHARE MODE').format(activity_scope))
        if conn.execute(sql.SQL('SELECT 1 FROM {} WHERE batch_id<>%s OR source_system<>%s '
            'OR source_account_id<>%s LIMIT 1').format(activity_scope),
                        (batch_id,source,account)).fetchone():
            raise RuntimeError('stale or cross-source daily activity scope')
        health = sql.Identifier(schema,prefix+'candidate_source_health')
        for _,candidate in candidates:
            conn.execute(sql.SQL('LOCK TABLE {} IN ACCESS SHARE MODE').format(candidate))
        conn.execute(sql.SQL('LOCK TABLE {} IN ACCESS SHARE MODE').format(health))
        history = candidates[0][1]
        invalid = conn.execute(sql.SQL('SELECT 1 FROM {} WHERE batch_id<>%s LIMIT 1').format(history),
                               (batch_id,)).fetchone()
        if invalid:
            raise RuntimeError('candidate history has stale batch lineage')
        # Children precede parents; untouched orders and their lineage are retained.
        for table in ('order_lines_current','orders_current'):
            conn.execute(sql.SQL('DELETE FROM {} t USING ops.delta_batch_keys k '
                'WHERE k.batch_id=%s AND t.source_system=%s AND t.source_account_id=%s '
                'AND t.source_order_id=k.source_order_id').format(sql.Identifier('core',table)),
                         (batch_id,source,account))
        for table in ('snapshot_evidence','order_line_snapshot_history'):
            conn.execute(sql.SQL('DELETE FROM {} t USING core.order_snapshot_history h,ops.delta_batch_keys k '
                'WHERE t.snapshot_id=h.snapshot_id AND k.batch_id=%s AND h.source_system=%s '
                'AND h.source_account_id=%s AND k.source_order_id=h.source_order_id').format(sql.Identifier('core',table)),
                         (batch_id,source,account))
        conn.execute('''DELETE FROM core.order_snapshot_history h USING ops.delta_batch_keys k
            WHERE k.batch_id=%s AND h.source_system=%s AND h.source_account_id=%s
              AND h.source_order_id=k.source_order_id''', (batch_id,source,account))
        for target,candidate in candidates:
            target_schema,table = target.split('.')
            if target_schema == 'mart':
                _merge_mart(conn,table,candidate,source,account,
                            batch_id=batch_id,scope=activity_scope)
            else:
                columns = _columns(conn,target_schema,table)
                names = sql.SQL(',').join(map(sql.Identifier,columns))
                conn.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {}').format(
                    sql.Identifier(target_schema,table),names,names,candidate))
        conn.execute('DELETE FROM mart.source_health WHERE source_system=%s AND source_account_id=%s',
                     (source,account))
        conn.execute(sql.SQL('''INSERT INTO mart.source_health
            SELECT source_system,source_account_id,stream_name,completed_window_end,
                last_successful_acquisition_at,clock_timestamp(),pending_work_count,failed_work_count,
                open_blocking_exception_count,coverage_state,published_batch_id FROM {}''').format(health))
        if inject_failure:
            raise RuntimeError('injected delta publication rollback')
        conn.execute('''INSERT INTO ops.publication_state
            (publication_name,batch_id,published_at,transformation_version,mapping_version)
            VALUES(%s,%s,clock_timestamp(),%s,%s) ON CONFLICT(publication_name) DO UPDATE
            SET batch_id=EXCLUDED.batch_id,published_at=EXCLUDED.published_at,
                transformation_version=EXCLUDED.transformation_version,mapping_version=EXCLUDED.mapping_version''',
                     (publication,batch_id,plan['transformation_version'],plan['mapping_version']))
        conn.execute('''UPDATE ops.transform_batches SET status='PUBLISHED',published_at=clock_timestamp()
            WHERE batch_id=%s''', (batch_id,))
        conn.execute('''INSERT INTO ops.delta_seen_raw(plan_sha256,raw_record_id,processed_batch_id)
            SELECT %s,raw_record_id,%s FROM ops.delta_new_inputs WHERE batch_id=%s''',
                     (plan['plan_sha256'],batch_id,batch_id))
        if run_id:
            conn.execute("UPDATE ops.pipeline_runs SET status='SUCCEEDED',finished_at=clock_timestamp() WHERE run_id=%s",(run_id,))
    return time.monotonic()


def audited_publish(plan,batch_id,run_id,*,airflow_dag_id=None,airflow_run_id=None,inject_failure=False):
    """One workflow-budgeted attempt; success is atomic with publication."""
    if bool(airflow_dag_id)!=bool(airflow_run_id):
        raise ValueError('Airflow owner requires both DAG and run IDs')
    with connect() as conn:
        conn.execute('''UPDATE ops.pipeline_runs SET status='FAILED',finished_at=clock_timestamp(),
            error_code='INTERRUPTED',error_message='Prior publisher ended before completion'
            WHERE batch_id=%s AND stage='PUBLISH' AND status='RUNNING' AND run_id<>%s''',
                     (batch_id,run_id))
        conn.execute('''INSERT INTO ops.pipeline_runs
            (run_id,stage,source_system,source_account_id,stream_name,batch_id,started_at,status,
             log_reference,airflow_dag_id,airflow_run_id)
            VALUES(%s,'PUBLISH',%s,%s,'orders',%s,clock_timestamp(),'RUNNING','m08d:delta:publish',%s,%s)''',
                     (run_id,plan['source'],SOURCES[plan['source']][0],batch_id,airflow_dag_id,airflow_run_id))
    try:
        return publish(plan,batch_id,run_id=run_id,inject_failure=inject_failure)
    except Exception as error:
        with connect() as conn:
            conn.execute('''UPDATE ops.pipeline_runs SET status='FAILED',finished_at=clock_timestamp(),
                error_code=%s,error_message='Delta publication rolled back; last-good retained'
                WHERE run_id=%s''',(type(error).__name__,run_id))
        raise
