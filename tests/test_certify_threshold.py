"""The threshold gate, and the case arithmetic both certifiers share."""
import dataclasses
import importlib
import json
import math

import pytest

from autorate.case_count import count_outcome
from autorate.certificate import CANONICALISED_BOUND_FIELDS, Certificate, Reason, canonicalise_bound
from autorate.certify_choice import certify_choice
from autorate.certify_threshold import certify_threshold, sweep_thresholds
from autorate.records import Record
from autorate.tails import bound_width, clopper_pearson_upper

# The score field the committed archive's choice rows actually carry. `confidence` is not one of them
# (the rows carry `act_probability` and `reported_confidence`), so every corpus-present threshold
# number in this file is measured on the field the corpus really has.
_ARCHIVE_FIELD = "reported_confidence"


def _rec(i, backend, case, probs, gold, predicted, conf, seed=0):
    keys = tuple("abc"[:len(probs)])
    # `case_id` is the field `case_key` reads; `meta.request_sha256` is provenance only.
    # Setting the latter and not the former would make every repeat its own case and the
    # grouping assertions below pass for the wrong reason.
    return Record(id="%s-%d" % (case, i), qtype="choice", backend=backend, repeat=i,
                  options=keys, probs=probs, gold=keys[gold], predicted=keys[predicted],
                  slices={"family": "f%d" % (i % 4)}, scores={"confidence": conf},
                  seed=seed, u=0.0, meta={"request_sha256": case}, case_id=case)


def _mixed(n=200, seed=7):
    """Half right, half wrong, with confidence separated so a threshold exists.

    `seed` is the split seed the certifiers are called with, not a draw: the fixture is
    deterministic by construction, and a seeded shuffle here would make the published
    counts of these tests depend on a stream nobody can audit.
    """
    out = []
    for i in range(n):
        ok = i % 2 == 0
        conf = 0.95 if ok else 0.40
        gold, pred = (0, 0) if ok else (0, 1)
        out.append(_rec(i % 3, "b", "case-%03d" % (i // 3),
                        (conf, 1 - conf, 0.0), gold, pred, conf, seed))
    return out


def _tiers():
    """Confidence tiers whose CASE-level error rate rises as the threshold falls.

    The plan's `_mixed` cannot express a moving operating point, and this was measured
    rather than assumed: its cases are three CONSECUTIVE record indices, so every case
    holds both a right and a wrong request, and a rule that automates a case only when
    every record in it automates has exactly two operating points on it -- lambda <= 0.40
    automates all 50 calibration cases and all 50 carry an error (case-level upper bound
    1.0000), lambda >= 0.41 automates 75 records but ZERO cases, so it makes no case-level
    claim to test at all. Selection is tested at the case denominator (item 4), so nothing
    on that grid can meet any budget in (0,1) -- measured: beta=0.999999 still selects
    nothing, and no value of `beta` moves lambda.

    What the comment used to claim, and what the record-level unit actually did: before
    item 4 the same sweep passed the budget on records (lambda=0.95: 0 errors over 75
    records, bound 0.0392 <= beta for any beta >= 0.04) and was refused two lines later on
    the case unit it publishes, and lambda=0.40 was selected only at beta >= 0.5700. That
    is the unit mix this round removes, and the reason the sentence above now says what the
    selector does instead of what the downstream refusal did.

    Here correctness varies BY CASE, which is what "confidence separated so a threshold
    exists" has to mean once the case is the unit (ledger R-36/R-44).
    """
    spec = ((0.95, 160, None), (0.80, 96, 6), (0.55, 96, 2))
    out = []
    for conf, n_cases, wrong_every in spec:
        for c in range(n_cases):
            case = "tier%g-%03d" % (conf, c)
            wrong = wrong_every is not None and c % wrong_every == 0
            gold, pred = (0, 1) if wrong else (0, 0)
            for rep in range(3):
                out.append(_rec(rep, "b", case, (conf, round(1.0 - conf, 4), 0.0),
                                gold, pred, conf))
    return out


def _flip(record, **kw):
    """A copy of a record with its answer or its label changed; identity untouched."""
    return dataclasses.replace(record, **kw)


def test_count_outcome_automates_a_case_only_when_every_record_in_it_automates():
    recs = _mixed(6)
    recs += [_rec(0, "b", "extra", (0.9, 0.1, 0.0), 0, 0, 0.95)]
    # R-66: one callable, one verdict per record. The rule names what it did AND the label it
    # submits when it automates; the counter compares that label to gold and guesses nothing.
    d = count_outcome(recs, lambda r: ("auto", r.predicted, r.scores["confidence"])
                      if r.scores["confidence"] >= 0.9 else ("refuse", None, r.scores["confidence"]))
    assert d["n_cases"] == len({r.case_id for r in recs})
    assert d["automated"] == sum(1 for r in recs if r.scores["confidence"] >= 0.9)
    # Errors are exactly the automated records whose submitted label is not the gold one.
    assert d["errors"] == sum(1 for r in recs if r.scores["confidence"] >= 0.9
                              and r.predicted != r.gold), d
    # The rule is per-case, not per-record: one failing record in a case refuses it all.
    assert d["automated_cases"] < d["n_cases"], d
    # Exhaustiveness: every case is automated or refused, and the counts add up. (The
    # `refused_cases` sum below is arithmetically forced -- case_count derives it as
    # `n_cases - automated_cases` -- so it is kept as a naming check, and the per-case RULE that
    # makes it mean anything is guarded by the assert two lines above and by tests/test_gate.py.)
    assert d["automated_cases"] + d["refused_cases"] == d["n_cases"], d
    assert d["erroneous_cases"] <= d["automated_cases"], d


def _wedge():
    """Data on which BOTH gates automate at least one case -- and disagree about which.

    Three tiers, three records per case, at seed 3 (measured on this module's own code):

    * 160 `sharp` cases at (0.97, 0.02, 0.01), confidence 0.97, correct: a singleton APS set, and
      above any lambda the selector can pick, so both gates automate them.
    * 40 `tie` cases at (0.45, 0.45, 0.10), confidence 0.45, correct: the two tied labels enter the
      certified set together (`aps_score` is the mass STRICTLY above, so both score 0), so the set
      gate escalates them while `score >= 0.45` automates them. This is the wedge spec 6.4 is about.
    * 60 `low` cases at (0.20, 0.70, 0.10), confidence 0.20, answered WRONG: below lambda, so the
      threshold refuses them, and multi-label, so the set gate escalates them too. They keep
      lambda off 0.20 without putting an automated error anywhere.

    Both certificates come back feasible. The set gate automates 75 of the 130 evaluation cases and
    escalates 165 records; the threshold selects lambda=0.45 and automates 102 of the 130 cases,
    refusing 84 records.
    """
    recs = []
    for c in range(160):
        for rep in range(3):
            recs.append(_rec(rep, "b", "sharp-%03d" % c, (0.97, 0.02, 0.01), 0, 0, 0.97))
    for c in range(40):
        for rep in range(3):
            recs.append(_rec(rep, "b", "tie-%03d" % c, (0.45, 0.45, 0.10), 0, 0, 0.45))
    for c in range(60):
        for rep in range(3):
            recs.append(_rec(rep, "b", "low-%03d" % c, (0.20, 0.70, 0.10), 0, 1, 0.20))
    return recs


def test_the_two_certifiers_count_the_same_split_the_same_way():
    # R-34: one rule, one counter. The two gates apply DIFFERENT rules, so the figures that are
    # supposed to agree are the ones the shared arithmetic owns -- the case partition and its
    # sizes -- and the figures that are supposed to DIFFER are the rule's own: which buckets a
    # refusal lands in, and what the mean means. Measured on 5e7630d this test ran on `_mixed(300)`,
    # where both gates automate NOTHING, so `0 == 0` on two of its four keys and the other two were
    # the split, which is shared by construction: a pin with no teeth.
    from autorate.case_count import case_key
    from autorate.certify_choice import split_cal

    recs = _wedge()
    _cal, ev, _d = split_cal(recs, 3)
    set_cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=3)
    thr_cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert set_cert.feasible is True, set_cert.summary()
    assert thr_cert.feasible is True, thr_cert.summary()
    # Both rules run: neither certificate is the empty comparison the old fixture was.
    assert set_cert.meta["automated_cases"] > 0 and thr_cert.meta["automated_cases"] > 0
    # The partition the counter owns is the same partition, and it is the archive's own rule.
    for key in ("n_eval_cases", "n_cal_cases", "cal_ids", "eval_ids", "total_labelled"):
        assert set_cert.meta[key] == thr_cert.meta[key], (key, set_cert.meta[key],
                                                          thr_cert.meta[key])
    assert set_cert.meta["n_eval_cases"] == len({case_key(r) for r in ev}), "not one counter"
    assert set_cert.n_cal + set_cert.n_eval == set_cert.meta["total_labelled"] == \
        thr_cert.meta["total_labelled"], (set_cert.n_cal, set_cert.n_eval, set_cert.meta)
    # Two different rules on the same cases must give two different answers, or the fixture is
    # the old 0 == 0 comparison wearing new shoes.
    assert set_cert.meta["automated_cases"] != thr_cert.meta["automated_cases"], (
        set_cert.meta["automated_cases"], thr_cert.meta["automated_cases"])
    assert thr_cert.meta["automated_cases"] > set_cert.meta["automated_cases"], (
        "the threshold automates the tied cases the set gate escalates: that is spec 6.4's wedge")
    # Each gate's buckets are exhaustive over the same n_eval, in ITS OWN refusal vocabulary.
    assert set_cert.meta["automated"] + set_cert.meta["empties"] + set_cert.meta["multi_label"] \
        == set_cert.n_eval, set_cert.meta
    assert thr_cert.meta["automated"] + thr_cert.meta["refused"] == thr_cert.n_eval, thr_cert.meta
    # The set gate names empties/multi_label and never `refused`; the threshold names `refused` and
    # never empties/multi_label -- its non-automating decision is neither an empty set nor a
    # multi-label one, and writing it into either bucket would put a false figure on a certificate.
    assert {"empties", "multi_label"} <= set(set_cert.meta) and "refused" not in set_cert.meta
    assert "refused" in thr_cert.meta and not ({"empties", "multi_label"} & set(thr_cert.meta))
    assert set_cert.meta["multi_label"] > 0 and thr_cert.meta["refused"] > 0, (
        set_cert.meta, thr_cert.meta)
    # One mean per gate, in the unit that gate's rule produces: labels for the set, scores for the
    # threshold. `mean_set_size` is the set gate's only name for it (it publishes no meta key);
    # `mean_score` is the threshold gate's name for the value in the same shape slot.
    assert set_cert.mean_set_size > 1.0 and "mean_score" not in set_cert.meta, set_cert.meta
    assert 0.0 <= thr_cert.meta["mean_score"] <= 1.0, thr_cert.meta
    assert thr_cert.meta["mean_score"] == thr_cert.mean_set_size, thr_cert.meta


