
"""
Run equation-based Z3 verification over the existing
500-case financial benchmark and cached LLM responses.

No OpenAI API calls are made by this script.
"""

import json
import re

from pathlib import Path
from decimal import Decimal, InvalidOperation

from z3_verifier import verify_calculation


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "combined_benchmark_500.json"
)

CACHE_FILE = PROJECT_DIR / "results" / "baseline_cache.json"

OUTPUT_FILE = PROJECT_DIR / "results" / "verification_results.json"

# None = process every benchmark case with a cached response.
MAX_CASES = None


# --------------------------------------------------
# JSON UTILITIES
# --------------------------------------------------

def load_json(path):

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


# --------------------------------------------------
# CACHE NORMALISATION
# --------------------------------------------------

def normalise_cache(cache):
    """
    Supports either a list or dictionary cache.

    Entries are indexed by case_id.
    Duplicate case IDs are counted and the last entry is retained.
    """

    entries = cache.values() if isinstance(cache, dict) else cache

    normalised = {}
    duplicate_count = 0

    for entry in entries:

        if not isinstance(entry, dict):
            continue

        case_id = entry.get("case_id")

        if not case_id:
            continue

        if case_id in normalised:
            duplicate_count += 1

        normalised[case_id] = entry

    return normalised, duplicate_count


# --------------------------------------------------
# NUMBER FORMATS
# --------------------------------------------------

NUMBER = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

# Simple equations:
# 28524 + 4934 = 33458
# 100 / 5 = 20
SIMPLE_EQUATION = re.compile(
    rf"({NUMBER})\s*([+\-*/])\s*({NUMBER})\s*=\s*({NUMBER})"
)

# Percentage change:
# ((26.2 - 28.8) / 28.8) * 100 = -9.03
PERCENTAGE_CHANGE = re.compile(
    rf"\(?\s*\(?\s*({NUMBER})\s*-\s*({NUMBER})\s*\)?"
    rf"\s*/\s*({NUMBER})\s*\)?\s*\*?\s*100"
    rf"\s*=\s*({NUMBER})"
)

# Percentage of:
# 5% of 200 = 10
PERCENTAGE_OF = re.compile(
    rf"({NUMBER})\s*%\s*of\s*({NUMBER})\s*=\s*({NUMBER})",
    re.IGNORECASE,
)


def clean_number(value):
    return value.replace(",", "").strip()


# --------------------------------------------------
# EXTRACT EXPLICIT CALCULATIONS
# --------------------------------------------------

def extract_calculation(model_answer):
    """
    Extract a supported, explicitly written equation.

    This function does not infer calculations from ordinary prose.
    """

    if not isinstance(model_answer, str) or not model_answer.strip():
        return None

    # 1. Percentage change.
    match = PERCENTAGE_CHANGE.search(model_answer)

    if match:

        a, b, denominator, claimed = match.groups()

        if Decimal(clean_number(denominator)) == Decimal(clean_number(b)):

            return {
                "operation": "percentage_change",
                "inputs": [
                    clean_number(a),
                    clean_number(b),
                ],
                "claimed_result": clean_number(claimed),
                "equation": match.group(0),
            }

    # 2. Percentage of.
    match = PERCENTAGE_OF.search(model_answer)

    if match:

        percentage, amount, claimed = match.groups()

        return {
            "operation": "percentage_of",
            "inputs": [
                clean_number(percentage),
                clean_number(amount),
            ],
            "claimed_result": clean_number(claimed),
            "equation": match.group(0),
        }

    # 3. Simple arithmetic.
    matches = list(SIMPLE_EQUATION.finditer(model_answer))

    if not matches:
        return None

    # Use the last explicit simple equation.
    match = matches[-1]

    a, operator, b, claimed = match.groups()

    operation_map = {
        "+": "add",
        "-": "subtract",
        "*": "multiply",
        "/": "divide",
    }

    operation = operation_map[operator]

    if operation == "divide" and Decimal(clean_number(b)) == 0:
        return None

    return {
        "operation": operation,
        "inputs": [
            clean_number(a),
            clean_number(b),
        ],
        "claimed_result": clean_number(claimed),
        "equation": match.group(0),
    }


# --------------------------------------------------
# DISPLAY-PRECISION TOLERANCE
# --------------------------------------------------

def get_tolerance(claimed_result):
    """
    Half a unit in the last displayed decimal place.

    Examples:
        10       -> 0.5
        10.2     -> 0.05
        10.25    -> 0.005
        0.5765604 -> 0.00000005
    """

    value = Decimal(str(claimed_result))

    decimal_places = max(0, -value.as_tuple().exponent)

    tolerance = (
        Decimal("0.5")
        * (Decimal("10") ** (-decimal_places))
    )

    return str(tolerance)


