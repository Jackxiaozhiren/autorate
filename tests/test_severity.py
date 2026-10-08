"""G3: an ordinal one-sided guarantee, and the control that multiclass CP cannot state it.

Spec §2's G3 row is an expressiveness claim -- ">=1 ordinal guarantee that multiclass CP cannot
express: the one-sided severity certificate P(Y > â(X)) <= alpha. If vanilla multiclass set CP
reproduces it, this criterion fails" -- so it is falsifiable against us, and the falsifier lives in
this file rather than in a comment (spec §6.4 asks for the contrast on the same records). Where the
measurement landed:

* **THE CONTROL HOLDS.** `build_ordinal(n=1200, seed=5, shift=0.1, temp=2.0)` is a model that
  under-calls by one level on 10% of cases; `_mirror_scale` of it reverses the presented option order
  and is therefore a model that OVER-calls by one level on 10% of cases, with the same gold labels,
  the same error magnitude and the same case partition. The ordinal set gate gives them
  byte-identical certificates (`autorate` 0.36, `qhat` 0.9115, `conditional_error_bound`
  0.04075368623063993, `mean_set_size` 3.01) and so does APS (`qhat` 0.8576157950260285, `autorate`
  0.36, `conditional_error_bound` 0.064198542706), while the one-sided certificate answers them
  differently: â=3 with bound 0.038310 and an over-call price of 0.658075 for the under-caller,
  against â=0 with bound 0.014867 and a price of 0.083335 for the over-caller. G3 therefore lands on
  the POSITIVE side, by construction and with numbers.
* **THE REVERSE HOLDS TOO, and it is this gate's own blind spot, not the control's.** Two populations
  with the same modal level and the same gold per case give IDENTICAL severity certificates while the
  set gate moves from `autorate` 0.505 to 1.0 (mean set size 1.745 against 1.0) and, at the published
  rubric, stops answering at all. The severity loss reads `gold_index` and the modal index and nothing
  else -- not the ballot's shape, not the recorded draw. The two quantities are incomparable, which is
  what "cannot express" claims; neither gate is a generalisation of the other.
* **THE PLAN'S OWN CONTROL ROW COULD NOT RUN AS WRITTEN**, and the reason is measured in
  `test_the_plan_s_literal_control_call_states_nothing_at_all`: `certify_choice._eligible` filters on
  `qtype == "choice"`, so handed the ordinal `score` population it drops all 1,200 records and refuses
  with `no_gold_labels`, and a refusal carries None in every headline slot -- which is exactly what
  that row asserts is not None. With the subject tag flipped the same call still refuses, now with
  `empty_feasible_set`: at `shift=0.9` the model is wrong on 90% of cases, so no certified set is a
  singleton and there is no bound for the control to be silent about. The plan's values are kept
  (`n=1200, seed=5, alpha=0.05, delta=0.05, seed=3`, `method="aps"`, `beta=0.05`); the population for
  the comparison row is one where the control publishes, and the deviation is asserted below rather
  than hidden.
* **EVERY RECORD HERE IS SYNTHETIC ORDINAL DATA WITH KNOWN ANSWERS**, seeded and re-derivable. The
  offline archive carries no `score` answers at all, so nothing in this file measures a shipped model
  (spec §12's concession; the same evidence boundary `certify_score` records in its own docstring).
"""
import collections
import dataclasses

import pytest
from _records import build_ordinal

from autorate.certificate import N_CLAIMS, Reason, canonicalise_bound
from autorate.case_count import case_key
from autorate.certify_choice import certify_choice
from autorate.certify_score import certify_score, split_cal
from autorate.correction import JOINT_LEVEL_RULE, joint_level
from autorate.nonconformity import aps_score
from autorate.ordinal import mode_index
from autorate.records import Record
from autorate.severity import (DIRECTIONS, SEVERITY_N_CLAIMS, SeverityCertificate, certify_severity,
                               over_call_bound, report_ceiling, report_level, severity_band,
                               tolerance_band)
from autorate.tails import clopper_pearson_upper

ALPHA = 0.05
DELTA = 0.05
SEED = 3
K = 5
OPTIONS = tuple(str(j) for j in range(K))
# The population the comparison rows run on: feasible for the set gate at the published rubric, so
# the control has numbers to be silent about. `build_ordinal` counts RECORDS in `n`, and at the
# default `repeats=3` 1,200 records are 400 cases, which the seed=3 split cuts into 600/600 records
# and 200/200 cases -- asserted below rather than assumed, because every bound in this file is a
# function of the case count.
CLEAN = dict(n=1200, seed=5, shift=0.1, temp=2.0)
# The plan's own fixture, kept for the rows whose values the plan fixes.
PLAN = dict(n=1200, seed=5, shift=0.9)
# A model that is never wrong: the only population on which a tolerance band of 0 is a true
# statement, so `d == 0` has a legal home and the guard that refuses it beside a miss is reachable.
EXACT = dict(n=1200, seed=5)


def ordinal_records(**kw):
    """Thin wrapper on the shared factory, so the plan's rows keep reading `ordinal_records(...)`.

    `tests/_records.py` is the one owner (ruling R-69: Task 3 creates/extends that module and calls it
    through this wrapper -- never through a fixture, because a fixture returning a factory is what the
    ruling forbids, and aliasing a fixture's return value at module scope is the same thing wearing a
    different hat).
    """
    return build_ordinal(**kw)


def _as_choice(records):
    """The same ballots under the `choice` subject tag.

    Only exists because `certify_choice._eligible` filters on `qtype == "choice"`. No record content
    changes, so the comparison stays a comparison of two RULES over one population and not of two
    populations.
    """
    return [dataclasses.replace(r, qtype="choice") for r in records]


def _mirror_scale(records):
    """Reverse the PRESENTED option order: the same labels, the ordinal scale running the other way.

    An under-caller becomes an over-caller and nothing else changes. `probs` and `options` are both
    reversed, so `mode_index` moves to `k-1-m`, `gold_index` moves to `k-1-g`, every certified SET
    keeps its size and its membership up to the mirrored label, and the case partition is untouched.
    `gold` and `predicted` keep their NAMES, because the level a record states is carried by the name
    and it is the name's POSITION that this mirror moves.
    """
    return [Record(id=r.id, qtype=r.qtype, backend=r.backend, repeat=r.repeat,
                   options=tuple(reversed(r.options)), probs=tuple(reversed(r.probs)),
                   gold=r.gold, predicted=r.predicted, case_id=r.case_id, slices=dict(r.slices),
                   scores=dict(r.scores), seed=r.seed, u=r.u, meta=dict(r.meta))
            for r in records]


