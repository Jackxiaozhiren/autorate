"""Ledger #37/#71: every published bound and ratio names its own denominator and unit.

The defect this file polices is one NAME carrying two DENOMINATORS. `conditional_error_bound` sits
inside a certificate's headline fields computed over CASES, inside `meta.at_requested_alpha` computed
over CASES, and inside every `meta.diagnostic_curve` row (and its `closest_attempt` copy) computed
over RECORDS -- and nothing on the artefact said which. A reader who trusted `meta.unit_note` ("the
bounds use the case denominator") read a record bound as a case bound.

So every assertion here RECOMPUTES the published number from the operands the row itself names, and
then checks that the row's declared unit is the unit those operands belong to. A test that only
checked the key existed would pass on a row that names the wrong pair, which is the defect.

Both directions of the records-vs-cases distinction are named, because one of them alone is a free
pass:
  * `data/cert_jev.json` / `data/cert_laya.json` -- 96 evaluation records over 32 distinct cases. The
    record pair and the case pair DIFFER, so a row that published the case pair under the record
    name would fail to reproduce its own bound.
  * `data/cert_massive_*_laya.json` -- 1487 records over 1487 cases. There the two pairs are EQUAL,
    legitimately, and an equal pair is only allowed when the artefact's own counts say one record per
    case. Without that arm a sloppy test passes on the massive files for the wrong reason.
"""
import json
import random
from pathlib import Path

import pytest
from _records import build_ordinal, choice_record

from autorate.certificate import (BOUND_UNIT_CASE, BOUND_UNIT_RECORD, CANONICALISED_BOUND_FIELDS,
                                  canonicalise_bound)
from autorate.certify_choice import _canonicalised as _choice_canonicalised
from autorate.certify_choice import certify_choice
from autorate.certify_score import certify_score
from autorate.certify_threshold import certify_threshold
from autorate.report import CERTS, MASSIVE_CERTIFICATES
from autorate.tails import clopper_pearson_upper

REPO = Path(__file__).resolve().parents[1]

# The published set-gate artefacts, read out of the tables that publish them rather than typed a second
# time here: `report.CERTS` and `report.MASSIVE_CERTIFICATES` are what `verify` re-derives and what
# `docs/REPORT.md` prints, so a list kept inside this file could disagree with the publication.
CHOICE_ARTEFACTS = tuple(sorted([CERTS[b] for b in CERTS]
                               + [MASSIVE_CERTIFICATES[k][1] for k in MASSIVE_CERTIFICATES]))


def _doc(rel):
    return json.loads((REPO / rel).read_text())


def _curve(doc):
    return doc["meta"].get("diagnostic_curve") or []


def _repeating_cases(n_cases=400, reps=3, seed=11, error_rate=0.3, sharpness=6.0):
    """`n_cases` cases of `reps` records each, ~`error_rate` of them wrong: 3 records per observation.

    A case's records share the ballot and the gold label and differ only in the recorded draw, which
    is the shape the committed archive has (feishu: 96 evaluation records over 32 distinct cases). The
    draw is what makes the two denominators disagree about HOW MANY automations happened, so the row's
    record pair and the certificate's case pair are different numbers on this population -- a fixture
    where they coincide cannot tell a mislabelled unit from a correct one.
    """
    rng = random.Random(seed)
    out = []
    for c in range(n_cases):
        options = tuple("opt%d" % j for j in range(4))
        gold_index = rng.randrange(4)
        if rng.random() < error_rate:
            peaked = (gold_index + 1 + rng.randrange(3)) % 4
        else:
            peaked = gold_index
        weights = [1.0] * 4
        weights[peaked] = sharpness
        total = sum(weights) + 4 * 0.05
        probs = [round(x / total, 4) for x in weights]
        probs[peaked] = round(probs[peaked] + (1.0 - sum(probs)), 4)
        for rep in range(reps):
            out.append(choice_record(id="c%03d.%d" % (c, rep), case_id="c%03d" % c, repeat=rep,
                                     probs=tuple(probs), gold=options[gold_index], u=rng.random()))
    return out


def _threshold_cases(n_right=90, n_wrong=40, reps=3):
    """The same idea for the threshold gate: one score per case, so a lambda separates the two tiers.

    Tier A automates and is right; tier B automates at a lower lambda and is wrong. The two tiers must
    be separated by score for `_select_lambda` to have an operating point at all, and every repeat of a
    case carries the same verdict, so the record count is `reps` times the case count on this data.
    """
    out = []
    for bucket, count, conf, pred_index in (("A", n_right, 0.95, 0), ("B", n_wrong, 0.90, 1)):
        for c in range(count):
            for rep in range(reps):
                out.append(choice_record(id="%s%03d.%d" % (bucket, c, rep),
                                         case_id="%s-%03d" % (bucket, c), repeat=rep,
                                         probs=(conf, 1 - conf, 0.0), gold="opt0",
                                         predicted="opt%d" % pred_index,
                                         scores={"confidence": conf}))
    return out


