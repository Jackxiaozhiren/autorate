#!/usr/bin/env python3
"""The 200-resplit experiment spec §2 G1 asks for: per-split outcomes, and a rate with a real denominator.

Two rules shape this file. The loop is ~10 minutes of compute (a certify over the 2,974-row MASSIVE records
costs ~0.95 s, so 200 seeds x 5 tasks is not a gate step), so the outcome is a committed artefact and
`autorate verify` re-derives the published aggregates from the stored rows rather than rerunning the sweep.
And the quantity G1 names -- the empirical violation rate of the claimed bound -- is a ratio over the
splits that ISSUED a certificate, so on corpora where none do, it is undefined: it is written as `None` and
rendered as "0 of 0 certificates", never as `0.0`, because a reader who sees 0.0 concludes the rule held when
it never ran.

Run it from the project interpreter, which is the one with numpy-free stdlib determinism here:

    uv run --frozen python3 tools/resplit_experiment.py --out data/resplit_200.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

from autorate.certify_choice import certify_choice
from autorate.certificate import ALPHA, BETA, DELTA, METHOD, SEED
from autorate.records import Record
from autorate.report import CERTS, MASSIVE_CERTIFICATES, RECORDS, load_records

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SEEDS = 200
ARTEFACT = "data/resplit_200.json"

# The published rubric, in an order this file owns. `certificate.PUBLISHED_RUBRIC` is a MappingProxyType
# whose key order is not pinned, so dumping it straight into JSON would make the artefact's bytes depend on
# a mapping detail; the five values are the owner's, the order is this writer's.
RUBRIC = (("alpha", ALPHA), ("beta", BETA), ("delta", DELTA), ("method", METHOD), ("seed", SEED))

# The control family, and the reason it is here rather than in the test: the artefact quotes a row from it,
# so a test-local generator would certify a fiction about what shipped. `error_rate` is non-zero on purpose --
# a family whose argmax is never wrong cannot be shown violating a bound, which is the vacuous-sweep defect
# the certifier's own tests record.
SYNTHETIC_FAMILY = {"label": "synthetic/sharp-k4-e0.02", "synthetic": {"n": 1200, "k": 4, "sharpness": 8.0,
                                                                        "error_rate": 0.02, "seed": 1}}


def published_tasks():
    """The tasks the gate already publishes, read from `report`'s tables -- never a list kept here."""
    tasks = [{"label": backend, "records": RECORDS, "backend": backend} for backend in sorted(CERTS)]
    for label in sorted(MASSIVE_CERTIFICATES):
        records, _cert = MASSIVE_CERTIFICATES[label]
        tasks.append({"label": label, "records": records, "backend": "laya"})
    return tasks


def _synthetic(spec):
    rng = random.Random(spec["seed"])
    k, n = spec["k"], spec["n"]
    rows = []
    for i in range(n):
        g = rng.randrange(k)
        peaked = g if rng.random() >= spec["error_rate"] else (g + 1 + rng.randrange(k - 1)) % k
        w = [1.0] * k
        w[peaked] = spec["sharpness"]
        tot = sum(w) + k * 0.05
        p = [round(x / tot, 4) for x in w]
        p[peaked] = round(p[peaked] + (1.0 - sum(p)), 4)
        options = tuple("opt%d" % j for j in range(k))
        rows.append(Record(id=str(i), qtype="choice", backend="synthetic", repeat=0, options=options,
                           probs=tuple(p), predicted=options[peaked], gold=options[g], case_id=str(i)))
    return rows


def _family_rows(family, cache):
    if "synthetic" in family:
        return _synthetic(family["synthetic"])
    key = (family["records"], family["backend"])
    if key not in cache:
        cache[key] = load_records(REPO / family["records"]).get(family["backend"], [])
    return cache[key]


def run_family(family, seeds=range(DEFAULT_SEEDS), cache=None):
    """One row per seed: what the certifier answered, and what the answer claimed."""
    cache = {} if cache is None else cache
    rows = _family_rows(family, cache)
    out = []
    for seed in seeds:
        cert = certify_choice(rows, seed=seed)
        automated = cert.meta.get("automated_cases")
        errors = cert.meta.get("errors_among_automated")
        observed = (errors / automated) if (automated and errors is not None) else None
        out.append({"label": family["label"], "seed": seed, "feasible": cert.feasible, "reason": cert.reason,
                    "n_cal_cases": cert.meta.get("n_cal_cases"), "n_eval_cases": cert.meta.get("n_eval_cases"),
                    "automated_cases": automated, "errors_among_automated": errors,
                    "observed_conditional_error": observed,
                    "conditional_error_bound": cert.conditional_error_bound,
                    "autorate": cert.autorate})
    return out


