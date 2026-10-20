"""Task 72 items 1 and 2: the severity command surface, its serialisation shape, the published artefact.

G3's engine has been tested since Plan B2 landed and nothing shipped could reach it: `autorate verify`, CI
and a reader of the documents all answered the one-sided guarantee by pointing at a library. These rows are
the difference between "a function that works when a test calls it" and "a program that produces the
artefact". R-170's first obligation is the reason the exit codes are asserted at `cli.main` and not at the
function: a refusal's exit code is a claim about the shipped program, and until a command invokes
`certify_severity` it is a claim about a test.

What is pinned here, in order:

* the serialisation shape (`severity.SEVERITY_SHAPE_VERSION`), round-tripping, and both directions of the
  cross-shape refusal -- a set certificate is not a severity certificate and neither reading may be silent;
* the command `autorate severity <records>` and its exit codes 0 / 2 / 3 / 4, with the two refusals R-170
  recorded as unreachable-by-a-command now reached through it, and no path to rc 1;
* the published ordinal artefact, `verify`'s re-derivation of it in BOTH lanes, its protocol stamp, the
  named refusal at exit 4 when the table's own file is absent or wrong-shaped, and the denominator row
  that proves the new checks are counted rather than claimed;
* the rubric ownership ruling: `severity.py`'s signature `0.05`s are library defaults the published path
  never consults, proved by moving them and showing the published numbers do not move with them.

Item 3 -- the falsification control for G3 -- is deliberately NOT here. It is the controller's, and a
control that has to be able to answer "no" is not this file's subject.
"""
import ast
import dataclasses
import json
import re
from pathlib import Path

import pytest

from autorate import cli, report, severity
from autorate.certificate import ALPHA, DELTA, SEED, SHAPE_VERSION, Certificate, CertificateShapeMismatch
from autorate.cli import main
from autorate.protocol import load_protocol, protocol_digest
from autorate.severity import (DIRECTIONS, SEVERITY_SHAPE_KEY, SEVERITY_SHAPE_VERSION,
                               SeverityCertificate, SeverityShapeMismatch, certify_severity)

REPO = Path(cli.__file__).resolve().parents[2]
# The population the published artefact is made from, in the one owner's parameters (ruling R-69 puts
# `build_ordinal` in `tests/_records.py`). `CLEAN` is the comparison population `tests/test_severity.py`
# already measures the one-sided claim on, so the published artefact and the suite's rows describe one
# population rather than two.
ORDINAL = dict(n=1200, seed=5, shift=0.1, temp=2.0)


@pytest.fixture
def in_repo(monkeypatch):
    monkeypatch.chdir(REPO)


def _cert(**kw):
    from _records import build_ordinal

    return certify_severity(build_ordinal(**{**ORDINAL, **kw}), alpha=ALPHA, delta=DELTA,
                            direction="under", seed=SEED)


def _ordinal_records_file(tmp_path, name="records_ordinal.jsonl", **kw):
    """The published population, written to a scratch path through the generator's one owner.

    The file is named, and an existing name is a refusal rather than an overwrite: two callers of this
    helper with different `kw` were measured to write the SAME path, so the second silent rewrite replaced
    the certified 1200-record population with a 60-record one and the sweep that meant to walk rc 0 saw
    rc 3. A fixture that quietly collides is worse than one that fails.
    """
    from _records import build_ordinal

    path = tmp_path / name
    assert not path.exists(), "%s already holds a different population" % name
    recs = build_ordinal(**{**ORDINAL, **kw})
    path.write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in recs))
    return path


def rc(argv):
    """`main`'s exit code, with argparse's own usage refusal folded in at its own code.

    A flag the parser cannot read never reaches a command function: argparse raises `SystemExit(2)`, which
    is the contract's 2 by a different door. Asserting the code here -- rather than letting a `SystemExit`
    sail past the test -- is what keeps "no path to rc 1" a statement about the whole surface instead of
    about the arms `main` catches.
    """
    try:
        return main(argv)
    except SystemExit as exc:
        assert exc.code == 2, exc.code
        return 2


# --- the serialisation shape ---------------------------------------------------------------------


def test_a_severity_certificate_round_trips_through_json_field_for_field():
    """`SeverityCertificate` had no serialisation surface at all; this is it, and it is lossless.

    Every field is compared, not just the headline numbers: `envelope` has to come back as a tuple (a list
    would make the loaded artefact unequal to the one produced, and `verify` compares it whole) and `meta`
    as the dict the producer wrote.
    """
    cert = _cert()
    assert cert.feasible, cert.summary()
    doc = json.loads(cert.to_json())
    assert doc[SEVERITY_SHAPE_KEY] == SEVERITY_SHAPE_VERSION, sorted(doc)
    back = SeverityCertificate.from_dict(doc)
    assert back == cert
    assert back.to_json() == cert.to_json()


def test_a_refused_severity_certificate_round_trips_too():
    """A refusal is a published-shaped artefact as well: rc 3 travels inside the bytes."""
    from _records import build_ordinal

    refused = certify_severity(build_ordinal(n=60, seed=5, shift=0.1, repeats=1), alpha=ALPHA,
                               delta=DELTA, direction="under", seed=SEED)
    assert not refused.feasible, refused.summary()
    assert SeverityCertificate.from_dict(json.loads(refused.to_json())) == refused


