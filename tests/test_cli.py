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

    expected = 2 * (len(CERT_COMPARE_FIELDS) + 1) + 1
    assert total == expected, (total, expected, p.stdout)


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


def test_verify_without_a_corpus_or_a_snapshot_is_a_usage_error(tmp_path):
    work = tmp_path / "no_data"
    (work / "data").mkdir(parents=True)
    shutil.copytree(REPO / "docs", work / "docs")
    shutil.copy(REPO / "data" / "records_feishu.jsonl", work / "data")
    shutil.copy(REPO / "data" / "cert_laya.json", work / "data")
    shutil.copy(REPO / "data" / "cert_jev.json", work / "data")
    r = run("verify", cwd=work, root=Path("/nonexistent-corpus-dir"))
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "nothing to verify against" in r.stderr, r.stderr


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
    stripped = Certificate(**{**live.to_dict(), "backend": None})
    d = Gate(stripped).decide(recs[0])
    assert d["action"] == "abstain" and d["reason"] == "subject_mismatch", d


def test_a_missing_input_is_a_usage_error_not_a_traceback(tmp_path):
    """I-1: rc 1 was reachable outside the documented 0/2/3/4 contract."""
    p = run("certify", str(tmp_path / "nope.jsonl"), "--out", str(tmp_path / "c.json"))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert p.stderr.strip(), "a usage error that prints nothing is not diagnosable"


def test_a_stored_certificate_that_violates_its_shape_is_a_usage_error(tmp_path):
    # The brief's own Step-2 tamper: feasible with an empty envelope. Certificate raises
    # ValueError, which used to escape as rc 1 with a traceback and no DRIFT row.
    for d in ("data", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
    cert = tmp_path / "data" / "cert_jev.json"
    doc = json.loads(cert.read_text())
    doc["envelope"] = []
    cert.write_text(json.dumps(doc, sort_keys=True))
    assert doc["envelope"] == [], "tampering did not land"
    p = run("verify", cwd=tmp_path)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "envelope" in p.stderr, p.stderr


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


def test_no_committed_file_carries_an_absolute_home_path():
    """I-7: an absolute literal passes every local gate, and only CI can see it break.

    Checked as structure over the tracked tree -- not by reading files I happen to think
    are the risky ones -- because the class of defect is the path itself.
    """
    import subprocess

    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             cwd=str(REPO)).stdout.split()
    assert tracked, "git ls-files returned nothing; the guard would pass vacuously"
    # A username-shaped segment, not the bare directory prefix: `<workspace>` prose and
    # this file's own patterns say "/Users/" without naming a machine.
    rx = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")
    home = str(Path.home())
    offenders = []
    for rel in tracked:
        f = REPO / rel
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if home in line:
                offenders.append((rel, i, "this machine's home directory"))
            elif rx.search(line):
                offenders.append((rel, i, rx.search(line).group(0)))
    assert not offenders, offenders
    # Built from pieces so this file does not become the offender it is looking for.
    assert home.startswith("/") and rx.search("/" + "Users/bob/x"), "the guard is vacuous"


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
