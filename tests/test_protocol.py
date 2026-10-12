"""Plan D Task 1: the frozen protocol, its loader, and the proof that the freeze can fail.

Every test here is stated against the tree's own owners, not against remembered values: the rubric is
read from `certificate.PUBLISHED_RUBRIC`, the artefact paths from `report.CERTS` and
`report.MASSIVE_CERTIFICATES`, the corpus digests from the bytes at the published paths, and the claim
statuses from the certificates that are actually committed. A test that quoted a number instead would
pass on the day the number moved, which is the exact failure this whole task exists to make loud.

The shape of the file is the contract under test, so the drift check (re-emit, compare bytes) is the
most important row here: it is the only mechanism that turns "someone changed a constant without
re-freezing" from a sentence in a review into a red test.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from autorate import protocol
from autorate.certificate import (ALPHA, BETA, DELTA, METHOD, MIN_CAL, MIN_EVAL, N_CLAIMS,
                                  PUBLISHED_RUBRIC, SEED, SHAPE_VERSION, SPLIT_SEED_DEFAULT,
                                  DIAGNOSTIC_GRID)
from autorate.protocol import (CLAIM_STATUS_CERTIFIED, CLAIM_STATUS_MEASURED_NOT_BOUNDED,
                               CLAIM_STATUS_NOT_CERTIFIABLE, CLAIM_STATUS_NOT_MEASURED,
                               CLAIM_STATUS_NOT_MET, ProtocolError, file_digest, load_protocol,
                               protocol_digest, render_protocol, write_protocol)
from autorate.records import QTYPES
from autorate.report import CERTS, INVENTORY_JSON, MASSIVE_CERTIFICATES, RECORDS

REPO = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO / "protocol.json"
UPSTREAM = Path(
    os.environ.get("AUTORATE_FEISHU_ROOT",
                   str(__import__("autorate.cli", fromlist=["_default_corpus"])._default_corpus()
                       or "/no/corpus/on/this/machine")))

# The §3 measured value, quoted from the ledger so a re-typed digest in the document is caught against
# the number the controller measured over 1,919 lines rather than against whatever this run computed.
MEASURED_RECORDS_DIGEST = ("d06e7e87f4de31e287f7900dc1662ea0c5c845b3b5cac592bff3612d33593026")


def run(*args, cwd=REPO, env_root=None):
    """The real invocation, rc read from the command and not from a pipe."""
    env = dict(os.environ)
    if env_root is not None:
        env["AUTORATE_FEISHU_ROOT"] = str(env_root)
    return subprocess.run([sys.executable, "-m", "autorate.cli", *args],
                          capture_output=True, text=True, cwd=str(cwd), env=env)


def committed_doc() -> dict:
    return json.loads(PROTOCOL_PATH.read_text())


def committed_frozen_at() -> str:
    return committed_doc()["frozen_at"]


# What the emitted `rubric` block has to equal: the owner's mapping, with the grid as the JSON array
# the document carries. The tuple-vs-list difference is the serializer's, not the value's.
EXPECTED_RUBRIC = {**PUBLISHED_RUBRIC, "grid": list(PUBLISHED_RUBRIC["grid"])}


@pytest.fixture(autouse=True)
def _repo_as_cwd(monkeypatch):
    """The producer surface reads the paths its own tables declare relative to the tree, exactly as
    `verify` does, so the in-process emissions need the repo as cwd. Through `monkeypatch` rather than
    a bare `chdir`, because a helper that left the session in the repo directory would be a side
    effect on every test that runs after it in the same process.
    """
    monkeypatch.chdir(REPO)


def emit_at_root(frozen_at=None):
    """Re-emit from today's code, from the paths the publication tables declare."""
    from autorate.report import read_inventory_snapshot

    return protocol.emit_protocol(read_inventory_snapshot(Path(INVENTORY_JSON)),
                                  file_digest(Path(RECORDS)),
                                  committed_frozen_at() if frozen_at is None else frozen_at)