def test_the_severity_shape_tag_is_not_the_set_shape_version():
    """Reusing `certificate.SHAPE_VERSION` for a different field set would be a false statement.

    A tag says which shape the bytes are in; two shapes sharing one number is a tag that cannot fail.
    """
    assert SEVERITY_SHAPE_VERSION != SHAPE_VERSION, (SEVERITY_SHAPE_VERSION, SHAPE_VERSION)
    assert SEVERITY_SHAPE_KEY == "shape", SEVERITY_SHAPE_KEY
    severity_names = {f.name for f in dataclasses.fields(SeverityCertificate)}
    set_names = {f.name for f in dataclasses.fields(Certificate)}
    assert severity_names != set_names, (severity_names, set_names)
    assert {"ahat", "direction", "price_bound"} <= severity_names, severity_names
    assert {"beta", "method", "qhat"} <= set_names, set_names


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.pop(SEVERITY_SHAPE_KEY), "no 'shape' key"),
    (lambda d: d.update({SEVERITY_SHAPE_KEY: 99}), "found shape 99"),
    (lambda d: d.pop("bound"), "missing"),
    (lambda d: d.update({"qhat": 0.9, "beta": 0.05, "method": "aps"}), "unknown"),
    (lambda d: d.update({"ahat": "3"}), "a reported level"),
    (lambda d: d.update({"bound": "0.04"}), "is a probability"),
    (lambda d: d.update({"meta": "not a mapping"}), "meta"),
])
def test_an_unknown_severity_shape_is_refused_by_name(mutate, needle):
    """A stale, foreign or tampered artefact is told what it is, by name, as a `ValueError` subclass.

    The type arms matter as much as the messages: `"3"` in the `ahat` slot is the comparison
    `not 0 <= "3"` answering with a `TypeError`, and `cli.main` maps no `TypeError` to an exit code -- rc 1,
    the one number the 0/2/3/4 contract forbids, arriving through the contents of a published file.
    """
    doc = json.loads(_cert().to_json())
    mutate(doc)
    with pytest.raises(SeverityShapeMismatch) as caught:
        SeverityCertificate.from_dict(doc)
    assert needle in str(caught.value), str(caught.value)


def test_a_set_certificate_is_not_read_as_a_severity_certificate_and_vice_versa():
    """The two shapes refuse each other in both directions, and each names the shape it found.

    `report.read_certificate` is bound to the set shape and was the only reader in the tree. A severity
    document handed to it -- or the reverse -- must refuse by version, not be believed, and not crash.
    """
    set_doc = json.loads((REPO / report.CERTS["laya"]).read_text())
    with pytest.raises(SeverityShapeMismatch) as caught:
        SeverityCertificate.from_dict(set_doc)
    assert "found shape %d" % SHAPE_VERSION in str(caught.value), str(caught.value)
    assert "set" in str(caught.value).lower(), str(caught.value)

    with pytest.raises(CertificateShapeMismatch) as caught:
        Certificate.from_dict(json.loads(_cert().to_json()))
    assert "found shape %d" % SEVERITY_SHAPE_VERSION in str(caught.value), str(caught.value)
    # The clause, not only the version number: `certificate.py` names the severity fields it found and says
    # which command produces them, because "regenerate it with `autorate certify`" is an instruction that
    # cannot produce this artefact. Emptying the field list (`foreign = []`) leaves the version sentence
    # intact and the guidance gone, so without these assertions the whole clause is decoration.
    text = str(caught.value)
    for name in ("ahat", "direction", "price_bound", "override_bound", "measured_violation"):
        assert name in text, (name, text)
    assert "`autorate severity` is its producer" in text, text
    assert "regenerate it with `autorate certify`" in text, text


def test_read_severity_certificate_accepts_the_published_bytes_and_refuses_a_wrong_shape(tmp_path):
    cert = _cert()
    good = tmp_path / "good.json"
    good.write_text(cert.to_json())
    assert report.read_severity_certificate(good) == cert

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**json.loads(cert.to_json()), SEVERITY_SHAPE_KEY: 77}))
    with pytest.raises(SeverityShapeMismatch):
        report.read_severity_certificate(bad)


# --- the command, and its exit codes -----------------------------------------------------------


