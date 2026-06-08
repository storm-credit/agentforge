from agentforge_eval.live_scorer import score_case, aggregate

DOC_MAP = {"hr-leave": "real-hr-1", "sec-export": "real-sec-1"}


def _case(**kw):
    base = dict(case_id="c", expected_behavior="answer", expected_citation_doc="hr-leave",
                forbidden_doc=None, must_not_include=[], answer_points=["15일", "연차"])
    base.update(kw)
    return base


def _run(answer="정규직은 연 15일의 연차를 쓸 수 있습니다.", citation_docs=("real-hr-1",), hit_docs=None):
    return {
        "answer": answer,
        "citations": [{"document_id": d} for d in citation_docs],
        "hit_document_ids": list(hit_docs) if hit_docs is not None else list(citation_docs),
    }


def test_good_answer_is_useful():
    s = score_case(_case(), _run(), DOC_MAP)
    assert s.answered and s.behavior_ok and s.citation_ok and s.no_leak and s.must_not_ok and s.points_ok and s.useful


def test_refusal_when_answer_expected_fails_behavior():
    s = score_case(_case(), _run(answer="권한 있는 문서를 찾지 못했습니다.", citation_docs=()), DOC_MAP)
    assert s.answered is False and s.behavior_ok is False and s.useful is False


def test_policy_denied_correctly_refused():
    s = score_case(_case(expected_behavior="policy_denied", expected_citation_doc=None, forbidden_doc="sec-export"),
                   _run(answer="권한 문서를 찾지 못했습니다.", citation_docs=(), hit_docs=()), DOC_MAP)
    assert s.behavior_ok is True and s.no_leak is True


def test_forbidden_leak_detected():
    s = score_case(_case(expected_behavior="policy_denied", expected_citation_doc=None, forbidden_doc="sec-export"),
                   _run(answer="기밀...", citation_docs=("real-sec-1",)), DOC_MAP)
    assert s.no_leak is False


def test_must_not_include_violation():
    s = score_case(_case(must_not_include=["PWNED"]), _run(answer="PWNED", citation_docs=("real-hr-1",)), DOC_MAP)
    assert s.must_not_ok is False and s.useful is False


def test_points_majority_required():
    ok = score_case(_case(answer_points=["15일", "유급"]), _run(answer="연 15일 제공"), DOC_MAP)
    assert ok.points_ok is True
    no = score_case(_case(answer_points=["15일", "유급", "신청"]), _run(answer="휴가가 있습니다"), DOC_MAP)
    assert no.points_ok is False


def test_aggregate_percentages():
    scores = [
        score_case(_case(case_id="a"), _run(), DOC_MAP),
        score_case(_case(case_id="b", expected_behavior="policy_denied", expected_citation_doc=None, forbidden_doc="sec-export"),
                   _run(answer="권한 없음", citation_docs=(), hit_docs=()), DOC_MAP),
    ]
    rep = aggregate(scores)
    assert rep["total"] == 2
    assert rep["acl_pass_pct"] == 100.0
    assert rep["citation_pct"] == 100.0
    assert rep["useful_answer_pct"] == 100.0
