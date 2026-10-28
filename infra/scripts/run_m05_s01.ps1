param([string]$EnvFile)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($EnvFile)) { $EnvFile = Join-Path $PSScriptRoot '..\..\.env' }
$composeEnv = (Resolve-Path -LiteralPath $EnvFile).Path
$compose = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\compose.yaml')).Path
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$execution = 'm05_' + [guid]::NewGuid().ToString('N')

function DC {
    & docker compose --env-file $composeEnv --file $compose @args
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed: $args" }
}
function Probe([string]$Action) {
    $result = Get-Content (Join-Path $root 'tests\m05_probe.py') -Raw | `
        docker compose --env-file $composeEnv --file $compose run --rm -T --no-deps `
        --entrypoint python m05-checks - $Action --execution-id $execution
    if ($LASTEXITCODE -ne 0) { throw "M05 probe failed: $Action" }
    return ($result | Select-Object -Last 1)
}
function Control([hashtable]$Config) {
    # Use the published control binding, including an owner override from Compose.
    $binding = DC port ebay-sim 8081
    Invoke-RestMethod -Method Post -Uri "http://$binding/state" -ContentType 'application/json' `
        -Body ($Config | ConvertTo-Json -Compress) | Out-Null
}
function Collect([string]$Name, [string]$Start, [string]$End, [bool]$ExpectFailure = $false, [bool]$Interrupt = $false) {
    $command = @('run','--rm','-T','ebay-collector','--execution-id',"$execution-$Name",'--window-start',"2026-10-17T${Start}:00Z",'--window-end',"2026-10-17T${End}:00Z",'--observed-at',"2026-10-17T${End}:00Z")
    if ($Interrupt) { $command += '--fail-after-page' }
    & docker compose --env-file $composeEnv --file $compose @command
    if (($LASTEXITCODE -ne 0) -ne $ExpectFailure) { throw "Unexpected collector outcome: $Name exit=$LASTEXITCODE" }
}
function Release([bool]$InjectFailure = $false) {
    $batch = [guid]::NewGuid().ToString()
    DC run --rm -T dbt-transform python -m transformation.batch freeze --source ebay_sim `
        --batch-id $batch --run-id ([guid]::NewGuid().ToString()) --mapping-version s01-v1 --transformation-version m05-v1
    DC run --rm -T dbt-transform python -m transformation.batch building --batch-id $batch
    $variables = "{batch_id: '$batch', mapping_version: s01-v1, transformation_version: m05-v1, release_source: ebay_sim, inject_test_failure: $($InjectFailure.ToString().ToLower())}"
    & docker compose --env-file $composeEnv --file $compose run --rm -T dbt-transform dbt build `
        --profiles-dir /app/infra/dbt --project-dir /app/transformations --target-path "target/$batch" --vars $variables
    if ($InjectFailure) {
        if ($LASTEXITCODE -eq 0) { throw 'Injected dbt failure did not fail' }
        DC run --rm -T dbt-transform python -m transformation.batch failed --batch-id $batch `
            --artifact "/app/transformations/target/$batch/run_results.json" --require-injected-failure
        & docker compose --env-file $composeEnv --file $compose run --rm -T platform-publisher python -m transformation.publish `
            --source ebay_sim --batch-id $batch --run-id ([guid]::NewGuid().ToString())
        if ($LASTEXITCODE -eq 0) { throw 'Failed batch was published' }
    } else {
        if ($LASTEXITCODE -ne 0) { throw "dbt build failed batch=$batch; inspect artifacts and fail the active batch before replay" }
        DC run --rm -T dbt-transform python -m transformation.batch tested --batch-id $batch --artifact "/app/transformations/target/$batch/run_results.json"
        & docker compose --env-file $composeEnv --file $compose run --rm -T platform-publisher python -m transformation.publish `
            --source internal_web --batch-id $batch --run-id ([guid]::NewGuid().ToString())
        if ($LASTEXITCODE -eq 0) { throw 'Publisher accepted the wrong source for this batch' }
        DC run --rm -T platform-publisher python -m transformation.publish --source ebay_sim --batch-id $batch --run-id ([guid]::NewGuid().ToString())
    }
}

DC config --quiet
DC --profile m05 build ebay-sim ebay-collector dbt-transform platform-publisher m05-checks
DC --profile m05 up --detach --wait --wait-timeout 120 postgres ebay-sim
DC run --rm -T --no-deps --volume "${root}:/repo:ro" --entrypoint python ebay-collector /repo/tests/test_m05_http.py
$websiteBefore = Probe preflight
Control @{state='0902'}
Collect first '09:00' '09:03'
$checkpoint = Probe checkpoint
Control @{state='0912'; repeat_page=$true; fail_offset=1; error_status=500; errors_left=5}
Collect badpage '09:01' '09:13' $true
if ((Probe checkpoint) -ne $checkpoint) { throw 'Failed page advanced checkpoint' }
Control @{state='0912'}
Collect interrupted '09:01' '09:13' $true $true
if ((Probe checkpoint) -ne $checkpoint) { throw 'Interrupted acquisition advanced checkpoint' }
Control @{state='0912'; repeat_page=$true; bad_next=$true}
Collect badlink '09:01' '09:13' $true
if ((Probe checkpoint) -ne $checkpoint) { throw 'Untrusted next advanced checkpoint' }
Control @{state='0912'; repeat_page=$true; fail_offset=1; error_status=429; errors_left=1}
Collect paged '09:01' '09:13'
Control @{state='0912'}
Collect replay '09:01' '09:13'
Control @{state='0902'}
Collect older '09:00' '09:03'
Control @{state='0912'}
Collect empty '09:14' '09:15'
Release
Probe check
Probe audit
if ((Probe website) -ne $websiteBefore) { throw 'eBay publication changed website data' }
$goodPublication = Probe publication
$fixtures = (Resolve-Path (Join-Path $root 'fixtures\s01')).Path
$tests = (Resolve-Path (Join-Path $root 'tests')).Path
DC run --rm -T --volume "${fixtures}:/fixtures/s01:ro" --volume "${tests}:/tests:ro" dbt-transform python /tests/test_m05_fingerprint.py
Release $true
if ((Probe publication) -ne $goodPublication) { throw 'Failed batch changed publication' }
Probe check
if ((Probe website) -ne $websiteBefore) { throw 'Failed release changed website data' }
Write-Output "M05 PASS execution=$execution publication=$goodPublication"
