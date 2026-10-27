r"""`README.md`'s G4 bullet restates three arms, and every restatement is checked against its owner.

Why this row exists. Round 22 widened the slice run -- a fifth MASSIVE language -- and moved six quantities the
frozen G4 note owns (`92` to `108` field comparisons, four slices to five, `11,896` cases to `14,870`,
`0.05 / 4 = 0.0125` to `0.05 / 5 = 0.01`, and the two row counts that follow from five groups). The note moved,
`docs/SLICES.md` re-rendered itself, and `README.md`'s G4 bullet kept the old values in eight hand-typed
positions. Nothing noticed: the transcript guard owns the lane pair, the digit-residue row owns the frozen notes,
and a third prose copy of the same run belonged to no one. Round 23 found it only because its driver read the
bullet against the artefact by hand -- so the correction landed then, and this row is the half that makes the
correction unnecessary next time.

How it works. Each fact the bullet states is a *family*: a regex over the folded bullet and the value its owner
computes. Owners are read, never retyped -- `data/slices_language.json` and the record files it lists for the
slice run; the five `data/cert_massive_*_laya.json` certificates for the marginal counts, including the "upper
bound" figure, which is lifted from each certificate's own `meta.detail` rather than re-rounded here, because a
rounding rule invented inside a test would be a second owner of a published bound; `data/contamination_probe.json`
for the pin's usable and excluded row counts and for `delta_hat` with its interval; `report.rederive_slices` and
`report.rederive_contamination`, each driven with counting callbacks at this freeze's rubric, for the two sentences
that state an arm's own size -- the same measurement `tests/test_verify_protocol.py` applies to the frozen note;
and `cli.EXIT_NOT_CERTIFIABLE` for the exit code the bullet quotes. Two directions are enforced per family: the
owner's value has to be present, and no *other* value in that shape may appear anywhere in the bullet, so a stale
sentence that survived a widening and a sentence added later from memory are both findings rather than a
satisfied presence check.

Then the census closes the hole a family list always leaves: every number token in the bullet must be computed by
an owner or excused by a declared exemption, and an exemption has to stay alive. Today exactly one sentence is
excused -- upstream's own Khmer read, `accuracy 0.000 at mean confidence 0.952` over 100 cases, which quotes an
external document this repository publishes no bytes of. Each waiver names the sentence it excuses, so the row
reddens if that wording disappears or if the token stops appearing in it: a waiver cannot outlive the fact that
earned it.

What it does not claim. It polices one bullet of one document. `README.md`'s other bullets, and the hand-typed
figures in `docs/VERIFICATION.md`, `docs/ERRATA.md` and the plans, are policed elsewhere or not at all --
`tests/test_errata_digests.py` checks digests rather than quantities, and the digit-residue row in
`tests/test_verify_protocol.py` owns `protocol.json`'s notes. A guard over one bullet is not a guard over the
repository, and this docstring would be overstating its own reach if it said otherwise.

Proof that it can fail, since it is green on the tree it lands in. Three readings, all run.
`test_every_family_this_row_polices_can_go_red` forges each family's own value in place and requires the finding
to name that family, so no family is policed by a lucky shared substring.
`test_the_token_census_catches_a_number_no_family_owns` injects a figure in a shape no family looks at, and parks
an exemption to prove a dead waiver is refused. And the controller replayed this same checker against the revision
the defect lived in -- `README.md` as of `577e5c7`, the commit that transcribed round 22's lanes and left the
bullet behind, against these owners -- where it came back with nine family findings naming every stale position.
That replay is why the row was not written to agree with the prose it polices.
"""
import json
import re
from pathlib import Path

from autorate import cli, report

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"

NUMWORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
           10: "ten"}

# token -> the sentence it lives in. Upstream's own 100-case read of the Khmer slice: this repository quotes it and
# says it neither replicates nor contradicts it, so the figures belong to a document no committed byte of ours
# holds. The row refuses the table if the quoted sentence disappears or a token stops appearing in it, which is
# what keeps a waiver from outliving its fact.
UPSTREAM_EXEMPTIONS = {
    "0.000": "Upstream's `accuracy 0.000 at mean confidence 0.952` remains upstream's own",
    "0.952": "Upstream's `accuracy 0.000 at mean confidence 0.952` remains upstream's own",
    "100": "own 100-case read, which these",
}


