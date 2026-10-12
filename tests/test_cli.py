"""Task 9: the CLI, the reproduction gate, and the proof that the gate can fail."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = Path(
    __import__("os").environ.get(
        "AUTORATE_FEISHU_ROOT",
        # One owner for corpus discovery: the same resolver the CLI uses, so a test
        # default cannot drift from the shipped default and disagree about what ran.
        str(__import__("autorate.cli", fromlist=["_default_corpus"])._default_corpus()
            or "/no/corpus/on/this/machine"),
    )
)
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")

# A username-shaped segment, not the bare directory prefix: `<workspace>` prose and this file's own
# patterns say "/Users/" without naming a machine. Machine-path-shaped is the defect class; the guard
# deliberately does NOT claim to catch every absolute path (see the tmp-shape gap recorded in Plan D).
MACHINE_PATH_RX = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")


def run(*args, cwd=REPO, root=None):
    """root=None keeps the vendored corpus; a path here simulates a machine without it."""
    import os

    env = dict(os.environ)
    if root is not None:
        env["AUTORATE_FEISHU_ROOT"] = str(root)
    return subprocess.run([sys.executable, "-m", "autorate.cli", *args],
                          capture_output=True, text=True, cwd=str(cwd), env=env)


def counts(text):
    m = re.search(r"re-derived (\d+) /(\d+) values", text)
    assert m, text
    return int(m.group(1)), int(m.group(2))


def stage_published(work):
    """Copy into `work` every artefact the gate's own tables say is published.

    A scratch checkout built from a hand-kept list of file names goes red on a missing artefact
    before it ever reaches the refusal the test is about: when G1's three MASSIVE certificates
    joined the gate, two tests that had been naming four files began to fail on a
    `FileNotFoundError` for a fifth. The tables in `report.py` are the one owner of what is
    published, so the fixture reads them instead of remembering them.
    """
    from autorate.cli import PROTOCOL_JSON
    from autorate.report import CERTS, MASSIVE_CERTIFICATES, RECORDS

    names = ({RECORDS, str(PROTOCOL_JSON)} | set(CERTS.values())
             | {p for pair in MASSIVE_CERTIFICATES.values() for p in pair})
    for rel in sorted(names):
        shutil.copy(REPO / rel, work / rel)


def stage_committed_tree(work, directories=("data", "docs")):
    """Copy the committed published trees AND the freeze into a scratch checkout.

    `verify` reads `protocol.json` as a table-declared artefact (`cli.PROTOCOL_JSON`), so a scratch tree
    built from `data/` and `docs/` has no freeze and the gate exits 4 naming the absent document before it
    can reach the drift the test is about. The path comes from its owner rather than a retyped literal, for
    the same reason `stage_published` reads the tables: a rename has to move the fixture and the gate
    together, or the fixture starts testing its own copy of the truth.
    """
    from autorate.cli import PROTOCOL_JSON

    for directory in directories:
        shutil.copytree(REPO / directory, work / directory)
    shutil.copy(REPO / str(PROTOCOL_JSON), work / str(PROTOCOL_JSON))
    return work


def test_verify_passes_on_the_committed_tree():
    p = run("verify")
    assert p.returncode == 0, p.stdout + p.stderr
    checked, total = counts(p.stdout)
    assert checked == total, p.stdout
    assert ("corpus present" in p.stdout) != ("corpus absent" in p.stdout), p.stdout
    absent = run("verify", root=Path("/nonexistent-corpus-dir"))
    a_checked, a_total = counts(absent.stdout)
    assert absent.returncode == 0, absent.stdout + absent.stderr
    # The strict comparison only holds where a corpus EXISTS to be found: a CI runner
    # sees 29 in both lanes, and asserting more there would be asserting the machine.
    if UPSTREAM.exists():
        assert total > a_total, (total, a_total)
    else:
        assert total == a_total, (total, a_total)


def test_verify_runs_and_agrees_where_the_corpus_does_not_exist(tmp_path):
    """The CI lane: a machine that never saw the vendored tree must reach the same verdict.

    Without this, `verify` would be green only here, and the numbers it quotes in CI
    would be transcriptions of a snapshot nothing in CI can contradict -- silently.
    """
    p = run("verify", root=tmp_path / "no_corpus")
    assert p.returncode == 0, p.stdout + p.stderr
    checked, total = counts(p.stdout)
    assert checked == total, p.stdout
    assert "corpus absent" in p.stdout, p.stdout
    assert "transcribed" in p.stdout, p.stdout
    # Every row the corpus-less lane can honestly print: the certificate fields re-derived
    # per backend, one summary each, and the report bytes. Derived from the shipped field
    # list rather than typed, so a row that quietly disappears changes the expectation too.
    from autorate.cli import CERT_COMPARE_FIELDS, CORPUS_DIGESTS, RUBRIC_FIELDS

    # every certificate in the two published tables x (each compared field + its summary), then one
    # row per published document that must reproduce byte for byte -- read from `PUBLISHED_DOCS`, the
    # same table the gate loops over, so a document the gate stops re-rendering has to shrink this
    # expectation before it can pass (R-168: a hand-kept list of published files is a second owner of
    # the publication list). Then every MASSIVE figure that `data/massive_provenance.json` owns.
    # The pin rows are counted from the same producer's output, and the ids it covers are pinned
    # separately so a narrowing of the arm (dropping `basis`, say) cannot pass as a formula change.
    # The key list is read from the gate itself (R-83), so a column the arm stops comparing has to
    # widen this expectation before it can shrink the gate.
    from autorate.cli import PIN_DERIVED_KEYS, PUBLISHED_DOCS
    from autorate.inventory import corpus_options, massive_pin
    from autorate.report import CERTS, MASSIVE_CERTIFICATES

    pin_options = [o for o in corpus_options(None, pin=massive_pin())
                   if o["id"].startswith("massive")]
    assert sorted(o["id"] for o in pin_options) == ["massive_intent_all_languages",
                                                    "massive_intent_per_language"], pin_options
    assert "bound_width_at_0.05" in PIN_DERIVED_KEYS, "the bound column has no producer again"
    assert "feasible_at_0.10" in PIN_DERIVED_KEYS and "feasible_at_0.25" in PIN_DERIVED_KEYS
    pin_rows = sum(1 for o in pin_options for k in PIN_DERIVED_KEYS if k in o)
    assert pin_rows == 13, pin_rows      # 7 for the pooled row, 6 for per-language (no `n_shards`)
    # Membership, not only the count. The denominator below is read from the same table the gate
    # loops over, so on its own it cannot notice a document deleted from the table: `expected` and
    # `total` shrink together and the row stays green. This literal is the independent statement of
    # which published documents `verify` owns -- it is the assertion that was red for `docs/AUDIT.md`
    # before MAJ-3, and it is what a future narrowing of `PUBLISHED_DOCS` has to edit first.
    assert {str(path) for path, _ in PUBLISHED_DOCS} == {"docs/RESULTS.md", "data/inventory.md",
                                                         "docs/AUDIT.md"}, PUBLISHED_DOCS
    # A published certificate is counted here because its table says it exists, not because a
    # literal remembered it. G1's three MASSIVE artefacts were committed and CI-witnessed while
    # `verify` re-derived neither them nor this row's knowledge of them: the row was red at
    # `total` 47 against `expected` 95 until the gate grew the arm, which is the defect class
    # (a published number with no producer) this formula exists to make loud.
    # The freeze adds two more terms, both read from their owners: one rubric comparison per
    # `RUBRIC_FIELDS` entry for each feishu certificate (Task 2's arm closes the hole that `alpha` is not
    # in `CERT_COMPARE_FIELDS`), and one per digest the protocol names in advance. Measured at the tip
    # before this row was widened, the absent lane printed 96; after the arm, 108 -- the movement is
    # added checks, not moved numbers, and the two are reported apart in `docs/ERRATA.md`.
    expected = ((len(CERTS) + len(MASSIVE_CERTIFICATES)) * (len(CERT_COMPARE_FIELDS) + 1)
                + len(CERTS) * len(RUBRIC_FIELDS) + len(CORPUS_DIGESTS)
                + len(PUBLISHED_DOCS) + pin_rows)
    assert total == expected, (total, expected, p.stdout)


def test_verify_reds_when_the_pin_and_the_published_rows_disagree(monkeypatch, tmp_path,
                                                         capsys):
    """The new pin arm must be able to fail, or it is a second copy of the snapshot.

    A self-consistent pin that simply describes a smaller corpus -- 50 shards instead of 51, every
    declared total matching its entries -- passes every loader check. If `verify` re-derives the
    MASSIVE rows from the pin rather than transcribing the snapshot, it must still catch that the
    published table says 151,674 rows and the committed evidence now says 148,700.

    Patched at `MASSIVE_PIN_PATH` rather than by running in a copied directory: the loader resolves
    the pin from the package's own `data/`, so a working directory does not select a different pin.
    That is worth knowing on its own -- the path is where the artefact's inputs live, not a
    parameter -- so the first version of this test was run in a tampered checkout, stayed green, and
    proved nothing.
    """
    import json

    from autorate import inventory as inv_module
    from autorate.cli import EXIT_DRIFT, main

    pin = json.loads((REPO / "data" / "massive_provenance.json").read_text())
    del pin["files"][-1]
    pin["n_files"] = len(pin["files"])
    pin["rows_total"] = sum(f["rows"] for f in pin["files"])
    pin["bytes_total"] = sum(f["bytes"] for f in pin["files"])
    assert pin["rows_total"] == pin["distinct_ids"] * pin["n_files"], pin["rows_total"]
    tampered = tmp_path / "massive_provenance.json"
    tampered.write_text(json.dumps(pin))
    monkeypatch.setattr(inv_module, "MASSIVE_PIN_PATH", tampered)

    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus"))
    rc = main(["verify"])
    err = capsys.readouterr().err
    assert rc == EXIT_DRIFT, (rc, err)
    assert "pin option massive_intent_all_languages.n_rows" in err, err
    assert "148700" in err and "151674" in err, err


def test_report_is_byte_identical_with_and_without_the_corpus(tmp_path):
    """The report must not quote which machine produced it, or CI can never reproduce it."""
    committed = (REPO / "docs" / "RESULTS.md").read_bytes()
    here = tmp_path / "here.md"
    there = tmp_path / "there.md"
    assert run("report", "--out", str(here)).returncode == 0
    v = run("report", "--out", str(there), root=tmp_path / "no_corpus")
    assert v.returncode == 0, v.stdout + v.stderr
    assert here.read_bytes() == there.read_bytes(), "report depends on this machine"
    assert there.read_bytes() == committed, "committed docs/RESULTS.md is stale"


def test_report_is_byte_stable_and_matches_the_committed_file(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    assert run("report", "--out", str(a)).returncode == 0
    assert run("report", "--out", str(b)).returncode == 0
    assert a.read_bytes() == b.read_bytes(), "report is not deterministic"
    assert a.read_bytes() == (REPO / "docs" / "RESULTS.md").read_bytes(), \
        "committed docs/RESULTS.md is not what `report` emits"


@skip
def test_verify_catches_an_inventory_snapshot_that_went_stale(tmp_path):
    """The snapshot is what a corpus-less run trusts, so the corpus must police it."""
    stage_committed_tree(tmp_path)
    path = tmp_path / "data" / "inventory.md.json"
    doc = json.loads(path.read_text())
    doc["unique_ids"] = 63
    path.write_text(json.dumps(doc, sort_keys=True))
    assert doc["unique_ids"] == 63, "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "snapshot unique_ids" in p.stderr, p.stderr


def test_verify_catches_a_tampered_certificate(tmp_path):
    """The reproduction gate must be able to fail: edit one published number."""
    stage_committed_tree(tmp_path)
    (tmp_path / "tests").mkdir()
    cert = tmp_path / "data" / "cert_jev.json"
    doc = json.loads(cert.read_text())
    original = doc["meta"]["automated_cases"]
    doc["meta"]["automated_cases"] = original - 1
    cert.write_text(json.dumps(doc, sort_keys=True))
    assert doc["meta"]["automated_cases"] != original, "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "cert jev.meta" in p.stderr, p.stderr
    assert "DRIFT" in p.stderr


def test_verify_also_catches_a_hand_edited_results_file(tmp_path):
    stage_committed_tree(tmp_path)
    results = tmp_path / "docs" / "RESULTS.md"
    results.write_text(results.read_text().replace("0.3395", "0.2000"))
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "RESULTS.md byte-identical" in p.stderr, p.stderr


@skip
def test_export_then_certify_reports_the_quarantine_and_its_exit_code(tmp_path):
    recs = tmp_path / "records.jsonl"
    e = run("export-feishu", "--out", str(recs))
    assert e.returncode == 0, e.stderr
    assert "quarantined: jev/lifecycle-01 repeat=1 probs_sum=0.99" in e.stdout
    assert "1919 records" in e.stdout
    by_backend = {}
    for line in recs.read_text().splitlines():
        d = json.loads(line)
        by_backend[d["backend"]] = by_backend.get(d["backend"], 0) + 1
    assert by_backend == {"laya": 960, "jev": 959}

    for backend in ("laya", "jev"):
        out = tmp_path / ("c_%s.json" % backend)
        c = run("certify", str(recs), "--backend", backend, "--out", str(out))
        # Both refuse, and the two refusals say different things: laya automates nothing at
        # 95% coverage, and jev automates all 32 of its evaluation cases with zero errors
        # yet still cannot meet a 0.05 budget at n=32 cases. Under the old record-level
        # split jev "certified" -- on 44 cases that were also in its calibration half.
        assert c.returncode == 3, (backend, c.stdout, c.stderr)
        assert "NOT_CERTIFIABLE" in c.stdout, c.stdout
        doc = json.loads(out.read_text())
        assert doc["feasible"] is False and doc["envelope"], doc
        assert doc["meta"]["n_eval_cases"] < doc["n_eval"], doc["meta"]
        assert "wrote %s" % out in c.stdout, c.stdout
        assert "diagnostic sweep" in c.stdout, c.stdout
    lac = run("certify", str(recs), "--backend", "jev", "--method", "lac",
              "--out", str(tmp_path / "lac.json"))
    assert json.loads((tmp_path / "lac.json").read_text())["method"] == "lac", lac.stdout


def test_compare_prints_both_verdicts_and_never_drops_the_envelope():
    p = run("compare", "data/cert_laya.json", "data/cert_jev.json")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.count("NOT_CERTIFIABLE") == 2, p.stdout
    assert "case-level upper bound" in p.stdout, p.stdout
    # two refusals x the two assumptions a refusal is required to carry
    assert p.stdout.count("envelope:") >= 4, p.stdout
    # What it claims about pairing is measured, with its denominators named.
    assert "comparable: yes" in p.stdout, p.stdout
    assert "records over" in p.stdout and "request ids in common" in p.stdout, p.stdout


def test_compare_refuses_to_call_different_rubrics_comparable(tmp_path):
    """C-1's falsifier. The old line asserted identical rubrics without reading either.

    A certificate certified at alpha=0.20, beta=0.30, seed=99 is not the same
    experiment as one at 0.05/0.05/7, and a reader comparing the two needs the tool to
    say so rather than print a claim.
    """
    off = tmp_path / "cert_off.json"
    c = run("certify", "data/records_feishu.jsonl", "--backend", "jev",
            "--alpha", "0.20", "--beta", "0.30", "--seed", "99", "--out", str(off))
    assert c.returncode in (0, 3), c.stdout + c.stderr
    p = run("compare", "data/cert_jev.json", str(off))
    assert "comparable: NO" in p.stdout, p.stdout
    assert p.returncode == 2, (p.returncode, p.stdout)  # not comparable is an input error
    for f in ("alpha", "beta", "seed"):
        assert f in p.stdout.splitlines()[0] or f in p.stdout, f
    # The same file twice shares a subject, so it is not a pair: the tool must say the
    # halves are not paired and exit 2, not quietly report a comparison of one thing.
    q = run("compare", "data/cert_jev.json", "data/cert_jev.json")
    assert "halves not paired" in q.stdout, q.stdout
    assert q.returncode == 2, (q.returncode, q.stdout)


@skip
def test_gate_lines_name_the_action_and_are_self_sufficient(tmp_path):
    recs = tmp_path / "records.jsonl"
    assert run("export-feishu", "--out", str(recs)).returncode == 0
    cert = tmp_path / "cert.json"
    run("certify", str(recs), "--backend", "jev", "--out", str(cert))
    g = run("gate", str(recs), "--cert", str(cert), "--backend", "jev", "--limit", "3")
    assert g.returncode in (0, 3)
    lines = [l for l in g.stdout.splitlines() if "action=" in l]
    assert len(lines) == 3, g.stdout
    assert all("why=" in l and "qhat=" in l for l in lines), lines
    # The certificate is jev's; a laya record must not be automated on it (subject_mismatch).
    assert "envelope carried by every decision below" in g.stdout, g.stdout


def test_the_cli_has_no_network_or_hosted_dependency():
    """Constraint 1 is invisible to every other test here: nothing in src/ may reach out."""
    import ast

    banned = {"urllib.request", "httpx", "requests", "socket", "aiohttp"}
    offenders = []
    for path in sorted((REPO / "src" / "autorate").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = set()
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module}
            hit = names & banned
            if hit:
                offenders.append((path.name, sorted(hit)))
    assert not offenders, offenders


def test_installed_console_script_exit_codes(tmp_path):
    """R-6: the guard runs the script as a subprocess and asserts its exit code, not an
    in-process return value -- an argparse main() reads pytest's own argv otherwise."""
    script = Path(sys.executable).parent / "autorate"
    assert script.exists(), "the autorate console script is not installed"
    ok = subprocess.run([str(script), "--help"], capture_output=True, text=True, cwd=tmp_path)
    assert ok.returncode == 0
    noargs = subprocess.run([str(script)], capture_output=True, text=True, cwd=tmp_path)
    assert noargs.returncode == 2, (noargs.returncode, noargs.stderr)


