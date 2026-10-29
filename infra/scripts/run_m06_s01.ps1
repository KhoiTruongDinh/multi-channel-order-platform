param([string]$EnvFile)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $EnvFile) { $EnvFile=Join-Path $root '.env' }
$composeEnv=(Resolve-Path $EnvFile).Path
$compose=(Resolve-Path (Join-Path $PSScriptRoot '..\compose.yaml')).Path
$fixtures=(Resolve-Path (Join-Path $root 'fixtures\s01')).Path
$execution='m06_'+[guid]::NewGuid().ToString('N')
function DC { & docker compose --env-file $composeEnv --file $compose @args; if ($LASTEXITCODE -ne 0) { throw "Compose failed: $args" } }
function Probe([string]$Action) {
    $output=Get-Content (Join-Path $root 'tests\m06_probe.py') -Raw | docker compose --env-file $composeEnv --file $compose exec -T airflow /opt/airflow/project-venv/bin/python - $Action
    if ($LASTEXITCODE -ne 0) { throw "M06 probe failed: $Action" }
    return ($output | Select-Object -Last 1)
}
function Deliver([string]$Id,[string]$MessageId) {
    $headers=Get-Content (Join-Path $fixtures "webhooks\$Id.headers.json") -Raw | ConvertFrom-Json
    if (-not $MessageId) { $MessageId=$headers.'webhook-id' }
    DC run --rm -T --no-deps --volume "${fixtures}:/fixtures/s01:ro" etsy-receiver python -m simulator.etsy_sender `
        --body-file "/fixtures/s01/webhooks/$Id.body.json" --message-id $MessageId
}
function Release([bool]$Fail=$false) {
    $batch=[guid]::NewGuid().ToString()
    DC run --rm -T dbt-transform python -m transformation.batch freeze --source etsy_sim --batch-id $batch `
        --run-id ([guid]::NewGuid().ToString()) --mapping-version s01-v1 --transformation-version m06-v1
    DC run --rm -T dbt-transform python -m transformation.batch building --batch-id $batch
    $vars="{batch_id: '$batch', mapping_version: s01-v1, transformation_version: m06-v1, release_source: etsy_sim, inject_test_failure: $($Fail.ToString().ToLower())}"
    & docker compose --env-file $composeEnv --file $compose run --rm -T dbt-transform dbt build --profiles-dir /app/infra/dbt `
        --project-dir /app/transformations --target-path "target/$batch" --vars $vars
    if ($Fail) {
        if ($LASTEXITCODE -eq 0) { throw 'Expected injected dbt failure' }
        DC run --rm -T dbt-transform python -m transformation.batch failed --batch-id $batch `
            --artifact "/app/transformations/target/$batch/run_results.json" --require-injected-failure
        & docker compose --env-file $composeEnv --file $compose run --rm -T platform-publisher python -m transformation.publish `
            --source etsy_sim --batch-id $batch --run-id ([guid]::NewGuid().ToString())
        if ($LASTEXITCODE -eq 0) { throw 'Failed Etsy batch was published' }
    } else {
        if ($LASTEXITCODE -ne 0) { throw "dbt failed batch=$batch; inspect/fail this active batch before replay" }
        DC run --rm -T dbt-transform python -m transformation.batch tested --batch-id $batch --artifact "/app/transformations/target/$batch/run_results.json"
        DC run --rm -T platform-publisher python -m transformation.publish --source etsy_sim --batch-id $batch --run-id ([guid]::NewGuid().ToString())
    }
}
DC config --quiet
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'migrate.ps1') -EnvFile $composeEnv
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
DC --profile m04 --profile m06 build airflow etsy-sim etsy-receiver dbt-transform platform-publisher
DC --profile m04 --profile m06 up --detach --wait --wait-timeout 300 airflow etsy-sim etsy-receiver
# Normal polling must be paused and no manual batch may be active before this runner.
Probe preflight
$signature=Probe signature
$before=[int](Probe deliveries)
Deliver D1
DC restart etsy-receiver
DC --profile m06 up --detach --wait --wait-timeout 120 etsy-receiver
DC exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy drain --execution-id "$execution-paid" --observed-at 2026-10-17T09:06:00Z
Deliver D2
DC exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy drain --execution-id "$execution-shipped" --observed-at 2026-10-17T09:07:00Z
Deliver D3
if ([int](Probe deliveries) -ne ($before+3)) { throw 'Missing delivery audit' }
# Separate message scope: shipped first, then delayed paid; one transient receipt error.
Deliver D2 "$execution-reordered-shipped"
DC exec -T etsy-receiver python -c "import urllib.request,json; urllib.request.urlopen(urllib.request.Request('http://etsy-sim:8081/control',data=json.dumps(dict(state='0905',errors_left=1,error_status=429)).encode())).read()"
& docker compose --env-file $composeEnv --file $compose exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy drain --execution-id "$execution-reordered-fault" --observed-at 2026-10-17T09:07:00Z
if ($LASTEXITCODE -eq 0) { throw 'Expected one transient receipt failure' }
Start-Sleep -Seconds 3
DC exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy drain --execution-id "$execution-reordered-shipped" --observed-at 2026-10-17T09:07:00Z
Deliver D1 "$execution-reordered-paid"
DC exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy drain --execution-id "$execution-reordered-paid" --observed-at 2026-10-17T09:06:00Z
Release
Probe check
if ((Probe signature) -ne $signature) { throw 'Etsy release changed website/eBay' }
$goodPublication=Probe publication
Release $true
Probe check
if ((Probe publication) -ne $goodPublication) { throw 'Failed release changed Etsy publication pointer' }
if ((Probe signature) -ne $signature) { throw 'Failed Etsy release changed website/eBay' }
Write-Output "M06 S01 PASS execution=$execution"
