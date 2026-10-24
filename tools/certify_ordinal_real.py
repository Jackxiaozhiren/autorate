#!/usr/bin/env python3
"""Publish the first real-corpus ordinal one-sided guarantee: records -> certificate + derived document.

    uv run --frozen python3 tools/certify_ordinal_real.py --out data/cert_severity_typed_decisions.json \\
        --doc docs/ORDINAL_REAL.md --force

Spec §2 states G3 as ">=1 ordinal guarantee that multiclass CP cannot express" and measures it by the negative
test. `data/cert_severity_ordinal.json` answers that test on a synthetic population, and this file publishes
the same statement over a real one: 400 held-out `urgency` decisions scored by the cached `laya` revision,
committed as `data/records_typed_decisions_urgency.jsonl` and pinned by `data/typed_decisions_provenance.json`.
The certificate is real; the criterion's status is not moved by it, and the document says why in plain words.

Three rules shape it, and they are the rules `tools/g3_contrast.py` and `autorate severity` already keep.

*No arithmetic and no prose lives here.* `autorate.severity.certify_severity` measures the bound,
`report.build_ordinal_real_refusal` re-measures the set gate whose refusal is stored beside it, and
`report.render_ordinal_real` owns every sentence of the document. Those are the same functions
`report.rederive_ordinal_real` calls under `autorate verify`, which is what makes the committed bytes a
re-derivation rather than a transcription. This file resolves the freeze, refuses an unsafe run, and writes.

*The population is not a knob, and neither is the rule.* `report.ORDINAL_REAL_CERTS` names the records file,
the artefact and the direction; a run at the published paths with `--direction over` would rewrite a `under`
certificate above a document that still named `under`, so the guard compares all three table elements.

*The refusal of the set gate is a published field.* It goes into `meta.set_gate_refusal` with the budget it
ran at, because the G3 claim depends on it and `verify` compares `meta` whole. A future certification on this
population therefore cannot rewrite that claim by editing prose: the artefact would have to be re-measured.

Exit codes, on the axis the whole CLI draws -- who named the path.

    0  the certificate certified and the pair was written
    2  a refusal about an argument: a foreign `--records`/`--out`/`--doc`/`--direction`, an existing `--out`
       or `--doc` without `--force`, a `--protocol` that is not there, an unwritable destination
    3  the run measured and refused: no certificate exists over these records. The artefact and its document
       are still written, because a refusal is a result this repository ships
    4  a defect in the bytes at a path this build declares -- the records file, the pin or the freeze --
       including a records file whose sha256 is not the one the pin publishes

Nothing escapes as 1.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    # Script mode puts `tools/` on sys.path, not the repository's `src`. A layout note, not a lint
    # exemption: the project's gate selects E9,F63,F7,F82,F401,F811 and none of them fires here.
    sys.path.insert(0, str(REPO / "src"))

from autorate import report
from autorate.cli import (EXIT_CERTIFIED, EXIT_DRIFT, EXIT_NOT_CERTIFIABLE, EXIT_USAGE,
                          PROTOCOL_JSON, SEVERITY_RUBRIC_FIELDS)
from autorate.protocol import file_digest, load_protocol, protocol_digest
from autorate.severity import DIRECTIONS, certify_severity

ARTEFACT = report.ORDINAL_REAL_CERT_JSON
DOC_PATH = str(report.ORDINAL_REAL_MD)
RECORDS = report.ORDINAL_REAL_CERTS[report.ORDINAL_REAL_LABEL][0]
DIRECTION = report.ORDINAL_REAL_CERTS[report.ORDINAL_REAL_LABEL][2]
PRODUCER = report.ORDINAL_REAL_PRODUCER
PIN = report.TYPED_DECISIONS_PIN


def resolve_protocol(stated):
    """The freeze, on the who-named-the-path axis: a typed `--protocol` that is missing is usage (2); the
    table-declared default that is missing is the checkout's refusal (4). Same rule as
    `tools/g3_contrast.py`, restated because the argument shapes differ, not the law."""
    if stated:
        path = Path(stated)
        if not path.is_file():
            raise ValueError("--protocol %s does not exist" % path)
        return load_protocol(path)
    return report.load_published(PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PRODUCER,
                                     description="Publish the real-corpus ordinal one-sided certificate "
                                                 "(Plan E) and the document rendered from it.")
    parser.add_argument("--records", default=RECORDS,
                        help="only the published real ordinal population is allowed here: %s" % RECORDS)
    parser.add_argument("--out", default=ARTEFACT, help="where to write the artefact (default %s)" % ARTEFACT)
    parser.add_argument("--doc", help="also write the derived document (the published %s)" % DOC_PATH)
    parser.add_argument("--direction", default=DIRECTION, choices=DIRECTIONS,
                        help="the rule the publication declares for this row (only %s is it)" % DIRECTION)
    parser.add_argument("--pin", default=PIN, help="the corpus identity file (default %s)" % PIN)
    parser.add_argument("--protocol", default=None,
                        help="which freeze to read the rubric from (default %s, read as a published artefact)"
                             % PROTOCOL_JSON)
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    args = parser.parse_args(argv)

    # Checked before anything is read, measured or written, because every refusal below says so.
    if str(args.records) != RECORDS:
        print("%s: --records %s is refused. %s publishes the real-corpus certificate over the population "
              "report.ORDINAL_REAL_CERTS declares -- %s -- and an artefact naming that path while carrying "
              "another sample's figures is a misattribution the gate cannot see. Nothing was written"
              % (PRODUCER, args.records, ARTEFACT, RECORDS), file=sys.stderr)
        return EXIT_USAGE
    if args.direction != DIRECTION:
        print("%s: --direction %s is refused: the publication declares `%s` for this row, and the rule is "
              "the element the table exists to carry. Nothing was written" % (PRODUCER, args.direction,
                                                                              DIRECTION), file=sys.stderr)
        return EXIT_USAGE
    if Path(args.out).exists() and not args.force:
        print("%s: %s already exists; pass --force to replace it -- nothing was written"
              % (PRODUCER, args.out), file=sys.stderr)
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
    rubric = {name: protocol.rubric[name] for name in SEVERITY_RUBRIC_FIELDS}

    # Measuring is a separate refusal from argument handling: the records, the pin and the shape of the
    # certificate assembled from them are bytes this build's tables name, and no argument an operator typed
    # selects or repairs them.
    try:
        pin = report.load_published(args.pin, "report.TYPED_DECISIONS_PIN",
                                    report.read_typed_decisions_pin)
        actual = file_digest(Path(RECORDS))
        if pin["records"]["sha256"] != actual:
            raise report.PublishedArtefactUnavailable(
                "%s pins the published records file at sha256 %s, but %s hashes to %s: the certificate "
                "would be measured over rows the corpus identity file does not describe"
                % (PIN, pin["records"]["sha256"], RECORDS, actual))
        rows = report.load_published(RECORDS, "report.ORDINAL_REAL_CERTS", report.load_records)
        if len(rows) != 1:
            raise report.PublishedArtefactUnavailable(
                "%s publishes one ordinal population across %d backends (%s), and a severity certificate "
                "asserts exchangeability across whatever it is handed -- the gate would pool corpora nobody "
                "claimed are the same subject"
                % (RECORDS, len(rows), ", ".join(sorted(rows)) or "nothing"))
        records = rows[next(iter(rows))]
        if not records:
            raise report.PublishedArtefactUnavailable(
                "%s holds no record for the backend it names, so the certificate would be measured over an "
                "empty population" % RECORDS)
        cert = certify_severity(records, alpha=rubric["alpha"], delta=rubric["delta"],
                                direction=DIRECTION, seed=rubric["seed"],
                                population=report.ordinal_real_population(pin))
        budget = dict(rubric, beta=protocol.rubric["beta"])
        cert = replace(cert, meta={**cert.meta, "set_gate_refusal":
                                   report.build_ordinal_real_refusal(records, budget)})
        cert = replace(cert, meta={**cert.meta, "protocol_digest": protocol_digest(protocol)})
        text = report.render_ordinal_real(report.ORDINAL_REAL_LABEL, cert, pin)
    except report.PublishedArtefactUnavailable as exc:
        print("%s: PUBLISHED ARTEFACT UNAVAILABLE: %s -- nothing was written" % (PRODUCER, exc),
              file=sys.stderr)
        return EXIT_DRIFT
    except (ArithmeticError, AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        print("%s: PUBLISHED ARTEFACT UNAVAILABLE: %s: %s -- this run read the paths %s declares and could "
              "not assemble the certificate from them; nothing was written"
              % (PRODUCER, type(exc).__name__, exc, ARTEFACT), file=sys.stderr)
        return EXIT_DRIFT

    moved = []
    try:
        payload = cert.to_json()
        pair = [(Path(args.out), payload)]
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

    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    refusal = cert.meta["set_gate_refusal"]
    print("  set gate over the same records: %s%s" % (
        "certified" if refusal["feasible"] else "refused: %s" % refusal["reason"], ""))
    if protocol is not None:
        print("  protocol: %s (version %d, frozen %s) digest %s"
              % (args.protocol or PROTOCOL_JSON, protocol.protocol_version, protocol.frozen_at,
                 protocol_digest(protocol)))
    if args.doc is not None:
        print("wrote %s" % args.doc)
    print("wrote %s" % args.out)
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


if __name__ == "__main__":
    sys.exit(main())
