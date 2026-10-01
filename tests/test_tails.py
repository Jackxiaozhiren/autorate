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
