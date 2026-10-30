"""Actual processing clocks only; never reinterpret simulated observation times."""
from datetime import datetime,timezone
import time
import uuid
from transformation.source_config import SOURCES


def begin(conn,args,stage,attempt_id=None):
    # The caller holds the source/stage lock before retiring interrupted stages.
    if attempt_id is not None:
        conn.execute("""UPDATE ops.execution_measurements SET outcome='INTERRUPTED',
            finished_at=GREATEST(clock_timestamp(),started_at) WHERE run_id=%s AND stage=%s AND outcome='RUNNING'""",
            (args.workflow_id,stage))
    key=uuid.uuid4()
    conn.execute("""INSERT INTO ops.execution_measurements(measurement_id,run_id,attempt_id,
        source_system,source_account_id,validation_mode,stage,started_at,outcome)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'RUNNING')""",
        (key,args.workflow_id,attempt_id,args.source,SOURCES[args.source][0],
         args.validation_mode,stage,datetime.now(timezone.utc)))
    conn.commit()
    return key,time.monotonic()


def finish(conn,measurement,outcome,commit=True):
    key,start=measurement
    elapsed=max(0,(time.monotonic()-start)*1000)
    conn.execute("""UPDATE ops.execution_measurements SET outcome=%s,
        finished_at=GREATEST(clock_timestamp(),started_at),duration_ms=%s
        WHERE measurement_id=%s AND outcome='RUNNING'""",(outcome,elapsed,key))
    if commit:
        conn.commit()