def test_lambda_is_chosen_on_the_calibration_half_and_never_moves_on_the_eval_half():
    # R-28 restated for this gate: a threshold tuned to the evaluation numbers is not a
    # calibrated rule, it is the answer dressed as a method.
    recs = _tiers()
    a = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.20, seed=3)
    b = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert a.qhat != b.qhat, "the budget must actually move the operating point"
    assert a.autorate > b.autorate, (a.autorate, b.autorate)


def test_alpha_does_not_move_the_threshold_gate_at_all():
    # The other half of R-54, and it is a SEPARATE test on purpose. Both arms used to live in the
    # test above, and a planted `beta` -> `alpha` in the selector reddened only the first assert,
    # so the alpha arm never executed: one-sided in the sense that matters. Split, the same plant
    # reddens both tests independently -- which is the only way either one says anything.
    #
    # At the published rubric alpha == beta == 0.05, so an implementation that gated on the wrong
    # symbol would be indistinguishable from the right one under a test that only varied alpha;
    # the test above varies beta and this one proves alpha is inert.
    recs = _tiers()
    b = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    c = certify_threshold(recs, score_field="confidence", alpha=0.20, beta=0.05, seed=3)
    assert c.qhat == b.qhat, (c.qhat, b.qhat)
    assert c.autorate == b.autorate, (c.autorate, b.autorate)
    assert c.conditional_error_bound == b.conditional_error_bound
    # `alpha` is still recorded, because a certificate that drops a handed-in rubric field is
    # silently re-interpreting it (spec 10).
    assert c.alpha == 0.20 and b.alpha == 0.05, (c.alpha, b.alpha)


def test_the_operating_point_ignores_everything_the_evaluation_half_says():
    # The other half of the name above, and the one the beta/alpha arms cannot reach:
    # make the evaluation half PREFER a looser rule -- every high-confidence case wrong,
    # every low-confidence case right. A selector that looked at the held-out half would
    # move lambda to 0.55 and automate nearly everything; one that obeys R-28 does not
    # blink, because the calibration half it selects on was not touched.
    recs = _tiers()
    base = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    ev_ids = set(base.meta["eval_ids"])
    mutated = []
    for r in recs:
        if r.id not in ev_ids:
            mutated.append(r)
        elif r.scores["confidence"] >= 0.80:
            mutated.append(_flip(r, predicted="b"))
        else:
            mutated.append(_flip(r, gold="b"))
    moved = certify_threshold(mutated, score_field="confidence", alpha=0.05, beta=0.05,
                              seed=3)
    assert moved.meta["n_eval_cases"] == base.meta["n_eval_cases"], (
        "the mutation must not re-roll the seeded split")
    assert moved.meta["erroneous_cases"] != base.meta["erroneous_cases"], (
        "the evaluation half the selector is being tempted by must actually have changed")
    # Corrected expectation, in the same lines that carry it. This asserted `moved.qhat ==
    # base.qhat == 0.95`, and it cannot hold: making every high-confidence evaluation case wrong
    # is exactly the data that must REFUSE, and `Certificate.refused` carries `qhat=None` because a
    # feasible certificate is required to carry one -- so a refusal reporting a qhat would be
    # certifying a rule it declined. The selected operating point survives the refusal in
    # meta["lambda"], which is the number this test is about, and the refusal itself is the proof
    # that the held-out half was never consulted to pick it.
    assert moved.meta["lambda"] == base.qhat == 0.95, (moved.meta.get("lambda"), base.qhat)
    assert moved.feasible is False, moved.summary()
    # And the rule the mutated evaluation half would have preferred is the looser one, which is
    # what a selector that looked there would have chosen: 0.55 automates more of that half.
    preferred = max(sweep_thresholds(mutated, "confidence", grid=(0.55, 0.80, 0.95)),
                    key=lambda r: r["automated"])
    assert preferred["lambda"] == 0.55, preferred
    assert moved.meta["lambda"] != preferred["lambda"], (
        "the gate selected the evaluation half's preference, which is R-28's defect")


def test_the_marginal_risk_of_an_automated_error_is_monotone_in_lambda():
    # §6.1/§6.4's precondition, and exactly what the naive weighted loss violated.
    from autorate.certify_threshold import sweep_thresholds
    recs = _mixed(300)
    rows = sweep_thresholds(recs, "confidence", grid=(0.0, 0.3, 0.6, 0.9, 0.99))
    marg = [r["marginal_errors"] for r in rows]
    assert marg == sorted(marg, reverse=True), marg
    assert [r["automated"] for r in rows] == sorted([r["automated"] for r in rows],
                                                    reverse=True), rows


def test_a_field_that_is_constant_cannot_be_certified_and_says_which_failure_it_is():
    # Half wrong, half right, every record at confidence 0.5. The brief's version named
    # `predicted` the gold answer for all 200 records, which is data a gate can certify
    # (measured: 100 calibration cases, zero errors, case bound 0.0295 <= 0.05, feasible)
    # -- so the assertion it was written to protect could not be reached at all.
    recs = [_rec(i % 3, "b", "c%d" % i, (0.6, 0.3, 0.1), 0, i % 2, 0.5) for i in range(200)]
    # Structural, not wording: a constant field collapses the grid to two distinct operating
    # points, so the failure is a property of the data and no phrasing choice can satisfy it.
    from autorate.certify_threshold import sweep_thresholds
    rows = sweep_thresholds(recs, "confidence", grid=(0.0, 0.3, 0.6, 0.9, 0.99))
    assert len({r["automated"] for r in rows}) == 2, rows
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05)
    assert cert.feasible is False
    # By symbol, not by literal: Task 5 splits this label in two (PF-B1-2), and an
    # assertion naming the enum member is one the rename can find.
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    # The closest-to-meeting point is recorded, not invented: this is the artefact that makes the
    # refusal auditable, so assert its shape rather than a sentence inside it.
    assert cert.meta.get("closest_attempt"), cert.meta