def _flattened(records):
    """The same modal level and the same gold, in a near-flat ballot.

    Severity cannot see this change at all (its loss is a function of two indices); the set gate's
    whole certificate moves, which is the reverse direction of the expressiveness claim.
    """
    out = []
    for r in records:
        k = len(r.options)
        m = mode_index(r.probs)
        raw = [0.19 - 0.01 * j for j in range(k)]
        s = sum(raw)
        probs = [0.0] * k
        for j in range(k):
            probs[(m + j) % k] = round(raw[j] / s, 4)
        probs[m] = round(probs[m] + (1.0 - sum(probs)), 4)
        out.append(dataclasses.replace(r, probs=tuple(probs)))
    return out


def _case_groups(half):
    """Test-local case grouping, so the case arithmetic below is derived twice, not read back."""
    groups = collections.OrderedDict()
    for r in half:
        groups.setdefault(case_key(r), []).append(r)
    return groups


# The two shapes the unit guard needs. `UNDER_ROW` under-calls at every candidate below level 2 (its
# gold sits one above its own modal level); `EXACT_ROW` is never under-called (gold IS its modal
# level). One case holding one of each violates as a CASE while exactly one of its two RECORDS
# violates -- the only shape that can tell the two denominators apart, and the shape the task-2
# review's MINOR-1 says a `repeats=1` population cannot supply.
UNDER_ROW = (0.16, 0.52, 0.24, 0.06, 0.02)     # mode 1, gold "2"
NONVIOL_ROW = (0.06, 0.10, 0.17, 0.55, 0.12)   # mode 3, gold "3"
EXACT_ROW = (0.06, 0.10, 0.66, 0.12, 0.06)     # mode 2, gold "2"


def _mixed_repeat_cases(count):
    """`count` two-record cases whose repeats disagree about under-calling."""
    out = []
    for i in range(count):
        cid = "mix%04d" % i
        out.append(Record(id="%s.r0" % cid, qtype="score", backend="synthetic-ordinal", repeat=0,
                          options=OPTIONS, probs=UNDER_ROW, gold="2", predicted="1", case_id=cid,
                          seed=11, u=0.1))
        out.append(Record(id="%s.r1" % cid, qtype="score", backend="synthetic-ordinal", repeat=1,
                          options=OPTIONS, probs=NONVIOL_ROW, gold="3", predicted="3",
                          case_id=cid, seed=11, u=0.7))
    return out


def _clean_three_record_cases(count):
    """`count` three-record cases that never under-call: mode == gold == level 2."""
    out = []
    for i in range(count):
        cid = "clean%04d" % i
        for rep in range(3):
            out.append(Record(id="%s.r%d" % (cid, rep), qtype="score",
                              backend="synthetic-ordinal", repeat=rep, options=OPTIONS,
                              probs=EXACT_ROW, gold="2", predicted="2", case_id=cid, seed=11,
                              u=0.1 * rep))
    return out


def _hand_bound(count, n, delta=DELTA):
    """The published form of one exact binomial upper bound, counted here from the definitions."""
    return canonicalise_bound(clopper_pearson_upper(count, n, delta))


# ---------------------------------------------------------------- the plan's four rows (Step 1) --


def test_the_under_call_bound_holds_on_the_evaluation_half():
    """The plan's row 1, values verbatim: a bound, its budget, and its own observed rate."""
    recs = ordinal_records(**PLAN)     # model under-reports severity
    cert = certify_severity(recs, alpha=0.05, delta=0.05, direction="under", seed=3)
    assert cert.feasible is True, cert.summary()
    assert cert.bound <= 0.05 + 1e-9
    assert cert.measured_violation <= cert.bound, (
        "a bound below its own observed rate is the arithmetic bug this project already "
        "fixed once in tails.binom_cdf")


def test_a_monotone_loss_is_a_precondition_and_is_enforced_not_assumed():
    """The plan's row 2: the family is checked by measurement, and the naive sum fails it."""
    recs = ordinal_records(n=800, seed=6)
    risks = [sum(1 for r in recs if r.gold_index > a) / len(recs) for a in range(5)]
    assert risks == sorted(risks, reverse=True), risks
    with pytest.raises(ValueError, match="monotone"):
        certify_severity(recs, alpha=0.05, direction="both_sides_sum", seed=3)


def test_the_plan_s_literal_control_call_states_nothing_at_all():
    """Why the comparison row could not keep the plan's population: the control refuses twice over.

    This row states an arrival measurement, so it is green the moment the severity module imports;
    the changes that redden it are named in the assertions: `certify_choice._eligible` losing its
    `qtype == "choice"` filter (first half), or a generator whose model is not wrong on 90% of cases
    (second half).
    """
    recs = ordinal_records(**PLAN)
    refused = certify_choice(recs, alpha=ALPHA, beta=ALPHA, method="aps", seed=SEED)
    assert refused.feasible is False
    assert refused.reason == Reason.NO_GOLD_LABELS.value, refused.reason
    assert refused.marginal_error_bound is None and refused.conditional_error_bound is None
    assert refused.meta["skipped_wrong_qtype"] == len(recs), refused.meta["skipped_wrong_qtype"]
    # With the subject tag flipped the SAME population still gives the multiclass gate nothing to
    # say, so the plan's `is not None` assertions are unreachable on this fixture either way.
    silent = certify_choice(_as_choice(recs), alpha=ALPHA, beta=ALPHA, method="aps", seed=SEED)
    assert silent.feasible is False
    assert silent.reason == Reason.EMPTY_FEASIBLE_SET.value, silent.reason
    assert silent.meta["multi_label"] > 500, silent.meta["multi_label"]


