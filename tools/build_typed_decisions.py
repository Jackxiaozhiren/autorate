#!/usr/bin/env python3
"""Score-pinned typed-decisions export -> committed Records. Stdlib only, not on the test path, never in CI.

Two stages, and only the second one is this file.

Stage 1 (NOT this program, NOT this repository, NOT CI) turns one parquet shard of the pinned corpus into a
JSONL scoring export, one row per held-out decision, in the `laya` engine's own shape:

    uv run --with pyarrow --with torch --with transformers python3 tools/export_typed_decisions.py \
        --parquet all/test-00000-of-00001.parquet --out typed-decisions-export.jsonl

That command is written here as a statement of what produced the bytes this file reads; it is deliberately
outside CI, because a gate that needs `torch`, a checkpoint or a network is no longer the offline gate this
repository's G5 row claims (`pyproject.toml` runtime dependencies are `numpy` and nothing else). The engine
it runs is upstream's `research/scripts/bench_local.py`, copied verbatim for parity, against the cached
`convaiinnovations/laya` revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` with
`subfolder="typed-decisions"`.

Stage 2 (this file) is the build layer, and it owns everything that can be checked without a model:

* the digest of the export it was handed, against `data/typed_decisions_provenance.json`;
* the identity of the checkpoint that scored it -- the export names a cache DIRECTORY, which is a location on
  somebody's machine, and a location is not a committed fact; the build layer refuses a row whose path is
  not the pinned revision's snapshot and writes the revision instead;
* the Record contract itself (`autorate.records.Record.from_dict` validates every row before it is
  re-emitted, so a line that is not a decision never reaches a certificate);
* the canonical bytes of `data/records_typed_decisions_urgency.jsonl`.

Nothing here fetches, hashes a corpus, or imports `torch`/`pyarrow`. The pin is READ, never restated: the two
digests this tool compares against live in `data/typed_decisions_provenance.json` and nowhere else, which is
what makes a pinned digest a fact with one owner rather than a number that has to be edited in two places.

Exit codes, on the same axis every other producer in this tree draws: who named the path.

    0  the records file was written from a source the pin names
    2  a refusal about an argument: `--source` or `--pin` not readable, an existing `--out` without
       `--force`, an unwritable `--out`, a row the Record contract refuses
    4  a disagreement between the bytes and what this repository declares: the source's sha256 is not
       `pin.export.sha256`, a row's checkpoint path is not `pin.source.revision_used`, or the pin is not a
       JSON object carrying the fields this build reads

Nothing escapes as 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    # Script mode (`python3 tools/build_typed_decisions.py`) puts `tools/` on sys.path, not the repository's
    # `src`, so the Record contract would not resolve. The layout needs no lint exemption: the project's gate
    # selects E9,F63,F7,F82,F401,F811, and a module-level import below a path insert is not one of them.
    sys.path.insert(0, str(REPO / "src"))

from autorate.records import Record

EXIT_OK, EXIT_USAGE, EXIT_DRIFT = 0, 2, 4
PIN_FIELDS = ("source", "export", "records")
ROW_REQUIRED = ("id", "qtype", "backend", "repeat", "options", "probs")


class Refusal(Exception):
    """A refusal with its exit code attached, so `main` maps a class to a number and nothing escapes as 1."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_pin(path: Path) -> dict:
    """The pin as the mapping this build reads, or a refusal at 4: the pin is the publication's word."""
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(EXIT_USAGE, "%s: %s: %s -- nothing was written"
                      % (path, type(exc).__name__, exc)) from exc
    if not isinstance(doc, dict):
        raise Refusal(EXIT_DRIFT, "%s is a JSON %s, not the pin object this build reads"
                      % (path, type(doc).__name__))
    missing = sorted(field for field in PIN_FIELDS if not isinstance(doc.get(field), dict))
    if missing:
        raise Refusal(EXIT_DRIFT, "%s declares no readable %s block, so the identity of the bytes this tool "
                                  "would write has no owner" % (path, ", ".join(missing)))
    return doc


