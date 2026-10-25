\set ON_ERROR_STOP on

SELECT 'CREATE ROLE website_owner NOLOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'website_owner') \gexec
SELECT 'CREATE ROLE marketplace_owner NOLOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'marketplace_owner') \gexec
SELECT 'CREATE ROLE platform_owner NOLOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'platform_owner') \gexec
SELECT 'CREATE ROLE airflow_owner NOLOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow_owner') \gexec

SELECT 'CREATE ROLE website_reader LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'website_reader') \gexec
SELECT 'CREATE ROLE website_writer LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'website_writer') \gexec
SELECT 'CREATE ROLE marketplace_writer LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'marketplace_writer') \gexec
SELECT 'CREATE ROLE platform_ingest LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'platform_ingest') \gexec
SELECT 'CREATE ROLE platform_transform LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'platform_transform') \gexec
SELECT 'CREATE ROLE platform_publisher LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'platform_publisher') \gexec
SELECT 'CREATE ROLE platform_report LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'platform_report') \gexec
SELECT 'CREATE ROLE airflow_app LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow_app') \gexec

ALTER ROLE website_reader PASSWORD :'website_reader_password';
ALTER ROLE website_writer PASSWORD :'website_writer_password';
ALTER ROLE marketplace_writer PASSWORD :'marketplace_writer_password';
ALTER ROLE platform_ingest PASSWORD :'platform_ingest_password';
ALTER ROLE platform_transform PASSWORD :'platform_transform_password';
ALTER ROLE platform_publisher PASSWORD :'platform_publisher_password';
ALTER ROLE platform_report PASSWORD :'platform_report_password';
ALTER ROLE airflow_app PASSWORD :'airflow_app_password';

GRANT website_owner TO CURRENT_USER;
GRANT marketplace_owner TO CURRENT_USER;
GRANT platform_owner TO CURRENT_USER;
GRANT airflow_owner TO CURRENT_USER;

SELECT 'CREATE DATABASE website_source OWNER website_owner'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'website_source') \gexec
SELECT 'CREATE DATABASE marketplace_sim OWNER marketplace_owner'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'marketplace_sim') \gexec
SELECT 'CREATE DATABASE data_platform OWNER platform_owner'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'data_platform') \gexec
SELECT 'CREATE DATABASE airflow_meta OWNER airflow_owner'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow_meta') \gexec

REVOKE CONNECT ON DATABASE website_source FROM PUBLIC;
REVOKE CONNECT ON DATABASE marketplace_sim FROM PUBLIC;
REVOKE CONNECT ON DATABASE data_platform FROM PUBLIC;
REVOKE CONNECT ON DATABASE airflow_meta FROM PUBLIC;
GRANT CONNECT ON DATABASE website_source TO website_reader;
GRANT CONNECT ON DATABASE website_source TO website_writer;
GRANT CONNECT ON DATABASE marketplace_sim TO marketplace_writer;
GRANT CONNECT ON DATABASE data_platform TO platform_ingest, platform_transform, platform_publisher, platform_report;
GRANT CONNECT ON DATABASE airflow_meta TO airflow_app;
GRANT website_owner TO website_writer;
GRANT marketplace_owner TO marketplace_writer;
ALTER DATABASE airflow_meta OWNER TO airflow_app;
