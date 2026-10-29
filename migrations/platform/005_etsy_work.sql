\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE ops.processing_work ADD COLUMN IF NOT EXISTS lease_token UUID;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname='etsy_lease_token_state') THEN
        ALTER TABLE ops.processing_work ADD CONSTRAINT etsy_lease_token_state
          CHECK (work_type <> 'ETSY_RECEIPT' OR ((state='LEASED')=(lease_token IS NOT NULL)));
    END IF;
END $$;
CREATE OR REPLACE FUNCTION ops.protect_etsy_work() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
    IF OLD.work_type='ETSY_RECEIPT' AND
       (NEW.cycle_attempts<OLD.cycle_attempts OR
        (NEW.dedupe_key,NEW.work_type,NEW.source_system,NEW.source_account_id,NEW.source_entity_id,
         NEW.trigger_raw_record_id,NEW.inbox_id,NEW.created_at)
        IS DISTINCT FROM
        (OLD.dedupe_key,OLD.work_type,OLD.source_system,OLD.source_account_id,OLD.source_entity_id,
         OLD.trigger_raw_record_id,OLD.inbox_id,OLD.created_at)) THEN
        RAISE EXCEPTION 'Etsy work identity/budget is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_etsy_work ON ops.processing_work;
CREATE TRIGGER protect_etsy_work BEFORE UPDATE ON ops.processing_work
FOR EACH ROW EXECUTE FUNCTION ops.protect_etsy_work();
CREATE TABLE IF NOT EXISTS ops.etsy_work_context (
    work_id UUID PRIMARY KEY REFERENCES ops.processing_work(work_id),
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    resource_url TEXT NOT NULL CHECK (btrim(resource_url)<>''),
    cycle_id TEXT NOT NULL CHECK (btrim(cycle_id)<>'')
);
ALTER TABLE ops.etsy_work_context ADD COLUMN IF NOT EXISTS replay_of_work_id UUID REFERENCES ops.processing_work(work_id);
DROP TRIGGER IF EXISTS etsy_context_immutable ON ops.etsy_work_context;
CREATE TRIGGER etsy_context_immutable BEFORE UPDATE OR DELETE ON ops.etsy_work_context
FOR EACH ROW EXECUTE FUNCTION ops.reject_cycle_mutation();
CREATE TABLE IF NOT EXISTS ops.etsy_http_attempts (
    attempt_id UUID PRIMARY KEY,
    work_id UUID REFERENCES ops.processing_work(work_id),
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    lease_token UUID,
    attempt_number INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 5),
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    recorded_at TIMESTAMPTZ NOT NULL
);
ALTER TABLE ops.etsy_http_attempts ADD COLUMN IF NOT EXISTS collection_run_id UUID REFERENCES ops.pipeline_runs(run_id);
REVOKE ALL ON ops.etsy_work_context,ops.etsy_http_attempts FROM PUBLIC;
GRANT SELECT,INSERT ON ops.etsy_work_context,ops.etsy_http_attempts TO platform_ingest;
GRANT SELECT ON ops.etsy_work_context,ops.etsy_http_attempts TO platform_transform;
INSERT INTO public.schema_migrations(migration_name) VALUES ('platform/005_etsy_work.sql') ON CONFLICT DO NOTHING;
COMMIT;
