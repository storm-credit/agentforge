"""Ingestion lineage: what each index attempt actually produced.

WO-2026-08-14-INGESTION-INSTRUMENTATION-001 -- AC-01 .. AC-06.

The centre of this file is ``TestParserOutputIsUnchanged``, which is the AC-03 proof. Its
expected values were produced by running the parser on commit 12f0216 -- BEFORE any line of
this Work Order's implementation existed -- and pasted in verbatim. The Work Order says the
existing suite passing is "necessary but not sufficient"; a suite can only catch a regression
in what it already asserts, and nothing asserted the DOCX/PDF chunk ids or the Korean-heading
markdown locators. So the pin is a digest over every field of every chunk for four inputs,
plus the individual locators spelled out so a reader can see what is pinned rather than
trusting a hash.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json

import pytest

RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy", "docx", "pypdf")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


# =======================================================================================
# Fixture content: one policy text, expressed as markdown and as a DOCX with the same
# headings. This is the pair the Work Order's problem statement is about.
# =======================================================================================
POLICY_MD = (
    "# 취업규칙\n"
    "\n"
    "## 제3장 연차 유급휴가\n"
    "\n"
    "제15조 근속 1년 이상 직원은 15일의 연차 유급휴가를 받는다.\n"
    "연차는 회계연도 기준으로 산정한다.\n"
    "\n"
    "## 제4장 휴가 신청 절차\n"
    "\n"
    "제20조 휴가는 사용 3일 전까지 결재선에 상신한다.\n"
    "긴급한 경우 사후 결재를 허용한다.\n"
    "\n"
    "## 제5장 경조사 휴가\n"
    "\n"
    "제25조 본인 결혼은 5일, 배우자 출산은 10일의 경조사 휴가를 부여한다.\n"
)


def build_docx_bytes(markdown_text: str) -> bytes:
    """The same text as a DOCX: every markdown line becomes a paragraph, '#' stripped.

    Deliberately NOT using Word heading styles -- the point of the contrast is that the
    chunker is told ``text/plain`` regardless, so even a perfectly structured DOCX loses its
    hierarchy at the seam described in the ingestion-normalization design section 1-1.
    """
    from docx import Document as DocxDocument

    document = DocxDocument()
    for line in markdown_text.split("\n"):
        stripped = line.lstrip("#").strip()
        if stripped:
            document.add_paragraph(stripped)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_pdf_bytes(page_texts: list[str]) -> bytes:
    """A minimal multi-page PDF, hand-assembled so no new dependency is needed.

    Pages whose text is empty get no content stream at all, which is how a scanned page
    behaves to a text extractor: it is present and contributes nothing.
    """
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    content_ids: list[int | None] = []
    for text in page_texts:
        if text:
            escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1", "replace")
            content_ids.append(
                add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
            )
        else:
            content_ids.append(None)
        page_ids.append(add(b"PLACEHOLDER"))

    pages_id = add(b"PLACEHOLDER")
    catalog_id = add(b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>")

    for page_id, content_id in zip(page_ids, content_ids, strict=True):
        contents = f" /Contents {content_id} 0 R" if content_id else ""
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792]"
            f" /Resources << /Font << /F1 {font_id} 0 R >> >>{contents} >>"
        ).encode()
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>"
    ).encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(out)


# =======================================================================================
# AC-03: no conversion, chunking or citation-locator output changes
# =======================================================================================
def _canonical(chunks) -> list[dict]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "chunk_hash": chunk.chunk_hash,
            "token_count": chunk.token_count,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "section_path": list(chunk.section_path),
            "citation_locator": chunk.citation_locator,
            "parser_version": chunk.parser_version,
            "chunker_version": chunk.chunker_version,
        }
        for chunk in chunks
    ]


def _parser_output_snapshot() -> dict:
    from app.domain.parsers import (
        DOCX_MIME_TYPE,
        chunker_mime_type_for,
        extract_text_from_bytes,
        parse_txt_md_document,
    )

    docx_text = extract_text_from_bytes(
        mime_type=DOCX_MIME_TYPE, content=build_docx_bytes(POLICY_MD)
    )
    return {
        "docx_extracted_text": docx_text,
        "docx": _canonical(
            parse_txt_md_document(
                document_id="doc-docx",
                document_version="2026-08-14",
                title="취업규칙 (DOCX)",
                mime_type=chunker_mime_type_for(DOCX_MIME_TYPE),
                source_text=docx_text,
            )
        ),
        "markdown": _canonical(
            parse_txt_md_document(
                document_id="doc-md",
                document_version="2026-08-14",
                title="취업규칙 (MD)",
                mime_type="text/markdown",
                source_text=POLICY_MD,
            )
        ),
        "plain": _canonical(
            parse_txt_md_document(
                document_id="doc-txt",
                document_version="v0",
                title="Holiday Policy",
                mime_type="text/plain",
                source_text="First paragraph.\n\nSecond paragraph for citation.",
            )
        ),
        "windowed": _canonical(
            parse_txt_md_document(
                document_id="doc-overlap",
                document_version="v0",
                title="Window Doc",
                mime_type="text/plain",
                source_text="\n".join(f"w{n}" for n in range(1, 13)),
                target_tokens=5,
                overlap_tokens=2,
            )
        ),
    }


#: sha256 of the canonical JSON of every field of every chunk for the four inputs above,
#: recorded from commit 12f0216 (the merge-base of this Work Order's branch), i.e. from the
#: tree BEFORE the lineage instrumentation existed. If instrumentation ever perturbs parsing
#: -- a normalisation "while we're here", a different extraction order, an extra strip -- this
#: digest changes and the Work Order's escalation clause applies: stop and report, because
#: behaviour change belongs to a separate Work Order.
PARSER_OUTPUT_DIGEST_BEFORE = (
    "702efdc09a5c945eb1b582c85a4dbd66b5792cdbc8610d5067711679b65af6d8"
)


class TestParserOutputIsUnchanged:
    """AC-03."""

    def test_every_parser_field_matches_the_pre_change_recording(self):
        snapshot = _parser_output_snapshot()
        digest = hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        assert digest == PARSER_OUTPUT_DIGEST_BEFORE, (
            "Parser output changed. This Work Order is instrumentation only: conversion, "
            "chunking and citation locators must be byte-identical. Snapshot was: "
            f"{json.dumps(snapshot, ensure_ascii=False, sort_keys=True)}"
        )

    def test_the_pinned_values_are_the_ones_a_reader_would_check(self):
        """The digest above is opaque; these are the same facts in readable form."""
        snapshot = _parser_output_snapshot()
        assert [chunk["citation_locator"] for chunk in snapshot["markdown"]] == [
            "취업규칙 (MD) / 취업규칙 > 제3장 연차 유급휴가 / lines 5-6",
            "취업규칙 (MD) / 취업규칙 > 제4장 휴가 신청 절차 / lines 10-11",
            "취업규칙 (MD) / 취업규칙 > 제5장 경조사 휴가 / lines 15-15",
        ]
        assert [chunk["citation_locator"] for chunk in snapshot["docx"]] == [
            "취업규칙 (DOCX) / body / lines 1-17",
        ]
        assert [chunk["chunk_id"] for chunk in snapshot["docx"]] == [
            "doc-docx:2026-08-14:l1-17:c000:0d08caeb",
        ]
        assert [chunk["chunk_id"] for chunk in snapshot["markdown"]] == [
            "doc-md:2026-08-14:l5-6:c000:b651aa8b",
            "doc-md:2026-08-14:l10-11:c001:038f0d1d",
            "doc-md:2026-08-14:l15-15:c002:8bf4b5db",
        ]

    def test_the_collapse_this_work_order_measures_is_still_present(self):
        """Instrumentation must MEASURE the defect, not repair it. If a future slice fixes the
        seam, this test fails and that is correct -- it is the ledger entry saying the
        instrumentation baseline was taken against the broken behaviour."""
        snapshot = _parser_output_snapshot()
        assert all(chunk["section_path"] == [] for chunk in snapshot["docx"])
        assert all(chunk["section_path"] for chunk in snapshot["markdown"])