def test_multiclass_cp_bounds_membership_not_the_side_of_the_miss():
    """The control, on the population where the control publishes. If APS can state `P(Y > a)`, G3 failed."""
    recs = ordinal_records(**CLEAN)
    aps = certify_choice(_as_choice(recs), alpha=ALPHA, beta=0.80, method="aps", seed=SEED)
    sev = certify_severity(recs, alpha=ALPHA, delta=DELTA, direction="under", seed=SEED)
    assert hasattr(sev, "bound") and sev.bound <= 0.05
    for name in ("marginal_error_bound", "conditional_error_bound"):
        assert getattr(aps, name) is not None, (name, aps.reason, aps.meta.get("detail"))
    assert "P(Y >" in sev.summary() and "P(Y >" not in aps.summary(), (
        "the quantity G3 claims to add must be the one the control cannot print")
    # The stronger control is the ordinal set gate itself: same subject, same family, same records,
    # and it still has nowhere to put the side of the miss.
    sets = certify_score(recs, alpha=ALPHA, beta=ALPHA, delta=DELTA, seed=SEED)
    assert sets.feasible is True, sets.summary()
    assert "P(Y >" not in sets.summary(), sets.summary()


# ---------------------------------------------------- the comparison, constructed with its numbers --


def test_the_set_gate_reads_the_same_certificate_for_a_model_and_its_scale_reversal():
    """G3's falsifier, and it did not fire: identical sets, opposite severity verdicts.

    `CLEAN` under-calls by one level on 10% of cases and `_mirror_scale(CLEAN)` over-calls by one
    level on 10%, with every certified set carried over by the reversal. So the set numbers MUST be
    identical and the one-sided certificate must differ. If the two `certify_score` certificates ever
    diverge this row stops being a control and the claim moves to the refusal arm; if the two
    severity certificates ever agree, G3 is void and this is the row that says so.
    """
    recs = ordinal_records(**CLEAN)
    mir = _mirror_scale(recs)
    mine = certify_score(recs, ALPHA, ALPHA, DELTA, seed=SEED)
    theirs = certify_score(mir, ALPHA, ALPHA, DELTA, seed=SEED)
    for field in ("feasible", "qhat", "autorate", "mean_set_size", "conditional_error_bound",
                  "marginal_error_bound", "autorate_ci", "n_cal", "n_eval"):
        assert getattr(mine, field) == getattr(theirs, field), field
    assert (mine.qhat, mine.autorate, mine.mean_set_size) == (0.9115, 0.36, 3.01)
    aps_mine = certify_choice(_as_choice(recs), ALPHA, 0.80, DELTA, SEED, "aps")
    aps_theirs = certify_choice(_as_choice(mir), ALPHA, 0.80, DELTA, SEED, "aps")
    assert aps_mine.qhat == aps_theirs.qhat == 0.8576157950260285
    assert (aps_mine.autorate, aps_mine.conditional_error_bound) == \
        (aps_theirs.autorate, aps_theirs.conditional_error_bound)

    sev = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    sev_m = certify_severity(mir, ALPHA, DELTA, "under", SEED)
    assert (sev.ahat, sev_m.ahat) == (3, 0), (sev.ahat, sev_m.ahat)
    assert sev.bound > sev_m.bound, (sev.bound, sev_m.bound)
    assert sev.price_bound > sev_m.price_bound, (sev.price_bound, sev_m.price_bound)
    # The counts the four bounds are made from, hand-derived from the generator's definition and the
    # seed=3 split: the under-caller violates on 3 of its 200 calibration cases and its floor
    # over-calls on 120; the over-caller never under-calls (0 of 200) but its own answer over-calls
    # on 10.
    assert sev.bound == _hand_bound(3, 200), sev.bound
    assert sev.price_bound == _hand_bound(120, 200), sev.price_bound
    assert sev_m.bound == _hand_bound(0, 200), sev_m.bound
    assert sev_m.price_bound == _hand_bound(10, 200), sev_m.price_bound
    assert "P(Y >" in sev.summary() and "P(Y >" in sev_m.summary()


def test_the_severity_certificate_is_identical_when_only_the_ballot_shape_changes():
    """The reverse direction, and it is this gate's own blind spot stated with numbers.

    Same modal level, same gold, near-flat ballots: every severity field is identical because the
    severity loss is a function of `(gold_index, mode_index)` alone, while the set gate's automation
    rate and mean set size move, and at the published rubric the set gate stops answering. Reported
    because G3 is a claim about expressiveness, not about superiority.
    """
    recs = ordinal_records(**CLEAN)
    flat = _flattened(recs)
    assert [mode_index(r.probs) for r in flat] == [mode_index(r.probs) for r in recs]
    assert [r.gold_index for r in flat] == [r.gold_index for r in recs]
    sev = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    sev_flat = certify_severity(flat, ALPHA, DELTA, "under", SEED)
    for field in ("ahat", "bound", "price_bound", "override_bound", "measured_violation", "n_cal",
                  "n_eval", "level"):
        assert getattr(sev, field) == getattr(sev_flat, field), field
    strict = certify_score(flat, ALPHA, ALPHA, DELTA, seed=SEED)
    assert strict.feasible is False and strict.reason == Reason.EMPTY_FEASIBLE_SET.value
    loose_mine = certify_score(recs, 0.20, 0.80, DELTA, seed=SEED)
    loose_flat = certify_score(flat, 0.20, 0.80, DELTA, seed=SEED)
    assert (loose_mine.autorate, loose_flat.autorate) == (0.505, 1.0)
    assert (loose_mine.mean_set_size, loose_flat.mean_set_size) == (1.745, 1.0)


# ------------------------------------------------------------------------ the certification unit --


