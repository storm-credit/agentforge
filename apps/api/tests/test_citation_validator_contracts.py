from app.domain.citations import validate_run_citations


def test_citation_validator_passes_complete_required_citation():
    result = validate_run_citations(
        [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "Remote Work Policy",
                "citation_locator": "Remote Work Policy / body / lines 1-2",
            }
        ],
        citation_required=True,
    )

    assert result.passed is True
    assert result.required is True
    assert result.citation_count == 1
    assert result.error_code is None


def test_citation_validator_fails_required_response_without_citations():
    result = validate_run_citations([], citation_required=True)

    assert result.passed is False
    assert result.error_code == "NO_CITATION"
    assert result.citation_count == 0


def test_citation_validator_fails_incomplete_required_citation_metadata():
    result = validate_run_citations(
        [
            {
                "document_id": "doc-1",
                "title": "Remote Work Policy",
                "citation_locator": "",
            }
        ],
        citation_required=True,
    )

    assert result.passed is False
    assert result.error_code == "BAD_CITATION"
    assert result.missing_fields == ("chunk_id", "citation_locator")


def test_citation_validator_allows_uncited_response_when_not_required():
    result = validate_run_citations([], citation_required=False)

    assert result.passed is True
    assert result.required is False
    assert result.citation_count == 0
