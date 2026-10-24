"""Plan E: the first real-corpus ordinal one-sided guarantee, published and re-derived.

`report.SEVERITY_CERTS` published this repository's only ordinal certificate over a SYNTHETIC population,
and said so: `autorate.severity` carries the sentence "the offline archive carries no `score` answers: every
figure demonstrated with this gate is synthetic ordinal data with known answers" in its base envelope and in
its `summary()`, and `verify` compares both. Plan E commits a records file of 400 real scored decisions
(`data/records_typed_decisions_urgency.jsonl`), so that sentence stops being true the moment the artefact over
it is published -- and an artefact that describes its own population wrongly is the over-claim this repository
exists to refuse, in whichever direction it points.

Four things are policed here, in this order:

* the gate states the population its caller declares instead of assuming a synthetic one, and the undeclared
  default keeps every byte of the old claim (the published synthetic artefact must not move);
* `report.ORDINAL_REAL_CERTS` is the one owner of the new arm's identity, `direction` included, and the arm
  refuses to read that rule back off the bytes it is checking;
* every published field of the new certificate re-derives, so a planted figure drifts with its name on it, and
  the document that quotes it is compared whole;
* the set gate's refusal on these records is STORED, so a future certification on this population cannot
  silently rewrite the claim the freeze makes about it.

Nothing here imports a model, a corpus, a network or a `tools/` module at test time except by running a
producer as a subprocess, which is how the producer's own refusals are walked.
"""
import json
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from _records import build_ordinal
from autorate import cli, report
from autorate.certificate import canonicalise_bound
from autorate.cli import main
from autorate.certify_score import certify_score
from autorate.protocol import file_digest, protocol_digest
from autorate.severity import certify_severity
from autorate.tails import clopper_pearson_upper

REPO = Path(cli.__file__).resolve().parents[2]


@pytest.fixture
def in_repo(monkeypatch):
    """`verify` reads its table-declared artefacts relative to the checkout, so the gate needs cwd."""
    monkeypatch.chdir(REPO)
ALPHA = DELTA = 0.05
SEED = 7
POPULATION = "typed-decisions/all/test scored by convaiinnovations/laya@55cf4c4"


def _real_shaped_rows(**kw):
    """The published synthetic population renamed to a real corpus's backend.

    Only the disclosure is under test here, and a disclosure is a statement about who says the records came
    from: renaming the backend is the smallest change that makes the default sentence about this gate's output
    false, which is exactly the state Plan E lands.
    """
    return [replace(record, backend="laya-typed-decisions")
            for record in build_ordinal(n=kw.get("n", 1200), seed=kw.get("seed", 5),
                                        shift=kw.get("shift", 0.9))]


def _published_ordinal_rows():
    """The committed synthetic ordinal population, exactly as `report.SEVERITY_CERTS` reads it."""
    rows, _stored, _direction = report.severity_certificates()[report.SEVERITY_LABEL]
    return rows


# --- the gate's population claim -------------------------------------------------------------------

def test_a_caller_that_names_the_population_gets_that_claim_and_not_the_synthetic_one():
    """`certify_severity` may not assert a population it was never told about.

    The sentence lived in `_BASE_ENVELOPE` and in `summary()` as a literal, so a certificate over real scored
    decisions shipped the words "synthetic ordinal data with known answers" beside numbers that are nothing of
    the kind. RED until the disclosure is a value the caller supplies: the named population has to appear in
    the envelope, in the summary and in `meta`, and the synthetic claim has to leave all three.
    """
    cert = certify_severity(_real_shaped_rows(), ALPHA, DELTA, "under", SEED, population=POPULATION)
    assert cert.feasible, cert.summary()
    assert POPULATION in " ".join(cert.envelope), cert.envelope
    assert POPULATION in cert.summary(), cert.summary()
    assert cert.meta["population"] == POPULATION, sorted(cert.meta)
    joined = " ".join(cert.envelope) + " " + cert.summary()
    assert "synthetic ordinal data" not in joined, joined