def test_verify_sees_an_edited_method_or_meta(tmp_path):
    """The re-review's Important item: verify's compared list omitted `method` and `meta`.

    A certificate edited to method=lac verified 56/56 green, and `meta.eval_ids` -- which
    `compare` prints its pairing claim from -- was free to invent. Each field is planted
    with a different defect and each must turn the gate red.
    """
    for field, mutate in (("method", lambda d: d.update(method="lac")),
                          ("meta", lambda d: d["meta"].update(eval_ids=["invented-0"]))):
        work = tmp_path / field
        stage_committed_tree(work)
        cert = work / "data" / "cert_jev.json"
        doc = json.loads(cert.read_text())
        mutate(doc)
        cert.write_text(json.dumps(doc, sort_keys=True))
        assert doc["method"] == "lac" if field == "method" else \
            doc["meta"]["eval_ids"] == ["invented-0"], "tampering did not land"
        r = run("verify", cwd=work)
        assert r.returncode == 4, (field, r.returncode, r.stdout, r.stderr)
        assert "cert jev.%s" % field in r.stderr, (field, r.stderr)


def test_no_corpus_is_a_usage_error_not_rc_one(tmp_path):
    """I-1 again: `_require_root` raised SystemExit(text), which Python exits with 1."""
    for cmd in (["snapshot"], ["export-feishu", "--out", str(tmp_path / "r.jsonl")]):
        r = run(*cmd, root=Path("/nonexistent-corpus-dir"))
        assert r.returncode == 2, (cmd, r.returncode, r.stdout, r.stderr)
        assert "Traceback" not in r.stderr, r.stderr
        assert "no corpus found" in r.stderr, (cmd, r.stderr)


# ---------------------------------------------------------------------------
# R-131 / obligation #63: which root won has to be visible in what the tool prints.
# ---------------------------------------------------------------------------

_UNSET = object()          # sentinel: this arm runs with the variable NOT in the environment


def _corpus_stub(tmp: Path) -> Path:
    """The smallest root `snapshot` accepts, built where the test runs -- no absolute literal.

    A refusal cannot show which path was read unless a success is available to compare with, and
    the success needs a real corpus shape: manifest, cases, one archived response per backend, and
    an audit that exits 0. Same shape `tests/test_inventory.py::_tiny_corpus` uses, so both CI
    lanes can build it.
    """
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    (tmp / "data" / "manifest.json").write_text(json.dumps(
        {"asks": {"a1": "question?"}, "labels": {"a": 1}, "families": ["f"],
         "provenance": "test-fixture"}))
    (tmp / "data" / "cases.jsonl").write_text(json.dumps({"id": "c0", "expected": "a"}) + "\n")
    row = json.dumps({"id": "c0", "mode": "choice", "repeat": 0, "status": "ok", "expected": "a",
                      "response": {"model": "m", "answers": {"category": {
                          "type": "choice", "choice": "a",
                          "probabilities": {"a": 0.5, "b": 0.5}}}}})
    for backend in ("laya", "jev"):
        d = tmp / "results" / "v1" / backend
        d.mkdir(parents=True, exist_ok=True)
        (d / "raw.jsonl").write_text(row + "\n")
    (tmp / "audit.py").write_text("import sys\nsys.exit(0)\n")
    return tmp


def _cli_root(args, env_root=_UNSET, cwd=REPO):
    """Run the shipped CLI with the corpus variable set to `env_root`, or removed when _UNSET.

    `run()` above can only ever SET the variable, so it cannot express the flag-alone and
    neither-source arms -- and this suite is routinely run with `AUTORATE_FEISHU_ROOT` exported for
    the whole process, which would otherwise leak into both.
    """
    import os

    env = dict(os.environ)
    if env_root is _UNSET:
        env.pop("AUTORATE_FEISHU_ROOT", None)
    else:
        env["AUTORATE_FEISHU_ROOT"] = str(env_root)
    return subprocess.run([sys.executable, "-m", "autorate.cli", *args],
                          capture_output=True, text=True, cwd=str(cwd), env=env)


def test_the_root_that_wins_is_the_root_the_tool_names(tmp_path):
    """R-131 / obligation #63: a discarded `--root` must be a LOUD discard.

    `_root()` resolves environment -> flag -> sibling, so `AUTORATE_FEISHU_ROOT` outranks the
    argument the operator typed. That order is this repository's own harness contract (the
    corpus-absent lane is *defined* by exporting the variable to a nonexistent path for a whole
    process, and `tests/test_inventory.py:1367` pins env-over-flag), so the defect R-131 records
    is not the precedence: it is that the resolution was silent AND the refusal then contradicted
    itself -- "pass --root" to a user who just did, and "looked for a sibling" about the third
    path, neither of which is the source that answered. A refusal that is correctly classified and
    wrongly explained still misattributes the tool's own failure.

    So the contract asserted here is the shape, in both directions, at the real entry point and on
    the user-visible surface only (exit code plus printed text):

    1. both present -> exactly one is used, and every message names THAT one, including the path
       it tried and the source it came from, and says the flag was overridden;
    2. env alone -> uses it;
    3. flag alone (variable absent from the environment) -> uses it;
    4. neither -> the sibling default, unchanged.

    Nothing here may pass by naming both paths ambiguously: 1a is the arm that reddens if the
    precedence is flipped to flag-wins without the harness being updated, and 1b reddens today.
    """
    cli = __import__("autorate.cli", fromlist=["_default_corpus"])
    stub = _corpus_stub(tmp_path / "stubRoot")
    bogus = tmp_path / "bogusRoot"           # never created: no manifest, no archive, nothing
    out = str(tmp_path / "inv" / "inventory.md")

    # 1a. The ambient variable wins, and the run says which root it read: the successful snapshot
    #     names the env root and never mentions the --root it threw away.
    won = _cli_root(["snapshot", "--root", str(bogus), "--out", out], env_root=stub)
    assert won.returncode == 0, won.stdout + won.stderr
    assert "stubRoot" in won.stdout, won.stdout
    assert "bogusRoot" not in won.stdout, won.stdout

    # 1b. The mirror arm, and the defect's own surface: same precedence, but this time the winner
    #     is not a corpus, so the refusal is what the operator reads.
    refused = _cli_root(["snapshot", "--root", str(stub), "--out", out], env_root=bogus)
    err = refused.stderr
    assert refused.returncode == 2, (refused.returncode, refused.stdout, err)
    assert "Traceback" not in err, err
    assert "no corpus found" in err, err                      # the committed prefix contract
    assert str(bogus) in err, err                             # the root it ACTUALLY tried
    assert "AUTORATE_FEISHU_ROOT" in err, err                  # and the source that answered
    assert "overridden" in err, err                           # what happened to the flag
    assert str(stub) in err, err                              # the overridden path, named too
    assert "pass --root" not in err, err                      # never instructs the done thing
    assert "sibling" not in err, err                          # never claims the third path

    # 2. env alone: the corpus-absent lane's shape, inverted to a corpus that is actually there.
    by_env = _cli_root(["snapshot", "--out", out], env_root=stub)
    assert by_env.returncode == 0, by_env.stdout + by_env.stderr
    assert "stubRoot" in by_env.stdout, by_env.stdout

    # 3. flag alone, with the variable removed from the environment entirely -- the only arm on
    #    this machine that can tell a working `--root` from an ambient override.
    by_flag = _cli_root(["snapshot", "--root", str(stub), "--out", out], env_root=_UNSET)
    assert by_flag.returncode == 0, by_flag.stdout + by_flag.stderr
    assert "stubRoot" in by_flag.stdout, by_flag.stdout

    # 4. neither: the sibling default, and it must still be a real last resort rather than a lie.
    #    The branch reads the shipped resolver only to pick WHICH observable can be seen here (a
    #    machine with the checkout beside it proves the default works; a machine without it proves
    #    the refusal says so); every assertion below is on rc and on printed text.
    default = cli._default_corpus()
    sibling_present = default is not None and (default / "data" / "manifest.json").exists()
    if sibling_present:
        fell = _cli_root(["export-feishu", "--out", str(tmp_path / "rec.jsonl")], env_root=_UNSET)
        assert fell.returncode == 0, fell.stdout + fell.stderr
        assert "exported " in fell.stdout, fell.stdout
    else:
        fell = _cli_root(["snapshot", "--out", out], env_root=_UNSET)
        assert fell.returncode == 2, (fell.returncode, fell.stdout, fell.stderr)
        assert "no corpus found" in fell.stderr, fell.stderr
        assert "sibling" in fell.stderr, fell.stderr


def test_verify_without_a_corpus_or_a_snapshot_is_a_usage_error(tmp_path):
    work = tmp_path / "no_data"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    stage_published(work)
    r = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "nothing to verify against" in r.stderr, r.stderr
    # The absent snapshot is the one statement about this path that stays a usage error, and no argument
    # can name it either. It is also the pin that fires if the content guard is ever routed over the
    # missing-file branch: `load_published` catches `ValueError`, `UsageError` is a `ValueError`
    # subclass, and a snapshot the tree does not have would be reported as a snapshot the tree corrupts.
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in r.stderr, r.stderr


def test_a_mixed_subject_certificate_gates_nothing():
    """The R-29 guard was inert for backend=None: it skipped the comparison it needed."""
    import random

    from autorate.certificate import Certificate
    from autorate.certify_choice import certify_choice
    from autorate.gate import Gate
    from autorate.records import Record

    rng = random.Random(11)
    recs = []
    for i in range(400):
        p = [0.7, 0.1, 0.1, 0.1]
        rng.shuffle(p)
        top = p.index(max(p))
        recs.append(Record(id=str(i), qtype="choice", backend="jev", repeat=0,
                           options=("a", "b", "c", "d"), probs=tuple(p),
                           gold=("a", "b", "c", "d")[top],
                           predicted=("a", "b", "c", "d")[top], slices={}, scores={},
                           seed=11, u=0.0, meta={}))
    live = certify_choice(recs, alpha=0.05, beta=0.20, seed=3)
    assert live.feasible is True, live.summary()
    assert Gate(live).decide(recs[0])["action"] == "auto"
    stripped = Certificate.from_dict({**live.to_dict(), "backend": None})
    d = Gate(stripped).decide(recs[0])
    assert d["action"] == "abstain" and d["reason"] == "subject_mismatch", d


def test_a_missing_input_is_a_usage_error_not_a_traceback(tmp_path):
    """I-1: rc 1 was reachable outside the documented 0/2/3/4 contract."""
    p = run("certify", str(tmp_path / "nope.jsonl"), "--out", str(tmp_path / "c.json"))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert p.stderr.strip(), "a usage error that prints nothing is not diagnosable"


def test_a_published_artefact_that_does_not_parse_is_the_same_drift_not_a_usage_error(tmp_path):
    """A table-declared artefact this checkout CAN open and cannot READ: content, not access.

    Measured before this row existed, on a scratch checkout with one published file corrupted:
    `data/cert_laya.json` with invalid JSON exited 2 with `JSONDecodeError: Expecting property name
    enclosed in double quotes`, and so did a corrupt `data/records_massive_sw.jsonl`. That is the same
    false attribution the two rows above retired, in its fourth and least visible form. No argument
    selected the path -- the table did -- and no argument can repair it either: the bytes this repository
    committed are the defect. rc 2's documented meaning is "an input this command was handed is wrong",
    so the code reports the tree's failure as the operator's, on the one artefact class a reader is most
    likely to be handed by a broken release.

    The refusal therefore names the table, quotes the parser's own words, and goes to `4`, whose clause
    is "the committed state cannot reproduce what it publishes". It must not borrow the access rows'
    wording: bytes that were read and rejected were opened, so "cannot be opened" would be false, and nothing
    vanished, so "is not in this checkout" would be false too.
    """
    cases = [
        ("data/cert_laya.json", "report.CERTS", "{not a certificate", False),
        ("data/cert_massive_de_laya.json", "report.MASSIVE_CERTIFICATES", "{not a certificate", False),
        ("data/records_massive_sw.jsonl", "report.MASSIVE_CERTIFICATES", "not a record line\n", False),
        # Not text at all: the document loop compares bytes verbatim rather than parsing them, so the
        # only way this site can fail to read is a decode error -- which is a ValueError, and belongs
        # to the same class as a certificate whose JSON will not parse.
        ("docs/RESULTS.md", "cli.PUBLISHED_DOCS", b"\xff\xfe\x80 not utf-8 \x81", True),
    ]
    for rel, table, corrupt, needs_snapshot in cases:
        work = tmp_path / rel.replace("/", "-").replace(".", "-")
        (work / "data").mkdir(parents=True)
        shutil.copytree(REPO / "docs", work / "docs")
        stage_published(work)
        if needs_snapshot:
            shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
        (work / rel).write_bytes(corrupt if isinstance(corrupt, bytes) else corrupt.encode())
        p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
        assert p.returncode == 4, (rel, p.returncode, p.stdout, p.stderr)
        assert "Traceback" not in p.stderr, (rel, p.stderr)
        assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, (rel, p.stderr)
        assert rel in p.stderr, (rel, p.stderr)
        assert table in p.stderr, (rel, p.stderr)
        assert "is not the artefact that table publishes" in p.stderr, (rel, p.stderr)
        assert "does not parse" not in p.stderr, (rel, p.stderr)
        assert "cannot be opened" not in p.stderr, (rel, p.stderr)
        assert "is not in this checkout" not in p.stderr, (rel, p.stderr)
        assert "re-derived" not in p.stdout, (rel, p.stdout)


