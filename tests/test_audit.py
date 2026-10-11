"""G2: the gate the reference README instructs, measured against what it implies.

Spec §2 row G2 asks for one comparison and one number, and the committed corpus makes three traps
out of getting it wrong (each measured, none read off a plan):

* 1,536 of the 1,919 archived rows carry `gold is None`, so grading every row reports 6.67x as if
  it were a finding -- `test_the_unlabelled_majority_is_excluded_and_the_exclusion_is_published`;
* the row and case denominators coincide for `laya` and diverge hard for `jev` (180 rows against 59
  cases), so the two must be published apart;
* 3.70x is five wrong out of NINE cases, a point estimate that needs its interval before it is
  anything at all.

Assertions are on relationships, and on figures re-derived here from the committed records through
the same owners `audit.py` calls (`case_count.count_outcome`, `tails.clopper_pearson_upper`) -- never
on a hand-typed multiple.
"""
import copy
import importlib
import json
import math
from pathlib import Path

import pytest

from _records import choice_record
from autorate.audit import (COLLAPSES, DEFAULT_DELTA, DEFAULT_GATE, DEFAULT_GRID, NO_ANSWER,
                            NO_GOLD, AuditDriftError, audit_fields, check_audit, frontier,
                            render_audit)
from autorate.case_count import Verdict, case_key, count_outcome
from autorate.certificate import CANONICALISED_BOUND_FIELDS, canonicalise_bound
from autorate.cli import EXIT_CERTIFIED, EXIT_NOT_CERTIFIABLE, EXIT_USAGE, main
from autorate.records import max_confidence
from autorate.report import load_records
from autorate.scales import scale_attribution
from autorate.tails import clopper_pearson_upper

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"
# The artefact `autorate audit` writes and this suite holds against the renderer. It is read here
# only to prove the ceiling moves no rendered figure; nothing in this file writes it.
AUDIT_MD = Path(__file__).resolve().parents[1] / "docs" / "AUDIT.md"


@pytest.fixture(scope="module")
def by_backend():
    return load_records(COMMITTED)


@pytest.fixture(scope="module")
def laya(by_backend):
    """The whole `laya` population, 960 rows: 192 labelled choice rows and 768 unlabelled noul.

    The brief's fixture pre-filtered on `qtype == "choice"`. Here the audit's own exclusion does the
    filtering, because the exclusion is one of the things under test and a fixture that has already
    applied it cannot show it working.
    """
    return by_backend["laya"]


@pytest.fixture(scope="module")
def laya_choice(by_backend):
    return [r for r in by_backend["laya"] if r.qtype == "choice"]


@pytest.fixture(scope="module")
def jev(by_backend):
    return by_backend["jev"]


@pytest.fixture(scope="module")
def audits(laya, jev):
    return {"laya": audit_fields(laya), "jev": audit_fields(jev)}


# --- the brief's Step 1: relationships, not typed figures ------------------------------------

def test_every_field_the_readme_offers_misses_its_own_implied_error_rate(laya_choice):
    rows = audit_fields(laya_choice, gate=0.85)
    assert set(rows) == {"confidence", "answer_confidence", "act_probability"}, rows
    for name, r in rows.items():
        assert r["automated_cases"] > 0, name
        assert r["measured_error"] > r["implied_error"], (name, r)
        assert r["multiple"] > 1.0, (name, r["multiple"])


def test_the_denominator_is_cases_and_says_so(laya_choice):
    # 192 archived laya choice rows are 64 cases x 3 repeats carrying the SAME probability vector and
    # the SAME published confidence -- not identical ROWS, since `meta`, `repeat` and `slices` differ
    # (jev's 191 rows are the same 64 cases carrying 1-3 distinct vectors). Counting rows would print
    # a 3x larger sample than the one that exists (R-36, R-44).
    rows = audit_fields(laya_choice, gate=0.85)
    assert rows["confidence"]["n_records"] == 192
    assert rows["confidence"]["n_cases"] == 64


def test_where_the_sample_cannot_bound_the_gate_the_audit_reports_that_instead(laya_choice):
    r = audit_fields(laya_choice, gate=0.85)["confidence"]
    assert r["bound"] is not None and r["bound"] > 0.9, r
    assert r["informative"] is False, "a 0.97 bound is not a certificate of anything"
    assert r["note"].startswith("NOT_INFORMATIVE"), r["note"]


def test_the_audit_names_the_scale_each_field_actually_is(laya_choice):
    rows = audit_fields(laya_choice, gate=0.85)
    assert rows["confidence"]["attributed_scale"] == "confidence_entropy", rows["confidence"]
    # `answer_confidence` is computed here from `probs`, so attributing it would claim a finding
    # about upstream's number that this tool never measured.
    assert "not attributed" in rows["answer_confidence"]["attributed_scale"]


def test_the_attribution_is_asked_per_slice_and_agrees_with_the_owner(laya_choice, jev):
    """The audit's `attributed_scale` is `scale_attribution`'s own verdict, not a restated word.

    R-56: attribution is per `(backend, qtype)`, because a batch spanning slices raises. The audit
    groups first, so the row and a direct call to the owner must agree.
    """
    rows = audit_fields(jev, gate=0.85)
    assert rows["confidence"]["slices"] == ["jev/choice"], rows["confidence"]["slices"]
    assert rows["confidence"]["attributed_scale"] == scale_attribution(
        [r for r in jev if r.qtype == "choice"])["verdict"]
    # The mixture travels beside the aggregate word: `jev: neither` is false for most of its rows,
    # and a published row that printed only the verdict would be the over-claim this file refuses.
    mixture = rows["confidence"]["attribution"]["jev/choice"]["row_mixture"]
    assert sum(mixture.values()) == rows["confidence"]["n_records"], mixture
    assert mixture["both"] > 0, mixture


def test_the_published_curve_exists_and_rises_with_the_gate(laya_choice):
    rows = frontier(laya_choice, ("confidence", "answer_confidence"),
                    grid=(0.0, 0.3, 0.6, 0.85, 0.99))
    for field in ("confidence", "answer_confidence"):
        pts = [r for r in rows if r["field"] == field]
        assert [r["automated_cases"] for r in pts] == sorted(
            [r["automated_cases"] for r in pts], reverse=True), pts
    assert {r["field"] for r in rows} == {"confidence", "answer_confidence"}


def test_the_curve_is_carried_in_the_row_so_no_prose_has_to_reproduce_it(laya_choice):
    r = audit_fields(laya_choice, gate=0.85)["answer_confidence"]
    assert [p["lambda"] for p in r["curve"]] == list(DEFAULT_GRID), r["curve"]
    at_gate = [p for p in r["curve"] if p["lambda"] == 0.85][0]
    # The curve's own point at the published gate must equal the headline row: one producer, so the
    # artefact cannot print a frontier figure and a table figure that disagree with each other.
    assert at_gate["automated_cases"] == r["automated_cases"], at_gate
    assert at_gate["erroneous_cases"] == r["erroneous_cases"], at_gate
    assert at_gate["bound"] == pytest.approx(r["bound"], abs=1e-12), at_gate


# --- MAJ-1: §7.3's frontier must reach the artefact, not just the data structure -------------
#
# `frontier` has built this curve since the commit under review, three comments said the artefact
# printed it, and `grep -c "curve\|lambda" docs/AUDIT.md` answered 0. The guards below are what make
# those comments descriptions; they are also the guards that redden if the renderer starts computing
# the curve itself instead of publishing the producer's numbers.

_CURVE_KEYS = ("lambda", "implied", "automated", "erroneous", "coverage", "error", "bound")


