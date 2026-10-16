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
    snapshot owns, or either lane stops being quoted at all.
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
    gap = len(inv["digests"]) + len(non_machine)
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
            "the corpus-present lane prints %s but the committed snapshot says it should be %s = %s + %d "
            "digests + %d non-machine keys -- the derivation this row falls back to on other machines is "
            "the thing that just disagreed with the real run"
            % (direct.group(1), n_present, n_absent, len(inv["digests"]), len(non_machine)))
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

    RED today on this tree: the arm makes 76 field comparisons and the frozen note says 70, because
    `report.SLICE_N_MIN_KEY` joined the compared fields and the sentence was not re-derived with it. The note
    edit costs a freeze and a six-artefact re-export, so it lands with the seventh freeze.
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
    policed now. G1's note says `verify` "compares 32 quantities the artefact asserts about itself plus its
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
