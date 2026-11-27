"""Evidence grounding of the equations Stage 1 v2 extracted from GPT-4o-mini answers.

Reads Chaewon's case results (not modified) and the benchmark, locates every
equation input in the case evidence (src/grounding/locate.py) and writes:
  results/grounding/stage1_v2_grounding_cases.json   per input / expression / case
  results/grounding/stage1_v2_grounding_summary.json counts
Gold answers and gold programs are NOT used.

Usage: python -m src.experiments.run_stage1_grounding
"""
from __future__ import annotations

import hashlib, json, sys
from collections import Counter
from pathlib import Path

from src.grounding.locate import GROUNDED_CLASSES, evidence_index, locate_number

STAGE1 = "experiments/stage1_v2/FinVerify_SMT_Stage1_v2_80_Case_Results.json"
BENCH = "data/combined_benchmark_500.json"
OUT = Path("results/grounding")


def expression_inputs(e):
    if e["kind"] == "binary_equation":
        return list(zip(e["inputs"], e.get("input_units") or [None] * len(e["inputs"])))
    return [(e["numerator"], e.get("numerator_unit")), (e["denominator"], e.get("denominator_unit"))]


def classify_expression(classes):
    if all(c in GROUNDED_CLASSES or c == "CONSTANT" for c in classes):
        return "ALL_INPUTS_IN_EVIDENCE"
    if all(c != "NOT_FOUND" for c in classes):   # includes derived / model-intermediate inputs
        return "INPUTS_IN_OR_DERIVED_FROM_EVIDENCE"
    if any(c in GROUNDED_CLASSES or c == "DERIVED_FROM_EVIDENCE" for c in classes):
        return "SOME_INPUTS_NOT_FOUND"
    return "NO_INPUT_FOUND"


def main():
    s1_raw = Path(STAGE1).read_bytes(); b_raw = Path(BENCH).read_bytes()
    s1 = json.loads(s1_raw)
    bench = {c["case_id"]: c for c in json.loads(b_raw)}
    cases_out, input_classes, expr_classes, case_classes = [], Counter(), Counter(), Counter()
    for c in s1["cases"]:
        case = bench[c["case_id"]]
        idx = evidence_index(case)
        exprs = []
        earlier = []
        for k, e in enumerate(c["expressions"]):
            ins = []
            for val, unit in expression_inputs(e):
                r = locate_number(val, case, unit, idx, earlier_values=earlier)
                input_classes[r.match_class] += 1
                ins.append({"value": val, "unit_hint": unit, "match_class": r.match_class,
                            "evidence_refs": r.refs, "evidence_raw": r.evidence_raw, "note": r.note})
            if e.get("claimed_value") is not None:
                earlier.append(e["claimed_value"])
            ec = classify_expression([i["match_class"] for i in ins])
            expr_classes[ec] += 1
            exprs.append({"expression_index": k, "kind": e["kind"], "source_expression": e["source_expression"],
                          "arithmetic_result": e.get("solver_result"), "inputs": ins, "grounding": ec})
        if not exprs:
            cg = "NO_EXPRESSION"
        else:
            gs = [x["grounding"] for x in exprs]
            if all(g == "ALL_INPUTS_IN_EVIDENCE" for g in gs):
                cg = "ALL_INPUTS_IN_EVIDENCE"
            elif all(g in ("ALL_INPUTS_IN_EVIDENCE", "INPUTS_IN_OR_DERIVED_FROM_EVIDENCE") for g in gs):
                cg = "INPUTS_IN_OR_DERIVED_FROM_EVIDENCE"
            else:
                cg = "SOME_INPUTS_NOT_FOUND"
        case_classes[cg] += 1
        both = None
        if exprs:
            arith_ok = all(x["arithmetic_result"] == "PASS" for x in exprs)
            both = bool(arith_ok and cg in ("ALL_INPUTS_IN_EVIDENCE", "INPUTS_IN_OR_DERIVED_FROM_EVIDENCE"))
        cases_out.append({"case_id": c["case_id"], "case_arithmetic_status": c["case_arithmetic_status"],
                          "evidence_grounding": cg, "arithmetic_pass_and_inputs_supported": both,
                          "expressions": exprs})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stage1_v2_grounding_cases.json").write_text(json.dumps(cases_out, indent=1))
    summary = {
        "inputs": {"stage1_results_sha256": hashlib.sha256(s1_raw).hexdigest(),
                   "benchmark_sha256": hashlib.sha256(b_raw).hexdigest()},
        "gold_used": False,
        "cases": len(cases_out),
        "input_match_classes": dict(input_classes),
        "expression_grounding": dict(expr_classes),
        "case_grounding": dict(case_classes),
        "cases_arithmetic_pass_and_inputs_supported": sum(1 for x in cases_out if x["arithmetic_pass_and_inputs_supported"]),
        "caveat": "Inputs supported by evidence does not mean the right evidence or the right financial calculation was used.",
    }
    (OUT / "stage1_v2_grounding_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    main()