# -----------------------------------------------------------------------------------------------
# The published artefacts: each bound reproduces from the operands its own row names.
# -----------------------------------------------------------------------------------------------

def test_the_table_names_artefacts_in_both_records_vs_cases_directions():
    """The guard below is not vacuous: both directions of the denominator split are on the surface.

    One artefact with repeats (records > cases) and one without (records == cases) must both be read,
    or the equality exception in `test_the_at_requested_alpha_block...` would never be exercised.
    """
    with_repeats, one_per_case = [], []
    for rel in CHOICE_ARTEFACTS:
        doc = _doc(rel)
        (one_per_case if doc["n_eval"] == doc["meta"]["n_eval_cases"] else with_repeats).append(rel)
    assert with_repeats and one_per_case, (with_repeats, one_per_case)
    assert any(_curve(_doc(rel)) for rel in CHOICE_ARTEFACTS), "no published artefact carries a curve"
    assert any(_doc(rel)["meta"].get("at_requested_alpha") for rel in CHOICE_ARTEFACTS), \
        "no published artefact carries `at_requested_alpha`"


@pytest.mark.parametrize("rel", CHOICE_ARTEFACTS)
def test_every_curve_row_names_the_operands_and_the_unit_it_was_bound_over(rel):
    """A diagnostic row's `conditional_error_bound` must be CP(the errors, the automated IN THIS ROW)
    at the level this certificate states, and `bound_unit` must say whose counts those are.

    The rows are the record denominator, while the certificate's headline field of the same name is
    the case denominator. `evaluated_records` is the `len(ev)` that `observed_automation_rate` was
    divided by -- until this round that divisor appeared nowhere on the row, so the ratio could not be
    attested from the bytes beside it.
    """
    doc = _doc(rel)
    delta, n_eval = doc["delta"], doc["n_eval"]
    rows = _curve(doc)
    assert rows, "%s publishes no diagnostic curve" % rel
    for row in rows:
        assert row["bound_unit"] == BOUND_UNIT_RECORD, row
        assert row["conditional_error_bound"] == canonicalise_bound(
            clopper_pearson_upper(row["errors"], row["automated"], delta)), row
        # The row's own sibling ratio now has its own denominator on the row.
        assert row["evaluated_records"] == n_eval, (row, n_eval)
        assert row["observed_automation_rate"] == row["automated"] / row["evaluated_records"], row
        assert row["observed_conditional_error"] == row["errors"] / row["automated"], row
    # `closest_attempt` is one of those rows, so it inherits the naming rather than special-casing it.
    closest = doc["meta"]["closest_attempt"]
    assert any(closest is row or closest == row for row in rows), closest
    assert closest["bound_unit"] == BOUND_UNIT_RECORD, closest


@pytest.mark.parametrize("rel", CHOICE_ARTEFACTS)
def test_the_at_requested_alpha_block_names_the_case_operands_its_bound_used(rel):
    """The headline refusal block publishes a CASE bound; it must carry the case operands and say so.

    `automated` / `errors` in this block are record counts and the bound beside them is not computed
    from them, so before this round the block stated a number whose denominator it did not name. Both
    directions of the records-vs-cases test are asserted here: an equal pair is only admissible where
    the artefact's own counts state one record per case.
    """
    doc = _doc(rel)
    block = doc["meta"].get("at_requested_alpha")
    if block is None:
        # `de` refuses before reaching the case stage (zero automated), and says so in its own detail.
        assert doc["meta"]["automated_cases"] == 0, (rel, block)
        return
    delta = doc["delta"]
    assert block["bound_unit"] == BOUND_UNIT_CASE, (rel, block)
    assert block["conditional_error_bound"] == canonicalise_bound(
        clopper_pearson_upper(block["errors_cases"], block["automated_cases"], delta)), (rel, block)
    record_pair = (block["automated"], block["errors"])
    case_pair = (block["automated_cases"], block["errors_cases"])
    one_record_per_case = doc["n_eval"] == doc["meta"]["n_eval_cases"]
    if record_pair == case_pair:
        # The ONLY corpus fact that makes an equal pair honest is one record per case.
        assert one_record_per_case, (rel, record_pair, case_pair, doc["n_eval"],
                                     doc["meta"]["n_eval_cases"])
    else:
        assert not one_record_per_case, (rel, record_pair, case_pair)
    # The case operands named here are the same case the certificate's headline counts over, so the
    # block cannot invent a third pair.
    assert case_pair[0] == doc["meta"]["automated_cases"], (rel, block)
    assert case_pair[1] == doc["meta"]["erroneous_cases"], (rel, block)