def test_a_corrupt_committed_inventory_snapshot_is_the_same_drift_not_a_usage_error(tmp_path):
    """The fifth table-declared read, which round 3 enumerated past.

    Round 3 listed the sites by table and wired four; the review of that round found the fifth,
    `_inventory`'s read of the committed snapshot. Measured on the round-3 tip, replacing
    `data/inventory.md.json` with `{not json` left `verify` exiting 2 with a bare `JSONDecodeError:
    Expecting property name enclosed in double quotes` naming no file -- the failure that round's own
    RED retired, still live on the path no argument can name.

    This is the case the README's residual cannot host. No CLI flag takes a snapshot path: `verify` and
    `report` accept none, and `audit --records` defaults to the records file, so the rationale that
    keeps `data/records_feishu.jsonl` at `2` -- a default you could have named -- has nothing to
    transfer to. And "no corpus and no committed inventory: nothing to verify against" is the statement
    of a MISSING snapshot; bytes that were read and rejected are the sentence's own contrast clause, "a
    published artefact that cannot be read", which belongs at `4`.
    """
    work = tmp_path / "corrupt-snapshot"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    stage_published(work)
    (work / "data" / "inventory.md.json").write_text("{not json")
    p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, p.stderr
    assert "data/inventory.md.json" in p.stderr, p.stderr
    assert "report.INVENTORY_JSON" in p.stderr, p.stderr
    assert "is not the artefact that table publishes" in p.stderr, p.stderr
    assert "does not parse" not in p.stderr, p.stderr
    assert "cannot be opened" not in p.stderr, p.stderr
    # The usage sentence must not survive onto this path: it is the absent snapshot's, and a run that
    # read the file and rejected it does not know that the file is missing.
    assert "nothing to verify against" not in p.stderr, p.stderr
    assert "re-derived" not in p.stdout, p.stdout


def test_the_corpus_present_snapshot_leg_refuses_corrupt_bytes_the_same_way(tmp_path, monkeypatch):
    """The same committed file, read by the other leg: `expect_snapshot_is_current`, corpus only.

    Called directly rather than as a corpus-gated end-to-end row because the condition is the bytes at
    one path, and a row that skipped whenever the vendored corpus is absent would leave this site
    policed by prose. `verify`'s ordering means the end-to-end lane reaches the certificate tables
    first anyway, so the leg needs its own call to be reachable at all.
    """
    from autorate.cli import expect_snapshot_is_current
    from autorate.report import PublishedArtefactUnavailable

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "inventory.md.json").write_text("{not json")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PublishedArtefactUnavailable) as caught:
        expect_snapshot_is_current(lambda label, actual, wanted: None, {"digests": []})
    message = str(caught.value)
    assert "data/inventory.md.json" in message, message
    assert "report.INVENTORY_JSON" in message, message
    assert "is not the artefact that table publishes" in message, message
    assert "cannot be opened" not in message, message
    assert "is not in this checkout" not in message, message


def test_a_committed_snapshot_that_parses_but_is_not_the_shape_this_build_reads_is_drift(tmp_path):
    """Round 4's docstring promised this row's behaviour and round 4's wiring did not deliver it.

    `load_published`'s own text listed "a snapshot whose shape this build does not accept" as one of the
    four content failures the arm answers. Measured at `da2a401`, it was the one item on that list with no
    mechanism behind it: `read_json` is `json.loads`, so anything it returns is handed to the renderers,
    and the renderers index. A survey that mutated ONE property of the committed snapshot at a time and ran
    `verify` corpus-less found ten shapes that escape as rc 1 -- a `TypeError` for a top-level array or
    string, a `KeyError` for `digests`, `unique_ids`, `upstream_audit_stdout_tail`, `id`, `match` -- while
    the unmodified control printed `re-derived 96 /96 values` and exited 0. rc 1 is the one exit code this
    project's contract forbids absolutely, and the defect is the checkout's: no argument named the file.

    These six plants are the classes that survey named, one per assertion rather than one per key, and each
    must land on `4` with the same refusal the parse failures get. The list is not decorative: `families`
    replaced by a string exits 4 on its own, because the byte comparison catches it -- which is why this row
    tests the shapes the byte comparison is reached *through*, not merely the shapes that differ.
    """
    base = json.loads((REPO / "data" / "inventory.md.json").read_text())

    def mutate(fn):
        # One property of a snapshot that passes differs per plant, so a plant that lands on 4 for a
        # second reason (an unrelated drift) cannot be mistaken for the shape rule working.
        return json.dumps(fn(json.loads(json.dumps(base))))

    plants = [
        ("top level is an array", mutate(lambda d: [])),
        ("top level is a string", mutate(lambda d: "just a string")),
        ("top level is an empty object", mutate(lambda d: {})),
        ("digest rows lost the key the renderer indexes", mutate(
            lambda d: dict(d, digests=[{k: v for k, v in row.items() if k != "match"}
                                       for row in d["digests"]]))),
        ("option rows are strings", mutate(
            lambda d: dict(d, corpus_options=["a string"] * len(d["corpus_options"])))),
        ("option rows lost `id`", mutate(
            lambda d: dict(d, corpus_options=[{k: v for k, v in row.items() if k != "id"}
                                              for row in d["corpus_options"]]))),
    ]
    for why, text in plants:
        work = tmp_path / "shape"
        (work / "data").mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO / "docs", work / "docs", dirs_exist_ok=True)
        stage_published(work)
        shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
        (work / "data" / "inventory.md.json").write_text(text)
        p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
        assert p.returncode == 4, (why, p.returncode, p.stdout, p.stderr)
        assert "Traceback" not in p.stderr, (why, p.stderr)
        for leak in ("KeyError", "TypeError", "AttributeError"):
            assert leak not in p.stderr, (why, leak, p.stderr)
        assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, (why, p.stderr)
        assert "data/inventory.md.json" in p.stderr, (why, p.stderr)
        assert "report.INVENTORY_JSON" in p.stderr, (why, p.stderr)
        assert "is not the artefact that table publishes" in p.stderr, (why, p.stderr)
        assert "re-derived" not in p.stdout, (why, p.stdout)


def test_the_shape_contract_demands_exactly_the_keys_this_build_indexes(tmp_path):
    """The two directions a shape rule needs, run in one process over the committed artefact.

    A guard that demands keys nobody reads is as wrong as one that demands nothing: it would refuse a
    checkout whose snapshot is fine, and it would let the contract rot silently in the other direction. So
    every key in the declared list gets a removal that must be refused, naming the key; every key of the
    real snapshot OUTSIDE the list gets the same removal and must be accepted, with the returned document
    still carrying all the others. Which keys belong to which class was measured by the one-variable survey
    in the row above, not chosen here: the 13 refused keys are the ones whose absence raised a `KeyError`
    from a renderer, and the tolerated ones are read with `.get()` or not read at all.

    The third assertion is the satisfiability check: the committed file must load. A contract no artefact
    satisfies is a gate that only ever refuses.
    """
    from autorate.report import INVENTORY_DIGEST_KEYS, INVENTORY_OPTION_KEYS, INVENTORY_TOP_KEYS
    from autorate.report import read_inventory_snapshot

    # The loader's list, checked against the measurement that produced it rather than against itself. The
    # two loops below derive BOTH directions from `INVENTORY_TOP_KEYS`, so on their own they can only prove
    # the list is internally consistent: demanding one key too many simply moves that key from the tolerated
    # loop to the refused one and the row stays green. Measured -- the first falsification pass planted
    # `sum_tolerance` into the required tuple and all three rows passed. This literal is the survey's
    # transcription, and it is the assertion that makes an over-reach visible.
    MEASURED_INDEXED_KEYS = ("corpus_options", "digests", "families", "gaps", "label_counts",
                             "lines_by_mode_backend", "provenance", "reader_lines_read", "repeats",
                             "source", "unique_ids", "upstream_audit_rc", "upstream_audit_stdout_tail")
    assert INVENTORY_TOP_KEYS == MEASURED_INDEXED_KEYS, (INVENTORY_TOP_KEYS, MEASURED_INDEXED_KEYS)

    real = json.loads((REPO / "data" / "inventory.md.json").read_text())
    assert read_inventory_snapshot(REPO / "data" / "inventory.md.json") == real

    required = sorted(set(INVENTORY_TOP_KEYS) | set(INVENTORY_DIGEST_KEYS) | set(INVENTORY_OPTION_KEYS))
    universe = (set(real)
                | {k for row in real["corpus_options"] for k in row}
                | {k for row in real["digests"] for k in row})
    assert set(required) <= universe, (sorted(set(required) - universe),)

    for key in INVENTORY_TOP_KEYS:
        doc = json.loads(json.dumps(real))
        del doc[key]
        path = tmp_path / ("top-%s.json" % key)
        path.write_text(json.dumps(doc))
        with pytest.raises(ValueError) as caught:
            read_inventory_snapshot(path)
        assert key in str(caught.value), (key, str(caught.value))

    for key in sorted(set(real) - set(INVENTORY_TOP_KEYS)):
        doc = json.loads(json.dumps(real))
        del doc[key]
        path = tmp_path / ("tolerated-%s.json" % key)
        path.write_text(json.dumps(doc))
        loaded = read_inventory_snapshot(path)
        assert key not in loaded, (key, sorted(loaded))
        assert set(loaded) == set(doc), (key, sorted(loaded), sorted(doc))

    for label, list_key, row_keys in (("digest", "digests", INVENTORY_DIGEST_KEYS),
                                      ("option", "corpus_options", INVENTORY_OPTION_KEYS)):
        for key in row_keys:
            doc = json.loads(json.dumps(real))
            doc[list_key] = [{k: v for k, v in row.items() if k != key} for row in doc[list_key]]
            path = tmp_path / ("%s-row-%s.json" % (label, key))
            path.write_text(json.dumps(doc))
            with pytest.raises(ValueError) as caught:
                read_inventory_snapshot(path)
            assert key in str(caught.value), (label, key, str(caught.value))


def test_the_corpus_present_leg_refuses_a_snapshot_that_is_not_a_json_object(tmp_path, monkeypatch):
    """The other reader of the same file, whose crash is an `AttributeError` rather than an index error.

    `expect_snapshot_is_current` unions `set(inv)` with `set(committed)` and then calls
    `committed.get(key)`, so a top-level array or string does not raise at the read -- it raises one
    statement later, and `AttributeError: 'list' object has no attribute 'get'` left the corpus-present lane
    at rc 1 while the corpus-less lane was already being repaired. Measured at `da2a401` with the vendored
    corpus in place: `[]` and `"x"` both exit 1, while `{}` exits 4 as a drift because `.get()` returns
    `None` and the comparison then disagrees. That asymmetry is why this row plants the two objects that
    crash and not the empty mapping, which the gate already answers correctly.
    """
    from autorate.cli import expect_snapshot_is_current
    from autorate.report import PublishedArtefactUnavailable

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    for text in ("[]", '"x"'):
        (tmp_path / "data" / "inventory.md.json").write_text(text)
        with pytest.raises(PublishedArtefactUnavailable) as caught:
            expect_snapshot_is_current(lambda label, actual, wanted: None, {"digests": []})
        message = str(caught.value)
        assert "data/inventory.md.json" in message, (text, message)
        assert "report.INVENTORY_JSON" in message, (text, message)
        assert "is not the artefact that table publishes" in message, (text, message)


