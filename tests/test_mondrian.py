"""G4's engine: refuse the thin slices by name, and never publish a worst-of-G without the correction.

Every row here is about a claim, not a code path. The claims are spec §8.1's: a group-conditional
guarantee is conditional on the slice and needs exchangeability *within* it, and the worst-of-G report
has to divide by the slice count the census produced or it is a false claim.

THE CONSTRUCTION, NAMED (the dispatch's requirement: if the pooled certificate and the per-slice
verdict never diverge, the fixture proves nothing). Eight families of unequal size, built by
`_family` below with the seeds printed on the fixture, at `alpha = beta = delta = 0.05`:

* `a`,`b`,`c`,`d`,`e` -- 700 cases each, sharp and correct. Certify at the corrected `alpha/8`.
* `risky` -- 150 cases, sharp but wrong 30% of the time. No certificate exists for it at
  `alpha/8`: its own 0.99375-quantile of 75 calibration scores is above 1 (`vacuous_quantile`), and
  its diagnostic curve says why -- 60 automated cases carrying 21 wrong ones, observed 0.35, bound
  0.508 against a 0.05 budget.
* `wide` -- 300 cases, sharp and correct, and STILL refused: at `alpha/8` its thin calibration half
  cannot set the quantile either. This is the row that shows the refusal is a property of the slice's
  own evidence, not of the population being bad.
* `tiny` -- 10 cases. Below `MIN_CASES_PER_SLICE` (120 = MIN_CAL + MIN_EVAL, the two halves the
  two-way construction of §5.3 runs on), so it is refused by name and never certified.

The POOLED certificate over these same 3,960 records is feasible: autorate 0.95808, conditional error
bound 0.013412, inside the 0.05 budget. So the run that ignores slices issues a permission the run
that conditions on them refuses three times over. That divergence is the fixture's whole point, and it
is constructed on purpose: the risky and wide cases are 11% of the pool, and at the pooled `alpha`
they land in the pool's *refusal* bucket rather than its error count, which is exactly how a pool
hides a slice -- by reclassifying it as abstention.

Everything here is a constructed population, labelled as constructed. The real collapsed slices the
Plan C lane measured (`de`: 0 of 1,487 automated; `sw`: 39 automated, 13 wrong, bound 0.477) are not
read into these rows: `km` is measured but not yet published, and R-158 says not to read machine paths
into a committed test. The slice-level real-data row is a named follow-up (obligation #68).

TWO FIXTURES, BECAUSE THE UNIT THEY GUARD DIFFERS. `_family` below emits ONE record per case
(`repeat=0`, a per-record unique `id`, no `case_id`), so in its 3,960 rows `cases == records` and no
assertion about which of the two the size floor counts can fail -- plant `len(members)` in place of
the case set at `certify_choice.py:539` and every row here stays green while the artefact publishes a
slice's record count as its case count. That inertness is F-1 of the Task 2 review, and it is the
third time this session a `repeats=1` fixture has made a case/record guard blind. `_case_slice` is the
disagreeing-repeat arm: a case owns 1-3 records whose `id`, `repeat` and drawn `u` differ, and whose
ANSWER differs too for the `km` slice, so the floor's unit is contradicted in both directions.
`tests/_records.py::choice_record` is the builder it goes through, because a fixture shaped by only
one consumer certifies a fiction (R-69).
"""
from __future__ import annotations

import json
import random
from dataclasses import fields

import pytest

from autorate.case_count import case_key
from autorate.certificate import N_CLAIMS, Certificate
from autorate.certify_choice import (MIN_CAL, MIN_CASES_PER_SLICE, MIN_EVAL, GroupsCertificate,
                                     certify_choice, certify_groups)
from autorate.correction import GROUP_FLOOR_MESSAGE, bonferroni
from autorate.groups import by_group
from autorate.records import Record
from autorate.report import ALPHA, BETA

from _records import choice_record

FAMILIES = (("a", 700, 8.0, 0.0), ("b", 700, 8.0, 0.0), ("c", 700, 8.0, 0.0), ("d", 700, 8.0, 0.0),
            ("e", 700, 8.0, 0.0), ("risky", 150, 8.0, 0.30), ("tiny", 10, 8.0, 0.0),
            ("wide", 300, 8.0, 0.0))


def _family(name, n, sharpness=8.0, seed=1, k=4, error_rate=0.0, backend="synthetic",
            unlabelled=0):
    """Labelled synthetic decisions, one slice key per family.

    The generator is `tests/test_certify_choice.py::_records`, copied only in its parameters and not
    in its identity: `error_rate` is what makes a slice able to be WRONG, because a fixture that
    cannot be wrong cannot be shown refusing one (that file's own lesson). `u` is drawn, not fixed --
    APS randomisation at ties is part of what a slice's evidence is.
    """
    rng = random.Random(seed)
    out = []
    for i in range(n):
        g = rng.randrange(k)
        peaked = g if rng.random() >= error_rate else (g + 1 + rng.randrange(k - 1)) % k
        w = [1.0] * k
        w[peaked] = sharpness
        tot = sum(w) + k * 0.05
        p = [round(x / tot, 4) for x in w]
        p[peaked] = round(p[peaked] + (1.0 - sum(p)), 4)
        options = tuple("opt%d" % j for j in range(k))
        gold = None if i < unlabelled else options[g]
        out.append(Record(id="%s-%d" % (name, i), qtype="choice", backend=backend, repeat=0,
                          options=options, probs=tuple(p), gold=gold, predicted=options[peaked],
                          slices={"family": name}, scores={}, seed=seed, u=rng.random(), meta={}))
    return out


