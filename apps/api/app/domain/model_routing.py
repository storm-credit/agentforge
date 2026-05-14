from __future__ import annotations

from copy import deepcopy
from typing import Any

MODEL_ROUTING_POLICY_REF = "packages/shared-contracts/model-routing-policy.v0.1.json"
DEFAULT_BUDGET_CLASS = "standard"

MODEL_TIERS = {
    "deterministic",
    "fast-small",
    "standard-rag",
    "deep-review",
    "embedding",
    "reranker",
    "safe-fallback",
}

BUDGET_CLASSES = {
    "smoke": {"deep_review_allowed": False},
    "standard": {"deep_review_allowed": True},
    "release-gate": {"deep_review_allowed": True},
    "incident": {"deep_review_allowed": True},
}

RUNTIME_MODEL_ROUTE_SUMMARY: dict[str, dict[str, Any]] = {
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

REQUIRED_RUNTIME_STAGES = tuple(RUNTIME_MODEL_ROUTE_SUMMARY.keys())

DEFAULT_AGENT_MODEL_POLICY: dict[str, Any] = {
    "routing_profile_ref": MODEL_ROUTING_POLICY_REF,
    "budget_class": DEFAULT_BUDGET_CLASS,
    "stages": RUNTIME_MODEL_ROUTE_SUMMARY,
    "fallback": {
        "on_timeout": "safe-fallback",
        "on_model_error": "safe-fallback",
        "on_policy_conflict": "deep-review",
    },
}


class ModelRoutingPolicyError(ValueError):
    pass


def runtime_model_route_summary() -> dict[str, dict[str, Any]]:
    return deepcopy(RUNTIME_MODEL_ROUTE_SUMMARY)


def default_agent_model_policy() -> dict[str, Any]:
    return deepcopy(DEFAULT_AGENT_MODEL_POLICY)


def normalize_agent_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(config or {})
    model_policy = normalized.get("model_policy")
    if model_policy is None:
        model_policy = default_agent_model_policy()
    elif not isinstance(model_policy, dict):
        raise ModelRoutingPolicyError("model_policy must be an object")
    else:
        model_policy = deepcopy(model_policy)

    policy_ref = model_policy.get("routing_profile_ref", MODEL_ROUTING_POLICY_REF)
    if policy_ref != MODEL_ROUTING_POLICY_REF:
        raise ModelRoutingPolicyError(
            f"model_policy.routing_profile_ref must be {MODEL_ROUTING_POLICY_REF}"
        )

    budget_class = model_policy.get("budget_class", DEFAULT_BUDGET_CLASS)
    stages = model_policy.get("stages")
    if stages is None:
        stages = runtime_model_route_summary()

    validate_model_route_summary(stages, budget_class=budget_class)
    model_policy["routing_profile_ref"] = policy_ref
    model_policy["budget_class"] = budget_class
    model_policy["stages"] = deepcopy(stages)
    normalized["model_policy"] = model_policy
    return normalized


def runtime_policy_from_agent_config(
    config: dict[str, Any] | None,
) -> tuple[str, dict[str, dict[str, Any]]]:
    normalized = normalize_agent_config(config)
    model_policy = normalized["model_policy"]
    return model_policy["budget_class"], deepcopy(model_policy["stages"])


def validate_model_routing_policy_ref(policy_ref: str) -> None:
    if policy_ref != MODEL_ROUTING_POLICY_REF:
        raise ModelRoutingPolicyError(f"model_routing_policy_ref must be {MODEL_ROUTING_POLICY_REF}")


def validate_budget_class(budget_class: str) -> None:
    if budget_class not in BUDGET_CLASSES:
        allowed = ", ".join(sorted(BUDGET_CLASSES))
        raise ModelRoutingPolicyError(f"budget_class must be one of: {allowed}")


def validate_model_route_summary(
    summary: dict[str, Any],
    *,
    budget_class: str,
    required_stages: tuple[str, ...] = REQUIRED_RUNTIME_STAGES,
) -> None:
    validate_budget_class(budget_class)
    if not isinstance(summary, dict):
        raise ModelRoutingPolicyError("model_route_summary must be an object")

    missing = [stage for stage in required_stages if stage not in summary]
    if missing:
        raise ModelRoutingPolicyError(
            "model_route_summary is missing runtime stages: " + ", ".join(missing)
        )

    unexpected = [stage for stage in summary if stage not in REQUIRED_RUNTIME_STAGES]
    if unexpected:
        raise ModelRoutingPolicyError(
            "model_route_summary has unknown runtime stages: " + ", ".join(unexpected)
        )

    deep_review_allowed = bool(BUDGET_CLASSES[budget_class]["deep_review_allowed"])
    for stage, route in summary.items():
        if not isinstance(route, dict):
            raise ModelRoutingPolicyError(f"model_route_summary.{stage} must be an object")

        tier = route.get("tier")
        if tier not in MODEL_TIERS:
            raise ModelRoutingPolicyError(
                f"model_route_summary.{stage}.tier must be a known model tier"
            )

        escalation_tier = route.get("escalation_tier")
        if escalation_tier is not None and escalation_tier not in MODEL_TIERS:
            raise ModelRoutingPolicyError(
                f"model_route_summary.{stage}.escalation_tier must be a known model tier"
            )

        if (
            not deep_review_allowed
            and (tier == "deep-review" or escalation_tier == "deep-review")
        ):
            raise ModelRoutingPolicyError(
                f"budget_class {budget_class} does not allow deep-review for {stage}"
            )

        uses = route.get("uses", [])
        if not isinstance(uses, list) or any(use not in MODEL_TIERS for use in uses):
            raise ModelRoutingPolicyError(
                f"model_route_summary.{stage}.uses must contain known model tiers"
            )