def test_severity_command_certifies_and_writes_the_artefact(tmp_path, capsys):
    out = tmp_path / "sev.json"
    records = _ordinal_records_file(tmp_path)
    code = rc(["severity", str(records), "--direction", "under", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 0, (code, captured.out, captured.err)
    assert "severity certificate" in captured.out, captured.out
    assert "envelope:" in captured.out, captured.out
    doc = json.loads(out.read_text())
    assert doc[SEVERITY_SHAPE_KEY] == SEVERITY_SHAPE_VERSION
    assert doc["feasible"] is True
    assert "protocol_digest" not in doc["meta"], "a run with no --protocol stays unstamped"


def test_the_command_reproduces_the_published_artefact_byte_for_byte(tmp_path, in_repo):
    """The committed artefact is this command's output, not a file somebody typed.

    Re-run at the published arguments and compare bytes. A published artefact nobody can re-produce is the
    defect class R-168 was written for, and the byte comparison is what makes "emitted by the command" a
    checked statement instead of a sentence.
    """
    _records_path, cert_path, _d = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    published = (REPO / cert_path).read_text()
    out = tmp_path / "again.json"
    code = rc(["severity", str(REPO / report.SEVERITY_RECORDS), "--direction", "under",
               "--protocol", "protocol.json", "--out", str(out)])
    assert code == 0, code
    assert out.read_text() == published


def test_severity_command_writes_the_protocol_digest_when_the_flag_names_one(tmp_path, in_repo):
    out = tmp_path / "sev.json"
    records = _ordinal_records_file(tmp_path)
    assert rc(["severity", str(records), "--direction", "under", "--protocol", "protocol.json",
               "--out", str(out)]) == 0
    digest = protocol_digest(load_protocol(REPO / "protocol.json"))
    assert json.loads(out.read_text())["meta"]["protocol_digest"] == digest


def test_a_rubric_flag_that_argues_with_its_own_protocol_is_usage_two(tmp_path, in_repo, capsys):
    """R-199's freeze, applied to the ordinal gate: the protocol is the rule, not a suggestion."""
    records = _ordinal_records_file(tmp_path)
    code = rc(["severity", str(records), "--direction", "under", "--protocol", "protocol.json",
               "--delta", "0.10", "--out", str(tmp_path / "sev.json")])
    err = capsys.readouterr().err
    assert code == 2, (code, err)
    assert "--delta" in err and "protocol.json" in err, err
    assert not (tmp_path / "sev.json").exists(), "a refused run wrote an artefact anyway"


def test_a_refusal_exits_three_and_names_its_reason(tmp_path, capsys):
    """The sample is short: a result, not a crash, and not the operator's mistake either."""
    records = _ordinal_records_file(tmp_path, n=60, repeats=1)
    out = tmp_path / "sev.json"
    code = rc(["severity", str(records), "--direction", "under", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 3, (code, captured.out, captured.err)
    assert "NOT_CERTIFIABLE" in captured.out, captured.out
    doc = json.loads(out.read_text())
    assert doc["feasible"] is False and doc["reason"], doc
    for name in ("ahat", "bound", "price_bound", "override_bound", "measured_violation"):
        assert doc[name] is None, (name, doc[name])


def test_a_budget_the_owner_refuses_is_usage_two_reached_by_a_command(tmp_path, in_repo, capsys):
    """R-170's first obligation: the `--delta 0.40` refusal had no path a user could walk.

    It is `correction.joint_level`'s `ValueError` and `main` maps it to 2. Asserted at the entry point
    because until a command reaches it the exit code is a statement about a test.
    """
    records = _ordinal_records_file(tmp_path)
    code = rc(["severity", str(records), "--direction", "under", "--delta", "0.40",
               "--out", str(tmp_path / "s.json")])
    err = capsys.readouterr().err
    assert code == 2, (code, err)
    assert "not a probability" in err, err


def test_a_non_probability_budget_is_usage_two(tmp_path, capsys):
    records = _ordinal_records_file(tmp_path)
    code = rc(["severity", str(records), "--direction", "under", "--alpha", "1.5",
               "--out", str(tmp_path / "s.json")])
    assert code == 2, (code, capsys.readouterr().err)


def test_the_naive_two_sided_direction_is_refused_by_a_command_naming_the_curve(tmp_path, capsys):
    """§6.1's non-monotone loss was refused only inside a test; `--direction` walks the same refusal."""
    records = _ordinal_records_file(tmp_path)
    code = rc(["severity", str(records), "--direction", "both_sides_sum",
               "--out", str(tmp_path / "s.json")])
    err = capsys.readouterr().err
    assert code == 2, (code, err)
    assert "not monotone" in err, err


def test_a_population_with_no_ordinal_record_is_usage_two_naming_the_subject(tmp_path, capsys):
    from _records import choice_record

    choice_only = tmp_path / "choice.jsonl"
    rows = [choice_record(id="r%d" % i, case_id="c%d" % i).to_dict() for i in range(200)]
    choice_only.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    code = rc(["severity", str(choice_only), "--direction", "under",
               "--out", str(tmp_path / "s.json")])
    err = capsys.readouterr().err
    assert code == 2, (code, err)
    assert "score" in err, err


def test_a_missing_records_path_is_usage_two_not_a_crash(tmp_path, capsys):
    code = rc(["severity", str(tmp_path / "nope.jsonl"), "--direction", "under",
               "--out", str(tmp_path / "s.json")])
    assert code == 2, (code, capsys.readouterr().err)


def test_the_documented_directions_are_the_closed_set_reachable_from_the_parser():
    """The parser's `choices` is `severity.DIRECTIONS`, so the CLI cannot invent a fourth family."""
    parser = cli.build_parser()
    sub = parser._subparsers._group_actions[0].choices["severity"]
    action = next(a for a in sub._actions if a.dest == "direction")
    assert tuple(action.choices) == tuple(DIRECTIONS), action.choices


# --- the `--doc` arm, which publishes the artefact and its document together ---------------------


def test_doc_writes_the_published_pair_the_command_is_named_for(tmp_path, in_repo):
    """`--doc` is the only way the tracked document is produced, so its bytes are the command's claim.

    Run in a staged copy of the committed trees, because the guard only admits the run that names the
    published paths -- and a passing `--doc` arm writes those paths. Asserting the pair reproduces the
    committed bytes is what turns "the artefact and its document land in one commit" (PF-D-3's rule) from a
    sentence into a checked statement: an artefact re-exported without re-rendering its document, or the
    reverse, fails here rather than in `verify`'s byte comparison after somebody else commits it.
    """
    from test_cli import run, stage_committed_tree

    work = tmp_path / "checkout"
    stage_committed_tree(work)
    p = run("severity", "data/records_ordinal_synthetic.jsonl", "--direction", "under",
            "--protocol", "protocol.json", "--out", "data/cert_severity_ordinal.json",
            "--doc", "docs/SEVERITY.md", cwd=work)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (work / "data" / "cert_severity_ordinal.json").read_text() == \
        (REPO / report.SEVERITY_CERTS[report.SEVERITY_LABEL][1]).read_text(), p.stdout
    assert (work / "docs" / "SEVERITY.md").read_text() == (REPO / cli.SEVERITY_MD).read_text(), p.stdout


@pytest.mark.parametrize("extra,needle", [
    (["--out", "other.json"], "--out"),
    (["--direction", "over"], "direction"),
])
def test_doc_refuses_before_writing_anything_else(tmp_path, monkeypatch, in_repo, capsys, extra, needle):
    """The guard runs before the artefact is written, and it checks the direction the table declares.

    Both arms were measured against the code as adopted: with `--out other.json` the command exited 2 while
    `other.json` sat on disk, so its own refusal text ("Nothing was written") and its help ("writing
    nothing") were false; and `--direction over` at the published paths exited 0 and rewrote the artefact as
    an `over` certificate while the freshly-rendered document's bullet still said `under`, because the guard
    compared only `SEVERITY_CERTS[label][:2]` and left out the element the table exists to carry.

    The table is re-pointed at a scratch certificate path so a guard that fails open cannot rewrite the
    tracked artefact, which would leave the suite asserting against bytes it just changed.
    """
    _records_path, cert_path, _direction = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    published_out = str(tmp_path / Path(cert_path).name)
    table = {label: (records, published_out, direction)
             for label, (records, _stored, direction) in sorted(report.SEVERITY_CERTS.items())}
    monkeypatch.setattr(cli, "SEVERITY_CERTS", table)
    monkeypatch.setattr(report, "SEVERITY_CERTS", table)
    written = tmp_path / "other.json"
    out = str(written) if "--out" in extra else published_out
    direction = extra[extra.index("--direction") + 1] if "--direction" in extra else "under"
    argv = ["severity", report.SEVERITY_RECORDS, "--direction", direction,
            "--protocol", "protocol.json", "--out", out, "--doc", str(tmp_path / "SEVERITY.md")]
    code = rc(argv)
    captured = capsys.readouterr()
    assert code == 2, (code, captured.out, captured.err)
    assert needle in captured.err, captured.err
    assert not written.exists(), "the refusal wrote an artefact, and says it wrote nothing"
    assert not (tmp_path / "SEVERITY.md").exists(), "the refusal wrote the published document"
    assert not Path(published_out).exists(), "the refusal wrote the published certificate"


def test_no_severity_command_path_exits_one(tmp_path, capsys):
    """The contract is 0/2/3/4, so every arm of this surface is walked and the set is checked.

    The codes are pinned per arm, not just as a set: a bare `== {0, 2, 3}` was satisfied by a fixture whose
    two populations shared one filename, which made the certified arm refuse at 3 and left the 0 arriving
    from nowhere the test could name. One entry per argv says which door each code comes out of, so an arm
    that stops being reachable reddens this row instead of quietly shrinking the set.
    """
    good = _ordinal_records_file(tmp_path, name="good.jsonl")
    short = _ordinal_records_file(tmp_path, name="short.jsonl", n=60, repeats=1)
    codes = []
    for argv in ([str(good), "--direction", "under"],
                 [str(short), "--direction", "under"],
                 [str(good), "--direction", "both_sides_sum"],
                 [str(good), "--direction", "nonsense"],
                 [str(good), "--direction", "under", "--seed", "not-an-int"],
                 [str(good), "--direction", "under", "--delta", "0.40"],
                 [str(tmp_path / "absent.jsonl"), "--direction", "under"]):
        codes.append(rc(["severity"] + argv + ["--out", str(tmp_path / "s.json")]))
        capsys.readouterr()
    # 0 certified, 3 too few records, 2 for the non-monotone direction, the unparseable direction, the
    # non-integer seed (argparse's own door), the budget the owner refuses, and the absent records file.
    assert codes == [0, 3, 2, 2, 2, 2, 2], codes
    assert set(codes) <= {0, 2, 3, 4}, codes


# --- the published artefact, and `verify`'s re-derivation of it ---------------------------------


def test_the_table_declares_one_published_ordinal_artefact():
    """One row, its two paths, and the direction the publication -- not the artefact -- declares."""
    assert list(report.SEVERITY_CERTS) == [report.SEVERITY_LABEL], report.SEVERITY_CERTS
    records_path, cert_path, direction = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    assert records_path == report.SEVERITY_RECORDS, records_path
    assert direction in DIRECTIONS and direction == "under", direction
    for rel in (records_path, cert_path):
        assert (REPO / rel).is_file(), rel
        assert not str(rel).startswith("/"), rel
        assert not re.search(r"/(Users|home)/[A-Za-z0-9._-]+/", Path(rel).read_text()), rel


def test_the_committed_ordinal_records_file_is_the_owner_generator_output():
    """The published population has a named producer and a byte-identity check, not a folklore recipe.

    Measured before this row was written: none of the four committed records files carries a single
    `qtype="score"` record (feishu is `choice`+`noul`, the three MASSIVE files are `choice`), so no corpus
    this checkout holds can produce a severity certificate and the published artefact is over the synthetic
    ordinal population the generator owns. The disclosure is inside the artefact's own envelope; this row is
    what stops the committed bytes from drifting away from the producer they claim.
    """
    from _records import build_ordinal

    committed = (REPO / report.SEVERITY_RECORDS).read_text()
    regenerated = "".join(json.dumps(r.to_dict(), sort_keys=True) + "\n"
                          for r in build_ordinal(**ORDINAL))
    assert committed == regenerated, "the committed ordinal population diverged from its generator"


def test_the_published_severity_artefact_carries_the_committed_freeze():
    digest = protocol_digest(load_protocol(REPO / "protocol.json"))
    _records_path, cert_path, _direction = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    doc = json.loads((REPO / cert_path).read_text())
    rubric = load_protocol(REPO / "protocol.json").rubric
    assert doc["meta"]["protocol_digest"] == digest, cert_path
    assert doc["alpha"] == rubric["alpha"] and doc["delta"] == rubric["delta"]
    assert doc["meta"]["seed"] == rubric["seed"]
    assert doc[SEVERITY_SHAPE_KEY] == SEVERITY_SHAPE_VERSION
    assert doc["feasible"] is True, doc["reason"]


def test_the_ordinal_arm_is_counted_in_both_lanes_and_the_total_is_derived(tmp_path, monkeypatch,
                                                                           in_repo, capsys):
    """The denominator is read from the shipped tables, and the ordinal rows are proved to be in it.

    Two statements: the corpus-less total equals the formula over the same owners the gate loops over (the
    `test_cli.py` derivation carries the same arithmetic, so neither can be quietly narrowed), and emptying
    the severity table moves the total by exactly the rows that table adds, document rows included -- so a
    row that stopped being counted cannot hide inside a number that happens to match. In-process, because a
    subprocess would not see the patched tables.
    """
    def absent_total():
        monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus"))
        assert main(["verify"]) == 0
        out = capsys.readouterr().out
        assert "corpus absent" in out, out
        checked, total = (int(group) for group in
                          re.search(r"re-derived (\d+) /(\d+) values", out).groups())
        assert checked == total, out
        return total

    rows = (len(cli.SEVERITY_COMPARE_FIELDS) + 1 + len(cli.SEVERITY_RUBRIC_FIELDS)
            # #119's contrast arm is driven off the same table: `rederive_g3_contrast` loops over
            # `severity_certificates()`, so emptying it removes the contrast's rows with these. Counted from
            # the arm's own lists rather than typed, and proved by the delta below -- an arm that silently
            # stopped being counted shows up as a total that does not drop by this much.
            + len(report.G3_CONTRAST_POPULATION_FIELDS) + len(report.G3_CONTRAST_SET_FIELDS)
            + len(report.G3_CONTRAST_SEVERITY_FIELDS) + len(cli.G3_CONTRAST_RUBRIC_FIELDS))
    assert len(cli.SEVERITY_COMPARE_FIELDS) == 15, cli.SEVERITY_COMPARE_FIELDS
    assert len(cli.SEVERITY_RUBRIC_FIELDS) == 3, cli.SEVERITY_RUBRIC_FIELDS
    assert {"ahat", "bound", "price_bound", "override_bound", "measured_violation", "direction",
            "meta", "envelope"} <= set(cli.SEVERITY_COMPARE_FIELDS), cli.SEVERITY_COMPARE_FIELDS
    with_severity = absent_total()
    # BOTH owners again, as in `_point_table_at_copies`: the arm's loop lives in `report` and reads the
    # table through `report.SEVERITY_CERTS`, so emptying only `cli`'s copy leaves the gate looping over the
    # real row and the delta measures the document arm alone. That is how this row read (128, 127) -- a
    # denominator claim that would have passed on one row of twenty.
    monkeypatch.setattr(cli, "SEVERITY_CERTS", {})
    monkeypatch.setattr(report, "SEVERITY_CERTS", {})
    # Two document rows go with the ordinal arm, not one. `docs/SEVERITY.md` renders the artefact, and
    # `docs/REPORT.md` reads it through `report.published_severity()` in its own certificate section, so a
    # hypothetical tree with no ordinal publication has no technical report either -- emptying the table and
    # dropping one document leaves the gate refusing on the other, which is exactly what this row measured
    # when Task 4 joined the table. The delta is therefore the arm plus one row per document dropped, and
    # the dropped rows are read from the filter rather than typed.
    # `docs/G3.md` joins the dropped set with #119: it renders the contrast whose population is the same
    # ordinal publication, so a tree with no ordinal publication has no contrast document either. Leaving it
    # in would keep its byte row passing while the arm behind it had nothing left to measure -- a published
    # number with no producer, which is the defect class this row exists to make loud.
    dropped = tuple(row for row in cli.PUBLISHED_DOCS
                    if str(row[0]) in {str(cli.SEVERITY_MD), str(cli.REPORT_MD),
                                       str(report.G3_CONTRAST_MD)})
    assert len(dropped) == 3, dropped
    monkeypatch.setattr(cli, "PUBLISHED_DOCS",
                        tuple(row for row in cli.PUBLISHED_DOCS if row not in dropped))
    without_severity = absent_total()
    assert with_severity - without_severity == rows + len(dropped), (with_severity, without_severity)


def _drift_labels(err):
    """The set of comparison labels `verify` refused, one per `DRIFT:` line, nothing else.

    Split on the gate's own separator instead of counting lines, because one refusal's value is an entire
    rendered document: its inner newlines arrive as separate lines that are not themselves refusals, and a
    reader that counted them would report drift that never happened. A `DRIFT:` line without the separator
    is a shape this helper does not know, so it raises rather than returning a silently short set.
    """
    labels = set()
    for line in err.splitlines():
        if not line.startswith("DRIFT:"):
            continue
        head, sep, _rest = line.partition(": recomputed")
        assert sep, line[:160]
        labels.add(head[len("DRIFT: "):])
    return labels


def test_an_edited_published_severity_artefact_is_drift_four_not_a_pass(tmp_path, monkeypatch, in_repo,
                                                                        capsys):
    """The new arm must be able to fail on the new numbers, or it is decoration beside them.

    The whole refusal set is pinned, not three `any()` probes: an `ahat` edit moves the field, the summary
    that quotes it, `docs/SEVERITY.md` that renders it (measured, in that order) and `docs/REPORT.md`, whose
    certificate section prints the ordinal `ahat` beside its own count, and `meta` is NOT in the set because
    the producer echoes only `alpha`/`delta`/`seed` there. A line appearing beside these is a claim this row
    would rather see than swallow -- which is how the technical report's fourth line was found rather than
    waived: a published figure now has two documents, and an edit to it reddens both.

    Both non-obvious members were planted. Editing the summary so it stops quoting `ahat` dropped
    `cert ordinal.summary` and reddened this row. Editing the document's own `ahat` bullet did NOT drop the
    document arm, because the figure reaches the prose a second time through the verbatim summary block --
    the tamper is caught twice over, and neither site alone is what this row relies on.
    """
    _point_table_at_copies(tmp_path, monkeypatch, mutate=lambda d: d.update({"ahat": 0}))
    code = main(["verify", "--protocol", "protocol.json"])
    assert code == 4, code
    assert _drift_labels(capsys.readouterr().err) == {
        "cert ordinal.ahat", "cert ordinal.summary", "%s byte-identical" % cli.SEVERITY_MD,
        "%s byte-identical" % cli.REPORT_MD}


def test_a_severity_artefact_produced_without_a_protocol_refuses_by_name(tmp_path, monkeypatch, in_repo,
                                                                         capsys):
    """R-200's rule, applied to the newest artefact: no stamp is drift the gate can attribute.

    Two lines, and no third. The artefact's `meta` is compared whole, so a missing digest is drift the gate
    can name; the document refuses alongside it because the committed bytes state the digest on their own
    line, which a stampless artefact cannot reproduce. The summary is NOT in the set -- it quotes no digest
    -- so the stamp reaches the reader exactly where the artefact states it, and nowhere else.

    Bounded honestly: suppressing `render_severity`'s digest line leaves this row green, because the document
    arm then fails for the other reason (the render no longer matches the committed file either way). What
    this row proves is attribution by name in both places plus the absence of a third line, not that the
    bullet is the only route to the second refusal.
    """
    _point_table_at_copies(tmp_path, monkeypatch,
                           mutate=lambda d: d["meta"].pop("protocol_digest"))
    code = main(["verify", "--protocol", "protocol.json"])
    assert code == 4, code
    assert _drift_labels(capsys.readouterr().err) == {
        "cert ordinal.meta", "%s byte-identical" % cli.SEVERITY_MD}


def test_a_wrong_shaped_published_severity_artefact_is_four_not_two(tmp_path, monkeypatch, in_repo,
                                                                     capsys):
    """A table-declared artefact whose shape this build cannot read is the checkout's failure at 4."""
    _point_table_at_copies(tmp_path, monkeypatch, mutate=lambda d: d.update({"shape": 99}))
    code = main(["verify"])
    assert code == 4, code
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "report.SEVERITY_CERTS" in err, err


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.pop("envelope"), "missing"),
    (lambda d: d.pop("meta"), "missing"),
    (lambda d: d.update({"n_cal": "600"}), "an integer"),
    (lambda d: d.update({"n_eval": None}), "an integer"),
    (lambda d: d.update({"backend": ["laya"]}), "a backend name"),
    (lambda d: d.update({"envelope": "exchangeability assumed"}), "must be a list"),
    (lambda d: d.update({"envelope": [1]}), "must be a list"),
])
def test_a_published_severity_artefact_with_a_wrongly_typed_slot_refuses_at_four_not_one(
        tmp_path, monkeypatch, in_repo, capsys, mutate, needle):
    """The four slots whose wrong type used to answer with an unmapped exception, walked at the entry point.

    Measured before the guard existed: `envelope` absent raised `KeyError`, `n_cal` as a JSON string raised
    `TypeError` out of `summary()`'s `%d`, `backend` as a list raised `TypeError: unhashable type` at the
    records lookup, and a top-level JSON array raised `AttributeError` on `.get` -- and `cli.main` maps none
    of those, so each was exit 1, the one number the 0/2/3/4 contract forbids. They are asserted through
    `main(["verify"])` rather than through `from_dict` because the claim being policed is the shipped
    program's exit code, and a reader that tests the loader directly can watch a `TypeError` and still call
    it a pass.
    """
    _point_table_at_copies(tmp_path, monkeypatch, mutate=mutate)
    code = main(["verify"])
    assert code == 4, code
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "report.SEVERITY_CERTS" in err, err
    assert needle in err, err


def test_a_published_severity_artefact_that_is_not_a_json_object_refuses_by_its_type(
        tmp_path, monkeypatch, in_repo, capsys):
    """A document that is an array is not a certificate, and `.get` on it is not a refusal.

    The shape guard reads `d[SEVERITY_SHAPE_KEY]` before anything else, so a list answers `AttributeError`
    and the gate dies at 1 -- the same door as the tampered artefacts above, arriving from a different shape.
    """
    table = {}
    for label, (records_path, cert_path, direction) in sorted(report.SEVERITY_CERTS.items()):
        doc = json.loads((REPO / cert_path).read_text())
        dst = tmp_path / Path(cert_path).name
        dst.write_text(json.dumps([doc], indent=2) + "\n")
        table[label] = (records_path, str(dst), direction)
    monkeypatch.setattr(cli, "SEVERITY_CERTS", table)
    monkeypatch.setattr(report, "SEVERITY_CERTS", table)
    assert main(["verify"]) == 4
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "array" in err, err


def test_a_missing_published_severity_artefact_is_four(tmp_path, monkeypatch, in_repo, capsys):
    _point_table_at_copies(tmp_path, monkeypatch)
    (_tmp_cert(tmp_path)).unlink()
    code = main(["verify"])
    assert code == 4, code
    err = capsys.readouterr().err
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in err and "report.SEVERITY_CERTS" in err, err


def _tmp_cert(tmp_path):
    _records_path, cert_path, _d = report.SEVERITY_CERTS[report.SEVERITY_LABEL]
    return tmp_path / Path(cert_path).name


def _point_table_at_copies(tmp_path, monkeypatch, mutate=None):
    """Re-point `SEVERITY_CERTS` at copies, so the gate reads a tampered artefact.

    BOTH owners are patched, exactly as `test_verify_protocol.py` does for `CERTS`: the gate iterates the
    name it imported and opens each path through `report.load_published`, so a helper that patched one of
    the two leaves part of the gate reading the real files -- which is how a refusal test passes while
    asserting nothing.
    """
    table = {}
    for label, (records_path, cert_path, direction) in sorted(report.SEVERITY_CERTS.items()):
        dst = tmp_path / Path(cert_path).name
        doc = json.loads((REPO / cert_path).read_text())
        if mutate is not None:
            mutate(doc)
        dst.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        table[label] = (records_path, str(dst), direction)
    monkeypatch.setattr(cli, "SEVERITY_CERTS", table)
    monkeypatch.setattr(report, "SEVERITY_CERTS", table)
    return table


# --- the published document ---------------------------------------------------------------------


def test_the_published_severity_document_is_byte_reproducible(tmp_path, in_repo):
    """`docs/SEVERITY.md` is emitted from the artefact and compared byte for byte by `verify`.

    Rendered again and diffed against the committed bytes: a document that cannot be re-produced from the
    artefact it describes is the stale-prose defect this repository has corrected for once already.
    """
    stored = (REPO / cli.SEVERITY_MD).read_text()
    label, _records, cert, _direction = report.published_severity()
    rendered = report.render_severity(label, cert)
    assert rendered == stored, "\n".join([
        next((line for line in rendered.splitlines() if line not in stored.splitlines()), ""),
        next((line for line in stored.splitlines() if line not in rendered.splitlines()), "")])
    assert str(cli.SEVERITY_MD) in {str(path) for path, _ in cli.PUBLISHED_DOCS}


def test_the_published_severity_document_carries_no_figure_the_artefact_does_not(tmp_path, in_repo):
    """Derived prose (B1 Task 2d's rule), widened: every figure a reader sees is one the artefact states.

    The first version of this guard matched `\\d+\\.\\d+` only, and only in the text before the verbatim
    summary, so it policed two decimals out of the dozen quantities on the page: `seed: 7`, `ahat: 3`, `a rubric
    of 5 levels`, `600/600`, `200/200` and the 1200-record population were all invisible, and the whole
    Envelope section was skipped -- a hand-typed integer in `render_severity` passed. Integers are the numbers a
    reader is most likely to act on, so the bullet section is now checked in full, the envelope is compared as
    the artefact's own strings, and the summary block is checked to be the artefact's `summary()` rather than
    mined for digits: that block carries prior-art years (`2023`, `216:2346-2355`) which are quotations of a
    citation, not figures the artefact states, and a guard that called them violations would be a guard a reader
    learns to ignore.
    """
    _label, _records, cert, _direction = report.published_severity()
    text = (REPO / cli.SEVERITY_MD).read_text()
    body, _, rest = text.partition("## Verbatim summary")
    summary_block, _, envelope_block = rest.partition("## Envelope")

    allowed = set()
    for value in (cert.alpha, cert.delta, cert.level, cert.bound, cert.price_bound,
                  cert.override_bound, cert.measured_violation):
        for fmt in ("%.6f", "%.3f", "%.2f"):
            allowed.add(fmt % value)
    for key in ("seed", "rubric_levels", "total_labelled", "n_cal_cases", "n_eval_cases",
                "violating_cases", "eval_violating_cases", "override_cases", "price_cases",
                "skipped_no_gold", "skipped_wrong_qtype"):
        if cert.meta.get(key) is not None:
            allowed.add(str(cert.meta[key]))
    for value in (cert.ahat, cert.n_cal, cert.n_eval, len(cert.envelope)):
        allowed.add(str(value))

    digest = str(cert.meta.get("protocol_digest"))
    assert body.count(digest) == 1, "the document states the artefact's stamp exactly once"
    # A hex digest is a run of digits to `\d+`, so the token is excised -- only after the line above has proved
    # it is the artefact's own value. Any other digit run stays in the scan, including a different hex string.
    found = set(re.findall(r"\d+\.\d+|\d+", body.replace(digest, "DIGEST")))
    assert found <= allowed, sorted(found - allowed)
    assert str(cert.ahat) in body, body
    assert cert.summary() in summary_block, summary_block
    envelope_lines = [line[2:] for line in envelope_block.splitlines() if line.startswith("- ")]
    assert envelope_lines == list(cert.envelope), (envelope_lines, cert.envelope)
    assert not re.search(r"/(Users|home)/[A-Za-z0-9._-]+/", text), text


def test_the_widened_derived_prose_guard_rejects_a_figure_the_artefact_does_not_state(tmp_path, in_repo):
    """The row above is only worth its width if a typed integer reddens it -- proven here, on a copy.

    Proven without editing production code: the committed document's own bytes are retyped to claim a reported
    level of 4 instead of the artefact's 3. That is precisely the defect the byte-comparison row cannot see,
    because a number hand-typed into `render_severity` reproduces itself exactly.
    """
    text = (REPO / cli.SEVERITY_MD).read_text()
    tampered = text.replace("- reported level `ahat`: 3,", "- reported level `ahat`: 4,")
    assert tampered != text, "the document no longer carries the bullet this proof edits"
    _label, _records, cert, _direction = report.published_severity()
    allowed = {fmt % v for v in (cert.alpha, cert.delta, cert.level, cert.bound, cert.price_bound,
                                 cert.override_bound, cert.measured_violation)
               for fmt in ("%.6f", "%.3f", "%.2f")}
    allowed |= {str(cert.meta.get(k)) for k in ("seed", "rubric_levels", "total_labelled", "n_cal_cases",
                                                "n_eval_cases")}
    allowed |= {str(cert.ahat), str(cert.n_cal), str(cert.n_eval)}
    body = tampered.partition("## Verbatim summary")[0]
    digest = str(cert.meta.get("protocol_digest"))
    assert body.count(digest) == 1
    found = set(re.findall(r"\d+\.\d+|\d+", body.replace(digest, "DIGEST")))
    assert not found <= allowed, "a typed ahat slipped through: the guard is still blind to integers"


# --- the rubric ownership ruling ----------------------------------------------------------------


def test_the_published_path_never_consults_the_library_defaults(monkeypatch, tmp_path, in_repo, capsys):
    """`severity.py`'s signature `0.05`s are library defaults; the command does not read them.

    `protocol.RUBRIC_SCOPE` states that these copies live outside the published rubric's fence, and this
    task keeps them -- so the honest form of "one owner" is a test that MOVES the library default and shows
    the published number does not move with it. If the command ever passed `alpha`/`delta`/`seed` through
    implicitly, patching the signature would move the artefact and this row goes red.
    """
    monkeypatch.setattr(severity.certify_severity, "__defaults__", (0.07, 0.07, "under", 0))
    records = _ordinal_records_file(tmp_path)
    out = tmp_path / "patched.json"
    assert rc(["severity", str(records), "--direction", "under", "--out", str(out)]) == 0
    patched = json.loads(out.read_text())
    assert patched["alpha"] == ALPHA and patched["delta"] == DELTA, patched
    assert patched["meta"]["seed"] == SEED, patched["meta"]["seed"]
    capsys.readouterr()
    assert rc(["severity", str(records), "--direction", "under",
               "--out", str(tmp_path / "plain.json")]) == 0
    assert json.loads((tmp_path / "plain.json").read_text()) == patched


def test_the_library_defaults_still_agree_with_the_owner_today():
    """The pre-deletion equality, stated as a pin rather than as a claim of deletion.

    `test_the_rubric_scope_sentence_names_copies_that_still_exist` reddens if the literals leave
    `severity.py`, because the freeze's own `rubric_scope` field names them as still existing. So this task
    documents the copies, polices them, and does not remove them -- the removal is not free.
    """
    import inspect

    assert severity.certify_severity.__defaults__[:2] == (ALPHA, DELTA)
    for func in (severity.certify_severity, severity.severity_band, severity.over_call_bound,
                 severity.tolerance_band):
        parameters = inspect.signature(func).parameters
        assert parameters["alpha"].default == 0.05, func.__name__
        assert parameters["delta"].default == 0.05, func.__name__
    assert "0.05" in Path(severity.__file__).read_text()


def test_the_severity_command_rubric_flags_default_to_the_owner_names_not_literals():
    """#62's rule on a new surface: each flag's default IS the imported owner, not a retyped number."""
    parser = cli.build_parser()
    sub = parser._subparsers._group_actions[0].choices["severity"]
    owners = dict(cli.SEVERITY_RUBRIC_FLAGS)
    flags = {a.dest: a.default for a in sub._actions if a.dest in owners}
    assert flags == owners, flags
    assert flags["alpha"] is ALPHA and flags["delta"] is DELTA and flags["seed"] is SEED



def _producer_denominators():
    """Which local each published figure divides by, and which meta key each local is stored under.

    Read out of `severity.py`'s AST rather than its text: the bounds are produced by `_bounds(counts, n_case,
    delta)` and inline by `clopper_pearson_upper(price_cases, n_case, delta)`, and `measured` is a division, so
    a substring search for `n_case` would match all three and answer nothing. The helper resolves one level of
    helper call, because the candidate bounds -- the figure the certificate is published for -- are computed
    inside `_bounds`.
    """
    tree = ast.parse(Path(severity.__file__).read_text())
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    producer = funcs["certify_severity"]

    def divides_by(func, call_node):
        """The local name `clopper_pearson_upper` divides by inside `func`, resolved against this call site."""
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "clopper_pearson_upper":
                arg = node.args[1]
                if isinstance(arg, ast.Name):
                    if arg.id not in {a.arg for a in func.args.args}:
                        return arg.id
                    index = [a.arg for a in func.args.args].index(arg.id)
                    if len(call_node.args) > index and isinstance(call_node.args[index], ast.Name):
                        return call_node.args[index].id
        return None

    bound = set()
    for node in ast.walk(producer):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None)
        if name == "clopper_pearson_upper" and len(node.args) > 1 and isinstance(node.args[1], ast.Name):
            bound.add(node.args[1].id)
        elif name in funcs and name != "certify_severity":
            got = divides_by(funcs[name], node)
            if got:
                bound.add(got)
    measured = None
    for node in producer.body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "measured" and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Div) and isinstance(node.value.right, ast.Name)):
            measured = node.value.right.id
    stored = {}
    for node in ast.walk(producer):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                        and key.value.startswith("n_") and key.value.endswith("_cases")
                        and isinstance(value, ast.Name)):
                    stored[key.value] = value.id
    assert bound and measured and stored, (sorted(bound), measured, stored)
    assert set(bound) <= set(stored.values()), (sorted(bound), stored)
    by_local = {v: k for k, v in stored.items()}
    assert measured in by_local, (measured, stored)
    return sorted({by_local[o] for o in bound}), by_local[measured], stored


