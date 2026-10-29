param([string]$EnvFile,[switch]$DrainOnly)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $EnvFile) { $EnvFile=Join-Path $root '.env' }
$composeEnv=(Resolve-Path $EnvFile).Path
$compose=(Resolve-Path (Join-Path $PSScriptRoot '..\compose.yaml')).Path
$fixtures=(Resolve-Path (Join-Path $root 'fixtures\s01')).Path
$execution='m06_schedule_'+[guid]::NewGuid().ToString('N')
$since=(Get-Date).ToUniversalTime().ToString('o')
function DC { & docker compose --env-file $composeEnv --file $compose @args; if ($LASTEXITCODE -ne 0) { throw "Compose failed: $args" } }
function Probe([string]$Action,[string]$Id='unused',[string[]]$Extra=@()) {
    $output=Get-Content (Join-Path $root 'tests\m05b_probe.py') -Raw | docker compose --env-file $composeEnv --file $compose exec -T airflow /opt/airflow/project-venv/bin/python - $Action --source etsy_sim --execution-id $Id @Extra
    if ($LASTEXITCODE -ne 0) { throw "Etsy workflow probe failed: $Action $Id" }
    return ($output | Select-Object -Last 1)
}
function Scheduled-Probe([string]$Action) {
    $output=Get-Content (Join-Path $root 'tests\m06_probe.py') -Raw | docker compose --env-file $composeEnv --file $compose exec -T airflow /opt/airflow/project-venv/bin/python - $Action --since $since
    if ($LASTEXITCODE -ne 0) { throw "M06 probe failed: $Action" }
    return ($output | Select-Object -Last 1)
}
function Wait-State([string]$Action,[string]$Id,[string]$Expected) {
    $deadline=(Get-Date).AddMinutes(20)
    do {
        $state=Probe $Action $Id
        if ($state -eq $Expected) { return }
        if ($state -eq 'failed' -and $Expected -ne 'failed') { throw "Unexpected $Action failure: $Id" }
        Write-Host "M06 $Action=$state; waiting for $Expected"
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Timed out: $Action $Id"
}
function Reconcile-Terminal {
    Get-Content (Join-Path $root 'orchestration\draining.py') -Raw | docker compose --env-file $composeEnv --file $compose exec -T airflow /opt/airflow/project-venv/bin/python -
    if ($LASTEXITCODE -ne 0) { throw 'Failed to reconcile terminal Airflow workflow audit' }
}
function Wait-Probe([string]$Action,[string]$Expected,[int]$Minutes=20) {
    $deadline=(Get-Date).AddMinutes($Minutes)
    do {
        if ($Action -eq 'idle') {
            # DAG timeout can skip the watcher; close only terminal FAILED parents.
            Reconcile-Terminal
        }
        $state=Scheduled-Probe $Action
        if ($state -eq $Expected) { return }
        Write-Host "M06 $Action=$state; waiting for $Expected (DAG retries remain enabled)"
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Timed out: $Action; inspect running DAGs/task logs; no counters were reset"
}
function Drain-Workflows {
    $script:drained=$false
    # Pausing first strands up_for_retry tasks. Null timetables stop new intervals
    # while unpaused DAGs finish their already-created runs with original budgets.
    [Environment]::SetEnvironmentVariable('POLLING_DRAIN_MODE','true','Process')
    DC --profile m04 up --detach --wait --wait-timeout 300 airflow
    Wait-Probe drain_ready ready 5
    foreach ($dag in @('etsy_inbox','etsy_recovery','etsy_replay','website_polling','ebay_polling')) { DC exec -T airflow airflow dags unpause $dag }
    Wait-Probe idle idle
    foreach ($dag in @('etsy_inbox','etsy_recovery','etsy_replay','website_polling','ebay_polling')) { DC exec -T airflow airflow dags pause $dag }
    $script:drained=$true
}
$script:drained=$false
$passMessage=$null
$names=@('ETSY_INBOX_INTERVAL_SECONDS','ETSY_RECOVERY_INTERVAL_SECONDS','ETSY_RECOVERY_INITIAL_START','ETSY_RECOVERY_STREAM','POLLING_DRAIN_MODE')
$prior=@{}
foreach ($name in $names) { $prior[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
try {
    [Environment]::SetEnvironmentVariable('POLLING_DRAIN_MODE','true','Process')
    DC --profile m04 --profile m05 --profile m06 build airflow etsy-receiver
    DC --profile m04 --profile m05 --profile m06 up --detach --wait --wait-timeout 300 airflow ebay-sim etsy-sim etsy-receiver
    Write-Host 'M06 draining any unfinished prior runs before changing campaign configuration'
    Drain-Workflows
    if ($DrainOnly) {
        $passMessage='M06 drain PASS (existing runs terminal; no new scheduled campaign)'
        return
    }
    [Environment]::SetEnvironmentVariable('POLLING_DRAIN_MODE','false','Process')
    [Environment]::SetEnvironmentVariable('ETSY_INBOX_INTERVAL_SECONDS','30','Process')
    [Environment]::SetEnvironmentVariable('ETSY_RECOVERY_INTERVAL_SECONDS','30','Process')
    # Explicitly cover the historical receipt for the independent missed-notification scan.
    [Environment]::SetEnvironmentVariable('ETSY_RECOVERY_INITIAL_START','2026-10-17T09:00:00Z','Process')
    [Environment]::SetEnvironmentVariable('ETSY_RECOVERY_STREAM',('receipts_test_'+[guid]::NewGuid().ToString('N')),'Process')
    DC --profile m04 --profile m05 --profile m06 up --detach --wait --wait-timeout 300 airflow ebay-sim etsy-sim etsy-receiver
    Wait-Probe schedule_ready ready 5
    $errors=DC exec -T airflow airflow dags list-import-errors --output json
    $parsed=($errors -join "`n") | ConvertFrom-Json
    if (@($parsed | Where-Object { $null -ne $_ }).Count) { throw "DAG import errors: $errors" }
    $before=Scheduled-Probe signature
    $since=(Get-Date).ToUniversalTime().ToString('o')
    # One signed delivery; all subsequent processing must be scheduler-created.
    DC run --rm -T --no-deps --volume "${fixtures}:/fixtures/s01:ro" etsy-receiver python -m simulator.etsy_sender `
        --body-file /fixtures/s01/webhooks/D1.body.json --message-id "$execution-inbox"
    $script:drained=$false
    foreach ($dag in @('etsy_inbox','etsy_recovery','website_polling','ebay_polling')) { DC exec -T airflow airflow dags unpause $dag }
    $deadline=(Get-Date).AddMinutes(20)
    do {
        $state=Scheduled-Probe scheduled
        if ($state -eq 'success') { break }
        Write-Host 'M06 waiting for two real scheduled successes per Etsy DAG'
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    if ($state -ne 'success') { throw 'Scheduled acceptance timed out' }
    Write-Host 'M06 scheduled successes verified; draining remaining runs before replay tests'
    Drain-Workflows
    Scheduled-Probe check
    if ((Scheduled-Probe signature) -ne $before) { throw 'Etsy scheduling changed website/eBay facts' }
    $script:drained=$false
    DC exec -T airflow airflow dags unpause etsy_replay
    $retry="$execution-retry"
    Probe trigger $retry
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
    if ((Probe manifest $retry) -ne $manifest) { throw 'Manifest changed after restart' }
    Probe check_retry $retry
    $goodPublication=Probe publication
    $failed="$execution-failed"
    Probe trigger $failed @('--test-failure')
    Wait-State state $failed failed
    Probe check_failed $failed
    Probe clear $failed
    Wait-State cleared $failed failed
    Probe budget $failed
    if ((Probe publication) -ne $goodPublication) { throw 'Failed/cleared run changed good Etsy release' }
    Scheduled-Probe check
    $passMessage="M06 scheduled PASS execution=$execution since=$since publication=$goodPublication"
} catch {
    # Report the original failure before potentially slow cleanup/recreation.
    Write-Host "M06 scheduled FAILED: $($_.Exception.Message)" -ForegroundColor Red
    throw
} finally {
    $cleanupSafe=$false
    try {
        if (-not $script:drained) { Drain-Workflows }
        $cleanupSafe=$true
    } catch {
        Write-Warning "M06 cleanup incomplete: $($_.Exception.Message). Drain mode is retained; do not reset DB or mark runs successful. Rerun with -DrainOnly."
    }
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$prior[$name],'Process') }
    if ($cleanupSafe) {
        DC --profile m04 up --detach --wait --wait-timeout 300 airflow
        if ($passMessage) { Write-Output $passMessage }
    } else {
        throw 'M06 cleanup failed; campaign is not accepted; container retains drain configuration for recovery'
    }
}
