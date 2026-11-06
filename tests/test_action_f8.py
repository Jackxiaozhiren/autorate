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
    # negative controls: a superseded digest, and an svg that lost its denominator.
    stale = json.loads(json.dumps(payload))
    stale["protocol"]["digest"] = "0" * 12
    assert any("freeze" in p for p in _badge_problems(stale, digest12, svg))
    assert any("denominator" in p for p in _badge_problems(payload, digest12, "autorate certified"))


# --- the action and its checkout contract ---------------------------------------------------------

INPUTS = ("version", "ref", "alpha", "beta", "path", "records", "fail-on", "badge-dir", "comment")


def _declared_inputs(text):
    return set(re.findall(r"^ {2}([a-z-]+):$", text, re.MULTILINE))


def test_the_action_is_a_composite_that_runs_the_shipped_shell():
    text = ACTION.read_text()
    assert "using: composite" in text, "a JavaScript or Docker action would move the logic out of this repo"
    assert "docker://" not in text
    assert "tools/action_report.py" in text, "the action no longer runs the shipped shell"
    assert "default: drift,not-run" in text, "the documented default is what makes exit 3 a result"
    missing = set(INPUTS) - _declared_inputs(text)
    assert not missing, "inputs F8 names but the action does not declare: %s" % sorted(missing)
    # negative control: the same predicate must refuse an action.yml missing one input.
    synthetic = re.sub(r"^ {2}fail-on:$", "  failon:", text, flags=re.MULTILINE)
    assert "fail-on" in set(INPUTS) - _declared_inputs(synthetic)


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
    """F8 rule 4: a bound diff shows both sides' denominators; the action computes neither."""
    out = ("cert_laya.json: comparable: no -- the two sides were certified at different alpha\n"
           "  cert_laya.json: CERTIFIED at alpha=0.050; n_cal=96 n_eval=96\n"
           "  cert_old.json: CERTIFIED at alpha=0.100; n_cal=95 n_eval=96\n")
    body = ar.comment_body({"state": "certified"}, "a" * 40, "b" * 40, [("data/cert_laya.json", 0, out)])
    assert "n_cal=96 n_eval=96" in body and "n_cal=95 n_eval=96" in body
    assert "computes no bound" in body, "the comment must say it is quoting, not deriving"
    # negative control: the same body without the quote loses both denominators, so their presence is
    # what the row above reads -- not a sentence the formatter adds on its own.
    empty = ar.comment_body({"state": "certified"}, "a" * 40, "b" * 40, [("data/cert_laya.json", 0, "")])
    assert "n_cal=96" not in empty


def test_the_action_reads_the_protocol_from_the_working_tree_and_says_so():
    """F8 exception (a): use full history or the working tree, and assert which one was used."""
    # Only the `runs:` block is a command surface; the inputs block explains the prohibition in prose.
    run_block = ACTION.read_text().split("runs:", 1)[1]
    assert "git show" not in run_block, (
        "the action must not read the protocol out of the object database; `ref` is the only lane that "
        "needs history, and it reports `not-run` when the checkout is shallow")
    assert "git show" in "run: git show HEAD:protocol.json", "the check cannot see the shape it forbids"
    rec = {"state": "certified", "verify_exit": 0, "certify_exit": None, "denominator": (649, 649),
           "lane": "corpus present", "protocol": {"path": "protocol.json", "digest": "ce43f8e29cc1",
                                                 "frozen_at": "2026-10-17"},
           "cli_source": "working tree", "history_source": "object-db", "notes": [], "reason": None}
    assert "history source" in ar.summary_markdown(rec)
    assert "re-derived 649 /649 values" not in ar.summary_markdown(rec)  # the line is not invented
    rec["denominator_line"] = "re-derived 649 /649 values"
    assert "```text\nre-derived 649 /649 values\n```" in ar.summary_markdown(rec)


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
    assert ar.history_source(ROOT) == "object-db"


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
