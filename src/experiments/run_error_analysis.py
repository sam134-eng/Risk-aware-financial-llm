"""Error taxonomy for the 80 selected cases (GPT-4o-mini), from deterministic signals.

Needs: results/evaluation/answer_eval_cases.csv (run_answer_evaluation) and
results/grounding/stage1_v2_grounding_cases.json (run_stage1_grounding).
Outputs: results/analysis/error_taxonomy_80_cases.csv, error_taxonomy_80_summary.csv/.json
"""
from __future__ import annotations

import csv, json
from collections import defaultdict
from pathlib import Path

from src.evaluation.error_taxonomy import TAXONOMY, labels_for

OUT = Path("results/analysis")


def main():
    rows = [r for r in csv.DictReader(open("results/evaluation/answer_eval_cases.csv")) if r["in_80"] == "True"]
    OUT.mkdir(parents=True, exist_ok=True)
    per_case, by_label = [], defaultdict(list)
    for r in rows:
        labs = labels_for(r)
        for l in labs:
            by_label[l].append(r["case_id"])
        per_case.append({"case_id": r["case_id"], "outcome": r["outcome"], "lenient_correct": r["lenient"],
                         "labels": ";".join(labs), "review_flag": r["review_flag"],
                         "stage1_arithmetic": r["stage1_arithmetic"], "stage1_grounding": r["stage1_grounding"]})
    with open(OUT / "error_taxonomy_80_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_case[0])); w.writeheader(); w.writerows(per_case)
    n = len(rows)
    summ = []
    for key, (group, desc, det, review) in TAXONOMY.items():
        ids = by_label.get(key, [])
        summ.append({"group": group, "label": key, "description": desc, "cases": len(ids),
                     "percent_of_80": round(100 * len(ids) / n, 1), "model": "gpt-4o-mini", "detected_by": det,
                     "needs_human_review": review, "example_cases": ", ".join(ids[:5])})
    with open(OUT / "error_taxonomy_80_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0])); w.writeheader(); w.writerows(summ)
    # arithmetic correctness vs financial correctness on cases with extracted equations
    eq = [r for r in rows if r["stage1_arithmetic"] in ("ALL_CHECKED_PASS", "ARITHMETIC_FAIL_PRESENT")]
    cross = defaultdict(lambda: {"cases": 0, "answer_correct": 0})
    for r in eq:
        k = (r["stage1_arithmetic"], "inputs_supported" if r["stage1_grounding"] in
             ("ALL_INPUTS_IN_EVIDENCE", "INPUTS_IN_OR_DERIVED_FROM_EVIDENCE") else "some_inputs_not_found")
        cross[k]["cases"] += 1
        cross[k]["answer_correct"] += r["lenient"] == "True"
    ver = defaultdict(lambda: {"cases": 0, "answer_correct": 0})
    for r in csv.DictReader(open("results/evaluation/answer_eval_cases.csv")):
        if r["outcome"] == "NOT_EVALUATED":
            continue
        ver[r["verifier_status"]]["cases"] += 1
        ver[r["verifier_status"]]["answer_correct"] += r["lenient"] == "True"
    out = {"n_cases": n, "labels": {s["label"]: s["cases"] for s in summ},
           "cases_with_no_label_and_correct": sum(1 for p in per_case if p["lenient_correct"] == "True" and not [
               l for l in p["labels"].split(";") if l and l != "not_formalizable_by_stage1"]),
           "arithmetic_vs_answer_on_extracted_equations": {f"{a}|{g}": v for (a, g), v in cross.items()},
           "original_verifier_status_vs_answer_correct_500": dict(ver)}
    (OUT / "error_taxonomy_80_summary.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
