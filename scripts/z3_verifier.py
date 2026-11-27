
"""
Z3-based numerical verifier for financial calculations.

Supported operations:
    add
    subtract
    multiply
    divide
    percentage_change
    percentage_of
    ratio

The verifier checks whether a claimed numerical result is
consistent with a mathematical operation, within a specified
absolute numerical tolerance.
"""

from decimal import Decimal, InvalidOperation
from z3 import Real, RealVal, Solver, Abs, sat, unsat


# --------------------------------------------------
# NUMERICAL CONVERSION
# --------------------------------------------------

def to_decimal(value):
    """Convert a value into a finite Decimal."""

    try:
        number = Decimal(str(value).replace(",", "").strip())

        if not number.is_finite():
            raise ValueError("Input must be a finite number.")

        return number

    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid numerical input: {value}")


def to_z3_real(value):
    """Convert a Decimal into an exact Z3 rational."""

    number = to_decimal(value)
    numerator, denominator = number.as_integer_ratio()

    return RealVal(numerator) / RealVal(denominator)


# --------------------------------------------------
# EXPECTED VALUE CALCULATION
# --------------------------------------------------

def calculate_expected(operation, a, b):
    """Calculate the expected result using Decimal arithmetic."""

    if operation == "add":
        return a + b

    if operation == "subtract":
        return a - b

    if operation == "multiply":
        return a * b

    if operation in {"divide", "ratio"}:
        return a / b

    if operation == "percentage_change":
        return ((a - b) / b) * Decimal("100")

    if operation == "percentage_of":
        return (a / Decimal("100")) * b

    raise ValueError(f"Unsupported operation: {operation}")


# --------------------------------------------------
# Z3 VERIFICATION
# --------------------------------------------------

def verify_calculation(
    operation,
    inputs,
    claimed_result,
    tolerance="0"
):
    """
    Verify a numerical calculation using Z3.

    Parameters:
        operation:
            Mathematical operation to verify.

        inputs:
            Exactly two numerical inputs.

        claimed_result:
            Numerical result claimed by the model.

        tolerance:
            Maximum accepted absolute difference between
            the calculated and claimed results.

    Status:
        PASS:
            Difference is within tolerance.

        FAIL:
            Difference exceeds tolerance.

        UNKNOWN:
            Z3 cannot determine the result.

        NOT_APPLICABLE:
            Unsupported operation or invalid input.
    """

    supported_operations = {
        "add",
        "subtract",
        "multiply",
        "divide",
        "percentage_change",
        "percentage_of",
        "ratio",
    }

    if operation not in supported_operations:
        return {
            "status": "NOT_APPLICABLE",
            "reason": f"Unsupported operation: {operation}",
        }

    try:
        if not isinstance(inputs, (list, tuple)) or len(inputs) != 2:
            raise ValueError("Exactly two numerical inputs are required.")

        a, b = [to_decimal(value) for value in inputs]
        claimed = to_decimal(claimed_result)
        allowed_error = to_decimal(tolerance)

        if allowed_error < 0:
            raise ValueError("Tolerance cannot be negative.")

        if operation in {"divide", "ratio", "percentage_change"} and b == 0:
            raise ValueError("Division by zero is not allowed.")

        # Create symbolic variables.
        x = Real("x")
        y = Real("y")

        solver = Solver()

        # Fix the variables to the supplied numerical inputs.
        solver.add(x == to_z3_real(a))
        solver.add(y == to_z3_real(b))

        # Encode the mathematical operation.
        if operation == "add":
            expression = x + y

        elif operation == "subtract":
            expression = x - y

        elif operation == "multiply":
            expression = x * y

        elif operation in {"divide", "ratio"}:
            expression = x / y

        elif operation == "percentage_change":
            expression = ((x - y) / y) * 100

        elif operation == "percentage_of":
            expression = (x / 100) * y

        # Ask whether the absolute error exceeds tolerance.
        solver.add(
            Abs(expression - to_z3_real(claimed))
            > to_z3_real(allowed_error)
        )

        result = solver.check()

        expected = calculate_expected(operation, a, b)

        if result == unsat:
            return {
                "status": "PASS",
                "operation": operation,
                "inputs": [str(a), str(b)],
                "claimed_result": str(claimed),
                "expected_result": str(expected),
                "absolute_error": str(abs(expected - claimed)),
                "tolerance": str(allowed_error),
                "reason": (
                    "The claimed result is consistent with the "
                    "specified calculation within tolerance."
                ),
            }

        if result == sat:
            return {
                "status": "FAIL",
                "operation": operation,
                "inputs": [str(a), str(b)],
                "claimed_result": str(claimed),
                "expected_result": str(expected),
                "absolute_error": str(abs(expected - claimed)),
                "tolerance": str(allowed_error),
                "reason": (
                    "The claimed result differs from the "
                    "specified calculation beyond tolerance."
                ),
            }

        return {
            "status": "UNKNOWN",
            "operation": operation,
            "reason": "Z3 could not determine the result.",
        }

    except (ValueError, InvalidOperation, ZeroDivisionError) as error:
        return {
            "status": "NOT_APPLICABLE",
            "reason": str(error),
        }


# --------------------------------------------------
# CONTROLLED TESTS
# --------------------------------------------------

def run_tests():

    test_cases = [
        {
            "name": "Correct addition",
            "operation": "add",
            "inputs": [28524, 4934],
            "claimed": 33458,
            "tolerance": "0",
            "expected": "PASS",
        },
        {
            "name": "Incorrect addition",
            "operation": "add",
            "inputs": [28524, 4934],
            "claimed": 63458,
            "tolerance": "0",
            "expected": "FAIL",
        },
        {
            "name": "Rounded percentage change",
            "operation": "percentage_change",
            "inputs": [26.2, 28.8],
            "claimed": -9.02777777777778,
            "tolerance": "0.000000000000005",
            "expected": "PASS",
        },
        {
            "name": "Rounded ratio",
            "operation": "ratio",
            "inputs": [6725, 11664],
            "claimed": 0.5765604,
            "tolerance": "0.00000005",
            "expected": "PASS",
        },
    ]

    print("\nZ3 FINANCIAL VERIFICATION TESTS")
    print("=" * 60)

    all_passed = True

    for test in test_cases:

        result = verify_calculation(
            operation=test["operation"],
            inputs=test["inputs"],
            claimed_result=test["claimed"],
            tolerance=test["tolerance"],
        )

        test_passed = result["status"] == test["expected"]

        if not test_passed:
            all_passed = False

        print(f"\nTest: {test['name']}")
        print(f"Expected status : {test['expected']}")
        print(f"Actual status   : {result['status']}")
        print(f"Test outcome    : {'OK' if test_passed else 'CHECK'}")
        print(f"Expected value  : {result.get('expected_result')}")
        print(f"Absolute error  : {result.get('absolute_error')}")
        print(f"Reason          : {result.get('reason')}")

    print("\n" + "=" * 60)
    print(
        "OVERALL TEST RESULT:",
        "ALL TESTS PASSED" if all_passed else "SOME TESTS NEED REVIEW"
    )


if __name__ == "__main__":
    run_tests()
