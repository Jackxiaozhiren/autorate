"""Task #72 item 3, measured: the ordinal set gate publishes NOTHING where the ordinal bound certifies.

This is the contrast G3 asks for, stated at the width the measurement supports and no wider. On the committed
ordinal population, at the rubric the freeze owns, `certify_score` -- this repository's multiclass set gate for
ordered labels, whose certified sets are *intervals* -- refuses with `empty_feasible_set` and publishes no
bound of any kind, while `certify_severity` certifies the one-sided statement `P(Y > ahat(X)) <= alpha` with a
measured held-out violation rate and a stated price. So the set gate is silent here in a specific, named
direction: it has nothing to say about the risk of reporting too low, because it says nothing at all.

What this file does NOT claim, and what would be an over-reading of these rows: that a set gate could never
express a one-sided bound. For an interval `C(X) = [lo, hi]`, `P(Y > hi(X)) <= alpha` follows from the set
gate's own coverage claim, so the general proposition is open -- and answerable rather than blocked. The four
variants this row walks all refuse, but a search of the generator's own knobs found `certify_score` certifying
in 4 of 64 populations, all of them the perfectly-calibrated corner where `shift = 0` and `error_rate = 0`
(measured in the plan ledger's R-245 and recorded in `docs/ERRATA.md`). Settling G3 means counting the
one-sided risk on one of those and asking whether any published field of the set certificate bounds it. That
count has not been done, so neither this file nor the README claims it has.

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
from autorate.ordinal import interval_set
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


def test_where_the_set_gate_certifies_coverage_also_bounds_the_interval_top_rule_at_a_price():
    """The measured narrowing of G3's wording, and the one quantity the set certificate does not carry.

    `shift = 0, error_rate = 0` is the corner of this generator where `certify_score` does certify (measured: 4
    of the 64 knob cells, R-245). On the 600 evaluation RECORDS the severity artefact itself names -- 200 cases,
    three repeats each -- the interval's top endpoint reports above the gold level in none of them, so
    `P(Y > hi(X)) = 0` sits inside the set certificate's published marginal bound of 0.014867. That is the
    finding against the claim: for an ORDINAL interval set, a coverage statement plus the top endpoint IS a
    one-sided bound, and the bare words "multiclass CP cannot express a one-sided ordinal guarantee" are false
    for it.

    What the set certificate does not state is the cost of taking that rule. It moves the reported level above
    the model's own modal level on a large fraction of the non-empty cases, and on 36 records the certified set
    is empty, so the interval has no top to report at all -- and neither fact appears in any field of the
    certificate it just certified. The severity certificate publishes both, as claims at the same `delta`. So
    the honest difference between the artefacts is: a one-sided bound that must be read off a rule nobody
    certified and whose abstentions are uncounted, versus a bound on the rule the artefact names, with its
    override rate and its abstention price stated beside it. Narrower than the criterion's original wording,
    and written here so that wording cannot drift back out.
    """
    rows = build_ordinal(n=1200, seed=5, shift=0.0, error_rate=0.0, temp=1.4)
    score, sev = _pair(rows)
    assert score.feasible, score.summary()
    ev_ids = set(sev.meta["eval_ids"])
    ev = [r for r in rows if r.id in ev_ids]
    # `eval_ids` names RECORDS and `n_eval_cases` counts CASES: three repeats of one case are one observation
    # for the guarantee, so the two are not the same denominator and the row says which is which rather than
    # asserting a flat equality that the first run measured false.
    assert len(ev) == len(ev_ids), (len(ev), len(ev_ids))
    assert len({r.case_id for r in ev}) == sev.meta["n_eval_cases"], (
        len({r.case_id for r in ev}), sev.meta["n_eval_cases"])

    empty = above_modal = over_hi = 0
    for r in ev:
        C = interval_set(r.probs, score.qhat)
        modal = max(range(len(r.probs)), key=lambda i: r.probs[i])
        if not C:
            empty += 1
            continue
        over_hi += r.gold_index > C[-1]
        above_modal += C[-1] != modal
    n = len(ev)
    # the bound holds, and is what a reader could only derive themselves...
    assert over_hi / n <= score.marginal_error_bound, (over_hi, n, score.marginal_error_bound)
    # ...because the set certificate publishes no rule and no price for one.
    assert not hasattr(score, "price_bound") and not hasattr(score, "override_bound")
    assert empty and above_modal, (empty, above_modal)
    assert sev.price_bound is not None and sev.override_bound is not None, sev.summary()
