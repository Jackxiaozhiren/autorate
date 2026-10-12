"""Task #87: the 200-resplit instrument spec §2 G1 asks for, with a producer and an honest denominator.

The measurement itself is not the interesting part -- a probe already ran 1,000 splits and every one refused.
What these rows pin down is the two ways a figure like that gets published wrongly: a violation rate printed
as `0.0` when its denominator is zero (an undefined quantity dressed as a result), and a committed table of
per-split outcomes that nothing can prove the tool wrote. So the artefact stores the rows, the aggregate is
recomputed from them, and the producer's own output is byte-stable across runs.

The synthetic family lives in the producer, not here: the artefact quotes a row from it, so a test-local
generator would certify a fiction about what shipped.
"""
import json
from pathlib import Path

import pytest

from tools.resplit_experiment import (SYNTHETIC_FAMILY, main, published_tasks, recompute, render_task,
                                      run_family, summarise)

REPO = Path(__file__).resolve().parents[1]


def _rows(family, seeds):
    return run_family(family, seeds=seeds)


def test_the_task_list_is_read_from_the_publication_tables():
    """Five tasks, because the tables say five -- not because a list in this file remembers five.

    The defect this project keeps hitting (R-168) is a second copy of "what is published" that goes quiet when
    the gate's table changes. The resplit experiment covers exactly the corpora `verify` re-derives, so it
    reads `report.CERTS` and `report.MASSIVE_CERTIFICATES`.
    """
    from autorate.report import CERTS, MASSIVE_CERTIFICATES

    tasks = published_tasks()
    assert len(tasks) == len(CERTS) + len(MASSIVE_CERTIFICATES), tasks
    assert {t["label"] for t in tasks} == (set(CERTS) | set(MASSIVE_CERTIFICATES)), tasks
    for task in tasks:
        assert (REPO / task["records"]).is_file(), task


def test_every_resplit_of_the_committed_feishu_records_is_refused_by_the_same_reason():
    """The published refusal is split-robust, and the reason is named rather than counted.

    Three seeds, not two hundred: this row is about the shape of the answer, and the full sweep is the
    artefact's job. Feishu is 960 rows at ~10 ms a certify, so it is cheap enough to run here; the MASSIVE
    corpora are 2,974 rows at ~0.95 s and are not.
    """
    laya = next(t for t in published_tasks() if t["label"] == "laya")
    rows = _rows(laya, seeds=(0, 1, 2))
    assert [r["feasible"] for r in rows] == [False, False, False], rows
    summary = summarise(laya["label"], rows)
    assert summary["certificates_issued"] == 0, summary
    assert summary["refusal_reasons"] == {"empty_feasible_set": 3}, summary


def test_the_violation_rate_is_none_when_no_certificate_exists_and_is_never_printed_as_zero():
    """0 violations over 0 certificates is undefined, and `0.0` would be a fabricated result.

    Both directions are asserted: the field is None, and the rendered line says the denominator out loud. A
    reader who sees `violation rate 0.000` on a table of refusals would conclude the rule held; it never ran.
    """
    laya = next(t for t in published_tasks() if t["label"] == "laya")
    summary = summarise("laya", _rows(laya, seeds=(0, 1)))
    assert summary["violations_denominator"] == 0, summary
    assert summary["violation_rate"] is None, summary
    line = render(summary)
    assert "0 of 0" in line, line
    assert "0.000" not in line, line


def test_the_violation_rate_computes_where_a_certificate_exists():
    """The instrument must be able to produce a number, or the row above is all it can ever say.

    The synthetic family (sharp scores, a non-zero `error_rate` so wrong answers exist) does certify. The
    expected rate is recomputed here from the per-row fields the artefact stores, independently of
    `summarise`, so the assertion is about the arithmetic and not about the same loop agreeing with itself.
    """
    rows = _rows(SYNTHETIC_FAMILY, seeds=tuple(range(8)))
    summary = summarise(SYNTHETIC_FAMILY["label"], rows)
    assert summary["certificates_issued"] > 0, summary
    certified = [r for r in rows if r["feasible"]]
    assert all(r["conditional_error_bound"] is not None for r in certified), certified
    expected = sum(1 for r in certified if r["observed_conditional_error"] > r["conditional_error_bound"])
    assert summary["violations"] == expected, (summary, expected)
    assert summary["violations_denominator"] == len(certified), summary
    assert abs(summary["violation_rate"] - expected / len(certified)) < 1e-12, summary


