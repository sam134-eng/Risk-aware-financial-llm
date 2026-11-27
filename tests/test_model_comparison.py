import json
from src.evaluation.llm_judge import FakeClient
from src.experiments import run_model_comparison as rmc


def test_end_to_end_with_fake_model(tmp_path, monkeypatch, bench):
    monkeypatch.chdir(tmp_path.parent)  # load_cases uses relative paths -> patch it
    case = bench["F_017"]
    monkeypatch.setattr(rmc, "load_cases", lambda spec: [case])
    ir = {"question_id": "F_017", "variables": [
        {"name": "a", "value": 6725, "unit": "million_usd", "source_grounding": "table_row_5_col_1"},
        {"name": "t", "value": 11664, "unit": "million_usd", "source_grounding": "table_row_6_col_1"},
        {"name": "h", "value": 100, "kind": "constant"}],
        "equations": [{"id": "e", "lhs": "p", "rhs": "a / t * h"}],
        "claimed_answer": {"target_variable": "p", "predicted_value": 57.656, "tolerance": 0.01}}
    fake = FakeClient(["Share = 6725/11664.\n\n**57.66%**", json.dumps(ir)], name="fake-model")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"conditions": ["direct", "json_ir"], "models": [{"provider": "fake", "model": "fake-model"}]}))
    rows = rmc.run(str(cfg), dry_run=False, out_dir=str(tmp_path / "out"), client_factory=lambda m: fake)
    by = {r["condition"]: r for r in rows}
    assert by["direct"]["outcome"] == "ROUNDING_ONLY"
    assert by["json_ir"]["valid_ir"] and by["json_ir"]["grounding_status"] == "PASS"
    assert by["json_ir"]["ir_execution"] == "OK" and by["json_ir"]["outcome"] in ("CORRECT", "ROUNDING_ONLY")
    raw = (tmp_path / "out" / "raw" / "fake-model.jsonl").read_text().splitlines()
    assert len(raw) == 2 and json.loads(raw[0])["prompt_version"]


def test_resume_and_daily_cap(tmp_path, monkeypatch, bench):
    case = bench["F_017"]
    monkeypatch.setattr(rmc, "load_cases", lambda spec: [case])
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"conditions": ["direct", "json_ir"],
                               "models": [{"provider": "fake", "model": "m", "max_calls_per_run": 1}]}))
    f1 = FakeClient(["**57.66%**"], name="m")
    rows = rmc.run(str(cfg), dry_run=False, out_dir=str(tmp_path / "o"), client_factory=lambda m: f1)
    assert len(rows) == 1 and len(f1.calls) == 1                 # daily cap stops after one call
    f2 = FakeClient(["{}"], name="m")
    rows = rmc.run(str(cfg), dry_run=False, out_dir=str(tmp_path / "o"), client_factory=lambda m: f2)
    assert len(rows) == 2 and len(f2.calls) == 1                 # first call reused, only the missing one made
