"""F8: the action that shells out, the four-state badge, and the checkout contract it asserts.

The rules these rows police are PRD §5 F8's, and the reason they are tests rather than prose is §6.2:
a guard that cannot fail is decoration. Every predicate here is therefore applied twice -- once to the
committed subject, which must pass, and once to a subject it must refuse. The second application is the
negative control; without it a regex that stopped matching would report a clean tree forever.
"""
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from autorate.protocol import load_protocol, protocol_digest
from tools import action_report as ar

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
SCRIPT = ROOT / "tools" / "action_report.py"
WORKFLOWS = ROOT / ".github" / "workflows"
BADGE_JSON = ROOT / ".github" / "badges" / "autorate-badge.json"
BADGE_SVG = ROOT / ".github" / "badges" / "autorate-badge.svg"

GREEN = "claim G5 certified ...\ndisclosure: corpus present: all re-derived\nre-derived 649 /649 values\n"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


# --- the vocabulary -------------------------------------------------------------------------------

def test_the_state_vocabulary_is_the_four_honest_states():
    """A fifth state, or a boolean, is the defect this row exists for (F8 rule 3)."""
    assert ar.STATES == ("certified", "not-certifiable", "drift", "not-run")
    for not_a_state in (True, False, "true", "green", "pass", "ok", ""):
        with pytest.raises(ValueError):
            ar.combine(not_a_state, None)
        with pytest.raises(ValueError):
            ar.badge_svg(not_a_state, "x", "")


def test_the_exit_code_contract_belongs_to_the_lane_that_printed_it():
    assert ar.classify("verify", 0) == "certified"
    assert ar.classify("verify", 4) == "drift"
    # `verify` never refuses; exit 3 belongs to `certify`/`gate`, so it cannot mint a refusal badge here.
    assert ar.classify("verify", 3) == "not-run"
    assert ar.classify("certify", 0) == "certified"
    assert ar.classify("certify", 3) == "not-certifiable"
    # exit 2 is a usage error: a configuration bug, not a red KPI (F6 rule 2).
    assert ar.classify("verify", 2) == "not-run"
    assert ar.classify("certify", 1) == "not-run"
    with pytest.raises(ValueError):
        ar.classify("gate", 0)


def test_a_green_exit_without_its_denominator_line_is_not_a_verdict():
    """I2 in one line: a badge may not certify a number the tool did not print with a denominator."""
    assert ar.read_denominator(GREEN) == (649, 649)
    assert ar.verdict_from(0, GREEN)[0] == "certified"
    # negative controls: the same exit code with no line, and with an impossible pair.
    assert ar.verdict_from(0, "claim G5 certified\n")[0] == "not-run"
    assert ar.read_denominator("re-derived 650 /649 values") is None
    assert ar.verdict_from(0, "re-derived 650 /649 values")[0] == "not-run"


def test_a_refusal_outranks_a_green_gate_and_a_missing_lane_does_not():
    assert ar.verdict_from(0, GREEN, 3, "NOT_CERTIFIABLE: reason=empty_feasible_set")[0] == "not-certifiable"
    assert ar.verdict_from(0, GREEN, 3, "NOT_CERTIFIABLE: reason=empty_feasible_set")[1] == \
        "NOT_CERTIFIABLE: reason=empty_feasible_set"
    # a certification that could not run is `not-run`, never the green the gate alone would have given
    assert ar.verdict_from(0, GREEN, 2, "usage: ...")[0] == "not-run"
    # and a drifting gate is not upgraded by a certification that happened to pass
    assert ar.verdict_from(4, "DRIFT: cert laya.autorate", 0, "")[0] == "drift"


def test_fail_on_defaults_to_drift_and_not_run_but_reports_a_refusal():
    default = {"drift", "not-run"}
    assert ar.exit_for("drift", default) == 1
    assert ar.exit_for("not-run", default) == 1
    assert ar.exit_for("not-certifiable", default) == 0      # a result, not a broken pipeline
    assert ar.exit_for("certified", default) == 0
    assert ar.exit_for("not-certifiable", {"not-certifiable"}) == 1


# --- the badge ------------------------------------------------------------------------------------

def test_the_badge_carries_its_word_and_its_denominator_and_not_run_is_not_green():
    cert = ar.badge_svg("certified", "certified 649/649", "protocol ce43f8e29cc1")
    notrun = ar.badge_svg("not-run", "not-run", "uv missing")
    assert "certified" in cert and "649/649" in cert
    assert "not-run" in notrun
    assert "certified" not in notrun, "a not-run badge may not carry the certified word"
    assert ar.FILL["not-run"] != ar.FILL["certified"]
    assert len(set(ar.FILL.values())) == len(ar.STATES), "two states share a colour"
    assert notrun.count(ar.FILL["not-run"]) == 1, "not-run carries its own grey exactly once"
    assert ar.FILL["certified"] not in notrun, "a not-run badge may not carry the certified colour"