@pytest.mark.parametrize("rel", CHOICE_ARTEFACTS)
def test_unit_note_names_both_units_it_covers(rel):
    """`meta.unit_note` is published prose; it may not claim one unit for a two-unit artefact.

    The sentence this replaced read "the bounds use the case denominator, because repeats of one case
    are one observation" -- true of the headline bounds, false of every curve row and of
    `closest_attempt`. A note that passes a "does it say the word record" check would pass on the OLD
    sentence too ("96 evaluation records over 32 distinct cases"), so the assertion names the curve and
    `closest_attempt` explicitly and requires the record denominator to be attributed to THEM.
    """
    doc = _doc(rel)
    if not _curve(doc):
        pytest.skip("%s carries no curve, so its note has no second unit to name" % rel)
    note = doc["meta"]["unit_note"]
    assert "%d distinct cases" % doc["meta"]["n_eval_cases"] in note, note
    assert "case denominator" in note, note
    assert "record denominator" in note, note
    for named in ("diagnostic curve", "closest_attempt"):
        assert named in note, (named, note)
    assert note.count("denominator") >= 2, note


# -----------------------------------------------------------------------------------------------
# The producers: one declared style each, and nothing outside the declaration gets to invent one.
# -----------------------------------------------------------------------------------------------

# Each producer that publishes a diagnostic curve, with the naming style IT is held to. The point of
# recording a style per producer rather than requiring "some unit naming exists" is that a fourth
# producer could otherwise pass by copying the wrong convention: the threshold gate already solved
# this problem by publishing two unit-named bounds, and the set gates solve it by naming the unit.
CURVE_PRODUCERS = {
    "certify_choice.py": "bound_unit",
    "certify_score.py": "bound_unit",
    "certify_threshold.py": "two-unit-named-bounds",
}


def test_the_declared_curve_producers_are_exactly_the_ones_that_write_a_curve():
    """A new diagnostic curve means a new entry here, with a style -- not a silent fourth spelling."""
    writers = sorted(p.name for p in (REPO / "src" / "autorate").glob("*.py")
                     if '"diagnostic_curve":' in p.read_text(encoding="utf-8"))
    assert writers == sorted(CURVE_PRODUCERS), writers


def test_the_choice_curve_rows_and_headline_block_carry_the_naming_at_the_source():
    """The producer, not the committed file: rows and `at_requested_alpha` name their own operands."""
    cert = certify_choice(_repeating_cases(), alpha=0.05, beta=0.05, delta=0.05, seed=7)
    assert cert.feasible is False, cert.summary()
    rows = cert.meta["diagnostic_curve"]
    assert rows, cert.meta
    for row in rows:
        assert row["bound_unit"] == BOUND_UNIT_RECORD, row
        assert "record_conditional_error_bound" not in row, row
        assert row["conditional_error_bound"] == canonicalise_bound(
            clopper_pearson_upper(row["errors"], row["automated"], cert.delta)), row
        assert row["evaluated_records"] == cert.n_eval, row
    # The population really does have repeats, so the record pair and the case pair are different
    # numbers and the naming below has content rather than a coincidence.
    assert cert.n_eval > cert.meta["n_eval_cases"], (cert.n_eval, cert.meta["n_eval_cases"])
    block = cert.meta["at_requested_alpha"]
    assert block["bound_unit"] == BOUND_UNIT_CASE, block
    assert block["automated"] != block["automated_cases"], block
    assert block["conditional_error_bound"] == canonicalise_bound(
        clopper_pearson_upper(block["errors_cases"], block["automated_cases"], cert.delta)), block
    # The note this artefact publishes states both units, on the producer's own words.
    assert "record denominator" in cert.meta["unit_note"], cert.meta["unit_note"]


