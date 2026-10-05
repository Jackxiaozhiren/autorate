"""Task 4: the one public data contract. Field names live here; statistics do not.

Every constant quoted from upstream is measured against the archived record it comes
from, not from upstream's prose.
"""
import json
from pathlib import Path

import pytest

from _thresholds import p_max_for_entropy
from autorate.records import (
    QTYPES,
    Record,
    entropy_confidence,
    is_hashable_key,
    max_confidence,
    validate,
)

# Verbatim from upstream feishu_zh results/v1/laya/raw.jsonl, id=lifecycle-05, repeat=1:
# probabilities {urgent: .2955, todo: .2984, valuable: .2973, noise: .1087}, confidence 0.0456.
L05_OPTIONS = ("urgent", "todo", "valuable", "noise")
L05_PROBS = (0.2955, 0.2984, 0.2973, 0.1087)
L05_REPORTED_CONFIDENCE = 0.0456


def _rec(probs=L05_PROBS, options=L05_OPTIONS, **kw):
    base = dict(id="x", qtype="choice", backend="laya", repeat=0, options=tuple(options),
                probs=tuple(probs), gold="valuable", predicted=None,
                slices={"family": "lifecycle"},
                scores={"reported_confidence": L05_REPORTED_CONFIDENCE}, seed=13, u=0.0, meta={})
    base.update(kw)
    return Record(**base)


def test_entropy_confidence_reproduces_the_archived_field_to_the_rounding():
    # This pins WHICH of laya's three confidence quantities reached the archive.
    assert abs(entropy_confidence(L05_PROBS) - L05_REPORTED_CONFIDENCE) <= 1e-4
    assert abs(max_confidence(L05_PROBS) - 0.2984) < 1e-9


def test_the_two_scales_disagree_on_the_same_record_and_are_not_interchangeable():
    assert entropy_confidence(L05_PROBS) < 0.05 < max_confidence(L05_PROBS)


def test_one_entropy_threshold_means_a_different_p_max_for_every_option_count():
    # The bisection has ONE owner, `tests/_thresholds.py::p_max_for_entropy`, and its parameters are
    # keyword-only: this file used to carry a second copy whose two parameters were in the opposite
    # order, and a transposed call there was loud only by accident (the solver multiplies a list by
    # `k`), silent for any value pair that arithmetic happens to accept. This file owns the FIGURES
    # the solver produces, and they correct an earlier hand-computed claim in this project's own
    # design notes -- at tau=0.85 the requirement is p_max >= 0.9609 at k=4, not the ~0.93 first
    # written down (that figure belongs to k=20), and the requirement is STRICTER at small k, not
    # looser. Each number below is produced by the solver, so it cannot drift.
    eq = {k: p_max_for_entropy(target=0.85, k=k) for k in (2, 4, 10, 20, 51)}
    assert eq[2] > eq[4] > eq[10] > eq[20] > eq[51]
    assert abs(eq[4] - 0.9609) < 6e-4
    assert abs(eq[2] - 0.9785) < 6e-4
    assert abs(eq[51] - 0.9203) < 6e-4
    # The spread is what makes a single shared threshold a unit error, and it widens
    # as the threshold loosens: 0.058 points apart at 0.85, 0.229 points at 0.50.
    assert eq[2] - eq[51] > 0.05
    loose = {k: p_max_for_entropy(target=0.50, k=k) for k in (2, 51)}
    assert loose[2] - loose[51] > 0.22


def test_a_sharp_looking_answer_can_still_miss_the_documented_threshold():
    # The archived-style near-uniform record is low on both scales, and a 0.93 answer
    # at k=4 is NOT "0.85 confident": it is 0.7616. Measured, not argued.
    assert abs(entropy_confidence([0.93, 0.023, 0.023, 0.024]) - 0.7616) < 1e-4
    assert abs(entropy_confidence([0.90, 0.10]) - 0.531) < 1e-3
    assert entropy_confidence(L05_PROBS) < 0.05 < max_confidence(L05_PROBS)


def test_uniform_mass_is_zero_on_the_entropy_scale_and_quarter_on_the_max_scale():
    u = [0.25, 0.25, 0.25, 0.25]
    assert abs(entropy_confidence(u)) < 1e-9
    assert abs(max_confidence(u) - 0.25) < 1e-9


def test_validate_rejects_mismatched_option_and_probability_lengths():
    with pytest.raises(ValueError, match="length"):
        validate(["a", "b"], [0.5])


