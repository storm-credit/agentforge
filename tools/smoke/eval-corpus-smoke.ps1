param(
    [string]$CorpusPath = "eval/synthetic-corpus/cases-v0.1.json"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $repoRoot

Write-Step "Loading synthetic corpus"
$corpus = Get-Content -Raw $CorpusPath | ConvertFrom-Json

if ($corpus.schema_version -ne "agentforge.synthetic_corpus/v0.1") {
    throw "Unexpected schema version: $($corpus.schema_version)"
}

$documentsById = @{}
$corpus.documents | ForEach-Object {
    $documentsById[$_.document_id] = $_
}

if ($corpus.cases.Count -ne 30) {
    throw "Expected 30 cases, found $($corpus.cases.Count)"
}

$expectedSuiteCounts = @{
    "rag-core" = 8
    "citation" = 6
    "acl" = 8
    "refusal" = 5
    "safety" = 3
}

foreach ($suite in $expectedSuiteCounts.Keys) {
    $actual = @($corpus.cases | Where-Object { $_.suite -eq $suite }).Count
    if ($actual -ne $expectedSuiteCounts[$suite]) {
        throw "Suite $suite expected $($expectedSuiteCounts[$suite]) cases, found $actual"
    }
}

$caseIds = @{}
foreach ($case in $corpus.cases) {
    if ($caseIds.ContainsKey($case.case_id)) {
        throw "Duplicate case_id: $($case.case_id)"
    }
    $caseIds[$case.case_id] = $true

    foreach ($citation in $case.expected_citations) {
        if (-not $documentsById.ContainsKey($citation.document_id)) {
            throw "Unknown expected citation document $($citation.document_id) in $($case.case_id)"
        }
    }
}

Write-Step "Synthetic corpus smoke passed"