def test_the_stored_rows_recompute_every_published_aggregate(tmp_path):
    """`verify`'s future job, pinned at the producer: the aggregates are a function of the rows.

    Re-deriving from the stored table is what lets the gate check a ten-minute experiment in milliseconds.
    Deleting a row has to move an aggregate, and the test asserts that it does -- otherwise the recompute
    would be reading the summary it is supposed to check.
    """
    family = next(t for t in published_tasks() if t["label"] == "laya")
    rows = _rows(family, seeds=(0, 1, 2))
    summary = summarise(family["label"], rows)
    assert recompute(rows)[family["label"]] == summary, (recompute(rows), summary)
    dropped = recompute(rows[:-1])[family["label"]]
    assert dropped != summary, (dropped, summary)
    assert dropped["refusal_reasons"] == {"empty_feasible_set": 2}, dropped


def test_the_violation_counter_fires_on_a_row_it_should_fire_on():
    """A rate of 0.000 must be distinguishable from a counter that never counts.

    The synthetic family certifies on every split and violates on none, so every end-to-end row in this file
    would still pass if `summarise` counted nothing at all. That is the vacuous-guard class this project
    keeps finding in its own work, so the counter is exercised directly, on rows built here rather than
    produced by the certifier: two violations, one exactly-at-the-bound case that is NOT a violation (the
    claim is `<=`), and one refusal that must not enter the denominator at all.
    """
    def row(seed, feasible, observed, bound):
        return {"label": "synthetic/planted", "seed": seed, "feasible": feasible,
                "reason": None if feasible else "empty_feasible_set", "n_cal_cases": 100,
                "n_eval_cases": 100, "automated_cases": 50, "errors_among_automated": 1,
                "observed_conditional_error": observed, "conditional_error_bound": bound,
                "autorate": 0.5}

    rows = [row(0, True, 0.10, 0.05),       # above the bound: a violation
            row(1, True, 0.05, 0.05),       # exactly the bound: the claim holds, so not a violation
            row(2, True, 0.01, 0.05),       # below: not a violation
            row(3, False, None, None),      # refused: absent from the denominator
            row(4, True, 0.20, 0.05)]      # above: a violation
    summary = summarise("synthetic/planted", rows)
    assert summary["certificates_issued"] == 4, summary
    assert summary["violations_denominator"] == 4, summary
    assert summary["violations"] == 2, summary
    assert summary["violation_rate"] == 0.5, summary
    assert render_task(summary).count("2 of 4") == 1, render_task(summary)


def test_a_re_run_writes_byte_identical_json(tmp_path):
    """Determinism is the product: same seeds and same committed inputs, same bytes.

    The rubric block is ordered explicitly rather than dumped from the `MappingProxyType`, whose key order is
    not pinned, and no timestamp is written -- `verify` compares published documents byte for byte, and a
    run date in the artefact would make every CI run look like drift.
    """
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    for out in (first, second):
        assert main(["--out", str(out), "--seeds", "2", "--tasks", "laya"]) == 0
    assert first.read_bytes() == second.read_bytes(), "the artefact is not reproducible"
    doc = json.loads(first.read_text())
    assert doc["resplits"] == 2, doc
    assert [t["label"] for t in doc["tasks"]] == ["laya"], doc
    assert doc["rubric"]["alpha"] == doc["rubric"]["beta"] == doc["rubric"]["delta"], doc
    assert "generated_at" not in json.dumps(doc), "a timestamp entered the artefact"


def test_the_producer_refuses_to_replace_an_existing_artefact_until_asked(tmp_path, capsys):
    """The same contract `tools/build_records.py` carries: an existing destination is a refusal, exit 2.

    Asserted as the sentence rather than the code alone, because several causes share exit 2 and the operator
    has to be told which one and what the way forward is.
    """
    out = tmp_path / "resplit.json"
    assert main(["--out", str(out), "--seeds", "1", "--tasks", "laya"]) == 0
    capsys.readouterr()
    assert main(["--out", str(out), "--seeds", "1", "--tasks", "laya"]) == 2
    err = capsys.readouterr().err
    assert "--force" in err and str(out) in err, err
    assert main(["--out", str(out), "--seeds", "1", "--tasks", "laya", "--force"]) == 0


def render(summary):
    """The one line the documents quote, read from the producer's own renderer."""
    from tools.resplit_experiment import render_task

    return render_task(summary)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Nothing here reaches a corpus, a model or a socket: the inputs are committed files."""
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", "/nonexistent-corpus-dir")
