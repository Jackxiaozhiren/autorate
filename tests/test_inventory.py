"""Task 3: what offline, labelled, per-case decision data actually exists, and whether n supports a bound.

Two things this suite refuses to do: certify on a corpus too small to bound, and
silently write into the vendored upstream tree it reads from.
"""
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autorate.inventory import corpus_options, inventory, n_feasible, write_inventory

REPO = Path(__file__).resolve().parents[1]

UPSTREAM = Path(
    __import__("os").environ.get(
        "AUTORATE_FEISHU_ROOT",
        # One owner for corpus discovery: the same resolver the CLI uses, so a test
        # default cannot drift from the shipped default and disagree about what ran.
        str(__import__("autorate.cli", fromlist=["_default_corpus"])._default_corpus()
            or "/no/corpus/on/this/machine"),
    )
)
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")


@skip
def test_inventory_sees_the_recorded_shape():
    d = inventory(UPSTREAM)
    assert d["unique_ids"] == 64
    assert d["repeats"] == [0, 1, 2]
    assert d["lines_by_mode_backend"] == {
        "choice/laya": 192,
        "choice/jev": 192,
        "four_noul/laya": 192,
        "four_noul/jev": 192,
    }
    assert sorted(d["families"]) == [
        "conditional",
        "cross_chat",
        "knowledge",
        "lifecycle",
        "ownership",
        "thread_context",
        "untrusted_content",
        "urgency",
    ]


@skip
def test_upstream_audit_is_the_owner_of_integrity_and_it_passes():
    d = inventory(UPSTREAM)
    assert d["upstream_audit_rc"] == 0, d["upstream_audit_stderr_tail"]
    # The audit's own verdict, not ours: it recomputes metrics from the archive.
    assert "laya / choice: 20/64" in d["upstream_audit_stdout_tail"]
    assert "jev / choice: 64/64" in d["upstream_audit_stdout_tail"]


@skip
def test_reading_the_corpus_never_writes_into_the_vendored_tree(tmp_path):
    # audit.py only writes data with --write-summary, but importing it drops .pyc files
    # next to its siblings. A tool that dirties someone else's tree on a read is a bug.
    before = _digest(UPSTREAM)
    inventory(UPSTREAM)
    assert _digest(UPSTREAM) == before, "inventory modified the vendored upstream tree"


@skip
def test_label_balance_is_read_from_the_manifest_not_inferred():
    d = inventory(UPSTREAM)
    assert set(d["label_counts"].values()) == {16}, d["label_counts"]
    assert d["provenance"].startswith("AI-assisted")


def test_small_n_is_declared_infeasible_not_silently_certified():
    # Bound width is 2*sqrt(ln(2/alpha)/(2n)). At alpha=0.05:
    #   n=64 -> 0.3395   n=240 -> 0.1753   n=1000 -> 0.0859   n=2550 -> 0.0538
    assert n_feasible(unique_n=64, alpha=0.05, max_bound_width=0.25) is False
    assert n_feasible(unique_n=64, alpha=0.05, max_bound_width=0.4) is True
    assert n_feasible(unique_n=240, alpha=0.05, max_bound_width=0.25) is True
    assert n_feasible(unique_n=240, alpha=0.05, max_bound_width=0.10) is False
    assert n_feasible(unique_n=1000, alpha=0.05, max_bound_width=0.10) is True
    assert n_feasible(unique_n=1, alpha=0.05, max_bound_width=1.0) is False


def test_the_bound_width_is_monotone_in_n():
    widths = [n_feasible_bound(2 * n + 2, 0.05) for n in range(1, 200)]
    assert widths == sorted(widths, reverse=True)[: len(widths)]


def n_feasible_bound(n, alpha):
    from autorate.inventory import bound_width

    return bound_width(n, alpha)


def test_a_larger_corpus_option_is_recorded_with_its_measured_numbers():
    """Ledger R-12: MASSIVE ships 51 x test/xx.json.gz, 2974 rows each, stdlib-readable.

    Review finding C-1 was that the all-language row multiplied three opened files by a
    51-file listing and printed the product as a sample size. The bound must key on
    independent cases, so 51 translations of the same utterances buy coverage, not n.
    O-6 then found the other direction: the row said "3 of 51 files opened" after all 51 had
    been opened and hashed. Both are the same defect -- a basis an reader cannot re-derive --
    so this asserts the row against the pin list rather than against a frozen sentence.
    """
    from autorate.inventory import (massive_pin, massive_pinned_shards,
                                    massive_pooled_basis)

    pin = massive_pin()
    listed, declared = massive_pinned_shards(pin)
    assert pin["distinct_row_counts"] == [2974], pin["distinct_row_counts"]
    assert (listed, declared) == (51, 51), (listed, declared)
    opts = {o["id"]: o for o in corpus_options(64)}
    one, all_langs = opts["massive_intent_per_language"], opts["massive_intent_all_languages"]
    assert opts["feishu_zh"]["n_independent"] == 64, opts["feishu_zh"]
    assert one["n_independent"] == one["n_rows"] == 2974
    assert all_langs["n_rows"] == pin["rows_total"] == 2974 * 51
    assert all_langs["n_independent"] == 2974, "translations must not inflate the sample"
    assert all_langs["bound_width_at_0.05"] == one["bound_width_at_0.05"]
    assert all_langs["basis"] == massive_pooled_basis(pin), all_langs["basis"]
    assert "%d of %d" % (listed, declared) in all_langs["basis"], all_langs["basis"]
    assert "data/massive_provenance.json" in all_langs["basis"], all_langs["basis"]
    assert "NOT independent" in all_langs["unit"], all_langs["unit"]
    # The feasibility answer comes from the formula, not from a typed word.
    assert opts["feishu_zh"]["bound_width_at_0.05"] > 0.25
    assert opts["feishu_zh"]["feasible_at_0.10"] is False
    assert one["feasible_at_0.10"] is True
    assert opts["typed_decisions"]["n_independent"] is None
    assert opts["typed_decisions"]["feasible_at_0.10"] is None


