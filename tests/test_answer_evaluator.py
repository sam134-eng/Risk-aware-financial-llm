from decimal import Decimal as D
from src.evaluation.answer_evaluator import evaluate, extract_final_answer, parse_gold
from src.evaluation.gold_audit import gold_consistency, program_value


def test_extract_bold_percent():
    a = extract_final_answer("calc...\n\nThus it is **57.66%**.")
    assert a.value == D("57.66") and a.is_percent and a.method == "bold"


def test_extract_skips_bold_years_and_ratio():
    a = extract_final_answer("- **2013**: x\n\nThe ratio is **1:1**.")
    assert a.value == 1
    assert extract_final_answer("**2012**: $5\n\nNo calculations are needed.").value != D(2012)


def test_refusal():
    a = extract_final_answer("The evidence is insufficient to calculate the value.")
    assert a.refused


def test_outcomes():
    assert evaluate("**57.66%**", "57.65%").outcome == "ROUNDING_ONLY"
    assert evaluate("**57.66%**", "57.7%").outcome == "CORRECT"
    assert evaluate("**0.5766**", "57.7%").outcome == "CORRECT"           # fraction for percent
    assert evaluate("**22%**", "-22%").outcome == "SIGN_MISMATCH"
    assert evaluate("a decrease of **$17 million**", "-17").outcome == "SIGN_CONVENTION"
    assert evaluate("**7.0**", "7000").outcome == "SCALE_MISMATCH"
    assert evaluate("**12**", "15").outcome == "INCORRECT"
    assert evaluate("I cannot determine this; insufficient information.", "15").outcome == "REFUSED"
    assert evaluate("**0.39**", ".385").outcome == "ROUNDING_ONLY"        # model rounded coarser
    assert evaluate("x", "Average = $40,000. Turnover = 9 times.").outcome == "NOT_EVALUATED"


def test_yes_no():
    assert evaluate("**Yes, it was greater.**", "yes").outcome == "CORRECT"
    assert evaluate("Thus the B series did **not** outperform the A series.", "no").outcome == "CORRECT"
    assert evaluate("No further calculation needed.\n\nIt was greater than the other.", "yes").outcome == "CORRECT"


def test_parse_gold():
    g = parse_gold("$ 9015431")
    assert g.kind == "number" and g.value == 9015431
    assert parse_gold("1.371:1").value == D("1.371")
    assert parse_gold("yes").kind == "yes_no"


def test_gold_audit_real(bench):
    c = bench["F_151"]
    assert program_value(c["gold_reasoning"]) == 38290
    assert gold_consistency(c["gold_answer"], c["gold_reasoning"]) == "INCONSISTENT"
    c = bench["F_026"]                       # 997 / 7000 = 14.24% -> "14.2%"
    assert gold_consistency(c["gold_answer"], c["gold_reasoning"]) == "CONSISTENT"
    c = bench["F_017"]                       # 57.656% stored as "57.65%" (truncated, not rounded)
    assert gold_consistency(c["gold_answer"], c["gold_reasoning"]) == "ROUNDING_DIFFERENCE"