def test_validate_rejects_probabilities_that_do_not_close_to_one():
    with pytest.raises(ValueError, match="sum"):
        validate(["a", "b"], [0.5, 0.9])


def test_validate_accepts_four_decimal_rounding_slack():
    validate(["a", "b"], [0.5001, 0.4998])  # sum 0.9999: served rounding, legal


def test_validate_rejects_non_finite_probability_because_it_would_poison_a_quantile():
    with pytest.raises(ValueError, match="finite"):
        validate(["a", "b"], [float("nan"), 1.0])
    with pytest.raises(ValueError, match="finite"):
        validate(["a", "b"], [float("inf"), 0.0])


def test_gold_must_be_one_of_the_options():
    with pytest.raises(ValueError, match="gold"):
        validate(["a", "b"], [0.5, 0.5], gold="c")


def test_empty_option_set_is_rejected_not_certified_as_singleton():
    with pytest.raises(ValueError, match="empty"):
        validate([], [])


def test_unknown_qtype_is_rejected():
    with pytest.raises(ValueError, match="qtype"):
        _rec(qtype="regression")
    assert QTYPES == ("choice", "score", "noul")


def test_a_record_without_gold_is_never_calibratable_but_is_still_gatable():
    r = _rec(gold=None)
    assert r.calibratable is False
    assert r.k == 4
    with pytest.raises(ValueError, match="gold"):
        r.gold_index


def test_gold_index_is_the_archived_option_order_not_a_sorted_one():
    # Upstream renders probabilities in its own order; sorting here would silently
    # change every set computed downstream.
    r = _rec(gold="valuable")
    assert r.gold_index == 2
    assert r.options == L05_OPTIONS


def test_u_is_required_in_the_validated_range_because_sets_are_reproducible_only_with_it():
    with pytest.raises(ValueError, match="u must be"):
        _rec(u=1.0)
    with pytest.raises(ValueError, match="u must be"):
        _rec(u=-0.001)


def test_a_noul_scalar_gains_a_two_slot_vector_and_the_shape_flag():
    # Upstream four_noul answers carry one P(true) and set confidence equal to it, so
    # "confidently no" and "low confidence" are the same number. Modeled, not hidden.
    r = _rec(qtype="noul", options=(), probs=(0.7745,), gold=None, scores={})
    assert r.options == ("false", "true")
    assert r.probs == (0.2255, 0.7745)
    assert r.scores["noul_scalar_expanded"] is True
    assert r.k == 2


def test_the_two_slot_order_is_the_callers_and_p_true_follows_it():
    # A positional guess here would assert P(true)=0.2255 for an archived 0.7745.
    flipped = _rec(qtype="noul", options=("true", "false"), probs=(0.7745,), gold=None,
                   scores={})
    assert flipped.options == ("true", "false")
    assert flipped.probs == (0.7745, 0.2255)
    assert flipped.options.index("true") == 0


def test_a_scalar_noul_with_slots_that_are_not_the_pair_is_refused():
    with pytest.raises(ValueError, match="must name both slots"):
        _rec(qtype="noul", options=("yes", "no"), probs=(0.6,), gold=None, scores={})
    with pytest.raises(ValueError, match="must name both slots"):
        _rec(qtype="noul", options=("true",), probs=(0.6,), gold=None, scores={})


def test_the_confounding_flag_belongs_to_the_reader_and_survives_construction():
    # records.py used to clobber it to True, which made the reader's computation dead
    # and made 1527 archived noul records claim a property 759 of them have.
    observed = _rec(qtype="noul", options=("false", "true"), probs=(0.2, 0.8), gold="true",
                    scores={"noul_confounded_with_yes": False})
    assert observed.scores["noul_confounded_with_yes"] is False
    assert "noul_scalar_expanded" not in observed.scores


def test_a_two_slot_noul_is_not_marked_as_an_expanded_scalar():
    r = _rec(qtype="noul", options=("false", "true"), probs=(0.2, 0.8), gold="true")
    assert "noul_scalar_expanded" not in r.scores


def test_a_noul_gold_is_named_by_the_slot_not_by_an_invented_label():
    r = _rec(qtype="noul", options=("false", "true"), probs=(0.3, 0.7), gold="true")
    assert r.gold_index == 1


