"""The drift module declares an envelope; it does not buy immunity.

What this suite CANNOT detect, stated up front because several of its claims are prose claims about
guarantees and a test cannot prove a guarantee:

* it cannot show that ACI's regret bound is *true*. The bound is a theorem this module quotes, not
  derives. What is checked here is its FORM (a long-run average, a term that does not vanish, an
  alpha domain) and that the implementation does not contradict it on sequences the analysis
  covers -- numeric agreement is evidence, not a proof.
* it cannot detect a certificate whose producer declared a drift variable that does not exist in
  the data. `drift.py` reads a declaration; it has no record set to check it against, so a sincere
  lie ("variable: language" over a batch with no language slice) passes `marginal_only` and lands in
  a report. The guard for that belongs to the producer that holds the records (`groups.py` refuses
  an undeclared slice key), not here.
* it cannot see whether the caller-declared densities in `weighted_quantile` are the right ones.
  Every weighted-mode refusal below is about a *missing* or *malformed* declaration; a plausible
  wrong one moves the quantile and nothing here can tell that from a regime shift, which is exactly
  why the weighted envelope names the declaration as an assumption instead of a measurement.

The one real artefact used is `data/cert_laya.json`, a committed certificate produced by the real
certifier over the committed archive: it is the honest subject for the flag test, because nothing in
this project has ever conditioned on a declared drift variable.
"""
import inspect
import json
import math
from pathlib import Path

import pytest

from autorate.certificate import Certificate
from autorate.conformal import split_quantile
from autorate.drift import (ACI_ENVELOPE, DRIFT_DECLARATION_KEY, NOT_CERTIFIABLE_UNDER_DRIFT,
                            WEIGHTED_ENVELOPE, aci_regret_bound, aci_threshold, marginal_only,
                            weighted_level, weighted_quantile, with_drift_envelope)

REPO = Path(__file__).resolve().parents[1]
LAYA_CERT = REPO / "data" / "cert_laya.json"


def _cert(meta=None, **kwargs):
    """A refused `Certificate` carrying the caller's meta: the shape owner validates every field.

    Refused rather than feasible on purpose. A feasible certificate needs six headline numbers
    that have nothing to do with the drift flag, and fabricating them here would put a synthetic
    automation rate in a test that is about an envelope line.
    """
    base = dict(feasible=False, reason="no_gold_labels", alpha=0.05, beta=0.05, delta=0.05,
                method="aps", backend="synthetic", qhat=None, autorate=None, autorate_ci=None,
                conditional_error_bound=None, marginal_error_bound=None, mean_set_size=None,
                n_cal=0, n_eval=0,
                envelope=("exchangeability within group assumed; no group conditioning applied",),
                meta=dict(meta or {}))
    base.update(kwargs)
    return Certificate(**base)


def _committed_certificate():
    return Certificate.from_dict(json.loads(LAYA_CERT.read_text()))


def _declaration(variable="language", declared_by="producer slices", evidence="Record.slices"):
    return {"variable": variable, "declared_by": declared_by, "evidence": evidence}


def _grid(count, modulus=100):
    """A deterministic pseudo-uniform sequence of scores in [0,1): no RNG, so a red is re-runnable."""
    return [((i * 37) % modulus) / float(modulus) for i in range(count)]


# ----------------------------------------------------------------------------- the envelope flag

def test_a_marginal_only_certificate_carries_the_flag_and_it_is_the_committed_one():
    """The flag on real evidence: the archived laya certificate conditioned on nothing.

    `data/cert_laya.json` came out of `certify_choice` over the committed archive, so this is not a
    fixture shaped to pass. It states no drift declaration, therefore it is marginal-only, therefore
    the flag applies.
    """
    cert = _committed_certificate()
    assert DRIFT_DECLARATION_KEY not in cert.meta, sorted(cert.meta)
    assert marginal_only(cert) is True
    flagged = with_drift_envelope(cert)
    assert NOT_CERTIFIABLE_UNDER_DRIFT in flagged.envelope, flagged.envelope
    assert flagged.envelope[:len(cert.envelope)] == cert.envelope, "the flag is added, not swapped"
    assert with_drift_envelope(flagged) is flagged, "applying it twice must not double-print it"


