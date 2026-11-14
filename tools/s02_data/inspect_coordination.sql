-- DBeaver, data_platform, local administrative connection. Read-only.
-- Cache rows are payload computations, NOT order counts or new raw evidence.
SELECT source_system,source_account_id,normalization_version,count(*) AS cached_payloads,
       min(cached_at) AS first_cached_at,max(cached_at) AS latest_cached_at
FROM cache.etsy_payloads GROUP BY source_system,source_account_id,normalization_version;

-- RUNNING owner stays in charge even when its Airflow task is up_for_reschedule.
SELECT o.source_system,o.source_account_id,o.run_id,p.status,p.airflow_dag_id,
       p.airflow_run_id,o.acquired_at,p.log_reference
FROM ops.source_cycle_owners o JOIN ops.pipeline_runs p USING(run_id)
ORDER BY o.source_system;

-- One clock per phase/real task attempt, not one fresh clock per sensor poke.
-- RUNNING duration here is wall wait, including scheduler rescheduling, not CPU.
SELECT w.run_id,w.wait_kind,w.task_try_number,p.status AS workflow_status,p.airflow_dag_id,p.airflow_run_id,
       m.started_at,m.finished_at,m.outcome,
       CASE WHEN m.outcome='RUNNING' THEN extract(epoch FROM clock_timestamp()-m.started_at)
            ELSE m.duration_ms/1000 END AS wall_seconds
FROM ops.coordinator_waits w JOIN ops.execution_measurements m USING(measurement_id)
JOIN ops.pipeline_runs p ON p.run_id=w.run_id
ORDER BY m.started_at DESC LIMIT 50;

-- Current FIFO release tickets, using the live deployment's 300-second policy.
-- If POLLING_SLOT_WAIT_SECONDS changes, use that same value here (diagnostic only).
-- An already-active batch resumes before queued tickets, by design.
WITH latest AS (
 SELECT DISTINCT ON (w.run_id) w.run_id,p.airflow_dag_id,w.task_try_number,
        m.started_at,m.outcome,
        min(m.started_at) OVER (PARTITION BY w.run_id) AS first_wait_at
 FROM ops.coordinator_waits w JOIN ops.execution_measurements m USING(measurement_id)
 JOIN ops.pipeline_runs p ON p.run_id=w.run_id
 WHERE w.wait_kind='release_slot' AND p.status='RUNNING'
 ORDER BY w.run_id,w.task_try_number DESC
)
SELECT *,outcome='RUNNING' AND clock_timestamp()<started_at+interval '300 seconds' AS eligible
FROM latest ORDER BY first_wait_at,run_id;

-- Separate DBeaver connection: airflow_meta. Do NOT execute below in data_platform.
-- SELECT dag_id,run_id,task_id,state,try_number FROM task_instance
-- WHERE dag_id IN ('website_polling','ebay_polling','etsy_inbox','etsy_recovery')
--   AND state IN ('running','queued','up_for_reschedule','up_for_retry')
-- ORDER BY dag_id,run_id DESC;
