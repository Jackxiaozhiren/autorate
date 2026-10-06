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
from autorate.readers.feishu_zh import MALFORMED_LINE

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
    # 192 `choice` lines were archived on each backend; R-80 names the jev one whose published
    # probabilities do not close rather than bucketing it, because the reader keeps no record for
    # it, so the table reads 191 for `choice/jev` and `lines_quarantined_only` carries the 192nd.
    assert d["lines_by_mode_backend"] == {
        "choice/laya": 192,
        "choice/jev": 191,
        "four_noul/laya": 192,
        "four_noul/jev": 192,
    }
    assert d["lines_quarantined_only"] == d["reader_lines_quarantined_only"] == {"choice": 1}, d
    assert d["lines_refused_not_ok"] == 0, d
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
        by_mode, ids, reps, unclosed, outside, refused, lines_read = _scan_jsonl(p)
    assert by_mode == {"choice": 1} and unclosed == []
    # Task 1b: one readable line, so the unreadable buckets are empty and the identity
    # closes over the line the pass read.
    assert (outside == [] and refused == 0 and lines_read == 1 and ids == {"k-0"}
            and reps == [0])


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

# R-80 (review MA-2's rows 3-5, the half the first fix left open): readable lines that must be
# COUNTED and named NOWHERE, plus the readable line whose `mode` spells the internal bucket. The
# first fix put `LINE_KEYS` on the `status == "ok"` branch, which closed the shape it planted and
# proved nothing about the ones below -- the shipped corpus is entirely `status: "ok"` (measured:
# `{'ok': 768}` across both `raw.jsonl`), so only a planted lane can see this class at all.
_PLANTED_REFUSED = (
    ("not ok, mode outside MODES", json.dumps(_planted_row(mode="ranked", status="cached"))),
    ("not ok, no mode", json.dumps(_planted_row(drop=("mode",), status="error"))),
    ("not ok, mode in MODES", json.dumps(_planted_row(status="error"))),
    ("mode spells the internal bucket", json.dumps(_planted_row(mode=MALFORMED_LINE))),
)

# The ledger each refused shape must produce in BOTH passes: `{}` for a line refused on its
# `status`, because the reader declines it before it reads a `mode`, and the namespaced key for a
# mode string that would otherwise borrow the internal bucket's name (R-81).
_REFUSED_LEDGER = {
    "not ok, mode outside MODES": {},
    "not ok, no mode": {},
    "not ok, mode in MODES": {},
    "mode spells the internal bucket": {"mode:malformed_line": 1},
}


def _every_planted_shape():
    """The whole planted sweep: unreadable shapes, the unbucketable mode, and the refused ones.

    Each entry carries the quarantine ledger BOTH passes must publish for that single planted line,
    which is the claim R-80 makes -- `{}` for a line refused on its `status`, and the namespaced key
    for a mode string that would otherwise borrow the internal bucket's name.
    """
    return ([(label, raw, {"malformed_line": 1}) for label, raw, _ in _PLANTED]
            + [("mode outside MODES", _UNBUCKETABLE_MODE, {"ranked": 1})]
            + [(label, raw, _REFUSED_LEDGER[label]) for label, raw in _PLANTED_REFUSED])


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
    """The quantity the conservation identity is asserted over: bucketed, named, and refused lines.

    R-80 added the third term: a line refused on its own `status` is counted by the scanner and
    named by neither pass's quarantine ledger, so it appears in neither of the first two totals and
    the identity only closes over all three.
    """
    return (sum(d["lines_by_mode_backend"].values()) + sum(d["lines_quarantined_only"].values())
            + d["lines_refused_not_ok"])


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


@pytest.mark.parametrize("label,raw,ledger", _every_planted_shape())
def test_the_two_published_quarantine_ledgers_are_one_dict_for_every_planted_shape(tmp_path,
                                                                                   label, raw,
                                                                                   ledger):
    """R-80 as a gate that can fail: the artefact publishes two ledgers, and they must be equal.

    `lines_quarantined_only` (the scanner) and `reader_lines_quarantined_only` (the reader) sit
    beside each other in `data/inventory.md.json`, and the comment over them claimed they mirrored
    each other while two shapes refuted it: a refused line whose `mode` was outside MODES (named by
    one pass, dropped by the other, and under the literal key `"None"` at that), and the shipped
    corpus's one unclosing `choice` line (bucketed by the scanner, quarantined by the reader). The
    sweep covers both, and the ledger is asserted as data on BOTH dicts rather than on prose.

    Before this round's source change the three refused shapes measured `{'ranked': 1}`, `{'None':
    1}` and `{}` against the reader's empty ledger, and the real corpus measured `{}` against
    `{'choice': 1}`.
    """
    from autorate.readers.feishu_zh import read_archive

    sub = tmp_path / label.replace(" ", "_").replace("`", "")
    sub.mkdir()
    root, _ = _plant(sub, [raw])
    d = inventory(root)
    stats = {}
    read_archive(root, stats=stats)
    assert d["lines_quarantined_only"] == ledger, (label, d)
    assert d["reader_lines_quarantined_only"] == ledger, (label, d)
    assert stats["lines_quarantined_only"] == ledger, (label, stats)
    # The refused counter is the other half of the same ruling: equal for every shape, because
    # neither pass reads a `mode` from a line it declined.
    assert d["lines_refused_not_ok"] == stats["lines_dropped_not_ok"], (label, d, stats)
    assert _identity(d) == d["reader_lines_read"] == 5, (label, d)


