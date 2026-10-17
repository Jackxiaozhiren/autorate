"""Plan D Task 2: `verify --protocol`, and the one check a self-consistent regeneration cannot answer for.

The design being tested is Plan D R-200's Design G, and it is worth restating why the shape is what it is.
`verify` reads the committed `protocol.json` as a **table-declared default**, whether or not `--protocol` was
typed, so both command shapes exit 0 on a frozen tree and a missing freeze is exit **4** naming
`cli.PROTOCOL_JSON` -- never 2, because the operator typed no path. `--protocol PATH` selects a different
document, which is how the flag's effect stays observable: red arrives from a protocol that disagrees, not from
the presence of a flag. And the check that matters most is the one that does not read the artefacts' own word:
`corpus.records_digest`. Every other corpus-less comparison asks whether the published files reproduce from the
records lying beside them, so swapping the records and regenerating the certificates in the same commit answers
all of them -- spec 2 D-12. A digest frozen before the numbers cannot be answered for.

Nothing here imports a model, a corpus or a network: these are the same committed files `verify` reads.
"""
import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from autorate import cli, report
from autorate.cli import main
from autorate.protocol import load_protocol, protocol_digest

REPO = Path(cli.__file__).resolve().parents[2]


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)


def _records(tmp_path, monkeypatch, mutate=None):
    """Point `verify` at a copy of the committed records, optionally altered in a schema-valid way."""
    src = REPO / "data" / "records_feishu.jsonl"
    dst = tmp_path / "records_feishu.jsonl"
    lines = src.read_text().splitlines()
    if mutate is not None:
        lines = mutate(lines)
    dst.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(cli, "RECORDS", str(dst))
    return dst


def _certs(tmp_path, monkeypatch, drop_digest_for=None, mutate=None):
    """Re-point the feishu publication table at copies, optionally with `meta.protocol_digest` removed.

    BOTH owners are patched. `cmd_verify` iterates the table it imported as `cli.CERTS` but opens each
    artefact through `load_published(path, "report.CERTS", ...)`, and `report.certify_all` -- which the
    published documents are built from -- reads `report.CERTS`. A helper that patched only the name in
    `cli` would leave part of the gate reading the real files: this test's first version did exactly
    that and passed rc 0 while asserting a refusal.
    """
    table = {}
    for backend, path in sorted(cli.CERTS.items()):
        dst = tmp_path / Path(path).name
        doc = json.loads((REPO / path).read_text())
        if drop_digest_for in ("*", backend):
            doc.get("meta", {}).pop("protocol_digest", None)
        if mutate is not None:
            mutate(doc)
        dst.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        table[backend] = str(dst)
    monkeypatch.setattr(cli, "CERTS", table)
    monkeypatch.setattr(report, "CERTS", table)
    return table


def _massive(tmp_path, monkeypatch, label, mutate=None):
    """Re-point one row of G1's published table at a copy, optionally altered."""
    records_path, cert_path = report.MASSIVE_CERTIFICATES[label]
    dst = tmp_path / Path(cert_path).name
    doc = json.loads((REPO / cert_path).read_text())
    if mutate is not None:
        mutate(doc)
    dst.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    table = {key: (rec, str(dst) if key == label else cert)
             for key, (rec, cert) in report.MASSIVE_CERTIFICATES.items()}
    monkeypatch.setattr(report, "MASSIVE_CERTIFICATES", table)
    return dst


def _protocol(tmp_path, sub=None, key=None, value=None):
    """A copy of the committed freeze, optionally with one field changed, written for `--protocol`."""
    doc = json.loads((REPO / "protocol.json").read_text())
    if sub is not None:
        doc[sub][key] = value
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return path


def test_verify_reads_the_committed_protocol_and_exits_zero(in_repo, capsys):
    """Both command shapes agree on the frozen tree: the flag is a selector, not an enabler."""
    assert main(["verify"]) == 0
    assert main(["verify", "--protocol", "protocol.json"]) == 0
    out = capsys.readouterr().out
    assert "protocol:" in out, out[-600:]


