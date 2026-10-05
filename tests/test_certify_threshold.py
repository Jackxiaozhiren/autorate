"""The threshold gate, and the case arithmetic both certifiers share."""
import dataclasses

import pytest

from autorate.case_count import count_outcome
from autorate.certificate import Reason
from autorate.certify_choice import certify_choice
from autorate.certify_threshold import certify_threshold, sweep_thresholds
from autorate.records import Record


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
    1.0000), lambda >= 0.45 automates zero cases. No budget below 1.0 selects anything,
    so varying `beta` cannot move lambda. Here correctness varies BY CASE, which is what
    "confidence separated so a threshold exists" has to mean once the case is the unit
    (ledger R-36/R-44).
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
    d = count_outcome(recs, lambda r: "auto" if r.scores["confidence"] >= 0.9 else "refuse")
    assert d["n_cases"] == len({r.case_id for r in recs})
    assert d["automated"] == sum(1 for r in recs if r.scores["confidence"] >= 0.9)
    # The rule is per-case, not per-record: one failing record in a case refuses it all.
    assert d["automated_cases"] < d["n_cases"], d
    # Exhaustiveness: every case is automated or refused, and the counts add up.
    assert d["automated_cases"] + d["refused_cases"] == d["n_cases"], d
    assert d["erroneous_cases"] <= d["automated_cases"], d


def test_the_two_certifiers_count_the_same_split_the_same_way():
    # R-34: one rule, one counter. If either certifier re-implements the buckets, this
    # is the test that says so.
    recs = _mixed(300)
    set_cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=3)
    thr_cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05,
                                 seed=3)
    for key in ("n_eval_cases", "automated_cases", "erroneous_cases", "n_cal_cases"):
        assert set_cert.meta[key] == thr_cert.meta[key], (key, set_cert.meta[key],
                                                          thr_cert.meta[key])


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
    # to close. The mapping is the set certifier's job, not the counter's silence.
    recs = _mixed(6)
    with pytest.raises(ValueError, match="escalate"):
        count_outcome(recs, lambda r: "escalate")


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

    Not a re-derivation of any number: every assertion here is a relation that must hold for
    whatever the rule decides, so it says the counting is well-formed rather than pinning a
    figure that `verify` already owns. It runs on the committed archive's own evaluation halves
    across the diagnostic grid, because the synthetic fixtures cannot reach a case whose repeats
    disagree, which is exactly the shape the per-case rule exists to handle.
    """
    import json
    from pathlib import Path as _P

    from autorate.certify_choice import DIAGNOSTIC_GRID, _set_rule, split_cal
    from autorate.records import Record

    rows = [Record.from_dict(json.loads(l))
            for l in _P("data/records_feishu.jsonl").read_text().splitlines()]
    checked = 0
    for backend in ("laya", "jev"):
        sub = [r for r in rows if r.backend == backend and r.qtype == "choice" and r.calibratable]
        cal, ev, _ = split_cal(sub, 7)
        assert len(cal) >= 60 and len(ev) >= 60, (backend, len(cal), len(ev))
        for q in DIAGNOSTIC_GRID:
            o = count_outcome(ev, *_set_rule(q, "aps"))
            checked += 1
            assert o["automated"] + o["empties"] + o["multi_label"] == len(ev), o
            assert o["automated"] + o["refused"] == len(ev), o
            assert o["automated_cases"] + o["refused_cases"] == o["n_cases"], o
            assert o["erroneous_cases"] <= o["automated_cases"], o
            assert o["errors"] <= o["automated"], o
            assert 1.0 <= o["mean_measure"] <= 3.0, o
            # A case with any non-automated record cannot be automated: the per-case rule is the
            # reason the case count is never above the record count divided by the repeat factor.
            assert o["automated_cases"] <= o["n_cases"], o
    assert checked == 58, checked


def test_a_missing_score_is_refused_by_the_rule_rather_than_read_as_zero():
    # A record that carries no value for the field is not a record whose value is 0.0. Reading it
    # as one would let an absent field decide the automation rate -- the blank-label mistake this
    # project already refuses inside a quantile. Asserted at the rule, not only through the
    # certificate, because the two records differ in nothing else and the rule is where the
    # distinction lives.
    from autorate.certify_threshold import _rule

    zero = _rec(0, "b", "zs", (0.5, 0.3, 0.2), 0, 0, 0.0)
    blank = _rec(1, "b", "bs", (0.5, 0.3, 0.2), 0, 0, 0.0)
    blank = dataclasses.replace(blank, scores={})
    kind, measure = _rule("confidence", 0.0)
    assert kind(zero) == "auto" and kind(blank) == "refuse", (kind(zero), kind(blank))
    assert measure(zero) == 1.0 and measure(blank) == 0.0
    obs = count_outcome([zero, blank], kind, measure)
    assert obs["automated"] == 1 and obs["refused"] == 1, obs

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