def test_the_conservation_identity_closes_over_a_mixed_corpus(tmp_path):
    """lines read = bucketed + named + refused, asserted by inventory, over every planted shape.

    Three good lines and every defect this file can plant -- unreadable, unbucketable mode, refused
    `status`, and a mode string that spells the internal bucket -- in one corpus: the identity has to
    account for each of them, the reader's own count of the same files has to agree, and the two
    published quarantine ledgers have to be the same dict (R-80).
    """
    from autorate.readers.feishu_zh import read_archive

    refused_lines = [raw for _, raw in _PLANTED_REFUSED]
    planted = [raw for _, raw, _ in _PLANTED] + [_UNBUCKETABLE_MODE] + refused_lines
    root, first_planted = _plant(tmp_path, planted, n_good=3)
    d = inventory(root)
    assert first_planted == 4, first_planted
    assert d["lines_malformed"] == len(_PLANTED), d
    assert d["lines_malformed_by_backend"] == {"laya": len(_PLANTED), "jev": 0}, d
    assert d["lines_quarantined_only"] == {"malformed_line": len(_PLANTED), "ranked": 1,
                                          "mode:malformed_line": 1}, d
    entries = d["lines_outside_mode_counts"]
    # The three refused shapes are counted, never named, so they are absent from the list the
    # named shapes are disclosed in: unreadable lines on 4..3+N, the unbucketable mode right after
    # them, then three refused lines with no entry, then the mode that spells the internal bucket.
    n_unreadable = len(_PLANTED)
    assert sorted(e["line_no"] for e in entries) == sorted(
        list(range(4, 4 + n_unreadable)) + [4 + n_unreadable, 8 + n_unreadable]), entries
    assert d["unique_ids"] == 3, "an unreadable line must not join the case count"
    assert d["lines_by_mode_backend"]["choice/laya"] == 3, d
    assert d["lines_refused_not_ok"] == 3, d
    assert _identity(d) == d["reader_lines_read"] == 3 * 2 + len(planted), d
    stats = {}
    read_archive(root, stats=stats)
    assert d["lines_quarantined_only"] == stats["lines_quarantined_only"], stats
    assert d["lines_refused_not_ok"] == stats["lines_dropped_not_ok"], stats


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


def test_the_committed_snapshot_publishes_the_two_quarantine_ledgers_as_one_dict():
    """R-80 on the shipped artefact: the ledgers published side by side ARE the same dict.

    Read from the committed file rather than from a fresh scan, because this is the CI-runnable
    half of the claim: a corpus-less runner cannot re-derive the counts, but it can see that the
    artefact contradicts itself. Before the reconciliation the pair published `{}` beside
    `{'choice': 1}` for the shipped corpus's one unclosing `choice` line, while the comment over the
    two keys asserted they mirrored each other.

    Two published numbers move, and both are disclosed in `docs/ERRATA.md`: `choice/jev` 192 -> 191
    (that line is named, not bucketed), and `lines_quarantined_only` `{}` -> `{'choice': 1}`.
    `lines_refused_not_ok` is new and is 0 here, because the shipped archive is entirely `ok`.
    """
    published = json.loads((REPO / "data" / "inventory.md.json").read_text())
    assert published["unique_ids"] == 64 and published["repeats"] == [0, 1, 2], published
    assert published["lines_by_mode_backend"] == {"choice/jev": 191, "choice/laya": 192,
                                                  "four_noul/jev": 192, "four_noul/laya": 192}
    assert published["lines_malformed"] == 0, published
    assert published["lines_malformed_by_backend"] == {"jev": 0, "laya": 0}, published
    assert published["lines_refused_not_ok"] == 0, published
    assert len(published["lines_outside_mode_counts"]) == 1, published
    outside = published["lines_outside_mode_counts"][0]
    assert (outside["backend"], outside["id"], outside["repeat"]) == ("jev", "lifecycle-01", 1), \
        outside
    assert outside["reason"] == "probabilities do not close to 1 within tolerance", outside
    assert published["lines_quarantined_only"] == {"choice": 1}, published
    assert published["reader_lines_quarantined_only"] == {"choice": 1}, published
    # The equality this round exists to create, asserted as data on the published artefact.
    assert published["lines_quarantined_only"] == published["reader_lines_quarantined_only"]
    assert published["reader_lines_read"] == 768, published
    assert (sum(published["lines_by_mode_backend"].values())
            + sum(published["lines_quarantined_only"].values())
            + published["lines_refused_not_ok"]) == published["reader_lines_read"], published
    # And the reader's record count is still not a published quantity (m-2).
    assert "records_kept" not in published, sorted(published)


