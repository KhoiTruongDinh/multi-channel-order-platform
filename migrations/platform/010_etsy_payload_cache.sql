\set ON_ERROR_STOP on
BEGIN;
CREATE SCHEMA IF NOT EXISTS cache AUTHORIZATION platform_owner;
REVOKE ALL ON SCHEMA cache FROM PUBLIC;
CREATE TABLE IF NOT EXISTS cache.etsy_payloads (
    source_system TEXT NOT NULL CHECK(source_system='etsy_sim'),
    source_account_id TEXT NOT NULL CHECK(source_account_id<>''),
    byte_sha256 BYTEA NOT NULL CHECK(octet_length(byte_sha256)=32),
    normalization_version TEXT NOT NULL CHECK(normalization_version ~ '^[0-9a-f]{32}$'),
    source_payload JSONB NOT NULL,
    order_json JSONB NOT NULL,
    content_fingerprint BYTEA NOT NULL CHECK(octet_length(content_fingerprint)=32),
    cached_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(source_system,source_account_id,byte_sha256,normalization_version)
);
ALTER TABLE cache.etsy_payloads OWNER TO platform_owner;
REVOKE ALL ON cache.etsy_payloads FROM PUBLIC;
GRANT USAGE ON SCHEMA cache TO platform_transform;
GRANT SELECT,INSERT ON cache.etsy_payloads TO platform_transform;
INSERT INTO public.schema_migrations(migration_name)
VALUES('platform/010_etsy_payload_cache.sql') ON CONFLICT DO NOTHING;
COMMIT;
