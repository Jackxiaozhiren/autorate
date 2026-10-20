"""#119: the G3 contrast reaches a committed artefact, so `verify` re-derives it instead of a test printing it.

`tests/test_g3_contrast.py` measures the contrast the criterion asks for -- the ordinal SET gate refusing the
same population the one-sided severity gate certifies -- and until now every figure it produced lived only in
that run's memory: printed, asserted, and published nowhere. The `claims.G3.note` in `protocol.json` said so
out loud ("a number `tests/test_g3_contrast.py`'s builder computes in memory and prints, not a value any
artefact under `data/` publishes"), which is the honest disclosure but not a fix: G1's ceiling (#97), G4's
`delta_hat` (#107) and the drift envelope (#110) each moved from "a test checks it" to "an artefact publishes
it and the gate re-derives it", and G3 is the last criterion whose evidence is only in-memory.

What this file pins, and what it deliberately does not:

* the artefact covers the populations whose records are COMMITTED. The narrowing half of the G3 note -- the
  `shift = 0, error_rate = 0` corner where the set gate certifies and the interval top bounds the one-sided
  risk -- is generated from knobs, not read from a committed file, so its digits (`0.014867`, the 36 empty
  certified sets) keep their producer-named disclosure and no row here claims they are published.
* the refusal is the point. A set-gate refusal writes no certificate, so before this artefact the fact
  "the multiclass gate publishes nothing on this population" existed in no committed file at all; the row
  below compares it against the severity half measured on the same bytes, at the same freeze.
* every field is re-derived by production code over a committed records file, so both lanes read the same
  numbers and the corpus-less lane is not a weaker witness.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from _records import build_ordinal
from autorate import cli, report
from autorate.protocol import protocol_digest

REPO = Path(cli.__file__).resolve().parents[2]

FROZEN = json.loads((REPO / "protocol.json").read_text())
RUBRIC = {key: FROZEN["rubric"][key] for key in cli.G3_CONTRAST_RUBRIC_FIELDS}


def _committed_rows():
    """The published ordinal population, read the way the arm reads it."""
    return report.published_severity()[1]


def _doc():
    return report.read_g3_contrast(REPO / report.G3_CONTRAST_JSON, cli.G3_CONTRAST_RUBRIC_FIELDS)


# Every published field, named here as a literal rather than read back off `report.G3_CONTRAST_*_FIELDS`.
# A plant battery that iterates the arm's own lists cannot see a list shrink: drop `summary` from
# `G3_CONTRAST_SET_FIELDS` and the loop simply stops planting it, so the arm loses an opinion about a published
# figure and the suite stays green -- the same shape as a test whose expected count is `sum(len(x) for x in
# lists)` (review MAJOR). The two rows below are what tie this literal to the code: the pairs are compared
# against the field lists, so a renamed or dropped field reddens here, and the count is a number a rename
# cannot silently agree with.
PLANTED_FIELDS = [
    ("population", "records"), ("population", "n_records"), ("population", "n_cases"),
    ("population", "direction"),
    ("set_gate", "module"), ("set_gate", "feasible"), ("set_gate", "reason"), ("set_gate", "qhat"),
    ("set_gate", "autorate"), ("set_gate", "conditional_error_bound"), ("set_gate", "marginal_error_bound"),
    ("set_gate", "mean_set_size"), ("set_gate", "summary"),
    ("severity_gate", "module"), ("severity_gate", "feasible"), ("severity_gate", "reason"),
    ("severity_gate", "ahat"), ("severity_gate", "bound"), ("severity_gate", "price_bound"),
    ("severity_gate", "override_bound"), ("severity_gate", "measured_violation"), ("severity_gate", "n_cal"),
    ("severity_gate", "n_eval"), ("severity_gate", "n_cal_cases"), ("severity_gate", "n_eval_cases"),
    ("severity_gate", "summary"),
]


def _collect(tmp_path, mutate=None):
    """Run the arm inside a copied tree, optionally with a tampered artefact, and return its findings.

    The arm reads `data/g3_contrast.json` by the declared relative path and re-measures from the records and
    certificate the publication table declares, so planting a value means planting a tree: three committed
    files copied beside each other, the same set an export-lane run sees. The untampered copy is the paired
    control -- it must find nothing -- because a tamper that fires in a tree the arm cannot read at all would
    prove nothing about the field it names.
    """
    for relative in (report.G3_CONTRAST_JSON, report.SEVERITY_CERTS[report.SEVERITY_LABEL][0],
                     report.SEVERITY_CERTS[report.SEVERITY_LABEL][1]):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO / relative).read_text())
    if mutate is not None:
        path = tmp_path / report.G3_CONTRAST_JSON
        doc = json.loads(path.read_text())
        mutate(doc)
        path.write_text(json.dumps(doc))
    drift, rubric_rows = [], []
    monkey = pytest.MonkeyPatch()
    monkey.chdir(str(tmp_path))
    try:
        report.rederive_g3_contrast(
            lambda label, fresh, stored: drift.append((label, fresh, stored)) if fresh != stored else None,
            lambda label, published, promised: rubric_rows.append(label),
            cli.G3_CONTRAST_RUBRIC_FIELDS, RUBRIC)
    finally:
        monkey.undo()
    return drift, rubric_rows


def test_the_contrast_artefact_is_declared_and_its_reader_refuses_a_wrong_shape(tmp_path):
    """The table names the file, and the reader is a shape contract rather than a `json.load`."""
    assert report.G3_CONTRAST_JSON == "data/g3_contrast.json"
    assert str(report.G3_CONTRAST_MD) == "docs/G3.md"

    doc = _doc()
    assert set(doc) == {"producer", "rubric", "population", "set_gate", "severity_gate"}, set(doc)
    # One owner for the population: the contrast is measured over the records the ordinal certificate is
    # certified from, named by `SEVERITY_CERTS`, and the artefact states that path as a value the arm
    # compares rather than as a second table entry that could disagree with the first.
    assert doc["population"]["records"] == report.SEVERITY_CERTS[report.SEVERITY_LABEL][0], doc["population"]

    broken = dict(doc)
    del broken["set_gate"]
    path = tmp_path / "g3.json"
    path.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match="set_gate"):
        report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)

    extra = {**doc, "claims_g3_measured": True}
    path.write_text(json.dumps(extra))
    with pytest.raises(ValueError, match="claims_g3_measured"):
        report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)

    path.write_text("[1, 2]")
    with pytest.raises(ValueError, match="not an object"):
        report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)

    # The `rubric` block is bounded against the fields the arm consumes, not against the published superset.
    # Both directions matter and they fail differently. A block missing `alpha` is a `KeyError` in the
    # renderer and the builder -- rc 1, the one code the contract forbids. A block carrying an extra name
    # is quieter and worse: `method` is in the published superset, so the old bound let it through, the
    # renderer prints every superset name it finds, and `docs/G3.md` would publish a rule statement the arm
    # compares against nothing. This artefact measures a comparison, not a method, and ERRATA's own rule is
    # that a published figure has an owner.
    thin = json.loads(json.dumps(doc))
    del thin["rubric"]["alpha"]
    path.write_text(json.dumps(thin))
    with pytest.raises(ValueError, match="alpha"):
        report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)

    padded = json.loads(json.dumps(doc))
    padded["rubric"]["method"] = "conformal_with_extrapolation"
    path.write_text(json.dumps(padded))
    with pytest.raises(ValueError, match="method"):
        report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)
    assert "method" in report.PUBLISHED_RUBRIC_FIELDS, (
        "the superset no longer holds `method`, so the plant above proves nothing about the slack it used to")
    # Why the plant is `method` and not some invented key: the old bound subtracted the published superset, so
    # a name inside it was accepted by construction. If this line ever goes false, the plant above has stopped
    # being a witness to that hole and the row needs a different example.
    assert not set(padded["rubric"]) - set(report.PUBLISHED_RUBRIC_FIELDS), padded["rubric"]


def test_a_contrast_artefact_whose_population_has_no_cases_is_refused_before_the_renderer_divides(tmp_path):
    """`n_cases` is a published value the document divides by, so its bound has to be about its value.

    `render_g3_contrast` states how many records repeat one calibration case by dividing the published
    `n_records` by the published `n_cases`. A shape contract that names the key but not its domain lets
    `n_cases` = 0 reach that line, and `ZeroDivisionError` is not a class `cli.main` maps -- rc 1, the code
    this project's contract forbids, arrived at through a document table rather than an argument. `None` and
    `"0"` are planted beside 0 because the bound has to hold for the spellings JSON actually carries, and a
    type test that only checks `< 1` would itself raise a `TypeError`.
    """
    path = tmp_path / "g3.json"
    doc = json.loads(json.dumps(_doc()))
    for bad in (0, None, "0", True, -3):
        forged = json.loads(json.dumps(doc))
        forged["population"]["n_cases"] = bad
        path.write_text(json.dumps(forged))
        with pytest.raises(ValueError, match="n_cases"):
            report.read_g3_contrast(path, cli.G3_CONTRAST_RUBRIC_FIELDS)


def test_the_committed_contrast_is_a_re_derivation_of_the_committed_records():
    """Nothing in the file is typed: the builder over the committed records reproduces it field for field."""
    doc = _doc()
    built = report.build_g3_contrast(report.SEVERITY_CERTS[report.SEVERITY_LABEL][0], _committed_rows(),
                                     report.SEVERITY_CERTS[report.SEVERITY_LABEL][2], RUBRIC)
    assert built == {name: doc[name] for name in ("population", "set_gate", "severity_gate")}, (
        "the committed contrast is not what this build computes from the committed records")
    assert doc["producer"] == report.G3_CONTRAST_PRODUCER
    assert doc["rubric"] == RUBRIC, "the artefact records a budget the freeze did not promise"


def test_the_arm_re_derives_every_field_and_a_planted_digit_drifts_by_name(tmp_path):
    """The arm has an opinion about each published field, and a tampered one is named rather than averaged."""
    drift, rubric_rows = _collect(tmp_path)
    assert drift == [], drift
    assert rubric_rows == ["contrast %s.%s" % (report.SEVERITY_LABEL, name)
                           for name in cli.G3_CONTRAST_RUBRIC_FIELDS], rubric_rows

    # The literal list above is the arm's whole published surface, and these two rows are what make it the
    # arm's surface rather than a list that drifted from it: a field in the code but not here is a field no
    # plant ever touches, and a field here but not in the code cannot be planted at all.
    from_lists = [("population", name) for name in report.G3_CONTRAST_POPULATION_FIELDS]
    from_lists += [("set_gate", name) for name in report.G3_CONTRAST_SET_FIELDS]
    from_lists += [("severity_gate", name) for name in report.G3_CONTRAST_SEVERITY_FIELDS]
    assert sorted(PLANTED_FIELDS) == sorted(from_lists), (
        sorted(set(PLANTED_FIELDS) - set(from_lists)), sorted(set(from_lists) - set(PLANTED_FIELDS)))
    assert len(PLANTED_FIELDS) == 26, len(PLANTED_FIELDS)

    planted = 0
    for block, name in PLANTED_FIELDS:
        def mutate(doc, block=block, name=name):
            """Put a different value at the field, whatever shape the published row happens to carry.

            A planted `None` becomes a figure and a planted figure becomes `None`'s opposite: both are the
            same defect for the arm -- a published quantity that disagrees with the measurement -- and the
            refusal must name the field either way. Strings get a suffix rather than a substitution so a
            tampered `reason` still reads as a reason.
            """
            value = doc[block][name]
            if isinstance(value, bool):
                doc[block][name] = not value
            elif value is None:
                doc[block][name] = 1
            elif isinstance(value, (int, float)):
                doc[block][name] = value + 1
            else:
                doc[block][name] = value + " tampered"

        tampered = tmp_path / ("plant%d" % planted)
        tampered.mkdir(exist_ok=True)
        found, _rows = _collect(tampered, mutate)
        assert [label for label, _f, _s in found] == ["contrast %s.%s.%s" % (report.SEVERITY_LABEL, block,
                                                                              name)], (block, name, found)
        assert found[0][1] != found[0][2], (block, name)
        planted += 1
    assert planted == 26, planted


def test_the_refusal_half_publishes_no_bound_and_that_is_a_measurement_not_a_hardcode():
    """The row is live: on a population where the set gate certifies, the same builder reports bounds.

    Without the second half this file could not tell a refusal from a renderer that only ever writes
    `false`, which is the failure mode every "the gate says no" artefact in this repository has been
    audited for (#97's ceiling, #111's uncompared slice notes).
    """
    doc = _doc()
    set_gate = doc["set_gate"]
    assert set_gate["feasible"] is False and set_gate["reason"] == "empty_feasible_set", set_gate
    for field in ("qhat", "autorate", "conditional_error_bound", "marginal_error_bound", "mean_set_size"):
        assert set_gate[field] is None, (field, set_gate[field])
    severity = doc["severity_gate"]
    assert severity["feasible"] is True and severity["bound"] <= RUBRIC["alpha"], severity

    corner = build_ordinal(n=1200, seed=5, shift=0.0, error_rate=0.0, temp=1.4)
    records_path, _cert, direction = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    fresh = report.build_g3_contrast(records_path, corner, direction, RUBRIC)
    assert fresh["set_gate"]["feasible"] is True, fresh["set_gate"]["summary"]
    assert fresh["set_gate"]["marginal_error_bound"] is not None, fresh["set_gate"]
    assert fresh["set_gate"]["reason"] is None, fresh["set_gate"]["reason"]


def test_a_contrast_artefact_faced_with_two_ordinal_populations_refuses_by_name(monkeypatch, tmp_path):
    """The artefact publishes ONE population, and a table that grows a second row is the checkout's defect.

    `rederive_severity` loops per label because each label has its own artefact; the contrast has a single
    flat row set, so honouring a second label silently would put two populations' figures under one heading.
    The refusal is the same shape `report.published_severity()` already uses, and this row is what keeps the
    branch from being dead prose.
    """
    import autorate.report as report_module

    collected = []
    for rel in (report.G3_CONTRAST_JSON, report.SEVERITY_CERTS[report.SEVERITY_LABEL][0],
                report.SEVERITY_CERTS[report.SEVERITY_LABEL][1]):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO / rel).read_text())
    rows = report.published_severity()[1]
    two = dict(report_module.SEVERITY_CERTS)
    two["second"] = (report.SEVERITY_CERTS[report.SEVERITY_LABEL][0],
                     report.SEVERITY_CERTS[report.SEVERITY_LABEL][1], "over")
    monkeypatch.setattr(report_module, "SEVERITY_CERTS", two)
    monkeypatch.chdir(str(tmp_path))
    try:
        with pytest.raises(report.PublishedArtefactUnavailable, match="second"):
            report.rederive_g3_contrast(lambda label, fresh, stored: collected.append(label),
                                        lambda label, published, promised: None,
                                        cli.G3_CONTRAST_RUBRIC_FIELDS, RUBRIC)
    finally:
        monkeypatch.undo()
    assert collected == [], collected


def test_docs_g3_md_is_rendered_from_the_artefact_and_joins_the_publication_table():
    """One owner for the document: the producer's renderer is what `verify` byte-compares."""
    paths = {str(path) for path, _render in cli.PUBLISHED_DOCS}
    assert "docs/G3.md" in paths, paths
    rendered = report.render_g3_contrast(_doc())
    assert rendered == (REPO / "docs/G3.md").read_text(), "the published document drifted from its artefact"
    text = rendered
    assert report.G3_CONTRAST_JSON in text and "empty_feasible_set" in text
    # The verdict is stated by the document's one owner (`report._verdict_text`, which `_verdict_cell`
    # delegates to), and the absent bounds are spelled the way the artefact spells them. Both are pinned
    # because the sentence above them says `null`: a renderer that printed Python's `None` beside a paragraph
    # about `null` would have the document disagree with itself, and a second verdict spelling would drift
    # from `docs/RESULTS.md` exactly the way #38 describes.
    assert "**NOT_CERTIFIABLE** (empty_feasible_set)" in text, text
    assert "**certified**" in text, text
    assert "`None`" not in text and "`False`" not in text, text
    # The sentence naming the certified figure had lost its middle clause to an earlier bulk edit, and the
    # published document shipped the wreckage -- `docs/G3.md` read "not the budget it sits" and then started
    # "is the half a membership bound cannot carry". No existing row in this file can see that: the digits are
    # all still present, just not inside a sentence. Pinned as a clause, and the values inside it are read
    # from the artefact, so the row proves the document states the price beside the bound instead of
    # trailing off mid-predicate.
    assert "are the always-report rule's cost, which is" in text, text
    assert "it sits\nis the half" not in text, text
    # The narrowing stays stated, because the document that publishes the contrast is where a reader who has
    # only this file would otherwise over-read it.
    assert "not_measured" in text, text
    assert "0.014867" not in text, "a corner-population digit belongs to its producer, not to this document"


def test_only_certificate_tables_publish_a_protocol_digest(tmp_path):
    """A `meta.protocol_digest` belongs to a certificate, and the tree agrees.

    `t96/restamp.py` enforces this from outside the repository and caught this round's first draft, which had
    given the contrast artefact a stamp: among the files under `data/`, the ones carrying that key are exactly the
    certificates the publication tables name. Asserting the set equality rather than writing a count in prose is
    deliberate -- the count was wrong the moment this round added a file, which is exactly how a remembered figure
    goes stale, and rule 6 wants something that re-derives it.

    The plant proves the row can fail: a forged stamp is added to a measurement artefact in a copied tree and the
    same walk names it. Copied rather than in place, because no test writes into committed bytes.
    """
    def stamped_under(root):
        found = {}
        for path in sorted((root / "data").glob("*.json")):
            try:
                doc = json.loads(path.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            meta = doc.get("meta") if isinstance(doc, dict) else None
            if isinstance(meta, dict) and "protocol_digest" in meta:
                found[path.name] = meta["protocol_digest"]
        return found

    declared = set(report.CERTS.values()) | {cert for _rec, cert in report.MASSIVE_CERTIFICATES.values()}
    declared |= {cert for _rec, cert, _dir in report.SEVERITY_CERTS.values()}
    declared_names = {Path(rel).name for rel in declared}

    on_disk = stamped_under(REPO)
    assert {name for name, _digest in on_disk.items()} == declared_names, (
        sorted(set(on_disk) - declared_names), sorted(declared_names - set(on_disk)))
    assert all(digest == protocol_digest(FROZEN) for _name, digest in on_disk.items()), (
        "a stamped artefact carries another freeze's digest")

    for rel in sorted(declared | {report.G1_FEASIBILITY_JSON}):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO / rel).read_text())
    measurement = tmp_path / report.G1_FEASIBILITY_JSON
    forged = json.loads(measurement.read_text())
    forged["meta"] = {"protocol_digest": protocol_digest(FROZEN)}
    measurement.write_text(json.dumps(forged))
    forged_tree = stamped_under(tmp_path)
    assert "g1_feasibility.json" in forged_tree, sorted(forged_tree)
    assert sorted(set(forged_tree) - declared_names) == ["g1_feasibility.json"], sorted(forged_tree)


