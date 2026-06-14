from app.domain.pii import mask_pii


def test_masks_korean_rrn():
    masked, changed = mask_pii("주민번호 900101-1234567 입니다")
    assert "900101-1234567" not in masked
    assert "[REDACTED:RRN]" in masked
    assert changed is True


def test_masks_email():
    masked, changed = mask_pii("연락처 hong.gildong@corp.co.kr 로 회신")
    assert "hong.gildong@corp.co.kr" not in masked
    assert "[REDACTED:EMAIL]" in masked
    assert changed is True


def test_masks_korean_mobile_phone():
    for raw in ("010-1234-5678", "01012345678"):
        masked, changed = mask_pii(f"전화 {raw}")
        assert raw not in masked
        assert "[REDACTED:PHONE]" in masked
        assert changed is True


def test_masks_card_number():
    masked, changed = mask_pii("카드 1234-5678-9012-3456")
    assert "1234-5678-9012-3456" not in masked
    assert "[REDACTED:CARD]" in masked
    assert changed is True


def test_clean_text_unchanged():
    text = "연 5일 유급 휴가가 제공됩니다."
    masked, changed = mask_pii(text)
    assert masked == text
    assert changed is False


def test_empty_text_is_safe():
    assert mask_pii("") == ("", False)


def test_masks_multiple_pii_in_one_string():
    masked, changed = mask_pii("hong@corp.com / 010-1234-5678 / 900101-1234567")
    assert changed is True
    assert "[REDACTED:EMAIL]" in masked
    assert "[REDACTED:PHONE]" in masked
    assert "[REDACTED:RRN]" in masked
    assert "@corp.com" not in masked
