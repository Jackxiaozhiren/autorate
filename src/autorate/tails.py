"""Exact binomial tails, with no scipy. n up to a few thousand is the whole design space."""
from __future__ import annotations

import math


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space so the head cannot underflow.

    The naive recursion starts at `(1-p)**n`, which is exactly 0.0 once `n*log1p(-p)`
    passes the double floor -- around n=1000 at p=0.5. A silent zero there makes every
    bisection step think the tail is below `delta`, and the published upper bound comes
    out *smaller than the observed rate it claims to bound*.
    """
    if not 0 <= k <= n:
        raise ValueError("k must satisfy 0 <= k <= n, got k=%d n=%d" % (k, n))
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    if p <= 0.0:
        return 1.0
    if k == n:
        return 1.0
    log_p, log_q = math.log(p), math.log1p(-p)
    log_term = n * log_q
    logs = [log_term]
    for i in range(1, int(k) + 1):
        log_term += math.log(n - i + 1) - math.log(i) + log_p - log_q
        logs.append(log_term)
    top = max(logs)
    return min(1.0, math.exp(top) * sum(math.exp(x - top) for x in logs))


def clopper_pearson_upper(k: int, n: int, delta: float) -> float:
    """One-sided exact upper bound on a binomial rate at level 1 - delta.

    Inverts P(X <= k | p) = delta by bisection. With k = 0 this is the solution of
    (1 - p)^n = delta, i.e. p = 1 - delta**(1/n), which test_tails pins against the
    -ln(delta)/n approximation and against the CDF identity.

    For `delta <= 0.5` the bound is at least the observed rate k/n; that invariant is
    asserted rather than assumed, because the underflow above breaks exactly it.
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
    bound = lo
    if delta <= 0.5 and bound < k / n:
        raise ArithmeticError(
            "Clopper-Pearson upper bound %.6f came out below the observed rate %.6f at "
            "k=%d n=%d delta=%g; an upper bound cannot be beaten by its own data" % (
                bound, k / n, k, n, delta))
    return bound
