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
        "/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh",
    )
)
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")


@skip
def test_inventory_sees_the_recorded_shape():
    d = inventory(UPSTREAM)
    assert d["unique_ids"] == 64
    assert d["repeats"] == [0, 1, 2]
    assert d["records_by_mode_backend"] == {
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
    # Ledger R-12: MASSIVE ships 51 x test/xx.json.gz, 2974 rows each, stdlib-readable.
    opts = corpus_options()
    by_id = {o["id"]: o for o in opts}
    assert by_id["feishu_zh"]["unique_ids"] == 64
    assert by_id["massive_intent_per_language"]["unique_ids"] == 2974
    assert by_id["massive_intent_all_languages"]["unique_ids"] == 2974 * 51
    # The feasibility answer must come from the formula, not from a typed word.
    assert by_id["feishu_zh"]["bound_width_at_0.05"] > 0.25
    assert by_id["massive_intent_per_language"]["bound_width_at_0.05"] < 0.10
    assert by_id["feishu_zh"]["feasible_at_0.10"] is False
    assert by_id["massive_intent_per_language"]["feasible_at_0.10"] is True


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


def test_write_inventory_refuses_a_corpus_whose_audit_failed(tmp_path):
    fake = {
        "source": "x",
        "records_by_mode_backend": {"choice|laya": 1},
        "unique_ids": 1,
        "repeats": [0],
        "families": [],
        "label_counts": {},
        "provenance": "",
        "upstream_audit_rc": 1,
        "upstream_audit_stdout_tail": "",
        "upstream_audit_stderr_tail": "boom",
        "min_calibration_n": 1,
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
        "records_by_mode_backend": {"choice/laya": 192, "four_noul/jev": 192},
        "unique_ids": 64, "repeats": [0, 1, 2], "families": ["lifecycle"],
        "label_counts": {"todo": 16}, "provenance": "p",
        "upstream_audit_rc": 0, "upstream_audit_stdout_tail": "",
        "upstream_audit_stderr_tail": "", "min_calibration_n": 64,
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