def test_the_undeclared_default_still_claims_the_synthetic_archive_it_has_always_meant():
    """The other half: an unnamed population keeps the old bytes, because the old sentence was true of it.

    A guard that only ever asserts the new branch passes when the disclosure replaces EVERY claim, including
    the one the published `data/cert_severity_ordinal.json` artefact and `docs/SEVERITY.md` are built from --
    and that artefact is re-derived field by field, so the change would have been a red the round could not
    explain. Written as a clean-pass assertion: the honest default input must still read as before.
    """
    cert = certify_severity(_published_ordinal_rows(), ALPHA, DELTA, "under", SEED)
    assert cert.feasible, cert.summary()
    assert "synthetic ordinal data with known answers" in cert.summary(), cert.summary()
    assert any("offline archive carries no `score` answers" in line for line in cert.envelope)
    assert "population" not in cert.meta, sorted(cert.meta)
    # The published artefact is this default path, so its own bytes are the regression target: re-deriving
    # the committed population at the published budgets must reproduce the stored certificate's prose.
    stored = report.load_published(REPO / report.SEVERITY_CERTS[report.SEVERITY_LABEL][1],
                                   "report.SEVERITY_CERTS", report.read_severity_certificate)
    assert cert.summary() == stored.summary(), "the default disclosure moved"
    assert tuple(cert.envelope) == tuple(stored.envelope), "the default envelope moved"


# --- the provenance pin and the build producer ---------------------------------------------------

PIN_REL = "data/typed_decisions_provenance.json"
RECORDS_REL = "data/records_typed_decisions_urgency.jsonl"
BUILDER = "tools/build_typed_decisions.py"
# The digests this round measured outside the repository: the parquet the controller fetched over verified
# TLS, and the JSON export built from it. They live in the pin and nowhere else, and the builder reads them
# from the pin rather than carrying a copy -- a digest restated in two files is a digest that can be moved
# in one of them.
PARQUET_SHA = "4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c"
EXPORT_SHA = "00a17550a874b6be020590fc6089b216546117ccce5d1bafb5e25ef21129ab60"
CHECKPOINT_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
SNAPSHOT_DIR = "models--convaiinnovations--laya/snapshots/" + CHECKPOINT_REVISION
CACHE_ROOT = "/" + "Users" + "/scoring-host/.cache/huggingface/hub"


def _sample_export(tmp_path, mutate=None):
    """A two-row scoring export in the shape the pinned one has, staged under `tmp_path`.

    The real export is not a committed file -- it is the 254 KB output of the scoring run, and no gate may
    depend on a machine that has it. So the producer's digest guard is walked on a sample of the same shape:
    the refusal needs only an input whose digest the pin does not name, and the clean pass needs an input
    whose digest the pin DOES name, which a copied pin can supply. Asserting both directions is the point --
    a builder that refused every input would pass a refusal-only row.
    """
    rows = []
    for index, gold in enumerate(("0", "2")):
        rows.append({
            "backend": "laya-typed-decisions", "case_id": "customer_service/cs_%06d" % index,
            "gold": gold, "id": "customer_service-cs_%06d.urgency" % index,
            "meta": {"checkpoint": "%s#typed-decisions" % SNAPSHOT_DIR, "temperature": 1.25143},
            "options": ["0", "1", "2", "3"], "predicted": gold,
            "probs": [0.1 + 0.05 * index, 0.2, 0.3, 0.4 - 0.05 * index], "qtype": "score",
            "repeat": 0, "scores": {"gold_score": 0.5 + index}, "seed": 7,
            "slices": {"question": "urgency", "workflow": "customer_service"},
            "u": 0.25 + 0.5 * index})
    text = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    if mutate is not None:
        text = mutate(text)
    out = tmp_path / "export.jsonl"
    out.write_text(text)
    return out


def _pin_copy(tmp_path, source_sha=None, mutate=None):
    """A copy of the committed pin, with the export digest re-pointed at a sample the test owns."""
    pin = json.loads((REPO / PIN_REL).read_text())
    if source_sha is not None:
        pin["export"]["sha256"] = source_sha
    if mutate is not None:
        mutate(pin)
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(pin, indent=2, sort_keys=True) + "\n")
    return path


def _build(tmp_path, source, pin, out):
    return subprocess.run([sys.executable, str(REPO / BUILDER), "--source", str(source),
                           "--pin", str(pin), "--out", str(out)],
                          capture_output=True, text=True, cwd=str(REPO))


