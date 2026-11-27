"""Multi-LLM comparison runner (same cases, same prompts, same evaluation for every model).

Conditions
  direct   – free-text answer                     -> deterministic answer evaluator
  json_ir  – JSON IR with source references       -> IR validity, grounding checker,
                                                     IR execution, answer evaluator
Per call it records model, prompt version, decoding parameters, latency, tokens,
raw output (results/model_comparison/raw/*.jsonl) and parsed/evaluated rows.

Usage
  python -m src.experiments.run_model_comparison --config configs/models.json            # real run (needs keys)
  python -m src.experiments.run_model_comparison --config configs/models.example.json --dry-run
                                                       # writes prompts only, no API calls
No results are produced without working API credentials.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, time
from pathlib import Path
from typing import Any, Dict, List

from src.evaluation.answer_evaluator import evaluate
from src.evaluation.ir_executor import execute_ir
from src.evaluation.llm_judge import format_evidence, _extract_json
from src.grounding import check_grounding

PROMPT_VERSION = "answer-v1/ir-v1"
SYSTEM = "You are a careful financial analyst. Use only the evidence provided."

DIRECT = """Question: {question}

Evidence:
{evidence}

Answer the question. Show the calculation, then give the final answer in bold on the last line."""

IR = """Question: {question}

Evidence (row/text ids are source references):
{evidence}

Return ONLY a JSON object:
{{"question_id": "{qid}",
 "variables": [{{"name": "...", "value": <number as written in the evidence, converted only if you state the unit>,
                "unit": "usd|thousand_usd|million_usd|billion_usd|percent|ratio|shares|count",
                "source_grounding": "table_row_R_col_C | text_N | question"}}],
 "equations": [{{"id": "eq_1", "lhs": "<name>", "rhs": "<arithmetic over variable names>"}}],
 "claimed_answer": {{"target_variable": "<name>", "predicted_value": <number>, "tolerance": 0.01}}}}