def loads(tmp_path, doc, name="doc.json"):
    path = tmp_path / name
    write_protocol(doc, path)
    return load_protocol(path)


# --- the emitter reads its values from the owners, and types none of them -------------------------

def test_the_emitted_rubric_is_the_published_mapping_verbatim():
    doc = emit_at_root()
    assert doc["rubric"] == EXPECTED_RUBRIC, doc["rubric"]
    # The grid is a JSON array of the owner's 29 points, in the owner's order.
    assert doc["rubric"]["grid"] == list(DIAGNOSTIC_GRID)
    assert len(doc["rubric"]["grid"]) == 29
    # `seed` is the published split, NOT the library default: collapsing the two re-rolls every seeded
    # partition, so the document has to carry 7 and say which 0 it is not.
    assert doc["rubric"]["seed"] == SEED == 7
    assert doc["rubric"]["seed"] != SPLIT_SEED_DEFAULT


def test_the_record_contract_names_the_shape_and_the_primitives_the_code_declares():
    doc = emit_at_root()
    # R-196: the shape version is imported, never typed and never `null`. A loader that accepted a
    # missing version would be a permanent hole for the mismatch it exists to catch.
    assert doc["record_contract"]["shape_version"] == SHAPE_VERSION
    assert doc["record_contract"]["primitives"] == list(QTYPES)


def test_the_emitter_body_types_no_rubric_value():
    """`no literals typed into the emitter body`, checked by parsing the source rather than by trust.

    A value comparison between the emitted document and the mapping cannot catch this defect: an
    emitter that typed `0.05` produces the same bytes as one that imported it, and the drift gate is
    green either way. So the guard is structural -- it reads the function's own AST.
    """
    tree = ast.parse(Path(protocol.__file__).read_text())
    body = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "emit_protocol"]
    assert len(body) == 1, "emit_protocol is the emitter's only owner"
    values = set()
    for node in body[0].body:
        for const in ast.walk(node):
            if isinstance(const, ast.Constant):
                values.add(const.value)
    rubric_values = {v for v in PUBLISHED_RUBRIC.values() if not isinstance(v, tuple)}
    rubric_values |= set(DIAGNOSTIC_GRID)
    offenders = sorted(v for v in values if isinstance(v, (int, float, str)) and v in rubric_values)
    assert not offenders, "the emitter re-typed %s instead of reading the owner" % offenders


# --- the freeze is byte-reproducible, and `frozen_at` is provenance, not a clock ------------------

def test_the_committed_protocol_loads_and_agrees_with_the_owner():
    loaded = load_protocol(PROTOCOL_PATH)
    assert loaded.rubric == EXPECTED_RUBRIC
    assert loaded.protocol_version == protocol.PROTOCOL_VERSION
    assert loaded.record_contract["shape_version"] == SHAPE_VERSION
    assert loaded.claims and loaded.known_limits


def test_reemission_against_todays_code_is_byte_identical_to_the_committed_file():
    """The drift check: change a constant without re-freezing and this is the row that reddens."""
    assert render_protocol(emit_at_root()) == PROTOCOL_PATH.read_text()
    assert protocol_digest(emit_at_root()) == protocol_digest(committed_doc())


def test_write_protocol_is_the_bytes_the_digest_is_taken_over(tmp_path):
    doc = emit_at_root()
    path = tmp_path / "protocol.json"
    write_protocol(doc, path)
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and raw == render_protocol(doc).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == protocol_digest(doc)
    # Field order is the emitter's, not the alphabet's: `sort_keys=False` is what makes the document
    # read as a protocol rather than as a dict dump.
    assert json.loads(raw.decode("utf-8"), object_pairs_hook=list)[0][0] == "protocol_version"