def checkpoint_revision(path_value, pinned: str) -> str:
    """The revision a scoring host's cache path stands for, or a refusal.

    The export row says `.../models--convaiinnovations--laya/snapshots/<sha>#typed-decisions`. The directory
    is a location on the machine that ran the model, and this repository publishes no location; the snapshot
    name IS the identity, so it is what survives. A path naming a different snapshot is refused rather than
    normalised, because a record whose model identity was quietly replaced would certify under a checkpoint
    nobody scored it with.
    """
    if not isinstance(path_value, str) or not path_value:
        raise Refusal(EXIT_DRIFT, "a source row carries no `meta.checkpoint` path to take the revision from")
    marker = "/snapshots/"
    if marker not in path_value:
        raise Refusal(EXIT_DRIFT, "the source row's checkpoint path %r has no %s segment, so this build "
                                  "cannot name the revision it scored the row with" % (path_value, marker))
    tail = path_value.split(marker, 1)[1]
    revision = tail.split("#", 1)[0].split("/", 1)[0]
    if revision != pinned:
        raise Refusal(EXIT_DRIFT, "the source row names checkpoint revision %r, which is not the revision "
                                  "the pin declares (%r): the records would be certified over a scoring run "
                                  "this repository did not pin" % (revision, pinned))
    return revision


def build_row(line: str, pinned_revision: str) -> str:
    """One export line as one canonical records line, validated by the contract it will be read with."""
    try:
        row = json.loads(line)
    except ValueError as exc:
        raise Refusal(EXIT_USAGE, "a source line is not JSON (%s)" % exc) from exc
    if not isinstance(row, dict):
        raise Refusal(EXIT_USAGE, "a source line is a JSON %s, not a decision" % type(row).__name__)
    absent = sorted(field for field in ROW_REQUIRED if field not in row)
    if absent:
        raise Refusal(EXIT_USAGE, "source record %r is missing %s" % (row.get("id"), absent))
    meta = dict(row.get("meta") or {})
    revision = checkpoint_revision(meta.pop("checkpoint", None), pinned_revision)
    meta["checkpoint_revision"] = revision
    row = dict(row, meta=meta)
    try:
        Record.from_dict(row)  # validation only: the bytes written are the source's own, re-emitted
    except (ValueError, TypeError, KeyError) as exc:
        raise Refusal(EXIT_USAGE, "source record %r is not a Record this repository can certify: %s"
                      % (row.get("id"), exc)) from exc
    return json.dumps(row, sort_keys=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools/build_typed_decisions.py",
                                     description="Build the published typed-decisions urgency records from a "
                                                 "pinned scoring export. Stdlib only; the export stage that "
                                                 "produces the input is documented in this file's docstring "
                                                 "and is deliberately outside CI.")
    parser.add_argument("--source", required=True,
                        help="the scoring export this build reads (its sha256 must be the pin's)")
    parser.add_argument("--pin", default="data/typed_decisions_provenance.json",
                        help="the corpus identity file that owns the digest (default the published pin)")
    parser.add_argument("--out", default="data/records_typed_decisions_urgency.jsonl",
                        help="where to write the records file")
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    args = parser.parse_args(argv)

    source, pin_path, out = Path(args.source), Path(args.pin), Path(args.out)
    try:
        if not source.is_file():
            raise Refusal(EXIT_USAGE, "--source %s does not exist, so nothing can be built from it" % source)
        pin = read_pin(pin_path)
        if out.exists() and not args.force:
            raise Refusal(EXIT_USAGE, "%s already exists; pass --force to replace it -- nothing was written"
                          % out)
        stated = pin["export"].get("sha256")
        actual = sha256_of(source)
        if actual != stated:
            raise Refusal(EXIT_DRIFT, "%s has sha256 %s, which is not the export %s pins (%s): this build "
                                      "refuses to write published records from bytes the publication does "
                                      "not identify. Nothing was written"
                          % (source, actual, pin_path, stated))
        revision = pin["source"].get("revision_used")
        if not isinstance(revision, str) or not revision:
            raise Refusal(EXIT_DRIFT, "%s declares no `source.revision_used`, so no row's checkpoint path "
                                      "could be resolved to an identity" % pin_path)
        built = [build_row(line, revision) for line in
                 source.read_text().splitlines() if line.strip()]
        payload = "".join(line + "\n" for line in built)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.parent / (out.name + ".tmp")
            tmp.write_text(payload)
            tmp.replace(out)
        except OSError as exc:
            raise Refusal(EXIT_USAGE, "%s: %s: %s -- nothing was written"
                          % (out, type(exc).__name__, exc)) from exc
    except Refusal as refusal:
        print("tools/build_typed_decisions.py: %s" % refusal.message, file=sys.stderr)
        return refusal.code
    print("wrote %s (%d records)" % (out, len(built)))
    print("  source %s sha256 %s (pinned by %s)" % (source, actual, pin_path))
    print("  checkpoint revision %s -- the scoring host's cache path is not published" % revision)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
