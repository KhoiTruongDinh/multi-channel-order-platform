# Exercise the runner's actual JSON guard without starting Docker or a workflow.
$ErrorActionPreference='Stop'
$runner=Join-Path $PSScriptRoot '..\infra\scripts\run_m05b_polling.ps1'
$source=Get-Content -LiteralPath $runner -Raw
$guard=[regex]::Match($source,'(?s)    \$parsedErrors=.*?(?=    # Build CLI baselines)')
if (-not $guard.Success) { throw 'Runner import-error guard not found' }
$check=[scriptblock]::Create($guard.Value)

function Assert-Guard([string]$Name,[string[]]$Lines,[bool]$ShouldFail) {
    $failed=$false
    try {
        & { param($importErrors) & $check } $Lines
    } catch {
        $failed=$true
        if ($Name -ne 'invalid JSON' -and $_.Exception.Message -notlike 'Airflow import errors:*') {
            throw
        }
    }
    if ($failed -ne $ShouldFail) { throw "Unexpected guard outcome: $Name" }
    Write-Output "$Name PASS"
}

Assert-Guard 'empty array' @('[]') $false
Assert-Guard 'multiline empty array' @('[',']') $false
Assert-Guard 'one real error' @('[{"filename":"bad.py","stack_trace":"error"}]') $true
Assert-Guard 'multiple real errors' @('[','{"filename":"a.py"},','{"filename":"b.py"}',']') $true
Assert-Guard 'invalid JSON' @('not JSON') $true
Write-Output 'M05B PowerShell import-error guard PASS (5 cases)'
