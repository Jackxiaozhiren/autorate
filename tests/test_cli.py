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
    from autorate.report import CERTS, MASSIVE_CERTIFICATES, RECORDS

    names = ({RECORDS} | set(CERTS.values())
             | {p for pair in MASSIVE_CERTIFICATES.values() for p in pair})
    for rel in sorted(names):
        shutil.copy(REPO / rel, work / rel)


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
    from autorate.cli import CERT_COMPARE_FIELDS

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
    expected = ((len(CERTS) + len(MASSIVE_CERTIFICATES)) * (len(CERT_COMPARE_FIELDS) + 1)
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
        for d in ("data", "docs"):
            shutil.copytree(REPO / d, work / d)
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
    wording: bytes that parse-failed were opened, so "cannot be opened" would be false, and nothing
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
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