def test_emitting_twice_into_different_paths_gives_equal_bytes(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    doc = emit_at_root()
    write_protocol(doc, a)
    write_protocol(doc, b)
    assert a.read_bytes() == b.read_bytes()


def test_a_different_frozen_at_is_drift_and_not_metadata(tmp_path):
    base = emit_at_root()
    moved = emit_at_root(frozen_at="2027-01-01")
    assert moved["frozen_at"] == "2027-01-01"
    assert protocol_digest(base) != protocol_digest(moved)
    # ...and the cost of keeping it inside the digest is stated where a reader meets it: the field is
    # normative, so no arm of the loader forgives a date nobody froze.
    with pytest.raises(ProtocolError, match="frozen_at"):
        loads(tmp_path, {**base, "frozen_at": "yesterday"})


def test_the_command_refuses_to_invent_a_freeze_date(tmp_path):
    """No clock, no git read, no silent default (§1's ruling)."""
    out = tmp_path / "fresh.json"
    p = run("protocol", "--out", str(out))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "--frozen-at" in p.stderr, p.stderr
    assert not out.exists(), "a refused run wrote a document anyway"


def test_the_command_reuses_the_date_already_in_the_file_it_rewrites(tmp_path):
    """`autorate protocol --out protocol.json` reproduces the committed bytes in ANY tree, git or not.

    This is the arm that makes the freeze checkable in the `git archive` export, where a git-derived
    date would raise or differ: the file it is about to overwrite carries the provenance, so the
    re-emission needs no repository and no clock.
    """
    staged = tmp_path / "protocol.json"
    staged.write_bytes(PROTOCOL_PATH.read_bytes())
    p = run("protocol", "--out", str(staged))
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert staged.read_bytes() == PROTOCOL_PATH.read_bytes()


def test_the_command_emits_the_committed_bytes_when_told_the_date(tmp_path):
    out = tmp_path / "reemit.json"
    p = run("protocol", "--out", str(out), "--frozen-at", committed_frozen_at())
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert out.read_bytes() == PROTOCOL_PATH.read_bytes()
    # The limitation is printed, not only stored: a reader of the command must see that this rubric
    # governs the choice rule and not the whole tree.
    assert "certify_score" in p.stdout and "choice" in p.stdout, p.stdout


# --- the corpus block is measured, not typed (§3) --------------------------------------------------

def test_records_digest_is_the_hash_of_the_committed_records_file():
    doc = emit_at_root()
    assert doc["corpus"]["records_digest"] == file_digest(REPO / RECORDS)
    assert doc["corpus"]["records_digest"] == MEASURED_RECORDS_DIGEST
    assert len((REPO / RECORDS).read_text().splitlines()) == 1919


def test_a_different_records_digest_changes_the_protocol_digest(tmp_path):
    base = emit_at_root()
    from autorate.report import read_inventory_snapshot

    other = protocol.emit_protocol(read_inventory_snapshot(Path(INVENTORY_JSON)),
                                   "f" * 64, base["frozen_at"])
    assert other["corpus"]["records_digest"] == "f" * 64
    assert protocol_digest(other) != protocol_digest(base)
    # ...and the field is not decoration in the other direction either: a one-byte change in a file
    # moves its digest, which is what `file_digest` is for.
    a, b = tmp_path / "r1.jsonl", tmp_path / "r2.jsonl"
    a.write_text('{"id": "1"}\n')
    b.write_text('{"id": "2"}\n')
    assert file_digest(a) != file_digest(b)


def test_inventory_digest_is_measured_and_a_one_byte_change_moves_it(tmp_path):
    doc = emit_at_root()
    assert doc["corpus"]["inventory_digest"] == file_digest(REPO / INVENTORY_JSON)
    other = tmp_path / "inventory.md.json"
    raw = (REPO / INVENTORY_JSON).read_bytes()
    other.write_bytes(raw[:-3] + b"}\n" if raw.endswith(b"}\n") else raw + b" ")
    assert file_digest(other) != doc["corpus"]["inventory_digest"]


def test_the_corpus_block_carries_no_absolute_path():
    doc = emit_at_root()
    assert doc["corpus"]["records_owner"] == RECORDS
    assert doc["corpus"]["inventory_owner"] == INVENTORY_JSON
    assert doc["corpus"]["pinned_builds"]["massive_intent"]["pin_label"] == \
        protocol.MASSIVE_PIN_LABEL
    labels = [row["label"] for row in doc["corpus"]["source_labels"]]
    assert len(labels) == 9 and all(not v.startswith("/") for v in labels), labels
    # The pin is pinned BY DIGEST; the 51 shard digests stay in the file that owns them.
    assert "files" not in doc["corpus"]["pinned_builds"]["massive_intent"]


def test_the_emitter_refuses_a_tree_that_has_no_pin_file(monkeypatch, tmp_path):
    """An absent pin is the checkout's fault, not the operator's: it is never frozen as `null`."""
    from autorate import inventory
    from autorate.report import PublishedArtefactUnavailable, read_inventory_snapshot

    monkeypatch.chdir(REPO)
    monkeypatch.setattr(inventory, "MASSIVE_PIN_PATH", tmp_path / "absent.json")
    with pytest.raises(PublishedArtefactUnavailable):
        protocol.emit_protocol(read_inventory_snapshot(Path(INVENTORY_JSON)),
                               file_digest(Path(RECORDS)), "2026-10-11")


# --- every validation clause is proved by a mutation that names itself ----------------------------

def _mutate(**changes):
    doc = committed_doc()
    for dotted, value in changes.items():
        node = doc
        parts = dotted.split(".")
        for p in parts[:-1]:
            node = node[int(p)] if p.isdigit() else node[p]
        node[parts[-1]] = value
    return doc


@pytest.mark.parametrize("dotted,value,clause", [
    ("protocol_version", 2, "protocol_version"),
    ("protocol_version", 0, "protocol_version"),
    ("rubric.alpha", 0.0, "alpha"),
    ("rubric.beta", 1.5, "beta"),
    ("rubric.delta", 0, "delta"),
    ("rubric.min_cal", 40, "min_cal"),
    ("rubric.min_eval", 40, "min_eval"),
    ("rubric.n_claims", 4, "n_claims"),
    ("rubric.unit", "row", "unit"),
    ("rubric.method", "lac", "method"),
    ("rubric.seed", 0, "seed"),
    ("record_contract.shape_version", None, "shape_version"),
    ("record_contract.shape_version", 1, "shape_version"),
    ("claims.0.status", "verified", "claims"),
    ("rubric_scope", "", "rubric_scope"),
])
def test_a_mutated_rubric_or_promise_is_refused_by_name(tmp_path, dotted, value, clause):
    with pytest.raises(ProtocolError, match=clause):
        loads(tmp_path, _mutate(**{dotted: value}))


def test_the_frozen_grid_is_refused_when_it_is_the_audit_frontier(tmp_path):
    """R-187's substitution: `audit.DEFAULT_GRID` is a different object and never a stand-in."""
    from autorate.audit import DEFAULT_GRID

    with pytest.raises(ProtocolError, match="grid"):
        loads(tmp_path, _mutate(**{"rubric.grid": list(DEFAULT_GRID)}))
    # ...and the refusal is about the owner, not about plausibility: the audit grid is monotone,
    # in (0,1) and 5 points long, so nothing but the comparison with `PUBLISHED_RUBRIC` catches it.
    assert all(0.0 <= g <= 1.0 for g in DEFAULT_GRID)


def test_a_rubric_key_the_owner_does_not_declare_is_refused(tmp_path):
    doc = _mutate(**{"rubric.min_slices": 12})
    with pytest.raises(ProtocolError, match="min_slices"):
        loads(tmp_path, doc)


@pytest.mark.parametrize("pieces", [
    ["/", "srv", "/corpus/x.jsonl"],
    ["/", "Users", "/jackson/corpus/x.jsonl"],
    ["~", "/corpus/x.jsonl"],
    ["C:", "\\corpus\\x.jsonl"],
])
def test_an_absolute_machine_path_in_the_corpus_block_is_refused(tmp_path, pieces):
    """The machine-path guard, moved into the loader so it fires before CI ever sees the file.

    The offending value is built from pieces, exactly as `tests/test_cli.py` builds its own probe
    string, so the test that polices machine paths never becomes an offender under its own guard.
    """
    doc = _mutate(**{"corpus.records_digest": "".join(pieces)})
    with pytest.raises(ProtocolError, match="absolute"):
        loads(tmp_path, doc)
    # anywhere inside the subtree, not only at the top: a nested list element is the same defect.
    nested = committed_doc()
    nested["corpus"]["source_labels"][0]["label"] = "".join(["/", "home", "/ someone/x"])
    with pytest.raises(ProtocolError, match="absolute"):
        loads(tmp_path, nested)


def test_the_shape_is_refused_before_the_values_are_checked(tmp_path):
    """A malformed document whose SHAPE is bad and whose VALUES are also bad reports the shape.

    The value checks index `rubric` and `corpus` as mappings; run first, they would raise a `TypeError`
    naming no field, or -- worse, for a document this repository calls authoritative -- a complaint
    about `protocol_version` while the real finding is that the file is not a protocol at all.
    """
    doc = _mutate(**{"protocol_version": 999, "rubric": "not-a-mapping"})
    with pytest.raises(ProtocolError) as got:
        loads(tmp_path, doc)
    message = str(got.value)
    assert "rubric" in message and "mapping" in message, message
    assert "protocol_version" not in message, message
    # the same ordering for a `corpus` that is not a mapping, and for `claims` that is not a list
    doc = _mutate(**{"min_cal": 1})
    doc["corpus"] = "data/x"
    with pytest.raises(ProtocolError, match="corpus"):
        loads(tmp_path, doc)
    doc = committed_doc()
    doc["claims"] = "G1"
    with pytest.raises(ProtocolError, match="claims"):
        loads(tmp_path, doc)


def test_a_missing_section_is_refused_by_name(tmp_path):
    for key in ("rubric", "corpus", "claims", "known_limits", "record_contract", "rubric_scope",
                "frozen_at", "protocol_version", "decision_rule"):
        doc = committed_doc()
        del doc[key]
        with pytest.raises(ProtocolError, match=re.escape(key)):
            loads(tmp_path, doc)


def test_an_added_top_level_key_round_trips_and_a_changed_value_does_not(tmp_path):
    """Forward compatibility for a key the loader does not read; no tolerance for one it does."""
    base = committed_doc()
    before = protocol_digest(load_protocol(PROTOCOL_PATH))
    added = loads(tmp_path, {**base, "a_key_nobody_reads": {"nested": 1}})
    assert protocol_digest(added) == before
    # a VALUE the loader reads: a different (still digest-shaped, still non-absolute) records digest
    # is a protocol about a different corpus, so it must not digest the same.
    changed = loads(tmp_path, _mutate(**{"corpus.records_digest": "e" * 64}))
    assert protocol_digest(changed) != before
    # and the normative sentences are pinned to their owner, so "editing the prose" is not available
    with pytest.raises(ProtocolError, match="decision_rule"):
        loads(tmp_path, _mutate(**{"decision_rule": "anything escalates"}))


def test_the_loaded_document_renders_back_to_the_committed_bytes(tmp_path):
    loaded = load_protocol(PROTOCOL_PATH)
    assert render_protocol(loaded) == PROTOCOL_PATH.read_text()
    # key order inside the rubric is the owner's, so a reordered file is the same protocol
    shuffled = committed_doc()
    shuffled["rubric"] = {k: shuffled["rubric"][k] for k in reversed(list(shuffled["rubric"]))}
    assert protocol_digest(loads(tmp_path, shuffled)) == protocol_digest(shuffled)


def test_the_document_is_pure_bytes_and_carries_no_comment(tmp_path):
    """`write_protocol` renders `sort_keys=False, indent=2` plus one trailing newline."""
    text = PROTOCOL_PATH.read_text()
    assert text.endswith("}\n") and not text.endswith("}\n\n")
    assert "\n// " not in text, "JSON comments are the plan's sketch, not the format"
    assert text == render_protocol(json.loads(text))


# --- the claims array: the first machine-readable home for spec §2, and it can say no -------------

def test_every_spec_criterion_is_present_and_g1_refuses():
    doc = committed_doc()
    ids = [c["id"] for c in doc["claims"]]
    assert ids == list(protocol.SPEC_CLAIM_IDS) == ["G1", "G2", "G3", "G4", "G5"]
    g1 = doc["claims"][0]
    assert g1["status"] == CLAIM_STATUS_NOT_CERTIFIABLE
    assert g1["certified_tasks"] == 0
    # G1's refusal is evidenced by the artefacts that hold it, named beside the status.
    assert set(g1["artefacts"]) == set(CERTS.values()) | {
        pair[1] for pair in MASSIVE_CERTIFICATES.values()}
    assert g1["refusal_reasons"] == ["empty_feasible_set"]
    for claim in doc["claims"]:
        for artefact in claim["artefacts"]:
            assert (REPO / artefact).is_file(), "claims names an artefact that is not there"
        assert claim["criterion"] and claim["measurement"] and claim["note"]


def test_no_claim_is_stated_as_satisfied_that_the_certificates_contradict():
    """The document may not launder a criterion the tree refuses (R-197)."""
    from autorate.report import load_published, read_certificate

    published = []
    for path in sorted(CERTS.values()):
        published.append(load_published(path, "report.CERTS", read_certificate))
    for label, (_records_path, cert_path) in sorted(MASSIVE_CERTIFICATES.items()):
        published.append(load_published(cert_path, "report.MASSIVE_CERTIFICATES", read_certificate))
    feasible = [c for c in published if c.feasible]
    assert not feasible, (
        "a published certificate now certifies: G1's status has to be re-derived, not edited")
    g1 = next(c for c in committed_doc()["claims"] if c["id"] == "G1")
    assert g1["status"] != CLAIM_STATUS_CERTIFIED
    assert g1["published_certificates"] == len(published)
    # the vocabulary admits failure, and the refusing state is the CLI's own word
    assert protocol.CLAIM_STATUSES == (CLAIM_STATUS_CERTIFIED, CLAIM_STATUS_NOT_CERTIFIABLE,
                                       CLAIM_STATUS_NOT_MET, CLAIM_STATUS_MEASURED_NOT_BOUNDED,
                                       CLAIM_STATUS_NOT_MEASURED)
    # every state the vocabulary can name is reachable from the count it is a sentence about, so no
    # arm of the derivation is code nobody has read
    assert protocol.g1_status(0) == CLAIM_STATUS_NOT_CERTIFIABLE
    assert protocol.g1_status(2) == CLAIM_STATUS_NOT_MET
    assert protocol.g1_status(protocol.G1_MIN_CERTIFIED_TASKS) == CLAIM_STATUS_CERTIFIED
    assert protocol.G1_MIN_CERTIFIED_TASKS == 3
    assert CLAIM_STATUS_NOT_CERTIFIABLE == "not_certifiable"


def test_a_claim_whose_status_its_own_count_refutes_is_refused(tmp_path):
    """Flipping G1's word while leaving the count at zero is the laundering this row exists for."""
    doc = _mutate(**{"claims.0.status": CLAIM_STATUS_CERTIFIED})
    with pytest.raises(ProtocolError, match="certified_tasks"):
        loads(tmp_path, doc)


def test_g2s_status_agrees_with_what_the_audit_can_bound():
    """G2 is `measured_not_bounded` only while the audit's own bound fails to bound the gate."""
    from autorate.audit import audit_fields
    from autorate.report import load_records

    rows = audit_fields(load_records(Path(RECORDS))["laya"])
    confidence = rows["confidence"]
    assert confidence["informative"] is False, confidence
    g2 = next(c for c in committed_doc()["claims"] if c["id"] == "G2")
    assert g2["status"] == CLAIM_STATUS_MEASURED_NOT_BOUNDED
    assert g2["artefacts"] == ["docs/AUDIT.md"]


def test_the_known_limits_are_the_envelopes_the_certificates_carry():
    from autorate.report import load_published, read_certificate

    limits = set(committed_doc()["known_limits"])
    for path in sorted(CERTS.values()):
        cert = load_published(path, "report.CERTS", read_certificate)
        assert set(cert.envelope) <= limits
    for _label, (_rp, cert_path) in sorted(MASSIVE_CERTIFICATES.items()):
        cert = load_published(cert_path, "report.MASSIVE_CERTIFICATES", read_certificate)
        assert set(cert.envelope) <= limits


# --- the honesty limitation the rubric owner does not cover --------------------------------------

def test_the_rubric_scope_sentence_names_copies_that_still_exist():
    """The scope must not read as though one mapping governed the ordinal and threshold paths.

    Half the sentence is checked against the tree: if a future round deletes the out-of-fence copies,
    this row reddens and the scope has to be re-written rather than inherited silently -- the same way
    `docs/ERRATA.md` recorded what 6A did NOT land.
    """
    scope = committed_doc()["rubric_scope"]
    assert load_protocol(PROTOCOL_PATH).rubric_scope == scope
    for named in ("certify_score", "certify_threshold", "severity", "tails.ALPHA_DEFAULT",
                  "choice", "not"):
        assert named in scope, scope
    for rel, needle in (("src/autorate/certify_score.py", "MIN_CAL"),
                        ("src/autorate/certify_threshold.py", "MIN_EVAL"),
                        ("src/autorate/severity.py", "0.05"),
                        ("src/autorate/tails.py", "ALPHA_DEFAULT")):
        assert needle in (REPO / rel).read_text(), "%s no longer declares %s: re-scope" % (rel, needle)


def test_the_scope_field_is_not_a_free_text_slot_an_editor_can_soften(tmp_path):
    with pytest.raises(ProtocolError, match="rubric_scope"):
        loads(tmp_path, _mutate(**{"rubric_scope": "the published rubric of this repository"}))


# --- the CLI: `certify --protocol`, and the boundary R-200 rules ----------------------------------

def _fixture_records(path, n=200):
    """A population that certifies, so the arms differ only by the flag."""
    from _records import choice_record

    options = tuple("opt%d" % j for j in range(4))
    lines = []
    for i in range(n):
        probs = (0.9700, 0.0100, 0.0100, 0.0100)
        lines.append(choice_record(id="r%d" % i, case_id="c%d" % i, backend="synthetic",
                                   options=options, probs=probs, gold="opt0",
                                   predicted="opt0", u=0.5).to_dict())
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in lines))
    return path