def _ballot(sharpness: float, peaked: int, k: int) -> tuple:
    """One probability vector: `sharpness` on `peaked`, mass elsewhere, summing to 1 by construction.

    Same arithmetic as `_family`'s inline ballot, kept local because moving it would re-roll the
    3,960-row fixture above and every published number that rides on it.
    """
    w = [1.0] * k
    w[peaked] = sharpness
    tot = sum(w) + k * 0.05
    p = [round(x / tot, 4) for x in w]
    p[peaked] = round(p[peaked] + (1.0 - sum(p)), 4)
    return tuple(p)


def _case_slice(value, n_cases, repeats=1, seed=1, wrong_repeats=0, k=4, sharpness=8.0):
    """`n_cases` independent CASES, each carrying `repeats` records that are not the same row.

    This is the arm `_family` cannot express, and the reason F-1 exists: one-record-per-case fixtures
    make `cases == records`, so the size floor's unit -- CASES, per `MIN_CASES_PER_SLICE`'s own
    docstring -- cannot be contradicted by any assertion. Here `case_id` is shared by a case's
    records while `id`, `repeat` and the drawn `u` differ, so the two counts disagree by a factor of
    `repeats` and the unit becomes falsifiable.

    `wrong_repeats` is how many of a case's records, counted from the last, put forward a label that
    is NOT the gold one. With it >= 1 the repeats genuinely disagree about the ANSWER, which is what
    makes a record-denominated error count and a case-denominated one tell different stories about
    the same slice. The committed archive does not exercise that: its three repeats per case carry
    byte-identical ballots (pinned by `tests/test_report_prose.py`), which is why 3/96 == 1/32 there
    and why a guard built on data of that shape is blind. Even with every repeat correct the two
    units still split, because a case automates only when EVERY one of its records does
    (`case_count.count_outcome`): measured on the `zh` slice below, 295 of 300 evaluation RECORDS
    automate while 95 of its 100 evaluation CASES do -- 0.98333 against the published 0.95.

    Built through `choice_record` (R-69's shared factory), so every validation a corpus row passes a
    fixture passes too, and `id`/`case_id` are passed by keyword because they are the same shape and
    can trade places without any assertion noticing.
    """
    rng = random.Random(seed)
    options = tuple("opt%d" % j for j in range(k))
    out = []
    for i in range(n_cases):
        case_id = "%s-%04d" % (value, i)
        gold = options[i % k]
        for rep in range(repeats):
            wrong = wrong_repeats and rep >= repeats - wrong_repeats
            peaked = (i % k + 1 + rep % (k - 1)) % k if wrong else i % k
            out.append(choice_record(id="%s.r%d" % (case_id, rep), case_id=case_id, repeat=rep,
                                     options=options, probs=_ballot(sharpness, peaked, k),
                                     gold=gold, predicted=options[peaked], u=rng.random(),
                                     slices={"language": value}))
    return out


@pytest.fixture(scope="module")
def repeat_records():
    """540 cases over 1,020 records, so one run holds a slice in each branch of the unit.

    km: 40 cases x 3 records (120), two of the three records per case answering WRONG.
    zh: 200 cases x 3 records (600), all answering right, the set still varying with each `u`.
    en: 300 cases x 1 record (300) -- the control where the two units genuinely coincide.
    """
    return (_case_slice("km", 40, repeats=3, seed=901, wrong_repeats=2)
            + _case_slice("zh", 200, repeats=3, seed=902)
            + _case_slice("en", 300, repeats=1, seed=903))


@pytest.fixture(scope="module")
def repeat_run(repeat_records):
    return certify_groups(repeat_records, alpha=ALPHA, beta=BETA, delta=0.05,
                          groups=("language",), seed=7)


def test_the_repeats_actually_disagree_so_the_unit_guard_has_a_premise(repeat_records):
    """The fixture's own premise, forced from the records rather than assumed from the parameters.

    Every case/record guard written this session has been made inert by a fixture that quietly was
    one-record-per-case (`tests/test_mondrian.py::_family`, B2 Task 2's MAJ-1, the drift lane's F3),
    so the premise gets its own row: if `_case_slice` ever collapses to `repeats=1` the guards below
    stop being guards, and this is the row that says so out loud instead of passing.
    """
    by_case = {}
    for r in repeat_records:
        by_case.setdefault(case_key(r), []).append(r)
    assert len(repeat_records) == 1020 and len(by_case) == 540, (
        "1,020 rows are 540 observations; a floor that counted rows would claim 480 extra cases")
    assert {len(members) for members in by_case.values()} == {1, 3}, "not all cases are one row"
    km = [members for members in by_case.values() if members[0].slices["language"] == "km"]
    assert len(km) == 40 and {len(m) for m in km} == {3}
    within = km[0]
    assert len({r.id for r in within}) == 3 and len({r.u for r in within}) == 3, (
        "three records of one case that are not the same row")
    assert [r.predicted for r in within].count(within[0].gold) < len(within), (
        "km's repeats must DISAGREE about the answer, or the case is just three copies of a record")
    assert all(len({r.case_id for r in m}) == 1 for m in by_case.values()), (
        "a case whose repeats carry different case_ids is two observations, not one")


