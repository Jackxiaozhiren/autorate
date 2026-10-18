"""Every citation is either opened at its primary source or deleted. No third state."""
import ast
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[1] / "docs" / "VERIFICATION.md"
ALLOWED = {"verified", "withdrawn"}

# Two deliberate deviations from the plan's pattern, both strength-preserving.
#
# (1) The plan writes the id class as `[a-z0-9]+`, which cannot match a hyphenated id
#     (`id=mapie-crc-disclaimer` stops at `mapie`, so the `\s*\|` that follows never matches). Every
#     id in this ledger is hyphenated because the ids name spec §17 rows, so the plan's own example
#     row is invisible to the plan's own gate and `test_no_row_is_left_unverified_or_unknown` would
#     pass on a ledger full of unresolved citations. The class is widened, never narrowed: any id the
#     plan's pattern accepted still matches.
#
# (2) Membership is keyed on the ROW MARKER (`| id=`), never on `status:`. Keying coverage on the
#     field whose existence is on trial lets a row that omits that field hide from every assertion in
#     this file: `| id=x | claim | https://u | 2026-09-30 |` with no status parsed as no row at all,
#     so the gate stayed green on an unresolved citation (review finding I-1). `ID` below is used only
#     to report a row the id pattern cannot read; the tests themselves iterate `ledger_rows()`, whose
#     only requirement is the marker.
ID = re.compile(r"^\|\s*id=(?P<id>[a-z0-9][a-z0-9-]*)\s*\|")
STATUS = re.compile(r"\bstatus:\s*(?P<status>\w+)")
ROW_START = "| id="
ROW_ANY = re.compile(r"^\s*\|\s*id=")   # review residual: `|id=x` must not escape

# (3) The census. Spec §17 publishes "N rows: V verified, W withdrawn"; until now no code produced or
#     checked any count, so a later-appended row made §17 silently wrong with CI green (review finding
#     I-2). The three constants below are the ledger's only published count: the test counts the rows,
#     prints the line §17 quotes verbatim, and asserts these numbers. Appending or re-status-ing a row
#     is a red run until the constants and the §17 sentence move together with it — the assertion is
#     updated with the row that motivated it, never loosened to absorb a drift.
CENSUS_ROWS = 46
CENSUS_VERIFIED = 40
CENSUS_WITHDRAWN = 6


def ledger_rows(text: str) -> list[str]:
    """Every ledger row in the file, found by its marker alone."""
    return [line for line in text.splitlines() if ROW_ANY.match(line)]


def row_id(line: str) -> str:
    """The id read straight off the marker, so a row whose id the pattern cannot parse still has a
    name in the failure message instead of dropping out of the gate."""
    return line.lstrip()[len(ROW_START):].split("|")[0].strip()


def row_status(line: str) -> str:
    match = STATUS.search(line)
    return match.group("status") if match else "<no status>"


def test_ledger_exists_and_has_rows():
    assert DOC.exists(), "docs/VERIFICATION.md missing"
    assert ledger_rows(DOC.read_text()), "ledger has no rows"


def test_no_row_is_left_unverified_or_unknown():
    bad = {row_id(line): row_status(line) for line in ledger_rows(DOC.read_text())
           if row_status(line) not in ALLOWED}
    assert not bad, f"unresolved citations: {bad}"


def test_every_verified_row_carries_url_and_date():
    for line in ledger_rows(DOC.read_text()):
        if row_status(line) == "verified":
            assert "https://" in line, line
            assert re.search(r"20\d\d-\d\d-\d\d", line), line


def test_withdrawn_rows_say_what_replaced_them():
    for line in ledger_rows(DOC.read_text()):
        if row_status(line) == "withdrawn":
            assert "replaced:" in line or "dropped:" in line, line


def test_ledger_census_matches_the_published_counts():
    rows = ledger_rows(DOC.read_text())
    statuses = [row_status(line) for line in rows]
    verified = statuses.count("verified")
    withdrawn = statuses.count("withdrawn")
    emitted = f"ledger census: {len(rows)} rows: {verified} verified, {withdrawn} withdrawn"
    print(emitted)
    assert len(rows) == CENSUS_ROWS, f"{emitted} — move the constants and spec §17 with the row"
    assert verified == CENSUS_VERIFIED, f"{emitted} — move the constants and spec §17 with the row"
    assert withdrawn == CENSUS_WITHDRAWN, f"{emitted} — move the constants and spec §17 with the row"