def test_an_unscanned_corpus_does_not_invent_its_own_size():
    opts = {o["id"]: o for o in corpus_options()}
    assert opts["feishu_zh"]["n_independent"] is None
    assert opts["feishu_zh"]["bound_width_at_0.05"] is None
    assert "not scanned" in opts["feishu_zh"]["basis"]


@skip
def test_inventory_md_numbers_are_produced_by_the_code_that_reports_them(tmp_path):
    # A nested destination: the artefact is generated into data/, which is not in git
    # until the first run, so write_inventory has to create it rather than assume it.
    out = tmp_path / "nested" / "inventory.md"
    write_inventory(inventory(UPSTREAM), out)
    assert out.exists()
    body = out.read_text()
    assert "64" in body and "192" in body
    assert "per-case records omitted" in body  # the MASSIVE gap, recorded not glossed
    assert "audit.py` exit code: **0**" in body
    sidecar = json.loads(Path(str(out) + ".json").read_text())
    assert sidecar["unique_ids"] == 64
    # The width quoted in the markdown is the width the function computes.
    from autorate.inventory import bound_width

    assert f"{bound_width(64, 0.05):.4f}" in body


@skip
def test_the_four_noul_asks_have_no_per_ask_ground_truth_anywhere():
    # Measured, not asserted from prose: `prompts.py:34` folds the four noul
    # probabilities into ONE composite 4-way label, and the fixtures supervise only
    # that label. So a per-ask noul certificate here would certify invented labels.
    from autorate.readers.feishu_zh import per_ask_gold

    g = per_ask_gold(UPSTREAM)
    assert g["asks"] == ["action", "related", "urgent", "value"]
    assert g["asks_with_gold"] == [], g
    assert g["composite_label_available"] is True
    assert "expected" in g["case_keys"]


@skip
def test_the_inventory_states_that_gap_because_the_code_found_it():
    d = inventory(UPSTREAM)
    assert d["per_ask_gold"]["asks_with_gold"] == []
    assert any("per-ask ground truth" in g for g in d["gaps"]), d["gaps"]


@skip
def test_exactly_one_archived_choice_line_does_not_close_and_it_is_named():
    d = inventory(UPSTREAM)
    assert d["sum_tolerance"] == 5e-3
    assert d["probs_not_closing"] == [{
        "id": "lifecycle-01", "backend": "jev", "repeat": 1,
        "probs": [0.0, 0.93, 0.01, 0.05], "probs_sum": 0.99,
    }], d["probs_not_closing"]
    assert any("quarantined by the reader" in g for g in d["gaps"]), d["gaps"]


@skip
def test_inventory_and_the_reader_quarantine_the_identical_line():
    # Two implementations, one tolerance, no disagreement about the corpus.
    from autorate.readers.feishu_zh import read_archive

    stats = {}
    read_archive(UPSTREAM, stats=stats)
    inv = inventory(UPSTREAM)["probs_not_closing"]
    key = lambda xs: sorted((x["id"], x["backend"], x["repeat"]) for x in xs)
    assert key(inv) == key(stats["quarantined"]), (inv, stats["quarantined"])


@skip
def test_a_closing_corpus_produces_neither_finding_nor_gap_line():
    # Negative control for the detector: it must stay quiet on well-formed data.
    fake = {
        "id": "k-0", "mode": "choice", "repeat": 0, "status": "ok", "expected": "a",
        "response": {"model": "m", "answers": {"category": {
            "type": "choice", "choice": "a",
            "probabilities": {"a": 0.5, "b": 0.5}}}},
    }
    from autorate.inventory import _scan_jsonl

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "laya" / "raw.jsonl"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(fake) + "\n")
        by_mode, ids, reps, unclosed, outside, lines_read = _scan_jsonl(p)
    assert by_mode == {"choice": 1} and unclosed == []
    # Task 1b: one readable line, so the unreadable buckets are empty and the identity
    # closes over the line the pass read.
    assert outside == [] and lines_read == 1 and ids == {"k-0"} and reps == [0]


@skip
def test_the_published_inventory_file_is_structurally_valid():
    """PF-12 applied to the real artefact, not only to a synthetic dict."""
    body = Path("data/inventory.md").read_text() if Path("data/inventory.md").exists() else _render()
    tables = _tables(body)
    # lines table, the bound table keyed on independent cases, and the unit/note table
    assert len(tables) == 3, [h for h, _ in tables]
    for header, rows in tables:
        ncol = len(_cells(header))
        assert ncol >= 2
        assert len(_cells(rows[0])) == ncol
        for line in rows[1:]:
            assert len(_cells(line)) == ncol, "column drift: %r vs header %r" % (line, header)
    # And the denominator is named where the counts appear.
    assert "archive LINES per mode and backend" in body or "Archive lines per mode" in body


@skip
def test_the_snapshot_records_upstreams_own_digests_and_they_match():
    d = inventory(UPSTREAM)
    assert d["digests"], "upstream SOURCE.json pins file digests; none were read"
    assert all(x["match"] for x in d["digests"]), [x for x in d["digests"] if not x["match"]]
    assert len({x["path"] for x in d["digests"]}) == len(d["digests"])


