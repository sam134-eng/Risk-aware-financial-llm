"""Estimate API cost of a run BEFORE spending money.

Input tokens are counted from the real prompts (tiktoken o200k_base if installed and
cached, otherwise characters/4). Output tokens are assumptions you set (reasoning models
also bill hidden reasoning tokens as output). Prices are passed in by you - copy them from
the provider's pricing page on the day you run.

Example
  python -m src.experiments.estimate_cost --models 1 --conditions 2 --judge-repeats 3 \\
      --model-price 2 10 --judge-price 10 50 --out-tokens 1500 --judge-out-tokens 1500
"""
from __future__ import annotations

import argparse, json
from pathlib import Path

from src.evaluation.llm_judge import build_stage_a_prompt
from src.experiments.run_model_comparison import build_prompt, load_cases


def counter():
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken o200k_base"
    except Exception:
        return (lambda s: len(s) // 4), "characters/4 (approximate)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="selected_80")
    ap.add_argument("--models", type=int, default=1, help="number of paid answer models")
    ap.add_argument("--conditions", type=int, choices=[1, 2], default=2, help="1 = direct only, 2 = direct + json_ir")
    ap.add_argument("--judge-repeats", type=int, default=3)
    ap.add_argument("--model-price", nargs=2, type=float, metavar=("IN", "OUT"), required=True, help="USD per 1M tokens")
    ap.add_argument("--judge-price", nargs=2, type=float, metavar=("IN", "OUT"), required=True)
    ap.add_argument("--out-tokens", type=int, default=1500, help="assumed output tokens per answer (incl. reasoning)")
    ap.add_argument("--judge-out-tokens", type=int, default=1500)
    a = ap.parse_args()
    n, how = counter()
    cases = load_cases(a.cases)
    answers = json.loads(Path("results/verification_results.json").read_text())["results"]
    conds = ["direct", "json_ir"][: a.conditions]
    ans_in = sum(n(p["system"] + p["user"]) for c in cases for p in (build_prompt(c, k) for k in conds)) * a.models
    ans_calls = len(cases) * len(conds) * a.models
    ans_out = ans_calls * a.out_tokens
    j_in = sum(n(p["system"] + p["user"]) for c in cases
               for p in [build_stage_a_prompt(c, answers[c["case_id"]]["model_answer"])]) * a.judge_repeats
    j_calls = len(cases) * a.judge_repeats
    j_out = j_calls * a.judge_out_tokens
    cost_a = ans_in / 1e6 * a.model_price[0] + ans_out / 1e6 * a.model_price[1]
    cost_j = j_in / 1e6 * a.judge_price[0] + j_out / 1e6 * a.judge_price[1]
    print(f"token counting: {how}; cases: {len(cases)}")
    print(f"answer models : {ans_calls} calls, {ans_in:,} input + {ans_out:,} output tokens  -> ${cost_a:,.2f}")
    print(f"judge         : {j_calls} calls, {j_in:,} input + {j_out:,} output tokens  -> ${cost_j:,.2f}")
    print(f"TOTAL         : ${cost_a + cost_j:,.2f}   (suggested hard limit: ${1.5 * (cost_a + cost_j):,.0f}, i.e. +50% margin)")


if __name__ == "__main__":
    main()