def test_certify_stamps_only_when_the_flag_is_on_its_own_command_line(tmp_path):
    """The flag is a stamp, not a re-run -- and the published artefacts are all stamped (R-200, Task 2)."""
    records = _fixture_records(tmp_path / "records.jsonl")
    plain, stamped = tmp_path / "plain.json", tmp_path / "stamped.json"

    first = run("certify", str(records), "--out", str(plain))
    assert first.returncode == 0, (first.returncode, first.stdout, first.stderr)
    second = run("certify", str(records), "--out", str(stamped),
                 "--protocol", str(PROTOCOL_PATH))
    assert second.returncode == 0, (second.returncode, second.stdout, second.stderr)

    plain_doc, stamped_doc = json.loads(plain.read_text()), json.loads(stamped.read_text())
    digest = protocol_digest(load_protocol(PROTOCOL_PATH))
    assert "protocol_digest" not in plain_doc["meta"], plain_doc["meta"]
    assert stamped_doc["meta"]["protocol_digest"] == digest
    # everything else about the two runs is identical, so the flag is a stamp and not a re-run
    assert {k: v for k, v in stamped_doc["meta"].items() if k != "protocol_digest"} \
        == plain_doc["meta"]

    # Task 2's re-export, measured rather than intended: every published certificate now carries the
    # freeze, and the value it carries is this digest. That is what the pair above makes costly -- a
    # published artefact produced without the flag disagrees with `verify`, which stamps its
    # re-derivation, so the flag has to be on the command line that writes a published number.
    for path in sorted(set(CERTS.values()) | {p for _l, p in MASSIVE_CERTIFICATES.values()}):
        assert json.loads((REPO / path).read_text())["meta"].get("protocol_digest") == digest, path
    gate = run("verify")
    assert gate.returncode == 0, gate.stdout + gate.stderr
    checked, total = re.search(r"re-derived (\d+) /(\d+) values", gate.stdout).groups()
    assert checked == total, gate.stdout