def test_the_size_floor_counts_cases_and_never_the_records_of_those_cases(repeat_run):
    """F-1's guard, in the direction that REFUSES: `len(members)` for the case count reddens this row.

    Plant `n_cases = len(members)` at `certify_choice.py:539` and km's 120 rows clear the 120-case
    floor, so `n_min_violations` goes empty, the census publishes 120 where the slice holds 40
    independent observations, and the slice's refusal becomes `empty_feasible_set` -- a different
    story about a different unit. Every one of those moves is asserted here in both directions: the
    published count IS the case count and IS NOT the record count.

    GREEN ON ARRIVAL against the shipped code, which already counts cases
    (`len({case_key(r) for r in members})`). The row is not evidence that the code was wrong; it is
    the guard that had been missing, and the plant in its docstring is what makes it one.
    """
    census = {row["group"]: row for row in repeat_run.slice_census}
    assert census["km"]["records"] == 120 and census["km"]["cases"] == 40
    assert census["km"]["cases"] != census["km"]["records"], (
        "the fixture has to keep the two units apart or this row guards nothing")
    assert [row["group"] for row in repeat_run.n_min_violations] == ["km"], (
        "40 cases is below MIN_CAL + MIN_EVAL = 120; 120 records is not, and the difference is the "
        "whole finding")
    row = repeat_run.n_min_violations[0]
    assert row["n"] == 40 and row["floor"] == MIN_CASES_PER_SLICE
    assert row["n"] != census["km"]["records"], "the refusal may not publish the record count as n"
    assert "holds 40 independent cases" in row["reason"], row["reason"]
    assert "holds 120 independent cases" not in row["reason"], row["reason"]
    assert repeat_run.per_group["km"].reason == "n_below_min", repeat_run.per_group["km"].reason
    assert repeat_run.thinnest == "km"
    summary = repeat_run.summary()
    assert "km(n=40)" in summary and "km(n=120)" not in summary, summary
    assert sum(census[name]["cases"] for name in census) == 540
    assert sum(census[name]["records"] for name in census) == 1020
    assert sum(census[name]["cases"] for name in census) != sum(
        census[name]["records"] for name in census), (
        "a run whose published case census equals its record census has no unit to guard")


def test_a_slice_that_clears_the_floor_on_cases_still_publishes_the_case_count(repeat_run):
    """The other direction: a case-heavy slice certifies, and its `n` is still not its row count.

    zh holds 600 records over 200 cases, so BOTH numbers clear the 120 floor and the refusal row
    above could not catch a record-denominated census here. It is caught on the published count
    instead: the artefact states 200, the same census row states 600 as the record count, and the
    slice's autorate is 95/100 CASES (0.95) where the record reading of the same evaluation half is
    295/300 (0.98333). A plant that counts rows makes `slice_cases["zh"] == 600` and reddens this row
    without moving a verdict, which is the half of F-1 the floor branch alone cannot show.

    GREEN ON ARRIVAL; reddened by `certify_choice.py:539` -> `len(members)`, and by any change that
    makes the certificate's autorate a record rate.
    """
    census = {row["group"]: row for row in repeat_run.slice_census}
    assert census["zh"]["cases"] == 200 and census["zh"]["records"] == 600
    assert repeat_run.slice_cases["zh"] == 200 != 600
    zh = repeat_run.per_group["zh"]
    assert zh.feasible is True, zh.summary()
    assert zh.meta["automated_cases"] == 95 and zh.meta["n_eval_cases"] == 100
    assert zh.meta["automated"] == 295 and zh.n_eval == 300
    assert zh.autorate == pytest.approx(95 / 100), (
        "the published rate is cases over cases: %r" % zh.autorate)
    assert zh.autorate != zh.meta["automated"] / zh.n_eval, (
        "the record reading of this slice is 0.98333; a certificate that published it would be "
        "naming a unit the bound is not computed on")
    assert repeat_run.slice_cases["en"] == 300 == census["en"]["records"], (
        "the one-record-per-case slice is the control: cases and records agree there, and only there")
    payload = repeat_run.to_dict()
    assert payload["slice_cases"] == {"en": 300, "km": 40, "zh": 200}, payload["slice_cases"]
    assert 120 not in payload["slice_cases"].values() and 600 not in payload["slice_cases"].values(), (
        "a record count published in the case map is the artefact-side half of F-1")


def test_the_floor_is_still_the_sum_of_the_two_halves_when_the_units_disagree(repeat_run):
    """The floor's owner, re-checked on a population where cases and records differ.

    `test_the_floor_and_the_pools_own_minima_have_one_owner` pins `MIN_CASES_PER_SLICE == MIN_CAL +
    MIN_EVAL` on one-record-per-case data, where a row and a case are the same thing. This row pins
    the same constant against the census of a repeat-bearing population: km is refused with its own
    case count, and `cases == records` is asserted to be FALSE for it, so the arithmetic the floor
    compares (40) is the arithmetic the split actually gets to halve (120 rows over 40 cases).
    """
    assert repeat_run.meta["min_cases_per_slice"] == MIN_CAL + MIN_EVAL == 120
    km = next(row for row in repeat_run.slice_census if row["group"] == "km")
    assert km["cases"] == 40 < 120 <= km["records"] == 120, (
        "the slice clears the floor on rows and falls below it on cases: that is the unit")
    assert GROUP_FLOOR_MESSAGE in repeat_run.n_min_violations[0]["reason"]
    assert repeat_run.worst_claim["n_groups"] == 3 == repeat_run.n_groups


