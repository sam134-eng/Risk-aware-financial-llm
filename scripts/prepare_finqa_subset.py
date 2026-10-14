"""
Prepare a reproducible subset of the public FinQA test split.

Source:
    Chen et al. (2021), FinQA: A Dataset of Numerical
    Reasoning over Financial Data.
    https://doi.org/10.18653/v1/2021.emnlp-main.300

Procedure:
    1. Load the source JSON.
    2. Retain records with the required QA and evidence fields.
    3. Shuffle eligible records using seed 2026.
    4. Select up to 134 records.
    5. Preserve source IDs, reference annotations, and context.
    6. Add project-specific IDs and provisional metadata.
    7. Write the selected records to data/finqa_subset.json.

Limitations:
    This script does not verify gold programs, evidence sufficiency,
    duplicate cases, or risk-severity annotations.

Reproducibility:
    Record the source dataset version or commit, Python version,
    random seed, and actual counts in the experiment log.
"""
import json
import random
from pathlib import Path

# Project root directory
ROOT = Path(__file__).resolve().parents[1]

# Specify input and output paths
SOURCE = ROOT / "external" / "FinQA" / "dataset" / "test.json"
OUTPUT = ROOT / "data" / "finqa_subset.json"

# Configuration sampling
TARGET_SIZE = 134
SEED = 2025
START_CASE_NUMBER = 17

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Dataset not found : {SOURCE}\n"
            "Check whether FinQA is cloned in external/FinQA."
        )
    
    # Load FinQA test dataset
    with SOURCE.open("r", encoding="utf-8") as f:
        records = json.load(f)
        
    candidates = []

    # We will keep those records that has question, answer, program and supporting evidence
    for record in records:
        qa = record.get("qa", {})
        question = qa.get("question") 
        answer = qa.get("answer")
        program = qa.get("program")
        evidence = qa.get("gold_inds", {})
        
        if not all([question, answer, program, evidence]):
            continue

        if not isinstance(evidence, dict) or not evidence:
            continue

        case = {
            "case_id": None,
            "source_dataset": "FinQA",
            "source_split": "test",
            "source_id": record.get("id"),
            "category": "Financial Numerical Reasoning",
            "question": question,
            "gold_answer": answer,
            "gold_reasoning": program,
            "gold_supporting_evidence": evidence,
            "evidence_context": {
                "pre_text": record.get("pre_text", []),
                "table": record.get("table", []),
                "post_text": record.get("post_text", [])
            },
            "gold_numeric": qa.get("exe_ans"),
            "risk_type": "numerical_reasoning",
            "severity": "unannotated",
            "annotation_status": {
                "risk_type": "provisional",
                "severity": "not_yet_annotated"
            }
        }

        candidates.append(case)

    # Reproducible random sampling
    rng = random.Random(SEED)
    rng.shuffle(candidates)

    selected = candidates[:TARGET_SIZE]

    # Assign IDs starting from F_017
    for i, case in enumerate(
        selected,
        start=START_CASE_NUMBER
    ):
        case["case_id"] = f"F_{i:03d}"

    # Create the output directory if necessary
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Save the selected records as readable JSON
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(
            selected,
            f,
            indent=2,
            ensure_ascii=False
        )

    # Print a summary
    print(f"Source records: {len(records)}")
    print(f"Usable candidates: {len(candidates)}")
    print(f"Selected cases: {len(selected)}")
    print(f"First case ID: {selected[0]['case_id'] if selected else 'N/A'}")
    print(f"Last case ID: {selected[-1]['case_id'] if selected else 'N/A'}")
    print(f"Random seed: {SEED}")
    print(f"Output file: {OUTPUT}")

    if len(selected) < TARGET_SIZE:
        print(
            "WARNING: Fewer than 134 eligible records found."
        )

if __name__ == "__main__":
    main()