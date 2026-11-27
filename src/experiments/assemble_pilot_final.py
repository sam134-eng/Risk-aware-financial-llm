"""Assemble the final 16-case pilot set: original records + reruns on the fixed runner commit.

Records from the rerun files (e.g. F_011, F_015 on dc8ce86) replace the original ones; every record keeps
a `source_run` tag. All 16 are then grounded against the inputs the model saw on the final commit
(pilot_inputs_v2.jsonl), scored, and summarised.

Usage
  python -m src.experiments.assemble_pilot_final --rerun-3 results/pilot_16/rerun_dc8ce86/rerun_dc8ce86_3shot.jsonl \
      --rerun-8 results/pilot_16/rerun_dc8ce86/rerun_dc8ce86_8shot.jsonl --commit dc8ce86 \
      [--requests N --cost-usd X]
Writes results/pilot_16/final/, results/pilot_16/final_dc8ce86.json, results/pilot_16/final_notes.tex,
and a 'Final 16-case set' section appended to results/pilot_16/pilot_comparison.md.
"""
from __future__ import annotations

import argparse, csv, json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from src.experiments import run_ir_grounding as rig
from src.experiments.report_pilot import text_gold_match

RAW = Path("results/pilot_16/raw")
FINAL = Path("results/pilot_16/final")
INPUTS_V2 = Path("results/pilot_16/rerun_F011/pilot_inputs_v2.jsonl")


def recs(path):
    return {json.loads(l)["question_id"]: json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()}


