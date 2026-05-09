$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $repoRoot

Write-Step "Running deterministic synthetic corpus scorer"
python eval/harness/run_synthetic_eval.py | Out-String | Write-Host

Write-Step "Running scorer unit tests"
python -m unittest discover eval/harness/tests

Write-Step "Eval scorer smoke passed"

