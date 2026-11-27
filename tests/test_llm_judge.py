import copy, json
import pytest
from src.evaluation.llm_judge import (FakeClient, build_stage_a_prompt, judge_case, validate_judgement,
                                      DIMENSIONS)
from src.evaluation.judge_agreement import (cohen_kappa, gwet_ac1, fp_fn, percent_agreement,
                                            repeat_consistency, bootstrap_ci)


def good(qid="F_017", **kw):
    d = {"question_id": qid, **{k: "correct" for k in DIMENSIONS}, "overall_reasoning_quality": 4,
         "errors": [], "explanation": "ok"}
    d.update(kw)
    return json.dumps(d)


def test_prompt_has_no_gold_and_is_invariant_to_gold(bench):
    c = bench["F_017"]
    p = build_stage_a_prompt(c, "answer text")
    assert c["gold_reasoning"] not in p["user"]
    c2 = copy.deepcopy(c)
    c2["gold_answer"], c2["gold_reasoning"], c2["gold_numeric"] = "999%", "add(1, 2)", 999
    assert build_stage_a_prompt(c2, "answer text") == p
    assert "[row 5] 2018 and thereafter | 6725" in p["user"]


def test_validation():
    assert validate_judgement(json.loads(good())) == []
    bad = json.loads(good(answer_correctness="mostly"))
    assert any("invalid label" in e for e in validate_judgement(bad))
    assert validate_judgement(json.loads(good(overall_reasoning_quality=7)))
    assert validate_judgement(json.loads(good(errors=["made_up"])))
    assert validate_judgement({"question_id": "x"})
    assert validate_judgement(json.loads(good()), "F_999") == ["question_id mismatch"]


def test_retry_then_valid(bench):
    cl = FakeClient(["not json", "```json\n" + good() + "\n```"])
    r = judge_case(cl, bench["F_017"], "ans", backoff_s=0)
    assert r.valid and r.attempt_count == 2 and len(r.raw_outputs) == 2
    assert "previous reply was invalid" in cl.calls[1]["user"]


def test_api_error_then_invalid(bench):
    cl = FakeClient([RuntimeError("timeout"), good(answer_correctness="??"), "{}"])
    r = judge_case(cl, bench["F_017"], "ans", backoff_s=0)
    assert not r.valid and r.judgement is None and r.attempt_count == 3


def test_agreement_stats():
    a = [True, True, False, False, True, None]
    b = [True, False, False, False, True, True]
    assert percent_agreement(a, b) == 0.8
    assert round(cohen_kappa(a, b), 4) == round((0.8 - 0.48) / 0.52, 4)
    assert gwet_ac1([1, 1, 1], [1, 1, 1]) == 1.0
    assert fp_fn([True, True, False], [True, False, True]) == {"TP": 1, "FP": 1, "FN": 1, "TN": 0}
    assert repeat_consistency([["c", "i"], ["c", "c"]]) == 0.5
    lo, hi = bootstrap_ci(a, b)
    assert lo <= hi