@pytest.fixture(scope="module")
def recs():
    out = []
    for index, (name, n, sharpness, error_rate) in enumerate(FAMILIES):
        out += _family(name, n, sharpness=sharpness, seed=400 + index, error_rate=error_rate)
    return out


@pytest.fixture(scope="module")
def cert(recs):
    return certify_groups(recs, alpha=ALPHA, beta=BETA, delta=0.05, seed=7, groups=("family",))


@pytest.fixture(scope="module")
def pooled(recs):
    return certify_choice(recs, alpha=ALPHA, beta=BETA, delta=0.05, seed=7)


def test_the_pooled_verdict_and_the_per_slice_verdict_diverge_on_this_population(cert, pooled):
    """The fixture's reason for existing: one says "automate", the other says "nothing is known".

    Green on arrival against this construction, and reddened by any change that makes the pool and the
    slices agree: a plant that certifies each slice at the UNCORRECTED alpha (no division) turns
    `wide` and `risky` feasible and this row goes red, because the divergence was bought with the
    correction rather than with the fixture.
    """
    assert pooled.feasible is True, pooled.summary()
    assert pooled.autorate > 0.9 and pooled.conditional_error_bound <= BETA
    refused = sorted(name for name, c in cert.per_group.items() if not c.feasible)
    assert refused == ["risky", "tiny", "wide"], (
        "three of the eight slices have no certificate at all")
    assert cert.n_groups == 8 and len(cert.per_group) == 8
    assert cert.any_slice_refused is True
    # The pool's comfort and the slices' refusal are about the SAME records: the case sets are not
    # disjoint, and the pool is computed over all eight families.
    assert set(cert.slice_cases) == {"a", "b", "c", "d", "e", "risky", "tiny", "wide"}
    assert sum(cert.slice_cases.values()) == 3960


def test_a_slice_too_small_to_bound_is_refused_by_name_not_averaged_away(cert):
    """§8.1's refusal, published under the name spec §10 gives it (line 208, mandated at line 214).

    RED in two directions, both named here because this row used to pin the opposite: its last
    assertion was `assert not hasattr(cert, "n_min_violations")` (R-149/2's deferral, which recorded
    that B3 Task 5 owns the name and the shape change together), and B3 Task 5 is this commit.
    Reverting the rename reddens the first line below with `AttributeError: 'GroupsCertificate' object
    has no attribute 'n_min_violations'`; re-adding `refused_by_size` to `to_dict` as a copy of the
    same rows reddens the "one fact, one name" line.
    """
    assert cert.n_min_violations == [{
        "group": "tiny", "n": 10, "floor": MIN_CASES_PER_SLICE,
        "reason": cert.n_min_violations[0]["reason"]}], "named, with its own n"
    assert GROUP_FLOOR_MESSAGE in cert.n_min_violations[0]["reason"]
    assert "MIN_CAL + MIN_EVAL" in cert.n_min_violations[0]["reason"], (
        "the floor names its owner, so a reader can tell a taste from a threshold")
    assert cert.thinnest == "tiny"
    # Averaged away would mean absent: the slice still holds a certificate and a census row, and both
    # say the same thing about it.
    assert cert.per_group["tiny"].feasible is False
    assert cert.per_group["tiny"].autorate is None
    assert cert.per_group["tiny"].conditional_error_bound is None
    tiny_row = next(row for row in cert.slice_census if row["group"] == "tiny")
    assert tiny_row["cases"] == 10 and tiny_row["records"] == 10
    # This equality is the FIXTURE's collapse, not a property of the floor: `_family` emits one
    # record per case, so on this population no assertion can tell the two units apart. The rows that
    # can are `test_the_size_floor_counts_cases_and_never_the_records_of_those_cases` and its
    # companion, which use `_case_slice`.
    summary = cert.summary().lower()
    assert "refused" in summary or "not certified" in summary, cert.summary()
    payload = cert.to_dict()
    assert "n_min_violations" in payload, (
        ":214 -- a serialized certificate lacking the key fails validation")
    assert "refused_by_size" not in payload, (
        "one fact, one name: the retired field must not ride along beside the spec's, because a reader "
        "who finds both cannot tell which one a loader trusts")
    assert "tiny(n=10)" in cert.summary(), "the summary names the slice, not just the count"


def _rebuilt(run, **overrides):
    """The same run, re-constructed with the named fields overridden, so a shape guard is reachable.

    `certify_groups` cannot be coaxed into returning a run without the spec's key -- the field has a
    default -- and the dataclass is frozen, so the only way to prove the guard bites rather than reads
    as decoration is to rebuild the object with the field absent.
    """
    kwargs = {f.name: getattr(run, f.name) for f in fields(run)}
    kwargs.update(overrides)
    return GroupsCertificate(**kwargs)


