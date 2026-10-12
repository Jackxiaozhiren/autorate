"""Task #87: the 200-resplit experiment is published, and the gate can refuse it by name.

G1's criterion has two columns -- certified decision tasks, and the empirical violation rate over 200
re-splits. The first is a refusal this repository publishes as five artefacts; the second existed only as a
six-minute run whose 422 KB document sat outside the tree, so the column the spec names had no committed
number, nothing for `verify` to check, and no prose that could not go stale. This file is the wiring: the
artefact is declared, its document is rendered from its own bytes and byte-compared, its internal arithmetic is
compared by the gate, and its recorded rubric is checked against the freeze rather than trusted.

What is deliberately NOT claimed here: that `verify` re-runs the experiment. Six minutes does not belong in a
gate that CI runs on two arms, and a gate that re-split the data would be a second owner of the producer's
seeded split. What the gate can do -- and these rows are that -- is refuse an artefact whose own quantities
disagree, refuse one whose rubric is not the promised one, and refuse a missing or unreadable file at exit 4.
The producer's determinism is a separate, measured fact: re-running `tools/resplit_experiment.py` reproduced
these bytes exactly, and `docs/ERRATA.md` records that run.
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


def _recorded_checks(doc=None, rubric=None):
    """Run the arm through the gate's own callbacks and collect what it compared, label and verdict."""
    seen, mismatches = [], []
    doc = doc if doc is not None else report.read_resplit(REPO / report.RESPLIT_JSON)
    rubric = rubric if rubric is not None else json.loads(
        (REPO / "protocol.json").read_text())["rubric"]

    def expect(label, actual, wanted):
        seen.append((label, actual == wanted))

    def expect_rubric(label, actual, wanted):
        mismatches.append((label, actual == wanted))

    original = report.load_published
    report.load_published = lambda path, owner, reader: doc
    try:
        report.rederive_resplit(expect, expect_rubric, rubric)
    finally:
        report.load_published = original
    return seen, mismatches


def test_the_published_resplit_document_is_byte_reproducible_from_the_artefact():
    """`docs/RESPLIT.md` is emitted from `data/resplit_200.json` and compared byte for byte by `verify`."""
    doc = report.read_resplit(REPO / report.RESPLIT_JSON)
    assert report.render_resplit(doc, doc["rubric"]) == (REPO / report.RESPLIT_MD).read_text()
    assert report.RESPLIT_MD in {path for path, _ in cli.PUBLISHED_DOCS}, cli.PUBLISHED_DOCS


def test_the_gate_compares_the_artefacts_own_arithmetic_and_the_freezes_rubric():
    """32 comparisons on this artefact, all passing, and the count is derived rather than typed."""
    doc = report.read_resplit(REPO / report.RESPLIT_JSON)
    expected = (len(doc["tasks"]) * 5
                + sum(1 for t in doc["tasks"] if t["bound_min"] is not None) + 1)
    seen, mismatches = _recorded_checks()
    assert len(seen) == expected, (len(seen), expected)
    assert all(passed for _label, passed in seen), [l for l, p in seen if not p]
    assert len(mismatches) == 5 and all(p for _l, p in mismatches), mismatches


def test_a_violation_rate_with_no_certificates_is_undefined_rather_than_zero(in_repo):
    """The vacuity this artefact must never fall into: a rate of `0.000` where nothing was certified."""
    doc = report.read_resplit(REPO / report.RESPLIT_JSON)
    refusing = [t for t in doc["tasks"] if t["certificates_issued"] == 0]
    assert refusing, "the published tasks are expected to refuse"
    for task in refusing:
        assert task["violation_rate"] is None, task
        assert task["violations_denominator"] == 0, task
    certified = [t for t in doc["tasks"] if t["certificates_issued"] > 0]
    for task in certified:
        assert task["violation_rate"] == task["violations"] / task["certificates_issued"], task


def test_a_resplit_artefact_whose_rate_does_not_match_its_denominator_is_drift_the_gate_names():
    """The invariant arm has to be able to fail, or it is a formality beside the numbers it claims to check."""
    doc = json.loads((REPO / report.RESPLIT_JSON).read_text())
    target = next(t for t in doc["tasks"] if t["certificates_issued"] > 0)
    target["violations"] = target["certificates_issued"]          # rate stays as published: no longer a ratio
    seen, _mismatches = _recorded_checks(doc=doc)
    failed = [label for label, passed in seen if not passed]
    assert any("rate is the ratio it claims" in label for label in failed), failed
    assert len(failed) == 1, failed


def test_a_resplit_artefact_measured_at_another_budget_is_a_rubric_mismatch_not_a_drift(in_repo):
    """R-20/R-31's two prefixes, applied to the experiment: a different beta is the freeze's disagreement."""
    doc = json.loads((REPO / report.RESPLIT_JSON).read_text())
    doc["rubric"]["beta"] = 0.10
    _seen, mismatches = _recorded_checks(doc=doc)
    flagged = [label for label, passed in mismatches if not passed]
    assert flagged == ["resplit rubric.beta"], flagged


def test_a_missing_resplit_artefact_is_a_named_refusal_at_four(tmp_path, monkeypatch, in_repo, capsys):
    """A published column with no file behind it is the checkout's failure, named by its table.

    Only the resplit path is re-pointed: an earlier draft of this row also moved the severity table aside and
    then asserted the wrong refusal, because the severity arm runs first and reported the copy it had never
    been given -- the test had manufactured a second absent artefact and blamed the one it was studying.
    """
    missing = tmp_path / "resplit_200.json"
    for module in (cli, report):
        monkeypatch.setattr(module, "RESPLIT_JSON", str(missing))
    assert main(["verify"]) == 4
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "report.RESPLIT_JSON" in err, err
    assert str(missing) in err, err


def test_the_committed_experiment_document_carries_no_machine_path_and_names_its_producer(in_repo):
    """The artefact is a published file, so the same hygiene the certificates are held to applies to it."""
    text = (REPO / report.RESPLIT_JSON).read_text()
    assert not re.search(r"/(Users|home)/[A-Za-z0-9._-]+/", text), "an absolute path in a published artefact"
    doc = json.loads(text)
    assert sorted(doc) == ["resplits", "rows", "rubric", "tasks"], sorted(doc)
    assert doc["resplits"] == 200, doc["resplits"]
    synthetic = [t for t in doc["tasks"] if "synthetic" in str(t["label"])]
    assert synthetic, "the control on the machinery is missing, so a rate would have no positive case"
    for task in synthetic:
        assert "synthetic" in task["label"], task["label"]
