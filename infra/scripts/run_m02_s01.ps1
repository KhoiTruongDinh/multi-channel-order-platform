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
$executionId = [guid]::NewGuid().ToString()

function Invoke-ComposeRun {
    param([string]$Service, [string[]]$Arguments)
    & docker compose --env-file $composeEnv --file $compose --profile m02 run --rm $Service @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Service failed with exit $LASTEXITCODE" }
}

& docker compose --env-file $composeEnv --file $compose --profile m02 build website-simulator website-collector
if ($LASTEXITCODE -ne 0) { throw "M02 image build failed" }

Invoke-ComposeRun website-simulator @("0901")
& docker compose --env-file $composeEnv --file $compose --profile m02 run --rm website-collector `
    --window-start 2026-10-17T08:58:00Z --window-end 2026-10-17T09:03:00Z `
    --observed-at 2026-10-17T09:03:00Z --execution-id $executionId `
    --run-kind failure-test --fail-after-raw
if ($LASTEXITCODE -eq 0) { throw "Fault injection unexpectedly succeeded" }

Invoke-ComposeRun website-collector @(
    "--window-start", "2026-10-17T08:58:00Z", "--window-end", "2026-10-17T09:03:00Z",
    "--observed-at", "2026-10-17T09:03:00Z", "--execution-id", $executionId, "--run-kind", "scheduled"
)
Invoke-ComposeRun website-simulator @("0910")
Invoke-ComposeRun website-collector @(
    "--window-start", "2026-10-17T09:01:00Z", "--window-end", "2026-10-17T09:11:00Z",
    "--observed-at", "2026-10-17T09:11:00Z", "--execution-id", $executionId, "--run-kind", "scheduled"
)
Invoke-ComposeRun website-simulator @("0914")
Invoke-ComposeRun website-collector @(
    "--window-start", "2026-10-17T09:09:00Z", "--window-end", "2026-10-17T09:15:00Z",
    "--observed-at", "2026-10-17T09:15:00Z", "--execution-id", $executionId, "--run-kind", "scheduled"
)
Invoke-ComposeRun website-collector @(
    "--window-start", "2026-10-17T09:09:00Z", "--window-end", "2026-10-17T09:15:00Z",
    "--observed-at", "2026-10-17T09:15:00Z", "--execution-id", $executionId, "--run-kind", "replay"
)

Get-Content (Join-Path $root "tests\m02_source_boundary.sql") -Raw | `
    docker compose --env-file $composeEnv --file $compose exec -T postgres `
    psql --set ON_ERROR_STOP=1 --username postgres --dbname website_source
if ($LASTEXITCODE -ne 0) { throw "M02 source boundary check failed" }

Get-Content (Join-Path $root "tests\m02_acceptance.sql") -Raw | `
    docker compose --env-file $composeEnv --file $compose exec -T postgres `
    psql --set ON_ERROR_STOP=1 --set "execution_id=$executionId" --username postgres --dbname data_platform
if ($LASTEXITCODE -ne 0) { throw "M02 acceptance SQL failed" }

& docker compose --env-file $composeEnv --file $compose --profile m02 run --rm --entrypoint sh website-collector `
    -c "test ! -e /fixtures && test ! -e /app/fixtures"
if ($LASTEXITCODE -ne 0) { throw "Collector image contains forbidden fixture paths" }

Write-Output "M02 execution_id=$executionId PASS"
