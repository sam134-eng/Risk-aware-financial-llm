"""Parse numbers as they appear in financial filings and FinQA evidence.

Handles commas, currency symbols, percent signs, decimals, minus signs and
accounting parentheses. FinQA stores negative cells as "$ -1.7 ( 1.7 )":
the parenthesised part repeats the absolute value of the same number, so it
is treated as the same quantity, not a second number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional

__all__ = ["ParsedNumber", "parse_number", "find_numbers", "to_decimal", "is_label_cell"]


@dataclass(frozen=True)
class ParsedNumber:
    value: Decimal          # signed value as written (percent NOT divided by 100)
    raw: str                # exact source substring
    is_percent: bool = False
    has_currency: bool = False
    start: int = -1         # character offset in the searched text
    end: int = -1


_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_TOKEN = re.compile(
    r"(?P<paren>\(\s*)?"
    r"(?P<cur>[$£€]\s*)?"
    r"(?P<sign>[-−–](?=\s*[$£€]?\s*[\d.]))?\s*"
    r"(?P<cur2>[$£€]\s*)?"
    r"(?P<num>" + _NUM + r")"
    r"(?P<pct>\s*%)?"
    r"(?P<close>\s*\))?"
)
# FinQA duplicate like "28.9% ( 28.9 % )" or "-1.7 ( 1.7 )"
_DUP = re.compile(r"\s*\(\s*[$£€]?\s*(" + _NUM + r")\s*%?\s*\)")


def to_decimal(value) -> Decimal:
    """Convert int/float/str to a finite Decimal (str() avoids float noise)."""
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"not a number: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return d


def find_numbers(text: str) -> List[ParsedNumber]:
    """Return every number in ``text`` with sign, percent and position.

    Rules:
    * ``(1,234)`` alone means -1234 (accounting negative).
    * ``-1.7 ( 1.7 )`` and ``28.9% ( 28.9 % )`` (FinQA duplicates) yield one number.
    * Year-like integers are returned too; callers decide what is relevant.
    """
    out: List[ParsedNumber] = []
    if not text:
        return out
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.search(text, pos)
        if not m:
            break
        num = m.group("num")
        # Skip digits that are part of a word/identifier, e.g. "page_77", "2019s"
        before = text[m.start("num") - 1] if m.start("num") > 0 else " "
        if before.isalpha() or before == "_":
            pos = m.end("num")
            continue
        value = to_decimal(num)
        negative = bool(m.group("sign"))
        opened = bool(m.group("paren"))
        closed = bool(m.group("close"))
        start = m.start()
        end = m.end()
        if negative and m.group("sign"):
            # "2014 - 2016" is a range, not a negative number
            prev = text[: m.start("sign")].rstrip()
            if prev and prev[-1].isdigit():
                negative = False
                start = m.start("cur2") if m.group("cur2") else m.start("num")
        if opened and closed and not negative:
            negative = True  # accounting parentheses
        elif opened and not closed:
            # "(" belongs to surrounding prose, not to this number
            start = m.start("cur") if m.group("cur") else m.start("sign") if m.group("sign") else m.start("num")
        elif closed and not opened:
            end = m.end("pct") if m.group("pct") else m.end("num")
        if negative:
            value = -value
        pn = ParsedNumber(
            value=value,
            raw=text[start:end].strip(),
            is_percent=bool(m.group("pct")),
            has_currency=bool(m.group("cur") or m.group("cur2")),
            start=start,
            end=end,
        )
        out.append(pn)
        pos = end
        # swallow a FinQA duplicate "( 1.7 )" that repeats the same magnitude
        dup = _DUP.match(text, pos)
        if dup and to_decimal(dup.group(1)) == abs(value):
            pos = dup.end()
    return out


def parse_number(text: str) -> Optional[ParsedNumber]:
    """Parse a cell that should hold one number; None if it holds none."""
    nums = find_numbers(text)
    return nums[0] if nums else None


_YEAR = re.compile(r"^\s*(?:fy\s*)?(19|20)\d{2}\s*$", re.I)


def is_label_cell(text: str) -> bool:
    """True if a first-column table cell is a row label (words or a bare year), not a value."""
    t = str(text or "")
    return bool(re.search(r"[A-Za-z]", t)) or bool(_YEAR.match(t)) or not t.strip()