def _fold(text):
    """Fold the bullet's wrapping so a pattern cannot go blind because a line moved under it.

    `README.md` wraps at ~110 columns and a phrase like "the five committed MASSIVE record files" spans two lines
    today. Matching against raw text would make this guard silently depend on formatting.
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


def _cert(language):
    return json.loads((REPO / "data" / ("cert_massive_%s_laya.json" % language)).read_text())


def _languages():
    """The five MASSIVE languages, read from the publication table that names their certificates.

    `report.MASSIVE_CERTIFICATES` keys are backend-qualified (`massive/de`), while the artefact file names carry
    the bare language code, so the split is the mapping -- a key typed here would be a second list of the five
    that a sixth language could miss.
    """
    return sorted(key.split("/")[-1] for key in report.MASSIVE_CERTIFICATES)


def _measured(driver):
    """Count what an arm compares in the corpus-ABSENT lane, which is the only lane that is deterministic.

    The corpus-present lane legitimately performs extra comparisons -- `rederive_contamination` re-digests the
    upstream results file when a checkout is visible -- so measuring without pinning the corpus made this row
    answer two different questions in two lanes and read the README's single figure as a disagreement. The absent
    count is therefore what the bullet's "in both lanes" number is compared against, and the corpus-only extras are
    taken from `report.CONTAMINATION_CORPUS_ONLY_CHECKS`, the owner `cli.corpus_only_comparisons` already uses for
    the gap between the two denominators.
    """
    import os

    fields, rubric_rows = [], []
    protocol = json.loads((REPO / "protocol.json").read_text())
    previous = os.environ.get("AUTORATE_FEISHU_ROOT")
    os.environ["AUTORATE_FEISHU_ROOT"] = str(REPO / "no-corpus-visible-here")
    try:
        driver(lambda label, actual, wanted: fields.append(label),
               lambda label, actual, wanted: rubric_rows.append(label),
               rubric=protocol["rubric"])
    finally:
        if previous is None:
            del os.environ["AUTORATE_FEISHU_ROOT"]
        else:
            os.environ["AUTORATE_FEISHU_ROOT"] = previous
    assert len(set(fields)) == len(fields), "an arm compared the same label twice, so counting is not measuring"
    return len(fields), len(rubric_rows)


def _owners():
    """Every value the G4 bullet is allowed to state, read from the artefact or the arm that owns it."""
    doc = json.loads((REPO / report.SLICE_JSON).read_text())
    run = doc["run"]
    slice_fields, slice_rubric = _measured(report.rederive_slices)
    contamination_fields, contamination_rubric = _measured(report.rederive_contamination)
    groups = run["worst_claim"]["groups"]
    census = {row["group"]: row for row in run["slice_census"]}
    km = run["per_group"]["km"]
    option_counts = set()
    for rel in report.SLICE_RECORDS:
        for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
            if line.strip():
                option_counts.add(len(json.loads(line)["options"]))
    contamination = json.loads((REPO / report.CONTAMINATION_JSON).read_text())
    languages = {}
    for language in _languages():
        cert = _cert(language)
        meta = cert["meta"]
        upper = re.search(r"upper bound ([0-9.]+)", meta["detail"])
        attempt = meta.get("closest_attempt", {})
        languages[language] = {
            "automated_cases": meta["automated_cases"],
            "erroneous": meta["erroneous_cases"],
            "eval_cases": meta["n_eval_cases"],
            "record_automated": attempt.get("automated"),
            "record_errors": attempt.get("errors"),
            "upper_bound": upper.group(1) if upper else None,
            "feasible": cert["feasible"],
            "alpha": cert["alpha"],
        }
    return {
        "record_files": len(report.SLICE_RECORDS),
        "total_rows": sum(row["rows"] for row in doc["inputs"]),
        "field_comparisons": slice_fields,
        "rubric_rows": slice_rubric,
        "n_groups": run["n_groups"],
        "certified": sum(1 for g in groups if g["feasible"]),
        "null_autorate_rows": sum(1 for g in groups if g["autorate"] is None),
        "alpha": run["alpha"],
        "corrected_alpha": run["corrected_alpha"],
        "joint_level": run["level"],
        "km_rows": census["km"]["records"],
        "km_cases": km["n_eval"],
        "option_count": option_counts,
        "languages": languages,
        "pin_rows": contamination["pin"]["rows"],
        "pin_excluded": len(contamination["pin"]["excluded"]),
        "delta_hat": "%.6f" % contamination["probe"]["delta_hat"],
        "interval": ["%.6f" % value for value in contamination["headline"]["interval"]],
        "contamination_fields": contamination_fields,
        "contamination_rubric": contamination_rubric,
        "contamination_corpus_only": len(report.CONTAMINATION_CORPUS_ONLY_CHECKS),
        "not_certifiable_rc": cli.EXIT_NOT_CERTIFIABLE,
        "budget": "%0.3f" % languages["en"]["alpha"],
    }


def _families(o):
    """(name, pattern, expected capture tuple) for each fact the bullet states about any of the three arms."""
    word = NUMWORD[o["record_files"]]
    other_word = NUMWORD[o["n_groups"] - 1]
    languages = o["languages"]
    families = [
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
        # The refusal is a published result, and the code it prints has one owner: `cli`'s exit contract.
        ("refusal exit code", r"the command over these records exits (\d+), `EXIT_NOT_CERTIFIABLE`",
         (str(o["not_certifiable_rc"]),)),
        # G4's second named output: the contamination arm's rows, bound, interval and own size.
        ("usable and excluded rows", r"(\d+) usable rows and (\d+) excluded by name",
         (str(o["pin_rows"]), str(o["pin_excluded"]))),
        ("delta and interval", r"`delta_hat` = (-[\d.]+) over \[(-[\d.]+), (-[\d.]+)\]",
         (o["delta_hat"], o["interval"][0], o["interval"][1])),
        ("contamination arm size", r"re-pools it \((\d+) quantities plus (\d+) budget values",
         (str(o["contamination_fields"]), str(o["contamination_rubric"]))),
        ("contamination corpus-only extras", r"and (\d+) further comparisons that re-digest the upstream file",
         (str(o["contamination_corpus_only"]),)),
        ("marginal certificate count", r"The (\w+) marginal certificates", (word,)),
        ("nothing certifies", r"none of the (\w+) certifies", (word,)),
        ("budget beside the bounds", r"above the ([\d.]+) budget", (o["budget"],)),
    ]
    de = languages["de"]
    es = languages["es"]
    families.append(("de automates no case", r"`de` automates (\d+) of ([\d,]+) cases",
                     (str(de["automated_cases"]), f"{de['eval_cases']:,}")))
    families.append(("es automates no case", r"and `es` likewise automates (\d+) of ([\d,]+)",
                     (str(es["automated_cases"]), f"{es['eval_cases']:,}")))
    families.append(("es record denominator", r"while its (\d+) automated records carry (\d+) wrong",
                     (str(es["record_automated"]), str(es["record_errors"]))))
    en = languages["en"]
    families.append(("en case denominator", r"`en` automates (\d+) with (\d+) wrong, upper bound (\d+\.\d+)",
                     (str(en["automated_cases"]), str(en["erroneous"]), en["upper_bound"])))
    for language in ("km", "sw"):
        entry = languages[language]
        families.append(("%s case denominator" % language, r"`%s` (\d+) with (\d+) wrong, (\d+\.\d+)" % language,
                         (str(entry["automated_cases"]), str(entry["erroneous"]), entry["upper_bound"])))
    return families


TOKEN_RE = re.compile(r"(?<![\w.])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\w.])")


def _owned_tokens(o):
    """Every spelling an owner computes, in both the comma and the bare form a sentence might use."""
    values = set()
    for value in (o["total_rows"], o["field_comparisons"], o["rubric_rows"], o["n_groups"], o["certified"],
                  o["km_rows"], o["km_cases"], o["pin_rows"], o["pin_excluded"], o["contamination_fields"],
                  o["contamination_rubric"], o["contamination_corpus_only"], o["not_certifiable_rc"]):
        values.add(f"{value:,}")
        values.add(str(value))
    for value in (o["alpha"], o["corrected_alpha"], o["joint_level"]):
        values.add(f"{value:g}")
        values.add("%0.3f" % value)
    values.add(o["budget"])
    # `delta_hat` and its interval are written as magnitudes in the bullet ("over [-a, -b]"), while the artefact
    # carries signed floats, so both spellings of the producer's own 6-dp rounding are offered.
    values.add(o["delta_hat"])
    values.add(o["delta_hat"].lstrip("-"))
    for endpoint in o["interval"]:
        values.add(endpoint)
        values.add(endpoint.lstrip("-"))
    values.add(str(next(iter(o["option_count"]))))
    for entry in o["languages"].values():
        for value in (entry["automated_cases"], entry["erroneous"], entry["eval_cases"],
                      entry["record_automated"], entry["record_errors"]):
            if value is not None:
                values.add(f"{value:,}")
                values.add(str(value))
        if entry["upper_bound"]:
            values.add(entry["upper_bound"])
    return values


def _findings(text, o):
    """Every way the bullet can disagree with its owners: wrong value, vanished family, unowned or parked number."""
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
    for token, context in sorted(UPSTREAM_EXEMPTIONS.items()):
        if context not in text or token not in text:
            found.append("exemption for %r is dead: the sentence it excuses (%r) is no longer this bullet's "
                         "wording, so the waiver has outlived the fact that earned it" % (token, context))
    owned = _owned_tokens(o)
    for token in sorted(set(TOKEN_RE.findall(text))):
        if token in owned or token in UPSTREAM_EXEMPTIONS:
            continue
        found.append("unowned number %r appears in the bullet and no artefact, arm or live exemption computes it"
                     % token)
    return found


def test_readme_g4_bullet_agrees_with_the_slice_artefact():
    o = _owners()
    assert o["record_files"] == o["n_groups"], (
        "the record files and the slice groups diverged, so the bullet's own arithmetic needs a new owner")
    assert len(o["option_count"]) == 1, (
        "`option_count` is no longer one value across the committed rows, so the bullet's single-cross argument is "
        "false: %s" % sorted(o["option_count"]))
    assert o["null_autorate_rows"] == o["n_groups"], (
        "the artefact now carries a measured `autorate` for some slice, so the tie-break caveat the bullet states "
        "has to be rewritten before this row can police it")
    assert o["certified"] == 0, "some slice certifies now, and the bullet's framing is a published refusal"
    assert not any(entry["feasible"] for entry in o["languages"].values()), (
        "a marginal certificate reports feasible, so `none of the five certifies` is no longer the result")
    findings = _findings(_bullet(), o)
    assert not findings, ("README's G4 bullet disagrees with the artefacts and arms it restates:\n  "
                          + "\n  ".join(findings))


def test_every_family_this_row_polices_can_go_red():
    """The negative control, per family: forge that family's value and the row has to name it.

    Without this the row is a presence check, and a presence check passes on a bullet that simply dropped the
    sentence it policed. Each forgery changes one value in one family and expects THAT family back as the
    finding -- not merely "some finding" -- so a family cannot be policed by a lucky shared substring.
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
        findings = [f for f in _findings(mutated, o) if not f.startswith("unowned number")]
        assert findings and all(name in f for f in findings), (
            "forging %s (%s -> %s) produced %s, so that family is not the one actually policed" % (
                name, expected[0], forged_value, findings))


def test_the_token_census_catches_a_number_no_family_owns():
    """The census has to catch an invented figure in a shape no family looks at, and a parked exemption.

    Families police known sentences; a new sentence carrying a new number is exactly what a family list goes
    blind to, and an exemption table is exactly where an inconvenient number would get parked. Both directions
    are forged here rather than asserted in a comment.
    """
    o = _owners()
    text = _bullet()
    injected = _findings(text.replace("the corrected budget", "the 41.7 corrected budget"), o)
    assert any("unowned number '41.7'" in f for f in injected), injected
    parked_source = text.replace(UPSTREAM_EXEMPTIONS["0.952"], UPSTREAM_EXEMPTIONS["0.952"].replace("0.952", "0.4"))
    parked = _findings(parked_source, o)
    assert any("exemption for '0.952' is dead" in f for f in parked), parked
    assert any("unowned number '0.4'" in f for f in parked), parked
