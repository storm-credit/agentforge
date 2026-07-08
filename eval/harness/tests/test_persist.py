import httpx
import pytest

from agentforge_eval.persist import (
    maybe_persist_report,
    persistence_enabled,
    resolve_label,
)

REPORT = {"total": 2, "citation_pct": 100.0, "corpus_id": "live-v0.2", "cases": []}


class _MustNotBeUsedClient:
    """Stands in for an httpx.Client; any POST attempt is a test failure."""

    def post(self, *args, **kwargs):  # pragma: no cover - reaching this IS the failure
        raise AssertionError("persistence POST attempted while disabled")


def _recording_client(handler_calls: list, status_code: int = 201, json_body: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        handler_calls.append(request)
        return httpx.Response(status_code, json=json_body if json_body is not None else {})

    return httpx.Client(
        base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
    )


def test_persistence_disabled_by_default_no_post(monkeypatch):
    monkeypatch.delenv("AGENT_FORGE_EVAL_PERSIST", raising=False)
    assert persistence_enabled() is False
    result = maybe_persist_report(
        REPORT,
        base_url="http://testserver/api/v1",
        corpus_filename="cases-live-v0.2.json",
        client=_MustNotBeUsedClient(),  # type: ignore[arg-type]
    )
    assert result is None


@pytest.mark.parametrize("value", ["false", "0", "no", "", "off"])
def test_persistence_stays_disabled_for_falsy_values(monkeypatch, value):
    monkeypatch.setenv("AGENT_FORGE_EVAL_PERSIST", value)
    assert persistence_enabled() is False


def test_persistence_enabled_posts_report_with_operator_identity(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_EVAL_PERSIST", "true")
    monkeypatch.delenv("AGENT_FORGE_EVAL_LABEL", raising=False)
    calls: list[httpx.Request] = []
    with _recording_client(calls, 201, {"id": "run-abc"}) as client:
        run_id = maybe_persist_report(
            REPORT,
            base_url="http://testserver/api/v1",
            corpus_filename="cases-live-v0.2.json",
            client=client,
        )
    assert run_id == "run-abc"
    assert len(calls) == 1
    request = calls[0]
    assert request.url.path.endswith("/eval/runs")
    # The write endpoint is privileged server-side: the operator identity must go along.
    assert request.headers["X-Agent-Forge-Roles"] == "admin"
    import json

    body = json.loads(request.content)
    assert body["corpus_id"] == "live-v0.2"  # from the report itself
    assert body["label"] == "cases-live-v0.2"  # corpus filename stem
    assert body["report"] == REPORT


def test_label_env_var_overrides_filename_stem(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_EVAL_LABEL", "pre-reranker-baseline")
    assert resolve_label("cases-live-v0.2.json") == "pre-reranker-baseline"
    monkeypatch.delenv("AGENT_FORGE_EVAL_LABEL", raising=False)
    assert resolve_label("cases-live-v0.2.json") == "cases-live-v0.2"


def test_persistence_http_error_fails_soft(monkeypatch, capsys):
    monkeypatch.setenv("AGENT_FORGE_EVAL_PERSIST", "1")
    calls: list[httpx.Request] = []
    with _recording_client(calls, 500) as client:
        result = maybe_persist_report(
            REPORT,
            base_url="http://testserver/api/v1",
            corpus_filename="cases-live-v0.2.json",
            client=client,
        )
    assert result is None  # no exception escaped, eval result unaffected
    assert len(calls) == 1
    assert "WARNING" in capsys.readouterr().err


def test_persistence_network_error_fails_soft(monkeypatch, capsys):
    monkeypatch.setenv("AGENT_FORGE_EVAL_PERSIST", "1")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("backend down")

    with httpx.Client(
        base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
    ) as client:
        result = maybe_persist_report(
            REPORT,
            base_url="http://testserver/api/v1",
            corpus_filename="cases-live-v0.2.json",
            client=client,
        )
    assert result is None
    assert "WARNING" in capsys.readouterr().err
