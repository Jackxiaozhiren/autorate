r"""`README.md`'s G4 bullet restates the slice run, so every restatement is checked against the artefact.

Why this row exists. Round 22 widened the slice run -- a fifth MASSIVE language -- and moved six quantities the
frozen G4 note owns (`92` to `108` field comparisons, four slices to five, `11,896` cases to `14,870`,
`0.05 / 4 = 0.0125` to `0.05 / 5 = 0.01`, and the two row counts that follow from five groups). The note moved,
`docs/SLICES.md` re-rendered itself, and `README.md`'s G4 bullet kept the old values in eight hand-typed
positions. Nothing noticed: the transcript guard owns the `895/932` pair, the digit-residue row owns the frozen
notes, and a third prose copy of the same run belonged to no one. Round 23 found it only because its driver read
the bullet against the artefact by hand. This row is what it should have been gated by.

How it works, and what that buys. Each fact the bullet states about the slice run is a *family*: a regex over the
bullet and the value its owner computes. Owners are read, never retyped -- the artefact
(`data/slices_language.json`), the record files it lists, and `report.rederive_slices` driven with counting
callbacks at this freeze's rubric, which is how `tests/test_verify_protocol.py` already polices the same digits
in the note. Two directions are enforced per family: the expected value has to be present, and no *other* value
in that shape is allowed anywhere in the bullet -- so a stale sentence that survived a widening, or one added
later with a remembered number, both come back as findings rather than as a passing presence check.

What it does not claim. The bullet also states upstream's own figures (`accuracy 0.000 at mean confidence 0.952`
on a 100-case read) and the contamination arm's (`27 usable rows`, `delta_hat = -0.235208`, `29 quantities plus 4
budget values`), plus the five marginal certificates' automation counts. Those are owned elsewhere and are not
policed here; the families below cover the slice run and the shape census around it. Widening this row to the
other arms is a later round with its own forgeries, not a claim this one gets to make.

Proof that it can fail, since it is green on the tree it lands in. Two directions, both run. First,
`test_every_family_this_row_polices_can_go_red` forges each family's own value in place and requires the finding
to name that family -- so no family is policed by a lucky substring and none is a presence check. Second, the
controller replayed this same checker against the revision the defect lived in: the README text of the commit
that transcribed the twenty-second round's lanes, with this round's owners. It came back naming all nine stale
positions (the record-file count, the case total in both of its spellings, the arm's field-comparison count, the
slice count, the corrected budget, the cross size, the null-row count and the "other slices" count), plus four
shape-census hits over three distinct digits no owner computes. That replay is the reason the row was not written to agree with
the bullet it now polices.
"""
import json
import re
from pathlib import Path

from autorate import report

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"

NUMWORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
           10: "ten"}


def _fold(text):
    """Fold the bullet's wrapping so a pattern cannot go blind because a line moved under it.

    `README.md` wraps at ~110 columns and a phrase like "the five committed MASSIVE record files" spans two
    lines today. Matching against raw text would make this guard silently depend on formatting.
    """
    return re.sub(r"\s+", " ", text)


def _bullet():
    text = _fold(README.read_text(encoding="utf-8"))
    start = text.index("- **G4, ")
    try:
        stop = text.index("- **G5, ", start)
    except ValueError:
        raise AssertionError("`README.md` no longer has a G5 bullet after G4, so this row's window is wrong")
    return text[start:stop]