def test_a_changed_corpus_file_breaks_its_own_digest_row(tmp_path):
    """The digest row must be a comparison against bytes, not a transcription of `expected`.

    A row that only echoes what SOURCE.json already says can never go red, so the gate
    would report '9/9 match' forever -- including after the archive changed underneath it.
    """
    from autorate.inventory import corpus_digests

    (tmp_path / "a").write_text("original")
    (tmp_path / "b").write_text("stable")
    (tmp_path / "SOURCE.json").write_text(json.dumps({"files": [
        {"path": p, "sha256": _sha256(tmp_path / p)} for p in ("a", "b")]}))
    clean = corpus_digests(tmp_path)
    assert [x["match"] for x in clean] == [True, True], clean
    (tmp_path / "a").write_text("tampered")
    after = corpus_digests(tmp_path)
    assert [x["match"] for x in after] == [False, True], after
    assert after[0]["actual"] == _sha256(tmp_path / "a")
    assert after[0]["expected"] != after[0]["actual"]


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_inventory_refuses_a_corpus_whose_audit_failed(tmp_path):
    fake = {
        "source": "x",
        "lines_by_mode_backend": {"choice/laya": 1},
        "unique_ids": 1,
        "repeats": [0],
        "families": [],
        "label_counts": {},
        "provenance": "",
        "upstream_audit_rc": 1,
        "upstream_audit_stdout_tail": "",
        "upstream_audit_stderr_tail": "boom",
        "digests": [],
        "gaps": [],
        "audit_interpreter": sys.version.split()[0],
        "corpus_options": corpus_options(),
    }
    with pytest.raises(ValueError, match="audit"):
        write_inventory(fake, tmp_path / "inv.md")


def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _tables(body: str):
    out, buf = [], []
    for line in body.splitlines() + [""]:
        if line.startswith("|"):
            buf.append(line)
            continue
        if len(buf) >= 2:
            out.append((buf[0], buf[1:]))
        buf = []
    return out


def _render() -> str:
    import tempfile
    from pathlib import Path as _P

    from autorate.inventory import write_inventory

    d = {
        "source": "x",
        "lines_by_mode_backend": {"choice/laya": 192, "four_noul/jev": 192},
        "unique_ids": 64, "repeats": [0, 1, 2], "families": ["lifecycle"],
        "label_counts": {"todo": 16}, "provenance": "p",
        "upstream_audit_rc": 0, "upstream_audit_stdout_tail": "",
        "upstream_audit_stderr_tail": "",
        "digests": [],
        "gaps": ["g"], "audit_interpreter": "python", "corpus_options": corpus_options(),
    }
    with tempfile.TemporaryDirectory() as td:
        out = _P(td) / "inv.md"
        write_inventory(d, out)
        return out.read_text()


def test_every_markdown_table_in_the_inventory_is_structurally_valid():
    """A cell containing a raw pipe adds a column and breaks the table.

    The `"192" in body` check cannot see that, so structure is checked as structure:
    header, delimiter row of the same width, and equal cell counts in every row.
    """
    tables = _tables(_render())
    assert len(tables) >= 2, "expected the records and corpus tables"
    for header, rows in tables:
        ncol = len(_cells(header))
        assert ncol >= 2, header
        assert len(rows) >= 2, header
        assert len(_cells(rows[0])) == ncol, "delimiter width != header: %r" % rows[0]
        for line in rows[1:]:
            assert len(_cells(line)) == ncol, "column drift (%d vs %d): %r" % (
                len(_cells(line)), ncol, line)


def test_that_structural_check_proves_it_can_fire():
    # Negative control: the same checker must reject the pipe-separated keys that
    # this task replaced, or the test above is green by construction.
    body = _render().replace("choice/laya", "choice|laya")
    offenders = [line for h, rows in _tables(body) for line in rows
                 if len(_cells(line)) != len(_cells(h))]
    assert offenders, "the structural check cannot detect a pipe inside a table cell"


def _digest(root: Path) -> dict:
    """Path -> (size, mtime_ns) for every regular file, excluding bytecode caches."""
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
            st = p.stat()
            out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


def test_audit_is_invoked_with_bytecode_writing_disabled():
    # The guard behind test_reading_the_corpus_never_writes_into_the_vendored_tree:
    # a subprocess without PYTHONDONTWRITEBYTECODE would silently re-dirty the tree.
    from autorate.inventory import audit_command

    cmd, env = audit_command(UPSTREAM)
    assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
    assert cmd[-2:] == ["audit.py"] or str(cmd[-1]).endswith("audit.py")


def _tiny_corpus(tmp_path: Path, *, declare_cases=None, n_ids: int = 2) -> Path:
    """A corpus root small enough to build in a test, so both CI lanes run these.

    `inventory()` shells out to upstream's audit with `cwd=root`, so the stub `audit.py`
    is the only integrity verdict a synthetic corpus can carry; the real one is asserted
    by the corpus-gated tests above.
    """
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    manifest = {"asks": {"a1": "question?"}, "labels": {"a": 1}, "families": ["f"],
                "provenance": "test-fixture"}
    if declare_cases is not None:
        manifest["cases"] = declare_cases
    (tmp_path / "data" / "manifest.json").write_text(json.dumps(manifest))
    lines = [json.dumps({"id": "c%d" % i, "expected": "a"}) for i in range(n_ids)]
    (tmp_path / "data" / "cases.jsonl").write_text("\n".join(lines) + "\n")
    rows = [json.dumps({
        "id": "c%d" % i, "mode": "choice", "repeat": 0, "status": "ok", "expected": "a",
        "response": {"model": "m", "answers": {"category": {
            "type": "choice", "choice": "a",
            "probabilities": {"a": 0.5, "b": 0.5}}}}}) for i in range(n_ids)]
    for backend in ("laya", "jev"):
        d = tmp_path / "results" / "v1" / backend
        d.mkdir(parents=True, exist_ok=True)
        (d / "raw.jsonl").write_text("\n".join(rows) + "\n")
    (tmp_path / "audit.py").write_text("import sys\nsys.exit(0)\n")
    return tmp_path


