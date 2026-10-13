"""Task #86: G4's worst-slice refusal becomes a published artefact the gate re-derives.

The criterion asks for a behaviour, not a number: with a simultaneous correction over the slices, the
WORST slice must refuse, and the pooled (marginal) bound must not be allowed to average that refusal away.
Until now the mechanism existed only on the CLI -- `certify --groups language` printed the refusal and threw
it away, so `verify` had nothing to check and the README could only say "what is missing is a published
artefact". The slice key was never the blocker: every committed MASSIVE row declares
`slices.language`, and the earlier "no language field" reading of the data looked for a top-level key.

This file is the wiring, in `test_resplit_surface.py`'s shape, with one deliberate difference: the run costs
seconds, so the gate RE-DERIVES it from the three committed records files instead of only auditing an
artefact's internal arithmetic. A published slice certificate that the certifier disagrees with is drift the
gate names, and the refusal itself -- which slice, at which corrected level, with which pooled neighbour --
is a published claim rather than terminal scrollback.
"""
import json
import re
from pathlib import Path

import pytest

from autorate import cli, report
from autorate.cli import main

REPO = Path(cli.__file__).resolve().parents[2]


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)


def _run():
    return report.read_slices(REPO / report.SLICE_JSON)["run"]


def _recorded(doc=None, rubric=None):
    """Drive the arm through the gate's own callbacks and collect (label, passed) for every comparison."""
    seen, mismatches = [], []
    if doc is None:
        doc = report.read_slices(REPO / report.SLICE_JSON)
    if rubric is None:
        rubric = json.loads((REPO / "protocol.json").read_text())["rubric"]

    def expect(label, actual, wanted):
        seen.append((label, actual == wanted))

    def expect_rubric(label, actual, wanted):
        mismatches.append((label, actual == wanted))

    original = report.load_published
    report.load_published = lambda path, owner, reader: doc
    try:
        report.rederive_slices(expect, expect_rubric, rubric)
    finally:
        report.load_published = original
    return seen, mismatches


def test_the_slice_run_refuses_the_worst_slice_rather_than_averaging_it(in_repo):
    """G4's own sentence, asserted on the published artefact: a refusal, named, with the pooled bound beside it."""
    run = _run()
    assert run["any_slice_refused"] is True and run["feasible"] is False
    # `groups` names the declared slice KEYS; the slice VALUES are the `per_group` keys. A row that conflated
    # them would pass on a run over one key with any number of slices, which is not the claim G4 makes.
    assert run["groups"] == [report.SLICE_GROUP_KEY], run["groups"]
    assert sorted(run["per_group"]) == ["de", "en", "sw"], sorted(run["per_group"])
    assert run["n_groups"] == len(run["per_group"]) == 3, run["n_groups"]
    refused = [g for g, cert in run["per_group"].items() if not cert["feasible"]]
    assert sorted(refused) == ["de", "en", "sw"], refused
    assert run["thinnest"] in refused, (run["thinnest"], refused)
    # the pooled marginal certificate is published BESIDE the slices, not in place of them, and it refuses too
    assert "pooled" in run and run["pooled"]["feasible"] is False, run.get("pooled")
    # and the refusal is a bound failure, not an artefact of the size floor: nothing was dropped for thinness
    assert run["refused_by_size"] == [], run["refused_by_size"]
    assert run["meta"]["n_refused_by_size"] == 0


def test_the_simultaneous_correction_the_run_publishes_is_the_rule_it_states(in_repo):
    """Each slice's budget divided by the SLICE count, the joint level rebuilt from the divided delta, beta unspent.

    Measured, and the arithmetic is the claim: 0.05 / 3 = 0.016667 per slice, and 3 slices x 3 claims x that
    delta = 0.15 family risk, so the joint level is 0.85. Dividing by slices x claims instead (0.00556) would
    publish a stricter run than the one that was made, and a level rebuilt from the wrong divisor would read
    as consistent while describing nothing.
    """
    run = _run()
    n_groups, n_claims = run["n_groups"], run["n_claims"]
    assert n_groups == 3 and n_claims == 3, (n_groups, n_claims)
    assert run["corrected_alpha"] == pytest.approx(run["alpha"] / n_groups)
    assert run["corrected_delta"] == pytest.approx(run["delta"] / n_groups)
    assert run["level"] == pytest.approx(1 - n_groups * n_claims * run["corrected_delta"])
    assert run["level"] == pytest.approx(1 - n_claims * run["delta"])
    # the per-slice certificate is certified at the divided budget, and `beta` is the one quantity that is not
    per_slice = run["per_group"][run["thinnest"]]
    assert per_slice["alpha"] == pytest.approx(run["corrected_alpha"]), per_slice["alpha"]
    assert per_slice["beta"] == run["beta"], per_slice["beta"]
    assert any("beta is NOT divided" in line for line in run["envelope"]), run["envelope"]


def test_the_gate_re_derives_the_published_slice_run_from_the_committed_records(in_repo):
    """The arm recomputes the certification: a stale artefact is drift the gate names, not a stale sentence."""
    seen, mismatches = _recorded()
    expected = (len(report.SLICE_COMPARE_FIELDS)
                + len(report.SLICE_GROUP_FIELDS) * 3
                + len(report.SLICE_CENSUS_FIELDS) * 3
                + len(report.SLICE_POOLED_FIELDS) + 1          # +1: the six envelope lines, as one value
                + len(report.SLICE_WORST_FIELDS) + 1           # +1: `refused_by_size`, joined as one value
                + len(report.SLICE_INPUT_FIELDS) * 3)
    assert len(seen) == expected, (len(seen), expected)
    assert all(passed for _label, passed in seen), [l for l, p in seen if not p]
    assert len(mismatches) == len(report.SLICE_RUBRIC_FIELDS)
    assert all(p for _l, p in mismatches), mismatches