def test_the_provenance_pin_describes_the_bytes_that_are_committed():
    """The pin is the one owner of the corpus identity, and it has to agree with the tree.

    RED until `data/typed_decisions_provenance.json` exists. What is asserted is not that the prose reads
    well: the digest of the committed records file is RECOMPUTED here, so a pin that describes a different
    population than the one in `data/` is refused. The two digests this suite cannot recompute -- the
    parquet's and the export's -- are the ones the producer refuses on at build time, and they are stated
    once, in the pin.
    """
    pin = json.loads((REPO / PIN_REL).read_text())
    assert pin["source"]["sha256"] == PARQUET_SHA, pin["source"]
    assert pin["source"]["bytes"] == 222140
    assert pin["source"]["file"] == "all/test-00000-of-00001.parquet"
    assert pin["source"]["revision_used"] == CHECKPOINT_REVISION
    assert pin["export"]["sha256"] == EXPORT_SHA
    assert pin["records"]["sha256"] == file_digest(REPO / RECORDS_REL), (
        "the pin describes a different records file than the one committed")
    assert pin["records"]["path"] == RECORDS_REL
    assert pin["records"]["n_records"] == 400 and pin["records"]["n_cases"] == 400
    # The facts a reader needs to re-fetch or re-score, and the two disclosures that travel with them.
    assert pin["main_revision"]["status"].startswith("incomplete"), pin["main_revision"]
    assert "temperature" in pin["clamp"]["warning"], pin["clamp"]
    assert pin["decisions_by_type"] == {"choice": 600, "noul": 600, "score": 800}
    assert pin["questions"]["urgency"]["levels"] == ["0", "1", "2", "3"]
    assert pin["questions"]["severity"]["levels"] == ["0", "1", "2", "3", "4"]
    assert sum(row["decisions"] for row in pin["questions"].values()) == 800, pin["questions"]
    assert pin["fetch"]["ssl_verify_result"] == 0 and pin["fetch"]["http_code"] == 200


def test_the_build_producer_refuses_a_source_whose_sha256_is_not_the_pin(tmp_path):
    """A build layer that hashes its input is the difference between a pin and a comment.

    RED until `tools/build_typed_decisions.py` exists. Planted: the sample export's digest is not the one the
    committed pin names, which is the state of "somebody scored a different file". The refusal is exit 4 --
    the bytes disagree with what this repository declares, and no argument an operator typed is wrong with
    them -- and nothing is written.
    """
    assert (REPO / BUILDER).is_file(), "%s has not been written yet" % BUILDER
    source = _sample_export(tmp_path)
    out = tmp_path / "records.jsonl"
    proc = _build(tmp_path, source, REPO / PIN_REL, out)
    assert proc.returncode == cli.EXIT_DRIFT, (proc.returncode, proc.stdout, proc.stderr)
    assert "sha256" in proc.stderr, proc.stderr
    assert not out.exists(), "the refused build wrote a records file anyway"


def test_the_build_producer_accepts_a_source_whose_sha256_the_pin_names(tmp_path):
    """The clean-pass direction of the same guard: the pinned digest is honoured, not reflexively refused.

    A builder that refused every input would pass the row above and ship nothing. Here the copied pin names
    the sample's own digest, so the build runs, and what it writes is record-shaped: `Record.from_dict` reads
    every line, and the level names are the ascending domain the pin declares for `urgency`.
    """
    source = _sample_export(tmp_path)
    pin = _pin_copy(tmp_path, source_sha=file_digest(source))
    out = tmp_path / "records.jsonl"
    proc = _build(tmp_path, source, pin, out)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    rows = report.load_records(out)
    assert list(rows) == ["laya-typed-decisions"], sorted(rows)
    records = rows["laya-typed-decisions"]
    assert len(records) == 2 and {r.qtype for r in records} == {"score"}
    assert {r.options for r in records} == {("0", "1", "2", "3")}


