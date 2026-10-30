param(
    [string]$EnvFile
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $PSScriptRoot "..\..\.env"
}
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Compose environment file not found: $EnvFile"
}

$compose = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\compose.yaml")).Path
$composeEnv = (Resolve-Path -LiteralPath $EnvFile).Path
foreach ($database in @("website_source", "marketplace_sim", "data_platform", "airflow_meta")) {
    docker compose --env-file $composeEnv --file $compose exec -T postgres sh -c `
        "psql --set ON_ERROR_STOP=1 --username `"`$POSTGRES_USER`" --dbname '$database' --file /migrations/bootstrap/002_database_baseline.sql"
    if ($LASTEXITCODE -ne 0) { throw "Baseline failed for: $database" }
}
$websiteMigration = "/migrations/website_source/001_schema.sql"
docker compose --env-file $composeEnv --file $compose exec -T postgres sh -c `
    "psql --set ON_ERROR_STOP=1 --username `"`$POSTGRES_USER`" --dbname website_source --file '$websiteMigration'"
if ($LASTEXITCODE -ne 0) { throw "Migration failed: $websiteMigration" }
foreach ($file in @(
    "/migrations/platform/001_foundation.sql",
    "/migrations/platform/002_access.sql",
    "/migrations/platform/003_s01_mapping.sql",
    "/migrations/platform/004_polling.sql",
    "/migrations/platform/005_etsy_work.sql",
    "/migrations/platform/006_report_health.sql",
    "/migrations/platform/007_report_order_detail.sql",
    "/migrations/platform/008_report_queries_telemetry.sql"
)) {
    docker compose --env-file $composeEnv --file $compose exec -T postgres sh -c `
        "psql --set ON_ERROR_STOP=1 --username `"`$POSTGRES_USER`" --dbname data_platform --file '$file'"
    if ($LASTEXITCODE -ne 0) { throw "Migration failed: $file" }
}
# End of migration runner.
