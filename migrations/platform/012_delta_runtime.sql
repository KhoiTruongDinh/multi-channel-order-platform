\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE IF NOT EXISTS ops.delta_raw_keys (
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    source_system TEXT NOT NULL CHECK(source_system<>''),
    source_account_id TEXT NOT NULL CHECK(source_account_id<>''),
    source_order_id TEXT CHECK(source_order_id IS NULL OR source_order_id<>''),
    UNIQUE NULLS NOT DISTINCT(raw_record_id,source_order_id)
);
CREATE INDEX IF NOT EXISTS delta_raw_order_idx ON ops.delta_raw_keys
    (source_system,source_account_id,source_order_id,raw_record_id);
CREATE TABLE IF NOT EXISTS ops.delta_batches (
    batch_id UUID PRIMARY KEY REFERENCES ops.transform_batches(batch_id),
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL CHECK(plan_sha256 ~ '^[0-9a-f]{64}$'),
    build_schema TEXT NOT NULL,
    base_batch_id UUID REFERENCES ops.transform_batches(batch_id),
    bootstrap BOOLEAN NOT NULL,
    expected_nodes JSONB NOT NULL CHECK(jsonb_typeof(expected_nodes)='object'),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK ((source_system,source_account_id,build_schema) IN
        (('internal_web','WEB01','build_delta_web'),('ebay_sim','seller_sim_01','build_delta_ebay'),
         ('etsy_sim','7001','build_delta_etsy')))
);
CREATE TABLE IF NOT EXISTS ops.delta_new_inputs (
    batch_id UUID NOT NULL,raw_record_id UUID NOT NULL,
    PRIMARY KEY(batch_id,raw_record_id),
    FOREIGN KEY(batch_id,raw_record_id) REFERENCES ops.batch_inputs(batch_id,raw_record_id)
);
CREATE TABLE IF NOT EXISTS ops.delta_batch_keys (
    batch_id UUID NOT NULL REFERENCES ops.delta_batches(batch_id),
    source_order_id TEXT NOT NULL CHECK(source_order_id<>''),
    PRIMARY KEY(batch_id,source_order_id)
);
CREATE TABLE IF NOT EXISTS ops.delta_seen_raw (
    plan_sha256 TEXT NOT NULL CHECK(plan_sha256 ~ '^[0-9a-f]{64}$'),
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    processed_batch_id UUID NOT NULL REFERENCES ops.delta_batches(batch_id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(plan_sha256,raw_record_id)
);
CREATE TABLE IF NOT EXISTS ops.delta_results (
    batch_id UUID NOT NULL REFERENCES ops.delta_batches(batch_id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 5),
    plan_sha256 TEXT NOT NULL CHECK(plan_sha256 ~ '^[0-9a-f]{64}$'),
    passed BOOLEAN NOT NULL,
    results JSONB NOT NULL CHECK(jsonb_typeof(results)='object'),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(batch_id,attempt_number)
);
CREATE OR REPLACE FUNCTION ops.delta_immutable() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'delta operational evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION ops.delta_consume_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM ops.delta_batches d JOIN ops.transform_batches b USING(batch_id)
        JOIN ops.delta_new_inputs i USING(batch_id)
        WHERE d.batch_id=NEW.processed_batch_id AND d.plan_sha256=NEW.plan_sha256
          AND b.status='PUBLISHED' AND i.raw_record_id=NEW.raw_record_id) THEN
        RAISE EXCEPTION 'raw consumption requires matching published frozen delta input';
    END IF;
    RETURN NEW;
END; $$;
DO $$ DECLARE relation_name TEXT; BEGIN
    FOREACH relation_name IN ARRAY ARRAY['delta_raw_keys','delta_batches','delta_new_inputs',
        'delta_batch_keys','delta_seen_raw','delta_results'] LOOP
        EXECUTE format('ALTER TABLE ops.%I OWNER TO platform_owner',relation_name);
        EXECUTE format('REVOKE ALL ON ops.%I FROM PUBLIC',relation_name);
        EXECUTE format('DROP TRIGGER IF EXISTS delta_no_rewrite ON ops.%I',relation_name);
        EXECUTE format('CREATE TRIGGER delta_no_rewrite BEFORE UPDATE OR DELETE ON ops.%I
            FOR EACH ROW EXECUTE FUNCTION ops.delta_immutable()',relation_name);
        EXECUTE format('GRANT SELECT ON ops.%I TO platform_transform,platform_publisher',relation_name);
    END LOOP;
END; $$;
DROP TRIGGER IF EXISTS delta_consumption ON ops.delta_seen_raw;
CREATE TRIGGER delta_consumption BEFORE INSERT ON ops.delta_seen_raw
    FOR EACH ROW EXECUTE FUNCTION ops.delta_consume_guard();
GRANT INSERT ON ops.delta_raw_keys,ops.delta_batches,ops.delta_new_inputs,
    ops.delta_batch_keys,ops.delta_results TO platform_transform;
GRANT INSERT ON ops.delta_seen_raw TO platform_publisher;
GRANT SELECT ON ALL TABLES IN SCHEMA core TO platform_transform;
GRANT USAGE ON SCHEMA config TO platform_publisher;
GRANT SELECT ON config.product_mapping TO platform_publisher;
DO $$ DECLARE schema_name TEXT; BEGIN
    FOREACH schema_name IN ARRAY ARRAY['build_delta_web','build_delta_ebay','build_delta_etsy'] LOOP
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION platform_owner',schema_name);
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC',schema_name);
        EXECUTE format('GRANT USAGE,CREATE ON SCHEMA %I TO platform_transform',schema_name);
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO platform_publisher',schema_name);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE platform_transform IN SCHEMA %I
            GRANT SELECT ON TABLES TO platform_publisher',schema_name);
    END LOOP;
END; $$;
CREATE INDEX IF NOT EXISTS order_lines_snapshot_fk_idx ON core.order_lines_current(snapshot_id);
INSERT INTO public.schema_migrations(migration_name) VALUES('platform/012_delta_runtime.sql') ON CONFLICT DO NOTHING;
COMMIT;
