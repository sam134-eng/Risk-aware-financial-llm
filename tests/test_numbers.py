from decimal import Decimal as D
from src.grounding.numbers import find_numbers, parse_number, is_label_cell


def vals(t):
    return [(n.value, n.is_percent) for n in find_numbers(t)]


def test_commas_currency_decimals():
    assert vals("$ 1,234.50 and £30,341.50") == [(D("1234.50"), False), (D("30341.50"), False)]


def test_percent():
    assert vals("28.9%") == [(D("28.9"), True)]


def test_finqa_duplicate_negative_is_one_number():
    assert vals("$ -1.7 ( 1.7 )") == [(D("-1.7"), False)]


def test_finqa_duplicate_percent_is_one_number():
    assert vals("4.1% ( 4.1 % )") == [(D("4.1"), True)]


def test_accounting_parentheses_negative():
    assert vals("( 8.0 )") == [(D("-8.0"), False)]
    assert vals("(1,234)") == [(D("-1234"), False)]


def test_range_hyphen_is_not_negative():
    assert vals("2014 - 2016") == [(D("2014"), False), (D("2016"), False)]


def test_identifier_digits_ignored():
    assert vals("page_77") == []


def test_parse_number_none():
    assert parse_number("n/a") is None


def test_label_cells():
    assert is_label_cell("revenue") and is_label_cell("2013") and is_label_cell("")
    assert not is_label_cell("$ 23596")