def test_an_empty_n_min_violations_is_a_fact_and_a_missing_one_is_a_shape_violation(cert):
    """§10:214's asymmetry in both directions: an empty list states a fact, an absent key breaks shape.

    Reddened by the two mutations this row exists to refuse. (1) A guard written `if not
    self.n_min_violations: raise` -- copying `envelope`'s NON-EMPTINESS enforcement at
    `certificate.py:243-244` where the brief asked for its enforcement STYLE -- reddens the `[]` lines,
    because a run in which no slice fell below the floor has something true to say and must still
    serialize the key; the published language run IS that case, so this is not a hypothetical.
    (2) Deleting the presence guard reddens the `None` line. Neither direction may be dropped.
    """
    clears_floor = certify_groups(_family("ok", 200, sharpness=8.0, seed=6), groups=("family",), seed=7)
    assert clears_floor.n_min_violations == [], clears_floor.to_dict()["n_min_violations"]
    payload = clears_floor.to_dict()
    assert "n_min_violations" in payload and payload["n_min_violations"] == [], (
        "the key is the shape and the empty list is the fact: a serialization lacking it fails "
        "validation even when there is nothing to report")
    assert json.loads(clears_floor.to_json())["n_min_violations"] == [], (
        "the bytes a reader loads must carry the key, not only the in-process mapping")
    with pytest.raises(ValueError, match="n_min_violations"):
        _rebuilt(cert, n_min_violations=None), "absence is refused at construction, not at the reader"
    assert _rebuilt(cert, n_min_violations=[]).to_dict()["n_min_violations"] == [], (
        "emptiness is legal: the guard polices presence")


def test_the_old_field_name_is_refused_rather_than_read_as_an_alias(cert):
    """A shape change is a shape change: nothing on the object or its bytes answers to the old name.

    Reddened by the compatibility bridge the brief forbids -- an alias attribute, or a `to_dict` that
    wrote `refused_by_size` beside `n_min_violations` so an old reader keeps working -- would pass every
    other row in this file while leaving one published fact with two names. The loader side of the same
    refusal (bytes that carry only the retired name) is
    `tests/test_slice_surface.py::test_a_slice_artefact_written_under_the_retired_name_is_refused`.
    """
    payload = cert.to_dict()
    assert "refused_by_size" not in payload, sorted(payload)
    assert getattr(cert, "refused_by_size", None) is None, (
        "no alias attribute: the retired name must not resolve to the new list")
    assert [row["group"] for row in payload["n_min_violations"]] == ["tiny"], sorted(payload)
    assert json.loads(cert.to_json()).get("refused_by_size") is None, (
        "the serialized bytes carry one name for the one list")


def test_the_floor_and_the_pools_own_minima_have_one_owner(cert):
    """`MIN_CASES_PER_SLICE == MIN_CAL + MIN_EVAL`, because the floor IS the two halves.

    Green on arrival: the constant is defined as that sum, so no plant in this file reddens it -- it
    reddens the moment someone restates the floor as a bare number, which is how a threshold starts
    meaning something its author did not intend. The slice that lands exactly in the gap between the
    two is the proof the sum is not decoration: a 119-case slice has enough records for one half of
    the split and not the other, and is refused here rather than certified thin.
    """
    assert MIN_CASES_PER_SLICE == MIN_CAL + MIN_EVAL == 120
    thin = _family("gap", 119, sharpness=8.0, seed=5) + _family("ok", 200, sharpness=8.0, seed=6)
    run = certify_groups(thin, groups=("family",), seed=7)
    assert [row["group"] for row in run.n_min_violations] == ["gap"]
    assert run.per_group["gap"].feasible is False
    assert run.per_group["ok"].feasible is True, "the neighbour is not punished by the thin slice"


def test_the_worst_of_g_claim_is_stated_at_the_corrected_level_and_the_work_is_visible(cert):
    """G, `n_groups`, the uncorrected budgets and the corrected ones are all on the artefact.

    The family level is CONSTANT in the slice count -- `1 - n_claims * delta`, the number a single
    pooled certificate already publishes -- and that is the correction working, not a no-op: each
    slice pays `delta / G` for each of its `N_CLAIMS` bounds, so `G * N_CLAIMS * (delta/G)` stays at
    `N_CLAIMS * delta` however many slices the census produced. See `correction.py`'s module
    docstring for the R-158 derivation; this row is the same claim at the certificate surface.
    """
    g = cert.n_groups
    assert cert.level == pytest.approx(1.0 - N_CLAIMS * cert.delta)
    assert cert.corrected_alpha == pytest.approx(ALPHA / g)
    assert cert.corrected_delta == pytest.approx(0.05 / g)
    assert bonferroni(0.05, g) == cert.corrected_alpha == cert.corrected_delta, (
        "one division, one owner: the level the certifier spends is the correction module's, not a "
        "restatement of it")
    assert g * N_CLAIMS * cert.corrected_delta == pytest.approx(N_CLAIMS * 0.05), (
        "the union the family level pays for, written out")
    for name, slice_cert in cert.per_group.items():
        assert slice_cert.delta == cert.corrected_delta, name
        assert slice_cert.level > cert.level, (
            "%s: a slice is individually MORE confident than the family, because it paid 1/G of the "
            "budget -- if this ever inverts, the division went the wrong way" % name)
    text = cert.summary()
    for needle in ("8 slices", "delta=0.050", "0.006250", "uncorrected alpha=0.050"):
        assert needle in text, text
    assert any("worst-of-8" in line for line in cert.envelope), cert.envelope