def _inventory_keys() -> list:
    return sorted(json.loads(Path("data/inventory.md.json").read_text()))


def test_the_published_inventory_names_no_key_that_claims_a_calibration_number():
    """`min_calibration_n` published the corpus's TOTAL case count under a floor-shaped name.

    It was never a minimum, never the calibration half (R-44's case-level split puts ~32 of
    the 64 cases there), and never asserted by a test -- while the real floor is
    `certify_choice.MIN_CAL` and the real calibration size is the certifier's own published
    `n_cal_cases`. A published name that claims a quantity this module never measured is the
    same defect class as the 151,674-row over-claim the same file already confesses to.
    """
    keys = _inventory_keys()
    assert len(keys) > 20, "reading a stub artefact would make this pass by being empty"
    bad = [k for k in keys if "calibration" in k]
    assert bad == [], bad


def test_that_calibration_key_check_proves_it_can_fire():
    """The guard must be able to catch the historical key, before and after it is gone.

    Asserting a count delta rather than an empty list keeps this control meaningful once
    the fix lands: it proves the predicate fires exactly once per injected key, so the guard
    above cannot be green because its filter matched nothing at all.
    """
    keys = _inventory_keys()
    clean = [k for k in keys if "calibration" in k]
    caught = [k for k in keys + ["min_calibration_n"] if "calibration" in k]
    assert len(caught) == len(clean) + 1, (clean, caught)


def test_a_manifest_that_declares_no_case_count_publishes_none_not_our_recount(tmp_path):
    d = inventory(_tiny_corpus(tmp_path, n_ids=2))
    assert d["unique_ids"] == 2
    assert d["manifest_declared_cases"] is None, (
        "the fallback to len(ids) published a number this module counted as if the manifest "
        "had declared it")


def test_the_declared_case_count_stays_the_manifest_s_even_where_we_disagree(tmp_path):
    d = inventory(_tiny_corpus(tmp_path, declare_cases=7, n_ids=2))
    assert d["manifest_declared_cases"] == 7, "recounting would hide a manifest/archive gap"
    assert d["unique_ids"] == 2


# ---------------------------------------------------------------------------
# Task 1b: the inventory scanner shares the reader's malformed-line rule (R-55)
# ---------------------------------------------------------------------------
#
# Every shape below is PLANTED in a `tmp_path` copy, never observed: the shipped archive
# measures 384 lines in `laya/raw.jsonl` and 384 in `jev/raw.jsonl` with 0 unreadable lines,
# so a test that only ran the real corpus would prove nothing except that today's data is
# clean. Against the pre-guard scanner these same shapes raised `JSONDecodeError` / `KeyError`
# / `TypeError` out of `_scan_jsonl`, and through the shipped CLI two of them exited 1 -- the
# one exit code this project's contract says no reachable path may emit.

def _planted_row(drop=(), **kw):
    """One readable `choice` line, with the fields a counting pass indexes blind."""
    row = {"id": "p1", "mode": "choice", "repeat": 0, "status": "ok", "expected": "a",
           "family": "f",
           "response": {"model": "m", "answers": {"category": {
               "type": "choice", "choice": "a",
               "probabilities": {"a": 0.5, "b": 0.5}}}}}
    row.update(kw)
    for key in drop:
        row.pop(key)
    return row


# (label, raw line, the exception type the named reason carries). `response` is kept present
# on the missing-key shapes so the reader and the scanner fail on the SAME key: the two error
# strings are asserted equal below, and that comparison is only meaningful if both passes are
# stopped by the same defect in the same line.
_PLANTED = (
    ("truncated json", '{"id": "p1", "mo', "JSONDecodeError"),
    ("json list", "[1, 2, 3]", "TypeError"),
    ("json null", "null", "TypeError"),
    ("no mode", json.dumps(_planted_row(drop=("mode",))), "KeyError"),
    ("no id", json.dumps(_planted_row(drop=("id",))), "KeyError"),
    ("no repeat", json.dumps(_planted_row(drop=("repeat",))), "KeyError"),
    ("no choice answers", json.dumps(_planted_row(response={"model": "m", "answers": {}})),
     "KeyError"),
    ("probability is not a number", json.dumps(_planted_row(response={"model": "m", "answers": {
        "category": {"type": "choice", "probabilities": {"a": "high", "b": 0.5}}}})), "ValueError"),
)

# A `mode` outside MODES is the opposite case: the line IS readable, so the rule must name it
# without filing it under the unreadable bucket -- the reader already files it by mode string.
_UNBUCKETABLE_MODE = json.dumps(_planted_row(mode="ranked"))


def _plant(tmp_path, raw_lines, n_good=2, backend="laya"):
    """`_tiny_corpus`, then planted lines appended to ONE backend so per-backend counts are real.

    Returns the root and the `line_no` of the first planted line.
    """
    root = _tiny_corpus(tmp_path, n_ids=n_good)
    target = root / "results" / "v1" / backend / "raw.jsonl"
    target.write_text(target.read_text() + "".join(
        line if line.endswith("\n") else line + "\n" for line in raw_lines))
    return root, n_good + 1


