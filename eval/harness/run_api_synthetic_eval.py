from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HARNESS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.api_eval import (  # noqa: E402
    build_api_report,
    build_document_markdown,
    document_access_groups,
    index_expected_to_succeed,
    principal_headers,
    score_api_case,
    select_cases,
    upload_filename,
)
from agentforge_eval.corpus import Corpus, Document, load_corpus  # noqa: E402
from agentforge_eval.model_probe import (  # noqa: E402
    ModelProbeConfig,
    model_probe_skipped,
    probe_openai_compatible_model,
)

MODEL_ROUTING_POLICY_REF = "packages/shared-contracts/model-routing-policy.v0.1.json"
VALIDATION_LANE_BUDGET_CLASS = {
    "local-regression": "smoke",
    "company-quality": "release-gate",
}
QUALITY_REVIEW_RUBRIC_VERSION = "quality-rubric-v0.1"
QUALITY_REVIEW_RUBRIC = {
    "rubric_version": QUALITY_REVIEW_RUBRIC_VERSION,
    "score_scale": {"min": 1, "max": 5, "passing_score": 4},
    "dimensions": {
        "answer_naturalness": {
            "label": "Answer naturalness",
            "passing_score": 4,
        },
        "korean_business_tone": {
            "label": "Korean business tone",
            "passing_score": 4,
        },
        "recommendation_rationale": {
            "label": "Recommendation rationale",
            "passing_score": 4,
        },
        "groundedness": {
            "label": "Groundedness to authorized citations",
            "passing_score": 4,
        },
    },
    "automatic_gates": {
        "final_answer_cleanliness": {
            "severity": "blocker",
            "must_not_include": ["<think>", "</think>"],
        },
        "citation_acl_recheck": {
            "severity": "blocker",
            "required": True,
        },
        "raw_endpoint_secret_absent": {
            "severity": "blocker",
            "required": True,
        },
    },
}
EVAL_MODEL_ROUTE_SUMMARY = {
    "security_precheck": {
        "tier": "fast-small",
        "temperature": 0.0,
        "route_decision_source": "input_guard",
    },
    "planner": {
        "tier": "fast-small",
        "temperature": 0.0,
        "route_decision_source": "agent_card",
    },
    "retriever": {
        "tier": "deterministic",
        "uses": ["embedding", "reranker"],
        "route_decision_source": "acl_filter",
    },
    "answer_generator": {
        "tier": "standard-rag",
        "temperature": 0.2,
        "route_decision_source": "authorized_context",
    },
    "critic": {
        "tier": "fast-small",
        "escalation_tier": "deep-review",
        "temperature": 0.0,
        "route_decision_source": "citation_gate",
    },
    "security_finalcheck": {
        "tier": "fast-small",
        "escalation_tier": "deep-review",
        "temperature": 0.0,
        "route_decision_source": "output_guard",
    },
    "formatter": {
        "tier": "deterministic",
        "route_decision_source": "response_envelope",
    },
    "cost_latency_controller": {
        "tier": "deterministic",
        "route_decision_source": "budget_policy",
    },
}


class ApiError(RuntimeError):
    def __init__(
        self,
        *,
        method: str,
        path: str,
        status_code: int | None,
        body: str,
    ) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.body = body
        status = status_code if status_code is not None else "network"
        super().__init__(f"{method} {path} failed with {status}: {body}")


