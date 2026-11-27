"""Regression + error-injection evaluation of the evidence grounding checker.

For every FinQA case whose gold program can be converted (see gold_ir.py):
  * baseline  – the reference IR should be grounded (PASS)
  * five injected errors on the first source-grounded variable:
      scale_x1000      value multiplied by 1000            -> expect FAIL (unit error)
      sign_flip        value negated                        -> expect FAIL (sign mismatch)
      transcription    last significant digit changed       -> expect FAIL (value mismatch)
      wrong_reference  source points to another evidence item that lacks the value -> expect FAIL
      missing_source   source_grounding removed             -> expect PARTIAL
      wrong_period_cited   value AND reference moved to the neighbouring cell in the same row
                       (e.g. 2010 instead of 2011) -> grounding still PASSES: this is a
                       semantic (period) error that grounding cannot detect, by design
Deterministic: no randomness; the first eligible variable / item is always used.

Usage:  python -m src.experiments.run_grounding_evaluation [benchmark.json] [out_dir]
"""
from __future__ import annotations

import copy, csv, hashlib, json, sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from src.grounding import check_grounding, resolve, SourceError
from src.grounding.gold_ir import build_gold_ir, UnsupportedProgram

EXPECT = {"baseline": "PASS", "scale_x1000": "FAIL", "sign_flip": "FAIL",
          "transcription": "FAIL", "wrong_reference": "FAIL", "missing_source": "PARTIAL",
          "wrong_period_cited": "PASS"}


def _first_source_var(ir):
    for i, v in enumerate(ir["variables"]):
        if v.get("source_grounding") and v.get("kind") != "constant" and v.get("value") not in (0, 0.0):
            return i
    return None


def _change_digit(x: float) -> float:
    d = Decimal(str(x))
    exp = d.as_tuple().exponent
    step = Decimal(1).scaleb(exp)          # one unit in the last written place
    return float(d + step)


def _wrong_ref(case, var):
    ec = case.get("evidence_context") or {}
    n_text = len((ec.get("pre_text") or []) + (ec.get("post_text") or []))
    n_tab = len(ec.get("table") or [])
    cands = [f"text_{i}" for i in range(n_text)] + [f"table_{i}" for i in range(n_tab)]
    for ref in cands:
        if ref == var["source_grounding"]:
            continue
        try:
            src = resolve(ref, case)
        except SourceError:
            continue
        if src.numbers and all(abs(n.value) != abs(Decimal(str(var["value"]))) and
                               abs(n.value) * 1000 != abs(Decimal(str(var["value"]))) for n in src.numbers):
            return ref
    return None


def perturb(ir, case, kind):
    ir = copy.deepcopy(ir)
    i = _first_source_var(ir)
    if kind == "baseline":
        return ir
    if i is None:
        return None
    v = ir["variables"][i]
    if kind == "scale_x1000":
        v["value"] = v["value"] * 1000
    elif kind == "sign_flip":
        v["value"] = -v["value"]
    elif kind == "transcription":
        v["value"] = _change_digit(v["value"])
    elif kind == "wrong_reference":
        ref = _wrong_ref(case, v)
        if ref is None:
            return None
        v["source_grounding"] = ref
    elif kind == "missing_source":
        v.pop("source_grounding")
    elif kind == "wrong_period_cited":
        import re
        m = re.match(r"table_row_(\d+)_col_(\d+)$", v["source_grounding"])
        if not m:
            return None
        r, c = int(m.group(1)), int(m.group(2))
        row = (case.get("evidence_context") or {}).get("table", [])[r]
        for c2 in [c + 1, c - 1]:
            if 1 <= c2 < len(row):
                nums = resolve(f"table_row_{r}_col_{c2}", case).numbers
                if nums and nums[0].value != Decimal(str(v["value"])):
                    v["source_grounding"] = f"table_row_{r}_col_{c2}"
                    v["value"] = float(nums[0].value)
                    return ir
        return None
    return ir


def main(bench="data/combined_benchmark_500.json", out="results/grounding"):
    raw = Path(bench).read_bytes()
    cases = json.loads(raw)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    rows, skipped = [], Counter()
    for case in cases:
        if case.get("source_dataset") != "FinQA":
            skipped["manual_case"] += 1
            continue
        try:
            ir = build_gold_ir(case)
        except UnsupportedProgram as exc:
            skipped["unsupported_program"] += 1
            continue
        for kind in EXPECT:
            p = perturb(ir, case, kind)
            if p is None:
                rows.append({"case_id": case["case_id"], "condition": kind, "status": "SKIPPED",
                             "expected": EXPECT[kind], "detected": "", "codes": ""})
                continue
            r = check_grounding(p, case)
            rows.append({"case_id": case["case_id"], "condition": kind, "status": r.grounding_status,
                         "expected": EXPECT[kind], "detected": int(r.grounding_status == EXPECT[kind]),
                         "codes": ";".join(sorted({e["code"] for e in r.detailed_error_messages}))})
    with open(out / "grounding_eval_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"benchmark_sha256": hashlib.sha256(raw).hexdigest(), "skipped_cases": dict(skipped),
               "conditions": {}}
    by = defaultdict(list)
    for r in rows:
        by[r["condition"]].append(r)
    for kind, rs in by.items():
        ev = [r for r in rs if r["status"] != "SKIPPED"]
        hit = sum(r["detected"] for r in ev)
        summary["conditions"][kind] = {
            "expected_status": EXPECT[kind], "evaluated": len(ev), "skipped": len(rs) - len(ev),
            "as_expected": hit, "rate": round(hit / len(ev), 4) if ev else None,
            "status_counts": dict(Counter(r["status"] for r in ev)),
            "not_as_expected_cases": [r["case_id"] for r in ev if not r["detected"]],
        }
    (out / "grounding_eval_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: {kk: v[kk] for kk in ("evaluated", "as_expected", "rate", "status_counts")}
                      for k, v in summary["conditions"].items()}, indent=1))
    print("skipped:", dict(skipped))
    return summary


if __name__ == "__main__":
    main(*sys.argv[1:])