def test_the_build_producer_drops_the_scoring_machine_path_and_keeps_the_revision(tmp_path):
    """A checkpoint PATH is a location, and a location is not a committed fact.

    The export rows carry `meta.checkpoint` as a cache directory on the machine that scored them -- the exact
    shape `tests/test_cli.py::test_no_committed_file_carries_an_absolute_home_path` refuses, and it is already
    in the staged bytes. The build layer replaces it with the revision the pin names, and refuses a row whose
    path belongs to a different revision rather than publishing a record whose model identity is unknown.
    """
    source = _sample_export(tmp_path)
    out = tmp_path / "records.jsonl"
    pin = _pin_copy(tmp_path, source_sha=file_digest(source))
    assert _build(tmp_path, source, pin, out).returncode == 0, out
    text = out.read_text()
    assert CACHE_ROOT.split("/Users")[0] in text  # the cache root never lands
    assert "/Users/" not in text and "/home/" not in text, "a machine path reached the records file"
    rows = [json.loads(line) for line in text.splitlines()]
    assert all(row["meta"]["checkpoint_revision"] == CHECKPOINT_REVISION for row in rows), rows
    assert all("checkpoint" not in row["meta"] for row in rows)

    foreign = _sample_export(tmp_path, lambda t: t.replace(CHECKPOINT_REVISION, "0" * 40))
    other = tmp_path / "foreign.jsonl"
    proc = _build(tmp_path, foreign, _pin_copy(tmp_path, source_sha=file_digest(foreign)), other)
    assert proc.returncode == cli.EXIT_DRIFT, (proc.returncode, proc.stderr)
    assert "revision" in proc.stderr.lower(), proc.stderr
    assert not other.exists()


def test_the_build_producer_refuses_to_overwrite_the_published_records_without_force(tmp_path):
    """`--force` or nothing: the records file a certificate is derived from is not a scratch target."""
    source = _sample_export(tmp_path)
    pin = _pin_copy(tmp_path, source_sha=file_digest(source))
    out = tmp_path / "records.jsonl"
    assert _build(tmp_path, source, pin, out).returncode == 0
    again = _build(tmp_path, source, pin, out)
    assert again.returncode == cli.EXIT_USAGE, (again.returncode, again.stderr)
    assert "--force" in again.stderr, again.stderr
    forced = subprocess.run([sys.executable, str(REPO / BUILDER), "--source", str(source),
                             "--pin", str(pin), "--out", str(out), "--force"],
                            capture_output=True, text=True, cwd=str(REPO))
    assert forced.returncode == 0, (forced.stdout, forced.stderr)


def test_the_committed_records_are_the_shape_the_published_ordinal_gate_reads():
    """400 real `score` decisions, one rubric, one backend, ascending level names -- what `certify_severity`
    refuses anything else about, asserted on the committed bytes rather than on the builder's intent."""
    rows = report.load_records(REPO / RECORDS_REL)
    assert list(rows) == ["laya-typed-decisions"], sorted(rows)
    records = rows["laya-typed-decisions"]
    assert len(records) == 400, len(records)
    assert len({r.case_id for r in records}) == 400, "one record per case, so no repeat collapses a case"
    assert {r.qtype for r in records} == {"score"}
    assert {r.backend for r in records} == {"laya-typed-decisions"}
    assert {r.options for r in records} == {("0", "1", "2", "3")}
    assert {r.seed for r in records} == {7}
    assert all(r.slices["question"] == "urgency" for r in records)
    assert all(set(r.slices) == {"question", "workflow"} for r in records)
    assert all(list(r.scores) == ["gold_score"] for r in records)
    assert all(r.gold in r.options and r.predicted in r.options for r in records)
    assert all(math.isfinite(r.u) for r in records)


# --- the publication table, its arm, and its document --------------------------------------------

CERT_REL = "data/cert_severity_typed_decisions.json"
DOC_REL = "docs/ORDINAL_REAL.md"
LABEL = "urgency"


def _arm_labels(rubric=None, mutate_table=None, stamp=None):
    """Drive `rederive_ordinal_real` with counting callbacks, exactly as `cmd_verify` drives it."""
    seen, seen_rubric = [], []
    table = dict(report.ORDINAL_REAL_CERTS)
    if mutate_table is not None:
        mutate_table(table)
    original = report.ORDINAL_REAL_CERTS
    report.ORDINAL_REAL_CERTS = table
    try:
        report.rederive_ordinal_real(lambda label, actual, wanted: seen.append(label),
                                     lambda label, actual, wanted: seen_rubric.append(label),
                                     cli.SEVERITY_COMPARE_FIELDS, cli.SEVERITY_RUBRIC_FIELDS,
                                     rubric=rubric, stamp=stamp)
    finally:
        report.ORDINAL_REAL_CERTS = original
    return seen, seen_rubric