def test_the_bound_is_tested_on_cases_and_not_on_rows_a_disagreeing_repeat_arms_it():
    """MINOR-1's trap, armed: on byte-identical repeats the two denominators are the same number.

    `build_ordinal`'s cases are byte-identical across repeats on purpose (that is what the committed
    archive looks like), so on that population a case-unit bound and a record-unit bound cannot be
    told apart. The mixed population below puts one under-calling record and one non-under-calling
    record in the same case, so the CASE violates while one row of it does not: the numerators
    coincide and the DENOMINATORS part company (100 cases against 299 records in the calibration
    half), which is the shape the assertion needs. Both directions are asserted -- equality to the
    case unit, inequality to the record unit -- exactly as the task-2 fix round pinned its own
    bounds row.
    """
    recs = _mixed_repeat_cases(2) + _clean_three_record_cases(198)
    cal, ev, dropped = split_cal(recs, SEED)
    groups = _case_groups(cal)
    n_cases = len(groups)
    assert len(recs) == 598 and n_cases == 100 and len(cal) == 299, (n_cases, len(cal))
    assert n_cases != len(cal)

    def case_count(a):
        return sum(1 for g in groups.values()
                   if any(r.gold_index > max(mode_index(r.probs), a) for r in g))

    def row_count(a):
        return sum(1 for r in cal if r.gold_index > max(mode_index(r.probs), a))

    assert case_count(0) == row_count(0) == 1, (case_count(0), row_count(0))
    cert = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    assert cert.ahat == 0, cert.summary()
    assert cert.bound == _hand_bound(1, 100), cert.bound
    assert cert.bound != _hand_bound(1, 299)
    assert cert.meta["n_cal_cases"] == n_cases
    assert cert.meta["violating_cases"] == case_count(cert.ahat)
    assert dropped == {"skipped_no_gold": 0, "skipped_wrong_qtype": 0}


def test_the_evaluation_half_is_measured_not_certified():
    """The empirical check G1 asks for, stated on its own half: the bound comes from calibration."""
    recs = ordinal_records(**CLEAN)
    cert = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    cal, ev, _ = split_cal(recs, SEED)
    ev_groups = _case_groups(ev)
    assert len(ev_groups) == 200 and len(_case_groups(cal)) == 200
    assert cert.meta["n_eval_cases"] == 200
    measured = sum(1 for g in ev_groups.values()
                   if any(r.gold_index > max(mode_index(r.probs), cert.ahat) for r in g))
    assert measured == 2, measured
    assert cert.measured_violation == measured / 200
    assert cert.bound == _hand_bound(3, cert.meta["n_cal_cases"])
    assert set(_case_groups(cal)) & set(ev_groups) == set()


# ----------------------------------------------------------------------- the rules being certified --


def test_report_level_floors_and_report_ceiling_clips_and_neither_loses_its_own_direction():
    """`report_level(probs, a)` = max(modal level, a); the clip is its mirror image.

    The floor can only RAISE a report, which is what makes `P(Y > â(X)) <= alpha` a statement about
    the rule a deployment runs rather than about a constant; the clip can only LOWER one. A floor
    that at `a=0` was not the model's own answer would mean the gate read some other anchor.
    """
    probs = (0.06, 0.10, 0.54, 0.18, 0.12)
    assert mode_index(probs) == 2
    assert report_level(probs, 0) == 2
    assert [report_level(probs, a) for a in range(K)] == [2, 2, 2, 3, 4]
    assert [report_ceiling(probs, a) for a in range(K)] == [0, 1, 2, 2, 2]
    for a in range(K):
        assert report_level(probs, a) >= max(mode_index(probs), a)
        assert report_ceiling(probs, a) <= min(mode_index(probs), a)
    with pytest.raises(ValueError, match="level"):
        report_level(probs, K)
    with pytest.raises(ValueError, match="level"):
        report_ceiling(probs, -1)


def test_the_certified_direction_decides_which_end_of_the_rubric_is_the_degenerate_one():
    """§6.2's symmetric sentence, implemented: a floor is met at the ceiling, a clip at the floor.

    Informativeness runs the other way for a clip than for a floor, so the over direction must return
    the LARGEST feasible candidate (the least clipping still certified), not the smallest. Asserting
    which end is picked is what stops a future edit making both directions "smallest feasible", which
    would silently certify the constant bottom of the rubric and call it a guarantee.
    """
    recs = ordinal_records(n=800, seed=6)
    over = certify_severity(recs, ALPHA, DELTA, "over", SEED)
    assert over.feasible is True, over.summary()
    assert over.direction == "over" and over.ahat == K - 1, over.ahat
    assert over.bound == _hand_bound(over.meta["violating_cases"], over.meta["n_cal_cases"])
    under = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    assert under.ahat == 0, under.ahat
    assert over.bound == under.bound == _hand_bound(0, under.meta["n_cal_cases"])
    assert "direction=over: P(Y <" in over.summary(), over.summary()
    assert "direction=under: P(Y >" in under.summary(), under.summary()
    # The price line names the OTHER side of the same rule, which is the point of publishing it: an
    # `under` certificate that printed only its own side would hide that the floor over-calls on
    # 0.85 of the cases the plan's fixture certifies.
    assert "the price is P(Y >" in over.summary() and "the price is P(Y <" in under.summary()


def test_the_recorded_randomisation_is_carried_and_never_read():
    """R-78's rule, restated for this gate: re-draw every `u` and nothing moves.

    The severity loss reads levels, not masses, so `u` cannot enter it -- but a future edit that
    threaded the draw through "for symmetry with the set gate" would make the certified level a
    function of a random number, and this row catches that on the spot.
    """
    recs = ordinal_records(**CLEAN)
    base = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    redrawn = [dataclasses.replace(r, u=(r.u + 0.37) % 1.0) for r in recs]
    again = certify_severity(redrawn, ALPHA, DELTA, "under", SEED)
    for field in ("ahat", "bound", "price_bound", "override_bound", "measured_violation", "level"):
        assert getattr(base, field) == getattr(again, field), field
    assert base.meta["eval_ids"] == again.meta["eval_ids"]


def test_aps_is_order_blind_by_construction_which_is_why_it_cannot_carry_a_side():
    """Names the mechanism, so the expressiveness claim is not just two summaries being compared.

    APS's score is a mass tail: the same multiset of masses and the same `p_gold` under a reversal, so
    the ORDER of the scale never reaches it. GREEN-ON-ARRIVAL for the invariance; the change that
    reddens it is `nonconformity.aps_score` learning to read the presented option order, at which
    point it stops being APS.
    """
    recs = ordinal_records(**CLEAN)
    mine = [(r.id, round(aps_score(r.probs, r.gold_index, r.u), 12)) for r in recs[:200]]
    theirs = {(r.id, round(aps_score(r.probs, r.gold_index, r.u), 12))
              for r in _mirror_scale(recs)[:200]}
    assert all(pair in theirs for pair in mine), mine[:3]
    assert certify_severity(recs, ALPHA, DELTA, "under", SEED).ahat == 3


# ---------------------------------------------------------------------------- precision, budgets --


