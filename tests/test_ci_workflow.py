"""Task #91/R-263: the G5 note rests on CI running the frozen form, and nothing policed the workflow.

`docs/G5.md` and the G5 claim sentence say `verify --protocol protocol.json` is platform-witnessed. That is
true today because `.github/workflows/ci.yml` was edited to invoke the frozen form on every job; the witness
comes from reading the runner's own log for run `38400305544`, and again for run `38674203783` (both at head
`9e6363a`, whose lanes printed `re-derived 249 /249 values`: `offline`, `cross-libc-verify (ubuntu-latest)`
and `cross-libc-verify (macos-latest)` each printed that line there -- read with
`gh run view <id> --log --job <jid> | grep re-derived`, so the claim is a log line and not a job status. The
denominators are named as that revision's, not as today's: the transcript now names the commit it was
re-exported from, and a log witness for a workflow shape does not expire when a lane grows). The first run,
three jobs, each printing `re-derived 248 /248 values` at exit 0), not from this file. What this file does is
refuse the quiet regression that would make those sentences false again: a workflow step edited back to the
plain `verify`, which re-derives the numbers but never asks the freeze to agree with them.

Both rows are needed. The first can go vacuous -- a regex that matches nothing makes "every match has the
flag" true by default -- so the second applies the same predicate to a synthetic workflow carrying the bare
form and requires it to name the offender. That is what proves the first row can fail.
"""
import re
from pathlib import Path

import pytest

from autorate import cli

WORKFLOW = Path(cli.__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
VERIFY_RX = re.compile(r"autorate\s+verify\b")
PROTOCOL_RX = re.compile(r"--protocol\b")


STEP_RX = re.compile(r"^\s*(?:-\s*)?run:\s*(.*)$")


def verify_commands(text):
    """The workflow's actual `run:` steps that invoke `autorate verify`, comment lines excluded.

    Scanning every line instead of every step was measured to indict four prose mentions -- the header comment
    explaining why the cross-libc arm exists, and the sentence in `verify`'s own job comment -- so a line scan
    reports the honest-looking failure of a guard whose subject is commands. A step's value is folded with its
    continuation lines, because a `run: |` block can put the flag on the next physical line.
    """
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        m = STEP_RX.match(line)
        if not m:
            continue
        body = [m.group(1)]
        for following in lines[i + 1:]:
            if not following.strip() or STEP_RX.match(following) or not following.startswith(" " * (len(line) - len(line.lstrip()) + 1)):
                break
            body.append(following)
        command = " ".join(" ".join(body).split())
        if VERIFY_RX.search(command):
            found.append(command)
    return found


def bare_verify_steps(commands):
    return [c for c in commands if not PROTOCOL_RX.search(c)]


def test_the_committed_workflow_only_asks_verify_about_the_frozen_protocol():
    """RED if a step is edited back to the plain form; also red if the parse finds nothing to check."""
    text = WORKFLOW.read_text()
    invocations = verify_commands(text)
    assert len(invocations) >= 2, (
        "the workflow no longer runs `autorate verify` on at least two jobs, so this row is comparing an "
        "empty list and the G5 note's platform-witness claim has no owner here: %r" % invocations)
    offenders = bare_verify_steps(invocations)
    assert not offenders, "verify steps that never consult the freeze: %s" % offenders


def test_a_bare_verify_step_is_named_rather_than_waved_through():
    """The negative control: the same predicate must refuse a workflow that dropped the flag."""
    synthetic = (
        "jobs:\n"
        "  offline:\n"
        "    # a comment that mentions autorate verify and must NOT count as a step\n"
        "    - run: uv run --frozen autorate verify\n"
        "    - run: uv run --frozen\n"
        "        autorate verify --protocol protocol.json\n")
    commands = verify_commands(synthetic)
    assert any(c.endswith("autorate verify") for c in commands), commands
    assert not any("NOT COUNT" in c for c in commands), (
        "a prose mention inside a job must not be scanned as a step: %s" % commands)
    offenders = bare_verify_steps(commands)
    assert offenders and offenders[0].endswith("autorate verify"), offenders
    assert PROTOCOL_RX.search(synthetic), "the second step must still pass, or the predicate is not a filter"


@pytest.mark.parametrize("form", ["autorate  verify", "autorate verify --protocol protocol.json"])
def test_the_predicate_keys_on_the_command_not_on_spacing(form):
    """A tab-continuation or a double space must not hide a step from the guard."""
    assert VERIFY_RX.search("- run: uv run --frozen %s" % form)


def test_the_runner_fetches_the_history_the_transcript_rows_need():
    """`fetch-depth: 0` is not a preference; two G5 rows read an earlier commit's freeze.

    Measured on CI run 38503812390: the default shallow checkout gave the runner one commit in its object
    database, `git show <named>:protocol.json` failed with "Not a valid object name", and the transcript's
    digest and ancestry rows went red on the platform while passing in every full clone and skipping inside a
    `git archive` export. Reproduced locally with a `file://` clone at depth 1 (1 object) and the same fetch
    unshallowed (208 objects, the object present). Plant: drop `fetch-depth: 0` from a checkout step and this
    row names the step instead of letting the failure surface three files away.
    """
    lines = WORKFLOW.read_text().splitlines()
    checkouts = [i for i, line in enumerate(lines) if "actions/checkout@" in line]
    assert checkouts, "the workflow no longer checks the repository out, so the transcript rows have no runner"
    shallow = [lines[i].strip() for i in checkouts if "fetch-depth: 0" not in "\n".join(lines[i:i + 8])]
    assert not shallow, "checkout steps without full history: %s" % shallow