def test_an_unknown_score_field_is_a_usage_error_not_a_silent_zero():
    with pytest.raises(ValueError, match="confidence"):
        certify_threshold(_mixed(6), score_field="nope")


def test_the_shared_counter_will_not_invent_a_bucket_for_a_rule_it_does_not_know():
    # `classify_set` spells its multi-label outcome "escalate". If the counter folded an
    # unknown kind into any bucket -- or into none -- a published `multi_label` would stop
    # describing the rule the gate applied, which is the R-34 defect this extraction exists
    # to close. The mapping is the set certifier's job (`_SET_KINDS`), not the counter's silence.
    recs = _mixed(6)
    with pytest.raises(ValueError, match="escalate"):
        count_outcome(recs, lambda r: ("escalate", None, None))


def test_each_certifier_names_its_own_mean_and_the_shape_reuse_is_disclosed():
    # R-53: the shared arithmetic returns `mean_measure` and never names a published
    # figure. The certificate SHAPE, though, has one mean slot (`mean_set_size`) and it is
    # not this task's to widen, so a threshold certificate carries its mean score there and
    # must say so -- a slot whose label does not match its contents is the founding defect.
    recs = _tiers()
    thr = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert thr.feasible is True, thr.summary()
    assert thr.meta["mean_score"] == thr.mean_set_size
    assert "mean_set_size" not in thr.meta, thr.meta
    assert any("mean_set_size" in line and "score" in line for line in thr.envelope), (
        thr.envelope)
    set_cert = certify_choice(_mixed(300), alpha=0.05, beta=0.05, seed=3)
    assert "mean_score" not in set_cert.meta, set_cert.meta


def test_the_shared_counter_keeps_its_buckets_exhaustive_on_the_real_archive():
    """The published `meta` is a partition, and a partition can be checked rather than trusted.

    Not a re-derivation of any number: every assertion below is a relation that must hold for
    whatever the rule decides, so it says the counting is well-formed rather than pinning a figure
    `verify` already owns. It runs on the committed archive's own evaluation halves, across the
    diagnostic grid read on ITS OWN AXIS: `DIAGNOSTIC_GRID` holds coverage levels (alphas), which
    `certify_choice.py:234` feeds to `split_quantile`, and this sweep does the same.

    Measured, and this is why the rewrite matters: the previous version passed those alphas to
    `_set_rule` as QHATS, so every one of its 58 applications landed on the same operating point --
    2 distinct outcome states across the whole test (one per backend), `mean_measure` pinned at
    exactly 1.0 on the lower edge of its own asserted band, and `automated_cases == n_cases` at
    every application, which made the per-case rule the docstring says the archive exists to reach
    inert for the entire test. On the alpha axis the same halves give 56 applications (0.01 is
    vacuous for both backends and is skipped, as the gate skips it) over 10 distinct outcome
    states, with laya's automated records rising 3 -> 33 as alpha rises and its mean set size
    spanning 1.875 -> 3.75 labels.
    """
    import json
    from pathlib import Path as _P

    from autorate.certify_choice import DIAGNOSTIC_GRID, _scores, _set_rule, split_cal
    from autorate.conformal import split_quantile
    from autorate.records import Record

    rows = [Record.from_dict(json.loads(l))
            for l in _P("data/records_feishu.jsonl").read_text().splitlines()]
    applications = 0
    signatures = set()
    per_case_rule_bites = 0
    for backend in ("laya", "jev"):
        sub = [r for r in rows if r.backend == backend and r.qtype == "choice" and r.calibratable]
        cal, ev, _ = split_cal(sub, 7)
        assert len(cal) >= 60 and len(ev) >= 60, (backend, len(cal), len(ev))
        cal_scores = _scores(cal, "aps")
        max_options = max(len(r.options) for r in ev)
        automated_over_alpha = []
        for a in DIAGNOSTIC_GRID:
            qhat, vacuous = split_quantile(cal_scores, a)
            if vacuous:
                continue
            o = count_outcome(ev, _set_rule(qhat, "aps"))
            applications += 1
            assert o["automated"] + o["empties"] + o["multi_label"] == len(ev), o
            assert o["automated"] + o["refused"] == len(ev), o
            # The two refusal vocabularies name one bucket: `empties + multi_label` IS `refused`.
            assert o["empties"] + o["multi_label"] == o["refused"], o
            assert o["automated_cases"] + o["refused_cases"] == o["n_cases"], o
            assert o["erroneous_cases"] <= o["automated_cases"], o
            assert o["errors"] <= o["automated"], o
            # A mean of SET SIZES, over every evaluated record: at least one label per record that
            # automates or escalates, at most every option -- and the band is the data's own, not
            # the 3.0 the old single-operating-point sweep sat underneath.
            assert 1.0 <= o["mean_measure"] <= max_options, (o["mean_measure"], max_options)
            # The relation that MOVES with alpha: a looser coverage floor certifies smaller sets,
            # so automation cannot fall as alpha rises. Held per backend, and asserted to be a
            # range rather than a constant below.
            automated_over_alpha.append(o["automated"])
            if o["automated_cases"] < o["n_cases"]:
                per_case_rule_bites += 1
            signatures.add((backend, o["automated"], o["empties"], o["multi_label"],
                            o["automated_cases"], o["erroneous_cases"],
                            round(o["mean_measure"], 9)))
        assert automated_over_alpha == sorted(automated_over_alpha), (backend, automated_over_alpha)
    assert len({s[1] for s in signatures}) > 1, "the sweep measures one state again"
    assert applications == 56, applications
    assert len(signatures) == 10, sorted(signatures)
    # And the shape the per-case rule exists for, which the old axis never reached: on the archive
    # some cases have repeats whose certified sets disagree, so one record refuses the whole case
    # and `automated_cases < n_cases`. Measured: 28 of the 56 applications -- every one of laya's,
    # none of jev's, whose three repeats per case carry byte-identical probability vectors and so
    # always automate as a whole.
    assert per_case_rule_bites == 28, per_case_rule_bites


