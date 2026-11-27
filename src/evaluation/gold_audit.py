"""Check FinQA gold answers against their own reference programs (no model involved).

``program_value`` executes the gold program; ``gold_consistency`` compares the
result with gold_answer at the gold's displayed precision (percent/fraction aware).
Cases flagged in the team's manual reviews are listed in REVIEW_FLAGS.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from src.evaluation.answer_evaluator import parse_gold, _matches_at_precision, _rel

_STEP = re.compile(r"(\w+)\(([^()]*)\)")

# Manual review flags (80-case manual review, 23 Nov; Chaewon Stage 1 v2 review flags CSV).
REVIEW_FLAGS = {
    "F_048": "gold divides compensation expense by shares (not a share price)",
    "F_147": "reference uses 2006-2007 values for a 2005-2006 question",
    "F_151": "gold_answer 3829 vs program/gold_numeric 38290",
    "F_162": "endpoint convention for the 2011 index value (Stage 1 v2 review)",
    "F_183": "program adds instead of subtracting; gold_answer close to correct 2.78%",
    "F_189": "gold_answer 3% vs computed 2.65%",
    "F_236": "operating ratio 'improved' (fell) but gold adds the change",
    "F_332": "program returns 9.3 instead of a percentage change",
    "F_376": "direction reversed: gold +780% vs -88.64%",
    "F_430": "gold_answer 219.35 vs program 21.94; method financially doubtful",
    "F_453": "uses employee purchase price as share price",
    "F_463": "question asks millions; values appear to be thousands",
    "F_488": "gold_answer 29% vs program 27.27%",
}


def program_value(prog: str) -> Optional[Decimal]:
    res = []
    try:
        for op, args in _STEP.findall(prog or ""):
            if op.startswith("table_"):
                return None
            vals = []
            for a in args.split(",")[:2]:
                a = a.strip()
                if a.startswith("#"):
                    vals.append(res[int(a[1:])])
                elif a.startswith("const_"):
                    vals.append(Decimal(-1) if a[6:] == "m1" else Decimal(a[6:]))
                else:
                    pct = a.endswith("%")
                    v = Decimal(a.rstrip("%").replace(",", ""))
                    vals.append(v / 100 if pct else v)
            x, y = vals
            r = {"add": x + y, "subtract": x - y, "multiply": x * y,
                 "divide": (x / y) if y else None, "exp": x ** y if y == y.to_integral() else None,
                 "greater": Decimal(1) if x > y else Decimal(0)}.get(op)
            if r is None:
                return None
            res.append(r)
    except Exception:
        return None
    return res[-1] if res else None


def gold_consistency(gold_answer, prog: str) -> str:
    g = parse_gold(gold_answer)
    if g.kind in ("unsupported", "yes_no"):
        return "NOT_CHECKED"
    pv = program_value(prog)
    if pv is None:
        return "NOT_CHECKED"
    for cand in (pv, pv * 100):
        if _matches_at_precision(cand, g.value, g.decimals):
            return "CONSISTENT"
    for cand in (pv, pv * 100):
        if g.value != 0 and _rel(cand, g.value) <= Decimal("0.01"):
            return "ROUNDING_DIFFERENCE"
    return "INCONSISTENT"
