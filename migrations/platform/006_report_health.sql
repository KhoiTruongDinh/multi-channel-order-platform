\set ON_ERROR_STOP on
BEGIN;
CREATE OR REPLACE VIEW report.live_source_health AS
WITH scopes(source_system,source_account_id,publication_name) AS (
    VALUES ('internal_web'::TEXT,'WEB01'::TEXT,'website_orders'::TEXT),
           ('ebay_sim','seller_sim_01','ebay_orders'),('etsy_sim','7001','etsy_orders'))
SELECT s.*,
    (SELECT max(p.finished_at) FROM ops.pipeline_runs p WHERE p.source_system=s.source_system
     AND p.source_account_id=s.source_account_id AND p.stage='ACQUIRE' AND p.status='SUCCEEDED'
     AND (s.source_system<>'etsy_sim' OR p.stream_name IN ('receipt_work','receipts','receipts_polling')
          OR p.stream_name ~ '^receipts_test_[0-9a-f]{32}$')) AS last_successful_acquisition_at,
    (SELECT max(p.finished_at) FROM ops.pipeline_runs p WHERE p.source_system=s.source_system
     AND p.source_account_id=s.source_account_id AND p.status='FAILED') AS last_failed_at,
    (SELECT count(*) FROM ops.processing_work w WHERE w.source_system=s.source_system
     AND w.source_account_id=s.source_account_id AND w.state IN ('PENDING','LEASED')) AS pending_work_count,
    (SELECT count(*) FROM ops.processing_work w WHERE w.source_system=s.source_system
     AND w.source_account_id=s.source_account_id AND w.state IN ('FAILED','DEAD_LETTER')) AS failed_work_count,
    (SELECT count(*) FROM ops.data_exceptions e WHERE e.source_system=s.source_system
     AND e.source_account_id=s.source_account_id AND e.state<>'RESOLVED') AS unresolved_exception_count,
    (SELECT count(*) FROM ops.data_exceptions e WHERE e.source_system=s.source_system
     AND e.source_account_id=s.source_account_id AND e.state<>'RESOLVED' AND e.severity='BLOCKING') AS blocking_exception_count,
    'UNKNOWN'::TEXT AS coverage_state
FROM scopes s;

CREATE OR REPLACE VIEW report.live_runs AS
SELECT run_id,source_system,source_account_id,stage,stream_name,status,
       requested_window_start,requested_window_end,started_at,finished_at,batch_id
FROM ops.pipeline_runs WHERE source_system IS NOT NULL AND source_account_id IS NOT NULL;

CREATE OR REPLACE VIEW report.live_test_outcomes AS
SELECT b.batch_id,p.source_system,p.source_account_id,b.status,b.validation_mode,
       b.manifest_frozen_at,b.published_at,
       CASE WHEN b.status IN ('TESTED','PUBLISHED') THEN 'PASSED'
            WHEN b.status='FAILED' THEN 'FAILED_OR_INTERRUPTED'
            ELSE 'NOT_FINISHED' END::TEXT AS test_outcome
FROM ops.transform_batches b JOIN ops.pipeline_runs p USING(run_id)
WHERE p.source_system IS NOT NULL AND p.source_account_id IS NOT NULL;

CREATE OR REPLACE VIEW report.live_exceptions AS
SELECT exception_id,rule_id,severity,state,source_system,source_account_id,source_entity_id,
       run_id,batch_id,raw_record_id,first_seen_at,last_seen_at
FROM ops.data_exceptions WHERE state<>'RESOLVED';

CREATE OR REPLACE VIEW report.live_checkpoints AS
SELECT source_system,source_account_id,stream_name,completed_window_end,updated_at,successful_run_id
FROM ops.extraction_checkpoints;

REVOKE ALL ON report.live_source_health,report.live_runs,report.live_test_outcomes,
    report.live_exceptions,report.live_checkpoints FROM PUBLIC;
GRANT SELECT ON report.live_source_health,report.live_runs,report.live_test_outcomes,
    report.live_exceptions,report.live_checkpoints TO platform_report;
INSERT INTO public.schema_migrations(migration_name) VALUES ('platform/006_report_health.sql') ON CONFLICT DO NOTHING;
COMMIT;
