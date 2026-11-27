from decimal import Decimal as D
from src.evaluation.ir_executor import execute_ir


def test_execute_and_check(toy_ir):
    v, info = execute_ir(toy_ir)
    assert v == D("0.2") and info["status"] == "OK"
    toy_ir["claimed_answer"]["predicted_value"] = 0.25
    assert execute_ir(toy_ir)[1]["status"] == "MISMATCH"


def test_errors():
    assert execute_ir({"variables": [], "equations": [{"lhs": "y", "rhs": "x + 1"}]})[1]["status"] == "ERROR"
    assert execute_ir({"variables": [{"name": "x", "value": 1}], "equations": [{"lhs": "y", "rhs": "x / 0"}],
                       "claimed_answer": {"target_variable": "y"}})[1]["status"] == "ERROR"
    assert execute_ir({"variables": [{"name": "x", "value": 1}], "equations": [{"lhs": "y", "rhs": "__import__('os')"}],
                       "claimed_answer": {"target_variable": "y"}})[1]["status"] == "ERROR"


def test_functions_and_compare():
    ir = {"variables": [{"name": "a", "value": 3}, {"name": "b", "value": 5}],
          "equations": [{"lhs": "m", "rhs": "avg(a, b)"}, {"lhs": "g", "rhs": "a > b"}],
          "claimed_answer": {"target_variable": "m", "predicted_value": 4}}
    v, info = execute_ir(ir)
    assert v == 4 and info["status"] == "OK"