def test_the_published_bound_is_canonical_on_the_grid_and_never_beats_its_own_alpha():
    """R-121/R-127: one precision owner, no epsilon, and the feasibility test reads the published value.

    A ceilinged bound can only move UP, so a gate that tested the RAW value and published the
    canonical one could print a bound above the budget it just claimed to meet. The order here is
    canonicalise-then-test, the same order `certify_choice` documents at its own bound call sites.
    """
    for kw in (PLAN, CLEAN):
        cert = certify_severity(ordinal_records(**kw), ALPHA, DELTA, "under", SEED)
        assert cert.bound == canonicalise_bound(cert.bound), cert.bound
        assert cert.price_bound == canonicalise_bound(cert.price_bound)
        assert cert.override_bound == canonicalise_bound(cert.override_bound)
        assert cert.bound <= ALPHA, "no epsilon: the published bound meets the budget exactly"
    cert = certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "under", SEED)
    assert cert.measured_violation == (cert.meta["eval_violating_cases"]
                                       / cert.meta["n_eval_cases"])


def test_budgets_outside_the_open_interval_are_usage_and_not_a_refusal():
    """Every non-level is refused BY NAME, before any arithmetic.

    `not 0.0 < "0.05" < 1.0` raises `TypeError`, and `cli.py` maps no `TypeError` to an exit code, so
    a budget that arrives as text (which is how a CLI flag arrives) must be refused by type as well as
    range -- the rule `correction._level` states. The set gates have not adopted it; this gate does,
    and the row is the reason it cannot quietly be dropped later.
    """
    for bad in (0.0, 1.0, -0.1, 1.5, "0.05", None, True, float("nan")):
        with pytest.raises(ValueError):
            certify_severity(ordinal_records(**CLEAN), bad, DELTA, "under", SEED)
        with pytest.raises(ValueError):
            certify_severity(ordinal_records(**CLEAN), ALPHA, bad, "under", SEED)
    with pytest.raises(ValueError, match="direction"):
        certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "sideways", SEED)
    assert DIRECTIONS == ("under", "over", "both_sides_sum")


def test_a_foreign_subject_two_backends_or_two_rubrics_is_a_usage_error_naming_the_input():
    """The three input mistakes a severity gate can be handed, each refused before any number.

    A `choice` population carries no ordinal scale, so `1{Y > a}` is not defined on it -- that is the
    subject guard, and it is why the control's twin exists. Two backends is the
    certificate-names-one-subject correction this gate inherits from the ordinal set gate. Two rubric
    widths is the one this gate adds: the candidate domain 0..k-1 and the degenerate end of the family
    are both facts about ONE rubric, and a mixed population has no single ceiling to be pushed into.
    """
    with pytest.raises(ValueError, match="qtype"):
        certify_severity(_as_choice(ordinal_records(**CLEAN)), ALPHA, DELTA, "under", SEED)
    mixed = ordinal_records(**CLEAN)[:600] + ordinal_records(n=600, seed=8, backend="other")
    with pytest.raises(ValueError, match="backend"):
        certify_severity(mixed, ALPHA, DELTA, "under", SEED)
    two_rubrics = (ordinal_records(n=600, seed=9, k=4) + ordinal_records(n=600, seed=9, k=5))
    with pytest.raises(ValueError, match="rubric"):
        certify_severity(two_rubrics, ALPHA, DELTA, "under", SEED)


def test_the_split_is_the_set_gate_s_own_and_not_a_third_copy():
    """Spec §6.4's "on the same records" is a property of the code, so it is called, not mirrored.

    `severity.py` uses `certify_score.split_cal` rather than holding its own copy, which is the only
    way the two gates are guaranteed to describe the same held-out cases. The case/record counts are
    asserted because they are what a copy would drift on: balancing the calibration half by CASE
    count instead of by record count turns (600, 600) records into (201, 999) -- the P-F2a drift the
    task-2 review measured red -- and this row's numbers move with it.
    """
    recs = ordinal_records(**CLEAN)
    cert = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    cal, ev, _ = split_cal(recs, SEED)
    assert cert.n_cal == len(cal) == 600 and cert.n_eval == len(ev) == 600
    assert cert.meta["n_cal_cases"] == 200 and cert.meta["n_eval_cases"] == 200
    assert cert.meta["cal_ids"] == sorted(r.id for r in cal)
    assert cert.meta["eval_ids"] == sorted(r.id for r in ev)
    assert set(_case_groups(cal)) & set(_case_groups(ev)) == set()


# ----------------------------------------------------------------- R-160: one joint level, one owner --


def test_the_two_gates_publish_one_joint_level_and_not_two_conventions():
    """R-160's deliverable: the same number, computed one way, by one shared owner.

    `correction.joint_level` is that owner -- it says so in its own docstring, and its
    `JOINT_LEVEL_RULE` names the convention -- and the severity gate CALLS it instead of restating
    `1 - 3*delta`. The set shape still evaluates `1 - N_CLAIMS * delta` itself, so the agreement is
    asserted here rather than assumed: at the published rubric both gates say 0.85, and an edit that
    moves either the envelope count or the combination rule reddens this row in the lane that did not
    make it.
    """
    recs = ordinal_records(**CLEAN)
    sev = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    sets = certify_score(recs, ALPHA, ALPHA, DELTA, seed=SEED)
    assert sev.level == sets.level == 0.85, (sev.level, sets.level)
    assert sev.level == joint_level({"alpha": DELTA, "beta": DELTA}, n_groups=1,
                                   n_claims=SEVERITY_N_CLAIMS)
    assert SEVERITY_N_CLAIMS == N_CLAIMS == 3
    assert any(JOINT_LEVEL_RULE in line for line in sev.envelope), sev.envelope
    loose = certify_severity(recs, ALPHA, 0.01, "under", SEED)
    assert loose.level == joint_level({"alpha": 0.01, "beta": 0.01}, 1, N_CLAIMS) == 0.97
    assert loose.level != sev.level


