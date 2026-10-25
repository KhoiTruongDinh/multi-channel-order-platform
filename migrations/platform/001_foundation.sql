\set ON_ERROR_STOP on
BEGIN;

CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS ops AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS config AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS core AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS mart AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS report AUTHORIZATION platform_owner;
CREATE SCHEMA IF NOT EXISTS build AUTHORIZATION platform_owner;

CREATE TABLE IF NOT EXISTS raw.raw_records (
    raw_record_id UUID PRIMARY KEY,
    run_id UUID NOT NULL,
    source_system TEXT NOT NULL CHECK (btrim(source_system) <> ''),
    source_account_id TEXT NOT NULL CHECK (btrim(source_account_id) <> ''),
    resource_type TEXT NOT NULL CHECK (btrim(resource_type) <> ''),
    resource_locator TEXT,
    request_method TEXT,
    request_window_start TIMESTAMPTZ,
    request_window_end TIMESTAMPTZ,
    response_status INTEGER CHECK (response_status BETWEEN 100 AND 599),
    acquired_at TIMESTAMPTZ NOT NULL,
    raw_bytes BYTEA NOT NULL,
    parsed_payload JSONB,
    byte_sha256 BYTEA NOT NULL CHECK (octet_length(byte_sha256) = 32),
    contract_version TEXT NOT NULL CHECK (btrim(contract_version) <> ''),
    sanitized_headers JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(sanitized_headers) = 'object'),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (request_window_end IS NULL OR request_window_start IS NOT NULL),
    CHECK (request_window_end IS NULL OR request_window_end >= request_window_start)
);

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id UUID PRIMARY KEY,
    stage TEXT NOT NULL CHECK (stage IN ('ACQUIRE', 'TRANSFORM', 'PUBLISH', 'RECOVER')),
    source_system TEXT,
    source_account_id TEXT,
    stream_name TEXT,
    batch_id UUID,
    requested_window_start TIMESTAMPTZ,
    requested_window_end TIMESTAMPTZ,
    airflow_dag_id TEXT,
    airflow_run_id TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED')),
    error_code TEXT,
    error_message TEXT,
    log_reference TEXT,
    CHECK (requested_window_end IS NULL OR requested_window_start IS NOT NULL),
    CHECK (requested_window_end IS NULL OR requested_window_end >= requested_window_start),
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    CHECK ((status = 'RUNNING') = (finished_at IS NULL))
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname = 'raw_records_run_fk') THEN
        ALTER TABLE raw.raw_records ADD CONSTRAINT raw_records_run_fk
            FOREIGN KEY (run_id) REFERENCES ops.pipeline_runs(run_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ops.task_attempts (
    attempt_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    task_name TEXT NOT NULL CHECK (btrim(task_name) <> ''),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYABLE')),
    error_code TEXT,
    error_message TEXT,
    log_reference TEXT,
    UNIQUE (run_id, task_name, attempt_number),
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE IF NOT EXISTS ops.extraction_checkpoints (
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    completed_window_end TIMESTAMPTZ NOT NULL,
    successful_run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (source_system, source_account_id, stream_name)
);

CREATE TABLE IF NOT EXISTS ops.webhook_inbox (
    inbox_id UUID PRIMARY KEY,
    source_system TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    webhook_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    resource_url TEXT NOT NULL,
    first_raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    first_received_at TIMESTAMPTZ NOT NULL,
    fetch_state TEXT NOT NULL CHECK (fetch_state IN ('PENDING', 'LEASED', 'SUCCEEDED', 'FAILED', 'IGNORED')),
    UNIQUE (source_system, subscription_id, webhook_id)
);

CREATE TABLE IF NOT EXISTS ops.webhook_delivery_attempts (
    delivery_id UUID PRIMARY KEY,
    source_system TEXT NOT NULL,
    subscription_id TEXT,
    webhook_id TEXT,
    inbox_id UUID REFERENCES ops.webhook_inbox(inbox_id),
    raw_record_id UUID REFERENCES raw.raw_records(raw_record_id),
    received_at TIMESTAMPTZ NOT NULL,
    signature_valid BOOLEAN NOT NULL,
    freshness_valid BOOLEAN NOT NULL,
    accepted BOOLEAN NOT NULL,
    response_status INTEGER NOT NULL CHECK (response_status BETWEEN 100 AND 599),
    rejection_reason TEXT,
    CHECK (NOT accepted OR (signature_valid AND freshness_valid AND inbox_id IS NOT NULL AND raw_record_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ops.processing_work (
    work_id UUID PRIMARY KEY,
    dedupe_key TEXT NOT NULL UNIQUE,
    work_type TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    source_entity_id TEXT,
    trigger_raw_record_id UUID REFERENCES raw.raw_records(raw_record_id),
    inbox_id UUID REFERENCES ops.webhook_inbox(inbox_id),
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'LEASED', 'SUCCEEDED', 'FAILED', 'DEAD_LETTER')),
    cycle_attempts INTEGER NOT NULL DEFAULT 0 CHECK (cycle_attempts BETWEEN 0 AND 5),
    next_attempt_at TIMESTAMPTZ,
    lease_until TIMESTAMPTZ,
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK ((state = 'LEASED') = (lease_until IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ops.transform_batches (
    batch_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    mapping_version TEXT NOT NULL,
    transformation_version TEXT NOT NULL,
    manifest_frozen_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('FROZEN', 'BUILDING', 'TESTED', 'PUBLISHED', 'FAILED')),
    test_artifact_reference TEXT,
    published_at TIMESTAMPTZ,
    UNIQUE (run_id),
    CHECK ((status = 'PUBLISHED') = (published_at IS NOT NULL))
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname = 'pipeline_runs_batch_fk') THEN
        ALTER TABLE ops.pipeline_runs ADD CONSTRAINT pipeline_runs_batch_fk
            FOREIGN KEY (batch_id) REFERENCES ops.transform_batches(batch_id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ops.batch_inputs (
    batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    PRIMARY KEY (batch_id, raw_record_id)
);

CREATE TABLE IF NOT EXISTS ops.publication_state (
    publication_name TEXT PRIMARY KEY,
    batch_id UUID NOT NULL UNIQUE REFERENCES ops.transform_batches(batch_id),
    published_at TIMESTAMPTZ NOT NULL,
    transformation_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ops.data_exceptions (
    exception_id UUID PRIMARY KEY,
    exception_key TEXT NOT NULL UNIQUE,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'BLOCKING')),
    state TEXT NOT NULL CHECK (state IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    source_system TEXT,
    source_account_id TEXT,
    source_entity_id TEXT,
    run_id UUID REFERENCES ops.pipeline_runs(run_id),
    batch_id UUID REFERENCES ops.transform_batches(batch_id),
    raw_record_id UUID REFERENCES raw.raw_records(raw_record_id),
    processing_version TEXT NOT NULL,
    reason TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    CHECK (last_seen_at >= first_seen_at),
    CHECK ((state = 'RESOLVED') = (resolved_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS config.product_mapping (
    mapping_id UUID PRIMARY KEY,
    mapping_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    source_listing_id TEXT,
    source_variant_id TEXT,
    source_sku TEXT,
    canonical_variant_id TEXT NOT NULL,
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('CONFIRMED', 'REJECTED', 'PENDING')),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (source_listing_id IS NOT NULL OR source_variant_id IS NOT NULL OR source_sku IS NOT NULL),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS product_mapping_exact_active_uq
    ON config.product_mapping (
        source_system, source_account_id,
        COALESCE(source_listing_id, ''), COALESCE(source_variant_id, ''), COALESCE(source_sku, '')
    ) WHERE valid_to IS NULL AND mapping_status = 'CONFIRMED';
CREATE UNIQUE INDEX IF NOT EXISTS product_mapping_variant_active_uq
    ON config.product_mapping (
        source_system, source_account_id, COALESCE(source_listing_id, ''), source_variant_id
    ) WHERE valid_to IS NULL AND mapping_status = 'CONFIRMED' AND source_variant_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS product_mapping_listing_active_uq
    ON config.product_mapping (source_system, source_account_id, source_listing_id)
    WHERE valid_to IS NULL AND mapping_status = 'CONFIRMED'
        AND source_listing_id IS NOT NULL AND source_variant_id IS NULL;

CREATE TABLE IF NOT EXISTS core.order_snapshot_history (
    snapshot_id UUID PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    source_order_id TEXT NOT NULL,
    source_created_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ NOT NULL,
    first_observed_at TIMESTAMPTZ NOT NULL,
    content_fingerprint BYTEA NOT NULL CHECK (octet_length(content_fingerprint) = 32),
    source_payment_status TEXT,
    source_fulfillment_status TEXT,
    source_cancellation_status TEXT,
    payment_state TEXT NOT NULL,
    fulfillment_state TEXT NOT NULL,
    cancellation_state TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    items_gross_amount NUMERIC(20,6),
    discount_amount NUMERIC(20,6),
    shipping_amount NUMERIC(20,6),
    tax_amount NUMERIC(20,6),
    source_order_total_amount NUMERIC(20,6),
    mapping_version TEXT NOT NULL,
    transformation_version TEXT NOT NULL,
    batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    UNIQUE (source_system, source_account_id, source_order_id, source_updated_at, content_fingerprint),
    CHECK (source_updated_at >= source_created_at),
    CHECK (first_observed_at >= source_created_at)
);

CREATE TABLE IF NOT EXISTS core.order_line_snapshot_history (
    snapshot_id UUID NOT NULL REFERENCES core.order_snapshot_history(snapshot_id),
    source_line_id TEXT NOT NULL,
    source_listing_id TEXT,
    source_variant_id TEXT,
    source_sku TEXT,
    source_title TEXT,
    canonical_variant_id TEXT,
    mapping_status TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_gross_amount NUMERIC(20,6),
    line_gross_amount NUMERIC(20,6),
    line_discount_amount NUMERIC(20,6),
    line_tax_amount NUMERIC(20,6),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    fulfillment_evidence JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(fulfillment_evidence) = 'object'),
    PRIMARY KEY (snapshot_id, source_line_id)
);

CREATE TABLE IF NOT EXISTS core.snapshot_evidence (
    snapshot_id UUID NOT NULL REFERENCES core.order_snapshot_history(snapshot_id),
    raw_record_id UUID NOT NULL REFERENCES raw.raw_records(raw_record_id),
    evidence_role TEXT NOT NULL,
    resource_fingerprint BYTEA NOT NULL CHECK (octet_length(resource_fingerprint) = 32),
    resource_observed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (snapshot_id, raw_record_id, evidence_role)
);

CREATE TABLE IF NOT EXISTS core.orders_current (
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    source_order_id TEXT NOT NULL,
    snapshot_id UUID NOT NULL UNIQUE REFERENCES core.order_snapshot_history(snapshot_id),
    source_created_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ NOT NULL,
    source_snapshot_observed_at TIMESTAMPTZ NOT NULL,
    payment_state TEXT NOT NULL,
    fulfillment_state TEXT NOT NULL,
    cancellation_state TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    items_gross_amount NUMERIC(20,6),
    source_order_total_amount NUMERIC(20,6),
    published_batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (source_system, source_account_id, source_order_id)
);

CREATE TABLE IF NOT EXISTS core.order_lines_current (
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    source_order_id TEXT NOT NULL,
    source_line_id TEXT NOT NULL,
    snapshot_id UUID NOT NULL REFERENCES core.order_snapshot_history(snapshot_id),
    source_listing_id TEXT,
    source_variant_id TEXT,
    source_sku TEXT,
    source_title TEXT,
    canonical_variant_id TEXT,
    mapping_status TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_gross_amount NUMERIC(20,6),
    line_gross_amount NUMERIC(20,6),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    published_batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (source_system, source_account_id, source_order_id, source_line_id),
    FOREIGN KEY (source_system, source_account_id, source_order_id)
        REFERENCES core.orders_current(source_system, source_account_id, source_order_id)
);

CREATE TABLE IF NOT EXISTS mart.order_activity_daily (
    activity_date DATE NOT NULL,
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    order_count BIGINT NOT NULL CHECK (order_count >= 0),
    source_order_total_amount NUMERIC(20,6),
    published_batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (activity_date, source_system, source_account_id, currency)
);

CREATE TABLE IF NOT EXISTS mart.product_activity_daily (
    activity_date DATE NOT NULL,
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    product_bucket_key TEXT NOT NULL,
    canonical_variant_id TEXT,
    mapping_status TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    line_count BIGINT NOT NULL CHECK (line_count >= 0),
    ordered_units BIGINT NOT NULL CHECK (ordered_units >= 0),
    merchandise_amount NUMERIC(20,6),
    published_batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (activity_date, source_system, source_account_id, product_bucket_key, mapping_status, currency),
    CHECK (product_bucket_key = COALESCE(canonical_variant_id, '__UNMAPPED__'))
);

CREATE TABLE IF NOT EXISTS mart.order_status_current (
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    payment_state TEXT NOT NULL,
    fulfillment_state TEXT NOT NULL,
    cancellation_state TEXT NOT NULL,
    order_count BIGINT NOT NULL CHECK (order_count >= 0),
    published_batch_id UUID NOT NULL REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (source_system, source_account_id, payment_state, fulfillment_state, cancellation_state)
);

CREATE TABLE IF NOT EXISTS mart.source_health (
    source_system TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    completed_window_end TIMESTAMPTZ,
    last_successful_acquisition_at TIMESTAMPTZ,
    last_published_at TIMESTAMPTZ,
    pending_work_count BIGINT NOT NULL CHECK (pending_work_count >= 0),
    failed_work_count BIGINT NOT NULL CHECK (failed_work_count >= 0),
    open_blocking_exception_count BIGINT NOT NULL CHECK (open_blocking_exception_count >= 0),
    coverage_state TEXT NOT NULL CHECK (coverage_state IN ('COMPLETE', 'INCOMPLETE', 'UNKNOWN', 'UNAVAILABLE')),
    published_batch_id UUID REFERENCES ops.transform_batches(batch_id),
    PRIMARY KEY (source_system, source_account_id, stream_name)
);

CREATE OR REPLACE VIEW report.publication_state AS SELECT * FROM ops.publication_state;
CREATE OR REPLACE VIEW report.orders_current AS SELECT * FROM core.orders_current;
CREATE OR REPLACE VIEW report.order_lines_current AS SELECT * FROM core.order_lines_current;
CREATE OR REPLACE VIEW report.order_activity_daily AS SELECT * FROM mart.order_activity_daily;
CREATE OR REPLACE VIEW report.product_activity_daily AS SELECT * FROM mart.product_activity_daily;
CREATE OR REPLACE VIEW report.order_status_current AS SELECT * FROM mart.order_status_current;
CREATE OR REPLACE VIEW report.source_health AS SELECT * FROM mart.source_health;

INSERT INTO public.schema_migrations (migration_name)
VALUES ('platform/001_foundation.sql') ON CONFLICT DO NOTHING;
COMMIT;