def test_the_envelope_says_what_the_envelope_means_and_its_printed_product_is_its_own_arithmetic(
        cert):
    """The line that carries a formula has to print the formula's value, not a neighbouring one.

    Found while writing this file, and pinned because it is the defect class the drift review named
    (MAJOR-C2: a guard whose asserted fields are all `None` proves nothing): the first version of the
    correction line printed "the family risk is 8 x 3 x 0.006250 = 1.2000 and the joint level is
    -0.2000" -- the operands of the CORRECTED union, the value of the UNCORRECTED one, and a
    certificate that then also published level=0.85 two lines later. A reader who checked the
    arithmetic would have concluded the module cannot multiply.
    """
    line = next(text for text in cert.envelope if "family risk is" in text)
    g, claims = cert.n_groups, cert.n_claims
    assert "%d x %d x %.6f = %.4f" % (g, claims, cert.corrected_delta,
                                      g * claims * cert.corrected_delta) in line, line
    assert "= %.4f" % (claims * cert.delta) in line, (
        "the corrected family union must equal the uncorrected one -- that is the cancellation")
    assert "joint level is %.4f" % cert.level in line, line
    assert "-0.2000" not in line, "the uncorrected figure belongs on its own labelled line"


def test_the_envelope_names_the_budget_the_slices_were_actually_tested_against(cert):
    """F-8: the line about `beta` has to state the number the control flow SPENT.

    `corrected_beta` is computed and published, and no bound in the artefact is ever compared with
    it: each slice goes through `certify_choice(..., beta=beta, ...)`, the uncorrected budget. The
    first version of the envelope line said the corrected pair was published "for the reader to see
    which number gated", which is a sentence the module's own control flow contradicts -- the number
    it showed is the one that did not gate. Same class as the drift lane's F4 and the audit lane's
    MAJ-1: prose asserting what the code does not do.

    The gating value is read out of the slices themselves (each certificate's own `beta` attribute,
    which is the budget its bound was tested against) rather than typed, so a plant that starts
    spending `corrected_beta` at the slice call site reddens this row by making the sentence
    disagree with the artefact, not by being reworded.
    """
    line = next(text for text in cert.envelope if "beta is NOT divided" in text)
    spent = sorted({slice_cert.beta for slice_cert in cert.per_group.values()})
    assert spent == [cert.beta], spent
    assert cert.corrected_beta != cert.beta, (
        "a run at G=1 makes the pair coincide and this row vacuous; the census here is 8")
    assert ("uncorrected %.3f" % cert.beta) in line, line
    assert ("%.6f" % cert.corrected_beta) in line, line
    assert "NOT spent" in line, line
    assert "no bound in this artefact is compared with it" in line, line


def test_the_divided_beta_would_have_refused_the_slices_this_run_certifies(cert, recs):
    """The counterfactual the envelope line now publishes, measured instead of asserted in prose.

    The five clean families certify with a conditional bound of about 0.0144 against a budget of
    0.050, and the divided budget is 0.006250, so every one of those bounds sits ABOVE it: had this
    run spent `corrected_beta`, all five would have refused and the pooled-versus-slice divergence
    this fixture exists to show would have been an artefact of a self-imposed straitjacket rather
    than of the slice structure. That is the reason §8.1 leaves `beta` undivided, and the last two
    lines measure it by running the same slice through the same certifier at the divided budget.

    GREEN ON ARRIVAL (a measurement row); reddened by a plant that passes `corrected_beta` to the
    slice call, which flips the first two assertions because the slices stop being feasible.
    """
    certified = {name: c for name, c in cert.per_group.items() if c.feasible}
    assert sorted(certified) == ["a", "b", "c", "d", "e"], sorted(certified)
    for name, slice_cert in certified.items():
        assert slice_cert.conditional_error_bound > cert.corrected_beta, (
            "%s: the sentence claims the divided budget was not the gate" % name)
        assert slice_cert.conditional_error_bound <= cert.beta, name
    divided = certify_choice(by_group(recs, ("family",))["a"], alpha=cert.corrected_alpha,
                            beta=cert.corrected_beta, delta=cert.corrected_delta, seed=7)
    assert divided.feasible is False, divided.summary()
    assert divided.reason == "empty_feasible_set", divided.summary()
    assert "exceeds the budget %.3f" % cert.corrected_beta in divided.summary(), divided.summary()


def test_an_uncorrected_worst_of_g_would_not_be_a_probability_and_the_envelope_says_so(cert):
    """The correction shown to do work by the number it replaces (R-149's falsification demand).

    8 slices x 3 claims x 0.05 = 1.2, so an uncorrected worst-of-8 would publish a joint confidence of
    -0.2: not a confidence at all. Reddened by a plant that drops the `n_groups` factor from the
    envelope line, or that states the uncorrected product without the refusal language.
    """
    uncorrected = cert.n_groups * N_CLAIMS * cert.delta
    assert uncorrected == pytest.approx(1.2)
    assert not (0.0 < 1.0 - uncorrected < 1.0), "this is the false claim §8.1 exists to stop"
    line = next(line for line in cert.envelope if "UNCORRECTED worst-of-8" in line)
    assert "-0.2000" in line and "NOT a probability" in line, line