def test_certify_has_no_default_protocol(tmp_path):
    """`certify`'s default must not read `protocol.json`, or the stamped lane turns red here."""
    parser = __import__("autorate.cli", fromlist=["build_parser"]).build_parser()
    args = parser.parse_args(["certify", "x"])
    assert args.protocol is None, args
    records = _fixture_records(tmp_path / "records.jsonl")
    out = tmp_path / "c.json"
    p = run("certify", str(records), "--out", str(out), cwd=tmp_path)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert "protocol_digest" not in json.loads(out.read_text())["meta"]


def test_a_flag_that_contradicts_the_protocol_exits_2_naming_both_values(tmp_path):
    records = _fixture_records(tmp_path / "records.jsonl")
    p = run("certify", str(records), "--out", str(tmp_path / "c.json"),
            "--protocol", str(PROTOCOL_PATH), "--alpha", "0.10")
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "--alpha" in p.stderr and "protocol" in p.stderr, p.stderr
    assert "0.1" in p.stderr and "0.05" in p.stderr, p.stderr
    assert not (tmp_path / "c.json").exists(), "a contradicted run wrote a certificate"


@pytest.mark.parametrize("flag,value", [("--beta", "0.20"), ("--delta", "0.10"),
                                        ("--seed", "0"), ("--method", "lac")])
