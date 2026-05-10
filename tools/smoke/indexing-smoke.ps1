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

Write-Host "[smoke] Running indexing parser smoke against $ApiBaseUrl"

$headers = @{
    "X-Agent-Forge-User" = "smoke-indexer"
    "X-Agent-Forge-Department" = "Operations"
    "X-Agent-Forge-Clearance" = "internal"
}

$sourceBody = @{
    name = "Indexing Smoke"
    description = "Synthetic TXT/MD parser smoke"
    owner_department = "Operations"
} | ConvertTo-Json

$source = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/sources" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $sourceBody

$documentBody = @{
    knowledge_source_id = $source.id
    title = "Remote Work Policy"
    object_uri = "object://synthetic/smoke/remote-work.md"
    checksum = "sha256-smoke-remote-work"
    mime_type = "text/markdown"
    confidentiality_level = "internal"
    access_groups = @("all-employees")
    effective_date = "2026-05-10"
} | ConvertTo-Json

$document = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/documents" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $documentBody

$jobBody = @{
    source_text = "# Remote Work`n`nCompany-wide remote work rules.`n`n## Eligibility`n`nEmployees may request remote work after manager approval."
    chunking = @{
        strategy = "line-heading"
        chunk_size = 900
        chunk_overlap = 0
    }
} | ConvertTo-Json -Depth 6

$job = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/documents/$($document.id)/index-jobs" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $jobBody

Assert-Smoke ($job.status -eq "succeeded") "Expected index job to succeed"
Assert-Smoke ($job.chunk_count -eq 2) "Expected two parser chunks"

$chunks = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/knowledge/documents/$($document.id)/chunks" `
    -Headers $headers

Assert-Smoke ($chunks.Count -eq 2) "Expected two chunk metadata rows"
Assert-Smoke (-not ($chunks[0].PSObject.Properties.Name -contains "content")) "Chunk API exposed raw content"
Assert-Smoke ($chunks[1].section_path[1] -eq "Eligibility") "Expected markdown heading path"

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

Assert-Smoke ($preview.hits.Count -eq 1) "Expected one retrieval hit"
Assert-Smoke ($preview.hits[0].chunk_id -eq $chunks[1].id) "Expected retrieval preview to return the matching chunk"

$noAclBody = @{
    knowledge_source_id = $source.id
    title = "No ACL Draft"
    object_uri = "object://synthetic/smoke/no-acl.md"
    checksum = "sha256-smoke-no-acl"
    mime_type = "text/markdown"
    confidentiality_level = "internal"
    access_groups = @()
} | ConvertTo-Json

$noAclDocument = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/documents" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $noAclBody

$failedJobBody = @{
    source_text = "# Draft`n`nThis document must not become searchable."
} | ConvertTo-Json

$failedJob = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/knowledge/documents/$($noAclDocument.id)/index-jobs" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $failedJobBody

Assert-Smoke ($failedJob.status -eq "failed") "Expected no-ACL document indexing to fail closed"
Assert-Smoke ($failedJob.error_code -eq "DOCUMENT_NOT_INDEXABLE") "Expected DOCUMENT_NOT_INDEXABLE"

Write-Host "[smoke] Indexing parser smoke passed"
