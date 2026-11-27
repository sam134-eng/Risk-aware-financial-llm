"""Side-by-side report for the 16-case autoformalization pilot (3-shot vs 8-shot).

Needs results/ir_grounding/{3-shot,8-shot}_cases.csv (run_ir_grounding) and the raw files in
results/pilot_16/raw/. Writes results/pilot_16/pilot_comparison.md and pilot_comparison.json.
Usage: python -m src.experiments.report_pilot [--tokens-3 N --tokens-8 N --cost-usd X]
"""
from __future__ import annotations

import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path

RAW = Path("results/pilot_16/raw")
OUT = Path("results/pilot_16")


def load(k):
    rows = {r["case_id"]: r for r in csv.DictReader(open(f"results/ir_grounding/{k}-shot_cases.csv"))}
    recs = {json.loads(l)["question_id"]: json.loads(l) for l in open(RAW / f"pilot_{k}shot.jsonl")}
    val = json.loads((RAW / f"validation_{k}shot.json").read_text())
    return rows, recs, val


def text_gold_match(row) -> bool:
    """Free-text gold (manual cases): does the IR value round to a number stated in the gold text?"""
    from decimal import Decimal, ROUND_HALF_UP
    from src.grounding.numbers import find_numbers
    if not row["computed"]:
        return False
    v = Decimal(row["computed"])
    for n in find_numbers(row["gold_answer"] or ""):
        d = -n.value.as_tuple().exponent if n.value.as_tuple().exponent < 0 else 0
        if v.quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP) == n.value:
            return True
    return False


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "–"


