import httpx

from app.services.llm_gateway import ContextBlock, LLMGateway, build_messages

CTX = (ContextBlock(title="Holiday Policy", locator="Holiday Policy / lines 1-3", content="Five days paid leave per year."),)


def test_no_base_url_uses_fallback():
    gw = LLMGateway(base_url=None, model="qwen3:8b", timeout_seconds=5)
    result = gw.generate(question="휴가 며칠?", context=CTX, language="ko")
    assert result.used_llm is False
    assert result.fallback_used is True
    assert result.text


def test_empty_context_refuses_without_calling_llm():
    gw = LLMGateway(base_url="http://x/v1", model="m", timeout_seconds=5)
    result = gw.generate(question="무엇?", context=(), language="ko")
    assert result.used_llm is False
    assert "근거" in result.text or "no" in result.text.lower() or "못" in result.text


def test_generate_calls_openai_endpoint(monkeypatch):
    captured = {}

    def fake_post(self, url, json, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>x</think>5 days."}}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    gw = LLMGateway(base_url="http://x/v1", model="qwen3:8b", timeout_seconds=5)
    result = gw.generate(question="leave days?", context=CTX, language="en")
    assert result.used_llm is True
    assert result.text == "5 days."
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["model"] == "qwen3:8b"


def test_http_error_falls_back(monkeypatch):
    def boom(self, url, json, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "post", boom)
    gw = LLMGateway(base_url="http://x/v1", model="m", timeout_seconds=5)
    result = gw.generate(question="q", context=CTX, language="en")
    assert result.fallback_used is True


def test_build_messages_sets_language_and_context():
    msgs = build_messages(question="q", context=CTX, language="ko")
    assert msgs[0]["role"] == "system"
    assert "한국어" in msgs[0]["content"]
    assert "Holiday Policy / lines 1-3" in msgs[1]["content"]