def test_gate_sees_every_row_it_checks():
    # Falsifiability of the gate itself, in both directions. A table row that carries a status but
    # has no `| id=` marker would be skipped by every assertion above; a marker row whose id the
    # `ID` pattern cannot read would be reported without a name. Either is a way for an unresolved
    # citation to survive a green run.
    text = DOC.read_text()
    unmarked = [
        line
        for line in text.splitlines()
        if line.lstrip().startswith("|") and STATUS.search(line) and not line.lstrip().startswith(ROW_START)
    ]
    unreadable = [line for line in ledger_rows(text) if not ID.match(line.lstrip())]
    assert not unmarked, f"table rows carrying a status but no `| id=` marker: {unmarked}"
    assert not unreadable, f"rows carrying the marker whose id the gate cannot read: {unreadable}"


# ---------------------------------------------------------------- spec agreement (anti-clobber)
#
# Commit e386c08 replaced the spec file from a second working copy of the same document and
# silently reverted every narrowing Task 2 had made: the emitted census line vanished from
# §17, the withdrawn KIGEL acronym and the invented AISTATS 2023 venue came back, and the
# machine-local private path returned. CI stayed green throughout, because nothing in this
# file read the spec. These assertions are the cheapest thing that would have reddened it.

SPEC = Path(__file__).resolve().parents[1] / "docs" / "superpowers" / "specs" / \
    "2026-09-29-certified-decision-gate-design.md"


def _spec_text() -> str:
    assert SPEC.exists(), "the spec the ledger is supposed to back is missing: %s" % SPEC
    return SPEC.read_text()


def test_spec_quotes_the_census_line_the_gate_emits():
    emitted = "ledger census: %d rows: %d verified, %d withdrawn" % (
        CENSUS_ROWS, CENSUS_VERIFIED, CENSUS_WITHDRAWN)
    assert emitted in _spec_text(), (
        "spec §17 no longer quotes the line this gate prints -- a spec edit has diverged from "
        "the ledger (this is how e386c08 reverted Task 2)")


def test_every_ledger_id_cited_in_the_spec_exists_in_the_ledger():
    cited = set(re.findall(r"`([a-z0-9][a-z0-9-]{3,})`", _spec_text()))
    known = set(row_id(l) for l in ledger_rows(DOC.read_text()))
    # Only ids that look like ledger rows and appear near the words that mark a citation, so
    # ordinary backticked identifiers do not create noise.
    referenced = {c for c in cited if c in known or c.endswith(("-reporting", "-calibration",
                "-guarantee", "-disclaimer", "-example", "-tests", "-acronym", "-section",
                "-source", "-two-losses", "-channels", "-count", "-size"))}
    dangling = sorted(r for r in referenced if r not in known)
    assert not dangling, "spec cites ledger ids that do not exist: %s" % dangling


def test_the_spec_does_not_re_assert_a_withdrawn_identifier_without_citing_its_row():
    # A line may mention a withdrawn identifier only if it cites the ledger row that
    # withdrew it. Word heuristics ("not", "no such") were the first attempt and they are
    # unfalsifiable prose-guessing; a row id is checkable, and it makes every correction
    # traceable to its evidence, which is the whole habit of this project.
    text = _spec_text()
    bad = []
    for token, guard in (("KIGEL", "kigel-acronym"),
                         ("AISTATS 2023", "ordinal-cp-aistats2023"),
                         # `marginal-only` is deliberately NOT policed: it is ordinary
                         # vocabulary for our own certificates, and no word list tells a
                         # correction from a use. The three tokens below are proper names.
                         ("~20k", "laya-star-count")):
        for n, line in enumerate(text.splitlines(), 1):
            if token in line and guard not in line:
                bad.append((n, token, line[:80]))
    assert not bad, "withdrawn identifier without its ledger row: %s" % bad