def test_a_malformed_artefact_on_a_path_the_operator_supplied_is_still_a_usage_error(tmp_path):
    """The boundary the content arm must not cross: the same bad bytes, a path from argv or a default.

    Green on arrival for its first two blocks, and it is the row that keeps the fix in the right place.
    If the refusal lived inside `read_certificate` or `load_records` rather than at the sites the
    publication tables declare, all three reads below would turn rc 4: a typo in a `--cert` argument, and
    the malformed default records file as `verify` reads it and as `audit` reads it, are inputs this
    command was handed, which is exactly what `2` is for. Same file type, same broken contents, different
    owner of the path, different exit code. `compare` is deliberately not asserted here -- it reaches the
    same unwrapped `load_records`, and the round-3 ERRATA paragraph that claimed a row pinned its
    malformed-content case over-claimed and is corrected in round 4.
    """
    bad = tmp_path / "bad-cert.json"
    bad.write_text("{not a certificate")
    g = run("gate", str(REPO / "data" / "records_feishu.jsonl"), "--cert", str(bad))
    assert g.returncode == 2, (g.returncode, g.stdout, g.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in g.stderr, g.stderr

    work = tmp_path / "bad-default-records"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    stage_published(work)
    shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
    (work / "data" / "records_feishu.jsonl").write_text("not a record line\n")
    p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in p.stderr, p.stderr
    assert "re-derived" not in p.stdout, p.stdout

    # The command the README actually names for this residual. Round 3's prose said `audit --records`
    # and its row only ran `verify`; the claim and the pin now agree. Green on arrival, and the arm that
    # wraps this read in the content guard is what proves it can fail.
    a = run("audit", cwd=work)
    assert a.returncode == 2, (a.returncode, a.stdout, a.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in a.stderr, a.stderr
    assert "Traceback" not in a.stderr, a.stderr


def test_a_missing_published_artefact_is_a_named_drift_not_a_usage_error(tmp_path):
    """`verify` says "usage error" about a file no argument selected.

    Disclosed rather than fixed in `docs/ERRATA.md` (2026-10-08): with a published certificate absent
    the gate surfaced a bare `FileNotFoundError` mapped onto rc 2, whose only readable content is an
    errno and a relative path. That attribution is false twice over. It is not a usage error -- the
    path comes from the tables that state which artefacts this repository publishes, and nothing the
    operator typed selects it. And rc 2 is the code README gives to an input the command was
    handed, while the true statement is the one rc 4 already carries: the committed state cannot
    reproduce its
    own published numbers.

    One row per read path, because there are four and they are four different lines of code: the feishu
    certificate loop in `cmd_verify`, `report.massive_certificates()`'s certificate read, its records
    read, and the document loop. A refusal added to one of them and missing from the other three would
    pass a test that only had the first row.
    """
    cases = [
        ("data/cert_laya.json", "report.CERTS", False),
        ("data/cert_massive_de_laya.json", "report.MASSIVE_CERTIFICATES", False),
        ("data/records_massive_sw.jsonl", "report.MASSIVE_CERTIFICATES", False),
        # First in `PUBLISHED_DOCS`, so this row refuses on it and not on the `data/inventory.md`
        # beside it that this scratch tree also lacks: whichever missing file the gate reaches first
        # is the one the refusal is allowed to name.
        ("docs/RESULTS.md", "cli.PUBLISHED_DOCS", True),
    ]
    for rel, table, needs_snapshot in cases:
        work = tmp_path / rel.replace("/", "-").replace(".", "-")
        (work / "data").mkdir(parents=True)
        shutil.copytree(REPO / "docs", work / "docs")
        stage_published(work)
        if needs_snapshot:
            shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
        (work / rel).unlink()
        p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
        assert p.returncode == 4, (rel, p.returncode, p.stdout, p.stderr)
        assert "Traceback" not in p.stderr, (rel, p.stderr)
        assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, (rel, p.stderr)
        assert rel in p.stderr, (rel, p.stderr)
        assert table in p.stderr, (rel, p.stderr)
        # The two refusals the guard can raise say different things, and a reader acts on the
        # difference: restoring a file is not the same repair as fixing a permission. Without this
        # line the absent rows would still pass if the guard collapsed into one "cannot be opened"
        # branch and announced a checkout as present-but-broken.
        assert "is not in this checkout" in p.stderr, (rel, p.stderr)
        # The refusal must not be delivered as a reproduction result: there is no `re-derived` line
        # to read, and a printed denominator from a run that never got to the arithmetic would be a
        # second claim about a tree we know is broken.
        assert "re-derived" not in p.stdout, (rel, p.stdout)


def test_a_certificate_path_the_operator_supplied_is_still_a_usage_error(tmp_path):
    """The boundary the named refusal must not cross: a path from argv is the operator's to fix.

    Green on arrival -- this is the arm that keeps the change honest, not the fix's proof. If the
    named refusal were put inside `read_certificate` instead of at the sites the publication tables
    declare, both rows below would turn rc 4 and blame the reproduction gate for a typo in a command
    line. Same file type, same missing file, different owner of the path, different exit code.
    """
    absent = tmp_path / "absent.json"
    g = run("gate", str(REPO / "data" / "records_feishu.jsonl"), "--cert", str(absent))
    assert g.returncode == 2, (g.returncode, g.stdout, g.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in g.stderr, g.stderr
    c = run("compare", str(absent), str(REPO / "data" / "cert_jev.json"))
    assert c.returncode == 2, (c.returncode, c.stdout, c.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in c.stderr, c.stderr


def test_the_default_records_path_is_still_a_usage_error(tmp_path):
    """The third boundary the README states, on both of its arms: the records file the operator can name.

    Green on arrival, and it keeps the refusal's scope honest from the other side of the fence. The
    guard covers the artefacts whose absence contradicts a publication; `data/records_feishu.jsonl` is
    `audit --records`' default, so a checkout without it is reported as the unreadable input it is, not
    as drift. Wiring `require_published` over that read is the mutation this row exists to catch.

    It ran `verify` alone until round 4's falsification pass tried to predict its behaviour: the README's
    residual names `audit`, and `audit` was the command nobody pinned for the access arm. Measured on a
    scratch checkout, `audit` with the file unlinked prints `FileNotFoundError: [Errno 2] No such file or
    directory: 'data/records_feishu.jsonl'` and exits `2` -- the correct attribution, and previously only
    a habit. The block below is what makes it a guarantee, and the arm that wraps `audit`'s read reddens
    it along with the content row.
    """
    work = tmp_path / "no-default-records"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    stage_published(work)
    shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
    (work / "data" / "records_feishu.jsonl").unlink()
    p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in p.stderr, p.stderr
    assert "re-derived" not in p.stdout, p.stdout

    a = run("audit", cwd=work)
    assert a.returncode == 2, (a.returncode, a.stdout, a.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in a.stderr, a.stderr
    assert "Traceback" not in a.stderr, a.stderr


def test_a_published_artefact_that_cannot_be_opened_is_the_same_drift_not_a_usage_error(tmp_path):
    """The gate cannot READ a file its own tables declare: a directory in its place, or a mode that
    refuses the open. Measured before this row existed -- both exited 2, the first with
    `IsADirectoryError: [Errno 21] Is a directory: 'data/cert_laya.json'`, the second with
    `PermissionError: [Errno 13] Permission denied: 'data/cert_laya.json'`.

    Those are the same misattribution the row above retired, one step further along: the path is
    still the table's and not the operator's, and a checkout whose published certificate cannot be
    opened reproduces nothing, which is the sentence `4` carries. So `require_published` opens the
    file it vouches for rather than only stat-ing it, and the class and the printed label say
    `unavailable` instead of `absent` -- neither may claim the file has gone when it is present and
    unreadable.

    The permission row is skipped, not weakened, where the environment can read a mode-000 file: a
    runner executing as root cannot produce the condition, and a row asserting a refusal the OS will
    not raise is a red that proves nothing about the product.
    """
    for how in ("directory", "unreadable"):
        work = tmp_path / how
        (work / "data").mkdir(parents=True)
        shutil.copytree(REPO / "docs", work / "docs")
        stage_published(work)
        shutil.copy(REPO / "data" / "inventory.md.json", work / "data" / "inventory.md.json")
        target = work / "data" / "cert_laya.json"
        if how == "directory":
            target.unlink()
            target.mkdir()
        else:
            target.chmod(0)
            try:
                target.read_bytes()
            except OSError:
                pass
            else:
                target.chmod(0o644)
                pytest.skip("this environment reads a mode-000 file, so the condition cannot be made")
        try:
            p = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
            assert p.returncode == 4, (how, p.returncode, p.stdout, p.stderr)
            assert "Traceback" not in p.stderr, (how, p.stderr)
            assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, (how, p.stderr)
            assert "cannot be opened" in p.stderr, (how, p.stderr)
            assert "[Errno" in p.stderr, (how, p.stderr)
            assert "is not in this checkout" not in p.stderr, (how, p.stderr)
            # The refusal may not characterise what stands at the path, because the two rows differ:
            # under mode 000 the file is there, and under a directory it is not. Only the errno is
            # true in both, so anything else the message asserts is a claim this run did not earn.
            assert "the artefact is present" not in p.stderr, (how, p.stderr)
            assert "data/cert_laya.json" in p.stderr, (how, p.stderr)
            assert "report.CERTS" in p.stderr, (how, p.stderr)
            assert "re-derived" not in p.stdout, (how, p.stdout)
        finally:
            target.chmod(0o755 if target.is_dir() else 0o644)


def test_a_supervised_per_ask_gold_is_a_non_zero_refusal_not_a_malformed_line(tmp_path):
    """I-2: the R-14 per-ask-gold tripwire is a policy refusal, not an unreadable line.

    `read_archive` quarantines what it cannot read and keeps going, and the refusal travelled
    with it: the line IS readable, so the corpus condition got filed under
    `reason: malformed_line` and the command exited 0. A refusal has to stay loud and
    non-zero, and it must never be counted as a parse failure.
    """
    raw = tmp_path / "results" / "v1" / "laya" / "raw.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps({
        "id": "c-0", "mode": "four_noul", "repeat": 0, "status": "ok", "family": "f",
        "response": {"model": "m", "answers": {
            "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.8}}}}) + "\n")
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "manifest.json").write_text(json.dumps({"asks": ["urgent"]}))
    # The ask name now appears among the fixture keys: that is the condition R-14 names.
    (tmp_path / "data" / "cases.jsonl").write_text(
        json.dumps({"id": "c-0", "expected": "a", "urgent": "true"}) + "\n")
    p = run("export-feishu", "--backend", "laya", "--out", str(tmp_path / "out.jsonl"),
            root=tmp_path)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert "now supervised" in p.stderr, (p.stdout, p.stderr)
    # Not absorbed: no quarantine reason is published for a refusal, and no line is counted.
    assert "malformed_line" not in p.stdout + p.stderr, (p.stdout, p.stderr)
    assert "quarantined:" not in p.stdout, p.stdout


def test_a_stored_certificate_that_violates_its_shape_is_drift_on_a_published_path(tmp_path):
    """The brief's own Step-2 tamper, now told apart by whose path it was read from.

    Originally a single assertion that this tamper exits 2 rather than escaping as rc 1 with a traceback
    and no DRIFT row -- a real guarantee about a hole in the exit-code contract, and it still holds on the
    row below, where the path came from argv.

    R-176 moved the `verify` row to `4`. The certificate this run reads is the one `report.CERTS` declares
    published; its bytes are in the commit, no argument selected the path, and no argument can repair it.
    `2` says "an input this command was handed is wrong" about an input nobody was handed, which is the
    same false attribution the missing and unopenable rows retired. So the rc-1 hole is now closed by a
    named refusal rather than by a usage code, and the two rows together pin the axis that decides which:
    ownership of the path, not the class of the exception.
    """
    stage_committed_tree(tmp_path)
    cert = tmp_path / "data" / "cert_jev.json"
    doc = json.loads(cert.read_text())
    doc["envelope"] = []
    cert.write_text(json.dumps(doc, sort_keys=True))
    assert doc["envelope"] == [], "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" in p.stderr, p.stderr
    assert "data/cert_jev.json" in p.stderr, p.stderr
    assert "report.CERTS" in p.stderr, p.stderr
    assert "is not the artefact that table publishes" in p.stderr, p.stderr
    assert "does not parse" not in p.stderr, p.stderr
    assert "envelope" in p.stderr, p.stderr
    assert "Traceback" not in p.stderr, p.stderr
    assert "re-derived" not in p.stdout, p.stdout

    same = run("gate", str(REPO / "data" / "records_feishu.jsonl"), "--cert", str(cert))
    assert same.returncode == 2, (same.returncode, same.stdout, same.stderr)
    assert "PUBLISHED ARTEFACT UNAVAILABLE" not in same.stderr, same.stderr
    assert "envelope" in same.stderr, same.stderr
    assert "Traceback" not in same.stderr, same.stderr


def test_the_inventory_names_a_command_the_cli_actually_has(tmp_path):
    """I-2, half 1: the artefact's header tells readers how to reproduce it.

    Checked against the shipped parser rather than against prose, so a runner with no
    corpus still catches a header that names a command nobody implemented.
    """
    header = (REPO / "data" / "inventory.md").read_text().splitlines()[2]
    named = __import__("re").search(r"`uv run --frozen autorate ([a-z-]+)`", header)
    assert named, header
    help_text = __import__("autorate.cli", fromlist=["build_parser"]).build_parser(
    ).format_help()
    assert named.group(1) in help_text, (named.group(1), help_text)
    unknown = run("definitely-not-a-command")
    assert unknown.returncode == 2, unknown.returncode


@skip
def test_snapshot_command_reproduces_the_committed_inventory(tmp_path):
    """I-2, half 2: the named command must really produce the committed bytes."""
    out = tmp_path / "inv" / "inventory.md"
    p = run("snapshot", "--out", str(out))
    assert p.returncode == 0, p.stdout + p.stderr
    assert out.read_bytes() == (REPO / "data" / "inventory.md").read_bytes(), \
        "the committed inventory is not what `snapshot` writes"
    assert json.loads((Path(str(out) + ".json")).read_text()) == \
        json.loads((REPO / "data" / "inventory.md.json").read_text())


def test_verify_catches_an_edited_inventory_markdown(tmp_path):
    """The published inventory is now byte-checked in both lanes, so prove it can fail."""
    stage_committed_tree(tmp_path)
    doc = tmp_path / "data" / "inventory.md"
    doc.write_text(doc.read_text().replace("label balance: noise=16", "label balance: noise=99"))
    assert "noise=99" in doc.read_text(), "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "data/inventory.md byte-identical" in p.stderr, p.stderr


def test_verify_catches_an_edited_audit_markdown(tmp_path):
    """MAJ-3's arm must be able to fail, or `docs/AUDIT.md` is a document the gate merely counts.

    Same shape as the two byte-checks above: copy the published set, change one number the tool
    emits, and require rc 4 naming the file. `docs/AUDIT.md` carries no timestamp, so a re-render is
    byte-comparable -- the claim `tests/test_audit.py` could only make against its own re-render
    until the gate itself re-derived the artefact.
    """
    stage_committed_tree(tmp_path)
    doc = tmp_path / "docs" / "AUDIT.md"
    doc.write_text(doc.read_text().replace("0.8312", "0.9000"))
    assert "0.9000" in doc.read_text(), "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "docs/AUDIT.md byte-identical" in p.stderr, p.stderr


def _tracked_subjects(repo: Path) -> tuple:
    """The files the path guard scans, and where that list came from.

    A `git archive` export carries no `.git`, so a `git ls-files`-only subject is EMPTY there: the
    guard either passes vacuously or reddens before the export lane can demonstrate anything (G5). The
    export script therefore writes its own tracked list and points `AUTORATE_TRACKED_FILES` at it, so
    the scan covers exactly the published set -- no ignore list, which would be its own blind spot --
    and an empty subject still fails loudly.
    """
    import os
    import subprocess

    manifest = os.environ.get("AUTORATE_TRACKED_FILES")
    if manifest:
        path = Path(manifest)
        if not path.is_file():
            raise AssertionError("AUTORATE_TRACKED_FILES=%s names no file" % manifest)
        names = path.read_text(errors="ignore").split()
        if not names:
            raise AssertionError("manifest %s is empty; the guard has no subject" % path)
        return names, "manifest"
    names = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                           cwd=str(repo)).stdout.split()
    if names:
        return names, "git ls-files"
    raise AssertionError(
        "nothing to scan: AUTORATE_TRACKED_FILES is unset and `git ls-files` returned no paths. "
        "In a `git archive` export, write `git ls-files > <export>/.tracked-files` before the suite")


def _path_offenders(names, root: Path) -> list:
    home = str(Path.home())
    out = []
    for rel in names:
        f = root / rel
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if home in line:
                out.append((rel, i, "this machine's home directory"))
            elif MACHINE_PATH_RX.search(line):
                out.append((rel, i, MACHINE_PATH_RX.search(line).group(0)))
    return out


def test_no_committed_file_carries_an_absolute_home_path():
    """I-7: an absolute literal passes every local gate, and only CI can see it break.

    Checked as structure over the tracked tree -- not by reading files I happen to think
    are the risky ones -- because the class of defect is the path itself.
    """
    names, source = _tracked_subjects(REPO)
    assert names, "empty subject from %s; the guard would pass vacuously" % source
    offenders = _path_offenders(names, REPO)
    assert not offenders, offenders
    # Built from pieces so this file does not become the offender it is looking for.
    assert str(Path.home()).startswith("/") and MACHINE_PATH_RX.search("/" + "Users/bob/x"), \
        "the guard is vacuous"


def test_the_path_guard_scans_a_manifest_when_there_is_no_repository(tmp_path, monkeypatch):
    """The export case: no `.git`, so the subject must come from the manifest -- and still bite."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "g.md").write_text("see /%s/%s/x.jsonl\n" % ("Users", "someone"))
    listing = tmp_path / ".tracked-files"
    listing.write_text("docs/g.md\n")
    monkeypatch.setenv("AUTORATE_TRACKED_FILES", str(listing))
    names, source = _tracked_subjects(tmp_path)
    assert source == "manifest" and names == ["docs/g.md"], (source, names)
    found = _path_offenders(names, tmp_path)
    assert found and found[0][0] == "docs/g.md", found
    # ...and a clean manifest over the same tree proves the hit came from the content, not the shape
    # of the fixture: removing the line must empty the report.
    (tmp_path / "docs" / "g.md").write_text("no path here\n")
    assert _path_offenders(names, tmp_path) == []


def test_the_path_guard_refuses_an_empty_subject_from_either_source(tmp_path, monkeypatch):
    """Non-vacuity is the guard's whole value, so both empty paths must raise, not pass."""
    empty = tmp_path / ".tracked-files"
    empty.write_text("\n")
    monkeypatch.setenv("AUTORATE_TRACKED_FILES", str(empty))
    with pytest.raises(AssertionError, match="empty"):
        _tracked_subjects(tmp_path)
    monkeypatch.setenv("AUTORATE_TRACKED_FILES", str(tmp_path / "absent"))
    with pytest.raises(AssertionError, match="no file"):
        _tracked_subjects(tmp_path)
    monkeypatch.delenv("AUTORATE_TRACKED_FILES")
    with pytest.raises(AssertionError, match="git ls-files"):
        _tracked_subjects(tmp_path)


def test_not_certifiable_exits_3_on_a_records_file_with_no_corpus(tmp_path):
    """I-4: exit 3 was only reachable behind a corpus skip, so CI never exercised it.

    Built from synthetic records rather than the vendored archive: 100 labelled choice
    records split 50/50, which is under MIN_CAL/MIN_EVAL, so the refusal is a property of
    the contract and every runner can see it.
    """
    import random

    from autorate.records import Record

    rng = random.Random(3)
    recs = []
    for i in range(100):
        p = [0.4, 0.3, 0.2, 0.1]
        rng.shuffle(p)
        opts = tuple("opt%d" % j for j in range(4))
        recs.append(Record(id=str(i), qtype="choice", backend="synthetic", repeat=0,
                           options=opts, probs=tuple(p), gold=opts[0], predicted=opts[0],
                           slices={}, scores={}, seed=3, u=rng.random(), meta={}))
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in recs))
    cert = tmp_path / "cert.json"
    p = run("certify", str(path), "--out", str(cert))
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert "NOT_CERTIFIABLE" in p.stdout and "n_below_min" in p.stdout, p.stdout
    doc = json.loads(cert.read_text())
    assert doc["feasible"] is False and doc["reason"] == "n_below_min"
    assert doc["envelope"], "a refusal without its envelope is invalid output"
    assert doc["autorate"] is None and doc["qhat"] is None

    g = run("gate", str(path), "--cert", str(cert), "--limit", "2")
    assert g.returncode == 3, (g.returncode, g.stdout, g.stderr)
    assert all("action=abstain" in l for l in g.stdout.splitlines() if "action=" in l), g.stdout


def test_unknown_method_raises_before_any_certification():
    from autorate.certify_choice import certify_choice

    with pytest.raises(ValueError, match="unknown method"):
        certify_choice([], method="crc")


def test_a_tripped_arithmetic_invariant_exits_4_and_names_itself(tmp_path, monkeypatch, capsys):
    """#27: rc 1 was reachable from the CLI through the guards that protect our own arithmetic.

    Both sites -- `tails.clopper_pearson_upper` refusing a bound beaten by its own data, and the
    reader refusing to return when line accounting does not conserve -- are ArithmeticError, which
    neither of the documented clauses used to see, so they escaped as a traceback with exit code 1:
    outside the published 0/2/3/4 contract. Mapping them to EXIT_DRIFT says what is actually wrong
    (the tool cannot reproduce its own numbers) and the prefix keeps the message distinguishable
    from ordinary drift.
    """
    import importlib

    # `autorate/__init__` re-exports the FUNCTION named certify_choice, so attribute access on the
    # package would hand back the function and the patch would land on nothing.
    cz = importlib.import_module("autorate.certify_choice")
    from autorate import tails
    from autorate.cli import EXIT_DRIFT, main

    def boom(*args, **kwargs):
        raise ArithmeticError("forced: a bound cannot be beaten by its own data")

    monkeypatch.setattr(cz, "clopper_pearson_upper", boom)
    rc = main(["certify", str(REPO / "data" / "records_feishu.jsonl"), "--backend", "jev",
               "--out", str(tmp_path / "cert.json")])
    assert rc == EXIT_DRIFT, rc
    err = capsys.readouterr().err
    assert err.startswith("INVARIANT: ArithmeticError: forced:"), err
    assert "Traceback" not in err, err

    # the guards themselves must stay armed -- a mapping that swallowed them would look like this
    monkeypatch.undo()
    monkeypatch.setattr(tails, "binom_cdf", lambda k, n, p: 0.0)
    with pytest.raises(ArithmeticError, match="cannot be beaten"):
        tails.clopper_pearson_upper(1, 10, 0.05)


def test_the_invariant_clause_is_not_reached_by_an_ordinary_usage_error(capsys):
    """Ordering control: the new clause must not become the catch-all for bad input.

    A missing records file is `OSError`, which still maps to EXIT_USAGE -- if the invariant clause
    were placed above it, or widened to take ValueError, a user typo would start reporting that this
    repository's arithmetic is broken.
    """
    from autorate.cli import EXIT_USAGE, main

    assert main(["certify", "/nonexistent/path/records.jsonl"]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert not err.startswith("INVARIANT"), err


def test_verify_reds_when_a_transcribed_bound_column_is_wrong(monkeypatch, tmp_path, capsys):
    """R-79 (re-review MA-5): the pin arm re-derived counts but not the columns beside them.

    `data/inventory.md` and `docs/RESULTS.md` publish `bound width at alpha=0.05` and
    `feasible at 0.10` for every corpus option, and those columns are computed by
    `tails.bound_width` from the row count -- so a copy that carried 0.0100 for n=2,974
    (the true width is 0.0498) passed `verify` at 41/41, exit 0. That is the goal's own
    criterion with a hole in it: G5 says every published number re-derives.

    The artefacts are re-rendered from the tampered snapshot through the repository's own
    writers, so the two byte-comparisons stay satisfied and only a recomputation can catch it.
    The control at the end is what proves that: the same tree, restored to the published
    numbers, must go green -- otherwise this is a test that the markdown disagrees with itself.
    """
    import shutil

    from autorate.cli import EXIT_CERTIFIED as EXIT_OK, EXIT_DRIFT, main
    from autorate.inventory import write_inventory
    from autorate.report import (build_report, certify_all, load_records, write_report)

    work = tmp_path / "checkout"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    stage_published(work)
    for name in ("massive_provenance.json", "inventory.md.json"):
        shutil.copy(REPO / "data" / name, work / "data" / name)

    published = json.loads((REPO / "data" / "inventory.md.json").read_text())

    def render(inv):
        """Publish `inv` the way the repository does, so no byte-comparison can object."""
        (work / "data" / "inventory.md.json").write_text(json.dumps(inv))
        write_inventory(inv, work / "data" / "inventory.md")
        records = load_records(work / "data" / "records_feishu.jsonl")
        write_report(build_report(inv, certify_all(records),
                                  {b: len(rs) for b, rs in records.items()}),
                     work / "docs" / "RESULTS.md")

    def verify():
        monkeypatch.chdir(work)
        monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus"))
        rc = main(["verify"])
        captured = capsys.readouterr()
        monkeypatch.undo()
        return rc, captured.out, captured.err

    tampered = json.loads(json.dumps(published))
    wrong = 0
    for option in tampered["corpus_options"]:
        if option["id"].startswith("massive"):
            option["bound_width_at_0.05"] = 0.01        # true: 0.0498
            option["feasible_at_0.10"] = False          # true: yes -- the row's whole point
            wrong += 1
    assert wrong == 2, wrong
    render(tampered)
    rc, out, err = verify()
    assert rc == EXIT_DRIFT, (rc, out, err)
    assert "bound_width_at_0.05" in err, err
    assert "feasible_at_0.10" in err, err
    assert "byte-identical" not in err, err             # only a recomputation may object

    render(published)                                   # the control: same machinery, true numbers
    rc, out, err = verify()
    assert rc == EXIT_OK, (rc, out, err)


def _group_record(name, i, gold, peaked, k=4, sharpness=30.0, u=0.5, slices=None):
    """One labelled decision, from the shared R-69 factory and nothing else.

    `slices` is the point: the Mondrian surface conditions on keys the PRODUCER declared, so a fixture
    that left `slices` empty could only ever exercise the refusal, never the run.
    """
    from _records import choice_record

    vector = [1.0] * k
    vector[peaked] = sharpness
    total = sum(vector) + k * 0.05
    probs = [round(x / total, 4) for x in vector]
    probs[peaked] = round(probs[peaked] + (1.0 - sum(probs)), 4)
    options = tuple("opt%d" % j for j in range(k))
    # `slices or {...}` would be wrong here: the file needs a batch that declares NOTHING, and an
    # empty dict is falsy, so `or` would quietly fill it in and the undeclared-key row would be
    # testing a population that does have the key.
    return choice_record(id="%s-%d" % (name, i), probs=tuple(probs), gold=options[gold],
                         predicted=options[peaked], u=u,
                         slices=({"family": name} if slices is None else slices))


def _write(path, records):
    path.write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in records))
    return path


def _clean(name, n, start=0, slices=None):
    return [_group_record(name, i, gold=i % 4, peaked=i % 4, u=(i % 97) / 100.0, slices=slices)
            for i in range(start, start + n)]


@pytest.fixture(scope="module")
def group_files(tmp_path_factory):
    """Three slices of unequal size, one under the floor, and a two-slice file that clears it.

    CONSTRUCTED, and labelled as such: the point is the size floor and the exit code, and the real
    collapsed slices (`de`, `sw`, `km`) are Plan C's publication to make (obligation #68), not this
    file's to read from a machine path.
    """
    root = tmp_path_factory.mktemp("groups")
    mixed = _write(root / "mixed.jsonl", _clean("clean-a", 150) + _clean("clean-b", 150, start=1)
                   + _clean("tiny", 8, start=2))
    clear = _write(root / "clear.jsonl", _clean("clean-a", 150) + _clean("clean-b", 150, start=1))
    plain = _write(root / "no_slices.jsonl", [_group_record("f", i, gold=i % 4, peaked=i % 4,
                                                            slices={}) for i in range(140)])
    return root, mixed, clear, plain


@pytest.fixture(scope="module")
def dark_file(tmp_path_factory):
    """One slice of 140 unlabelled cases -- above the floor, so it reaches the certifier.

    CONSTRUCTED. The 140 cases are the whole point: below the floor the size branch prints the held
    count and never touches the denominator this file is about, so a smaller fixture could not
    exercise the line at all.
    """
    from _records import choice_record

    root = tmp_path_factory.mktemp("dark")
    records = [choice_record(id="dark-%d" % i, gold=None, predicted="opt0",
                             u=(i % 97) / 100.0, slices={"family": "dark"}) for i in range(140)]
    return _write(root / "dark.jsonl", records), root / "dark.json"


def test_groups_on_the_cli_reaches_the_mondrian_surface_and_rc_follows_the_worst_slice(group_files):
    """`--groups` is the user's door to spec 8.1, and the exit code is the worst slice's verdict."""
    _root, mixed, clear, _plain = group_files
    out = _root / "certified.json"
    run_result = run("certify", str(mixed), "--groups", "family", "--out", str(out), "--seed", "7")
    assert run_result.returncode == 3, (run_result.stdout, run_result.stderr)
    text = run_result.stdout
    assert "group-conditional (Mondrian) run over 3 slices declared as 'family'" in text, text
    assert "slice tiny (n=8 cases): NOT CERTIFIED" in text, text
    assert "below the group size floor" in text, text
    assert "refused by size (below 120 cases" in text and "tiny(n=8)" in text, text
    assert "worst-of-3 over 'family': slice tiny" in text, text
    doc = json.loads(out.read_text())
    assert doc["n_groups"] == 3 and doc["any_slice_refused"] is True
    assert [row["group"] for row in doc["refused_by_size"]] == ["tiny"]
    assert doc["thinnest"] == "tiny"

    ok = _root / "all_certified.json"
    clean_run = run("certify", str(clear), "--groups", "family", "--out", str(ok), "--seed", "7")
    assert clean_run.returncode == 0, (clean_run.stdout, clean_run.stderr)
    assert "2 certified, 0 refused" in clean_run.stdout, clean_run.stdout
    assert "NOT CERTIFIED" not in clean_run.stdout, clean_run.stdout
    assert json.loads(ok.read_text())["any_slice_refused"] is False


def test_every_rendered_slice_line_matches_the_artefact_that_was_written(group_files):
    """The lines are rendered FROM the certificates, so each one is checkable against the JSON.

    Asserted per rendered row rather than as a count: the drift review's MAJOR-C2 class is a guard
    that iterates fields which are all `None`, and a "there are 3 slice lines" assertion passes on
    three lines about the wrong slices.
    """
    _root, mixed, _clear, _plain = group_files
    out = _root / "rendered.json"
    result = run("certify", str(mixed), "--groups", "family", "--out", str(out), "--seed", "7")
    doc = json.loads(out.read_text())
    census = {row["group"]: row for row in doc["slice_census"]}
    lines = [line for line in result.stdout.splitlines() if line.startswith("  slice ")]
    assert len(lines) == doc["n_groups"], lines
    for line in lines:
        name = line.split("slice ", 1)[1].split(" ", 1)[0]
        stated_n = int(line.split("(n=", 1)[1].split(" cases)", 1)[0])
        # Two different denominators, chosen by WHICH branch produced the verdict: the size floor is
        # stated in terms of the cases the slice HOLDS (its own reason string prints that number), and
        # a certifier verdict -- feasible or refused -- is stated in terms of the cases the certifier
        # was actually handed. Asserting one field for both would let either renderer slide.
        if name in {row["group"] for row in doc["refused_by_size"]}:
            assert stated_n == doc["slice_cases"][name], (line, doc["slice_cases"])
        else:
            assert "eligible_cases" in census[name], (line, census[name])
            assert stated_n == census[name]["eligible_cases"], (line, census[name])
            assert stated_n <= doc["slice_cases"][name], (line, census[name])
        certified = "autorate" in line
        assert certified is doc["per_group"][name]["feasible"], line
        if certified:
            assert "conditional error <=" in line and "autorate " in line, line
        else:
            stated = next((row["why"] for row in doc["worst_claim"]["refusals"]
                           if row["group"] == name), None)
            assert stated is not None, (name, doc["worst_claim"]["refusals"])
            assert "NOT CERTIFIED -- " + stated in line, (line, stated)


@pytest.fixture(scope="module")
def partly_labelled_files(tmp_path_factory):
    """Two slices whose HOLDINGS and ELIGIBLE CASES differ, one above the floor and one below.

    CONSTRUCTED. The all-or-nothing `dark` slice cannot tell the two renderers apart on the floor
    branch: this file makes `cases` and `eligible_cases` disagree inside BOTH branches, so a line that
    picked the wrong one for a branch is checkable rather than merely unlikely.
    """
    from _records import choice_record
    from autorate.records import Record

    root = tmp_path_factory.mktemp("partly")
    unlabelled = lambda name, count: [choice_record(id="%s-u%d" % (name, j), gold=None,
                                                    predicted="opt0", u=(j % 97) / 100.0,
                                                    slices={"family": name})
                                       for j in range(count)]
    part = _clean("part", 120) + unlabelled("part", 20)
    dim = _clean("dim", 30, start=7) + unlabelled("dim", 10)
    # A third cause for the SAME gap in the printed denominator: `foreign` is fully labelled, and its
    # cases still never reach a CHOICE certifier because they answer another question. A sentence that
    # attributed every gap to a missing gold label would lie on this row.
    foreign = _clean("foreign", 130, start=11) + [
        Record(id="foreign-n%d" % j, qtype="noul", backend="synthetic", repeat=0,
               options=("false", "true"), probs=(0.2, 0.8), gold="true", predicted="true",
               case_id=None, slices={"family": "foreign"}, scores={}, seed=1, u=0.5, meta={})
        for j in range(30)]
    return _write(root / "partly.jsonl", part + dim + foreign), root / "partly.json"


def test_a_partly_labelled_slice_prints_the_certifier_count_and_the_floor_keeps_the_holding(
        partly_labelled_files):
    """The two branches state two denominators, and the gap is said in words on the same line.

    `part` holds 140 cases and is handed 120; `dim` holds 40 and is refused BY THE FLOOR, whose own
    reason string names 40. A renderer that used one denominator everywhere would print 30 for `dim`
    -- a refusal of a slice that "only had 30 cases", when the floor is priced on holdings -- or 140
    for `part`, which is the G2/F-5 defect at the non-extreme size the real corpus actually has.
    """
    path, out = partly_labelled_files
    result = run("certify", str(path), "--groups", "family", "--out", str(out), "--seed", "7")
    assert result.returncode == 3, (result.stdout, result.stderr)
    text = result.stdout
    lines = {line.split("slice ", 1)[1].split(" ", 1)[0]: line
             for line in text.splitlines() if line.startswith("  slice ")}
    assert set(lines) == {"part", "dim", "foreign"}, text
    assert "slice part (n=120 cases)" in lines["part"], lines["part"]
    assert "n=140" not in lines["part"], lines["part"]
    assert "-- 20 of the slice's 140 cases never reached the rule (20 records carry no gold label)" \
        in lines["part"], lines["part"]
    assert "slice dim (n=40 cases)" in lines["dim"], lines["dim"]
    assert "n=30" not in lines["dim"], lines["dim"]
    assert "never reached the rule" not in lines["dim"], lines["dim"]
    assert "dim(n=40)" in text, text
    assert "slice foreign (n=130 cases)" in lines["foreign"], lines["foreign"]
    assert "n=160" not in lines["foreign"], lines["foreign"]
    assert "-- 30 of the slice's 160 cases never reached the rule (30 records answer another " \
        "question type)" in lines["foreign"], lines["foreign"]
    assert "no gold label" not in lines["foreign"], lines["foreign"]
    doc = json.loads(out.read_text())
    census = {row["group"]: row for row in doc["slice_census"]}
    assert (census["part"]["cases"], census["part"]["eligible_cases"],
            census["part"]["kept"], census["part"]["skipped_no_gold"]) == (140, 120, 120, 20), \
        census["part"]
    assert (census["dim"]["cases"], census["dim"]["eligible_cases"],
            census["dim"]["kept"]) == (40, 30, 30), census["dim"]
    assert (census["foreign"]["cases"], census["foreign"]["eligible_cases"],
            census["foreign"]["skipped_no_gold"],
            census["foreign"]["skipped_wrong_qtype"]) == (160, 130, 0, 30), census["foreign"]
    assert doc["slice_cases"] == {"part": 140, "dim": 40, "foreign": 160}, doc["slice_cases"]
    assert doc["slice_eligible_cases"] == {"part": 120, "dim": 30,
                                           "foreign": 130}, doc["slice_eligible_cases"]


def test_a_slice_with_no_labelled_cases_prints_the_denominator_the_certifier_was_handed(dark_file):
    """The `n` on a certifier's slice line is the cases it could READ, not the cases on disk.

    Measured before the fix: the line read `slice dark (n=140 cases)` for a certificate built from an
    empty population -- `certify_groups` hands `certify_choice` the `kept` records, and all 140 of
    these were dropped for lacking gold. A reader comparing that `n` with the refusal had to conclude
    the rule refused 140 labelled cases; it refused zero. The census keeps `cases` 140 because the
    floor is priced on holdings, so the two numbers must appear together or one of them is a lie.
    """
    path, out = dark_file
    result = run("certify", str(path), "--groups", "family", "--out", str(out), "--seed", "7")
    assert result.returncode == 3, (result.stdout, result.stderr)
    text = result.stdout
    assert "slice dark (n=0 cases): NOT CERTIFIED -- no labelled choice records to calibrate on" \
        in text, text
    assert "n=140 cases" not in text, text
    assert "-- 140 of the slice's 140 cases never reached the rule (140 records carry no gold " \
           "label)" in text, text
    assert "refused by size" not in text, text
    doc = json.loads(out.read_text())
    row = next(entry for entry in doc["slice_census"] if entry["group"] == "dark")
    assert "eligible_cases" in row, row
    assert (row["cases"], row["eligible_cases"], row["kept"]) == (140, 0, 0), row
    assert doc["slice_cases"] == {"dark": 140}, doc["slice_cases"]
    assert doc["slice_eligible_cases"] == {"dark": 0}, doc


def test_an_undeclared_group_key_exits_2_through_the_cli_and_names_the_keys_the_batch_states(
        group_files):
    """R-115's ruling, reached the way an operator reaches it: a typo on `--groups`.

    In-process the function raised the refusal; through `main()` the same refusal was an rc-1
    traceback, because `groups.py` raised a bare `KeyError` and `main` has no such arm (and must not
    gain one). `UndeclaredGroupKey(ValueError)` is what makes the existing `ValueError -> 2` mapping
    correct here, and the message names the keys the batch DOES state so the operator can fix the
    argument rather than guess.
    """
    from autorate.cli import main
    from autorate.groups import UndeclaredGroupKey

    _root, mixed, _clear, plain = group_files
    typo = run("certify", str(mixed), "--groups", "langauge", "--out", str(_root / "t.json"))
    assert typo.returncode == 2, (typo.returncode, typo.stdout, typo.stderr)
    assert "UndeclaredGroupKey" in typo.stderr, typo.stderr
    assert "Traceback" not in typo.stderr, typo.stderr
    assert "'family'" in typo.stderr, "it must say what the batch actually declares"

    # A records file that declares NO slice keys at all: the same refusal, the same exit code.
    unprepared = run("certify", str(plain), "--groups", "family", "--out", str(_root / "u.json"))
    assert unprepared.returncode == 2, (unprepared.returncode, unprepared.stderr)
    assert "UndeclaredGroupKey" in unprepared.stderr and "nothing" in unprepared.stderr

    assert main(["certify", str(mixed), "--groups", "language",
                 "--out", str(_root / "inproc.json")]) == 2
    with pytest.raises(UndeclaredGroupKey):
        from autorate.certify_choice import certify_groups

        certify_groups(_clean("x", 130), groups=("language",))


def test_the_undeclared_group_key_is_a_valueerror_and_not_a_keyerror(group_files):
    """The exit-code contract is delivered by the parent class, and the diagnosis by this one.

    R-115 chose the shape for exactly this reason, and `main()`'s arm is `(OSError, ValueError)`:
    if `UndeclaredGroupKey` stopped being a `ValueError` the CLI would go back to rc 1, and if it were
    a plain `ValueError` the operator could not grep what refused them. Both halves asserted, because
    either one alone is the defect.
    """
    from autorate.groups import UndeclaredGroupKey

    assert issubclass(UndeclaredGroupKey, ValueError)
    assert not issubclass(UndeclaredGroupKey, KeyError), (
        "KeyError stays uncaught centrally: it is ordinary dict access everywhere in this codebase, "
        "and mapping it to 2 would turn unrelated bugs into a usage exit with a helpful message")
    _root, mixed, _clear, _plain = group_files
    result = run("certify", str(mixed), "--groups", "language", "--out", str(_root / "v.json"))
    assert result.returncode == 2, result.stderr
    assert "KeyError" not in result.stderr, result.stderr


def test_no_groups_value_a_user_can_type_reaches_rc_1(group_files):
    """The rc-1 sweep: every malformed `--groups` is a usage refusal (2), never a traceback (1).

    Includes the shapes a shell actually produces -- an empty value, a trailing comma, a bare comma,
    a space, and a key named twice -- plus `--groups` with no value at all, which argparse itself
    refuses at 2. A `TypeError` or `KeyError` escaping here would be rc 1 and outside the documented
    0/2/3/4 contract.
    """
    _root, mixed, _clear, _plain = group_files
    # Two owners, two messages, one exit code. A value the CLI itself cannot read is the CLI's
    # refusal and names the flag; a well-formed key the records never declare is refused at the
    # raising site (R-115) and names what the batch DOES state. Asserting only the rc would pass on
    # either message, so each arm asserts its own diagnosis too.
    malformed = ["", " ", ",", "family,", "family, ", "family,family", "family, family",
                 "family,,clean-a"]
    for value in malformed:
        result = run("certify", str(mixed), "--groups", value, "--out", str(_root / "s.json"))
        assert result.returncode == 2, (value, result.returncode, result.stdout, result.stderr)
        assert "Traceback" not in result.stderr, (value, result.stderr)
        assert result.stderr.strip(), "a usage error that prints nothing is not diagnosable"
        assert "UsageError" in result.stderr, (value, result.stderr)
        assert "--groups" in result.stderr, (value, result.stderr)
    undeclared = ["language", "FAMILY", "langauge", "slices"]
    for value in undeclared:
        result = run("certify", str(mixed), "--groups", value, "--out", str(_root / "s.json"))
        assert result.returncode == 2, (value, result.returncode, result.stderr)
        assert "Traceback" not in result.stderr, (value, result.stderr)
        assert "UndeclaredGroupKey" in result.stderr, (value, result.stderr)
        assert "'family'" in result.stderr, (value, "the refusal must state the keys that exist")
    missing_value = run("certify", str(mixed), "--groups", "--out", str(_root / "m.json"))
    assert missing_value.returncode == 2, missing_value.stderr
    assert "Traceback" not in missing_value.stderr, missing_value.stderr


def test_the_group_run_writes_an_artefact_a_reader_can_rebuild_the_level_from(group_files):
    """R-159 at the user's surface: a bare 0.85 has to be reconstructible from the file alone.

    Every field the product needs is in the JSON, and the identity is checked there rather than in
    Python -- the artefact is what a reviewer gets.
    """
    _root, mixed, clear, _plain = group_files
    out = _root / "rebuild.json"
    result = run("certify", str(clear), "--groups", "family", "--out", str(out), "--seed", "7")
    assert result.returncode == 0, (result.stdout, result.stderr)
    doc = json.loads(out.read_text())
    assert doc["level"] == pytest.approx(1.0 - doc["n_claims"] * doc["delta"])
    assert doc["corrected_alpha"] == pytest.approx(doc["alpha"] / doc["n_groups"])
    assert doc["corrected_delta"] == pytest.approx(doc["delta"] / doc["n_groups"])
    assert doc["n_groups"] == len(doc["per_group"]) == len(doc["slice_census"])
    assert doc["n_claims"] == 3 and doc["n_groups"] != 3, (
        "the slice count is the census's, not the envelope count (R-149)")
    assert doc["worst_claim"]["joint_level"] is None and doc["worst_claim"]["joint_level_rule"], (
        "one publisher of the level, and the rule stated even where the number is not derived")
    assert "derive_joint_level=False" in doc["worst_claim"]["joint_level_note"]
    assert any("beta is NOT divided" in line for line in doc["envelope"]), doc["envelope"]
    for name, slice_doc in doc["per_group"].items():
        assert slice_doc["delta"] == pytest.approx(doc["corrected_delta"]), name
        # `level` is not a stored field on a certificate -- a stored one was the second owner R-20
        # removed -- so the slice's level is rebuilt from the delta the payload does carry.
        assert 1.0 - doc["n_claims"] * slice_doc["delta"] > doc["level"], name


def test_the_two_key_declaration_partitions_by_the_tuple_and_still_refuses_by_name(group_files):
    """`--groups family,mode` is spec 8.1's (language x option-count) shape, reached from a shell.

    The names in the artefact are the tuples, the slice count is the product of the two keys, and the
    floor still refuses the thin cells by name instead of averaging them into their neighbours.
    """
    from autorate.certify_choice import certify_choice

    rows = []
    for family in ("f0", "f1"):
        for mode in ("fast", "slow"):
            n = 150 if (family, mode) != ("f1", "slow") else 8
            # Unique id prefix per CELL: `f0-0` present in both modes would be one case that
            # disagrees with itself about a declared key, and `by_group` refuses exactly that (the
            # leakage refusal fired here first, which is the refusal working, not the fixture).
            rows += [_group_record("%s.%s" % (family, mode), i, gold=i % 4, peaked=i % 4,
                                   u=(i % 97) / 100.0,
                                   slices={"family": family, "mode": mode})
                     for i in range(n)]
    path = _write(group_files[0] / "two_key.jsonl", rows)
    out = group_files[0] / "two_key.json"
    result = run("certify", str(path), "--groups", "family,mode", "--out", str(out), "--seed", "7")
    assert result.returncode == 3, (result.stdout, result.stderr)
    doc = json.loads(out.read_text())
    assert doc["groups"] == ["family", "mode"] and doc["n_groups"] == 4
    assert doc["corrected_alpha"] == pytest.approx(0.05 / 4)
    assert doc["thinnest"] == ["f1", "slow"], doc["thinnest"]
    assert [row["group"] for row in doc["refused_by_size"]] == [["f1", "slow"]], doc["refused_by_size"]
    assert "f1" in result.stdout and "slow" in result.stdout, result.stdout
    # One flag, two spellings: the repeated form is the same run.
    repeated = run("certify", str(path), "--groups", "family", "--groups", "mode",
                   "--out", str(group_files[0] / "two_key_b.json"), "--seed", "7")
    assert repeated.returncode == 3, repeated.stderr
    assert json.loads((group_files[0] / "two_key_b.json").read_text())["n_groups"] == 4
    assert certify_choice([], alpha=0.05, beta=0.05, seed=7).feasible is False


def test_certify_without_groups_still_writes_the_marginal_certificate_only(group_files):
    """The new surface must not leak into the shipped one: no group fields, same exit codes.

    Reddened by a plant that routes the pooled path through `certify_groups`, which would add
    `n_groups` to every certificate `verify` byte-compares.
    """
    _root, mixed, clear, _plain = group_files
    out = _root / "marginal.json"
    result = run("certify", str(clear), "--out", str(out), "--seed", "7")
    assert result.returncode == 0, (result.stdout, result.stderr)
    doc = json.loads(out.read_text())
    for leaked in ("n_groups", "per_group", "refused_by_size", "corrected_alpha", "pooled"):
        assert leaked not in doc, leaked
    assert doc["feasible"] is True and doc["envelope"], doc
    assert "reason" in doc and doc["reason"] is None, doc
    assert "marginal certificate only - not group-conditional" in " ".join(doc["envelope"]), doc
    assert "group-conditional (Mondrian)" not in result.stdout, result.stdout
    assert "\n  slice " not in result.stdout, "the pooled run must render no per-slice lines"
    assert "worst-of-" not in result.stdout, result.stdout


def test_a_multi_key_group_name_still_serialises_because_json_has_no_tuple_keys(tmp_path):
    """Every map the artefact keys by a group renders with string keys, or the CLI exits 1.

    Measured before the fix, through the real `certify --groups family,mode`: `json.dumps` raised
    `TypeError: keys must be str, int, float, bool or None, not tuple` and the process exited rc 1 --
    outside the documented 0/2/3/4 contract, on a flag this task just shipped. `by_group` names a
    one-key slice by its value and a multi-key slice by a TUPLE (test_groups.py pins that collapse),
    so any group-keyed map added to this payload later inherits the hazard. Asserted over the payload
    rather than over one field, because the defect is the key type, not the field.
    """
    from autorate.certify_choice import certify_groups

    rows = []
    for family in ("f0", "f1"):
        for mode in ("fast", "slow"):
            rows += [_group_record("%s.%s" % (family, mode), i, gold=i % 4, peaked=i % 4,
                                   u=(i % 97) / 100.0, slices={"family": family, "mode": mode})
                     for i in range(150)]
    cert = certify_groups(rows, groups=("family", "mode"), seed=7)
    assert cert.n_groups == 4
    doc = json.loads(cert.to_json())
    for field in ("per_group", "slice_cases"):
        assert all(isinstance(key, str) for key in doc[field]), (field, list(doc[field]))
    # The tuple names survive as VALUES, which is where a tuple is legal JSON -- checked as a set
    # because `by_group`'s first-appearance ORDER is test_groups.py's claim, not this row's.
    census_names = {tuple(row["group"]) for row in doc["slice_census"]}
    assert census_names == {("f0", "fast"), ("f0", "slow"), ("f1", "fast"), ("f1", "slow")}, doc
    # the same four slices, by the same four names, in the map that carries their certificates
    assert set(doc["per_group"]) == {str(name) for name in census_names}, list(doc["per_group"])
    written = tmp_path / "multi.json"
    result = run("certify", str(_write(tmp_path / "multi.jsonl", rows)), "--groups", "family,mode",
                 "--out", str(written), "--seed", "7")
    doc = json.loads(written.read_text())
    # rc 3, and the artefact says so too: four cells of 150 cases is 4 slices, so each is certified at
    # alpha/4 = 0.0125 and its own 75-score calibration half cannot set that quantile -- every cell
    # refuses with `vacuous_quantile`. That is spec 8.1's cost, measured, not a fixture mistake: a
    # finer declaration shrinks the evidence each cell certifies on.
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert doc["n_groups"] == 4 and doc["feasible"] is False
    assert doc["any_slice_refused"] is True and doc["refused_by_size"] == []
    assert [row["reason"] for row in doc["per_group"].values()] == ["vacuous_quantile"] * 4
    # The exit code is reconstructible from the file: no reader should have to re-run the tool to know
    # whether the permission exists.
    assert result.returncode == (0 if doc["feasible"] else 3)
    assert doc["feasible"] is (not doc["any_slice_refused"])


def test_a_records_row_that_is_not_an_object_is_a_usage_error_and_never_rc_1(tmp_path):
    """A `null` row exited rc 1 with a `TypeError`; rc 1 is a defect, not an exit code (R-115).

    Found by sweeping the new `--groups` surface with the shapes a truncated or hand-edited JSONL
    actually contains -- a blank final line is skipped, but `null`, a bare number, a string and a list
    are all valid JSON that is not a record. `_records_from` handed each straight to
    `Record.from_dict`, whose first act is a membership test on the row: a list happens to answer with
    `MissingRecordField` (the loader round, `746f10f`), and `None` answers
    `TypeError: argument of type 'NoneType' is not iterable` --
    a traceback outside the documented 0/2/3/4 contract, on the one input an operator can produce by
    pressing enter twice in the wrong place.
    """
    good = _write(tmp_path / "good.jsonl", _clean("f", 140))
    for index, (shape, needle) in enumerate((("null", "NoneType"), ("42", "int"),
                                             ('"a row"', "str"), ("[1, 2, 3]", "list"))):
        path = tmp_path / ("bad_row_%d.jsonl" % index)
        path.write_text(good.read_text() + shape + "\n")
        for extra in ([], ["--groups", "family"]):
            result = run("certify", str(path), "--out", str(tmp_path / "o.json"), *extra)
            assert result.returncode == 2, (shape, extra, result.returncode, result.stderr)
            assert "Traceback" not in result.stderr, (shape, extra, result.stderr)
            assert "TypeError" not in result.stderr, (shape, extra, result.stderr)
            assert "UsageError" in result.stderr, (shape, extra, result.stderr)
            assert needle in result.stderr, (shape, extra, result.stderr)
            assert "line 141" in result.stderr, (shape, result.stderr)
        # the same file with the offending line removed still certifies: this is a refusal about the
        # row, not a poisoning of the run
        clean = tmp_path / "clean_again.jsonl"
        clean.write_text(good.read_text())
        assert run("certify", str(clean), "--out", str(tmp_path / "c.json")).returncode == 0


# --- #62: one owner for the published rubric (amendments items 6 and 9) --------------------
#
# R-184 measured the consumers before writing these rows: `tests/test_correction.py` and
# `tests/test_mondrian.py` do `from autorate.report import ALPHA, BETA`, `tests/test_audit.py`
# imports `DEFAULT_DELTA` from `audit.py`, and three suites import `MIN_CAL`/`MIN_EVAL`/
# `DIAGNOSTIC_GRID` from the certifiers. The values are therefore NOT unconsumed, and a green suite
# proves nothing about ownership because every one of those imports reads whichever module the suite
# happened to name. What was missing is a row saying these ARE the published rubric, and a single
# owner for delta (three statements: `audit.py:95`, `cli.py`'s `--delta` default, `certify_choice`'s
# signature default), for the floors (three) and for the diagnostic grid (two).
#
# The guards below are AST guards, not value guards, on purpose. A value guard written as
# `report.ALPHA == 0.05` cannot tell an import from a re-declared literal, because at the published
# rubric both sides are the same number; that is R-54's green-on-arrival class ("alpha == beta ==
# 0.05 at the published rubric, so gating on the wrong symbol passes every test at the defaults").
# Only the binding form distinguishes "imports the owner" from "restates the owner's value", so
# these rows read the source and check how each name is bound.

RUBRIC_KEYS = ("alpha", "beta", "delta", "seed", "method", "unit", "n_claims", "min_cal",
               "min_eval", "grid")
# Names a consumer may only ever IMPORT. `DEFAULT_DELTA` is on the list because it is `audit.py`'s
# alias for the same number, and an alias re-declared as a literal is the same defect wearing a
# different name.
RUBRIC_NAMES = ("ALPHA", "BETA", "DELTA", "SEED", "METHOD", "UNIT", "N_CLAIMS", "MIN_CAL",
                "MIN_EVAL", "DIAGNOSTIC_GRID", "DEFAULT_DELTA", "PUBLISHED_RUBRIC")
SRC = REPO / "src" / "autorate"
# The modules this task's fence owns and can therefore fix. `certify_score.py` and
# `certify_threshold.py` are deliberately absent, and the whole reason is a fact about this file's
# own fence rather than about an untracked ledger: they are not in `task-6-controller-amendments.md`
# item 7's file list, so the owner could not converge the copies they still carry --
# `certify_score.py:69-70,75` (`MIN_CAL`/`MIN_EVAL`/`DIAGNOSTIC_GRID`), `certify_threshold.py:65-66`
# (`MIN_CAL`/`MIN_EVAL`), and the `alpha`/`beta`/`delta` signature defaults at `certify_score.py:191`
# and `certify_threshold.py:279`. Widening the fence to delete them was the wrong move, so each copy
# is pinned against the owner instead:
# `test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner`,
# `test_certify_scores_out_of_fence_signature_defaults_agree_with_the_owner` and
# `test_certify_thresholds_out_of_fence_signature_defaults_agree_with_the_owner`. Converging the
# copies -- together with `severity.py`'s defaults, which task #72 owns -- is a separate round with
# its own file list.
RUBRIC_CONSUMERS = ("report.py", "cli.py", "audit.py", "certify_choice.py")


def _module_bindings(path):
    """Names bound at module level, split into imports and assignments, from the parsed source."""
    tree = __import__("ast").parse(path.read_text(encoding="utf-8"))
    imported, assigned = set(), {}
    for node in tree.body:
        if isinstance(node, (__import__("ast").Import, __import__("ast").ImportFrom)):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, __import__("ast").Assign):
            for target in node.targets:
                if isinstance(target, __import__("ast").Name):
                    assigned.setdefault(target.id, node)
        elif isinstance(node, __import__("ast").AnnAssign) and isinstance(node.target,
                                                                          __import__("ast").Name):
            assigned.setdefault(node.target.id, node)
    return imported, assigned


def _default_nodes(path, flags):
    """Every `(flag, lineno, default-node)` pair an `add_argument` call passes, as written."""
    tree = __import__("ast").parse(path.read_text(encoding="utf-8"))
    out = []
    for node in __import__("ast").walk(tree):
        if not (isinstance(node, __import__("ast").Call) and isinstance(node.func,
                                                                        __import__("ast").Attribute)
                and node.func.attr == "add_argument"):
            continue
        if not node.args or not isinstance(node.args[0], __import__("ast").Constant):
            continue
        flag = node.args[0].value
        if flag not in flags:
            continue
        for kw in node.keywords:
            if kw.arg == "default":
                out.append((flag, node.lineno, kw.value))
    return out


def test_the_published_rubric_is_one_mapping_that_names_every_number_it_publishes():
    """The mapping is the owner, and it holds exactly the ten names #62 and R-187 listed.

    The values are transcribed from `c8ec8f8` as measured BEFORE the move (`pre-delete-equality.txt`
    in the evidence directory): alpha/beta/seed from `report.py:23-25`, delta from `audit.py:95` and
    `cli.py:631` and `certify_choice`'s signature, n_claims from `certificate.py:19`, the floors from
    `certify_choice.py:43-44` / `certify_score.py:69-70` / `certify_threshold.py:65-66`, the grid from
    the two textually identical `DIAGNOSTIC_GRID` expressions. They are literals here on purpose: a
    pin that read them back out of the owner would certify only that the owner equals itself, and the
    one claim this row exists to keep is that MOVING the declaration moved no value.
    """
    from autorate.certificate import PUBLISHED_RUBRIC

    assert set(PUBLISHED_RUBRIC) == set(RUBRIC_KEYS), sorted(PUBLISHED_RUBRIC)
    assert PUBLISHED_RUBRIC["alpha"] == 0.05
    assert PUBLISHED_RUBRIC["beta"] == 0.05
    assert PUBLISHED_RUBRIC["delta"] == 0.05
    assert PUBLISHED_RUBRIC["seed"] == 7
    assert PUBLISHED_RUBRIC["method"] == "aps"
    assert PUBLISHED_RUBRIC["unit"] == "case", "the case, never the row (R-36/R-44)"
    assert PUBLISHED_RUBRIC["n_claims"] == 3
    assert PUBLISHED_RUBRIC["min_cal"] == 60
    assert PUBLISHED_RUBRIC["min_eval"] == 60
    assert PUBLISHED_RUBRIC["grid"] == tuple(round(0.01 * i, 2) for i in range(1, 30))

    from autorate import certificate
    for key, name in (("n_claims", "N_CLAIMS"), ("min_cal", "MIN_CAL"), ("min_eval", "MIN_EVAL"),
                      ("grid", "DIAGNOSTIC_GRID"), ("alpha", "ALPHA"), ("beta", "BETA"),
                      ("delta", "DELTA"), ("seed", "SEED"), ("method", "METHOD"),
                      ("unit", "UNIT")):
        assert getattr(certificate, name) == PUBLISHED_RUBRIC[key], name


def test_the_owner_mapping_holds_one_literal_and_every_derived_name_reads_from_it():
    """`certificate.py` may declare the values, but only inside the mapping.

    The derived names are convenience bindings for consumers; if one of them carried its own literal
    the module would have two owners of the same number and the mapping would be decoration.
    """
    ast = __import__("ast")
    from autorate.certificate import PUBLISHED_RUBRIC

    _imported, assigned = _module_bindings(SRC / "certificate.py")
    assert "PUBLISHED_RUBRIC" in assigned, "the owner is not declared in the owner's module"
    derived = {n: node for n, node in assigned.items()
               if n in RUBRIC_NAMES and n != "PUBLISHED_RUBRIC"}
    for name, node in derived.items():
        assert isinstance(node.value, ast.Subscript), (
            "%s re-declares a rubric value instead of reading PUBLISHED_RUBRIC" % name)
        base = node.value.value
        assert isinstance(base, ast.Name) and base.id == "PUBLISHED_RUBRIC", ast.dump(node)
        assert isinstance(node.value.slice, ast.Constant), ast.dump(node)
        assert node.value.slice.value in RUBRIC_KEYS, node.value.slice.value
    for key in RUBRIC_KEYS:
        assert PUBLISHED_RUBRIC[key] is not None, key


def test_no_module_inside_the_fence_redeclares_a_rubric_name_it_could_import():
    """Every consumer binds rubric names by IMPORT; a re-declared literal is the defect.

    This is the row R-184 says does not exist today. Before the move it is red for four modules at
    once -- `report.py` declares ALPHA/BETA/SEED, `audit.py` declares DEFAULT_DELTA,
    `certify_choice.py` declares MIN_CAL/MIN_EVAL/DIAGNOSTIC_GRID -- and it stays red if any of them
    restates a value later, which is exactly the drift an `==` pin cannot see while both sides agree.
    """
    offenders = {}
    for module in RUBRIC_CONSUMERS:
        _imported, assigned = _module_bindings(SRC / module)
        restated = sorted(n for n in assigned if n in RUBRIC_NAMES)
        if restated:
            offenders[module] = [
                "%s:%d" % (n, assigned[n].lineno) for n in restated]
    assert offenders == {}, "rubric names re-declared instead of imported: %s" % offenders


def test_every_cli_rubric_flag_defaults_to_the_owner_name_and_not_a_literal():
    """`--alpha/--beta/--delta/--seed/--method` default to imported names, never typed numbers.

    Red on arrival at `c8ec8f8` for the two flags that were literals (`--delta default=0.05`,
    `--method default="aps"`), and green once they read the owner. The value half of the claim is
    checked through the real parser, because a flag renamed but left at the wrong number would pass
    the AST half alone.
    """
    ast = __import__("ast")
    from autorate.certificate import PUBLISHED_RUBRIC
    from autorate.cli import build_parser

    expected = {"--alpha": "ALPHA", "--beta": "BETA", "--delta": ("DELTA", "DEFAULT_DELTA"),
                "--seed": "SEED", "--method": "METHOD"}
    seen = set()
    for module in RUBRIC_CONSUMERS:
        for flag, lineno, node in _default_nodes(SRC / module, set(expected)):
            assert isinstance(node, ast.Name), "%s:%d %s still defaults to a literal" % (
                module, lineno, flag)
            want = expected[flag]
            want = (want,) if isinstance(want, str) else want
            assert node.id in want, "%s:%d %s reads %s, not %s" % (module, lineno, flag,
                                                                   node.id, want)
            seen.add(flag)
    assert seen == set(expected), "a rubric flag stopped being registered: %s" % (
        sorted(set(expected) - seen))

    ns = build_parser().parse_args(["certify", "records.jsonl"])
    assert (ns.alpha, ns.beta, ns.delta, ns.seed, ns.method) == (
        PUBLISHED_RUBRIC["alpha"], PUBLISHED_RUBRIC["beta"], PUBLISHED_RUBRIC["delta"],
        PUBLISHED_RUBRIC["seed"], PUBLISHED_RUBRIC["method"]), vars(ns)
    audit_ns = build_parser().parse_args(["audit"])
    assert audit_ns.delta == PUBLISHED_RUBRIC["delta"], vars(audit_ns)


def test_the_certificates_rubric_fields_are_a_subset_of_the_owner():
    """`cli.RUBRIC_FIELDS` names what a certificate stamps; every one is owned by the mapping.

    The list itself stays in `cli.py` -- it is the comparison surface of `compare`, not a value --
    but a field added there without a rubric owner is the second half of the same defect, so the
    subset relation is pinned.
    """
    from autorate.certificate import PUBLISHED_RUBRIC
    from autorate.cli import RUBRIC_FIELDS

    assert set(RUBRIC_FIELDS) <= set(PUBLISHED_RUBRIC), (
        sorted(set(RUBRIC_FIELDS) - set(PUBLISHED_RUBRIC)))


def test_the_published_rubric_cannot_be_edited_through_the_mapping_by_a_consumer():
    """A consumer that wrote `PUBLISHED_RUBRIC["alpha"] = ...` would move every published number
    in the same process, silently and without a file change. The mapping is therefore a read-only
    view, and this row is the guard that says so.
    """
    from autorate.certificate import PUBLISHED_RUBRIC

    with pytest.raises(TypeError):
        PUBLISHED_RUBRIC["alpha"] = 0.10
    assert PUBLISHED_RUBRIC["alpha"] == 0.05, "the mapping was mutated by the row meant to refuse it"


def test_audit_default_grid_stays_the_frontier_and_is_never_the_diagnostic_grid():
    """`audit.DEFAULT_GRID` is the audit's risk-coverage frontier: a DIFFERENT object (R-187).

    The rubric's `grid` is the 29-point diagnostic sweep the certifiers walk. Substituting one for
    the other keeps both names looking right and changes which curve a certificate publishes, so the
    separation is asserted as a fact about the objects and as a fact about the certifier's behaviour.
    """
    from autorate.audit import DEFAULT_GRID
    from autorate.certificate import PUBLISHED_RUBRIC
    from autorate.certify_choice import certify_choice

    assert DEFAULT_GRID == (0.0, 0.3, 0.6, 0.85, 0.99), DEFAULT_GRID
    assert PUBLISHED_RUBRIC["grid"] != DEFAULT_GRID, "the frontier was substituted for the sweep"
    assert len(PUBLISHED_RUBRIC["grid"]) == 29
    # the behaviour, not only the constant: an empty population still walks the sweep it was given
    refusal = certify_choice([])
    assert refusal.meta["diagnostic_grid_size"] == len(PUBLISHED_RUBRIC["grid"]), refusal.meta
    assert refusal.meta["diagnostic_grid_size"] != len(DEFAULT_GRID)


# --- one comparison surface, shared by each out-of-fence pin and by its own negative control --
#
# `certify_score.py` and `certify_threshold.py` sit outside this task's fence, so the rubric values
# they re-declare -- the floors, the diagnostic grid, and the levels their signatures default to --
# cannot be deleted here. They are policed instead, and the policing goes through ONE function per
# copy family: the pin row calls it on the live modules, and the control row calls the same function
# on the same live modules with one copy patched in memory. That sharing is the point. The control
# this round replaced asserted facts about its own monkeypatch and never called what the pin
# compared, so a file plant (`MIN_CAL = 61` at `certify_score.py:69`) reddened the pin while the
# control stayed green at rc 0 -- a control that cannot see the pin failing is decoration.
RUBRIC_COPY_CHECKS = (
    # Each entry is `(module, name it declares at module level, key of PUBLISHED_RUBRIC it must equal)`
    ("autorate.certify_score", "MIN_CAL", "min_cal"),
    ("autorate.certify_score", "MIN_EVAL", "min_eval"),
    ("autorate.certify_score", "DIAGNOSTIC_GRID", "grid"),
    ("autorate.certify_threshold", "MIN_CAL", "min_cal"),
    ("autorate.certify_threshold", "MIN_EVAL", "min_eval"),
)
# A rubric-NAMED copy the table above deliberately does not compare, with the reason. `METHOD` is each
# gate's own rule name (`ordinal` at `certify_score.py:71`, `threshold` at `certify_threshold.py:67`)
# while `PUBLISHED_RUBRIC["method"]` is the nonconformity the published certificates were measured
# with (`aps`): two different facts wearing one word, so pinning them equal would be the error. The
# coverage assertion in the pin row makes this list load-bearing: a fourth shared name appearing in
# either file reddens it until it is pinned in the table or disclosed here.
RUBRIC_COPIES_DISCLOSED_NOT_PINNED = frozenset({
    ("autorate.certify_score", "METHOD"),
    ("autorate.certify_threshold", "METHOD"),
})
RUBRIC_SIGNATURE_DEFAULTS = (
    # Each entry is `(parameter a certifier's signature defaults to, PUBLISHED_RUBRIC key it equals)`
    ("alpha", "alpha"),
    ("beta", "beta"),
    ("delta", "delta"),
)


def _rubric_copy_modules():
    """The two out-of-fence modules, looked up live so a control's patch is visible to the pin."""
    from importlib import import_module

    return {name: import_module(name) for name in
            sorted({module for module, _attribute, _key in RUBRIC_COPY_CHECKS})}


def _assert_rubric_copies_agree(modules, published):
    """The module-level copies against the owner: the first divergence raises and names its copy."""
    for module_name, attribute, key in RUBRIC_COPY_CHECKS:
        declared = getattr(modules[module_name], attribute)
        if declared != published[key]:
            raise AssertionError(
                "%s.%s is %r while PUBLISHED_RUBRIC[%r] is %r: the copy diverged from its owner"
                % (module_name, attribute, declared, key, published[key]))


def _assert_signature_defaults_agree(module_name, fn, published):
    """A certifier's signature defaults against the owner: the first divergence names its parameter."""
    defaults = _certifier_signature_defaults(fn)
    for parameter, key in RUBRIC_SIGNATURE_DEFAULTS:
        if defaults[parameter] != published[key]:
            raise AssertionError(
                "%s's %s default is %r while PUBLISHED_RUBRIC[%r] is %r: a published level was "
                "restated in a signature" % (module_name, parameter, defaults[parameter], key,
                                             published[key]))


def _certifier_signature_defaults(fn):
    """The rubric-owned defaults as the LIVE signature binds them, keyed by parameter name.

    Read through `inspect.signature` rather than out of the source text, because the claim being
    policed is what a caller who omits the argument gets, and that is a fact about the object.
    """
    inspect = __import__("inspect")
    parameters = inspect.signature(fn).parameters
    defaults = {}
    for parameter, _key in RUBRIC_SIGNATURE_DEFAULTS:
        assert parameter in parameters, "%s declares no %s parameter any more" % (
            fn.__qualname__, parameter)
        default = parameters[parameter].default
        assert default is not inspect.Parameter.empty, (
            "%s's %s parameter stopped carrying a default, so the pin has no copy to compare" % (
                fn.__qualname__, parameter))
        defaults[parameter] = default
    return defaults


def _a_diverged_copy(current, published):
    """A value guaranteed to differ from BOTH what the module declares now and what the owner says.

    Derived from those two values instead of typed, because a typed value (the `owner + 1` the old
    control used) silently becomes a no-op the moment the file itself is planted with it -- exactly
    the ineffectual patch this control is supposed to catch.
    """
    if isinstance(current, tuple):
        assert current, "an empty copy has no derived divergence; extend this helper deliberately"
        candidate = current + (current[-1],)
    else:
        candidate = current + 1
        if candidate == published:
            candidate = current + 2
    assert candidate != current and candidate != published, (candidate, current, published)
    return candidate


def _drive_signature_default_control(monkeypatch, module_name, function_name):
    """Patch one signature default of a live certifier at a time and run THAT pin's comparison.

    The divergence cannot be planted in the file from inside this fence, so it is planted on the
    function object: `inspect.signature` reads `__defaults__`, so replacing that tuple is the same
    state a file edit produces and restoring it is the same revert. `monkeypatch` owns the revert,
    and the row asserts the patch landed and reverted rather than trusting either.
    """
    from importlib import import_module

    from autorate.certificate import PUBLISHED_RUBRIC

    fn = getattr(import_module(module_name), function_name)
    defaulted = [p.name for p in __import__("inspect").signature(fn).parameters.values()
                 if p.default is not __import__("inspect").Parameter.empty]
    for parameter, key in RUBRIC_SIGNATURE_DEFAULTS:
        assert parameter in defaulted, "%s's %s has no default to diverge" % (
            function_name, parameter)
    before = getattr(fn, "__defaults__")
    assert before is not None and len(before) == len(defaulted), (before, defaulted)
    for parameter, key in RUBRIC_SIGNATURE_DEFAULTS:
        index = defaulted.index(parameter)
        diverged = list(before)
        diverged[index] = _a_diverged_copy(before[index], PUBLISHED_RUBRIC[key])
        monkeypatch.setattr(fn, "__defaults__", tuple(diverged))
        after = getattr(fn, "__defaults__")
        assert after != before, (
            "the patch did not land on %s's defaults, which are still %r" % (
                function_name, before))
        assert after[index] != PUBLISHED_RUBRIC[key], (
            "the patch left %s's %s equal to the owner (%r), so nothing diverged" % (
                function_name, parameter, after[index]))
        with pytest.raises(AssertionError) as caught:
            _assert_signature_defaults_agree(module_name, fn, PUBLISHED_RUBRIC)
        message = str(caught.value)
        assert "%s default is %r" % (parameter, after[index]) in message, message
        assert module_name in message, message
        for other, _key in RUBRIC_SIGNATURE_DEFAULTS:
            if other != parameter:
                assert "%s default is" % other not in message, message
        monkeypatch.undo()
        assert getattr(fn, "__defaults__") == before, (
            "the patch of %s's defaults was not reverted, so it would leak into the pin above" % (
                function_name,))


def test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner():
    """The duplication #62 cannot finish inside its fence, recorded as a pin rather than as a claim.

    `certify_score.py:69-70,75` and `certify_threshold.py:65-66` are outside
    `task-6-controller-amendments.md` item 7's file list, so item 9's owner covers the names and this
    row polices the copies instead of deleting them. It is TRUE on arrival by construction -- the
    copies agree with the owner at `c8ec8f8`, which is the pre-deletion equality measurement the
    dispatch requires -- and it is the guard that turns a silent divergence into a red. That red is
    produced by `_assert_rubric_copies_agree`, the one comparison this row and its negative control
    share; the control is an in-memory patch rather than a file plant because planting there would
    write to the two files the fence exists to protect.
    """
    from autorate.certificate import PUBLISHED_RUBRIC

    _assert_rubric_copies_agree(_rubric_copy_modules(), PUBLISHED_RUBRIC)

    # The comparison above is worth nothing once its table stops covering the copies the two modules
    # declare, so the table is checked against the parsed source rather than against a count typed
    # here: a copy removed from the table has to be disclosed below or this row goes red.
    declared = set()
    for module_name in sorted({m for m, _a, _k in RUBRIC_COPY_CHECKS}):
        _imported, assigned = _module_bindings(SRC / (module_name.rsplit(".", 1)[-1] + ".py"))
        declared.update((module_name, name) for name in assigned if name in RUBRIC_NAMES)
    pinned = {(module_name, attribute) for module_name, attribute, _key in RUBRIC_COPY_CHECKS}
    assert declared == pinned | RUBRIC_COPIES_DISCLOSED_NOT_PINNED, (
        "copies unpinned by the table: %s; table entries no longer declared: %s" % (
            sorted(declared - pinned - RUBRIC_COPIES_DISCLOSED_NOT_PINNED),
            sorted(pinned - declared)))


def test_the_out_of_fence_pin_fires_when_a_copy_diverges(monkeypatch):
    """Negative control for the row above: it drives THAT row's comparison against a diverged copy.

    The first version of this row patched a module attribute and then asserted facts about its own
    patch, never calling anything the pin compared. Measured on `plan/b1-task6-fix1` before the
    rewrite: `MIN_CAL = 61` planted at `certify_score.py:69` reddened the pin and left this row
    passing at rc 0, which is the decoration R-149's class describes.
    """
    from autorate.certificate import PUBLISHED_RUBRIC

    assert RUBRIC_COPY_CHECKS, "the pin's comparison table is empty, so nothing below can fail"
    for module_name, attribute, key in RUBRIC_COPY_CHECKS:
        modules = _rubric_copy_modules()
        before = getattr(modules[module_name], attribute)
        monkeypatch.setattr(modules[module_name], attribute,
                            _a_diverged_copy(before, PUBLISHED_RUBRIC[key]))
        after = getattr(modules[module_name], attribute)
        assert after != before, (
            "the patch did not land on %s.%s, which is still %r" % (
                module_name, attribute, before))
        assert after != PUBLISHED_RUBRIC[key], (
            "the patch left %s.%s equal to the owner (%r), so no copy actually diverged" % (
                module_name, attribute, after))
        with pytest.raises(AssertionError) as caught:
            _assert_rubric_copies_agree(modules, PUBLISHED_RUBRIC)
        message = str(caught.value)
        assert "%s.%s is %r" % (module_name, attribute, after) in message, message
        for other_module, other_attribute, _key in RUBRIC_COPY_CHECKS:
            if (other_module, other_attribute) != (module_name, attribute):
                assert "%s.%s is" % (other_module, other_attribute) not in message, message
        monkeypatch.undo()
        assert getattr(modules[module_name], attribute) == before, (
            "the patch of %s.%s was not reverted, so it would leak into the pin above" % (
                module_name, attribute))


def test_certify_scores_out_of_fence_signature_defaults_agree_with_the_owner():
    """`certify_score.py:191` still writes `alpha/beta/delta = 0.05`; pinned to the owner, not deleted.

    The signature defaults are a third copy of the published levels, in a file this fence cannot
    change, so they are policed the same way as the module-level floors above: green on arrival
    because the restated numbers do agree, red the moment one of them stops agreeing. `seed` is not
    in the table -- the certifiers' own split default is `certificate.SPLIT_SEED_DEFAULT` (0) while
    the published seed is 7, and collapsing them re-rolls the partition.
    """
    from autorate.certificate import PUBLISHED_RUBRIC
    from autorate.certify_score import certify_score

    _assert_signature_defaults_agree("autorate.certify_score", certify_score, PUBLISHED_RUBRIC)


def test_certify_thresholds_out_of_fence_signature_defaults_agree_with_the_owner():
    """`certify_threshold.py:279` restates the same three levels, and is pinned identically.

    Separate from the row above on purpose: one row per file is what lets a divergence name which
    certifier moved.
    """
    from autorate.certificate import PUBLISHED_RUBRIC
    from autorate.certify_threshold import certify_threshold

    _assert_signature_defaults_agree("autorate.certify_threshold", certify_threshold,
                                     PUBLISHED_RUBRIC)


def test_certify_scores_signature_default_pin_fires_when_a_default_diverges(monkeypatch):
    """Negative control for `certify_score`'s signature pin, driving that pin's own comparison."""
    _drive_signature_default_control(monkeypatch, "autorate.certify_score", "certify_score")


def test_certify_thresholds_signature_default_pin_fires_when_a_default_diverges(monkeypatch):
    """Negative control for `certify_threshold`'s signature pin, driving that pin's own comparison."""
    _drive_signature_default_control(monkeypatch, "autorate.certify_threshold", "certify_threshold")
