"""Error taxonomy for the 80-case study, built from deterministic signals only.

Each case can carry several labels. Every label records which component detects it.
Labels that need human judgement are marked as candidates (``needs_review``).
"""
from __future__ import annotations

from typing import Dict, List

# (group, label, detector, needs_review)
TAXONOMY = {
    "gold_reference_issue":      ("Benchmark", "Gold answer disagrees with its own program or was flagged in review", "gold audit + manual review", False),
    "unit_or_scale_error":       ("Evidence", "Final answer off by a power of 1000", "answer evaluator", False),
    "unsupported_number":        ("Evidence", "Equation input not found in the evidence", "grounding locator", True),
    "arithmetic_error":          ("Arithmetic", "A written equation is arithmetically wrong", "Stage 1 v2 (Z3)", False),
    "rounding_only":             ("Arithmetic", "Within 1% of gold but not equal at gold precision", "answer evaluator", False),
    "sign_or_direction_error":   ("Financial reasoning", "Right magnitude, wrong sign / direction", "answer evaluator", False),
    "wrong_value_unexplained":   ("Financial reasoning", "Wrong value; arithmetic and inputs look fine or were not extracted (metric, denominator or period suspected)", "answer evaluator", True),
    "refusal":                   ("LLM behaviour", "Model said the question cannot be answered", "answer evaluator", False),
    "no_final_answer":           ("LLM behaviour", "No final value stated (e.g. lists values only)", "answer evaluator", False),
    "not_formalizable_by_stage1": ("Formalization", "No equation could be extracted by Stage 1 v2", "Stage 1 v2", False),
}


def labels_for(row: Dict[str, str]) -> List[str]:
    out = []
    o = row["outcome"]
    if row.get("gold_consistency") == "INCONSISTENT" or row.get("review_flag"):
        out.append("gold_reference_issue")
    if o == "SCALE_MISMATCH":
        out.append("unit_or_scale_error")
    if row.get("stage1_grounding") == "SOME_INPUTS_NOT_FOUND":
        out.append("unsupported_number")
    if row.get("stage1_arithmetic") == "ARITHMETIC_FAIL_PRESENT":
        out.append("arithmetic_error")
    if o == "ROUNDING_ONLY":
        out.append("rounding_only")
    if o == "SIGN_MISMATCH":
        out.append("sign_or_direction_error")
    if o == "INCORRECT" and "arithmetic_error" not in out and "unsupported_number" not in out:
        out.append("wrong_value_unexplained")
    if o == "REFUSED":
        out.append("refusal")
    if o == "NO_ANSWER":
        out.append("no_final_answer")
    if row.get("stage1_arithmetic") == "NO_EXPRESSION":
        out.append("not_formalizable_by_stage1")
    return out