def _identity(d):
    """The quantity the conservation identity is asserted over: bucketed + named lines."""
    return sum(d["lines_by_mode_backend"].values()) + sum(d["lines_quarantined_only"].values())


def _snapshot_cli(root, out):
    """Run the SHIPPED console entry point, not `inventory()`.

    The exit-code contract (0 CERTIFIED / 2 USAGE / 3 NOT_CERTIFIABLE / 4 DRIFT, and rc 1
    unreachable) governs the process. A test that calls the function cannot see it: the defect
    this task closes was a function raising and `main` having no mapping for it.
    """
    exe = shutil.which("autorate")
    assert exe, "the `autorate` console script is not on PATH: the shipped entry point cannot run"
    env = dict(os.environ)
    env["AUTORATE_FEISHU_ROOT"] = str(root)
    return subprocess.run([exe, "snapshot", "--root", str(root), "--out", str(out)],
                          capture_output=True, text=True, cwd=str(REPO), env=env)


@pytest.mark.parametrize("label,raw,error_prefix", _PLANTED)
def test_a_planted_unreadable_line_is_counted_and_named(tmp_path, label, raw, error_prefix):
    root, line_no = _plant(tmp_path, [raw])
    d = inventory(root)          # raised before the guard; must not now
    assert d["lines_malformed"] == 1, label
    assert d["lines_malformed_by_backend"] == {"jev": 0, "laya": 1}, label
    assert d["lines_quarantined_only"] == {"malformed_line": 1}, label
    entries = d["lines_outside_mode_counts"]
    assert len(entries) == 1, label
    entry = entries[0]
    assert entry["reason"] == "malformed_line", entry
    assert entry["backend"] == "laya" and entry["line_no"] == line_no, entry
    assert entry["error"].startswith(error_prefix), entry
    # The readable lines keep the counts they had before the change: a guard that silently
    # re-bucketed would show up here, not in the malformed total.
    assert d["lines_by_mode_backend"] == {"choice/jev": 2, "choice/laya": 2,
                                          "four_noul/jev": 0, "four_noul/laya": 0}, label
    # An unreadable line joins neither the case count nor the line denominator it cannot read.
    assert d["unique_ids"] == 2, label
    assert _identity(d) == d["reader_lines_read"] == 5, (label, d)


@pytest.mark.parametrize("label,raw,error_prefix", _PLANTED)
def test_the_scanner_and_the_reader_name_the_same_line_identically(tmp_path, label, raw,
                                                                   error_prefix):
    """R-55 is the whole point of the task: ONE malformed-line rule, so one owner for the name.

    Both passes read the same bytes, so a line one of them cannot read must be named by the
    other the same way. Copied `try/except` sets drift invisibly -- the day the scanner grows
    its own rule, this is the only thing that notices a shape passing one guard and not the other.
    """
    from autorate.readers.feishu_zh import read_archive

    sub = tmp_path / label.replace(" ", "_")
    sub.mkdir()
    root, line_no = _plant(sub, [raw])
    d = inventory(root)
    stats = {}
    read_archive(root, stats=stats)
    scanner = [e for e in d["lines_outside_mode_counts"] if e["reason"] == "malformed_line"]
    reader = [e for e in stats["quarantined"] if e["reason"] == "malformed_line"]
    assert len(scanner) == len(reader) == 1, (label, scanner, reader)
    assert scanner[0]["error"] == reader[0]["error"], (label, scanner[0], reader[0])
    assert scanner[0]["line_no"] == reader[0]["line_no"] == line_no, (label, scanner, reader)
    assert d["lines_malformed"] == stats["lines_malformed"] == 1, label
    assert d["lines_quarantined_only"] == stats["lines_quarantined_only"], label


def test_a_mode_this_inventory_cannot_bucket_is_named_but_is_not_unreadable(tmp_path):
    """A readable line whose `mode` is outside MODES has a bucket of its own, not `malformed_line`.

    The reader files it under the mode string (Task 1's ruling), so the scanner must too: one
    shape filed two ways is the disagreement about the corpus this task exists to close.
    """
    from autorate.readers.feishu_zh import read_archive

    root, line_no = _plant(tmp_path, [_UNBUCKETABLE_MODE])
    d = inventory(root)
    assert d["lines_malformed"] == 0, d
    assert d["lines_quarantined_only"] == {"ranked": 1}, d
    entry = d["lines_outside_mode_counts"][0]
    assert entry["reason"] == "mode 'ranked' is not readable by this reader", entry
    assert entry["line_no"] == line_no and entry["mode"] == "ranked", entry
    assert d["lines_by_mode_backend"] == {"choice/jev": 2, "choice/laya": 2,
                                          "four_noul/jev": 0, "four_noul/laya": 0}, d
    assert _identity(d) == d["reader_lines_read"] == 5, d
    stats = {}
    read_archive(root, stats=stats)
    assert stats["lines_quarantined_only"] == {"ranked": 1}, stats
    assert stats["lines_malformed"] == 0, stats


