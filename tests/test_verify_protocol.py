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
    assert "not_measured" in joined, joined             # G3/G4/G5 until their surfaces exist


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
    """The durable half of the re-export: all five artefacts, one digest, the document in this checkout.

    Read through `CERT_COMPARE_FIELDS` rather than a typed list, because that tuple has one owner and a
    second copy of it in a test is how a field that exists only on the dataclass (a property, not JSON)
    gets asserted as a key of the stored document. This test's first version did exactly that and was red
    on a green tree.
    """
    digest = protocol_digest(load_protocol(REPO / "protocol.json"))
    paths = sorted(cli.CERTS.values()) + sorted(path for _, path in report.MASSIVE_CERTIFICATES.values())
    assert len(paths) == 5, paths
    for path in paths:
        doc = json.loads((REPO / path).read_text())
        assert doc["meta"].get("protocol_digest") == digest, path
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
