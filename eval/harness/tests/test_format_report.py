"""The ingestion-format section of a report, at the scorer level."""

import pathlib
import sys

HARNESS_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.ingest_formats import NO_DOCUMENT_FORMAT  # noqa: E402
from agentforge_eval.live_scorer import (  # noqa: E402
    FORMAT_COVERAGE_MARKDOWN_ONLY,
    FORMAT_COVERAGE_MIXED,
    FORMAT_COVERAGE_UNKNOWN,
    MARKDOWN_ONLY_QUALIFICATION,
    aggregate,
    citation_structure_by_format,
    score_case,
)

DOC_MAP = {"hr-leave": "real-hr-1"}


def _scores(*case_ids):
    case = {
        "case_id": "c", "expected_behavior": "answer", "expected_citation_doc": "hr-leave",
        "forbidden_doc": None, "must_not_include": [], "answer_points": ["15일"],
    }
    run = {
        "answer": "연 15일입니다.",
        "citations": [{"document_id": "real-hr-1"}],
        "hit_document_ids": ["real-hr-1"],
    }
    return [score_case({**case, "case_id": cid}, run, DOC_MAP) for cid in case_ids]


def test_a_run_that_declared_nothing_is_unknown_not_assumed_markdown():
    report = aggregate(_scores("a"))
    assert report["format_coverage"] == FORMAT_COVERAGE_UNKNOWN
    assert "NOT DECLARED" in report["format_qualification"]
    assert report["ingestion_formats"]["formats_measured"] == []


def test_markdown_only_run_carries_the_best_case_qualification():
    report = aggregate(
        _scores("a", "b"),
        case_formats={"a": "markdown", "b": "markdown"},
        document_formats={"d": "markdown"},
    )
    assert report["format_coverage"] == FORMAT_COVERAGE_MARKDOWN_ONLY
    assert report["format_qualification"] == MARKDOWN_ONLY_QUALIFICATION


def test_cases_about_no_document_do_not_count_as_an_ingestion_format():
    # A refuse case exercises no document, so it gets its own bucket -- but the run is still
    # a markdown-only measurement and "no_document" is not a format anyone ingested.
    report = aggregate(
        _scores("a", "r"),
        case_formats={"a": "markdown", "r": NO_DOCUMENT_FORMAT},
        document_formats={"d": "markdown"},
    )
    assert report["format_coverage"] == FORMAT_COVERAGE_MARKDOWN_ONLY
    assert report["ingestion_formats"]["formats_measured"] == ["markdown"]
    assert report["ingestion_formats"]["case_counts"] == {"markdown": 1, NO_DOCUMENT_FORMAT: 1}


def test_one_binary_document_is_enough_to_stop_a_run_being_markdown_only():
    report = aggregate(
        _scores("a"),
        case_formats={"a": "markdown"},
        document_formats={"d1": "markdown", "d2": "docx"},
    )
    assert report["format_coverage"] == FORMAT_COVERAGE_MIXED
    assert report["ingestion_formats"]["formats_measured"] == ["docx", "markdown"]


def test_per_format_metrics_slice_the_aligned_per_case_inputs():
    report = aggregate(
        _scores("a", "b"),
        latencies_ms=[100, 900],
        trace_complete=[True, False],
        grounding_scores=[0.9, None],
        grounding_min=0.5,
        case_formats={"a": "markdown", "b": "docx"},
    )
    by_format = report["ingestion_formats"]["by_format"]
    assert by_format["markdown"]["latency_p50_ms"] == 100.0
    assert by_format["markdown"]["trace_completeness_pct"] == 100.0
    assert by_format["markdown"]["lexical_overlap_pct"] == 100.0
    assert by_format["docx"]["latency_p50_ms"] == 900.0
    assert by_format["docx"]["trace_completeness_pct"] == 0.0
    # The docx case reported no grounding score, so its share is unmeasured, not 0 or 100.
    assert by_format["docx"]["lexical_overlap_pct"] is None


def test_citation_structure_sums_only_what_the_product_recorded():
    structure = citation_structure_by_format(
        document_formats={"a": "docx", "b": "docx", "c": "markdown"},
        ingestion_lineage={
            "a": {"chunk_count": 1, "structured_chunk_count": 0,
                  "converted_mime_type": "text/plain",
                  "warnings": ["HEADING_DETECTION_UNAVAILABLE", "NO_HEADINGS_DETECTED"]},
            "b": {"chunk_count": 3, "structured_chunk_count": 1,
                  "converted_mime_type": "text/plain",
                  "warnings": ["HEADING_DETECTION_UNAVAILABLE"]},
            "c": {"chunk_count": 4, "structured_chunk_count": 4,
                  "converted_mime_type": "text/markdown", "warnings": []},
        },
    )
    assert structure["docx"]["chunk_count"] == 4
    assert structure["docx"]["structured_chunk_count"] == 1
    assert structure["docx"]["structured_chunk_pct"] == 25.0
    assert structure["docx"]["warning_counts"] == {
        "HEADING_DETECTION_UNAVAILABLE": 2, "NO_HEADINGS_DETECTED": 1
    }
    assert structure["markdown"]["structured_chunk_pct"] == 100.0
