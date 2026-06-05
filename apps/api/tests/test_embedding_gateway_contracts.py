import httpx
import pytest

from app.services.embedding_gateway import (
    EmbeddingGateway,
    EmbeddingUnavailable,
)


def test_not_configured_raises():
    gw = EmbeddingGateway(base_url=None, model="bge-m3", dim=1024, timeout_seconds=5)
    with pytest.raises(EmbeddingUnavailable):
        gw.embed(["hello"])


def test_embed_calls_openai_endpoint(monkeypatch):
    captured = {}

    def fake_post(self, url, json, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    gw = EmbeddingGateway(base_url="http://x/v1", model="bge-m3", dim=3, timeout_seconds=5)
    vectors = gw.embed(["a", "b"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert captured["url"].endswith("/embeddings")
    assert captured["json"]["model"] == "bge-m3"
    assert captured["json"]["input"] == ["a", "b"]


def test_http_error_raises_unavailable(monkeypatch):
    def boom(self, url, json, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "post", boom)
    gw = EmbeddingGateway(base_url="http://x/v1", model="m", dim=3, timeout_seconds=5)
    with pytest.raises(EmbeddingUnavailable):
        gw.embed(["a"])


def test_empty_input_returns_empty_without_call():
    gw = EmbeddingGateway(base_url="http://x/v1", model="m", dim=3, timeout_seconds=5)
    assert gw.embed([]) == []