@skip
def test_the_real_corpus_publishes_the_two_quarantine_ledgers_equal(tmp_path):
    """R-80's claim on the corpus itself, not on its transcription: one line, named once, by both.

    `autorate snapshot` writes the committed artefact from this same call, so the CI-runnable test
    above is a check on the transcription of what this one measures. The shipped corpus has exactly
    one line outside the per-mode counts, and both passes must agree that it is the jev
    `lifecycle-01` repeat=1 whose published probabilities do not close.
    """
    from autorate.readers.feishu_zh import read_archive

    d = inventory(UPSTREAM)
    stats = {}
    read_archive(UPSTREAM, stats=stats)
    assert d["lines_quarantined_only"] == d["reader_lines_quarantined_only"] == {"choice": 1}, d
    assert d["lines_quarantined_only"] == stats["lines_quarantined_only"], stats
    assert d["lines_refused_not_ok"] == stats["lines_dropped_not_ok"] == 0, (d, stats)
    assert d["lines_malformed"] == stats["lines_malformed"] == 0, (d, stats)
    assert sum(d["lines_by_mode_backend"].values()) == sum(
        d["reader_lines_by_mode"].values()) == 767, d
    assert _identity(d) == d["reader_lines_read"] == 768, d
    assert [(u["backend"], u["id"], u["repeat"]) for u in d["probs_not_closing"]] == [
        ("jev", "lifecycle-01", 1)], d


def test_the_scanner_does_not_mirror_the_reader_s_per_ask_quarantine(tmp_path):
    """The measured limit of R-80, pinned so the equality above is never read as a theorem.

    The scanner reproduces the reader for the two shapes R-80 named. It does not model the
    `four_noul` per-ask refusals ("carries no noul-typed answer", "noul probability outside [0,1]"),
    because doing so would be a second implementation of the record-building rule -- and R-55 is the
    reason there is only one. So this shape is the one where the two published ledgers genuinely
    differ, on data the shipped corpus does not contain (measured: its `four_noul` ledger is empty
    and all 768 lines are `ok`), and the artefact's per-mode denominator double-counts it.
    """
    from autorate.readers.feishu_zh import read_archive

    empty_noul = json.dumps(_planted_row(mode="four_noul", response={"model": "m", "answers": {
        "urgent": {"type": "score", "noul": 0.5}}}))
    root, _ = _plant(tmp_path, [empty_noul])
    d = inventory(root)
    stats = {}
    read_archive(root, stats=stats)
    assert d["lines_quarantined_only"] == {}, d
    assert stats["lines_quarantined_only"] == {"four_noul": 1}, stats      # the planted line only
    assert d["reader_lines_quarantined_only"] == {"four_noul": 1}, d
    assert d["lines_by_mode_backend"]["four_noul/laya"] == 1, d            # bucketed by the scanner
    assert d["reader_lines_by_mode"].get("four_noul", 0) == 0, d           # kept by nobody
    # Both passes still account for every line, and neither exits 4 over it.
    assert _identity(d) == d["reader_lines_read"] == 5, d