def _owners():
    """Every value the G4 bullet is allowed to state about the slice run, read from its owners."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    run = doc["run"]
    protocol = json.loads((REPO / "protocol.json").read_text())
    fields, rubric = [], []
    report.rederive_slices(lambda label, actual, wanted: fields.append(label),
                           lambda label, actual, wanted: rubric.append(label),
                           rubric=protocol["rubric"])
    groups = run["worst_claim"]["groups"]
    census = {row["group"]: row for row in run["slice_census"]}
    km = run["per_group"]["km"]
    option_counts = set()
    for rel in report.SLICE_RECORDS:
        for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
            if line.strip():
                option_counts.add(len(json.loads(line)["options"]))
    total_rows = sum(row["rows"] for row in doc["inputs"])
    n_groups = run["n_groups"]
    return {
        "record_files": len(report.SLICE_RECORDS),
        "total_rows": total_rows,
        "field_comparisons": len(fields),
        "rubric_rows": len(rubric),
        "n_groups": n_groups,
        "certified": sum(1 for g in groups if g["feasible"]),
        "null_autorate_rows": sum(1 for g in groups if g["autorate"] is None),
        "alpha": run["alpha"],
        "corrected_alpha": run["corrected_alpha"],
        "joint_level": run["level"],
        "km_rows": census["km"]["records"],
        "km_cases": km["n_eval"],
        "option_count": option_counts,
    }


def _families(o):
    """(name, pattern, expected capture tuple) for each fact the bullet states about the slice run."""
    word = NUMWORD[o["record_files"]]
    other_word = NUMWORD[o["n_groups"] - 1]
    return [
        ("record-file count", r"certifies the (\w+) committed MASSIVE record files", (word,)),
        ("case total", r"files \(([\d,]+) cases\) as slices", (f"{o['total_rows']:,}",)),
        ("arm size", r"recomputes that run from the same bytes, ([\d,]+) field comparisons plus (\d+) rubric rows",
         (f"{o['field_comparisons']:,}", str(o["rubric_rows"]))),
        ("slice and certified counts", r"(\d+) slices, (\d+) certified", (str(o["n_groups"]), str(o["certified"]))),
        ("corrected budget", r"alpha and delta ([\d.]+) / (\d+) = ([\d.]+), joint level ([\d.]+)",
         (f"{o['alpha']:g}", str(o["n_groups"]), f"{o['corrected_alpha']:g}", f"{o['joint_level']:g}")),
        ("row total", r"measured across all ([\d,]+) rows", (f"{o['total_rows']:,}",)),
        ("cross size", r"would be the same (\w+) slices", (NUMWORD[o["n_groups"]],)),
        ("null rows", r"null in all (\w+) rows", (NUMWORD[o["n_groups"]],)),
        ("other slices refused", r"refusing like the other (\w+) at the same rubric", (other_word,)),
        ("khmer rows", r"commits ([\d,]+) per-case rows", (f"{o['km_rows']:,}",)),
        ("khmer cases", r"these ([\d,]+) evaluated Khmer cases", (f"{o['km_cases']:,}",)),
        ("option count", r"`option_count` is (\d+) for every committed MASSIVE row",
         (str(next(iter(o["option_count"]))),)),
    ]


SHAPES = ("slices", "field comparisons", "rubric rows", "cases", "rows", "per-case rows", "evaluated Khmer cases")
SHAPE_RE = re.compile(r"([\d,]+) (?:(?:%s)\b)" % "|".join(SHAPES))


def _findings(text, o):
    """Every way the bullet can disagree with its owner: a wrong value, a missing family, an unowned shape."""
    found = []
    for name, pattern, expected in _families(o):
        matches = re.findall(pattern, text)
        if not matches:
            found.append("%s: no sentence matches %r, so the fact this row polices has left the bullet"
                         % (name, pattern))
            continue
        for match in matches:
            group = match if isinstance(match, tuple) else (match,)
            if group != expected:
                found.append("%s: bullet states %s, its owner states %s" % (name, group, expected))
    owned = {f"{o['total_rows']:,}", f"{o['field_comparisons']:,}", str(o["rubric_rows"]), str(o["n_groups"]),
             str(o["certified"]), f"{o['km_rows']:,}", f"{o['km_cases']:,}", "0"}
    for number in SHAPE_RE.findall(text):
        if number not in owned:
            found.append("unowned shape digit: %s appears before a slice-run noun and no owner computes it "
                         "(owned: %s)" % (number, sorted(owned)))
    return found


def test_readme_g4_bullet_agrees_with_the_slice_artefact():
    o = _owners()
    assert o["record_files"] == o["n_groups"], (
        "the record files and the slice groups diverged, so the bullet's own arithmetic needs a new owner")
    assert o["option_count"] == {20} or len(o["option_count"]) == 1, (
        "`option_count` is no longer one value across the committed rows, so the bullet's "
        "single-cross argument is false: %s" % sorted(o["option_count"]))
    assert o["null_autorate_rows"] == o["n_groups"], (
        "the artefact now carries a measured `autorate` for some slice, so the tie-break caveat the bullet "
        "states has to be rewritten before this row can police it")
    findings = _findings(_bullet(), o)
    assert not findings, "README's G4 bullet disagrees with `data/slices_language.json`:\n  " + "\n  ".join(findings)


def test_every_family_this_row_polices_can_go_red():
    """The negative control, per family: forge that family's value and the row has to name it.

    Without this the row is a presence check, and a presence check passes on a bullet that simply dropped the
    sentence it policed. Each forgery changes one number in one family and expects that family back as the
    finding -- not merely "some finding".
    """
    o = _owners()
    text = _bullet()
    for name, pattern, expected in _families(o):
        m = re.search(pattern, text)
        assert m, "family %r is not matched by its own pattern" % name
        forged_value = "nine" if expected[0].isalpha() else "99999"
        forged_match = m.group(0).replace(expected[0], forged_value, 1)
        assert forged_match != m.group(0), "the %s forgery changed nothing" % name
        mutated = text[:m.start()] + forged_match + text[m.end():]
        findings = _findings(mutated, o)
        family_findings = [f for f in findings if not f.startswith("unowned shape digit")]
        assert family_findings and all(name in f for f in family_findings), (
            "forging %s (%s -> %s) produced %s, so that family is not the one actually policed" % (
                name, expected[0], forged_value, findings))
