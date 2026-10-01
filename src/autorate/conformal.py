"""Split conformal machinery. Knows numbers only, never field names (spec 5.1)."""
from __future__ import annotations

import math
from typing import Sequence

from .nonconformity import aps_score, lac_score

METHODS = {"aps": aps_score, "lac": lac_score}


def split_quantile(scores: Sequence[float], alpha: float) -> tuple:
    """The finite-sample-corrected split-conformal quantile, plus a vacuity flag.

    Returns (1.0, True) when ceil((1-alpha)(n+1)) exceeds n: the set would contain
    every label and the certificate would be a number with no content. Callers must
    surface that flag; it is a result, not an error to hide.
    """
    n = len(scores)
    if n == 0:
        raise ValueError("empty calibration set; nothing is certifiable")
    k = math.ceil((1.0 - alpha) * (n + 1))
    if k > n:
        return 1.0, True
    return float(sorted(float(s) for s in scores)[k - 1]), False


def conformal_set(probs: Sequence[float], qhat: float, u: float, method: str = "aps") -> list:
    fn = METHODS[method]
    return [j for j in range(len(probs)) if fn(probs, j, u) <= qhat]


def is_singleton(indices: Sequence[int]) -> bool:
    return len(indices) == 1
