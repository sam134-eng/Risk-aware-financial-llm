"""Build the benchmark tables (Markdown + CSV) from result files. Only measured numbers are used.

Usage: python -m src.reporting.generate_tables   -> results/tables/
"""
from __future__ import annotations

import csv, json
from collections import Counter
from pathlib import Path

OUT = Path("results/tables")


def pct(a, b):
    return f"{100 * a / b:.1f}% ({a}/{b})" if b else "–"


def md(rows, header):
    s = "| " + " | ".join(header) + " |\n|" + "|".join("---" for _ in header) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def write(name, title, header, rows, note=""):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.md").write_text(f"### {title}\n\n" + md(rows, header) + (f"\n{note}\n" if note else ""))
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    return f"### {title}\n\n" + md(rows, header) + (f"\n{note}\n" if note else "")


def main():
    ans = json.loads(Path("results/evaluation/answer_eval_summary.json").read_text())
    rows = list(csv.DictReader(open("results/evaluation/answer_eval_cases.csv")))
    g1 = json.loads(Path("results/grounding/stage1_v2_grounding_summary.json").read_text())
    gcases = json.loads(Path("results/grounding/stage1_v2_grounding_cases.json").read_text())
    s1 = json.loads(Path("experiments/stage1_v2/FinVerify_SMT_Stage1_v2_80_Case_Results.json").read_text())["summary"]
    tax = list(csv.DictReader(open("results/analysis/error_taxonomy_80_summary.csv")))
    taxj = json.loads(Path("results/analysis/error_taxonomy_80_summary.json").read_text())
    inj = json.loads(Path("results/grounding/grounding_eval_summary.json").read_text())
    parts = []

    a80, a500 = ans["selected_80"], ans["all_500"]
    n_in = sum(g1["input_match_classes"].values())
    supported = n_in - g1["input_match_classes"].get("NOT_FOUND", 0)
    direct = sum(v for k, v in g1["input_match_classes"].items()
                 if k in ("EVIDENCE_EXACT", "EVIDENCE_SCALED", "EVIDENCE_RESCALED", "EVIDENCE_PERCENT_AS_RATIO",
                          "EVIDENCE_SIGN_DIFFERS", "EVIDENCE_ROUNDED", "QUESTION"))
    parts.append(write("table1_main_benchmark", "Table 1. Main benchmark (GPT-4o-mini, stored answers)",
        ["Model", "Cases", "Answer acc. (lenient)", "Answer acc. (strict)", "Grounding: inputs supported",
         "Equation (arithmetic) acc.", "Metric acc.", "Valid IR rate", "Latency"],
        [["gpt-4o-mini", "500 benchmark", pct(a500["lenient"]["correct"], a500["lenient"]["n"]),
          pct(a500["strict"]["correct"], a500["strict"]["n"]), "not measured", "not measured", "not measured", "n/a", "not recorded"],
         ["gpt-4o-mini", "80 selected", pct(a80["lenient"]["correct"], a80["lenient"]["n"]),
          pct(a80["strict"]["correct"], a80["strict"]["n"]),
          f"{pct(direct, n_in)} found in evidence; {pct(supported, n_in)} traced incl. derived/earlier steps",
          pct(s1["z3_arithmetic_pass"], s1["total_extracted_equations"]) + " equations",
          "not measured (needs judge/human)", f"n/a (free text); Stage 1 extraction {pct(s1['cases_with_expressions'], 80)} cases",
          "not recorded"]],
        "Denominators exclude cases whose gold is not a single value (manual multi-part cases, F_037). "
        "Lenient = correct at gold precision, within 1%, or sign stated in words. Grounding and arithmetic are on the "
        "equations Stage 1 v2 extracted (68 inputs, 34 equations, 27 cases). Other models were not run: no API access."))

    parts.append(write("table2_error_taxonomy_80", "Table 2. Error categories, 80 selected cases (GPT-4o-mini; multi-label)",
        ["Group", "Category", "Cases", "% of 80", "Detected by", "Needs human review", "Examples"],
        [[t["group"], t["label"], t["cases"], t["percent_of_80"], t["detected_by"], t["needs_human_review"], t["example_cases"]]
         for t in tax]))

    ver = taxj["original_verifier_status_vs_answer_correct_500"]
    cross = taxj["arithmetic_vs_answer_on_extracted_equations"]
    pass_both = cross.get("ALL_CHECKED_PASS|inputs_supported", {"cases": 0, "answer_correct": 0})
    parts.append(write("table3_verification_impact", "Table 3. What each verification step covers, and answer correctness of what it accepts",
        ["Configuration (implemented)", "Scope", "Cases accepted", "Of which answer correct (lenient)"],
        [["Original Z3 verifier: PASS", "500", ver["PASS"]["cases"], pct(ver["PASS"]["answer_correct"], ver["PASS"]["cases"])],
         ["Original Z3 verifier: FAIL", "500", ver["FAIL"]["cases"], pct(ver["FAIL"]["answer_correct"], ver["FAIL"]["cases"])],
         ["Original Z3 verifier: NOT_APPLICABLE", "500", ver["NOT_APPLICABLE"]["cases"], pct(ver["NOT_APPLICABLE"]["answer_correct"], ver["NOT_APPLICABLE"]["cases"])],
         ["Stage 1 v2: equations extracted", "80", s1["cases_with_expressions"], "–"],
         ["Stage 1 v2: all equations arithmetic PASS", "80", s1["cases_all_checked_pass"], "–"],
         ["+ grounding: arithmetic PASS and inputs supported", "80", pass_both["cases"], pct(pass_both["answer_correct"], pass_both["cases"])]],
        "Grounding+arithmetic does not certify the answer: of the 7 accepted-but-wrong cases, 5 have a questionable "
        "gold answer (F_147, F_151, F_183, F_376, F_488) and F_089 uses the wrong denominator."))

    pat = ans["by_reasoning_pattern"]
    parts.append(write("table4_by_reasoning_pattern", "Table 4. GPT-4o-mini answer accuracy by reasoning pattern (500 cases)",
        ["Pattern", "Evaluated", "Lenient accuracy"],
        [[k, v["n"], f"{100 * v['accuracy']:.1f}%" if v["accuracy"] is not None else "–"]
         for k, v in sorted(pat.items(), key=lambda kv: -(kv[1]["n"] or 0)) if v["n"]],
        "The 16 manual cases have multi-part gold answers and are not scored automatically."))

    parts.append(write("table5_grounding_checker_injection", "Table 5. Grounding checker on reference IR with injected errors (FinQA, 468 cases)",
        ["Condition", "Expected", "As expected", "Rate"],
        [[k, v["expected_status"], f"{v['as_expected']}/{v['evaluated']}", f"{100 * v['rate']:.1f}%"]
         for k, v in inj["conditions"].items()],
        "Synthetic single errors; shows the checks work, not real model error rates. wrong_period_cited passing is the "
        "documented limitation (grounding cannot see period errors)."))

    gc = ans["gold_consistency_finqa"]
    parts.append(write("table6_gold_consistency", "Table 6. FinQA gold answers vs their own reference programs (484 cases)",
        ["Result", "Cases"], [[k, v] for k, v in sorted(gc.items(), key=lambda kv: -kv[1])],
        "INCONSISTENT cases: " + ", ".join(ans["gold_inconsistent_cases"])))

    mcls = g1["input_match_classes"]
    parts.append(write("table7_stage1_input_grounding", f"Table 7. Where the {n_in} equation inputs extracted from GPT-4o-mini answers come from",
        ["Match class", "Inputs"], [[k, v] for k, v in sorted(mcls.items(), key=lambda kv: -kv[1])]))
    (OUT / "all_tables.md").write_text("\n\n".join(parts))
    print("\n\n".join(parts))


if __name__ == "__main__":
    main()
