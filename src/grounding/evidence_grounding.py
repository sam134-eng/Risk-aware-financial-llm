"""Fine-grained evidence grounding checker for FinVerify-SMT JSON IR.

Checks that every numerical input in an IR is supported by the case's
evidence (table cell, text span, question text or structured evidence),
with sign, percent and scale/unit handling. It is deterministic and does
not call any LLM.

Grounding is NOT answer correctness: a correctly grounded IR can still use
the wrong metric, denominator or period. Those are checked elsewhere.

Statuses
--------
PASS            every source variable grounded; no unsupported constants or undefined names
PARTIAL         no hard errors, but some numbers have no source (missing source,
                undefined variable, unsupported literal constant)
FAIL            at least one value mismatch, invalid source reference or unit error
NOT_APPLICABLE  IR malformed, or it contains nothing to ground
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .numbers import ParsedNumber, to_decimal
from .source_resolver import ResolvedSource, SourceError, resolve
from .unit_normalizer import Unit, UnitError, convert, detect_scale_near, parse_unit

__all__ = ["check_grounding", "GroundingResult", "VariableTrace", "DEFAULT_ALLOWED_CONSTANTS"]

PASS, PARTIAL, FAIL, NA = "PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE"

# Literal numbers allowed in equations / as constants without a source:
# unit factors, percent/bp conversions, small counts for averages, period counts.
DEFAULT_ALLOWED_CONSTANTS = frozenset(
    Decimal(x) for x in ("0", "1", "2", "3", "4", "5", "12", "100", "360", "365",
                         "1000", "10000", "1000000", "1000000000", "-1")
)
_FUNCS = {"abs", "min", "max", "round", "sum", "avg", "mean", "pow", "exp", "log", "sqrt"}
_SCALE_STEPS = [Decimal(10) ** k for k in (-9, -6, -3, 3, 6, 9)]


@dataclass
class VariableTrace:
    name: str
    status: str                       # GROUNDED | MISMATCH | UNIT_ERROR | INVALID_SOURCE | UNGROUNDED | CONSTANT | DERIVED | UNSUPPORTED_CONSTANT
    source_ref: Optional[str] = None
    source_kind: Optional[str] = None
    source_text: Optional[str] = None
    original_value: Optional[str] = None    # raw string in the evidence
    extracted_value: Optional[str] = None   # value in the IR
    normalized_value: Optional[str] = None  # IR value converted to the source's unit
    declared_unit: Optional[str] = None
    source_unit: Optional[str] = None
    char_span: Optional[Tuple[int, int]] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class GroundingResult:
    question_id: Optional[str]
    grounding_status: str
    total_variables: int = 0
    grounded_variables: List[str] = field(default_factory=list)
    ungrounded_variables: List[str] = field(default_factory=list)
    mismatched_variables: List[str] = field(default_factory=list)
    invalid_source_references: List[str] = field(default_factory=list)
    unit_errors: List[str] = field(default_factory=list)
    unsupported_constants: List[str] = field(default_factory=list)
    detailed_error_messages: List[Dict[str, str]] = field(default_factory=list)
    variables: List[VariableTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# --------------------------------------------------------------------- helpers

def _err(res: GroundingResult, code: str, var: Optional[str], msg: str) -> None:
    res.detailed_error_messages.append({"code": code, "variable": var or "", "message": msg})


def _close(a: Decimal, b: Decimal, rel: Decimal) -> bool:
    return abs(a - b) <= rel * max(Decimal(1), abs(b))


def _source_unit_for(cand: ParsedNumber, src: ResolvedSource, declared: Unit) -> Tuple[Optional[Unit], str]:
    """Infer the unit of a source number. Returns (unit or None if unknown, description)."""
    if cand.is_percent:
        return Unit("percent", Decimal(1), None, "percent"), "percent sign in source"
    if src.kind == "structured" and src.structured_unit:
        try:
            return parse_unit(src.structured_unit), f"structured unit {src.structured_unit}"
        except UnitError:
            return None, f"unparsed structured unit {src.structured_unit}"
    near = detect_scale_near(src.text, cand.end) if cand.end >= 0 else None
    scale = near or src.header_scale
    if declared.dimension in ("currency", "count", "shares"):
        if scale is None:
            return None, "no scale stated in evidence"
        how = "scale word after number" if near else "table/paragraph header"
        return Unit(declared.dimension, scale, declared.currency, f"{declared.dimension}x{scale}"), how
    return None, "source dimension not stated"


def _match_candidate(value: Decimal, declared: Unit, cand: ParsedNumber, src: ResolvedSource,
                     rel: Decimal) -> Tuple[str, Optional[Decimal], str, Optional[Unit]]:
    """Compare one IR value with one source number.

    Returns (outcome, normalized_value, note, source_unit) where outcome is
    'match' | 'match_unverified_unit' | 'sign' | 'unit' | 'none'.
    """
    src_unit, how = _source_unit_for(cand, src, declared)
    n = cand.value
    if src_unit is not None and declared.dimension != "unknown":
        try:
            # express the source number in the IR's declared unit
            expected = convert(n, src_unit, declared)
        except UnitError as exc:
            if _close(value, n, rel) or _close(abs(value), abs(n), rel):
                return "unit", None, f"declared unit {declared} incompatible with source ({exc})", src_unit
            return "none", None, "", src_unit
        if _close(value, expected, rel):
            return "match", value, f"source unit: {src_unit} ({how})", src_unit
        if _close(abs(value), abs(expected), rel):
            return "sign", None, "same magnitude, opposite sign", src_unit
        if _close(value, n, rel) and (src_unit.scale != declared.scale
                                       or src_unit.dimension != declared.dimension):
            return "unit", None, (f"value copied without scale conversion: source is {src_unit} ({how}), "
                                  f"IR declares {declared}"), src_unit
        for k in _SCALE_STEPS:
            if _close(value, expected * k, rel):
                return "unit", None, (f"value is off by a factor of {k} relative to the source in the declared "
                                      f"unit {declared}"), src_unit
        return "none", None, "", src_unit
    # source unit unknown (or declared unit unknown): compare raw values
    if _close(value, n, rel):
        return "match_unverified_unit", value, f"unit not verifiable: {how}", None
    if declared.dimension in ("percent", "ratio") and not cand.is_percent:
        if declared.dimension == "ratio" and _close(value * 100, n, rel):
            return "match_unverified_unit", value, "source number read as a percentage without %", None
    if _close(abs(value), abs(n), rel):
        return "sign", None, "same magnitude, opposite sign", None
    for k in _SCALE_STEPS:
        if _close(value, n * k, rel):
            return "unit", None, (f"value equals source × {k}, but the evidence states no scale that "
                                  f"justifies this conversion"), None
    return "none", None, "", None


def _equation_symbols(rhs: str) -> Tuple[List[str], List[Decimal]]:
    tree = ast.parse(rhs, mode="eval")
    names, consts = [], []
    funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            funcs.add(node.func.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in funcs:
            names.append(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            consts.append(to_decimal(node.value))
    unknown_funcs = funcs - _FUNCS
    if unknown_funcs:
        raise ValueError(f"unsupported function(s): {sorted(unknown_funcs)}")
    return names, consts


# --------------------------------------------------------------------- main

def check_grounding(ir: Dict[str, Any], case: Dict[str, Any], *,
                    rel_tolerance: float = 1e-12,
                    sign_policy: str = "strict",
                    allowed_constants: Iterable = DEFAULT_ALLOWED_CONSTANTS) -> GroundingResult:
    """Check every numerical variable of ``ir`` against ``case`` evidence.

    ``ir``   – team JSON IR (``variables``, ``equations``, ``claimed_answer``).
    ``case`` – one benchmark record (FinQA ``evidence_context`` or manual ``evidence``).
    ``rel_tolerance`` – relative tolerance for value equality (guards float noise only;
      grounding is meant to be exact, rounding is NOT accepted).
    ``sign_policy`` – "strict": opposite sign is a mismatch (FAIL); "warn": accepted as
      grounded with a SIGN_DIFFERS note (for questions that ask for a magnitude).
    """
    if sign_policy not in ("strict", "warn"):
        raise ValueError("sign_policy must be 'strict' or 'warn'")
    qid = ir.get("question_id") if isinstance(ir, dict) else None
    res = GroundingResult(question_id=qid, grounding_status=NA)
    rel = Decimal(str(rel_tolerance))
    allowed = {to_decimal(c) for c in allowed_constants}

    if not isinstance(ir, dict) or not isinstance(ir.get("variables"), list):
        _err(res, "INVALID_IR", None, "IR must be an object with a 'variables' list")
        return res
    variables = ir["variables"]
    equations = ir.get("equations") or []
    if not isinstance(equations, list):
        _err(res, "INVALID_IR", None, "'equations' must be a list")
        return res
    res.total_variables = len(variables)

    lhs_names = {e.get("lhs") for e in equations if isinstance(e, dict) and e.get("lhs")}
    defined = set()
    n_source = 0

    for i, var in enumerate(variables):
        if not isinstance(var, dict) or not var.get("name"):
            _err(res, "INVALID_IR", None, f"variable #{i} has no name")
            res.ungrounded_variables.append(f"#{i}")
            continue
        name = str(var["name"])
        defined.add(name)
        kind = (var.get("kind") or "").lower()
        ref = var.get("source_grounding")
        tr = VariableTrace(name=name, status="UNGROUNDED", source_ref=ref,
                           extracted_value=None if var.get("value") is None else str(var.get("value")),
                           declared_unit=var.get("unit"))
        res.variables.append(tr)

        if kind in ("derived", "intermediate") or (name in lhs_names and not ref):
            tr.status = "DERIVED"
            continue
        if kind == "constant" or ref == "constant":
            try:
                v = to_decimal(var.get("value"))
            except ValueError:
                tr.status = "UNSUPPORTED_CONSTANT"
                res.unsupported_constants.append(name)
                _err(res, "INVALID_VALUE", name, f"constant {name} has no numeric value")
                continue
            if v in allowed:
                tr.status = "CONSTANT"
            else:
                tr.status = "UNSUPPORTED_CONSTANT"
                res.unsupported_constants.append(name)
                _err(res, "UNSUPPORTED_CONSTANT", name,
                     f"constant {name} = {v} is not a standard mathematical/unit constant and has no source")
            continue

        n_source += 1
        if not ref:
            res.ungrounded_variables.append(name)
            _err(res, "MISSING_SOURCE", name, f"{name} has no source_grounding")
            continue
        try:
            value = to_decimal(var.get("value"))
        except ValueError:
            tr.status = "MISMATCH"
            res.mismatched_variables.append(name)
            _err(res, "INVALID_VALUE", name, f"{name} value {var.get('value')!r} is not numeric")
            continue
        try:
            declared = parse_unit(var.get("unit"))
        except UnitError:
            # an unrecognised unit label is not an evidence error: compare the raw value
            declared = Unit("unknown", Decimal(1), None, str(var.get("unit")))
            tr.notes.append(f"unit label {var.get('unit')!r} not recognised; unit not verified")
        try:
            src = resolve(ref, case)
        except SourceError as exc:
            tr.status = "INVALID_SOURCE"
            res.invalid_source_references.append(name)
            _err(res, "INVALID_SOURCE", name, str(exc))
            continue
        tr.source_kind, tr.source_text = src.kind, src.text
        if not src.numbers:
            tr.status = "MISMATCH"
            res.mismatched_variables.append(name)
            _err(res, "NO_NUMBER_IN_SOURCE", name, f"{ref} contains no number")
            continue

        best = None
        outcomes = []
        for cand in src.numbers:
            out = _match_candidate(value, declared, cand, src, rel)
            outcomes.append((out, cand))
            rank = {"match": 0, "match_unverified_unit": 1, "unit": 2, "sign": 3, "none": 9}[out[0]]
            if best is None or rank < best[0]:
                best = (rank, out, cand)
        rank, (outcome, normv, note, sunit), cand = best
        tr.original_value = cand.raw
        tr.char_span = (cand.start, cand.end) if cand.start >= 0 else None
        tr.source_unit = str(sunit) if sunit else None
        if note:
            tr.notes.append(note)
        n_matches = sum(1 for (o, _) in outcomes if o[0] in ("match", "match_unverified_unit"))
        if n_matches > 1:
            tr.notes.append(f"value occurs {n_matches} times in this source")
        if src.kind == "question":
            tr.notes.append("grounded in the question text, not the filing")

        if outcome in ("match", "match_unverified_unit"):
            tr.status = "GROUNDED"
            tr.normalized_value = str(normv)
            res.grounded_variables.append(name)
        elif outcome == "unit":
            tr.status = "UNIT_ERROR"
            res.unit_errors.append(name)
            _err(res, "UNIT_ERROR", name, f"{name}: {note}")
        elif outcome == "sign" and sign_policy == "warn":
            tr.status = "GROUNDED"
            tr.normalized_value = str(value)
            tr.notes.append("SIGN_DIFFERS: IR uses the magnitude of a signed source value")
            res.grounded_variables.append(name)
        elif outcome == "sign":
            tr.status = "MISMATCH"
            res.mismatched_variables.append(name)
            _err(res, "SIGN_MISMATCH", name, f"{name} = {value} but source shows {cand.raw}")
        else:
            tr.status = "MISMATCH"
            res.mismatched_variables.append(name)
            shown = ", ".join(c.raw for c in src.numbers[:8])
            _err(res, "VALUE_MISMATCH", name, f"{name} = {value} not found in {ref} (numbers there: {shown})")

    # equations: undefined names and literal constants
    for eq in equations:
        if not isinstance(eq, dict) or not eq.get("rhs"):
            _err(res, "INVALID_IR", None, f"equation without rhs: {eq!r}")
            continue
        try:
            names, consts = _equation_symbols(str(eq["rhs"]))
        except (SyntaxError, ValueError) as exc:
            _err(res, "INVALID_EQUATION", eq.get("id"), f"{eq.get('id')}: {exc}")
            continue
        for nm in names:
            if nm not in defined and nm not in lhs_names:
                if nm not in res.ungrounded_variables:
                    res.ungrounded_variables.append(nm)
                _err(res, "UNDEFINED_VARIABLE", nm, f"{eq.get('id')}: {nm} is used but never defined")
        for c in consts:
            if c not in allowed:
                label = f"{eq.get('id')}:{c}"
                res.unsupported_constants.append(label)
                _err(res, "UNSUPPORTED_CONSTANT", None,
                     f"{eq.get('id')}: literal {c} in equation has no source")

    ca = ir.get("claimed_answer") or {}
    tgt = ca.get("target_variable") if isinstance(ca, dict) else None
    if tgt and tgt not in defined and tgt not in lhs_names:
        _err(res, "TARGET_UNDEFINED", tgt, f"target variable {tgt} is not defined (formalization error)")

    # overall status
    if res.mismatched_variables or res.invalid_source_references or res.unit_errors:
        res.grounding_status = FAIL
    elif n_source == 0 and not res.ungrounded_variables and not res.unsupported_constants:
        res.grounding_status = NA
        _err(res, "NOTHING_TO_GROUND", None, "IR has no source-derived variables")
    elif res.ungrounded_variables or res.unsupported_constants:
        res.grounding_status = PARTIAL
    else:
        res.grounding_status = PASS
    return res
