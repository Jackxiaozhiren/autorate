"""G4's second named output: the contamination gap `delta_hat`, published with an interval.

Spec section 2 asks criterion G4 for two things, "Khmer-class slices refused, not averaged" and
"`delta_hat` published with interval"; the first is `data/slices_language.json` and this file produces the
second. Spec section 9 defines the quantity: certify the same model on the in-training stratum and the
held-out stratum, publish the gap with a two-sided interval, and label it a diagnostic with an interpretation
rule rather than a proof of leakage.

Two design decisions are load-bearing enough to be stated where a reader will find them:

* The only in-training-versus-held-out census that exists is upstream's own per-suite result file, and it
  publishes aggregate `n` and `accuracy` with no per-case probabilities. No certificate can be built from
  that, so this probe does not pretend otherwise: it reads the committed pin and calls
  `contamination.from_counts`, which is the same interval arithmetic `stratified` uses, and every surface it
  writes carries `claim = False`.
* The pin is committed precisely so this producer answers identically with the corpus absent. The digest of
  the upstream file is therefore transcribed, not recomputed, in that lane -- and `verify` says so, the way
  it says so for the inventory snapshot.

Exit codes follow the published contract: 0 when the gap clears the interval ceiling, 3 when the probe ran and
refused (a thin stratum, or an interval too wide to exclude zero), 2 for a bad argument or a pin whose rows do
not answer, 4 when the pin is missing or unreadable. Nothing escapes as 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from autorate.cli import EXIT_CERTIFIED, EXIT_DRIFT, EXIT_NOT_CERTIFIABLE, EXIT_USAGE
from autorate.report import (CONTAMINATION_JSON, CONTAMINATION_MD, CONTAMINATION_PIN,
                             ContaminationRefusal, build_contamination,
                             render_contamination)

ProbeRefusal = ContaminationRefusal

PIN_PATH = CONTAMINATION_PIN
PROBE_PATH = CONTAMINATION_JSON
PROBE_DOC = str(CONTAMINATION_MD)
PROBE_PRODUCER = "tools/contamination_probe.py"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--out" not in argv or "--doc" not in argv:
        sys.stderr.write("USAGE: contamination_probe.py --out %s --doc %s [--force]\n" % (PROBE_PATH,
                                                                                           PROBE_DOC))
        return EXIT_USAGE
    out, doc = Path(argv[argv.index("--out") + 1]), Path(argv[argv.index("--doc") + 1])
    if {str(out), str(doc)} != {str(PROBE_PATH), str(PROBE_DOC)} and "--force" not in argv:
        sys.stderr.write("USAGE: %s publishes %s and quotes it at %s, so the two paths must be the published "
                         "pair (this run named %s and %s). Pass --force for a scratch run.\n"
                         % (PROBE_PRODUCER, PROBE_PATH, PROBE_DOC, out, doc))
        return EXIT_USAGE
    pin_path = Path(argv[argv.index("--pin") + 1]) if "--pin" in argv else Path(PIN_PATH)
    if not pin_path.is_file():
        sys.stderr.write("PUBLISHED ARTEFACT UNAVAILABLE: %s is not readable, and the probe derives every "
                         "figure from it. Produce it with tools/contamination_pin.py in the corpus-present "
                         "lane.\n" % pin_path)
        return EXIT_DRIFT
    try:
        pin = json.loads(pin_path.read_text())
        record = build_contamination(pin)
    except (ProbeRefusal, json.JSONDecodeError, TypeError) as problem:
        sys.stderr.write("PROBE REFUSED: %s\nNothing was written.\n" % problem)
        return EXIT_USAGE
    if not isinstance(pin.get("source"), dict) or "sha256" not in pin["source"]:
        sys.stderr.write("PROBE REFUSED: the pin names no source digest, so this artefact could not be "
                         "traced to the file it came from.\nNothing was written.\n")
        return EXIT_USAGE

    out.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    doc.write_text(render_contamination(record))
    if "refusal" in record["probe"]:
        print("refused: %s" % record["probe"]["refusal"])
        return EXIT_NOT_CERTIFIABLE
    print("delta_hat=%s over %d in-training and %d held-out cases; interval [%s, %s]; claim=False"
          % (record["headline"]["delta_hat"], record["strata"]["in_stratum"]["cases"],
             record["strata"]["out_stratum"]["cases"], *record["headline"]["interval"]))
    return EXIT_CERTIFIED


if __name__ == "__main__":
    sys.exit(main())