def test_a_missing_score_is_refused_by_the_rule_rather_than_read_as_zero():
    # A record that carries no value for the field is not a record whose value is 0.0. Reading it
    # as one would let an absent field decide the automation rate -- the blank-label mistake this
    # project already refuses inside a quantile. Asserted at the rule, not only through the
    # certificate, because the two records differ in nothing else and the rule is where the
    # distinction lives.
    from autorate.certify_threshold import _rule

    zero = _rec(0, "b", "zs", (0.5, 0.3, 0.2), 0, 0, 0.0)
    one = _rec(1, "b", "os", (0.5, 0.3, 0.2), 0, 0, 1.0)
    blank = _rec(2, "b", "bs", (0.5, 0.3, 0.2), 0, 0, 0.0)
    blank = dataclasses.replace(blank, scores={})
    decide = _rule("confidence", 0.0)
    assert decide(zero).outcome == "auto" and decide(blank).outcome == "refuse", decide(zero)
    # R-66's verdict carries the label the rule submits, and the score it measures. A record with
    # no value measures NOTHING (`measure=None`), not zero: item 2's mean is over the records that
    # carry a value, so a blank cannot drag the average toward 0.
    assert decide(zero).submitted == "a" and decide(zero).measure == 0.0, decide(zero)
    assert decide(blank).submitted is None and decide(blank).measure is None, decide(blank)
    obs = count_outcome([zero, blank], decide)
    assert obs["automated"] == 1 and obs["refused"] == 1, obs
    both = count_outcome([zero, one, blank], decide)
    assert both["mean_measure"] == 0.5, both
    assert both["mean_measure"] != 1.0 / 3.0, "the blank was counted as a zero-width denominator"

    # End to end: blind the tier the gate selects, and the refusal reports how many records had no
    # value rather than automating the ones that did. Measured at seed 3 -- the fixture is 352 cases
    # over 1056 records, split 528/528, and 255 of the EVALUATION records carry nothing once the 0.95
    # tier is blanked. No operating point is ever selected, so `lambda` is absent from the meta
    # instead of being a number the gate never chose; `missing_score` is a count over the evaluation
    # half, which is why its denominator is asserted beside it.
    blinded = [dataclasses.replace(r, scores={}) if r.scores["confidence"] >= 0.95 else r
               for r in _tiers()]
    cert = certify_threshold(blinded, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert cert.feasible is False, cert.summary()
    assert cert.n_eval == 528 and cert.meta["missing_score"] == 255, (cert.n_eval,
                                                                      cert.meta["missing_score"])
    assert "lambda" not in cert.meta, cert.meta


def _archive_rows(backend):
    """The committed archive's calibratable choice rows for one backend."""
    import json
    from pathlib import Path as _P

    from autorate.records import Record

    rows = [Record.from_dict(json.loads(l))
            for l in _P("data/records_feishu.jsonl").read_text().splitlines()]
    return [r for r in rows if r.backend == backend and r.qtype == "choice" and r.calibratable]


def _field_values(recs, field):
    """Every value `field` carries, one entry per RECORD that carries it (no id collapse)."""
    found = []
    for r in recs:
        value = (r.scores or {}).get(field)
        if value is not None:
            found.append(float(value))
    return found


def test_the_candidate_grid_is_the_calibration_half_s_own_values():
    # Item 1 / R-28's missing arm: the operating point may only be chosen from values the
    # calibration half itself carries. The archive reuses ids (1919 rows / 320 ids; 383 choice
    # rows / 64 ids), so an `{record.id: value}` map is neither the calibration population nor a
    # multiset -- it silently keeps one repeat per id and it lets held-out values into the grid.
    # Measured on 5e7630d at the published seed 7 with the field the archive actually carries:
    # the gate's 16-point jev grid held 7 values the calibration half never carries and the
    # selected lambda was 0.84, one of them; the calibration half's own neighbours are
    # 0.87, 0.89, 0.90. laya's 63-point grid held 31.
    from autorate.certify_choice import split_cal

    for backend in ("laya", "jev"):
        sub = _archive_rows(backend)
        cal, ev, _ = split_cal(sub, 7)
        cal_values = set(_field_values(cal, _ARCHIVE_FIELD))
        ev_values = set(_field_values(ev, _ARCHIVE_FIELD))
        # The instrument must be able to fail: repeats of one id carry DIFFERENT values here,
        # and the held-out half does carry values the calibration half never does.
        assert ev_values - cal_values, (backend, "the two arms of the leak are indistinguishable")
        assert len({r.id for r in cal}) < len(cal), (backend, "no id reuse: the dict would be inert")
        cert = certify_threshold(sub, score_field=_ARCHIVE_FIELD, seed=7)
        assert set(cert.meta["lambda_grid"]) == cal_values, (
            backend, "the grid is not the calibration half's own values",
            sorted(set(cert.meta["lambda_grid"]) - cal_values))
        if cert.meta.get("lambda") is not None:
            assert cert.meta["lambda"] in cal_values, (
                backend, cert.meta["lambda"], "published an operating point the calibration "
                "half never carried")
        assert cert.meta["missing_score"] == len(ev) - len(_field_values(ev, _ARCHIVE_FIELD)), backend
    # A caller-supplied grid is used verbatim, and still without consulting the evaluation half.
    pinned = certify_threshold(_archive_rows("jev"), score_field=_ARCHIVE_FIELD, seed=7,
                               grid=(0.5, 0.93))
    assert pinned.meta["lambda_grid"] == [0.5, 0.93], pinned.meta["lambda_grid"]


def test_the_value_collection_is_per_record_not_per_id():
    # Item 1's second half: `missing_score` and the "does anyone carry this field" check count
    # RECORDS, so they need per-record presence. A map keyed by id reports one carrier where
    # three records carry, and reports a field absent where its surviving value was overwritten.
    from autorate.certify_threshold import _values_of

    a = _rec(0, "b", "case-x", (0.6, 0.3, 0.1), 0, 0, 0.9)
    same_id_other_value = dataclasses.replace(a, case_id="case-y", scores={"confidence": 0.4})
    same_id_same_value = dataclasses.replace(a, case_id="case-z")
    blank = dataclasses.replace(a, case_id="case-w", scores={})
    assert _values_of([a, same_id_other_value, blank], "confidence") == [0.9, 0.4]
    assert _values_of([blank], "confidence") == []
    # Three repeats carrying the SAME value are three carriers: a set would report one, and
    # `missing_score` is `len(half) - carriers`, so a collapsed count invents missing values.
    assert _values_of([a, same_id_same_value, dataclasses.replace(a, case_id="case-v")],
                      "confidence") == [0.9, 0.9, 0.9]


def _ties():
    """Two operating points that automate the SAME cases and DIFFERENT numbers of records.

    200 cases of three records at 0.99, every one of them correct, and 60 cases whose records are
    {0.92, 0.92, 0.30} -- also all correct, so no point on the grid differs in ERRORS and the only
    thing that can separate them is the unit they are counted in. At lambda in {0.90, 0.92} the
    0.92 records of a `lo` case automate while its 0.30 record does not, so the case does not
    automate: 107 calibration cases and 367 calibration records. At {0.95, 0.99} the same 107 cases
    automate off 321 records. Measured on 5e7630d: the selector took 0.92, because its key put the
    RECORD count ahead of lambda; R-62 and the docstring above it say the tie goes to the higher
    lambda, which is 0.99.
    """
    recs = []
    for c in range(200):
        for rep in range(3):
            recs.append(_rec(rep, "b", "hi-%03d" % c, (0.99, 0.01, 0.0), 0, 0, 0.99))
    for c in range(60):
        for rep, conf in enumerate((0.92, 0.92, 0.30)):
            recs.append(_rec(rep, "b", "lo-%03d" % c, (conf, round(1.0 - conf, 4), 0.0), 0, 0, conf))
    return recs


_TIE_GRID = (0.90, 0.92, 0.95, 0.99)


def test_a_tie_in_cases_breaks_to_the_higher_lambda_not_to_the_looser_rule():
    # Item 3 / R-62: the promise is the number of CASES automated, so the record count must not
    # outrank lambda. Measured on 5e7630d: this fixture selected 0.92 (367 calibration records)
    # where the stated rule gives 0.99 (321 records), and inverting the tie-break outright left
    # all 283 tests green -- the one genuinely new decision in the task had no owner in the suite.
    from autorate.certify_choice import split_cal

    recs = _ties()
    cal, _ev, _d = split_cal(recs, 3)
    rows = {r["lambda"]: r for r in sweep_thresholds(cal, "confidence", grid=_TIE_GRID)}
    # The tie must really be a tie in cases and a difference in records, or the assertion below
    # is decoration: 107 cases everywhere, 367 records at {0.90, 0.92} and 321 at {0.95, 0.99}.
    assert len({r["automated_cases"] for r in rows.values()}) == 1, rows
    assert rows[0.90]["automated_cases"] == rows[0.99]["automated_cases"], rows
    assert rows[0.92]["automated"] > rows[0.99]["automated"], rows
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3,
                             grid=_TIE_GRID)
    assert cert.feasible is True, cert.summary()
    assert cert.meta["lambda"] == 0.99, cert.meta["lambda"]
    # The record share stays auditable beside the choice, as the smaller claim it now is.
    assert cert.meta["cal_automated"] == rows[0.99]["automated"] < rows[0.92]["automated"], cert.meta