def _curve_rows(text: str) -> dict:
    """Every rendered curve block, keyed by (backend, field), as the strings the artefact prints.

    Parsed out of the text rather than compared to a whole-file literal, so a guard can name the
    point that moved. The values stay strings: the assertion that matters is that the printed figure
    IS the stored figure at the published precision, and re-reading it as a float would let a
    different rounding pass.
    """
    blocks = {}
    backend = None
    field = None
    for line in text.splitlines():
        if line.startswith("## `"):
            backend = line.strip("# ").strip("`")
            field = None
        elif "Risk-coverage curve for `" in line:
            field = line.split("Risk-coverage curve for `")[1].split("`")[0]
            blocks[(backend, field)] = []
        elif field is not None and line.startswith("| `"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != len(_CURVE_KEYS):
                continue
            blocks[(backend, field)].append(dict(
                zip(_CURVE_KEYS, [cells[0].split(" ")[0].strip("`")] + cells[1:])))
            if "(the gate above)" in cells[0]:
                blocks[(backend, field)][-1]["is_gate"] = True
        elif field is not None and line.startswith("- ") and blocks.get((backend, field)):
            field = None
    return blocks


def test_the_artefact_prints_the_curve_for_every_field_and_backend(laya, jev):
    """Red before this round's fix: the curve existed in the row and nowhere in the artefact.

    Every published cell is compared to the figure `audit_fields` stored, formatted at the precision
    the artefact uses -- so the guard reddens if the renderer drops a block, drops a point, or starts
    printing a number the producer did not compute.
    """
    audits = {b: audit_fields(rs, gate=DEFAULT_GATE) for b, rs in (("laya", laya), ("jev", jev))}
    parsed = _curve_rows(render_audit(audits))
    assert set(parsed) == {(b, f) for b in sorted(audits) for f in sorted(audits[b])}, sorted(parsed)
    for (backend, field), cells in sorted(parsed.items()):
        stored = audits[backend][field]["curve"]
        assert len(cells) == len(stored), (backend, field, len(cells), len(stored))
        for cell, point in zip(cells, stored):
            assert cell["lambda"] == "%.2f" % point["lambda"], (backend, field, cell, point)
            assert cell["implied"] == "%.2f" % point["implied_error"], (backend, field, cell)
            assert cell["automated"] == str(point["automated_cases"]), (backend, field, cell)
            assert cell["erroneous"] == str(point["erroneous_cases"]), (backend, field, cell)
            assert cell["coverage"] == _fmt_like(point["coverage"]), (backend, field, cell)
            assert cell["error"] == _fmt_like(point["measured_error"]), (backend, field, cell)
            assert cell["bound"] == _fmt_like(point["bound"]), (backend, field, cell, point)


def _fmt_like(value) -> str:
    """The artefact's own rendering of a stored figure: four decimals, or the dash for `None`."""
    return "-" if value is None else "%.4f" % value


def test_the_thinnest_point_of_the_published_curve_is_printed_not_hidden(laya, jev):
    """The reviewer's named example: laya `answer_confidence` at `lambda = 0.99`.

    That point automates nothing, so a renderer that showed only the informative end of the sweep
    would drop it -- and dropping it is how a frontier becomes a headline again.
    """
    parsed = _curve_rows(render_audit({"laya": audit_fields(laya), "jev": audit_fields(jev)}))
    last = parsed[("laya", "answer_confidence")][-1]
    assert last["lambda"] == "0.99", last
    assert (last["automated"], last["erroneous"]) == ("0", "0"), last
    assert last["error"] == "-" and last["bound"] == "-", last


def test_the_curve_block_names_the_denominator_of_every_ratio_it_prints(laya, jev):
    """R-166's defect class, applied to this renderer: a ratio with no denominator is not a number.

    The curve publishes three ratios per point. Each header here has to say which counts it divides,
    or the reader is back to guessing whether 0.7823 bounds nine cases or twenty-seven rows.
    """
    text = render_audit({"laya": audit_fields(laya), "jev": audit_fields(jev)})
    laya_cases = audit_fields(laya)["answer_confidence"]["n_cases"]
    header = [l for l in text.splitlines() if l.startswith("| lambda |")][0]
    assert "automated cases (of %d cases)" % laya_cases in header, header
    assert "coverage (automated / %d cases)" % laya_cases in header, header
    assert "measured error (wrong / automated cases)" in header, header
    assert "CP upper (1-sided, `delta = %.2f`)" % DEFAULT_DELTA in header, header
    assert "The unit is the CASE" in text, "the curve must keep saying what it counts"


def test_the_curve_carries_the_delta_the_run_actually_used(laya_choice):
    """MAJ-1's compounding detail: `frontier` used to hard-code `DEFAULT_DELTA` for its bounds.

    Under `--delta 0.10` the header said 0.10 and the curve answered at 0.05, so the artefact
    published two rubrics. This asks the run's own delta out of the curve, at the gate, against
    `tails` -- and that the 0.05 figure is gone, not merely absent from one column.
    """
    rows = audit_fields(laya_choice, gate=0.85, delta=0.10)
    text = render_audit({"laya": rows})
    at_gate = [p for p in rows["answer_confidence"]["curve"] if p["lambda"] == 0.85][0]
    assert at_gate["delta"] == 0.10, at_gate
    assert at_gate["bound"] == pytest.approx(canonicalise_bound(
        clopper_pearson_upper(5, 9, 0.10)), abs=1e-12), at_gate
    assert "%.4f" % at_gate["bound"] in text, "the run's own bound never reached the artefact"
    assert "`delta = 0.10`" in text, text[:600]
    # The 0.05 one-sided answer for 5-of-9 is 0.8312, and it must not be anywhere in the curve. It
    # DOES appear elsewhere in this artefact by design: the headline table's two-sided endpoint is
    # the same owner called at `delta / 2`, so a 0.10 run publishes 0.8312 legitimately. The guard
    # therefore reads the curve block, which is one-sided by construction.
    default_at_gate = canonicalise_bound(clopper_pearson_upper(5, 9, DEFAULT_DELTA))
    curve_cells = _curve_rows(text)[("laya", "answer_confidence")]
    assert "%.4f" % default_at_gate not in [c["bound"] for c in curve_cells], curve_cells
    assert curve_cells[3]["bound"] == "%.4f" % at_gate["bound"], curve_cells[3]
    # `frontier` is a producer, not a reader of the module default: the parameter is the level, and
    # it is the same producer whether the caller passes it positionally or by name.
    assert [p["bound"] for p in frontier(laya_choice, ("answer_confidence",), DEFAULT_GRID, 0.10)] \
        == [p["bound"] for p in
            frontier(laya_choice, ("answer_confidence",), DEFAULT_GRID, delta=0.10)]
    assert [p["delta"] for p in frontier(laya_choice, ("answer_confidence",), DEFAULT_GRID, 0.10)] \
        == [0.10] * len(DEFAULT_GRID)


def test_the_frontier_refuses_an_unusable_delta_as_a_usage_error(laya_choice):
    """`frontier` is a public entry point, so its rubric check cannot be left to the caller.

    An out-of-range `delta` used to reach `clopper_pearson_upper`, which raises `ValueError` from
    `tails` -- rc 2 either way -- but the message named a binomial tail rather than the operator's
    argument, and the same guard on the gate side has refused by name since the first round.
    """
    for bad in (0.0, 1.0, -0.5):
        with pytest.raises(ValueError, match="delta"):
            frontier(laya_choice, ("confidence",), DEFAULT_GRID, bad)


def test_the_curve_covers_the_gate_the_run_published(laya_choice):
    """A grid that does not name the gate would print a frontier the headline is not on.

    `--gate 0.5` is an operator's question and `DEFAULT_GRID` does not contain 0.5, so
    `audit_fields` adds it. Refusing to sweep the gate is the same defect as printing a curve the
    table cannot be found in.
    """
    rows = audit_fields(laya_choice, gate=0.5)
    lambdas = [p["lambda"] for p in rows["answer_confidence"]["curve"]]
    assert 0.5 in lambdas, lambdas
    assert lambdas == sorted(lambdas), lambdas
    at_gate = [p for p in rows["answer_confidence"]["curve"] if p["lambda"] == 0.5][0]
    assert at_gate["automated_cases"] == rows["answer_confidence"]["automated_cases"], at_gate



def test_rendered_audit_contains_no_machine_path_and_no_unproduced_number(laya_choice):
    text = render_audit({"laya": audit_fields(laya_choice, gate=0.85)})
    assert "laya-0.3.20/" not in text or "research/benchmarks" in text
    for tok in ("/Users/", "/home/"):
        assert tok not in text, tok
    assert "3.33" in text, "the multiple must be produced, not narrated"


# --- trap 1: `noul` is not a labelled task, and the exclusion has to be visible --------------

def test_the_unlabelled_majority_is_excluded_and_the_exclusion_is_published(laya, jev):
    for backend, population, labelled in (("laya", laya, 192), ("jev", jev, 191)):
        rows = audit_fields(population, gate=0.85)
        assert len(population) == labelled + 768
        for field, r in rows.items():
            label = "%s/%s" % (backend, field)
            assert r["n_rows_handed_over"] == len(population), label
            assert r["n_records"] == labelled, label
            assert r["excluded_unlabelled"] == 768, label
            assert r["excluded_no_answer"] == 0, label
            assert r["excluded_reasons"] == {NO_GOLD: 768}, label
            assert "gold is None" in next(iter(r["excluded_reasons"])), label
    audited = [r for r in laya if r.gold is not None]
    assert len(audited) == 192 and all(r.gold is not None for r in audited)


def test_an_unlabelled_row_is_refused_by_the_counter_that_scores_it(by_backend):
    """The premise's 6.67x, shown at its source rather than quoted.

    `gold is None` against a `true`/`false` `predicted` makes wrong-by-inequality true on 100% of
    noul rows. `count_outcome` refuses such a row instead of guessing, which is why the filter is a
    precondition here and not a courtesy -- and why an audit that skipped the filter would publish a
    rate about nothing.
    """
    noul = [r for r in by_backend["laya"] if r.qtype == "noul"]
    assert len(noul) == 768 and all(r.gold is None for r in noul)
    with pytest.raises(ValueError, match="no gold label"):
        count_outcome(noul, lambda r: Verdict("auto", r.predicted, 1.0))
    with pytest.raises(ValueError, match="gold is None"):
        audit_fields(noul, gate=0.85)
    with pytest.raises(ValueError, match="gold is None"):
        frontier(noul, ("confidence",))


def test_a_record_that_states_no_answer_is_counted_in_a_separate_bucket():
    """`NO_ANSWER` is a published bucket with its own count, not a fold into `NO_GOLD`.

    It needs a surviving row beside it: a population of nothing but unanswerable records is the same
    question as an unlabelled one, and the audit refuses it as rc 2 rather than scoring it -- which
    is what `test_an_unlabelled_only_records_file_is_rc_2_not_a_rate` pins at the CLI.
    """
    silent = choice_record(id="r0", case_id="c0", options=("a", "b"), probs=(0.9, 0.1),
                           gold="a", predicted=None)
    answered = choice_record(id="r1", case_id="c1", options=("a", "b"), probs=(0.9, 0.1),
                             gold="a", predicted="a")
    rows = audit_fields([silent, answered], fields=("answer_confidence",))
    r = rows["answer_confidence"]
    assert r["excluded_no_answer"] == 1, r
    assert r["excluded_unlabelled"] == 0, r
    assert r["excluded_reasons"] == {NO_ANSWER: 1}, r["excluded_reasons"]
    assert r["n_records"] == 1 and r["n_cases"] == 1, r
    text = render_audit({"synthetic": rows})
    assert "predicted is None" in text, text


def test_an_empty_population_is_a_usage_error(laya_choice):
    with pytest.raises(ValueError, match="no records handed"):
        audit_fields([], gate=0.85)
    with pytest.raises(ValueError, match="nothing to measure"):
        frontier([], ("confidence",))


# --- trap 3: the interval travels with the point estimate ------------------------------------

def test_the_bound_is_the_owner_s_and_not_a_second_implementation(laya_choice):
    r = audit_fields(laya_choice, gate=0.85)["answer_confidence"]
    assert (r["automated_cases"], r["erroneous_cases"]) == (9, 5), r
    assert r["bound"] == pytest.approx(clopper_pearson_upper(5, 9, DEFAULT_DELTA), abs=1e-12)
    assert r["bound_two_sided"] == pytest.approx(clopper_pearson_upper(5, 9, DEFAULT_DELTA / 2),
                                                 abs=1e-12)
    assert r["bound_two_sided"] > r["bound"], "the inversion cannot come out tighter"
    conf = audit_fields(laya_choice, gate=0.85)["confidence"]
    # R-72: the plan's prose said "~0.92" at n=2. This tool's one-sided bound is 0.9747, and
    # publishing 0.92 would quote an interval no owner in this repository computes.
    assert conf["bound"] == pytest.approx(clopper_pearson_upper(1, 2, 0.05), abs=1e-12)
    assert conf["bound"] > 0.97
    assert abs(conf["bound"] - 0.92) > 0.05, "the plan's 0.92 is not this module's number"


def test_the_two_sided_bound_is_printed_beside_the_point_estimate(laya_choice):
    text = render_audit({"laya": audit_fields(laya_choice, gate=0.85)})
    assert "CP upper (2-sided)" in text
    assert "0.8630" in text, "the two-sided endpoint of 5-of-9 must reach the artefact"
    assert "0.8312" in text
    assert "A multiple is a point estimate and needs its interval" in text


# --- trap 2: cases are the unit, and the row figure sits beside them -------------------------

def test_the_row_figure_and_the_case_figure_are_both_published_and_diverge_for_jev(jev):
    r = audit_fields(jev, gate=0.85)["answer_confidence"]
    assert r["automated_rows"] == 180, r
    assert r["automated_cases"] == 59, r
    assert r["erroneous_cases"] == 0 and r["measured_error"] == 0.0, r
    # The published multiple is the CASE rate over the implied error; the row rate is printed
    # beside it, never blended into it.
    assert r["measured_error"] == r["erroneous_cases"] / r["automated_cases"]
    text = render_audit({"jev": audit_fields(jev, gate=0.85)})
    assert "180 of 191 ROWS automate" in text
    assert "| 59 of 64 |" in text


def test_laya_s_row_and_case_rates_coincide_without_being_called_identical(laya_choice):
    r = audit_fields(laya_choice, gate=0.85)["answer_confidence"]
    assert (r["automated_rows"], r["erroneous_rows"]) == (27, 15)
    assert r["measured_error_rows"] == pytest.approx(r["measured_error"], abs=1e-12)
    # Coincidence, not identity: the row count is 3x the case count, so a reader who took the wrong
    # column would infer three times the sample that exists.
    assert r["automated_rows"] == 3 * r["automated_cases"]
    assert r["n_records"] == 3 * r["n_cases"]
    assert r["bound"] == pytest.approx(clopper_pearson_upper(5, 9, DEFAULT_DELTA), abs=1e-12), \
        "the bound is computed on cases, never on the 27 rows"


# --- trap 4: the aggregation convention is measured, all three of them -----------------------

def _one_row_per_case(population, mode, field_get):
    groups = {}
    for index, r in enumerate(population):
        groups.setdefault(case_key(r), []).append((index, r))
    picked = []
    for key in sorted(groups):
        items = groups[key]
        if mode == "max_field_row":
            picked.append(max(items, key=lambda ir: (field_get(ir[1]), -ir[0]))[1])
        elif mode == "first_row":
            picked.append(items[0][1])
        else:
            picked.append(min(items, key=lambda ir: (ir[1].repeat, ir[0]))[1])
    return picked


def _collapse_counts(population, field_get, gate):
    return {mode: count_outcome(_one_row_per_case(population, mode, field_get),
                                lambda r: _verdict(field_get(r), gate, r))["automated_cases"]
            for mode in COLLAPSES}


def _verdict(value, gate, record):
    if value is not None and value >= gate:
        return Verdict("auto", record.predicted, value)
    return Verdict("refuse", None, value)


def test_the_collapse_conventions_are_measured_not_quoted(laya_choice, jev):
    rows = audit_fields(jev, gate=0.85)
    labelled_jev = [r for r in jev if r.gold is not None]
    answer = rows["answer_confidence"]
    assert set(answer["automated_cases_by_collapse"]) == set(COLLAPSES)
    assert answer["automated_cases_by_collapse"] == _collapse_counts(
        labelled_jev, lambda r: max_confidence(r.probs), 0.85)
    # Three separate measurements, not one figure copied three times: on jev's published
    # `confidence` the max-row collapse and the first-row collapse are different counts.
    conf = rows["confidence"]
    by_collapse = conf["automated_cases_by_collapse"]
    assert by_collapse["max_field_row"] != by_collapse["first_row"], by_collapse
    assert by_collapse == _collapse_counts(
        labelled_jev, lambda r: (r.scores or {}).get("reported_confidence"), 0.85)
    # None of them is a figure computed over an all-qtype population: every collapse here is
    # bounded by the AUDITED case count, which excludes noul by construction.
    for field, r in rows.items():
        for mode, cases in r["automated_cases_by_collapse"].items():
            assert 0 <= cases <= r["n_cases"], (field, mode)
        assert r["automated_cases_by_collapse"]["max_field_row"] >= r["automated_cases"], field
    for r in audit_fields(laya_choice, gate=0.85).values():
        assert set(r["automated_cases_by_collapse"]) == set(COLLAPSES)
        assert r["automated_cases_by_collapse"]["max_field_row"] >= r["automated_cases"]


def test_the_renderer_shows_which_convention_is_doing_the_work(laya_choice, jev):
    text = render_audit({"jev": audit_fields(jev, gate=0.85)})
    assert "the case convention moves the count" in text
    assert "max_field_row = 61" in text and "first_row = 61" in text
    # Where every convention agrees -- laya's choice rows are three repeats of one vector -- the
    # artefact stays quiet instead of printing a difference that is not in the data.
    assert "the case convention moves the count" not in render_audit(
        {"laya": audit_fields(laya_choice, gate=0.85)})


# --- the two `confidence`s: the artefact names upstream locations, not a ledger id -----------

def test_the_output_names_which_confidence_definition_was_used(laya_choice):
    """R-146: the two definitions are named by their UPSTREAM locations, never by a task id.

    `docs/AUDIT.md` used to open its evidence-boundary bullet with "obligation #31 records that
    upstream defines it two ways". The substance was right; the citation was wrong, because a reader
    of a published artefact has no task list. This guard asks for the two places upstream defines the
    name, for the place that fills the key the README's sentence reads, for that sentence's own
    location -- and it refuses every ledger id back out, so putting the old string back reddens it
    rather than matching it.
    """
    rows = audit_fields(laya_choice, gate=0.85)
    text = render_audit({"laya": rows})
    assert "laya/common.py:273" in text, "upstream's first definition must be openable, not quoted"
    assert "laya/common.py:289" in text, "upstream's second definition must be openable too"
    assert "laya/agent.py:684" in text, "which key upstream fills is the fact the gate turns on"
    assert "laya/README.md:567-581" in text, "the sentence G2 is about needs its own location"
    assert "max(probs)" in text, "the answer scale's definition must be readable, not implied"
    for ledger in ("obligation #", "#31", "R-121", "R-72", "R-146", "R-137"):
        assert ledger not in text, "a published artefact cites upstream, not the task list: %s" % (
            ledger)
    for field, r in rows.items():
        assert r["source"] in text, field
        assert r["case_rule"] in text, field
        # Defect 4, red before the fix: the header promises each field "names the definition it was
        # read as", but the renderer published `source` only and `definition` was computed, stored in
        # the row dict, and dropped -- so this line is what makes the header's claim true.
        assert r["definition"] in text, (field, r["definition"])


def test_the_artefact_says_which_row_answers_the_readme_s_own_sentence(laya, jev):
    """MAJ-2: three multiples were published and none was tied to the sentence G2 names.

    Upstream's README gates on the response key `confidence`, and `laya/agent.py:684` fills that key
    from `confidence_from_probs` -- so the row answering the sentence verbatim is `confidence` (laya:
    3.33x on 2 of 64 cases), while 3.70x belongs to `answer_confidence` (9 of 64), the same rule read
    as `p_max = max(probs)`. Neither is quietly promoted to the other here: the guard asks for both,
    each attached to its own field and its own denominator, and for the rows' OWN `informative`
    verdicts -- jev's `confidence` row bounds under the implied error and laya's does not, so a
    blanket "neither is certified" would be a claim about this corpus that this corpus contradicts.
    """
    audits = {b: audit_fields(rs) for b, rs in (("laya", laya), ("jev", jev))}
    text = render_audit(audits)
    hits = [l for l in text.splitlines() if l.startswith("- Which row answers the README")]
    assert len(hits) == 1, hits
    line = hits[0]
    assert "verbatim is **`confidence`**" in line, line
    literal, intended = audits["laya"]["confidence"], audits["laya"]["answer_confidence"]
    assert "%.2fx on %d of %d automated cases" % (
        literal["multiple"], literal["automated_cases"], literal["n_cases"]) in line, line
    assert "%.2fx on %d of %d automated cases" % (
        intended["multiple"], intended["automated_cases"], intended["n_cases"]) in line, line
    assert "p_max = max(probs)" in line, "the second reading has to be named, not hinted"
    assert "informative: **NO**" in line, "laya's rows refuse to bound, and the bullet must say so"
    assert "informative: yes" in line, "jev bounds; a blanket refusal sentence would be false"
    # The intended headline keeps its field name and its multiple is not softened into the other row.
    assert "3.70x" in text and "3.33x" in text
    assert "`answer_confidence`" in line and "`confidence`" in line


# --- the case rule and the backend partition -------------------------------------------------

def test_the_audit_refuses_a_population_that_mixes_backends(by_backend):
    pooled = by_backend["laya"] + by_backend["jev"]
    with pytest.raises(ValueError, match="one backend"):
        audit_fields(pooled, gate=0.85)
    with pytest.raises(ValueError, match="one backend"):
        frontier(pooled, ("confidence",))
    # The reason is measured, not asserted: the archive pairs the same requests across backends, so
    # pooling would divide by a denominator half the size of the one that exists.
    assert [len({case_key(r) for r in by_backend[b]}) for b in ("laya", "jev")] == [128, 128]
    assert len({case_key(r) for r in pooled}) == 128


def test_an_unusable_rubric_is_a_usage_error_not_a_crash(laya_choice):
    for bad_gate in (0.0, 1.0, 1.5, -0.2):
        with pytest.raises(ValueError, match="gate"):
            audit_fields(laya_choice, gate=bad_gate)
    for bad_delta in (0.0, 1.0, -1.0):
        with pytest.raises(ValueError, match="delta"):
            audit_fields(laya_choice, delta=bad_delta)


# --- guards for the three defects found in the inherited code --------------------------------

def _two_rows_one_case():
    """One case whose rows straddle the gate: a ROW clears it, the CASE does not."""
    return [choice_record(id="r0", case_id="cX", repeat=0, options=("a", "b"), probs=(0.9, 0.1),
                          gold="a", predicted="a"),
            choice_record(id="r1", case_id="cX", repeat=1, options=("a", "b"), probs=(0.5, 0.5),
                          gold="a", predicted="a")]


def test_rows_that_clear_the_gate_without_a_case_are_not_called_rows_below_it():
    """Defect 1, red before the fix.

    The inherited `NOTHING_AUTOMATED` note asserted "every one of the N audited rows carries a value
    below the gate" whenever no CASE automated -- including the population below, where one row
    clears the gate and only the case rule declines to carry it forward. A published artefact
    describing the data as something it is not is the failure this repository's ERRATA exists to
    correct, and this one was reachable from any `--gate` over a partially-repeating backend.
    """
    rows = audit_fields(_two_rows_one_case(), fields=("answer_confidence",))
    r = rows["answer_confidence"]
    assert (r["automated_rows"], r["automated_cases"]) == (1, 0), r
    assert r["note"].startswith("ROWS_NOT_CASES"), r["note"]
    assert "below the gate" not in r["note"], r["note"]
    assert "ROWS_NOT_CASES" in render_audit({"synthetic": rows})
    # The genuinely-empty arm still says what it means, and the two are told apart.
    below = [choice_record(id="r0", case_id="cX", repeat=0, options=("a", "b"), probs=(0.5, 0.5),
                           gold="a", predicted="a")]
    assert audit_fields(below, fields=("answer_confidence",)
                        )["answer_confidence"]["note"].startswith("NOTHING_AUTOMATED")


CURVE_TAMPERS = [
    ("emptied the curve", lambda t: t["answer_confidence"].__setitem__("curve", [])),
    ("dropped the gate point from the curve",
     lambda t: t["answer_confidence"].__setitem__(
         "curve", [p for p in t["answer_confidence"]["curve"] if p["lambda"] != 0.85])),
    ("moved a curve point's bound",
     lambda t: t["answer_confidence"]["curve"][3].__setitem__("bound", 0.5)),
    ("stamped one curve point with a delta the row does not publish",
     lambda t: t["answer_confidence"]["curve"][3].__setitem__("delta", 0.04)),
    ("made the at-gate curve point disagree with the headline",
     lambda t: t["answer_confidence"]["curve"][3].__setitem__("automated_cases", 12)),
    ("inflated a curve point's coverage past its own denominator",
     lambda t: t["answer_confidence"]["curve"][0].__setitem__("coverage", 1.5)),
    ("published a curve measured at another run's delta",
     lambda t: t["answer_confidence"].__setitem__("delta", 0.04)),
]


@pytest.mark.parametrize("label,mutate", [(t[0], t[1]) for t in CURVE_TAMPERS],
                         ids=[t[0] for t in CURVE_TAMPERS])
def test_check_audit_re_derives_the_curve_the_artefact_prints(audits, label, mutate):
    """MAJ-1's second half: a published frontier is a published number, so it is policed.

    The renderer prints `row["curve"]` verbatim, which makes every cell of it a figure this module is
    responsible for. `check_audit` re-derives each point's bound from the point's own counts at the
    row's own `delta`, refuses a point stamped with a different delta, and requires the at-gate point
    to equal the headline row -- so a curve that disagrees with its own header is drift (rc 4), not a
    drafting slip a reader has to catch. The control is the untouched-rows test below.
    """
    mutated = copy.deepcopy(audits)
    mutate(mutated["laya"])
    with pytest.raises(AuditDriftError):
        check_audit(mutated)


def test_a_row_without_a_curve_is_refused_by_name_not_by_keyerror(laya_choice):
    """The renderer reads `row["curve"]`, and `KeyError` is not in `cli.main`'s catch: rc 1.

    Refusing with `ValueError` keeps the exit-code contract the module documents, and names the row
    that lost its frontier instead of naming a dict key.
    """
    rows = audit_fields(laya_choice, gate=0.85)
    del rows["answer_confidence"]["curve"]
    with pytest.raises(ValueError, match="no risk-coverage curve"):
        render_audit({"laya": rows})
    # Same for the grid sentence, which is read off the curves rather than off DEFAULT_GRID.
    rows2 = audit_fields(laya_choice, gate=0.85)
    for row in rows2.values():
        row.pop("curve")
    with pytest.raises(ValueError, match="risk-coverage curve"):
        render_audit({"laya": rows2})


def test_an_undeclared_field_name_is_a_usage_error_at_every_entry_point(laya_choice):
    """Defect 2a, red before the fix.

    `audit_fields` refused an unknown field with `ValueError` (rc 2), while `frontier` indexed
    `FIELDS[field]` and `render_audit` indexed `table[FIELD_ORDER[0]]` directly and raised
    `KeyError`. `KeyError` is a `LookupError`, which `main` does not catch, so an undeclared key
    escaped the documented 0/2/3/4 contract as rc 1 with a traceback. Ruled at the raising site
    (R-115's precedent), not by widening `main`'s catch.
    """
    with pytest.raises(ValueError, match="knows no field"):
        audit_fields(laya_choice, fields=("typo",))
    with pytest.raises(ValueError, match="knows no field"):
        frontier(laya_choice, ("typo",))
    # The refusal names what it knows, so an operator can correct the argument from the message.
    with pytest.raises(ValueError, match="confidence"):
        frontier(laya_choice, ("typo",))


def _headline_rows(text: str) -> list:
    """The rows of the headline table, counted by the header they sit under.

    The curve blocks publish seven-cell rows and the headline publishes eleven, so "exactly one field
    row" has to be read off the table that claim belongs to now that the artefact prints both; counting
    every line that starts with a back-quoted cell would test the frontier instead.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith("| field | read as |"):
            inside = True
            continue
        if inside:
            if not line.startswith("|"):
                break
            if len(line.strip().strip("|").split("|")) == 11 and line.startswith("| `"):
                rows.append(line)
    return rows


def test_rendering_a_table_that_holds_a_subset_of_the_fields_does_not_crash(laya_choice):
    """Defect 2b, red before the fix: `KeyError: 'confidence'`, which reached the CLI as rc 1."""
    rows = audit_fields(laya_choice, fields=("answer_confidence",))
    text = render_audit({"laya": rows})
    headline = _headline_rows(text)
    assert len(headline) == 1 and headline[0].startswith("| `answer_confidence`"), headline
    assert len(_curve_rows(text)[("laya", "answer_confidence")]) == len(DEFAULT_GRID)
    assert "3.70x" in text
    with pytest.raises(ValueError, match="cannot render"):
        render_audit({"laya": {"bogus": rows["answer_confidence"]}})


TAMPERS = [
    ("laya", "automated_rows",
     lambda t: t["answer_confidence"].__setitem__("automated_rows", 999)),
    ("laya", "erroneous_rows over automated_rows",
     lambda t: t["answer_confidence"].__setitem__("erroneous_rows", 20)),
    ("laya", "measured_error_rows",
     lambda t: t["answer_confidence"].__setitem__("measured_error_rows", 0.0)),
    ("laya", "multiple_rows",
     lambda t: t["answer_confidence"].__setitem__("multiple_rows", 1.0)),
    ("laya", "informative, which chooses rc 0 vs rc 3",
     lambda t: t["answer_confidence"].__setitem__("informative", True)),
    ("laya", "n_records_carrying_field",
     lambda t: t["answer_confidence"].__setitem__("n_records_carrying_field", 999)),
    ("laya", "dropped collapse convention",
     lambda t: t["answer_confidence"]["automated_cases_by_collapse"].pop("max_field_row")),
    ("laya", "bound below the rate it bounds",
     lambda t: t["answer_confidence"].__setitem__("bound", 0.05)),
    ("laya", "two-sided tighter than one-sided",
     lambda t: t["answer_confidence"].__setitem__("bound_two_sided", 0.1)),
    ("laya", "bound dropped on a populated denominator",
     lambda t: t["answer_confidence"].__setitem__("bound", None)),
    ("laya", "case partition opened",
     lambda t: t["answer_confidence"].__setitem__("refused_cases", 60)),
    ("laya", "excluded row left uncounted",
     lambda t: t["confidence"].__setitem__("n_rows_handed_over", 961)),
    ("laya", "measured_error",
     lambda t: t["answer_confidence"].__setitem__("measured_error", 0.05)),
    ("laya", "multiple", lambda t: t["answer_confidence"].__setitem__("multiple", 1.0)),
    ("jev", "mean_value on a field nobody carries",
     lambda t: t["act_probability"].__setitem__("mean_value", 0.5)),
]


@pytest.mark.parametrize("backend,mutate", [(t[0], t[2]) for t in TAMPERS],
                         ids=["%s: %s" % (t[0], t[1]) for t in TAMPERS])
def test_check_audit_re_derives_every_figure_the_artefact_prints(audits, backend, mutate):
    """Defect 3, red before the fix: each of these lines printed SILENT.

    `check_audit` policed the case partition and the exclusion accounting, then stopped. Every row
    column `render_audit` prints -- `automated_rows`, `erroneous_rows`, `measured_error_rows`,
    `multiple_rows`, `n_records_carrying_field`, `mean_value` -- and `informative` itself, the
    figure `cmd_audit` picks the exit code on, went unchecked. A gate that re-derives some of the
    printed columns licenses the rest.
    """
    mutated = copy.deepcopy(audits)
    mutate(mutated[backend])
    with pytest.raises(AuditDriftError):
        check_audit(mutated)


def test_check_audit_is_not_an_empty_gate_on_untouched_rows(audits):
    """The control for the tamper test: untouched rows pass, so every red is the mutation's."""
    check_audit(audits)
    check_audit({"laya": audits["laya"]})


# --- the command and its exit codes ----------------------------------------------------------

def _cli(argv, tmp_path):
    return main(["audit"] + argv + ["--records", str(COMMITTED), "--out", str(tmp_path / "a.md")])


def test_the_command_refuses_to_certify_laya_and_lands_on_rc_3(tmp_path, capsys):
    assert _cli(["laya"], tmp_path) == EXIT_NOT_CERTIFIABLE == 3
    out = capsys.readouterr().out
    assert "3.70x" in out and "0.8630" in out
    assert "NOT_INFORMATIVE" in out


def test_the_command_prints_the_exclusion_rather_than_filtering_it_away(tmp_path, capsys):
    assert _cli([], tmp_path) == EXIT_CERTIFIED == 0
    out = capsys.readouterr().out
    assert "laya: 960 rows handed over, 192 audited, 768 excluded" in out
    assert "jev: 959 rows handed over, 191 audited, 768 excluded" in out
    assert out.count("gold is None") >= 2, out


def test_every_operator_triggerable_failure_is_rc_2_and_never_rc_1(tmp_path, capsys):
    assert _cli(["nosuch"], tmp_path) == EXIT_USAGE == 2
    assert _cli(["laya", "--gate", "1.5"], tmp_path) == EXIT_USAGE == 2
    assert _cli(["laya", "--delta", "0"], tmp_path) == EXIT_USAGE == 2
    assert main(["audit", "laya", "--records", str(tmp_path / "absent.jsonl"),
                 "--out", str(tmp_path / "a.md")]) == EXIT_USAGE == 2
    assert EXIT_USAGE == 2 and EXIT_NOT_CERTIFIABLE == 3


def test_an_unlabelled_only_records_file_is_rc_2_not_a_rate(tmp_path, capsys):
    path = tmp_path / "noul.jsonl"
    lines = [l for l in COMMITTED.read_text().splitlines() if l.strip()
             and json.loads(l)["qtype"] == "noul"]
    path.write_text("\n".join(lines) + "\n")
    assert len(lines) == 1536
    assert main(["audit", "--records", str(path), "--out", str(tmp_path / "a.md")]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "nothing to audit" in err and "gold is None" in err
    assert (tmp_path / "a.md").exists() is False, "a refused audit writes no artefact"


def test_the_artefact_is_re_derivable_and_carries_no_timestamp(tmp_path, by_backend):
    def render():
        return render_audit({b: audit_fields(rs, gate=DEFAULT_GATE) for b, rs in by_backend.items()})
    first, second = render(), render()
    assert first == second, "a re-run must be byte-comparable"
    _cli([], tmp_path)
    written = (tmp_path / "a.md").read_text()
    assert written == first, "the file is the renderer's output, not a transcription of it"
    # MAJ-3's test half, red before this round: this comparison was fresh-render-to-fresh-render, so
    # `sed 's/| 3.70x |/| 9.99x |/' docs/AUDIT.md` left the whole suite green. The committed bytes
    # are the published artefact, and they are what this assertion holds against now.
    assert written == AUDIT_MD.read_text(), \
        "the bytes `autorate audit` writes are not the bytes the repository commits"
    for token in ("/Users/", "/home/", "T00:00", "UTC"):
        assert token not in written, token


def test_the_committed_artefact_is_what_this_revision_writes(by_backend):
    """The published G2 numbers are re-derivable, and this is the guard that says so out loud.

    Written as its own test rather than as a side effect of the determinism check above, because the
    claim being policed is different: not "two renders agree" (they always did) but "the file in git
    is the file this code produces". `autorate verify` re-derives the same equality in both of its
    lanes; this test is the one that names the artefact when the renderer moves and nobody re-ran the
    command.
    """
    committed = AUDIT_MD.read_text()
    assert committed == render_audit(
        {b: audit_fields(rs) for b, rs in sorted(by_backend.items())}), \
        "committed docs/AUDIT.md is not what this revision renders"
    assert committed.splitlines()[0] == ("# Audit: the gate the README instructs, measured against "
                                         "what it implies"), committed.splitlines()[0]


# --- MAJ-3: the artefact's own sentence about who re-derives it -------------------------------


def test_the_artefact_names_the_gate_that_re_derives_it():
    """The producer wrote "re-derived by `tests/test_audit.py`" at a revision where that was all.

    True as far as it went -- the suite does re-render the file -- and beside the point: the
    repository's published-numbers gate is `autorate verify`, and until `PUBLISHED_DOCS` grew this
    artefact the gate never opened it. A published document that names the wrong re-derivation owner
    states a fact no reader can check, so the sentence itself is policed here, and it is the sentence
    the generator has to be changed to satisfy.
    """
    prose = AUDIT_MD.read_text().splitlines()[2]
    assert "autorate verify" in prose, prose
    assert "tests/test_audit.py" in prose, prose


# --- R-121 at this module's producer: the precision a published bound is stored at -------------
#
# `float-canonical-b` fixed the choice gate and reported, as its concern 3, that this module was
# equally exposed: `clopper_pearson_upper` inverts a binomial tail through `math.log`/`math.exp` and
# its last bits are not the same between Apple libm and glibc (~4e-16 at 0.79, ~9000 ULPs wide
# there), so a full-precision bound written on one C library is not a number the other re-derives.
# Here the bound is not only printed: `informative` is `bound <= implied_error`, and `cmd_audit`
# chooses rc 0 or rc 3 from `informative`. An unreproducible transcendental therefore decided an
# exit code.
#
# The audit publishes no JSON artefact, so the gate the pair below drives is the one this module
# already runs against its own numbers: `check_audit` re-derives every figure the table prints and
# raises `AuditDriftError` (rc 4) when a published figure is not the one the row's own counts
# produce, and the committed `docs/AUDIT.md` is the stored side a re-render is compared with. The
# per-figure `==` diff below is `verify`'s comparison shape applied to that re-derivation, so a red
# names the field that moved and prints both numbers.

# The bound-valued columns of a published row. `CANONICALISED_BOUND_FIELDS` names the certificate
# shape's two headline attributes and is deliberately NOT reused as this module's key list -- the
# audit's bounds are keyed `bound` and `bound_two_sided`, and on the curve `bound` -- but they are
# produced by the same call, so the guard sweeps by these names.
_BOUND_KEYS = ("bound", "bound_two_sided")


def _scalar_leaves(node, prefix=""):
    """Every published number in a row, with the path that names it, so a diff can say which field."""
    if isinstance(node, dict):
        for key in sorted(node):
            yield from _scalar_leaves(node[key], "%s.%s" % (prefix, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _scalar_leaves(item, "%s[%d]" % (prefix, index))
    elif isinstance(node, bool):
        return
    elif isinstance(node, (int, float)):
        yield prefix, node


def _published_diff(published, fresh) -> list:
    """`verify`'s exact comparison, over every figure the two audit tables publish."""
    failures = []
    for backend in sorted(published):
        for field in sorted(published[backend]):
            left = dict(_scalar_leaves(published[backend][field], "%s/%s" % (backend, field)))
            right = dict(_scalar_leaves(fresh[backend][field], "%s/%s" % (backend, field)))
            assert set(left) == set(right), (sorted(set(left) ^ set(right)))
            for label in sorted(left):
                if left[label] != right[label]:
                    failures.append("%s: recomputed %r, published %r"
                                    % (label, right[label], left[label]))
    return failures


def _drift_the_bound_producer(monkeypatch, move):
    """Make the audit's one bound producer answer as a different C library, recording every call.

    `audit._bound` is the single site that turns a transcendental into a published figure, and it
    reads the name this module imported, so patching `autorate.audit.clopper_pearson_upper` makes
    the producer answer the way the other C library answered -- and moves every bound in the table
    and on the curve at once, exactly as a different libc would. The calls are recorded so a test
    can prove the instrument was reached rather than quietly never wired.
    """
    calls = []

    def drifting(k, n, delta):
        raw = clopper_pearson_upper(k, n, delta)
        moved = move(raw)
        calls.append((k, n, delta, raw, moved))
        return moved

    monkeypatch.setattr(importlib.import_module("autorate.audit"),
                        "clopper_pearson_upper", drifting)
    return calls


def _one_ulp(raw, direction):
    """One unit in the last place up or down: the size of the drift R-121 measured.

    A bound of exactly 1.0 is left alone -- the bisection brackets [0, 1], so 1.0 is the bracket's
    own endpoint rather than an answer `math.exp` produced, and no two libms disagree about it.
    """
    return raw if raw >= 1.0 else math.nextafter(raw, direction)


def _tables(by_backend):
    return {b: audit_fields(rs, gate=DEFAULT_GATE) for b, rs in sorted(by_backend.items())}


def test_the_audit_publishes_only_bounds_another_libc_can_write(by_backend):
    """Content guard: every bound the audit table carries is its own canonical value.

    Walks the committed corpus's rows and curve points and asks of every value stored under a bound
    key that `canonicalise_bound(value) == value` -- the property a raw inversion does not have --
    then asks the OPPOSITE of the row's quotient columns, because R-121's fix is a sweep by field
    name and not a pass over floats. `CANONICALISED_BOUND_FIELDS` is asserted to stay the
    certificate's own two names: the audit shares the ceiling, not the shape's field list.
    """
    assert CANONICALISED_BOUND_FIELDS == ("conditional_error_bound", "marginal_error_bound")
    assert set(_BOUND_KEYS).isdisjoint(CANONICALISED_BOUND_FIELDS), _BOUND_KEYS
    rows = _tables(by_backend)
    bounds = quotients = empty_arms = 0
    for backend, table in rows.items():
        for field, row in table.items():
            leaves = dict(_scalar_leaves(row, "%s/%s" % (backend, field)))
            named = {k: v for k, v in leaves.items()
                     if k.split(".")[-1].split("[")[0] in _BOUND_KEYS}
            if row["bound"] is None:
                # The empty-denominator arm: `jev` carries no `act_probability` on any row, so this
                # row publishes no bound, and `check_audit` requires that it publish none. A guard
                # that demanded a canonical bound here would be demanding an invented number --
                # the very failure mode this module's notes exist to refuse.
                assert not named and row["informative"] is None, (backend, field)
                empty_arms += 1
                continue
            assert named, "row %s/%s publishes no bound at all" % (backend, field)
            for label, value in named.items():
                assert canonicalise_bound(value) == value, (label, repr(value))
                assert len(repr(value).split(".")[-1]) <= 12, (label, repr(value))
                bounds += 1
            for label, value in leaves.items():
                tail = label.split(".")[-1].split("[")[0]
                if tail in ("measured_error", "multiple", "implied_error", "mean_value",
                            "measured_error_rows", "multiple_rows", "coverage"):
                    quotients += 1
                    assert isinstance(value, float), label
    assert empty_arms == 1, empty_arms
    assert bounds >= 20, "the audit no longer publishes this many bounds: %d" % bounds
    assert quotients >= 10, quotients
    # and the artefact the reader actually gets renders them at four decimals: the ceiling is
    # invisible in prose and load-bearing in the machine-readable row, where it decides rc 0 vs 3.
    assert "0.974679434481" not in AUDIT_MD.read_text()
    assert "0.9747" in AUDIT_MD.read_text()


def test_the_audit_absorbs_a_last_bit_libm_drift_and_stays_green(tmp_path, by_backend,
                                                                 monkeypatch, capsys):
    """Guard pair (a): a platform difference in the 16th decimal moves nothing, both directions.

    Three separate surfaces must not move: the exact per-figure re-derivation, `check_audit` (which
    is this module's own drift gate and raises rc 4), and the rendered `docs/AUDIT.md` bytes. The
    assertions after the drift is planted keep the green honest -- the instrument must have fired,
    the move must really be one ULP, and every drifted value must canonicalise back to the stored
    number -- otherwise the gate would be green because nothing reached it.
    """
    published = _tables(by_backend)
    rendered = render_audit(published)
    assert rendered == AUDIT_MD.read_text(), "the committed artefact is not what this machine writes"
    rc_control = _cli([], tmp_path)
    capsys.readouterr()
    assert _published_diff(published, _tables(by_backend)) == []   # the control, undrifted

    for direction in (math.inf, 0.0):
        calls = _drift_the_bound_producer(monkeypatch,
                                          lambda raw, d=direction: _one_ulp(raw, d))
        drifted = _tables(by_backend)
        assert calls, "the producer was never asked for a bound"
        moved_apart = [(raw, moved) for _, _, _, raw, moved in calls if moved != raw]
        assert moved_apart, "a one-ULP drift moved nothing: the instrument is blind"
        assert all(abs(moved - raw) < 1e-15 for raw, moved in moved_apart), moved_apart[:3]
        assert all(canonicalise_bound(moved) == canonicalise_bound(raw)
                   for _, _, _, raw, moved in calls), \
            [repr((raw, moved)) for raw, moved in moved_apart
             if canonicalise_bound(moved) != canonicalise_bound(raw)][:3]
        assert _published_diff(published, drifted) == [], direction
        check_audit(drifted)                          # must not raise AuditDriftError
        assert render_audit(drifted) == rendered, direction
        rc = _cli([], tmp_path)
        assert rc == rc_control, (rc, rc_control)
        assert "DRIFT" not in capsys.readouterr().err, direction
        monkeypatch.undo()


def test_the_audit_reds_when_a_bound_moves_in_the_tenth_decimal(tmp_path, by_backend,
                                                               monkeypatch, capsys):
    """Guard pair (b): a bound that actually MOVED is still drift, and is named by row and column.

    Same producer, same fields, same gate, two orders of magnitude further along the number, so the
    pair differs only in size -- which is the claim `PUBLISHED_DECIMALS` makes. Absorbing 4e-16 is a
    fix and not a blinder only if 1e-10 still turns this red, and red with the field named is the
    difference between a diagnosis and a dict repr.
    """
    published = _tables(by_backend)
    stored = published["laya"]["confidence"]["bound"]
    assert canonicalise_bound(stored + 1e-10) != stored, "the planted drift would not take"

    calls = _drift_the_bound_producer(monkeypatch, lambda raw: raw + 1e-10)
    failures = _published_diff(published, _tables(by_backend))
    assert calls and all(moved != raw for _, _, _, raw, moved in calls)
    assert failures, "a bound that moved by 1e-10 re-derived the published table"
    labels = [f.split(":")[0] for f in failures]
    assert any(l.endswith(".bound") and l.startswith("laya/confidence") for l in labels), labels
    assert any(l.endswith(".bound_two_sided") for l in labels), labels
    assert any(".curve[" in l and l.endswith("].bound") for l in labels), labels
    text = "\n".join(failures)
    assert "recomputed" in text and "published" in text, text[:400]
    assert repr(stored) in text, text[:400]
    assert repr(canonicalise_bound(stored + 1e-10)) in text, text[:400]
    # and only bound columns object: the quotient columns of the same rows are not blamed
    assert not [l for l in labels if l.split(".")[-1].split("[")[0] not in _BOUND_KEYS], labels


# ---------------------------------------------------------------------------
# #88: `unit` became load-bearing when it joined the rubric mapping (B1 Task 6A's own ERRATA
# names this gap), because two sentences in `render_audit` print it and `docs/AUDIT.md` is in
# `PUBLISHED_DOCS`. Before these rows, a changed unit could only surface as "the document no
# longer matches" -- never as a test naming the value or the sentence. Green on arrival by
# construction (the renderer already binds the owner), so the work here is the two falsifications:
# a re-typed literal in the source, and a live patch of the owner's value.


def _unit_sites(source):
    """Every `%`-format in `render_audit` whose template mentions the unit, with what feeds it.

    Returns one dict per site: the template, the variable names substituted, and any string
    literal substituted. A site carrying a literal where the unit belongs is a second owner of the
    rubric's unit -- and a value comparison cannot see it, because the literal would hold the same
    word the owner holds.
    """
    import ast

    tree = ast.parse(source)
    sites = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)):
            continue
        left = node.left
        if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
            continue
        if "unit" not in left.value.lower():
            continue
        right = node.right
        args = list(right.elts) if isinstance(right, ast.Tuple) else [right]
        names, literals = [], []
        for arg in args:
            target = arg
            # `UNIT.upper()` / `UNIT.lower()` still name the owner; unwrap the call before judging.
            if (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
                    and isinstance(arg.func.value, ast.Name)):
                names.append(arg.func.value.id)
                continue
            if isinstance(target, ast.Name):
                names.append(target.id)
            elif isinstance(target, ast.Constant) and isinstance(target.value, str):
                literals.append(target.value)
        sites.append({"template": left.value, "names": names, "literals": literals})
    return sites


def _rendered_unit_lines(text):
    return [line for line in text.splitlines()
            if "certification unit: the" in line or "The unit is the" in line]


def test_the_renderer_names_the_rubric_owner_for_every_unit_sentence():
    """Both unit sentences read the owner; neither carries its own copy of the word."""
    import inspect

    sites = _unit_sites(inspect.getsource(render_audit))
    assert len(sites) >= 2, (
        "the renderer is expected to hold at least the header line and the per-field line; found %d"
        % len(sites))
    for site in sites:
        assert "UNIT" in site["names"], (
            "a unit sentence is built without the rubric owner: %r feeds %r"
            % (site["names"], site["template"][:70]))
        assert not site["literals"], (
            "a string literal stands where the unit name belongs: %r in %r"
            % (site["literals"], site["template"][:70]))


def test_a_retyped_unit_literal_is_caught_by_the_source_probe():
    """The probe bites: swap the owner for its own value as a literal and the site is reported."""
    import inspect

    source = inspect.getsource(render_audit)
    mutated = source.replace("UNIT.upper()", '"CASE"')
    assert mutated != source, "the mutation did not land; this control would prove nothing"
    sites = _unit_sites(mutated)
    assert sites, "the probe found no unit site even in the mutated source"
    offenders = [s for s in sites if s["literals"] or "UNIT" not in s["names"]]
    assert offenders, "a re-typed unit literal passed the binding probe"
    assert '"CASE"' not in source, "the unmutated source already holds a unit literal"


def test_the_published_unit_sentence_is_a_live_read_of_the_owner(monkeypatch, audits):
    """Patch the owner's value and both sentences move with it; the committed artefact carries it.

    This is the falsification the source probe cannot supply: a renderer that captured the unit at
    import time, or one whose sentences were hand-edited into `docs/AUDIT.md`, would pass the AST
    probe while the published document silently kept a stale denominator.
    """
    import autorate.audit as audit_module

    owner = str(audit_module.UNIT)
    before = _rendered_unit_lines(render_audit(audits))
    assert before, "no unit sentence rendered, so the assertions below would pass on an empty list"
    assert all(owner.upper() in line for line in before), before

    patched = "slice"
    monkeypatch.setattr(audit_module, "UNIT", patched)
    after = _rendered_unit_lines(render_audit(audits))
    assert len(after) == len(before), (
        "patching the unit changed how many sentences render (%d -> %d); the header and the "
        "per-field line are not the same site" % (len(before), len(after)))
    assert all(patched.upper() in line for line in after), after
    assert not any(owner.upper() in line for line in after), (
        "a rendered line still carries the unpatched unit: %s" % [l for l in after
                                                                  if owner.upper() in l])

    published = AUDIT_MD.read_text()
    published_lines = _rendered_unit_lines(published)
    assert len(published_lines) >= 3, (
        "`docs/AUDIT.md` is expected to hold the header line and one per-field line per `field`; "
        "found %d" % len(published_lines))
    assert all(owner.upper() in line for line in published_lines), published_lines[:2]


def test_a_stale_published_unit_sentence_would_be_caught(monkeypatch, tmp_path, audits):
    """The control for the row above: point it at a document whose unit disagrees, and it reddens.

    Written as a test rather than invoked by hand, because a hand-call against a pytest fixture
    raises `TypeError` and proves nothing about the assertion's power -- which is exactly what
    happened to the first version of this control.
    """
    import autorate.audit as audit_module

    word = str(audit_module.UNIT).upper()
    published = AUDIT_MD.read_text()
    stale_text = published.replace("the %s" % word, "the ROW")
    assert stale_text != published, "the planted document is identical to the published one"
    stale = tmp_path / "AUDIT.md"
    stale.write_text(stale_text)

    module = __import__("test_audit")
    monkeypatch.setattr(module, "AUDIT_MD", stale)
    with pytest.raises(AssertionError) as excinfo:
        module.test_the_published_unit_sentence_is_a_live_read_of_the_owner(monkeypatch, audits)
    message = str(excinfo.value)
    assert "the ROW" in message, (
        "the row failed, but not because of the planted unit word: %s" % message[:200])
    assert "no unit sentence rendered" not in message, (
        "the row failed on an empty render rather than on the stale artefact")
