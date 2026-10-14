"""Plan D Task 4: `docs/REPORT.md` is generated prose, so every figure in it has a producer.

The rule these rows exist to keep is the one the whole repository is built on: a document that contains
a typed-in number is a document that can lie. `report.render_resplit` and `report.render_slices` are the
shape the renderer is expected to follow -- prose assembled out of the artefact's own values, so a changed
value changes the sentence and nothing else does.

Every row says in its docstring what change reddens it, because a test that cannot fail is a second copy
of the prose it claims to police.
"""
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
# Same convention the sibling suites use: the package and the shared test helpers are both importable
# from a test module without touching an installed path.
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))


@pytest.fixture(autouse=True)
def in_repo(monkeypatch):
    """Run every row from the repository root, the way `verify` does.

    The renderer's inputs are resolved by repository-relative path (`cli._inventory` reads the committed
    snapshot, `report.load_records` the records file), so a row executed from anywhere else would be
    measuring the working directory instead of the artefacts.
    """
    monkeypatch.chdir(REPO)


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
    from autorate.report import SEVERITY_CERTS

    inputs = _inputs()
    text = techreport.render_report(inputs)

    for path, cert in inputs.certificates:
        assert str(path) in text, path
        assert cert.summary() in text, path

    label, _records, severity, direction = inputs.severity
    assert severity.summary() in text, label
    # The records file is named by the path `report.SEVERITY_CERTS` declares, not by the record objects
    # `published_severity()` hands the renderer: a bullet that prints their repr quotes a population
    # instead of naming the file the reader has to re-derive it from.
    assert SEVERITY_CERTS[label][0] in text, label
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
        # `cited_ids()`, not `RELATED_WORK`: the table is a tuple of (group, rows) pairs, so testing a bare
        # id against it compares a string with tuples and is never true -- a vacuous arm that would have
        # let every quoted row's date go unchecked while still printing green.
        if row["id"] in techreport.cited_ids():
            assert row["opened"] in text, row["id"]


# ---------------------------------------------------------------- 2b. no value the artefact does not carry

def test_the_rendered_text_prints_no_unfilled_placeholder_and_no_missing_value():
    """Red when a builder prints what a format call or a missing figure left behind.

    `%s` on the page means a line was written as a template and never substituted -- the pinned-build
    sentence did exactly that -- and `None` means the sentence was kept around a figure the artefact does
    not carry. Both are the same defect the brief forbids in a generated document: prose describing the
    renderer's own accident instead of the artefact. The rule is to drop the clause, not to print its
    absence, so neither token may appear anywhere in the text.
    """
    from autorate import techreport

    text = techreport.render_report(_inputs())

    unfilled = [m.group(0) for m in re.finditer("%" + "[sdrfx]", text)]
    assert unfilled == [], "unfilled format specifiers reached the document: %s" % unfilled
    absent = [line for line in text.splitlines()
              if re.search(r"\bNone\b|\bnan\b|\bNaN\b|\binf\b", line)]
    assert absent == [], "a missing value was printed instead of the sentence being dropped: %s" % absent

    # The guard has to be able to bite: the parked renderer shipped both defects, so each pattern is
    # checked against the exact shape it exists to catch.
    assert re.search("%" + "[sdrfx]", "Read from `%s` through the pin"), "the placeholder scan is vacuous"
    assert re.search(r"\bNone\b", "published `qhat`=" + "None"), "the missing-value scan is vacuous"


# ---------------------------------------------------------------- 3. no citation the ledger does not back

# A related-work bullet always begins with its row id in backticks and then its role in parentheses; that
# shape is what the renderer emits and the only place the document puts an id in a citation slot. The
# second pattern is the loose one -- any backticked token shaped like a ledger id and carrying the ledger's
# two-or-more-hyphen signature -- so an id hand-written into a prose literal anywhere in the document is
# named even if it never reaches a bullet.
_CITATION_BULLET = re.compile(r"^- `([a-z0-9][a-z0-9-]*)` \(", re.M)
_ID_TOKEN = re.compile(r"`([a-z0-9][a-z0-9-]*)`")


def _related_work(text: str) -> str:
    return text[text.index("## Related work"):]


