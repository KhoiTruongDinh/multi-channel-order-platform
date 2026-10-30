param([string]$EnvFile)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $EnvFile) { $EnvFile=Join-Path $root '.env' }
$composeEnv=(Resolve-Path $EnvFile).Path
$compose=(Resolve-Path (Join-Path $PSScriptRoot '..\compose.yaml')).Path
function DC { & docker compose --env-file $composeEnv --file $compose @args; if ($LASTEXITCODE -ne 0) { throw "Compose failed: $args" } }
DC config --quiet
DC up --detach --wait postgres
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'migrate.ps1') -EnvFile $composeEnv
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
DC --profile m07 build report scheduler-observer
DC --profile m07 up --detach --wait --wait-timeout 180 report scheduler-observer
DC exec -T scheduler-observer /opt/airflow/project-venv/bin/python -m orchestration.scheduler_probe --once
Get-Content (Join-Path $root 'tests\m07_acceptance.sql') -Raw | docker compose --env-file $composeEnv --file $compose exec -T postgres psql --set ON_ERROR_STOP=1 --username postgres --dbname data_platform
if ($LASTEXITCODE -ne 0) { throw 'M07 SQL acceptance failed' }
DC exec -T report python -m pip check
DC --profile m07 run --rm -T --no-deps --env PYTHONDONTWRITEBYTECODE=1 --volume "${root}:/repo:ro" report python /repo/tests/test_m07_operations.py
DC exec -T --env PYTHONDONTWRITEBYTECODE=1 report python -c "import os; forbidden=('PLATFORM_INGEST_PASSWORD','PLATFORM_TRANSFORM_PASSWORD','PLATFORM_PUBLISHER_PASSWORD','ETSY_SIGNING_SECRET','ETSY_SIM_TOKEN','AIRFLOW_APP_PASSWORD'); assert not any(k in os.environ for k in forbidden); assert not os.path.exists('/var/run/docker.sock'); assert not os.path.exists('/fixtures'); print('M07 runtime boundaries PASS')"
DC --profile m07 run --rm -T --no-deps --env PYTHONDONTWRITEBYTECODE=1 --volume "${root}:/repo:ro" report python /repo/tests/test_m07_report.py
Write-Output 'M07 report PASS (SQL, role, metrics, filters, UI and runtime boundaries)'
