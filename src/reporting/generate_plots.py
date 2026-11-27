"""Publication figures from measured results only (PNG 300 dpi + PDF). Usage: python -m src.reporting.generate_plots

Not produced (no data): multi-model comparison and latency (other models not run; latency not recorded).
"""
from __future__ import annotations

import csv, json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results/plots")
BLUE, ORANGE, AQUA, GREY = "#257de0", "#f47230", "#00b894", "#c9c9c9"
INK, INK2 = "#191919", "#666666"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=300)
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def hbar(ax, labels, values, color=BLUE, fmt="{:.0f}", xmax=None, annot=None):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=color, height=0.62, edgecolor="white", linewidth=1)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels)
    ax.xaxis.grid(True, color="#ececec", linewidth=0.6); ax.set_axisbelow(True)
    top = xmax or max(values) * 1.18
    ax.set_xlim(0, top)
    for yi, v, a in zip(y, values, annot or [None] * len(values)):
        ax.text(v + top * 0.01, yi, a or fmt.format(v), va="center", color=INK, fontsize=8)


def main():
    ans = json.loads(Path("results/evaluation/answer_eval_summary.json").read_text())
    tax = json.loads(Path("results/analysis/error_taxonomy_80_summary.json").read_text())
    inj = json.loads(Path("results/grounding/grounding_eval_summary.json").read_text())
    g1 = json.loads(Path("results/grounding/stage1_v2_grounding_summary.json").read_text())
    s1 = json.loads(Path("experiments/stage1_v2/FinVerify_SMT_Stage1_v2_80_Case_Results.json").read_text())["summary"]

    # Fig 1: outcome distribution, 500 vs 80 (small multiples, shared order)
    order = ["CORRECT", "ROUNDING_ONLY", "SIGN_CONVENTION", "INCORRECT", "SIGN_MISMATCH", "SCALE_MISMATCH",
             "REFUSED", "NO_ANSWER"]
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.4), sharey=True)
    for ax, key, title in ((axes[0], "all_500", "All benchmark cases"), (axes[1], "selected_80", "80 selected NOT_APPLICABLE cases")):
        o = ans[key]["outcomes"]; n = ans[key]["lenient"]["n"]
        vals = [100 * o.get(k, 0) / n for k in order]
        cols = [BLUE if k in ("CORRECT", "ROUNDING_ONLY", "SIGN_CONVENTION") else ORANGE for k in order]
        hbar(ax, [k.replace("_", " ").lower() for k in order], vals, cols, xmax=70,
             annot=[f"{v:.1f}% ({o.get(k, 0)})" for k, v in zip(order, vals)])
        ax.set_title(f"{title} (n={n})", loc="left"); ax.set_xlabel("% of evaluated cases")
    fig.suptitle("GPT-4o-mini answer outcomes vs gold (blue = counted correct, lenient)", x=0.01, ha="left",
                 fontsize=10, color=INK)
    save(fig, "fig1_answer_outcomes")

    # Fig 2: verification impact – correctness of answers per verifier decision
    ver = tax["original_verifier_status_vs_answer_correct_500"]
    cross = tax["arithmetic_vs_answer_on_extracted_equations"]
    both = cross.get("ALL_CHECKED_PASS|inputs_supported")
    labels = ["Original Z3: PASS", "Original Z3: FAIL", "Original Z3: NOT_APPLICABLE",
              "Stage 1 v2 arithmetic PASS\n+ inputs grounded (80-case set)"]
    data = [ver["PASS"], ver["FAIL"], ver["NOT_APPLICABLE"], both]
    vals = [100 * d["answer_correct"] / d["cases"] for d in data]
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    hbar(ax, labels, vals, [BLUE, BLUE, BLUE, AQUA], xmax=100,
         annot=[f"{v:.1f}%  ({d['answer_correct']}/{d['cases']})" for v, d in zip(vals, data)])
    ax.set_xlabel("% of accepted cases whose final answer matches gold (lenient)")
    ax.set_title("Passing verification does not mean the answer is right", loc="left")
    save(fig, "fig2_verification_vs_answer_correctness")

    # Fig 3: accuracy by reasoning pattern
    pat = {k: v for k, v in ans["by_reasoning_pattern"].items() if v["n"]}
    items = sorted(pat.items(), key=lambda kv: -kv[1]["accuracy"])
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    hbar(ax, [k.replace("_", " ") for k, _ in items], [100 * v["accuracy"] for _, v in items], xmax=110,
         annot=[f"{100 * v['accuracy']:.0f}%  (n={v['n']})" for _, v in items])
    ax.set_xlabel("Lenient answer accuracy, %"); ax.set_title("GPT-4o-mini accuracy by reasoning pattern (500 cases)", loc="left")
    save(fig, "fig3_accuracy_by_reasoning_pattern")

    # Fig 4: 80-case funnel
    steps = [("80 selected cases", 80), ("equations extracted (Stage 1 v2)", s1["cases_with_expressions"]),
             ("all equations arithmetic PASS", s1["cases_all_checked_pass"]),
             ("+ every input traced to evidence", both["cases"]),
             ("+ final answer matches gold", both["answer_correct"])]
    fig, ax = plt.subplots(figsize=(6.2, 2.7))
    hbar(ax, [s for s, _ in steps], [v for _, v in steps], [GREY, BLUE, BLUE, AQUA, AQUA], xmax=92,
         annot=[str(v) for _, v in steps])
    ax.set_xlabel("Cases"); ax.set_title("From NOT_APPLICABLE to checked: the 80-case set", loc="left")
    save(fig, "fig4_80_case_funnel")

    # Fig 5: grounding vs answer correctness on extracted-equation cases
    keys = [("ALL_CHECKED_PASS|inputs_supported", "arith PASS, inputs grounded"),
            ("ARITHMETIC_FAIL_PRESENT|inputs_supported", "arith FAIL, inputs grounded"),
            ("ALL_CHECKED_PASS|some_inputs_not_found", "arith PASS, input not found"),
            ("ARITHMETIC_FAIL_PRESENT|some_inputs_not_found", "arith FAIL, input not found")]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    vals = [cross.get(k, {"cases": 0})["cases"] for k, _ in keys]
    corr = [cross.get(k, {"answer_correct": 0})["answer_correct"] for k, _ in keys]
    y = range(len(keys))[::-1]
    ax.barh(list(y), vals, color=GREY, height=0.62, label="cases", edgecolor="white")
    ax.barh(list(y), corr, color=BLUE, height=0.62, label="answer correct", edgecolor="white")
    ax.set_yticks(list(y)); ax.set_yticklabels([l for _, l in keys])
    for yi, v, c in zip(y, vals, corr):
        ax.text(v + 0.3, yi, f"{c}/{v} correct", va="center", fontsize=8, color=INK)
    ax.set_xlim(0, max(vals) * 1.35); ax.set_xlabel("Cases (27 with extracted equations)")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    ax.set_title("Grounding and arithmetic vs final-answer correctness", loc="left")
    save(fig, "fig5_grounding_vs_answer_accuracy")

    # Fig 6: error taxonomy 80
    rows = list(csv.DictReader(open("results/analysis/error_taxonomy_80_summary.csv")))
    rows = [r for r in rows if r["label"] != "not_formalizable_by_stage1"]
    rows.sort(key=lambda r: -int(r["cases"]))
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    hbar(ax, [f"{r['label'].replace('_', ' ')} [{r['group']}]" for r in rows], [int(r["cases"]) for r in rows],
         xmax=30, annot=[f"{r['cases']} ({r['percent_of_80']}%)" for r in rows])
    ax.set_xlabel("Cases (multi-label; 53/80 also not formalizable by Stage 1 v2)")
    ax.set_title("Error categories in the 80 selected cases (GPT-4o-mini)", loc="left")
    save(fig, "fig6_error_distribution_80")

    # Fig 7: grounding checker error-injection
    c = inj["conditions"]
    names = list(c)
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    hbar(ax, [f"{k.replace('_', ' ')} → {c[k]['expected_status']}" for k in names],
         [100 * c[k]["rate"] for k in names], xmax=118,
         annot=[f"{c[k]['as_expected']}/{c[k]['evaluated']}" for k in names])
    ax.set_xlabel("% of cases with the expected status")
    ax.set_title("Grounding checker on injected errors (reference IR, FinQA)", loc="left")
    save(fig, "fig7_grounding_checker_injection")
    print(sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
