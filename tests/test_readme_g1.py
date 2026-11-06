r"""`README.md`'s G1 bullet restates the resplit result; every number in it now has a named owner.

Why this row exists. R-347 found the G1 bullet saying "Six decision tasks", "zero of the six" and
"All six published tasks certify in 0 of 200 splits" while `protocol.json`'s G1 note, `docs/RESPLIT.md`
and `data/resplit_200.json` all held seven. The correction deleted the count instead of retyping it,
but the bullet still carries number tokens and no row owned them: `tests/test_readme_slices.py` windows
from "- **G4, " to "- **G5, ", and `AGENTS.md` rule 6 states that row's reach as "that bullet and no
further". A census over the G4 bullet cannot see G1. This row is the half that makes the next
hand-typed figure in the headline criterion impossible to miss.

Three kinds of owner, named so the reach is not overstated. Measurements come from committed
artefacts: `data/resplit_200.json` for the split count, the published tasks' certificate count, the
synthetic control's rate and its certificate count, and `protocol.json`'s rubric for alpha and the
percent budget. Section citations are validated, not measured: a `§N` or `section N` in the bullet has
to name a heading that exists in the spec, and the kill criterion's section number and threshold are
read out of the spec's own table row. This row therefore detects a spec that was renumbered or
re-thresholded while the README kept the old digits. It does NOT claim to verify that each cited
section says what the sentence says -- that is prose review, not a number guard.

Census plus families, because neither alone is enough. The census refuses any number token no owner
computes; the families require the sentences stating a measurement to name the owner's value, so
swapping one owned figure for another owned figure is still a finding. Both are forged below, and
the families are forged one at a time so each has to name itself in the finding.

What it does not claim. It polices the G1 bullet only. G2--G5, `docs/VERIFICATION.md`, `docs/ERRATA.md`
and the plans are outside this window; the G4 bullet has its own row, and the rest are policed by
their own rows or not at all.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
RESPLIT = REPO / "data" / "resplit_200.json"
PROTOCOL = REPO / "protocol.json"
SPEC = (REPO / "docs" / "superpowers" / "specs"
        / "2026-09-29-certified-decision-gate-design.md")

# The same token shape `tests/test_readme_slices.py` uses for the G4 bullet, so a figure is a figure
# in either window. Kept here rather than imported: the two rows are independent guards, and a
# shared definition would make one of them unable to fail on its own.
TOKEN_RE = re.compile(r"(?<![\w.])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\w.])")
SECTION_HEADING_RE = re.compile(r"^## (\d+)\.", re.M)
KILL_THRESHOLD_RE = re.compile(r"if worst-group certified autorate < ([\d.]+)")
KILL_NEEDLE = "if worst-group certified autorate < "


def _fold(text):
    """Fold the bullet's wrapping so a pattern cannot go blind because a line moved under it."""
    return re.sub(r"\s+", " ", text)


def _bullet():
    text = _fold(README.read_text(encoding="utf-8"))
    start = text.index("- **G1, ")
    try:
        stop = text.index("- **G2, ", start)
    except ValueError:
        raise AssertionError("`README.md` no longer has a G2 bullet after G1, so this row's window is wrong")
    return text[start:stop]


def _section_before(spec, needle):
    """The `## N.` heading that owns `needle`, read from the spec rather than typed here."""
    pos = spec.find(needle)
    assert pos >= 0, "the spec no longer carries %r, so the README's citation has no owner" % needle
    headings = list(SECTION_HEADING_RE.finditer(spec, 0, pos))
    assert headings, "no `## N.` heading precedes %r in the spec" % needle
    return headings[-1].group(1)


def _owners():
    resplit = json.loads(RESPLIT.read_text(encoding="utf-8"))
    rubric = json.loads(PROTOCOL.read_text(encoding="utf-8"))["rubric"]
    spec = SPEC.read_text(encoding="utf-8")

    tasks = resplit["tasks"]
    control = [t for t in tasks if t["label"].startswith("synthetic/")]
    published = [t for t in tasks if not t["label"].startswith("synthetic/")]
    assert len(control) == 1, "the artefact no longer has exactly one synthetic control"
    assert published, "the artefact has no published decision tasks"
    counts = {t["certificates_issued"] for t in published}
    assert len(counts) == 1, "published tasks no longer all refuse, so the bullet's single count needs rewriting"
    assert control[0]["violation_rate"] is not None, "the control no longer carries a rate"

    kill = KILL_THRESHOLD_RE.search(spec)
    assert kill, "the spec's numeric kill criterion is gone, so the README's threshold has no owner"
    sections = set(SECTION_HEADING_RE.findall(spec))
    assert sections, "the spec has no numbered headings, so no section citation can be validated"

    return {
        "alpha": "%g" % rubric["alpha"],
        "budget_pct": "%g" % (rubric["beta"] * 100),
        "resplits": resplit["resplits"],
        "published_certified": counts.pop(),
        "control_certified": control[0]["certificates_issued"],
        "control_rate": "%.3f" % control[0]["violation_rate"],
        "sections": sections,
        "kill_section": _section_before(spec, KILL_NEEDLE),
        "kill_threshold": kill.group(1),
    }


