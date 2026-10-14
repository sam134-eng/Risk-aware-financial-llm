
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "finqa_subset.json"


def main():
    with INPUT.open("r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Total number of  cases: {len(cases)}")

    # Check required fields
    required_fields = [
        "case_id",
        "question",
        "gold_answer",
        "gold_reasoning",
        "gold_supporting_evidence",
        "evidence_context",
    ]

    missing_fields = []
    for case in cases:
        for field in required_fields:
            if field not in case or case[field] in (None, "", {}):
                missing_fields.append((case.get("case_id"), field))

    print(f"Missing required fields: {len(missing_fields)}")
    for case_id, field in missing_fields[:20]:
        print(f"  {case_id}: missing {field}")

    # Check duplicate questions
    question_counts = Counter(
        case["question"].strip().lower()
        for case in cases
        if isinstance(case.get("question"), str)
    )

    duplicate_questions = {
        question: count
        for question, count in question_counts.items()
        if count > 1
    }

    print(f"Unique questions: {len(question_counts)}")
    print(f"Duplicate question groups: {len(duplicate_questions)}")

    for question, count in list(duplicate_questions.items())[:10]:
        print(f"  ({count} times) {question}")

    # Check duplicate source IDs
    source_ids = [
        case.get("source_id")
        for case in cases
        if case.get("source_id") is not None
    ]
    duplicate_source_ids = [
        source_id
        for source_id, count in Counter(source_ids).items()
        if count > 1
    ]

    print(f"Duplicate source IDs: {len(duplicate_source_ids)}")

    # Check case IDs
    case_ids = [case.get("case_id") for case in cases]
    print(f"Unique case IDs: {len(set(case_ids))}")
    print(f"First case ID: {case_ids[0] if case_ids else 'N/A'}")
    print(f"Last case ID: {case_ids[-1] if case_ids else 'N/A'}")

    # Summarise the risk labels
    risk_counts = Counter(case.get("risk_type") for case in cases)
    print(f"Risk type counts: {dict(risk_counts)}")

    print("\nValidation script finished.")
    print("Review warnings before using this dataset for evaluation.")


if __name__ == "__main__":
    main()