def test_the_severity_gate_ships_the_union_bound_the_spec_names_and_says_which_reading_it_rejects():
    """R-160 settled from the spec, not by preference, and the resolution travels in the artefact.

    §5.3 fixes coverage on one split and bounds the conditional error on the other, and says the pair
    "carries a union-bound confidence level"; §6.1 certifies two one-sided risks "each ... certified
    separately and both reported" at `alpha_miss` and `alpha_block`, i.e. one budget per failure
    event. A union bound over DISTINCT events is a SUM of their budgets, and `correction.joint_level`
    bounds that sum by `n_claims * max(budgets)`, which is conservative for every assignment of
    budgets to envelopes. So the 0.85-against-0.90 discrepancy R-160 recorded is NOT a max-versus-sum
    disagreement at all: with every envelope paid at the same budget the two readings are the same
    arithmetic, and `1 - (alpha + beta)` = 0.90 is the level of the §5.3 PAIR -- two envelopes. What
    decides the published number is the ENVELOPE COUNT, which each gate must state, and which the
    band function below demonstrates by publishing 0.95 for its one envelope under the same rule.
    """
    sev = certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "under", SEED)
    assert sev.level == joint_level({"alpha": DELTA, "beta": DELTA}, 1, 3) == 0.85
    pair_only = joint_level({"alpha": DELTA, "beta": DELTA}, 1, 2)
    assert pair_only == 1.0 - (DELTA + DELTA) == 0.90, pair_only
    assert pair_only != sev.level
    unequal = joint_level({"alpha": 0.05, "beta": 0.01}, 1, 3)
    assert unequal == 1.0 - 3 * 0.05, unequal
    assert unequal != 1.0 - 3 * (0.05 + 0.01)
    assert "n_claims * max(alpha, beta)" in JOINT_LEVEL_RULE
    band = tolerance_band(ordinal_records(**CLEAN), ALPHA, DELTA, SEED)
    assert band["n_claims"] == 1 and band["level"] == joint_level({"alpha": DELTA, "beta": DELTA},
                                                                 1, 1) == 0.95
    assert band["level"] != sev.level


def test_severity_uses_the_binomial_owner_and_defines_no_arithmetic_of_its_own():
    """R-19/R-127: the no-new-machinery claim is proved by identity, not asserted in prose.

    GREEN-ON-ARRIVAL as a set; the change that reddens any line is a second definition of that
    arithmetic appearing in `severity.py` -- a local tail, a local quantile, or a local rounding.
    """
    import autorate.certify_score as score_gate
    import autorate.severity as severity
    from autorate import ordinal, tails
    assert severity.clopper_pearson_upper is tails.clopper_pearson_upper
    assert severity.canonicalise_bound is canonicalise_bound
    assert severity.split_cal is score_gate.split_cal
    assert severity.mode_index is ordinal.mode_index


# ------------------------------------------------------------- Task 4: the tolerance band, both ways --


def test_the_search_and_a_scan_of_the_same_bounds_must_agree_or_the_run_raises(monkeypatch):
    """§6.2 names a binary search; this is the guard that says when a search is not allowed to run.

    `tails.clopper_pearson_upper` already failed this project once by inverting a tail into a bound
    BELOW its own observed rate (the `binom_cdf` underflow), and that class of drift can leave the
    COUNTS monotone while the BOUNDS are not -- which is exactly the state that turns a binary search
    into a coin toss. So `_search` cross-checks its answer against a scan of the same canonical array
    and raises `ArithmeticError` (drift in this project's own published arithmetic, the convention
    `tails` uses for the same hazard) instead of publishing a level that bounds nothing.

    GREEN-ON-ARRIVAL, because no honest population reaches the state: the arm manufactures it by
    patching the inversion this module imported, giving candidate 0 (10 violating cases) a bound of
    0.010 while candidate 2 keeps the true 0.052 -- feasible at both ends, ordered nowhere. The leak
    arms show the patch is exactly as wide as the guard: `severity.clopper_pearson_upper` is the real
    object again after `undo()`, and the same run then certifies `ahat=3` as it does everywhere else in
    this file. The change that reddens the row for real is a `_search` that stopped checking itself.
    """
    import autorate.severity as severity

    real = severity.clopper_pearson_upper
    monkeypatch.setattr(severity, "clopper_pearson_upper",
                        lambda k, n, d: 0.010 if k == 10 else real(k, n, d))
    with pytest.raises(ArithmeticError, match="not monotone"):
        certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "under", SEED)
    monkeypatch.undo()
    assert severity.clopper_pearson_upper is real
    ok = certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "under", SEED)
    assert ok.feasible is True and ok.ahat == 3, ok.summary()


def test_tolerance_band_is_the_same_search_as_6_2_and_adds_no_machinery():
    """Task 4 Step 1: `d` indexes a monotone family, so the search IS §6.2's, and this row proves it.

    Two derivations of the same `d` must agree: the production one, and a test-side linear scan over
    the band family recomputed from `tails.clopper_pearson_upper` on case groups this file builds. If
    `tolerance_band` grew its own search, its own tail or its own anchor, the two part company -- and
    the off-by-one drift this project has already been bitten by (`>` written as `>=`) moves `d` from
    1 to 2 on the `d == 1` row below, which is where that plant is caught.
    """
    recs = ordinal_records(**CLEAN)
    cert = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    band = tolerance_band(recs, ALPHA, DELTA, SEED)
    assert band["feasible"] is True, band
    assert band["ahat"] == cert.ahat == 3
    cal, _ev, _ = split_cal(recs, SEED)
    groups = _case_groups(cal)
    n = len(groups)
    counts = {d: sum(1 for g in groups.values()
                     if any(abs(r.gold_index - report_level(r.probs, cert.ahat)) > d for r in g))
              for d in range(K)}
    assert [counts[d] for d in range(K)] == [123, 76, 37, 0, 0], counts
    expected = min(d for d in counts if _hand_bound(counts[d], n) <= ALPHA)
    assert band["d"] == expected == 3, (band["d"], expected)
    assert band["bound"] == _hand_bound(0, n)
    assert band["n_cal_cases"] == n == 200
    assert band["alpha"] == ALPHA and band["delta"] == DELTA and band["seed"] == SEED


def test_a_task_that_never_misses_by_more_than_one_level_yields_a_band_of_one():
    """Task 4's own arm: d == 1 on a one-level-error distribution, and the band is not the floor."""
    band = tolerance_band(_mirror_scale(ordinal_records(**PLAN)), ALPHA, DELTA, SEED)
    assert band["feasible"] is True, band
    assert band["ahat"] == 0, band
    assert band["d"] == 1, band
    assert band["bound"] <= ALPHA
    # 145 of the 200 calibration cases are off by exactly one level and none by more, which is the
    # whole content of "the answer is never off by more than one level".
    assert band["missing_cases"] == 145 and band["violating_cases"] == 0, band
    assert band["exact_cases"] + band["missing_cases"] == band["n_cal_cases"] == 200