def test_the_score_curve_rows_are_named_the_same_way_as_the_choice_ones():
    """`certify_score` copies the set gate's `_with_diagnostic` treatment, so it copies the naming too.

    Its bounds are compared RAW, not through `canonicalise_bound`: R-121's canonicalisation landed on
    the choice gate and never reached this one (`certify_score.py:254,284` still publish the raw
    `bound_width` / `clopper_pearson_upper` doubles). That gap is not this task's to close, and pinning
    the canonical value here would assert a thing the producer does not do.
    """
    cert = certify_score(build_ordinal(n=1200, seed=4, shift=0.35), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False, cert.summary()
    rows = cert.meta["diagnostic_curve"]
    assert rows, cert.meta
    for row in rows:
        assert row["bound_unit"] == BOUND_UNIT_RECORD, row
        assert row["conditional_error_bound"] == clopper_pearson_upper(
            row["errors"], row["automated"], cert.delta), row
        assert row["evaluated_records"] == cert.n_eval, row
    block = cert.meta["at_requested_alpha"]
    assert block["bound_unit"] == BOUND_UNIT_CASE, block
    assert block["conditional_error_bound"] == clopper_pearson_upper(
        block["errors_cases"], block["automated_cases"], cert.delta), block
    assert "record denominator" in cert.meta["unit_note"], cert.meta["unit_note"]


def test_the_threshold_gate_keeps_its_own_style_and_is_not_renamed_into_the_new_one():
    """Threshold is the reference: TWO unit-named bounds per row, and no `bound_unit` key at all.

    Its rows already say which denominator each bound carries by NAME, so adding `bound_unit` here
    would give one artefact two owners of the same statement. This row asserts the declared style in
    both directions -- what it must carry, and what it must not.
    """
    cert = certify_threshold(_threshold_cases(), score_field="confidence", alpha=0.05, beta=0.05,
                             delta=0.05, seed=3, grid=(0.90, 0.95))
    assert cert.feasible is False, cert.summary()
    rows = cert.meta["diagnostic_curve"]
    assert rows, cert.meta
    for row in rows:
        assert "bound_unit" not in row, row
        assert row["conditional_error_bound"] == canonicalise_bound(clopper_pearson_upper(
            row["erroneous_cases"], row["automated_cases"], cert.delta)), row
        assert row["record_conditional_error_bound"] == canonicalise_bound(
            clopper_pearson_upper(row["errors"], row["automated"], cert.delta)), row


def test_the_two_unit_names_have_exactly_one_owner_and_no_third_spelling_exists():
    """A fourth producer cannot invent "cases"/"records": the names are imported, never typed."""
    assert BOUND_UNIT_CASE == "case" and BOUND_UNIT_RECORD == "record"
    typed = [p.name for p in (REPO / "src" / "autorate").glob("*.py")
             if '"bound_unit": "' in p.read_text(encoding="utf-8")
             or "'bound_unit': '" in p.read_text(encoding="utf-8")]
    assert typed == [], typed
    seen = set()
    for rel in CHOICE_ARTEFACTS:
        doc = _doc(rel)
        for row in _curve(doc):
            seen.add(row["bound_unit"])
        block = doc["meta"].get("at_requested_alpha")
        if block:
            seen.add(block["bound_unit"])
    assert seen and seen <= {BOUND_UNIT_CASE, BOUND_UNIT_RECORD}, seen


# -----------------------------------------------------------------------------------------------
# R-121's precision contract: the new fields must not become a float-tolerance back-door.
# -----------------------------------------------------------------------------------------------

def test_the_canonicalisation_sweep_leaves_the_new_fields_and_every_non_bound_alone():
    """`CANONICALISED_BOUND_FIELDS` walks by field NAME, and these two keys are not in it.

    `bound_unit` is a string and `evaluated_records` an int; the sweep must return both untouched, and
    a non-bound float added to the same row must keep the exact double the records determine. That is
    the precision contract: a blanket pass over floats would absorb a genuinely changed automation rate
    as cheerfully as it absorbs a libm difference, which is what R-121 forbids.
    """
    assert "bound_unit" not in CANONICALISED_BOUND_FIELDS
    assert "evaluated_records" not in CANONICALISED_BOUND_FIELDS
    raw = 0.9813999999999999          # a double only a quotient of integers can produce
    row = {"conditional_error_bound": clopper_pearson_upper(1, 32, 0.05),
           "qhat": 0.9999999999999999,
           "observed_automation_rate": raw,
           "bound_unit": BOUND_UNIT_RECORD,
           "evaluated_records": 96,
           "newly_added_non_bound": raw}
    out = _choice_canonicalised(row)
    assert out["conditional_error_bound"] == canonicalise_bound(row["conditional_error_bound"])
    assert out["bound_unit"] is BOUND_UNIT_RECORD, out
    assert type(out["evaluated_records"]) is int and out["evaluated_records"] == 96, out
    for key in ("qhat", "observed_automation_rate", "newly_added_non_bound"):
        assert out[key] == row[key], (key, out)
        # Untouched means untouched: a raw non-bound double stays raw, which is the whole point of
        # sweeping by field name instead of by "this looks like a float".
        assert out[key] != canonicalise_bound(out[key]), (key, out)


@pytest.mark.parametrize("rel", CHOICE_ARTEFACTS)
def test_the_committed_curve_rows_store_the_new_fields_in_their_own_types(rel):
    """No published `evaluated_records` was rounded into a float, and no `bound_unit` into anything."""
    for row in _curve(_doc(rel)):
        assert isinstance(row["evaluated_records"], int) and not isinstance(
            row["evaluated_records"], bool), row
        assert isinstance(row["bound_unit"], str), row
        assert row["bound_unit"] not in CANONICALISED_BOUND_FIELDS
