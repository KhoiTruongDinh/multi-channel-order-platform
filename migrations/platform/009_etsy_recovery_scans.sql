\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE IF NOT EXISTS ops.etsy_recovery_scans (
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    scan_number SMALLINT NOT NULL CHECK (scan_number BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','VALIDATED','INVALID')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    finished_at TIMESTAMPTZ,
    error_code TEXT,
    PRIMARY KEY(run_id,scan_number),
    CHECK ((status='RUNNING')=(finished_at IS NULL)),
    CHECK (finished_at IS NULL OR finished_at>=started_at),
    CHECK ((status='INVALID' AND error_code='PAGE_SET_CHANGED') OR
           (status<>'INVALID' AND error_code IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS etsy_recovery_one_active_scan
    ON ops.etsy_recovery_scans(run_id) WHERE status<>'INVALID';
-- CHECK permits UNKNOWN; explicitly forbid a NULL error on INVALID rows.
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conrelid='ops.etsy_recovery_scans'::regclass
                   AND conname='etsy_scan_error_presence') THEN
        ALTER TABLE ops.etsy_recovery_scans ADD CONSTRAINT etsy_scan_error_presence
            CHECK ((status='INVALID')=(error_code IS NOT NULL));
    END IF;
END $$;
CREATE OR REPLACE FUNCTION ops.protect_etsy_recovery_scan() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Recovery scan audit cannot be deleted'; END IF;
    IF OLD.status<>'RUNNING' OR NEW.status='RUNNING' OR
       (NEW.run_id,NEW.scan_number,NEW.started_at) IS DISTINCT FROM
       (OLD.run_id,OLD.scan_number,OLD.started_at) THEN
        RAISE EXCEPTION 'Recovery scan identity/state is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_etsy_recovery_scan ON ops.etsy_recovery_scans;
CREATE TRIGGER protect_etsy_recovery_scan BEFORE UPDATE OR DELETE ON ops.etsy_recovery_scans
    FOR EACH ROW EXECUTE FUNCTION ops.protect_etsy_recovery_scan();
ALTER TABLE ops.etsy_http_attempts ADD COLUMN IF NOT EXISTS recovery_scan_number SMALLINT;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conrelid='ops.etsy_http_attempts'::regclass
                   AND conname='etsy_http_recovery_scan_fk') THEN
        ALTER TABLE ops.etsy_http_attempts ADD CONSTRAINT etsy_http_recovery_scan_fk
            FOREIGN KEY(run_id,recovery_scan_number) REFERENCES ops.etsy_recovery_scans(run_id,scan_number);
        ALTER TABLE ops.etsy_http_attempts ADD CONSTRAINT etsy_http_recovery_scan_kind
            CHECK (recovery_scan_number IS NULL OR work_id IS NULL);
    END IF;
END $$;
REVOKE ALL ON ops.etsy_recovery_scans FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON ops.etsy_recovery_scans TO platform_ingest;
GRANT SELECT ON ops.etsy_recovery_scans TO platform_transform;
INSERT INTO public.schema_migrations(migration_name)
    VALUES ('platform/009_etsy_recovery_scans.sql') ON CONFLICT DO NOTHING;
COMMIT;
