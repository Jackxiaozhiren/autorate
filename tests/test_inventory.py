"""Task 3: what offline, labelled, per-case decision data actually exists, and whether n supports a bound.

Two things this suite refuses to do: certify on a corpus too small to bound, and
silently write into the vendored upstream tree it reads from.
"""
import json
import sys
from pathlib import Path

import pytest

from autorate.inventory import corpus_options, inventory, n_feasible, write_inventory

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
    """
    opts = {o["id"]: o for o in corpus_options(64)}
    one, all_langs = opts["massive_intent_per_language"], opts["massive_intent_all_languages"]
    assert opts["feishu_zh"]["n_independent"] == 64, opts["feishu_zh"]
    assert one["n_independent"] == one["n_rows"] == 2974
    assert all_langs["n_rows"] == 2974 * 51
    assert all_langs["n_independent"] == 2974, "translations must not inflate the sample"
    assert all_langs["bound_width_at_0.05"] == one["bound_width_at_0.05"]
    assert "3 of 51" in all_langs["basis"], all_langs["basis"]
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
        by_mode, ids, reps, unclosed = _scan_jsonl(p)
    assert by_mode == {"choice": 1} and unclosed == []


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