def test_verify_prints_one_line_per_claim_with_a_status_that_can_say_no(in_repo, capsys):
    """R-197: a claims list that cannot express failure is the most misleading string in the repository."""
    assert main(["verify", "--protocol", "protocol.json"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("claim G")]
    assert [line.split()[1] for line in lines] == ["G1", "G2", "G3", "G4", "G5"], lines
    joined = "\n".join(lines)
    assert "not_certifiable" in joined, joined          # G1: 0 of 5 published tasks certify (R-204)
    assert "not_measured" in joined, joined             # G3 still refuses; G5 left this list when the transcript landed


def test_a_records_file_the_protocol_did_not_bless_refuses_in_the_corpus_less_lane(tmp_path, monkeypatch,
                                                                                   in_repo, capsys):
    """The D-12 control, and it must name its own cause rather than merely change the exit code.

    Two served probabilities are swapped: the row stays schema-valid (the sum is untouched, so nothing is
    quarantined), the bytes are not. The certificates then fail to reproduce for a second, unrelated
    reason, so the assertion is the digest line rather than `rc == 4` alone -- an exit code several causes
    share proves nothing about which one fired (the lesson of R-219).
    """
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", "/nonexistent-corpus-dir")

    def swap(lines):
        row = json.loads(lines[0])
        probs = row["probs"]
        assert len(probs) > 1 and probs[0] != probs[1], probs
        probs[0], probs[1] = probs[1], probs[0]
        lines[0] = json.dumps(row, sort_keys=True)
        return lines

    _records(tmp_path, monkeypatch, swap)
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    err = capsys.readouterr().err
    assert "records_digest" in err, err[-800:]


def test_the_digest_check_fires_even_when_nothing_else_is_wrong(tmp_path, monkeypatch, in_repo, capsys):
    """A records file with a valid shape but a different byte count is refused on the digest alone."""
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", "/nonexistent-corpus-dir")
    dst = _records(tmp_path, monkeypatch)
    digest_before = cli.file_digest(dst)
    frozen = load_protocol(REPO / "protocol.json").corpus["records_digest"]
    assert digest_before == frozen                      # the control's premise, not an assumption
    with dst.open("a") as handle:
        handle.write("")                                # same bytes: the check must still pass
    assert cli.file_digest(dst) == frozen
    with dst.open("a") as handle:
        handle.write("\n")                              # one byte changes the digest, nothing else
    assert cli.file_digest(dst) != frozen
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    assert "records_digest" in capsys.readouterr().err


def test_a_certificate_produced_without_a_protocol_refuses_by_name(tmp_path, monkeypatch, in_repo, capsys):
    """The artefacts must carry the freeze, and an unstamped one is drift the gate can attribute.

    The refusal is `cert <backend>.meta` rather than a new sentence: the re-derivation stamps and the stored
    artefact does not, and `meta` is compared by whole-dict equality. The count is asserted because a gate
    that checked only one of the two published artefacts would look identical here.
    """
    _certs(tmp_path, monkeypatch, drop_digest_for="*")
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    drift = [line for line in capsys.readouterr().err.splitlines() if line.startswith("DRIFT:")]
    assert len(drift) == 2, drift                        # exactly the two feishu artefacts
    for backend in ("laya", "jev"):
        assert any("cert %s.meta" % backend in line for line in drift), (backend, drift)


def test_rubric_mismatch_is_reported_as_its_own_failure_not_folded_into_drift(tmp_path, monkeypatch,
                                                                              in_repo, capsys):
    """"The number does not reproduce" and "the number came from a rule we never promised" differ.

    The artefact, not the protocol, is edited at `alpha`: `alpha` is a top-level field and is NOT in
    `CERT_COMPARE_FIELDS`, so the field list alone would notice only the summary sentence that happens to
    quote it. The rubric row is what names the cause, and it must arrive under its own prefix -- an operator
    repairs a mismatch by re-certifying at the promised rule and repairs drift by re-exporting, so the two
    sentences cannot share a line.
    """
    def raise_alpha(doc):
        assert doc["alpha"] == 0.05, doc["alpha"]
        doc["alpha"] = 0.04

    _certs(tmp_path, monkeypatch, mutate=raise_alpha)
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    err = capsys.readouterr().err
    mismatch = [line for line in err.splitlines() if line.startswith("RUBRIC MISMATCH:")]
    assert len(mismatch) == 2 and all("alpha" in line for line in mismatch), mismatch
    drift = [line for line in err.splitlines() if line.startswith("DRIFT:")]
    assert len(drift) == 2 and all(".summary" in line for line in drift), drift
    assert not [line for line in mismatch if "summary" in line], mismatch


def test_a_published_seed_that_disagrees_with_the_freeze_is_named_in_both_kinds(tmp_path, monkeypatch,
                                                                                in_repo, capsys):
    """`seed` lives in `meta` as well as in the split, so an edited artefact fails twice -- loudly.

    The rubric row says the published rule was not the promised one; the drift row says the bytes of `meta`
    differ. Both are wanted: the first is the sentence an operator acts on, the second is the field list
    that made it necessary. Asserting the pair is what keeps a later "just fold them together" change from
    costing the diagnosis.
    """
    def reseed(doc):
        assert doc["meta"]["seed"] == 7, doc["meta"]["seed"]
        doc["meta"]["seed"] = 8

    _certs(tmp_path, monkeypatch, mutate=reseed)
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    err = capsys.readouterr().err
    assert len([line for line in err.splitlines() if line.startswith("RUBRIC MISMATCH:")]) == 2, err
    assert all("seed" in line for line in err.splitlines() if line.startswith("RUBRIC MISMATCH:")), err
    assert len([line for line in err.splitlines() if line.startswith("DRIFT:")]) == 2, err


def test_a_protocol_that_rewrites_its_own_rubric_owner_is_refused_before_anything_reads_it(tmp_path,
                                                                                           in_repo, capsys):
    """The freeze cannot be used to relabel the rubric: `load_protocol` refuses that at the document."""
    path = _protocol(tmp_path, "rubric", "beta", 0.0404)
    assert main(["verify", "--protocol", str(path)]) == 2
    assert "rubric.beta" in capsys.readouterr().err


def test_a_missing_committed_protocol_is_a_named_refusal_at_four_not_a_usage_error(tmp_path, monkeypatch,
                                                                                   in_repo, capsys):
    """Round 5's axis, applied to the freeze: nobody typed a path, so the checkout is what is missing."""
    monkeypatch.setattr(cli, "PROTOCOL_JSON", tmp_path / "absent-protocol.json")
    rc = main(["verify"])
    assert rc == 4, rc
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "cli.PROTOCOL_JSON" in err, err[-600:]


def test_a_path_named_on_the_command_line_that_does_not_exist_is_still_a_usage_error(tmp_path, in_repo):
    assert main(["verify", "--protocol", str(tmp_path / "nope.json")]) == 2


def test_compare_refuses_across_protocols_and_still_names_the_rubric(tmp_path, monkeypatch, in_repo,
                                                                   capsys):
    """A `before/after` table would otherwise compare two protocols while claiming to compare two backends.

    Two assertions, because the first version of this row made `compare` refuse and stop talking: the
    digest mismatch returned before the rubric check, so an existing published sentence -- `comparable:
    NO -- the two sides disagree on ...` -- became unreachable for exactly the pairs that needed both.
    The affirmative is the other half: one command may not print a refusal and a pass.
    """
    doc = json.loads((REPO / "data" / "cert_laya.json").read_text())
    assert "protocol_digest" in doc.get("meta", {}), doc.get("meta", {}).keys()
    other = copy.deepcopy(doc)
    other["meta"]["protocol_digest"] = "0" * 64
    other["backend"] = doc["backend"]
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(doc, sort_keys=True))
    b.write_text(json.dumps(other, sort_keys=True))
    rc = main(["compare", str(a), str(b)])
    assert rc == 2, rc
    captured = capsys.readouterr()
    assert "protocol" in captured.err.lower(), captured.err
    assert "comparable: yes" not in captured.out, captured.out

    # the same pair, now agreeing on the protocol and disagreeing on the rubric: the old sentence lives
    rubric_off = copy.deepcopy(other)
    rubric_off["meta"]["protocol_digest"] = doc["meta"]["protocol_digest"]
    rubric_off["delta"] = 0.04
    c = tmp_path / "c.json"
    c.write_text(json.dumps(rubric_off, sort_keys=True))
    assert main(["compare", str(a), str(c)]) == 2
    second = capsys.readouterr()
    assert "comparable: NO" in second.out and "delta" in second.out, second.out
    assert "comparable: yes" not in second.out, second.out


