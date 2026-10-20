#!/usr/bin/env python3
"""G3's contrast, published: one population, the multiclass set gate refusing it, the one-sided gate certifying.

    uv run --frozen python3 tools/g3_contrast.py --out data/g3_contrast.json \\
        --doc docs/G3.md --force

Spec §2 states G3 as ">=1 ordinal guarantee that multiclass CP cannot express" and measures it by the
negative test -- if vanilla multiclass set CP reproduces the one-sided bound, the criterion fails. Both
halves of the answer lived only inside `tests/test_g3_contrast.py`: computed, asserted, printed, and
published nowhere. That is a specific kind of hole, because a set-gate REFUSAL writes no certificate, so
before this file the repository had no committed bytes at all recording that its multiclass gate publishes
nothing on the very population its severity certificate is built from. G1's ceiling (#97), G4's `delta_hat`
(#107) and the drift envelope (#110) each moved from "a test checks it" to "an artefact publishes it and the
gate re-derives it" first; this is the same widening for G3.

Three rules shape it.

*No arithmetic and no prose lives here.* `report.build_g3_contrast` calls both certifiers and assembles the
rows -- the same function `report.rederive_g3_contrast` calls, which is what makes the committed file a
re-derivation rather than a transcription -- and `report.render_g3_contrast` owns the document's sentences.
This file resolves the freeze, refuses an unsafe run, and writes bytes.

*The population is not a knob.* `report.SEVERITY_CERTS` names the records file, and the artefact's identity
IS that population: a run that pointed `--records` somewhere else would put another sample's figures under
the path that promises this one, which is why it is refused at 2 instead of honoured. The one exception is
honest exploration, so `--records` is accepted when it repeats the published path.

*Exit codes, on the axis the whole CLI draws: who named the path.* **0** when both gates answered and the
artefact (and `--doc` document) were written. **2** for a refusal about an argument: a foreign `--records`,
an existing `--out` without `--force`, a `--doc` off the paths the publication declares, a `--protocol` that
is not there, an unwritable `--out`. **4** for a defect in the bytes at a path this build declares -- the
committed certificate, records file, or protocol the reads go through `load_published` for. **3** is not
used: this artefact publishes a measurement, not a verdict, and `claims.G3.status` stays `not_measured`
because the criterion is worded wider than the contrast the committed records can support. Nothing escapes
at 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from autorate import report
from autorate.cli import (EXIT_DRIFT, EXIT_USAGE, G3_CONTRAST_RUBRIC_FIELDS, PROTOCOL_JSON)
from autorate.protocol import load_protocol

ARTEFACT = report.G3_CONTRAST_JSON
DOC_PATH = str(report.G3_CONTRAST_MD)
PRODUCER = report.G3_CONTRAST_PRODUCER
RECORDS = report.SEVERITY_CERTS[report.SEVERITY_LABEL][0]


def resolve_protocol(stated):
    """The freeze, resolved on the who-named-the-path axis: a typed `--protocol` that is missing is usage (2),
    the table-declared default that is missing is the checkout's refusal (4).

    `tools/g1_feasibility.py` states the same rule one layer up, for the rubric it returns. The two are
    separate functions rather than one shared helper because the axis they enforce lives in each tool's own
    argument shape; the rule's owner for the PUBLISHED budget is `certificate.PUBLISHED_RUBRIC`, and the arm
    that compares this artefact's rubric against that is `verify`, not this file."""
    if stated:
        path = Path(stated)
        if not path.is_file():
            raise ValueError("--protocol %s does not exist" % path)
        return load_protocol(path)
    return report.load_published(PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PRODUCER,
                                     description="Publish G3's ordinal contrast (the set gate's refusal "
                                                 "beside the one-sided certificate, on one committed "
                                                 "population).")
    parser.add_argument("--out", default=ARTEFACT, help="where to write the artefact (default %s)" % ARTEFACT)
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    parser.add_argument("--doc", help="also write the derived document (the published %s)" % DOC_PATH)
    parser.add_argument("--records", default=RECORDS,
                        help="only the published ordinal population is allowed here: %s" % RECORDS)
    parser.add_argument("--protocol", default=None,
                        help="which freeze to read the rubric from (default %s, read as a published artefact)"
                             % PROTOCOL_JSON)
    args = parser.parse_args(argv)

    # Checked before anything is read, measured or written, because the refusal's own sentence ends "nothing
    # was written".
    if str(args.records) != RECORDS:
        print("%s: --records %s is refused. %s publishes the contrast over the population "
              "report.SEVERITY_CERTS declares -- %s -- and an artefact naming that path while carrying "
              "another sample's figures is a misattribution the gate cannot see. Nothing was written"
              % (PRODUCER, args.records, ARTEFACT, RECORDS), file=sys.stderr)
        return EXIT_USAGE
    out = Path(args.out)
    if out.exists() and not args.force:
        print("%s: %s already exists; pass --force to replace it" % (PRODUCER, out), file=sys.stderr)
        return EXIT_USAGE
    if args.doc is not None and (str(args.out) != ARTEFACT or str(args.doc) != DOC_PATH):
        print("%s: --doc publishes %s, which quotes the artefact at its declared path, so it requires "
              "--out %s --doc %s (this run named --out %s --doc %s). Nothing was written"
              % (PRODUCER, DOC_PATH, ARTEFACT, DOC_PATH, args.out, args.doc), file=sys.stderr)
        return EXIT_USAGE
    try:
        protocol = resolve_protocol(args.protocol)
    except (OSError, ValueError) as exc:
        print("%s: %s: %s -- nothing was written" % (PRODUCER, type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE
    rubric = {name: protocol.rubric[name] for name in G3_CONTRAST_RUBRIC_FIELDS}
    # Measuring is a separate refusal from argument handling: the records, the certificate and the shape of
    # the object assembled from them are all bytes this build's tables name, and no argument an operator typed
    # selects or repairs them. A defect that surfaced here used to answer 2 -- the code README says names the
    # operator -- because the certifier's `ValueError` shared the net with `--protocol` (review MINOR).
    try:
        label, rows, _stored, direction = report.published_severity()
        records_path = report.SEVERITY_CERTS[label][0]
        built = report.build_g3_contrast(records_path, rows, direction, rubric)
        doc = {"producer": PRODUCER, "rubric": rubric, "population": built["population"],
               "set_gate": built["set_gate"], "severity_gate": built["severity_gate"]}
        report.check_g3_contrast(doc, G3_CONTRAST_RUBRIC_FIELDS)
        text = report.render_g3_contrast(doc)
    except report.PublishedArtefactUnavailable as exc:
        print("%s: PUBLISHED ARTEFACT UNAVAILABLE: %s -- nothing was written" % (PRODUCER, exc),
              file=sys.stderr)
        return EXIT_DRIFT
    except (ArithmeticError, AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        # The net `tools/drift_envelope.py`'s gate arm walks for the same reason: these are the classes a
        # missing constant, an unreadable record or a shape this build cannot honour arrives through, and
        # letting one escape would put rc 1 -- the code the published contract forbids -- on a run whose only
        # input was the table's own path.
        print("%s: PUBLISHED ARTEFACT UNAVAILABLE: %s: %s -- this run read the paths %s declares and could "
              "not assemble the contrast from them; nothing was written"
              % (PRODUCER, type(exc).__name__, exc, ARTEFACT), file=sys.stderr)
        return EXIT_DRIFT

    # The write is inside a refusal, not outside one: an `--out` this process cannot write is an input the
    # operator named, and `tools/g1_feasibility.py` answers the identical input with 2. Letting `OSError`
    # escape here would put a traceback at rc 1, the one code the published contract forbids.
    #
    # Both destinations or neither. Each blob is rendered and serialised before either file is touched, then
    # written beside its target and moved into place: an `--out` that landed and a `--doc` that then failed
    # would leave the artefact and its document describing different runs while the handler below printed
    # "nothing was written" over a file that exists.
    moved = []
    try:
        payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
        pair = [(out, payload)]
        if args.doc is not None:
            document = Path(args.doc)
            document.parent.mkdir(parents=True, exist_ok=True)
            pair.append((document, text))
        for path, body in pair:
            path.parent.mkdir(parents=True, exist_ok=True)
            Path(str(path) + ".tmp").write_text(body)
        for path, _body in pair:
            os.replace(str(path) + ".tmp", str(path))
            moved.append(str(path))
    except OSError as exc:
        for path in pair:
            try:
                os.unlink(str(path[0]) + ".tmp")
            except OSError:
                pass
        if moved:
            print("%s: %s: %s -- PARTIAL WRITE: %s landed before the failure; the pair is not a single "
                  "emission and must be re-run" % (PRODUCER, type(exc).__name__, exc, ", ".join(moved)),
                  file=sys.stderr)
        else:
            print("%s: %s: %s -- nothing was written" % (PRODUCER, type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE
    print("wrote %s" % args.out)
    if args.doc is not None:
        print("wrote %s" % args.doc)
    for block in ("set_gate", "severity_gate"):
        print("  %s: %s %s" % (block, doc[block]["module"],
                               "certified" if doc[block]["feasible"] else "refused: %s" % doc[block]["reason"]))
    print("  protocol: %s" % (args.protocol or PROTOCOL_JSON))
    return 0


if __name__ == "__main__":
    sys.exit(main())
