"""Ground autoformalized IRs (e.g. Chaewon's 3-shot / 8-shot outputs) and separate error types.

For every IR it reports
  grounding  – evidence grounding checker (PASS / PARTIAL / FAIL / NOT_APPLICABLE)
  execution  – deterministic execution of the IR equations vs its claimed value (OK / MISMATCH / ERROR / NO_TARGET)
  answer     – executed value vs gold (deterministic Stage B), when the IR can be executed
and assigns ONE primary error class (first that applies):
  INVALID_IR       not parseable as an IR
  GROUNDING_ERROR  a number is missing from / inconsistent with the evidence (FAIL)
  UNSOURCED_INPUT  some number has no source (PARTIAL)
  CLAIM_MISMATCH   grounded, equations execute, but they do not give the claimed value (beyond rounding);
                   when the IR formalizes a recorded answer this often exposes an arithmetic error in that answer
  LOGIC_ERROR      grounded, but the equations do not execute (undefined target, division by zero, ...)
  ANSWER_ERROR     grounded and self-consistent, but the result does not match gold (metric / period / denominator)
  GOLD_DISPUTED    as ANSWER_ERROR, but the gold answer itself is flagged (team review or gold-vs-program audit)
  NOT_SCORED       grounded and consistent, but the gold is not a single value (manual multi-part cases)
  ABSTAIN          the IR is empty (the formalizer declined)
  CORRECT          grounded, consistent and matches gold
The column computed_answer_correct scores the value the IR equations compute, independent of the class.

Input: a JSON file (list or {"results": [...]}) or JSONL, or a folder of such files.
Field names differ between pipelines, so they can be mapped:
  --id-field question_id  --vars-field variables  --value-field value  --source-field source_grounding
  --unit-field unit  --eqs-field equations  --ir-field ir   (if each record wraps the IR under a key)
  --evidence-from inputs.jsonl   ground against the evidence the model saw (runner's prepared inputs)

Usage
  python -m src.experiments.run_ir_grounding --input path\\to\\3shot_outputs --label 3-shot
  python -m src.experiments.run_ir_grounding --input path\\to\\8shot_outputs --label 8-shot
  python -m src.experiments.run_ir_grounding --compare 3-shot 8-shot
Outputs: results/ir_grounding/<label>_cases.csv, <label>_summary.json, comparison.md
"""
from __future__ import annotations

import argparse, csv, json
from collections import Counter
from pathlib import Path

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from src.evaluation.answer_evaluator import evaluate
from src.evaluation.gold_audit import REVIEW_FLAGS, gold_consistency
from src.evaluation.ir_executor import execute_ir
from src.evaluation.llm_judge import _extract_json
from src.grounding import check_grounding

OUT = Path("results/ir_grounding")
CLASSES = ["CORRECT", "GOLD_DISPUTED", "ANSWER_ERROR", "NOT_SCORED", "CLAIM_MISMATCH", "LOGIC_ERROR",
           "UNSOURCED_INPUT", "GROUNDING_ERROR", "ABSTAIN", "INVALID_IR"]
LENIENT = ("CORRECT", "ROUNDING_ONLY", "SIGN_CONVENTION")


def claimed_is_rounding(claimed, computed) -> bool:
    """True if the claimed value is the computed value rounded or truncated to the claimed precision."""
    try:
        c = Decimal(str(claimed))
    except Exception:
        return False
    d = -c.as_tuple().exponent if c.as_tuple().exponent < 0 else 0
    q = Decimal(1).scaleb(-d)
    return any(computed.quantize(q, rounding=r) == c for r in (ROUND_HALF_UP, ROUND_DOWN))


def _records(path: Path):
    files = sorted(p for p in path.rglob("*") if p.suffix in (".json", ".jsonl")) if path.is_dir() else [path]
    for f in files:
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    yield f.name, json.loads(line)
            continue
        obj = json.loads(text)
        if isinstance(obj, dict) and isinstance(obj.get("results"), list):
            obj = obj["results"]
        if isinstance(obj, dict) and isinstance(obj.get("cases"), list):
            obj = obj["cases"]
        for r in (obj if isinstance(obj, list) else [obj]):
            yield f.name, r


def normalise(rec, a):
    raw = rec.get(a.ir_field) if a.ir_field else rec
    if isinstance(raw, str):
        raw = _extract_json(raw)
    if not isinstance(raw, dict):
        return None, rec.get(a.id_field) or rec.get("case_id")
    cid = raw.get(a.id_field) or rec.get(a.id_field) or raw.get("case_id") or rec.get("case_id")
    vars_ = []
    for v in raw.get(a.vars_field) or []:
        if not isinstance(v, dict):
            continue
        nv = dict(v)
        nv["name"] = v.get("name") or v.get("id") or v.get("symbol")
        if a.value_field in v:
            nv["value"] = v[a.value_field]
        if a.source_field in v:
            nv["source_grounding"] = v[a.source_field]
        if a.unit_field in v:
            nv["unit"] = v[a.unit_field]
        vars_.append(nv)
    ir = {"question_id": cid, "variables": vars_, "equations": raw.get(a.eqs_field) or [],
          "claimed_answer": raw.get("claimed_answer") or {}}
    return ir, cid


