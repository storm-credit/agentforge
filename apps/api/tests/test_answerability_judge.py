from app.services.answerability_judge import (
    LlmAnswerabilityJudge,
    NoopJudge,
    get_judge,
)
from app.services.llm_gateway import ContextBlock

_CTX = (ContextBlock(title="T", locator="T / l1", content="some content"),)


def test_noop_judge_always_answerable():
    j = NoopJudge()
    assert j.is_answerable("q", _CTX) is True
    assert j.name == "none"


class _FakeGateway:
    def __init__(self, verdict):
        self._verdict = verdict

    def judge_answerable(self, *, question, context):
        return self._verdict


def test_llm_judge_returns_gateway_verdict():
    assert LlmAnswerabilityJudge(_FakeGateway(True)).is_answerable("q", _CTX) is True
    assert LlmAnswerabilityJudge(_FakeGateway(False)).is_answerable("q", _CTX) is False


def test_llm_judge_fails_open_on_none():
    # no verdict (gateway offline / unparseable) must not block a valid answer
    assert LlmAnswerabilityJudge(_FakeGateway(None)).is_answerable("q", _CTX) is True


def test_get_judge_default_is_noop():
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_judge.cache_clear()
    assert isinstance(get_judge(), NoopJudge)