def test_a_pinned_massive_row_without_an_id_set_says_which_of_the_two_it_is(tmp_path):
    """m-4: "not opened" was one cell for two findings, and for MASSIVE it contradicted its row.

    Measured on a pin carrying `id_sets_identical: false`: `autorate snapshot` exited 0 and the
    pooled row read `| massive_intent_all_languages | not opened | 151674 | 51 of 51 pinned shards
    opened, hashed and row-counted on ...` -- one cell denying what the cell beside it asserts. The
    shards WERE opened; what is missing is the id-set measurement that lets a translation table be
    read as a sample. `typed_decisions` keeps "not opened", because there it is the true statement:
    no file of that corpus was opened at all.

    The shipped artefact does not change: the committed pin records the id sets as identical, so no
    MASSIVE row reaches this cell, which the control arm below checks rather than assumes.
    """
    import tempfile

    from autorate.inventory import corpus_options, massive_pin, write_inventory

    pin = massive_pin()
    assert pin["id_sets_identical"] is True, pin

    def render(options):
        d = {
            "source": "x", "lines_by_mode_backend": {"choice/laya": 2}, "unique_ids": 2,
            "repeats": [0], "families": ["lifecycle"], "label_counts": {"todo": 16},
            "provenance": "p", "upstream_audit_rc": 0, "upstream_audit_stdout_tail": "",
            "upstream_audit_stderr_tail": "", "digests": [], "gaps": [],
            "audit_interpreter": "python", "corpus_options": options,
            "reader_lines_by_mode": {"choice": 2}, "reader_lines_quarantined_only": {},
            "reader_lines_malformed": 0, "reader_lines_dropped_not_ok": 0,
            "reader_lines_filtered": 0, "lines_refused_not_ok": 0,
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "inventory.md"
            write_inventory(d, out)
            return out.read_text()

    body = render(corpus_options(2, pin={**pin, "id_sets_identical": False}))
    pooled = [line for line in body.splitlines() if line.startswith("| massive_intent_all_")]
    assert len(pooled) == 2, body                       # bound table and unit/note table
    assert "| not measured (id sets not pinned) |" in pooled[0], pooled[0]
    assert "| not opened |" not in pooled[0], pooled[0]
    typed = [line for line in body.splitlines() if line.startswith("| typed_decisions |")]
    assert "| not opened |" in typed[0], typed[0]

    control = render(corpus_options(2, pin=pin))
    assert "not measured (id sets not pinned)" not in control, control
    assert "| massive_intent_all_languages | 2974 |" in control, control
    # And the published artefact still needs neither phrase from the MASSIVE rows.
    committed = (REPO / "data" / "inventory.md").read_text()
    assert "not measured (id sets not pinned)" not in committed, committed
    assert "| massive_intent_all_languages | 2974 |" in committed, committed


def test_the_committed_inventory_markdown_names_the_one_line_it_holds(tmp_path):
    """R-80 moved a shipped finding into the human artefact, so the artefact must say it.

    This test used to assert the opposite -- that the disclosure never appears in `data/inventory.md`
    -- because the guard it policed was latent: the scanner counted the shipped corpus's unclosing
    `choice` line in the per-mode table while the reader quarantined it, so `lines_outside_mode_counts`
    was empty and the prose stayed quiet. Reconciling the two passes makes the finding real and
    published, and the artefact is required to name it: which line, in which backend, on which
    line number, for what reason, and the per-mode table's own total no longer adding up on its own.
    """
    body = (REPO / "data" / "inventory.md").read_text()
    assert "outside the per-mode counts" in body, body
    assert "1 archive line(s) sit outside the per-mode counts (0 unreadable, 1 readable but " \
        "refused by the line rule the reader owns)" in body, body
    assert "jev line 269 id=lifecycle-01 (probabilities do not close to 1 within tolerance)" \
        in body, body
    assert "| choice/jev | 191 |" in body, body
    assert len(_tables(body)) == 3, [h for h, _ in _tables(body)]
    # The refused-line clause is NOT here: the shipped archive is entirely `status: "ok"`.
    assert "carried no `status` of `ok`" not in body, body


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
    for label, raw, ledger in _every_planted_shape():
        case = tmp_path / label.replace(" ", "_").replace("`", "")
        case.mkdir()
        proc = _snapshot_cli(_plant(case, [raw])[0], case / "inventory.md")
        # rc 0 is the whole claim: 1 would be a traceback and 2 would file a corpus defect as a
        # usage error, and `== 0` rules out both. A separate `!= 1` here could never fail.
        assert proc.returncode == 0, (label, proc.returncode, proc.stderr[-500:])
        assert "Traceback" not in proc.stderr, (label, proc.stderr[-500:])
        sidecar = json.loads(Path(str(case / "inventory.md") + ".json").read_text())
        # `lines_quarantined_only` is the total of every line named outside the mode counts, and
        # `lines_malformed` is one of its buckets -- the same quantity rendered twice, which
        # `assert_line_conservation` refuses to let drift. Adding the two would count the planted
        # line twice and call the artefact wrong; the line is named once, per bucket.
        named = sum(sidecar["lines_quarantined_only"].values())
        assert sidecar["lines_quarantined_only"] == ledger, (label, sidecar)
        assert named == sum(ledger.values()), (label, sidecar)
        assert len(sidecar["lines_outside_mode_counts"]) == named, (label, sidecar)
        assert sidecar["lines_malformed"] == sum(
            sidecar["lines_malformed_by_backend"].values()), (label, sidecar)
        # The refused shapes are the class this sweep used to omit entirely: counted somewhere,
        # so the identity still closes over the planted line, and named nowhere.
        assert (sidecar["lines_refused_not_ok"] == 1) == (ledger == {}), (label, sidecar)


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


def test_a_line_the_reader_refuses_before_reading_its_keys_is_not_named_unreadable(tmp_path):
    """R-75 (review M2): the ORDER of the shared rule is part of having one owner.

    Measured before this test existed: a line carrying no `id` and no `status` was filed
    `malformed_line` by the scanner, because the scanner required its `LINE_KEYS` at parse time,
    while the reader drops a non-`ok` line at `records_from_line`'s first line and never reads a key
    from it -- so it landed in `lines_dropped_not_ok` and in neither quarantine dict. The artefact
    publishes `lines_quarantined_only` and `reader_lines_quarantined_only` beside each other, and
    `test_the_conservation_identity_closes_over_a_mixed_corpus` asserts the two are equal; that
    assertion held only because every planted shape carries `status: "ok"`, which hid the whole class.

    The scanner now asks the reader's first question first, so the two dicts agree for both shapes:
    an `ok` line missing a key is malformed to both, and a refused line is malformed to neither.
    """
    from autorate.readers.feishu_zh import read_archive

    refused_and_incomplete = json.dumps(_planted_row(drop=("id", "status")))
    root, line_no = _plant(tmp_path, [refused_and_incomplete])
    d = inventory(root)
    assert d["lines_malformed"] == 0, d
    assert d["lines_quarantined_only"] == {}, d
    assert d["lines_outside_mode_counts"] == [], d
    # Counted, not lost -- and R-80 moved WHERE it is counted. The first fix left the scanner
    # consulting the `mode` of a line the reader had already declined, so this line inflated the
    # per-mode archive table (`choice/laya == 3`); it is now held in its own counter, because the
    # reader refuses a line before it reads a `mode` and the artefact must not bucket what the
    # reader never read.
    assert d["lines_by_mode_backend"]["choice/laya"] == 2, d
    assert d["lines_refused_not_ok"] == 1, d
    assert _identity(d) == d["reader_lines_read"] == 5, d

    stats = {}
    read_archive(root, stats=stats)
    assert stats["lines_dropped_not_ok"] == 1, stats
    assert stats["lines_malformed"] == 0, stats
    # The assertion the old corpus could not make: the two passes' quarantine ledgers agree.
    assert d["lines_quarantined_only"] == stats["lines_quarantined_only"] == {}, (
        d["lines_quarantined_only"], stats["lines_quarantined_only"])
    # And the two passes' refused counters are the same quantity read twice, which is what makes
    # the split above more than a relocation of the line.
    assert d["lines_refused_not_ok"] == stats["lines_dropped_not_ok"] == 1, (d, stats)
    # And the shape that IS unreadable to both still agrees, so the fix did not just move the hole.
    ok_but_no_id = json.dumps(_planted_row(drop=("id",)))
    root2, _ = _plant(tmp_path / "ok", [ok_but_no_id])
    d2 = inventory(root2)
    stats2 = {}
    read_archive(root2, stats=stats2)
    assert d2["lines_malformed"] == stats2["lines_malformed"] == 1, (d2, stats2)
    assert d2["lines_quarantined_only"] == stats2["lines_quarantined_only"], (d2, stats2)
    assert [e["error"] for e in d2["lines_outside_mode_counts"]] == \
           [e["error"] for e in stats2["quarantined"]], (d2, stats2)


def test_inventory_itself_refuses_a_pass_that_loses_a_line(monkeypatch, tmp_path):
    """R-75 (review M6): the conservation guard has to be reachable through `inventory`.

    `test_the_conservation_check_can_fire` calls the helper with literals, which proves the helper
    can refuse but says nothing about the call site: with only that test, a branch that drops a line
    without a counter would still produce an artefact, because nothing in the pipeline was shown to
    consult the identity. So this fakes exactly that defect -- a scan that forgets one line -- and
    requires `inventory()` to stop rather than publish a smaller corpus.
    """
    from autorate import inventory as inventory_module

    root, _ = _plant(tmp_path, [json.dumps(_planted_row(drop=("status",)))])
    real = inventory_module._scan_jsonl

    def losing_pass(path):
        by_mode, ids, repeats, unclosed, outside, refused, lines_read = real(path)
        for mode in list(by_mode):
            if by_mode[mode] > 1:
                by_mode[mode] -= 1          # the line is gone, and no bucket mentions it
                return by_mode, ids, repeats, unclosed, outside, refused, lines_read
        raise AssertionError("the fixture has no mode with more than one line to drop")

    monkeypatch.setattr(inventory_module, "_scan_jsonl", losing_pass)
    with pytest.raises(ArithmeticError, match="does not conserve"):
        inventory(root)
    # The unpatched pass still conserved, so the refusal came from the injected loss.
    monkeypatch.undo()
    assert _identity(inventory(root)) == inventory(root)["reader_lines_read"]


def test_write_inventory_names_the_reader_its_own_buckets_and_not_a_difference(tmp_path):
    """R-75 (review M1): `present - kept` is not `quarantined`, and the artefact said it was.

    The per-mode bullet subtracted the reader's kept-line count from the scanner's line count and
    labelled the remainder "quarantined". For a refused (`status != "ok"`) line the reader quarantines
    nothing, so the sentence accused the quarantine of a line it had declined on its own rule -- and it
    invented a number by subtraction instead of reading the two the reader already publishes.
    """
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    root, _ = _plant(dirty, [json.dumps(_planted_row(drop=("status",))),
                             json.dumps(_planted_row(response={"model": "m", "answers": {}}))])
    out = dirty / "inventory.md"
    write_inventory(inventory(root), out)
    body = out.read_text()
    # One refused line, one unreadable line: the bullet must name each disposition as itself, and the
    # two must not be netted into one "quarantined" figure.
    assert "1 refused" in body, body
    assert "1 malformed" in body, body
    assert "2 quarantined" not in body, body


def test_a_line_the_reader_drops_for_its_own_reason_is_not_the_same_as_unreadable(tmp_path):
    """The measured boundary of the shared rule, recorded so nobody "fixes" it into agreement.

    A line carrying no `status` is READABLE, so it is not `malformed_line` to either pass; and it is
    refused before its `mode` means anything, so R-80 moved it out of the per-mode table into
    `lines_refused_not_ok`, where the reader's own `lines_dropped_not_ok` already counted it. Neither
    pass loses it -- both see 5 lines -- and the labels differ on purpose: dropping a refused
    response is not the same rule as failing to parse a line. The asymmetry is real and pinned here
    rather than smoothed over, because the same two counters answering "how many choice lines are in
    the archive" is how a reader comes to believe 192 lines became 192 records.
    """
    from autorate.readers.feishu_zh import read_archive

    no_status = json.dumps(_planted_row(drop=("status",)))
    root, _ = _plant(tmp_path, [no_status], backend="jev")
    d = inventory(root)
    assert d["lines_malformed"] == 0, d
    assert d["lines_quarantined_only"] == {}, d
    assert d["lines_outside_mode_counts"] == [], d
    assert d["lines_by_mode_backend"]["choice/jev"] == 2, d      # the refused line is not bucketed
    assert d["lines_refused_not_ok"] == 1, d
    stats = {}
    read_archive(root, stats=stats)
    assert stats["lines_malformed"] == 0, stats
    assert stats["lines_dropped_not_ok"] == 1, stats
    assert _identity(d) == d["reader_lines_read"] == 5, d
    # The two passes' per-mode counts are different quantities, and the artefact names them apart:
    # `lines_by_mode_backend` counts archive lines the scanner could bucket, while
    # `reader_lines_by_mode` counts only the lines the reader turned into at least one record --
    # still LINES, not records: one `four_noul` line yields four records, and the reader's record
    # count is a third quantity, `records_kept`, returned by `read_archive(stats=...)` and NOT
    # published in the inventory artefact at all (m-2: the sentence this test replaces claimed it
    # was, and no key of that name exists in `data/inventory.md.json`).
    assert sum(d["lines_by_mode_backend"].values()) == 4, d
    assert sum(d["reader_lines_by_mode"].values()) == 4, d
    assert "records_kept" not in json.dumps(
        json.loads((REPO / "data" / "inventory.md.json").read_text())), "the artefact grew the key"


def test_the_conservation_check_can_fire():
    """The identity must be able to refuse a branch that drops a line without a counter.

    Without this control the assertion in `inventory()` is green by construction: a check that
    cannot fail is the case this project refuses to accept as evidence.
    """
    from autorate.inventory import assert_line_conservation

    assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                             lines_quarantined_only={"malformed_line": 2},
                             lines_malformed=2, lines_malformed_by_backend={"laya": 2},
                             lines_refused_not_ok=0)
    # R-80's third term, falsified on its own: everything the other two arms police is right here,
    # so only the refused line is missing. Without this arm a scanner that dropped a refused line
    # entirely would still satisfy every other term of the identity.
    with pytest.raises(ArithmeticError, match="does not conserve"):
        assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                                 lines_quarantined_only={"malformed_line": 1},
                                 lines_malformed=1, lines_malformed_by_backend={"laya": 1},
                                 lines_refused_not_ok=0)
    assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                             lines_quarantined_only={"malformed_line": 1},
                             lines_malformed=1, lines_malformed_by_backend={"laya": 1},
                             lines_refused_not_ok=1)
    with pytest.raises(ArithmeticError, match="does not conserve"):
        assert_line_conservation(lines_read=5, lines_by_mode={"choice": 3},
                                 lines_quarantined_only={"malformed_line": 2},
                                 lines_malformed=2, lines_malformed_by_backend={"laya": 2},
                                 lines_refused_not_ok=1)
    with pytest.raises(ArithmeticError, match="does not match"):
        assert_line_conservation(lines_read=4, lines_by_mode={"choice": 2},
                                 lines_quarantined_only={"malformed_line": 2},
                                 lines_malformed=1, lines_malformed_by_backend={"laya": 1},
                                 lines_refused_not_ok=0)


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


