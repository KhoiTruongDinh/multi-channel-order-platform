\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE ops.transform_batches ADD COLUMN IF NOT EXISTS validation_mode TEXT
    NOT NULL DEFAULT 's01' CHECK (validation_mode IN ('s01','runtime'));
CREATE OR REPLACE FUNCTION ops.protect_batch_config() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
    IF (NEW.run_id,NEW.mapping_version,NEW.transformation_version,NEW.validation_mode,NEW.manifest_frozen_at)
       IS DISTINCT FROM (OLD.run_id,OLD.mapping_version,OLD.transformation_version,OLD.validation_mode,OLD.manifest_frozen_at) THEN
        RAISE EXCEPTION 'frozen batch configuration is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_batch_config ON ops.transform_batches;
CREATE TRIGGER protect_batch_config BEFORE UPDATE ON ops.transform_batches
FOR EACH ROW EXECUTE FUNCTION ops.protect_batch_config();
CREATE TABLE IF NOT EXISTS ops.polling_cycles (
    run_id UUID PRIMARY KEY REFERENCES ops.pipeline_runs(run_id),
    validation_mode TEXT NOT NULL CHECK (validation_mode='runtime'),
    clock_mode TEXT NOT NULL CHECK (clock_mode='current'),
    mapping_version TEXT NOT NULL CHECK (btrim(mapping_version)<>''),
    transformation_version TEXT NOT NULL CHECK (btrim(transformation_version)<>''),
    overlap_seconds INTEGER NOT NULL CHECK (overlap_seconds>=0),
    settings JSONB NOT NULL CHECK (jsonb_typeof(settings)='object')
);
CREATE OR REPLACE FUNCTION ops.reject_cycle_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'polling cycle configuration is immutable'; END $$;
DROP TRIGGER IF EXISTS polling_cycle_immutable ON ops.polling_cycles;
CREATE TRIGGER polling_cycle_immutable BEFORE UPDATE OR DELETE ON ops.polling_cycles
FOR EACH ROW EXECUTE FUNCTION ops.reject_cycle_mutation();
CREATE OR REPLACE FUNCTION ops.protect_polling_window() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
    IF EXISTS (SELECT 1 FROM ops.polling_cycles WHERE run_id=OLD.run_id)
       AND (NEW.requested_window_start,NEW.requested_window_end,NEW.source_system,
            NEW.source_account_id,NEW.airflow_dag_id,NEW.airflow_run_id)
       IS DISTINCT FROM (OLD.requested_window_start,OLD.requested_window_end,OLD.source_system,
            OLD.source_account_id,OLD.airflow_dag_id,OLD.airflow_run_id) THEN
        RAISE EXCEPTION 'polling window/context is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_polling_window ON ops.pipeline_runs;
CREATE TRIGGER protect_polling_window BEFORE UPDATE ON ops.pipeline_runs
FOR EACH ROW EXECUTE FUNCTION ops.protect_polling_window();
REVOKE ALL ON ops.polling_cycles FROM PUBLIC;
GRANT SELECT,INSERT ON ops.polling_cycles TO platform_ingest;
GRANT SELECT ON ops.polling_cycles TO platform_transform,platform_publisher;
INSERT INTO public.schema_migrations(migration_name) VALUES ('platform/004_polling.sql') ON CONFLICT DO NOTHING;
COMMIT;
