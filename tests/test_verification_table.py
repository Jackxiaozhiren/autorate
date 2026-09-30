"""Every citation is either opened at its primary source or deleted. No third state."""
import re
from pathlib import Path

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

# (3) The census. Spec §17 publishes "N rows: V verified, W withdrawn"; until now no code produced or
#     checked any count, so a later-appended row made §17 silently wrong with CI green (review finding
#     I-2). The three constants below are the ledger's only published count: the test counts the rows,
#     prints the line §17 quotes verbatim, and asserts these numbers. Appending or re-status-ing a row
#     is a red run until the constants and the §17 sentence move together with it — the assertion is
#     updated with the row that motivated it, never loosened to absorb a drift.
CENSUS_ROWS = 45
CENSUS_VERIFIED = 39
CENSUS_WITHDRAWN = 6


def ledger_rows(text: str) -> list[str]:
    """Every ledger row in the file, found by its marker alone."""
    return [line for line in text.splitlines() if line.lstrip().startswith(ROW_START)]


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
