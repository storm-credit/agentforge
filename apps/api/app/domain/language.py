def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def resolve_language(language: str, question: str) -> str:
    if language in ("ko", "en"):
        return language
    return "ko" if _has_hangul(question) else "en"
