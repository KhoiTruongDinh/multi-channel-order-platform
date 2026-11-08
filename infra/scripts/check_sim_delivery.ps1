$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$runId = [guid]::NewGuid().ToString('N').Substring(0,12)
$network = "sim-delivery-$runId"
$pgName = "sim-delivery-pg-$runId"
$cliName = "sim-delivery-cli-$runId"
$cliImage = 'multi-channel-order-platform-airflow'
$pgImage = 'postgres:16.15-bookworm'
function Docker-Check {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "SIM check Docker command failed ($($args[0]))" }
}
# Unique disposable resources only. No host ports, owner .env, scheduler or volumes.
# Trust is restricted to this private test network, removed after the check.
$created = $false
$report = @{status='FAIL'; scope='SIM only, not M08D acceptance'; started_at=[DateTime]::UtcNow.ToString('o'); run_id=$runId}
$report.hashes = @{}
foreach ($file in @('migrations/marketplace_sim/004_delivery_schedule.sql','simulator/delivery_sender.py',
    'simulator/live_worker.py','tools/s02_data/config.py','tools/s02_data/load.py','tools/s02_data/delivery.py',
    'tests/sim_delivery_probe.py','tools/s02_data/inspect_delivery.sql')) {
    $report.hashes[$file] = (Get-FileHash -LiteralPath (Join-Path $repo $file) -Algorithm SHA256).Hash.ToLowerInvariant()
}
try {
    Docker-Check image inspect --format '{{.Id}}' $cliImage
    Docker-Check image inspect --format '{{.Id}}' $pgImage
    Docker-Check network create --internal --label "sim-delivery-test=$runId" $network
    $created = $true
    Docker-Check run --detach --rm --name $pgName --network $network --network-alias sim-delivery-pg `
        --label "sim-delivery-test=$runId" --memory 192m --cpus 0.5 `
        --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=marketplace_sim `
        $pgImage -c shared_buffers=16MB -c max_connections=15
    $ready = $false
    for ($i=0; $i -lt 30; $i++) {
        & docker exec $pgName pg_isready --username postgres --dbname marketplace_sim 2>$null
        if ($LASTEXITCODE -eq 0) { $ready=$true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Disposable PostgreSQL did not become ready' }
    $cliArgs = @('run','--rm','--name',$cliName,'--network',$network,'--label',"sim-delivery-test=$runId",
        '--label','com.docker.compose.project=sim-delivery-tests','--label','com.docker.compose.service=cli',
        '--memory','256m','--cpus','0.5','--env','PYTHONPATH=/repo')
    foreach ($folder in @('tools','tests','test_support','simulator','fixtures','migrations')) {
        $source = Join-Path $repo $folder
        $cliArgs += @('--volume',"${source}:/repo/${folder}:ro")
    }
    $cliArgs += @('--entrypoint','/opt/airflow/project-venv/bin/python',$cliImage,'/repo/tests/sim_delivery_probe.py')
    $probeOutput = Docker-Check @cliArgs
    $report.probe = ($probeOutput -join "`n") | ConvertFrom-Json
    if ($report.probe.status -ne 'PASS') { throw 'SIM probe did not pass' }
    Write-Output $probeOutput
    $report.status = 'PASS'
} finally {
    $report.cleanup = 'FAIL'
    try {
        # Each exact random name belongs to this invocation; never target owner resources.
        foreach ($name in @($cliName,$pgName)) {
            $found = & docker ps -aq --filter "name=^/${name}$" --filter "label=sim-delivery-test=$runId"
            if ($LASTEXITCODE -ne 0) { throw 'Cannot verify disposable cleanup target' }
            if ($found) { Docker-Check stop --timeout 10 $name }
        }
        if ($created) { Docker-Check network rm $network }
        $report.cleanup = 'PASS'
    } finally {
        if ($report.cleanup -ne 'PASS') { $report.status='FAIL' }
        $report.finished_at = [DateTime]::UtcNow.ToString('o')
        $runtimeDir = Join-Path $repo 'runtime'
        if (-not (Test-Path -LiteralPath $runtimeDir)) { New-Item -ItemType Directory -Path $runtimeDir | Out-Null }
        $reportPath = Join-Path $runtimeDir "sim-delivery-$runId.json"
        $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
        Write-Output "SIM evidence: $reportPath"
    }
}
