"""Task 4: the one public data contract. Field names live here; statistics do not.

Every constant quoted from upstream is measured against the archived record it comes
from, not from prose.
"""
import json
import math
import re
from pathlib import Path

import pytest

from _thresholds import p_max_for_entropy
from autorate.records import (
    OPTIONAL_FIELDS,
    QTYPES,
    REQUIRED_FIELDS,
    MissingRecordField,
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


def test_a_stored_record_missing_a_required_field_is_refused_by_name_not_by_keyerror():
    """Review MAJ-4: `{"options" missing}` reached the operator as a `KeyError` traceback and rc 1.

    Measured on the route the reviewer measured -- `autorate audit --records <file of one row with
    "options" deleted>` -- the escape was `KeyError: 'options'` at `records.py:170` through
    `report.load_records`, and `cli.main` has no `KeyError` arm, so it left the documented 0/2/3/4
    contract as 1 while `cli.py`'s own docstring stated in the imperative that no such path exists.
    The fix is at the raising site (ledger R-115, the ruling that made `groups.py` raise
    `UndeclaredGroupKey(ValueError)` for the same shape of escape), so this asserts the loader
    boundary: the refusal is the dedicated class, and it names both the row and the field.
    """
    d = _rec(id="lifecycle-05").to_dict()
    del d["options"]
    with pytest.raises(MissingRecordField) as caught:
        Record.from_dict(d)
    message = str(caught.value)
    assert "record 'lifecycle-05'" in message, message
    assert "'options'" in message, message


def test_the_loader_refusal_is_a_valueerror_so_the_existing_cli_arm_maps_it_to_2():
    """Which class was chosen, and why the two neighbouring candidates were not.

    `KeyError` is what the code did, and it is ordinary dict access everywhere in this codebase: a
    central `main` arm for it would convert unrelated bugs into exit 2 with a helpful-looking
    message (R-115's reason for refusing that). `ReaderContractError` already maps to 2 through its
    own arm, but it is a `RuntimeError` because a reader POLICY refusal must escape
    `read_archive`'s per-line `ValueError` quarantine; a row that is not a record is not a policy
    refusal, so reusing it would collapse two distinguishable failures into one name. Being a
    `ValueError` subclass is what makes the existing arm catch it; being its own class is what makes
    it greppable and separately testable -- asserted here rather than in a docstring.
    """
    from autorate.readers.feishu_zh import ReaderContractError

    assert issubclass(MissingRecordField, ValueError)
    assert not issubclass(MissingRecordField, KeyError)
    assert not issubclass(MissingRecordField, RuntimeError)
    assert not issubclass(MissingRecordField, ReaderContractError)
    assert not issubclass(ReaderContractError, MissingRecordField)


def test_every_field_the_loader_indexes_blind_is_refused_by_name_not_defaulted():
    """The neighbouring shape, checked while the raising site was open (review MAJ-4).

    `repeat`, `qtype`, `backend`, `probs` and `id` were indexed exactly as blindly as `options`, so
    fixing only the reported key would have left five identical rc 1 escapes. Each is asserted
    individually -- and the `KeyError` below is the point: a plain `d[key]` that no longer fires is
    what the guard replaced, so this test reddens if the guard is narrowed back to one field.
    """
    assert REQUIRED_FIELDS == ("id", "qtype", "backend", "repeat", "options", "probs")
    for key in REQUIRED_FIELDS:
        d = _rec(id="row-under-test").to_dict()
        del d[key]
        with pytest.raises(MissingRecordField, match=re.escape("'%s'" % key)) as caught:
            Record.from_dict(d)
        # The row is named by its id whenever it still has one. `id` is the exception by design --
        # the anonymous case below is what pins what the refusal says when it cannot -- so this
        # states the rule as an equivalence rather than accepting either rendering.
        message = str(caught.value)
        assert ("row-under-test" in message) == (key != "id"), (key, message)
    # A row that states no identity is named by what it lacks, not by an id it does not have.
    anonymous = _rec(id="row-under-test").to_dict()
    del anonymous["id"]
    with pytest.raises(MissingRecordField) as caught:
        Record.from_dict(anonymous)
    assert "no 'id'" in str(caught.value), str(caught.value)
    assert "row-under-test" not in str(caught.value), str(caught.value)


def test_the_fields_the_contract_declares_optional_still_load_with_the_constructors_default():
    """The other half of the guard, so the fix cannot become a strictness regression.

    `gold` absent is not a defect but a shape under test (a record that is gatable and never
    calibratable), `case_id` absent is legal history for an artefact stored before the field existed
    (`test_case_id_survives_both_round_trips...`), and the rest carry dataclass defaults. This is
    also the census of what absence is currently DEFAULTED rather than raised: `u` lands on 0.0,
    which the constructor's own message calls the draw a certified set is reproducible only with --
    reported as a latent question, deliberately not changed by this fix, which is about the fields
    the loader reads blind.
    """
    assert OPTIONAL_FIELDS == ("gold", "predicted", "case_id", "slices", "scores", "seed", "u",
                               "meta")
    d = _rec(id="lifecycle-05", case_id="abc", slices={"family": "lifecycle"},
             scores={"reported_confidence": 0.1}, seed=13, u=0.25).to_dict()
    for key in OPTIONAL_FIELDS:
        del d[key]
    r = Record.from_dict(d)
    assert r.gold is None and r.predicted is None and r.case_id is None
    assert r.slices == {} and r.scores == {} and r.meta == {}
    assert r.seed == 0 and r.u == 0.0


def test_the_load_path_propagates_the_refusal_undefaulted_and_uncollected(tmp_path):
    """No `except Exception` on the route: the row is refused, not skipped and not repaired.

    The honest completion of MAJ-4 is the CLI assertion -- `autorate audit --records <bad file>`
    exits 2, not 1 -- and `tests/test_cli.py` is another lane's file, so it is recorded as the
    follow-up rather than made here. This is the layer below it: the refusal reaches the command
    intact, so whichever arm fires is `main`'s existing `ValueError` one, and `load_records` returns
    nothing at all (an audit over the rows that DID load would be the success path this defect
    must not become).
    """
    from autorate.report import load_records

    d = _rec(id="lifecycle-05").to_dict()
    del d["options"]
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps(d) + "\n")
    with pytest.raises(MissingRecordField) as caught:
        load_records(path)
    assert type(caught.value) is MissingRecordField, type(caught.value)
    # A good row beside the bad one is not silently published as a partial population.
    good = _rec(id="lifecycle-06").to_dict()
    path.write_text(json.dumps(good) + "\n" + json.dumps(d) + "\n")
    with pytest.raises(MissingRecordField):
        load_records(path)


COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"
ERRATA = Path(__file__).resolve().parents[1] / "docs" / "ERRATA.md"

# The rounding half-step of a 4-decimal published cell, and the tolerance the errata guard uses. One
# constant, both places: the guard compares through `_float_form_agrees` at `<= HALF_STEP` and the probe
# sweep walks the two basin edges `quoted +/- HALF_STEP`, and those are the same number -- making it a
# literal in one place and a magic constant in the other is how a tolerance and its own justification
# drift apart.
HALF_STEP = 5e-5


def _published_gate_table(text):
    """Read the published gate table out of `docs/ERRATA.md`: its header columns and its two rows.

    The option counts come from the HEADER ROW, not from a tuple typed in this file. `ks = (2, 4, 10,
    20, 51)` was hand-written here while the shape guard compared each published row against it, so a
    table whose header and cells disagree -- add a `k=100` column to the header and leave the rows
    alone -- satisfied the guard that exists to catch exactly that. Now the header is the producer of
    `ks`, and the guard checks the cells against it.

    The table arrives as TEXT rather than being read here, because a guard whose producer is a file can
    only be falsified by editing the file: every plant below hands this same reader a doctored table and
    shows the guard reddening on it, which is the difference between a check and a transcription.

    Returns `(ks, rows)` where each row is `(gate_cell, cells)` and `cells` keeps the gate cell at
    index 0, which is the shape the guard below asserts on.
    """
    lines = text.splitlines()
    headers = [l for l in lines if l.startswith("| gate |")]
    assert len(headers) == 1, headers
    header_cells = [c.strip() for c in headers[0].strip().strip("|").split("|")]
    columns = [c for c in header_cells[1:] if c.startswith("k=")]
    assert columns, header_cells
    ks = tuple(int(c[len("k="):]) for c in columns)
    rows = []
    for line in lines:
        if line.startswith("| `confidence >="):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            gate = re.search(r"(\d+\.\d+)", cells[0])
            assert gate, cells
            rows.append((cells[0], cells))
    assert len(rows) == 2, rows
    return ks, rows


def _published_cells(text):
    """Every `(tau, k, quoted)` cell the published gate table carries -- ten for the two rows.

    Derived from `_published_gate_table`, so the sweep below probes the cells the document actually
    publishes and not a copy of them typed into this file.
    """
    ks, rows = _published_gate_table(text)
    cells = []
    for gate, line_cells in rows:
        tau = float(re.search(r"(\d+\.\d+)", gate).group(1))
        cells.extend((tau, k, quoted) for k, quoted in zip(ks, line_cells[1:]))
    return cells


