param([string]$Image = 'multi-channel-order-platform-airflow')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& docker image inspect --format '{{.Id}}' $Image
if ($LASTEXITCODE -ne 0) { throw 'Build the existing Airflow image first; this check does not start services.' }
$runtimePath = Join-Path $repoRoot 'runtime'
if (-not (Test-Path -LiteralPath $runtimePath)) {
    New-Item -ItemType Directory -Path $runtimePath | Out-Null
}
$dockerArgs = @('run', '--rm', '--network', 'none', '--memory', '256m', '--cpus', '0.5')
# No .env, Docker socket, warehouse network or extra scheduler in this container.
foreach ($relative in @('test_support', 'tests', 'tools', 'simulator', 'ingestion',
    'orchestration', 'transformation', 'transformations', 'fixtures', 'migrations', 'infra', '.env.example')) {
    $sourcePath = Join-Path $repoRoot $relative
    $dockerArgs += @('--volume', "${sourcePath}:/repo/${relative}:ro")
}
$dockerArgs += @('--volume', "${runtimePath}:/repo/runtime", '--env', 'PYTHONPATH=/repo',
    '--entrypoint', '/opt/airflow/project-venv/bin/python', $Image,
    '-m', 'test_support.m08c', 'offline')
& docker @dockerArgs
exit $LASTEXITCODE
