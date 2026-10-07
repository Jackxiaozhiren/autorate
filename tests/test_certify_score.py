"""Task 2 (Plan B2): the ordinal set gate -- the choice gate's shape over the chain family.

Every assertion here is about a number the certificate claims, and the shape is deliberately the one
`tests/test_certify_choice.py` polices, so a reader comparing the two gates compares like with like:
one split rule, one shared counter, one refusal ladder, one evidence-only grid, three claims. What
differs is the SUBJECT (`score` records, not `choice`) and the FAMILY (the modal-anchored chain of
`ordinal.py`, not APS/LAC), and each difference is asserted below rather than left to a comment --
including the one ruling R-92a exists for: the second positional of `interval_set` is the calibration
quantile, and a gate that passed `alpha` there would certify nothing while printing a coverage number.

The record factory is LOCAL to this file, which is the convention that actually holds in this suite
(`tests/test_certify_choice.py` builds its own `_records`, `tests/test_certify_threshold.py` builds its
own `_rec`). Its keyword names are the ones Plan B2 Task 3 documents for
`tests/_records.build_ordinal`, so when that module lands the call sites move without being rewritten;
it is not imported here because it does not exist yet.
"""
import dataclasses
import json
import math
import random

import pytest

from autorate.case_count import KINDS, case_key, count_outcome
from autorate.certificate import N_CLAIMS, Certificate, Reason
from autorate.certify_score import (
    DIAGNOSTIC_GRID,
    METHOD,
    MIN_CAL,
    MIN_EVAL,
    _eligible,
    _outcome,
    _score_rule,
    _scores,
    certify_score,
    split_cal,
)
from autorate.conformal import METHODS, classify_set, split_quantile
from autorate.nonconformity import aps_score
from autorate.ordinal import interval_set, is_contiguous
from autorate.records import Record
from autorate.tails import bound_width, clopper_pearson_upper

ALPHA = 0.05
BETA = 0.05
DELTA = 0.05
K = 5


def _ballot(rng, centre, k, temp, jitter):
    """One ordinal ballot: exponential decay away from `centre`, jittered so scores are not tied.

    The jitter is not decoration. With `jitter=0` every ballot of a given shape is the same ballot,
    the calibration scores collapse onto k distinct values, and the quantile stops being a sample
    statistic at all -- the coverage row of this file would then be asserting the arithmetic of one
    fixed vector. Ruling R-78 puts tie-breaking in the quantile, so the scores have to be distinct
    for a gate's threshold to mean anything.
    """
    w = [math.exp(-temp * abs(j - centre)) * (1.0 + jitter * (rng.random() - 0.5)) for j in range(k)]
    s = sum(w)
    p = [round(x / s, 4) for x in w]
    p[centre] = round(p[centre] + (1.0 - sum(p)), 4)
    return tuple(p)


def build_ordinal(n=1200, seed=1, k=K, shift=0.0, error_rate=0.0, temp=1.4, jitter=0.8, repeats=3,
                  backend="synthetic-ordinal", unlabelled=0):
    """`n` labelled `score` records over ceil(n/repeats) cases. Synthetic, with known answers.

    `shift` is the probability that the reported centre sits one level BELOW the gold level -- a model
    that under-calls severity, which is the failure spec §6.2 is about. `error_rate` overrides it with
    a random displacement of one or two levels in either direction, and is the knob that makes the
    peak wrong at all: a generator that is never wrong cannot be shown refusing an error, which is the
    defect ledger D12 records for the choice gate's first generator.

    `repeats` is what makes the certification unit visible: a case's repeats carry byte-identical
    probabilities and gold, as the committed archive does (laya: three records per case), and only the
    draw `u` differs -- which is also the inertness probe, since the chain family may not read `u`.
    """
    rng = random.Random(seed)
    options = tuple(str(j) for j in range(k))
    out = []
    case = 0
    while len(out) < n:
        cid = "case%04d" % case
        case += 1
        gold = rng.randrange(k)
        centre = gold
        if error_rate and rng.random() < error_rate:
            centre = gold + rng.choice([-2, -1, 1, 2])
        elif rng.random() < shift:
            centre = gold - 1
        centre = max(0, min(k - 1, centre))
        probs = _ballot(rng, centre, k, temp, jitter)
        for rep in range(repeats):
            if len(out) >= n:
                break
            out.append(Record(id="%s.r%d" % (cid, rep), qtype="score", backend=backend, repeat=rep,
                              options=options, probs=probs,
                              gold=None if len(out) < unlabelled else options[gold],
                              predicted=options[centre], case_id=cid, seed=seed, u=rng.random()))
    return out


def _disagreeing_cases(count):
    """`count` two-record cases whose repeats DISAGREE about automating: a peaked record, a flat twin.

    The peaked ballot's modal level carries 0.80 and both neighbours 0.06, so its chain interval is
    the singleton `[2]` for any threshold in `[0.80, 0.86)` -- which is where this file's certified
    qhat sits (measured 0.8094 on the armed population) -- while its gold is that same level, so the
    record automates AND is correct. The flat twin certifies four levels: it refuses. Same `case_id`,
    so the CASE is not automated even though one of its rows was: the case rate and the record rate
    part company, which is the only shape that can tell the two denominators apart. `build_ordinal`
    cannot produce it -- a case's repeats are byte-identical there, on purpose, because that is what
    the committed archive looks like.

    Built as raw `Record`s (not via `build_ordinal`) and with the file's `synthetic-ordinal` backend,
    so adding them neither splits a backend nor asks the generator for a shape it will not emit.
    """
    options = tuple(str(j) for j in range(K))
    peaked = (0.02, 0.06, 0.80, 0.06, 0.06)
    flat = tuple(round(1.0 / K, 4) for _ in range(K))
    out = []
    for i in range(count):
        cid = "dis%04d" % i
        for rep, probs in enumerate((peaked, flat)):
            out.append(Record(id="%s.r%d" % (cid, rep), qtype="score",
                              backend="synthetic-ordinal", repeat=rep, options=options,
                              probs=probs, gold="2", predicted="2", case_id=cid, seed=4,
                              u=0.05 * rep + 0.01))
    return out


def test_the_generator_actually_moves_the_peak_off_gold_when_asked():
    """Guards the vacuity of every error assertion below, exactly as D12 does for the choice gate."""
    clean = build_ordinal(n=600, shift=0.0, repeats=1)
    biased = build_ordinal(n=600, shift=0.5, repeats=1)
    assert sum(r.predicted != r.gold for r in clean) == 0
    wrong = sum(r.predicted != r.gold for r in biased)
    assert 200 < wrong < 400, wrong
    # The displacement is an UNDER-call, not noise: every reported level sits below gold.
    under = sum(int(r.predicted) < int(r.gold) for r in biased if r.predicted != r.gold)
    assert under == wrong, (under, wrong)