def test_every_ledger_row_sits_under_its_own_table_header():
    """The defect this guards: a row appended after prose renders as text, not a table.

    The `competitor-age-stars-packaging` row was found that way -- counted by the census,
    invisible on the page. So the check is block structure: every contiguous run of `|`
    lines that holds ledger rows must open with the five-column header and a delimiter
    row. A cell-count check was tried and rejected -- these rows quote grep patterns
    containing `|`, so counting separators reported ten columns on a five-column table.
    """
    blocks = _table_blocks(DOC.read_text())
    assert len(blocks) >= 2, "expected one table per ledger section"
    total = 0
    for head, rows in blocks:
        assert head.strip().startswith("| id | claim |"), head[:40]
        assert rows and set(rows[0].strip()) <= set("|-: "), rows[:1]
        total += len(rows) - 1
    assert total == CENSUS_ROWS, total


def _table_blocks(body: str) -> list:
    """(header line, [delimiter, ...rows]) per contiguous `|` run holding ledger rows."""
    out, buf = [], []
    for line in body.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            buf.append(line)
            continue
        if any(l.lstrip().startswith("| id=") for l in buf):
            out.append((buf[0], buf[1:]))
        buf = []
    return out


def test_the_block_check_proves_it_can_fire():
    """The orphan-row defect, planted: a ledger row with no header above it."""
    body = DOC.read_text()
    lines = body.splitlines(keepends=True)
    prose = [i for i, l in enumerate(lines)
             if l.strip() and not l.lstrip().startswith("|") and not l.startswith("#")]
    assert prose, "no prose to plant against"
    planted = ("\n| id=planted-orphan | a claim | https://e | 2026-10-02 | "
               "status: verified |\n")
    broken = "".join(lines[:prose[0]] + [planted] + lines[prose[0]:])
    orphans = [head for head, _ in _table_blocks(broken)
               if not head.strip().startswith("| id | claim |")]
    assert orphans, "the check cannot see a headerless row"
    assert not [h for h, _ in _table_blocks(body) if not h.strip().startswith("| id | claim |")]


# --------------------------------------------------------------- spec API surface (rulings D-c / D-e)

def _spec_api_block() -> str:
    """The fenced python block under spec section 10, exactly as the document carries it."""
    text = _spec_text()
    start = text.index("## 10. Public API surface")
    fence = text.index("```python", start)
    end = text.index("```", fence + len("```python"))
    return text[fence + len("```python"):end]


def _api_objects() -> dict:
    """The two shapes section 10 documents, read from their dataclasses rather than from prose."""
    import dataclasses
    import importlib

    certificate = importlib.import_module("autorate.certificate")
    certify_choice = importlib.import_module("autorate.certify_choice")
    out = {}
    for key, cls in (("cert", certificate.Certificate), ("grouped", certify_choice.GroupsCertificate)):
        out[key] = ({f.name for f in dataclasses.fields(cls)}
                    | {a for a in dir(cls) if not a.startswith("_")})
    return out


def _attributed_fields(block: str) -> tuple:
    """Every `object.field` the block attributes, with comments removed first.

    Comment-stripping is the whole point, not a nicety: the amendment's header lines name `cert.risk_bound`
    in order to say it was retired. A guard that scanned them would fail the sentence that fixes the defect it
    is policing -- the same trap the withdrawn-row guard above had to step around.
    """
    code = "\n".join(line.split("#")[0] for line in block.splitlines())
    return tuple(re.findall(r"\b(cert|grouped)\.([a-z_]+)", code))


@pytest.mark.parametrize("object_name,attr", [
    ("cert", "autorate"), ("cert", "autorate_ci"), ("cert", "conditional_error_bound"),
    ("cert", "marginal_error_bound"), ("cert", "feasible"), ("cert", "envelope"),
    ("grouped", "feasible"), ("grouped", "envelope"), ("grouped", "n_min_violations"),
])
def test_the_api_objects_expose_every_field_the_amendment_attributes(object_name, attr):
    """The premise the guard below stands on: each named object really carries the field section 10 cites.

    Red if a dataclass loses a field section 10 cites. This is NOT the negative control for the row below --
    it proves the sets being consulted are the shipped shapes; the next row proves the guard can fail.
    """
    assert attr in _api_objects()[object_name], (
        object_name, attr, sorted(_api_objects()[object_name])[:8])


