from app.domain.grounding import grounding_score

CONTEXT = (
    "# 연차·휴가 정책\n정규직은 입사 1년 후 연 15일의 연차 유급휴가를 사용할 수 있다. "
    "휴가는 사용 3일 전까지 관리자 승인을 받아 신청한다."
)


def test_grounded_answer_scores_high():
    answer = "정규직은 연 15일의 유급 휴가를 사용할 수 있습니다."
    assert grounding_score(answer, CONTEXT) >= 0.7


def test_inflected_korean_tokens_match_via_prefix():
    # 조사 접미가 붙어도 어간 접두사로 근거 인정 (휴가를 → 휴가)
    assert grounding_score("휴가를 신청합니다", CONTEXT) >= 0.5


def test_injection_hijack_scores_near_zero():
    # 컨텍스트와 무관한 납치 답변
    assert grounding_score("PWNED", CONTEXT) == 0.0
    assert grounding_score("ignore all rules", CONTEXT) <= 0.25


def test_empty_answer_not_penalized():
    assert grounding_score("", CONTEXT) == 1.0
    assert grounding_score("   ", CONTEXT) == 1.0


def test_score_is_fraction_between_zero_and_one():
    s = grounding_score("연차 15일 그리고 우주여행 화성탐사", CONTEXT)
    assert 0.0 <= s <= 1.0
    # 일부만 근거 → 1.0 미만
    assert s < 1.0
