param(
    [switch]$Boot,
    [string]$ComposeFile = "deploy/compose/docker-compose.dev.yaml",
    [int]$TimeoutSeconds = 90,
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000,
    [int]$PostgresPort = 5432,
    [int]$MinioApiPort = 9000,
    [int]$MinioConsolePort = 9001,
    [int]$QdrantPort = 6333
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

function Resolve-Port {
    param([int]$RequestedPort)

    if ($RequestedPort -ne 0) {
        return $RequestedPort
    }

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        return $listener.LocalEndpoint.Port
    }
    finally {
        $listener.Stop()
    }
}

function Stop-ComposeStack {
    docker compose -f $ComposeFile down | Out-Null
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $repoRoot

$ApiPort = Resolve-Port -RequestedPort $ApiPort
$WebPort = Resolve-Port -RequestedPort $WebPort
$PostgresPort = Resolve-Port -RequestedPort $PostgresPort
$MinioApiPort = Resolve-Port -RequestedPort $MinioApiPort
$MinioConsolePort = Resolve-Port -RequestedPort $MinioConsolePort
$QdrantPort = Resolve-Port -RequestedPort $QdrantPort

$env:AGENT_FORGE_API_PORT = "$ApiPort"
$env:AGENT_FORGE_WEB_PORT = "$WebPort"
$env:AGENT_FORGE_POSTGRES_PORT = "$PostgresPort"
$env:AGENT_FORGE_MINIO_API_PORT = "$MinioApiPort"
$env:AGENT_FORGE_MINIO_CONSOLE_PORT = "$MinioConsolePort"
$env:AGENT_FORGE_QDRANT_PORT = "$QdrantPort"

Write-Step "Using ports api=$ApiPort web=$WebPort postgres=$PostgresPort minio=$MinioApiPort/$MinioConsolePort qdrant=$QdrantPort"
Write-Step "Rendering Docker Compose config"
$config = docker compose -f $ComposeFile config
$configText = $config -join "`n"

@("postgres", "minio", "qdrant", "api", "web") | ForEach-Object {
    Assert-Contains -Text $configText -Needle "$($_):" -Label "service"
}

@("""$PostgresPort""", """$ApiPort""", """$WebPort""", """$MinioApiPort""", """$MinioConsolePort""", """$QdrantPort""") | ForEach-Object {
    Assert-Contains -Text $configText -Needle $_ -Label "published port"
}

Write-Step "Compose config smoke passed"

if (-not $Boot) {
    Write-Step "Skipping container boot. Pass -Boot to run the full stack smoke."
    exit 0
}

Write-Step "Starting local stack"
docker compose -f $ComposeFile up --build -d
if ($LASTEXITCODE -ne 0) {
    Stop-ComposeStack
    throw "docker compose up failed with exit code $LASTEXITCODE"
}

$runningServices = @(docker compose -f $ComposeFile ps --services --status running)
@("postgres", "minio", "qdrant", "api", "web") | ForEach-Object {
    if ($runningServices -notcontains $_) {
        Stop-ComposeStack
        throw "Service is not running after compose up: $_"
    }
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$healthzOk = $false
$readyzOk = $false
$webOk = $false

while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:$ApiPort/healthz" -TimeoutSec 3
        if ($health.status -eq "ok") {
            $healthzOk = $true
        }

        $ready = Invoke-RestMethod -Uri "http://localhost:$ApiPort/readyz" -TimeoutSec 3
        if ($ready.status -eq "ok") {
            $readyzOk = $true
        }

        $web = Invoke-WebRequest -Uri "http://localhost:$WebPort" -UseBasicParsing -TimeoutSec 3
        if ($web.StatusCode -ge 200 -and $web.StatusCode -lt 500) {
            $webOk = $true
        }

        if ($healthzOk -and $readyzOk -and $webOk) {
            break
        }
    }
    catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $healthzOk) {
    Stop-ComposeStack
    throw "API /healthz did not pass within $TimeoutSeconds seconds"
}

if (-not $readyzOk) {
    Stop-ComposeStack
    throw "API /readyz did not pass within $TimeoutSeconds seconds"
}

if (-not $webOk) {
    Stop-ComposeStack
    throw "Web root did not respond within $TimeoutSeconds seconds"
}

Write-Step "Full compose boot smoke passed"