def test_the_flag_names_the_condition_it_withdraws_and_moves_no_number():
    """A reader has to learn from the line itself what it voids, and the certificate stays intact.

    An envelope flag that also edited a bound would be the opposite failure: the flag is a
    statement about the claim, so every measured field has to survive it unchanged.
    """
    cert = _cert()
    flagged = with_drift_envelope(cert)
    text = NOT_CERTIFIABLE_UNDER_DRIFT.lower()
    assert "marginal" in text, NOT_CERTIFIABLE_UNDER_DRIFT
    assert "not_certifiable_under_drift" in text, (
        "the flag names itself, so a report can be grepped for it")
    for field in ("autorate", "qhat", "conditional_error_bound", "marginal_error_bound", "delta",
                  "reason"):
        assert getattr(flagged, field) == getattr(cert, field), field
    assert len(flagged.envelope) == len(cert.envelope) + 1, flagged.envelope


def test_a_declared_drift_variable_exempts_the_certificate_from_the_flag():
    """The exemption is reachable, which is what makes the flag a statement rather than a stamp.

    It cannot detect a false declaration (module docstring): it checks the shape of the declaration,
    and only the producer holding the records can check its truth.
    """
    cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration()})
    assert marginal_only(cert) is False
    assert with_drift_envelope(cert) is cert
    assert NOT_CERTIFIABLE_UNDER_DRIFT not in cert.envelope


def test_a_declaration_that_declares_no_conditioning_still_carries_the_flag():
    """`variable: "marginal"` is a caller buying the exemption with the word for having none."""
    for worthless in ("marginal", "MARGINAL", "none", "none declared", "unconditional"):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration(variable=worthless)})
        assert marginal_only(cert) is True, worthless
    for nameless in ("", " ", "\t"):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration(variable=nameless)})
        with pytest.raises(ValueError, match="variable"):
            marginal_only(cert)


def test_a_malformed_declaration_is_a_usage_refusal_not_a_pass_and_not_a_flag():
    """Absence means marginal-only; a garbled statement means nobody knows, and those differ.

    Reading a half-filled declaration as absence would refuse certification loudly (safe), and
    reading it as a declaration would exempt it silently (unsafe). Neither is chosen: the caller
    gets exit code 2 and a message naming the key it got wrong.
    """
    for bad in (["not", "a", "mapping"], "language", 7, {}, {"variable": "language"},
                {"variable": "", "declared_by": "x", "evidence": "y"},
                {"variable": "language", "declared_by": None, "evidence": "y"},
                {"variable": "language", "declared_by": "x", "evidence": ""},
                {"variable": None, "declared_by": "x", "evidence": "y"}):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: bad})
        with pytest.raises(ValueError, match="declaration") as excinfo:
            marginal_only(cert)
        assert "drift" in str(excinfo.value).lower(), str(excinfo.value)
    # and a key holding None is the absence case, which is a flag, not a refusal
    assert marginal_only(_cert(meta={DRIFT_DECLARATION_KEY: None})) is True


