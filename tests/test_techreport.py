"""Plan D Task 4: `docs/REPORT.md` is generated prose, so every figure in it has a producer.

The rule these rows exist to keep is the one the whole repository is built on: a document that contains
a typed-in number is a document that can lie. `report.render_resplit` and `report.render_slices` are the
shape the renderer is expected to follow -- prose assembled out of the artefact's own values, so a changed
value changes the sentence and nothing else does.

Every row says in its docstring what change reddens it, because a test that cannot fail is a second copy
of the prose it claims to police.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Same convention the sibling suites use: the package and the shared test helpers are both importable
# from a test module without touching an installed path.
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))


def _inputs():
    """The renderer's whole input, assembled the way `cli._render_techreport_doc` assembles it.

    Deliberately not a shortcut around the CLI's call: the freeze and the two tables the renderer is
    handed are read from the owners that publish them, so a document deleted from `PUBLISHED_DOCS` moves
    this fixture and the gate together rather than letting the test remember a publication list of its
    own (R-168).
    """
    from autorate import cli, report, techreport
    from autorate.protocol import load_protocol

    inv, _source = cli._inventory()
    records = report.load_records(Path(report.RECORDS))
    protocol = report.load_published(cli.PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol)
    return techreport.load_inputs(protocol, inv, records,
                                  tuple(path for path, _ in cli.PUBLISHED_DOCS),
                                  cli.EXIT_CODE_MEANINGS)


# ---------------------------------------------------------------- 1. re-rendering is byte-stable

def test_rendering_the_report_twice_gives_the_same_bytes(tmp_path):
    """Red when the renderer reads anything that is not a committed artefact.

    A clock, `Path.home()`, an unordered set rendered straight into a line, or the machine's locale would
    all make two calls in one process differ -- and, worse, would make `verify`'s byte comparison
    unreproducible on the one machine that matters, the CI runner that never saw this disk.
    """
    from autorate import techreport

    a, b = techreport.render_report(_inputs()), techreport.render_report(_inputs())
    assert a == b, "two renders of the same artefacts disagree"
    first, second = tmp_path / "a.md", tmp_path / "b.md"
    first.write_text(a)
    second.write_text(b)
    assert first.read_bytes() == second.read_bytes(), "the document is not stable through a write"
    assert a.endswith("\n") and not a.endswith("\n\n"), "one trailing newline, never two"


# ---------------------------------------------------------------- 2. every figure is its artefact's

def test_every_published_figure_appears_with_the_value_its_artefact_carries():
    """Red when a headline number is dropped, re-rounded, or remembered instead of read.

    Nothing in this row is a literal: every expected string is taken from the artefact the report is
    supposed to quote, so an artefact whose value moves moves the expectation with it. The certificate
    summaries are the strongest of these -- the whole verbatim sentence the certifier prints, bound
    digits and all -- and the digest rows are full-precision hex, so a report that quoted a truncated or
    retyped digest fails on the same assertion.
    """
    from autorate import techreport

    inputs = _inputs()
    text = techreport.render_report(inputs)

    for path, cert in inputs.certificates:
        assert str(path) in text, path
        assert cert.summary() in text, path

    label, records_path, severity, direction = inputs.severity
    assert severity.summary() in text, label
    assert records_path in text, label
    assert direction in text, label

    for row in inputs.protocol.claims:
        assert row["criterion"] in text, row["id"]
        assert row["measurement"] in text, row["id"]
        assert "`%s`" % row["status"] in text, row["id"]

    for line in inputs.protocol.known_limits:
        assert line in text, line

    corpus = inputs.protocol.corpus
    assert corpus["records_digest"] in text
    assert corpus["inventory_digest"] in text
    pinned = corpus["pinned_builds"]["massive_intent"]
    assert str(pinned["rows_total"]) in text
    assert str(pinned["distinct_ids"]) in text
    assert pinned["revision"] in text

    for row in inputs.slices["inputs"]:
        assert row["digest"] in text, row["path"]
        assert str(row["rows"]) in text, row["path"]

    for task in inputs.resplit["tasks"]:
        assert str(task["label"]) in text

    for row in inputs.ledger:
        if row["id"] in techreport.RELATED_WORK:
            assert row["opened"] in text, row["id"]
