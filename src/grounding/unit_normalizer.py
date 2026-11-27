"""Unit vocabulary, scale factors and scale detection for financial evidence.

Units are split into a *dimension* (currency, percent, ratio, count, ...) and
a *scale* (1, 1e3, 1e6, 1e9). A conversion between two units is
deterministic only when the dimension is the same (or percent <-> ratio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

__all__ = [
    "Unit", "parse_unit", "convert", "UnitError",
    "detect_scale_near", "detect_scale_in_header", "SCALE_WORDS",
]


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class Unit:
    dimension: str      # currency | percent | ratio | count | shares | per_share | bp | year | unknown
    scale: Decimal      # multiplier to the base unit
    currency: Optional[str] = None
    name: str = ""

    def __str__(self) -> str:
        return self.name or f"{self.dimension}x{self.scale}"


SCALE_WORDS = {
    "": Decimal(1), "unit": Decimal(1), "units": Decimal(1),
    "thousand": Decimal(10) ** 3, "thousands": Decimal(10) ** 3, "k": Decimal(10) ** 3,
    "million": Decimal(10) ** 6, "millions": Decimal(10) ** 6, "mn": Decimal(10) ** 6, "m": Decimal(10) ** 6,
    "billion": Decimal(10) ** 9, "billions": Decimal(10) ** 9, "bn": Decimal(10) ** 9, "b": Decimal(10) ** 9,
}
_CURRENCIES = {"usd", "gbp", "eur", "jpy", "cad", "aud", "chf", "cny"}

_ALIASES = {
    "percent": ("percent", 1), "percentage": ("percent", 1), "pct": ("percent", 1), "%": ("percent", 1),
    "ratio": ("ratio", 1), "decimal_rate": ("ratio", 1), "fraction": ("ratio", 1), "times": ("ratio", 1),
    "multiple": ("ratio", 1), "x": ("ratio", 1),
    "bp": ("bp", 1), "bps": ("bp", 1), "basis_points": ("bp", 1),
    "count": ("count", 1), "number": ("count", 1), "years": ("year", 1), "year": ("year", 1),
    "shares": ("shares", 1), "share": ("shares", 1),
    "per_share_usd": ("per_share", 1), "usd_per_share": ("per_share", 1),
    "dimensionless": ("ratio", 1), "unknown": ("unknown", 1), "": ("unknown", 1),
}


def parse_unit(text: Optional[str]) -> Unit:
    """Parse unit strings like 'million_usd', 'USD', 'thousand_shares', 'percent'."""
    raw = (text or "").strip()
    key = raw.lower().replace(" ", "_").replace("-", "_")
    if "_per_" in key and ("share" in key or key.startswith(tuple(_CURRENCIES))):
        return Unit("per_share", Decimal(1), None, raw)   # e.g. usd_per_common_share
    if key in ("payments", "monthly_payments", "months", "periods", "quarters"):
        return Unit("count", Decimal(1), None, raw)
    if key in _ALIASES:
        dim, sc = _ALIASES[key]
        return Unit(dim, Decimal(sc), None, raw or "unknown")
    parts = [p for p in key.split("_") if p]
    scale = Decimal(1)
    cur = None
    dim = None
    rest = []
    for p in parts:
        if p in SCALE_WORDS and p not in ("m", "b", "k") and p != "":
            scale *= SCALE_WORDS[p]
        elif p in ("k", "m", "mn", "bn", "b") and len(parts) > 1:
            scale *= SCALE_WORDS[p]
        elif p in _CURRENCIES or p in ("dollars", "dollar"):
            cur = "usd" if p.startswith("dollar") else p
            dim = "currency"
        elif p in ("shares", "share"):
            dim = "shares"
        elif p in ("count", "units", "employees"):
            dim = "count"
        else:
            rest.append(p)
    if dim is None:
        if rest:
            raise UnitError(f"unknown unit: {raw!r}")
        dim = "count"
    return Unit(dim, scale, cur, raw)


def convert(value: Decimal, src: Unit, dst: Unit) -> Decimal:
    """Convert value from src to dst unit. Raises UnitError if not deterministic."""
    if src.dimension == "unknown" or dst.dimension == "unknown":
        raise UnitError("unknown unit")
    if src.dimension == dst.dimension:
        if src.dimension == "currency" and src.currency and dst.currency and src.currency != dst.currency:
            raise UnitError(f"currency conversion {src.currency}->{dst.currency} needs an FX rate")
        return value * src.scale / dst.scale
    pair = (src.dimension, dst.dimension)
    if pair == ("percent", "ratio"):
        return value / Decimal(100)
    if pair == ("ratio", "percent"):
        return value * Decimal(100)
    if pair == ("bp", "percent"):
        return value / Decimal(100)
    if pair == ("percent", "bp"):
        return value * Decimal(100)
    if pair == ("bp", "ratio"):
        return value / Decimal(10000)
    if pair == ("ratio", "bp"):
        return value * Decimal(10000)
    raise UnitError(f"cannot convert {src} to {dst}")


_SCALE_AFTER = re.compile(r"^\s*(thousand|thousands|million|millions|billion|billions|bn|mn)\b", re.I)
_HEADER = re.compile(
    r"(?:in|\$\s*in|amounts\s+in|dollars\s+in|dollar\s+amounts\s+in)\s+(thousands|millions|billions)", re.I
)


def detect_scale_near(text: str, end: int) -> Optional[Decimal]:
    """Scale word directly after a number, e.g. '$ 7.0 billion'."""
    m = _SCALE_AFTER.match(text[end:end + 15])
    if not m:
        return None
    return SCALE_WORDS[m.group(1).lower()]


def detect_scale_in_header(*texts: str) -> Optional[Decimal]:
    """Scale stated as '( in millions )' etc. Returns None if absent or conflicting."""
    found = set()
    for t in texts:
        for m in _HEADER.finditer(t or ""):
            found.add(SCALE_WORDS[m.group(1).lower()])
    if len(found) == 1:
        return found.pop()
    return None