def test_the_report_carries_no_claim_id_the_ledger_does_not_verify():
    """Red when a sentence about somebody else's work outlives, or never had, its ledger row.

    Three arms, for three ways this happens. (a) A bullet leader `docs/VERIFICATION.md` does not carry --
    a citation written into a renderer's string, which `cited_ids()` cannot see because it only knows the
    table. (b) A bullet whose row exists but has left `verified`: the evidence was withdrawn and the
    sentence stayed. (c) An id-shaped token anywhere in the document -- the mechanism prose, the refusal
    prose -- that the ledger never opened. The renderer's `_validate_citations` refuses (a) and (b) before
    a single byte is written, so this row checks both the emitted text and that the refusal actually fires
    when a cited row is deleted from, or withdrawn in, the ledger it was read from.
    """
    from autorate import techreport
    from autorate.report import PublishedArtefactUnavailable

    inputs = _inputs()
    text = techreport.render_report(inputs)
    status_by_id = {row["id"]: row["status"] for row in inputs.ledger}

    leaders = _CITATION_BULLET.findall(_related_work(text))
    assert len(leaders) == len(set(leaders)) == len(techreport.cited_ids()), leaders
    assert set(leaders) == set(techreport.cited_ids()), set(leaders) ^ set(techreport.cited_ids())
    assert all(row_id in status_by_id for row_id in leaders), \
        [row_id for row_id in leaders if row_id not in status_by_id]
    assert all(status_by_id[row_id] == "verified" for row_id in leaders), \
        [(row_id, status_by_id[row_id]) for row_id in leaders if status_by_id[row_id] != "verified"]

    # (c): the loose scan over the whole document, and the ids the closing paragraphs name.
    stray = sorted(token for token in set(_ID_TOKEN.findall(text))
                   if token.count("-") >= 2 and token not in status_by_id)
    assert stray == [], "cited ids the ledger never opened: %s" % stray
    for row_id in techreport.SEVERITY_PRIOR_ART:
        assert status_by_id.get(row_id) == "verified", row_id

    # The guard is not decorative: a token of that shape is exactly what it rejects.
    assert "no-such-ledger-row-here" not in status_by_id
    assert _ID_TOKEN.search("cited `no-such-ledger-row-here` above")

    victim = techreport.cited_ids()[0]
    with pytest.raises(PublishedArtefactUnavailable, match=re.escape(victim)):
        techreport.render_report(replace(
            inputs, ledger=tuple(row for row in inputs.ledger if row["id"] != victim)))
    with pytest.raises(PublishedArtefactUnavailable, match=re.escape(victim)):
        techreport.render_report(replace(
            inputs, ledger=tuple({**row, "status": "withdrawn"} if row["id"] == victim else row
                                  for row in inputs.ledger)))


# ---------------------------------------------------------------- 4. the path guard over the text

def test_the_absolute_machine_path_guard_runs_over_the_rendered_text():
    """Red the day the report prints a path that only exists on one machine.

    The document quotes corpus paths, digests and inventory basis sentences, so this is where an absolute
    path would actually appear -- not in the source, which the tracked-tree scan already polices. The
    pattern and its deliberate `/tmp` exemption are `tests/test_cli.py`'s, imported rather than recopied:
    a second copy would drift, and the exemption there is reasoned (CI writes its logs to `/tmp`, honest
    prose says `/tmp/falsify`), so this row inherits it instead of re-litigating it.
    """
    from autorate import techreport
    from test_cli import MACHINE_PATH_RX

    text = techreport.render_report(_inputs())
    home = str(Path.home())
    hits = [(number, line) for number, line in enumerate(text.splitlines(), 1)
            if MACHINE_PATH_RX.search(line) or home in line]
    assert hits == [], "absolute machine path in the rendered document: %s" % hits

    # Built from pieces so this file does not become the offender it is looking for.
    shapes = ("/" + "Users/someone/laya/research/benchmarks/feishu_zh",
              "/" + "home/someone/laya/research/benchmarks/feishu_zh",
              "/" + "var/folders/aa/bbbbcc/T/pytest-of-someone/docs/REPORT.md")
    for shape in shapes:
        assert MACHINE_PATH_RX.search(text + "\nthe corpus lives in %s\n" % shape), shape
    # ...and `/tmp` stays out of the pattern on purpose, so this row cannot be satisfied by a wider net.
    assert not MACHINE_PATH_RX.search("/" + "tmp/laya/research/feishu_zh")


# ---------------------------------------------------------------- 5. one number, its own sentences

def _swap_certificate(inputs, path, mutate):
    """`inputs` with one certificate replaced by `mutate(cert)`, everything else the same bytes."""
    rows = tuple((row_path, mutate(cert) if row_path == path else cert)
                 for row_path, cert in inputs.certificates)
    return replace(inputs, certificates=rows)


def test_perturbing_one_number_moves_exactly_the_sentences_that_quote_it():
    """Red for a report that remembered its figures instead of reading them -- or leaked one sideways.

    `n_eval` of one published set certificate is incremented by one. The claim is in two halves, and the
    second is the one a typed-in document cannot survive: some line must change (a renderer that printed a
    hard-coded sentence would change nothing), and every line that changes must be a line that names that
    artefact. Nothing quoting a different certificate, a different gate, or the freeze may move, so a
    figure shared by two owners, or a paragraph the renderer memorised, reddens this row.
    """
    from autorate import techreport

    inputs = _inputs()
    before = techreport.render_report(inputs)
    path, cert = inputs.certificates[0]
    moved = cert.n_eval + 1
    assert str(cert.n_eval) in before, "the control never quoted the number being perturbed"

    after = techreport.render_report(_swap_certificate(inputs, path, lambda c: replace(c, n_eval=moved)))
    before_lines, after_lines = before.splitlines(), after.splitlines()
    assert len(before_lines) == len(after_lines), \
        "one value moved and the document changed shape: %d lines became %d" % (
            len(before_lines), len(after_lines))

    changed = [(a, b) for a, b in zip(before_lines, after_lines) if a != b]
    assert changed, "a certificate's own number changed and no sentence did"
    for a, b in changed:
        assert str(path) in a, "a line that never named the artefact moved: %r" % a
        assert str(cert.n_eval) in a or str(moved) in b, a

    # Confined: every line that does not name this artefact is byte-identical.
    assert [b for a, b in zip(before_lines, after_lines) if str(path) not in a] == \
        [a for a in before_lines if str(path) not in a]
    # ...and the other published certificates kept their own numbers.
    for other_path, other in inputs.certificates[1:]:
        assert str(other.n_eval) in after, other_path