def test_every_published_certificate_carries_the_committed_freeze(tmp_path, in_repo):
    """The durable half of the re-export: every declared artefact, one digest, the document in this checkout.

    Read through `CERT_COMPARE_FIELDS` rather than a typed list, because that tuple has one owner and a
    second copy of it in a test is how a field that exists only on the dataclass (a property, not JSON)
    gets asserted as a key of the stored document. This test's first version did exactly that and was red
    on a green tree.

    The count is not asserted as a literal. It used to be `== 5`, which froze the size of the published
    set inside a test: adding Khmer as a fourth MASSIVE corpus reddened a row whose subject was the digest,
    and the next reader's instinct would be to bump the number rather than to ask whether the artefact is
    declared. What this row can actually fail on is the two directions a publication can drift: a
    certificate the tables declare and the disk does not stamp, and a stamped file no table declares.
    Those are checked against the filesystem and against the tables, which are different sources.
    """
    digest = protocol_digest(load_protocol(REPO / "protocol.json"))
    declared = sorted(cli.CERTS.values()) + sorted(path for _, path in report.MASSIVE_CERTIFICATES.values())
    declared += sorted(cert for _label, (_records, cert, _direction) in report.SEVERITY_CERTS.items())
    assert declared, "the publication tables name no certificate at all, so this row would certify nothing"
    stamped_on_disk = []
    for path in sorted((REPO / "data").glob("cert_*.json")):
        document = json.loads(path.read_text())
        if "protocol_digest" in document.get("meta", {}):
            stamped_on_disk.append(str(path.relative_to(REPO)))
    missing = sorted(set(declared) - set(stamped_on_disk))
    extra = sorted(set(stamped_on_disk) - set(declared))
    assert not missing, "declared by the publication tables but carrying no digest on disk: %s" % missing
    assert not extra, ("carrying a digest that no publication table declares: %s -- `verify` would never "
                       "compare it, so a frozen artefact can hide there" % extra)
    for path in sorted(set(declared)):
        doc = json.loads((REPO / path).read_text())
        assert doc["meta"].get("protocol_digest") == digest, path
    # The rubric block below is the CHOICE family's: `alpha`, `beta`, `delta`, `method`, `seed` are fields of
    # a set certificate, and the severity artefact carries a different shape -- measured on the committed
    # bytes, it has `alpha` and `delta` but neither `beta` nor `method`, and its own rubric is policed by the
    # 32 alpha/delta/rubric rows in `tests/test_severity_surface.py`. Looping the choice fields over every
    # stamped artefact would raise a KeyError, which is not a finding about the artefact.
    for path in sorted(cli.CERTS.values()) + sorted(p for _, p in report.MASSIVE_CERTIFICATES.values()):
        doc = json.loads((REPO / path).read_text())
        for name in ("alpha", "beta", "delta", "method"):
            assert doc[name] == load_protocol(REPO / "protocol.json").rubric[name], (path, name)
        assert doc["meta"]["seed"] == load_protocol(REPO / "protocol.json").rubric["seed"], path


def test_a_massive_certificate_produced_without_a_protocol_refuses_by_name(tmp_path, monkeypatch,
                                                                           in_repo, capsys):
    """G1's table is checked by the same rule as the feishu one, through the owner that reads it.

    This is also the control on `rederive_massive`'s rubric alignment: the gate re-derives at the protocol's
    numbers and echoes them into `meta`, so an unaltered artefact must stay green (the baseline test) and
    only the removed digest may turn it red.
    """
    _massive(tmp_path, monkeypatch, "massive/en",
             mutate=lambda doc: doc["meta"].pop("protocol_digest"))
    rc = main(["verify", "--protocol", "protocol.json"])
    assert rc == 4, rc
    drift = [line for line in capsys.readouterr().err.splitlines() if line.startswith("DRIFT:")]
    assert len(drift) == 1, drift
    assert "cert massive/en.meta" in drift[0], drift


def test_the_records_digest_and_inventory_digest_are_both_checked_in_both_lanes(tmp_path, monkeypatch, in_repo,
                                                                               capsys):
    """The snapshot staleness this lane structurally cannot see is exactly what the freeze can see."""
    frozen = load_protocol(REPO / "protocol.json").corpus
    assert cli.file_digest(REPO / frozen["records_owner"]) == frozen["records_digest"]
    assert cli.file_digest(REPO / "data" / "inventory.md.json") == frozen["inventory_digest"]
    assert main(["verify", "--protocol", "protocol.json"]) == 0
    shutil.copyfile(REPO / "protocol.json", tmp_path / "keep.json")
    doc = json.loads((REPO / "protocol.json").read_text())
    doc["corpus"]["inventory_digest"] = "f" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    assert main(["verify", "--protocol", str(bad)]) == 4
    assert "inventory_digest" in capsys.readouterr().err


def test_a_claim_note_that_counts_an_arm_must_count_what_the_arm_actually_does(tmp_path):
    """R-260: a digit inside a claim note is a published figure no gate used to re-derive.

    The G3 note says the severity arm makes "20 comparisons in `verify`". Driving that arm through
    `verify`'s own callbacks with the field lists `cmd_verify` passes counts 19 -- so the frozen document
    carried a number that its own artefact contradicts, in a project whose entire §11 claim is that every
    published figure is re-derivable. This row is the gate that claim was missing: it compares the digit in
    the note against the count the arm produces, so the next arm change reddens a test instead of quietly
    falsifying a sentence in the freeze.

    Red today, by design: the note half is a value `load_protocol` reads, so correcting it costs a new
    freeze and a six-artefact re-export -- which is the controller's act, not something to sneak in here.
    """
    import json
    import re

    from autorate import report
    from autorate.cli import SEVERITY_COMPARE_FIELDS, SEVERITY_RUBRIC_FIELDS

    doc = json.loads((REPO / "protocol.json").read_text())
    note = next(c["note"] for c in doc["claims"] if c["id"] == "G3")
    claimed = re.search(r"(\d+) comparisons", note)
    assert claimed, "the G3 note no longer counts comparisons, so this row guards nothing: %r" % note[:80]

    seen = []
    report.rederive_severity(lambda label, actual, wanted: seen.append(label),
                             lambda label, actual, wanted: seen.append(label),
                             SEVERITY_COMPARE_FIELDS, SEVERITY_RUBRIC_FIELDS,
                             rubric=doc["rubric"], stamp=lambda cert: cert)
    assert int(claimed.group(1)) == len(seen), (
        "protocol.json's G3 note claims %s comparisons and the severity arm makes %d -- the digit and the "
        "arm must not be kept by hand in two places" % (claimed.group(1), len(seen)))


