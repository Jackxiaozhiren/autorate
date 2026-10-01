"""Task 7b: the two-way choice certifier.

Every assertion here is about a number the certificate claims, so the tests check the
claim, not the code path: an automation rate that ignores refusals, or a conditional
bound that quietly equals the marginal one, both pass a weaker suite.
"""
import random

from autorate.certificate import Reason
from autorate.certify_choice import certify_choice
from autorate.records import Record


def _records(n, k=4, sharpness=6.0, seed=1, backend="synthetic", unlabelled=0,
             error_rate=0.0):
    """Synthetic labelled decisions.

    `error_rate` matters: the first version always peaked the probability vector on the
    gold label, so the argmax was never wrong, `errors_among_automated` came out 0 for
    every difficulty, and the whole error-budget sweep was vacuous. A certifier that is
    never shown a wrong answer cannot be shown refusing one.
    """
    rng = random.Random(seed)
    out = []
    for i in range(n):
        g = rng.randrange(k)
        peaked = g if rng.random() >= error_rate else (g + 1 + rng.randrange(k - 1)) % k
        w = [1.0] * k
        w[peaked] = sharpness
        tot = sum(w) + k * 0.05
        p = [x / tot for x in w]
        p = [round(x, 4) for x in p]
        p[peaked] = round(p[peaked] + (1.0 - sum(p)), 4)
        options = tuple("opt%d" % j for j in range(k))
        gold = None if i < unlabelled else options[g]
        out.append(Record(id=str(i), qtype="choice", backend=backend, repeat=0,
                          options=options, probs=tuple(p), gold=gold,
                          predicted=options[peaked], slices={}, scores={}, seed=seed,
                          u=rng.random(), meta={}))
    return out


def test_the_generator_actually_makes_wrong_argmaxes_when_asked():
    # Guards the vacuity of the error sweep: with error_rate=0.5 about half the
    # records must have predicted != gold, and with 0.0 none.
    clean = _records(400, sharpness=6.0, error_rate=0.0)
    noisy = _records(400, sharpness=6.0, error_rate=0.5)
    assert sum(r.predicted != r.gold for r in clean) == 0
    wrong = sum(r.predicted != r.gold for r in noisy)
    assert 120 < wrong < 280, wrong


def test_a_sharp_easy_task_produces_a_number_and_both_bounds():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is True, cert.summary()
    assert 0.0 < cert.autorate <= 1.0
    lo, hi = cert.autorate_ci
    assert lo <= cert.autorate <= hi
    assert cert.conditional_error_bound <= 0.05 + 1e-9
    assert cert.marginal_error_bound <= cert.conditional_error_bound
    assert cert.n_cal + cert.n_eval == 1200


