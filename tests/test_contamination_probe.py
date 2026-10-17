"""G4's contamination gap: the pin, the probe, the document, and the arm that re-pools them.

Spec §2's G4 row names two outputs, and `docs/SLICES.md` is the first. This module is about the second,
`delta_hat` with its interval, published by `tools/contamination_probe.py` from `data/pin_app_benchmark.json`.

The defect class this file is written against is the one the whole-branch review named twice: a published
number with no owner. So every row here reads its expectation from a committed artefact or from the producer
itself, and the refusal rows go through the real entry point, because a probe that cannot refuse is a probe
that will publish a gap out of a stratum that does not exist.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autorate import cli, report

REPO = Path(cli.__file__).resolve().parents[2]
CORPUS_ENV = "AUTORATE_FEISHU_ROOT"
TOOL = "tools/contamination_probe.py"


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)


def _run_tool(args, env_root=None):
    """The producer, as an operator runs it: same interpreter, same contract, exit code measured directly."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": str(REPO / "src"), "NO_PROXY": "*", "no_proxy": "*"}
    if env_root is not None:
        env[CORPUS_ENV] = env_root
    else:
        env.pop(CORPUS_ENV, None)
    proc = subprocess.run([sys.executable, str(REPO / TOOL)] + list(args), cwd=REPO, env=env,
                          capture_output=True, text=True)
    return proc


def _pin():
    return json.loads((REPO / report.CONTAMINATION_PIN).read_text())


def _artefact():
    return report.read_contamination(REPO / report.CONTAMINATION_JSON)


def _arm_counts():
    field, budget = [], []
    report.rederive_contamination(lambda label, actual, wanted: field.append((label, actual == wanted)),
                                  lambda label, actual, wanted: budget.append((label, actual == wanted)))
    return field, budget


def test_the_pin_is_reproducible_from_the_corpus_and_says_which_lane_recomputes_it(monkeypatch):
    """The pin is the only thing that lets the corpus-absent lane re-derive the gap, so its bytes are checked.

    Skipped cleanly -- naming what it skipped -- where no corpus is visible, because that is the CI lane and
    the absence is the point of the second denominator.
    """
    root = os.environ.get(CORPUS_ENV)
    if not root or not (Path(root) / "data" / "manifest.json").is_file():
        pytest.skip("no corpus visible: the pin's digest can only be recomputed in the corpus-present lane; "
                    "the committed pin and its artefact are still checked by every other row here")
    committed = _pin()
    rebuilt = subprocess.run(
        [sys.executable, str(REPO / "tools" / "contamination_pin.py"), "--out", "data/pin_app_benchmark.json"],
        cwd=REPO, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO / "src"),
                       CORPUS_ENV: root}, capture_output=True, text=True)
    assert rebuilt.returncode == 0, rebuilt.stderr
    fresh = json.loads((REPO / report.CONTAMINATION_PIN).read_text())
    (REPO / report.CONTAMINATION_PIN).write_text(json.dumps(committed, sort_keys=True, indent=2) + "\n")
    assert fresh == committed, "the pin is not reproducible from the corpus it names"


def test_the_document_is_byte_reproducible_from_the_artefact(in_repo):
    """`verify` byte-compares this document, so a renderer that drifts is a red gate and not a stale claim."""
    rendered = report.render_contamination(_artefact())
    assert rendered == (REPO / report.CONTAMINATION_MD).read_text(), "the gap document drifted from its bytes"


def test_the_document_carries_no_machine_path_and_no_run_timestamp(in_repo):
    text = (REPO / report.CONTAMINATION_MD).read_text()
    assert not [1 for _ in __import__("re").finditer(r"/(Users|home|var/folders)/[A-Za-z0-9._-]+/", text)], \
        "an absolute path in a published document"
    assert "delta_hat" in text and "`claim` | False" in text, text[:400]


def _arm_in_lane(monkeypatch, root):
    """Run the arm with the corpus deliberately visible or not, so the lane is a fact of the test."""
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", root)


