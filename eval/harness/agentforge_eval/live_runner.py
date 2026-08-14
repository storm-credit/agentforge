from __future__ import annotations

import contextlib
import json
from pathlib import Path

import httpx

from agentforge_eval.ingest_formats import (
    MARKDOWN_MIME_TYPE,
    case_ingestion_format,
    document_formats,
    document_ingestion_format,
    fixture_for,
    is_binary_format,
)
from agentforge_eval.live_scorer import aggregate, score_case, trace_is_complete

_OPERATOR = {
    "X-Agent-Forge-User": "eval-operator",
    "X-Agent-Forge-Department": "Operations",
    "X-Agent-Forge-Roles": "admin",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
}


def _principal_headers(p: dict) -> dict:
    return {
        "X-Agent-Forge-User": "eval-" + p["department"],
        "X-Agent-Forge-Department": p["department"],
        "X-Agent-Forge-Roles": ",".join(p.get("roles", [])) or "employee",
        "X-Agent-Forge-Groups": ",".join(p.get("groups", [])) or "all-employees",
        "X-Agent-Forge-Clearance": p.get("clearance", "internal"),
    }


def _ingest_markdown_document(
    client: httpx.Client, *, doc: dict, prefix: str, source_id: str
) -> tuple[str, dict | None]:
    """The original register + index-job path, byte-for-byte unchanged.

    Every pre-existing corpus takes this branch (``ingestion_format`` defaults to markdown),
    so previously recorded baselines stay comparable: same endpoints, same request bodies.
    """
    reg = client.post(
        "/knowledge/documents",
        headers=_OPERATOR,
        json={
            "knowledge_source_id": source_id,
            "title": doc["title"],
            "object_uri": f"eval://{prefix}/{doc['doc_id']}.md",
            "checksum": f"sha256-{prefix}-{doc['doc_id']}",
            "mime_type": MARKDOWN_MIME_TYPE,
            "confidentiality_level": doc["confidentiality_level"],
            "access_groups": doc["access_groups"],
            "status": "registered",
        },
    )
    reg.raise_for_status()
    document_id = reg.json()["id"]

    job = client.post(
        f"/knowledge/documents/{document_id}/index-jobs",
        headers=_OPERATOR,
        json={
            "parser_profile": "default-txt-md",
            "embedding_model": "bge-m3",
            "source_text": doc["body"],
        },
    )
    job.raise_for_status()
    job_body = job.json()
    if job_body.get("status") != "succeeded":
        raise RuntimeError(f"index failed for {doc['doc_id']}: {job_body}")
    return document_id, job_body.get("ingestion")


def _ingest_binary_document(
    client: httpx.Client, *, doc: dict, source_id: str, ingestion_format: str
) -> tuple[str, dict | None]:
    """The REAL upload path: a generated file posted to POST /knowledge/documents/upload.

    Not a simulation of a binary ingest -- this is the endpoint an administrator uses, so the
    file goes through the product's own extractor, ``chunker_mime_type_for`` and chunker. The
    endpoint registers, indexes inline and returns the index job, whose ``ingestion`` object is
    the product's own record of what the conversion produced.
    """
    fixture = fixture_for(ingestion_format, doc_id=doc["doc_id"], body=doc["body"])
    response = client.post(
        "/knowledge/documents/upload",
        headers=_OPERATOR,
        data={
            "knowledge_source_id": source_id,
            "title": doc["title"],
            "confidentiality_level": doc["confidentiality_level"],
            "access_groups": ",".join(doc["access_groups"]),
            "embedding_model": "bge-m3",
        },
        files={"file": (fixture.filename, fixture.content, fixture.mime_type)},
    )
    response.raise_for_status()
    body = response.json()
    job_body = body["index_job"]
    if job_body.get("status") != "succeeded":
        raise RuntimeError(f"upload index failed for {doc['doc_id']}: {job_body}")
    return body["document"]["id"], job_body.get("ingestion")


