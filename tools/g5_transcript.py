#!/usr/bin/env python3
"""Turn one export run's record into `docs/G5.md`, with the machine's paths removed.

    python3 tools/g5_transcript.py --record <run.tsv> --out docs/G5.md

The transcript is generated, never typed, for the same reason `docs/RESULTS.md` is: a hand-copied exit code is
a claim about a run rather than a record of one. `tools/g5_export.sh` produces the record -- one masked
`key<TAB>value` line per fact -- and this file decides what a reader sees.

Three rules the emitter exists to enforce.

*Nothing recomputed.* The protocol digest printed here is the value the RUN recorded, not the value this
process could calculate now. Recomputing it would make `tests/test_g5_transcript.py`'s staleness row unable to
fail: a transcript that always prints today's digest can never be caught describing an older freeze.

*No leak survives to a tracked file.* A transcript's most natural content is the path of the directory the run
happened in. `tools/g5_export.sh` masks it on the way into the record, and this file refuses to write any
document that still matches a machine-path shape -- including the `/var/folders` and `/private/tmp` spellings
of one scratch directory that the tracked-tree guard in `tests/test_cli.py` does not cover.

*The exit-code contract is decided here, not downstream.* A lane that did not exit 0, a code outside 0/2/3/4,
a plant recorded as not having landed, and a plant with no restore receipt for its own file are all refusals
rather than renderings. The reason is the shape of the failure this file caused once: the renderer printed any
`\\d+` it was handed, `docs/G5.md` carried an escaping rc 1 into a tracked file, and the test that named it ran
after the overwrite -- so the record that would have explained the refusal was in a temp directory nobody
referenced. Un-writable beats un-green.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LEAK_RX = re.compile(r"/(?:Users|home|var/folders|private/tmp|private/var|tmp)/\S*")
MASK = "<export-dir>"
STEPS = ("lane_absent", "lane_present")
FALSIFICATIONS = ("tamper_protocol", "swap_records", "wrong_shape_snapshot", "tamper_artefact_digest")
HEX64 = re.compile(r"[0-9a-f]{64}")

# The exit codes this repository documents (`cli.py`: 0 certified, 2 usage, 3 not certifiable, 4 drift).
CONTRACT = (0, 2, 3, 4)
# ...and the only one a lane may carry: a lane IS the criterion's command, and the transcript's claim is that
# it succeeded. Review M1 measured that the contract row accepted 0/2/3/4 everywhere, so a record of a gate
# that refused itself rendered as a passing reproduction.
LANE_RC = (0,)
PLANT_NOTE = "PLANT DID NOT LAND"
RESTORE_OK = "restored byte-identical"


class TranscriptRefusal(ValueError):
    """The record is not something a published transcript may be built from."""


def read_record(path: Path) -> dict:
    """`{dotted.key: value}` from the runner's TSV."""
    flat = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            raise TranscriptRefusal("record line without a value: %r" % line)
        flat[parts[0]] = parts[1]
    return flat


def _step(flat: dict, prefix: str, expected=CONTRACT) -> dict:
    """One recorded command: its label, its exit code, and the line the reader checks.

    The exit-code contract lives HERE, not only downstream in `tests/test_g5_transcript.py`. The reason is
    the shape of the failure this round was called for: a renderer that prints any `\\d+` it is handed lets a
    record of an escaping rc 1 become a tracked file, and the test that notices runs after the overwrite --
    the transcript that would explain the refusal is then in a temp directory nobody references. Refusing to
    render makes the document un-writable instead of un-green.
    """
    missing = [key for key in ("%s.command" % prefix, "%s.rc" % prefix, "%s.output" % prefix)
               if key not in flat]
    if missing:
        raise TranscriptRefusal("the record has no %s -- the run did not complete that step" % missing[0])
    rc = flat["%s.rc" % prefix]
    if not re.fullmatch(r"\d+", rc):
        raise TranscriptRefusal("%s.rc is %r, not an exit code" % (prefix, rc))
    code = int(rc)
    if code not in expected:
        why = ("a lane is the criterion's own command and the transcript claims it exited 0"
               if expected is LANE_RC else
               "the documented contract is 0/2/3/4, and a code outside it is an escape rather than a result")
        raise TranscriptRefusal("%s.rc is %d, which this record may not publish: %s" % (prefix, code, why))
    return {"command": flat["%s.command" % prefix], "rc": code, "output": flat["%s.output" % prefix],
            "restored": flat.get("%s.restored" % prefix), "note": flat.get("%s.note" % prefix)}


