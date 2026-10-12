"""Task #72 item 3, measured: the ordinal set gate publishes NOTHING where the ordinal bound certifies.

This is the contrast G3 asks for, stated at the width the measurement supports and no wider. On the committed
ordinal population, at the rubric the freeze owns, `certify_score` -- this repository's multiclass set gate for
ordered labels, whose certified sets are *intervals* -- refuses with `empty_feasible_set` and publishes no
bound of any kind, while `certify_severity` certifies the one-sided statement `P(Y > ahat(X)) <= alpha` with a
measured held-out violation rate and a stated price. So the set gate is silent here in a specific, named
direction: it has nothing to say about the risk of reporting too low, because it says nothing at all.

What this file does NOT claim, and what would be an over-reading of these rows: that a set gate could never
express a one-sided bound. For an interval `C(X) = [lo, hi]`, `P(Y > hi(X)) <= alpha` follows from the set
gate's own coverage claim, so the general proposition is open. It stays open in this family because no
population here lets the set gate certify -- the four variants this row walks all refuse -- so the interval-top
construction never acquires a certified `qhat` to bind to. Settling that needs a population where the set gate
certifies, which is recorded as the next step rather than asserted here.

Every number is read from the certificate objects, never typed: a row that quoted `0.045180` would certify a
transcription, not a measurement.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _records import build_ordinal
from autorate import report
from autorate.certify_score import certify_score
from autorate.certificate import ALPHA, BETA, DELTA, SEED
from autorate.severity import certify_severity

# The published population and its live variants. `temp` is not a decoration: rows 2 and 3 below prove the
# statistics move when it moves.
PUBLISHED = dict(n=1200, seed=5, shift=0.1, temp=2.0)
VARIANTS = (PUBLISHED, dict(n=1200, seed=5, shift=0.1, temp=6.0),
            dict(n=1200, seed=5, shift=0.1, temp=12.0), dict(n=1200, seed=5, shift=0.1, temp=0.3))


def _pair(rows):
    return (certify_score(rows, alpha=ALPHA, beta=BETA, delta=DELTA, seed=SEED),
            certify_severity(rows, alpha=ALPHA, delta=DELTA, direction="under", seed=SEED))


def test_the_published_ordinal_population_is_a_refusal_for_the_set_gate_and_a_certificate_for_severity():
    """One population, two gates, two outcomes -- both read from the objects, at the frozen rubric."""
    rows = report.severity_certificates()[report.SEVERITY_LABEL][0]
    assert rows == build_ordinal(**PUBLISHED), "the published records are not this generator's population"

    score, sev = _pair(rows)
    assert not score.feasible, score.summary()
    assert score.reason == "empty_feasible_set", score.reason
    # The refusal publishes nothing: every headline bound is absent, so no field of it bounds any risk.
    for field in ("qhat", "autorate", "conditional_error_bound", "marginal_error_bound", "mean_set_size"):
        assert getattr(score, field) is None, (field, getattr(score, field))
    # The named cause, read out of the certificate rather than restated: the set gate's own budget is what it
    # cannot meet, which is a conditional-error refusal and says nothing about a one-sided level risk.
    detail = score.meta["detail"]
    assert "automated" in detail and "bound" in detail and "budget" in detail, detail

    assert sev.feasible, sev.summary()
    assert sev.bound is not None and sev.bound <= ALPHA, (sev.bound, ALPHA)
    assert sev.measured_violation is not None and sev.measured_violation <= sev.bound, sev.summary()
    # The price of the always-report rule, which is the half of the statement a membership bound cannot carry.
    assert sev.price_bound is not None and sev.override_bound is not None, sev.summary()
    assert sev.ahat is not None


def test_the_contrast_is_not_one_lucky_population_all_four_variants_refuse_the_set_gate():
    """The set gate refuses across every variant, so the silence is a property of this family at this rubric."""
    for kw in VARIANTS:
        score, sev = _pair(build_ordinal(**kw))
        assert not score.feasible and score.reason == "empty_feasible_set", (kw, score.reason)
        assert sev.feasible, (kw, sev.summary())


def test_the_statistics_are_live_not_saturated_everywhere_the_temperature_moves_them():
    """The rows above could be vacuous if the generator ignored `temp`, or if nothing ever moved.

    Measured: the probabilities differ per temperature (so `temp` is consumed, not decorative), the reported
    rule saturates once the ballot is sharp -- temp 2.0/6.0/12.0 give the same certificate -- and a flat
    population (temp 0.3) gives a DIFFERENT bound, a different reported level and a different measured rate.
    A sharp-region invariance is a real property of this generator, and it is the reason the published
    population's envelope should not be read as if `temp` were the binding knob: `shift` and `error_rate` are.
    """
    import hashlib

    digests, bounds = {}, {}
    for kw in VARIANTS:
        rows = build_ordinal(**kw)
        key = kw["temp"]
        digests[key] = hashlib.sha256("".join(repr(r.probs) for r in rows).encode()).hexdigest()
        _score, sev = _pair(rows)
        bounds[key] = (sev.bound, sev.ahat, sev.measured_violation)
    assert len(set(digests.values())) == len(digests), "the generator's `temp` stopped reaching the probabilities"
    assert bounds[2.0] == bounds[6.0] == bounds[12.0], "the sharp region was expected to agree: %s" % (bounds,)
    assert bounds[0.3] != bounds[2.0], (bounds[0.3], bounds[2.0])
    assert bounds[0.3][0] < bounds[2.0][0], (bounds[0.3], bounds[2.0])