# --------------------------------------------------
# BENCHMARK VERIFICATION
# --------------------------------------------------

def main():

    print("\nLoading benchmark and baseline cache...")

    benchmark = load_json(DATA_FILE)
    cache_data = load_json(CACHE_FILE)

    if not isinstance(benchmark, list):
        raise ValueError("Benchmark JSON must contain a list of cases.")

    cache, duplicate_count = normalise_cache(cache_data)

    benchmark_cases = {
        case["case_id"]: case
        for case in benchmark
        if case.get("case_id")
    }

    # Only process benchmark case IDs.
    matched_ids = [
        case_id
        for case_id in benchmark_cases
        if case_id in cache
    ]

    if MAX_CASES is not None:
        matched_ids = matched_ids[:MAX_CASES]

    results = {}

    counts = {
        "PASS": 0,
        "FAIL": 0,
        "UNKNOWN": 0,
        "NOT_APPLICABLE": 0,
    }

    print("\n" + "=" * 65)
    print("STARTING EQUATION-BASED Z3 VERIFICATION")
    print("=" * 65)

    print(f"Benchmark cases       : {len(benchmark_cases)}")
    print(f"Unique cached cases   : {len(cache)}")
    print(f"Duplicate cache IDs   : {duplicate_count}")
    print(f"Matched cases         : {len(matched_ids)}")

    for index, case_id in enumerate(matched_ids, start=1):

        entry = cache[case_id]
        case_data = benchmark_cases[case_id]

        model_answer = entry.get("model_answer", "")

        extracted = extract_calculation(model_answer)

        if extracted is None:

            verification = {
                "status": "NOT_APPLICABLE",
                "reason": (
                    "No supported explicit numerical equation "
                    "could be extracted from the model answer."
                ),
            }

            counts["NOT_APPLICABLE"] += 1

        else:

            tolerance = get_tolerance(
                extracted["claimed_result"]
            )

            try:

                verification = verify_calculation(
                    operation=extracted["operation"],
                    inputs=extracted["inputs"],
                    claimed_result=extracted["claimed_result"],
                    tolerance=tolerance,
                )

            except Exception as error:

                verification = {
                    "status": "UNKNOWN",
                    "reason": f"Verifier execution error: {error}",
                }

            status = verification.get("status", "UNKNOWN")

            if status not in counts:
                status = "UNKNOWN"
                verification["status"] = status

            counts[status] += 1

        results[case_id] = {
            "case_id": case_id,
            "source_dataset": case_data.get("source_dataset"),
            "source_split": case_data.get("source_split"),
            "question": case_data.get("question"),
            "gold_answer": case_data.get("gold_answer"),
            "gold_numeric": case_data.get("gold_numeric"),
            "model_answer": model_answer,
            "extraction": extracted,
            "tolerance": (
                get_tolerance(extracted["claimed_result"])
                if extracted is not None
                else None
            ),
            "verification": verification,
        }

        print(
            f"[{index}/{len(matched_ids)}] "
            f"{case_id}: "
            f"{verification['status']}"
        )

    # Benchmark cases without a cached answer.
    missing_ids = [
        case_id
        for case_id in benchmark_cases
        if case_id not in cache
    ]

    output = {
        "method": "Equation-based Z3 numerical verification",
        "benchmark_total": len(benchmark_cases),
        "unique_cached_cases": len(cache),
        "duplicate_cache_ids": duplicate_count,
        "matched_cases": len(matched_ids),
        "missing_baseline_cases": missing_ids,
        "summary": counts,
        "results": results,
    }

    save_json(OUTPUT_FILE, output)

    print("\n" + "=" * 65)
    print("Z3 VERIFICATION SUMMARY")
    print("=" * 65)

    print(f"Benchmark total       : {len(benchmark_cases)}")
    print(f"Unique cached cases   : {len(cache)}")
    print(f"Matched cases         : {len(matched_ids)}")
    print(f"PASS                  : {counts['PASS']}")
    print(f"FAIL                  : {counts['FAIL']}")
    print(f"UNKNOWN               : {counts['UNKNOWN']}")
    print(f"NOT_APPLICABLE        : {counts['NOT_APPLICABLE']}")
    print(f"Missing baseline      : {len(missing_ids)}")

    print("\nDetailed results saved to:")
    print(OUTPUT_FILE)

    print("\nNo OpenAI API calls were made.")


if __name__ == "__main__":
    main()
