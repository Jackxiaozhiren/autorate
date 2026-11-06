"""F8's shell half: run `autorate`, map its exit code to one of four states, write the badge.

The rule this file obeys is PRD §5 F8 rule 5: **the action shells out; it implements no statistics**.
Nothing here computes a bound, a rate, a mean or an aggregate. Its whole numeric surface is parsing two
integers out of a line the tool already printed (`re-derived N /M values`) so the badge can carry its own
denominator -- which is I2, not arithmetic.

The state vocabulary is closed and honest (F8 rule 3): `certified`, `not-certifiable`, `drift`, `not-run`.
There is no boolean. A caller that asks for one gets `ValueError`, because the failure this guards against
is a badge that renders green when the run produced no verdict at all.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Closed vocabulary, in the order the README explains it. `not-run` is a state, not an absence of one.
STATES = ("certified", "not-certifiable", "drift", "not-run")

# Exit code -> state, per lane. A code the lane does not define is `not-run`, never a pass: exit 2 is a
# usage error (F6 rule 2 calls that a configuration bug, not a red KPI), and a crash or a missing
# interpreter must not be reported as a verdict about the model.
VERDICTS = {
    "verify": {0: "certified", 4: "drift"},
    "certify": {0: "certified", 3: "not-certifiable"},
}

# Every state gets a colour AND its own word. Section 11's accessibility row forbids signalling status by
# colour alone, so the word is load-bearing and the colour is decoration.
FILL = {
    "certified": "#1a7f37",
    "not-certifiable": "#9a6700",
    "drift": "#cf222e",
    "not-run": "#6e7781",
}

STATE_MEANING = {
    "certified": ("`verify` exited 0: every published number re-derived and the frozen protocol's rubric "
                  "was enforced. When a records file was supplied, `certify` also exited 0 at the budget."),
    "not-certifiable": ("`certify` exited 3: the data cannot support the claim at this alpha/beta. This is a "
                        "result, not a broken pipeline -- the badge says so instead of turning green."),
    "drift": "`verify` exited 4: the committed tree cannot reproduce what it publishes.",
    "not-run": ("No verdict was produced -- no CLI, no network, a shallow checkout for the requested ref, a "
                "usage error, or a missing denominator line. A run that did not happen is never a pass."),
}

DENOMINATOR_RX = re.compile(r"re-derived (\d+) /(\d+) values")
PROTOCOL_RX = re.compile(r"^protocol: (\S+) ([0-9a-f]{12}) \(frozen ([^)]+)\)", re.MULTILINE)
LANE_RX = re.compile(r"^disclosure: (corpus (?:present|absent))\b", re.MULTILINE)


def classify(lane: str, rc: int) -> str:
    """The lane's own exit-code contract, and nothing else.

    `verify` can only certify or drift: it never refuses (exit 3 belongs to `certify`/`gate`), so a
    refusal badge can only come from a lane that actually ran a certification.
    """
    if lane not in VERDICTS:
        raise ValueError("unknown lane %r; the vocabulary is closed: %s" % (lane, sorted(VERDICTS)))
    return VERDICTS[lane].get(int(rc), "not-run")


def combine(verify_state: str, certify_state: str | None) -> str:
    """`verify` is the gate; a fresh certification can only make the verdict narrower.

    - verify did not certify -> its verdict stands (drift / not-run).
    - verify certified, no certification lane -> certified.
    - verify certified, certify refused -> `not-certifiable`: a refusal is a first-class result (I3) and
      outranks a green gate, because the gate re-derives published numbers while the certification asks a
      different question -- whether this data supports the claim at this budget.
    - verify certified, certify could not run -> `not-run`, never the green one.
    """
    for state in (verify_state, certify_state):
        if state is not None and state not in STATES:
            raise ValueError("not a state: %r" % (state,))
    if verify_state != "certified":
        return verify_state
    if certify_state in (None, "certified"):
        return "certified"
    return "not-certifiable" if certify_state == "not-certifiable" else "not-run"


def read_denominator(text: str):
    """The tool's own `re-derived N /M values` line -> (N, M), or None if absent or impossible.

    Last match wins: the line closes `verify`'s output, and a transcript quoted earlier in the log must
    not shadow it. `N > M` is treated as absent rather than repaired -- a badge may not launder a line the
    tool did not print.
    """
    hits = DENOMINATOR_RX.findall(text or "")
    if not hits:
        return None
    checked, total = int(hits[-1][0]), int(hits[-1][1])
    if checked > total:
        return None
    return checked, total


def read_protocol(text: str):
    """`protocol: <path> <digest12> (frozen <date>)` -> dict, or None."""
    m = PROTOCOL_RX.search(text or "")
    if not m:
        return None
    return {"path": m.group(1), "digest": m.group(2), "frozen_at": m.group(3)}


def read_lane(text: str):
    """The lane label as the tool prints it (`corpus present` / `corpus absent`), shortened to the label."""
    m = LANE_RX.search(text or "")
    return m.group(1) if m else None


def badge_svg(state: str, value: str, tooltip: str) -> str:
    """A two-cell badge. `value` carries the state word and, when there is one, the denominator."""
    if state not in STATES:
        raise ValueError("not a state: %r" % (state,))
    label = "autorate"
    left_w = 7 + 7 * len(label)
    right_w = 14 + 7 * len(value)
    width = left_w + right_w
    tip = html.escape(tooltip or "%s: %s" % (label, value), quote=True)
    lx, vx = left_w // 2 + 1, left_w + right_w // 2
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="20" role="img" '
        'aria-label="autorate: %s">\n'
        "  <title>%s</title>\n"
        '  <clipPath id="r"><rect width="%d" height="20" rx="3" fill="#fff"/></clipPath>\n'
        '  <g clip-path="url(#r)">\n'
        '    <rect width="%d" height="20" fill="#555"/>\n'
        '    <rect x="%d" width="%d" height="20" fill="%s"/>\n'
        "  </g>\n"
        '  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'font-size="11">\n'
        '    <text x="%d" y="14">%s</text>\n'
        '    <text x="%d" y="14">%s</text>\n'
        "  </g>\n"
        "</svg>\n"
    ) % (width, html.escape(value, quote=True), tip, width,
         left_w, left_w, right_w, FILL[state], lx, label, vx, html.escape(value))


def history_source(repo: Path) -> str:
    """Which store a base revision can be read from, asserted rather than assumed (F8 exception (a)).

    `object-db`    - full history: `git show <rev>:<path>` resolves.
    `shallow`      - a shallow checkout: only HEAD is present, so a base revision cannot be read.
    `no-object-db` - not a git work tree at all (a `git archive` export).
    """
    try:
        inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo),
                                capture_output=True, text=True)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return "no-object-db"
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=str(repo),
                                 capture_output=True, text=True)
        if shallow.returncode != 0:
            return "no-object-db"
        return "shallow" if shallow.stdout.strip() == "true" else "object-db"
    except OSError:
        return "no-object-db"


def run(cmd, cwd: Path):
    """One command, one exit code taken from that command (PRD §13.1's exit-code hygiene)."""
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def resolve_cli(args, repo: Path):
    """Decide where the CLI comes from before running anything, and refuse what cannot work.

    Returns `(source, reason)`. `source` is a dict with `kind` in {version, ref, working-tree}.
    """
    if args.version and args.ref:
        return None, "`version` and `ref` are mutually exclusive; name one of them"
    if args.version:
        if not shutil.which("uvx"):
            return None, "`version` needs `uvx` on PATH; it is absent"
        return {"kind": "version", "value": args.version}, None
    if args.ref:
        hist = history_source(repo)
        if hist != "object-db":
            # F8 exception (a), stated as a state rather than a stack trace.
            return None, ("`ref` needs full history to resolve %r and this checkout is `%s`; use "
                          "actions/checkout with fetch-depth: 0, or drop `ref`" % (args.ref, hist))
        return {"kind": "ref", "value": args.ref}, None
    if not (repo / "pyproject.toml").is_file():
        return None, "no `version`/`ref` given and no pyproject.toml here; there is nothing to run"
    return {"kind": "working-tree", "value": "."}, None


def prefix_for(source: dict, repo: Path):
    """The argv prefix that reaches the CLI. The summary always says which resolver produced it."""
    if source["kind"] == "version":
        return ["uvx", "--from", "autorate==%s" % source["value"], "autorate"]
    if source["kind"] == "ref":
        return ["uv", "run", "--frozen", "--project", source["worktree"], "autorate"]
    return ["uv", "run", "--frozen", "autorate"]


def cli_label(source: dict) -> str:
    if source["kind"] == "version":
        return "pypi `autorate==%s`" % source["value"]
    if source["kind"] == "ref":
        return "worktree at `%s`" % source["value"]
    return "working tree (`uv run --frozen autorate`)"


def _line_starting(text: str, prefix: str):
    for line in (text or "").splitlines():
        if line.startswith(prefix):
            return line
    return None


def _first_nonempty(text: str):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def summary_markdown(rec: dict) -> str:
    """The job summary. The tool's denominator line goes in **verbatim** (F8 rule 2)."""
    lines = ["## autorate gate: `%s`" % rec["state"], "", STATE_MEANING[rec["state"]], ""]
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append("| state | `%s` |" % rec["state"])
    lines.append("| verify exit | `%s` |" % rec["verify_exit"])
    if rec.get("certify_exit") is not None:
        lines.append("| certify exit | `%s` |" % rec["certify_exit"])
    if rec.get("denominator"):
        lines.append("| re-derived | `%d /%d` |" % rec["denominator"])
    if rec.get("lane"):
        lines.append("| lane | `%s` |" % rec["lane"])
    if rec.get("protocol"):
        p = rec["protocol"]
        lines.append("| protocol | `%s %s` (frozen %s) |" % (p["path"], p["digest"], p["frozen_at"]))
    lines.append("| cli source | %s |" % rec["cli_source"])
    lines.append("| history source | `%s` |" % rec["history_source"])
    if rec.get("badge"):
        lines.append("| badge | `%s` |" % rec["badge"])
    lines.append("")
    if rec.get("denominator_line"):
        lines.append("The tool's own denominator line, verbatim:")
        lines.append("")
        lines.append("```text")
        lines.append(rec["denominator_line"])
        lines.append("```")
        lines.append("")
    if rec.get("refusal"):
        lines.append("The refusal, as the certificate prints it:")
        lines.append("")
        lines.append("```text")
        lines.append(rec["refusal"])
        lines.append("```")
        lines.append("")
    if rec.get("reason"):
        lines.append("**Why this is not a verdict:** %s" % rec["reason"])
        lines.append("")
    if rec.get("notes"):
        lines.append("Notes:")
        lines.append("")
        for note in rec["notes"]:
            lines.append("- %s" % note)
        lines.append("")
    return "\n".join(lines)


def _write_summary(text: str, target: str):
    if target:
        with Path(target).open("a", encoding="utf-8") as fh:
            fh.write(text + ("\n" if not text.endswith("\n") else ""))
    else:
        sys.stdout.write(text + "\n")


def changed_certificates(repo: Path, base_sha: str, head_sha: str, prefix):
    """Quote `autorate compare` for every certificate this PR changed. No diff is computed here."""
    rc, out = run(["git", "diff", "--name-only", base_sha, head_sha, "--", "data/cert_*.json"], repo)
    if rc != 0:
        return [], "`git diff %s..%s` exited %d" % (base_sha[:12], head_sha[:12], rc)
    names = [line.strip() for line in out.splitlines() if line.strip()]
    if not names:
        return [], None
    sections = []
    tmp = Path(tempfile.mkdtemp(prefix="autorate-base-"))
    for name in names:
        base_file = tmp / Path(name).name
        rc, blob = run(["git", "show", "%s:%s" % (base_sha, name)], repo)
        if rc != 0:
            sections.append((name, rc, "`git show %s:%s` exited %d: the base blob is not in this object "
                                       "database" % (base_sha[:12], name, rc)))
            continue
        base_file.write_text(blob, encoding="utf-8")
        rc, out = run([*prefix, "compare", str(base_file), str(repo / name)], repo)
        sections.append((name, rc, out))
    return sections, None


def comment_body(rec: dict, base_sha: str, head_sha: str, sections) -> str:
    lines = ["### autorate: bound vs previous bound", "",
             "`%s` -> `%s`. Both denominators are quoted by `autorate compare`; this action computes no "
             "bound." % (base_sha[:12], head_sha[:12]), ""]
    if not sections:
        lines.append("No certificate under `data/` changed in this pull request, so there is no bound to "
                     "diff. The gate verdict is in the job summary.")
    for name, rc, out in sections:
        lines += ["`%s` -- `autorate compare` exit `%d`" % (name, rc), "", "```text",
                  out.strip() or "(no output)", "```", ""]
    return "\n".join(lines)


def _post_comment(args, repo: Path, rec, sections):
    base_rc, head_sha = run(["git", "rev-parse", "HEAD"], repo)
    head_sha = head_sha.strip() if base_rc == 0 else "HEAD"
    body = comment_body(rec, args.base_ref, head_sha, sections)
    path = Path(tempfile.mkdtemp(prefix="autorate-comment-")) / "comment.md"
    path.write_text(body, encoding="utf-8")
    rc, out = run(["gh", "pr", "comment", args.pr, "--body-file", str(path)], repo)
    if rc != 0:
        print("pr comment: not-run (gh exited %d): %s" % (rc, out.strip()[:400]), file=sys.stderr)


def verdict_from(verify_rc: int, verify_out: str, certify_rc=None, certify_out: str = ""):
    """The whole F8 decision, as a pure function of the tool's exit codes and its own printed lines.

    Split out of `main` so the one rule that must never regress -- "a green exit without a denominator is
    not a verdict" -- can be exercised without a subprocess. Returns `(state, refusal_line)`.
    """
    if verify_rc == 0 and read_denominator(verify_out) is None:
        return "not-run", None
    verify_state = "certified" if verify_rc == 0 else classify("verify", verify_rc)
    certify_state = classify("certify", certify_rc) if certify_rc is not None else None
    refusal = None
    if certify_rc == 3:
        refusal = _line_starting(certify_out, "NOT_CERTIFIABLE") or _first_nonempty(certify_out)
    return combine(verify_state, certify_state), refusal


def exit_for(state: str, fail_on, force_fail: bool = False) -> int:
    """`fail_on` is the documented knob from F8 rule 1; the default is `drift,not-run`."""
    return 1 if (force_fail or state in fail_on) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="autorate gate shell: exit codes in, four states out.")
    ap.add_argument("--path", default="protocol.json")
    ap.add_argument("--alpha", default="")
    ap.add_argument("--beta", default="")
    ap.add_argument("--records", default="")
    ap.add_argument("--version", default="")
    ap.add_argument("--ref", default="")
    ap.add_argument("--fail-on", default="drift,not-run")
    ap.add_argument("--badge-dir", default=".autorate")
    ap.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    ap.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_SHA", ""))
    ap.add_argument("--pr", default=os.environ.get("GITHUB_PR_NUMBER", ""))
    ap.add_argument("--comment", default="true")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    notes = []
    rec = {
        "state": "not-run",
        "verify_exit": None,
        "certify_exit": None,
        "denominator": None,
        "lane": None,
        "protocol": None,
        "cli_source": "none",
        "history_source": history_source(repo),
        "notes": notes,
        "reason": None,
    }

    source, why = resolve_cli(args, repo)
    if source is None:
        rec["reason"] = why
        return _finish(rec, args, repo, sections=[], force_fail=True)

    if source["kind"] == "ref":
        worktree = Path(tempfile.mkdtemp(prefix="autorate-ref-")) / "tree"
        rc, out = run(["git", "worktree", "add", "--detach", worktree, source["value"]], repo)
        if rc != 0:
            rec["reason"] = "`git worktree add %s` exited %d: %s" % (source["value"], rc, out.strip()[:300])
            return _finish(rec, args, repo, sections=[], force_fail=True)
        source["worktree"] = str(worktree)
        notes.append("cli source: a detached worktree at `%s`; the revision's own lockfile is what ran"
                     % source["value"])

    prefix = prefix_for(source, repo)
    rec["cli_source"] = cli_label(source)

    if not (repo / args.path).is_file():
        rec["reason"] = ("`%s` is not a file in the working tree; the action reads the working tree and "
                         "never `git show <rev>:%s`" % (args.path, args.path))
        return _finish(rec, args, repo, sections=[], force_fail=True)

    verify_rc, verify_out = run([*prefix, "verify", "--protocol", args.path], repo)
    rec["verify_exit"] = verify_rc
    rec["denominator"] = read_denominator(verify_out)
    rec["lane"] = read_lane(verify_out)
    rec["protocol"] = read_protocol(verify_out)
    rec["denominator_line"] = _line_starting(verify_out, "re-derived ")
    if verify_rc == 0 and rec["denominator"] is None:
        rec["reason"] = ("`verify` exited 0 but printed no `re-derived N /M values` line, so there is no "
                         "denominator the badge could carry")
        return _finish(rec, args, repo, sections=[], force_fail=True)
    if verify_rc not in (0, 4):
        rec["reason"] = "`verify` exited %d: %s" % (verify_rc, _first_nonempty(verify_out)[:300])

    certify_rc, certify_out = None, ""
    if verify_rc == 0 and args.records:
        if not (repo / args.records).is_file():
            rec["reason"] = "`records` names `%s`, which is not in the working tree" % args.records
            return _finish(rec, args, repo, sections=[], force_fail=True)
        out_cert = Path(tempfile.mkdtemp(prefix="autorate-cert-")) / "cert.json"
        cmd = [*prefix, "certify", args.records, "--protocol", args.path, "--out", str(out_cert)]
        if args.alpha:
            cmd += ["--alpha", args.alpha]
        if args.beta:
            cmd += ["--beta", args.beta]
        certify_rc, certify_out = run(cmd, repo)
        rec["certify_exit"] = certify_rc
        if certify_rc not in (0, 3):
            rec["reason"] = ("`certify` exited %d: a usage or artefact error is a configuration bug, "
                             "not a verdict" % certify_rc)

    rec["state"], refusal = verdict_from(verify_rc, verify_out, certify_rc, certify_out)
    if refusal:
        rec["refusal"] = refusal

    sections = []
    if args.base_ref:
        if rec["history_source"] != "object-db":
            notes.append("bound diff: not-run -- history source is `%s`, so the base revision cannot be "
                         "read (F8 exception (a))" % rec["history_source"])
        else:
            head_rc, head_sha = run(["git", "rev-parse", "HEAD"], repo)
            head_sha = head_sha.strip() if head_rc == 0 else "HEAD"
            sections, diff_why = changed_certificates(repo, args.base_ref, head_sha, prefix)
            if diff_why:
                notes.append("bound diff: not-run -- %s" % diff_why)

    return _finish(rec, args, repo, sections=sections)


