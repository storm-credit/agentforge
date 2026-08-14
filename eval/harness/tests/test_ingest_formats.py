"""Format declaration and fixture generation (WO-2026-08-14-EVAL-FORMAT-COVERAGE-001)."""

import io
import json
import pathlib
import sys

import pytest

HARNESS_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.ingest_formats import (  # noqa: E402
    DOCX,
    DOCX_MIME_TYPE,
    MARKDOWN,
    NO_DOCUMENT_FORMAT,
    UnsupportedIngestionFormat,
    build_docx_fixture,
    case_ingestion_format,
    document_formats,
    document_ingestion_format,
    fixture_for,
    is_binary_format,
    normalize_format,
)

BODY = "# 취업규칙\n## 제3장 연차유급휴가\n연 15일의 연차유급휴가를 부여한다.\n## 제4장 수습\n수습기간은 3개월로 한다.\n"


def test_absent_format_defaults_to_markdown_so_existing_corpora_are_unchanged():
    assert document_ingestion_format({"doc_id": "d", "body": BODY}) == MARKDOWN
    assert normalize_format(None) == MARKDOWN
    assert is_binary_format(MARKDOWN) is False


def test_unknown_or_unbuildable_format_raises_instead_of_silently_ingesting_as_markdown():
    # Quietly falling back to markdown is exactly the failure this Work Order exists to end.
    with pytest.raises(UnsupportedIngestionFormat):
        normalize_format("dcox")
    with pytest.raises(UnsupportedIngestionFormat):
        # The product parses PDF, but nothing here can WRITE one -- see ingest_formats.py.
        normalize_format("pdf")


def test_declared_docx_is_a_binary_format_with_an_upload_fixture():
    assert is_binary_format(DOCX) is True
    fixture = fixture_for(DOCX, doc_id="hr-work-rules-docx", body=BODY)
    assert fixture.filename == "hr-work-rules-docx.docx"
    assert fixture.mime_type == DOCX_MIME_TYPE
    assert fixture.content.startswith(b"PK")  # a real OOXML zip container


def test_docx_fixture_carries_heading_STYLES_not_literal_markdown_markers():
    from docx import Document as DocxDocument

    document = DocxDocument(io.BytesIO(build_docx_fixture(BODY)))
    styled = [(p.style.name, p.text) for p in document.paragraphs]
    assert ("Heading 1", "취업규칙") in styled
    assert ("Heading 2", "제3장 연차유급휴가") in styled
    # If the hash marks survived into the text, the fixture would be smuggling markdown
    # through the binary path and the measurement would describe this generator, not the
    # product's conversion.
    assert all("#" not in text for _, text in styled)


def test_case_format_inherits_from_the_document_the_case_is_about():
    doc_formats = {"md-doc": MARKDOWN, "docx-doc": DOCX}
    cited = {"case_id": "a", "expected_citation_doc": "docx-doc", "forbidden_doc": None}
    assert case_ingestion_format(cited, doc_formats) == DOCX
    denied = {"case_id": "b", "expected_citation_doc": None, "forbidden_doc": "docx-doc"}
    assert case_ingestion_format(denied, doc_formats) == DOCX
    explicit = {"case_id": "c", "expected_citation_doc": "md-doc", "ingestion_format": "docx"}
    assert case_ingestion_format(explicit, doc_formats) == DOCX


def test_case_about_no_document_is_not_attributed_to_a_format_it_never_exercised():
    bare = {"case_id": "r", "expected_citation_doc": None, "forbidden_doc": None}
    assert case_ingestion_format(bare, {"md-doc": MARKDOWN}) == NO_DOCUMENT_FORMAT


def _load(name):
    path = REPO_ROOT / "eval" / "synthetic-corpus" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_existing_live_corpora_declare_no_format_and_therefore_stay_markdown():
    # AC-04: the pre-existing corpora are untouched, so their runs keep taking the exact
    # register + index-job path their recorded baselines were measured on.
    for name in ("cases-live-v0.1.json", "cases-live-v0.2.json", "cases-live-v0.3.json",
                 "cases-pilot-hr-v1.json"):
        corpus = _load(name)
        assert all("ingestion_format" not in doc for doc in corpus["documents"])
        assert set(document_formats(corpus["documents"]).values()) == {MARKDOWN}


def test_format_corpus_pairs_identical_text_across_the_two_formats():
    corpus = _load("cases-pilot-hr-format-v1.json")
    docs = {doc["doc_id"]: doc for doc in corpus["documents"]}
    md_docs = [d for d in corpus["documents"] if d["ingestion_format"] == MARKDOWN]
    assert md_docs, "the corpus must still measure markdown"
    for md_doc in md_docs:
        twin = docs[md_doc["doc_id"].replace("-md", "-docx")]
        assert twin["ingestion_format"] == DOCX
        # Same policy text, ingested twice: any per-format difference is the product's.
        assert twin["body"] == md_doc["body"]
        assert twin["confidentiality_level"] == md_doc["confidentiality_level"]


def test_format_corpus_isolates_the_formats_so_they_cannot_compete_in_retrieval():
    # Both copies of a policy live in the same run. If a principal could reach both, a docx
    # case could "pass" by citing the markdown twin and the per-format numbers would be
    # meaningless. Each format's documents are therefore in their own access groups, and each
    # case's principal holds only its own format's groups.
    corpus = _load("cases-pilot-hr-format-v1.json")
    groups_by_format = {}
    for doc in corpus["documents"]:
        groups_by_format.setdefault(doc["ingestion_format"], set()).update(doc["access_groups"])
    assert not groups_by_format[MARKDOWN] & groups_by_format[DOCX]
    for case in corpus["cases"]:
        held = set(case["principal"]["groups"])
        other = groups_by_format[DOCX if case["ingestion_format"] == MARKDOWN else MARKDOWN]
        assert not held & other, f"{case['case_id']} can reach the other format's copies"
        # "all-employees" is granted to every principal unconditionally by the product, so a
        # corpus document carrying it would be readable from both formats' cases.
        assert "all-employees" not in held


def test_format_corpus_asks_the_same_questions_of_both_formats():
    corpus = _load("cases-pilot-hr-format-v1.json")
    questions = {MARKDOWN: {}, DOCX: {}}
    for case in corpus["cases"]:
        questions[case["ingestion_format"]][case["question"]] = case["expected_behavior"]
    assert questions[MARKDOWN] == questions[DOCX]
    assert len(questions[MARKDOWN]) >= 10
    doc_ids = {doc["doc_id"] for doc in corpus["documents"]}
    for case in corpus["cases"]:
        assert case["expected_behavior"] in {"answer", "policy_denied", "refuse"}
        for key in ("expected_citation_doc", "forbidden_doc"):
            if case[key]:
                assert case[key] in doc_ids
