\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE IF NOT EXISTS ops.collection_options (
    run_id UUID PRIMARY KEY REFERENCES ops.pipeline_runs,
    settings JSONB NOT NULL CHECK((jsonb_typeof(settings)='object'
        AND settings ?& ARRAY['mode','workers','page_size']
        AND settings->>'mode'='page-reuse'
        AND settings->'workers' IN ('1'::JSONB,'2'::JSONB)
        AND (settings->>'page_size') ~ '^[1-9][0-9]*$'
        AND (settings->>'page_size')::INTEGER BETWEEN 1 AND 200) IS TRUE)
);
CREATE TABLE IF NOT EXISTS ops.ebay_collection_scans (
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs,
    scan_number SMALLINT NOT NULL CHECK(scan_number BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'RUNNING' CHECK(status IN ('RUNNING','VALIDATED','INVALID')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    finished_at TIMESTAMPTZ,
    PRIMARY KEY(run_id,scan_number),
    CHECK((status='RUNNING')=(finished_at IS NULL)),
    CHECK(finished_at IS NULL OR finished_at>=started_at)
);
CREATE TABLE IF NOT EXISTS ops.ebay_scan_restarts (
    run_id UUID NOT NULL,
    scan_number SMALLINT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(run_id,scan_number),
    FOREIGN KEY(run_id,scan_number) REFERENCES ops.ebay_collection_scans
);
CREATE TABLE IF NOT EXISTS ops.acquisition_elements (
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records,
    source_entity_id TEXT NOT NULL CHECK(source_entity_id<>''),
    element_index INTEGER NOT NULL CHECK(element_index>=0),
    collection_run_id UUID NOT NULL REFERENCES ops.pipeline_runs,
    scan_number SMALLINT NOT NULL CHECK(scan_number BETWEEN 1 AND 5),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(raw_record_id,source_entity_id),
    UNIQUE(raw_record_id,element_index)
);
CREATE TABLE IF NOT EXISTS cache.etsy_elements (
    source_system TEXT NOT NULL CHECK(source_system='etsy_sim'),
    source_account_id TEXT NOT NULL CHECK(source_account_id<>''),
    source_entity_id TEXT NOT NULL CHECK(source_entity_id<>''),
    element_sha256 BYTEA NOT NULL CHECK(octet_length(element_sha256)=32),
    normalization_version TEXT NOT NULL CHECK(normalization_version ~ '^[0-9a-f]{32}$'),
    source_payload JSONB NOT NULL CHECK(jsonb_typeof(source_payload)='object'),
    order_json JSONB NOT NULL CHECK(jsonb_typeof(order_json)='object'),
    content_fingerprint BYTEA NOT NULL CHECK(octet_length(content_fingerprint)=32),
    cached_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(source_system,source_account_id,source_entity_id,element_sha256,normalization_version)
);
CREATE OR REPLACE FUNCTION ops.acquisition_immutable() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'acquisition evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION ops.acquisition_element_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE r RECORD; identity_value TEXT; validated BOOLEAN;
BEGIN
    SELECT run_id,response_status,source_system,source_account_id,resource_type,parsed_payload,metadata
      INTO STRICT r FROM raw.raw_records WHERE raw_record_id=NEW.raw_record_id;
    IF r.run_id<>NEW.collection_run_id OR r.response_status IS DISTINCT FROM 200 THEN
        RAISE EXCEPTION 'element needs actual successful collection page';
    END IF;
    IF r.source_system='ebay_sim' AND r.source_account_id='seller_sim_01' AND r.resource_type='ebay_orders' THEN
        identity_value := r.parsed_payload->'orders'->NEW.element_index->>'orderId';
        SELECT status='VALIDATED' INTO validated FROM ops.ebay_collection_scans
          WHERE run_id=NEW.collection_run_id AND scan_number=NEW.scan_number;
        validated := validated AND r.metadata->>'collection_scan'=NEW.scan_number::TEXT;
    ELSIF r.source_system='etsy_sim' AND r.source_account_id='7001' AND r.resource_type='etsy_receipts' THEN
        identity_value := r.parsed_payload->'results'->NEW.element_index->>'receipt_id';
        SELECT status='VALIDATED' INTO validated FROM ops.etsy_recovery_scans
          WHERE run_id=NEW.collection_run_id AND scan_number=NEW.scan_number;
        validated := validated AND EXISTS (SELECT 1 FROM ops.etsy_http_attempts a
            WHERE a.raw_record_id=NEW.raw_record_id AND a.run_id=NEW.collection_run_id
              AND (a.recovery_scan_number=NEW.scan_number OR
                   (NEW.scan_number=1 AND a.recovery_scan_number IS NULL)));
    END IF;
    IF identity_value IS DISTINCT FROM NEW.source_entity_id OR validated IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'element identity or validated scan mismatch';
    END IF;
    RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION ops.ebay_scan_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'scan audit cannot be deleted'; END IF;
    IF OLD.status<>'RUNNING' OR NEW.status='RUNNING' OR
       (OLD.run_id,OLD.scan_number,OLD.started_at) IS DISTINCT FROM
       (NEW.run_id,NEW.scan_number,NEW.started_at) THEN
        RAISE EXCEPTION 'only a running scan may finish';
    END IF;
    RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS acquisition_element_guard ON ops.acquisition_elements;
CREATE TRIGGER acquisition_element_guard BEFORE INSERT ON ops.acquisition_elements
 FOR EACH ROW EXECUTE FUNCTION ops.acquisition_element_guard();
DROP TRIGGER IF EXISTS ebay_scan_guard ON ops.ebay_collection_scans;
CREATE TRIGGER ebay_scan_guard BEFORE UPDATE OR DELETE ON ops.ebay_collection_scans
 FOR EACH ROW EXECUTE FUNCTION ops.ebay_scan_guard();
DO $$ DECLARE t TEXT; BEGIN
    FOREACH t IN ARRAY ARRAY['collection_options','ebay_collection_scans','ebay_scan_restarts','acquisition_elements'] LOOP
        EXECUTE format('ALTER TABLE ops.%I OWNER TO platform_owner',t);
        EXECUTE format('REVOKE ALL ON ops.%I FROM PUBLIC',t);
        EXECUTE format('GRANT SELECT,INSERT ON ops.%I TO platform_ingest',t);
        EXECUTE format('GRANT SELECT ON ops.%I TO platform_transform,platform_publisher',t);
        IF t<>'ebay_collection_scans' THEN
            EXECUTE format('DROP TRIGGER IF EXISTS acquisition_no_rewrite ON ops.%I',t);
            EXECUTE format('CREATE TRIGGER acquisition_no_rewrite BEFORE UPDATE OR DELETE ON ops.%I FOR EACH ROW EXECUTE FUNCTION ops.acquisition_immutable()',t);
        END IF;
    END LOOP;
END; $$;
GRANT UPDATE ON ops.ebay_collection_scans TO platform_ingest;
ALTER TABLE cache.etsy_elements OWNER TO platform_owner;
REVOKE ALL ON cache.etsy_elements FROM PUBLIC;
GRANT SELECT,INSERT ON cache.etsy_elements TO platform_transform;
DROP TRIGGER IF EXISTS acquisition_no_rewrite ON cache.etsy_elements;
CREATE TRIGGER acquisition_no_rewrite BEFORE UPDATE OR DELETE ON cache.etsy_elements
 FOR EACH ROW EXECUTE FUNCTION ops.acquisition_immutable();
CREATE INDEX IF NOT EXISTS marketplace_http_cooldown_idx ON raw.raw_records
 (source_system,source_account_id,(metadata->>'fetched_at')) WHERE response_status IN (429,503);
CREATE INDEX IF NOT EXISTS etsy_http_raw_recorded_idx ON ops.etsy_http_attempts(raw_record_id,recorded_at);
CREATE UNIQUE INDEX IF NOT EXISTS ebay_one_running_scan_idx ON ops.ebay_collection_scans(run_id) WHERE status='RUNNING';
INSERT INTO public.schema_migrations(migration_name)
VALUES('platform/014_acquisition_elements.sql') ON CONFLICT DO NOTHING;
COMMIT;
