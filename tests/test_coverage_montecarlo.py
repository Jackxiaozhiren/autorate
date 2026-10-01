"""Task 6c: the coverage proof. Synthetic, seeded, with a known exchangeable pair.

Every allowance in here is DERIVED (3 sigma of the estimate being compared), not
picked, because an undistributed slack is how a coverage test starts passing things
it should fail. The falsification is a scratch-copy edit, not a shipped helper.
"""
import math
import random

import pytest

from autorate.conformal import conformal_set, split_quantile
from autorate.nonconformity import aps_score

ALPHA = 0.05
N_CAL = 800
N_EVAL = 400
TRIALS = 60


def _draw(rng, k, sharpness, error_rate=0.0, jitter=0.0):
    """One labelled decision: a gold index and a probability vector over k options.

    `error_rate` is the point. The first version always peaked the vector on the gold
    label, so every singleton set was correct, `auto_wrong` was 0 across all 24000
    pooled decisions, and the joint-event test below could not have failed -- the same
    defect the ledger records for the Task 7 generator, re-checked here and found live.
    """
    gold = rng.randrange(k)
    peak = gold if rng.random() < error_rate else (gold + 1) % k
    # jitter=0 keeps the non-gold options exactly tied, which is the tie behaviour APS
    # randomisation is for; a jittered vector gives a continuous score distribution,
    # which is what makes two neighbouring quantiles produce DIFFERENT sets.
    w = [1.0 + jitter * rng.random() for _ in range(k)]
    w[peak] = sharpness
    # A real additive floor: dividing by `sum(w) + k*eps` and renormalising afterwards
    # cancels exactly, so the smoothing used to do nothing but claim to do something.
    # Non-gold options stay exactly tied, which is the tie behaviour APS exists for.
    p = [x + 0.05 for x in w]
    s = sum(p)
    return gold, [x / s for x in p]


def _one_trial(seed, k, sharpness, error_rate=0.0):
    """Returns raw counts, not rates: rates multiply wrongly and rounding hides it."""
    rng = random.Random(seed)
    cal_scores = []
    for _ in range(N_CAL):
        g, p = _draw(rng, k, sharpness, error_rate)
        cal_scores.append(aps_score(p, g, rng.random()))
    qhat, vacuous = split_quantile(cal_scores, ALPHA)
    if vacuous:
        return None
    misses = autom = auto_wrong = empties = multi = size_sum = 0
    for _ in range(N_EVAL):
        g, p = _draw(rng, k, sharpness, error_rate)
        C = conformal_set(p, qhat, rng.random(), "aps")
        size_sum += len(C)
        if g not in C:
            misses += 1
        if not C:
            empties += 1
        elif len(C) == 1:
            autom += 1
            if C[0] != g:
                auto_wrong += 1
        else:
            multi += 1
    return {"misses": misses, "autom": autom, "auto_wrong": auto_wrong,
            "empties": empties, "multi": multi,
            "mean_size": size_sum / N_EVAL, "qhat": qhat}


@pytest.mark.parametrize("k,sharpness", [(4, 6.0), (4, 1.2), (20, 3.0), (2, 1.05)])
def test_marginal_coverage_holds_within_the_derived_allowance(k, sharpness):
    # 3 sigma of an empirical miss rate at the nominal level, over N_EVAL draws.
    slack = 3.0 * math.sqrt(ALPHA * (1.0 - ALPHA) / N_EVAL)
    # Trials that trip the per-trial bound by chance alone are allowed at a rate set by
    # the normal approximation to the binomial, not by taste.
    per_trial_trip = 1.0 - 0.9986501  # P(|Z| > 3)
    allowed = math.ceil(TRIALS * per_trial_trip * 2)         # one order of margin
    violations = 0
    worst = 0.0
    for t in range(TRIALS):
        r = _one_trial(20260929 + t, k, sharpness)
        if r is None:
            violations += 1
            continue
        miss = r["misses"] / N_EVAL
        worst = max(worst, miss)
        if miss > ALPHA + slack:
            violations += 1
    assert violations <= allowed, (
        "%d/%d trials under-covered beyond alpha+%.4f (worst miss %.4f)"
        % (violations, TRIALS, slack, worst))


