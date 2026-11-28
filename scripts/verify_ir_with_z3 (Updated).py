"""Z3 verification of LLM-extracted IRs (variables + equations + claimed answer).

Statuses: PASS (claim entailed within tolerance), FAIL (IR consistent but entails another
value), UNDERDETERMINED (claim possible, not forced), INCONSISTENT_IR (constraints contradict),
NOT_APPLICABLE (missing/malformed/unsupported IR), UNKNOWN (Z3 unknown/timeout).
PASS means the claim follows from the IR, not that the IR matches the problem.
Tolerance is absolute (default 0.01), as in the original script.
"""
import ast
import csv
import json
import operator
from decimal import Decimal, InvalidOperation
from pathlib import Path

from z3 import Not, Or, Real, RealVal, Solver, sat, unsat

STATUSES = ("PASS", "FAIL", "UNDERDETERMINED", "INCONSISTENT_IR", "NOT_APPLICABLE", "UNKNOWN")
TIMEOUT_MS = 10_000
ADJUDICATION_CSV = "results/gold_audit/gold_adjudication_30.csv"
# Bad/unsupported IR content -> abstain. Any other exception is a real bug and propagates.
EXPECTED_ERRORS = (ValueError, SyntaxError, ArithmeticError, RecursionError)
BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow}