def test_repeats_of_one_case_are_one_observation_and_never_sit_in_both_halves():
    """R-36/R-44: the split unit is the case, and a repeat carries no new information."""
    recs = build_ordinal(n=1200, repeats=3)
    assert len(recs) == 1200
    by_case = {}
    for r in recs:
        by_case.setdefault(r.case_id, []).append(r)
    assert len(by_case) == 400
    for group in by_case.values():
        assert len(group) == 3
        assert len({(r.probs, r.gold, r.predicted) for r in group}) == 1, group
        assert len({r.u for r in group}) == 3, "the repeats must stay distinguishable rows"
    cal, ev, _dropped = split_cal(recs, 7)
    assert {case_key(r) for r in cal} & {case_key(r) for r in ev} == set()
    assert len(cal) + len(ev) == 1200


def test_the_split_is_the_choice_gate_s_rule_with_a_different_subject():
    """This gate shares the partition with `certify_choice.split_cal`, and only the partition.

    It cannot CALL that function: its eligibility rule is `qtype == "choice"`, so on score records it
    drops everything and returns two empty halves -- which is also why handing this gate a choice
    population is a usage error rather than a result. The twins below exist only to compare the two
    partitions line by line; no gate runs on them. Without this pin, "shares the split" is a comment,
    and the day one copy drifts the two gates stop describing the same held-out cases while every test
    in each file stays green.

    The population is the one that makes that promise true, and it is not the obvious one. At
    `repeats=1` with ids generated in sorted order, `len(recs) == len(groups)` and insertion order
    equals `sorted` order, so BOTH choice-side drifts this pin exists to watch -- balancing the
    calibration half by CASE count (`len(recs)//2` -> `len(groups)//2`) instead of by record count,
    and dropping the `sorted()` before the seeded shuffle -- left the pin green; that was measured,
    and it is why the R-123 deferral of the `split_cal` merge to B3 Task 2 could not rest on this row.
    `repeats=3` over a REVERSED list makes each drift a different partition: 1200 records over 400
    cases separates the two balance rules by 200 units of `half`, and reversal makes `list(groups)`
    a permutation of `sorted(groups)` rather than a copy of it. The pin stays green against the
    pristine copy -- the mirror really is correct; a pin that could not be satisfied by any two
    agreeing implementations would only prove the assertion is a tautology. GREEN-ON-ARRIVAL
    against the unmutated `certify_choice.split_cal`, and the changes that redden it are named:
    either choice-side drift (balance the half by case count, or drop the `sorted()` -- both
    measured red in the fix report's P-F2a/P-F2b lanes) and the score-side drift the original
    report measured as P6.
    """
    from autorate.certify_choice import split_cal as choice_split_cal

    recs = build_ordinal(n=1200, repeats=3, seed=4)[::-1]
    twins = [dataclasses.replace(r, qtype="choice") for r in recs]
    mine_cal, mine_ev, dropped = split_cal(recs, 9)
    their_cal, their_ev, _ = choice_split_cal(twins, 9)
    assert [r.id for r in mine_cal] == [r.id for r in their_cal]
    assert [r.id for r in mine_ev] == [r.id for r in their_ev]
    assert dropped == {"skipped_no_gold": 0, "skipped_wrong_qtype": 0}


def test_a_clean_ordinal_task_produces_a_number_and_both_bounds():
    recs = build_ordinal(n=1200, seed=1)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    assert cert.method == METHOD == "ordinal"
    assert 0.0 < cert.autorate <= 1.0
    lo, hi = cert.autorate_ci
    assert lo <= cert.autorate <= hi
    assert 0.0 < cert.qhat <= 1.0
    assert cert.conditional_error_bound <= BETA + 1e-9
    assert cert.marginal_error_bound <= cert.conditional_error_bound
    assert cert.n_cal + cert.n_eval == 1200
    assert cert.mean_set_size > 0.0


def test_every_certified_set_is_a_contiguous_chain_and_a_singleton_is_the_modal_level():
    """The family's two properties, asserted on the threshold the certificate publishes.

    Contiguity is why §5.4 exists at all ("urgency is either level 0 or level 4" is not an answer), and
    the singleton clause is a fact about this family rather than a coincidence of the data: every
    non-empty sublevel set contains the mode, so a one-level set IS the modal level. APS gives the
    choice gate no such guarantee, which is why its `_set_rule` has to say which label it submits.
    """
    recs = build_ordinal(n=1200, seed=1)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    _cal, ev, _dropped = split_cal(recs, 7)
    lengths = []
    singletons = empties = 0
    for r in ev:
        C = interval_set(r.probs, cert.qhat)
        assert is_contiguous(C), (r.probs, cert.qhat, C)
        lengths.append(len(C))
        if C:
            mode = max(range(len(r.probs)), key=lambda j: (r.probs[j], -j))
            assert mode in C, (r.probs, cert.qhat, C, mode)
            if len(C) == 1:
                singletons += 1
                assert C[0] == mode, (r.probs, C, mode)
        else:
            empties += 1
    assert singletons > 0, "nothing automates: this row cannot support an automation rate"
    # R-17, on data where it actually bites: an empty certified set is a refusal, and on this shape
    # it is the ONLY way the truth escapes the set -- so the coverage mass and the refusal mass are
    # the same cases, and neither is an error.
    assert empties > 0, "no empty set anywhere: the refusal arm of this rule is unexercised"
    assert cert.meta["empties"] == empties
    assert cert.meta["errors_among_automated"] == 0


def test_the_published_mean_is_the_interval_length_and_has_exactly_one_name():
    """One owner, checked where the leak would actually be: the counter's dict and the serialised cert.

    `count_outcome` publishes `mean_measure` precisely because it does not name a figure; this gate
    renames it. The rename has to be a RENAME -- if the shared name survives alongside the gate's name
    in the returned dict, the next person who splats `observed` into `meta` publishes two names for one
    number, and nothing would notice. So the assertion is on `_outcome`'s own keys and on the
    serialised certificate, not on a meta dict this module builds key by key.
    """
    recs = build_ordinal(n=1200, seed=3)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=11)
    assert cert.feasible is True, cert.summary()
    _cal, ev, _dropped = split_cal(recs, 11)
    obs = _outcome(ev, cert.qhat)
    assert "mean_measure" not in obs, "the shared counter's name was copied, not renamed"
    assert obs["mean_interval_length"] == cert.mean_set_size
    assert cert.meta["mean_interval_length"] == cert.mean_set_size
    assert "mean_measure" not in json.dumps(cert.to_dict()), cert.meta
    rederived = sum(len(interval_set(r.probs, cert.qhat)) for r in ev) / len(ev)
    assert abs(rederived - cert.mean_set_size) < 1e-12, (rederived, cert.mean_set_size)
    # Partial sets, or the mean is describing a degenerate family (the whole ballot, or all singleton).
    assert 1.0 < cert.mean_set_size < K, cert.mean_set_size