def _badge_problems(payload, digest12, svg):
    """What a reader must be able to check about a committed badge, as a list of problems."""
    out = []
    state = payload.get("state")
    if state not in ar.STATES:
        out.append("state %r is not in the vocabulary" % (state,))
    den = payload.get("denominator")
    if not (isinstance(den, list) and len(den) == 2 and all(isinstance(x, int) for x in den)):
        out.append("denominator %r is not a pair of integers" % (den,))
    elif den[0] > den[1]:
        out.append("denominator %r claims more re-derived values than it checked" % (den,))
    elif state == "certified" and den[0] != den[1]:
        out.append("a certified badge must show N/N, got %r" % (den,))
    proto = payload.get("protocol") or {}
    if proto.get("digest") != digest12:
        out.append("badge minted under %r, the tree's freeze is %r" % (proto.get("digest"), digest12))
    lane = payload.get("lane")
    if lane not in ("corpus present", "corpus absent"):
        out.append("lane %r is not a label the tool prints" % (lane,))
    line = payload.get("denominator_line") or ""
    m = re.search(r"re-derived (\d+) /(\d+) values", line)
    if not m:
        out.append("the record carries no verbatim denominator line")
    elif isinstance(den, list) and len(den) == 2 and [int(m.group(1)), int(m.group(2))] != den:
        out.append("denominator_line %r disagrees with denominator %r" % (line, den))
    if state and state not in svg:
        out.append("the svg does not carry its state word")
    if isinstance(den, list) and len(den) == 2 and ("%d/%d" % (den[0], den[1])) not in svg:
        out.append("the svg does not carry its denominator")
    return out


def test_the_committed_badge_names_the_digest_it_was_minted_under():
    """A green pill must not outlive the freeze it describes; a re-freeze reddens this row."""
    digest12 = protocol_digest(load_protocol(ROOT / "protocol.json"))[:12]
    payload = json.loads(BADGE_JSON.read_text())
    svg = BADGE_SVG.read_text()
    assert not _badge_problems(payload, digest12, svg)
    # negative controls: a superseded digest, an svg that lost its denominator, and a record whose
    # verbatim line was edited away from the pair it claims.
    stale = json.loads(json.dumps(payload))
    stale["protocol"]["digest"] = "0" * 12
    assert any("freeze" in p for p in _badge_problems(stale, digest12, svg))
    assert any("denominator" in p for p in _badge_problems(payload, digest12, "autorate certified"))
    edited = json.loads(json.dumps(payload))
    edited["denominator_line"] = "re-derived 1 /1 values"
    assert any("disagrees" in p for p in _badge_problems(edited, digest12, svg))
    unlabelled = json.loads(json.dumps(payload))
    unlabelled["lane"] = "green"
    assert any("lane" in p for p in _badge_problems(unlabelled, digest12, svg))


# --- the action and its checkout contract ---------------------------------------------------------

INPUTS = ("version", "ref", "alpha", "beta", "path", "records", "fail_on", "badge_dir", "comment")


def _declared_inputs(text):
    return set(re.findall(r"^ {2}([a-z_-]+):$", text, re.MULTILINE))


def test_the_action_is_a_composite_that_runs_the_shipped_shell():
    text = ACTION.read_text()
    assert "using: composite" in text, "a JavaScript or Docker action would move the logic out of this repo"
    assert "docker://" not in text
    assert "tools/action_report.py" in text, "the action no longer runs the shipped shell"
    assert "default: drift,not-run" in text, "the documented default is what makes exit 3 a result"
    missing = set(INPUTS) - _declared_inputs(text)
    assert not missing, "inputs F8 names but the action does not declare: %s" % sorted(missing)
    # negative control: the same predicate must refuse an action.yml missing one input.
    synthetic = re.sub(r"^ {2}fail_on:$", "  failon:", text, flags=re.MULTILINE)
    assert "fail_on" in set(INPUTS) - _declared_inputs(synthetic)