def test_the_envelope_text_withdraws_the_finite_sample_claim_where_it_does_not_hold():
    """The deliverable is the prose. Both modes say what they assume and neither claims immunity.

    This is a pattern guard, the same shape as the plan's Task 2 prose guard: it forbids wording,
    it can go red on an edit, and the pattern list only ever grows -- never narrows to pass.
    """
    forbidden = ("immune", "immunity", "no drift", "drift-free", "guarantees coverage",
                 "protected against", "regardless of drift", "unaffected by", "always valid")
    lines = tuple(WEIGHTED_ENVELOPE) + tuple(ACI_ENVELOPE) + (NOT_CERTIFIABLE_UNDER_DRIFT,)
    for line in lines:
        low = line.lower()
        for pattern in forbidden:
            assert pattern not in low, (line, pattern)
    assert any("declared" in l.lower() for l in WEIGHTED_ENVELOPE), WEIGHTED_ENVELOPE
    assert any("assum" in l.lower() for l in WEIGHTED_ENVELOPE), "an assumption, not a measurement"
    assert any("regret" in l.lower() or "long-run" in l.lower() for l in ACI_ENVELOPE), ACI_ENVELOPE
    assert any("finite" in l.lower() for l in ACI_ENVELOPE), ACI_ENVELOPE


# ---------------------------------------------------------------------------- the weighted mode

def test_unit_weights_reproduce_split_quantile_exactly_on_every_alpha_and_size():
    """The control that keeps the generalisation honest (the brief's own words).

    Checked over sizes 1..400 on a tie-heavy and tie-free score grid at nine alphas, comparing the
    whole answer -- quantile AND vacuity flag. It cannot detect a weighted path that is wrong for
    NON-unit weights (the tilt, order and zero-weight tests below reach that), and it cannot detect
    an agreement that holds because both arms return the same ceiling for different reasons -- the
    flag comparison is what narrows that.
    """
    scores = [0.0, 0.25, 0.25, 0.5, 0.75, 0.75, 0.75, 1.0]
    for n in range(1, 401):
        s = [scores[i % len(scores)] for i in range(n)]
        for alpha in (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99):
            plain = split_quantile(s, alpha)
            weighted = weighted_quantile(s, [1.0] * n, alpha)
            assert weighted == plain, (n, alpha, weighted, plain)


def test_the_density_vector_has_no_default_and_an_absent_one_is_a_refusal():
    """Mode 1 requires caller-declared densities: no uniform fallback may be reachable by omission.

    The signature check is the part a `weights=None` arm alone cannot satisfy -- a default
    parameter would let a caller take a weighted answer while declaring nothing at all.
    """
    parameters = inspect.signature(weighted_quantile).parameters
    assert parameters["weights"].default is inspect.Parameter.empty, (
        "a default density is an undeclared density")
    with pytest.raises(ValueError, match="declar"):
        weighted_quantile([0.5, 0.4], None, 0.1)
    with pytest.raises(ValueError, match="declar"):
        weighted_quantile([0.5, 0.4], (), 0.1)


def test_declared_densities_that_tilt_upward_cannot_lower_the_threshold():
    """The weighted mode must move in the direction the declaration says it will.

    Weights concentrated on the large scores raise the quantile; weights concentrated on the small
    ones lower it; the unit declaration sits between them. A sign error here is the
    anti-conservative direction, and both strict arms are what catch it.
    """
    scores = [0.1, 0.2, 0.3, 0.4, 0.9]
    alpha = 0.4
    middle, _ = weighted_quantile(scores, [1.0] * 5, alpha)
    high, _ = weighted_quantile(scores, [0.1, 0.1, 0.1, 0.1, 5.0], alpha)
    low, _ = weighted_quantile(scores, [5.0, 5.0, 5.0, 5.0, 0.1], alpha)
    assert high > middle > low, (high, middle, low)
    assert high in scores and low in scores and middle in scores, (high, low, middle)


