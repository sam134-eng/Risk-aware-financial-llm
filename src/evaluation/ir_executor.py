"""Safely execute the equations of a JSON IR (no eval) and check the claimed answer.

Supports + - * / ** unary minus, comparisons, and abs/min/max/round/sum/avg/mean/sqrt.
Equations run in order; each lhs becomes available to later equations.
"""
from __future__ import annotations

import ast
from decimal import Decimal, getcontext
from typing import Any, Dict, Optional, Tuple

from src.grounding.numbers import to_decimal

getcontext().prec = 34
__all__ = ["execute_ir", "IRExecutionError"]


class IRExecutionError(ValueError):
    pass


def _ev(node, env):
    if isinstance(node, ast.Expression):
        return _ev(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return to_decimal(node.value)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise IRExecutionError(f"undefined variable {node.id}")
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _ev(node.operand, env)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _ev(node.left, env), _ev(node.right, env)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            if b == 0:
                raise IRExecutionError("division by zero")
            return a / b
        if isinstance(node.op, ast.Pow):
            if abs(b) > 1000:
                raise IRExecutionError("exponent too large")
            return a ** b if b == b.to_integral_value() else Decimal(float(a) ** float(b))
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        a, b = _ev(node.left, env), _ev(node.comparators[0], env)
        op = node.ops[0]
        r = {ast.Gt: a > b, ast.GtE: a >= b, ast.Lt: a < b, ast.LtE: a <= b, ast.Eq: a == b, ast.NotEq: a != b}.get(type(op))
        if r is None:
            raise IRExecutionError("unsupported comparison")
        return Decimal(1) if r else Decimal(0)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = [_ev(a, env) for a in node.args]
        f = node.func.id
        if f == "abs" and len(args) == 1:
            return abs(args[0])
        if f in ("min", "max") and args:
            return (min if f == "min" else max)(args)
        if f == "round" and 1 <= len(args) <= 2:
            return round(args[0], int(args[1]) if len(args) == 2 else 0)
        if f == "sum" and args:
            return sum(args, Decimal(0))
        if f in ("avg", "mean") and args:
            return sum(args, Decimal(0)) / len(args)
        if f == "sqrt" and len(args) == 1:
            return args[0].sqrt()
    raise IRExecutionError(f"unsupported expression: {ast.dump(node)[:80]}")


def execute_ir(ir: Dict[str, Any]) -> Tuple[Optional[Decimal], Dict[str, str]]:
    """Return (target value, info). info['status'] in OK | MISMATCH | ERROR | NO_TARGET."""
    env: Dict[str, Decimal] = {}
    for v in ir.get("variables") or []:
        if isinstance(v, dict) and v.get("name") and v.get("value") is not None:
            try:
                env[str(v["name"])] = to_decimal(v["value"])
            except ValueError:
                pass
    try:
        for eq in ir.get("equations") or []:
            env[str(eq["lhs"])] = _ev(ast.parse(str(eq["rhs"]), mode="eval"), env)
    except (SyntaxError, KeyError, IRExecutionError, ArithmeticError) as exc:
        return None, {"status": "ERROR", "message": str(exc)}
    ca = ir.get("claimed_answer") or {}
    tgt = ca.get("target_variable")
    if not tgt or tgt not in env:
        return None, {"status": "NO_TARGET", "message": f"target {tgt!r} not computed"}
    val = env[tgt]
    info = {"status": "OK", "computed": str(val)}
    if ca.get("predicted_value") is not None:
        try:
            pv = to_decimal(ca["predicted_value"])
            tol = to_decimal(ca.get("tolerance", 0) or 0)
            if abs(pv - val) > max(tol, abs(val) * Decimal("1e-9")):
                info["status"] = "MISMATCH"
                info["message"] = f"claimed {pv} but equations give {val}"
        except ValueError:
            info["status"] = "MISMATCH"
            info["message"] = "predicted_value not numeric"
    return val, info