def test_the_refusal_mass_is_reported_and_consistent_with_the_automation_rate():
    cert = certify_choice(_records(1200, sharpness=4.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.refusal_rate is not None and cert.refusal_rate >= 0.0
    assert cert.autorate + cert.refusal_rate <= 1.0 + 1e-9
    assert cert.mean_set_size > 0.0


def test_an_uninformative_task_with_real_errors_is_refused_not_certified():
    # Uniform mass AND a wrong argmax half the time: there is nothing to automate and
    # the conditional budget cannot be met. This is the case the old generator could
    # not express, because its argmax was never wrong.
    cert = certify_choice(_records(1200, sharpness=1.0, error_rate=0.5),
                          alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False, cert.summary()
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    assert cert.autorate is None and cert.qhat is None
    # R-21: a refusal carries the observation that caused it, not just a label.
    closest = cert.meta["closest_attempt"]
    assert closest is not None and closest["errors"] > 0
    assert closest["conditional_error_bound"] > 0.05
    assert "closest attempt" in cert.summary() or "error budget" in cert.summary()


def test_error_mass_alone_degrades_the_automation_rate():
    """Same shapes, same seed, only the wrongness differs."""
    clean = certify_choice(_records(1600, sharpness=5.0, error_rate=0.0),
                           alpha=0.05, beta=0.05, seed=13)
    noisy = certify_choice(_records(1600, sharpness=5.0, error_rate=0.35),
                           alpha=0.05, beta=0.05, seed=13)
    assert clean.feasible is True
    assert (noisy.autorate or 0.0) < clean.autorate, (clean.summary(), noisy.summary())
    assert noisy.meta["errors_among_automated"] > 0 or not noisy.feasible


def test_too_few_labelled_cases_is_its_own_refusal_reason():
    cert = certify_choice(_records(12), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False
    assert cert.reason == Reason.N_BELOW_MIN.value
    assert cert.n_cal + cert.n_eval == 12


def test_unlabelled_records_are_never_used_for_calibration_but_are_counted():
    labelled = _records(400, sharpness=8.0, seed=3)
    unlabelled = _records(400, sharpness=8.0, seed=2, unlabelled=400)
    cert = certify_choice(labelled + unlabelled, alpha=0.05, beta=0.05, seed=7)
    assert cert.n_cal + cert.n_eval == 400
    assert cert.meta["skipped_no_gold"] == 400
    assert cert.meta["skipped_wrong_qtype"] == 0


def test_other_question_types_are_not_silently_certified_as_choice():
    from autorate.records import Record as R

    noul = [R(id=str(i), qtype="noul", backend="synthetic", repeat=0,
              options=("false", "true"), probs=(0.2, 0.8), gold="true",
              predicted="true", slices={}, scores={}, seed=1, u=0.5, meta={})
            for i in range(300)]
    cert = certify_choice(noul, alpha=0.05, beta=0.05, seed=5)
    assert cert.feasible is False
    assert cert.reason == Reason.NO_GOLD_LABELS.value or cert.meta["skipped_wrong_qtype"] == 300
    assert cert.meta["skipped_wrong_qtype"] == 300


def test_envelope_is_never_empty_even_on_success():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert any("exchangeability" in s for s in cert.envelope)
    assert any("group" in s for s in cert.envelope)
    assert any("archived" in s or "shift" in s for s in cert.envelope)


def test_a_sharper_task_automates_more_at_the_same_budget():
    easy = certify_choice(_records(1200, sharpness=9.0, error_rate=0.01),
                          alpha=0.05, beta=0.05, seed=21)
    hard = certify_choice(_records(1200, sharpness=2.0, error_rate=0.35),
                          alpha=0.05, beta=0.05, seed=21)
    assert easy.feasible is True
    assert easy.autorate > (hard.autorate or 0.0)


def test_tighter_error_budgets_never_increase_the_automation_rate():
    recs = _records(1600, sharpness=4.0, error_rate=0.15)
    loose = certify_choice(recs, alpha=0.10, beta=0.10, seed=11)
    mid = certify_choice(recs, alpha=0.05, beta=0.05, seed=11)
    tight = certify_choice(recs, alpha=0.01, beta=0.01, seed=11)
    rates = [c.autorate if c.feasible else 0.0 for c in (loose, mid, tight)]
    assert rates == sorted(rates, reverse=True), rates


def test_the_same_records_produce_the_same_certificate_twice():
    recs = _records(800, sharpness=6.0, seed=3)
    a = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    b = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    assert a.autorate == b.autorate
    assert a.conditional_error_bound == b.conditional_error_bound
    assert a.qhat == b.qhat and a.refusal_rate == b.refusal_rate


def test_method_is_a_declared_choice_and_lac_certifies_a_different_frontier():
    recs = _records(1200, sharpness=6.0, seed=5)
    aps = certify_choice(recs, alpha=0.05, beta=0.05, seed=9, method="aps")
    lac = certify_choice(recs, alpha=0.05, beta=0.05, seed=9, method="lac")
    assert aps.method == "aps" and lac.method == "lac"
    assert aps.qhat != lac.qhat
