#!/usr/bin/env python3
"""Turn one export run's record into `docs/G5.md`, with the machine's paths removed.

    python3 tools/g5_transcript.py --record <run.tsv> --out docs/G5.md

The transcript is generated, never typed, for the same reason `docs/RESULTS.md` is: a hand-copied exit code is
a claim about a run rather than a record of one. `tools/g5_export.sh` produces the record -- one masked
`key<TAB>value` line per fact -- and this file decides what a reader sees.

Two rules the emitter exists to enforce.

*Nothing recomputed.* The protocol digest printed here is the value the RUN recorded, not the value this
process could calculate now. Recomputing it would make `tests/test_g5_transcript.py`'s staleness row unable to
fail: a transcript that always prints today's digest can never be caught describing an older freeze.

*No leak survives to a tracked file.* A transcript's most natural content is the path of the directory the run
happened in. `tools/g5_export.sh` masks it on the way into the record, and this file refuses to write any
document that still matches a machine-path shape -- including the `/var/folders/...` and `/private/tmp/...`
shapes the tracked-tree guard in `tests/test_cli.py` does not cover.
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


def _step(flat: dict, prefix: str) -> dict:
    """One recorded command: its label, its exit code, and the line the reader checks."""
    missing = [key for key in ("%s.command" % prefix, "%s.rc" % prefix, "%s.output" % prefix)
               if key not in flat]
    if missing:
        raise TranscriptRefusal("the record has no %s -- the run did not complete that step" % missing[0])
    rc = flat["%s.rc" % prefix]
    if not re.fullmatch(r"\d+", rc):
        raise TranscriptRefusal("%s.rc is %r, not an exit code" % (prefix, rc))
    return {"command": flat["%s.command" % prefix], "rc": int(rc), "output": flat["%s.output" % prefix],
            "restored": flat.get("%s.restored" % prefix), "note": flat.get("%s.note")}


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
        "commit and runs the gate inside it. `tests/test_g5_transcript.py` parses this file and refuses it",
        "if the digest below is not the digest of the `protocol.json` in the tree, if any recorded exit code",
        "falls outside 0/2/3/4, if a lane's two counts disagree, or if any line names a real path.",
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
        "the line above names which interpreter answered: the vendored tree's interpreter would answer",
        "differently, and that difference is the claim. The network line records a fetch that was attempted",
        "and had to fail -- an assertion that never tries the network is not a proof of absence.",
        "",
        "Scope of the no-network claim, stated because the run itself does not prove it: it covers the gate",
        "steps -- `verify` and the three falsifications -- which reach no network and are run with",
        "`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. The dependency install that precedes them reads the",
        "package registry like any `uv sync` does, and this transcript does not claim otherwise. G5's",
        "criterion is about what a published number needs to be re-derived; provisioning is a different act.",
        "",
        "## The lanes",
        "",
        "Both run inside the export, each with its own exit code and its own denominator. They are not two",
        "speeds of one gate: the corpus-present lane recomputes the upstream `SOURCE.json` digests and the",
        "inventory snapshot that the corpus-absent lane can only transcribe, and no runner can close that",
        "gap, because the corpus is not a committed file.",
        "",
    ]
    for prefix in STEPS:
        step = _step(flat, prefix)
        lines += ["```", "$ %s" % step["command"], "rc=%d  %s" % (step["rc"], step["output"]), "```", ""]

    lines += [
        "## The falsifications",
        "",
        "A reproduction that cannot fail is not evidence, so %d defects are planted inside the export and"
        % len(FALSIFICATIONS),
        "the gate is run again. Each file is restored byte-identically afterwards, and the restore is checked",
        "rather than assumed.",
        "",
    ]
    for prefix in FALSIFICATIONS:
        step = _step(flat, prefix)
        lines += ["```", "$ %s" % step["command"], "rc=%d  %s" % (step["rc"], step["output"]), "```", ""]
        if step["restored"]:
            lines.append("   %s" % step["restored"])
        if step["note"]:
            lines.append("   %s" % step["note"])
        if step["restored"] or step["note"]:
            lines.append("")

    lines += [
        "## What this transcript does not show",
        "",
        "- It does not show the corpus-present lane on somebody else's machine. The archive is not a committed",
        "  file, so that lane stays a local obligation run before a push; this document is where its numbers",
        "  become a published record instead of terminal scrollback.",
        "- It does not re-run a model. Nothing here scores a case: the records are committed bytes, which is",
        "  the whole reason a no-GPU claim is checkable at all.",
        "- It is a transcript of one revision. Re-freezing the protocol, or replacing a records file, makes the",
        "  digest above disagree with the tree, and `tests/test_g5_transcript.py` turns that into a red test",
        "  rather than a quietly stale document.",
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
