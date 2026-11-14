"""Durable source ordering and bounded, worker-free live coordinator waits."""
import uuid

from orchestration import website_workflow as workflow
from transformation.source_config import SOURCES


class CoordinatorBusy(RuntimeError):
    """Exit75 asks the Airflow sensor to reschedule, not consume a retry."""


def source_available(conn,args):
    """Legacy/manual callers must not overtake a rescheduled live owner."""
    relation=conn.execute("SELECT to_regclass('ops.source_cycle_owners')").fetchone()[0]
    if relation is None:
        return True
    active=conn.execute('''SELECT 1 FROM ops.transform_batches b JOIN ops.pipeline_runs p ON p.run_id=b.run_id
        WHERE p.source_system=%s AND p.source_account_id=%s AND b.batch_id<>%s
        AND b.status IN ('FROZEN','BUILDING','TESTED') LIMIT 1''',
                        (args.source,SOURCES[args.source][0],args.batch_id)).fetchone()
    if active:
        return False
    row=conn.execute('''SELECT o.run_id,p.status FROM ops.source_cycle_owners o
        JOIN ops.pipeline_runs p USING(run_id)
        WHERE o.source_system=%s AND o.source_account_id=%s''',
                     (args.source,SOURCES[args.source][0])).fetchone()
    return row is None or row[0]==args.workflow_id or row[1] in ('SUCCEEDED','FAILED')


def source_owner(args):
    """Caller holds the source session lock; pointer survives process exit."""
    with workflow.connect() as conn:
        from transformation.admission import registration_lock
        registration_lock(conn,args.source)
        if not source_available(conn,args):
            return False
        conn.execute('''INSERT INTO ops.source_cycle_owners(source_system,source_account_id,run_id)
            VALUES(%s,%s,%s) ON CONFLICT DO NOTHING''',
                     (args.source,SOURCES[args.source][0],args.workflow_id))
        owner,status=conn.execute('''SELECT o.run_id,p.status FROM ops.source_cycle_owners o
            JOIN ops.pipeline_runs p USING(run_id)
            WHERE o.source_system=%s AND o.source_account_id=%s FOR UPDATE OF o''',
                                  (args.source,SOURCES[args.source][0])).fetchone()
        if owner==args.workflow_id:
            return True
        if status not in ('SUCCEEDED','FAILED'):
            return False
        conn.execute('''UPDATE ops.source_cycle_owners SET run_id=%s,acquired_at=clock_timestamp()
            WHERE source_system=%s AND source_account_id=%s''',
                     (args.workflow_id,args.source,SOURCES[args.source][0]))
        return True


def wait(args,kind,ready):
    """Use one durable infrastructure clock per phase and actual task attempt."""
    attempt=args.coordinator_attempt
    with workflow.connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     (f'coordinator-wait:{args.workflow_id}:{kind}:{attempt}',))
        row=conn.execute('''SELECT m.measurement_id,m.outcome,
            extract(epoch FROM clock_timestamp()-m.started_at)
            FROM ops.coordinator_waits w JOIN ops.execution_measurements m USING(measurement_id)
            WHERE w.run_id=%s AND w.wait_kind=%s AND w.task_try_number=%s''',
                         (args.workflow_id,kind,attempt)).fetchone()
        if row is None and ready:
            return
        if row is None:
            measurement=uuid.uuid4()
            conn.execute('''INSERT INTO ops.execution_measurements
                (measurement_id,run_id,source_system,source_account_id,validation_mode,stage,started_at,outcome)
                VALUES(%s,%s,%s,%s,'runtime',%s,clock_timestamp(),'RUNNING')''',
                         (measurement,args.workflow_id,args.source,SOURCES[args.source][0],kind))
            conn.execute('''INSERT INTO ops.coordinator_waits
                (run_id,wait_kind,task_try_number,measurement_id) VALUES(%s,%s,%s,%s)''',
                         (args.workflow_id,kind,attempt,measurement))
            elapsed,outcome=0,'RUNNING'
        else:
            measurement,outcome,elapsed=row
        expired=outcome=='TIMED_OUT' or (outcome=='RUNNING' and elapsed>=args.wait_seconds)
        if expired or ready:
            conn.execute('''UPDATE ops.execution_measurements SET outcome=%s,
                finished_at=GREATEST(clock_timestamp(),started_at),
                duration_ms=GREATEST(0,extract(epoch FROM clock_timestamp()-started_at)*1000)
                WHERE measurement_id=%s AND outcome='RUNNING' ''',
                         ('TIMED_OUT' if expired else 'SUCCEEDED',measurement))
        conn.commit()
    if expired:
        raise TimeoutError(kind+': durable infrastructure wait exceeded; no business attempt consumed')
    if not ready:
        raise CoordinatorBusy(kind+': reschedule; no business attempt consumed')


def coordinate(args):
    # The terminal workflow and pointer remain as evidence. A successor may take
    # ownership only after the predecessor succeeded or was explicitly aborted.
    from transformation.batch import connect
    with workflow.connect() as state:
        status=state.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s',
                             (args.workflow_id,)).fetchone()
        if not args.abort and status and status[0]=='SUCCEEDED':
            return
        if args.abort:
            own=state.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',
                              (args.batch_id,)).fetchone()
            if not own or own[0] not in ('FROZEN','BUILDING','TESTED'):
                workflow.run_stage(args,'abort')
                return
    with connect() as source_lock:
        acquired=source_lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))',
            (f'source-cycle:{args.source}:{SOURCES[args.source][0]}',)).fetchone()[0]
        source_lock.commit()
        wait(args,'source_slot',acquired and source_owner(args))
        if getattr(args,'delta_plan_sha256',None):
            # The existing source lock/pointer span every stage. Source-private
            # candidates do not require the global legacy build/FIFO barrier.
            args.delta_connection=source_lock
            if args.abort:
                workflow.run_stage(args,'abort')
            else:
                for stage in workflow.STAGES:
                    workflow.run_stage(args,stage)
            return
        if not args.abort:
            workflow.run_stage(args,'collect')
        with connect() as lock:
            acquired=lock.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0]
            lock.commit()
            if acquired:
                active=lock.execute("SELECT batch_id FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchall()
                lock.commit()
                from orchestration.release_queue import is_turn
                acquired=active==[(args.batch_id,)] or (not active and is_turn(args))
            wait(args,'release_slot',acquired)
            args.freeze_connection=lock
            if args.abort:
                workflow.run_stage(args,'abort')
            else:
                for stage in workflow.STAGES[1:]:
                    workflow.run_stage(args,stage)