def _finish(rec: dict, args, repo: Path, sections, force_fail: bool = False) -> int:
    detail = " %d/%d" % rec["denominator"] if rec.get("denominator") else ""
    value = "%s%s" % (rec["state"], detail)
    tips = ["autorate %s" % value]
    if rec.get("lane"):
        tips.append(rec["lane"])
    if rec.get("protocol"):
        tips.append("protocol %s frozen %s" % (rec["protocol"]["digest"], rec["protocol"]["frozen_at"]))
    svg = badge_svg(rec["state"], value, "; ".join(tips))

    badge_dir = Path(args.badge_dir)
    if not badge_dir.is_absolute():
        badge_dir = repo / badge_dir
    badge_dir.mkdir(parents=True, exist_ok=True)
    (badge_dir / "autorate-badge.svg").write_text(svg, encoding="utf-8")
    payload = {k: v for k, v in rec.items() if k != "notes"}
    (badge_dir / "autorate-badge.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                                   encoding="utf-8")
    svg_path = badge_dir / "autorate-badge.svg"
    try:
        rec["badge"] = str(svg_path.relative_to(repo))
    except ValueError:
        rec["badge"] = str(svg_path)

    _write_summary(summary_markdown(rec), args.summary)

    fail_on = {s.strip() for s in (args.fail_on or "").split(",") if s.strip()}
    unknown = fail_on - set(STATES)
    if unknown:
        print("unknown fail-on value(s): %s; the vocabulary is %s" % (sorted(unknown), list(STATES)),
              file=sys.stderr)
        return 2

    outputs = os.environ.get("GITHUB_OUTPUT")
    if outputs:
        with Path(outputs).open("a", encoding="utf-8") as fh:
            fh.write("state=%s\n" % rec["state"])
            fh.write("badge=%s\n" % rec["badge"])
            if rec.get("denominator"):
                fh.write("denominator=%d/%d\n" % rec["denominator"])

    if args.comment.lower() == "true" and args.pr and args.base_ref:
        _post_comment(args, repo, rec, sections)

    return exit_for(rec["state"], fail_on, force_fail)


if __name__ == "__main__":
    sys.exit(main())