def test_a_certifying_set_gate_row_is_not_rendered_as_a_silence():
    """The document may call the bounds `null` only when the row it prints is null.

    The renderer asserted the silence above the figures unconditionally, so a certifying population would
    print a bound under a sentence saying no bound exists -- the same defect class as a claim note quoting a
    moved number, only inside a generated document, and with the same fix: read the value.
    """
    doc = json.loads(json.dumps(_doc()))
    doc["set_gate"]["feasible"] = True
    doc["set_gate"]["reason"] = None
    doc["set_gate"]["qhat"] = 0.42
    text = report.render_g3_contrast(doc)
    assert "Every headline bound of the shape is `null`" not in text, text
    assert "4 of the 5 headline bounds this shape carries are `null` and 1 hold a figure" in text, text
    assert "`qhat`: `0.42`" in text, text
    assert "Every headline bound of the shape is `null`" in report.render_g3_contrast(_doc())


def test_a_contrast_artefact_whose_rubric_omits_a_consumed_field_is_a_named_refusal(tmp_path):
    """A `rubric` block missing `beta` is rc-4 territory naming the key, never a `KeyError` at rc 1.

    Same defect as the reader rows above, driven from the other side: this one walks `rederive_g3_contrast`,
    so it proves the refusal arrives through `load_published`'s wrap -- the path the gate itself takes --
    rather than only through a direct call. Without the bound the lookup reached `chosen[name]` and the
    builder and raised `KeyError`, `cli.main` maps no `KeyError`, and `verify` escaped at the one code the
    contract forbids: the review's point that this round's first rc 1 was fixed at a call site rather than
    guarded against the shape.
    """
    for rel in (report.G3_CONTRAST_JSON, report.SEVERITY_CERTS[report.SEVERITY_LABEL][0],
                report.SEVERITY_CERTS[report.SEVERITY_LABEL][1]):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO / rel).read_text())
    path = tmp_path / report.G3_CONTRAST_JSON
    doc = json.loads(path.read_text())
    del doc["rubric"]["beta"]
    path.write_text(json.dumps(doc))
    monkey = pytest.MonkeyPatch()
    monkey.chdir(str(tmp_path))
    try:
        with pytest.raises(report.PublishedArtefactUnavailable, match="beta"):
            report.rederive_g3_contrast(lambda label, fresh, stored: None,
                                        lambda label, published, promised: None,
                                        cli.G3_CONTRAST_RUBRIC_FIELDS, RUBRIC)
    finally:
        monkey.undo()


