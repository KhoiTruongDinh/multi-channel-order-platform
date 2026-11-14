\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE IF NOT EXISTS ops.source_cycle_owners (
    source_system TEXT NOT NULL CHECK(source_system IN ('internal_web','ebay_sim','etsy_sim')),
    source_account_id TEXT NOT NULL CHECK(source_account_id<>''),
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(source_system,source_account_id)
);
CREATE TABLE IF NOT EXISTS ops.coordinator_waits (
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    wait_kind TEXT NOT NULL CHECK(wait_kind IN ('source_slot','release_slot')),
    task_try_number INTEGER NOT NULL CHECK(task_try_number>0),
    measurement_id UUID NOT NULL UNIQUE REFERENCES ops.execution_measurements(measurement_id),
    PRIMARY KEY(run_id,wait_kind,task_try_number)
);
ALTER TABLE ops.source_cycle_owners OWNER TO platform_owner;
ALTER TABLE ops.coordinator_waits OWNER TO platform_owner;
REVOKE ALL ON ops.source_cycle_owners,ops.coordinator_waits FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON ops.source_cycle_owners TO platform_ingest;
GRANT SELECT,INSERT ON ops.coordinator_waits TO platform_ingest;
GRANT SELECT ON ops.source_cycle_owners,ops.coordinator_waits TO platform_transform;
INSERT INTO public.schema_migrations(migration_name)
VALUES('platform/011_coordinator_waits.sql') ON CONFLICT DO NOTHING;
COMMIT;
