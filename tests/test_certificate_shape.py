"""Task 8a: the certificate object's shape rules.

The envelope is the product: a serialized certificate without one must be
unconstructable, so the disclaimer cannot be lost by forgetting to copy a README
section (spec 10).
"""
import pytest

from autorate.certificate import Reason, Certificate

_OK = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
           method="aps", backend="synthetic", qhat=0.4, autorate=0.6,
           autorate_ci=(0.55, 0.65), conditional_error_bound=0.04,
           marginal_error_bound=0.02, mean_set_size=1.05,
           n_cal=500, n_eval=500,
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


def test_the_refusal_mass_is_derived_from_the_automation_rate_not_supplied():
    # R-17 + R-20: every evaluated case is empty, singleton, or multi-label, so
    # refusal = 1 - autorate. It used to be a second field guarded only by `<= 1`,
    # which let 0.6 + 0.01 through: one number, two owners, and a guard that missed
    # everything between.
    assert _ok(autorate=0.6).refusal_rate == 0.4
    assert _ok(autorate=1.0).refusal_rate == 0.0
    with pytest.raises(TypeError):
        Certificate(**{**_OK, "refusal_rate": 0.05})
    with pytest.raises(ValueError, match="autorate"):
        _ok(autorate=1.01)


def test_a_refusal_still_reports_n_so_small_n_is_visible_as_the_cause():
    c = Certificate.refused(Reason.N_BELOW_MIN, alpha=0.05, beta=0.05, n_cal=12, n_eval=0,
                           detail="need 60/60", meta={})
    assert c.feasible is False and c.n_cal == 12
    assert c.reason == Reason.N_BELOW_MIN.value == "n_below_min"
    assert c.autorate is None and c.autorate_ci is None
    assert c.envelope  # a refusal is still conditioned by assumptions


def test_the_joint_level_is_derived_from_delta_and_the_claim_count():
    assert _ok(delta=0.05).level == 1.0 - 3 * 0.05
    assert _ok(delta=0.01).level == 0.97
    with pytest.raises(TypeError):
        Certificate(**{**_OK, "level": 0.9})


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


def test_a_refusal_cannot_carry_headline_numbers():
    # A refused certificate has measured nothing. Publishing an automation rate next to
    # "NOT_CERTIFIABLE" is how a refusal gets read as a small success downstream.
    for field, value in (("autorate", 0.6), ("qhat", 0.4), ("mean_set_size", 1.1),
                        ("conditional_error_bound", 0.01), ("autorate_ci", (0.1, 0.2))):
        kw = dict(_OK)
        kw.update(feasible=False, reason=Reason.N_BELOW_MIN.value, autorate_ci=None,
                  autorate=None, qhat=None, mean_set_size=None,
                  conditional_error_bound=None, marginal_error_bound=None)
        kw[field] = value
        with pytest.raises(ValueError, match="headline numbers"):
            Certificate(**kw)


def test_mean_set_size_below_one_is_legal_because_empty_sets_are_refusals():
    # R-17 again: measured 0.948 on synthetic data; a guard demanding >= 1 would reject truth.
    assert _ok(mean_set_size=0.948, autorate=0.94).mean_set_size < 1.0


def test_a_success_missing_a_bound_is_a_readable_error_not_a_typeerror():
    # The from_dict path took `lo, hi = self.autorate_ci` before any None check, so a
    # stored certificate without its bounds raised TypeError on the CLI and escaped the
    # documented exit codes.
    for field in ("autorate_ci", "conditional_error_bound", "marginal_error_bound",
                  "mean_set_size", "qhat", "autorate"):
        kw = dict(_OK)
        kw[field] = None
        with pytest.raises(ValueError, match="must carry"):
            Certificate(**kw)