def test_the_producer_refuses_an_unwritable_destination_at_two_not_as_a_traceback(tmp_path):
    """`--out` is an argument the operator named, so its failure is rc 2 with nothing written.

    The write used to sit outside the refusals, and an `OSError` there escaped as a traceback at rc 1 on the
    input `tools/g1_feasibility.py` answers with 2 -- one contract, two producers, one of them wrong. A
    read-only directory rather than a missing parent, because `mkdir` is inside the same guard.
    """
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        result = subprocess.run([sys.executable, str(REPO / "tools/g3_contrast.py"),
                                 "--out", str(locked / "g3.json")], capture_output=True, text=True,
                                cwd=str(REPO))
    finally:
        locked.chmod(0o700)
    assert result.returncode == cli.EXIT_USAGE, (result.returncode, result.stdout, result.stderr)
    assert "Traceback" not in result.stderr, result.stderr
    assert "nothing was written" in result.stderr, result.stderr
    assert not (locked / "g3.json").exists(), "a refused producer wrote anyway"


def test_the_g3_claim_row_names_the_artefact_and_every_path_it_lists_exists():
    """The protocol's artefact list is a pointer set, so a phantom path is a refusal this row can catch."""
    claims = {claim["id"]: claim for claim in FROZEN["claims"]}
    row = claims["G3"]
    assert report.G3_CONTRAST_JSON in row["artefacts"], row["artefacts"]
    assert "docs/G3.md" in row["artefacts"], row["artefacts"]
    for artefact in row["artefacts"]:
        assert (REPO / artefact).exists(), artefact
    assert row["status"] == "not_measured", (
        "the criterion is worded as the wider claim, which the corner measurement contradicts; publishing the "
        "contrast makes its evidence re-derivable, and this row says so rather than re-defining the status")
    assert "data/g3_contrast.json" in row["note"], row["note"]


def test_the_producer_refuses_a_run_that_would_publish_the_wrong_population(tmp_path):
    """`tools/g3_contrast.py` is a build script, but what it writes is a published artefact.

    `--records` defaults to the published population, and a run that names a different file while writing
    the published path would put another population's figures under a name that promises this one -- the
    misattribution `cmd_severity --doc` and `g1_feasibility --doc` both refuse. Nothing may be written by a
    refused run, which is the half of this row that a code-path-only reading would miss.
    """
    other = tmp_path / "other.jsonl"
    other.write_text("")
    out = tmp_path / "g3.json"
    result = subprocess.run([sys.executable, str(REPO / "tools/g3_contrast.py"), "--records", str(other),
                             "--out", str(out), "--force"], capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == cli.EXIT_USAGE, (result.returncode, result.stdout, result.stderr)
    assert "records_ordinal_synthetic" in result.stderr, result.stderr
    assert not out.exists(), "a refused producer left an artefact on disk"
