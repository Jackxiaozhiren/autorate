"""Exact binomial tails, with no scipy. n up to a few thousand is the whole design space."""
from __future__ import annotations


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed recursively so no factorial overflows."""
    if not 0 <= k <= n:
        raise ValueError("k must satisfy 0 <= k <= n, got k=%d n=%d" % (k, n))
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    if p <= 0.0:
        return 1.0
    term = (1.0 - p) ** n
    cdf = term
    for i in range(int(k)):
        term *= (n - i) / (i + 1) * p / (1.0 - p)
        cdf += term
    return min(1.0, cdf)


def clopper_pearson_upper(k: int, n: int, delta: float) -> float:
    """One-sided exact upper bound on a binomial rate at level 1 - delta.

    Inverts P(X <= k | p) = delta by bisection. With k = 0 this is the solution of
    (1 - p)^n = delta, i.e. p = 1 - delta**(1/n), which test_tails pins against the
    -ln(delta)/n approximation and against the CDF identity.
    """
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1), got %r" % (delta,))
    if not 0 <= k <= n:
        raise ValueError("k must satisfy 0 <= k <= n, got k=%d n=%d" % (k, n))
    if n == 0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if binom_cdf(k, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return lo
