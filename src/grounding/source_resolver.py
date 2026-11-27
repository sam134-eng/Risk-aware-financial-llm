"""Resolve source references in the IR to the exact evidence they point at.

Supported reference formats (see README for the convention):

=====================  ==========================================================
``table_row_R_col_C``  one table cell. R and C are 0-based; row 0 is the first
                       row stored in ``evidence_context.table`` (usually the header).
``table_R``            a whole table row (FinQA ``gold_inds`` convention).
``text_N``             item N of ``pre_text + post_text`` (FinQA convention).
``pre_text_N``         item N of ``pre_text``.
``post_text_N``        item N of ``post_text``.
``question``           the question text.
``evidence.NAME``      a value in the structured ``evidence`` dict (manual cases).
=====================  ==========================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from .numbers import ParsedNumber, find_numbers, is_label_cell, to_decimal
from .unit_normalizer import detect_scale_in_header

__all__ = ["ResolvedSource", "SourceError", "resolve", "REF_PATTERNS"]


class SourceError(LookupError):
    """The reference is malformed or points outside the evidence."""


@dataclass
class ResolvedSource:
    ref: str
    kind: str                         # table_cell | table_row | text | question | structured
    text: str                         # exact evidence text (or "name = value unit")
    numbers: List[ParsedNumber] = field(default_factory=list)
    header_scale: Optional[Decimal] = None   # e.g. 1e6 when the table says "( in millions )"
    row_label: Optional[str] = None
    column_label: Optional[str] = None
    structured_unit: Optional[str] = None


REF_PATTERNS = {
    "table_cell": re.compile(r"^table_row_(\d+)_col_(\d+)$"),
    "table_row": re.compile(r"^table_(\d+)$"),
    "text": re.compile(r"^text_(\d+)$"),
    "pre_text": re.compile(r"^pre_text_(\d+)$"),
    "post_text": re.compile(r"^post_text_(\d+)$"),
    "question": re.compile(r"^question$"),
    "structured": re.compile(r"^evidence\.([A-Za-z0-9_]+)$"),
}


def _cell_text(cell) -> str:
    return "" if cell is None else str(cell)


def _table_scale(case: dict) -> Optional[Decimal]:
    ec = case.get("evidence_context") or {}
    table = ec.get("table") or []
    header_bits = [" ".join(_cell_text(c) for c in table[0])] if table else []
    first_col = [_cell_text(r[0]) for r in table if r]
    pre = ec.get("pre_text") or []
    return detect_scale_in_header(*(header_bits + first_col + pre[-3:]))


def resolve(ref: str, case: dict) -> ResolvedSource:
    """Resolve ``ref`` against a benchmark case. Raises SourceError if invalid."""
    if not isinstance(ref, str) or not ref.strip():
        raise SourceError("empty source reference")
    ref = ref.strip()
    ec = case.get("evidence_context") or {}
    table = ec.get("table") or []
    pre = ec.get("pre_text") or []
    post = ec.get("post_text") or []

    m = REF_PATTERNS["table_cell"].match(ref)
    if m:
        r, c = int(m.group(1)), int(m.group(2))
        if r >= len(table):
            raise SourceError(f"{ref}: table has {len(table)} rows")
        if c >= len(table[r]):
            raise SourceError(f"{ref}: row {r} has {len(table[r])} columns")
        text = _cell_text(table[r][c])
        return ResolvedSource(
            ref, "table_cell", text, find_numbers(text), _table_scale(case),
            row_label=_cell_text(table[r][0]) if table[r] else None,
            column_label=_cell_text(table[0][c]) if table and c < len(table[0]) else None,
        )

    m = REF_PATTERNS["table_row"].match(ref)
    if m:
        r = int(m.group(1))
        if r >= len(table):
            raise SourceError(f"{ref}: table has {len(table)} rows")
        cells = [_cell_text(x) for x in table[r]]
        nums: List[ParsedNumber] = []
        for j, x in enumerate(cells):       # skip the row label (words or a bare year)
            if j == 0 and is_label_cell(x):
                continue
            nums.extend(find_numbers(x))
        return ResolvedSource(ref, "table_row", " | ".join(cells), nums, _table_scale(case),
                              row_label=cells[0] if cells else None)

    for kind, items, offset_name in (("text", pre + post, "text"), ("pre_text", pre, "pre_text"),
                                     ("post_text", post, "post_text")):
        m = REF_PATTERNS[kind].match(ref)
        if m:
            i = int(m.group(1))
            if i >= len(items):
                raise SourceError(f"{ref}: only {len(items)} {offset_name} items")
            text = items[i]
            return ResolvedSource(ref, "text", text, find_numbers(text), detect_scale_in_header(text))

    if REF_PATTERNS["question"].match(ref):
        q = case.get("question") or ""
        return ResolvedSource(ref, "question", q, find_numbers(q), None)

    m = REF_PATTERNS["structured"].match(ref)
    if m:
        ev = case.get("evidence") or {}
        name = m.group(1)
        if name not in ev:
            raise SourceError(f"{ref}: no evidence field {name!r}")
        item = ev[name]
        value = item.get("value") if isinstance(item, dict) else item
        unit = item.get("unit") if isinstance(item, dict) else None
        pn = ParsedNumber(to_decimal(value), str(value))
        return ResolvedSource(ref, "structured", f"{name} = {value} {unit or ''}".strip(), [pn],
                              None, structured_unit=unit)

    raise SourceError(f"unrecognised source reference format: {ref!r}")
