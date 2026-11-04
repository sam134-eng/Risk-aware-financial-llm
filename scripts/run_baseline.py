
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


# project folder and the file configuration
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "processed" / "combined_benchmark_500.json"
RESULTS_DIR = PROJECT_DIR / "results"
CACHE_FILE = RESULTS_DIR / "baseline_cache.json"

# Load the API key from the project's .env file.
load_dotenv(PROJECT_DIR / ".env")

MODEL = os.getenv("BASELINE_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "baseline_v2"

# We will start with a small pilot before running all 500 cases.
PILOT_SIZE = 500


def load_json(path):
    """Load data from a JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    """Save results safely so completed answers are not lost."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = path.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    temporary_file.replace(path)


def build_prompt(case):
    """Prepare the question and available evidence for the model."""
    question = case["question"]

    # FinQA cases may contain tables and supporting text.
    # Manual cases may use a different evidence field.
    evidence = case.get("evidence_context")

    if evidence is None:
        evidence = case.get("evidence", {})

    if not evidence:
        evidence = case.get("gold_supporting_evidence", {})

    prompt = (
        "You are answering a financial reasoning question.\n"
        "Use the supplied financial evidence to answer the question.\n"
        "Show the key calculation when relevant.\n"
        "Do not invent figures or make unsupported assumptions.\n"
        "If the evidence is not sufficient,mention that clearly in your response.\n\n"
        f"Question:\n{question}\n\n"
        "Financial evidence:\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n"
        "Give a clear, concise answer and include the calculation "
        "when relevant."
    )

    return prompt


def get_answer(client, prompt):
    """Ask the model for an answer, retrying temporary API errors."""
    for attempt in range(5):
        try:
            response = client.responses.create(
                model=MODEL,
                input=prompt,
            )

            return response.output_text

        except (
            RateLimitError,
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
        ):
            if attempt == 4:
                raise

            wait_seconds = min(2 ** attempt, 30)
            print(f"Temporary API error. Retrying in {wait_seconds} seconds...")
            time.sleep(wait_seconds)


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {DATA_FILE}"
        )

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY was not found. Check your project's .env file."
        )

    cases = load_json(DATA_FILE)

    # Load earlier results so completed cases do not need to be repeated.
    if CACHE_FILE.exists():
        cache = load_json(CACHE_FILE)
    else:
        cache = {}

    client = OpenAI()

    # Process only the first ten cases during the initial pilot.
    pilot_cases = cases[:PILOT_SIZE]

    print(f"Model: {MODEL}")
    print(f"Cases in this pilot: {len(pilot_cases)}")
    print("-" * 50)

    for case in pilot_cases:
        case_id = case["case_id"]
        prompt = build_prompt(case)

        # The key changes if the question, evidence, model, or prompt changes.
        cache_input = {
            "case_id": case_id,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "prompt": prompt,
        }

        cache_key = hashlib.sha256(
            json.dumps(
                cache_input,
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        if cache_key in cache:
            print(f"{case_id}: using cached answer")
            continue

        print(f"{case_id}: generating answer...")

        try:
            answer = get_answer(client, prompt)

            cache[cache_key] = {
                "case_id": case_id,
                "model": MODEL,
                "prompt_version": PROMPT_VERSION,
                "question": case["question"],
                "gold_answer": case.get("gold_answer"),
                "gold_numeric": case.get("gold_numeric"),
                "model_answer": answer,
            }

            # Save after each answer in case a later request fails.
            save_json(CACHE_FILE, cache)

            print(f"{case_id}: answer saved")

        except Exception as error:
            # Preserve every result generated before this error.
            save_json(CACHE_FILE, cache)

            print(
                f"Stopped at {case_id}: "
                f"{type(error).__name__}: {error}"
            )
            print("Previously saved answers have been preserved.")
            break

    print("-" * 50)
    print(f"Results saved to: {CACHE_FILE}")


if __name__ == "__main__":
    main()
