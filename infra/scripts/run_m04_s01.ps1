param([string]$EnvFile)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($EnvFile)) { $EnvFile = Join-Path $PSScriptRoot '..\..\.env' }
$composeEnv = (Resolve-Path -LiteralPath $EnvFile).Path
$compose = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\compose.yaml')).Path
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path

function Invoke-Probe {
    param([string]$Action, [string]$ExecutionId = 'unused', [string[]]$ProbeArguments = @())
    $probeOutput = Get-Content (Join-Path $root 'tests\m04_probe.py') -Raw | `
        docker compose --env-file $composeEnv --file $compose exec -T airflow `
        /opt/airflow/project-venv/bin/python - $Action --execution-id $ExecutionId @ProbeArguments
    if ($LASTEXITCODE -ne 0) { throw "M04 probe failed: $Action $ExecutionId" }
    return ($probeOutput | Select-Object -Last 1)
}

function Wait-M04State {
    param([string]$Action, [string]$ExecutionId, [string]$Expected)
    $deadline = (Get-Date).AddMinutes(10)
    do {
        $actual = Invoke-Probe $Action $ExecutionId
        if ($actual -eq $Expected) { return }
        if ($actual -eq 'failed' -or ($actual -eq 'success' -and $Expected -ne 'success')) {
            throw "Unexpected Airflow state $actual while waiting for $Action=$Expected"
        }
        Write-Host "M04 $ExecutionId $Action=$actual; waiting for $Expected"
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Action=$Expected"
}

docker compose --env-file $composeEnv --file $compose --profile m04 build airflow
if ($LASTEXITCODE -ne 0) { throw 'Airflow build failed' }
docker compose --env-file $composeEnv --file $compose --profile m04 up --detach --wait --wait-timeout 300 airflow
if ($LASTEXITCODE -ne 0) { throw 'Airflow did not become healthy' }
Invoke-Probe preflight
docker compose --env-file $composeEnv --file $compose exec -T airflow airflow dags list-import-errors --output json
if ($LASTEXITCODE -ne 0) { throw 'Airflow DAG import inspection failed' }

$cliId = 'm04_cli_' + [guid]::NewGuid().ToString('N')
docker compose --env-file $composeEnv --file $compose exec -T airflow `
    /opt/airflow/project-venv/bin/python -m orchestration.website_workflow --stage all `
    --execution-id $cliId --window-start 2026-10-17T09:09:00Z --window-end 2026-10-17T09:15:00Z `
    --observed-at 2026-10-17T09:15:00Z
if ($LASTEXITCODE -ne 0) { throw 'Reusable CLI baseline failed' }
$baseline = Invoke-Probe signature
$checkpointBefore = Invoke-Probe checkpoint

$retryId = 'm04_retry_' + [guid]::NewGuid().ToString('N')
Invoke-Probe trigger $retryId @('--faults')
Wait-M04State collect_retry $retryId up_for_retry
if ((Invoke-Probe checkpoint) -ne $checkpointBefore) { throw 'Failed collection falsely advanced checkpoint' }
Wait-M04State freeze_retry $retryId up_for_retry
$manifestBefore = Invoke-Probe manifest $retryId
docker compose --env-file $composeEnv --file $compose restart airflow
if ($LASTEXITCODE -ne 0) { throw 'Airflow restart failed' }
docker compose --env-file $composeEnv --file $compose --profile m04 up --detach --wait --wait-timeout 300 airflow
if ($LASTEXITCODE -ne 0) { throw 'Airflow restart health failed' }
Wait-M04State status $retryId success
if ((Invoke-Probe manifest $retryId) -ne $manifestBefore) { throw 'Restart changed frozen raw manifest' }
Invoke-Probe check_success $retryId
if ((Invoke-Probe signature) -ne $baseline) { throw 'DAG and CLI published business results differ' }
$goodPublication = Invoke-Probe publication

$failedId = 'm04_failed_' + [guid]::NewGuid().ToString('N')
Invoke-Probe trigger $failedId @('--test-failure')
Wait-M04State status $failedId failed
Invoke-Probe check_failure $failedId
Invoke-Probe budget $failedId
Invoke-Probe clear $failedId
Wait-M04State cleared_status $failedId failed
Invoke-Probe budget $failedId
if ((Invoke-Probe signature) -ne $baseline) { throw 'Failed DAG changed published business results' }
if ((Invoke-Probe publication) -ne $goodPublication) { throw 'Failed DAG changed publication pointer' }
Write-Output "M04 PASS cli=$cliId retry_restart=$retryId exhausted=$failedId publication=$goodPublication"
