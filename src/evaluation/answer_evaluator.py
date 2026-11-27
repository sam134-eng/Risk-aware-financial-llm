"""Deterministic final-answer evaluation (Stage B: the only stage that sees the gold answer).

1. ``extract_final_answer`` pulls the model's final answer out of free text
   (last bold value, "answer:" line, or last number of the final paragraph)
   and detects refusals ("not possible", "insufficient information", ...).
2. ``evaluate`` compares it with the gold answer.

Outcomes
--------
CORRECT          rounds to the gold answer at the gold's displayed precision
ROUNDING_ONLY    within 1% relative error but not equal at the gold's precision
SIGN_CONVENTION  same magnitude, opposite sign, but the direction is stated in words
                 ("a decrease of $17 million") or the question asks for a decline/decrease
SIGN_MISMATCH    same magnitude, opposite sign, no wording that explains it
SCALE_MISMATCH   off by a power of 1000 (unit/scale error)
INCORRECT        any other numeric difference
REFUSED          the model said the question cannot be answered
NO_ANSWER        no final value could be extracted
NOT_EVALUATED    gold is not a single number / yes-no (manual multi-part cases)

Percent answers given as fractions (0.25 for 25%) are accepted and noted, as in
common FinQA practice. ``lenient_correct`` = CORRECT, ROUNDING_ONLY or SIGN_CONVENTION.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from src.grounding.numbers import find_numbers, to_decimal

__all__ = ["ExtractedAnswer", "extract_final_answer", "parse_gold", "evaluate", "EvalResult"]

_REFUSAL = re.compile(
    r"not possible to (?:answer|calculate|determine)|cannot be (?:determined|calculated|answered)|"
    r"(?:is|are) (?:insufficient|not sufficient)|insufficient (?:information|data|evidence)|"
    r"(?:can ?not|unable to) (?:calculate|determine|answer|compute)|"
    r"does not (?:provide|contain|include) (?:sufficient|enough|the necessary)|"
    r"impossible to (?:calculate|determine)|not (?:enough|sufficient) (?:information|data)", re.I)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_YESNO = re.compile(r"\b(yes|no)\b", re.I)
_RATIO = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s*:\s*(\d[\d,]*(?:\.\d+)?)")


@dataclass
class ExtractedAnswer:
    value: Optional[Decimal]
    is_percent: bool
    yes_no: Optional[str]
    refused: bool
    method: str
    raw: str


def _num_from(text: str):
    m = _RATIO.search(text)
    if m and "ratio" not in text.lower()[:0]:
        a, b = to_decimal(m.group(1)), to_decimal(m.group(2))
        if b != 0:
            return a / b, False, m.group(0)
    nums = [n for n in find_numbers(text)]
    if not nums:
        return None
    n = nums[-1]
    return n.value, n.is_percent, n.raw


_NEG = re.compile(r"\b(?:not|did not|does not|was not|were not|is not|isn't|wasn't|didn't|less than|lower than|"
                  r"fewer than|underperform\w*)\b", re.I)
_AFF = re.compile(r"\b(?:greater than|more than|more\b[^.]{0,60}\bthan|higher than|exceed\w*|outperform\w*|did indeed|grew|increased)\b",
                  re.I)


def extract_yes_no(text: str) -> ExtractedAnswer:
    """For yes/no questions: explicit yes/no in the conclusion, else negated/affirmed comparison."""
    text = text or ""
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    concl = " ".join(paras[-2:]) if paras else ""
    found = [m.group(1).lower() for m in re.finditer(r"(?:^|[*:.\s])(yes|no)\b[,.!*\s]", concl, re.I)]
    found = [f for f in found if not re.search(r"\bno (?:further|additional|calculation)", concl, re.I) or f == "yes"]
    if found:
        return ExtractedAnswer(None, False, found[-1], False, "yes_no_explicit", concl[-120:])
    last = paras[-1] if paras else ""
    if _NEG.search(last):
        return ExtractedAnswer(None, False, "no", False, "yes_no_negated_comparison", last[-120:])
    if _AFF.search(last):
        return ExtractedAnswer(None, False, "yes", False, "yes_no_affirmed_comparison", last[-120:])
    refused = bool(_REFUSAL.search(text[-600:]))
    return ExtractedAnswer(None, False, None, refused, "none", "")


_YEAR_ONLY = re.compile(r"^\s*(?:19|20)\d{2}\s*:?\s*$")


def extract_final_answer(text: str) -> ExtractedAnswer:
    text = text or ""
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    last = paras[-1] if paras else ""
    tail = text[-600:]
    refused = bool(_REFUSAL.search(tail))
    def numeric_bolds(t):
        return [b for b in _BOLD.findall(t) if re.search(r"\d", b) and len(b) < 80 and not _YEAR_ONLY.match(b)]
    bolds = numeric_bolds(last) or numeric_bolds(text)[-1:]
    if bolds:
        got = _num_from(bolds[-1])
        if got:
            return ExtractedAnswer(got[0], got[1], None, False, "bold", bolds[-1].strip()[:80])
    m = re.search(r"(?:final answer|answer)\s*[:=]\s*(.+)", text, re.I)
    if m:
        got = _num_from(m.group(1)[:120])
        if got:
            return ExtractedAnswer(got[0], got[1], None, False, "answer_line", m.group(1).strip()[:80])
    if refused:
        return ExtractedAnswer(None, False, None, True, "refusal", tail.strip()[-160:])
    got = _num_from(last)
    if got:
        return ExtractedAnswer(got[0], got[1], None, False, "last_number", last.strip()[-80:])
    return ExtractedAnswer(None, False, None, False, "none", "")


@dataclass
class Gold:
    kind: str                 # number | percent | yes_no | unsupported
    value: Optional[Decimal]
    decimals: int
    yes_no: Optional[str]
    raw: str


def parse_gold(gold_answer) -> Gold:
    s = str(gold_answer).strip()
    low = s.lower().rstrip(" .")
    if low in ("yes", "no"):
        return Gold("yes_no", None, 0, low, s)
    m = _RATIO.fullmatch(s)
    if m:
        return Gold("number", to_decimal(m.group(1)) / to_decimal(m.group(2)), 3, None, s)
    nums = find_numbers(s)
    if len(nums) != 1 or re.search(r"[a-z]{4,}", low.replace("per share", "")):
        return Gold("unsupported", None, 0, None, s)
    n = nums[0]
    body = n.raw.replace("$", "").replace("%", "").replace("(", "").replace(")", "").strip().lstrip("-")
    d = len(body.split(".")[1]) if "." in body else 0
    return Gold("percent" if n.is_percent else "number", n.value, d, None, s)


@dataclass
class EvalResult:
    outcome: str
    lenient_correct: Optional[bool]
    strict_correct: Optional[bool]
    predicted: Optional[str]
    gold: str
    relative_error: Optional[str]
    note: str
    extraction_method: str

    def to_dict(self):
        return asdict(self)


def _rel(a: Decimal, b: Decimal) -> Decimal:
    return abs(a - b) / abs(b) if b != 0 else abs(a - b)


def _matches_at_precision(p: Decimal, g: Decimal, d: int) -> bool:
    q = Decimal(1).scaleb(-d)
    return p.quantize(q, rounding=ROUND_HALF_UP) == g.quantize(q, rounding=ROUND_HALF_UP)


_DIRECTION = re.compile(r"\b(?:decrease[sd]?|decline[sd]?|reduction|reduced|fell|drop(?:ped)?|lower|"
                        r"less|loss|in favou?r of)\b", re.I)


def evaluate(model_text: str, gold_answer, rel_tol: Decimal = Decimal("0.01"),
             question: Optional[str] = None) -> EvalResult:
    gold = parse_gold(gold_answer)
    ans = extract_yes_no(model_text) if gold.kind == "yes_no" else extract_final_answer(model_text)
    if gold.kind == "unsupported":
        return EvalResult("NOT_EVALUATED", None, None, None, gold.raw, None, "gold is not a single value", ans.method)
    if gold.kind == "yes_no":
        if ans.yes_no is None:
            out = "REFUSED" if ans.refused else "NO_ANSWER"
            return EvalResult(out, False, False, None, gold.raw, None, "", ans.method)
        ok = ans.yes_no == gold.yes_no
        return EvalResult("CORRECT" if ok else "INCORRECT", ok, ok, ans.yes_no, gold.raw, None, "", ans.method)
    if ans.value is None:
        out = "REFUSED" if ans.refused else "NO_ANSWER"
        return EvalResult(out, False, False, None, gold.raw, None, "", ans.method)
    p, g = ans.value, gold.value
    note = ""
    cands = [(p, "")]
    if gold.kind == "percent" and not ans.is_percent:
        cands.append((p * 100, "fraction given for a percent"))
    if gold.kind == "number" and ans.is_percent:
        cands.append((p / 100, "percent given for a fraction"))
    best = min(cands, key=lambda c: _rel(abs(c[0]), abs(g)))   # choose the scale by magnitude, judge sign after
    p, note = best
    if _matches_at_precision(p, g, gold.decimals):
        return EvalResult("CORRECT", True, True, str(ans.value), gold.raw, str(_rel(p, g)), note, ans.method)
    r = _rel(p, g)
    raw_p = (ans.raw or "")
    mdec = 0
    mm = re.search(r"\d+\.(\d+)", raw_p)
    if mm:
        mdec = len(mm.group(1))
    coarser = mdec < gold.decimals and _matches_at_precision(g, p, mdec)
    if r <= rel_tol or coarser:
        note = (note + "; " if note else "") + ("model rounded more coarsely than gold" if coarser and r > rel_tol else "")
        note = note.strip("; ")
        return EvalResult("ROUNDING_ONLY", True, False, str(ans.value), gold.raw, str(r), note, ans.method)
    if g != 0 and (_rel(-p, g) <= rel_tol or _matches_at_precision(-p, g, gold.decimals)):
        raw_num = (ans.raw or "").strip("* ")
        pos = (model_text or "").rfind(raw_num[:12]) if raw_num else -1
        window = (model_text or "")[max(0, pos - 80):pos + len(raw_num) + 40] if pos >= 0 else ""
        if _DIRECTION.search(window) or (question and _DIRECTION.search(question)):
            return EvalResult("SIGN_CONVENTION", True, False, str(ans.value), gold.raw, str(r),
                              "direction stated in words or asked in the question", ans.method)
        return EvalResult("SIGN_MISMATCH", False, False, str(ans.value), gold.raw, str(r), note, ans.method)
    for k in (3, 6, 9, -3, -6, -9):
        if g != 0 and _rel(p * Decimal(10) ** k, g) <= rel_tol:
            return EvalResult("SCALE_MISMATCH", False, False, str(ans.value), gold.raw, str(r),
                              f"off by 10^{-k}", ans.method)
    return EvalResult("INCORRECT", False, False, str(ans.value), gold.raw, str(r), note, ans.method)
