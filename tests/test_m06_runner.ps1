# Execute actual runner functions with Docker/probe/wait stubs; no infrastructure IO.
$ErrorActionPreference='Stop'
$runner=Join-Path $PSScriptRoot '..\infra\scripts\run_m06_scheduled.ps1'
$tokens=$null; $parseErrors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $runner),[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw 'Runner AST invalid' }
foreach ($name in @('Wait-Probe','Drain-Workflows')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    if (-not $node) { throw "Missing runner function $name" }
    Invoke-Expression $node.Extent.Text
}
$script:events=[System.Collections.Generic.List[string]]::new()
function DC { $script:events.Add("DC $args") }
function Reconcile-Terminal { $script:events.Add('reconcile terminal failed parents') }
function Scheduled-Probe([string]$Action) {
    $script:events.Add("probe $Action")
    if ($Action -eq 'drain_ready') { return 'ready' }
    if ($script:blocked) { return 'waiting' }
    return 'idle'
}
function Start-Sleep { }
$before=[Environment]::GetEnvironmentVariable('POLLING_DRAIN_MODE','Process')
try {
    $script:blocked=$false
    Drain-Workflows
    if ($env:POLLING_DRAIN_MODE -ne 'true') { throw 'Drain must set the maintenance environment' }
    if (-not $script:drained) { throw 'Successful drain must be remembered for safe cleanup' }
    $ready=$script:events.IndexOf('probe drain_ready')
    $idle=$script:events.IndexOf('probe idle')
    if ($ready -lt 0 -or $idle -le $ready) { throw 'Must await parsed timetable before idle' }
    foreach ($dag in @('etsy_inbox','etsy_recovery','etsy_replay','website_polling','ebay_polling')) {
        $unpause=$script:events.IndexOf("DC exec -T airflow airflow dags unpause $dag")
        $pause=$script:events.IndexOf("DC exec -T airflow airflow dags pause $dag")
        if ($unpause -le $ready -or $unpause -ge $idle -or $pause -le $idle) { throw "Unsafe drain order for $dag" }
    }
    Write-Output 'Drain order PASS (all five DAGs retry before pause)'
    # A blocked retry is not idle; timeout must be visible rather than accepted.
    $script:blocked=$true
    $caught=$false
    try { Wait-Probe idle idle 0 } catch {
        if ($_.Exception.Message -notlike 'Timed out: idle*') { throw }
        $caught=$true
    }
    if (-not $caught) { throw 'Blocked drain was accepted' }
    Write-Output 'Blocked retry timeout PASS'
    $script:blocked=$false
    Wait-Probe idle idle 0
    Write-Output 'Already idle PASS'
    $source=Get-Content -LiteralPath $runner -Raw
    if ($source.IndexOf('Write-Output $passMessage') -lt $source.IndexOf('} finally {')) {
        throw 'PASS must follow successful cleanup, not precede it'
    }
    Write-Output 'PASS-after-cleanup guard PASS'
} finally {
    [Environment]::SetEnvironmentVariable('POLLING_DRAIN_MODE',$before,'Process')
}