def test_alpha_moves_the_operating_point_instead_of_labeling_it():
    """R-28, the rule the set gate was corrected for: `alpha` fixes the set size and nothing else.

    If a grid were swept on the evaluation half this row would produce byte-identical certificates
    under different headings -- coverage 0.89 under a 0.95 heading, which is the failure the choice
    gate's first version published.

    The automation rate is NOT monotone in `alpha`, and this row says so out loud because the opposite
    looks like an obvious assertion and is false: as the threshold falls, doubletons become singletons
    AT THE SAME TIME singletons become empty, and an empty certified set is a refusal. Measured on this
    population (seed 3, 267 evaluation cases, q̂ 0.8348 / 0.813 / 0.7588): 294 / 273 / 445 automated
    records against 24 / 63 / 129 empties. What IS monotone, and is the property the coverage claim
    rests on, is the set -- so that is what is asserted, along with the empties, which do move one way.
    """
    recs = build_ordinal(n=1600, seed=3)
    levels = (0.02, 0.05, 0.20)
    certs = {a: certify_score(recs, alpha=a, beta=BETA, seed=7) for a in levels}
    for a, c in certs.items():
        assert c.feasible is True, (a, c.summary())
        assert c.alpha == a
    assert certs[0.02].qhat > certs[0.05].qhat > certs[0.20].qhat, [c.qhat for c in certs.values()]
    assert "coverage 0.950 (alpha=0.050)" in certs[0.05].summary(), certs[0.05].summary()
    rates = [certs[a].autorate for a in levels]
    assert len(set(rates)) == 3, rates

    # Nesting, on the three thresholds the certificates actually published.
    _cal, ev, _dropped = split_cal(recs, 7)
    for r in ev:
        small = set(interval_set(r.probs, certs[0.20].qhat))
        middle = set(interval_set(r.probs, certs[0.05].qhat))
        large = set(interval_set(r.probs, certs[0.02].qhat))
        assert small <= middle <= large, (r.probs, small, middle, large)
    empties = [certs[a].meta["empties"] for a in levels]
    assert empties == sorted(empties), empties
    automated = [certs[a].meta["automated"] for a in levels]
    # The middle threshold automates FEWER records than both ends: non-monotone, and asserted as a
    # relation rather than smoothed into a tidier claim. Anyone who later "fixes" this row by asking
    # for monotonicity is asking for a property the refusal bucket does not have.
    assert automated[1] < min(automated[0], automated[2]), automated


def test_beta_gates_the_result_and_selects_nothing():
    """The other half of R-28 for this gate: `beta` is a budget, not an operating point.

    `certify_threshold` selects its lambda at `beta`; this gate must not, or its coverage claim would
    be a selected number.
    """
    recs = build_ordinal(n=1600, seed=3)
    certs = {b: certify_score(recs, alpha=ALPHA, beta=b, seed=7) for b in (0.01, 0.05, 0.20)}
    qhats = {c.qhat for c in certs.values() if c.qhat is not None}
    assert len(qhats) == 1 and qhats == {certs[0.05].qhat}, qhats
    assert certs[0.05].feasible and certs[0.20].feasible, {b: c.summary() for b, c in certs.items()}
    # Same threshold, same measured decisions: only the verdict on the budget may differ.
    assert certs[0.05].autorate == certs[0.20].autorate
    assert certs[0.05].conditional_error_bound == certs[0.20].conditional_error_bound
    # Feasibility is monotone in the budget: a point that pays a tight beta pays a loose one.
    assert not certs[0.01].feasible or certs[0.05].feasible
    if not certs[0.01].feasible:
        assert certs[0.01].reason == Reason.EMPTY_FEASIBLE_SET.value, certs[0.01].summary()


def test_the_certified_threshold_is_a_calibration_half_fact_and_nothing_else():
    """q̂ is the alpha-quantile of the calibration scores, and the held-out half has no vote."""
    recs = build_ordinal(n=1200, seed=5)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    cal, ev, _dropped = split_cal(recs, 7)
    assert {r.id for r in ev} == set(cert.meta["eval_ids"])
    assert {r.id for r in cal} == set(cert.meta["cal_ids"])
    q, vacuous = split_quantile(_scores(cal), ALPHA)
    assert vacuous is False and q == cert.qhat

    # The plant: wreck every evaluation ballot. The threshold may not blink, and if this arm changed
    # nothing on the held-out side either, the plant would be inert and so would the line above it.
    # The wrecked certificate is a REFUSAL (a uniform ballot certifies as the whole interval, so
    # nothing is a singleton) and the shape forbids a refusal from carrying a qhat -- which is the
    # point: the number that did not move is the calibration-half quantile, recomputed below from the
    # wrecked population's own calibration half.
    ev_keys = {case_key(r) for r in ev}
    flat = tuple(round(1.0 / K, 4) for _ in range(K))
    wrecked = [r if case_key(r) not in ev_keys else dataclasses.replace(r, probs=flat) for r in recs]
    wreck = certify_score(wrecked, alpha=ALPHA, beta=BETA, seed=7)
    wreck_cal, wreck_ev, _ = split_cal(wrecked, 7)
    assert [r.id for r in wreck_cal] == [r.id for r in cal], "the wreck moved the split"
    assert split_quantile(_scores(wreck_cal), ALPHA)[0] == cert.qhat
    assert wreck.feasible is False and wreck.reason == Reason.EMPTY_FEASIBLE_SET.value, \
        wreck.summary()
    assert wreck.meta["automated"] != cert.meta["automated"], (
        wreck.meta["automated"], cert.meta["automated"])
    assert wreck.meta["n_eval_cases"] == cert.meta["n_eval_cases"], "the split itself moved"


