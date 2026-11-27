"""Agreement and reliability statistics for judge validation (pure Python, no dependencies).

* cohen_kappa / gwet_ac1  – chance-corrected agreement between two label sequences
  (AC1 is robust when one label dominates, e.g. most answers correct)
* confusion / fp_fn       – judge vs deterministic or human reference
* bootstrap_ci            – percentile CI over cases (fixed seed)
* repeat_consistency      – share of cases with identical labels across repeated runs
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Tuple

__all__ = ["percent_agreement", "cohen_kappa", "gwet_ac1", "confusion", "fp_fn", "bootstrap_ci",
           "repeat_consistency"]


def _pairs(a: Sequence, b: Sequence) -> List[Tuple]:
    if len(a) != len(b):
        raise ValueError("sequences differ in length")
    return [(x, y) for x, y in zip(a, b) if x is not None and y is not None]


def percent_agreement(a, b) -> Optional[float]:
    p = _pairs(a, b)
    return sum(x == y for x, y in p) / len(p) if p else None


def cohen_kappa(a, b) -> Optional[float]:
    p = _pairs(a, b)
    if not p:
        return None
    n = len(p)
    po = sum(x == y for x, y in p) / n
    ca, cb = Counter(x for x, _ in p), Counter(y for _, y in p)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def gwet_ac1(a, b) -> Optional[float]:
    p = _pairs(a, b)
    if not p:
        return None
    n = len(p)
    cats = sorted({x for x, _ in p} | {y for _, y in p}, key=str)
    q = len(cats)
    po = sum(x == y for x, y in p) / n
    if q < 2:
        return 1.0
    ca, cb = Counter(x for x, _ in p), Counter(y for _, y in p)
    pi = {k: (ca[k] + cb[k]) / (2 * n) for k in cats}
    pe = sum(v * (1 - v) for v in pi.values()) / (q - 1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def confusion(pred, ref) -> Dict[Tuple[Hashable, Hashable], int]:
    return dict(Counter(_pairs(pred, ref)))


def fp_fn(pred_correct: Sequence[Optional[bool]], ref_correct: Sequence[Optional[bool]]) -> Dict[str, int]:
    """Judge says correct but reference says wrong = false positive (lenient judge)."""
    c = Counter()
    for p, r in _pairs(pred_correct, ref_correct):
        c["TP" if p and r else "FP" if p and not r else "FN" if (not p) and r else "TN"] += 1
    return {k: c.get(k, 0) for k in ("TP", "FP", "FN", "TN")}


def bootstrap_ci(a, b, stat: Callable = cohen_kappa, n_boot: int = 2000, seed: int = 13,
                 alpha: float = 0.05) -> Tuple[Optional[float], Optional[float]]:
    p = _pairs(a, b)
    if len(p) < 2:
        return (None, None)
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        s = [p[rng.randrange(len(p))] for _ in p]
        v = stat([x for x, _ in s], [y for _, y in s])
        if v is not None:
            vals.append(v)
    vals.sort()
    lo, hi = vals[int(alpha / 2 * len(vals))], vals[int((1 - alpha / 2) * len(vals)) - 1]
    return (round(lo, 4), round(hi, 4))


def repeat_consistency(runs: List[Sequence]) -> Optional[float]:
    """runs = [labels_run1, labels_run2, ...] aligned by case."""
    if len(runs) < 2:
        return None
    n = len(runs[0])
    same = sum(1 for i in range(n) if len({r[i] for r in runs}) == 1)
    return same / n if n else None