def test_readme_quotes_both_lane_denominators_and_neither_is_remembered(capsys, monkeypatch, tmp_path):
    """Every denominator `README.md` quotes in the command's own spelling is one this gate really prints.

    Why the row exists. The absent-lane count has been left stale in prose twice inside one document -- a
    `242` survived in a sentence about what the run *cannot* prove long after every other mention moved --
    and both lanes changed again when `docs/REPORT.md` joined the byte-compared documents. No artefact owns
    either figure, so nothing re-derived them: they lived in a person's memory of a terminal, which is the
    same failure class `docs/G5.md` was written to close, one layer down.

    Scope, deliberately narrow. Two shapes are policed: `N /N values`, the command's own output form, and
    `a N run`, the prose form that names a lane. `README.md` also transcribes `docs/G5.md`, whose lanes
    belong to the commit that transcript names (`248/248`, `283/283` -- written with no space around the
    slash). Those are a record of a measurement at another revision and are true of it; a guard that
    indicted them would be a guard against honest citation, so the spaced form is the tell between "this is
    what the command prints" and "this is what the archive said".

    The corpus-present lane is *derived* rather than run, because the archive is not a committed file and a
    row that only passes on one machine is a row CI cannot see (the same reasoning that keeps the transcript
    guard deriving its 35-check gap). It is checked directly as well whenever this machine can see the
    corpus, so a derivation that drifts from the real second lane is caught here, not in prose.

    Red if: a quoted output line disagrees with the run, its two halves disagree with each other, a
    lane-shaped number names neither lane, the lanes no longer differ by the comparisons the committed
    snapshot and the contamination arm's corpus-only checks own, or either lane stops being quoted at all.
    """
    import re

    from autorate.cli import SNAPSHOT_MACHINE_KEYS

    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus_here"))
    text = re.sub(r"\s+", " ", (REPO / "README.md").read_text())

    rc = main(["verify", "--protocol", "protocol.json"])
    printed = capsys.readouterr().out
    assert rc == 0, (rc, printed[-400:])
    measured = re.search(r"re-derived (\d+) /(\d+) values", printed)
    assert measured, printed[-400:]
    assert measured.group(1) == measured.group(2), measured.groups()
    n_absent = int(measured.group(1))

    inv = json.loads((REPO / "data" / "inventory.md.json").read_text())
    non_machine = [k for k in inv if k not in SNAPSHOT_MACHINE_KEYS]
    # The present lane is the absent lane plus the snapshot's corpus-only comparisons and the contamination
    # arm's two re-digest checks. Both parts are counts of published structure, so a check added to either arm
    # moves the derivation instead of making this row disagree with the run.
    gap = len(inv["digests"]) + len(non_machine) + len(report.CONTAMINATION_CORPUS_ONLY_CHECKS)
    n_present = n_absent + gap

    corpus_root = REPO.parent / "laya-0.3.20" / "research" / "benchmarks" / "feishu_zh"
    if (corpus_root / "data" / "manifest.json").is_file():
        monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(corpus_root))
        rc = main(["verify", "--protocol", "protocol.json"])
        present_out = capsys.readouterr().out
        assert rc == 0, (rc, present_out[-400:])
        direct = re.search(r"re-derived (\d+) /(\d+) values", present_out)
        assert direct and direct.group(1) == direct.group(2), present_out[-400:]
        assert int(direct.group(1)) == n_present, (
            "the corpus-present lane prints %s but the published structure says it should be %s = %s + %d "
            "digests + %d non-machine snapshot keys + %d corpus-only contamination checks -- the derivation "
            "this row falls back to on other machines is the thing that just disagreed with the real run"
            % (direct.group(1), n_present, n_absent, len(inv["digests"]), len(non_machine),
               len(report.CONTAMINATION_CORPUS_ONLY_CHECKS)))
        checked = "measured directly"
    else:
        checked = "derived from the committed snapshot (corpus not visible here)"

    quoted = sorted({int(m.group(1)) for m in re.finditer(r"\b(\d+) /(\d+) values", text)
                     if m.group(1) == m.group(2)})
    assert quoted, "README.md no longer quotes a lane denominator, so this row has nothing to check"
    unknown = sorted(set(quoted) - {n_absent, n_present})
    assert not unknown, (
        "README.md quotes %s as `N /N values`, which matches neither lane: this tree's `verify` prints "
        "%s with the corpus absent and %s with it present (%s) -- a remembered number, not a derived one"
        % (unknown, n_absent, n_present, checked))
    missing = sorted({n_absent, n_present} - set(quoted))
    assert not missing, (
        "README.md stopped quoting %s, which is what one of the two lanes prints; the document has to name "
        "both denominators or a reader cannot tell a corpus-less CI run from a local one" % missing)

    named = sorted({int(m.group(1)) for m in re.finditer(r"\ba (\d{3}) run\b", text, re.IGNORECASE)})
    assert named, "README.md no longer names a lane in prose, so the second shape has nothing to check"
    stray = sorted(set(named) - {n_absent, n_present})
    assert not stray, (
        "README.md calls something `a %s run`, which is neither lane this gate prints (%s absent, %s "
        "present)" % (", ".join(str(s) for s in stray), n_absent, n_present))


# ---------------------------------------------------------------------------
# Freeze round 7 (task #96): the digits a claim note states about an ARM or about ANOTHER DOCUMENT have to
# come from that arm or that document. Both rows below were written against the tree at `135549b`, where the
# G4 note's comparison count and the G5 note's parent-commit phrase were already false, and the set row was
# already satisfiable -- which is why it names what it prevents rather than claiming to have caught anything.
# ---------------------------------------------------------------------------

ARM_COUNT_NOTE_IDS = ("G1", "G3", "G4")


def _recorded_lanes(g5_text):
    """The transcript's two lanes as (absent, present) denominator pairs, read off its own command lines.

    The record prints the command's own `N /N values` spelling; a note that transcribes it writes `N/N`. The
    guard parses the record rather than trusting either spacing, so a re-export that changes the numbers
    changes what the prose has to say -- and nothing else.

    Only an `rc=0` count is a lane. The planted falsifications run the same command with the same
    `AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir` and print `rc=4  re-derived 248 /249 values`, so a parser
    that keyed on the command alone would read a plant as the clean absent lane -- measured while writing this
    row, where the first version picked up the tampered denominator and the transcription legs went red for
    the wrong reason.
    """
    lanes = {}
    for block in re.findall(r"```\n(.*?)```", g5_text, re.DOTALL):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines or not lines[0].startswith("$ "):
            continue
        counts = [m.groups() for m in re.finditer(r"^rc=0\s+re-derived (\d+) /(\d+) values", block,
                                                  re.MULTILINE)]
        if len(counts) != 1:
            continue
        if "nonexistent-corpus-dir" in lines[0]:
            lanes["absent"] = counts[0]
        elif "<corpus" in lines[0]:
            lanes["present"] = counts[0]
    return lanes


