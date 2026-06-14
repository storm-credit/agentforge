from app.services.reranker import NoopReranker, get_reranker


def test_noop_preserves_order_and_content():
    r = NoopReranker()
    assert r.rerank("q", ["a", "b", "c"]) == ("a", "b", "c")
    assert r.name == "none"


def test_get_reranker_default_is_noop():
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_reranker.cache_clear()
    r = get_reranker()
    assert isinstance(r, NoopReranker)
    assert r.name == "none"


def test_unknown_backend_falls_back_to_noop(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AGENT_FORGE_RERANK_BACKEND", "vllm")
    get_settings.cache_clear()
    get_reranker.cache_clear()
    try:
        assert isinstance(get_reranker(), NoopReranker)
    finally:
        get_settings.cache_clear()
        get_reranker.cache_clear()
