import json
from pathlib import Path

# Locate the project directory automatically
project_folder = Path(__file__).resolve().parent.parent

# Input dataset
manual_file = project_folder / "data" / "pilot_cases.json"
finqa_file = project_folder / "data" / "finqa_subset.json"

# Output file name
output_file = project_folder / "data" / "processed" / "combined_benchmark_v1.json"


def load_cases(file_path):
    """Read the financial cases from a JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Can not find the input file: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as file:
        cases = json.load(file)
        
    if not isinstance(cases, list):
        raise ValueError(f"{file_path.name} should contain a json list")
        
    return cases


def main():
    # Loading datasets
    manual_cases = load_cases(manual_file)
    finqa_cases = load_cases(finqa_file)

    print(f"Manual cases loaded: {len(manual_cases)}")
    print(f"FinQA cases loaded: {len(finqa_cases)}")

    # Combine the record without modifying the source file
    combined_cases = finqa_cases + manual_cases

    # Check that every case has unique case id
    case_ids = []
    for case in combined_cases:
        case_id = case.get("case_id")

        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("Every record must have a non-empty string case_id.")

        case_ids.append(case_id)

    if len(case_ids) != len(set(case_ids)):
        raise ValueError(
            "Duplicate case IDs detected. Please resolve them before merging."
        )

    # Check essential fields.
    for case in combined_cases:
        case_id = case["case_id"]

        if not isinstance(case.get("question"), str):
            raise ValueError(f"Question is missing or invalid for {case_id}.")

        if not case["question"].strip():
            raise ValueError(f"Question is empty for {case_id}.")

        if case.get("gold_answer") is None:
            raise ValueError(f"Gold answer is missing for {case_id}.")

    # Create the output directory if necessary.
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write the merged benchmark to a new JSON file.
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(
            combined_cases,
            file,
            indent=2,
            ensure_ascii=False
        )
        file.write("\n")

    print("\nBenchmark created successfully.")
    print(f"Manual cases: {len(manual_cases)}")
    print(f"FinQA cases: {len(finqa_cases)}")
    print(f"Total cases: {len(combined_cases)}")
    print(f"Output file: {output_file}")


if __name__ == "__main__":
    main()



