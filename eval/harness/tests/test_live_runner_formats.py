"""What the runner ASKS the product for, and what the report then says (AC-01/02/03).

These tests drive ``run_live_eval`` against an httpx MockTransport, so they assert the exact
requests the harness makes for each declared ingestion format -- a markdown document must
still take the register + index-job path it always took, and a declared DOCX document must go
out as a multipart file to the real upload endpoint -- without needing a live stack.

The fake product deliberately returns lineage counts that the harness could NOT derive from
the run results it is given. That is the point of AC-03: the citation-structure numbers in the
report have to be the product's recorded ones, so the harness and the product can never
disagree about what ingestion produced.
"""

import json
import pathlib
import sys

import httpx

HARNESS_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.live_runner import run_live_eval  # noqa: E402
from agentforge_eval.live_scorer import (  # noqa: E402
    FORMAT_COVERAGE_MARKDOWN_ONLY,
    FORMAT_COVERAGE_MIXED,
    MARKDOWN_ONLY_QUALIFICATION,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

MD_LINEAGE = {
    "extraction_status": "ok",
    "source_mime_type": "text/markdown",
    "converted_mime_type": "text/markdown",
    "converter_chain": "identity/decode-utf8>text/markdown",
    "chunk_count": 3,
    "structured_chunk_count": 3,
    "warnings": [],
}
# One blob, no clause path -- and counts (7/2) that no amount of looking at the run results
# could produce, so a passing assertion proves the harness read them from the product.
DOCX_LINEAGE = {
    "extraction_status": "ok",
    "source_mime_type": DOCX_MIME,
    "converted_mime_type": "text/plain",
    "converter_chain": "python-docx/1.2.0>text/plain",
    "chunk_count": 7,
    "structured_chunk_count": 2,
    "warnings": ["HEADING_DETECTION_UNAVAILABLE"],
}


def _document(doc_id, *, ingestion_format=None, groups=("all-employees",)):
    doc = {
        "doc_id": doc_id,
        "title": f"title-{doc_id}",
        "confidentiality_level": "internal",
        "access_groups": list(groups),
        "body": "# 제목\n## 제3장 연차\n연 15일의 연차를 부여한다.\n",
    }
    if ingestion_format is not None:
        doc["ingestion_format"] = ingestion_format
    return doc


def _case(case_id, doc_id, question):
    return {
        "case_id": case_id,
        "question": question,
        "principal": {
            "department": "Engineering",
            "groups": ["all-employees"],
            "roles": ["employee"],
            "clearance": "internal",
        },
        "expected_behavior": "answer",
        "expected_citation_doc": doc_id,
        "forbidden_doc": None,
        "must_not_include": [],
        "answer_points": ["15일"],
    }


class FakeProduct:
    """Just enough of the API for the runner, plus a log of every request it made."""

    def __init__(self, corpus, lineages):
        self.corpus = corpus
        self.lineages = lineages
        self.requests: list[httpx.Request] = []
        self.doc_ids: dict[str, str] = {}
        self._pending = [doc["doc_id"] for doc in corpus["documents"]]
        self._questions = {c["question"]: c for c in corpus["cases"]}

    # -- helpers ---------------------------------------------------------------------
    def _next_document(self) -> str:
        return self._pending.pop(0)

    def _lineage_for(self, corpus_doc_id: str) -> dict:
        return self.lineages[corpus_doc_id]

    def uploaded(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path.endswith("/documents/upload")]

    def registered(self) -> list[httpx.Request]:
        return [
            r
            for r in self.requests
            if r.url.path.endswith("/knowledge/documents") and r.method == "POST"
        ]

    def index_jobs(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path.endswith("/index-jobs")]

    # -- transport -------------------------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/knowledge/sources"):
            return httpx.Response(201, json={"id": f"src-{len(self.requests)}"})
        if path.endswith("/knowledge/documents") and request.method == "POST":
            corpus_doc_id = self._next_document()
            self.doc_ids[corpus_doc_id] = f"real-{corpus_doc_id}"
            self._last_registered = corpus_doc_id
            return httpx.Response(201, json={"id": f"real-{corpus_doc_id}"})
        if path.endswith("/index-jobs"):
            return httpx.Response(
                201,
                json={"status": "succeeded", "ingestion": self._lineage_for(self._last_registered)},
            )
        if path.endswith("/documents/upload"):
            corpus_doc_id = self._next_document()
            self.doc_ids[corpus_doc_id] = f"real-{corpus_doc_id}"
            return httpx.Response(
                201,
                json={
                    "document": {"id": f"real-{corpus_doc_id}"},
                    "index_job": {
                        "status": "succeeded",
                        "ingestion": self._lineage_for(corpus_doc_id),
                    },
                },
            )
        if path.endswith("/agents"):
            return httpx.Response(201, json={"id": "agent-1"})
        if path.endswith("/agents/versions"):
            return httpx.Response(201, json={"id": "ver-1"})
        if path.endswith("/publish"):
            return httpx.Response(200, json={"id": "ver-1"})
        if path.endswith("/runs"):
            case = self._questions[json.loads(request.content)["input"]["message"]]
            real = self.doc_ids[case["expected_citation_doc"]]
            return httpx.Response(
                201,
                json={
                    "id": f"run-{case['case_id']}",
                    "answer": "연 15일의 연차를 부여합니다.",
                    "citations": [{"document_id": real}],
                    "latency_ms": 1000,
                },
            )
        if path.endswith("/retrieval-hits"):
            case_id = path.split("/runs/run-")[1].split("/")[0]
            case = next(c for c in self.corpus["cases"] if c["case_id"] == case_id)
            real = self.doc_ids[case["expected_citation_doc"]]
            return httpx.Response(200, json=[{"document_id": real, "score_vector": 0.7}])
        if path.endswith("/steps"):
            return httpx.Response(
                200,
                json=[
                    {"step_type": "guard_input", "output_summary": {}},
                    {"step_type": "retriever", "output_summary": {}},
                    {"step_type": "generator", "output_summary": {}},
                    {"step_type": "citation_validator", "output_summary": {}},
                    {
                        "step_type": "guard_output",
                        "output_summary": {"grounding_score": 0.9, "guard_tripped": False},
                    },
                ],
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")


def _run(tmp_path, corpus, lineages):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    product = FakeProduct(corpus, lineages)
    client = httpx.Client(
        transport=httpx.MockTransport(product.handler), base_url="http://test/api/v1"
    )
    with client:
        report = run_live_eval(path, base_url="http://test/api/v1", prefix="t", client=client)
    return report, product


def _markdown_only_corpus():
    return {
        "corpus_id": "md-only",
        "documents": [_document("md-doc")],
        "cases": [_case("c-md", "md-doc", "연차는 며칠인가요?")],
    }


def _mixed_corpus():
    return {
        "corpus_id": "mixed",
        "documents": [
            _document("md-doc", ingestion_format="markdown"),
            _document("docx-doc", ingestion_format="docx"),
        ],
        "cases": [
            _case("c-md", "md-doc", "연차는 며칠인가요?"),
            _case("c-docx", "docx-doc", "연차 휴가일수를 알려주세요."),
        ],
    }


MIXED_LINEAGES = {"md-doc": MD_LINEAGE, "docx-doc": DOCX_LINEAGE}


def test_markdown_document_still_registers_as_markdown_and_never_uploads(tmp_path):
    # AC-01/AC-04: the pre-existing path is unchanged, so old baselines stay comparable.
    _report, product = _run(tmp_path, _markdown_only_corpus(), {"md-doc": MD_LINEAGE})
    assert product.uploaded() == []
    registered = json.loads(product.registered()[0].content)
    assert registered["mime_type"] == "text/markdown"
    assert registered["object_uri"] == "eval://t/md-doc.md"
    assert registered["status"] == "registered"
    job = json.loads(product.index_jobs()[0].content)
    assert job["source_text"] == _markdown_only_corpus()["documents"][0]["body"]
    assert job["parser_profile"] == "default-txt-md"


def test_declared_docx_document_is_posted_as_a_file_to_the_real_upload_endpoint(tmp_path):
    # AC-01: exercising the binary path for real, not simulating it -- POST
    # /knowledge/documents/upload is the same endpoint an administrator uses.
    _report, product = _run(tmp_path, _mixed_corpus(), MIXED_LINEAGES)
    assert len(product.uploaded()) == 1
    upload = product.uploaded()[0]
    body = upload.content
    assert b'filename="docx-doc.docx"' in body
    assert DOCX_MIME.encode() in body
    assert b"PK\x03\x04" in body  # a real OOXML zip, generated in memory
    assert b'name="access_groups"' in body
    # The markdown twin still went the register route; only one document was registered.
    assert len(product.registered()) == 1
    assert json.loads(product.registered()[0].content)["title"] == "title-md-doc"


def test_markdown_only_corpus_is_reported_as_markdown_only(tmp_path):
    # AC-02: the acceptance criterion that actually prevents the failure being fixed here.
    report, _product = _run(tmp_path, _markdown_only_corpus(), {"md-doc": MD_LINEAGE})
    assert report["citation_pct"] == 100.0
    assert report["format_coverage"] == FORMAT_COVERAGE_MARKDOWN_ONLY
    assert report["format_qualification"] == MARKDOWN_ONLY_QUALIFICATION
    assert "BEST CASE" in report["format_qualification"]
    assert report["ingestion_formats"]["coverage"] == FORMAT_COVERAGE_MARKDOWN_ONLY
    assert report["ingestion_formats"]["formats_measured"] == ["markdown"]
    assert list(report["ingestion_formats"]["by_format"]) == ["markdown"]


def test_mixed_corpus_is_not_labelled_markdown_only_and_splits_the_metrics(tmp_path):
    report, _product = _run(tmp_path, _mixed_corpus(), MIXED_LINEAGES)
    assert report["format_coverage"] == FORMAT_COVERAGE_MIXED
    assert report["ingestion_formats"]["formats_measured"] == ["docx", "markdown"]
    assert report["ingestion_formats"]["case_counts"] == {"docx": 1, "markdown": 1}
    by_format = report["ingestion_formats"]["by_format"]
    assert by_format["markdown"]["total"] == 1
    assert by_format["docx"]["total"] == 1
    assert by_format["docx"]["citation_pct"] == 100.0
    assert {row["ingestion_format"] for row in report["cases"]} == {"markdown", "docx"}


def test_citation_structure_is_the_products_recorded_lineage_not_a_harness_recomputation(
    tmp_path,
):
    # AC-03. The fake product recorded 7 chunks of which 2 were structured for the DOCX
    # document. Nothing in the run results (one citation, one hit) could yield 7 and 2, so
    # these numbers can only have come from the lineage the product returned.
    report, _product = _run(tmp_path, _mixed_corpus(), MIXED_LINEAGES)
    structure = report["ingestion_formats"]["citation_structure"]
    assert structure["docx"]["chunk_count"] == 7
    assert structure["docx"]["structured_chunk_count"] == 2
    assert structure["docx"]["structured_chunk_pct"] == 28.6
    assert structure["docx"]["converted_mime_types"] == ["text/plain"]
    assert structure["docx"]["converter_chains"] == ["python-docx/1.2.0>text/plain"]
    assert structure["docx"]["warning_counts"] == {"HEADING_DETECTION_UNAVAILABLE": 1}
    assert structure["markdown"]["structured_chunk_pct"] == 100.0
    assert structure["markdown"]["warning_counts"] == {}
    assert "never recomputes" in report["ingestion_formats"]["citation_structure_source"]


def test_missing_lineage_reads_as_unmeasured_rather_than_as_zero_structure(tmp_path):
    corpus = _mixed_corpus()
    report, _product = _run(tmp_path, corpus, {"md-doc": MD_LINEAGE, "docx-doc": None})
    docx = report["ingestion_formats"]["citation_structure"]["docx"]
    assert docx["documents"] == 1
    assert docx["documents_with_lineage"] == 0
    assert docx["chunk_count"] is None
    assert docx["structured_chunk_count"] is None
    assert docx["structured_chunk_pct"] is None
    assert docx["documents_missing_lineage"] == ["docx-doc"]