def test_the_pooled_row_takes_its_independent_count_from_the_id_set_not_the_row_count():
    """R-75 (review M3): "measured, not asserted" was said of a figure nothing had measured.

    Both MASSIVE rows used to fill `n_independent` from `files[].rows` -- a ROW count. That 2,974 rows
    and 2,974 independent cases are the same number is the whole translation claim, so the claim now
    reads a field that was produced by comparing id sets across shards (`distinct_ids`,
    `id_sets_identical`), and the two figures can disagree. If a future pin adds a 52nd shard with new
    utterances, `n_independent` moves while `rows` does not, and the pooled row stops claiming a
    sample it cannot support rather than quietly reusing the old number.
    """
    from autorate.inventory import corpus_options, massive_pin

    pin = massive_pin()
    assert pin["id_sets_identical"] is True, pin["provenance"].get("id_sets")
    opts = {o["id"]: o for o in corpus_options(64, pin=pin)}
    pooled, per_lang = opts["massive_intent_all_languages"], opts["massive_intent_per_language"]
    assert pooled["n_independent"] == pin["distinct_ids"]
    assert pooled["n_independent"] != pooled["n_rows"], "rows are not a sample"
    assert pooled["n_shards"] == pin["n_files"]
    assert per_lang["n_independent"] == pin["files"][0]["rows"]
    # The arithmetic that ties them: rows = shards x independent, one equation, three fields.
    assert pooled["n_rows"] == pooled["n_shards"] * pooled["n_independent"], pooled

    not_identical = {**pin, "id_sets_identical": False}
    opts2 = {o["id"]: o for o in corpus_options(64, pin=not_identical)}
    assert opts2["massive_intent_all_languages"]["n_independent"] is None, opts2
    assert "cannot" in opts2["massive_intent_all_languages"]["basis"].lower(), opts2