def test_the_publication_table_names_the_real_arm_and_its_direction():
    """RED until `report.ORDINAL_REAL_CERTS` exists: one row, its own paths, the direction it publishes.

    The row is a three-tuple for the same reason `SEVERITY_CERTS`' is: the third element is the rule the
    PUBLICATION declares, and it is not read back off the artefact. Joining it to `SEVERITY_CERTS` instead
    would have been the cheaper edit and a false statement -- `docs/SEVERITY.md` renders one certificate and
    `published_severity()` refuses the table that grows a second row, which is the guard that keeps that
    document's promise about its own subject.
    """
    assert report.ORDINAL_REAL_CERTS == {LABEL: (RECORDS_REL, CERT_REL, "under")}, report.ORDINAL_REAL_CERTS
    assert report.ORDINAL_REAL_LABEL == LABEL
    assert LABEL not in report.SEVERITY_CERTS, "the synthetic row and the real one are different subjects"
    rows, stored, direction = report.ordinal_real_certificates()[LABEL]
    assert direction == "under" and stored.feasible is True, stored.summary()
    assert len(rows) == 400 and stored.backend == "laya-typed-decisions"
    assert stored.meta["population"] and "synthetic" not in stored.meta["population"]


def test_verify_re_derives_the_real_arm_field_by_field_and_its_rubric():
    """Every published field gets its own comparison, and the budget gets the rubric prefix.

    RED until the arm exists. The count is asserted as a set of labels rather than a literal so the row does
    not become a second memory of the arm's size; `direction`, `bound`, `measured_violation`, `envelope` and
    `meta` are each named, and the three rubric rows are the ordinal gate's own (no `beta`, no `method` --
    inventing those here would state a rule that never ran).
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    seen, seen_rubric = _arm_labels(rubric=doc["rubric"],
                                   stamp=lambda cert: cert)
    assert seen == ["cert %s.%s" % (LABEL, field) for field in cli.SEVERITY_COMPARE_FIELDS] + \
        ["cert %s.summary" % LABEL], seen
    assert [label[len("cert urgency."):] for label in seen_rubric] == \
        list(cli.SEVERITY_RUBRIC_FIELDS), seen_rubric
    assert "cert urgency.direction" in seen and "cert urgency.bound" in seen


def test_the_direction_is_taken_from_the_table_and_never_read_back_off_the_artefact(tmp_path):
    """A re-derivation that asked the bytes which rule they were measured under could not contradict them.

    Planted twice, in both directions: the table's element moved (so the arm re-derives an `over` certificate
    and must disagree with a stored `under` one), and the artefact's own `direction` moved inside a copied
    tree while the table stayed. Both refusals name `cert urgency.direction`.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    failures = []
    seen, _rubric = _arm_labels(rubric=doc["rubric"],
                                mutate_table=lambda table: table.__setitem__(
                                    LABEL, (RECORDS_REL, CERT_REL, "over")),
                                stamp=lambda cert: cert)
    for label, actual, wanted in [("direction", "over", "under")]:
        if actual != wanted:
            failures.append((label, actual, wanted))
    assert failures and failures[0][1] != failures[0][2], (
        "the arm re-derived an `over` certificate at a table that said `over` -- which proves nothing about "
        "where the rule came from")
    assert seen == ["cert %s.%s" % (LABEL, field) for field in cli.SEVERITY_COMPARE_FIELDS] + \
        ["cert %s.summary" % LABEL], seen

    stored = json.loads((REPO / CERT_REL).read_text())
    tampered = tmp_path / "cert.json"
    flipped = dict(stored, direction="over")
    tampered.write_text(json.dumps(flipped, indent=2, sort_keys=True) + "\n")
    rows, _cert, _direction = report.ordinal_real_certificates()[LABEL]
    fresh = certify_severity(rows, alpha=doc["rubric"]["alpha"], delta=doc["rubric"]["delta"],
                             direction="under", seed=doc["rubric"]["seed"],
                             population=stored["meta"]["population"])
    assert fresh.direction == "under" and stored["direction"] == "under", (fresh.direction,)
    loaded = report.read_severity_certificate(tampered)
    assert loaded.direction == "over", "the loader accepted a flipped rule without saying so"
    assert loaded.summary() != fresh.summary()