def test_the_conservation_identity_closes_over_a_mixed_corpus(tmp_path):
    """lines read = lines counted per mode + lines named outside those counts, asserted by inventory.

    Three good lines and nine planted defects per backend pair: the identity has to account for
    every one of them, and the reader's own count of the same files has to agree.
    """
    from autorate.readers.feishu_zh import read_archive

    planted = [raw for _, raw, _ in _PLANTED] + [_UNBUCKETABLE_MODE]
    root, first_planted = _plant(tmp_path, planted, n_good=3)
    d = inventory(root)
    assert first_planted == 4, first_planted
    assert d["lines_malformed"] == len(_PLANTED), d
    assert d["lines_malformed_by_backend"] == {"laya": len(_PLANTED), "jev": 0}, d
    assert d["lines_quarantined_only"] == {"malformed_line": len(_PLANTED), "ranked": 1}, d
    entries = d["lines_outside_mode_counts"]
    assert sorted(e["line_no"] for e in entries) == list(range(4, 4 + len(planted))), entries
    assert d["unique_ids"] == 3, "an unreadable line must not join the case count"
    assert d["lines_by_mode_backend"]["choice/laya"] == 3, d
    assert _identity(d) == d["reader_lines_read"] == 3 * 2 + len(planted), d
    stats = {}
    read_archive(root, stats=stats)
    assert d["lines_quarantined_only"] == stats["lines_quarantined_only"], stats


def test_a_good_corpus_publishes_exactly_the_numbers_it_did_before_the_guard(tmp_path):
    """The refactor is a fix, not a rewrite: a clean corpus re-buckets nothing.

    Every figure is pinned to the value the pre-guard scanner produced for the same fixture, and
    the new disclosure keys are zeros -- which is also why no published number moves.
    """
    d = inventory(_tiny_corpus(tmp_path, n_ids=4))
    assert d["lines_by_mode_backend"] == {"choice/jev": 4, "choice/laya": 4,
                                          "four_noul/jev": 0, "four_noul/laya": 0}, d
    assert d["unique_ids"] == 4 and d["repeats"] == [0], d
    assert d["lines_malformed"] == 0 and d["lines_outside_mode_counts"] == [], d
    assert d["lines_malformed_by_backend"] == {"jev": 0, "laya": 0}, d
    assert d["lines_quarantined_only"] == {}, d
    assert _identity(d) == d["reader_lines_read"] == 8, d


def test_the_committed_snapshot_gained_the_new_buckets_and_no_moved_number():
    """The shipped corpus has nothing to quarantine, so the guard publishes zeros there too.

    Read from the committed artefact rather than from a fresh scan: this is the check that the
    re-snapshot landed additive keys and left every published number alone.
    """
    published = json.loads((REPO / "data" / "inventory.md.json").read_text())
    assert published["unique_ids"] == 64 and published["repeats"] == [0, 1, 2], published
    assert published["lines_by_mode_backend"] == {"choice/jev": 192, "choice/laya": 192,
                                                  "four_noul/jev": 192, "four_noul/laya": 192}
    assert published["lines_malformed"] == 0, published
    assert published["lines_malformed_by_backend"] == {"jev": 0, "laya": 0}, published
    assert published["lines_outside_mode_counts"] == [], published
    assert published["reader_lines_read"] == 768, published
    assert sum(published["lines_by_mode_backend"].values()) == published["reader_lines_read"]


def test_the_committed_inventory_markdown_names_no_unreadable_line():
    """The guard is latent on the shipped corpus, so the human artefact must not change either.

    Asserted against the committed file rather than a fresh render, because this task's own
    gate is "no published number and no published sentence moves": zeros belong in the
    machine-readable snapshot, not in prose an operator reads as a finding.
    """
    body = (REPO / "data" / "inventory.md").read_text()
    assert "outside the per-mode counts" not in body, body
    assert len(_tables(body)) == 3, [h for h, _ in _tables(body)]


def test_the_unreadable_disclosure_is_bounded_and_says_what_it_left_out(tmp_path):
    """A defect list is disclosed under the same discipline as the reader's quarantine."""
    from autorate.inventory import UNREADABLE_DISCLOSURE_LIMIT

    planted = ['{"id": "p%d", "mo' % i for i in range(UNREADABLE_DISCLOSURE_LIMIT + 2)]
    root, _ = _plant(tmp_path, planted)
    d = inventory(root)
    assert d["lines_malformed"] == len(planted), d
    assert len(d["lines_outside_mode_counts"]) == UNREADABLE_DISCLOSURE_LIMIT, d
    gaps = [g for g in d["gaps"] if "outside the per-mode counts" in g]
    assert len(gaps) == 1, d["gaps"]
    assert "%d archive line(s)" % len(planted) in gaps[0], gaps
    assert "the first %d are named" % UNREADABLE_DISCLOSURE_LIMIT in gaps[0], gaps


def test_write_inventory_names_the_unreadable_lines_and_stays_quiet_on_zeros(tmp_path):
    """The human-readable artefact carries the same disclosure, and adds no table to the file."""
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    root, _ = _plant(dirty, [json.dumps(_planted_row(drop=("mode",))), _UNBUCKETABLE_MODE])
    out = dirty / "inventory.md"
    write_inventory(inventory(root), out)
    body = out.read_text()
    assert "outside the per-mode counts" in body, body
    assert "laya line 3" in body, body        # backend + line_no, so an operator can find it
    assert len(_tables(body)) == 3, "the disclosure must not add a fourth table"

    clean = tmp_path / "clean"
    clean.mkdir()
    clean_out = clean / "inventory.md"
    write_inventory(inventory(_tiny_corpus(clean, n_ids=2)), clean_out)
    clean_body = clean_out.read_text()
    assert "outside the per-mode counts" not in clean_body, clean_body
    assert len(_tables(clean_body)) == 3, clean_body