def test_the_pin_refuses_a_declared_field_its_entries_do_not_sum_to(tmp_path):
    """The loader polices every declared total, including the two that describe id sets.

    `distinct_row_counts` and `distinct_ids` are claims ABOUT `files`, so a pin that keeps one field
    while an entry changes must refuse rather than publish the stale aggregate (review M3's minor).
    """
    from autorate.inventory import massive_pin

    good = massive_pin()
    path = tmp_path / "massive_provenance.json"
    for key, mutate in (
        ("distinct_row_counts", lambda p: p.update(distinct_row_counts=[1, 2974])),
        ("distinct_ids", lambda p: p.update(distinct_ids=p["distinct_ids"] + 1)),
    ):
        broken = json.loads(json.dumps(good))
        mutate(broken)
        path.write_text(json.dumps(broken))
        with pytest.raises(ArithmeticError, match=key):
            massive_pin(path)


def test_a_missing_or_corrupt_pin_refuses_as_drift_not_as_a_usage_error(monkeypatch, tmp_path,
                                                                         capsys):
    """R-75 (review M5): a repository data defect must not be filed under the operator's mistake.

    Measured before the fix: truncating `data/massive_provenance.json` made `autorate snapshot` exit 2
    with `JSONDecodeError` (a `ValueError`, which `main` maps to EXIT_USAGE), and deleting it made the
    same command exit 0 while the artefact's MASSIVE rows read "not opened" -- one case blamed the
    person running the command, the other reported a corpus finding that was not a finding. Both are
    "this checkout cannot re-derive its own published numbers", which is exactly what EXIT_DRIFT means
    here, and `main` already maps `ArithmeticError` to it.
    """
    from autorate import inventory as inv_module
    from autorate.cli import EXIT_DRIFT, EXIT_USAGE, main

    root = _tiny_corpus(tmp_path / "corpus", n_ids=2)
    out = str(tmp_path / "inventory.md")

    # m-3: `_root()` prefers `AUTORATE_FEISHU_ROOT` over an explicit `--root`, so in a legitimately
    # set environment -- this project's own briefs recommend setting the variable to a nonexistent
    # path to exercise the corpus-less lane -- this test measured `assert 2 == 4`: `_require_root`
    # raised `UsageError` before the pin was ever read. The refusal under test belongs to the PIN,
    # so the environment must not be allowed to answer first. The arm below is the interference,
    # run rather than described: with the variable pointing at a corpus that is not there, the same
    # call exits 2 whatever the pin says.
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus"))
    assert main(["snapshot", "--root", str(root), "--out", out]) == EXIT_USAGE
    capsys.readouterr()
    monkeypatch.delenv("AUTORATE_FEISHU_ROOT", raising=False)

    monkeypatch.setattr(inv_module, "MASSIVE_PIN_PATH", tmp_path / "absent.json")
    assert main(["snapshot", "--root", str(root), "--out", out]) == EXIT_DRIFT
    err = capsys.readouterr().err
    assert "Traceback" not in err, err
    assert "massive_provenance.json is missing or unreadable" in err, err

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text('{"files": [')
    monkeypatch.setattr(inv_module, "MASSIVE_PIN_PATH", corrupt)
    assert main(["snapshot", "--root", str(root), "--out", out]) == EXIT_DRIFT
    err = capsys.readouterr().err
    assert "Traceback" not in err, err
    assert "not readable JSON" in err, err