def test_the_api_guard_proves_it_can_fire():
    """Negative control: the same predicate must refuse a planted attribution, in two ways.

    The first plant moves the retired name `cert.risk_bound` out of the comment and into a code line, which
    is exactly the edit that let the invented field survive in the document. The second re-attributes a real
    field to the wrong object -- `n_min_violations` belongs to `GroupsCertificate` and `Certificate` does not
    carry it -- so a check that only asked "does this field exist somewhere" would stay green.
    """
    objects = _api_objects()
    block = _spec_api_block()

    planted = block.replace("cert.autorate  ", "cert.autorate\n cert.risk_bound      ")
    assert _attributed_fields(block) != _attributed_fields(planted), "the plant did not land in the parsed text"
    assert sorted({(o, f) for o, f in _attributed_fields(planted) if f not in objects[o]}) == \
        [("cert", "risk_bound")]

    swapped = block.replace("grouped.n_min_violations", "cert.n_min_violations")
    assert _attributed_fields(block) != _attributed_fields(swapped), "the plant did not land in the parsed text"
    missing = sorted({(o, f) for o, f in _attributed_fields(swapped) if f not in objects[o]})
    assert missing == [("cert", "n_min_violations")], (
        "re-attributing a real field to the wrong object must be named by the predicate, got %s" % (missing,))


def test_every_field_section_10_attributes_lives_on_that_object():
    """Section 10 printed two objects' fields as one's, and named a bound that was never shipped.

    Rulings D-c and D-e were recorded in the ledger and never written into the spec, so the document still
    showed `cert.risk_bound` (no shape carries it; `Certificate` names `conditional_error_bound` and
    `marginal_error_bound`) and a single `certify` entry that does not exist. Re-reading the dataclasses
    surfaced a third divergence neither ruling covered: `n_min_violations` belongs to `GroupsCertificate`
    while the bounds belong to `Certificate`, and the old block printed them side by side as though one
    object had all of them.

    Red if: a field the block attributes to `cert` or `grouped` is absent from that object's dataclass, or the
    block stops attributing any field to a named object (an unattributed `cert.<field>` is the ambiguity that
    let the invented name survive).
    """
    objects = _api_objects()
    cited = _attributed_fields(_spec_api_block())
    assert len(cited) >= 8, "section 10 stopped attributing fields to objects: %r" % (cited,)
    missing = sorted({(obj, field) for obj, field in cited if field not in objects[obj]})
    assert not missing, (
        "spec section 10 attributes fields to objects that do not carry them: %s" % (missing,))


# --------------------------------------------------------------- citations point at things that exist

REPO = Path(__file__).resolve().parents[1]

#: The documents that describe the tree AS IT IS NOW. `docs/ERRATA.md` is excluded on purpose, and the
#: exclusion is a ruling rather than an oversight: every ERRATA entry is a dated observation about the tree
#: of its own date, and rule 7 forbids overwriting one to make it read well now. So a pointer inside an
#: ERRATA row names the test as it was named that day -- `test_a_stored_certificate_that_violates_its_shape_
#: is_a_usage_error` was the real name when it was written and later became
#: `..._is_drift_on_a_published_path` when the rc-2-vs-rc-4 axis settled -- and the correction channel for a
#: dated row is a NEW dated row, which is what the 2026-10-18 ERRATA entry does for both renames below.
#: `docs/superpowers/plans/*.md` is excluded for the mirror reason: a plan is an instruction written before
#: the code existed, and its test names are the names it asked for, not a claim about the suite.
CURRENT_TRUTH_DOCS = ("README.md", "docs/superpowers/specs")

BARE_TEST_CITE = re.compile(r"`(test_[a-z0-9_]{8,})`")
QUALIFIED_CITE = re.compile(r"tests/([A-Za-z_0-9]+\.py)::([A-Za-z_][A-Za-z0-9_]*)")


def _current_truth_documents() -> list:
    """Every document that speaks in the present tense about this tree, discovered rather than remembered."""
    docs = [REPO / "README.md"]
    docs.extend(sorted((REPO / "docs").glob("*.md")))
    docs.extend(sorted((REPO / "docs" / "superpowers" / "specs").glob("*.md")))
    docs = [d for d in docs if d.is_file() and d.relative_to(REPO).as_posix() != "docs/ERRATA.md"]
    assert docs, "no current-truth documents found at all, so this row has nothing to check"
    excluded = [d.relative_to(REPO).as_posix() for d in sorted((REPO / "docs").glob("*.md"))
                if d.relative_to(REPO).as_posix() == "docs/ERRATA.md"]
    assert excluded == ["docs/ERRATA.md"], (
        "the one declared exclusion vanished, which means the shape of the docs directory moved and this "
        "row is now checking a different corpus than it claims: %s" % excluded)
    return docs


