\set ON_ERROR_STOP on
DO $$
BEGIN
    IF NOT has_table_privilege('website_reader', 'public.orders', 'SELECT') THEN
        RAISE EXCEPTION 'website_reader lacks source SELECT';
    END IF;
    IF has_table_privilege('website_reader', 'public.orders', 'INSERT,UPDATE,DELETE') THEN
        RAISE EXCEPTION 'website_reader has source write access';
    END IF;
    IF has_database_privilege('platform_ingest', current_database(), 'CONNECT') THEN
        RAISE EXCEPTION 'platform_ingest unexpectedly connects to website source';
    END IF;
END $$;
SELECT 'M02 source role boundary PASS' AS result;
