#!/usr/bin/env bash
set -Eeuo pipefail

psql=(psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres)

"${psql[@]}" \
  --set website_reader_password="$WEBSITE_READER_PASSWORD" \
  --set website_writer_password="$WEBSITE_WRITER_PASSWORD" \
  --set marketplace_writer_password="$MARKETPLACE_WRITER_PASSWORD" \
  --set platform_ingest_password="$PLATFORM_INGEST_PASSWORD" \
  --set platform_transform_password="$PLATFORM_TRANSFORM_PASSWORD" \
  --set platform_publisher_password="$PLATFORM_PUBLISHER_PASSWORD" \
  --set platform_report_password="$PLATFORM_REPORT_PASSWORD" \
  --set airflow_app_password="$AIRFLOW_APP_PASSWORD" \
  --file /migrations/bootstrap/001_cluster.sql

for database in website_source marketplace_sim data_platform airflow_meta; do
  "${psql[@]}" --dbname "$database" --file /migrations/bootstrap/002_database_baseline.sql
done

"${psql[@]}" --dbname data_platform --file /migrations/platform/001_foundation.sql
"${psql[@]}" --dbname data_platform --file /migrations/platform/002_access.sql
"${psql[@]}" --dbname data_platform --file /migrations/platform/003_s01_mapping.sql
