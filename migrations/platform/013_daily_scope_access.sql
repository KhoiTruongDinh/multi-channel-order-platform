\set ON_ERROR_STOP on
BEGIN;
-- A bootstrap's dbt-owned scope includes old mart dates, even emptied buckets.
GRANT SELECT ON mart.order_activity_daily,mart.product_activity_daily TO platform_transform;
INSERT INTO public.schema_migrations(migration_name)
VALUES('platform/013_daily_scope_access.sql') ON CONFLICT DO NOTHING;
COMMIT;
