from decimal import Decimal as D
import pytest
from src.grounding.unit_normalizer import (parse_unit, convert, UnitError,
                                           detect_scale_in_header, detect_scale_near)


def test_parse_units():
    u = parse_unit("million_usd")
    assert (u.dimension, u.scale, u.currency) == ("currency", D(10) ** 6, "usd")
    assert parse_unit("USD").scale == 1
    assert parse_unit("thousand_shares").dimension == "shares"
    assert parse_unit("percent").dimension == "percent"
    assert parse_unit("ratio").dimension == "ratio"
    assert parse_unit("").dimension == "unknown"


def test_unknown_unit_raises():
    with pytest.raises(UnitError):
        parse_unit("furlongs")


def test_scale_conversion():
    assert convert(D("7.0"), parse_unit("billion_usd"), parse_unit("million_usd")) == D("7000")
    assert convert(D("500"), parse_unit("million_usd"), parse_unit("usd")) == D("500000000")


def test_percent_ratio_bp():
    assert convert(D("25"), parse_unit("percent"), parse_unit("ratio")) == D("0.25")
    assert convert(D("0.25"), parse_unit("ratio"), parse_unit("percent")) == D("25")
    assert convert(D("25"), parse_unit("bp"), parse_unit("percent")) == D("0.25")


def test_incompatible_dimensions():
    with pytest.raises(UnitError):
        convert(D(1), parse_unit("usd"), parse_unit("percent"))
    with pytest.raises(UnitError):
        convert(D(1), parse_unit("usd"), parse_unit("eur"))


def test_scale_detection():
    assert detect_scale_in_header("( in millions )") == D(10) ** 6
    assert detect_scale_in_header("in thousands", "in millions") is None  # conflicting
    t = "cash of $ 7.0 billion"
    assert detect_scale_near(t, t.index("7.0") + 3) == D(10) ** 9