def _families(o):
    """(name, pattern, expected captures) for each sentence that states an owned value."""
    return [
        ("criterion alpha", r"certified at `autorate\(α = ([\d.]+)\)`", (o["alpha"],)),
        ("criterion resplit count", r"with a (\d+)-resplit empirical", (str(o["resplits"]),)),
        ("percent budget", r"sits above a (\d+)% budget", (o["budget_pct"],)),
        ("method resplit count", r"re-splits every scored task (\d+) times", (str(o["resplits"]),)),
        ("published result", r"All published tasks certify in \*\*(\d+) of (\d+)\*\* splits",
         (str(o["published_certified"]), str(o["resplits"]))),
        ("no imputed rate", r"instead of being imputed as `([\d.]+)`", (o["control_rate"],)),
        ("synthetic control row",
         r"the synthetic control \((\d+) of (\d+) splits certify, rate ([\d.]+) over (\d+) certificates\)",
         (str(o["control_certified"]), str(o["resplits"]), o["control_rate"], str(o["control_certified"]))),
        ("feasibility alpha", r"certifiable at `α = ([\d.]+)`", (o["alpha"],)),
        ("kill section", r"§(\d+)'s kill criterion", (o["kill_section"],)),
        ("kill threshold", r"certified `autorate` with ([\d.]+)", (o["kill_threshold"],)),
    ]


def _owned(o):
    """Every spelling a measurement owner computes. Section numbers deliberately are NOT here: they
    belong to the citation check below, and admitting them would let a real heading number smuggle an
    unrelated figure through the census.
    """
    values = {o["kill_threshold"], o["control_rate"], o["alpha"], o["budget_pct"]}
    values.add("%0.3f" % float(o["alpha"]))
    for n in (o["resplits"], o["published_certified"], o["control_certified"]):
        values.add(str(n))
        values.add(f"{n:,}")
    return values


def _findings(text, o):
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
    for cited in sorted(set(re.findall(r"(?:§|section )(\d+)", text))):
        if cited not in o["sections"]:
            found.append("section citation %r names a section with no heading in the spec" % cited)
    # Citations are removed before the census, so a number is either a heading the spec backs (checked
    # above) or a figure an artefact/rubric computes (checked here), with no third state to hide in.
    residual = re.sub(r"(?:§|section )\d+", " ", text)
    owned = _owned(o)
    for token in sorted(set(TOKEN_RE.findall(residual))):
        if token not in owned:
            found.append("unowned number %r appears in the G1 bullet and no artefact, rubric or spec citation "
                         "computes it" % token)
    return found


def test_the_g1_bullet_agrees_with_the_artefacts_and_spec_it_quotes():
    o = _owners()
    assert o["published_certified"] == 0, (
        "a published decision task now certifies in some split, so the G1 bullet's refusal is no longer the result")
    findings = _findings(_bullet(), o)
    assert not findings, ("README's G1 bullet disagrees with the artefacts and the spec it quotes:\n  "
                          + "\n  ".join(findings))


def test_every_family_this_row_polices_can_go_red():
    """Forge each family's own value in place; the finding has to name THAT family."""
    o = _owners()
    text = _bullet()
    for name, pattern, expected in _families(o):
        m = re.search(pattern, text)
        assert m, "family %r is not matched by its own pattern" % name
        forged_value = "99999"
        forged_match = m.group(0).replace(expected[0], forged_value, 1)
        assert forged_match != m.group(0), "the %s forgery changed nothing" % name
        mutated = text[:m.start()] + forged_match + text[m.end():]
        findings = [f for f in _findings(mutated, o)
                    if not f.startswith("unowned number") and not f.startswith("section citation")]
        assert findings and all(name in f for f in findings), (
            "forging %s (%s -> %s) produced %s, so that family is not the one actually policed" % (
                name, expected[0], forged_value, findings))


def test_the_g1_census_catches_a_number_no_owner_computes():
    """A figure in a shape no family looks at is exactly what a family list goes blind to."""
    o = _owners()
    injected = _findings(_bullet().replace("the second column", "the 41.7 second column"), o)
    assert any("unowned number '41.7'" in f for f in injected), injected


def test_a_section_citation_the_spec_cannot_back_is_refused():
    """The spec's headings are the owner of a section number, not the README's own prose."""
    o = _owners()
    text = _bullet()
    assert o["kill_section"] in o["sections"]
    forged = text.replace("§%s's kill criterion" % o["kill_section"], "§99999's kill criterion")
    assert forged != text, "the citation forgery changed nothing"
    findings = _findings(forged, o)
    assert any("section citation '99999'" in f for f in findings), findings


def test_a_measurement_cannot_hide_behind_a_real_section_number():
    """A census that credited every spec heading as an owner would pass this, and that is the hole."""
    o = _owners()
    section = sorted(o["sections"])[0]
    text = _bullet()
    forged = text.replace("the second column", "the %s extra second column" % section, 1)
    assert forged != text, "the census forgery changed nothing"
    findings = _findings(forged, o)
    assert any("unowned number %r" % section in f for f in findings), findings