def _unit_mix():
    """A population on which the RECORD denominator is strictly looser than the CASE one.

    80 cases of three CORRECT records at 0.95 plus 40 cases of three WRONG records at 0.90. Every
    repeat of a case carries the same verdict, so a wrong case contributes exactly three wrong
    records: the two rates are equal (54/180 = 18/60 = 0.30) while the record count is 3x the case
    count, and an exact Clopper-Pearson upper bound tightens with n. Measured on 5e7630d at seed 3:
    0.361174 on records against 0.411737 on cases, so beta = 0.38 admits the loose lambda on the
    unit nothing else in this module uses and rejects it on the unit everything published uses.
    """
    recs = []
    for c in range(80):
        for rep in range(3):
            recs.append(_rec(rep, "b", "A-%03d" % c, (0.95, 0.05, 0.0), 0, 0, 0.95))
    for c in range(40):
        for rep in range(3):
            recs.append(_rec(rep, "b", "B-%03d" % c, (0.90, 0.10, 0.0), 0, 1, 0.90))
    return recs


def test_the_selection_budget_is_tested_at_the_case_denominator_it_publishes():
    # Item 4: one unit for one budget. Selection used to test the RECORD-level bound while every
    # figure the certificate publishes is at the CASE level, so a lambda could satisfy beta on a
    # unit the certificate never names and be refused two lines later on the unit it does.
    #
    # The bound comparisons below are against `canonicalise_bound(raw)`, not against `raw`: since
    # R-121 the gate publishes the canonical ceiling of the inversion, and the selector decides on
    # that same number, so the expectation is restated at the precision the artefact stores. That is
    # not a widened comparison -- each is still a single exact `==`, and
    # `test_the_threshold_gate_publishes_only_bounds_another_libc_can_write` pins the difference
    # between the two forms, so a producer that stopped canonicalising cannot pass here quietly.
    from autorate.certify_choice import split_cal
    from autorate.certify_threshold import _rule, _select_lambda
    from autorate.tails import clopper_pearson_upper

    cal, _ev, _d = split_cal(_unit_mix(), 3)
    obs = count_outcome(cal, _rule("confidence", 0.90))
    rec_bound = clopper_pearson_upper(obs["errors"], obs["automated"], 0.05)
    case_bound = clopper_pearson_upper(obs["erroneous_cases"], obs["automated_cases"], 0.05)
    assert rec_bound < 0.38 < case_bound, (rec_bound, case_bound)
    strict = count_outcome(cal, _rule("confidence", 0.95))
    strict_case_bound = clopper_pearson_upper(strict["erroneous_cases"],
                                              strict["automated_cases"], 0.05)
    chosen = _select_lambda(cal, "confidence", [0.90, 0.95], 0.38, 0.05)
    assert chosen[0] == 0.95, "selection still tests the budget on records: %r" % (chosen[0],)
    assert chosen[2] == canonicalise_bound(strict_case_bound), (chosen[2], strict_case_bound)

    cert = certify_threshold(_unit_mix(), score_field="confidence", alpha=0.05, beta=0.38,
                             seed=3, grid=(0.90, 0.95))
    assert cert.feasible is True, cert.summary()
    assert cert.meta["lambda"] == 0.95, cert.meta["lambda"]
    assert cert.meta["cal_conditional_error_bound"] == canonicalise_bound(
        strict_case_bound), cert.meta
    assert cert.conditional_error_bound == canonicalise_bound(clopper_pearson_upper(
        cert.meta["erroneous_cases"], cert.meta["automated_cases"], 0.05))


def test_a_threshold_diagnostic_row_names_the_unit_of_every_bound_it_carries():
    # Item 4's other half: inside this module `conditional_error_bound` means the CASE-level bound
    # -- the set gate's record-level `closest_attempt` is ledger #37 and Task 6's regeneration, and
    # is deliberately not touched here. The record-level bound stays where it is worth keeping, and
    # it is named for what it is. Both are read at the published precision (R-121): the row carries
    # TWO transcendentals, and a sweep by field name is what rounds both while leaving the two
    # quotient columns alone.
    from autorate.certify_choice import split_cal
    from autorate.certify_threshold import _rule
    from autorate.tails import clopper_pearson_upper

    recs = _unit_mix()
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3,
                             grid=(0.90, 0.95))
    assert cert.feasible is False and cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.summary()
    _cal, ev, _d = split_cal(recs, 3)
    row = cert.meta["closest_attempt"]
    obs = count_outcome(ev, _rule("confidence", row["lambda"]))
    assert row["conditional_error_bound"] == canonicalise_bound(clopper_pearson_upper(
        obs["erroneous_cases"], obs["automated_cases"], 0.05)), row
    assert row["record_conditional_error_bound"] == canonicalise_bound(clopper_pearson_upper(
        obs["errors"], obs["automated"], 0.05)), row
    assert cert.meta["diagnostic_curve"], cert.meta
    assert set(cert.meta["diagnostic_curve"][0]) >= {
        "conditional_error_bound", "record_conditional_error_bound"}, cert.meta["diagnostic_curve"][0]


def test_a_batch_spanning_two_backends_is_a_usage_error_not_a_nameless_certificate():
    # Item 5: the module docstring has always promised `ValueError` for a batch that spans more
    # than one `backend`, and the code answered by setting `backend=None` and certifying anyway.
    # A certificate that names no subject cannot be paired (`cli.py` refuses it, `gate.py:46-57`
    # treats it as authorising nothing), so a mixed batch used to come back as an artifact whose
    # own deployment refuses to act on it. `cli.py` maps ValueError to exit 2, so the documented
    # exit-code surface is unchanged.
    mixed = _wedge()
    renamed = [dataclasses.replace(r, backend="other" if r.id.startswith("low") else r.backend)
               for r in mixed]
    with pytest.raises(ValueError, match="other"):
        certify_threshold(renamed, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    # One subject, stated. The message names both backends it found, which is the only way a
    # reader can tell a typo from a genuine mixed corpus.
    with pytest.raises(ValueError, match="b"):
        certify_threshold(renamed, score_field="confidence", seed=3)


def test_the_threshold_certificate_publishes_the_seed_the_rubric_is_read_from():
    # Item 5's second half. `cli.RUBRIC_FIELDS` reads the seed out of `meta` (`cli.py:144`,
    # `_rubric`), and the set gate has always published it there (`certify_choice.py:144`) while
    # the threshold gate published nothing: measured on 5e7630d, `autorate compare <set> <threshold>`
    # printed `seed (cert_choice.json=3, cert_threshold.json=None)` and exited 2 on the very
    # contrast spec 6.4 requires. The refusal path also used to gain a bare `beta` key the
    # feasible path never had.
    recs = _wedge()
    seed = 3
    thr = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=seed)
    assert thr.feasible is True, thr.summary()
    assert thr.meta["seed"] == seed, thr.meta
    assert thr.meta["alpha"] == 0.05 and thr.meta["beta"] == 0.05, thr.meta
    # Same keys on a refusal, so a reader never has to know which path produced the artifact.
    blinded = [dataclasses.replace(r, scores={}) if r.scores["confidence"] >= 0.95 else r
               for r in _tiers()]
    refused = certify_threshold(blinded, score_field="confidence", seed=seed)
    assert refused.feasible is False, refused.summary()
    assert refused.meta["seed"] == seed, refused.meta


def test_a_threshold_certificate_pairs_with_a_set_certificate_on_the_same_records():
    # Spec 6.4's contrast is a PAIRING, so `compare`'s rubric check has to be able to see the two
    # gates as the same rubric. `method` is the one field that is meant to disagree -- a threshold
    # certificate that reported "aps" would be recording a rule it never ran -- and it is the only
    # one that does. Ledger note for the controller: record that the `method` disagreement between
    # the two gates is intended, so Task 4's audit does not route the gate contrast through
    # `compare`'s rubric check.
    from autorate.cli import RUBRIC_FIELDS, _rubric

    recs = _wedge()
    set_cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=3)
    thr_cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    left, right = _rubric(set_cert), _rubric(thr_cert)
    assert set(RUBRIC_FIELDS) == {"alpha", "beta", "delta", "method", "seed"}, RUBRIC_FIELDS
    assert left["seed"] == right["seed"] == 3, (left, right)
    assert left["alpha"] == right["alpha"] and left["beta"] == right["beta"]
    assert left["delta"] == right["delta"]
    assert {f for f in RUBRIC_FIELDS if left[f] != right[f]} == {"method"}, (left, right)