@pytest.mark.parametrize("k,sharpness", [(4, 6.0), (4, 1.2), (20, 3.0)])
def test_the_set_is_never_vacuous_and_its_refusal_mass_is_bounded(k, sharpness):
    """Non-vacuity plus the over-refusal mass that randomized sets produce.

    Measured, not assumed: with `u` drawn fresh at prediction time the argmax label's
    score is `u * p_max > 0`, so when qhat falls below it the certified set is EMPTY.
    An empty set is a REFUSAL, not an error, and it must be counted: a certificate that
    ignores it overstates how much of the traffic it automates.
    """
    total = empty = autom = size_sum = 0
    for t in range(TRIALS):
        r = _one_trial(777000 + t, k, sharpness)
        assert r is not None
        total += N_EVAL
        empty += r["empties"]
        autom += r["autom"]
        size_sum += int(round(r["mean_size"] * N_EVAL))
    assert total > 0
    mean_size = size_sum / total
    assert 0.0 < mean_size < k, "vacuous or degenerate: mean set size %.4f" % mean_size
    empty_rate = empty / total
    slack = 3.0 * math.sqrt(ALPHA * (1.0 - ALPHA) / total)
    assert empty_rate <= ALPHA + slack, (
        "refusal mass %.4f exceeds alpha+%.4f" % (empty_rate, slack))
    # The decomposition is an identity, not an inequality: every evaluated case is
    # empty, singleton, or multi-label, and `autom + empty <= total` was satisfied by
    # any two of the three counts being wrong.
    for t2 in range(1):
        r = _one_trial(777000, k, sharpness)
        assert r["autom"] + r["empties"] + r["multi"] == N_EVAL, r


@pytest.mark.parametrize("k,sharpness,error_rate", [(4, 6.0, 0.3), (4, 1.2, 0.4),
                                                   (20, 3.0, 0.25)])
def test_the_joint_event_the_certificate_claims_is_the_one_measured(k, sharpness, error_rate):
    """P(wrong AND automated) must not exceed alpha -- the claim §5.2 rests on.

    Measured over TRIALS x N_EVAL pooled decisions, with the allowance derived from
    the pooled binomial rather than asserted. `{wrong AND auto}` is a subset of
    `{gold outside the set}`, so the guarantee holds whatever the model's accuracy is --
    which is why the generator is forced to be WRONG often: an event that never occurs
    proves nothing about a bound on it.
    """
    total = 0
    wrong_auto = 0
    automated = 0
    misses = 0
    for t in range(TRIALS):
        r = _one_trial(31337 + t, k, sharpness, error_rate)
        if r is None:
            continue
        total += N_EVAL
        wrong_auto += r["auto_wrong"]      # already a joint count: no rate multiplication
        automated += r["autom"]
        misses += r["misses"]
    assert total > 0 and automated > 0, "nothing automated: the frontier claim is empty"
    assert wrong_auto > 0, (
        "the joint event never occurred in %d decisions: this test cannot fail, so it "
        "certifies nothing about P(wrong AND auto)" % total)
    assert wrong_auto <= misses, "a wrong singleton is by definition a miss"
    rate = wrong_auto / total
    slack = 3.0 * math.sqrt(max(rate, ALPHA) * (1 - max(rate, ALPHA)) / total)
    assert rate <= ALPHA + slack, (
        "P(wrong AND auto)=%.4f exceeds alpha+%.4f" % (rate, ALPHA + slack))


def test_the_naive_quantile_under_covers_and_this_test_can_see_it():
    """The falsifiability statement, executable.

    floor((1-alpha)n) instead of the (n+1)-corrected ceil() drops the largest score,
    so the set is strictly smaller and coverage must degrade. Computed here so the
    wrong rule never lives in src/.
    """
    rng = random.Random(4242)
    k, sharpness = 4, 1.6
    cal = [_draw(rng, k, sharpness, jitter=0.4) for _ in range(N_CAL)]
    scores = [aps_score(p, g, rng.random()) for g, p in cal]
    srt = sorted(scores)
    naive_idx = int(math.floor(0.95 * len(scores)))
    q_naive = srt[naive_idx - 1]
    q_correct, _ = split_quantile(scores, ALPHA)
    assert q_naive < q_correct, "the naive index is not smaller here: pick a size that exposes it"

    miss_naive = miss_correct = 0
    for _ in range(3000):
        g, p = _draw(rng, k, sharpness, jitter=0.4)
        u = rng.random()
        if g not in conformal_set(p, q_naive, u, "aps"):
            miss_naive += 1
        if g not in conformal_set(p, q_correct, u, "aps"):
            miss_correct += 1
    assert miss_naive / 3000 > miss_correct / 3000, (miss_naive, miss_correct)
    assert miss_correct / 3000 <= ALPHA + 3.0 * math.sqrt(ALPHA * (1 - ALPHA) / 3000)