def test_rc_one_is_unreachable_for_every_planted_shape(tmp_path):
    """The contract sweep: 0/2/3/4 only, and a corpus defect never becomes a usage error.

    Before the guard these inputs exited 2 (a `JSONDecodeError` is a `ValueError`, which
    `main` maps to EXIT_USAGE) or 1 (`TypeError`/`KeyError` escaped every catch). Both were
    wrong: the corpus is neither certified-nothing nor the operator's mistake.
    """
    for label, raw, _ in _PLANTED + (("mode outside MODES", _UNBUCKETABLE_MODE, "n/a"),):
        case = tmp_path / label.replace(" ", "_")
        case.mkdir()
        proc = _snapshot_cli(_plant(case, [raw])[0], case / "inventory.md")
        assert proc.returncode == 0, (label, proc.returncode, proc.stderr[-500:])
        assert proc.returncode != 1, label
        assert "Traceback" not in proc.stderr, (label, proc.stderr[-500:])
        sidecar = json.loads(Path(str(case / "inventory.md") + ".json").read_text())
        # `lines_quarantined_only` is the total of every line named outside the mode counts, and
        # `lines_malformed` is one of its buckets -- the same quantity rendered twice, which
        # `assert_line_conservation` refuses to let drift. Adding the two would count the planted
        # line twice and call the artefact wrong; the line is named once, per bucket.
        named = sum(sidecar["lines_quarantined_only"].values())
        assert named == 1, (label, sidecar["lines_quarantined_only"])
        assert len(sidecar["lines_outside_mode_counts"]) == 1, (label, sidecar)
        assert sidecar["lines_malformed"] == sum(
            sidecar["lines_malformed_by_backend"].values()), (label, sidecar)


