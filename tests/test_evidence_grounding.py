import copy

import pytest

from src.grounding import check_grounding
from src.grounding.gold_ir import build_gold_ir


def status(ir, case, **kw):
    return check_grounding(ir, case, **kw)


# ---------------------------------------------------------------- toy cases

def test_brief_example_passes(toy_ir, toy_case):
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "PASS"
    assert r.grounded_variables == ["rev_2021", "rev_2022"]
    assert r.total_variables == 2
    t = r.variables[0]
    assert t.original_value == "$ 500" and t.source_kind == "table_cell"
    assert t.normalized_value == "500.0"
    assert "header" in t.notes[0]


def test_derived_target_is_not_ungrounded(toy_ir, toy_case):
    toy_ir["variables"].append({"name": "growth_rate", "kind": "derived"})
    assert status(toy_ir, toy_case).grounding_status == "PASS"


def test_unit_converted_correctly_passes(toy_ir, toy_case):
    toy_ir["variables"][0].update(value=500_000_000.0, unit="usd")
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "PASS"


def test_unit_declared_but_value_not_converted_fails(toy_ir, toy_case):
    toy_ir["variables"][0].update(value=500.0, unit="usd")  # says dollars, value is in millions
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "FAIL" and r.unit_errors == ["rev_2021"]


def test_scale_error_fails(toy_ir, toy_case):
    toy_ir["variables"][0]["value"] = 500_000.0
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "FAIL" and "rev_2021" in r.unit_errors


def test_value_mismatch(toy_ir, toy_case):
    toy_ir["variables"][0]["value"] = 501.0
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "FAIL" and r.mismatched_variables == ["rev_2021"]
    assert r.detailed_error_messages[0]["code"] == "VALUE_MISMATCH"


def test_invalid_reference(toy_ir, toy_case):
    toy_ir["variables"][0]["source_grounding"] = "table_row_9_col_1"
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "FAIL" and r.invalid_source_references == ["rev_2021"]
    toy_ir["variables"][0]["source_grounding"] = "cell(1,1)"
    assert "unrecognised" in status(toy_ir, toy_case).detailed_error_messages[0]["message"]


def test_missing_source_is_partial(toy_ir, toy_case):
    del toy_ir["variables"][1]["source_grounding"]
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "PARTIAL" and r.ungrounded_variables == ["rev_2022"]


def test_negative_values_and_sign_policy(toy_case):
    ir = {"question_id": "t", "variables": [
        {"name": "loss", "value": -12.5, "unit": "million_usd", "source_grounding": "table_row_2_col_1"},
        {"name": "loss22", "value": -8.0, "unit": "million_usd", "source_grounding": "table_row_2_col_2"}],
        "equations": []}
    assert status(ir, toy_case).grounding_status == "PASS"
    ir["variables"][0]["value"] = 12.5
    r = status(ir, toy_case)
    assert r.grounding_status == "FAIL"
    assert r.detailed_error_messages[0]["code"] == "SIGN_MISMATCH"
    r = status(ir, toy_case, sign_policy="warn")
    assert r.grounding_status == "PASS" and "SIGN_DIFFERS" in r.variables[0].notes[-1]


def test_percent_as_percent_or_ratio(toy_case):
    ir = {"variables": [{"name": "m", "value": 4.1, "unit": "percent", "source_grounding": "table_row_3_col_1"},
                        {"name": "m2", "value": 0.05, "unit": "ratio", "source_grounding": "table_row_3_col_2"}]}
    assert status(ir, toy_case).grounding_status == "PASS"
    ir["variables"][1]["value"] = 5.0          # says ratio but gives 5.0 for 5%
    r = status(ir, toy_case)
    assert r.grounding_status == "FAIL" and r.unit_errors == ["m2"]


def test_text_span_with_scale_word(toy_case):
    ir = {"variables": [{"name": "cash", "value": 7000.0, "unit": "million_usd", "source_grounding": "text_1"}]}
    assert status(ir, toy_case).grounding_status == "PASS"
    ir["variables"][0]["value"] = 7.0           # declares millions but copies "7.0" (billions)
    r = status(ir, toy_case)
    assert r.grounding_status == "FAIL" and r.unit_errors == ["cash"]


def test_constants_and_equation_literals(toy_ir, toy_case):
    toy_ir["variables"].append({"name": "hundred", "value": 100, "kind": "constant"})
    toy_ir["equations"][0]["rhs"] = "(rev_2022 - rev_2021) / rev_2021 * hundred"
    assert status(toy_ir, toy_case).grounding_status == "PASS"
    toy_ir["equations"][0]["rhs"] = "(rev_2022 - rev_2021) / 480"      # unexplained literal
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "PARTIAL" and r.unsupported_constants == ["eq_1:480"]