def test_a_pin_that_is_valid_json_but_not_a_pin_refuses_instead_of_crashing(tmp_path):
    """R-79 (re-review MA-1): three shapes of `data/massive_provenance.json` exited 1.

    Measured at `5ec8639`: `null`, `[]` and a pin whose entries omit `rows` each raised
    `AttributeError` / `KeyError` out of `massive_pin` -- and neither class is in `main`'s map, so
    the process died with a traceback and exit 1, outside the 0/2/3/4 contract, on a file the
    repository tracks. A malformed pin is exactly the case `EXIT_DRIFT` exists for.
    """
    from autorate.inventory import massive_pin

    good = massive_pin()
    path = tmp_path / "massive_provenance.json"
    entries = good["files"]
    no_rows = {k: v for k, v in entries[0].items() if k != "rows"}
    broken_entry = json.dumps({**good, "files": [no_rows], "n_files": 1, "rows_total": 0,
                               "bytes_total": entries[0]["bytes"], "distinct_row_counts": [0],
                               "distinct_ids": 0, "id_sets_identical": False})
    for label, body in (
        ("json null", "null"),
        ("json list", "[]"),
        ("json string", '"a pin is not a string"'),
        ("entry without `rows`", broken_entry),
    ):
        path.write_text(body)
        try:
            massive_pin(path)
        except ArithmeticError:
            continue                       # the refusal this contract reserves for a bad pin
        raise AssertionError("%s was accepted as a pin" % label)