def test_d_can_never_be_reported_as_zero_while_any_certified_case_missed():
    """The guard's own arithmetic (Task 4 Step 1): d = 0 claims exactness, so a miss refutes it.

    `d == 0` says `P(|Y - ahat(X)| > 0) <= alpha` -- the rule is exact except on at most alpha of the
    cases. Both sides of that equivalence are pinned: a model that is never wrong really does yield
    d = 0 (so the guard is not a ban on small bands), and on the plan's fixture, where the certified
    floor lifts every case to the top of the rubric and 161 of 200 come out wrong, `d` is not
    published at all -- the refusal dict has no `d` key, because a refusal carrying a band would be a
    number a reader could act on.
    """
    clean = tolerance_band(ordinal_records(**EXACT), ALPHA, DELTA, SEED)
    assert clean["feasible"] is True and clean["ahat"] == 0, clean
    assert clean["missing_cases"] == 0 and clean["d"] == 0, clean
    missed = tolerance_band(ordinal_records(**PLAN), ALPHA, DELTA, SEED)
    assert missed["feasible"] is False, missed
    assert "d" not in missed and "bound" not in missed, sorted(missed)
    assert missed["missing_cases"] == 161 and missed["ahat"] == K - 1, missed


def test_the_whole_rubric_band_is_a_refusal_and_the_first_emitter_of_the_fifth_reason():
    """R-92b: `no_automation_at_coverage` is emitted first from `severity.py`, and it is the first kind.

    The state is `d = k - 1`: the smallest band the budget licenses is the whole rubric, which
    contains every level whatever the data said -- the vacuity `VACUOUS_QUANTILE` exists for, reached
    without any quantile. It is the FIRST kind, not the second, because more data would not change it,
    and that is measured rather than claimed: the obstruction is the mass at maximal error, so
    widening the calibration half from 200 to 2,000 cases shrinks the bound on the never-violated band
    and leaves the bound on `d = k - 2` sitting at five times the budget.
    """
    band = tolerance_band(ordinal_records(**PLAN), ALPHA, DELTA, SEED)
    assert band["feasible"] is False
    assert band["reason"] == Reason.NO_AUTOMATION_AT_COVERAGE.value, band
    assert "d" not in band and "bound" not in band, sorted(band)
    assert (band["alpha"], band["delta"], band["seed"]) == (ALPHA, DELTA, SEED)
    assert band["n_cal"] == 600 and band["n_cal_cases"] == 200 and band["rubric_levels"] == K
    assert band["envelope"], "a refusal is still conditioned by assumptions"
    assert "whole rubric" in band["detail"], band["detail"]

    grown = tolerance_band(ordinal_records(n=12000, seed=5, shift=0.9), ALPHA, DELTA, SEED)
    assert grown["reason"] == Reason.NO_AUTOMATION_AT_COVERAGE.value, grown
    assert grown["n_cal_cases"] == 2000, grown
    # The obstruction, counted from the definitions at both sizes: the cases that sit a whole rubric
    # away from the certified floor are 37 of 200 here and 396 of 2,000 there, and the exact binomial
    # upper bound on `d = k - 2` stays above three times the budget at both. That is what "more data
    # would not change this verdict" means, measured instead of asserted.
    obstruction = [(PLAN, 37, 200), (dict(n=12000, seed=5, shift=0.9), 396, 2000)]
    for kw, expected, n_cases in obstruction:
        population = ordinal_records(**kw)
        cal, _ev, _ = split_cal(population, SEED)
        groups = _case_groups(cal)
        assert len(groups) == n_cases, (kw, len(groups))
        at_second = sum(1 for g in groups.values()
                        if any(abs(r.gold_index - report_level(r.probs, K - 1)) > K - 2 for r in g))
        assert at_second == expected, (kw, at_second)
        assert _hand_bound(at_second, n_cases) > 3 * ALPHA, (kw, at_second, n_cases)


def test_an_empty_family_is_a_short_sample_and_is_the_other_reason():
    """The second kind, named and separated: at alpha=0.01 on 200 cases NOTHING is certifiable.

    Every severity family contains a candidate that never errs (the ceiling for a floor, the floor for
    a clip), so an empty family is never a fact about the task: it is `1 - delta**(1/n) > alpha`, a
    sample too short for any bound in the family to be informative -- which is what `n_below_min`'s
    own sentence says. The arm below proves it is the sample by re-running the same generator with
    twice the cases at the same alpha, which makes it certify.
    """
    tight = certify_severity(ordinal_records(**PLAN), 0.01, DELTA, "under", SEED)
    assert tight.feasible is False
    assert tight.reason == Reason.N_BELOW_MIN.value, tight.reason
    assert "200" in tight.meta["detail"], tight.meta["detail"]
    fixed = certify_severity(ordinal_records(n=2400, seed=5, shift=0.9), 0.01, DELTA, "under", SEED)
    assert fixed.feasible is True, fixed.summary()
    assert fixed.bound <= 0.01 and fixed.ahat == K - 1


def test_the_two_refusals_say_different_things_and_only_one_of_them_is_fixed_by_more_data():
    """I-10's distinction, measured rather than quoted: two refusals, two remedies.

    `n_below_min` responds to a bigger calibration half; `no_automation_at_coverage` does not. The
    pair below is the evidence: the same generator at sixty times the size turns the first refusal
    into a certificate and leaves the second refusal exactly where it was, with the same reason and
    the same whole-rubric obstruction.
    """
    small = certify_severity(ordinal_records(**PLAN), 0.01, DELTA, "under", SEED)
    grown = certify_severity(ordinal_records(n=12000, seed=5, shift=0.9), 0.01, DELTA, "under", SEED)
    assert small.reason == Reason.N_BELOW_MIN.value
    assert grown.feasible is True, grown.summary()
    band_small = tolerance_band(ordinal_records(**PLAN), ALPHA, DELTA, SEED)
    band_grown = tolerance_band(ordinal_records(n=12000, seed=5, shift=0.9), ALPHA, DELTA, SEED)
    assert band_small["reason"] == band_grown["reason"] == Reason.NO_AUTOMATION_AT_COVERAGE.value
    assert band_small["n_cal_cases"] == 200 and band_grown["n_cal_cases"] == 2000


