"""Find where a number written in a model answer comes from in the case evidence.

Used when the model output has no source references (e.g. numbers extracted
from free-text answers by Stage 1 v2). For each number we search every
evidence item (table cells, text sentences, question, structured evidence)
and classify the best match:

EVIDENCE_EXACT        same value as written in the evidence
EVIDENCE_SCALED       same value after a scale stated in the evidence ("in millions", "$ 7.0 billion")
EVIDENCE_RESCALED     same quantity expressed in another scale than the evidence
                      (e.g. "$ 7.0 billion" written as 7000 [millions]); model unit not stated
EVIDENCE_PERCENT_AS_RATIO  "15%" in the evidence written as 0.15
MODEL_INTERMEDIATE    equals a value the model computed in an earlier extracted step
EVIDENCE_SIGN_DIFFERS same magnitude, opposite sign (FinQA often stores negatives as "( 1.7 )")
EVIDENCE_ROUNDED      a rounded / rescaled form of an evidence number (weaker evidence)
DERIVED_FROM_EVIDENCE equals a+b, a-b or a/b of two numbers in the SAME evidence item
                      (same table row or sentence); the step itself is not verified
QUESTION              stated in the question text
CONSTANT              standard constant (0-5, 12, 100, 1000, ...)
NOT_FOUND             no supporting evidence found (candidate unsupported number)

Restricting derived matches to a single evidence item keeps chance matches low;
it also means multi-item derivations are reported as NOT_FOUND.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from itertools import permutations
from typing import Dict, List, Optional, Tuple

from .evidence_grounding import DEFAULT_ALLOWED_CONSTANTS
from .numbers import find_numbers, is_label_cell, to_decimal
from .source_resolver import _table_scale
from .unit_normalizer import SCALE_WORDS, detect_scale_in_header, detect_scale_near

__all__ = ["EvidenceNumber", "evidence_index", "locate_number", "LocateResult", "GROUNDED_CLASSES"]

GROUNDED_CLASSES = {"EVIDENCE_EXACT", "EVIDENCE_SCALED", "EVIDENCE_RESCALED", "EVIDENCE_PERCENT_AS_RATIO",
                    "EVIDENCE_SIGN_DIFFERS", "EVIDENCE_ROUNDED", "QUESTION"}
_RANK = ["EVIDENCE_EXACT", "EVIDENCE_SCALED", "EVIDENCE_PERCENT_AS_RATIO", "QUESTION", "EVIDENCE_RESCALED",
         "EVIDENCE_SIGN_DIFFERS", "EVIDENCE_ROUNDED", "CONSTANT", "MODEL_INTERMEDIATE",
         "DERIVED_FROM_EVIDENCE", "NOT_FOUND"]


@dataclass(frozen=True)
class EvidenceNumber:
    value: Decimal
    scale: Optional[Decimal]      # None = scale not stated
    ref: str                      # table_row_R_col_C | text_N | question | evidence.NAME
    item: str                     # evidence item id (table_R | text_N | question | evidence)
    raw: str
    is_percent: bool = False


@dataclass
class LocateResult:
    value: str
    match_class: str
    refs: List[str] = field(default_factory=list)
    evidence_raw: List[str] = field(default_factory=list)
    note: str = ""


def evidence_index(case: Dict) -> List[EvidenceNumber]:
    out: List[EvidenceNumber] = []
    ec = case.get("evidence_context") or {}
    table = ec.get("table") or []
    tscale = _table_scale(case) if table else None
    for r, row in enumerate(table):
        for c, cell in enumerate(row):
            if c == 0 and is_label_cell(cell):
                continue
            for n in find_numbers(str(cell)):
                out.append(EvidenceNumber(n.value, tscale, f"table_row_{r}_col_{c}", f"table_{r}", n.raw,
                                          n.is_percent))
    texts = (ec.get("pre_text") or []) + (ec.get("post_text") or [])
    for i, t in enumerate(texts):
        hdr = detect_scale_in_header(t)
        for n in find_numbers(t):
            sc = detect_scale_near(t, n.end) or hdr
            out.append(EvidenceNumber(n.value, sc, f"text_{i}", f"text_{i}", n.raw, n.is_percent))
    q = case.get("question") or ""
    for n in find_numbers(q):
        out.append(EvidenceNumber(n.value, detect_scale_near(q, n.end), "question", "question", n.raw,
                                  n.is_percent))
    for name, item in (case.get("evidence") or {}).items():
        v = item.get("value") if isinstance(item, dict) else item
        try:
            out.append(EvidenceNumber(to_decimal(v), Decimal(1), f"evidence.{name}", "evidence", str(v)))
        except ValueError:
            pass
    return out


def _decimals(s: str) -> int:
    s = s.strip().lstrip("-")
    return len(s.split(".")[1]) if "." in s else 0


def _rounds_to(x: Decimal, target: Decimal, d: int) -> bool:
    q = Decimal(1).scaleb(-d)
    return x.quantize(q, rounding=ROUND_HALF_UP) == target


def locate_number(value: str, case: Dict, unit_hint: Optional[str] = None,
                  index: Optional[List[EvidenceNumber]] = None,
                  constants=DEFAULT_ALLOWED_CONSTANTS,
                  earlier_values: Optional[List[str]] = None) -> LocateResult:
    """Classify where ``value`` (as written by the model) comes from."""
    v = to_decimal(value)
    d = _decimals(str(value))
    sm = SCALE_WORDS.get((unit_hint or "").lower(), Decimal(1))
    v_abs = v * sm
    idx = index if index is not None else evidence_index(case)
    hits: Dict[str, List[EvidenceNumber]] = {}

    def add(cls, en):
        hits.setdefault(cls, []).append(en)

    for en in idx:
        n = en.value
        if n == v:
            add("QUESTION" if en.item == "question" else "EVIDENCE_EXACT", en)
            continue
        if en.scale is not None and n * en.scale == v_abs:
            add("QUESTION" if en.item == "question" else "EVIDENCE_SCALED", en)
            continue
        if en.is_percent and sm == 1 and n / 100 == v:
            add("EVIDENCE_PERCENT_AS_RATIO", en)
            continue
        if en.scale is not None and any(n * en.scale / Decimal(10) ** k == v for k in (3, 6, 9)) \
                and en.scale != Decimal(1):
            add("EVIDENCE_RESCALED", en)
            continue
        if n == -v or (en.scale is not None and n * en.scale == -v_abs):
            add("EVIDENCE_SIGN_DIFFERS", en)
            continue
        if v != 0 and d >= 1:
            cands = [n]
            if en.scale is not None:
                cands += [n * en.scale / Decimal(10) ** k for k in (3, 6, 9)]
            for c in cands:
                if c != 0 and _rounds_to(c, v, d) and abs(c - v) / abs(c) < Decimal("0.005"):
                    add("EVIDENCE_ROUNDED", en)
                    break

    if v in {to_decimal(c) for c in constants}:
        add("CONSTANT", EvidenceNumber(v, None, "constant", "constant", str(v)))

    if not hits and earlier_values:
        for ev in earlier_values:
            if to_decimal(ev) == v:
                hits["MODEL_INTERMEDIATE"] = [EvidenceNumber(v, None, "earlier_step", "model", str(ev))]
                break

    if not hits:
        by_item: Dict[str, List[EvidenceNumber]] = {}
        for en in idx:
            by_item.setdefault(en.item, []).append(en)
        for item, nums in by_item.items():
            vals = nums[:40]                       # bound the search
            for a, b in permutations(vals, 2):
                for op, r in (("+", a.value + b.value), ("-", a.value - b.value),
                              ("/", a.value / b.value if b.value else None)):
                    if r is None:
                        continue
                    if r == v or (d >= 1 and r != 0 and _rounds_to(r, v, d)
                                  and abs(r - v) / abs(r) < Decimal("0.005")):
                        hits.setdefault("DERIVED_FROM_EVIDENCE", []).extend([a, b])
                        hits.setdefault("_how", []).append(EvidenceNumber(r, None, f"{a.raw} {op} {b.raw}", item, ""))
                        break
                if "DERIVED_FROM_EVIDENCE" in hits:
                    break
            if "DERIVED_FROM_EVIDENCE" in hits:
                break

    for cls in _RANK:
        if cls in hits:
            ens = hits[cls]
            note = ""
            if cls == "DERIVED_FROM_EVIDENCE":
                note = f"{hits['_how'][0].ref} in {ens[0].item}"
            if cls in ("EVIDENCE_EXACT", "EVIDENCE_SCALED") and len({e.ref for e in ens}) > 1:
                note = f"value appears in {len({e.ref for e in ens})} places"
            return LocateResult(str(value), cls, sorted({e.ref for e in ens})[:6], [e.raw for e in ens][:6], note)
    return LocateResult(str(value), "NOT_FOUND")
