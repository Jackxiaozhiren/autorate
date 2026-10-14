#!/usr/bin/env python3
"""G4's worst-slice run, published: the language slices this repository scored, certified together.

    uv run --frozen python3 tools/language_slices.py --out data/slices_language.json

The criterion asks for a behaviour -- with a simultaneous correction over the slices, the worst slice must
REFUSE, and the pooled bound must not be allowed to average that refusal away. The CLI has printed that run
since `--groups` landed, and printed it into terminal scrollback: nothing to re-derive, nothing to compare,
no document a reader can check. This file turns one run into an artefact, and `autorate verify` recomputes
it from the same three committed record files the run names inside itself.

Three rules shape it.

*No new evidence.* The inputs are the three published MASSIVE record files, read through `report.load_records`
-- the same reader the published certificates use, so the doubles certified here are the doubles those
certificates were built from. No corpus, no model, no cache: the run costs seconds and belongs in the gate.

*The slice key is the producer's declaration, never a guess.* `groups.py` refuses to condition on a key no
row states, and the rows here state `slices.language`. The filename is not the evidence: a row whose
`case_id` names a different language than its own `slices` does is two subjects in one row, and which slice
it lands in would depend on which field the reader believes. `split_records.py` proves that claim for the
split direction; `check_rows` inherits it here, and also proves the id set does not collide across files --
a repeated id would be one observation counted twice, which is exactly how a per-slice denominator inflates.

*Exit codes are the tool's contract.* 0 when the document is written (a refusing run is a legitimate
publication -- that is what G4 asked for), 2 for the refusals above and for an existing `--out` without
`--force`. Nothing escapes un-mapped: the refusals are this file's own exception types.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autorate import report
from autorate.certificate import ALPHA, BETA, DELTA, METHOD, SEED
from autorate.certify_choice import certify_choice

ARTEFACT = report.SLICE_JSON
PRODUCER = "tools/language_slices.py"


class SliceInputRefusal(ValueError):
    """A declared input is missing, collides, or describes its own row twice.

    A `ValueError` so an operator sees a usage refusal rather than a traceback, and so the reason names the
    row: "one of the inputs was wrong" is not actionable when the file holds 2,974 rows.
    """


def declared_inputs(directory=None) -> list:
    """The three files this run is a function of, in the order the artefact names them.

    With no `directory`, the paths are the repo-relative strings the publication declares, so what the
    artefact records as an input is what `verify` re-reads. A `directory` is the tool-mode view: the same
    declared names looked up under one place, which is how the missing-input refusal is testable at all.
    """
    if directory is None:
        return [Path(rel) for rel in sorted(report.SLICE_RECORDS)]
    base = Path(directory)
    return [base / Path(rel).name for rel in sorted(report.SLICE_RECORDS)]


def refuse_missing_inputs(directory=None) -> tuple:
    """`(2, message)` naming every declared input that is not there, or `(0, "")`.

    Checked before any certifying, because certifying 2 of 3 languages and publishing it as a language-slice
    run would state a population the artefact describes differently than it is. The message names only the
    absent files: a reader who is told three files are required and that one is missing has the whole fix.
    """
    missing = [str(path) for path in declared_inputs(directory) if not path.is_file()]
    if not missing:
        return 0, ""
    where = " under %s" % directory if directory is not None else ""
    return 2, ("%s declares %d input file(s) this run needs and %s cannot be found: %s. Nothing was written"
               % (PRODUCER, len(report.SLICE_RECORDS), where, ", ".join(missing)))


def check_rows(per_file) -> None:
    """Refuse a batch whose rows disagree with themselves, or whose ids are not one observation each.

    `per_file` is `[(path, raw_row_mapping), ...]` in the order the run concatenates them. Two claims, both
    re-derived from the bytes rather than from the filename: a row's `case_id` language segment must equal
    its declared `slices.language`, and no `id` may appear twice across the batch.
    """
    seen = {}
    for path, rows in per_file:
        for row in rows:
            case_id = str(row.get("case_id", ""))
            parts = case_id.split("/")
            stated = (row.get("slices") or {}).get(report.SLICE_GROUP_KEY)
            if len(parts) >= 2 and stated is not None and parts[1] != stated:
                raise SliceInputRefusal(
                    "%s: row %r states case_id %r, whose language segment is %r, but declares "
                    "slices.%s = %r -- one row with two subjects, and which slice it lands in would "
                    "depend on which field this tool believed"
                    % (path, row.get("id"), case_id, parts[1], report.SLICE_GROUP_KEY, stated))
            row_id = row.get("id")
            if row_id in seen:
                raise SliceInputRefusal(
                    "%s: id %r also appears in %s -- a repeated id is one observation counted twice, and "
                    "a per-slice denominator built from it would claim more independent cases than the "
                    "corpus holds" % (path, row_id, seen[row_id]))
            seen[row_id] = str(path)


def build_document() -> dict:
    """The run, as the mapping the artefact publishes: budgets, inputs, and the certification itself."""
    rubric = {"alpha": ALPHA, "beta": BETA, "delta": DELTA, "method": METHOD, "seed": SEED}
    raw = []
    for path in declared_inputs():
        if not path.is_file():
            raise SliceInputRefusal("%s: declared input is missing" % path)
        try:
            lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except ValueError as exc:                     # JSONDecodeError is a ValueError, and so is Record's
            raise SliceInputRefusal("%s: a line is not a readable Record (%s)" % (path, exc)) from exc
        raw.append((path, lines))
    check_rows(raw)
    # The records and the per-file rows/digests the artefact publishes come from the same function the gate
    # re-reads, so `inputs[].rows` has one owner. Two definitions of it -- every JSON line here, the backend's
    # Records there -- agree only while every committed row happens to be that backend, and "happens to" is
    # not a contract.
    records, inputs = report.slice_inputs()
    run = certify_choice(records, groups=[report.SLICE_GROUP_KEY], **rubric).to_dict()
    return {
        "backend": report.SLICE_BACKEND,
        "group_key": report.SLICE_GROUP_KEY,
        "inputs": inputs,
        "producer": PRODUCER,
        "rubric": rubric,
        "run": run,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PRODUCER, description="Publish G4's language-slice run.")
    parser.add_argument("--out", default=ARTEFACT, help="where to write the artefact (default %s)" % ARTEFACT)
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    parser.add_argument("--doc", help="also write the derived document (the published `docs/SLICES.md`)")
    args = parser.parse_args(argv)

    out = Path(args.out)
    if out.exists() and not args.force:
        print("%s: %s already exists; pass --force to replace it" % (PRODUCER, out), file=sys.stderr)
        return 2
    # The document quotes the artefact at its published path, so it may only be written by the run that
    # produces that artefact, and only at the paths the publication table declares -- the same rule the
    # severity `--doc` guard enforces: a document naming the published paths while carrying figures from
    # somebody else's records is a misattribution, and a path the operator typed could land in a tracked file.
    if args.doc is not None and (str(args.out) != ARTEFACT or str(args.doc) != str(report.SLICE_MD)):
        print("%s: --doc publishes %s, which quotes the artefact at its declared path, so it requires "
              "--out %s --doc %s (this run named --out %s --doc %s). Nothing was written"
              % (PRODUCER, report.SLICE_MD, ARTEFACT, report.SLICE_MD, args.out, args.doc), file=sys.stderr)
        return 2
    code, message = refuse_missing_inputs()
    if code:
        print(message, file=sys.stderr)
        return code
    try:
        doc = build_document()
    except (SliceInputRefusal, report.PublishedArtefactUnavailable) as exc:
        print("%s: %s" % (PRODUCER, exc), file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    if args.doc is not None:
        Path(args.doc).write_text(report.render_slices(doc))
    run = doc["run"]
    print("wrote %s" % out)
    print("  slices over %r: %d groups, %d claims per group, corrected alpha=%s delta=%s, joint level %s"
          % (doc["group_key"], run["n_groups"], run["n_claims"],
             run["corrected_alpha"], run["corrected_delta"], run["level"]))
    for group in sorted(run["per_group"]):
        cert = run["per_group"][group]
        print("  slice %s (n=%s cases): %s -- %s"
              % (group, cert["n_cal"] + cert["n_eval"],
                 "CERTIFIED" if cert["feasible"] else "NOT CERTIFIED", cert["reason"]))
    print("  worst slice: %s; any slice refused: %s; the run certifies: %s"
          % (run["thinnest"], run["any_slice_refused"], run["feasible"]))
    print("  pooled (marginal) certificate published beside them: feasible=%s reason=%s"
          % (run["pooled"]["feasible"], run["pooled"]["reason"]))
    print("  refused by the size floor: %d" % len(run["n_min_violations"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
