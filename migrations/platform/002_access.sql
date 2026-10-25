\set ON_ERROR_STOP on
BEGIN;

REVOKE ALL ON SCHEMA raw, ops, config, core, mart, report, build FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA raw, ops, config, core, mart, report FROM PUBLIC;

GRANT USAGE ON SCHEMA raw, ops TO platform_ingest;
GRANT SELECT, INSERT ON raw.raw_records TO platform_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO platform_ingest;
GRANT INSERT, UPDATE ON ops.pipeline_runs, ops.task_attempts, ops.extraction_checkpoints,
    ops.processing_work, ops.webhook_inbox, ops.webhook_delivery_attempts, ops.data_exceptions
    TO platform_ingest;

GRANT USAGE ON SCHEMA raw, ops, config, core, mart TO platform_transform;
GRANT USAGE, CREATE ON SCHEMA build TO platform_transform;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, ops, config TO platform_transform;
GRANT INSERT, UPDATE ON ops.pipeline_runs, ops.transform_batches, ops.data_exceptions TO platform_transform;
GRANT INSERT, DELETE ON ops.batch_inputs TO platform_transform;

GRANT USAGE ON SCHEMA ops, core, mart, report TO platform_publisher;
GRANT USAGE ON SCHEMA build TO platform_publisher;
GRANT SELECT ON ALL TABLES IN SCHEMA build TO platform_publisher;
GRANT SELECT, INSERT, UPDATE ON ops.transform_batches, ops.publication_state, ops.pipeline_runs TO platform_publisher;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core, mart TO platform_publisher;

GRANT USAGE ON SCHEMA report TO platform_report;
GRANT SELECT ON ALL TABLES IN SCHEMA report TO platform_report;

ALTER DEFAULT PRIVILEGES FOR ROLE platform_owner IN SCHEMA raw, ops, config, core, mart, report, build
    REVOKE ALL ON TABLES FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE platform_transform IN SCHEMA build
    GRANT SELECT ON TABLES TO platform_publisher;

INSERT INTO public.schema_migrations (migration_name)
VALUES ('platform/002_access.sql') ON CONFLICT DO NOTHING;
COMMIT;
-- End of access migration.
