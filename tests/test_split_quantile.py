"""Task 6b: the split-conformal quantile, its finite-sample correction, and vacuity."""
import pytest

from autorate.conformal import conformal_set, lac_score, split_quantile


def test_quantile_index_is_the_finite_sample_correction_not_the_naive_one():
    # n=19, alpha=0.05: ceil(0.95*20)=19, the 19th smallest of 19, i.e. the maximum.
    # The naive floor(0.95*n)=18 would take the 18th and silently under-cover.
    scores = [float(i) for i in range(1, 20)]
    q, vac = split_quantile(scores, 0.05)
    assert q == 19.0 and vac is False


def test_quantile_is_vacuous_and_flagged_when_the_correction_does_not_fit():
    # n=10, alpha=0.05: ceil(0.95*11)=11 > 10, so every label would be in the set.
    q, vac = split_quantile([0.1 * i for i in range(1, 11)], 0.05)
    assert q == 1.0 and vac is True


def test_vacuity_is_reported_as_a_value_not_hidden_behind_a_number():
    q, vac = split_quantile([0.5], 0.05)
    assert vac is True
    # A vacuous certificate covers every label, so it automates nothing.
    assert conformal_set([0.9, 0.1], q, 0.0, "aps") == [0, 1]


def test_empty_calibration_raises_instead_of_certifying_nothing():
    with pytest.raises(ValueError, match="empty"):
        split_quantile([], 0.05)


def test_alpha_monotonicity_larger_alpha_smaller_sets():
    scores = [i / 100 for i in range(1, 101)]
    q_loose, _ = split_quantile(scores, 0.10)
    q_tight, _ = split_quantile(scores, 0.01)
    assert q_loose <= q_tight
    probs = [0.5, 0.3, 0.2]
    assert len(conformal_set(probs, q_loose, 0.0, "aps")) <= len(
        conformal_set(probs, q_tight, 0.0, "aps"))


def test_the_naive_quantile_is_distinguishable_from_the_correct_one():
    # The naive rule is computed HERE, not shipped as a production function: a
    # deliberately wrong helper living in src/ would be dead code with an API name.
    import math

    scores = [float(i) for i in range(1, 20)]
    correct, _ = split_quantile(scores, 0.05)
    naive_index = int(math.floor(0.95 * len(scores)))          # 18th of 19
    naive = sorted(scores)[naive_index - 1]
    assert naive == 18.0 and correct == 19.0


def test_method_names_are_a_closed_set():
    # ValueError, not KeyError: the CLI maps a usage error to exit 2, and an uncaught
    # KeyError would escape the documented exit-code contract as rc 1.
    with pytest.raises(ValueError, match="unknown method"):
        conformal_set([0.5, 0.5], 0.4, 0.0, "truncation")


def test_lac_sets_are_a_different_frontier_from_aps_and_are_exercised_directly():
    # The name was selectable but never selected: METHODS = {"lac": aps_score} would
    # have shipped green, and every set assertion below ran on aps alone.
    # On an exact tie the two differ by construction: LAC scores both at 0.5 and
    # certifies neither, while randomised APS scores both at 0.25 and admits the pair.
    probs, qhat, u = [0.5, 0.5], 0.4, 0.5
    assert conformal_set(probs, qhat, u, method="lac") == []
    assert conformal_set(probs, qhat, u, method="aps") == [0, 1]
    assert lac_score(probs, 1) == 0.5 and lac_score(probs, 0) == 0.5


def test_an_alpha_outside_the_unit_interval_is_a_usage_error_not_a_quantile():
    # At alpha >= 1 the corrected index falls to <= 0 and sorted[-1] returns the MAXIMUM
    # score while reporting itself non-vacuous: anti-conservative with a clean flag.
    for bad in (0.0, 1.0, 1.5, -0.2):
        with pytest.raises(ValueError, match="alpha must be"):
            split_quantile([0.1, 0.2, 0.3], bad)
    # n=3 cannot supply the ceil(0.9*4)=4th order statistic, so a 90%-coverage level is
    # vacuous; a 1%-coverage level needs only the 1st and is not.
    q, vacuous = split_quantile([0.1, 0.2, 0.3], 0.10)
    assert vacuous is True and q == 1.0
    q2, vacuous2 = split_quantile([0.1, 0.2, 0.3], 0.99)
    assert vacuous2 is False and q2 == 0.1