def test_score_levels_keep_their_declared_order():
    r = _rec(qtype="score", options=("not urgent", "soon", "blocking"),
             probs=(0.1, 0.7, 0.2), gold="soon")
    assert r.gold_index == 1 and r.k == 3


def test_negative_probabilities_and_duplicate_options_are_rejected():
    # Both branches existed in validate() with no test behind them: a guard nobody has
    # seen fire is a guard that may be unreachable.
    with pytest.raises(ValueError, match="negative probability"):
        _rec(probs=(1.2, -0.2, 0.0, 0.0))
    with pytest.raises(ValueError, match="duplicate option"):
        _rec(options=("a", "a", "b", "c"), probs=(0.25, 0.25, 0.25, 0.25))


def test_a_predicted_answer_outside_the_ballot_is_rejected():
    # predicted is what the automated decision WOULD be; a name that is not an option
    # turns into a silent wrong answer in every certificate built from the record.
    with pytest.raises(ValueError, match="predicted"):
        _rec(predicted="maybe")
    with pytest.raises(ValueError, match="predicted"):
        _rec(qtype="score", options=("not urgent", "soon", "blocking"),
             probs=(0.1, 0.7, 0.2), gold="soon", predicted="todo")


def test_a_single_option_decision_is_refused_rather_than_certified_at_full_confidence():
    with pytest.raises(ValueError, match="one-option"):
        _rec(options=("only",), probs=(1.0,))
    with pytest.raises(ValueError, match="k=1"):
        entropy_confidence([1.0])


def test_the_confidence_scales_reject_an_empty_or_non_finite_vector():
    for bad in ([], [float("nan"), 0.5], [float("inf"), 0.0]):
        with pytest.raises(ValueError, match="empty|non-finite"):
            entropy_confidence(bad)
        with pytest.raises(ValueError, match="empty|non-finite"):
            max_confidence(bad)


def test_the_record_copies_the_mappings_it_was_handed():
    # A frozen dataclass does not freeze what the caller still holds. Before this, a
    # slice dict mutated after construction rewrote a certified record's grouping.
    slices, scores, meta = {"family": "lifecycle"}, {"reported_confidence": 0.1}, {"k": 1}
    r = _rec(slices=slices, scores=scores, meta=meta)
    slices["family"] = "tampered"
    scores["reported_confidence"] = 9.9
    meta["k"] = 99
    assert r.slices["family"] == "lifecycle"
    assert r.scores["reported_confidence"] == 0.1
    assert r.meta["k"] == 1


def test_round_trip_to_from_dict_is_lossless_including_types():
    for r in (_rec(), _rec(gold=None), _rec(qtype="noul", options=(), probs=(0.6,), gold=None, scores={})):
        d = r.to_dict()
        assert isinstance(d["options"], list) and isinstance(d["probs"], list)
        back = Record.from_dict(d)
        assert back == r
        assert isinstance(back.options, tuple) and isinstance(back.probs, tuple)
        assert back.to_dict() == d


def test_json_round_trip_is_lossless():
    import json

    r = _rec()
    assert Record.from_dict(json.loads(json.dumps(r.to_dict()))) == r


def test_case_id_survives_both_round_trips_because_it_is_the_bound_denominator():
    """`to_dict` wrote `case_id` and `from_dict` never read it back, so every record
    loaded from a stored artifact came back with no case identity at all.

    The round-trip tests above build records without a `case_id`, so they compare
    `None == None` and cannot see this field; R-44's denominator is the case, which is
    why a lost `case_id` is a lost unit rather than a lost label.
    """
    r = _rec(case_id="0335649ad46e60fe72fb5eeac62ea5b657df0ed55e77e54491ce8285438ec574")
    d = r.to_dict()
    assert d["case_id"] == r.case_id
    assert Record.from_dict(json.loads(json.dumps(d))) == r
    assert Record.from_dict(d).case_id == d["case_id"]
    # An artifact stored before the field existed must still load, hence `.get` and not
    # `d["case_id"]`: a missing key is legal history, a KeyError would be a regression.
    predating = {k: v for k, v in d.items() if k != "case_id"}
    assert Record.from_dict(predating).case_id is None


COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_noul_asks_of_one_case_group_to_one_case_after_a_round_trip():
    """64 archived cases x 4 asks x 3 repeats = 768 laya noul rows.

    The case, not the ask, is the unit a bound may divide by (R-44). Before
    `from_dict` read `case_id` back, this grouping came out 256.
    """
    from autorate.certify_choice import case_key

    rows = [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]
    noul = [Record.from_dict(d) for d in rows
            if d["qtype"] == "noul" and d["backend"] == "laya"]
    assert len(noul) == 768
    assert len({r.case_id for r in noul}) == 64, "case_id did not survive the round trip"
    assert len({case_key(r) for r in noul}) == 64
    choice = [Record.from_dict(d) for d in rows
              if d["qtype"] == "choice" and d["backend"] == "laya"]
    assert len({case_key(r) for r in choice}) == 64, (
        "choice grouping must stay at 64 while noul is repaired -- the fallback to `id` "
        "was hiding the bug here, and a fix that breaks this line is the wrong fix")


def test_the_errata_table_matches_the_function_that_produced_it():
    """A correction can go stale like any number, so the errata file is checked too.

    The check re-derives every published cell through the solver and compares FLOATS at 5e-5. It is
    not a byte comparison -- a byte check on a 4-decimal cell would be the weaker claim, since the
    solver's full-precision value has no bytes in this document -- and the second `2026-10-04` note in
    `docs/ERRATA.md`'s 2026-10-01 entry says so in the file that once claimed otherwise.

    The `5e-5` is not slack that can run out: it is the rounding half-step, because every published cell is
    a 4-decimal rounding of this solver's own value (measured agreement, 2.8e-6 to 4.888e-5). That fixes
    what the guard can see. A solver change that leaves every published 4th decimal intact passes by
    construction; a change that moves a value across a rounding boundary reddens it. So its drift
    sensitivity is set by where each cell sits relative to a midpoint. Comparing the rendered strings
    instead would be the same test EVERYWHERE EXCEPT at an exact rounding midpoint, and at a midpoint the
    string form is strictly stricter: measured 60 probes at the two basin edges of the ten cells, 9
    disagree and all 9 are float-passes/string-fails, none the other way -- `0.97855` is within `5e-5` of
    `0.9785` and renders `0.9786`. That form also has no stable tie rule (`f"{0.96095:.4f}"` renders
    `0.9609`), and it reads the published TEXT as well as the solver: a cell republished as `0.89` --
    correctly rounded, two digits shorter -- fails it while passing this one, so the two guards differ on
    formatting, which is a fragility a published table must not acquire. See the 2026-10-04 entry that
    withdraws that proposal and its 2026-10-05 note for these measurements. Making the guard able to see
    sub-4th-decimal drift means publishing more digits, which is a decision about this document, not about
    this test.
    """
    from pathlib import Path

    import re

    doc = Path(__file__).resolve().parents[1] / "docs" / "ERRATA.md"
    assert doc.exists(), "docs/ERRATA.md missing"
    ks = (2, 4, 10, 20, 51)
    lines = [l for l in doc.read_text().splitlines() if l.startswith("| `confidence >=")]
    assert len(lines) == 2, lines
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # The shape is part of the published claim: one gate cell plus one cell for every k. This line is
        # the FIRST catcher for both deletions, measured both ways: drop a MIDDLE cell (k=20) and the
        # guard reddens HERE with `5 == 1 + 5`, and only when this line is deleted as well does the same
        # plant reach the float loop below (it then re-aligns `0.9203` onto k=20 and misses by 1.157e-2).
        # What it exists for above all is the deletion the float check can never see: drop the LAST cell
        # and `zip` simply stops early, the four survivors still agree, and the row silently stops
        # claiming k=51. So this is a guard, not a pin -- it is the sole catcher of the last column.
        assert len(cells) == 1 + len(ks), (cells, len(cells))
        tau = float(re.search(r"(\d+\.\d+)", cells[0]).group(1))
        for k, quoted in zip(ks, cells[1:]):
            assert abs(p_max_for_entropy(target=tau, k=k) - float(quoted)) <= 5e-5, (tau, k, quoted)


def test_a_record_is_immutable_but_not_a_dict_key():
    from dataclasses import FrozenInstanceError

    r = _rec()
    with pytest.raises(FrozenInstanceError):
        r.gold = "urgent"
    # Documented limitation (PF-8): dict-valued fields make the frozen record
    # unhashable. Nothing in Plan A keys by Record, and this test is the guard
    # that the limitation is known rather than discovered.
    assert is_hashable_key(r) is False
    assert is_hashable_key((r.id, r.repeat)) is True