def scale_style(rec):
    ca = (rec["ir"].get("claimed_answer") or {})
    t = (ca.get("target_variable") or "").lower()
    rhs = " ".join(e["rhs"] for e in rec["ir"]["equations"])
    if not rec["ir"]["equations"]:
        return None
    return "percent (×100)" if ("* 100" in rhs or "*100" in rhs) else "fraction"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens-3", type=int); ap.add_argument("--tokens-8", type=int)
    ap.add_argument("--cost-usd", type=float, help="total pilot cost from the OpenAI dashboard")
    ap.add_argument("--tokens-total", type=int, help="total tokens for both runs (dashboard)")
    ap.add_argument("--requests", type=int, help="total requests for both runs (dashboard)")
    a = ap.parse_args()
    runs = {k: load(k) for k in (3, 8)}
    ids = sorted(runs[3][0])
    m = {}
    for k, (rows, recs, val) in runs.items():
        rs = list(rows.values())
        for r in rs:   # manual cases with free-text gold: score against the value stated in the gold text
            if r["answer_outcome"] == "NOT_EVALUATED" and r["computed"]:
                r["computed_answer_correct"] = str(text_gold_match(r))
                r["scored_against"] = "value stated in free-text gold"
        n_vars = sum(len(r["ir"]["variables"]) for r in recs.values())
        scored = [r for r in rs if r["computed_answer_correct"] in ("True", "False")]
        clean = [r for r in scored if not r["gold_flag"]]
        m[k] = {
            "irs": len(rs),
            "validator_status": val["statuses"],
            "abstain": sum(r["primary_class"] == "ABSTAIN" for r in rs),
            "variables": n_vars,
            "grounding_pass": sum(r["grounding"] == "PASS" for r in rs),
            "grounding_errors": sum(r["grounding"] == "FAIL" for r in rs),
            "unsourced": sum(r["grounding"] == "PARTIAL" for r in rs),
            "claim_mismatch": sum(r["primary_class"] == "CLAIM_MISMATCH" for r in rs),
            "claim_mismatch_with_correct_equations": sum(r["primary_class"] == "CLAIM_MISMATCH" and
                                                         r["computed_answer_correct"] == "True" for r in rs),
            "rounded_claims": sum(r["execution"] == "OK_ROUNDED_CLAIM" for r in rs),
            "computed_correct": sum(r["computed_answer_correct"] == "True" for r in scored), "scored": len(scored),
            "computed_correct_clean_gold": sum(r["computed_answer_correct"] == "True" for r in clean),
            "scored_clean_gold": len(clean),
            "answer_errors": [r["case_id"] for r in rs if r["primary_class"] == "ANSWER_ERROR"],
            "classes": dict(Counter(r["primary_class"] for r in rs)),
            "scale_styles": dict(Counter(s for s in (scale_style(r) for r in recs.values()) if s)),
            "model": sorted({r["model"] for r in recs.values()}),
            "prompt_sha256_distinct": len({r["generation_metadata"]["prompt_sha256"] for r in recs.values()}),
        }
    diff = [(i, runs[3][0][i]["primary_class"], runs[8][0][i]["primary_class"],
             runs[3][0][i]["computed"], runs[8][0][i]["computed"])
            for i in ids if runs[3][0][i]["primary_class"] != runs[8][0][i]["primary_class"]
            or runs[3][0][i]["computed_answer_correct"] != runs[8][0][i]["computed_answer_correct"]]
    hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16] for f in sorted(RAW.iterdir())}
    L = []
    L.append("# 16-case autoformalization pilot: 3-shot vs 8-shot\n")
    L.append(f"Model `{m[3]['model'][0]}` (both runs) · run 25 Nov 2026 · runner `experiments/autoformalization/autoformalize.py` "
             "(branch `chaewon/finqa-autoformalization`) · Responses API, strict JSON schema; temperature, seed, "
             "reasoning effort and output limit left at API defaults (not a seeded / temperature-0 comparison).\n")
    L.append("## Side-by-side\n")
    L.append("| Measure | 3-shot | 8-shot |\n|---|---|---|")
    rowsmd = [
        ("Validator: structurally valid", f"{m[3]['validator_status'].get('STRUCTURALLY_VALID', 0)}/16", f"{m[8]['validator_status'].get('STRUCTURALLY_VALID', 0)}/16"),
        ("Validator: arithmetic mismatch", f"{m[3]['validator_status'].get('ARITHMETIC_MISMATCH', 0)}/16", f"{m[8]['validator_status'].get('ARITHMETIC_MISMATCH', 0)}/16"),
        ("Abstained (empty IR)", f"{m[3]['abstain']}/16", f"{m[8]['abstain']}/16"),
        ("Variables extracted", m[3]["variables"], m[8]["variables"]),
        ("Grounding PASS (IRs)", pct(m[3]["grounding_pass"], 15), pct(m[8]["grounding_pass"], 15)),
        ("Grounding errors / unsourced inputs", f"{m[3]['grounding_errors']} / {m[3]['unsourced']}", f"{m[8]['grounding_errors']} / {m[8]['unsourced']}"),
        ("Equations give claimed value", f"{15 - m[3]['claim_mismatch']}/15 ({m[3]['rounded_claims']} after rounding)", f"{15 - m[8]['claim_mismatch']}/15 ({m[8]['rounded_claims']} after rounding)"),
        ("Claim mismatches where the equations are right", f"{m[3]['claim_mismatch_with_correct_equations']}/{m[3]['claim_mismatch']}", f"{m[8]['claim_mismatch_with_correct_equations']}/{m[8]['claim_mismatch']}"),
        ("**Formalization accuracy** (IR-computed value vs gold)", pct(m[3]["computed_correct"], m[3]["scored"]), pct(m[8]["computed_correct"], m[8]["scored"])),
        ("… excluding disputed gold answers", pct(m[3]["computed_correct_clean_gold"], m[3]["scored_clean_gold"]), pct(m[8]["computed_correct_clean_gold"], m[8]["scored_clean_gold"])),
        ("Wrong metric / denominator (answer error)", ", ".join(m[3]["answer_errors"]) or "none", ", ".join(m[8]["answer_errors"]) or "none"),
        ("Output scale used for ratios", ", ".join(f"{k}: {v}" for k, v in m[3]["scale_styles"].items()), ", ".join(f"{k}: {v}" for k, v in m[8]["scale_styles"].items())),
    ]
    if a.tokens_3 or a.tokens_8:
        rowsmd.append(("Tokens (dashboard)", a.tokens_3 or "–", a.tokens_8 or "–"))
    for r in rowsmd:
        L.append(f"| {r[0]} | {r[1]} | {r[2]} |")
    if a.cost_usd is not None:
        L.append(f"\n**Usage and cost (both runs together, OpenAI dashboard, project FinVerify-Benchmark-Eval):** "
                 f"{a.requests or '–'} requests, {a.tokens_total:,} tokens, ${a.cost_usd:.2f} "
                 f"(about ${a.cost_usd / (a.requests or 32):.3f} per IR; prompt-cache hit rate 0%). "
                 "Cost = organization November spend after the runs ($0.51) minus before ($0.14). "
                 "The output records hold response IDs but no token counts, so tokens are not split by run.\n")
    else:
        L.append("\nTotal API cost of the pilot: **to add**. The output records hold response IDs but no token counts.\n")
    L.append("Formalization accuracy is scored on the 15 non-empty IRs per run. F_015 has a free-text gold answer; its "
             "IR value is compared with the amount stated there (£933.39). 'Excluding disputed gold' drops cases whose "
             "gold answer was flagged in review or disagrees with its own reference program (F_151, F_183, F_189, "
             "F_332, F_376).\n")
    L.append("## Where the runs differ\n")
    L.append("| Case | 3-shot | 8-shot | IR value 3-shot | IR value 8-shot |\n|---|---|---|---|---|")
    for d in diff:
        L.append(f"| {d[0]} | {d[1]} | {d[2]} | {d[3]} | {d[4]} |")
    L.append("\nF_089: 3-shot divides the 2019 estimate by 2017 *actual* expense (75), reproducing GPT-4o-mini's wrong "
             "denominator; 8-shot divides by the 2018–2022 schedule total (205) and gets the gold 26.3%. Its *claimed* "
             "value still copies the original answer (0.72), so the validator reports an arithmetic mismatch – the "
             "8-shot IR is more correct, not less.\n")
    L.append("## Findings\n")
    L.append("1. **No grounding errors in either run.** Every one of the 32 (3-shot) and 36 (8-shot) input variables "
             "is found in the cited cell, sentence or question text, with consistent units.")
    L.append("2. **Validator arithmetic mismatches are mostly errors in the original answer, not in the IR.** The IR "
             "formalizes the recorded GPT-4o-mini answer; in F_015 (£916.35 vs £933.39), F_027 (251,375 vs "
             "251,599.67) and F_089 (8-shot) the IR equations are right and the copied claim is wrong. F_127 and "
             "F_278 differ only by rounding/truncation and are not counted as errors here.")
    L.append("3. **8-shot fixes the one semantic error 3-shot keeps (F_089);** otherwise the runs agree case by case.")
    L.append("4. **Gold answers dispute 3 results in both runs** (F_151, F_183, F_376), matching the gold audit: the "
             "IR values are the financially correct ones for F_183 (2.78%) and F_376 (−88.64%); F_151 depends on "
             "whether 'total return' means ending value (IR: $138,290) or gain ($38,290).")
    L.append("5. **F_011 abstains in both runs because its inputs never reach the model:** the 16 manual cases keep "
             "their numbers in the benchmark's structured `evidence` field, which `prepare` does not pass on "
             "(the prompt shows an empty table and text). This should be fixed before scaling to all 500 cases.")
    L.append("6. **Scale conventions vary:** some IRs return ratios as fractions (0.2068) and others as percent "
             "(20.68), and 8-shot uses fractions more often. A fixed convention in the schema would simplify scoring.")
    L.append("\nLimitations: 16 cases, one model, one sample per configuration (API defaults, no seed), so the 3- vs "
             "8-shot difference (one case) is not statistically meaningful. Grounding shows the numbers are in the "
             "evidence, not that they are the right numbers for the question.\n")
    L.append("## Files\n")
    L.append("Raw outputs (unchanged, as produced by the runner) in `results/pilot_16/raw/` – SHA-256 prefixes: " +
             ", ".join(f"`{k}` {v}" for k, v in hashes.items()) + ".")
    L.append("Per-IR results: `results/ir_grounding/3-shot_cases.csv`, `8-shot_cases.csv`; class table: `results/ir_grounding/comparison.md`.")
    rr = {k: Path(f"results/ir_grounding/F011-rerun-{k}shot_cases.csv") for k in (3, 8)}
    if all(p.exists() for p in rr.values()):
        rer = {k: next(csv.DictReader(open(p))) for k, p in rr.items()}
        commit = (RAW.parent / "rerun_F011" / "rerun_F011_commit.txt")
        commit = commit.read_text().strip() if commit.exists() else "?"
        L.append("## F_011 rerun after the evidence fix\n")
        L.append(f"Chaewon fixed `prepare` so the manual cases' structured evidence reaches the model (commit `{commit}`). "
                 "F_011 was rerun alone (`--limit 1`) with the same model and settings, 26 Nov 2026; files in "
                 "`results/pilot_16/rerun_F011/`. Inputs were grounded against the evidence the model saw "
                 "(`pilot_inputs_v2.jsonl`).\n")
        L.append("| | 3-shot | 8-shot |\n|---|---|---|")
        for lab, key in (("Validator", None), ("Grounding", "grounding"), ("IR value (quarterly)", "computed"),
                         ("Claimed value", "claimed"), ("Class", "primary_class")):
            if key is None:
                L.append("| Validator | ARITHMETIC_MISMATCH | ARITHMETIC_MISMATCH |")
            else:
                L.append(f"| {lab} | {rer[3][key]} | {rer[8][key]} |")
        ok = {k: text_gold_match(rer[k]) for k in (3, 8)}
        L.append(f"| IR value matches gold ($9,458.51) | {'yes' if ok[3] else 'no'} | {'yes' if ok[8] else 'no'} |")
        L.append("\nThe abstention is resolved. Both IRs compute the gold values (annual $9,450.00, quarterly $9,458.51, "
                 "monthly $9,460.46); the claimed $9,469.51 is GPT-4o-mini's quarterly error carried into the claim, the "
                 "same pattern as F_015 and F_027. 8-shot also uses the 1-year duration in the exponent "
                 "(frequency × duration); 3-shot hard-codes 4 and 12.\n")
        n3 = m[3]["computed_correct"] + ok[3]; n8 = m[8]["computed_correct"] + ok[8]
        c3 = m[3]["computed_correct_clean_gold"] + ok[3]; c8 = m[8]["computed_correct_clean_gold"] + ok[8]
        L.append(f"**With the rerun F_011 included**, formalization accuracy is {n3}/16 (3-shot) vs {n8}/16 (8-shot), and "
                 f"{c3}/{m[3]['scored_clean_gold'] + 1} vs {c8}/{m[8]['scored_clean_gold'] + 1} excluding disputed gold answers. "
                 "No grounding errors in either run. F_015's input also changed with the fix (its evidence is now passed "
                 "too); its pilot IR used the numbers in the question and was not rerun.\n")
    (OUT / "pilot_comparison.md").write_text("\n".join(L) + "\n")
    (OUT / "pilot_comparison.json").write_text(json.dumps({"metrics": m, "differences": diff, "raw_sha256_16": hashes,
                                                           "tokens": {"3-shot": a.tokens_3, "8-shot": a.tokens_8, "total": a.tokens_total},
                                                           "requests": a.requests,
                                                           "cost_usd": a.cost_usd}, indent=2))
    print("\n".join(L))


if __name__ == "__main__":
    main()