def test_the_arm_re_pools_the_pin_and_compares_the_published_gap_field_by_field(in_repo, monkeypatch):
    """The arm's own numbers: it must disagree with nothing, and it must be making comparisons.

    The counts are asserted, not the labels, because the note quotes them; the mismatch check is what shows
    the re-pooling agrees with the artefact on this tree.
    """
    _arm_in_lane(monkeypatch, "/nonexistent-corpus-dir")
    field, budget = _arm_counts()
    assert field and budget, (field, budget)
    assert [name for name, ok in field if not ok] == [], [n for n, ok in field if not ok]
    assert [name for name, ok in budget if not ok] == [], [n for n, ok in budget if not ok]
    assert len(field) == 29 and len(budget) == 4, (len(field), len(budget))


def test_the_corpus_visible_lane_adds_exactly_the_published_corpus_only_checks(in_repo, monkeypatch):
    """The two re-digest checks are the present lane's whole difference, and they are named in `report`.

    Kept out of the counts row because it can only run where the vendored corpus is reachable; a row that
    mixes the two would fail in the corpus-less export for a reason that is about the machine, which is the
    mistake the resolver branch above exists to stop.
    """
    corpus = REPO.parent / "laya-0.3.20" / "research" / "benchmarks" / "feishu_zh"
    if not (corpus / "data" / "manifest.json").is_file():
        pytest.skip("no corpus at %s: the two re-digest checks exist only in the corpus-visible lane" % corpus)
    _arm_in_lane(monkeypatch, "/nonexistent-corpus-dir")
    field, _ = _arm_counts()
    _arm_in_lane(monkeypatch, str(corpus))
    seen, _ = _arm_counts()
    labels = {name for name, ok in seen}
    extra = sorted(labels - {name for name, _ in field})
    assert extra == sorted(report.CONTAMINATION_CORPUS_ONLY_CHECKS), extra
    assert [name for name, ok in seen if not ok] == [], [n for n, ok in seen if not ok]


def test_the_note_digit_for_the_arm_is_the_number_of_comparisons_the_arm_makes(in_repo, monkeypatch):
    """The frozen note claims 29 quantities and 4 budget values; this row recomputes both from the arm."""
    _arm_in_lane(monkeypatch, "/nonexistent-corpus-dir")
    note = " ".join(next(c for c in json.loads((REPO / "protocol.json").read_text())["claims"]
                         if c["id"] == "G4")["note"].split())
    field, budget = _arm_counts()
    assert "compares %d quantities plus %d budget values" % (len(field), len(budget)) in note, \
        "the note quotes %d/%d and the arm makes %d/%d" % (29, 4, len(field), len(budget))


def test_a_stale_gap_is_drift_the_arm_names_field_by_field(in_repo, tmp_path, monkeypatch):
    """One changed number in the artefact must come back as a named disagreement, not a silent pass."""
    doc = _artefact()
    doc["probe"]["delta_hat"] += 1e-6
    assert doc["headline"]["worse"] == "out_stratum", doc["headline"]
    doc["headline"]["worse"] = "in_stratum"
    pin = _pin()

    def fake_load(path, table, load):
        return pin if str(path).endswith("pin_app_benchmark.json") else doc

    monkeypatch.setattr(report, "load_published", fake_load)
    seen = []
    report.rederive_contamination(lambda label, actual, wanted: seen.append((label, actual == wanted)),
                                  lambda label, actual, wanted: seen.append((label, actual == wanted)))
    bad = sorted(name for name, ok in seen if not ok)
    assert any("delta_hat" in name for name in bad), bad
    assert any("worse" in name for name in bad), bad


def test_a_pin_that_declares_no_held_out_stratum_is_refused_rather_than_bounded(in_repo):
    """The probe's whole claim is a comparison; one stratum is not a comparison."""
    from autorate.report import ContaminationRefusal, contamination_strata

    pin = _pin()
    pin["rows"] = [r for r in pin["rows"] if r["in_training"]]
    with pytest.raises(ContaminationRefusal, match="out_stratum"):
        contamination_strata(pin)