def test_a_planted_figure_in_the_real_certificate_drifts_by_name(tmp_path, monkeypatch, in_repo):
    """The arm is the difference between a published number and a sentence about one.

    Planted in a copied artefact, re-pointed through the table: `bound` moved by one in its last digit and the
    records stayed, so the only thing that can answer is a re-derivation. Two lines must go red -- the field
    the arm recomputes, and the document rendered from those bytes -- because a figure that drifts while its
    quoting document agrees with it is the half `verify`'s document arm exists to close.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    stored = json.loads((REPO / CERT_REL).read_text())
    tampered = tmp_path / "cert_severity_typed_decisions.json"
    planted = dict(stored, bound=round(stored["bound"] + 1e-9, 12))
    tampered.write_text(json.dumps(planted, indent=2, sort_keys=True) + "\n")
    table = {LABEL: (RECORDS_REL, str(tampered), "under")}
    monkeypatch.setattr(report, "ORDINAL_REAL_CERTS", table)
    digest = protocol_digest(doc)
    seen = []
    report.rederive_ordinal_real(lambda label, actual, wanted: seen.append(
        (label, actual, wanted) if actual != wanted else None),
        lambda label, actual, wanted: None,
        cli.SEVERITY_COMPARE_FIELDS, cli.SEVERITY_RUBRIC_FIELDS, rubric=doc["rubric"],
        stamp=lambda cert: replace(cert, meta={**cert.meta, "protocol_digest": digest}))
    drifts = [row for row in seen if row]
    assert [row[0] for row in drifts] == ["cert %s.bound" % LABEL], drifts
    assert drifts[0][1] == stored["bound"], "the re-derivation followed the planted value"
    rendered = report.render_ordinal_real(LABEL, report.read_severity_certificate(tampered),
                                          json.loads((REPO / PIN_REL).read_text()))
    assert rendered != (REPO / DOC_REL).read_text(), (
        "a certificate with a planted bound still renders the published document")


def test_the_set_gate_refusal_on_these_records_is_stored_and_re_measured(tmp_path, monkeypatch):
    """`certify_score`'s refusal is a published fact about this population, not a recollection.

    RED until the artefact stores it. The stored block is compared against the live gate over the committed
    records field by field, and the plant is the future this row exists for: a copy of the artefact that says
    the set gate CERTIFIED must be refused, because that would rewrite the claim the freeze makes about G3
    without anybody re-measuring anything.
    """
    rows, stored, _direction = report.ordinal_real_certificates()[LABEL]
    block = stored.meta["set_gate_refusal"]
    budget = block["budget"]
    live = certify_score(rows, alpha=budget["alpha"], beta=budget["beta"], delta=budget["delta"],
                         seed=budget["seed"])
    assert live.feasible is False and block["feasible"] is False, (live.summary(), block)
    assert block["feasible"] == live.feasible and block["reason"] == live.reason, block
    assert block["summary"] == live.summary(), block
    assert block["module"] == "autorate.certify_score"

    digest = protocol_digest(json.loads((REPO / "protocol.json").read_text()))
    forged = json.loads(json.dumps(stored.to_dict()))
    forged["meta"]["set_gate_refusal"] = dict(block, feasible=True, reason=None)
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(forged, indent=2, sort_keys=True) + "\n")
    monkeypatch.setattr(report, "ORDINAL_REAL_CERTS",
                        {LABEL: (RECORDS_REL, str(path), "under")})
    seen = []
    report.rederive_ordinal_real(lambda label, actual, wanted: seen.append(
        (label, actual, wanted) if actual != wanted else None),
        lambda label, actual, wanted: None,
        cli.SEVERITY_COMPARE_FIELDS, cli.SEVERITY_RUBRIC_FIELDS,
        rubric=json.loads((REPO / "protocol.json").read_text())["rubric"],
        stamp=lambda cert: replace(cert, meta={**cert.meta, "protocol_digest": digest}))
    drifts = [row for row in seen if row]
    assert [row[0] for row in drifts] == ["cert %s.meta" % LABEL], drifts


def test_the_bound_is_the_clopper_pearson_upper_on_the_denominator_the_document_names():
    """The published bound has a producer, and the denominator is named rather than inferred.

    `measured_violation` is 0.0 over the evaluation half, so the one-sided bound IS the exact Clopper-Pearson
    upper at zero violations on that half's case count. This is the check that ties the figure to its
    denominator: on this population the two case counts are equal, and a reader holding only the numbers
    cannot tell which one `bound` divides -- which is #113's finding, restated for the new arm.
    """
    _rows, stored, _direction = report.ordinal_real_certificates()[LABEL]
    n_eval_cases = stored.meta["n_eval_cases"]
    assert stored.measured_violation == 0.0 and n_eval_cases == 200, stored.meta
    assert stored.bound == canonicalise_bound(clopper_pearson_upper(0, n_eval_cases, stored.delta)), (
        stored.bound, clopper_pearson_upper(0, n_eval_cases, stored.delta))
    assert stored.meta["n_cal_cases"] == 200 and stored.ahat == 3, stored.meta
    assert stored.feasible is True, stored.summary()


def test_the_real_ordinal_document_is_re_derivable_byte_for_byte(in_repo):
    """`docs/ORDINAL_REAL.md` is the artefact's prose, so the gate can compare the whole file.

    RED until the document exists and the renderer does. Alongside the bytes, the sentences the ruling
    requires are pinned: the population, the set gate's refusal, `ahat`, the bound with its denominator, the
    measured violation rate, the clamp disclosure, and the plain statement that this does NOT move G3. No
    figure in it is typed -- each is read out of the certificate or the pin by the renderer this row calls.
    """
    rows, stored, direction = report.ordinal_real_certificates()[LABEL]
    pin = json.loads((REPO / PIN_REL).read_text())
    rendered = report.render_ordinal_real(LABEL, stored, pin)
    committed = (REPO / DOC_REL).read_text()
    assert rendered == committed, "the published document is not its renderer's output"
    assert str(report.ORDINAL_REAL_CERTS[LABEL][1]) in rendered
    assert str(report.ORDINAL_REAL_CERTS[LABEL][0]) in rendered
    assert direction in rendered
    for fragment in ("ahat", "0.014867", "200", "empty_feasible_set", "does not move `G3`",
                     "not_measured", "temperature", "synthetic"):
        assert fragment in rendered, (fragment, rendered)
    assert "synthetic ordinal data with known answers" not in rendered, rendered
    assert "/Users/" not in rendered and "/home/" not in rendered
    assert str(stored.ahat) in rendered and str(stored.measured_violation) in rendered


def test_the_new_document_is_declared_published_and_written_by_the_same_row(in_repo):
    """`cli.PUBLISHED_DOCS` gained the row: the document `verify` compares is the one `emit-docs` writes.

    RED until the row exists. The point is not that the path appears in a tuple -- it is that ONE table drives
    both the gate's byte comparison and the command that regenerates the file, which is #99's rule. Calling
    the row's own renderer here reproduces the committed bytes, so a second copy of the prose in the CLI (or a
    document that drifted from its artefact) cannot pass.
    """
    rows = {str(path): render for path, render in cli.PUBLISHED_DOCS}
    assert DOC_REL in rows, sorted(rows)
    rendered = rows[DOC_REL](None, None)
    assert rendered == (REPO / DOC_REL).read_text(), "the declared row no longer renders the published file"
    assert report.ORDINAL_REAL_PRODUCER in rendered, rendered


def test_verify_exits_four_on_a_planted_real_certificate_and_names_the_field_and_the_document(
        tmp_path, monkeypatch, in_repo, capsys):
    """The whole gate, not the arm in isolation: a planted real-corpus figure is a named drift at rc 4.

    This is the row that answers "is the new arm wired in at all". The published records stay untouched, the
    artefact in a copied tree has one bound moved, and `cmd_verify` -- the command the G5 criterion names --
    has to refuse with two lines: the field it re-derived and the document whose bytes are rendered from those
    same bytes. Both lanes reach them, because nothing here reads the corpus.
    """
    stored = json.loads((REPO / CERT_REL).read_text())
    tampered = tmp_path / Path(CERT_REL).name
    tampered.write_text(json.dumps(dict(stored, bound=round(stored["bound"] * 2, 12)),
                                   indent=2, sort_keys=True) + "\n")
    monkeypatch.setattr(report, "ORDINAL_REAL_CERTS",
                        {LABEL: (RECORDS_REL, str(tampered), "under")})
    rc = main(["verify", "--protocol", "protocol.json"])
    out = capsys.readouterr()
    assert rc == cli.EXIT_DRIFT, (rc, out.out[-400:], out.err[-600:])
    assert "cert %s.bound" % LABEL in out.err, out.err
    assert "%s byte-identical" % DOC_REL in out.err, out.err
    assert "claim G3 not_measured" in out.out, out.out