def test_a_refusal_carries_its_budgets_and_no_headline_number():
    """§5.5's product: the reason and the budget pair travel inside the object, and the numbers do not."""
    refused = certify_severity(ordinal_records(**PLAN), 0.01, DELTA, "under", SEED)
    assert isinstance(refused, SeverityCertificate)
    assert refused.feasible is False and refused.reason in {r.value for r in Reason}
    for field in ("ahat", "bound", "price_bound", "override_bound", "measured_violation"):
        assert getattr(refused, field) is None, field
    assert (refused.alpha, refused.delta, refused.direction) == (0.01, DELTA, "under")
    assert refused.level == joint_level({"alpha": DELTA, "beta": DELTA}, 1, N_CLAIMS)
    for required in ("n_below_min", "alpha=0.010", "delta=0.050"):
        assert required in refused.summary(), (required, refused.summary())


def test_over_call_bound_is_direction_over_with_no_extra_machinery():
    """Task 4's second name: `over_call_bound(...)` is `certify_severity(..., direction="over")`."""
    recs = ordinal_records(**CLEAN)
    direct = certify_severity(recs, ALPHA, DELTA, "over", SEED)
    wrapped = over_call_bound(recs, ALPHA, DELTA, SEED)
    assert wrapped == direct, (wrapped.summary(), direct.summary())
    assert wrapped.direction == "over" and wrapped.feasible is True
    assert wrapped.bound <= ALPHA and wrapped.ahat == K - 1
    under = certify_severity(recs, ALPHA, DELTA, "under", SEED)
    assert under.ahat == 3 and under.bound == _hand_bound(3, 200)


def test_severity_band_is_the_one_sided_radius_around_the_model_s_own_answer():
    """R-92c's integer radius, anchored at the modal level rather than at the certified floor.

    Anchored at the floor it would be structurally 0 whenever the severity certificate is feasible --
    a function that can only return 0 is a decoration, not a radius -- so §6.2's band is measured
    around what the model reports. On the plan's fixture the answer is 1: "the truth is never more
    than one level above what the model said", at confidence 0.95, which is the sentence §6.3 was
    written to license. `None` is the honest answer when even a radius of the whole rubric cannot be
    bounded at this `n`, and the refusal that names that state belongs to the certificate, not here.
    """
    assert severity_band(ordinal_records(**PLAN), ALPHA, DELTA, SEED) == 1
    assert severity_band(ordinal_records(**CLEAN), ALPHA, DELTA, SEED) == 1
    assert severity_band(_mirror_scale(ordinal_records(**CLEAN)), ALPHA, DELTA, SEED) == 0
    assert severity_band(ordinal_records(**PLAN), 0.01, DELTA, SEED) is None


def test_the_severity_risk_target_is_monotone_because_the_rule_never_abstains_and_the_set_rule_does():
    """R-124: nothing here may say "looser coverage automates more". The measured shapes say otherwise.

    The set rule's automation is NOT monotone in alpha: on `build_ordinal(n=1200, repeats=3, seed=4)`
    at `seed=7` it automates 78 cases at alpha=0.01 and 74 at alpha=0.02, because a looser coverage
    target produces wider sets, and a wider set that is not a singleton is a refusal. The severity
    path IS monotone in its risk target for a structural reason -- it abstains on no case, so there is
    no empty certified set to grow -- and that contrast is G3's argument in the batch brief's own
    words: a rule that always answers can be made monotone and says nothing about which side it
    missed, while a set rule refuses where it cannot say. A sweep of either shape that came out
    monotone on the other's population would be the fixture, not the rule.
    """
    recs = ordinal_records(n=1200, repeats=3, seed=4)
    automated = []
    for a in (0.01, 0.02, 0.05, 0.10):
        cert = certify_score(recs, a, 0.95, DELTA, seed=7)
        assert cert.feasible is True, cert.summary()
        automated.append(cert.meta["automated_cases"])
    assert automated == [78, 74, 78, 87], automated
    assert automated != sorted(automated)

    clean = ordinal_records(**CLEAN)
    floors = [certify_severity(clean, a, DELTA, "under", SEED).ahat
              for a in (0.02, 0.05, 0.10, 0.20)]
    assert floors == [4, 3, 0, 0], floors
    assert floors == sorted(floors, reverse=True)


def test_the_summary_carries_the_side_the_guarantee_is_about_and_its_evidence_boundary():
    """Step 5's honest framing, as text a reader of the artefact actually sees."""
    cert = certify_severity(ordinal_records(**PLAN), ALPHA, DELTA, "under", SEED)
    text = cert.summary()
    for required in ("P(Y >", "synthetic ordinal data with known answers", "NeurIPS 2023",
                     "UAI 2023", "AAAI-26", "joint level", "alpha=0.050", "delta=0.050", "200"):
        assert required in text, (required, text)
    assert "coverage" not in text, text
    assert all(line for line in cert.envelope)
    assert cert.meta["rule"] == JOINT_LEVEL_RULE


def test_the_degenerate_end_is_stated_in_the_envelope_and_not_only_in_the_number():
    """A reader must be able to see that the certified floor IS the top of the rubric.

    On the plan's fixture the only level that meets the budget is `k-1`, so the rule reports a
    constant and replaces the model on 197 of 200 cases. That is a result, and the envelope says so
    instead of letting a 0.996 override rate read as normal; the mild population keeps the line off,
    so the sentence is a statement about the shape and not a boilerplate.
    """
    cert = certify_severity(ordinal_records(**PLAN), ALPHA, DELTA, "under", SEED)
    assert cert.ahat == K - 1
    assert cert.meta["candidate_domain"] == [0, 1, 2, 3, 4]
    assert any("constant" in line for line in cert.envelope), cert.envelope
    assert cert.override_bound > 0.9, cert.override_bound
    mild = certify_severity(ordinal_records(**CLEAN), ALPHA, DELTA, "under", SEED)
    assert not any("constant" in line for line in mild.envelope), mild.envelope
    assert mild.ahat < K - 1
