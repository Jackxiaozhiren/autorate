"""Nonconformity scores. All are in [0, 1], so a quantile above 1 is vacuous by construction."""
from __future__ import annotations

from typing import Sequence


def aps_score(probs: Sequence[float], index: int, u: float) -> float:
    """Randomised APS: mass strictly above p_index, plus u * p_index.

    Randomisation is required here rather than decorative: served probabilities are
    rounded to 4 decimals and shipped temperatures sharpen them, so exact ties between
    options are routine (spec 5.2). One `u` is shared across the labels of a single
    example, which is what keeps the set family nested -- and means an exact tie is
    admitted together or not at all.
    """
    p = [float(x) for x in probs]
    py = p[index]
    return sum(x for x in p if x > py) + u * py


def lac_score(probs: Sequence[float], index: int, u: float = 0.0) -> float:
    """1 - p_index. Kept for the declared comparison against APS (spec 6.4)."""
    return 1.0 - float(probs[index])
