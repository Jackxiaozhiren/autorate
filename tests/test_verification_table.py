"""Every citation is either opened at its primary source or deleted. No third state."""
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "VERIFICATION.md"
ALLOWED = {"verified", "withdrawn"}
# Deviation from the plan's pattern, recorded deliberately: the plan writes the id class as
# `[a-z0-9]+`, which cannot match a hyphenated id (`id=mapie-crc-disclaimer` stops at `mapie`, so
# the `\s*\|` that follows never matches). Every id in this ledger is hyphenated because the ids
# name spec §17 rows, so the plan's own example row is invisible to the plan's own gate and
# `test_no_row_is_left_unverified_or_unknown` would pass on a ledger full of unresolved citations.
# The class is widened, never narrowed: any id the plan's pattern accepted still matches. The
# negative-control test below makes that fix checkable rather than load-bearing on luck.
ROW = re.compile(r"^\|\s*id=(?P<id>[a-z0-9][a-z0-9-]*)\s*\|.*status:\s*(?P<status>\w+)", re.M)


def test_ledger_exists_and_has_rows():
    assert DOC.exists(), "docs/VERIFICATION.md missing"
    assert ROW.findall(DOC.read_text()), "ledger has no rows"


def test_no_row_is_left_unverified_or_unknown():
    bad = {m["id"]: m["status"] for m in ROW.finditer(DOC.read_text())
           if m["status"] not in ALLOWED}
    assert not bad, f"unresolved citations: {bad}"


def test_every_verified_row_carries_url_and_date():
    for line in DOC.read_text().splitlines():
        if "status: verified" in line:
            assert "https://" in line, line
            assert re.search(r"20\d\d-\d\d-\d\d", line), line


def test_withdrawn_rows_say_what_replaced_them():
    for line in DOC.read_text().splitlines():
        if "status: withdrawn" in line:
            assert "replaced:" in line or "dropped:" in line, line


def test_gate_sees_every_row_it_checks():
    # Falsifiability of the gate itself: a row that carries a status but does not parse as
    # `| id=<lowercase-hyphenated> | … status: <word> |` would be skipped silently, which is how
    # an unresolved citation survives a green run. Any table row with a status must be matched.
    invisible = [
        line
        for line in DOC.read_text().splitlines()
        if line.lstrip().startswith("|")
        and re.search(r"status:\s*\w+", line)
        and not ROW.match(line)
    ]
    assert not invisible, f"rows invisible to the gate: {invisible}"
