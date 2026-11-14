"""Fair logical-cycle admission; active batch recovery bypasses this queue."""
from orchestration import website_workflow as workflow


def is_turn(args):
    with workflow.connect() as conn:
        first=conn.execute('''WITH latest AS (
            SELECT DISTINCT ON (w.run_id) w.run_id,m.started_at,m.outcome,
                   min(m.started_at) OVER (PARTITION BY w.run_id) AS first_wait_at
              FROM ops.coordinator_waits w
              JOIN ops.execution_measurements m USING(measurement_id)
              JOIN ops.pipeline_runs p ON p.run_id=w.run_id
             WHERE w.wait_kind='release_slot' AND p.status='RUNNING'
             ORDER BY w.run_id,w.task_try_number DESC
        ) SELECT run_id FROM latest WHERE outcome='RUNNING'
            AND clock_timestamp()<started_at+make_interval(secs=>%s)
          ORDER BY first_wait_at,run_id LIMIT 1''',(args.wait_seconds,)).fetchone()
    return first is None or first[0]==args.workflow_id