class ApiClient:
    def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get(
        self,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.request("GET", path, headers=headers, query=query)

    def post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.request("POST", path, headers=headers, query=query, json_payload=payload)

    def post_bytes(
        self,
        path: str,
        content: bytes,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        content_type: str,
    ) -> Any:
        merged_headers = {"Content-Type": content_type, **dict(headers or {})}
        return self.request("POST", path, headers=merged_headers, query=query, body=content)

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        json_payload: Mapping[str, Any] | None = None,
        body: bytes | None = None,
    ) -> Any:
        request_headers = {"Accept": "application/json", **dict(headers or {})}
        request_body = body
        if json_payload is not None:
            request_headers.setdefault("Content-Type", "application/json")
            request_body = json.dumps(json_payload).encode("utf-8")

        request = Request(
            self._url(path, query=query),
            data=request_body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return _decode_response(response.read())
        except HTTPError as exc:
            raise ApiError(
                method=method,
                path=path,
                status_code=exc.code,
                body=exc.read().decode("utf-8", errors="replace"),
            ) from exc
        except URLError as exc:
            raise ApiError(
                method=method,
                path=path,
                status_code=None,
                body=str(exc.reason),
            ) from exc

    def _url(self, path: str, *, query: Mapping[str, Any] | None) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url += "?" + urlencode(query, doseq=True)
        return url


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    corpus = load_corpus(args.corpus_path)
    try:
        selected_cases = select_cases(corpus, case_ids=args.case, suites=args.suite)
    except ValueError as exc:
        report = build_api_report(
            corpus=corpus,
            selected_cases=(),
            setup_findings=[str(exc)],
            setup={
                "api_base_url": args.api_base_url,
                "validation_lane": args.validation_lane,
            },
            results=(),
        )
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 2

    setup_findings: list[str] = []
    model_probe = _run_model_probe(args)
    if _model_probe_blocks_lane(args, model_probe):
        setup_findings.append(_model_probe_finding(model_probe))

    client = ApiClient(args.api_base_url, timeout_seconds=args.timeout_seconds)

    run_token = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    admin_headers = {
        "X-Agent-Forge-User": "eval-api-runner",
        "X-Agent-Forge-Department": "qa",
        "X-Agent-Forge-Roles": "developer,eval-runner",
        "X-Agent-Forge-Groups": "employee,eval-runners",
        "X-Agent-Forge-Clearance": "confidential",
    }

    try:
        source = _create_source(client, run_token=run_token, headers=admin_headers)
        document_setup = _upload_and_index_documents(
            client,
            corpus=corpus,
            source_id=source["id"],
            headers=admin_headers,
            setup_findings=setup_findings,
        )
        agent = _create_agent(client, run_token=run_token, headers=admin_headers)
        version = _create_and_publish_version(
            client,
            agent_id=agent["id"],
            source_id=source["id"],
            corpus=corpus,
            document_id_map=document_setup["api_to_corpus_document_ids"],
            run_token=run_token,
            headers=admin_headers,
        )
    except ApiError as exc:
        report = build_api_report(
            corpus=corpus,
            selected_cases=selected_cases,
            setup_findings=[str(exc)],
            setup={
                "api_base_url": args.api_base_url,
                "run_token": run_token,
                **_model_setup(args, model_probe),
            },
            results=(),
        )
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 1

    results = []
    for case in selected_cases:
        run = None
        retrieval_hits = []
        error = None
        try:
            run = client.post_json(
                "/runs",
                {
                    "agent_id": agent["id"],
                    "agent_version_id": version["id"],
                    "input": {"message": case.question},
                    "knowledge_source_ids": [source["id"]],
                    "top_k": args.top_k,
                },
                headers=principal_headers(case, corpus),
            )
            retrieval_hits = client.get(
                f"/runs/{run['id']}/retrieval-hits",
                headers=principal_headers(case, corpus),
            )
        except ApiError as exc:
            error = str(exc)

        results.append(
            score_api_case(
                case,
                run=run,
                retrieval_hits=retrieval_hits,
                api_document_id_map=document_setup["api_to_corpus_document_ids"],
                error=error,
            )
        )

    report = build_api_report(
        corpus=corpus,
        selected_cases=selected_cases,
        setup_findings=setup_findings,
        setup={
            "api_base_url": args.api_base_url,
            "run_token": run_token,
            "knowledge_source_id": source["id"],
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "top_k": args.top_k,
            **_model_setup(args, model_probe),
            **document_setup,
        },
        results=results,
    )
    persisted_eval_run = None
    persistence_error = None
    try:
        persisted_eval_run = client.post_json(
            "/eval/runs",
            _eval_run_payload(report.to_dict()),
            headers=admin_headers,
        )
    except ApiError as exc:
        persistence_error = f"Eval report persistence failed: {exc}"
        report = build_api_report(
            corpus=corpus,
            selected_cases=selected_cases,
            setup_findings=[*setup_findings, persistence_error],
            setup={
                "api_base_url": args.api_base_url,
                "run_token": run_token,
                "knowledge_source_id": source["id"],
                "agent_id": agent["id"],
                "agent_version_id": version["id"],
                "top_k": args.top_k,
                **_model_setup(args, model_probe),
                **document_setup,
            },
            results=results,
        )

    report_payload = _eval_run_payload(report.to_dict())
    if isinstance(persisted_eval_run, Mapping) and isinstance(persisted_eval_run.get("id"), str):
        report_payload["setup"]["eval_run_id"] = persisted_eval_run["id"]
        report_payload["setup"]["eval_api_endpoint"] = "/eval/runs"

    print(json.dumps(report_payload, indent=2, sort_keys=True))
    return 0 if report.passed else 1


def _eval_run_payload(report_payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = report_payload.get("summary")
    merged_summary = dict(summary) if isinstance(summary, Mapping) else {}
    merged_summary.setdefault("quality_review", _quality_review_for_report(report_payload))
    return {
        **dict(report_payload),
        "summary": merged_summary,
        "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
        "budget_class": _budget_class_for_report(report_payload),
        "model_route_summary": EVAL_MODEL_ROUTE_SUMMARY,
    }


def _quality_review_for_report(report_payload: Mapping[str, Any]) -> dict[str, Any]:
    setup = report_payload.get("setup")
    validation_lane = setup.get("validation_lane") if isinstance(setup, Mapping) else ""
    is_company_quality = validation_lane == "company-quality"
    return {
        **QUALITY_REVIEW_RUBRIC,
        "validation_lane": validation_lane or "unknown",
        "human_review_required": is_company_quality,
        "release_approval_blocked_until_review": is_company_quality,
        "status": "pending_human_review" if is_company_quality else "advisory_only",
        "notes": (
            "Company-quality runs require human review for tone, usefulness, rationale, "
            "and final-answer cleanliness before release approval."
            if is_company_quality
            else "Local-regression runs prove integration and safety regression only; "
            "they are not final answer-quality approval."
        ),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the synthetic corpus against a live Agent Forge API.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("AGENT_FORGE_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
        help="Base API URL, including /api/v1.",
    )
    parser.add_argument(
        "--validation-lane",
        choices=tuple(VALIDATION_LANE_BUDGET_CLASS),
        default=os.environ.get("AGENT_FORGE_VALIDATION_LANE", "local-regression"),
        help="Model validation lane to record in the eval report.",
    )
    parser.add_argument(
        "--model-base-url",
        default=os.environ.get("AGENT_FORGE_MODEL_BASE_URL", ""),
        help="OpenAI-compatible model base URL. Example: http://vllm.local:8000/v1",
    )
    parser.add_argument(
        "--model-id",
        default=os.environ.get("AGENT_FORGE_MODEL_ID", ""),
        help="Model ID to send to /v1/chat/completions.",
    )
    parser.add_argument(
        "--model-provider",
        default=os.environ.get("AGENT_FORGE_MODEL_PROVIDER", ""),
        help="Provider label for provenance, for example local or company-vllm.",
    )
    parser.add_argument(
        "--model-endpoint-alias",
        default=os.environ.get("AGENT_FORGE_MODEL_ENDPOINT_ALIAS", ""),
        help="Non-secret endpoint alias recorded in eval setup.",
    )
    parser.add_argument(
        "--model-timeout-seconds",
        type=float,
        default=float(os.environ.get("AGENT_FORGE_MODEL_TIMEOUT_SECONDS", "15")),
        help="Per-request timeout for the model probe.",
    )
    parser.add_argument(
        "--skip-model-probe",
        action="store_true",
        default=_truthy_env("AGENT_FORGE_SKIP_MODEL_PROBE"),
        help="Record model provenance fields without calling the configured model endpoint.",
    )
    parser.add_argument(
        "--corpus-path",
        type=Path,
        default=REPO_ROOT / "eval" / "synthetic-corpus" / "cases-v0.1.json",
        help="Path to synthetic corpus JSON.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Case ID to run. May be repeated or comma-separated. Defaults to all cases.",
    )
    parser.add_argument(
        "--suite",
        action="append",
        default=[],
        help="Suite to run. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Runtime retrieval top_k for each case.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-request HTTP timeout.",
    )
    return parser.parse_args(argv)


def _run_model_probe(args: argparse.Namespace) -> dict[str, Any]:
    provider = _model_provider(args)
    endpoint_alias = _model_endpoint_alias(args)
    model_id = args.model_id.strip()
    base_url = args.model_base_url.strip()

    if args.skip_model_probe:
        return model_probe_skipped(
            validation_lane=args.validation_lane,
            provider=provider,
            model_id=model_id,
            endpoint_alias=endpoint_alias,
            reason="model probe skipped by operator",
        )

    if not base_url or not model_id:
        return model_probe_skipped(
            validation_lane=args.validation_lane,
            provider=provider,
            model_id=model_id,
            endpoint_alias=endpoint_alias,
            reason="model endpoint or model id not configured",
        )

    return probe_openai_compatible_model(
        ModelProbeConfig(
            validation_lane=args.validation_lane,
            provider=provider,
            model_id=model_id,
            base_url=base_url,
            endpoint_alias=endpoint_alias,
            timeout_seconds=args.model_timeout_seconds,
            api_key=os.environ.get("AGENT_FORGE_MODEL_API_KEY"),
        )
    )


def _model_setup(args: argparse.Namespace, model_probe: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "validation_lane": args.validation_lane,
        "model_provider": _model_provider(args),
        "model_id": args.model_id.strip(),
        "model_endpoint_alias": _model_endpoint_alias(args),
        "model_timeout_seconds": args.model_timeout_seconds,
        "model_probe": dict(model_probe),
    }


def _model_probe_blocks_lane(args: argparse.Namespace, model_probe: Mapping[str, Any]) -> bool:
    status = model_probe.get("status")
    if status == "failed":
        return True
    return args.validation_lane == "company-quality" and status != "succeeded"


def _model_probe_finding(model_probe: Mapping[str, Any]) -> str:
    status = model_probe.get("status", "unknown")
    reason = model_probe.get("reason") or model_probe.get("error") or "model probe did not pass"
    return f"Model probe {status}: {reason}"


def _budget_class_for_report(report_payload: Mapping[str, Any]) -> str:
    setup = report_payload.get("setup")
    validation_lane = setup.get("validation_lane") if isinstance(setup, Mapping) else None
    return VALIDATION_LANE_BUDGET_CLASS.get(str(validation_lane), "smoke")


def _model_provider(args: argparse.Namespace) -> str:
    configured = args.model_provider.strip()
    if configured:
        return configured
    return "company-vllm" if args.validation_lane == "company-quality" else "local"


def _model_endpoint_alias(args: argparse.Namespace) -> str:
    configured = args.model_endpoint_alias.strip()
    if configured:
        return configured
    return "company-qwen35b" if args.validation_lane == "company-quality" else "local-qwen8b"


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _create_source(
    client: ApiClient,
    *,
    run_token: str,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    return client.post_json(
        "/knowledge/sources",
        {
            "name": f"Synthetic Eval {run_token}",
            "description": "API-backed synthetic corpus evaluation source.",
            "owner_department": "qa",
            "default_confidentiality_level": "internal",
        },
        headers=headers,
    )


def _upload_and_index_documents(
    client: ApiClient,
    *,
    corpus: Corpus,
    source_id: str,
    headers: Mapping[str, str],
    setup_findings: list[str],
) -> dict[str, Any]:
    corpus_to_api: dict[str, str] = {}
    api_to_corpus: dict[str, str] = {}
    index_jobs: dict[str, dict[str, Any]] = {}

    for document in corpus.documents:
        uploaded = _upload_document(
            client,
            source_id=source_id,
            document=document,
            content=build_document_markdown(document, corpus.cases).encode("utf-8"),
            headers=headers,
        )
        corpus_to_api[document.document_id] = uploaded["id"]
        api_to_corpus[uploaded["id"]] = document.document_id

        job = client.post_json(
            f"/knowledge/documents/{uploaded['id']}/index-jobs",
            {},
            headers=headers,
        )
        index_jobs[document.document_id] = {
            "api_document_id": uploaded["id"],
            "status": job.get("status"),
            "stage": job.get("stage"),
            "chunk_count": job.get("chunk_count"),
            "error_code": job.get("error_code"),
            "config_source": (job.get("config") or {}).get("source"),
        }

        if index_expected_to_succeed(document):
            if job.get("status") != "succeeded":
                setup_findings.append(
                    f"{document.document_id} index job failed: "
                    f"{job.get('error_code') or job.get('status')}"
                )
            if (job.get("config") or {}).get("source") != "object_store":
                setup_findings.append(
                    f"{document.document_id} index job did not use object_store source"
                )
        elif job.get("status") == "succeeded":
            setup_findings.append(
                f"{document.document_id} index job succeeded but corpus document is not indexable"
            )

    return {
        "corpus_to_api_document_ids": corpus_to_api,
        "api_to_corpus_document_ids": api_to_corpus,
        "index_jobs": index_jobs,
    }


def _upload_document(
    client: ApiClient,
    *,
    source_id: str,
    document: Document,
    content: bytes,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    upload_headers = {
        **headers,
        "X-Agent-Forge-Filename": upload_filename(document),
    }
    return client.post_bytes(
        "/knowledge/documents/upload",
        content,
        headers=upload_headers,
        query={
            "knowledge_source_id": source_id,
            "title": document.title,
            "confidentiality_level": document.confidentiality_level,
            "access_groups": ",".join(document_access_groups(document)),
            "effective_date": "2026-05-10",
        },
        content_type="text/markdown",
    )


def _create_agent(
    client: ApiClient,
    *,
    run_token: str,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    return client.post_json(
        "/agents",
        {
            "name": f"Synthetic Eval Agent {run_token}",
            "purpose": "Answer synthetic corpus questions with API retrieval citations.",
            "owner_department": "qa",
        },
        headers=headers,
    )


def _create_and_publish_version(
    client: ApiClient,
    *,
    agent_id: str,
    source_id: str,
    corpus: Corpus,
    document_id_map: Mapping[str, str],
    run_token: str,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    version = client.post_json(
        "/agents/versions",
        {
            "agent_id": agent_id,
            "version": 1,
            "config": {
                "citation_required": True,
                "knowledge_source_ids": [source_id],
                "eval_corpus_id": corpus.corpus_id,
                "api_to_corpus_document_ids": dict(document_id_map),
            },
        },
        headers=headers,
    )
    return client.post_json(
        f"/agents/versions/{version['id']}/publish",
        {"reason": f"API synthetic eval publish {run_token}"},
        headers=headers,
    )


def _decode_response(raw_body: bytes) -> Any:
    if not raw_body:
        return None
    text = raw_body.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


if __name__ == "__main__":
    raise SystemExit(main())