Rows are numbered from 0 including the header row; columns from 0 including the label column."""


def load_cases(spec: str, bench_path="data/combined_benchmark_500.json",
               s1="experiments/stage1_v2/FinVerify_SMT_Stage1_v2_80_Case_Results.json") -> List[Dict]:
    bench = json.loads(Path(bench_path).read_text())
    if spec == "selected_80":
        ids = {c["case_id"] for c in json.loads(Path(s1).read_text())["cases"]}
        return [c for c in bench if c["case_id"] in ids]
    if spec == "all":
        return bench
    ids = set(spec.split(","))
    return [c for c in bench if c["case_id"] in ids]


def make_client(m: Dict[str, Any]):
    from src.evaluation.llm_judge import AnthropicClient, OpenAIChatClient
    if m["provider"] in ("openai", "openai_compatible", "ollama", "google_ai_studio", "openrouter", "groq"):
        defaults = {"ollama": ("http://localhost:11434/v1", None),
                    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
                    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
                    "google_ai_studio": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY")}
        url, env = defaults.get(m["provider"], (None, "OPENAI_API_KEY"))
        extra = {"reasoning_effort": m["reasoning_effort"]} if m.get("reasoning_effort") else None
        return OpenAIChatClient(m["model"], m.get("api_key_env", env), m.get("base_url", url), extra,
                                token_param=m.get("token_param", "max_tokens"),
                                send_temperature=m.get("temperature") is not None)
    if m["provider"] == "anthropic":
        return AnthropicClient(m["model"], m.get("api_key_env", "FINVERIFY_ANTHROPIC_API_KEY"))
    raise ValueError(f"unknown provider {m['provider']}")


def build_prompt(case, condition) -> Dict[str, str]:
    tpl = DIRECT if condition == "direct" else IR
    return {"system": SYSTEM, "user": tpl.format(question=case["question"], evidence=format_evidence(case),
                                                 qid=case["case_id"])}


def evaluate_output(case, condition, text) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    if condition == "direct":
        r = evaluate(text, case["gold_answer"], question=case.get("question"))
        row.update(outcome=r.outcome, predicted=r.predicted)
        return row
    ir = _extract_json(text)
    row["valid_ir"] = isinstance(ir, dict) and isinstance(ir.get("variables"), list)
    if not row["valid_ir"]:
        row.update(outcome="INVALID_IR")
        return row
    g = check_grounding(ir, case)
    row["grounding_status"] = g.grounding_status
    row["grounding_errors"] = ";".join(sorted({e["code"] for e in g.detailed_error_messages}))
    val, info = execute_ir(ir)
    row["ir_execution"] = info["status"]
    if val is None:
        row.update(outcome="IR_NOT_EXECUTABLE")
        return row
    r = evaluate(f"**{val}**", case["gold_answer"], question=case.get("question"))
    row.update(outcome=r.outcome, predicted=str(val))
    return row


def run(config_path: str, dry_run: bool, out_dir="results/model_comparison", client_factory=make_client,
        cases_override: str = None, only_model: str = None):
    cfg = json.loads(Path(config_path).read_text())
    cases = load_cases(cases_override or cfg.get("cases", "selected_80"))
    if only_model:
        cfg["models"] = [m for m in cfg["models"] if only_model in m["model"]]
    out = Path(out_dir)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    if dry_run:
        p = out / "dry_run_prompts.jsonl"
        with open(p, "w") as f:
            for c in cases[:3]:
                for cond in cfg["conditions"]:
                    f.write(json.dumps({"case_id": c["case_id"], "condition": cond, **build_prompt(c, cond)}) + "\n")
        print(f"dry run: wrote example prompts for {min(3, len(cases))} cases to {p}; no API calls made")
        return []
    rows = []
    for m in cfg["models"]:
        client = client_factory(m)
        raw_path = out / "raw" / f"{re.sub(r'[^A-Za-z0-9._-]', '_', m['model'])}.jsonl"
        done = {}
        if raw_path.exists():                       # resume: reuse successful calls from earlier runs
            for line in raw_path.read_text().splitlines():
                r = json.loads(line)
                if not r.get("error"):
                    done[(r["case_id"], r["condition"])] = r
        gap = float(m.get("min_interval_s", cfg.get("min_interval_s", 0)))   # free tiers: e.g. 3.5 s for 20 req/min
        max_calls = m.get("max_calls_per_run")                              # free tiers: daily request cap
        calls = 0
        with open(raw_path, "a") as raw:
            for c in cases:
                for cond in cfg["conditions"]:
                    if (c["case_id"], cond) in done:
                        rec = done[(c["case_id"], cond)]
                        row = {k: rec.get(k) for k in ("case_id", "model", "condition", "latency_s", "input_tokens",
                                                       "output_tokens", "error")}
                        row.update(evaluate_output(c, cond, rec["output"]))
                        rows.append(row)
                        continue
                    if max_calls is not None and calls >= max_calls:
                        continue
                    if calls and gap:
                        time.sleep(gap)
                    calls += 1
                    pr = build_prompt(c, cond)
                    t0 = time.time()
                    try:
                        o = client.complete(pr["system"], pr["user"], temperature=m.get("temperature"),
                                            max_tokens=m.get("max_tokens", 900), seed=cfg.get("seed", 0))
                        text, err = o.get("text", ""), ""
                    except Exception as exc:
                        o, text, err = {}, "", f"{type(exc).__name__}: {exc}"
                    lat = round(time.time() - t0, 3)
                    rec = {"case_id": c["case_id"], "model": m["model"], "provider": m["provider"],
                           "reasoning_effort": m.get("reasoning_effort"),
                           "condition": cond, "prompt_version": cfg.get("prompt_version", PROMPT_VERSION),
                           "temperature": m.get("temperature", 0.0), "max_tokens": m.get("max_tokens", 900),
                           "seed": cfg.get("seed", 0), "latency_s": lat,
                           "input_tokens": o.get("input_tokens"), "output_tokens": o.get("output_tokens"),
                           "error": err, "output": text,
                           "prompt_sha256": hashlib.sha256(pr["user"].encode()).hexdigest()[:16]}
                    raw.write(json.dumps(rec) + "\n")
                    row = {k: rec[k] for k in ("case_id", "model", "condition", "latency_s", "input_tokens",
                                               "output_tokens", "error")}
                    row.update(evaluate_output(c, cond, text) if not err else {"outcome": "API_ERROR"})
                    rows.append(row)
    if rows:
        keys = sorted({k for r in rows for k in r})
        with open(out / "model_comparison_cases.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/models.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cases", help="e.g. F_017,F_026,F_151 for a quick test (default: from config)")
    ap.add_argument("--model", help="run only models whose ID contains this text")
    ap.add_argument("--out", default="results/model_comparison")
    a = ap.parse_args()
    rows = run(a.config, a.dry_run, out_dir=a.out, cases_override=a.cases, only_model=a.model)
    if rows:
        from collections import Counter
        by = {}
        for r in rows:
            by.setdefault((r["model"], r["condition"]), Counter())[r.get("outcome")] += 1
        print("\nmodel | condition | outcomes")
        for (mdl, cond), cnt in sorted(by.items()):
            print(f"{mdl} | {cond} | {dict(cnt)}")
        print(f"\nsaved: {a.out}/model_comparison_cases.csv and {a.out}/raw/")