def _float_form_agrees(value, quoted) -> bool:
    """The guard's own comparison: the solver within the rounding half-step of the published cell."""
    return abs(value - float(quoted)) <= HALF_STEP


def _string_form_agrees(value, quoted) -> bool:
    """The withdrawn proposal's comparison: the rendered value must equal the published TEXT.

    Kept next to `_float_form_agrees` because the whole 2026-10-04 row is about what the two do and do
    not share, and a reader should be able to run both from one place rather than re-type either.
    """
    return f"{value:.4f}" == quoted


def _basin_probes(cells):
    """Six probes per published cell: each of its two rounding-basin edges, plus one double each side.

    The edge of `quoted`'s basin is `quoted +/- HALF_STEP`, computed in doubles -- the recipe the
    2026-10-05 note of the 2026-10-04 errata entry gave as a parenthetical ("the edge itself plus one
    representable double each side") and no code implemented. Ten cells make the 60 probes that row
    counts, and this is where that count is produced rather than remembered.
    """
    probes = []
    for tau, k, quoted in cells:
        q = float(quoted)
        for edge in (q - HALF_STEP, q + HALF_STEP):
            for x in (edge, math.nextafter(edge, -math.inf), math.nextafter(edge, math.inf)):
                probes.append((tau, k, quoted, x))
    return probes


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

    The check re-derives every published cell through the solver and compares FLOATS at `HALF_STEP` --
    the rounding half-step of a 4-decimal cell, the same constant the basin sweep below walks its edges
    with. It is not a byte comparison -- a byte check on a 4-decimal cell would be the weaker claim,
    since the solver's full-precision value has no bytes in this document -- and the second
    `2026-10-04` note in `docs/ERRATA.md`'s 2026-10-01 entry says so in the file that once claimed
    otherwise.

    `HALF_STEP` is not slack that can run out: it is the half-step, because every published cell is a
    4-decimal rounding of this solver's own value. That fixes what the guard can see. A solver change
    that leaves every published 4th decimal intact passes by construction; a change that moves a value
    across a rounding boundary reddens it. So its drift sensitivity is set by where each cell sits
    relative to a midpoint.

    Every figure this docstring used to state as a measurement of its own -- the `2.8e-6 to 4.888e-5`
    agreement, the binding cell and its headroom, the 60 probes and the 9 disagreements, `0.97855`,
    `f"{0.96095:.4f}"` -> `0.9609`, `0.889972135562` and the `0.89` republishing argument -- is produced
    by `test_the_string_form_is_strictly_stricter_at_the_ten_basin_edges`, which reads this same table
    through this same reader and sweeps this same solver. Those were the present-tense claims of a run
    nobody could re-run (R-87); a docstring that quotes them is pointing at that test, not at a scratch
    directory. Comparing the rendered strings instead would be the same test EVERYWHERE EXCEPT at an
    exact rounding midpoint, and at a midpoint the string form is strictly stricter -- that is what the
    producer demonstrates, cell by cell. It also reads the published TEXT as well as the solver, so a
    cell republished as `0.89` -- correctly rounded, two digits shorter -- fails it while passing this
    one: the two guards differ on formatting, which is a fragility a published table must not acquire.
    See the 2026-10-04 entry that withdraws that proposal, its 2026-10-05 note, and the 2026-10-07 row
    that gives the whole set a producer. Making the guard able to see sub-4th-decimal drift means
    publishing more digits, which is a decision about this document, not about this test.
    """
    assert ERRATA.exists(), "docs/ERRATA.md missing"
    text = ERRATA.read_text()
    ks, rows = _published_gate_table(text)
    for gate, cells in rows:
        # The shape is part of the published claim: one gate cell plus one cell for every k. `ks` comes
        # from the table's own HEADER ROW now, so the claim "the row has one cell per column" is
        # checked against the columns rather than against a tuple typed here. The first catcher for a
        # deleted cell is still this line, measured both ways: drop a MIDDLE cell (k=20) and the guard
        # reddens HERE with `5 == 1 + 5`, and only when this line is deleted as well does the same
        # plant reach the float loop below (it then re-aligns `0.9203` onto k=20 and misses by
        # 1.157e-2). What it exists for above all is the deletion the float check can never see: drop
        # the LAST cell and `zip` simply stops early, the four survivors still agree, and the row
        # silently stops claiming k=51. So this is a guard, not a pin -- it is the sole catcher of the
        # last column, and the plant below is what says so.
        assert len(cells) == 1 + len(ks), (cells, len(cells))
        tau = float(re.search(r"(\d+\.\d+)", gate).group(1))
        for k, quoted in zip(ks, cells[1:]):
            assert _float_form_agrees(p_max_for_entropy(target=tau, k=k), quoted), (tau, k, quoted)

    # The header-as-producer is a guard that can fail, so it is executed rather than described. Both
    # directions of a table whose columns and cells disagree are planted by rewriting the header line
    # FROM the parsed `ks` -- no column name is typed here, so the plant cannot drift from the table --
    # and each planted table is then run through the float loop exactly as `zip` hands it: every pair it
    # does make still agrees (adding a column leaves a promised pair unmade, dropping one leaves a
    # published cell unclaimed), so the comparison is silent on both and only the shape line above
    # is loud. That is what "a guard, not a pin" has to mean, and it is measured rather than asserted.
    header = next(l for l in text.splitlines() if l.startswith("| gate |"))
    for planted_ks, why in ((ks + (100,), "a k=100 column added to the header alone"),
                            (ks[:-1], "the header's last column deleted alone")):
        planted_header = "| gate | " + " | ".join("k=%d" % k for k in planted_ks) + " |"
        planted_ks_read, planted_rows = _published_gate_table(text.replace(header, planted_header))
        assert planted_ks_read == planted_ks, (why, planted_ks_read)
        assert all(len(p_cells) != 1 + len(planted_ks) for _, p_cells in planted_rows), (why,
                                                                                        planted_rows)
        survivors = []
        for gate, p_cells in planted_rows:
            tau = float(re.search(r"(\d+\.\d+)", gate).group(1))
            survivors.extend(_float_form_agrees(p_max_for_entropy(target=tau, k=k), quoted)
                             for k, quoted in zip(planted_ks, p_cells[1:]))
        assert all(survivors), (why, survivors)
        # The float loop always under-covers a table whose columns and cells disagree: compared pairs is
        # fewer than the header PROMISES when a column has no cell (10 of 12), and fewer than the table
        # PUBLISHES when a cell has no column (8 of 10). Either way every comparison it does make passes,
        # which is exactly why the shape line above is the guard and this loop is not.
        compared = len(survivors)
        promised = len(planted_ks) * len(planted_rows)
        published = sum(len(p_cells) - 1 for _, p_cells in planted_rows)
        assert compared < max(promised, published), (why, compared, promised, published)


def test_the_string_form_is_strictly_stricter_at_the_ten_basin_edges():
    """The producer for every probe figure this file and `docs/ERRATA.md` state in present tense.

    R-87's standing rule is that a number quoted in the present tense needs a producer the suite runs.
    The 2026-10-04 entry and its 2026-10-05 note published a set of them -- `60 probes`, `9
    disagreements`, `zero in the other direction`, the nine named edges, `4.887545e-05`, `97.75%`,
    `tau=0.50, k=10`, `1.125e-6`, the `2.8e-6 to 4.888e-5` spread, `f"{0.96095:.4f}"` -> `0.9609`,
    `0.889972135562`, and the `0.89` republishing argument -- and for two rounds the only code beside
    them was `<= 5e-5`, which cannot see a single one. This test is option (a) of that ruling: the
    values are load-bearing for a published claim about the guard's own drift sensitivity, so they are
    recomputed here rather than demoted to a dated record. Each is derived from the published table
    through `_published_gate_table` and from the shared bisection, so a solver change or a republished
    cell that moves a figure reddens THIS test instead of leaving the prose behind it.

    Two tolerances are stated as decisions rather than inherited. The agreement figures are published at
    3 or 4 significant digits, whose own half-steps are 5e-8, 5e-9, 5e-10 and 5e-9; the two thin ones
    are bracketed at `1e-8` -- 2e-4 of the basin this whole row is about, and eight orders of magnitude
    above the last-bit libm drift R-121 measured -- because a bracket a reader cannot meet on their own
    libc is a second defect rather than a stricter gate. The `97.75%` ratio is held to the half-step of
    its own published digits, which it clears by 5x.

    What makes this more than a transcription of the note: the disagreement SET is computed from the
    table, so the plants at the end -- a cell republished with two digits fewer, and the binding cell
    transcribed one last digit wide -- change it. A count that could only move when the assertion above
    it were edited would not be a guard.
    """
    assert ERRATA.exists(), "docs/ERRATA.md missing"
    cells = _published_cells(ERRATA.read_text())
    assert len(cells) == 10, cells

    # 1. all ten published cells pass BOTH forms: `0` mismatches, the consistency check that made the
    #    equivalence 2026-10-04 argued from visible in the first place.
    devs = []
    for tau, k, quoted in cells:
        solver = p_max_for_entropy(target=tau, k=k)
        assert _float_form_agrees(solver, quoted), (tau, k, quoted)
        assert _string_form_agrees(solver, quoted), (tau, k, quoted)
        devs.append((abs(solver - float(quoted)), tau, k, quoted))

    # 2. the agreement spread, the cell that binds it, and the headroom beside it. These are three
    #    renderings of ONE measurement -- the largest deviation, its ratio to the ceiling, the ceiling
    #    minus it -- so they pin the published text, they do not corroborate each other.
    worst = max(devs, key=lambda d: d[0])
    best = min(devs, key=lambda d: d[0])
    assert best[0] == pytest.approx(2.8e-6, abs=1e-8), best
    assert worst[0] == pytest.approx(4.888e-5, abs=1e-8), worst
    assert (worst[1], worst[2]) == (0.5, 10), worst
    assert worst[0] / HALF_STEP == pytest.approx(0.9775, abs=5e-5), worst
    assert HALF_STEP - worst[0] == pytest.approx(1.125e-6, abs=1e-8), worst

    # 3. the sweep: six probes per cell -- each basin edge, then one representable double either side.
    probes = _basin_probes(cells)
    assert len(probes) == 60, len(probes)
    forward, reverse = [], []
    for tau, k, quoted, x in probes:
        if _float_form_agrees(x, quoted) and not _string_form_agrees(x, quoted):
            forward.append((x, quoted))
        elif _string_form_agrees(x, quoted) and not _float_form_agrees(x, quoted):
            reverse.append((x, quoted))
    assert len(forward) == 9, [(f"{x:.6f}", q) for x, q in forward]
    assert reverse == [], [(f"{x:.6f}", q) for x, q in reverse]
    # The nine edges the 2026-10-05 note names, each "within `5e-5` of the cell and rendering to the
    # wrong 4 decimals", compared as the five-decimal texts a reader checks by eye.
    published_edges = ("0.97855", "0.96085", "0.94265", "0.93185", "0.92035", "0.89005", "0.81065",
                       "0.69895", "0.66115")
    measured_edges = sorted((f"{x:.5f}" for x, _ in forward), reverse=True)
    assert measured_edges == sorted(published_edges, reverse=True), (measured_edges,
                                                                    sorted(published_edges,
                                                                           reverse=True))
    for x, quoted in forward:
        assert f"{x:.4f}" != quoted, (x, quoted)
        assert _float_form_agrees(x, quoted), (x, quoted)

    # 4. the tie rule the string form does not have, and the value the note quotes for k=2.
    assert f"{0.96095:.4f}" == "0.9609"
    k2 = p_max_for_entropy(target=0.50, k=2)
    assert k2 == pytest.approx(0.889972135562, abs=1e-8), k2

    # 5. the plants. `docs/ERRATA.md` is not edited for any of this: the cell list is doctored in memory
    #    and fed to the same predicates, which is the only way to show a file-fed guard bites without
    #    leaving a published correction wrong on disk.
    republished = [(tau, k, ("0.89" if (tau, k) == (0.5, 2) else quoted)) for tau, k, quoted in cells]
    assert len(republished) == 10, republished
    # correctly rounded, two digits shorter: the float check still passes everywhere...
    assert all(_float_form_agrees(p_max_for_entropy(target=t, k=kk), q) for t, kk, q in republished)
    # ...and the string check fails on the republished cell alone, which is the formatting-as-drift
    # fragility the withdrawal argued from.
    assert not _string_form_agrees(k2, "0.89"), k2
    assert sum(1 for t, kk, q in republished
               if not _string_form_agrees(p_max_for_entropy(target=t, k=kk), q)) == 1, republished
    transcribed = [(tau, k, ("%.4f" % (float(quoted) + 1e-4) if (tau, k) == (0.5, 10) else quoted))
                   for tau, k, quoted in cells]
    assert not all(_float_form_agrees(p_max_for_entropy(target=t, k=kk), q)
                   for t, kk, q in transcribed), transcribed
    planted_forward = [x for _, _, q, x in _basin_probes(transcribed)
                       if _float_form_agrees(x, q) and not _string_form_agrees(x, q)]
    assert len(planted_forward) != 9, len(planted_forward)
    assert sorted((f"{x:.5f}" for x in planted_forward), reverse=True) != sorted(
        published_edges, reverse=True), planted_forward


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
