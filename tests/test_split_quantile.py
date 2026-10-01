"""Task 6b: the split-conformal quantile, its finite-sample correction, and vacuity."""
import pytest

from autorate.conformal import conformal_set, split_quantile


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
    with pytest.raises(KeyError):
        conformal_set([0.5, 0.5], 0.4, 0.0, "truncation")