def test_the_bounds_use_the_case_denominator_and_not_the_row_count():
    """One owner for the counting, one unit for the bound: the case (R-34, R-36, R-44)."""
    recs = build_ordinal(n=1200, repeats=3, seed=5)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, delta=DELTA, seed=7)
    assert cert.feasible is True, cert.summary()
    n_case = cert.meta["n_eval_cases"]
    assert n_case < cert.n_eval // 2, (n_case, cert.n_eval)
    _cal, ev, _dropped = split_cal(recs, 7)
    obs = count_outcome(ev, _score_rule(cert.qhat))
    assert obs["n_cases"] == n_case
    assert cert.autorate == obs["automated_cases"] / obs["n_cases"]
    assert cert.conditional_error_bound == clopper_pearson_upper(
        obs["erroneous_cases"], obs["automated_cases"], DELTA)
    assert cert.marginal_error_bound == clopper_pearson_upper(
        obs["erroneous_cases"], obs["n_cases"], DELTA)
    # The CI half-width is the published width at the CASE count, and the row count gives a strictly
    # looser one: without that second line the reader cannot tell which unit was used.
    half = bound_width(n_case, DELTA) / 2.0
    lo, hi = cert.autorate_ci
    assert lo == max(0.0, cert.autorate - half) and hi == min(1.0, cert.autorate + half)
    assert bound_width(cert.n_eval, DELTA) / 2.0 < half

    # The arm above cannot fail on the POINT estimate: every `build_ordinal` case gives its repeats
    # byte-identical records -- that is the archive's shape, and it is deliberate -- so all of a
    # case's records automate together and `automated / n_eval == automated_cases / n_cases` EXACTLY
    # (measured on this population: 282/600 == 94/200 == 0.470000). A published rate computed from
    # the row count instead of the case count therefore passes everything above. The precedent for
    # the discriminating shape is `tests/test_certify_threshold.py`: `_ties()` ("two operating points
    # that automate the SAME cases and DIFFERENT numbers of records") and the archive sweep's
    # `per_case_rule_bites == 28`, which is the same fact read off the committed corpus.
    #
    # So: cases whose repeats DISAGREE. One peaked ballot, whose certified set is the singleton
    # holding its gold level, and a flat twin under the same `case_id`, whose set is four levels.
    # The case is not automated (one of its records refused), while one of its rows was: the unit
    # the per-case rule exists for, which no identical-repeat fixture can reach.
    #
    # GREEN-ON-ARRIVAL against the shipped `rate = auto_case / n_case` -- the shipped arithmetic
    # was never wrong; what was wrong is that nothing here could notice a gate that published the
    # row-count rate. The change that reddens the equality is exactly that drift: `rate = autom
    # / n_ev` (plant P-F1 in the fix report) makes it false. The disagreement assertion before it
    # is the fixture's own anti-inertness guard: it reddens the day the arm stops carrying a case
    # whose repeats part ways -- which is the change that would silently return this row to the
    # 0.470000 == 0.470000 comparison it was before.
    armed = recs + _disagreeing_cases(30)
    arm_cert = certify_score(armed, alpha=ALPHA, beta=BETA, delta=DELTA, seed=7)
    assert arm_cert.feasible is True, arm_cert.summary()
    arm_ev = split_cal(armed, 7)[1]
    arm_obs = count_outcome(arm_ev, _score_rule(arm_cert.qhat))
    outcomes_by_case = {}
    for r in arm_ev:
        if r.case_id.startswith("dis"):
            outcomes_by_case.setdefault(r.case_id, set()).add(
                _score_rule(arm_cert.qhat)(r).outcome)
    assert len(outcomes_by_case) > 0, "the arm's cases never reached the evaluation half"
    disagreeing = [cid for cid, kinds in outcomes_by_case.items()
                   if ("auto" in kinds and kinds - {"auto"})]
    assert disagreeing, ("no case's repeats disagree: the arm is inert and the two rates below "
                         "coincide by construction again")
    # Both directions, so the row names the unit it protects instead of trusting the fixture.
    assert arm_cert.autorate == arm_obs["automated_cases"] / arm_obs["n_cases"], arm_cert.autorate
    assert arm_cert.autorate != arm_obs["automated"] / len(arm_ev), (
        arm_cert.autorate, arm_obs["automated"] / len(arm_ev))


def test_the_refusal_decomposition_is_exhaustive_over_the_kinds_the_shared_counter_knows():
    """R-92b: this gate's buckets are `case_count.KINDS`, and it needs no new published reason.

    A set rule automates, returns an empty set, or returns a wider one. `refuse` is the threshold
    gate's fourth bucket, and a set rule that emitted it would write a false statement into a
    certificate. The sweep over thresholds -- not only the certified one -- is what shows all three
    reachable buckets and the fourth unreachable: one threshold would pass on a shape where a bucket
    never appears.
    """
    recs = build_ordinal(n=1200, seed=5)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    _cal, ev, _dropped = split_cal(recs, 7)
    emitted = set()
    for threshold in sorted(set(DIAGNOSTIC_GRID) | {cert.qhat, 0.6, 0.9, 1.0}):
        for r in ev:
            verdict = _score_rule(threshold)(r)
            assert verdict.outcome in KINDS, verdict
            emitted.add(verdict.outcome)
    assert emitted == {"auto", "empty", "multi"}, emitted
    assert "refuse" not in emitted

    obs = count_outcome(ev, _score_rule(cert.qhat))
    assert obs["automated"] + obs["empties"] + obs["multi_label"] == len(ev)
    assert obs["automated_cases"] + obs["refused_cases"] == obs["n_cases"]
    assert cert.meta["empties"] == obs["empties"]
    assert cert.meta["multi_label"] == obs["multi_label"]
    assert cert.meta["automated"] == obs["automated"]
    assert cert.meta["errors_among_automated"] == obs["errors"]


def test_an_unmapped_set_outcome_is_a_value_error_naming_the_outcome_not_a_keyerror(monkeypatch):
    """MIN-3: this gate's own translation guard must speak before the counter's guard can be reached.

    `classify_set`'s names are translated through `_SET_KINDS`, and the raw subscript used to run
    ahead of the shared counter's deliberate guard (`case_count.count_outcome` raises `ValueError`
    for an outcome it does not know). A missing key escaped as `KeyError` -- which `cli.py` maps to
    NO exit code at all, so rc 1, outside the published 0/2/3/4 contract -- while the counter's
    `ValueError` (rc 2) was never reached. The rule now raises the usage error itself, naming the
    unknown outcome and the keys it does know; the counter's guard stays as the backstop for a rule
    that submits a name this map should never have translated at all.

    GREEN-ON-ARRIVAL against this round's guard. Red against the subscript it replaces, the way
    the review measured it: with `"empty"` removed from the map the old line escaped
    `KeyError: 'empty'`, which `pytest.raises(ValueError)` lets through as an error, not a pass.
    The missing key is manufactured by monkeypatch here, not by editing `_SET_KINDS` in `src/`,
    because the finding is about what the guard does when the map and the family disagree -- a
    state a future `classify_set` can create on its own.
    """
    import autorate.certify_score as score_gate

    rec = build_ordinal(n=1, repeats=1, seed=1)[0]
    assert interval_set(rec.probs, 0.01) == [], "the set stopped being empty: re-read this row"
    assert classify_set(interval_set(rec.probs, 0.01)) == "empty"
    monkeypatch.setattr(score_gate, "_SET_KINDS", {"auto": "auto", "escalate": "multi"})
    with pytest.raises(ValueError, match="'empty'") as excinfo:
        _outcome([rec], 0.01)
    message = str(excinfo.value)
    assert "empty" in message and "auto" in message and "escalate" in message, message
    assert _outcome([rec], 1.0)["multi_label"] == 1, "the map is patched wider than the finding"


