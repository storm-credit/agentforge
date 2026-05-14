param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000/api/v1"
)

$ErrorActionPreference = "Stop"

function Assert-Smoke {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw "[smoke] $Message"
    }
}

function Url-Encode {
    param([string]$Value)
    return [System.Uri]::EscapeDataString($Value)
}

Write-Host "[smoke] Running real upload ingestion smoke against $ApiBaseUrl"

$headers = @{
    "X-Agent-Forge-User" = "smoke-uploader"
    "X-Agent-Forge-Department" = "Operations"
    "X-Agent-Forge-Clearance" = "internal"
}

$sourceBody = @{
    name = "Real Ingestion Smoke"
    description = "Upload-to-runtime smoke collection"
    owner_department = "Operations"
} | ConvertTo-Json

$source = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/sources" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $sourceBody

$fixturePath = Join-Path ([System.IO.Path]::GetTempPath()) "agentforge-real-ingestion-smoke.md"
Set-Content `
    -Path $fixturePath `
    -Encoding UTF8 `
    -Value "# Remote Work Upload`n`nCompany-wide remote work rules are stored through object storage.`n`n## Eligibility`n`nEmployees may request remote work after manager approval."

$uploadHeaders = $headers.Clone()
$uploadHeaders["X-Agent-Forge-Filename"] = "remote-work-upload.md"

$uploadUri = "$ApiBaseUrl/knowledge/documents/upload" +
    "?knowledge_source_id=$(Url-Encode $source.id)" +
    "&title=$(Url-Encode "Remote Work Upload")" +
    "&access_groups=$(Url-Encode "all-employees")" +
    "&effective_date=$(Url-Encode "2026-05-10")"

$document = Invoke-RestMethod `
    -Method Post `
    -Uri $uploadUri `
    -Headers $uploadHeaders `
    -ContentType "text/markdown" `
    -InFile $fixturePath

Assert-Smoke ($document.object_uri -like "object://*") "Expected uploaded object URI"
Assert-Smoke ($document.checksum -like "sha256-*") "Expected uploaded SHA-256 checksum"
Assert-Smoke ($document.access_groups[0] -eq "all-employees") "Expected uploaded ACL group"

$job = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/documents/$($document.id)/index-jobs" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body "{}"

Assert-Smoke ($job.status -eq "succeeded") "Expected storage-backed index job to succeed"
Assert-Smoke ($job.config.source -eq "object_store") "Expected index job to read object storage"
Assert-Smoke ($job.chunk_count -eq 2) "Expected two chunks from uploaded markdown"

$chunks = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/knowledge/documents/$($document.id)/chunks" `
    -Headers $headers

Assert-Smoke ($chunks.Count -eq 2) "Expected two chunk metadata rows"
Assert-Smoke ($chunks[1].citation_locator -like "*Eligibility*") "Expected heading citation locator"

$previewBody = @{
    query = "manager approval"
    knowledge_source_ids = @($source.id)
    top_k = 1
} | ConvertTo-Json

$preview = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/retrieval/preview" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $previewBody

Assert-Smoke ($preview.hits.Count -eq 1) "Expected retrieval preview hit"
Assert-Smoke ($preview.hits[0].chunk_id -eq $chunks[1].id) "Expected preview to use uploaded chunk"

$agentBody = @{
    name = "Real Ingestion Smoke Agent"
    purpose = "Answer uploaded smoke document questions with citations."
    owner_department = "Operations"
} | ConvertTo-Json

$agent = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/agents" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $agentBody

$versionBody = @{
    agent_id = $agent.id
    version = 1
    config = @{
        citation_required = $true
        knowledge_source_ids = @($source.id)
    }
} | ConvertTo-Json -Depth 6

$version = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/agents/versions" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $versionBody

$publishBody = @{ reason = "Real ingestion smoke publish" } | ConvertTo-Json

$published = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/agents/versions/$($version.id)/publish" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $publishBody

Assert-Smoke ($published.status -eq "published") "Expected smoke agent version to publish"

$runBody = @{
    agent_id = $agent.id
    input = @{
        message = "Who may request remote work after manager approval?"
    }
    knowledge_source_ids = @($source.id)
    top_k = 1
} | ConvertTo-Json -Depth 6

$run = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/runs" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $runBody

Assert-Smoke ($run.status -eq "succeeded") "Expected runtime run to succeed"
Assert-Smoke ($run.citations.Count -eq 1) "Expected runtime citation from uploaded document"
Assert-Smoke ($run.guardrail.citation_validation_pass -eq $true) "Expected citation validator pass"
Assert-Smoke ($run.input.model_routing_policy_ref -eq "packages/shared-contracts/model-routing-policy.v0.1.json") "Expected runtime input model routing policy ref"
Assert-Smoke ($run.guardrail.budget_class -eq "standard") "Expected runtime standard model budget"
Assert-Smoke ($run.guardrail.model_route_summary.answer_generator.tier -eq "standard-rag") "Expected answer generator route tier"

$steps = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/runs/$($run.id)/steps" `
    -Headers $headers

$hits = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/runs/$($run.id)/retrieval-hits" `
    -Headers $headers

Assert-Smoke ($steps.Count -eq 5) "Expected five runtime trace steps"
Assert-Smoke ($steps[2].output_summary.route_stage -eq "answer_generator") "Expected generator trace route stage"
Assert-Smoke ($hits.Count -eq 1) "Expected one stored retrieval hit"

Write-Host "[smoke] Real upload ingestion smoke passed"