def test_the_set_gate_counts_the_label_its_singleton_delivers_not_the_record_s_prediction():
    # R-66. `gate.py:66-67` delivers `record.options[C[0]]` -- the label inside the certified
    # singleton -- and the old shared counter read `record.predicted` (falling back to argmax).
    # Those agree on all 383 archived choice records (`predicted == argmax` everywhere, measured),
    # which is why nothing went red on the corpus; agreement by coincidence of the data is not
    # ownership. Both directions are pinned here, including the one that LOWERS a published bound.
    from autorate.certify_choice import _set_rule
    from autorate.tails import clopper_pearson_upper

    # A1: the singleton certifies 'a' (correct) while the record's own `predicted` says 'b'.
    a1 = _rec(0, "b", "a1", (0.9, 0.05, 0.05), 0, 1, 0.9)
    o1 = count_outcome([a1], _set_rule(0.3, "aps"))
    assert o1["automated"] == 1 and o1["automated_cases"] == 1, o1
    assert o1["errors"] == 0 and o1["erroneous_cases"] == 0, (o1, "counted the prediction, not the set")
    # A2: the singleton certifies 'b' (wrong) while `predicted` says 'a'. Reading the prediction
    # here hides an automated error and loosens the bound beside it: 1.0000 becomes 0.9500.
    a2 = _rec(0, "b", "a2", (0.4, 0.55, 0.05), 0, 0, 0.4)
    o2 = count_outcome([a2], _set_rule(0.3, "aps"))
    assert o2["automated"] == 1 and o2["automated_cases"] == 1, o2
    assert o2["errors"] == 1 and o2["erroneous_cases"] == 1, (o2, "counted the prediction, not the set")
    assert clopper_pearson_upper(o2["erroneous_cases"], o2["automated_cases"], 0.05) == \
        clopper_pearson_upper(1, 1, 0.05) == 1.0
    assert clopper_pearson_upper(0, 1, 0.05) == 0.95, "the direction the old reading took"


def test_a_rule_that_automates_must_name_the_label_it_submits():
    # R-66's contract, policed: the counter compares the rule's OWN submitted label to gold and
    # guesses nothing. A verdict that says "auto" while naming no label is a rule the counter does
    # not know how to score, and reading it as right (or as wrong) would put a bound on a decision
    # nobody described.
    from autorate import case_count

    rec = _rec(0, "b", "no-sub", (0.9, 0.05, 0.05), 0, 0, 0.9)
    with pytest.raises(ValueError, match="submits"):
        count_outcome([rec], lambda r: ("auto", None, None))
    # An unknown outcome name is still refused rather than filed in a bucket of the counter's own.
    with pytest.raises(ValueError, match="escalate"):
        count_outcome([rec], lambda r: ("escalate", "a", None))
    # The answer the counter used to compute for itself is gone, so no rule can inherit a guess.
    assert not hasattr(case_count, "decision_is_wrong"), "the counter still decides what a rule submits"


def test_the_threshold_gate_submits_the_answer_the_record_states():
    # The threshold rule automates the deployment's own answer: `records.py:74-77` names `predicted`
    # "what the automated decision would BE", and a record that states none answers with its largest
    # probability -- the only label it has to put forward. That reading is this rule's to declare,
    # not the shared counter's to assume.
    from autorate.certify_threshold import _rule

    stated = _rec(0, "b", "stated", (0.6, 0.3, 0.1), 0, 1, 0.9)      # says 'b', gold 'a'
    silent = dataclasses.replace(stated, case_id="silent", id="silent-0", predicted=None)
    decide = _rule("confidence", 0.5)
    assert decide(stated)[0] == "auto" and decide(stated)[1] == "b", decide(stated)
    assert decide(silent)[0] == "auto" and decide(silent)[1] == "a", decide(silent)
    assert count_outcome([stated], decide)["errors"] == 1
    assert count_outcome([silent], decide)["errors"] == 0


def test_mean_score_is_a_mean_of_scores_not_the_automation_share_under_another_name():
    # Item 2: the old `measure` returned 1.0/0.0 for passing/failing the threshold, so the published
    # "mean score" was the RECORD-level automation share -- a figure the certificate already carries
    # as `automated` over `n_eval`, and a label that did not match the number beside it.
    # Measured on 5e7630d, `_tiers()` at seed 3: mean_score = 0.48295454545454547 = 255/528 exactly,
    # while the mean of the field over the same half is 0.8127840909090909.
    recs = _tiers()
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert cert.feasible is True, cert.summary()
    from autorate.certify_choice import split_cal
    _cal, ev, _d = split_cal(recs, 3)
    carrying = _field_values(ev, "confidence")
    share = cert.meta["automated"] / cert.n_eval
    assert cert.meta["mean_score"] != share, (cert.meta["mean_score"], share)
    exact = math.fsum(carrying) / len(carrying)
    # The tolerance here is about float ACCUMULATION ORDER, not about the claim: the counter keeps
    # a running total while `fsum` is exact, and over these 528 records the two differ in the last
    # bits (429.15000000000197 against 429.15). The defect this test exists for -- a mean published
    # as the automation share -- is 0.483 against 0.813, and the line above asserts that apart
    # EXACTLY.
    assert cert.meta["mean_score"] == pytest.approx(exact, rel=1e-12), (
        cert.meta["mean_score"], exact)
    # The denominator is stated where the mean is published: records that carry the field, with the
    # count of those that carry nothing named beside it.
    assert len(carrying) == cert.n_eval - cert.meta["missing_score"], cert.meta
    # The set gate's mean is still a mean of SET SIZES over every evaluated record -- the shared
    # counter must not quietly narrow that denominator now that a measure may be absent.
    from autorate.conformal import conformal_set
    set_cert = certify_choice(recs, alpha=0.05, beta=0.30, seed=3)
    _c2, ev2, _d2 = split_cal(recs, 3)
    assert set_cert.mean_set_size == sum(len(conformal_set(r.probs, set_cert.qhat, r.u, "aps"))
                                         for r in ev2) / len(ev2), set_cert.mean_set_size


def test_a_threshold_certificate_summary_states_its_own_rule_budget_and_mean():
    # Item 6. A feasible threshold certificate used to print the SET gate's headline over its own
    # numbers: "at coverage 0.950", "refusal (empty or multi-label set)" and "mean set size 0.48",
    # three sentences on an artifact whose envelope line one says "this is the threshold gate of
    # spec 6.4, not the APS set gate" and whose alpha arm says the coverage level is not used.
    # `summary()` is the text `autorate certify`, `compare` and `verify` all print, so the
    # contradiction was in the sentence every consumer reads.
    recs = _tiers()
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert cert.feasible is True, cert.summary()
    said = cert.summary()
    for set_phrase in ("coverage", "empty or multi-label", "mean set size", "refusal (empty"):
        assert set_phrase not in said, said
    assert "confidence >= 0.950000" in said, said
    assert "beta=0.050" in said and "mean score 0.8128" in said, said
    assert "conditional error <= %.3f" % cert.conditional_error_bound in said, said
    assert "autorate %.3f" % cert.autorate in said, said
    # The set gate's wording is not this task's to reflow: `verify` compares a stored certificate's
    # summary byte for byte and tests/test_certify_choice.py:171 quotes the same clause.
    set_cert = certify_choice(recs, alpha=0.05, beta=0.30, seed=3)
    assert set_cert.feasible is True, set_cert.summary()
    assert "at coverage 0.950 (alpha=0.050), beta=0.300" in set_cert.summary()
    assert "refusal (empty or multi-label set)" in set_cert.summary()
    assert "mean set size %.2f" % set_cert.mean_set_size in set_cert.summary()
    # A refusal keeps naming its reason whichever gate produced it.
    blinded = [dataclasses.replace(r, scores={}) if r.scores["confidence"] >= 0.95 else r
               for r in _tiers()]
    refused = certify_threshold(blinded, score_field="confidence", seed=3)
    assert refused.summary().startswith("NOT_CERTIFIABLE: reason=empty_feasible_set"), refused.summary()


