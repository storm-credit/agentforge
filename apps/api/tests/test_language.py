from app.domain.language import resolve_language


def test_explicit_language_wins():
    assert resolve_language("en", "안녕하세요") == "en"
    assert resolve_language("ko", "hello") == "ko"


def test_auto_detects_korean_by_hangul():
    assert resolve_language("auto", "휴가 며칠 남았나요?") == "ko"


def test_auto_defaults_english_without_hangul():
    assert resolve_language("auto", "How many leave days?") == "en"