def test_every_rubric_flag_can_contradict_the_protocol_and_is_refused(tmp_path, flag, value):
    records = _fixture_records(tmp_path / "records.jsonl")
    p = run("certify", str(records), "--out", str(tmp_path / "c.json"),
            "--protocol", str(PROTOCOL_PATH), flag, value)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert flag in p.stderr, p.stderr


def test_a_flag_that_agrees_with_the_protocol_is_accepted_and_the_stamp_lands(tmp_path):
    records = _fixture_records(tmp_path / "records.jsonl")
    out = tmp_path / "c.json"
    p = run("certify", str(records), "--out", str(out), "--protocol", str(PROTOCOL_PATH),
            "--alpha", str(ALPHA), "--beta", str(BETA), "--delta", str(DELTA),
            "--seed", str(SEED), "--method", METHOD)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    doc = json.loads(out.read_text())
    assert doc["meta"]["protocol_digest"]
    assert (doc["alpha"], doc["beta"], doc["delta"], doc["method"]) == (ALPHA, BETA, DELTA, METHOD)
    assert doc["meta"]["seed"] == SEED


def test_certify_without_the_flag_still_defaults_to_the_owner(tmp_path):
    records = _fixture_records(tmp_path / "records.jsonl")
    out = tmp_path / "c.json"
    p = run("certify", str(records), "--out", str(out))
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    doc = json.loads(out.read_text())
    assert (doc["alpha"], doc["beta"], doc["delta"], doc["method"]) == (ALPHA, BETA, DELTA, METHOD)
    assert doc["meta"]["seed"] == SEED == 7
    assert N_CLAIMS == 3 and MIN_CAL == MIN_EVAL == 60


def test_the_protocol_flag_names_a_document_the_tree_cannot_read(tmp_path):
    """A malformed protocol reaching `certify` is the loader's refusal, at exit 2, with no traceback."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    records = _fixture_records(tmp_path / "records.jsonl")
    p = run("certify", str(records), "--out", str(tmp_path / "c.json"), "--protocol", str(bad))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr


def test_protocol_error_is_a_valueerror_so_the_exit_contract_closes():
    assert issubclass(ProtocolError, ValueError)
