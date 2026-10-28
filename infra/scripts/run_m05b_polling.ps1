param([string]$EnvFile, [int]$IntervalSeconds=30)
$ErrorActionPreference='Stop'
if ($IntervalSeconds -lt 10) { throw 'Interval must be at least 10 seconds' }
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $EnvFile) { $EnvFile=Join-Path $root '.env' }
$composeEnv=(Resolve-Path $EnvFile).Path
$compose=(Resolve-Path (Join-Path $PSScriptRoot '..\compose.yaml')).Path
$execution='m05b_'+[guid]::NewGuid().ToString('N')
$since=(Get-Date).ToUniversalTime().ToString('o')
function DC { & docker compose --env-file $composeEnv --file $compose @args; if ($LASTEXITCODE -ne 0) { throw "Compose failed: $args" } }
function Probe([string]$Action,[string]$Id='unused',[string[]]$Extra=@()) {
    $result=Get-Content (Join-Path $root 'tests\m05b_probe.py') -Raw | `
        docker compose --env-file $composeEnv --file $compose exec -T airflow `
        /opt/airflow/project-venv/bin/python - $Action --execution-id $Id --since $since @Extra
    if ($LASTEXITCODE -ne 0) { throw "M05B probe failed: $Action $Id" }
    return ($result | Select-Object -Last 1)
}
function Wait-State([string]$Action,[string]$Id,[string]$Expected) {
    $deadline=(Get-Date).AddMinutes(20)
    do {
        $state=Probe $Action $Id
        if ($state -eq $Expected) { return }
        if ($state -eq 'failed' -and $Expected -ne 'failed') { throw "Unexpected failed state: $Action $Id" }
        Write-Host "M05B $Action=$state; waiting for $Expected"
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Timed out: $Action $Id"
}
$names=@('WEBSITE_POLL_INTERVAL_SECONDS','EBAY_POLL_INTERVAL_SECONDS','WEBSITE_POLL_INITIAL_START','EBAY_POLL_INITIAL_START')
$prior=@{}
foreach ($name in $names) { $prior[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
$bootstrap=(Get-Date).ToUniversalTime().AddMinutes(-2).ToString('o')
try {
    foreach ($name in @('WEBSITE_POLL_INTERVAL_SECONDS','EBAY_POLL_INTERVAL_SECONDS')) { [Environment]::SetEnvironmentVariable($name,"$IntervalSeconds",'Process') }
    foreach ($name in @('WEBSITE_POLL_INITIAL_START','EBAY_POLL_INITIAL_START')) { [Environment]::SetEnvironmentVariable($name,$bootstrap,'Process') }
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'migrate.ps1') -EnvFile $composeEnv
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
    DC --profile m04 --profile m05 build airflow
    DC --profile m04 --profile m05 up --detach --wait --wait-timeout 300 airflow ebay-sim
    $importErrors=DC exec -T airflow airflow dags list-import-errors --output json
    # Windows PowerShell 5.1 can wrap an empty JSON array as one pipeline object.
    $parsedErrors=($importErrors -join "`n") | ConvertFrom-Json
    $actualErrors=@($parsedErrors | Where-Object { $null -ne $_ })
    if ($actualErrors.Count -gt 0) { throw "Airflow import errors: $importErrors" }
    # Build CLI baselines for both sources with the same runtime validation/version.
    foreach ($source in @('internal_web','ebay_sim')) {
        $end=(Get-Date).ToUniversalTime().AddSeconds(-1).ToString('o')
        DC exec -T airflow /opt/airflow/project-venv/bin/python -m orchestration.polling --source $source `
            --execution-id "$execution-cli-$source" --window-end $end --initial-start $bootstrap
    }
    $signature=Probe signature
    $checkpoint=Probe checkpoint
    $websiteCheckpoint=Probe checkpoint unused @('--source','internal_web')
    $since=(Get-Date).ToUniversalTime().ToString('o')
    DC exec -T airflow airflow dags unpause website_polling
    DC exec -T airflow airflow dags unpause ebay_polling
    Wait-State scheduled unused success
    DC exec -T airflow airflow dags pause website_polling
    DC exec -T airflow airflow dags pause ebay_polling
    Wait-State idle unused idle
    if ((Probe signature) -ne $signature) { throw 'Scheduled and CLI business results differ' }
    if ((Probe checkpoint) -ne $checkpoint -or (Probe checkpoint unused @('--source','internal_web')) -ne $websiteCheckpoint) { throw 'Polling changed historical S01 checkpoint' }
    DC exec -T airflow airflow dags unpause ebay_polling_replay
    $retry="$execution-retry"
    Probe trigger $retry
    # Wait for the second deliberate fault, after its raw manifest is committed.
    $deadline=(Get-Date).AddMinutes(10)
    do {
        $manifest=Probe manifest $retry
        $state=Probe retry $retry
        if ($manifest -ne 'waiting' -and $state -eq 'up_for_retry') { break }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    if ($manifest -eq 'waiting' -or $state -ne 'up_for_retry') { throw 'Did not observe durable freeze retry' }
    DC restart airflow
    DC --profile m04 up --detach --wait --wait-timeout 300 airflow
    Wait-State state $retry success
    if ((Probe manifest $retry) -ne $manifest) { throw 'Restart changed manifest' }
    Probe check_retry $retry
    Probe artifact $retry
    $goodPublication=Probe publication
    $failed="$execution-failed"
    Probe trigger $failed @('--test-failure')
    Wait-State state $failed failed
    Probe check_failed $failed
    Probe clear $failed
    Wait-State cleared $failed failed
    Probe budget $failed
    if ((Probe publication) -ne $goodPublication -or (Probe signature) -ne $signature) { throw 'Failed/cleared cycle changed good release' }
    Write-Output "M05B PASS execution=$execution publication=$goodPublication"
} finally {
    foreach ($dag in @('website_polling','ebay_polling','ebay_polling_replay')) {
        & docker compose --env-file $composeEnv --file $compose exec -T airflow airflow dags pause $dag
    }
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$prior[$name],'Process') }
    # Leave schedules paused and restore the owner's .env/default intervals.
    & docker compose --env-file $composeEnv --file $compose --profile m04 up --detach --wait --wait-timeout 300 airflow
}