def run_live_eval(
    corpus_path: Path,
    base_url: str,
    prefix: str,
    grounding_min: float | None = None,
    client: httpx.Client | None = None,
) -> dict:
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    doc_formats = document_formats(corpus["documents"])
    with contextlib.ExitStack() as stack:
        if client is None:
            client = stack.enter_context(httpx.Client(base_url=base_url, timeout=120.0))
        doc_id_map: dict[str, str] = {}
        source_ids: list[str] = []
        # doc_id -> the product's recorded lineage for this run's index attempt, or None when
        # the backend returned none. Never reconstructed by the harness (AC-03).
        ingestion_lineage: dict[str, dict | None] = {}
        for doc in corpus["documents"]:
            src = client.post(
                "/knowledge/sources",
                headers=_OPERATOR,
                json={"name": f"{prefix}:{doc['doc_id']}", "owner_department": "Operations"},
            )
            src.raise_for_status()
            source_id = src.json()["id"]
            source_ids.append(source_id)

            ingestion_format = document_ingestion_format(doc)
            if is_binary_format(ingestion_format):
                document_id, lineage = _ingest_binary_document(
                    client, doc=doc, source_id=source_id, ingestion_format=ingestion_format
                )
            else:
                document_id, lineage = _ingest_markdown_document(
                    client, doc=doc, prefix=prefix, source_id=source_id
                )
            doc_id_map[doc["doc_id"]] = document_id
            ingestion_lineage[doc["doc_id"]] = lineage

        agent = client.post(
            "/agents",
            headers=_OPERATOR,
            json={
                "name": f"{prefix} eval agent",
                "purpose": "live eval",
                "owner_department": "Operations",
                "status": "draft",
            },
        )
        agent.raise_for_status()
        agent_id = agent.json()["id"]

        ver = client.post(
            "/agents/versions",
            headers=_OPERATOR,
            json={
                "agent_id": agent_id,
                "version": 1,
                "status": "draft",
                "config": {"citation_required": True, "knowledge_source_ids": source_ids},
            },
        )
        ver.raise_for_status()
        version_id = ver.json()["id"]
        client.post(
            f"/agents/versions/{version_id}/publish", headers=_OPERATOR, json={"reason": "eval"}
        ).raise_for_status()

        scores = []
        top_scores: dict[str, float] = {}
        grounding_scores: dict[str, float | None] = {}
        guard_tripped: dict[str, bool] = {}
        latencies_ms: dict[str, int] = {}
        trace_complete: dict[str, bool] = {}
        for case in corpus["cases"]:
            run = client.post(
                "/runs",
                headers=_principal_headers(case["principal"]),
                json={"agent_id": agent_id, "input": {"message": case["question"]}, "language": "auto"},
            )
            run.raise_for_status()
            rj = run.json()
            latencies_ms[case["case_id"]] = rj.get("latency_ms", 0)
            # Reading the run trace is owner/admin-scoped; the eval harness is an
            # admin/operator tool, so read hits/steps with the operator identity.
            hits = client.get(f"/runs/{rj['id']}/retrieval-hits", headers=_OPERATOR).json()
            top_scores[case["case_id"]] = max(
                (h.get("score_vector") or 0.0 for h in hits), default=0.0
            )
            steps = client.get(f"/runs/{rj['id']}/steps", headers=_OPERATOR).json()
            guard = next((s for s in steps if s["step_type"] == "guard_output"), None)
            guard_out = (guard or {}).get("output_summary", {})
            grounding_scores[case["case_id"]] = guard_out.get("grounding_score")
            guard_tripped[case["case_id"]] = bool(guard_out.get("guard_tripped"))
            trace_complete[case["case_id"]] = trace_is_complete(
                s.get("step_type") for s in steps
            )
            run_result = {
                "answer": rj.get("answer", ""),
                "citations": rj.get("citations", []),
                "hit_document_ids": [h.get("document_id") for h in hits],
            }
            scores.append(score_case(case, run_result, doc_id_map))

    case_ids = [case["case_id"] for case in corpus["cases"]]
    case_formats = {
        case["case_id"]: case_ingestion_format(case, doc_formats) for case in corpus["cases"]
    }
    report = aggregate(
        scores,
        latencies_ms=[latencies_ms[cid] for cid in case_ids],
        trace_complete=[trace_complete[cid] for cid in case_ids],
        grounding_scores=[grounding_scores.get(cid) for cid in case_ids],
        grounding_min=grounding_min,
        case_formats=case_formats,
        ingestion_lineage=ingestion_lineage,
        document_formats=doc_formats,
    )
    for case_row in report["cases"]:
        cid = case_row["case_id"]
        case_row["top_score"] = round(top_scores.get(cid, 0.0), 4)
        case_row["grounding_score"] = grounding_scores.get(cid)
        case_row["guard_tripped"] = guard_tripped.get(cid, False)
        case_row["latency_ms"] = latencies_ms.get(cid)
        case_row["trace_complete"] = trace_complete.get(cid, False)
    report["corpus_id"] = corpus["corpus_id"]
    return report