def _falsification(flat: dict, prefix: str) -> dict:
    """One planted defect, with the two receipts that make it evidence rather than a description.

    *It fired.* `cmp -s backup target` after the plant is the runner's own check that the bytes the plant
    aims at actually changed; a `sed` whose pattern no longer matches, or a heredoc that raised, used to
    record `rc=0` and publish a falsification that falsified nothing (review M6). The note is refused here.

    *It came back.* The restore line is required, must report `restored byte-identical`, and must name the
    file the record says was planted at. Review M5 measured the emitter printing a blanket "each file is
    restored byte-identically" from a template while the receipts arrived through `.get`: an interrupted run
    published the promise with no evidence behind it.
    """
    step = _step(flat, prefix)
    note = step["note"]
    if note and PLANT_NOTE in note:
        raise TranscriptRefusal("%s: %s -- a defect that never moved the bytes it was aimed at is not a "
                                "falsification, and this transcript may not print one as evidence"
                                % (PLANT_NOTE, note))
    target = flat.get("%s.target" % prefix)
    if not target:
        raise TranscriptRefusal("%s.target is missing -- the runner planted a defect at a file the record "
                                "does not name, so no downstream row can check that the file came back"
                                % prefix)
    receipt = step["restored"]
    if not receipt:
        raise TranscriptRefusal("%s.restored is missing -- the plant at %s has no restore receipt, so the "
                                "transcript cannot say the file came back" % (prefix, target))
    if "RESTORE FAILED" in receipt:
        raise TranscriptRefusal("%s.restored reports %r: the export is left tampered, and a transcript of a "
                                "tampered export is not a reproduction of anything" % (prefix, receipt))
    if RESTORE_OK not in receipt:
        raise TranscriptRefusal("%s.restored is %r, which reports neither %s nor RESTORE FAILED -- the "
                                "emitter renders receipts that state the byte-for-byte return, nothing less"
                                % (prefix, receipt, RESTORE_OK))
    if target not in receipt:
        raise TranscriptRefusal("%s.restored names no file the record can check it against: the receipt is %r"
                                " and the plant was at %s" % (prefix, receipt, target))
    step["target"] = target
    return step


def _add(lines: list, label: str, value) -> None:
    """Append `- label: value`, or append nothing: a missing value deletes the sentence, not prints None."""
    if value not in (None, ""):
        lines.append("- %s: %s" % (label, value))


