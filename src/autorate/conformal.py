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

    `alpha` outside (0,1) is a usage error, not a vacuous answer: at alpha >= 1 the
    corrected index falls to <= 0 and `sorted[-1]` returns the MAXIMUM score while
    reporting itself non-vacuous -- anti-conservative with a clean flag.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1), got %r" % (alpha,))
    n = len(scores)
    if n == 0:
        raise ValueError("empty calibration set; nothing is certifiable")
    k = math.ceil((1.0 - alpha) * (n + 1))
    if k > n:
        return 1.0, True
    if k < 1:
        raise ValueError("alpha=%r drives the corrected index below 1 on n=%d; the coverage "
                         "floor must stay inside (0,1)" % (alpha, n))
    return float(sorted(float(s) for s in scores)[k - 1]), False


def conformal_set(probs: Sequence[float], qhat: float, u: float, method: str = "aps") -> list:
    if method not in METHODS:
        raise ValueError("unknown method %r; choose from %s" % (method, sorted(METHODS)))
    fn = METHODS[method]
    return [j for j in range(len(probs)) if fn(probs, j, u) <= qhat]


def classify_set(indices: Sequence[int]) -> str:
    """What a certified set MEANS: the one rule the certifier and the gate both use.

    Two owners for this decision is how a published automation rate comes to describe a
    rule the deployment never applied, so the classification lives here and is imported.
    """
    if not indices:
        return "empty"
    return "auto" if len(indices) == 1 else "escalate"


def is_singleton(indices: Sequence[int]) -> bool:
    return len(indices) == 1
