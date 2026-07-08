from app.domain.vector import VectorHit
from app.services.reranker import HybridLexicalReranker, NoopReranker, get_reranker


def _hit(chunk_id: str, score: float, rank: int) -> VectorHit:
    return VectorHit(
        document_id=f"doc-{chunk_id}",
        knowledge_source_id="ks-1",
        title=f"Title {chunk_id}",
        confidentiality_level="internal",
        access_groups=("all-employees",),
        score=score,
        citation=f"Title {chunk_id} > s1",
        rank_original=rank,
        chunk_id=chunk_id,
        citation_locator=f"Title {chunk_id} > s1",
    )


def test_noop_preserves_order_and_content():
    r = NoopReranker()
    assert r.rerank("q", ["a", "b", "c"]) == ("a", "b", "c")
    assert r.name == "none"


def test_noop_ignores_content_map():
    # Regression guard: the added content_by_chunk_id argument must not change
    # NoopReranker behavior in any way.
    r = NoopReranker()
    hits = [_hit("c1", 0.9, 1), _hit("c2", 0.5, 2)]
    assert r.rerank("query", hits, {"c1": "x", "c2": "query query query"}) == tuple(hits)
    assert r.rerank("query", hits, None) == tuple(hits)


def test_get_reranker_default_is_noop():
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_reranker.cache_clear()
    r = get_reranker()
    assert isinstance(r, NoopReranker)
    assert r.name == "none"


def test_unrecognized_rerank_backend_env_value_is_rejected_at_boot(monkeypatch):
    """rerank_backend is a Literal["none", "hybrid_lexical"]; a typo'd/unsupported
    env value (e.g. a not-yet-wired "vllm") must fail Settings construction loudly
    rather than silently booting on a fallback the operator didn't ask for."""
    import pytest

    from app.core.config import Settings, get_settings

    monkeypatch.setenv("AGENT_FORGE_RERANK_BACKEND", "vllm")
    get_settings.cache_clear()
    try:
        with pytest.raises(Exception, match="rerank_backend"):
            Settings()
    finally:
        get_settings.cache_clear()


def test_unknown_backend_on_existing_settings_falls_back_to_noop(monkeypatch):
    """get_reranker()'s own warn-and-fallback branch (for a backend value it doesn't
    implement) stays as defense-in-depth even though Literal validation now blocks
    that value at construction time -- exercised here via direct attribute mutation
    on an already-constructed Settings instance, the same pattern test_health.py
    uses for its backend-swap tests."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rerank_backend", "vllm")
    get_reranker.cache_clear()
    try:
        assert isinstance(get_reranker(), NoopReranker)
    finally:
        get_reranker.cache_clear()


def test_get_reranker_hybrid_lexical_backend(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AGENT_FORGE_RERANK_BACKEND", "hybrid_lexical")
    get_settings.cache_clear()
    get_reranker.cache_clear()
    try:
        r = get_reranker()
        assert isinstance(r, HybridLexicalReranker)
        assert r.name == "hybrid_lexical"
    finally:
        get_settings.cache_clear()
        get_reranker.cache_clear()


def test_hybrid_promotes_lexically_stronger_hit():
    # Hit "c1" wins on vector score but its content is off-topic; "c2" is second on
    # vector score but matches the query terms strongly. RRF must promote "c2".
    # Note: a mere 1<->2 swap between the two signals is RRF-symmetric (tie, broken
    # toward vector order), so c1 must fall to lexical rank 3 — i.e. the lexical
    # evidence must outweigh the vector gap for the order to actually change.
    r = HybridLexicalReranker()
    hits = [_hit("c1", 0.90, 1), _hit("c2", 0.80, 2), _hit("c3", 0.70, 3)]
    contents = {
        "c1": "사내 식당 운영 시간 안내",  # zero query-term overlap -> lexical rank 3
        "c2": "연차 휴가 부여 일수: 연차 휴가 는 15일",  # strong overlap -> lexical rank 1
        "c3": "휴가 복지 제도 개요",  # weak overlap -> lexical rank 2
    }
    ranked = r.rerank("연차 휴가 며칠 부여", hits, contents)
    assert [h.chunk_id for h in ranked] == ["c2", "c1", "c3"]
    # rank_original on the hit objects is untouched (frozen dataclass, reorder only)
    assert {h.chunk_id: h.rank_original for h in ranked} == {"c1": 1, "c2": 2, "c3": 3}
    assert set(ranked) == set(hits)


def test_hybrid_preserves_order_without_content():
    # No content map (or empty) -> lexical signal is uniform -> ties break toward
    # the vector order, so output == input. Safe degradation.
    r = HybridLexicalReranker()
    hits = [_hit("c1", 0.9, 1), _hit("c2", 0.8, 2), _hit("c3", 0.7, 3)]
    assert r.rerank("연차 휴가", hits, None) == tuple(hits)
    assert r.rerank("연차 휴가", hits, {}) == tuple(hits)


def test_hybrid_preserves_order_when_lexical_agrees_with_vector():
    r = HybridLexicalReranker()
    hits = [_hit("c1", 0.9, 1), _hit("c2", 0.8, 2)]
    contents = {"c1": "연차 휴가 규정 연차 휴가", "c2": "식당 안내"}
    assert r.rerank("연차 휴가", hits, contents) == tuple(hits)


def test_hybrid_is_deterministic_and_handles_edge_cases():
    r = HybridLexicalReranker()
    hits = [_hit("c1", 0.9, 1), _hit("c2", 0.8, 2), _hit("c3", 0.7, 3)]
    contents = {"c1": "b b b", "c2": "a a a a", "c3": "a b"}
    first = r.rerank("a b", hits, contents)
    second = r.rerank("a b", hits, contents)
    assert first == second
    # empty query and single/empty hit lists never crash
    assert r.rerank("", hits, contents) == tuple(hits)
    assert r.rerank("a", hits[:1], contents) == (hits[0],)
    assert r.rerank("a", [], contents) == ()