def test_the_g4_claim_note_counts_the_slice_arm_as_the_arm_actually_counts():
    r"""G4's note states the size of the slices arm, so the slices arm has to be the source of that digit.

    R-260's rule, applied to the second arm that states its own size. The note says the worst-slice run is
    re-derived by "N field comparisons plus M rubric rows"; driving `report.rederive_slices` with counting
    callbacks at the freeze's rubric gives the numbers the run really makes, and the note must agree with
    them. The G4 arm drifted because the existing row searched for `(\d+) comparisons`, which matches the G3
    spelling and cannot match "70 field comparisons plus" -- one spelling policed, two in use, which is the
    partial-re-derivation failure this repository keeps recording.

    RED when that row landed: the arm was making 76 field comparisons while the frozen note said 70, because
    `report.SLICE_N_MIN_KEY` had joined the compared fields and the sentence was not re-derived with it. The
    note edit cost a freeze and an artefact re-export, so it landed with that freeze; the digits quoted here
    are that history, and the row above is what decides the current pair.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    note = next(c["note"] for c in doc["claims"] if c["id"] == "G4")
    claimed = re.search(r"(\d+) field comparisons plus (\d+) rubric rows", note)
    assert claimed, "the G4 note no longer counts the arm, so this row guards nothing: %r" % note[:120]

    seen_field, seen_rubric = [], []
    report.rederive_slices(lambda label, actual, wanted: seen_field.append(label),
                           lambda label, actual, wanted: seen_rubric.append(label),
                           rubric=doc["rubric"])
    assert int(claimed.group(1)) == len(seen_field), (
        "protocol.json's G4 note claims %s field comparisons and the slices arm makes %d -- a digit in a "
        "frozen sentence and the arm it describes must have one owner"
        % (claimed.group(1), len(seen_field)))
    assert int(claimed.group(2)) == len(seen_rubric), (
        "the note claims %s rubric rows and the arm produces %d" % (claimed.group(2), len(seen_rubric)))


def test_every_claim_note_that_counts_an_arm_is_counted_by_a_row():
    r"""Which claim notes state an arm's size, and that each one is policed by a named row.

    The set is read from `protocol.json`, not typed: a note that starts stating a size without a row reddens
    here, which is the gap that let the G4 digit drift while the G3 digit was guarded. If a note stops
    stating a size, the row that policed it has to go in the same commit rather than pass vacuously, so the
    guard demands the names line up in both directions.

    GREEN on arrival, and that is the row's purpose: it names what it prevents. It went red during the making
    of this round in the one direction that matters -- with the G4 spelling removed from its regex the set
    collapsed to `['G3']` while two notes stated sizes.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    counting = sorted(c["id"] for c in doc["claims"]
                      if re.search(r"\d+ (?:comparisons in|field comparisons plus|quantities )", c["note"]))
    assert counting == sorted(ARM_COUNT_NOTE_IDS), (
        "the notes that state an arm's size are %s but the rows that re-derive them cover %s -- add or "
        "delete a row in this commit" % (counting, sorted(ARM_COUNT_NOTE_IDS)))