def _check_denominator_note(note, bound_keys, measured_key):
    """Raise unless the note says which key the bounds divide by and which the empirical rate divides by.

    Clause-scoped (split on `.` and `;`), because the note is prose: a key merely present somewhere in the
    sentence would let a note that attributes the bounds to the evaluation split pass by mentioning both keys.
    """
    clauses = [c for c in re.split(r"[.;]", note) if c.strip()]
    for key in sorted(set(bound_keys) | {measured_key}):
        named = [c for c in clauses if key in c]
        if not named:
            raise AssertionError("no clause of the note names %s" % key)
        for clause in named:
            if key in bound_keys and "measured_violation" in clause:
                raise AssertionError("the note attributes %s to the measured rate" % key)
            if key == measured_key and "bound" in clause:
                raise AssertionError("the note attributes %s to a bound" % key)
    if not any(measured_key in c and "measured_violation" in c for c in clauses):
        raise AssertionError("the note never tells a reader which key the measured rate divides by")


def test_the_published_note_names_the_denominator_each_figure_actually_used(in_repo):
    """#113: the artefact's two case counts are equal, so only the producer can say which one spoke.

    `bound`, `price_bound` and `override_bound` divide by one split's case count and `measured_violation` by
    the other's, and the published file carries `meta.n_cal_cases == meta.n_eval_cases` -- asserted below,
    because that equality IS the premise: no comparison of the artefact's own bytes distinguishes the two
    readings, so a guard written on the numbers would pass whichever denominator the code used. This row reads
    `severity.py` instead, maps each operand to the meta key it is stored under, and requires `meta.unit_note`
    to name that key for those figures.

    Plant: swap the two keys in a copy of the note and the same predicate must reject it.
    """
    bound_keys, measured_key, _stored = _producer_denominators()
    _records, cert_rel, _direction = report.SEVERITY_CERTS["ordinal"]
    doc = json.loads((REPO / cert_rel).read_text())
    meta = doc["meta"]
    assert meta["n_cal_cases"] == meta["n_eval_cases"], (
        "the two counts now differ, so the artefact's own numbers distinguish the denominators and this row is"
        " no longer the only thing that does -- re-check #113 against the new shape")

    note = meta["unit_note"]
    _check_denominator_note(note, bound_keys, measured_key)

    swapped = note.replace(bound_keys[0], "@@B@@").replace(measured_key, bound_keys[0]).replace("@@B@@",
                                                                                                  measured_key)
    assert swapped != note, "swapping the keys changed nothing, so the plant tests nothing"
    with pytest.raises(AssertionError, match="attributes|never tells|names"):
        _check_denominator_note(swapped, bound_keys, measured_key)