def test_undefined_variable_in_equation(toy_ir, toy_case):
    toy_ir["equations"][0]["rhs"] = "(rev_2023 - rev_2021) / rev_2021"
    r = status(toy_ir, toy_case)
    assert r.grounding_status == "PARTIAL" and "rev_2023" in r.ungrounded_variables


def test_malformed_ir_and_equation(toy_case):
    assert status({"foo": 1}, toy_case).grounding_status == "NOT_APPLICABLE"
    assert status([], toy_case).grounding_status == "NOT_APPLICABLE"
    ir = {"variables": [], "equations": [{"id": "e", "lhs": "y", "rhs": "a +"}]}
    r = status(ir, toy_case)
    assert any(e["code"] == "INVALID_EQUATION" for e in r.detailed_error_messages)


def test_only_constants_is_not_applicable(toy_case):
    ir = {"variables": [{"name": "c", "value": 100, "kind": "constant"}], "equations": []}
    assert status(ir, toy_case).grounding_status == "NOT_APPLICABLE"


def test_non_numeric_value(toy_ir, toy_case):
    toy_ir["variables"][0]["value"] = "five hundred"
    assert status(toy_ir, toy_case).mismatched_variables == ["rev_2021"]


def test_question_source_noted(toy_case):
    toy_case["question"] = "if revenue rose from $ 500 million , what ..."
    ir = {"variables": [{"name": "r", "value": 500, "unit": "", "source_grounding": "question"}]}
    r = status(ir, toy_case)
    assert r.grounding_status == "PASS" and "question text" in r.variables[0].notes[-1]


def test_deterministic(toy_ir, toy_case):
    a = status(copy.deepcopy(toy_ir), toy_case).to_dict()
    b = status(copy.deepcopy(toy_ir), toy_case).to_dict()
    assert a == b


# ---------------------------------------------------------------- real benchmark cases

def test_real_F017_cells(bench):
    c = bench["F_017"]
    ir = {"question_id": "F_017", "variables": [
        {"name": "later", "value": 6725, "unit": "million_usd", "source_grounding": "table_row_5_col_1"},
        {"name": "total", "value": 11664, "unit": "million_usd", "source_grounding": "table_row_6_col_1"}],
        "equations": [{"id": "e", "lhs": "share", "rhs": "later / total * 100"}]}
    r = check_grounding(ir, c)
    assert r.grounding_status == "PASS"
    assert r.variables[0].source_unit.startswith("currency")   # "( in millions )" found in pre_text


def test_real_F026_billion_text(bench):
    c = bench["F_026"]
    ir = {"variables": [
        {"name": "ge_cash", "value": 997, "unit": "million_usd", "source_grounding": "text_2"},
        {"name": "cash", "value": 7000, "unit": "million_usd", "source_grounding": "text_1"}]}
    assert check_grounding(ir, c).grounding_status == "PASS"
    ir["variables"][1]["value"] = 7.0          # the classic scale mistake
    r = check_grounding(ir, c)
    assert r.grounding_status == "FAIL" and r.unit_errors == ["cash"]


def test_real_F430_signed_sensitivity(bench):
    c = bench["F_430"]
    ir = {"variables": [{"name": "sens", "value": -1.7, "unit": "million_usd", "source_grounding": "table_row_2_col_1"},
                        {"name": "rate", "value": 7.75, "unit": "percent", "source_grounding": "text_18"}]}
    assert check_grounding(ir, c).grounding_status == "PASS"


def test_real_manual_structured_evidence(bench):
    c = bench["F_008"]
    ir = {"variables": [{"name": "sales", "value": 1200000, "unit": "usd", "source_grounding": "evidence.sales"},
                        {"name": "ni", "value": 96000, "unit": "usd", "source_grounding": "evidence.net_income"}]}
    assert check_grounding(ir, c).grounding_status == "PASS"
    ir["variables"][0].update(value=1.2, unit="million_usd")
    assert check_grounding(ir, c).grounding_status == "PASS"
    ir["variables"][0].update(value=1.2, unit="usd")
    assert check_grounding(ir, c).grounding_status == "FAIL"


@pytest.mark.parametrize("cid", ["F_017", "F_151", "F_183", "F_189", "F_430", "F_473"])
def test_gold_ir_regression(bench, cid):
    assert check_grounding(build_gold_ir(bench[cid]), bench[cid]).grounding_status == "PASS"


def test_gold_ir_flags_document_fact_used_as_constant(bench):
    # FinQA gold for F_026 writes the $7.0 billion as const_7: no source -> PARTIAL
    r = check_grounding(build_gold_ir(bench["F_026"]), bench["F_026"])
    assert r.grounding_status == "PARTIAL" and r.unsupported_constants
