param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000/api/v1",
    [switch]$BootStack,
    [int]$WebPort = 0,
    [switch]$SkipSyntheticHarness,
    [switch]$SkipApiEval,
    [switch]$KeepStack
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Push-Location $repoRoot

try {
    if ($BootStack) {
        Write-Step "Booting local compose stack"
        & (Join-Path $PSScriptRoot "compose-smoke.ps1") -Boot -WebPort $WebPort
    }

    if (-not $SkipSyntheticHarness) {
        Write-Step "Checking synthetic corpus and deterministic scorer"
        & (Join-Path $PSScriptRoot "eval-corpus-smoke.ps1")
        & (Join-Path $PSScriptRoot "eval-scorer-smoke.ps1")
    }

    Write-Step "Running real upload-to-runtime API smoke"
    & (Join-Path $PSScriptRoot "real-ingestion-smoke.ps1") -ApiBaseUrl $ApiBaseUrl

    if (-not $SkipApiEval) {
        Write-Step "Running full API-backed synthetic eval"
        python eval/harness/run_api_synthetic_eval.py --api-base-url $ApiBaseUrl
    }

    Write-Step "API-backed eval runner smoke passed"
}
finally {
    if ($BootStack -and -not $KeepStack) {
        Write-Step "Stopping local compose stack"
        docker compose -f deploy/compose/docker-compose.dev.yaml down | Out-Null
    }
    Pop-Location
}