def render(flat: dict) -> str:
    """The document, from the record's own keys, in the order a reader checks a claim."""
    if "commit" not in flat:
        raise TranscriptRefusal("the record names no commit, so `from a commit` would be rhetoric")
    digest = flat.get("env.digest")
    if not digest or not HEX64.fullmatch(digest):
        raise TranscriptRefusal(
            "the record carries no 64-hex protocol digest (found %r). Without a digest the RUN recorded, the"
            " transcript cannot be tested for staleness against the tree it describes" % digest)

    lines = [
        "# G5: the reproduction transcript",
        "",
        "Produced from commit `%s` by `bash tools/g5_export.sh`, which unpacks a `git archive` of that"
        % flat["commit"],
        "commit and runs the gate inside it. `tests/test_g5_transcript.py` parses this file. What it refuses,",
        "stated as the rows actually do it rather than as an intention:",
        "",
        "- a digest below that is not the digest of the `protocol.json` **at the commit named above**, read",
        "  out of the object database with `git show`. It is deliberately NOT compared with the reader's tree:",
        "  a transcript of commit X is a record about X, and demanding today's digest would turn every honest",
        "  re-freeze into a red test. The row that speaks to currency can only say what is true of it --",
        "  `test_the_transcript_describes_a_commit_this_branch_can_reach` requires the named commit to be an",
        "  ancestor of the reader's tip, and `test_the_transcript_names_a_commit_that_exists_in_this_history`",
        "  requires it to exist at all, so a transcript cannot be smuggled in from a branch that did not land.",
        "- a recorded exit code outside 0/2/3/4, or a lane that did not exit 0. Both are refused by the",
        "  emitter itself, before a file exists, because a document that published an escape and then went",
        "  red downstream is still a document that was committed.",
        "- a lane whose two counts disagree, or two lanes whose denominators do not differ by exactly the",
        "  comparisons only a corpus can make -- one per `SOURCE.json` digest in `data/inventory.md.json`",
        "  plus one per snapshot key outside `cli.SNAPSHOT_MACHINE_KEYS`. The row derives that number from",
        "  the committed snapshot; it is not allowed to remember it.",
        "- plant blocks that do not carry four distinct outcomes, a plant whose restore receipt is missing,",
        "  reports failure, or names a file other than its own, and a plant recorded as not having landed.",
        "- a single line naming a real path, in either of the shapes the guards hunt. `tools/g5_export.sh`",
        "  masks on the way in and `main` below refuses on the way out; the tracked-tree guard in",
        "  `tests/test_cli.py` and `test_the_recorder_files_themselves_carry_no_path_shape` are the two",
        "  witnesses, the second because a file git does not yet track is a file the first never scanned.",
        "",
        "The scratch directory the export was unpacked into is written as `%s` throughout. A transcript's" % MASK,
        "most likely content is the path of the directory it ran in, and this file is tracked; the emitter",
        "refuses the document rather than redacting it after the fact.",
        "",
        "## The environment the run asked about",
        "",
    ]
    _add(lines, "`%s/.git` exists" % MASK, flat.get("env.git_dir"))
    _add(lines, "torch importable", flat.get("env.torch"))
    _add(lines, "transformers importable", flat.get("env.transformers"))
    _add(lines, "answering interpreter", flat.get("env.prefix"))
    _add(lines, "toolchain", flat.get("env.toolchain"))
    _add(lines, "network", flat.get("env.network"))
    _add(lines, "offline flags", flat.get("env.offline_flags"))
    _add(lines, "tracked-file manifest", flat.get("env.tracked_files"))
    _add(lines, "protocol digest", "`%s`" % digest)
    lines += [
        "",
        "`torch importable` and `transformers importable` are answered by the export's own interpreter, and",
        "the line above names which interpreter answered so that a reader can ask a different one. What this",
        "document records is the answer this run measured at the prefix it names: no second interpreter was",
        "asked here, so nothing is claimed about what one would say. The network line records a fetch that",
        "was attempted and had to fail -- an assertion that never tries the network is not a proof of absence.",
        "",
        "Scope of the no-network claim, stated because the run itself does not prove it: it covers the gate",
        "steps -- `verify` and the %d falsifications -- which reach no network and are run with" % len(FALSIFICATIONS),
        "`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. The dependency install that precedes them reads the",
        "package registry like any `uv sync` does, and this transcript does not claim otherwise. G5's",
        "criterion is about what a published number needs to be re-derived; provisioning is a different act.",
        "",
        "## The lanes",
        "",
        "Both run inside the export and both answer 0 -- the emitter refuses a transcript whose lane did not,",
        "because a refusal is not a reproduction -- and each has its own denominator. They are not two speeds",
        "of one gate: the corpus-present lane recomputes the upstream `SOURCE.json` digests and the inventory",
        "snapshot that the corpus-absent lane can only transcribe, and no runner can close that gap, because",
        "the corpus is not a committed file. CI runs this same command at every push, in both of its jobs:",
        "`offline` and `cross-libc-verify` -- the second a matrix over ubuntu and macOS, so three job",
        "instances on two libc families each print the corpus-absent line below. No run id is quoted here:",
        "a run belongs to the commit that pushed it, and this document names a different commit above. The",
        "workflow's own shape is policed by `tests/test_ci_workflow.py`, which is also where the run-level",
        "log evidence is described rather than restated.",
        "",
    ]
    lane_steps = [_step(flat, prefix, LANE_RC) for prefix in STEPS]
    for step in lane_steps:
        lines += ["```", "$ %s" % step["command"], "rc=%d  %s" % (step["rc"], step["output"]), "```", ""]

    plants = [_falsification(flat, prefix) for prefix in FALSIFICATIONS]
    outcomes = [(s["rc"], s["output"].split(" -- ")[0].strip()) for s in plants]
    if len(set(outcomes)) != len(outcomes):
        raise TranscriptRefusal(
            "two planted defects answered with the same code and the same first clause (%r): four plants that"
            " cannot be told apart are not four checks, and this transcript would publish one symptom as the"
            " evidence for four -- the run before this one did exactly that, with plant 3 reporting plant 1's"
            " rubric error" % (next(o for o in outcomes if outcomes.count(o) > 1),))
    restored = sum(1 for s in plants if s["restored"] and RESTORE_OK in s["restored"])
    lines += [
        "## The falsifications",
        "",
        "A reproduction that cannot fail is not evidence, so %d defects are planted inside the export and"
        % len(FALSIFICATIONS),
        "the gate is run again. %d of %d files came back byte-identically, checked with `cmp` against the"
        % (restored, len(FALSIFICATIONS)),
        "backup each plant took first: the numerator counts the receipts printed under the blocks below, and",
        "a plant that did not land, or has no receipt naming its own file, or reports a failed restore, is a",
        "refusal rather than a smaller number under a sentence that says nothing went wrong.",
        "",
    ]
    for step in plants:
        lines += ["```", "$ %s" % step["command"], "rc=%d  %s" % (step["rc"], step["output"]), "```", ""]
        lines.append("   %s" % step["restored"])
        if step["note"]:
            lines.append("   %s" % step["note"])
        lines.append("")

    lines += [
        "## What this transcript does not show",
        "",
        "- It does not show the corpus-present lane on somebody else's machine. The archive is not a committed",
        "  file, so that lane stays a local obligation run before a push; this document is where its numbers",
        "  become a published record instead of terminal scrollback.",
        "- It does not re-run a model. Nothing here scores a case: the records are committed bytes, which is",
        "  the whole reason a no-GPU claim is checkable at all.",
        "- It is a transcript of ONE revision, and it is not kept current by anything here. The digest above",
        "  is the digest of the commit named above -- so a later re-freeze does not redden this file, and a",
        "  reader comparing it against their own tree will see a different number by design. The two rows on",
        "  the named commit can say only that it exists and that this branch can reach it; currency stays a",
        "  sentence a reader reads, not an assertion a test can make.",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv=None) -> int:
    """Build the transcript, or refuse with exit 2 and write nothing.

    The refusal is answered here rather than at the `__main__` seam because a refusal this file makes -- a
    record that is incomplete, or a document that still names a machine -- is exactly the kind of deliberate
    refusal the repository's other tools answer with exit 2. Anything that escapes as an exception would be a
    traceback where a caller expected a code.
    """
    parser = argparse.ArgumentParser(prog="tools/g5_transcript.py",
                                     description="Build docs/G5.md from one export run's record.")
    parser.add_argument("--record", required=True, help="the masked TSV `tools/g5_export.sh` wrote")
    parser.add_argument("--out", default="docs/G5.md", help="where to write the transcript")
    args = parser.parse_args(argv)

    try:
        text = render(read_record(Path(args.record)))
    except (TranscriptRefusal, OSError, ValueError) as exc:
        print("tools/g5_transcript.py: %s" % exc, file=sys.stderr)
        return 2
    offenders = [(i, line) for i, line in enumerate(text.splitlines(), 1) if LEAK_RX.search(line)]
    if offenders:
        print("tools/g5_transcript.py: the rendered transcript still names a machine path at %s -- "
              "refusing to write %s" % (offenders[:2], args.out), file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print("wrote %s (%d lines)" % (out, text.count("\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