def classify(g, ex, ans, empty=False, gold_flagged=False):
    """Primary class, first that applies (documented in the module docstring)."""
    if empty:
        return "ABSTAIN"
    if g == "FAIL":
        return "GROUNDING_ERROR"
    if g in ("PARTIAL",):
        return "UNSOURCED_INPUT"
    if ex in ("ERROR", "NO_TARGET"):
        return "LOGIC_ERROR"
    if ex == "MISMATCH":
        return "CLAIM_MISMATCH"
    if ans == "NOT_EVALUATED":
        return "NOT_SCORED"
    if ans in LENIENT:
        return "CORRECT"
    return "GOLD_DISPUTED" if gold_flagged else "ANSWER_ERROR"


def run(a):
    bench = {c["case_id"]: c for c in json.loads(Path(a.bench).read_text())}
    if getattr(a, "evidence_from", None):
        # ground against the evidence the model actually saw (e.g. pilot_inputs_v2.jsonl, where structured
        # evidence of the manual cases is rendered as "name: value [unit]" lines in pre_text)
        for line in Path(a.evidence_from).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                qid = r.get("question_id") or r.get("case_id")
                if qid in bench and isinstance(r.get("evidence"), dict):
                    bench[qid] = {**bench[qid], "evidence_context": r["evidence"]}
    rows = []
    for fname, rec in _records(Path(a.input)):
        ir, cid = normalise(rec, a)
        row = {"file": fname, "case_id": cid, "grounding": "", "grounding_errors": "", "execution": "",
               "claimed": "", "computed": "", "answer_outcome": "", "computed_answer_correct": "",
               "gold_answer": "", "gold_flag": "", "primary_class": ""}
        if ir is None or cid not in bench:
            row["primary_class"] = "INVALID_IR"
            row["grounding_errors"] = "not an IR" if ir is None else f"unknown case id {cid!r}"
            rows.append(row); continue
        case = bench[cid]
        empty = not ir["variables"] and not ir["equations"]
        g = check_grounding(ir, case)
        val, info = execute_ir(ir)
        claimed = (ir.get("claimed_answer") or {}).get("predicted_value")
        ex = info["status"]
        if ex == "MISMATCH" and val is not None and claimed_is_rounding(claimed, val):
            ex = "OK_ROUNDED_CLAIM"          # claimed value is the computed one rounded/truncated
        ans = evaluate(f"**{val}**", case["gold_answer"], question=case.get("question")).outcome if val is not None else ""
        flag = REVIEW_FLAGS.get(cid, "")
        if not flag and case.get("source_dataset") and \
                gold_consistency(case["gold_answer"], case.get("gold_reasoning") or "") == "INCONSISTENT":
            flag = "gold_answer disagrees with its own reference program"
        row.update(grounding=g.grounding_status,
                   grounding_errors=";".join(sorted({e["code"] for e in g.detailed_error_messages})),
                   execution=ex, claimed="" if claimed is None else str(claimed),
                   computed="" if val is None else f"{val:.6g}", answer_outcome=ans,
                   computed_answer_correct="" if ans in ("", "NOT_EVALUATED") else ans in LENIENT,
                   gold_answer=case.get("gold_answer"), gold_flag=flag,
                   primary_class=classify(g.grounding_status, ex if ex != "OK_ROUNDED_CLAIM" else "OK", ans,
                                          empty, bool(flag)))
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{a.label}_cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    s = {"label": a.label, "irs": len(rows), "primary_class": dict(Counter(r["primary_class"] for r in rows)),
         "grounding": dict(Counter(r["grounding"] for r in rows)),
         "execution": dict(Counter(r["execution"] for r in rows)),
         "grounding_error_codes": dict(Counter(c for r in rows for c in r["grounding_errors"].split(";") if c))}
    (OUT / f"{a.label}_summary.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=1))
    return s


def compare(labels):
    sums = [json.loads((OUT / f"{l}_summary.json").read_text()) for l in labels]
    lines = ["| Primary class | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for c in CLASSES:
        cells = []
        for s in sums:
            k = s["primary_class"].get(c, 0)
            cells.append(f"{k} ({100 * k / s['irs']:.0f}%)" if s["irs"] else "0")
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    lines.append("| Total IRs | " + " | ".join(str(s["irs"]) for s in sums) + " |")
    md = "\n".join(lines)
    (OUT / "comparison.md").write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input"); ap.add_argument("--label")
    ap.add_argument("--compare", nargs="+")
    ap.add_argument("--bench", default="data/combined_benchmark_500.json")
    ap.add_argument("--id-field", default="question_id"); ap.add_argument("--vars-field", default="variables")
    ap.add_argument("--value-field", default="value"); ap.add_argument("--source-field", default="source_grounding")
    ap.add_argument("--unit-field", default="unit"); ap.add_argument("--eqs-field", default="equations")
    ap.add_argument("--ir-field", default=None)
    ap.add_argument("--evidence-from", default=None,
                    help="JSONL of model inputs (question_id + evidence) to ground against instead of the benchmark")
    a = ap.parse_args()
    compare(a.compare) if a.compare else run(a)
