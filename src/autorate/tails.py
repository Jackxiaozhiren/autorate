"""The closed-form intervals a certificate publishes. No scipy; n up to a few thousand.

Owns both the exact binomial tail with its Clopper-Pearson inversion, and the DKW-style
width behind the automation-rate interval. The width lived in `inventory.py` until the
whole-branch review pointed out what that meant: the certifier imported the module that
spawns subprocesses and transcribes upstream manifests in order to do arithmetic.

`alpha` here is the tail of an interval. It is not the `alpha` on a certificate, which is
the coverage floor of the set -- the plan names both `alpha`, so the collision is
documented rather than renamed.
"""
from __future__ import annotations

import math

ALPHA_DEFAULT = 0.05


def bound_width(n: int, alpha: float = ALPHA_DEFAULT) -> float:
    """Width of the two-sided DKW-style interval on an automation-rate estimate.

    2 * sqrt(ln(2/alpha) / (2n)). The honest answer to "is this corpus big enough to
    certify anything", and the reason a refusal is a result.
    """
    if n <= 1:
        return float("inf")
    return 2.0 * math.sqrt(math.log(2.0 / alpha) / (2.0 * n))


def n_feasible(unique_n: int, alpha: float = ALPHA_DEFAULT,
               max_bound_width: float = 0.10) -> bool:
    return bound_width(unique_n, alpha) <= max_bound_width


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

    Deliberately NOT canonicalised. The returned double carries the last bits of 80
    `math.log`/`math.exp` evaluations, and those bits are not identical between Apple
    libm and glibc: the committed artefact says 0.7884344428029715, which is what this
    machine's libm answered, and the Linux runner re-derived 0.7884344428029711 for the
    same query (ledger R-121). That is exact arithmetic doing its job, and rounding it
    here would move every consumer's number -- the audit tables and the bounds that are
    only ever compared to themselves included -- to make a point about storage. The
    published precision is the CERTIFICATE's to own, at `certificate.PUBLISHED_DECIMALS`,
    applied where a bound crosses into a committed artefact. A caller re-deriving a stored
    certificate must go through that same canonicalisation, or it will disagree with the
    artefact in the last ULP.
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