def test_the_archive_error_criterion_is_the_label_the_singleton_delivers():
    # Item 8's residue in the suite. The MOVE was re-measured after R-66 over the archive's own
    # halves -- both backends, split_cal seeds 0..11, both methods, all 29 diagnostic points:
    # 1344 applications (the grid's 0.01 is vacuous on both backends and is skipped, as the gate
    # skips it), 0 disagreements on the eight shared keys, max absolute difference 0.0e+00, and
    # the new dict carries exactly `refused` and `refused_cases` beyond them. That sweep needs the
    # pre-extraction `_outcome`, which lives in git and not in the tree, so what the suite can own
    # is the criterion the sweep proved equivalent: `errors` counts the automated records whose
    # singleton label -- `options[C[0]]`, exactly what `gate.py:66-67` delivers -- is not the gold
    # answer. Re-derived here the way the deployment reads it, not the way the counter stores it.
    import json
    from pathlib import Path as _P

    from autorate.certify_choice import _scores, _set_rule, split_cal
    from autorate.conformal import conformal_set, split_quantile
    from autorate.records import Record

    rows = [Record.from_dict(json.loads(l))
            for l in _P("data/records_feishu.jsonl").read_text().splitlines()]
    rederived = 0
    for backend in ("laya", "jev"):
        sub = [r for r in rows if r.backend == backend and r.qtype == "choice" and r.calibratable]
        cal, ev, _ = split_cal(sub, 7)
        cal_scores = _scores(cal, "aps")
        for a in (0.02, 0.05, 0.11, 0.20, 0.29):
            qhat, vacuous = split_quantile(cal_scores, a)
            assert vacuous is False, (backend, a)
            o = count_outcome(ev, _set_rule(qhat, "aps"))
            rederived += 1
            delivered = [(conformal_set(r.probs, qhat, r.u, "aps")) for r in ev]
            singles = [C for C in delivered if len(C) == 1]
            expected_errors = sum(1 for r, C in zip(ev, delivered)
                                  if len(C) == 1 and r.options[C[0]] != r.gold)
            assert o["automated"] == len(singles), (backend, a, o["automated"], len(singles))
            assert o["errors"] == expected_errors, (backend, a, o["errors"], expected_errors)
            assert o["multi_label"] == sum(1 for C in delivered if len(C) > 1), (backend, a)
            assert o["empties"] == sum(1 for C in delivered if not C), (backend, a)
    assert rederived == 10, rederived


# --- R-121 at THIS gate's producers: the precision a published bound is stored at --------------
#
# `float-canonical-b` fixed the choice gate and reported, as its concern 3, that three modules still
# wrote raw transcendentals into published numbers. Two of them are this file's module and
# `tests/test_audit.py`; the third is another lane's fence. The exposure is the same one the runner
# printed twice: `clopper_pearson_upper` inverts a binomial tail through ~80 `math.log`/`math.exp`
# comparisons and `bound_width` is one `math.log`, and the last bits of those are not the same
# between Apple libm and glibc (~4e-16 at 0.79, ~9000 ULPs wide there).
#
# No threshold certificate is committed under `data/` yet and `cli.cmd_verify` re-derives only the
# set gate's two artefacts, so there is no shipped `verify` arm to point the guard pair at. The
# comparison used instead is `verify`'s OWN: the same `CERT_COMPARE_FIELDS` list, the same exact
# `==`, the same `recomputed %r, published %r` message shape -- applied to the certificate this
# module derives, taken across a JSON round trip so the two sides are stored-versus-re-derived and
# not one value compared with itself. That is the claim that actually matters here, because it is
# the claim a foreign libc breaks: the number a Mac wrote is the number Linux re-derives.


def _stored(cert):
    """The certificate as an artefact holds it: serialised, then read back."""
    return Certificate.from_dict(json.loads(cert.to_json()))


def _published_diff(stored, fresh) -> list:
    """Every field `verify` compares that the two sides disagree on, named the way it names them."""
    from autorate.cli import CERT_COMPARE_FIELDS

    failures = []
    for field in CERT_COMPARE_FIELDS:
        got, published = getattr(fresh, field), getattr(stored, field)
        if got != published:
            failures.append("cert threshold.%s: recomputed %r, published %r"
                            % (field, got, published))
    if fresh.summary() != stored.summary():
        failures.append("cert threshold.summary: recomputed %r, published %r"
                        % (fresh.summary(), stored.summary()))
    return failures


def _drift_the_transcendentals(monkeypatch, move):
    """Make this gate's bound producers answer as the other C library did, and record the calls.

    Both producers move, because both are published: `clopper_pearson_upper` feeds the two headline
    bounds, the calibration bound and every curve row, and `bound_width` feeds the half-width that
    sets `autorate_ci`. The module object is fetched by name -- `importlib.import_module` -- so the
    patch lands on the module the certifier reads rather than on a re-exported function.
    """
    calls = []

    def drifting_cp(k, n, delta):
        raw = clopper_pearson_upper(k, n, delta)
        moved = move(raw)
        calls.append(("clopper_pearson_upper", k, n, raw, moved))
        return moved

    def drifting_width(n, alpha=0.05):
        raw = bound_width(n, alpha)
        moved = move(raw)
        calls.append(("bound_width", n, None, raw, moved))
        return moved

    module = importlib.import_module("autorate.certify_threshold")
    monkeypatch.setattr(module, "clopper_pearson_upper", drifting_cp)
    monkeypatch.setattr(module, "bound_width", drifting_width)
    return calls


def _one_ulp(raw, direction):
    """One unit in the last place up or down -- the size of the drift R-121 measured.

    A bound of exactly 1.0 is left alone: the bisection brackets [0, 1], so 1.0 is the bracket's own
    endpoint and not an answer `math.exp` produced, and no two libms disagree about it.
    """
    return raw if raw >= 1.0 else math.nextafter(raw, direction)


def _gate_certificates():
    """One feasible certificate and one refusal, so both publishing paths are under the drift.

    The refusal is the half that matters most and the one a comparison-only fix would miss: its
    `meta.diagnostic_curve` and `closest_attempt` carry TWO bounds per row -- case-level and
    record-level -- and its `detail` sentence quotes a bound, so a raw double anywhere in that dict
    is a published number the other platform cannot write.
    """
    feasible = certify_threshold(_unit_mix(), score_field="confidence", alpha=0.05, beta=0.38,
                                 seed=3, grid=(0.90, 0.95))
    refusal = certify_threshold(_unit_mix(), score_field="confidence", alpha=0.05, beta=0.05,
                                seed=3, grid=(0.90, 0.95))
    assert feasible.feasible is True, feasible.summary()
    assert refusal.feasible is False, refusal.summary()
    assert refusal.meta["diagnostic_curve"], "the refusal publishes no sweep to drift"
    return feasible, refusal


def test_the_threshold_gate_publishes_only_bounds_another_libc_can_write():
    """Content guard: every bound-named published number is its own canonical value.

    This is the artefact-side half of the fix, stated where the fix was applied. It walks the
    serialised certificate -- the bytes a machine would commit -- and asks of every value stored
    under one of `_BOUND_FIELDS` that `canonicalise_bound(value) == value`, which is the property a
    raw transcendental does not have. It then asks the opposite question of the row's NON-bound
    floats, because R-121's fix is a sweep by field name and not a pass over floats: if this gate
    had rounded `observed_conditional_error` too, the gate would have become the blanket tolerance
    the report forbids, and this is the assertion that would notice.
    """
    from autorate.certify_threshold import _BOUND_FIELDS

    assert CANONICALISED_BOUND_FIELDS == ("conditional_error_bound", "marginal_error_bound")
    assert set(CANONICALISED_BOUND_FIELDS) < set(_BOUND_FIELDS), _BOUND_FIELDS
    bounds = quotients = 0
    for cert in _gate_certificates():
        doc = json.loads(cert.to_json())
        stack = [doc]
        seen = []
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in _BOUND_FIELDS:
                        seen.append((key, value))
                    else:
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)
        named = [(k, v) for k, v in seen if v is not None]
        assert [c for c in CANONICALISED_BOUND_FIELDS if any(k == c for k, _ in named)], named
        for key, value in named:
            assert canonicalise_bound(value) == value, (key, repr(value))
            assert len(repr(value).split(".")[-1]) <= 12, (key, repr(value))
            bounds += 1
        ratios = [(k, v) for k, v in (doc["meta"].get("diagnostic_curve") or [{}])[0].items()
                  if isinstance(v, float) and k not in _BOUND_FIELDS]
        if not doc["feasible"]:
            # Only a refusal sweeps, so only a refusal carries the curve rows and their ratios.
            assert {k for k, _ in ratios} >= {
                "observed_automation_rate", "observed_conditional_error"}, ratios
        quotients += len(ratios)
    assert bounds >= 6, "the two certificates no longer publish this many bounds: %d" % bounds
    # Three non-bound floats on the surface this guard walks: the row's `lambda` (a record value,
    # not a computed one) and the two ratio columns. Fewer would mean the refusal stopped sweeping.
    assert quotients >= 3, quotients