def clean_numeric_value(value):
    """Normalize currency, commas, percentages, or fractions into a finite Decimal."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Not a numeric value: {value!r}")
    if isinstance(value, (Decimal, int, float)):
        dec = Decimal(str(value))
    else:
        s = str(value).strip()
        is_percent = s.endswith("%")
        s = (s[:-1] if is_percent else s).replace(",", "").replace("$", "").strip()
        try:
            num, _, den = s.partition("/")  # simple fractions like "3/4" or "-10/3"
            dec = Decimal(num.strip()) / Decimal(den.strip()) if "/" in s else Decimal(s)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc
        if is_percent:
            dec /= 100
    if not dec.is_finite():
        raise ValueError(f"Non-finite numeric value: {value!r}")
    return dec


def to_z3_real(value):
    n, d = clean_numeric_value(value).as_integer_ratio()
    return RealVal(f"{n}/{d}")


def z3_val_to_float(z3_expr):
    if hasattr(z3_expr, "as_fraction"):
        return float(z3_expr.as_fraction())
    return float(Decimal(z3_expr.as_decimal(12).rstrip("?")))


def eval_z3_ast(node, z3_vars, guards):
    """Evaluate + - * / ** over an AST. Every division adds a `denominator != 0` guard."""
    if isinstance(node, ast.Expression):
        return eval_z3_ast(node.body, z3_vars, guards)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return to_z3_real(node.value)
    if isinstance(node, ast.Name) and node.id in z3_vars:
        return z3_vars[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        operand = eval_z3_ast(node.operand, z3_vars, guards)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
        left = eval_z3_ast(node.left, z3_vars, guards)
        right = eval_z3_ast(node.right, z3_vars, guards)
        if isinstance(node.op, ast.Div):
            guards.append(right != 0)
        return BIN_OPS[type(node.op)](left, right)
    raise ValueError(f"Unsupported or undefined expression: {ast.dump(node)[:80]}")


def parse_expression(expr_str, z3_vars, guards):
    tree = ast.parse(str(expr_str).replace("^", "**").strip(), mode="eval")  # empty -> SyntaxError
    return eval_z3_ast(tree, z3_vars, guards)


def _add(solver, constraint, label, track):
    solver.assert_and_track(constraint, label) if track else solver.add(constraint)


def add_variables_to_solver(variables, solver, z3_vars, track=False):
    if isinstance(variables, dict):
        variables = [{"name": k, "value": v} for k, v in variables.items()]
    if not isinstance(variables, list):
        raise ValueError("Unsupported variables container")
    for item in variables:
        if not isinstance(item, dict) or not str(item.get("name", "")).strip() or "value" not in item:
            raise ValueError(f"Malformed variable entry: {item!r}")
        name = str(item["name"]).strip()
        z3_vars.setdefault(name, Real(name))
        _add(solver, z3_vars[name] == to_z3_real(item["value"]), f"var:{name}", track)


def add_equations_to_solver(equations, solver, z3_vars, track=False):
    if not isinstance(equations, list) or not equations:
        raise ValueError("No equations in IR")
    for eq in equations:  # declare every LHS first so equation order does not matter
        if not isinstance(eq, dict) or not str(eq.get("lhs", "")).strip() or "rhs" not in eq:
            raise ValueError(f"Malformed equation entry: {eq!r}")
        z3_vars.setdefault(str(eq["lhs"]).strip(), Real(str(eq["lhs"]).strip()))
    for idx, eq in enumerate(equations):
        lhs, guards = str(eq["lhs"]).strip(), []
        rhs = parse_expression(eq["rhs"], z3_vars, guards)
        label = f"{idx + 1}:{eq.get('id', '')}:{lhs}"
        _add(solver, z3_vars[lhs] == rhs, f"eq:{label}", track)
        for k, guard in enumerate(guards):
            _add(solver, guard, f"guard:{label}:{k}", track)


def build_solver(ir_obj, track=False):
    solver = Solver()
    solver.set("timeout", TIMEOUT_MS, unsat_core=track)
    z3_vars = {}
    add_variables_to_solver(ir_obj.get("variables", []), solver, z3_vars, track)
    add_equations_to_solver(ir_obj.get("equations", []), solver, z3_vars, track)
    return solver, z3_vars


def extract_unsat_core_feedback(ir_obj, target, claimed_val):
    """Unsat core (not guaranteed minimal) of the IR constraints plus the claimed answer."""
    solver, z3_vars = build_solver(ir_obj, track=True)
    solver.assert_and_track(z3_vars[target] == to_z3_real(claimed_val), "claimed_answer")
    return sorted(str(c) for c in solver.unsat_core()) if solver.check() == unsat else []


def _check(solver, constraint):
    solver.push()
    solver.add(constraint)
    result = solver.check()
    solver.pop()
    return result


def _res(status, reason, **extra):
    return {"status": status, "reason": reason, **extra}


def verify_ir_entry(ir_obj, default_tol="0.01", override_claimed_val=None):
    if not isinstance(ir_obj, dict):
        return _res("NOT_APPLICABLE", "Empty or abstained IR")
    try:
        solver, z3_vars = build_solver(ir_obj)
        claimed_info = ir_obj.get("claimed_answer")
        if not isinstance(claimed_info, dict):
            claimed_info = {}
        target = claimed_info.get("target_variable")
        claimed_val = claimed_info.get("predicted_value")
        claimed_val = claimed_val if override_claimed_val is None else override_claimed_val
        if not target or target not in z3_vars or claimed_val is None:
            return _res("NOT_APPLICABLE", "Missing target or claimed value")

        raw_tol = default_tol if claimed_info.get("tolerance") is None else claimed_info["tolerance"]
        tol = clean_numeric_value(raw_tol)  # check the Decimal, not a Z3 expression
        if tol < 0:
            raise ValueError(f"Tolerance cannot be negative: {raw_tol}")
        tol_z3, claim_z3, var = to_z3_real(tol), to_z3_real(claimed_val), z3_vars[target]
        info = {"target_variable": target, "claimed_value": claimed_val, "tolerance": raw_tol}

        base = solver.check()  # Stage 1: are the IR constraints consistent?
        if base == unsat:
            return _res("INCONSISTENT_IR", "Constraints contradict.", **info)
        if base != sat:
            return _res("UNKNOWN", "Consistency check unresolved.", **info)
        model = solver.model()

        # Stage 2: can the target fall outside tolerance of the claim? Stage 3: or inside?
        outside = Or(var > claim_z3 + tol_z3, var < claim_z3 - tol_z3)
        res_out = _check(solver, outside)
        if res_out == unsat:
            return _res("PASS", "Z3 proved the claim within tolerance.", **info)
        res_in = _check(solver, Not(outside)) if res_out == sat else None
        if res_in not in (sat, unsat):
            return _res("UNKNOWN", "Z3 returned unknown.", **info)

        value = model.evaluate(var, model_completion=True)
        try:
            example = round(z3_val_to_float(value), 6)
        except Exception:
            example = str(value)
        if res_in == sat:
            return _res("UNDERDETERMINED", "Claim consistent with the IR but not forced.",
                        z3_example_value=example, **info)
        return _res("FAIL", f"Z3 mismatch: equations yield {example}, but claimed {claimed_val}.",
                    z3_expected_value=example, **info,
                    unsat_core=extract_unsat_core_feedback(ir_obj, target, claimed_val))
    except EXPECTED_ERRORS as error:
        return _res("NOT_APPLICABLE", f"Parse/validation error: {error}")


def load_adjudicated_overrides(csv_path=ADJUDICATION_CSV):
    """Exclude BOTH_WRONG/AMBIGUOUS; ANSWER_WRONG -> program_value; PROGRAM_WRONG -> gold_answer.
    Raises FileNotFoundError if the CSV is missing (no silent change of denominators)."""
    excluded, refs = set(), {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cid, verdict = str(row["case_id"]).strip(), row["verdict"].strip()
            if verdict in {"BOTH_WRONG", "AMBIGUOUS"}:
                excluded.add(cid)
            elif verdict == "ANSWER_WRONG":
                refs[cid] = row["program_value"].strip()
            elif verdict == "PROGRAM_WRONG":
                refs[cid] = row["gold_answer"].strip()
    return excluded, refs


def run_on_jsonl(jsonl_path, output_path, use_adjudicated_refs=False,
                 exclude_adjudicated=True, adjudication_csv=ADJUDICATION_CSV):
    excluded, refs = (load_adjudicated_overrides(adjudication_csv)
                      if exclude_adjudicated or use_adjudicated_refs else (set(), {}))
    excluded, refs = (excluded if exclude_adjudicated else set()), (refs if use_adjudicated_refs else {})

    ids_by_status, detailed, n_excluded = {s: [] for s in STATUSES}, [], 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            cid = next((str(record[k]) for k in ("case_id", "question_id")
                        if record.get(k) is not None), f"line_{lineno}")  # ids as strings
            if cid in excluded:
                n_excluded += 1
                continue
            verdict = verify_ir_entry(record.get("ir", record), override_claimed_val=refs.get(cid))
            ids_by_status[verdict["status"]].append(cid)
            detailed.append({"case_id": cid, "verification": verdict})

    summary = {k: len(v) for k, v in ids_by_status.items()}
    out = {"file": str(jsonl_path), "summary": summary, "case_ids": ids_by_status,
           "config": {"use_adjudicated_refs": use_adjudicated_refs,
                      "exclude_adjudicated": exclude_adjudicated, "n_excluded_seen": n_excluded},
           "results": detailed}
    Path(output_path).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n=== Z3 Verification: {jsonl_path} ===\nCounts:", summary, f"(excluded: {n_excluded})")
    for status in STATUSES[:5]:
        print(f"{status:16}:", ids_by_status[status])


if __name__ == "__main__":
    for name in ("3shot", "8shot"):
        run_on_jsonl(f"pilot_{name}.jsonl", f"z3_pilot_{name}_results.json",
                     use_adjudicated_refs=False, exclude_adjudicated=True)