def test_the_level_follows_the_envelope_budget_and_not_the_risk_budget():
    """`beta` is a budget on the worst slice; `delta` is what the claims are tested at.

    At `beta=0.03, delta=0.05` the family level is `1 - 3*0.05 = 0.85`, NOT `1 - 3*0.03 = 0.91`. This
    is the row that keeps `worst_group`'s rubric-derivation out of the level: a level computed from
    the two risk targets would coincide with the right number at the published rubric (where
    `alpha == beta == delta`) and diverge the moment they do not -- which is exactly when a reader
    needs it to be right. Small population on purpose: this row is about the arithmetic, not the
    refusal story.
    """
    small = (_family("s0", 200, sharpness=8.0, seed=21)
             + _family("s1", 200, sharpness=8.0, seed=22))
    run = certify_groups(small, alpha=0.05, beta=0.03, delta=0.05, groups=("family",), seed=7)
    assert run.level == pytest.approx(1.0 - N_CLAIMS * run.delta)
    assert run.level != pytest.approx(1.0 - N_CLAIMS * run.beta)
    assert run.beta == 0.03 and run.delta == 0.05
    assert run.worst_claim["joint_level"] is None, (
        "the slice rows publish no rubric on purpose; the family level has ONE publisher")
    assert "beta is NOT divided" in "\n".join(run.envelope), run.envelope


def test_within_group_exchangeability_is_the_envelope_line_and_it_is_not_proved(cert):
    """§8.1: the guarantee is conditional on the group and needs within-group exchangeability.

    Asserted POSITIVELY -- the line must say ASSUMED and must say this run does not prove it. A
    banned-vocabulary loop is deliberately NOT used: the drift review's MAJOR-C1 found that a prose
    guard on word lists is re-satisfiable with other words (a plant that wrote "empirically supported"
    would pass it), so the guard here is that the two statements a reader needs are present. Reddened
    by a plant that drops either clause.
    """
    joined = "\n".join(cert.envelope)
    assert "within group" in joined.lower()
    assert "ASSUMED" in joined, joined
    assert "not proved by this run" in joined, joined
    assert "conditional on 'family'" in joined, joined


def test_the_correction_divides_the_census_count_and_no_constant_stand_in_for_it(cert, recs):
    """R-149 at the certificate surface: the divisor is `len(by_group)`, and 3 and 4 are not it.

    A plant that substitutes `N_CLAIMS` or `contamination.N_PIECES` for the slice count reddens this
    row (the corrected budgets, the family-level union and the per-slice levels all move together),
    which is the under-correction made expensive here rather than only in prose.
    """
    census = len(by_group(recs, ("family",)))
    assert cert.n_groups == census == 8
    assert cert.n_groups != N_CLAIMS and cert.n_groups != 4
    assert cert.corrected_alpha == pytest.approx(ALPHA / census)
    assert cert.corrected_delta == pytest.approx(0.05 / census)
    assert cert.worst_claim["n_groups"] == census


def test_the_group_refusals_are_attributed_only_to_the_reason_that_is_evidence(cert):
    """Only the size floor is a group-conditional refusal this tool can name (R-149's other half).

    `tiny` is attributed to the floor. `risky` and `wide` refused for their own reasons -- a quantile
    above 1 -- and the artefact must say that nothing here is evidence the slice STRUCTURE caused it,
    even though the corrected `alpha/8` is what pushed the quantile over the edge. Reddened by a plant
    that attributes every refusal to the floor, which is the over-claim this row exists to refuse.
    """
    by_group_name = {row["group"]: row for row in cert.worst_claim["refusals"]}
    assert GROUP_FLOOR_MESSAGE in by_group_name["tiny"]["why"]
    floor_attributed = [name for name, row in by_group_name.items() if GROUP_FLOOR_MESSAGE in row["why"]]
    assert floor_attributed == ["tiny"]
    for name in ("risky", "wide"):
        assert "NOT attributed to the slice structure" in by_group_name[name]["why"], name
        assert "vacuous_quantile" == by_group_name[name]["reason"], name
    assert cert.n_min_violations and cert.worst_claim["slices_without_the_metric"] == []


def test_the_worst_slice_is_a_refusal_and_never_a_restatement_of_the_pooled_number(cert, pooled):
    """The plan's Step 3: compute the worst FROM the per-slice certificates, never by hand.

    `worst` is a real `Certificate` from `per_group` (so it carries the envelope, the refusal reason
    and the shape rules), its headline numbers are `None` because it is a refusal, and it is NOT the
    pooled certificate the same records produced.
    """
    worst = cert.worst
    assert isinstance(worst, Certificate)
    assert worst.autorate is None and worst.conditional_error_bound is None
    assert worst.feasible is False
    assert worst is cert.per_group[cert.worst_claim["worst"]["group"]]
    assert worst is not pooled
    assert cert.worst_claim["worst"]["n_cases"] == min(cert.slice_cases.values())
    # a refusal is the worst case, so it must not be reported as a permission
    assert cert.worst_claim["any_slice_refused"] is True