def test_a_rederivation_of_a_threshold_certificate_absorbs_a_last_bit_libm_drift(monkeypatch):
    """Guard pair (a): a platform difference in the 16th decimal is not drift, both directions.

    The assertions after the comparison are what keep the green honest, and they are the same three
    the choice lane's pair makes: the instrument must have been reached, the move must really be one
    ULP, and every drifted value must canonicalise back to the number it was canonicalised from.
    Without them the gate would be green because nothing arrived.
    """
    feasible, refusal = _gate_certificates()
    stored = (_stored(feasible), _stored(refusal))
    # The control: the same comparison over the undrifted re-derivation is already clean.
    for published, side in zip(stored, _gate_certificates()):
        assert _published_diff(published, side) == []

    for direction in (math.inf, 0.0):
        calls = _drift_the_transcendentals(monkeypatch,
                                           lambda raw, d=direction: _one_ulp(raw, d))
        drifted = (_published_diff(published, fresh)
                   for published, fresh in zip(stored, _gate_certificates()))
        diffs = [list(d) for d in drifted]
        assert calls, "the producers were never asked for a bound or a width"
        assert [c for c in calls if c[0] == "bound_width"], "the interval width was never derived"
        moved_apart = [(raw, moved) for _, _, _, raw, moved in calls if moved != raw]
        assert moved_apart, "a one-ULP drift moved nothing: the instrument is blind"
        assert all(abs(moved - raw) < 1e-15 for raw, moved in moved_apart), moved_apart[:3]
        assert all(canonicalise_bound(moved) == canonicalise_bound(raw)
                   for _, _, _, raw, moved in calls), \
            [repr((raw, moved)) for raw, moved in moved_apart
             if canonicalise_bound(moved) != canonicalise_bound(raw)][:3]
        assert diffs == [[], []], (direction, diffs)
        monkeypatch.undo()


def test_a_threshold_bound_that_moves_in_the_tenth_decimal_reds_naming_the_field(monkeypatch):
    """Guard pair (b): a bound that actually MOVED is still drift, and is named by field.

    Same instrument, same fields, same exact comparison as the green guard two orders of magnitude
    further along the number, so the pair differs only in the size of the move -- which is precisely
    the claim `PUBLISHED_DECIMALS` makes. Absorbing 4e-16 is a fix and not a blinder only if 1e-10
    still turns this red.
    """
    feasible, refusal = _gate_certificates()
    stored = (_stored(feasible), _stored(refusal))
    calls = _drift_the_transcendentals(monkeypatch, lambda raw: raw + 1e-10)
    diffs = [_published_diff(published, fresh)
             for published, fresh in zip(stored, _gate_certificates())]
    assert calls and all(moved != raw for _, _, _, raw, moved in calls)
    headline, sweep = diffs
    assert headline, "a 1e-10 move on the feasible certificate re-derives the same number"
    assert any(f.startswith("cert threshold.conditional_error_bound:") for f in headline), headline
    assert any(f.startswith("cert threshold.meta:") for f in headline), headline
    assert any(f.startswith("cert threshold.marginal_error_bound:") for f in headline), headline
    assert sweep, "a 1e-10 move on the refusal's sweep re-derives the same dict"
    assert any(f.startswith("cert threshold.meta:") for f in sweep), sweep
    # both numbers of the disagreement are printed, at the digits that differ
    text = "\n".join(headline + sweep)
    assert "recomputed" in text and "published" in text, text[:400]
    assert repr(feasible.conditional_error_bound) in text, text[:400]
    moved = canonicalise_bound(feasible.conditional_error_bound + 1e-10)
    assert moved != feasible.conditional_error_bound, "the planted drift did not take"
    assert repr(moved) in text, text[:400]


def test_a_foreign_libm_writes_the_same_bytes_for_the_same_threshold_certificate(monkeypatch):
    """The artefact surface stops being platform-dependent, not merely the comparison.

    The reference bytes are captured BEFORE any patch is installed -- they are what this machine
    writes with its own libm, and they are what a committed artefact would hold. Re-deriving the
    two certificates with the bound producers answering up to four ULPs away (more than the 4e-16
    actually measured) must then reproduce those bytes character for character. Comparing a drifted
    derivation with itself would be vacuous: both sides would drift together and the assertion
    could never fail, which is exactly the blind guard this repository's falsification round is for.

    A tolerance in a comparison layer cannot make this claim; it would still let two machines write
    two different files, which is the state R-121 was reported in.
    """
    reference = [cert.to_json() for cert in _gate_certificates()]
    for raw_offset in (1, 2, 4):
        def drifting(raw, offset=raw_offset):
            if raw >= 1.0:
                return raw
            moved = raw
            for _ in range(offset):
                moved = math.nextafter(moved, math.inf)
            assert moved - raw < 1e-15, (raw, moved)
            return moved

        calls = _drift_the_transcendentals(monkeypatch, drifting)
        drifted = _gate_certificates()
        # the instrument is live, and it moves the very numbers the artefact stores
        assert calls and any(moved != raw for _, _, _, raw, moved in calls), \
            "the drift was planted and moved nothing"
        for expected, cert in zip(reference, drifted):
            assert cert.to_json() == expected, "the artefact a %d-ULP libm writes differs" % \
                raw_offset
            assert expected == _stored(cert).to_json(), "the artefact does not survive its own format"
        monkeypatch.undo()


def test_the_threshold_gate_leaves_the_quotients_it_publishes_alone():
    """`autorate`, the two `observed_*` ratios and `mean_score` keep the double the records give.

    R-121's argument is that IEEE 754 requires + - * / and sqrt to be correctly rounded, so a
    quotient of two integers is already platform-exact and rounding it would buy nothing while
    costing the gate its ability to see a genuinely changed automation rate. Measured on this
    gate's own feasible certificate and on a refusal's swept row: each of those published floats is
    taken as the records determine it, and the ones the 12-decimal grid does not already hold are
    asserted to still be off-grid -- so a blanket sweep would have changed them, and changed none.
    """
    cert, refusal = _gate_certificates()
    doc = json.loads(cert.to_json())
    curve = (json.loads(refusal.to_json())["meta"].get("diagnostic_curve") or [{}])[0]
    raw_non_bounds = [cert.autorate, cert.mean_set_size, cert.refusal_rate,
                      cert.autorate_ci[0], cert.autorate_ci[1],
                      curve.get("observed_automation_rate"),
                      curve.get("observed_conditional_error")]
    untouched = [v for v in raw_non_bounds if isinstance(v, float)]
    assert len(untouched) == 7, untouched
    assert any(v != canonicalise_bound(v) for v in untouched), untouched
    assert cert.autorate == cert.meta["automated_cases"] / cert.meta["n_eval_cases"], cert.meta
    assert curve, "the refusal row this guard reads no longer exists"
    # The two ratio columns are re-derived here as the plain divisions they are, and compared
    # exactly: a sweep over "every float in the row" would have put them on the 12-decimal grid,
    # and this is the assertion that would then disagree.
    from autorate.certify_choice import split_cal
    from autorate.certify_threshold import _rule

    _cal, ev, _d = split_cal(_unit_mix(), 3)
    obs = count_outcome(ev, _rule("confidence", curve["lambda"]))
    assert curve["observed_automation_rate"] == obs["automated"] / len(ev), curve
    assert curve["observed_conditional_error"] == obs["errors"] / obs["automated"], curve
    for key in ("observed_automation_rate", "observed_conditional_error"):
        assert isinstance(curve[key], float), key
