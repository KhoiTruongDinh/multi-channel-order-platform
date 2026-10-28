\set ON_ERROR_STOP on

DO $$
DECLARE
    missing_databases TEXT;
    missing_relations TEXT;
BEGIN
    SELECT string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_databases
    FROM (VALUES ('website_source'), ('marketplace_sim'), ('data_platform'), ('airflow_meta')) required(name)
    WHERE NOT EXISTS (SELECT FROM pg_database d WHERE d.datname = required.name);
    IF missing_databases IS NOT NULL THEN
        RAISE EXCEPTION 'missing databases: %', missing_databases;
    END IF;

    SELECT string_agg(required.name, ', ' ORDER BY required.name)
    INTO missing_relations
    FROM (VALUES
        ('raw.raw_records'), ('ops.pipeline_runs'), ('ops.task_attempts'),
        ('ops.extraction_checkpoints'), ('ops.processing_work'),
        ('ops.webhook_inbox'), ('ops.webhook_delivery_attempts'),
        ('ops.transform_batches'), ('ops.batch_inputs'),
        ('ops.publication_state'), ('ops.data_exceptions'),
        ('config.product_mapping'), ('core.order_snapshot_history'),
        ('core.order_line_snapshot_history'), ('core.snapshot_evidence'),
        ('core.orders_current'), ('core.order_lines_current'),
        ('mart.order_activity_daily'), ('mart.product_activity_daily'),
        ('mart.order_status_current'), ('mart.source_health'),
        ('report.publication_state'), ('report.orders_current'),
        ('report.order_lines_current'), ('report.order_activity_daily'),
        ('report.product_activity_daily'), ('report.order_status_current'),
        ('report.source_health')
    ) required(name)
    WHERE to_regclass(required.name) IS NULL;
    IF missing_relations IS NOT NULL THEN
        RAISE EXCEPTION 'missing relations: %', missing_relations;
    END IF;

    IF (SELECT count(*) FROM public.schema_migrations WHERE migration_name IN
        ('platform/001_foundation.sql','platform/002_access.sql','platform/003_s01_mapping.sql')) <> 3 THEN
        RAISE EXCEPTION 'missing original platform migration records';
    END IF;
    IF (SELECT count(*) FROM config.product_mapping WHERE mapping_version = 's01-v1') <> 4 THEN
        RAISE EXCEPTION 'expected four independent S01 mapping rows';
    END IF;
    IF EXISTS (SELECT FROM pg_constraint WHERE NOT convalidated) THEN
        RAISE EXCEPTION 'unvalidated database constraint found';
    END IF;

    IF NOT has_table_privilege('platform_report', 'report.orders_current', 'SELECT')
       OR has_table_privilege('platform_report', 'raw.raw_records', 'SELECT') THEN
        RAISE EXCEPTION 'report role boundary failed';
    END IF;
    IF NOT has_table_privilege('platform_ingest', 'raw.raw_records', 'INSERT')
       OR has_table_privilege('platform_ingest', 'raw.raw_records', 'UPDATE') THEN
        RAISE EXCEPTION 'append-only raw role boundary failed';
    END IF;
    IF NOT has_schema_privilege('platform_transform', 'build', 'CREATE')
       OR has_table_privilege('platform_transform', 'core.orders_current', 'INSERT') THEN
        RAISE EXCEPTION 'transform role boundary failed';
    END IF;
    IF NOT has_table_privilege('platform_publisher', 'core.orders_current', 'INSERT') THEN
        RAISE EXCEPTION 'publisher role boundary failed';
    END IF;
    IF has_database_privilege('marketplace_writer', 'data_platform', 'CONNECT') THEN
        RAISE EXCEPTION 'marketplace database isolation failed';
    END IF;
END $$;

SELECT 'M01 database contract PASS' AS result;