def test_the_action_step_returns_the_shipped_scripts_exit_code():
    """A `cat` appended after the script would make every `drift` exit 0; tap the code first."""
    run_block = ACTION.read_text().split("runs:", 1)[1]
    assert "rc=$?" in run_block, "the step does not capture the script's exit code"
    assert 'exit "$rc"' in run_block, "the step does not return the captured code"
    # Negative control, executed rather than asserted: without the tap, the trailing command wins.
    swallowed = subprocess.run(["bash", "-c", "false; true; echo -n"], capture_output=True, text=True)
    tapped = subprocess.run(["bash", "-c", "false; rc=$?; true; exit $rc"], capture_output=True, text=True)
    assert swallowed.returncode == 0, "the mechanism this guards against did not reproduce"
    assert tapped.returncode == 1, "the tap does not preserve the failing code"


def _artifact_problems(text):
    """The upload step must be able to carry the badge out of a hidden directory, and say so if it
    cannot. Both halves were measured missing on run 42167495868: the gate was green, the artifact
    absent, and the only trace was a `##[warning]` line nobody reads."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if "actions/upload-artifact@" not in line:
            continue
        block = "\n".join(lines[i:i + 12])
        if ".autorate/" not in block and "badge" not in block:
            continue
        if "include-hidden-files: true" not in block:
            out.append("the badge directory is hidden and the step does not include hidden files")
        if "if-no-files-found: error" not in block:
            out.append("a missing badge is only a warning")
    return out


def test_the_badge_artifact_is_actually_uploaded():
    workflow = (WORKFLOWS / "action-gate.yml").read_text()
    assert _artifact_problems(workflow) == [], _artifact_problems(workflow)
    # negative control: the committed shape minus each flag must be named.
    hidden_dropped = workflow.replace("include-hidden-files: true\n", "")
    assert any("hidden" in p for p in _artifact_problems(hidden_dropped))
    warn_restored = workflow.replace("if-no-files-found: error", "if-no-files-found: warn")
    assert any("warning" in p for p in _artifact_problems(warn_restored))


def _shallow_checkouts(text):
    """Checkout steps whose next eight lines never say `fetch-depth: 0` (F8 exception (a))."""
    lines = text.splitlines()
    found = [i for i, line in enumerate(lines) if "actions/checkout@" in line]
    return [lines[i].strip() for i in found if "fetch-depth: 0" not in "\n".join(lines[i:i + 8])]


def test_every_workflow_that_uses_the_action_checks_out_full_history():
    users = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text()
        if "uses: ./" in text or "Jackxiaozhiren/autorate@" in text:
            users.append(path)
    assert users, "no workflow exercises the action, so the PR gate has no runner"
    offenders = {p.name: _shallow_checkouts(p.read_text()) for p in users}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, "checkout steps without full history: %s" % offenders
    # negative control: dropping the flag must be named, not waved through.
    dropped = (WORKFLOWS / "action-gate.yml").read_text().replace("fetch-depth: 0", "fetch-depth: 1")
    assert _shallow_checkouts(dropped), "the predicate does not see a shallow checkout"


def test_the_pr_comment_quotes_compare_and_carries_both_denominators():
    """F8 rule 4, honestly: both denominators come from the tool's own lines, not from a formatter.

    The fixture is `autorate compare data/cert_laya.json data/cert_jev.json`'s real output shape (see
    `src/autorate/cli.py::cmd_compare` and `Certificate.summary`). `compare` states in its own docstring
    that it "has no authority to pair anything", so the comment must not claim a before/after bound.
    """
    out = ("comparable: yes -- identical alpha=0.05, beta=0.05, delta=0.05, method=aps, seed=7\n"
           "evaluation halves: laya has 96 records over 32 distinct request ids, jev has 96 over 32\n"
           "  cert_laya.json: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; "
           "n_cal=96 n_eval=96; at coverage 0.950 the exact case-level upper bound 0.975 exceeds the "
           "budget 0.050\n"
           "  cert_jev.json: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; "
           "n_cal=95 n_eval=96; at coverage 0.950 the exact case-level upper bound 0.140 exceeds the "
           "budget 0.050\n")
    body = ar.comment_body({"state": "certified"}, "a" * 40, "b" * 40, [("data/cert_laya.json", 0, out)])
    assert "n_cal=96 n_eval=96" in body and "n_cal=95 n_eval=96" in body
    assert "no authority to pair" in body, "the comment must say what the tool refuses to do"
    assert "computes no bound" in body, "the comment must say it is quoting, not deriving"
    assert "bound vs previous bound" not in body, "a bound diff is a claim the CLI does not make"
    # negative controls: the formatter invents neither denominator, and an empty section is a named
    # not-run rather than a silently omitted output (§6.2).
    empty = ar.comment_body({"state": "certified"}, "a" * 40, "b" * 40, [("data/cert_laya.json", 0, "")])
    assert "n_cal=96" not in empty
    absent = ar.comment_body({"state": "certified"}, "a" * 40, "b" * 40, [])
    assert "not-run" in absent and "no before/after pair" in absent


def _shell_protocol_reads(text):
    return re.findall(r"git show[^\n]*:[^\n]*protocol\.json", text)


def _argv_protocol_reads(text):
    return re.findall(r'\["git"\s*,\s*"show"[^\]]*protocol\.json', text)


def test_the_action_reads_the_protocol_from_the_working_tree_and_says_so():
    """F8 exception (a): use full history or the working tree, and assert which one was used.

    Both *command* surfaces are subjects: the composite's `runs:` block (shell) and the script that
    actually issues the object-database read (argv). Prose that states the prohibition -- action.yml's
    `inputs:` descriptions, the script's docstring and its error messages -- is not a command and is not
    inspected, because a pattern that indicts its own honest negations is §0.3's exemption-shaped defect.
    """
    run_block = ACTION.read_text().split("runs:", 1)[1]
    script_text = SCRIPT.read_text()
    assert _shell_protocol_reads(run_block) == []
    assert _argv_protocol_reads(script_text) == []
    # The one permitted object-database read is scoped to base certificates, never to the protocol.
    assert '"data/cert_*.json"' in script_text
    # negative controls: both predicates fire on the forbidden shape planted in their real subjects.
    # The replaced guard asserted a literal that contained itself -- §6.2 calls that decoration.
    assert _shell_protocol_reads(run_block + "\n          git show HEAD~1:protocol.json\n")
    assert _argv_protocol_reads(script_text +
                                '\nrun(["git", "show", "%s:protocol.json" % base], repo)\n')

    rec = {"state": "certified", "verify_exit": 0, "certify_exit": None, "denominator": (649, 649),
           "lane": "corpus present", "protocol": {"path": "protocol.json", "digest": "ce43f8e29cc1",
                                                 "frozen_at": "2026-10-17"},
           "cli_source": "working tree", "history_source": "object-db", "notes": [], "reason": None}
    assert "history source" in ar.summary_markdown(rec)
    assert "re-derived 649 /649 values" not in ar.summary_markdown(rec)  # the line is not invented
    rec["denominator_line"] = "re-derived 649 /649 values"
    assert "```text\nre-derived 649 /649 values\n```" in ar.summary_markdown(rec)


def test_the_badge_number_comes_from_the_line_the_summary_quotes():
    """F8 rule 2: the quoted line and the parsed denominator must be one row, not two."""
    text = "re-derived 1 /2 values\nre-derived 649 /649 values\n"
    quoted = ar._line_starting(text, "re-derived ", last=True)
    assert quoted == "re-derived 649 /649 values"
    assert ar.read_denominator(quoted or "") == (649, 649)
    assert ar.read_denominator(text) == (649, 649), "the parser must agree with the last quoted line"
    # negative control: first-match would disagree with `read_denominator`'s last-match rule, which is
    # exactly the split this guard exists to prevent.
    first = ar._line_starting(text, "re-derived ")
    assert first != quoted
    assert ar.read_denominator(first or "") != (649, 649)


def test_a_failed_comment_delivery_is_a_named_not_run(tmp_path, monkeypatch):
    """§6.2: a step that cannot deliver its output must say so, not fail silently into stderr."""
    summary = tmp_path / "summary.md"
    args = SimpleNamespace(pr="14", base_ref="a" * 40, summary=str(summary))

    def refused(cmd, repo):
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "b" * 40 + "\n"
        return 1, "gh: not logged in"

    monkeypatch.setattr(ar, "run", refused)
    ar._post_comment(args, tmp_path, {"state": "certified"}, [])
    body = summary.read_text()
    assert "PR comment: `not-run`" in body and "not logged in" in body
    # negative control: a delivered comment leaves no not-run line behind.
    summary.write_text("")

    def delivered(cmd, repo):
        return (0, "b" * 40 + "\n") if cmd[:2] == ["git", "rev-parse"] else (0, "")

    monkeypatch.setattr(ar, "run", delivered)
    ar._post_comment(args, tmp_path, {"state": "certified"}, [])
    assert "not-run" not in summary.read_text()


def test_a_runner_without_uvx_gets_not_run_not_a_pass(monkeypatch, tmp_path):
    """F8 exception (b): a runner that cannot reach a distribution reports not-run, never certified."""
    args = SimpleNamespace(version="0.1.0", ref="")
    monkeypatch.setattr(ar.shutil, "which", lambda name: None)
    source, why = ar.resolve_cli(args, tmp_path)
    assert source is None and "uvx" in why
    assert ar.classify("verify", 2) == "not-run"
    assert ar.exit_for("not-run", {"drift", "not-run"}, False) != 0, "not-run must not be a green exit"
    # negative control: with uvx present the very same args resolve to the pinned-distribution lane,
    # so the refusal above is about the environment, not a blanket rejection of `version`.
    monkeypatch.setattr(ar.shutil, "which", lambda name: "/usr/bin/uvx")
    source2, why2 = ar.resolve_cli(args, tmp_path)
    assert source2 == {"kind": "version", "value": "0.1.0"} and why2 is None


def test_the_action_refuses_a_path_that_leaves_the_checkout(tmp_path):
    """The contract says "in the working tree"; an absolute path or a `..` is outside it."""
    (tmp_path / "protocol.json").write_text("{}")
    assert ar.workspace_path(tmp_path, "protocol.json", "path")[0] == (tmp_path / "protocol.json").resolve()
    assert ar.workspace_path(tmp_path, "sub/../protocol.json", "path")[0] == (tmp_path / "protocol.json").resolve()
    # negative controls: both escapes are refused, and the reason names the field, not just "bad path".
    absolute = ar.workspace_path(tmp_path, "/etc/passwd", "path")
    escaping = ar.workspace_path(tmp_path, "../protocol.json", "path")
    assert absolute[0] is None and "path" in absolute[1] and "absolute" in absolute[1]
    assert escaping[0] is None and "leaves the workspace" in escaping[1]


def test_a_ref_that_would_be_read_as_an_option_is_refused(tmp_path):
    """`git worktree add --detach <path> <ref>` must not receive `--upload-pack=...` as a revision."""
    bad = ar.resolve_cli(SimpleNamespace(version="", ref="--upload-pack=/bin/sh"), ROOT)
    assert bad[0] is None and "option" in bad[1]

    # Build the store rather than assuming ROOT has one: this suite also runs from a `git archive`
    # export, where there is no `.git` at all. A `git init` is enough -- `history_source` asks
    # whether the work tree is shallow, not whether it has commits.
    repo = tmp_path / "with-object-db"
    repo.mkdir()
    assert _git("init", "-q", cwd=repo).returncode == 0
    assert ar.history_source(repo) == "object-db"
    good = ar.resolve_cli(SimpleNamespace(version="", ref="HEAD"), repo)
    assert good[0] == {"kind": "ref", "value": "HEAD"} and good[1] is None

    # The export lane is itself a store: a ref there must be a named not-run, not a pass.
    export = tmp_path / "export"
    export.mkdir()
    refused = ar.resolve_cli(SimpleNamespace(version="", ref="HEAD"), export)
    assert refused[0] is None and "no-object-db" in refused[1]


def test_the_history_source_distinguishes_the_three_stores_it_names(tmp_path):
    """The assertion has to be able to say something other than `object-db`, or it asserts nothing."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("x\n")
    assert _git("init", "-b", "main", cwd=src).returncode == 0
    assert _git("add", "f.txt", cwd=src).returncode == 0
    assert _git("-c", "user.email=a@b", "-c", "user.name=a", "commit", "-m", "one", cwd=src).returncode == 0

    full = tmp_path / "full"
    assert _git("clone", "--quiet", "file://%s" % src, str(full), cwd=tmp_path).returncode == 0
    shallow = tmp_path / "shallow"
    assert _git("clone", "--quiet", "--depth", "1", "file://%s" % src, str(shallow), cwd=tmp_path).returncode == 0
    empty = tmp_path / "empty"
    empty.mkdir()

    assert ar.history_source(full) == "object-db"
    assert ar.history_source(shallow) == "shallow"
    assert ar.history_source(empty) == "no-object-db"
    # ROOT is deliberately not asserted: this suite runs both from a checkout and from a `git
    # archive` export, whose honest answer is `no-object-db`. The three stores are built here so
    # the distinction is pinned in either lane rather than borrowed from the surrounding checkout.


# --- no statistics in the shell -------------------------------------------------------------------

FORBIDDEN = ("import statistics", "import numpy", "numpy.", "np.", "sum(", "mean(", "median(", "stdev",
             "quantile(")


def _statistics_offenders(text):
    return [token for token in FORBIDDEN if token in text]


def test_the_action_shell_implements_no_statistics():
    """F8 rule 5. Layout arithmetic (centring a label) is not a statistic; an aggregate would be."""
    assert _statistics_offenders(SCRIPT.read_text()) == []
    # negative control: the detector must fire on the shape it forbids.
    assert _statistics_offenders("return sum(xs) / len(xs)") == ["sum("]
    assert _statistics_offenders("import statistics") == ["import statistics"]