def test_refusal_rate_is_one_minus_autorate_and_is_not_stored():
    """R-20's identity, asserted on this gate so the extraction cannot quietly give it a second owner."""
    cert = certify_score(build_ordinal(n=1200, seed=5), alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    assert cert.refusal_rate == 1.0 - cert.autorate
    cases = cert.meta["n_eval_cases"]
    assert cert.refusal_rate == (cases - cert.meta["automated_cases"]) / cases
    assert cert.refusal_rate >= 0.0
    assert "refusal_rate" not in cert.to_dict(), "the derived number was serialised as a stored field"


def test_the_score_gate_refuses_to_certify_a_choice_population():
    """The subject guard: a `score` certificate over `choice` records certifies the wrong subject.

    `certify_threshold` raises when no record carries the field it was asked to score, because a typo
    would otherwise come back as a clean-looking refusal; the argument is stronger here, since the
    qtype IS the subject and not a column. The mixed arm is the other half of it: one score case among
    choice traffic is a population, not a usage error, and the records it drops have to be counted
    where a reader can see them.
    """
    from autorate.certify_choice import certify_choice

    choice = [dataclasses.replace(r, qtype="choice") for r in build_ordinal(n=400, repeats=1)]
    with pytest.raises(ValueError, match="qtype"):
        certify_score(choice, alpha=ALPHA, beta=BETA, seed=7)

    mixed = build_ordinal(n=300, repeats=1) + choice
    cert = certify_score(mixed, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.meta["skipped_wrong_qtype"] == 400, cert.meta
    assert cert.n_cal + cert.n_eval == 300

    # Green on arrival: this is the set gate's existing eligibility filter, restated here so the pair
    # is checked in one place. score traffic is not choice traffic, in either direction.
    refused = certify_choice(build_ordinal(n=400, repeats=1), alpha=ALPHA, beta=BETA, seed=7)
    assert refused.feasible is False
    assert refused.meta["skipped_wrong_qtype"] == 400


def test_the_ordinal_family_is_not_registered_in_the_set_gate_allowlist():
    """Green on arrival, and it must stay green: `conformal.METHODS` holds the two set-gate scores only.

    Registering the chain family there would let `certify_choice` accept `method="ordinal"` on CHOICE
    records -- the subject mismatch this file's guard above exists to refuse -- while `interval_set`
    still has to own its own sublevel loop, because routing through `conformal_set` would pass `u` per
    level (R-78). Recording `method="ordinal"` on the certificate is a different thing and is correct:
    `certify_threshold` established that `method` names the rule that actually ran.
    """
    from autorate.certify_choice import certify_choice

    assert "ordinal" not in METHODS
    assert set(METHODS) == {"aps", "lac"}
    assert METHOD not in METHODS
    twins = [dataclasses.replace(r, qtype="choice") for r in build_ordinal(n=200, repeats=1)]
    with pytest.raises(ValueError, match="ordinal"):
        certify_choice(twins, alpha=ALPHA, beta=BETA, seed=7, method=METHOD)


def test_the_recorded_randomisation_draw_is_not_read_by_the_certified_rule():
    """R-78 end to end: re-drawing every `u` leaves the whole certificate identical.

    The contrast arm is what keeps this from being a tautology: on the SAME ballots the APS score is a
    function of `u`, so the set gate's threshold does move when the draws move. If this family ever
    starts reading the draw, the first assertion goes red.
    """
    recs = build_ordinal(n=1200, seed=5)
    redrawn = [dataclasses.replace(r, u=random.Random(9000 + i).random()) for i, r in enumerate(recs)]
    a = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7).to_dict()
    b = certify_score(redrawn, alpha=ALPHA, beta=BETA, seed=7).to_dict()
    assert a == b, "the ordinal rule read the recorded draw"

    twins = [dataclasses.replace(r, qtype="choice") for r in recs]
    flat_aps = [aps_score(r.probs, r.gold_index, 0.0) for r in twins]
    live_aps = [aps_score(r.probs, r.gold_index, r.u) for r in twins]
    assert flat_aps != live_aps, "the contrast arm is inert: this file has lost its APS witness"
    assert split_quantile(flat_aps, ALPHA)[0] != split_quantile(live_aps, ALPHA)[0]


def test_the_gate_submits_the_level_inside_the_certified_set_not_the_declared_answer():
    """R-66 for this rule: `submitted` is `options[C[0]]`, and the record's own answer is not it.

    On this family a singleton set is always the modal level, so for a well-behaved record the two
    readings coincide -- the same accident the archive reports for the choice gate (`predicted ==
    argmax` on 383/383 rows). The records below are built so the two readings DISAGREE on every
    automated record, and the published error count follows the set. Had the gate read `predicted`,
    this population would have been refused on the budget: that is the plant, and it is why the
    assertions are about counts, not about a message.
    """
    recs = [dataclasses.replace(r, predicted=r.options[(r.gold_index + 2) % K])
            for r in build_ordinal(n=1200, seed=1)]
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is True, cert.summary()
    assert cert.meta["errors_among_automated"] == 0, cert.meta
    _cal, ev, _dropped = split_cal(recs, 7)
    declared_wrong = sum(1 for r in ev if r.predicted != r.gold)
    assert declared_wrong == len(ev), declared_wrong
    assert 0 < cert.meta["automated"] < declared_wrong

    obs = count_outcome(ev, _score_rule(cert.qhat))
    assert obs["errors"] == 0 == cert.meta["errors_among_automated"]
    for r in ev:
        outcome, submitted, measure = _score_rule(cert.qhat)(r)
        if outcome == "auto":
            modal = r.options[list(r.probs).index(max(r.probs))]
            assert submitted == modal, (submitted, modal, r.probs)
            assert submitted != r.predicted and measure == 1, (submitted, r.predicted, measure)


def test_a_near_uniform_ordinal_task_is_refused_not_certified():
    """spec §11.3's negative control: flat mass means no singleton, and no automation rate.

    Every ballot here is uniform, so a level's chain mass is (index+1)/k and the requested 5% quantile
    lands on the whole ballot: nothing is a singleton, and the honest output is a refusal naming what
    it counted.
    """
    recs = build_ordinal(n=1200, seed=2, temp=0.0, jitter=0.0)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is False, cert.summary()
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    assert cert.qhat is None and cert.autorate is None and cert.mean_set_size is None
    assert cert.meta["empties"] == 0 and cert.meta["multi_label"] == cert.n_eval
    assert cert.meta["automated"] == 0
    assert "singleton" in cert.summary(), cert.summary()
    # The grid cannot find a singleton either, and says so rather than inventing a near-miss.
    assert cert.meta["closest_attempt"] is None and cert.meta["diagnostic_curve"] == []


def test_an_under_calling_task_with_real_errors_is_refused_not_certified():
    """The budget arm, with R-21's evidence: a refusal that names the closest point, not a label."""
    recs = build_ordinal(n=1200, seed=4, shift=0.35)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is False, cert.summary()
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    assert cert.method == METHOD
    assert "exceeds the budget" in cert.summary(), cert.summary()
    assert cert.meta["at_requested_alpha"]["conditional_error_bound"] > BETA
    assert cert.meta["at_requested_alpha"]["errors"] > 0
    curve = cert.meta["diagnostic_curve"]
    assert curve and "evidence only" in cert.meta["diagnostic_note"]
    assert 0 < len(curve) <= len(DIAGNOSTIC_GRID)
    assert cert.meta["diagnostic_grid_size"] == len(DIAGNOSTIC_GRID)
    assert cert.meta["closest_attempt"] == min(curve, key=lambda c: (c["conditional_error_bound"],
                                                                     -c["observed_automation_rate"]))
    assert cert.meta["closest_attempt"]["errors"] > 0
    assert cert.meta["alpha"] == ALPHA and cert.meta["beta"] == BETA


def test_too_few_labelled_cases_is_its_own_refusal_reason():
    cert = certify_score(build_ordinal(n=12, repeats=1), alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is False
    assert cert.reason == Reason.N_BELOW_MIN.value
    assert cert.n_cal + cert.n_eval == 12
    assert cert.method == METHOD


def test_a_vacuous_quantile_refuses_before_certifying_the_whole_ballot():
    """ceil((1-alpha)(n+1)) > n is a result, and here it is a computable boundary, not a constant.

    Vacuity needs `alpha < 1/(n_cal+1)`; the alpha below is just inside that, derived from the
    calibration count this very population produces, so the row survives a change of MIN_CAL.
    """
    recs = build_ordinal(n=MIN_CAL + MIN_EVAL, repeats=1, seed=2)
    cal, ev, _dropped = split_cal(recs, 3)
    assert len(cal) >= MIN_CAL and len(ev) >= MIN_EVAL, (len(cal), len(ev))
    alpha = 1.0 / (len(cal) + 2)
    assert math.ceil((1.0 - alpha) * (len(cal) + 1)) > len(cal)
    cert = certify_score(recs, alpha=alpha, beta=BETA, seed=3)
    assert cert.feasible is False, cert.summary()
    assert cert.reason == Reason.VACUOUS_QUANTILE.value, cert.reason
    assert cert.method == METHOD
    assert "every level" in cert.meta["detail"], cert.meta["detail"]


def test_the_gate_returns_every_existing_reason_and_invents_none():
    """R-92b: this decomposition uses the four `Reason` members that exist today and needs no fifth.

    The expected set is written as four NAMED members rather than `set(Reason)`, because Plan B1 Task 5
    owns the fifth label; a test here that pinned the enum's size would give one published refusal
    reason two owners.
    """
    arms = {
        "no_labels": certify_score(build_ordinal(n=600, repeats=1, unlabelled=600), seed=7),
        "too_small": certify_score(build_ordinal(n=12, repeats=1), seed=7),
        "vacuous": certify_score(build_ordinal(n=MIN_CAL + MIN_EVAL, repeats=1, seed=2),
                                 alpha=1.0 / (MIN_CAL + 2), seed=3),
        "no_singleton": certify_score(build_ordinal(n=1200, seed=2, temp=0.0, jitter=0.0), seed=7),
        "over_budget": certify_score(build_ordinal(n=1200, seed=4, shift=0.35), seed=7),
    }
    reasons = {name: c.reason for name, c in arms.items()}
    assert reasons["no_labels"] == Reason.NO_GOLD_LABELS.value, reasons
    assert reasons["too_small"] == Reason.N_BELOW_MIN.value, reasons
    assert reasons["vacuous"] == Reason.VACUOUS_QUANTILE.value, reasons
    assert {reasons["no_singleton"], reasons["over_budget"]} == {Reason.EMPTY_FEASIBLE_SET.value}
    assert set(reasons.values()) == {
        Reason.NO_GOLD_LABELS.value, Reason.N_BELOW_MIN.value, Reason.VACUOUS_QUANTILE.value,
        Reason.EMPTY_FEASIBLE_SET.value}, reasons
    assert set(reasons.values()) <= {r.value for r in Reason}
    for cert in arms.values():
        assert cert.method == METHOD and cert.feasible is False
        assert cert.autorate is None and cert.qhat is None and cert.mean_set_size is None
        assert cert.meta.get("detail")


def test_unlabelled_records_are_never_used_for_calibration_but_are_counted():
    labelled = build_ordinal(n=400, repeats=1, seed=3)
    unlabelled = build_ordinal(n=400, repeats=1, seed=2, unlabelled=400)
    cert = certify_score(labelled + unlabelled, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.n_cal + cert.n_eval == 400
    assert cert.meta["skipped_no_gold"] == 400
    assert cert.meta["skipped_wrong_qtype"] == 0
    kept, dropped = _eligible(labelled + unlabelled)
    assert len(kept) == 400 and dropped["skipped_no_gold"] == 400


def test_a_batch_spanning_two_subjects_is_a_usage_error_not_a_nameless_certificate():
    """The threshold gate fixed this for its own traffic; this gate inherits the fix, not the set
    gate's older `backend=None` answer (certify_threshold.py:247-255). A certificate that names no
    subject names no model: `cli.py` refuses it and `gate.py:46-57` treats it as authorising nothing."""
    recs = build_ordinal(n=1200, seed=1)
    renamed = [dataclasses.replace(r, backend="other" if r.case_id < "case0200" else r.backend)
               for r in recs]
    with pytest.raises(ValueError, match="other"):
        certify_score(renamed, alpha=ALPHA, beta=BETA, seed=7)
    with pytest.raises(ValueError, match="synthetic-ordinal"):
        certify_score(renamed, alpha=ALPHA, seed=7)


def test_a_requested_level_outside_the_unit_interval_is_a_usage_error():
    recs = build_ordinal(n=200, repeats=1)
    for name in ("alpha", "beta", "delta"):
        for bad in (0.0, 1.0, -0.1, 1.5):
            with pytest.raises(ValueError, match="must be in"):
                certify_score(recs, **{name: bad}, seed=7)


def test_the_error_mass_alone_degrades_the_certificate():
    """Same case count, same seed, only the under-calling differs."""
    clean = certify_score(build_ordinal(n=1600, seed=13, shift=0.0), alpha=ALPHA, beta=BETA, seed=13)
    noisy = certify_score(build_ordinal(n=1600, seed=13, shift=0.30), alpha=ALPHA, beta=BETA, seed=13)
    assert clean.feasible is True, clean.summary()
    assert clean.meta["errors_among_automated"] == 0
    assert noisy.meta["errors_among_automated"] > 0, noisy.meta
    assert (noisy.autorate or 0.0) <= clean.autorate, (clean.summary(), noisy.summary())


def test_the_same_records_produce_the_same_certificate_twice_and_survive_serialisation():
    recs = build_ordinal(n=800, seed=3)
    a = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    b = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert a == b, "the gate is not a pure function of (records, seed)"
    assert Certificate.from_dict(a.to_dict()) == a


def test_the_envelope_names_the_rule_and_the_level_its_claims_are_tested_at():
    cert = certify_score(build_ordinal(n=1200, seed=1), alpha=ALPHA, beta=BETA, delta=DELTA, seed=7)
    assert cert.feasible is True, cert.summary()
    assert cert.level == 1.0 - N_CLAIMS * DELTA
    joined = " ".join(cert.envelope)
    assert "%d claims at delta=%.3f" % (N_CLAIMS, DELTA) in joined, joined
    assert "joint level %.2f" % (1.0 - N_CLAIMS * DELTA) in joined, joined
    assert "exchangeability" in joined and "group-conditional" in joined
    assert "shift" in joined
    # What makes this gate a DIFFERENT rule, stated in the envelope instead of assumed from the
    # shared field names: the family, where the threshold came from, and that no draw is read.
    assert "modal-anchored chain" in joined, joined
    assert "qhat" in joined and "alpha=%.3f" % ALPHA in joined, joined
    assert "randomisation" in joined, joined
    assert "singleton" in joined, joined
    # The mean lives in the shape's one mean slot; the envelope has to say which name is which.
    assert "mean_set_size slot" in joined and "mean_interval_length" in joined, joined
    assert cert.meta["unit_note"] and "distinct cases" in cert.meta["unit_note"]
    assert cert.meta["seed"] == 7 and cert.meta["n_cal_cases"] > 0


# --------------------------------------------------------------------------------------------
# Step 4: the coverage proof. What this can detect, and what it cannot -- both measured, not typed.
#
# Every band below is DERIVED from the published bound in `tails.bound_width`: the same width the
# certificate puts on its own automation-rate interval, evaluated at the case count being compared.
# No tolerance in this section is a literal. At the size this suite runs (200 resplits x 200 held-out
# cases = 40,000 cases) that band is 0.00679; per resplit (n=200) it is 0.09603.
#
#   * The alpha/qhat confusion (ruling R-92a) IS detected, and instantly. Measured on all three rows:
#     at threshold `alpha` the mean certified length is 0.00 levels against 2.25-3.41, empirical
#     coverage is 0.0 against the claimed 0.95, and 200 of 200 resplits trip their own band. The
#     deterministic row after the sweep shows the nastier shape: on a wide near-flat ballot the wrong
#     call automates EVERY record at 0.3067 coverage, and NO COVERAGE STATEMENT NOTICES -- the
#     certificate's own error budget refuses that population only because 69% of its automated
#     cases are wrong (an accident of this shape, not a property of the gate), and the row's witness
#     measures the release: the same planted rule publishes `autorate 1.000` at `beta=0.80`.
#   * A one-order-statistic error in the quantile is NOT reliably detected. Measured: the pooled miss
#     rate moves by +0.0046 to +0.0050, under the 0.00679 pooled band; the per-resplit arm trips 0 or
#     1 times out of 200, and since the band is a 1 - delta width, delta of them may trip for the
#     CORRECT rule anyway (`trips["qhat"]` is 0, so this arm adds nothing measurable); and in 1 to 3
#     of the 200 resplits the un-corrected index selects the SAME value as the corrected one, so the
#     defect changes nothing at all. Whether the row then goes red depends on where the correct rate
#     happens to sit inside the band, not on the size of the defect. That is ledger R-19's conclusion
#     re-measured on this family's numbers: the guard against an index error is
#     `test_the_certified_threshold_is_a_calibration_half_fact_and_nothing_else` and
#     `split_quantile`'s own vacuity flag, not a Monte-Carlo band.
# --------------------------------------------------------------------------------------------
TRIALS = 200
CASES_PER_RESPLIT = 400


def _arm(ev, threshold):
    """Coverage and buckets of one rule at one threshold, counted on the CASE unit (one record each)."""
    miss = empties = auto = err = multi = 0
    length_sum = 0
    for r in ev:
        C = interval_set(r.probs, threshold)
        length_sum += len(C)
        if r.gold_index not in C:
            miss += 1
        if not C:
            empties += 1
        elif len(C) == 1:
            auto += 1
            err += C[0] != r.gold_index
        else:
            multi += 1
    return {"n": len(ev), "miss": miss, "mean_len": length_sum / len(ev), "auto": auto,
            "err": err, "empties": empties, "multi": multi}


def _band(n, delta=DELTA):
    """The published width the certificate uses for its own rate interval, as a half-width."""
    return bound_width(n, delta) / 2.0


def _assert_covers(rate, n, claim=ALPHA, delta=DELTA):
    """One predicate, run on the rule AND on both plants. The band is derived, never typed."""
    half = _band(n, delta)
    if not claim - half <= rate <= claim + half:
        raise AssertionError("empirical coverage %.5f is outside the claim %.5f +/- the published "
                             "band %.5f at n=%d delta=%g" % (rate, claim, half, n, delta))
    return half


def _one_resplit(seed, k, shift):
    """A fresh population, the gate's own split and quantile, and the two planted thresholds."""
    recs = build_ordinal(n=CASES_PER_RESPLIT, seed=seed, k=k, shift=shift, repeats=1)
    cal, ev, _dropped = split_cal(recs, seed)
    scores = _scores(cal)
    qhat, vacuous = split_quantile(scores, ALPHA)
    assert not vacuous, "this row is testing the vacuity flag, not coverage"
    srt = sorted(scores)
    # The un-corrected index: floor((1-alpha)n) instead of ceil((1-alpha)(n+1)) -- one order statistic
    # too low. Computed here so the wrong rule never lives in src/, as tests/test_coverage_montecarlo.py
    # does for the set gate. The index is one step down, and on a 4-decimal score distribution two
    # neighbouring order statistics are often the SAME value: that is measured below, not assumed, and
    # it is the first reason this suite is not the guard against an index error.
    naive = srt[max(0, int(math.floor((1.0 - ALPHA) * len(srt))) - 1)]
    assert naive <= qhat, "the un-corrected index came out ANTI-conservative: re-read it"
    return {"qhat": _arm(ev, qhat), "naive": _arm(ev, naive), "alpha": _arm(ev, ALPHA),
            "tied": naive == qhat}


@pytest.mark.parametrize("k,shift", [(5, 0.0), (5, 0.30), (7, 0.0)])
def test_the_certified_set_covers_at_the_claimed_level_over_200_resplits(k, shift):
    total = 0
    pooled = {"qhat": 0, "naive": 0, "alpha": 0}
    lens = {"qhat": 0.0, "naive": 0.0, "alpha": 0.0}
    trips = {"qhat": 0, "naive": 0, "alpha": 0}
    tied = 0
    for t in range(TRIALS):
        r = _one_resplit(7_000_000 + t, k, shift)
        total += r["qhat"]["n"]
        tied += r["tied"]
        for name in pooled:
            pooled[name] += r[name]["miss"]
            lens[name] += r[name]["mean_len"] * r[name]["n"]
            if r[name]["miss"] / r[name]["n"] > ALPHA + _band(r[name]["n"]):
                trips[name] += 1
    rates = {name: pooled[name] / total for name in pooled}

    # The claim: coverage of the certified set is 1 - alpha, inside the published band -- and not
    # merely BELOW it, because a rule that certified the whole ballot would satisfy the upper arm too.
    half = _assert_covers(rates["qhat"], total)
    # The tolerance is a FUNCTION of the case count, not a constant someone typed: four times the
    # evidence halves the band, a quarter of it doubles the band. A hand-typed band could not.
    assert abs(_band(total * 4) - half / 2.0) < 1e-15, (_band(total * 4), half)
    assert abs(_band(total // 4) - 2.0 * half) < 1e-15, (_band(total // 4), half)
    assert trips["qhat"] == 0, "resplits under-covered beyond their own published band"
    assert 1.0 < lens["qhat"] / total < k, "the sets are degenerate: coverage of a constant set"
    assert pooled["qhat"] > 0, "no case missed anywhere: this row cannot fail and proves nothing"

    # PLANT A (R-92a): the call the old parameter name invited, through the same predicate.
    with pytest.raises(AssertionError, match="outside the claim"):
        _assert_covers(rates["alpha"], total)
    assert rates["alpha"] - rates["qhat"] > half, "the wrong threshold hides inside the band"
    assert lens["alpha"] < lens["qhat"], "the alpha-thresholded sets are not strictly smaller"
    assert trips["alpha"] == TRIALS

    # PLANT B (R-19): real, and under the ruler. Asserted as a magnitude, not as a red test.
    index_shift = rates["naive"] - rates["qhat"]
    assert 0 < index_shift < half, (index_shift, half)
    # Per resplit the defect adds no signal beyond what the band allows by chance: the band is a
    # 1 - delta width, so `TRIALS * delta` of the resplits may sit outside it for the CORRECT rule.
    # Measured here: 0 trips for qhat, 0 or 1 for the un-corrected index, 200 for the alpha arm.
    assert trips["naive"] <= trips["qhat"] + TRIALS * DELTA, trips
    # And in some of the 200 resplits the un-corrected index selects the SAME value, so the defect
    # produces no difference at all -- the same conclusion from the other direction.
    assert 0 < tied < TRIALS, tied


def test_the_coverage_claim_is_about_the_number_the_certificate_publishes():
    """The bridge: the qhat the sweep above tests IS the qhat a certificate prints.

    The sweep re-derives qhat from `split_cal` + `split_quantile` so that shapes the gate refuses on
    the budget can still be covered; that is only honest if the gate publishes the same number, which
    is what this row pins on a shape where the gate is feasible.
    """
    recs = build_ordinal(n=CASES_PER_RESPLIT, seed=7_000_000, repeats=1)
    cal, ev, _dropped = split_cal(recs, 7_000_000)
    qhat, _vac = split_quantile(_scores(cal), ALPHA)
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7_000_000)
    assert cert.feasible is True, cert.summary()
    assert cert.qhat == qhat
    arm = _arm(ev, cert.qhat)
    # The certificate's own refusal mass is the same arithmetic the gate published.
    assert arm["empties"] == cert.meta["empties"] and arm["multi"] == cert.meta["multi_label"]
    assert arm["auto"] == cert.meta["automated"]


def test_passing_alpha_where_qhat_belongs_automates_everything_and_no_coverage_statement_notices(
        monkeypatch):
    """R-92a, deterministic: the wrong call is invisible to anything that speaks about coverage.

    On a wide near-flat ballot (25 levels, modal mass 0.0436 < alpha) the alpha-thresholded set is a
    NON-EMPTY singleton for every record: a gate that passed `alpha` into `interval_set` publishes an
    automation rate of 1.000 under a heading reading "at coverage 0.950", while the empirical
    coverage of those same sets is 0.3067. The correct threshold (qhat=0.176) gives coverage 0.9667
    and automates NOTHING, so this gate's real output for the population is a refusal.

    An earlier version of this row called that failure "a green run", and measured against this
    row's own beta that is false: the planted rule automates 600 cases, 416 of them wrong, the exact
    case-level upper bound is 0.724, and the ERROR budget refuses it. The true statement is weaker
    in one direction and stronger in the other: nothing on the certificate ever compares the sets
    with the threshold they were actually built at -- the catch here is an accident of this
    population's 69% error rate, not a property of the gate. The witness below measures both halves
    of that claim on the planted call: at `beta=0.05` the error budget refuses, at `beta=0.80` the
    same rule publishes `autorate 1.000` under the same coverage heading.
    """
    recs = build_ordinal(n=1200, seed=7, k=25, temp=0.01, jitter=0.1, repeats=1)
    assert max(recs[0].probs) < ALPHA, "the shape stopped demonstrating the point"
    cert = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert cert.feasible is False and cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.summary()
    cal, ev, _dropped = split_cal(recs, 7)
    qhat, vacuous = split_quantile(_scores(cal), ALPHA)
    assert not vacuous and qhat > ALPHA
    assert cert.meta["automated"] == 0 and cert.meta["multi_label"] == cert.n_eval

    right = _arm(ev, qhat)
    wrong = _arm(ev, ALPHA)
    _assert_covers(right["miss"] / right["n"], right["n"])
    with pytest.raises(AssertionError, match="outside the claim"):
        _assert_covers(wrong["miss"] / wrong["n"], wrong["n"])
    assert wrong["auto"] == wrong["n"] and right["auto"] == 0, (wrong["auto"], right["auto"])
    assert wrong["mean_len"] < right["mean_len"], (wrong["mean_len"], right["mean_len"])
    # And the shrink is graded, not a cliff: between the two sits a threshold whose set is smaller
    # than the certified one but not empty, so a partial agreement is possible and still wrong.
    middle = (ALPHA + qhat) / 2.0
    assert set(interval_set(recs[0].probs, middle)) < set(interval_set(recs[0].probs, qhat))

    # The witness the corrected claim needs, measured through the whole gate rather than argued in
    # prose: re-wire the production call the way R-92a found it (`interval_set` handed `alpha` where
    # the quantile belongs -- the monkeypatch emulates the plant so the assertion runs against
    # shipped code) and read both budgets off the result. GREEN-ON-ARRIVAL by construction -- the
    # plant is emulated inside this row, so what reddens it is a drift in what the witness claims:
    # an error budget that stops gating on the case unit would let the tight arm publish, and a
    # gate that checks the sets against the threshold used (the fix R-92a asks nobody for here)
    # would refuse the loose one. Both arms reproduce against the real P-F1 production plant,
    # which reddens this row outright -- see the fix report's lane.
    import autorate.certify_score as score_gate

    real_interval_set = score_gate.interval_set
    monkeypatch.setattr(score_gate, "interval_set",
                        lambda probs, threshold, u=0.0: real_interval_set(probs, ALPHA))
    planted_tight = certify_score(recs, alpha=ALPHA, beta=BETA, seed=7)
    assert planted_tight.feasible is False, planted_tight.summary()
    assert planted_tight.reason == Reason.EMPTY_FEASIBLE_SET.value, planted_tight.summary()
    assert "exceeds the budget" in planted_tight.meta["detail"], planted_tight.meta["detail"]
    planted_loose = certify_score(recs, alpha=ALPHA, beta=0.80, seed=7)
    assert planted_loose.feasible is True, planted_loose.summary()
    assert planted_loose.autorate == 1.0 and "coverage 0.950" in planted_loose.summary(), \
        planted_loose.summary()
    monkeypatch.undo()
    assert score_gate.interval_set is real_interval_set, "the plant leaked past this row"