def test_a_refused_corpus_still_exits_two_while_an_unreadable_line_exits_zero(tmp_path):
    """The `ReaderContractError` interaction, tested rather than asserted.

    `ReaderContractError` is a `RuntimeError` and NOT a `ValueError` precisely so a per-line
    guard cannot absorb it. A widened catch would file a policy refusal under `malformed_line`
    and exit 0 on a corpus this project refused to read -- so the refusal must still reach
    EXIT_USAGE while a genuinely unreadable line is inventoried with rc 0.
    """
    from autorate.readers.feishu_zh import ReaderContractError

    assert not issubclass(ReaderContractError, ValueError), "the per-line guard would absorb it"

    refused = tmp_path / "refused"
    refused.mkdir()
    root = _tiny_corpus(refused, n_ids=1)
    # The fixtures now supervise an ask: R-14 says the reader must refuse rather than invent
    # per-ask gold, and that refusal is not a line it could not read.
    (root / "data" / "manifest.json").write_text(json.dumps(
        {"asks": {"urgent": "is it urgent?"}, "labels": {"a": 1}, "families": ["f"],
         "provenance": "test-fixture"}))
    (root / "data" / "cases.jsonl").write_text(
        json.dumps({"id": "c0", "expected": "a", "urgent": "true"}) + "\n")
    noul = json.dumps(_planted_row(mode="four_noul", response={"model": "m", "answers": {
        "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.8}}}))
    for backend in ("laya", "jev"):
        (root / "results" / "v1" / backend / "raw.jsonl").write_text(noul + "\n")
    refused_proc = _snapshot_cli(root, refused / "inventory.md")
    assert refused_proc.returncode == 2, (refused_proc.returncode, refused_proc.stderr[-500:])
    assert "ReaderContractError" in refused_proc.stderr, refused_proc.stderr
    assert "Traceback" not in refused_proc.stderr, refused_proc.stderr

    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    bad_root, _ = _plant(unreadable, [_PLANTED[0][1]])
    ok_proc = _snapshot_cli(bad_root, unreadable / "inventory.md")
    assert ok_proc.returncode == 0, (ok_proc.returncode, ok_proc.stderr[-500:])
    sidecar = json.loads(Path(str(unreadable / "inventory.md") + ".json").read_text())
    assert sidecar["lines_malformed"] == 1, sidecar
    assert sidecar["lines_outside_mode_counts"][0]["reason"] == "malformed_line", sidecar


def test_a_line_the_reader_drops_for_its_own_reason_is_not_the_same_as_unreadable(tmp_path):
    """The measured boundary of the shared rule, recorded so nobody "fixes" it into agreement.

    A line carrying no `status` is readable and its `mode` is in MODES, so the scanner counts it
    in the per-mode table; the reader never tries to turn it into a record and files it under its
    own `lines_dropped_not_ok`. Neither pass loses it -- both see 5 lines -- and the labels differ
    on purpose: dropping a refused response is not the same rule as failing to parse a line. The
    asymmetry is real and pinned here rather than smoothed over, because the same two counters
    answering "how many choice lines are in the archive" is how a reader comes to believe 192
    lines became 192 records.
    """
    from autorate.readers.feishu_zh import read_archive

    no_status = json.dumps(_planted_row(drop=("status",)))
    root, _ = _plant(tmp_path, [no_status], backend="jev")
    d = inventory(root)
    assert d["lines_malformed"] == 0, d
    assert d["lines_quarantined_only"] == {}, d
    assert d["lines_outside_mode_counts"] == [], d
    assert d["lines_by_mode_backend"]["choice/jev"] == 3, d      # 2 good + the refused line
    stats = {}
    read_archive(root, stats=stats)
    assert stats["lines_malformed"] == 0, stats
    assert stats["lines_dropped_not_ok"] == 1, stats
    assert _identity(d) == d["reader_lines_read"] == 5, d
    # The two passes' per-mode counts are different quantities, and the artefact names them
    # apart: `lines_by_mode_backend` is archive lines, `reader_lines_by_mode` is records kept.
    assert sum(d["lines_by_mode_backend"].values()) == 5, d
    assert sum(d["reader_lines_by_mode"].values()) == 4, d


def test_the_conservation_check_can_fire():
    """The identity must be able to refuse a branch that drops a line without a counter.

    Without this control the assertion in `inventory()` is green by construction: a check that
    cannot fail is the case this project refuses to accept as evidence.
    """
    from autorate.inventory import assert_line_conservation

    assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                             lines_quarantined_only={"malformed_line": 2},
                             lines_malformed=2, lines_malformed_by_backend={"laya": 2})
    with pytest.raises(ArithmeticError, match="does not conserve"):
        assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                                 lines_quarantined_only={"malformed_line": 1},
                                 lines_malformed=1, lines_malformed_by_backend={"laya": 1})
    with pytest.raises(ArithmeticError, match="does not match"):
        assert_line_conservation(lines_read=4, lines_by_mode={"choice": 2},
                                 lines_quarantined_only={"malformed_line": 2},
                                 lines_malformed=1, lines_malformed_by_backend={"laya": 1})


def test_the_pin_list_refuses_to_disagree_with_itself(tmp_path):
    """`massive_pin`'s shape guards can fire, or the totals they police are decoration.

    The published row counts come from this file, so a pin whose declared totals are not the sum
    of its own entries would print a number no reader can re-derive -- the O-6 defect again, one
    layer down. Each arm plants one disagreement and names the quantity it caught.
    """
    from autorate.inventory import massive_pin

    good = massive_pin()
    path = tmp_path / "massive_provenance.json"
    path.write_text(json.dumps(good))
    assert massive_pin(path)["n_files"] == 51, "the control arm must read the real pin"

    for key, mutate in (
        ("n_files", lambda p: p.update(n_files=50)),
        ("rows_total", lambda p: p.update(rows_total=1)),
        ("bytes_total", lambda p: p.update(bytes_total=p["bytes_total"] + 1)),
    ):
        broken = json.loads(json.dumps(good))
        mutate(broken)
        path.write_text(json.dumps(broken))
        with pytest.raises(ArithmeticError, match=key):
            massive_pin(path)

    no_files = tmp_path / "empty.json"
    no_files.write_text(json.dumps({"dataset": "x"}))
    with pytest.raises(ArithmeticError, match="no `files` list"):
        massive_pin(no_files)


def test_the_pooled_massive_row_reports_the_whole_pin_list_and_names_its_owner(tmp_path):
    """O-6: the basis said "3 of 51 files opened" while all 51 pinned shards were opened and hashed.

    The upgrade may not type a number: the count comes from the committed pin list, and the
    prose names that file as its owner, so a reader can re-derive it. The limit is stated in the
    same sentence -- the shards are not vendored, so this repository carries the pin list rather
    than re-hashing bytes -- because an ownerless number is the defect `docs/ERRATA.md` records
    twice, and printing 51 while the only evidence sat in a gitignored file would recreate it.
    """
    from autorate.inventory import massive_pin, massive_pooled_basis

    pin = massive_pin()
    assert pin, "the pin list is not committed: O-6's owner is missing"
    files = pin["files"]
    assert len(files) == pin["n_files"] == 51, len(files)
    assert len({f["path"] for f in files}) == 51
    assert {f["rows"] for f in files} == {2974}
    assert pin["distinct_row_counts"] == [2974]
    assert all(re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) for f in files)
    assert pin["rows_total"] == 51 * 2974 == 151674
    assert pin["dataset"] == "mteb/amazon_massive_intent" and pin["revision"]

    basis = massive_pooled_basis(pin)
    assert "51 of 51" in basis and "data/massive_provenance.json" in basis, basis
    option = {o["id"]: o for o in corpus_options(64)}["massive_intent_all_languages"]
    assert option["basis"] == basis, option
    assert option["n_rows"] == pin["rows_total"], option
    # The pool row is not independent cases: 51 translations of one utterance set.
    assert option["n_independent"] == 2974, option

    absent = massive_pooled_basis({})
    assert "51 of 51" not in absent, absent
    assert "cannot" in absent, absent


def test_that_the_pinned_shard_count_proves_it_can_fire():
    """The prose must move with the list, or "51 of 51" is a typed word wearing a derivation."""
    from autorate.inventory import massive_pin, massive_pooled_basis, massive_pinned_shards

    pin = massive_pin()
    assert massive_pinned_shards(pin) == (51, 51), massive_pinned_shards(pin)
    one_short = {**pin, "files": pin["files"][:-1]}
    assert massive_pinned_shards(one_short) == (50, 51), massive_pinned_shards(one_short)
    assert "50 of 51" in massive_pooled_basis(one_short), massive_pooled_basis(one_short)
    unhashed = {**pin, "files": [{**f, "sha256": ""} for f in pin["files"]][:20]}
    assert massive_pinned_shards(unhashed) == (20, 51), massive_pinned_shards(unhashed)


def test_the_per_ask_gold_local_is_named_for_what_it_holds():
    """O-7: `gold` was the whole per-ask measurement, not a gold value.

    A misleading local is invisible to a behavioural test -- the expression it indexes is
    unchanged and still correct -- so this reads the shipped source, with the control that the
    predicate catches the name it replaced.
    """
    src = inspect.getsource(inventory)
    assert 'gold["asks_with_gold"]' not in src, src
    assert 'ask_gold_measurement["asks_with_gold"]' in src, src
    mutated = src.replace("ask_gold_measurement[", "gold[")
    assert 'gold["asks_with_gold"]' in mutated, "the predicate above cannot fail"
