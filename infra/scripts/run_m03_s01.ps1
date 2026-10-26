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
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path

function Invoke-M03Service {
    param([string]$Service, [string[]]$Arguments)
    & docker compose --env-file $composeEnv --file $compose --profile m03 run --rm $Service @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Service failed with exit $LASTEXITCODE" }
}

& docker compose --env-file $composeEnv --file $compose --profile m03 build dbt-transform platform-publisher
if ($LASTEXITCODE -ne 0) { throw "M03 image build failed" }
Invoke-M03Service dbt-transform @("dbt", "--version")

$batchId = [guid]::NewGuid().ToString()
$transformRunId = [guid]::NewGuid().ToString()
$publishRunId = [guid]::NewGuid().ToString()
$vars = "{batch_id: '$batchId', mapping_version: 's01-v1', transformation_version: 'm03-v1', inject_test_failure: false}"

Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "freeze", "--batch-id", $batchId, "--run-id", $transformRunId, "--mapping-version", "s01-v1", "--transformation-version", "m03-v1")
Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "building", "--batch-id", $batchId)
& docker compose --env-file $composeEnv --file $compose --profile m03 run --rm dbt-transform `
    dbt build --profiles-dir /app/infra/dbt --project-dir /app/transformations --target-path "target/$batchId" --vars $vars
if ($LASTEXITCODE -ne 0) {
    Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "failed", "--batch-id", $batchId)
    throw "Required dbt build failed"
}
Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "tested", "--batch-id", $batchId, "--artifact", "target/$batchId/run_results.json")
& docker compose --env-file $composeEnv --file $compose --profile m03 run --rm `
    --volume "${root}/tests:/tests:ro" --volume "${root}/fixtures/s01:/fixtures/s01:ro" `
    dbt-transform python /tests/test_m03_fingerprint.py
if ($LASTEXITCODE -ne 0) { throw "M03 fingerprint parity failed" }
Invoke-M03Service platform-publisher @("python", "-m", "transformation.publish", "--batch-id", $batchId, "--run-id", $publishRunId)

$failedBatchId = [guid]::NewGuid().ToString()
$failedRunId = [guid]::NewGuid().ToString()
$failedVars = "{batch_id: '$failedBatchId', mapping_version: 's01-v1', transformation_version: 'm03-v1', inject_test_failure: true}"
Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "freeze", "--batch-id", $failedBatchId, "--run-id", $failedRunId, "--mapping-version", "s01-v1", "--transformation-version", "m03-v1")
Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "building", "--batch-id", $failedBatchId)
& docker compose --env-file $composeEnv --file $compose --profile m03 run --rm dbt-transform `
    dbt build --profiles-dir /app/infra/dbt --project-dir /app/transformations --target-path "target/$failedBatchId" --vars $failedVars
if ($LASTEXITCODE -eq 0) { throw "Injected dbt test failure unexpectedly passed" }
Invoke-M03Service dbt-transform @("python", "-m", "transformation.batch", "failed", "--batch-id", $failedBatchId, "--artifact", "target/$failedBatchId/run_results.json", "--require-injected-failure")
& docker compose --env-file $composeEnv --file $compose --profile m03 run --rm platform-publisher `
    python -m transformation.publish --batch-id $failedBatchId --run-id ([guid]::NewGuid().ToString())
if ($LASTEXITCODE -eq 0) { throw "Publisher accepted a failed batch" }

Get-Content (Join-Path $root "tests\m03_acceptance.sql") -Raw | `
    docker compose --env-file $composeEnv --file $compose exec -T postgres `
    psql --set ON_ERROR_STOP=1 --set "published_batch_id=$batchId" `
         --set "failed_batch_id=$failedBatchId" --username postgres --dbname data_platform
if ($LASTEXITCODE -ne 0) { throw "M03 acceptance SQL failed" }

Get-Content (Join-Path $root "tests\m03_report.sql") -Raw | `
    docker compose --env-file $composeEnv --file $compose exec -T postgres sh -c `
    'PGPASSWORD="$PLATFORM_REPORT_PASSWORD" psql --set ON_ERROR_STOP=1 --host 127.0.0.1 --username platform_report --dbname data_platform'
if ($LASTEXITCODE -ne 0) { throw "M03 report-role SQL failed" }

Write-Output "M03 published_batch_id=$batchId failed_batch_id=$failedBatchId PASS"
