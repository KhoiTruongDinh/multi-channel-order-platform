-- Read-only inspection. Execute each section in the indicated database.
-- In marketplace_sim: use the exact dataset printed at ADMITTED for a fixed run.
SELECT d.name,d.campaign_id,b.published_at,b.shift_seconds
FROM s02.local_datasets d JOIN s02.live_batches b USING(campaign_id)
WHERE d.name LIKE 'campaign-%'
ORDER BY b.published_at DESC LIMIT 20;

-- marketplace_sim: final versions for all three sources in the latest campaign.
WITH chosen AS (
 SELECT d.campaign_id FROM s02.local_datasets d JOIN s02.live_batches b USING(campaign_id)
 WHERE d.name LIKE 'campaign-%'
 ORDER BY b.published_at DESC LIMIT 1
), candidates AS (
 SELECT v.campaign_id,v.source,v.account_id,v.order_id,v.sequence,v.source_updated_at
 FROM chosen JOIN s02.versions v USING(campaign_id)
 UNION ALL
 SELECT v.campaign_id,'internal_web','WEB01',v.order_id,v.sequence,
  (v.payload#>>'{orders,0,updated_at}')::timestamptz
 FROM chosen JOIN s02.website_versions v USING(campaign_id)
)
SELECT DISTINCT ON(v.source,v.account_id,v.order_id)
 v.source,v.account_id,v.order_id,v.sequence,
 v.source_updated_at+make_interval(secs=>b.shift_seconds::double precision) AS effective_updated_at
FROM candidates v JOIN s02.live_batches b USING(campaign_id)
ORDER BY v.source,v.account_id,v.order_id,v.sequence DESC;

-- marketplace_sim: source plan counts, including bounded rate profiles.
-- Replace the prefix filter with d.name='EXACT_PRINTED_DATASET' to pin one run.
WITH chosen AS (
 SELECT d.campaign_id,b.shift_seconds FROM s02.local_datasets d
 JOIN s02.live_batches b USING(campaign_id)
 WHERE d.name LIKE 'campaign-%' ORDER BY b.published_at DESC LIMIT 1
), versions AS (
 SELECT 'internal_web' AS source,v.order_id,v.visible_at,c.shift_seconds
 FROM s02.website_versions v JOIN chosen c USING(campaign_id)
 UNION ALL
 SELECT v.source,v.order_id,v.visible_at,c.shift_seconds
 FROM s02.versions v JOIN chosen c USING(campaign_id)
)
SELECT source,count(DISTINCT order_id) AS planned_orders,count(*) AS planned_versions,
 count(*) FILTER (WHERE visible_at+make_interval(secs=>shift_seconds::double precision)>statement_timestamp()) AS future_versions
FROM versions GROUP BY source ORDER BY source;

-- data_platform: paste the scoped order IDs above for exact source-to-core checks.
-- No campaign selector belongs in production collectors.
-- SELECT source_system,source_account_id,source_order_id,source_updated_at,
--        payment_state,fulfillment_state,cancellation_state
-- FROM core.orders_current
-- WHERE (source_system,source_account_id,source_order_id)
-- IN (('PASTE_SOURCE','PASTE_ACCOUNT','PASTE_ORDER_ID'));

-- data_platform: recent workflow stages (durations are observations, not SLA grades).
SELECT p.source_system,p.airflow_dag_id,p.airflow_run_id,p.batch_id,
 a.task_name,a.attempt_number,a.status,a.started_at,a.finished_at,a.error_code
FROM ops.pipeline_runs p JOIN ops.task_attempts a USING(run_id)
WHERE p.started_at>=statement_timestamp()-interval '1 hour'
 AND a.task_name IN ('collect','freeze','build_and_test','publish')
ORDER BY a.started_at DESC LIMIT 80;

-- data_platform: last-good publication persists during source failure.
SELECT publication_name,batch_id,published_at,mapping_version,transformation_version
FROM ops.publication_state ORDER BY publication_name;

-- data_platform: bounded Etsy scan reconciliation (migration009).
-- INVALID is preserved evidence, not an erased attempt or necessarily a failed
-- whole workflow: a later scan may VALIDATE within the SAME URL/work budgets.
SELECT p.airflow_dag_id,p.airflow_run_id,s.run_id,s.scan_number,s.status,
 s.started_at,s.finished_at,s.error_code,count(a.attempt_id) AS list_http_attempts
FROM ops.etsy_recovery_scans s JOIN ops.pipeline_runs p USING(run_id)
LEFT JOIN ops.etsy_http_attempts a ON a.run_id=s.run_id
 AND a.recovery_scan_number=s.scan_number
GROUP BY p.airflow_dag_id,p.airflow_run_id,s.run_id,s.scan_number,s.status,
 s.started_at,s.finished_at,s.error_code
ORDER BY s.started_at DESC LIMIT 40;

-- data_platform: HTTP failures/timeouts remain audit records, not erased by retry.
SELECT raw_record_id,run_id,acquired_at AS observation_clock,
 metadata->>'fetched_at' AS physical_fetch_time,
 metadata->>'http_attempt' AS http_attempt,response_status
FROM raw.raw_records
WHERE source_system='ebay_sim' AND acquired_at>=statement_timestamp()-interval '1 hour'
 AND (response_status IS NULL OR response_status>=400)
ORDER BY metadata->>'fetched_at' DESC NULLS LAST,acquired_at DESC LIMIT 40;

-- airflow_meta (NOT data_platform): latest cycle-task attempt executor queue.
-- This30-minute view is whole-stack, not one campaign's exclusive work.
-- For comparison, replace the time filter with the report's admission/source-end bounds.
SELECT t.dag_id,
 count(*) FILTER(WHERE t.start_date>=t.queued_dttm) AS queue_samples,
 count(*) FILTER(WHERE t.start_date IS NULL OR t.queued_dttm IS NULL) AS not_started_or_missing_clock,
 round((percentile_cont(.5) WITHIN GROUP(ORDER BY extract(epoch FROM t.start_date-t.queued_dttm))
   FILTER(WHERE t.start_date>=t.queued_dttm))::numeric,2) AS queue_p50_seconds,
 round((percentile_cont(.95) WITHIN GROUP(ORDER BY extract(epoch FROM t.start_date-t.queued_dttm))
   FILTER(WHERE t.start_date>=t.queued_dttm))::numeric,2) AS queue_p95_seconds
FROM task_instance t JOIN dag_run d USING(dag_id,run_id)
WHERE t.task_id='cycle' AND t.map_index=-1 AND d.run_type='scheduled'
 AND d.start_date>=statement_timestamp()-interval '30 minutes'
GROUP BY t.dag_id ORDER BY t.dag_id;