def test_a_mixed_backend_batch_refuses_the_group_run_naming_both_backends(recs):
    """One certificate, one subject -- and a worst-of-G across two models is one permission for two.

    The pooled set gate answers a mixed batch with `backend=None` and certifies it (its published
    behaviour, unchanged here); the group run refuses instead, mirroring `certify_score.py:219-225`
    and `certify_threshold.py:301-310`. Reddened by a plant that drops the check and lets the run
    inherit the `backend=None` silence.
    """
    mixed = recs + _family("other", 130, sharpness=8.0, seed=99, backend="second_model")
    with pytest.raises(ValueError, match="spans backends") as excinfo:
        certify_groups(mixed, groups=("family",), seed=7)
    message = str(excinfo.value)
    assert "second_model" in message and "synthetic" in message, message
    assert "one backend at a time" in message


def test_a_slice_whose_records_all_lack_gold_is_named_in_the_census_not_filtered(recs):
    """Never silently filtered: an unlabelled slice is a census row and a refusal, by name.

    The contamination lane's `skipped_wrong_qtype=768` census is the precedent -- a count that moved
    without a line saying so is how a denominator stops describing the data.
    """
    with_dark = recs + _family("dark", 140, sharpness=8.0, seed=77, unlabelled=140)
    run = certify_groups(with_dark, groups=("family",), seed=7)
    row = next(entry for entry in run.slice_census if entry["group"] == "dark")
    assert row["records"] == 140 and row["kept"] == 0
    assert row["skipped_no_gold"] == 140, row
    # The verdict was always right; the DENOMINATOR was the defect. `cases` is what the slice holds
    # and what the floor is priced on; `eligible_cases` is what the certifier was handed, and a slice
    # line that prints only the first reads as "140 labelled cases were refused".
    assert "eligible_cases" in row, row
    assert row["eligible_cases"] == 0, row
    assert run.slice_eligible_cases["dark"] == 0, run.slice_eligible_cases
    assert run.per_group["dark"].feasible is False
    assert run.per_group["dark"].reason == "no_gold_labels"
    assert "dark" in run.meta["slices_declared_but_empty"], run.meta
    assert run.n_groups == 9 == len(run.per_group), "the slice is counted, not dropped"


def test_the_slice_automation_rate_is_non_monotone_in_the_sweep_and_is_asserted_as_a_fact(cert):
    """R-124, measured rather than waved at: looser coverage does NOT automate more.

    On the `risky` slice's own diagnostic curve the automated count reaches 72 at `grid_alpha=0.27`
    and then DROPS to 70 at 0.28, because a set that stops being a singleton is a refusal, not an
    error. This is why nothing in this file says or implies a monotone relation between `alpha` and
    automation; the curve is evidence, and the evidence says non-monotone.
    """
    curve = cert.per_group["risky"].meta["diagnostic_curve"]
    automated = [point["automated"] for point in curve]
    assert not all(first <= second for first, second in zip(automated, automated[1:])), automated
    peak = max(range(len(curve)), key=lambda i: automated[i])
    assert automated[peak] > automated[-1], "the loosest level on the grid is not the busiest"
    assert curve[-1]["grid_alpha"] > curve[peak]["grid_alpha"]
    assert cert.per_group["risky"].meta.get("diagnostic_note"), (
        "the sweep is labelled evidence only; nothing on it was certified")


def test_the_group_argument_leaves_the_pooled_surface_exactly_as_it_was(recs, pooled, cert):
    """The dispatch must not have moved a published number: `groups=None` is still the marginal gate.

    Reddened by a plant that routes the pooled path through the corrected budgets, which would make
    every committed certificate the tool already publishes disagree with a re-run.
    """
    assert isinstance(cert, GroupsCertificate)
    plain = certify_choice(recs, alpha=ALPHA, beta=BETA, delta=0.05, seed=7)
    assert isinstance(plain, Certificate) and not isinstance(plain, GroupsCertificate)
    assert plain.feasible == pooled.feasible
    assert plain.autorate == pooled.autorate
    assert plain.conditional_error_bound == pooled.conditional_error_bound
    assert plain.meta["eval_ids"] == pooled.meta["eval_ids"]
    assert plain.envelope == pooled.envelope
    assert "marginal certificate only - not group-conditional" in plain.envelope, (
        "the pooled certificate still says out loud that it is not group-conditional")
    for bad, error in ((dict(alpha=1.5), ValueError), (dict(method="knn"), ValueError)):
        with pytest.raises(error):
            certify_choice(recs, groups=("family",), seed=7, **bad), (
                "the rubric is validated before the dispatch, so a group run cannot skip the guard")
    with pytest.raises(ValueError):
        certify_groups(recs, groups="family", seed=7), (
            "a bare string iterates characters, so it would ask for the keys 'f', 'a', 'm'...")


def test_the_artefact_serialises_with_the_correction_stated(cert):
    """A reader of the JSON alone must be able to see the family, the level and the refusals.

    Green on arrival against `to_dict` as written; it reddens if a field is dropped from the
    serialization, which is how a published artefact stops being reconstructible (R-159).
    """
    payload = cert.to_dict()
    for key in ("n_groups", "corrected_alpha", "corrected_delta", "corrected_beta", "n_claims",
                "level", "n_min_violations", "slice_census", "slice_cases", "slice_eligible_cases",
                "per_group", "pooled", "worst_claim", "envelope"):
        assert key in payload, key
    assert payload["level"] == pytest.approx(1.0 - payload["n_claims"] * cert.delta)
    assert payload["n_min_violations"][0]["group"] == "tiny"
    assert "joint level 0.8500" in cert.summary()
    assert cert.to_json().startswith("{")
    assert "per_group" in cert.to_json()
