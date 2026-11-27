"""Build a reference IR from a FinQA gold program (for testing only).

The gold program, e.g. ``subtract(138.29, const_100), divide(#0, const_100)``,
is turned into IR variables (one per literal number, linked to the evidence
cell or text span that contains it), constants and equations. This gives a
large, realistic regression set for the grounding checker without any LLM.

It is NOT a model output and must never be used as a system input in
experiments (it is derived from the gold answer).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .numbers import find_numbers, is_label_cell, to_decimal

__all__ = ["build_gold_ir", "UnsupportedProgram", "locate_value"]

_STEP = re.compile(r"(\w+)\(([^()]*)\)")
_OPS = {"add": "{a} + {b}", "subtract": "{a} - {b}", "multiply": "{a} * {b}",
        "divide": "{a} / {b}", "exp": "{a} ** {b}", "greater": "{a} > {b}"}


class UnsupportedProgram(ValueError):
    pass


def _evidence_items(case: Dict[str, Any]):
    """Yield (ref, kind, text, row) in priority order: gold evidence first, then everything else."""
    ec = case.get("evidence_context") or {}
    table = ec.get("table") or []
    texts = (ec.get("pre_text") or []) + (ec.get("post_text") or [])
    gold = list((case.get("gold_supporting_evidence") or {}).keys())
    order = gold + [f"table_{i}" for i in range(len(table))] + [f"text_{i}" for i in range(len(texts))]
    seen = set()
    for key in order:
        if key in seen:
            continue
        seen.add(key)
        kind, idx = key.rsplit("_", 1)
        idx = int(idx)
        if kind == "table" and idx < len(table):
            yield key, "table", None, table[idx], idx
        elif kind == "text" and idx < len(texts):
            yield key, "text", texts[idx], None, idx
    yield "question", "question", case.get("question") or "", None, None


def locate_value(value: Decimal, is_percent: bool, case: Dict[str, Any]) -> Optional[str]:
    """Return a source reference whose evidence contains ``value`` (sign-insensitive)."""
    for key, kind, text, row, idx in _evidence_items(case):
        if kind == "table":
            for c, cell in enumerate(row):
                if c == 0 and is_label_cell(cell):
                    continue
                for n in find_numbers(str(cell)):
                    if abs(n.value) == abs(value):
                        return f"table_row_{idx}_col_{c}"
        else:
            for n in find_numbers(text):
                if abs(n.value) == abs(value):
                    return key if kind == "text" else "question"
    return None


def _source_value(ref: str, value: Decimal, case: Dict[str, Any]) -> Decimal:
    """Use the sign shown in the source (gold programs often drop it)."""
    from .source_resolver import resolve
    src = resolve(ref, case)
    for n in src.numbers:
        if n.value == value:
            return value
    for n in src.numbers:
        if abs(n.value) == abs(value):
            return n.value
    return value


def build_gold_ir(case: Dict[str, Any]) -> Dict[str, Any]:
    prog = case.get("gold_reasoning") or ""
    steps = _STEP.findall(prog)
    if not steps:
        raise UnsupportedProgram("no program")
    variables: List[Dict[str, Any]] = []
    equations: List[Dict[str, Any]] = []
    by_literal: Dict[Tuple[str, bool], str] = {}

    def operand(tok: str) -> str:
        tok = tok.strip()
        if tok.startswith("#"):
            return f"step_{int(tok[1:])}"
        if tok.startswith("const_"):
            raw = tok[6:]
            val = Decimal(-1) if raw == "m1" else to_decimal(raw)
            name = f"c_{str(val).replace('-', 'm').replace('.', '_')}"
            if not any(v["name"] == name for v in variables):
                variables.append({"name": name, "value": float(val), "kind": "constant",
                                  "source_grounding": "constant", "unit": ""})
            return name
        is_pct = tok.endswith("%")
        val = to_decimal(tok.rstrip("%"))
        key = (str(val), is_pct)
        if key in by_literal:
            return by_literal[key]
        ref = locate_value(val, is_pct, case)
        name = f"x{len(by_literal)}"
        by_literal[key] = name
        var = {"name": name, "unit": "percent" if is_pct else ""}
        if ref:
            var["source_grounding"] = ref
            var["value"] = float(_source_value(ref, val, case))
        else:
            var["value"] = float(val)
        variables.append(var)
        return name

    for i, (op, args) in enumerate(steps):
        if op not in _OPS:
            raise UnsupportedProgram(f"operation {op} not converted")
        a, b = [s for s in args.split(",")][:2]
        equations.append({"id": f"eq_{i}", "lhs": f"step_{i}",
                          "rhs": _OPS[op].format(a=operand(a), b=operand(b))})
    return {
        "question_id": case.get("case_id"),
        "variables": variables,
        "equations": equations,
        "claimed_answer": {"target_variable": f"step_{len(steps) - 1}",
                           "predicted_value": case.get("gold_numeric"), "tolerance": 0.001},
        "_note": "built from FinQA gold program for testing; not a model output",
    }