# ---------------------------------------------------------------- 6. the published arm, and its counts

_READS_LINE = re.compile(
    r"^- artefacts this document reads: (\d+) set certificates, (\d+) ordinal one, (\d+) resplit tasks,"
    r" (\d+) slice rows declared as inputs, (\d+) inventory gaps, (\d+) ledger rows of which (\d+) are"
    r" quoted here$", re.M)
_DOCS_LINE = re.compile(
    r"^- documents `verify` byte-compares \(`cli\.PUBLISHED_DOCS`, (\d+) of them, this file among"
    r" them\): (.*)$", re.M)


def test_the_report_is_published_and_its_own_counts_are_its_artefacts_counts():
    """Red when the document leaves the gate, drifts from a fresh render, or miscounts what it read.

    Four things a reader of `docs/REPORT.md` is told and this repository has to be able to prove: it is in
    `cli.PUBLISHED_DOCS` (so `verify` byte-compares it), the committed bytes ARE a fresh render of the
    artefacts, the CLI's own render site produces the same text the renderer does, and every count the
    document declares about itself -- artefacts read, ledger rows, quoted rows, published documents -- is
    the count the artefacts carry. The expectations are computed here from the tables and files, never
    typed: a certificate added to `report.CERTS`, a ledger row opened, or a document published moves the
    document and this row together, while a hand-kept integer in either of them reddens one of them.
    """
    from autorate import cli, report, techreport
    from autorate.protocol import published_certificates

    inputs = _inputs()
    text = techreport.render_report(inputs)

    assert cli.REPORT_MD in {path for path, _render in cli.PUBLISHED_DOCS}, cli.PUBLISHED_DOCS
    committed = REPO / techreport.REPORT_MD
    assert committed.is_file(), "%s has not been emitted" % techreport.REPORT_MD
    assert committed.read_text() == text, "the committed document is not what the artefacts render"
    inv, _source = cli._inventory()
    records = report.load_records(Path(report.RECORDS))
    assert cli._render_techreport_doc(inv, records) == text, "the gate's render site disagrees with itself"

    reads = _READS_LINE.search(text)
    assert reads, "the document no longer declares what it read"
    assert [int(g) for g in reads.groups()] == [
        len(published_certificates()), len(report.SEVERITY_CERTS), len(inputs.resplit["tasks"]),
        len(inputs.slices["inputs"]), len(inputs.inventory["gaps"]), len(inputs.ledger),
        len(techreport.cited_ids())], reads.groups()

    docs = _DOCS_LINE.search(text)
    assert docs, "the document no longer declares the published table"
    assert int(docs.group(1)) == len(cli.PUBLISHED_DOCS), docs.group(1)
    assert docs.group(2) == ", ".join("`%s`" % path for path, _render in cli.PUBLISHED_DOCS), docs.group(2)


# ---------------------------------------------------------------- 7. the ledger read is the table's

def test_a_ledger_this_checkout_cannot_supply_is_the_tables_failure_and_not_the_operators(tmp_path):
    """Red when the report's read of `docs/VERIFICATION.md` answers a filesystem failure as usage.

    Three shapes of the same misattribution, all on a path no argument selected -- `techreport.LEDGER_MD`
    names it. Nothing at the path, a row whose tail this parser cannot read, and a file that holds no
    ledger rows at all: each has to come back as the named drift refusal, because `cli.main` maps a bare
    `OSError` and `ValueError` onto exit 2 and would tell the operator about a file they never typed. The
    two parsed arms were built this way from the start; the absent one was a `FileNotFoundError` until the
    row was written, which is the class the published-artefact contract exists to close.
    """
    from autorate import techreport
    from autorate.report import PublishedArtefactUnavailable

    absent = tmp_path / "docs" / "VERIFICATION.md"
    with pytest.raises(PublishedArtefactUnavailable) as missing:
        techreport.read_ledger(absent)
    assert "techreport.LEDGER_MD" in str(missing.value), str(missing.value)
    assert "is not in this checkout" in str(missing.value), str(missing.value)

    unreadable = tmp_path / "tail.md"
    unreadable.write_text("| id=laya-star-count | a claim with no tail\n", encoding="utf-8")
    with pytest.raises(PublishedArtefactUnavailable, match="cannot read"):
        techreport.read_ledger(unreadable)

    empty = tmp_path / "empty.md"
    empty.write_text("# a document with no ledger rows\n", encoding="utf-8")
    with pytest.raises(PublishedArtefactUnavailable, match="no ledger rows"):
        techreport.read_ledger(empty)
