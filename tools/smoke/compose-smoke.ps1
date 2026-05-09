param(
    [switch]$Boot,
    [string]$ComposeFile = "deploy/compose/docker-compose.dev.yaml",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

function Assert-Contains {
    param(
        [string]$Text,
        [string]$Needle,
        [string]$Label
    )

    if (-not $Text.Contains($Needle)) {
        throw "Missing ${Label}: $Needle"
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $repoRoot

Write-Step "Rendering Docker Compose config"
$config = docker compose -f $ComposeFile config
$configText = $config -join "`n"

@("postgres", "minio", "qdrant", "api", "web") | ForEach-Object {
    Assert-Contains -Text $configText -Needle "$($_):" -Label "service"
}

@('"5432"', '"8000"', '"3000"', '"9000"', '"6333"') | ForEach-Object {
    Assert-Contains -Text $configText -Needle $_ -Label "published port"
}

Write-Step "Compose config smoke passed"

if (-not $Boot) {
    Write-Step "Skipping container boot. Pass -Boot to run the full stack smoke."
    exit 0
}

Write-Step "Starting local stack"
docker compose -f $ComposeFile up --build -d

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$healthzOk = $false
$readyzOk = $false

while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -TimeoutSec 3
        if ($health.status -eq "ok") {
            $healthzOk = $true
        }

        $ready = Invoke-RestMethod -Uri "http://localhost:8000/readyz" -TimeoutSec 3
        if ($ready.status -eq "ok") {
            $readyzOk = $true
        }

        if ($healthzOk -and $readyzOk) {
            break
        }
    }
    catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $healthzOk) {
    throw "API /healthz did not pass within $TimeoutSeconds seconds"
}

if (-not $readyzOk) {
    throw "API /readyz did not pass within $TimeoutSeconds seconds"
}

Write-Step "Full compose boot smoke passed"
