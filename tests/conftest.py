import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def bench():
    p = ROOT / "data" / "combined_benchmark_500.json"
    return {c["case_id"]: c for c in json.loads(p.read_text())}


@pytest.fixture
def toy_case():
    """Small FinQA-style case (values in millions)."""
    return {
        "case_id": "toy_001",
        "question": "what was the growth rate in revenue from 2021 to 2022?",
        "evidence_context": {
            "pre_text": ["revenue by year is shown below ( in millions ) :"],
            "table": [["", "2021", "2022"],
                      ["revenue", "$ 500", "$ 600"],
                      ["net loss", "$ -12.5 ( 12.5 )", "( 8.0 )"],
                      ["margin", "4.1% ( 4.1 % )", "5.0% ( 5.0 % )"]],
            "post_text": ["cash and equivalents were $ 7.0 billion at year end ."],
        },
    }


@pytest.fixture
def toy_ir():
    return {
        "question_id": "toy_001",
        "variables": [
            {"name": "rev_2021", "value": 500.0, "unit": "million_usd", "source_grounding": "table_row_1_col_1"},
            {"name": "rev_2022", "value": 600.0, "unit": "million_usd", "source_grounding": "table_row_1_col_2"},
        ],
        "equations": [{"id": "eq_1", "lhs": "growth_rate", "rhs": "(rev_2022 - rev_2021) / rev_2021"}],
        "claimed_answer": {"target_variable": "growth_rate", "predicted_value": 0.2, "tolerance": 0.001},
    }