def test_each_refused_pin_shape_reaches_the_command_as_drift(monkeypatch, tmp_path, capsys):
    """R-82's exit-code half: the refusal has to survive the trip through `main`.

    `ArithmeticError` from the loader is only the middle of the claim. The published contract is
    about the process, so each shape that `massive_pin` now refuses must reach `autorate snapshot`
    as EXIT_DRIFT with a one-line message -- and must not be the `AttributeError`/`KeyError` that
    `main` has no clause for, which is what made the same file exit 1 with a traceback.
    """
    from autorate import inventory as inv_module
    from autorate.cli import EXIT_DRIFT, main

    good = inv_module.massive_pin()
    root = _tiny_corpus(tmp_path / "corpus", n_ids=2)
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(root))
    bodies = {
        "json null": "null",
        "json list": "[1, 2, 3]",
        "entry not an object": json.dumps({**good, "files": ["test/aa.json.gz"]}),
        "entry without `rows`": json.dumps(
            {**good, "files": [{k: v for k, v in f.items() if k != "rows"}
                               for f in good["files"]]}),
        "entry without `bytes`": json.dumps(
            {**good, "files": [{k: v for k, v in f.items() if k != "bytes"}
                               for f in good["files"]]}),
        "entry without `path`": json.dumps(
            {**good, "files": [{k: v for k, v in f.items() if k != "path"}
                               for f in good["files"]]}),
        "truncated digest": json.dumps(
            {**good, "files": [{**f, "sha256": "deadbeef"} for f in good["files"]]}),
    }
    for label, body in bodies.items():
        path = tmp_path / ("pin_%s.json" % label.replace(" ", "_").replace("`", ""))
        path.write_text(body)
        monkeypatch.setattr(inv_module, "MASSIVE_PIN_PATH", path)
        assert main(["snapshot", "--root", str(root),
                     "--out", str(tmp_path / "out" / "inventory.md")]) == EXIT_DRIFT, label
        err = capsys.readouterr().err
        assert "Traceback" not in err, (label, err)
        assert err.startswith("INVARIANT: ArithmeticError:"), (label, err)
        assert "data/massive_provenance.json" in err, (label, err)


def test_a_corpus_line_named_like_the_internal_bucket_does_not_select_the_exit_code(tmp_path):
    """R-79 (re-review MA-6): `mode: "malformed_line"` in the archive made ordinary content exit 4.

    The scanner keyed its ledger with the mode string for an unbucketable mode and with
    `MALFORMED_LINE` for an unreadable one, so a corpus whose `mode` column literally contained
    that word collided the two buckets, `assert_line_conservation` refused, and the published
    snapshot command returned DRIFT for a corpus that is merely strange. Bucket keys are namespaced
    on collision, which leaves the shipped corpus's `{'choice': 1}` untouched.
    """
    planted = json.dumps(_planted_row(mode="malformed_line"))
    root, _ = _plant(tmp_path, [planted])
    d = inventory(root)                       # must not raise
    assert d["lines_malformed"] == 0, d
    assert d["lines_quarantined_only"] == {"mode:malformed_line": 1}, d
    assert d["lines_outside_mode_counts"][0]["reason"] == \
        "mode 'malformed_line' is not readable by this reader", d
    assert _identity(d) == d["reader_lines_read"] == 5, d

    root2, _ = _plant(tmp_path / "two", [planted, _UNBUCKETABLE_MODE])
    d2 = inventory(root2)
    assert d2["lines_quarantined_only"] == {"mode:malformed_line": 1, "ranked": 1}, d2
