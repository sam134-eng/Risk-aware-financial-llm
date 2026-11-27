"""Run the LLM judge (Stage A) on stored model answers and validate it.

Validation against:
  * the deterministic answer evaluator (Stage B)     -> agreement, kappa, AC1, FP/FN
  * human labels, if results/evaluation/human_labels_80.csv is filled in
  * itself across repeated runs                      -> repeat consistency
  * different judge models (run once per judge config)

Usage
  python -m src.experiments.run_judge_evaluation --config configs/models.json [--repeats 3]
  python -m src.experiments.run_judge_evaluation --dry-run      # prompt for one case, no API call
Needs a working judge API key; produces nothing without one.
"""
from __future__ import annotations

import argparse, csv, json
from dataclasses import asdict
from pathlib import Path

from src.evaluation.answer_evaluator import evaluate
from src.evaluation.judge_agreement import (bootstrap_ci, cohen_kappa, fp_fn, gwet_ac1, percent_agreement,
                                            repeat_consistency)
from src.evaluation.llm_judge import build_stage_a_prompt, judge_case
from src.experiments.run_model_comparison import load_cases, make_client

LENIENT = {"CORRECT", "ROUNDING_ONLY", "SIGN_CONVENTION"}
OUT = Path("results/judge")


def human_labels(path=Path("results/evaluation/human_labels_80.csv")):
    if not path.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(path)):
        v = (r.get("human_answer_correct") or "").strip().lower()
        if v in ("yes", "no"):
            out[r["case_id"]] = v == "yes"
    return out


def run(config_path, repeats=3, client_factory=make_client, dry_run=False):
    cases = load_cases("selected_80")
    answers = json.loads(Path("results/verification_results.json").read_text())["results"]
    if dry_run:
        c = cases[0]
        p = build_stage_a_prompt(c, answers[c["case_id"]]["model_answer"])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "dry_run_prompt.txt").write_text(p["system"] + "\n\n" + p["user"])
        print("dry run: wrote", OUT / "dry_run_prompt.txt")
        return None
    cfg = json.loads(Path(config_path).read_text())
    jm = cfg["judge"]
    client = client_factory(jm)
    OUT.mkdir(parents=True, exist_ok=True)
    runs = []
    raw_path = OUT / f"judge_raw_{jm['model'].replace('/', '_').replace(':', '_')}.jsonl"
    done = {}
    if raw_path.exists():                           # resume across days on free tiers
        for line in raw_path.read_text().splitlines():
            r = json.loads(line)
            if r.get("valid"):
                done[(r["repeat"], r["question_id"])] = r
    gap = float(jm.get("min_interval_s", 0))
    import time
    with open(raw_path, "a") as raw:
        for k in range(repeats):
            labels = {}
            for c in cases:
                if (k, c["case_id"]) in done:
                    labels[c["case_id"]] = done[(k, c["case_id"])]["judgement"]["answer_correctness"]
                    continue
                if gap:
                    time.sleep(gap)
                rec = judge_case(client, c, answers[c["case_id"]]["model_answer"],
                                 temperature=jm.get("temperature", 0.0), max_tokens=jm.get("max_tokens", 600),
                                 seed=k)
                raw.write(json.dumps({"repeat": k, **asdict(rec)}) + "\n")
                labels[c["case_id"]] = rec.judgement["answer_correctness"] if rec.valid else None
            runs.append(labels)
    ids = [c["case_id"] for c in cases]
    det = {c["case_id"]: evaluate(answers[c["case_id"]]["model_answer"], c["gold_answer"], question=c["question"])
           for c in cases}
    det_ok = [None if det[i].outcome == "NOT_EVALUATED" else det[i].outcome in LENIENT for i in ids]
    j = [None if runs[0][i] in (None, "cannot_determine", "not_applicable") else runs[0][i] == "correct" for i in ids]
    hum = human_labels()
    summary = {
        "judge_model": jm["model"], "repeats": repeats, "cases": len(ids),
        "valid_rate": sum(1 for i in ids if runs[0][i] is not None) / len(ids),
        "vs_deterministic": {"agreement": percent_agreement(j, det_ok), "kappa": cohen_kappa(j, det_ok),
                             "kappa_95ci": bootstrap_ci(j, det_ok), "ac1": gwet_ac1(j, det_ok),
                             "fp_fn": fp_fn(j, det_ok)},
        "repeat_consistency": repeat_consistency([[r[i] for i in ids] for r in runs]),
    }
    if hum:
        h = [hum.get(i) for i in ids]
        summary["vs_human"] = {"n": sum(x is not None for x in h), "agreement": percent_agreement(j, h),
                               "kappa": cohen_kappa(j, h), "ac1": gwet_ac1(j, h), "fp_fn": fp_fn(j, h)}
        summary["deterministic_vs_human"] = {"agreement": percent_agreement(det_ok, h), "kappa": cohen_kappa(det_ok, h)}
    (OUT / f"judge_summary_{jm['model'].replace('/', '_')}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/models.json")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.config, a.repeats, dry_run=a.dry_run)
