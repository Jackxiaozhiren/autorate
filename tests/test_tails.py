"""Task 7a: exact binomial tails, no scipy. n up to a few thousand is the design space."""
import math

import pytest

from autorate.tails import binom_cdf, clopper_pearson_upper


def test_zero_failures_matches_the_closed_form():
    # k=0: the bound is the p with (1-p)^n = delta, i.e. -ln(delta)/n.
    got = clopper_pearson_upper(0, 100, 0.05)
    assert abs(got - (-math.log(0.05) / 100.0)) < 2e-3


def test_the_cdf_is_the_one_the_inversion_is_solving():
    # At the returned bound, P(X <= k) must sit at delta; that is the definition.
    for k, n in ((0, 100), (3, 200), (17, 500)):
        p = clopper_pearson_upper(k, n, 0.05)
        assert abs(binom_cdf(k, n, p) - 0.05) < 1e-3, (k, n, p, binom_cdf(k, n, p))


def test_bound_is_monotone_in_observed_failures():
    xs = [clopper_pearson_upper(k, 200, 0.05) for k in range(0, 20)]
    assert xs == sorted(xs)


def test_bound_shrinks_with_sample_size():
    assert clopper_pearson_upper(5, 500, 0.05) < clopper_pearson_upper(5, 50, 0.05)


def test_bound_is_at_least_the_point_estimate():
    for k, n in ((7, 100), (0, 100), (50, 200)):
        assert clopper_pearson_upper(k, n, 0.05) >= k / n


def test_no_events_yet_returns_the_upper_end_not_nan():
    assert clopper_pearson_upper(0, 0, 0.05) == 1.0
    assert math.isnan(clopper_pearson_upper(0, 0, 0.05)) is False


def test_cdf_endpoints_are_exact():
    assert binom_cdf(0, 50, 0.0) == 1.0
    assert abs(binom_cdf(0, 50, 0.1) - 0.9 ** 50) < 1e-12
    assert binom_cdf(50, 50, 0.5) == 1.0
    assert binom_cdf(0, 50, 1.0) == 0.0


def test_cdf_matches_a_brute_force_sum_on_a_small_case():
    from math import comb

    n, k, p = 12, 4, 0.3
    brute = sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    assert abs(binom_cdf(k, n, p) - brute) < 1e-12


def test_a_looser_confidence_level_gives_a_tighter_bound():
    assert clopper_pearson_upper(5, 200, 0.10) < clopper_pearson_upper(5, 200, 0.05)


def test_invalid_inputs_are_refused_not_silently_clamped():
    with pytest.raises(ValueError, match="delta"):
        clopper_pearson_upper(1, 10, 0.0)
    with pytest.raises(ValueError, match="k"):
        clopper_pearson_upper(11, 10, 0.05)


def test_the_bound_survives_the_double_precision_floor():
    """The head of the binomial CDF underflows at n in the thousands, and the module's
    own docstring names that range as its design space.

    Summing `(1-p)**n` first gave exactly 0.0 at n=3146, p=0.5, so every bisection step
    read the tail as below `delta` and the published "upper bound" came out BELOW the
    observed rate it claims to bound -- an anti-conservative bound with no signal.
    """
    import math

    n, k, delta = 3146, 1421, 0.05
    observed = k / n
    bound = clopper_pearson_upper(k, n, delta)
    assert bound >= observed, (bound, observed)
    assert observed < bound < 0.5, (observed, bound)
    # The normal approximation to the one-sided 95% bound, as an independent witness.
    approx = observed + 1.6449 * math.sqrt(observed * (1 - observed) / n)
    assert abs(bound - approx) < 0.004, (bound, approx)
    # The inversion identity is what the bisection promises.
    assert abs(binom_cdf(k, n, bound) - delta) < 1e-3, binom_cdf(k, n, bound)
    # And the probe is not vacuous here: the naive leading term the old code summed from
    # is exactly zero in this environment, which is how the bound got silently capped.
    assert (1.0 - observed) ** n == 0.0, "this environment does not underflow; the probe is vacuous"
    assert binom_cdf(k, n, observed) > 0.0


def test_the_cdf_is_a_distribution_function_on_a_large_case():
    n, p = 2000, 0.3
    assert binom_cdf(n, n, p) == 1.0
    # Steps through the body of the distribution: out in the far tails both ends saturate
    # (1.0 and 0.0) and a strict increase there would be a rounding artefact, not a CDF.
    cdfs = [binom_cdf(k, n, p) for k in (550, 580, 600, 620, 650)]
    assert all(b > a for a, b in zip(cdfs, cdfs[1:])), cdfs
    assert binom_cdf(0, n, p) < 1e-9 and binom_cdf(1000, n, p) > 0.999999


def test_the_primitive_stays_exact_and_the_published_precision_lives_elsewhere():
    """`tails` answers a mathematical question; the CERTIFICATE decides its storage.

    The obvious wrong fix for the cross-libc drift (R-121) is to round inside
    `clopper_pearson_upper`, because that is where the last bits come from. It is wrong twice
    over: the function's own contract is the root of P(X <= k | p) = delta, which test_tails
    pins by feeding the returned value back into `binom_cdf` below, and rounding there moves
    every consumer's number at once -- the audit tables, the non-published bounds that are only
    ever compared to themselves, and the other two certifiers -- to make a point about one
    artefact's bytes. So the raw double must stay raw here, and the canonicalisation belongs
    where a bound crosses into a committed certificate.
    """
    from autorate.certificate import CANONICALISED_BOUND_FIELDS, canonicalise_bound

    assert CANONICALISED_BOUND_FIELDS == ("conditional_error_bound", "marginal_error_bound")
    for k, n in ((1, 96), (21, 33), (3, 200)):          # the pairs the published artefacts hold
        raw = clopper_pearson_upper(k, n, 0.05)
        canon = canonicalise_bound(raw)
        assert raw != canon, (k, n, repr(raw))          # the primitive did NOT round itself
        assert canon > raw, (k, n)                      # and the published value is not weaker
        assert canon - raw < 1e-12, (k, n)
        # the identity this module promises is the raw root, not the stored grid point
        assert abs(binom_cdf(k, n, raw) - 0.05) < 1e-3, (k, n, raw)