def test_the_weighted_answer_does_not_depend_on_the_order_the_declaration_is_written_in():
    """A scan that accumulated in insertion order instead of score order would be wrong here.

    The permutation is over (score, weight) PAIRS, so the multiset is identical and every answer
    must be bit-identical -- including the flag, which is where an unordered scan shows up first.
    """
    pairs = [(0.9, 3.0), (0.1, 1.0), (0.5, 2.0), (0.5, 0.5), (0.2, 4.0)]
    reference = weighted_quantile([p[0] for p in pairs], [p[1] for p in pairs], 0.2)
    for rotated in range(len(pairs)):
        turned = pairs[rotated:] + pairs[:rotated]
        for alpha in (0.05, 0.2, 0.35, 0.5, 0.8):
            got = weighted_quantile([p[0] for p in turned], [p[1] for p in turned], alpha)
            want = weighted_quantile([p[0] for p in pairs], [p[1] for p in pairs], alpha)
            assert got == want, (turned, alpha, got, want)
    assert reference[0] in [p[0] for p in pairs], reference


def test_weighted_level_states_the_level_a_threshold_buys_and_the_selection_uses_it():
    """The cross-check's predicate is public, so its non-vacuity is testable without an edit.

    `weighted_level` returns (weight at-or-below, weight strictly-below) for a candidate threshold.
    The selected quantile must satisfy at-or-below >= target > strictly-below, and a threshold one
    step too LOW must fail the first half -- which is the shape of the anti-conservative error the
    internal cross-check refuses as `ArithmeticError`. What is tested is that the predicate
    discriminates; a wrong threshold is not a parameter this module can be handed.
    """
    scores = [0.1, 0.5, 0.9]
    weights = [1.0, 2.0, 4.0]
    alpha = 0.2
    target = (1.0 - alpha) * (sum(weights) + 1.0)
    q, vacuous = weighted_quantile(scores, weights, alpha)
    assert vacuous is False
    at_or_below, strictly_below = weighted_level(scores, weights, q)
    assert at_or_below >= target, (at_or_below, target)
    assert strictly_below < target, "q is the smallest value that reaches the level"
    too_low, _ = weighted_level(scores, weights, 0.5)
    assert too_low < target, too_low
    too_high, _ = weighted_level(scores, weights, 1.0)
    assert too_high > target, too_high


