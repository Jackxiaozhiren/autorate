"""Task #91/R-263: the G5 note rests on CI running the frozen form, and nothing policed the workflow.

`docs/G5.md` and the G5 claim sentence say `verify --protocol protocol.json` is platform-witnessed. That is
true today because `.github/workflows/ci.yml` was edited to invoke the frozen form on every job; the witness is
read out of the runner's own log, never from a job status. Measured on the tip this round pushed: run
`39119773205` at head `c2cff3a`, three job instances -- `offline`, `cross-libc-verify (ubuntu-latest)` and
`cross-libc-verify (macos-latest)` -- and the log yields exactly three occurrences of
`re-derived 734 /734 values`, which is the corpus-absent denominator the transcript now carries. Read it with
`gh run view 39119773205 --log | grep -o 're-derived [0-9]* /[0-9]* values' | sort | uniq -c`. The older cited
runs, `38400305544` and `38674203783` at head `9e6363a`, printed `249 /249` there (and an earlier run printed
`248 /248` at exit 0); they stay the witness for the workflow-shape edit itself, and their denominators are
named as that revision's, because a run belongs to the commit that was pushed -- which is exactly why
`docs/G5.md` quotes no run id at all. What this file does is refuse the quiet regression that would make those
sentences false again: a workflow step edited back to the plain `verify`, which re-derives the numbers but
never asks the freeze to agree with them.

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


JOB_RX = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
SHELL_RX = re.compile(r"^\s*shell:\s*(\S+)")


def _job_blocks(text):
    """The workflow's job bodies, split on the two-space keys under `jobs:`.

    A YAML parse is not available here -- the project's runtime floor is the standard library plus numpy, and a
    test-only dependency would have to be justified in `pyproject.toml` and `uv.lock` for one file -- so the
    scan is line-shaped, like the rows above it. It is keyed on indentation rather than on a list of job names,
    because a guard that enumerates two jobs cannot see a third.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        raise AssertionError("the workflow has no `jobs:` mapping, so nothing here can be censused")
    blocks, name = [], None
    for line in lines[start + 1:]:
        keyed = JOB_RX.match(line)
        if keyed:
            name, body = keyed.group(1), []
            blocks.append((name, body))
        elif name is not None and not line.startswith(" " * 4) and line.strip():
            name = None                                  # dedented back to a workflow-level key
        elif name is not None:
            blocks[-1][1].append(line)
    return blocks


def piped_steps_without_pipefail(text):
    """Jobs whose `run:` steps pipe a gate into a consumer while the job never asks for a failing pipeline.

    GitHub's `shell: bash` runs `bash -e -o pipefail`; its documented default for `run` is `bash -e`, which
    reports the *last* command's status -- so `pytest | tee /tmp/pytest.log` on the default shell is green on a
    red suite. Every gate step in this workflow pipes its output to a log, so the workflow's ability to fail
    lives in those `defaults.run.shell: bash` declarations, and a comment saying so is not a guard.
    """
    offenders = []
    for name, body in _job_blocks(text):
        shell = {m.group(1) for line in body for m in [SHELL_RX.match(line)] if m}
        if "bash" in shell:
            continue
        pipes = [cmd for cmd in (STEP_RX.match(line) for line in body)
                 if cmd and "|" in cmd.group(1).strip()]
        if pipes:
            offenders.append((name, len(pipes)))
    return offenders


def test_no_ci_job_pipes_a_gate_without_declaring_the_shell_that_makes_it_fail():
    """Every job that pipes a gate to a log must declare `shell: bash`, or its exit code is `tee`'s.

    GREEN on arrival: both jobs (`offline`, `cross-libc-verify`) carry the declaration, and the row above the
    first one records it as a deliberate choice with a comment. It is proved able to fail by the plant below,
    which runs the same predicate over a workflow with a piped step and no `defaults` block, and by the second
    plant, which shows the predicate is not a pipe-detector that indicts every job -- a job with no pipes is
    not named even without the declaration.
    """
    text = WORKFLOW.read_text()
    blocks = _job_blocks(text)
    assert sorted(name for name, _body in blocks) == ["cross-libc-verify", "offline"], blocks
    assert any(any("|" in (STEP_RX.match(line).group(1) if STEP_RX.match(line) else "") for line in body)
               for _name, body in blocks), "no step pipes anywhere, so this row guards nothing"
    assert piped_steps_without_pipefail(text) == [], piped_steps_without_pipefail(text)

    bare = ("jobs:\n"
            "  sneaky:\n"
            "    steps:\n"
            "      - run: uv run --frozen pytest | tee /tmp/pytest.log\n"
            "      - run: uv run --frozen autorate verify --protocol protocol.json | tee /tmp/verify.log\n")
    assert piped_steps_without_pipefail(bare) == [("sneaky", 2)], piped_steps_without_pipefail(bare)

    quiet = ("jobs:\n"
             "  nopipes:\n"
             "    steps:\n"
             "      - uses: actions/checkout@v4\n")
    assert piped_steps_without_pipefail(quiet) == [], piped_steps_without_pipefail(quiet)