def test_the_g5_transcript_is_the_only_owner_of_its_digits_and_every_quoter_transcribes_it():
    """The frozen G5 note and README both quote `docs/G5.md`; both quotes have to match the record, byte for byte.

    Why this row exists. The note and README each restate the transcript's two lane denominators and its
    gap, and the transcript names the commit it was unpacked from. Neither restatement is derived by
    anything: when the sixth freeze moved the live denominators, the quoted 248/283 stayed, and the only
    reason that was still honest is that the numbers belong to the recorded commit -- a fact the note
    conveyed with the words "which is this document's parent". That phrase is the second defect. `protocol.json`
    is quoted verbatim into `docs/REPORT.md`, so a reader of the report resolves "this document" to the
    report, whose parent is not the transcript's commit at all; and the relation stales one commit later
    even inside the protocol, which is why the durable form names both commits.

    Red today on the deictic leg alone; the transcription legs pass today and are what stop a later
    re-export from leaving the prose behind.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    note = next(c["note"] for c in doc["claims"] if c["id"] == "G5")
    g5 = (REPO / "docs" / "G5.md").read_text()
    readme = (REPO / "README.md").read_text()

    lanes = _recorded_lanes(g5)
    assert set(lanes) == {"absent", "present"}, (
        "docs/G5.md no longer prints one count under one command per lane, so its quoters cannot be "
        "checked against it: %r" % (lanes,))
    recorded_commit = re.search(r"Produced from commit `([0-9a-f]{7,40})`", g5)
    assert recorded_commit, "docs/G5.md does not name the commit it was produced from"

    note_pairs = re.findall(r"\b(\d+)/(\d+)\b", note)
    assert len(note_pairs) == 2, (
        "the G5 note should transcribe exactly the record's two lane denominators and it carries %d "
        "slash-shaped numbers: %s" % (len(note_pairs), note_pairs))
    assert tuple(note_pairs[0]) == lanes["absent"], (
        "the note says the absent lane ran %s while docs/G5.md records %s" % (note_pairs[0], lanes["absent"]))
    assert tuple(note_pairs[1]) == lanes["present"], (
        "the note says the corpus-present lane ran %s while docs/G5.md records %s"
        % (note_pairs[1], lanes["present"]))
    gap = re.search(r"the (\d+)-check difference", note)
    assert gap, "the G5 note no longer states the lane gap, so the record's gap is unquoted: %r" % note[:120]
    assert int(gap.group(1)) == int(lanes["present"][1]) - int(lanes["absent"][1]), (
        "the note calls the gap %s checks and the recorded lanes differ by %d"
        % (gap.group(1), int(lanes["present"][1]) - int(lanes["absent"][1])))

    note_commit = re.search(r"git archive` of commit ([0-9a-f]{7,40})", note)
    assert note_commit, "the G5 note no longer names the commit the export unpacks"
    assert note_commit.group(1) == recorded_commit.group(1), (
        "the note names commit %s and docs/G5.md names itself the product of %s -- one record, two owners"
        % (note_commit.group(1), recorded_commit.group(1)))

    readme_commit = re.search(r"git archive` of commit `([0-9a-f]{7,40})`", readme)
    assert readme_commit, "README.md no longer names the commit the transcript was unpacked from"
    assert readme_commit.group(1) == recorded_commit.group(1), (
        "README.md cites commit %s as the transcript's subject and docs/G5.md says %s"
        % (readme_commit.group(1), recorded_commit.group(1)))
    readme_pairs = re.findall(r"`(\d+)/(\d+)`", readme)
    assert readme_pairs, "README.md no longer quotes the recorded denominators, so nothing checks its quote"
    assert tuple(readme_pairs[0]) == lanes["absent"] and tuple(readme_pairs[1]) == lanes["present"], (
        "README.md quotes %s where docs/G5.md records absent %s and present %s"
        % (readme_pairs, lanes["absent"], lanes["present"]))

    for label, text in (("protocol.json's G5 note", note), ("README.md", readme)):
        assert "this document's parent" not in text and "document's parent" not in text, (
            "%s resolves the transcript's commit with a deictic phrase. `docs/REPORT.md` quotes claim notes "
            "verbatim, so the referent depends on which file the reader is holding, and it is wrong from the "
            "next commit onward -- name the commits instead." % label)

    run_ids = re.findall(r"\brun `\d{6,}`", g5)
    assert not run_ids, (
        "docs/G5.md quotes a CI run id (%s). A run belongs to the push that produced it, while this "
        "document's first line names the commit it was unpacked from: the emitter carried that id as prose, "
        "and the first re-export turned it into a claim about a commit CI never ran. `tools/g5_transcript.py` "
        "now names the workflow and its jobs, and `tests/test_ci_workflow.py` owns the run-level evidence."
        % ", ".join(run_ids))


def test_the_g1_claim_note_counts_the_resplit_arm_as_the_arm_actually_counts():
    r"""G1's note states how many quantities the resplit arm compares, so that arm is the only honest source.

    The third occurrence of one defect class in three arms. `claims.G3.note` said "20 comparisons" against the
    severity arm's 19 and `claims.G4.note` said "70 field comparisons" against the slice arm's 76; both are
    policed now. G1's note then said `verify` "compares 32 quantities the artefact asserts about itself plus its
    rubric", and the existing rows could not see it: their patterns are `(\d+) comparisons` and
    `(\d+) field comparisons plus`, and neither matches a digit followed by "quantities". One spelling
    policed, three in use -- which is why the set row's regex was widened to the third spelling in this
    commit rather than leaving a note that states a size nobody re-derives.

    GREEN on arrival, and stated as such: 32 field comparisons and 5 rubric rows is what driving
    `report.rederive_resplit` with counting callbacks answers on this tree, so nothing was broken to be
    fixed here. What it makes able to fail is the next arm change: a comparison added to or removed from the
    resplit arm reddens this row instead of quietly falsifying a sentence inside the freeze. Falsified by
    planting -- the digit in the note changed to 31, the row went red naming both numbers, and
    `protocol.json` came back byte-identically with the restore checked.
    """
    doc = json.loads((REPO / "protocol.json").read_text())
    note = next(c["note"] for c in doc["claims"] if c["id"] == "G1")
    claimed = re.search(r"compares (\d+) quantities", note)
    assert claimed, "the G1 note no longer counts the resplit arm, so this row guards nothing: %r" % note[:120]

    seen, seen_rubric = [], []
    report.rederive_resplit(lambda label, actual, wanted: seen.append(label),
                            lambda label, actual, wanted: seen_rubric.append(label),
                            doc["rubric"])
    assert int(claimed.group(1)) == len(seen), (
        "protocol.json's G1 note claims %s quantities and the resplit arm makes %d -- the digit and the arm "
        "must not be kept by hand in two places" % (claimed.group(1), len(seen)))
    assert [label[len("resplit rubric."):] for label in seen_rubric] == list(report.RESPLIT_RUBRIC_FIELDS), (
        "the note says the arm compares the artefact's quantities 'plus its rubric', and the rubric rows it "
        "actually makes are %s against the %s the table declares" % (seen_rubric,
                                                                     report.RESPLIT_RUBRIC_FIELDS))


NOTE_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
              8: "eight", 9: "nine", 10: "ten"}

# The whole note is the subject, not the three spellings one row happened to know about: every numeric token
# that is not part of an identifier, a hex sha or a section sign has to be owned. Structural is decided by the
# character next to the digit -- `g1_feasibility.py`'s 1 and `9e6363a`'s 9 are inside words, `200-resplit` and
# `42 re-derivations` are not -- so the exclusion is a rule with a reason rather than a noun whitelist the next
# sentence can step around. Section signs are the one waiver this rule leaves standing, and the row below
# (`test_every_spec_section_pointer_in_the_frozen_notes_names_a_real_section`) is what closes it.
NOTE_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
NOTE_STRUCTURAL_NEIGHBOURS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_\u00a7")


def _is_structural(note: str, match) -> bool:
    before = note[match.start() - 1] if match.start() else ""
    after = note[match.end()] if match.end() < len(note) else ""
    return before in NOTE_STRUCTURAL_NEIGHBOURS or after.isalpha() or after == "_"


def _note_tokens(note: str) -> set:
    return {m.group().rstrip(",") for m in NOTE_NUMBER.finditer(note) if not _is_structural(note, m)}


def _folded_notes():
    doc = json.loads((REPO / "protocol.json").read_text())
    return {c["id"]: " ".join(c["note"].split()) for c in doc["claims"]}


# A note points at the spec either as `§9` or as "section 9". The first spelling is invisible to the residue
# rule -- a section sign is a structural neighbour -- so before this row a pointer to a section the spec does
# not have was waived, not checked. Both spellings are one claim with one owner: the spec's own heading list.
NOTE_SECTION_POINTER = re.compile("(?:\u00a7|sections? )(\\d+)")
SPEC_MD = "docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md"


def _spec_sections():
    return {m.group(1) for m in re.finditer(r"^## (\d+)\.", (REPO / SPEC_MD).read_text(), re.M)}


def test_every_spec_section_pointer_in_the_frozen_notes_names_a_real_section(in_repo):
    """The frozen notes cite the spec by number; the numbers have to exist there.

    Plant that proves this row can fail: in a `git archive` copy, change G1's note "section 9" to "section 99"
    and re-emit `protocol.json` -- the row reddens naming 99, and the residue row reddens on it too.
    """
    sections = _spec_sections()
    assert len(sections) >= 10, "the spec's headings are no longer enumerable, so nothing owns a pointer"
    for cid, note in sorted(_folded_notes().items()):
        pointers = set(NOTE_SECTION_POINTER.findall(note))
        assert pointers <= sections, "%s points at section(s) %s, which %s has no top-level heading for" % (
            cid, sorted(pointers - sections, key=int), SPEC_MD)


def test_the_frozen_notes_count_of_tasks_and_cases_is_derived_from_the_files_they_name(in_repo):
    """Two counts the notes state had no owner (review M5): the task count and the case count.

    Both are functions of committed files, so both are recomputed here rather than agreed with the prose:
    G1's task count is the non-synthetic rows of `data/resplit_200.json` and its split count is the artefact's
    own `resplits`, and G4's case count is the line count of every file `report.SLICE_RECORDS` declares. A
    publication that adds a corpus, or a resplit budget that changes, reddens the sentence that used to be
    right. The plant that proves this row can fail is in `docs/VERIFICATION.md`'s freeze checklist.
    """
    notes = _folded_notes()
    resplit = report.read_resplit(REPO / report.RESPLIT_JSON)
    decision = [t for t in resplit["tasks"] if "synthetic" not in str(t["label"])]
    assert decision, "no decision-task rows, so the sentence this row polices has no subject"
    assert "all %s decision tasks certify in %d of %d splits" % (
        NOTE_WORDS[len(decision)], 0 if all(not t["certificates_issued"] for t in decision) else -1,
        resplit["resplits"]) in notes["G1"], (
        "G1's note states a task count or a split count the resplit artefact does not: %d tasks, %d splits"
        % (len(decision), resplit["resplits"]))

    cases = sum(sum(1 for _ in (REPO / rel).open()) for rel in report.SLICE_RECORDS)
    assert "{:,} cases".format(cases) in notes["G4"], (
        "G4's note states a case count that is not the line count of the files it certifies (%d)" % cases)
    assert "%d slices" % len(report.SLICE_RECORDS) in notes["G4"], (
        "the published run refuses %d slices; the note's slice count must be that number"
        % len(report.SLICE_RECORDS))


DECLARED_UNOWNED_NOTE_DIGITS = {
    # Each entry is a digit a frozen note states that NO row recomputes yet, with the place that computes it.
    # The row below refuses a new addition and refuses a listed token that has left the note, so this table is
    # an inventory rather than an ignore list (review M4: the old enumeration row could not see a fourth note
    # or a fourth spelling, and a digit outside three literals stayed silently unowned).
    # G2's whole audit family and G3's population family now have owner rows below; only the knob-cell
    # sweep's two counts and the upstream-quoted pair remain, each named with the site that computes it.
    "G3": {"4", "64"},
    "G4": {"0.000", "0.952", "100"},
}


def test_no_frozen_note_states_a_quantity_digit_that_neither_a_row_nor_the_inventory_owns(in_repo, monkeypatch):
    """Invert the arm-count row: take every number a note states, then subtract what is derived.

    `test_every_claim_note_that_counts_an_arm_is_counted_by_a_row` matches three spellings and compares note
    IDS, so a note that states a size in new words -- or a fourth note that states one at all -- stays green.
    The first version of THIS row nearly repeated that mistake with a longer list: it matched digits followed
    by a noun, and the review's plant sentence "the audit arm makes 42 re-derivations in verify" passed it,
    because "re-derivations" was not in the noun list. The plant is in the ledger and the mechanism is now a
    rule with one predicate: a number is in scope unless its neighbour is a letter or an underscore, which
    makes `g1_feasibility.py`'s 1, `9e6363a`'s 9 and `§14` structural and leaves `42 re-derivations` counted.
    What that gives up is stated rather than hidden: a quantity written fused into an identifier would be
    read as an identifier.

    Everything in scope must be either recomputed below or named in `DECLARED_UNOWNED_NOTE_DIGITS` with the
    site that computes it, and three more assertions keep the inventory honest: a token that gains a real
    owner has to leave the list, a token that leaves the note has to leave it too, and a token cannot be both
    declared unowned and derived here.
    """
    notes = _folded_notes()
    doc = json.loads((REPO / "protocol.json").read_text())
    seen_slices, seen_slice_rubric = [], []
    report.rederive_slices(lambda label, actual, wanted: seen_slices.append(label),
                           lambda label, actual, wanted: seen_slice_rubric.append(label), doc["rubric"])
    seen_resplit, seen_resplit_rubric = [], []
    report.rederive_resplit(lambda label, actual, wanted: seen_resplit.append(label),
                            lambda label, actual, wanted: seen_resplit_rubric.append(label), doc["rubric"])
    seen_sev, seen_sev_rubric = [], []
    report.rederive_g1_feasibility(lambda label, actual, wanted: seen_sev.append(label),
                                   lambda label, actual, wanted: seen_sev_rubric.append(label), doc["rubric"])

    rubric = doc["rubric"]
    alpha = rubric["alpha"]
    n_slices = len(report.SLICE_RECORDS)
    corrected = alpha / n_slices
    family = corrected * n_slices * 3
    option_counts = set()
    for rel in report.SLICE_RECORDS:
        with (REPO / rel).open() as handle:
            for line in handle:
                option_counts.add(len(json.loads(line)["options"]))
    slice_run = report.read_slices(REPO / report.SLICE_JSON)["run"]
    certified_slices = sum(1 for c in slice_run["per_group"].values() if c["feasible"])
    g4_owned = ({"{:,}".format(sum(sum(1 for _ in (REPO / rel).open()) for rel in report.SLICE_RECORDS)),
                 "%d" % len(seen_slices), "%d" % len(seen_slice_rubric), "%d" % n_slices}
                | set(str(v) for v in option_counts)
                | _g1_num(alpha) | _g1_num(corrected) | _g1_num(family) | _g1_num(1 - family)
                | {"%d" % slice_run["n_claims"], "%d" % certified_slices})
    assert option_counts, "the committed MASSIVE rows carry no option_count, so the note has nothing to state"
    # G2's note states the audit's `laya`/`confidence` row. The row is produced from the committed records by
    # the same function that renders `docs/AUDIT.md`, which `verify` already byte-compares, so the note's five
    # digits are derived here rather than agreed with the prose.
    from autorate.audit import audit_fields
    audit_recs = report.load_records(REPO / "data" / "records_feishu.jsonl")
    conf = audit_fields(audit_recs["laya"])["confidence"]
    g2_audit = ({"%d" % conf["automated_cases"], "%d" % conf["n_cases"], "%d" % conf["erroneous_cases"]}
                | _g1_num(conf["measured_error"]) | _g1_num(conf["implied_error"])
                | _g1_num(conf["bound"]) | _g1_num(conf["multiple"]))

    # G3's note states the ordinal contrast's own population: records, cases, empty sets, the over-top count
    # and the set certificate's marginal bound. All five come out of the generator and certifiers the contrast
    # test uses, through the shared helper so this is the same pair, not a look-alike.
    from _records import build_ordinal, g3_pair
    from autorate.ordinal import interval_set
    rows = build_ordinal(n=1200, seed=5, shift=0.0, error_rate=0.0, temp=1.4)
    score, sev = g3_pair(rows)
    ev_ids = set(sev.meta["eval_ids"])
    ev = [r for r in rows if r.id in ev_ids]
    over_hi = empty = 0
    for r in ev:
        C = interval_set(r.probs, score.qhat)
        if not C:
            empty += 1
            continue
        over_hi += r.gold_index > C[-1]
    g3_contrast = ({"%d" % len(ev), "%d" % len({r.case_id for r in ev}), "%d" % empty, "%d" % over_hi}
                   | _g1_num(score.marginal_error_bound))

    resplit_doc = report.read_resplit(REPO / report.RESPLIT_JSON)
    control = [t for t in resplit_doc["tasks"] if "synthetic" in str(t["label"])]
    rates = {"%.3f" % c["violation_rate"] for c in control if c["violation_rate"] is not None}
    # G4 now states the contamination arm's sizes and the gap it publishes; both come from the artefacts.
    # The contamination arm's size is a lane fact (two checks exist only where the corpus is visible), and the
    # note quotes the corpus-absent pair, so the derivation is pinned to that lane rather than inherited.
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", "/nonexistent-corpus-dir")
    contamination_field, contamination_budget = [], []
    report.rederive_contamination(lambda label, actual, wanted: contamination_field.append(label),
                                  lambda label, actual, wanted: contamination_budget.append(label))
    pin = json.loads((REPO / report.CONTAMINATION_PIN).read_text())
    gap = report.build_contamination(pin)["headline"]
    g4_owned = (g4_owned | {"%d" % len(contamination_field), "%d" % len(contamination_budget),
                            "%d" % len(pin["rows"]), "%d" % len(pin["excluded"])}
                | {t for key in ("delta_hat", "R_in", "R_out") for t in _g1_num(abs(gap[key]))}
                | {t for end in gap["interval"] for t in _g1_num(abs(end))})
    owned = {
        "G1": {"%d" % resplit_doc["resplits"],
               "%d" % len(seen_resplit), "%d" % len(seen_resplit_rubric), "0"} | rates,
        "G2": g2_audit,
        "G3": {"19", "%d" % len(seen_sev), "%d" % len(seen_sev_rubric)} | g3_contrast,
        "G4": g4_owned,
        "G5": {"249", "284", "35", "0"},
    }
    # G1's note quotes spec section 14's kill threshold, so the spec is its only honest source: read the
    # number there and require the note to carry that spelling. A threshold that moves in the spec reddens
    # the note, which is the whole point of transcribing rather than restating.
    spec = (REPO / SPEC_MD).read_text()
    kill = re.search(r"worst-group certified autorate < (\S+) on all tasks", spec)
    assert kill, "spec section 14's kill criterion changed wording, so the note's threshold lost its source"
    owned["G1"] = owned["G1"] | {kill.group(1)}
    assert kill.group(1) in notes["G1"], (
        "spec section 14 says %s and G1's note quotes a different threshold" % kill.group(1))

    contract = {str(v) for k, v in vars(cli).items() if k.startswith("EXIT_") and isinstance(v, int)}
    sections = _spec_sections()
    for cid, note in sorted(notes.items()):
        stated = _note_tokens(note)
        # A section pointer is a claim about the spec's structure, not a quantity, so the spec owns it -- but
        # only where the heading exists. A pointer to a section the spec does not have stays in the residue.
        stated = stated - (set(NOTE_SECTION_POINTER.findall(note)) & sections)
        # An `rc=N` digit is owned by the published exit-code contract, and only if the contract has that code:
        # a note citing exit 5 would be a claim about an exit code `cli.main` cannot return.
        rc_digits = {m.group(1) for m in re.finditer(r"rc=(\d+)", note)}
        assert rc_digits <= contract, "%s cites %s, outside the published exit codes %s" % (
            cid, sorted(rc_digits - contract), sorted(contract))
        stated = stated - rc_digits
        residue = stated - owned[cid] - DECLARED_UNOWNED_NOTE_DIGITS.get(cid, set())
        assert not residue, "%s states digit(s) %s that no row re-derives and the inventory does not name" % (
            cid, sorted(residue))
        stale = {t for t in DECLARED_UNOWNED_NOTE_DIGITS.get(cid, set()) if t not in stated}
        assert not stale, "%s no longer states %s: delete it from DECLARED_UNOWNED_NOTE_DIGITS" % (cid, sorted(stale))
        both = DECLARED_UNOWNED_NOTE_DIGITS.get(cid, set()) & owned[cid]
        assert not both, "%s declares %s unowned while this row derives it -- the inventory is lying" % (
            cid, sorted(both))


def _g1_num(value) -> str:
    """The digit spellings a note may use for one value, so an owner match does not depend on formatting."""
    out = {"%s" % value}
    if isinstance(value, float):
        for places in (2, 3, 4, 6):
            out.add("%.*f" % (places, value))
        out.add("%s" % float("%s" % value))
    return {str(v) for v in out}


def _published_surface_stems():
    """The stems of every committed artefact's own `producer` field: what the artefacts say produced them."""
    stems = set()
    for path in sorted((REPO / "data").glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except ValueError:
            continue
        producer = doc.get("producer") if isinstance(doc, dict) else None
        if isinstance(producer, str):
            stems.add(producer.rsplit("/", 1)[-1][:-len(".py")])
    return stems


def test_readme_s_unpublished_list_agrees_with_the_artefacts_producers(in_repo):
    """README's "written and tested, but not yet published as evidence" claim is policed against the artefacts.

    Red when it was written: README still named `contamination.py` as unpublished after the eleventh freeze
    committed `data/contamination_probe.json`, whose own `producer` field names the contamination tool -- the
    document contradicted the G1 claim note in the same release, and no row could see it because nothing read
    the sentence. The predicate is the artefact's `producer`, so a surface is caught leaving the list by its
    evidence landing, not by someone remembering prose. The matching is substring-on-stem, which errs toward
    calling a surface published: the safe direction, since the cost is a README sentence that has to be edited.
    """
    from autorate.report import UNPUBLISHED_SURFACES

    readme = re.sub(r"\s+", " ", (REPO / "README.md").read_text())
    listed = re.search(r"not yet published as evidence: (.*?) Each of", readme)
    assert listed, "README no longer states the unpublished list, so the table has no witness"
    named = sorted(set(re.findall(r"`([a-z0-9_]+\.py)`", listed.group(1))))
    assert named == sorted(UNPUBLISHED_SURFACES), (
        "README names %s and `report.UNPUBLISHED_SURFACES` names %s -- one list, two places that remember it"
        % (named, sorted(UNPUBLISHED_SURFACES)))
    stems = _published_surface_stems()
    assert stems, "no committed artefact names a producer, so this row would certify anything as unpublished"
    for module in UNPUBLISHED_SURFACES:
        stem = module[:-len(".py")]
        assert not any(stem in producer for producer in stems), (
            "%s is listed as unpublished while a committed artefact names %s as its producer"
            % (module, [p for p in stems if stem in p]))
    for sentence in re.split(r"(?<=[.]) ", readme):
        if "unpublished" not in sentence:
            continue
        for producer in stems:
            assert producer.split("_")[0] not in sentence or producer in sentence, (
                    "README calls %r unpublished in %r while an artefact names it as produced" % (producer, sentence[:160]))
