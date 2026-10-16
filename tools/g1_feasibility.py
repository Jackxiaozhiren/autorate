#!/usr/bin/env python3
"""G1's feasibility ceiling, published: which automated size could certify at all, at the freeze's rubric.

    uv run --frozen python3 tools/g1_feasibility.py --out data/g1_feasibility.json \\
        --doc docs/FEASIBILITY.md --force

Spec §2's G1 asks for at least three decision tasks certified at `autorate(alpha)` for the freeze's
published alpha. This tree scores the decision tasks its certificates name and certifies none, and
the resplit experiment shows no seeded split certifying for any of them. The stronger statement -- that **no automated size certifies on
this evidence base at this budget** -- lived only in an untracked scratch probe, and this project has
already ruled that a simulation performed and deleted is not evidence (`docs/G5.md` is that ruling's
artefact). This file turns the ceiling into committed bytes -- `data/g1_feasibility.json`, with
`docs/FEASIBILITY.md` rendered from them -- that `autorate verify` re-derives in both lanes.

Three rules shape it.

*No arithmetic lives here.* The bounds belong to `src/autorate/tails.py` (`clopper_pearson_upper`,
`bound_width`, `n_feasible`), the precision a published bound answers at belongs to
`certificate.canonicalise_bound`, and the assembly of the ladder and the task rows belongs to
`report.build_g1_feasibility` -- the same function `rederive_g1_feasibility` calls, which is what makes
the committed file a re-derivation rather than a transcription. The rubric is read from the loaded
protocol the way every other arm reads it; no budget is typed into this file, and the row in
`tests/test_g1_feasibility.py` that polices that scans these very bytes for a re-typed literal.

*The inputs are committed bytes.* The five published certificates, the record files the MASSIVE ones
were certified from, the inventory snapshot and the MASSIVE pin: every read goes through
`report.load_published`, so a defect in a table-declared artefact is the named refusal at exit 4 --
never a traceback, and never an attribution to an operator who typed nothing.

*Exit codes are this tool's contract, and the axis is who named the path.* **0** when the published
ceiling shows G1 satisfiable -- at least three scored tasks certifying at their own sizes. **3** when
it does not: on this evidence base that is the answer the arithmetic gives, a refusal is a result, and
the artefact and the document are written and printed before the code says so. **2** for the refusals
about an argument the operator typed: an existing `--out` without `--force`, a `--doc` off the paths
the publication declares, a `--protocol` path that is not there, an unwritable `--out`. **4** for a
defect in the bytes at a path this build declares, or a tripped invariant of our own arithmetic.
Nothing escapes at 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autorate import report
from autorate.cli import (EXIT_CERTIFIED, EXIT_DRIFT, EXIT_NOT_CERTIFIABLE, EXIT_USAGE, PROTOCOL_JSON)
from autorate.protocol import G1_MIN_CERTIFIED_TASKS, load_protocol

ARTEFACT = report.G1_FEASIBILITY_JSON
DOC_PATH = str(report.G1_FEASIBILITY_MD)
PRODUCER = report.G1_FEASIBILITY_PRODUCER


def resolve_rubric(stated):
    """The freeze's rubric, resolved on the who-named-the-path axis the whole CLI draws.

    A `--protocol` the operator typed is theirs: missing there is usage (2). The default is the
    table-declared `cli.PROTOCOL_JSON`, read through `load_published`: missing or unreadable there is
    the checkout's named refusal (4), because no argument selected that path and no argument can
    repair it.
    """
    if stated:
        path = Path(stated)
        if not path.is_file():
            raise ValueError("--protocol %s does not exist" % path)
        return load_protocol(path).rubric
    return report.load_published(PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol).rubric


def ceiling_summary(doc: dict) -> tuple:
    """`(scored_rows, certifying_tasks)` read off the artefact's own rows -- the exit code's only inputs.

    A task counts as certifying exactly when its published verdict is `feasible: True`; corpora carried
    as refusals (`feasible: null`, the `typed_decisions` shape) are scored but cannot certify, and the
    ceiling says nothing otherwise -- the row already names what is missing.
    """
    scored = [row for row in doc["rows"] if row.get("table") != "inventory.corpus_options"]
    certifying = sorted(str(row.get("task")) for row in doc["rows"] if row.get("feasible") is True)
    return scored, certifying


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PRODUCER, description="Publish G1's feasibility ceiling.")
    parser.add_argument("--out", default=ARTEFACT, help="where to write the artefact (default %s)" % ARTEFACT)
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    parser.add_argument("--doc", help="also write the derived document (the published `docs/FEASIBILITY.md`)")
    parser.add_argument("--protocol", default=None,
                        help="which freeze to read the rubric from (default %s, read as a published artefact)"
                             % PROTOCOL_JSON)
    args = parser.parse_args(argv)

    out = Path(args.out)
    if out.exists() and not args.force:
        print("%s: %s already exists; pass --force to replace it" % (PRODUCER, out), file=sys.stderr)
        return EXIT_USAGE
    # The document quotes the ceiling at its declared artefact path, so it may only be written by the
    # run that produces that artefact, and only at the paths the publication declares -- `language_slices`'
    # rule, inherited: a document naming the published paths while carrying figures from somebody else's
    # bytes is a misattribution, and a path the operator typed could land in a tracked file.
    if args.doc is not None and (str(args.out) != ARTEFACT or str(args.doc) != DOC_PATH):
        print("%s: --doc publishes %s, which quotes the artefact at its declared path, so it requires "
              "--out %s --doc %s (this run named --out %s --doc %s). Nothing was written"
              % (PRODUCER, DOC_PATH, ARTEFACT, DOC_PATH, args.out, args.doc), file=sys.stderr)
        return EXIT_USAGE
    try:
        rubric = resolve_rubric(args.protocol)
        doc = report.build_g1_feasibility(rubric)
    except (report.PublishedArtefactUnavailable, ArithmeticError) as exc:
        # 4, not 2: both classes complain about bytes at a path this build's tables declare (or about
        # our own arithmetic), and nothing an operator typed selects or repairs them. Naming the two
        # kinds apart is what keeps a tripped invariant from reading as a missing file.
        kind = ("PUBLISHED ARTEFACT UNAVAILABLE"
                if isinstance(exc, report.PublishedArtefactUnavailable) else "INVARIANT")
        print("%s: %s: %s -- nothing was written" % (PRODUCER, kind, exc), file=sys.stderr)
        return EXIT_DRIFT
    except (OSError, ValueError) as exc:
        # 2: a `--protocol` path the operator named that is not there, and an `--out` this run cannot
        # write, are both "an input this command was handed is wrong" -- README's own words for the
        # code, covering the supplied default as well as the typed one.
        print("%s: %s: %s -- nothing was written" % (PRODUCER, type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        if args.doc is not None:
            Path(args.doc).write_text(report.render_g1_feasibility(doc))
    except OSError as exc:
        print("%s: %s -- nothing further was written" % (PRODUCER, exc), file=sys.stderr)
        return EXIT_USAGE

    scored, certifying = ceiling_summary(doc)
    rubric_block = doc["rubric"]
    print("wrote %s" % out)
    print("  rubric: alpha=%s beta=%s delta=%s method `%s`, seed %s"
          % (rubric_block["alpha"], rubric_block["beta"], rubric_block["delta"],
             rubric_block["method"], rubric_block["seed"]))
    print("  ladder: %d sizes; tasks read from certificates: %d; corpora carried as refusals: %d"
          % (len(doc["reference"]), len(scored), len(doc["rows"]) - len(scored)))
    for row in scored:
        print("  %s: k_max records=%s cases=%s; oracle ceiling records=%s cases=%s"
              % (row["task"], row["k_max_records"], row["k_max_cases"],
                 row["oracle_ceiling_records"], row["oracle_ceiling_cases"]))
    if len(certifying) >= G1_MIN_CERTIFIED_TASKS:
        print("  %d tasks certify at their published sizes: %s -- G1's bar (%d) is met on this evidence"
              % (len(certifying), ", ".join(certifying), G1_MIN_CERTIFIED_TASKS))
        return EXIT_CERTIFIED
    print("  %d of %d scored tasks certify at their published sizes (G1 asks for %d): the ceiling above "
          "is the size statement beside that refusal, and `claim G1 = not_certifiable` stays"
          % (len(certifying), len(scored), G1_MIN_CERTIFIED_TASKS))
    return EXIT_NOT_CERTIFIABLE


if __name__ == "__main__":
    sys.exit(main())
