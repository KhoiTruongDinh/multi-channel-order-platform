\set ON_ERROR_STOP on
BEGIN;
CREATE OR REPLACE FUNCTION report.review_reasons(payment TEXT,fulfillment TEXT,cancellation TEXT)
RETURNS TEXT[] LANGUAGE SQL IMMUTABLE PARALLEL SAFE AS $$
SELECT CASE WHEN cancellation='CANCELED' THEN ARRAY[]::TEXT[] ELSE array_remove(ARRAY[
 CASE WHEN cancellation='REQUESTED' THEN 'Cancellation requested' END,
 CASE WHEN cancellation='NOT_REQUESTED' AND payment='PAID' AND fulfillment='PARTIALLY_SHIPPED' THEN 'Partial fulfillment' END,
 CASE WHEN cancellation='NOT_REQUESTED' AND payment='PAID' AND fulfillment='NOT_STARTED' THEN 'Fulfillment not started' END,
 CASE WHEN payment='UNPAID' THEN 'Payment pending' END,
 CASE WHEN payment IS NULL OR payment NOT IN ('PAID','UNPAID') THEN 'Payment status verification' END,
 CASE WHEN fulfillment IS NULL OR fulfillment NOT IN ('NOT_STARTED','PARTIALLY_SHIPPED','SHIPPED','DELIVERED') THEN 'Fulfillment status verification' END,
 CASE WHEN (cancellation IS NULL OR cancellation NOT IN ('NOT_REQUESTED','REQUESTED','CANCELED'))
       AND fulfillment IN ('NOT_STARTED','PARTIALLY_SHIPPED') THEN 'Cancellation status verification' END
],NULL) END $$;
REVOKE ALL ON FUNCTION report.review_reasons(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION report.review_reasons(TEXT,TEXT,TEXT) TO platform_report;
CREATE OR REPLACE VIEW report.operations_orders AS
SELECT c.*,report.review_reasons(payment_state,fulfillment_state,cancellation_state) AS review_reasons,
 EXISTS(SELECT FROM core.order_lines_current l WHERE
   (l.source_system,l.source_account_id,l.source_order_id)=(c.source_system,c.source_account_id,c.source_order_id)
   AND (l.mapping_status<>'CONFIRMED' OR l.canonical_variant_id IS NULL)) AS data_issue
FROM core.orders_current c;
CREATE INDEX IF NOT EXISTS orders_report_seek_idx ON core.orders_current
 (source_created_at DESC,source_system DESC,source_account_id DESC,source_order_id DESC);
CREATE INDEX IF NOT EXISTS orders_report_lookup_idx ON core.orders_current
 (source_order_id,source_system,source_account_id);
CREATE INDEX IF NOT EXISTS history_report_detail_idx ON core.order_snapshot_history
 (source_system,source_account_id,source_order_id,source_updated_at,snapshot_id);
CREATE INDEX IF NOT EXISTS pipeline_source_time_idx ON ops.pipeline_runs(source_system,source_account_id,started_at DESC);
CREATE INDEX IF NOT EXISTS work_source_state_idx ON ops.processing_work(source_system,source_account_id,state);

CREATE TABLE IF NOT EXISTS ops.execution_measurements (
 measurement_id UUID PRIMARY KEY,run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
 attempt_id UUID REFERENCES ops.task_attempts(attempt_id),
 source_system TEXT NOT NULL,source_account_id TEXT NOT NULL,
 validation_mode TEXT NOT NULL CHECK(validation_mode IN ('s01','runtime')),
 stage TEXT NOT NULL CHECK(stage IN ('collect','freeze','build_and_test','publish','source_slot','release_slot')),
 started_at TIMESTAMPTZ NOT NULL,finished_at TIMESTAMPTZ,
 duration_ms DOUBLE PRECISION CHECK(duration_ms>=0 AND duration_ms<'Infinity'::DOUBLE PRECISION),
 outcome TEXT NOT NULL CHECK(outcome IN ('RUNNING','SUCCEEDED','FAILED','TIMED_OUT','INTERRUPTED')),
 CHECK((outcome='RUNNING')=(finished_at IS NULL)),
 CHECK(finished_at IS NULL OR finished_at>=started_at),
 CHECK(outcome IN ('RUNNING','INTERRUPTED') OR duration_ms IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS execution_source_time_idx ON ops.execution_measurements(source_system,source_account_id,started_at DESC);
CREATE INDEX IF NOT EXISTS execution_run_stage_idx ON ops.execution_measurements(run_id,stage);
CREATE OR REPLACE FUNCTION ops.protect_measurement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.measurement_id,NEW.run_id,NEW.attempt_id,NEW.source_system,NEW.source_account_id,NEW.validation_mode,NEW.stage,NEW.started_at)
 IS DISTINCT FROM (OLD.measurement_id,OLD.run_id,OLD.attempt_id,OLD.source_system,OLD.source_account_id,OLD.validation_mode,OLD.stage,OLD.started_at)
 OR OLD.outcome<>'RUNNING' THEN RAISE EXCEPTION 'measurement identity/terminal outcome immutable'; END IF;
 RETURN NEW; END $$;
DROP TRIGGER IF EXISTS protect_measurement ON ops.execution_measurements;
CREATE TRIGGER protect_measurement BEFORE UPDATE ON ops.execution_measurements FOR EACH ROW EXECUTE FUNCTION ops.protect_measurement();
CREATE TABLE IF NOT EXISTS ops.scheduler_observations (
 dag_id TEXT PRIMARY KEY,source_system TEXT NOT NULL,source_account_id TEXT NOT NULL,
 is_paused BOOLEAN NOT NULL,latest_run_state TEXT,scheduler_heartbeat_at TIMESTAMPTZ,
 observed_at TIMESTAMPTZ NOT NULL
);
ALTER TABLE ops.processing_work ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMPTZ;
CREATE OR REPLACE FUNCTION ops.work_recorded_clock() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='INSERT' THEN NEW.recorded_at=clock_timestamp();
 ELSIF NEW.recorded_at IS DISTINCT FROM OLD.recorded_at THEN RAISE EXCEPTION 'work recording clock immutable'; END IF;
 RETURN NEW; END $$;
DROP TRIGGER IF EXISTS work_recorded_clock ON ops.processing_work;
CREATE TRIGGER work_recorded_clock BEFORE INSERT OR UPDATE ON ops.processing_work FOR EACH ROW EXECUTE FUNCTION ops.work_recorded_clock();
CREATE OR REPLACE VIEW report.execution_measurements AS
 SELECT measurement_id,run_id,source_system,source_account_id,validation_mode,stage,
 started_at,finished_at,duration_ms,outcome FROM ops.execution_measurements;
CREATE OR REPLACE VIEW report.scheduler_observations AS
 SELECT dag_id,source_system,source_account_id,is_paused,latest_run_state,scheduler_heartbeat_at,observed_at FROM ops.scheduler_observations;
CREATE OR REPLACE VIEW report.work_backlog AS
 SELECT source_system,source_account_id,state,count(*) AS work_count,
 CASE WHEN count(*) FILTER(WHERE recorded_at IS NULL)>0 THEN NULL ELSE min(recorded_at) END AS oldest_recorded_at
 FROM ops.processing_work WHERE state<>'SUCCEEDED' GROUP BY source_system,source_account_id,state;
REVOKE ALL ON ops.execution_measurements,ops.scheduler_observations FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON ops.execution_measurements,ops.scheduler_observations TO platform_ingest;
GRANT SELECT ON ops.execution_measurements,ops.scheduler_observations TO platform_transform;
REVOKE ALL ON report.operations_orders,report.execution_measurements,report.scheduler_observations,report.work_backlog FROM PUBLIC;
GRANT SELECT ON report.operations_orders,report.execution_measurements,report.scheduler_observations,report.work_backlog TO platform_report;
INSERT INTO public.schema_migrations(migration_name) VALUES('platform/008_report_queries_telemetry.sql') ON CONFLICT DO NOTHING;
COMMIT;