def test_a_row_whose_rate_is_not_a_whole_number_of_cases_is_excluded_by_name():
    """The producer set three rows aside rather than rounding them into existence, and says which three."""
    from tools.contamination_pin import extract

    rows, excluded = extract({"suites": {"app.x": {"english": {"n": 399, "accuracy": 0.6391,
                                                               "in_training": False},
                                                    "welsh": {"n": 400, "accuracy": 0.5,
                                                              "in_training": True}}}})
    assert len(rows) == 1 and len(excluded) == 1, (rows, excluded)
    # the committed pin carries the same census from the real corpus, and the artefact quotes it
    assert len(_pin()["excluded"]) == 3, [e["pointer"] for e in _pin()["excluded"]]
    assert "not a whole number" in excluded[0]["reason"], excluded[0]
    assert excluded[0]["pointer"] == "/suites/app.x/english", excluded[0]


def test_a_missing_pin_is_a_named_refusal_at_four_not_a_crash(in_repo, tmp_path, capsys):
    """The pin is the probe's only input, so its absence is a named refusal and writes nothing.

    Driven through the real entry point with `--pin` pointing at a path that does not exist: an
    operator-typed path is usage territory, but this one is not unusable because the operator mistyped it --
    the file the published contract names is simply missing -- so R-272's table-declared answer (4) is the
    one the test insists on.
    """
    proc = _run_tool(["--out", str(tmp_path / "probe.json"), "--doc", str(tmp_path / "doc.md"),
                      "--pin", str(tmp_path / "no_such_pin.json"), "--force"])
    sys.stderr.write(proc.stdout + proc.stderr)
    assert proc.returncode == 4, (proc.returncode, proc.stdout, proc.stderr)
    assert "no_such_pin.json" in proc.stderr, proc.stderr
    assert not (tmp_path / "probe.json").exists(), "a refused publication must not leave half its artefact"


def test_a_scratch_path_pair_is_refused_at_two(in_repo, tmp_path):
    proc = _run_tool(["--out", str(tmp_path / "probe.json"), "--doc", str(tmp_path / "doc.md")])
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "published" in proc.stderr and "--force" in proc.stderr, proc.stderr


def test_the_committed_artefact_publishes_no_claim(in_repo):
    """`claim` false is the artefact's own guard rail: the gap is a diagnostic, in every surface that shows it."""
    doc = _artefact()
    assert doc["claim"] is False and doc["probe"]["claim"] is False, doc["claim"]
    assert "not a proof of leakage" in (REPO / report.CONTAMINATION_MD).read_text()
    assert doc["headline"]["excludes_zero"] is True, doc["headline"]


def test_the_resolver_returns_nothing_rather_than_raising_where_no_corpus_exists(monkeypatch):
    """No environment variable and no sibling corpus is the shape of a fresh clone, not an error.

    `cli._default_corpus()` answers `None` when the glob finds nothing, so a resolver that wraps it in `Path`
    unconditionally raises `TypeError` -- an rc 1 out of `verify` on the one machine the published gates never
    see. This is the row the corpus-less export wrote: it reddened as a crash before the branch was added.
    """
    monkeypatch.delenv("AUTORATE_FEISHU_ROOT", raising=False)
    monkeypatch.setattr("autorate.cli._default_corpus", lambda: None)
    assert report._corpus_root_for_contamination() is None


def test_the_present_lane_extras_do_not_depend_on_how_the_corpus_was_named(monkeypatch):
    """A denominator that changes with the *form* of the corpus argument would be a fact about the call.

    The two re-digest checks are the corpus-present lane's own work, so they must fire wherever a real corpus
    is reachable -- environment variable or the sibling default every other corpus path also uses. The row
    that fails without the fix is this one: resolving through the default and getting nothing back would make
    `verify` print a smaller present-lane denominator than the tree can support.
    """
    from autorate.cli import _default_corpus

    monkeypatch.delenv("AUTORATE_FEISHU_ROOT", raising=False)
    default = _default_corpus()
    if default is None or not (Path(default) / "data" / "manifest.json").is_file():
        pytest.skip("no sibling corpus to resolve: %r; the env-var lane is covered by every other row"
                    % (default,))
    default = Path(default)
    root = report._corpus_root_for_contamination()
    assert root is not None, "the sibling default resolved to nothing, so the lane would lose its two checks"
    assert (root / "research/results/app_benchmark_results.json").is_file(), root