def test_a_slice_artefact_whose_joint_level_disagrees_with_its_correction_is_drift(in_repo):
    """The re-derivation must be able to fail on this artefact, or the arm is a formality beside its numbers."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    doc["run"]["level"] = 0.999
    seen, _mismatches = _recorded(doc=doc)
    failed = sorted(label for label, passed in seen if not passed)
    assert failed == ["slice level"], failed


def test_a_slice_artefact_that_averages_the_refusal_away_is_named_field_by_field(in_repo):
    """The defect G4 exists for: a slice silently reported as certifying, or with a bound it never produced."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    doc["run"]["any_slice_refused"] = False
    doc["run"]["per_group"]["de"]["feasible"] = True
    doc["run"]["per_group"]["de"]["qhat"] = 0.5
    seen, _mismatches = _recorded(doc=doc)
    failed = sorted(label for label, passed in seen if not passed)
    assert failed == ["slice any_slice_refused", "slice per_group.de.feasible",
                      "slice per_group.de.qhat"], failed


def test_a_slice_artefact_measured_at_another_budget_is_a_rubric_mismatch_not_a_drift(in_repo):
    """R-20/R-31's two prefixes: a different delta is the freeze disagreeing, and prints on its own line."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    doc["rubric"]["delta"] = 0.10
    _seen, mismatches = _recorded(doc=doc)
    flagged = sorted(label for label, passed in mismatches if not passed)
    assert flagged == ["slice rubric.delta"], flagged


def test_a_missing_slice_artefact_is_a_named_refusal_at_four(tmp_path, monkeypatch, in_repo, capsys):
    """A published criterion whose artefact is absent is the checkout's failure, named by its owner table."""
    missing = tmp_path / "slices_language.json"
    for module in (cli, report):
        monkeypatch.setattr(module, "SLICE_JSON", str(missing))
    assert main(["verify"]) == 4
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "report.SLICE_JSON" in err, err
    assert str(missing) in err, err


def test_the_slice_document_is_byte_reproducible_from_its_artefact(in_repo):
    """`docs/SLICES.md` is rendered from the published bytes and joins the document table."""
    doc = report.read_slices(REPO / report.SLICE_JSON)
    assert report.render_slices(doc) == (REPO / report.SLICE_MD).read_text()
    assert report.SLICE_MD in {path for path, _ in cli.PUBLISHED_DOCS}, cli.PUBLISHED_DOCS


def test_the_producer_refuses_a_declared_input_file_it_cannot_find(tmp_path, monkeypatch, in_repo):
    """A run whose declared input is missing must refuse before certifying, not publish a short pool.

    The refusal belongs to the producer: the gate's job is to name drift in what was published, while this is
    the act of publishing, and a tool that certified 2 of 3 languages and called it a language-slice run
    would put a bound over a population the artefact describes differently than it is.
    """
    from tools import language_slices

    missing = tmp_path / "empty"
    missing.mkdir()
    for rel in report.SLICE_RECORDS:
        (missing / Path(rel).name).write_text((REPO / rel).read_text())
    (missing / "records_massive_sw.jsonl").unlink()
    monkeypatch.chdir(missing)
    code, err = language_slices.refuse_missing_inputs(missing)
    assert code == 2, code
    assert "records_massive_sw.jsonl" in err and "records_massive_de.jsonl" not in err, err


def test_the_producer_refuses_a_row_whose_case_id_and_declared_language_disagree(tmp_path):
    """Two subjects in one row: which slice a case lands in would depend on which field the reader believes.

    `split_records.py` proves this for the split direction; the merge direction inherits the claim, re-derived
    from the row's own bytes rather than from the filename it happens to sit in.
    """
    from tools import language_slices

    row = json.loads((REPO / report.SLICE_RECORDS[0]).read_text().splitlines()[0])
    row["case_id"] = "massive/fr/0"
    path = tmp_path / "records_massive_de.jsonl"
    path.write_text(json.dumps(row, sort_keys=True) + "\n")
    with pytest.raises(language_slices.SliceInputRefusal, match="case_id"):
        language_slices.check_rows([(path, [row])])


def test_the_published_slice_artefact_names_its_inputs_and_carries_no_machine_path(in_repo):
    """The run is a function of three committed files, so the file says which three and how many rows."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    assert not re.search(r"/(Users|home)/[A-Za-z0-9._-]+/", (REPO / report.SLICE_JSON).read_text()), \
        "an absolute path in a published artefact"
    assert sorted(doc) == ["backend", "group_key", "inputs", "producer", "rubric", "run"], sorted(doc)
    assert [row["path"] for row in doc["inputs"]] == sorted(report.SLICE_RECORDS)
    for row in doc["inputs"]:
        assert row["rows"] == sum(1 for _ in (REPO / row["path"]).open()), row
    assert doc["group_key"] == report.SLICE_GROUP_KEY == "language"
    assert doc["producer"] == "tools/language_slices.py"