def test_weighted_quantile_refuses_inputs_that_cannot_be_a_density_declaration():
    """Every one of these is exit code 2 (usage), not a vacuous answer: the input is the problem."""
    good = [0.1, 0.5, 0.9]
    for bad_alpha in (0.0, 1.0, -0.1, 1.5, float("nan")):
        with pytest.raises(ValueError, match="alpha"):
            weighted_quantile(good, [1.0, 1.0, 1.0], bad_alpha)
    with pytest.raises(ValueError, match="empty"):
        weighted_quantile([], [], 0.1)
    with pytest.raises(ValueError, match="length"):
        weighted_quantile(good, [1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="negative"):
        weighted_quantile(good, [1.0, -2.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile(good, [float("nan"), 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile(good, [float("inf"), 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile([0.1, float("nan"), 0.9], [1.0, 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="sum to zero"):
        weighted_quantile(good, [0.0, 0.0, 0.0], 0.1)
    # an unbounded score would make the vacuous arm's 1.0 a threshold instead of a ceiling
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        weighted_quantile([0.1, 3.5, 0.9], [1.0, 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        weighted_quantile([0.1, -0.5, 0.9], [1.0, 1.0, 1.0], 0.1)


def test_a_zero_weight_sample_is_kept_and_never_selected_as_the_threshold():
    """A density of zero is a declaration with content: this score has no mass in that regime.

    It must not be dropped -- the denominator is the sum of the declared weights -- and it must not
    become the selected threshold, because a value carrying no weight cannot be where the declared
    mass crosses.
    """
    scores = [0.1, 0.2, 0.8]
    weights = [0.0, 3.0, 3.0]
    total = sum(weights)
    for alpha in (0.1, 0.4, 0.6):
        target = (1.0 - alpha) * (total + 1.0)
        q, vacuous = weighted_quantile(scores, weights, alpha)
        assert q != 0.1, "a zero-weight score was selected at alpha=%r" % alpha
        at_or_below, strictly_below = weighted_level(scores, weights, q)
        if not vacuous:
            assert at_or_below >= target > strictly_below, (q, target, at_or_below)
        assert at_or_below <= total, at_or_below


def test_the_vacuous_arm_is_the_ceiling_and_not_an_invented_value():
    """A small alpha asks for a high level and no declared sample reaches it.

    The answer is the ceiling 1.0 plus the flag, exactly as `split_quantile` does it: a weighted
    mode that answered with an interpolated value here would publish a threshold no declaration
    supports, with a clean flag beside it.
    """
    scores = [0.1, 0.2, 0.3]
    q, vacuous = weighted_quantile(scores, [1.0, 1.0, 1.0], 0.01)
    assert (q, vacuous) == (1.0, True), (q, vacuous)
    assert (q, vacuous) == split_quantile(scores, 0.01)
    assert weighted_quantile(scores, [0.5, 0.5, 0.5], 0.01) == (1.0, True)
    assert weighted_quantile(scores, [2.0, 2.0, 2.0], 0.05) == (1.0, True)


# ------------------------------------------------------------------------------- the ACI mode

def _steps(scores, alpha=0.05, gamma=0.05, **kwargs):
    return list(aci_threshold(scores, alpha, gamma, **kwargs))


def test_aci_yields_the_threshold_it_used_before_it_saw_the_score():
    """The ordering is the guarantee's whole content: a threshold chosen after the score is not one.

    Round t's `lam` is round t-1's updated value, and the first round's is the declared start --
    recorded, never presented as informative. A raise-on-error step is what keeps the recursion
    stable, so the sign is asserted too: an error at round 1 must push the next threshold UP.
    """
    scores = [0.9, 0.1, 0.9, 0.9]
    steps = _steps(scores, alpha=0.05, gamma=0.1, lam0=0.5)
    assert [s.t for s in steps] == [1, 2, 3, 4], steps
    assert steps[0].lam == 0.5, "the declared start is used, not a fitted one"
    assert steps[0].score == 0.9 and steps[0].err == 1
    assert steps[1].lam == pytest.approx(0.595), steps[1].lam
    assert steps[1].err == 0
    assert steps[2].lam == pytest.approx(0.59), steps[2].lam
    assert all(0.0 <= s.lam <= 1.0 for s in steps), steps


def test_the_iterator_is_an_iterator_and_a_prefix_is_the_same_answer_as_the_full_run():
    """The API promise is an iterator, and partial consumption must not change any answer.

    What this CANNOT detect: that the score list itself is held in memory (it must be, the input is
    a sequence), and that a list-returning implementation would satisfy the prefix arm -- which is
    why the iterator-protocol arm is asserted separately.
    """
    scores = [0.5] * 10000
    it = aci_threshold(scores, 0.05, 0.05)
    assert iter(it) is it, "not an iterator: %r" % type(it)
    first_three = [next(it) for _ in range(3)]
    assert [s.t for s in first_three] == [1, 2, 3]
    full = _steps(scores)
    assert [(s.t, s.lam, s.err) for s in first_three] == [(s.t, s.lam, s.err) for s in full[:3]]


def test_the_regret_bound_is_a_regret_bound_and_says_nothing_about_one_round():
    """The brief's central requirement: assert the regret form, and explicitly NOT finite-sample.

    Three properties, each of which an implementation dressed up as finite-sample would fail:
      at T=1 and T=10 the bound exceeds 1.0, so it permits ANY realised error rate;
      with gamma fixed it tends to gamma / (2(1-2 alpha)) as T grows and never to zero;
      it is not monotone in gamma -- one term wants a large step and the other a small one -- which
        is what a regret trade-off looks like and never what a confidence width looks like.
    The measured crossing this module has to state honestly: at alpha=0.05 and gamma=0.05 the
    bound first comes under 0.10 at round 277. A drift mode that said anything earlier would be
    saying more than its analysis does.
    """
    alpha, gamma = 0.05, 0.05
    assert aci_regret_bound(1, alpha, gamma) > 1.0, "a one-round guarantee would be a lie"
    assert aci_regret_bound(10, alpha, gamma) > 1.0
    assert aci_regret_bound(100, alpha, gamma) > 0.10
    assert aci_regret_bound(277, alpha, gamma) <= 0.10
    tail = gamma / (2.0 * (1.0 - 2.0 * alpha))
    assert aci_regret_bound(10 ** 9, alpha, gamma) == pytest.approx(tail, rel=1e-6)
    assert aci_regret_bound(10 ** 9, alpha, gamma) > 0.0
    large_t = [aci_regret_bound(t, alpha, gamma) for t in (100, 1000, 10000)]
    assert large_t == sorted(large_t, reverse=True), large_t
    sweeping = [aci_regret_bound(5000, alpha, g) for g in
                (0.005, 0.01, 0.02, 0.04, 0.08, 0.2, 0.5)]
    assert sweeping[0] > min(sweeping) and sweeping[-1] > min(sweeping), sweeping
    assert math.isfinite(aci_regret_bound(277, alpha, gamma))


def test_aci_regret_bound_refuses_a_request_outside_the_range_it_was_stated_for():
    """alpha >= 0.5 makes the second term infinite: a formula's domain is its owner's business.

    `tails.bound_width` refuses n <= 1 the same way, and an unguarded alpha=0.5 here would return
    a division-by-zero `ZeroDivisionError`, which has no exit code in this project.
    """
    # the explosion the refusal exists to prevent, shown rather than asserted about python
    assert aci_regret_bound(100, 0.49, 0.05) > 1.0, aci_regret_bound(100, 0.49, 0.05)
    assert aci_regret_bound(100, 0.4999, 0.05) > 100.0, aci_regret_bound(100, 0.4999, 0.05)
    for bad_alpha in (0.5, 0.75, 1.0, 0.0, -0.2):
        with pytest.raises(ValueError, match="alpha"):
            aci_regret_bound(100, bad_alpha, 0.05)
    with pytest.raises(ValueError, match="rounds"):
        aci_regret_bound(0, 0.05, 0.05)
    with pytest.raises(ValueError, match="rounds"):
        aci_regret_bound(-1, 0.05, 0.05)
    for bad_gamma in (0.0, 1.0, 1.5, -0.5):
        with pytest.raises(ValueError, match="gamma"):
            aci_regret_bound(100, 0.05, bad_gamma)


def test_aci_tracks_the_target_rate_on_stationary_and_shifted_scores_within_the_bound():
    """Numeric agreement with the stated form, including a sequence that shifts mid-run.

    This is evidence for the implementation, not for the theorem (module docstring). It also shows
    what the mode trades: on 12 scores at alpha=0.05 `split_quantile` answers vacuously, while ACI
    returns a working threshold -- a threshold with no finite-sample statement attached to it.
    """
    stationary = _grid(2000)
    shifted = _grid(1000) + [((i * 37) % 50 + 50) / 100.0 for i in range(1000)]
    constant = [0.95] * 2000
    for name, scores in (("stationary", stationary), ("shifted", shifted), ("constant", constant)):
        steps = _steps(scores, alpha=0.05, gamma=0.05)
        realised = sum(s.err for s in steps) / len(steps)
        limit = aci_regret_bound(len(steps), 0.05, 0.05)
        assert abs(realised - 0.05) <= limit, (name, realised, limit)
    small = _steps(_grid(4, modulus=10) * 3, alpha=0.05, gamma=0.05)
    assert len(small) == 12
    q_hat, vacuous = split_quantile([s.score for s in small], 0.05)
    assert vacuous is True and q_hat == 1.0, (q_hat, vacuous)
    assert any(0.0 < s.lam < 1.0 for s in small), "ACI answered with a working threshold"


def test_aci_under_a_shift_makes_no_per_round_promise():
    """The failure mode this test exists to forbid: reading a mid-adaptation threshold as a bound.

    Right after the shift the realised window error rate is far above alpha -- drift doing what
    drift does -- and no finite-sample statement is available to soften it. Measured here: 6/10 of
    the first ten rounds after the shift are errors at gamma=0.005, and the window rate stays above
    0.3. If a future edit made those look bounded, this test reddens and the envelope line has to
    be re-read, which is the intended behaviour.
    """
    before = _grid(500)
    after = [(90 + (i * 7) % 10) / 100.0 for i in range(50)]
    steps = _steps(before + after, alpha=0.05, gamma=0.005)
    window = steps[500:550]
    assert sum(s.err for s in window[:10]) / 10.0 == 0.6, [s.err for s in window[:10]]
    assert sum(s.err for s in window) / len(window) > 0.3
    carried = min(1.0, max(0.0, steps[499].lam + 0.005 * (steps[499].err - 0.05)))
    assert window[0].lam == pytest.approx(carried), (
        "the threshold carries over the shift instead of restarting at a fitted value")
    assert any("per-round" in l.lower() for l in ACI_ENVELOPE), ACI_ENVELOPE


def test_aci_refuses_inputs_that_would_silently_widen_its_stated_range():
    """Scores outside [0,1] leave the bounded range the analysis is stated on; an empty sequence has
    no rounds to bound; and a declared start outside [0,1] would break the clipping the proof uses."""
    with pytest.raises(ValueError, match="empty"):
        _steps([])
    for bad_alpha in (0.0, 0.5, 0.9):
        with pytest.raises(ValueError, match="alpha"):
            _steps([0.1, 0.2], alpha=bad_alpha, gamma=0.05)
    for bad_gamma in (0.0, 1.0, 2.0):
        with pytest.raises(ValueError, match="gamma"):
            _steps([0.1, 0.2], alpha=0.05, gamma=bad_gamma)
    with pytest.raises(ValueError, match="0,1"):
        _steps([0.1, 1.4], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="0,1"):
        _steps([0.1, -0.2], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="finite"):
        _steps([0.1, float("nan")], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="lam0"):
        _steps([0.1, 0.2], lam0=1.5)
    with pytest.raises(ValueError, match="lam0"):
        _steps([0.1, 0.2], lam0=-0.5)


def test_aci_threshold_is_not_a_renamed_split_quantile():
    """Two different guarantees, so a caller cannot mix them up by accident.

    The ACI step carries no vacuity flag and no finite-sample correction: at alpha=0.95 over three
    scores `split_quantile` selects the LOWEST order statistic while ACI sits at the declared start
    and reports each round's error. Asserting the two disagree is what stops a later edit from
    "unifying" them, which would smuggle the finite-sample claim back in.
    """
    scores = [0.2, 0.5, 0.9]
    plain = split_quantile(scores, 0.95)
    steps = _steps(scores, alpha=0.05, gamma=0.05, lam0=0.5)
    assert plain == (0.2, False), plain
    assert steps[0].lam == 0.5
    assert steps[0].err == 0
    assert not hasattr(steps[0], "vacuous"), "ACI has no finite-sample vacuity to report"


def test_the_weighted_and_aci_modes_are_stated_as_two_modes_and_never_combined():
    """Mode 1 assumes a declared density ratio; mode 2 assumes nothing and pays regret.

    A single call that did both would be an unnameable guarantee, so neither function accepts the
    other's control: `weighted_quantile` has no gamma and `aci_threshold` has no weights.
    """
    w_params = set(inspect.signature(weighted_quantile).parameters)
    a_params = set(inspect.signature(aci_threshold).parameters)
    assert w_params == {"scores", "weights", "alpha"}, w_params
    assert a_params == {"scores", "alpha", "gamma", "lam0"}, a_params
    assert math.isfinite(aci_regret_bound(1000, 0.05, 0.05))