def summarise(label, rows):
    """The published aggregate, including the denominator that makes the rate mean what it says."""
    certified = [r for r in rows if r["feasible"]]
    reasons = {}
    for r in rows:
        if not r["feasible"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    bounds = [r["conditional_error_bound"] for r in certified]
    rates = [r["autorate"] for r in certified]
    violations = sum(1 for r in certified
                     if r["observed_conditional_error"] is not None
                     and r["observed_conditional_error"] > r["conditional_error_bound"])
    return {"label": label, "resplits": len(rows), "certificates_issued": len(certified),
            "refusal_reasons": dict(sorted(reasons.items())),
            "violations": violations, "violations_denominator": len(certified),
            "violation_rate": (violations / len(certified)) if certified else None,
            "bound_min": min(bounds) if bounds else None,
            "bound_median": statistics.median(bounds) if bounds else None,
            "bound_max": max(bounds) if bounds else None,
            "autorate_min": min(rates) if rates else None,
            "autorate_max": max(rates) if rates else None}


def recompute(rows):
    """Every aggregate in the artefact, derived from its stored rows -- the check `verify` will run."""
    by_label = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)
    return {label: summarise(label, by_label[label]) for label in sorted(by_label)}


def render_task(summary):
    """One line per family. A rate with no certificates is said to be undefined, in those words."""
    rate = summary["violation_rate"]
    stated = "undefined (%d of %d certificates)" % (summary["violations"], summary["violations_denominator"]) \
        if rate is None else "%.3f (%d of %d certificates)" % (rate, summary["violations"],
                                                               summary["violations_denominator"])
    refusals = ", ".join("%s:%d" % item for item in summary["refusal_reasons"].items()) or "-"
    return ("task %s: %d of %d splits certify; refusals %s; empirical violation rate %s"
            % (summary["label"], summary["certificates_issued"], summary["resplits"], refusals, stated))


def build_document(rows, summaries, seeds):
    return {"resplits": len(seeds), "rubric": {name: value for name, value in RUBRIC},
            "tasks": summaries, "rows": rows}


def _refuse_existing(out, force):
    """An existing destination is a refusal, not a truncation: the bytes there may be the published ones."""
    if out.exists() and not force:
        print("refusing to overwrite %s: pass --force to replace it (the experiment takes minutes, and a "
              "mistyped --out should not be able to destroy a published artefact)" % out, file=sys.stderr)
        return 2
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="resplit_experiment", description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=ARTEFACT, help="where to write the artefact (default %s)" % ARTEFACT)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS,
                        help="how many seeds to sweep, as range(N) (default %d)" % DEFAULT_SEEDS)
    parser.add_argument("--tasks", action="append", metavar="LABEL",
                        help="run only these labels; repeatable. Default: every published task plus the "
                             "synthetic control family")
    parser.add_argument("--no-synthetic", dest="synthetic", action="store_false",
                        help="omit the synthetic control family (it is the row that shows the rate can "
                             "be computed at all)")
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    args = parser.parse_args(argv)

    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    refusal = _refuse_existing(out, args.force)
    if refusal is not None:
        return refusal

    families = published_tasks()
    if args.synthetic:
        families = families + [SYNTHETIC_FAMILY]
    if args.tasks:
        wanted = set(args.tasks)
        unknown = sorted(wanted - {f["label"] for f in families})
        if unknown:
            print("no such task label(s): %s -- the tables publish %s"
                  % (", ".join(unknown), ", ".join(sorted(f["label"] for f in families))), file=sys.stderr)
            return 2
        families = [f for f in families if f["label"] in wanted]

    seeds = tuple(range(args.seeds))
    cache = {}
    rows = []
    summaries = []
    for family in families:
        got = run_family(family, seeds=seeds, cache=cache)
        rows.extend(got)
        summary = summarise(family["label"], got)
        summaries.append(summary)
        print(render_task(summary))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_document(rows, summaries, seeds), indent=2, sort_keys=True) + "\n")
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
