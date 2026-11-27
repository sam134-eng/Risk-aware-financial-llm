import json, sys
from types import SimpleNamespace
from src.experiments import run_ir_grounding as rig


def ir(value, src="table_row_5_col_1", claimed=57.656):
    return {"question_id": "F_017",
            "variables": [{"name": "a", "value": value, "unit": "million_usd", "source_grounding": src},
                          {"name": "t", "value": 11664, "unit": "million_usd", "source_grounding": "table_row_6_col_1"},
                          {"name": "h", "value": 100, "kind": "constant"}],
            "equations": [{"id": "e", "lhs": "p", "rhs": "a / t * h"}],
            "claimed_answer": {"target_variable": "p", "predicted_value": claimed, "tolerance": 0.01}}


def test_classes(tmp_path, monkeypatch):
    monkeypatch.setattr(rig, "OUT", tmp_path / "out")
    recs = [ir(6725), ir(6725000), ir(6725, claimed=99), {"output": "not json"},
            {"question_id": "F_017", "variables": [{"name": "a", "value": 1}], "equations": [],
             "claimed_answer": {"target_variable": "a", "predicted_value": 1}}]
    p = tmp_path / "irs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs))
    a = SimpleNamespace(input=str(p), label="t", bench="data/combined_benchmark_500.json", id_field="question_id",
                        vars_field="variables", value_field="value", source_field="source_grounding",
                        unit_field="unit", eqs_field="equations", ir_field=None)
    s = rig.run(a)
    rows = list(__import__("csv").DictReader(open(tmp_path / "out" / "t_cases.csv")))
    assert [r["primary_class"] for r in rows] == ["CORRECT", "GROUNDING_ERROR", "CLAIM_MISMATCH", "INVALID_IR",
                                                  "UNSOURCED_INPUT"]
    rig.compare(["t"])
    assert "GROUNDING_ERROR" in (tmp_path / "out" / "comparison.md").read_text()


def test_new_classes(tmp_path, monkeypatch):
    monkeypatch.setattr(rig, "OUT", tmp_path / "out")
    abstain = {"question_id": "F_017", "ir": {"question_id": "F_017", "variables": [], "equations": [],
                                              "claimed_answer": None}}
    rounded = {"question_id": "F_017", "ir": ir(6725, claimed=57.65)}          # truncated claim -> not a mismatch
    rounded["ir"]["claimed_answer"]["tolerance"] = 0.0001
    disputed = {"question_id": "F_376", "ir": {
        "question_id": "F_376",
        "variables": [{"name": "a", "value": 8.8, "unit": "millions", "source_grounding": "table_row_2_col_2"},
                      {"name": "b", "value": 1.0, "unit": "millions", "source_grounding": "table_row_2_col_1"},
                      {"name": "h", "value": 100, "kind": "constant"}],
        "equations": [{"id": "e", "lhs": "p", "rhs": "(b - a) / a * h"}],
        "claimed_answer": {"target_variable": "p", "predicted_value": -88.64, "tolerance": 0.005}}}
    p = tmp_path / "x.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in (abstain, rounded, disputed)))
    a = SimpleNamespace(input=str(p), label="n", bench="data/combined_benchmark_500.json", id_field="question_id",
                        vars_field="variables", value_field="value", source_field="source_grounding",
                        unit_field="unit", eqs_field="equations", ir_field="ir")
    rig.run(a)
    rows = list(__import__("csv").DictReader(open(tmp_path / "out" / "n_cases.csv")))
    assert [r["primary_class"] for r in rows] == ["ABSTAIN", "CORRECT", "GOLD_DISPUTED"]
    assert rows[1]["execution"] == "OK_ROUNDED_CLAIM"


def test_sign_with_fraction_for_percent():
    from src.evaluation.answer_evaluator import evaluate
    assert evaluate("**0.038**", "-3.8%", question="what was the percentage decline").outcome == "SIGN_CONVENTION"


def test_evidence_from_model_inputs(tmp_path, monkeypatch):
    """Manual case F_011: ground against the evidence lines the model saw (pilot_inputs_v2)."""
    monkeypatch.setattr(rig, "OUT", tmp_path / "out")
    inputs = tmp_path / "inputs.jsonl"
    inputs.write_text(json.dumps({"question_id": "F_011", "evidence": {
        "pre_text": ["principal: 9000 [USD]", "nominal_annual_interest_rate: 0.05 [decimal_rate]"],
        "table": [], "post_text": []}}))
    rec = {"question_id": "F_011", "ir": {"question_id": "F_011", "variables": [
        {"name": "p", "value": 9000, "unit": "USD", "source_grounding": "pre_text_0"},
        {"name": "r", "value": 0.05, "unit": "decimal_rate", "source_grounding": "pre_text_1"}],
        "equations": [{"id": "e", "lhs": "fv", "rhs": "p * (1 + r / 4) ** 4"}],
        "claimed_answer": {"target_variable": "fv", "predicted_value": 9469.51, "tolerance": 0.01}}}
    p = tmp_path / "ir.jsonl"
    p.write_text(json.dumps(rec))
    a = SimpleNamespace(input=str(p), label="e", bench="data/combined_benchmark_500.json", id_field="question_id",
                        vars_field="variables", value_field="value", source_field="source_grounding",
                        unit_field="unit", eqs_field="equations", ir_field="ir", evidence_from=str(inputs))
    rig.run(a)
    row = next(__import__("csv").DictReader(open(tmp_path / "out" / "e_cases.csv")))
    assert row["grounding"] == "PASS" and row["primary_class"] == "CLAIM_MISMATCH" and row["computed"] == "9458.51"
