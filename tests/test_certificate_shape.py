"""Task 8a: the certificate object's shape rules.

The envelope is the product: a serialized certificate without one must be
unconstructable, so the disclaimer cannot be lost by forgetting to copy a README
section (spec 10).
"""
import pytest

from autorate.certificate import Reason, Certificate

_OK = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
           method="aps", grid_alpha=0.05, qhat=0.4, autorate=0.6,
           autorate_ci=(0.55, 0.65), conditional_error_bound=0.04,
           marginal_error_bound=0.02, joint_error_bound=0.03,
           refusal_rate=0.05, mean_set_size=1.05,
           n_cal=500, n_eval=500, level=0.9,
           envelope=("exchangeability within group assumed",), meta={})


def _ok(**kw):
    base = dict(_OK)
    base.update(kw)
    # When a test overrides only the point estimate, derive an interval that brackets it;
    # otherwise the ci guard fires first and the test measures the wrong rule.
    if "autorate" in kw and "autorate_ci" not in kw:
        a = kw["autorate"]
        base["autorate_ci"] = (max(0.0, a - 0.05), min(1.0, a + 0.05))
    return Certificate(**base)


def test_a_success_without_an_envelope_cannot_be_constructed():
    with pytest.raises(ValueError, match="envelope"):
        _ok(envelope=())


def test_a_refusal_without_a_reason_cannot_be_constructed():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason=None)


def test_a_reason_outside_the_closed_set_is_rejected():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason="because")


def test_a_feasible_certificate_may_not_carry_a_reason():
    with pytest.raises(ValueError, match="reason"):
        _ok(reason=Reason.N_BELOW_MIN.value)


def test_the_interval_must_bracket_the_point_estimate():
    with pytest.raises(ValueError, match="ci"):
        _ok(autorate=0.6, autorate_ci=(0.7, 0.8))
    with pytest.raises(ValueError, match="ci"):
        _ok(autorate_ci=(0.55, 0.5))


def test_the_refusal_decomposition_must_be_consistent():
    # R-17: automation + refusal + multi-label must not exceed the evaluated mass,
    # and an automation rate above 1.0 is arithmetically impossible.
    with pytest.raises(ValueError, match="refusal"):
        _ok(autorate=0.9, refusal_rate=0.5)
    with pytest.raises(ValueError, match="autorate"):
        _ok(autorate=1.01)


def test_a_refusal_still_reports_n_so_small_n_is_visible_as_the_cause():
    c = Certificate.refused(Reason.N_BELOW_MIN, alpha=0.05, beta=0.05, n_cal=12, n_eval=0,
                           detail="need 60/60", meta={})
    assert c.feasible is False and c.n_cal == 12
    assert c.reason == Reason.N_BELOW_MIN.value == "n_below_min"
    assert c.autorate is None and c.autorate_ci is None
    assert c.envelope  # a refusal is still conditioned by assumptions


def test_json_round_trip_is_exact_for_both_poles():
    for c in (_ok(), Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                        n_cal=500, n_eval=500, detail="none", meta={})):
        assert Certificate.from_dict(c.to_dict()) == c


def test_summary_names_the_budgets_a_refusal_failed():
    c = Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                            n_cal=500, n_eval=500, detail="none", meta={})
    assert "NOT_CERTIFIABLE" in c.summary() and "beta=0.05" in c.summary()
    assert "empty_feasible_set" in c.summary()


def test_a_feasible_summary_states_both_error_notions_and_never_conflates_them():
    s = _ok().summary()
    assert "conditional" in s and "marginal" in s
    assert "refusal" in s  # R-17
    # conditional is a rate among automated; marginal is a rate over all evaluated
    assert _ok(conditional_error_bound=0.5, marginal_error_bound=0.01).feasible is True


def test_reason_codes_are_a_closed_enumeration():
    assert {r.value for r in Reason} == {
        "n_below_min", "empty_feasible_set", "vacuous_quantile", "no_gold_labels"}


def test_marginal_can_never_exceed_conditional_because_p_auto_is_at_most_one():
    # P(wrong) = P(wrong | auto) * P(auto), and P(auto) <= 1.
    with pytest.raises(ValueError, match="marginal"):
        _ok(marginal_error_bound=0.30, conditional_error_bound=0.04)


def test_a_refusal_decomposition_cannot_exceed_the_evaluated_mass():
    with pytest.raises(ValueError, match="refusal"):
        _ok(autorate=0.6, refusal_rate=0.5)  # 1.1 > 1.0


def test_mean_set_size_below_one_is_legal_because_empty_sets_are_refusals():
    # R-17 again: measured 0.948 on synthetic data; a guard demanding >= 1 would reject truth.
    assert _ok(mean_set_size=0.948, refusal_rate=0.06, autorate=0.94).mean_size < 1.0