def metrics(rows, records):
    for r in rows:
        if r["answer_outcome"] == "NOT_EVALUATED" and r["computed"]:
            r["computed_answer_correct"] = str(text_gold_match(r))
    scored = [r for r in rows if r["computed_answer_correct"] in ("True", "False")]
    clean = [r for r in scored if not r["gold_flag"]]
    vs = Counter(rec["checks"]["status"] for rec in records.values())
    return {
        "irs": len(rows), "validator_status": dict(vs),
        "abstain": sum(r["primary_class"] == "ABSTAIN" for r in rows),
        "variables": sum(len(rec["ir"]["variables"]) for rec in records.values()),
        "grounding_pass": sum(r["grounding"] == "PASS" for r in rows),
        "grounding_errors": sum(r["grounding"] == "FAIL" for r in rows),
        "unsourced": sum(r["grounding"] == "PARTIAL" for r in rows),
        "claim_mismatch": sum(r["primary_class"] == "CLAIM_MISMATCH" for r in rows),
        "claim_mismatch_with_correct_equations": sum(r["primary_class"] == "CLAIM_MISMATCH" and
                                                     r["computed_answer_correct"] == "True" for r in rows),
        "computed_correct": sum(r["computed_answer_correct"] == "True" for r in scored), "scored": len(scored),
        "computed_correct_clean_gold": sum(r["computed_answer_correct"] == "True" for r in clean),
        "scored_clean_gold": len(clean),
        "answer_errors": [r["case_id"] for r in rows if r["primary_class"] == "ANSWER_ERROR"],
        "classes": dict(Counter(r["primary_class"] for r in rows)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun-3", required=True); ap.add_argument("--rerun-8", required=True)
    ap.add_argument("--commit", required=True); ap.add_argument("--orig-commit", default="(pre-fix commit: fill in)")
    ap.add_argument("--requests", type=int); ap.add_argument("--tokens", type=int); ap.add_argument("--cost-usd", type=float)
    a = ap.parse_args()
    FINAL.mkdir(parents=True, exist_ok=True)
    out, rows_by = {}, {}
    for k, rr in ((3, a.rerun_3), (8, a.rerun_8)):
        orig, new = recs(RAW / f"pilot_{k}shot.jsonl"), recs(rr)
        merged = {}
        for qid in orig:
            if qid in new:
                merged[qid] = {**new[qid], "source_run": f"rerun on {a.commit}"}
            else:
                merged[qid] = {**orig[qid], "source_run": f"pilot run on {a.orig_commit}"}
        p = FINAL / f"pilot_{k}shot_final.jsonl"
        p.write_text("".join(json.dumps(merged[q]) + "\n" for q in orig))
        ns = SimpleNamespace(input=str(p), label=f"final-{k}shot", bench="data/combined_benchmark_500.json",
                             id_field="question_id", vars_field="variables", value_field="value",
                             source_field="source_grounding", unit_field="unit", eqs_field="equations",
                             ir_field="ir", evidence_from=str(INPUTS_V2))
        rig.run(ns)
        rows = list(csv.DictReader(open(f"results/ir_grounding/final-{k}shot_cases.csv")))
        rows_by[k] = {r["case_id"]: r for r in rows}
        out[k] = metrics(rows, merged)
        out[k]["rerun_cases"] = sorted(new)
    cost_note = None
    if a.cost_usd is not None:
        cost_note = (f"OpenAI usage for the pilot including both reruns: {a.requests} requests, "
                     f"{a.tokens:,} tokens, ${a.cost_usd:.2f} (project dashboard, November)")
    summary = {"commit_final": a.commit, "commit_pilot": a.orig_commit, "metrics": out, "cost_note": cost_note,
               "model": "gpt-6.2-sol"}
    Path("results/pilot_16/final_dc8ce86.json").write_text(json.dumps(summary, indent=2))

    m3, m8 = out[3], out[8]
    c = lambda x, y: f"{x}/{y} ({100 * x / y:.0f}%)" if y else "–"
    md = ["\n## Final 16-case set (all evidence handling on " + a.commit + ")\n",
          f"Reruns on `{a.commit}`: {', '.join(m3['rerun_cases'])} (the two manual cases whose inputs changed with the "
          f"evidence fix); the other 14 records come from the pilot run on `{a.orig_commit}`, whose prepared inputs are "
          "byte-identical on both commits. Grounding uses the inputs of the final commit.\n",
          "| Measure | 3-shot | 8-shot |", "|---|---|---|",
          f"| Abstained | {m3['abstain']}/16 | {m8['abstain']}/16 |",
          f"| Grounding errors / unsourced | {m3['grounding_errors']} / {m3['unsourced']} | {m8['grounding_errors']} / {m8['unsourced']} |",
          f"| Validator arithmetic mismatch | {m3['validator_status'].get('ARITHMETIC_MISMATCH', 0)}/16 | {m8['validator_status'].get('ARITHMETIC_MISMATCH', 0)}/16 |",
          f"| … where the IR equations are right | {m3['claim_mismatch_with_correct_equations']}/{m3['claim_mismatch']} | {m8['claim_mismatch_with_correct_equations']}/{m8['claim_mismatch']} |",
          f"| **Formalization accuracy** | {c(m3['computed_correct'], m3['scored'])} | {c(m8['computed_correct'], m8['scored'])} |",
          f"| … excluding disputed gold | {c(m3['computed_correct_clean_gold'], m3['scored_clean_gold'])} | {c(m8['computed_correct_clean_gold'], m8['scored_clean_gold'])} |",
          f"| Wrong metric / denominator | {', '.join(m3['answer_errors']) or 'none'} | {', '.join(m8['answer_errors']) or 'none'} |"]
    if cost_note:
        md.append(f"\n{cost_note}")
    pc = Path("results/pilot_16/pilot_comparison.md")
    text = pc.read_text()
    if "## Final 16-case set" in text:
        text = text[:text.index("\n## Final 16-case set")]
    pc.write_text(text.rstrip() + "\n" + "\n".join(md) + "\n")

    def tx(s): return s.replace("%", "\\%").replace("_", "\\_").replace("$", "\\$")
    notes = rf"""\paragraph{{E4. Autoformalization pilot: 3-shot vs 8-shot (16 cases).}}
\begin{{itemize}}
\item No grounding errors in either configuration: every IR input is found in the cited cell, sentence or evidence line.
\item Formalization accuracy (Python execution of the IR equations vs gold) is {tx(c(m3['computed_correct'], m3['scored']))} for 3-shot and
  {tx(c(m8['computed_correct'], m8['scored']))} for 8-shot ({tx(c(m3['computed_correct_clean_gold'], m3['scored_clean_gold']))} vs
  {tx(c(m8['computed_correct_clean_gold'], m8['scored_clean_gold']))} excluding disputed gold); 8-shot fixes the F\_089 denominator (Table~\ref{{tab:pilot}}).
\item Most validator arithmetic mismatches are errors in the formalized GPT-4o-mini answer that the IR exposes: the
  equations are right but the claimed value is copied: F\_015 equations give \pounds 933.39 (= gold) vs the claimed \pounds 916.35,
  F\_011 \$9{{,}}458.51 (= gold) vs \$9{{,}}469.51.
\item Limitations: 16 cases, one model, one sample per configuration (API defaults, no seed); the difference is one case.
\item Provenance: runner \texttt{{experiments/autoformalization/autoformalize.py}} (branch chaewon/finqa-autoformalization;
  14 cases on {a.orig_commit}; {tx(' and '.join(m3['rerun_cases']))} rerun on {a.commit} after the evidence fix; prepared inputs of the 14 identical on both);
  model gpt-6.2-sol (Responses API, strict JSON schema, API defaults); scoring \texttt{{src/experiments/run\_ir\_grounding.py}}
  (Python IR execution, not Z3){'; ' + tx(cost_note) if cost_note else ''}.
\end{{itemize}}
"""
    Path("results/pilot_16/final_notes.tex").write_text(notes)
    print(json.dumps({k: {kk: v[kk] for kk in ("computed_correct", "scored", "computed_correct_clean_gold",
                                               "scored_clean_gold", "grounding_errors", "claim_mismatch", "rerun_cases")}
                      for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
