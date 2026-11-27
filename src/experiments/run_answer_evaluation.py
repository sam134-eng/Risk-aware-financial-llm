"""Stage B answer evaluation of the stored GPT-4o-mini answers (500 cases, plus the 80-case subset).

Inputs : data/combined_benchmark_500.json, results/verification_results.json,
         experiments/stage1_v2/* (Chaewon), results/grounding/stage1_v2_grounding_cases.json,
         the 80-case list in experiments/stage1_v2/FinVerify_SMT_Stage1_80_Case_Pilot.py results.
Outputs: results/evaluation/answer_eval_cases.csv, results/evaluation/answer_eval_summary.json
Usage  : python -m src.experiments.run_answer_evaluation
"""
from __future__ import annotations

import csv, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path

from src.evaluation.answer_evaluator import evaluate, parse_gold
from src.evaluation.gold_audit import REVIEW_FLAGS, gold_consistency, program_value

BENCH = Path("data/combined_benchmark_500.json")
VER = Path("results/verification_results.json")
S1 = Path("experiments/stage1_v2/FinVerify_SMT_Stage1_v2_80_Case_Results.json")
GR = Path("results/grounding/stage1_v2_grounding_cases.json")
OUT = Path("results/evaluation")

LENIENT = {"CORRECT", "ROUNDING_ONLY", "SIGN_CONVENTION"}


def reasoning_pattern(case) -> str:
    if not case.get("source_dataset"):
        return "manual_formula"
    prog = case.get("gold_reasoning") or ""
    ops = re.findall(r"(\w+)\(", prog)
    q = (case.get("question") or "").lower()
    if any(o.startswith("table_") for o in ops):
        return "table_aggregation"
    if "greater" in ops:
        return "comparison_yes_no"
    if len(ops) >= 3:
        return "multi_step"
    if ops[:2] == ["subtract", "divide"] or re.search(r"percent(age)? (change|increase|decrease|decline)|growth rate", q):
        return "percentage_change"
    if ops == ["divide"] or ops[:2] == ["divide", "multiply"]:
        return "ratio_or_share"
    if ops == ["subtract"]:
        return "difference"
    if set(ops) <= {"add"}:
        return "sum"
    if "multiply" in ops:
        return "product"
    return "other_two_step"


def acc(rows, key="lenient"):
    ev = [r for r in rows if r["outcome"] != "NOT_EVALUATED"]
    k = sum(1 for r in ev if r[key])
    return {"n": len(ev), "correct": k, "accuracy": round(k / len(ev), 4) if ev else None}


def main():
    braw, vraw = BENCH.read_bytes(), VER.read_bytes()
    bench = json.loads(braw)
    ver = json.loads(vraw)["results"]
    s1 = {c["case_id"]: c for c in json.loads(S1.read_text())["cases"]}
    gr = {c["case_id"]: c for c in json.loads(GR.read_text())} if GR.exists() else {}
    rows = []
    for c in bench:
        cid = c["case_id"]
        r = evaluate(ver[cid]["model_answer"], c["gold_answer"], question=c.get("question"))
        pv = program_value(c.get("gold_reasoning") or "") if c.get("source_dataset") else None
        gc = gold_consistency(c["gold_answer"], c.get("gold_reasoning") or "") if c.get("source_dataset") else "NOT_CHECKED"
        alt = None
        if pv is not None and r.outcome not in ("NOT_EVALUATED",) and parse_gold(c["gold_answer"]).kind != "yes_no":
            g = parse_gold(c["gold_answer"])
            alt_gold = (pv * 100) if g.kind == "percent" else pv
            alt = evaluate(ver[cid]["model_answer"], f"{alt_gold:.4f}{'%' if g.kind == 'percent' else ''}",
                           question=c.get("question")).outcome
        rows.append({
            "case_id": cid, "in_80": cid in s1, "source": c.get("source_dataset") or "manual",
            "reasoning_pattern": reasoning_pattern(c),
            "verifier_status": ver[cid]["verification"]["status"],
            "gold_answer": c["gold_answer"], "gold_program_value": None if pv is None else f"{pv:.6g}",
            "gold_consistency": gc, "review_flag": REVIEW_FLAGS.get(cid, ""),
            "predicted": r.predicted, "extraction_method": r.extraction_method,
            "outcome": r.outcome, "lenient": r.outcome in LENIENT, "strict": r.outcome == "CORRECT",
            "outcome_vs_program": alt, "note": r.note,
            "stage1_arithmetic": s1[cid]["case_arithmetic_status"] if cid in s1 else "",
            "stage1_grounding": gr[cid]["evidence_grounding"] if cid in gr else "",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "answer_eval_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def block(rs):
        clean = [r for r in rs if r["gold_consistency"] != "INCONSISTENT" and not r["review_flag"]]
        return {"lenient": acc(rs), "strict": acc(rs, "strict"), "outcomes": dict(Counter(r["outcome"] for r in rs)),
                "lenient_excluding_flagged_gold": acc(clean)}

    by_pattern = defaultdict(list)
    for r in rows:
        by_pattern[r["reasoning_pattern"]].append(r)
    by_status = defaultdict(list)
    for r in rows:
        by_status[r["verifier_status"]].append(r)
    summary = {
        "model": "gpt-4o-mini (stored answers in results/verification_results.json; decoding settings not recorded)",
        "inputs": {"benchmark_sha256": hashlib.sha256(braw).hexdigest(),
                   "verification_results_sha256": hashlib.sha256(vraw).hexdigest()},
        "all_500": block(rows),
        "finqa_484": block([r for r in rows if r["source"] == "FinQA"]),
        "selected_80": block([r for r in rows if r["in_80"]]),
        "by_verifier_status": {k: block(v) for k, v in by_status.items()},
        "by_reasoning_pattern": {k: {"n": len(v), **acc(v)} for k, v in sorted(by_pattern.items())},
        "gold_consistency_finqa": dict(Counter(r["gold_consistency"] for r in rows if r["source"] == "FinQA")),
        "gold_inconsistent_cases": [r["case_id"] for r in rows if r["gold_consistency"] == "INCONSISTENT"],
        "definitions": {"lenient": "CORRECT, ROUNDING_ONLY (<=1% rel.) or SIGN_CONVENTION",
                        "strict": "equal at the gold answer's displayed precision",
                        "excluding_flagged_gold": "drops cases whose gold_answer disagrees with its own program or that a team review flagged"},
    }
    (OUT / "answer_eval_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("all_500", "finqa_484", "selected_80")}, indent=1))
    print(json.dumps(summary["by_verifier_status"], indent=1)[:1500])
    print(summary["gold_consistency_finqa"], len(summary["gold_inconsistent_cases"]))
    return summary


if __name__ == "__main__":
    main()