def _module_level_names(path: Path) -> set:
    """Top-level defs, classes and bindings of one test module, read with `ast` rather than scanned."""
    names = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _unresolved_citations(texts) -> list:
    """Every `(document, citation)` pair whose target does not exist in this tree."""
    suite = {}
    for path in sorted((REPO / "tests").glob("*.py")):
        suite[path.name] = _module_level_names(path)
    any_test = {name for path, names in suite.items() if path.startswith("test_") for name in names}
    unresolved = []
    for label, text in texts:
        for match in QUALIFIED_CITE.finditer(text):
            module, name = match.group(1), match.group(2)
            if module not in suite:
                unresolved.append((label, "%s (no such test module)" % module))
            elif name not in suite[module]:
                unresolved.append((label, "tests/%s::%s" % (module, name)))
        for name in sorted(set(BARE_TEST_CITE.findall(text))):
            if name not in any_test:
                unresolved.append((label, name + " (bare)"))
    return unresolved


def test_every_test_citation_in_the_current_docs_names_a_function_that_exists():
    """A sentence that tells a reader to go look at a test is a citation, and a stale one is a defect.

    Found by writing this row: `docs/VERIFICATION.md` and spec §5.5 both point §5.5's flagship
    `NOT_CERTIFIABLE` anchor at `test_a_near_uniform_task_is_refused_not_certified`, a name that left the
    suite when the I-10 round made the generator able to produce a wrong argmax -- the shipped row is
    `tests/test_certify_choice.py::test_an_uninformative_task_with_real_errors_is_refused_not_certified`.
    Nothing in the repository checked test-name pointers, so the ledger kept certifying a reproducible
    refusal by citing a test nobody can open, which is exactly the failure the §17 ledger exists to prevent
    for URLs.

    Red if: a `tests/<file>.py::name` citation names a module or a module-level object that is not there, or
    a bare `` `test_...` `` citation names a function no test module defines.

    The convention this row enforces, stated because it decides how a rename is written down: a test name in
    backticks is a LIVE pointer -- the reader is being told to go open it -- so it must resolve. A historical
    name is prose, and prose about a name that no longer exists goes without backticks (see the two 2026-10-18
    notes in `docs/VERIFICATION.md` and spec section 5.5, which cite the current name live and mention the old
    one unquoted). That keeps the gate strict without forcing anyone to rewrite a dated sentence.
    """
    texts = [(path.relative_to(REPO).as_posix(), path.read_text()) for path in _current_truth_documents()]
    unresolved = _unresolved_citations(texts)
    assert unresolved == [], (
        "%d test citation(s) in the current-truth documents point at nothing in this tree: %s -- the reader "
        "is told to re-run a test that does not exist, which is the same defect class as a URL that 404s"
        % (len(unresolved), "; ".join("%s -> %s" % pair for pair in unresolved)))


def test_the_citation_row_fires_on_a_renamed_target():
    """The plant this row needs, because a citation guard that finds nothing is indistinguishable from one
    that cannot look: the two stale names it actually caught are replayed as forged text, and one live name
    is asserted to pass so the check is not simply always-red.
    """
    live = sorted((REPO / "tests").glob("test_certify_choice.py"))[0].name
    assert _unresolved_citations([("forged", "see `test_a_near_uniform_task_is_refused_not_certified`")]) == [
        ("forged", "test_a_near_uniform_task_is_refused_not_certified (bare)")], "the bare shape does not fire"
    assert _unresolved_citations([("forged", "tests/%s::test_a_stored_certificate_that_violates_its_shape_"
                                            "is_a_usage_error" % live)]) == [
        ("forged", "tests/%s::test_a_stored_certificate_that_violates_its_shape_is_a_usage_error" % live)], (
        "the qualified shape does not fire")
    assert _unresolved_citations([("forged", "tests/test_certify_choice.py::"
                                    "test_an_uninformative_task_with_real_errors_is_refused_not_certified")]) == [], (
        "a live qualified citation is being reported, so the row cannot be trusted to be quiet")
    assert _unresolved_citations([("forged", "`test_an_uninformative_task_with_real_errors_is_refused_not_"
                                    "certified`")]) == [], "a live bare citation is being reported"
