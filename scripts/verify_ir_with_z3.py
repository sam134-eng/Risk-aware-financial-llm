import ast
import json
from decimal import Decimal
from pathlib import Path
from z3 import Real, RealVal, Solver, Abs, sat, unsat


def to_z3_real(value):
    num = Decimal(str(value).replace(",", "").strip())
    n, d = num.as_integer_ratio()
    return RealVal(n) / RealVal(d)


def eval_z3_ast(node, z3_vars):
    """Safely evaluate arithmetic AST nodes including Power (** or ^) for Z3."""
    if isinstance(node, ast.Expression):
        return eval_z3_ast(node.body, z3_vars)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return to_z3_real(node.value)
        raise ValueError(f"Unsupported constant: {node.value}")
    if isinstance(node, ast.Name):
        if node.id not in z3_vars:
            raise ValueError(f"Undefined variable: {node.id}")
        return z3_vars[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = eval_z3_ast(node.operand, z3_vars)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        raise ValueError(f"Unsupported unary op: {node.op}")
    if isinstance(node, ast.BinOp):
        left = eval_z3_ast(node.left, z3_vars)
        right = eval_z3_ast(node.right, z3_vars)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError(f"Unsupported binary op: {node.op}")
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


def parse_expression(expr_str, z3_vars):
    clean_expr = str(expr_str).replace("^", "**").strip()
    tree = ast.parse(clean_expr, mode="eval")
    return eval_z3_ast(tree, z3_vars)


def verify_ir_entry(ir_obj, default_tol="0.01"):
    if not isinstance(ir_obj, dict):
        return {"status": "NOT_APPLICABLE", "reason": "Empty or abstained IR"}

    solver = Solver()
    solver.set(unsat_core=True)
    z3_vars = {}

    try:
        # 1. Load extracted variables into Z3
        variables = ir_obj.get("variables", [])
        if isinstance(variables, dict):
            for name, val in variables.items():
                z3_vars[name] = Real(name)
                solver.assert_and_track(
                    z3_vars[name] == to_z3_real(val), f"var_{name}"
                )
        elif isinstance(variables, list):
            for item in variables:
                name = item["name"]
                z3_vars[name] = Real(name)
                solver.assert_and_track(
                    z3_vars[name] == to_z3_real(item["value"]), f"var_{name}"
                )

        # 2. Add all equations to Z3 (supports +, -, *, /, and ** / ^)
        equations = ir_obj.get("equations", [])
        if not equations:
            return {"status": "NOT_APPLICABLE", "reason": "No equations in IR"}

        for idx, eq in enumerate(equations):
            lhs = eq["lhs"]
            rhs = eq["rhs"]
            eq_id = eq.get("id", f"eq_{idx+1}")
            if lhs not in z3_vars:
                z3_vars[lhs] = Real(lhs)
            rhs_expr = parse_expression(rhs, z3_vars)
            solver.assert_and_track(z3_vars[lhs] == rhs_expr, f"constraint_{eq_id}")

        # 3. Check claimed answer against tolerance
        claimed_info = ir_obj.get("claimed_answer", {})
        target = claimed_info.get("target_variable")
        claimed_val = claimed_info.get("predicted_value")
        tol = claimed_info.get("tolerance", default_tol)

        if target not in z3_vars or claimed_val is None:
            return {"status": "NOT_APPLICABLE", "reason": "Missing target or claimed value"}

        solver.assert_and_track(
            Abs(z3_vars[target] - to_z3_real(claimed_val)) > to_z3_real(tol),
            "claim_check",
        )

        res = solver.check()

        if res == unsat:
            return {
                "status": "PASS",
                "reason": "Z3 verified mathematical consistency within tolerance.",
            }
        elif res == sat:
            return {
                "status": "FAIL",
                "reason": "Z3 detected arithmetic mismatch beyond tolerance.",
            }
        return {"status": "UNKNOWN", "reason": "Z3 returned unknown (non-linear power)."}

    except Exception as e:
        return {"status": "NOT_APPLICABLE", "reason": f"Parse/Solver error: {e}"}


def run_on_jsonl(jsonl_path, output_path):
    path = Path(jsonl_path)
    if not path.exists():
        print(f"File not found: {jsonl_path}")
        return

    counts = {"PASS": 0, "FAIL": 0, "NOT_APPLICABLE": 0, "UNKNOWN": 0}
    detailed = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            case_id = record.get("case_id") or record.get("question_id")
            ir = record.get("ir", record)
            verdict = verify_ir_entry(ir)
            counts[verdict["status"]] += 1
            detailed.append({"case_id": case_id, "verification": verdict})

    out = {"file": str(jsonl_path), "summary": counts, "results": detailed}
    Path(output_path).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n=== Z3 Verification: {jsonl_path} ===")
    print(counts)
    print(f"Saved detailed results to: {output_path}")


if __name__ == "__main__":
    run_on_jsonl(
        "results/pilot_3shot.jsonl",
        "results/z3_pilot_3shot_results.json"
    )
    run_on_jsonl(
        "results/pilot_8shot.jsonl",
        "results/z3_pilot_8shot_results.json"
    )
