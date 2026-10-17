#!/usr/bin/env python3
"""B3's drift envelope, published: the two withdrawals, as bytes a re-derivation can check.

    uv run --frozen python3 tools/drift_envelope.py --out data/drift_envelope.json \\
        --doc docs/DRIFT.md --force

`autorate`'s rule is that a published number is evidence only if a committed producer wrote it and a gate
re-derives it. Plan B3's Task 3 declared this envelope and withdrew two guarantees -- correctly, and with
measurements `tests/test_drift.py` re-runs -- but the withdrawals lived in a module docstring and a test, so
the gate never checked them and `data/` held nothing. This file turns them into an artefact:
`data/drift_envelope.json`, with `docs/DRIFT.md` rendered from those bytes.

Three rules shape it.

*The envelope text is COPIED, never retyped or summarised.* Both tuples are read out of
`autorate.drift.WEIGHTED_ENVELOPE` / `autorate.drift.ACI_ENVELOPE` and stored as JSON lists, and every
envelope figure this artefact compares itself to (seed, trials per size, test points, alpha, gamma, the
calibration regime, the target density, `E_F0[w]`, the cited miscoverage at each size, the cited 3SE, the cited
vacuous share, the four cited long-run rates and their cited bounds, the sweep's count, seed, length and its
two counts) is *parsed out of those tuples* by `read_module_provenance` and friends. A figure this producer
cannot find in the module text is a named refusal at exit 4, not a value remembered from a previous run. That
is why an edit to the envelope prose reddens a row: the artefact and the document are downstream of the
module's bytes, and `--check` compares them line for line.

*The measurement is the one the suite already runs, at the same scale.* Mode 1 is `tests/test_drift.py:539-570`
-- calibration ~ U[0,1], the declared ratio `w(s) = 10*s^9` (`E_F0[w] = 1`), `random.Random(seed + n)` per
size, `alpha = 0.05`, 4000 trials per size, coverage from the closed form `P(score > q) = 1 - q^10` rather
than from sampled test points, so the artefact carries one Monte-Carlo layer and not two. Mode 2 is
`tests/test_drift.py:731-760` -- four deterministic constructions walked through the shipped `aci_threshold`,
each with its realised long-run rate and its comparison against `aci_regret_bound`, plus the two controls
where the inequality does hold -- and that file's 400-sequence sweep at T=2000. Pure Python `float` and
`random.Random`, no numpy: the published figures are the ones `tests/test_drift.py` computes with those, and a
second arithmetic over the same quantity is what this repository refuses (the last ULP of `pow` is a platform
fact, ledger R-121). Measured cost of the whole run: under a second, so it re-runs comfortably -- which is why
`--trials` below the scale the envelope states is *refused* on a publishing run instead of quietly shrinking
the sample behind the envelope's 0.0933.

*Exit codes are this tool's contract, and the axis is who named the path.* **0** when the artefact and the
document were written and every figure in them re-derives, or (under `--check`) when the committed bytes
re-derive. **3** when the run measured and a claim did NOT reproduce: the envelope states a figure the shipped
functions no longer yield, or the sweep fired a violation without a clip. The artefact and the document are
written and printed first -- the disagreement is the result, and it is published -- then 3. **2** for the
refusals about an argument the operator typed: `--check` combined with a write flag, exactly one of
`--out`/`--doc` when the run would publish, NEITHER of them (which would rewrite the declared artefact and
leave the document that quotes it stale), a pair off the paths this build declares, `--trials` below the
stated scale on a publishing run, an existing `--out` without `--force`, an unwritable destination, or a
`--check --artefact` path that is missing, unusable, or does not reproduce. **4** for a defect in the state
this build declares: `autorate.drift` absent or holding a malformed envelope, or a `--check` of the DECLARED
artefact that is absent, wrong-shaped, truncated, re-provenanced, quoted from a sentence the module does not
contain (`WITHDRAWAL PROSE`), byte-different from its own document, or carrying a figure the arithmetic no
longer yields. Nothing escapes at 1: every input problem is a `ValueError` subclass mapped to
2, every committed-state problem is a `RuntimeError` subclass mapped to 4, and `weighted_quantile`'s own
`ArithmeticError` cross-check is named rather than allowed to reach the operator as a traceback. The checks
also read stored rows *by key*, so both catch-alls carry `LookupError` and `AttributeError` as well: a
top-level-valid artefact missing one subkey, or a `drift` that no longer holds an envelope constant, is refused
under the class of defect with the wanted name and the path printed, at 4 when the declared path is what was
being read and 2 when the operator named it. Widening that tuple decides nothing about whose fault it is --
the naming axis still picks the code, so an unplanned error becomes a refusal rather than a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
import textwrap
from pathlib import Path

from autorate import drift
from autorate.cli import EXIT_CERTIFIED, EXIT_DRIFT, EXIT_NOT_CERTIFIABLE, EXIT_USAGE

PRODUCER = "tools/drift_envelope.py"
ARTEFACT_REL = "data/drift_envelope.json"
DOC_REL = "docs/DRIFT.md"
REPO = Path(__file__).resolve().parents[1]
ARTEFACT_PATH = REPO / ARTEFACT_REL
DOC_PATH = REPO / DOC_REL

#: The keys a reader of this artefact has to find in it, named once so `--check` and the row that counts the
#: check read the same list.
REQUIRED_KEYS = ("producer", "artefact_path", "document_path", "provenance", "mode1", "mode2",
                 "mode2_controls", "mode2_sweep", "weighted_envelope", "aci_envelope",
                 "not_certifiable_under_drift", "withdrawals", "reproduction")

# The producer's own measurement parameters, not envelope figures: the lengths `tests/test_drift.py:731-760`
# walks its four constructions and its two controls at, and the two atoms that test names for the controls.
# The envelope's six-decimal long-run rates are stated at these lengths, so a shorter run would disagree with
# the prose it exists to check; the values are named here rather than scattered through the code.
MODE2_SEQUENCE_ROUNDS = {
    "every score == SCORE_CEILING": 20000,
    "adversarial period-2 0.99/0.01": 100000,
    "constant 0.99, below the ceiling": 20000,
    "every score == the floor 0.0": 20000,
}
MODE2_CONTROL_ROUNDS = {"grid control": 2000, "constant 0.95 control": 2000}
MODE2_CONTROL_CONSTANTS = {"grid control": 100, "constant 0.95 control": 0.95}

#: The precision the published mode-1 figures are stored at. Six decimals, because the envelope quotes four and
#: because the last bits of `q ** 10` are a libm fact (ledger R-121): a published artefact that stored 17
#: significant digits would be publishing a platform fact as evidence.
PUBLISHED_DECIMALS = 6

#: The column width the renderer's own prose is folded at, so the document reads the way the other
#: published documents here do and a re-flow is a producer change rather than an editor's.
DOC_WIDTH = 92


class DriftEnvelopeUsage(ValueError):
    """An argument this command was handed is wrong -- `cli`'s register for exit 2."""


class DriftEnvelopeState(RuntimeError):
    """The state this build declares cannot be read as what it publishes -- exit 4.

    Deliberately NOT a `ValueError`: the same defect at a path the operator named is a 2, and if the two
    meanings shared a class the code would stop telling the reader whose fault it is and what to do next.
    """


# --------------------------------------------------------------------- reading the module's own bytes

def _checked_tuple(value, name: str) -> tuple:
    """A module envelope constant, as the tuple of strings it promises to be, or a named refusal."""
    if not isinstance(value, tuple) or not value or not all(isinstance(line, str) for line in value):
        raise DriftEnvelopeState(
            "PUBLISHED SOURCE UNAVAILABLE: drift.%s is %s, not a non-empty tuple of strings -- this artefact "
            "copies that tuple and cannot copy this" % (name, type(value).__name__))
    return value


def _first_match(pattern: str, text: str, what: str):
    """One group out of the envelope text, or a named refusal that quotes the pattern it wanted.

    Every envelope figure in this artefact is read through here. A pattern that stops matching is a `drift.py`
    edit this producer refuses instead of papering over with a value remembered from the last run -- which is
    how a withdrawal sentence that loses its number becomes a loud failure rather than a stale document.
    """
    match = re.search(pattern, text)
    if match is None:
        raise DriftEnvelopeState(
            "ENVELOPE PROVENANCE: %s is not in drift.py's envelope text (pattern %r); this artefact states "
            "no figure the module does not" % (what, pattern))
    return match


def _envelope_reason(lines: tuple, pattern: str, name: str) -> str:
    """The one envelope line this artefact quotes as the module's reason, or a named refusal.

    MAJOR-2 was a quotation the module did not contain: `build_artefact` typed a paraphrase into the
    withdrawals block and `render_document` printed it after "the module states the reason as". A paraphrase
    can outlive the sentence it claims to quote, so the reason is read out of the tuple the way every figure
    is -- and the stored value is that line verbatim, which is what lets `check_envelope_copies` compare it
    against the module again on a `--check` run.

    Exactly one line must match. Zero matches is a `drift.py` edit that dropped or reworded the mechanism
    sentence; two is an envelope that no longer says which line is the reason. Both are exit 4, because the
    alternative -- publishing the tool's own words under the module's name -- is the defect this replaces.
    """
    hits = [line for line in lines if re.match(pattern, line)]
    if len(hits) != 1:
        raise DriftEnvelopeState(
            "ENVELOPE PROVENANCE: drift.%s gives %d lines matching %r, and this artefact publishes exactly "
            "the one the module states as its reason (found %d)" % (name, len(hits), pattern, len(hits)))
    return hits[0]


def read_module_provenance() -> dict:
    """Every figure of its own measurement this artefact publishes, parsed out of the two envelope tuples."""
    weighted = " ".join(_checked_tuple(drift.WEIGHTED_ENVELOPE, "WEIGHTED_ENVELOPE"))
    aci = " ".join(_checked_tuple(drift.ACI_ENVELOPE, "ACI_ENVELOPE"))
    cited_by_size = {int(n): float(value) for value, n in re.findall(r"(\d\.\d{4}) at n=(\d+)", weighted)}
    if not cited_by_size:
        raise DriftEnvelopeState("ENVELOPE PROVENANCE: WEIGHTED_ENVELOPE states no `0.NNNN at n=NN` figure, "
                                 "so there is no measured deficit for this artefact to reproduce")
    vacuous = _first_match(r"(\d\.\d{4}) of those n=(\d+)", weighted, "the vacuous-ceiling share")
    alpha = float(_first_match(r"alpha = (\d\.\d+)", weighted, "the nominal alpha").group(1))
    gamma = float(_first_match(r"alpha=gamma=(\d\.\d+)", aci, "the alpha=gamma pair").group(1))
    if abs(alpha - gamma) > 1e-12:
        raise DriftEnvelopeState(
            "ENVELOPE PROVENANCE: WEIGHTED_ENVELOPE states alpha=%s while ACI_ENVELOPE states alpha=gamma=%s "
            "-- the two modes are no longer measured against the same nominal rate" % (alpha, gamma))
    scale = _first_match(r"(\d{3,5}) trials x (\d{3,5}) test points", weighted,
                         "the trials-per-size and test-points counts")
    return {
        "seed": int(_first_match(r"seed (\d{7,9})", weighted, "the Monte-Carlo seed").group(1)),
        "trials_per_size": int(scale.group(1)),
        "test_points_stated_by_envelope": int(scale.group(2)),
        "sizes": sorted(cited_by_size),
        "alpha": alpha,
        "gamma": gamma,
        "calibration_regime": _first_match(r"calibration ~ (.+?), target density", weighted,
                                           "the calibration regime").group(1),
        "target_density": _first_match(r"target density (\S+?), ", weighted, "the target density").group(1),
        "expected_weight_under_calibration": float(_first_match(r"E_F0\[w\] = (\d+)", weighted,
                                                                "E_F0[w]").group(1)),
        "three_se_stated_by_envelope": float(_first_match(r"3SE (\d\.\d{4})", weighted,
                                                          "the stated 3SE").group(1)),
        "cited_miscoverage_by_size": {str(n): cited_by_size[n] for n in sorted(cited_by_size)},
        "vacuous_share_cited_in_envelope": float(vacuous.group(1)),
        "vacuous_share_stated_for_size": int(vacuous.group(2)),
        "module_constants": {"SCORE_CEILING": drift.SCORE_CEILING,
                             "TEST_POINT_WEIGHT": drift.TEST_POINT_WEIGHT,
                             "DRIFT_DECLARATION_KEY": drift.DRIFT_DECLARATION_KEY},
        "produced_by": {"weighted_quantile": drift.weighted_quantile.__name__,
                        "aci_threshold": drift.aci_threshold.__name__,
                        "aci_regret_bound": drift.aci_regret_bound.__name__},
        "read_from": "autorate.drift",
        "mode1_stream_rule": "random.Random(seed + n) per size, so the two sizes are different streams",
        "mode1_coverage_method": ("closed form under the declared target regime: P(score > q) = 1 - q^10, so "
                                  "this measurement carries one Monte-Carlo layer (the calibration draws) and "
                                  "not a second over test points"),
        "mode2_rounds_by_sequence": dict(MODE2_SEQUENCE_ROUNDS),
        "mode2_rounds_by_control": dict(MODE2_CONTROL_ROUNDS),
        "published_decimals": PUBLISHED_DECIMALS,
    }


def _mode2_text() -> str:
    return " ".join(_checked_tuple(drift.ACI_ENVELOPE, "ACI_ENVELOPE"))


def mode2_constructions() -> list:
    """The four constructed sequences whose atoms `ACI_ENVELOPE` names, in the order its sentence gives them.

    `tests/test_drift.py:731-760` walks exactly these four. Their atoms come from the envelope's own prose --
    the ceiling constant the module calls its `SCORE_CEILING`, the alternating pair, the constant interior
    value, the floor -- and the ceiling atom is additionally checked against `drift.SCORE_CEILING`, because the
    envelope's claim is that the vacuous arm's own value is what breaks the inequality.
    """
    aci = _mode2_text()
    ceiling_value = float(_first_match(r"an all-([\d.]+) sequence \(this module's own SCORE_CEILING", aci,
                                      "the all-ceiling sequence").group(1))
    if ceiling_value != drift.SCORE_CEILING:
        raise DriftEnvelopeState(
            "ENVELOPE PROVENANCE: ACI_ENVELOPE calls its all-%s sequence this module's own SCORE_CEILING, but "
            "drift.SCORE_CEILING is %s" % (ceiling_value, drift.SCORE_CEILING))
    alternating = _first_match(r"an alternating ([\d.]+)/([\d.]+) ordering", aci, "the alternating ordering")
    constant = _first_match(r"a constant ([\d.]+) sequence", aci, "the constant interior sequence")
    floor = _first_match(r"an all-([\d.]+) sequence reaches", aci, "the all-floor sequence")
    return [
        {"name": "every score == SCORE_CEILING",
         "construction": {"kind": "constant", "value": ceiling_value,
                          "rounds": MODE2_SEQUENCE_ROUNDS["every score == SCORE_CEILING"]}},
        {"name": "adversarial period-2 0.99/0.01",
         "construction": {"kind": "alternating",
                          "values": [float(alternating.group(1)), float(alternating.group(2))],
                          "rounds": MODE2_SEQUENCE_ROUNDS["adversarial period-2 0.99/0.01"]}},
        {"name": "constant 0.99, below the ceiling",
         "construction": {"kind": "constant", "value": float(constant.group(1)),
                          "rounds": MODE2_SEQUENCE_ROUNDS["constant 0.99, below the ceiling"]}},
        {"name": "every score == the floor 0.0",
         "construction": {"kind": "constant", "value": float(floor.group(1)),
                          "rounds": MODE2_SEQUENCE_ROUNDS["every score == the floor 0.0"]}},
    ]


def mode2_control_constructions() -> list:
    """The two controls that test row ends with, where the inequality DOES hold.

    They are what stop the four above from reading as "nothing holds". Their values are the producer's own
    measurement parameters (`MODE2_CONTROL_CONSTANTS`), not envelope figures, because the envelope states no
    number for them.
    """
    return [
        {"name": "grid control",
         "construction": {"kind": "grid", "modulus": MODE2_CONTROL_CONSTANTS["grid control"],
                          "rounds": MODE2_CONTROL_ROUNDS["grid control"]}},
        {"name": "constant 0.95 control",
         "construction": {"kind": "constant",
                          "value": MODE2_CONTROL_CONSTANTS["constant 0.95 control"],
                          "rounds": MODE2_CONTROL_ROUNDS["constant 0.95 control"]}},
    ]


def cited_mode2_rates() -> dict:
    """The per-sequence figures `ACI_ENVELOPE` states, keyed by the names `mode2_constructions` uses.

    Parsed so measured and cited can be published side by side without either being remembered. Two of the four
    sentences give a rate and no bound of their own ("against the same formula"), so those rows carry the bound
    the ceiling sentence states -- which is the formula the sentence says is the same.
    """
    aci = _mode2_text()
    ceiling = _first_match(r"converges to a long-run error rate of (\d\.\d{3,6}) against a bound of "
                           r"(\d\.\d{3,6})", aci, "the all-ceiling rate and bound")
    alternating = _first_match(r"ordering reaches (\d\.\d{3,6}) against (\d\.\d{3,6})", aci,
                              "the alternating ordering's rate and bound")
    constant = _first_match(r"a constant [\d.]+ sequence reaches (\d\.\d{3,6})", aci,
                            "the constant interior sequence's rate")
    floor = _first_match(r"an all-[\d.]+ sequence reaches (\d\.\d{3,6})", aci, "the all-floor sequence's rate")
    return {
        "every score == SCORE_CEILING": float(ceiling.group(1)),
        "every score == SCORE_CEILING|bound": float(ceiling.group(2)),
        "adversarial period-2 0.99/0.01": float(alternating.group(1)),
        "adversarial period-2 0.99/0.01|bound": float(alternating.group(2)),
        "constant 0.99, below the ceiling": float(constant.group(1)),
        "constant 0.99, below the ceiling|bound": float(ceiling.group(2)),
        "every score == the floor 0.0": float(floor.group(1)),
        "every score == the floor 0.0|bound": float(ceiling.group(2)),
    }


# ------------------------------------------------------------------------------------ measurement

def _grid(count: int, modulus: int = 100) -> list:
    """The deterministic pseudo-uniform sequence `tests/test_drift.py` uses -- no RNG, so a red re-runs."""
    return [((i * 37) % modulus) / float(modulus) for i in range(count)]


def materialise(construction: dict) -> list:
    """Rebuild a published sequence from the recipe the artefact stores."""
    if not isinstance(construction, dict):
        raise DriftEnvelopeState("ARTEFACT SHAPE: a published sequence is described by %s, not a recipe"
                                 % (type(construction).__name__,))
    kind = construction.get("kind")
    rounds = construction.get("rounds")
    if not isinstance(rounds, int) or rounds < 1:
        raise DriftEnvelopeState("ARTEFACT SHAPE: a published recipe states %r rounds" % (rounds,))
    if kind == "constant":
        return [float(construction["value"])] * rounds
    if kind == "alternating":
        values = [float(value) for value in construction["values"]]
        if not values:
            raise DriftEnvelopeState("ARTEFACT SHAPE: an alternating recipe with no atoms")
        return [values[i % len(values)] for i in range(rounds)]
    if kind == "grid":
        return _grid(rounds, int(construction.get("modulus", 100)))
    raise DriftEnvelopeState("ARTEFACT SHAPE: unknown published sequence recipe %r" % (kind,))


def sequence_digest(values) -> str:
    """A digest over the materialised sequence, so a recipe cannot drift from what was measured.

    Stored instead of 180,000 literals: the recipe plus this digest IS the sequence, and a row that re-derives
    a rate recomputes the digest before trusting the recipe it materialised from.
    """
    return hashlib.sha256(repr(list(values)).encode()).hexdigest()


def measure_mode1(trials: int, provenance: dict) -> list:
    """`tests/test_drift.py:539-570`'s declared-ratio Monte-Carlo, at the stated number of trials.

    Calibration ~ U[0,1] with the EXACT declared ratio `w(s) = 10*s^9`, so the only error left to the estimator
    is the finite-sample one and the coverage a threshold buys is available in closed form. The estimator is the
    shipped `drift.weighted_quantile`, vacuous arm included -- the arm's share is one of the published figures.
    """
    alpha = float(provenance["alpha"])
    seed = int(provenance["seed"])
    cited = provenance["cited_miscoverage_by_size"]
    rows = []
    for n in [int(size) for size in provenance["sizes"]]:
        rng = random.Random(seed + n)
        misses = []
        vacuous = 0
        for _ in range(trials):
            cal = [rng.random() for _ in range(n)]
            try:
                q, flag = drift.weighted_quantile(cal, [10.0 * s ** 9 for s in cal], alpha)
            except (ArithmeticError, ValueError) as exc:
                # Both classes mean the same thing here: the shipped estimator refused the calibration stream
                # this producer built from the module's own constants. No argument selected those values, so it
                # is never a 2 -- a bare `ValueError` reaching the CLI with a message about the operator's input
                # is the defect `drift.py`'s own exit-code paragraph forbids.
                raise DriftEnvelopeState(
                    "INVARIANT: drift.weighted_quantile refused the declared-ratio stream at n=%d (%s: %s) -- "
                    "this project's published arithmetic contradicted itself mid-measurement"
                    % (n, type(exc).__name__, exc)) from None
            if flag:
                vacuous += 1
            misses.append(1.0 - q ** 10)
        mean = math.fsum(misses) / trials
        standard_error = math.sqrt(math.fsum((m - mean) ** 2 for m in misses) / (trials - 1) / trials)
        rounded_mean = round(mean, PUBLISHED_DECIMALS)
        rounded_se = round(standard_error, PUBLISHED_DECIMALS)
        three_se = round(3.0 * rounded_se, PUBLISHED_DECIMALS)
        share = vacuous / float(trials)
        vacuous_se = math.sqrt(share * (1.0 - share) / trials) if 0.0 < share < 1.0 else 0.0
        cited_for_size = cited.get(str(n))
        if cited_for_size is None:
            raise DriftEnvelopeState("ENVELOPE PROVENANCE: this producer measured n=%d but WEIGHTED_ENVELOPE "
                                     "states no figure for that size" % n)
        rows.append({
            "n": n,
            "trials": trials,
            "stream_seed": seed + n,
            "realised_miscoverage": rounded_mean,
            "standard_error": rounded_se,
            "three_se": three_se,
            "envelope_cited": cited_for_size,
            "delta_to_envelope_cited": round(mean - cited_for_size, PUBLISHED_DECIMALS),
            "cited_agrees_within_measured_three_se": bool(abs(mean - cited_for_size) <= three_se),
            "vacuous_trials": vacuous,
            "vacuous_share": round(share, PUBLISHED_DECIMALS),
            "vacuous_share_three_se": round(3.0 * vacuous_se, PUBLISHED_DECIMALS),
            "vacuous_share_cited_in_envelope": (
                float(provenance["vacuous_share_cited_in_envelope"])
                if int(provenance["vacuous_share_stated_for_size"]) == n else None),
            "nominal_alpha": alpha,
        })
    return rows


def walk_mode2(scores: list, alpha: float, gamma: float) -> tuple:
    """(long-run error rate, whether any round sat on a clip) over the shipped recursion, streamed.

    The clip flag is the observable the envelope's mechanism sentence points a caller at -- `step.lam` in
    `(0.0, SCORE_CEILING)` names the rounds whose update the clamp discarded -- and it is published per
    sequence because the withdrawal explains itself with it.
    """
    total = 0
    count = 0
    clipped = False
    try:
        rounds = drift.aci_threshold(scores, alpha, gamma)
    except (ValueError, ArithmeticError) as exc:
        raise DriftEnvelopeState(
            "INVARIANT: drift.aci_threshold refused a sequence this producer built from drift.py's own atoms "
            "(%s: %s) -- the published constructions are no longer inputs the shipped validator accepts"
            % (type(exc).__name__, exc)) from None
    for step in rounds:
        total += step.err
        count += 1
        if step.lam in (0.0, drift.SCORE_CEILING):
            clipped = True
    if not count:
        raise DriftEnvelopeState("INVARIANT: a mode-2 sequence yielded no rounds, so it has no rate to publish")
    return total / float(count), clipped


def _mode2_row(item: dict, provenance: dict, cited: dict = None) -> dict:
    alpha, gamma = float(provenance["alpha"]), float(provenance["gamma"])
    scores = materialise(item["construction"])
    realised, clipped = walk_mode2(scores, alpha, gamma)
    bound = drift.aci_regret_bound(len(scores), alpha, gamma)
    # Canonicalised at the producer, on the grid the artefact declares for itself (ledger R-121, and the same
    # rule that fixed the contamination interval after a second libc re-derived `0.7884344428029711` against
    # the stored `...715`). Mode 1 already did this; mode 2 stored `0.02877777777777778` and
    # `0.004499999999999997`, which publish a libm fact as evidence. The published figures are the rounded
    # ones, so `violates_bound` is decided from them too -- a reader who re-adds the row's own numbers has to
    # land on the same verdict the artefact states.
    decimals = int(provenance["published_decimals"])
    realised = round(realised, decimals)
    bound = round(bound, decimals)
    deviation = round(abs(realised - alpha), decimals)
    row = {"name": item["name"], "construction": dict(item["construction"]), "rounds": len(scores),
           "sequence_digest_sha256": sequence_digest(scores), "realised_long_run_rate": realised,
           "deviation_from_alpha": deviation, "regret_bound": bound,
           "violates_bound": bool(deviation > bound), "clip_observable": clipped}
    if cited is not None:
        row["envelope_cited_rate"] = cited.get(item["name"])
        row["envelope_cited_bound"] = cited.get("%s|bound" % item["name"])
    return row


def measure_mode2(provenance: dict, constructions: list) -> list:
    """The four constructions, their realised rates, and the bound each one exceeds: the withdrawal's evidence."""
    cited = cited_mode2_rates()
    return [_mode2_row(item, provenance, cited) for item in constructions]


def measure_mode2_controls(provenance: dict, constructions: list) -> list:
    """The two controls, published beside the four: there the inequality holds, so the four are a result."""
    return [_mode2_row(item, provenance) for item in constructions]


def measure_mode2_sweep(provenance: dict) -> dict:
    """The 400-sequence mechanism sweep `ACI_ENVELOPE` cites, re-run at the scale, seed and length it cites.

    Eight constructed classes, streamed, never materialised twice. The claim is one-sided on purpose: no
    violation fired without a clip, while some clipped sequences still held. Necessary, not sufficient.
    """
    aci = _mode2_text()
    sweep = _first_match(r"Over (\d{2,4}) constructed sequences \(seed (\d{7,9}), T=(\d{3,5})\)", aci,
                         "the sweep's sequence count, seed and length")
    sequences, seed, rounds = int(sweep.group(1)), int(sweep.group(2)), int(sweep.group(3))
    if seed != int(provenance["seed"]):
        raise DriftEnvelopeState("ENVELOPE PROVENANCE: the sweep cites seed %d while WEIGHTED_ENVELOPE cites "
                                 "%d" % (seed, provenance["seed"]))
    unclipped = _first_match(r"no violation fired without a clip \((\d+) of (\d+)\)", aci,
                            "the sweep's violated-without-a-clip count")
    held = _first_match(r"while (\d+) of (\d+) clipped sequences still held", aci,
                        "the sweep's clipped-but-held count")
    if int(unclipped.group(2)) != sequences or int(held.group(2)) != sequences:
        raise DriftEnvelopeState("ENVELOPE PROVENANCE: the sweep's denominators (%s, %s) are not its sequence "
                                 "count %d" % (unclipped.group(2), held.group(2), sequences))
    alpha, gamma = float(provenance["alpha"]), float(provenance["gamma"])
    bound = round(drift.aci_regret_bound(rounds, alpha, gamma), int(provenance["published_decimals"]))
    rng = random.Random(seed)
    violations = violated_unclipped = held_clipped = clipped_total = 0
    for k in range(sequences):
        kind = k % 8
        if kind == 0:
            scores = [rng.random() for _ in range(rounds)]
        elif kind == 1:
            scores = [min(1.0, max(0.0, rng.gauss(0.9, 0.05))) for _ in range(rounds)]
        elif kind == 2:
            scores = [min(1.0, max(0.0, rng.gauss(0.5, 0.2))) for _ in range(rounds)]
        elif kind == 3:
            scores = [rng.choice((0.0, 1.0)) for _ in range(rounds)]
        elif kind == 4:
            scores = [rng.choice((0.99, 0.01)) for _ in range(rounds)]
        elif kind == 5:
            scores = [drift.SCORE_CEILING] * rounds
        elif kind == 6:
            scores = [0.0] * rounds
        else:
            scores = _grid(rounds)
        realised, clipped = walk_mode2(scores, alpha, gamma)
        violated = abs(realised - alpha) > bound
        violations += 1 if violated else 0
        violated_unclipped += 1 if (violated and not clipped) else 0
        held_clipped += 1 if (clipped and not violated) else 0
        clipped_total += 1 if clipped else 0
    return {"seed": seed, "sequences": sequences, "rounds": rounds, "alpha": alpha, "gamma": gamma,
            "bound": bound, "classes": 8, "violations": violations,
            "violated_without_clip": violated_unclipped, "clipped": clipped_total,
            "held_clipped": held_clipped,
            "envelope_cited_violated_without_clip": int(unclipped.group(1)),
            "envelope_cited_held_clipped": int(held.group(1))}


# ------------------------------------------------------------------------------------ the artefact

def build_reproduction(mode1: list, mode2: list, mode2_controls: list, sweep: dict) -> dict:
    """The claims a `--check` run re-tests, each with the measured value and the value the module states.

    This list is the gate's content: a row that stops agreeing is the disagreement `--check` prints and the
    publishing run exits 3 on, instead of a sentence in a document nobody re-reads. Tolerances are stated per
    row -- the measurement's own 3SE, the 6-decimal precision the envelope quotes at, or "direction only" for
    the four inequalities whose whole point is which way they fail.
    """
    checks = []
    for row in mode1:
        checks.append({"id": "mode1 realised miscoverage at n=%d" % row["n"],
                       "measured": row["realised_miscoverage"], "envelope_states": row["envelope_cited"],
                       "tolerance": row["three_se"],
                       "tolerance_basis": "the measurement's own 3 standard errors",
                       "agrees": row["cited_agrees_within_measured_three_se"]})
        if row["vacuous_share_cited_in_envelope"] is not None:
            checks.append({"id": "mode1 vacuous-ceiling share at n=%d" % row["n"],
                           "measured": row["vacuous_share"],
                           "envelope_states": row["vacuous_share_cited_in_envelope"],
                           "tolerance": row["vacuous_share_three_se"],
                           "tolerance_basis": "3 standard errors of a share over the stated trials",
                           "agrees": bool(abs(row["vacuous_share"] - row["vacuous_share_cited_in_envelope"])
                                          <= row["vacuous_share_three_se"])})
    for row in mode2:
        if row.get("envelope_cited_rate") is not None:
            checks.append({"id": "mode2 long-run rate: %s" % row["name"],
                           "measured": row["realised_long_run_rate"],
                           "envelope_states": row["envelope_cited_rate"], "tolerance": 5e-4,
                           "tolerance_basis": "the precision the envelope quotes its rates at",
                           "agrees": bool(abs(row["realised_long_run_rate"] - row["envelope_cited_rate"])
                                          < 5e-4)})
        checks.append({"id": "mode2 regret inequality violated: %s" % row["name"],
                       "measured": row["deviation_from_alpha"], "envelope_states": row["regret_bound"],
                       "tolerance": None,
                       "tolerance_basis": "a direction, not a band: the deviation must EXCEED the bound",
                       "agrees": row["violates_bound"]})
        checks.append({"id": "mode2 clip observable: %s" % row["name"], "measured": row["clip_observable"],
                       "envelope_states": True, "tolerance": None,
                       "tolerance_basis": "the envelope names a fired clip beside every one of these",
                       "agrees": row["clip_observable"] is True})
    for row in mode2_controls:
        checks.append({"id": "mode2 control holds: %s" % row["name"],
                       "measured": row["deviation_from_alpha"], "envelope_states": row["regret_bound"],
                       "tolerance": None,
                       "tolerance_basis": "a direction, not a band: the control must sit INSIDE the bound",
                       "agrees": row["violates_bound"] is False})
    checks.append({"id": "mode2 sweep: no violation fired without a clip",
                   "measured": sweep["violated_without_clip"],
                   "envelope_states": sweep["envelope_cited_violated_without_clip"], "tolerance": 0,
                   "tolerance_basis": "an exact count over the sweep's own sequences",
                   "agrees": sweep["violated_without_clip"] == sweep["envelope_cited_violated_without_clip"]})
    checks.append({"id": "mode2 sweep: clipped sequences that still held",
                   "measured": sweep["held_clipped"], "envelope_states": sweep["envelope_cited_held_clipped"],
                   "tolerance": 0, "tolerance_basis": "an exact count over the sweep's own sequences",
                   "agrees": sweep["held_clipped"] == sweep["envelope_cited_held_clipped"]})
    return {"checks": checks, "all_agree": all(row["agrees"] for row in checks),
            "disagreements": [row["id"] for row in checks if not row["agrees"]]}


def build_artefact(trials: int) -> dict:
    """Every published figure of this artefact, measured now, with the module's envelope text copied beside it."""
    provenance = read_module_provenance()
    stated = int(provenance["trials_per_size"])
    if trials > stated:
        raise DriftEnvelopeUsage("SCALE: --trials %d exceeds the %d trials drift.py's envelope states; this "
                                 "producer publishes no measurement at a scale the envelope does not name"
                                 % (trials, stated))
    if trials != stated:
        provenance = dict(provenance, trials_per_size=trials,
                          scale_refusal="REDUCED scale: %d trials per size, not the %d the envelope states; "
                                        "this artefact may not be the published one" % (trials, stated))
    mode1 = measure_mode1(trials, provenance)
    mode2 = measure_mode2(provenance, mode2_constructions())
    mode2_controls = measure_mode2_controls(provenance, mode2_control_constructions())
    sweep = measure_mode2_sweep(provenance)
    weighted = _checked_tuple(drift.WEIGHTED_ENVELOPE, "WEIGHTED_ENVELOPE")
    aci = _checked_tuple(drift.ACI_ENVELOPE, "ACI_ENVELOPE")
    return {
        "producer": PRODUCER,
        "artefact_path": ARTEFACT_REL,
        "document_path": DOC_REL,
        "provenance": provenance,
        "mode1": mode1,
        "mode2": mode2,
        "mode2_controls": mode2_controls,
        "mode2_sweep": sweep,
        "weighted_envelope": list(weighted),
        "aci_envelope": list(aci),
        "not_certifiable_under_drift": drift.NOT_CERTIFIABLE_UNDER_DRIFT,
        "withdrawals": {
            "mode1": {"statement_withdrawn": "the finite-sample coverage statement",
                      "status": "withdrawn",
                      "what_the_mode_buys": "a re-weighted estimate of the target-regime quantile, and no "
                                            "bound on it",
                      "reason_owner": "drift.WEIGHTED_ENVELOPE",
                      "why": _envelope_reason(
                          weighted, r"^the finite-sample correction is the EXCHANGEABLE case's",
                          "WEIGHTED_ENVELOPE")},
            "mode2": {"statement_withdrawn": "the long-run regret statement |mean err - alpha| <= "
                                             "aci_regret_bound(T, alpha, gamma)",
                      "status": "withdrawn",
                      "what_the_mode_buys": "a threshold that tracks the target rate while its iterate stays "
                                            "inside (0,1)",
                      "reason_owner": "drift.ACI_ENVELOPE",
                      "why": _envelope_reason(aci, r"^the mechanism, stated because", "ACI_ENVELOPE")},
        },
        "reproduction": build_reproduction(mode1, mode2, mode2_controls, sweep),
    }


# ------------------------------------------------------------------------------------ the document

def _wrap(text: str, width: int = DOC_WIDTH) -> list:
    """One prose sentence, folded to the document's column width.

    The renderer's own text is wrapped; the module's envelope lines are not, because they are published as the
    module states them and a re-wrap would make the artefact's copy and the document's copy differ in bytes
    while agreeing in words -- which is the wrong thing for a guard that compares them line for line.
    """
    return textwrap.wrap(" ".join(text.split()), width=width)


def render_document(doc: dict) -> str:
    """`docs/DRIFT.md`, rendered from the artefact's bytes -- not one figure or count here is typed.

    MINOR-4 was this docstring's own overclaim: the prose spelled "Four of them are below", "Two controls
    beside them, so the four rows above" and a heading naming "the four constructions" while those counts came
    from nothing but the run that wrote them. Each is now `len()` of the artefact's own list, so a construction
    added to or dropped from the publication moves the sentence with the table instead of leaving the document
    asserting a count the table contradicts.

    The header names the command that writes the file, states both withdrawals in plain words, prints the
    module's two envelope tuples line by line, and lists the provenance the measurement read. No timestamp and
    no machine path, so the corpus lane and the corpus-less lane byte-compare the same bytes.
    """
    provenance = doc["provenance"]
    reproduction = doc["reproduction"]
    lines = ["# B3's drift envelope, published", ""]
    lines += ["Written by `python3 %(producer)s --out %(artefact)s --doc %(document)s --force`,"
              % {"producer": PRODUCER, "artefact": doc["artefact_path"], "document": doc["document_path"]},
              "and re-checked by `python3 %s --check`." % PRODUCER]
    lines += [""]
    lines += _wrap(
        "That check re-reads `src/autorate/drift.py`, re-runs every measurement below on the shipped "
        "`weighted_quantile`, `aci_threshold` and `aci_regret_bound`, byte-compares this document against a "
        "fresh render of the artefact, and refuses at exit 4 if the committed bytes cannot reproduce what they "
        "publish. Exit 3 is a measured disagreement: the artefact is written anyway, carrying both the figure "
        "the envelope states and the figure the arithmetic yielded. Nothing here reads the corpus, so both "
        "lanes re-derive the same bytes, and this document carries no timestamp and no machine path.")
    lines += [""]
    lines += _wrap(
        "Every envelope sentence below is a copy of `drift.WEIGHTED_ENVELOPE` and `drift.ACI_ENVELOPE`: the "
        "artefact stores those tuples verbatim and this renderer prints them verbatim, so an edit to that prose "
        "changes this document or reddens a row -- it cannot be quietly summarised.")
    lines += ["", "## In plain words", ""]
    withdrawal1 = doc["withdrawals"]["mode1"]
    withdrawal2 = doc["withdrawals"]["mode2"]
    lines += _wrap("**Mode 1 (a declared density ratio): the finite-sample statement is %s.** What the mode "
                   "buys instead is %s. The shipped estimator adds the constant test-point weight named in the "
                   "provenance block below instead of the test point's own target-regime weight, which is not "
                   "knowable at calibration time; the module states the reason verbatim: \"%s\". On an exactly "
                   "declared "
                   "ratio it therefore under-covers, and the Mode 1 table is that under-coverage measured "
                   "against the figure the envelope states."
                   % (withdrawal1["status"], withdrawal1["what_the_mode_buys"], withdrawal1["why"]))
    lines += [""]
    lines += _wrap("**Mode 2 (an adaptive threshold): the regret statement is %s.** The inequality this module "
                   "used to publish as mode 2's guarantee -- `|mean err - alpha| <= aci_regret_bound(T, alpha, "
                   "gamma)` -- is false on sequences the module's own validator accepts, and the %d below are "
                   "among them, "
                   "each with its realised long-run rate, its deviation from the target, and the bound it "
                   "exceeds. The clip that keeps the iterate inside the score range discards the update whenever "
                   "it fires, and every violation below has a fired clip beside it; a clip is necessary for a "
                   "violation, not sufficient, which is what the sweep counts say. The module states the "
                   "reason verbatim: \"%s\"."
                   % (withdrawal2["status"], len(doc["mode2"]), withdrawal2["why"]))
    lines += ["", "## Mode 1: the declared ratio, measured", ""]
    lines += _wrap(
        "Calibration regime %s, declared target density %s, `E_F0[w] = %s`, nominal alpha %s, seed %s, %s "
        "trials per size at sizes %s, streams derived as `%s`. Coverage: %s The envelope's own provenance "
        "names %s test points per trial, and this run does not sample them, so the figure below and the figure "
        "the envelope quotes share one Monte-Carlo layer and not two."
        % (provenance["calibration_regime"], provenance["target_density"],
           provenance["expected_weight_under_calibration"], provenance["alpha"], provenance["seed"],
           provenance["trials_per_size"], provenance["sizes"], provenance["mode1_stream_rule"],
           provenance["mode1_coverage_method"] + ".", provenance["test_points_stated_by_envelope"]))
    lines += [""]
    lines += [
        "| n | trials | realised miscoverage | standard error | 3SE | envelope states | agrees | "
        "vacuous trials | vacuous share | vacuous 3SE | vacuous envelope states |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in doc["mode1"]:
        cited_vacuous = ("not stated" if row["vacuous_share_cited_in_envelope"] is None else
                         "%.4f" % row["vacuous_share_cited_in_envelope"])
        lines.append("| %d | %d | %.6f | %.6f | %.6f | %.4f | %s | %d | %.6f | %.6f | %s |" % (
            row["n"], row["trials"], row["realised_miscoverage"], row["standard_error"], row["three_se"],
            row["envelope_cited"], row["cited_agrees_within_measured_three_se"], row["vacuous_trials"],
            row["vacuous_share"], row["vacuous_share_three_se"], cited_vacuous))
    lines += [""]
    lines += _wrap("The point of these rows is the direction, not the width of the gap: the realised rate sits "
                   "*above* the nominal rate at every published size, and the 3SE column is what lets a reader "
                   "judge whether the envelope's figure and this measurement are the same measurement.")
    lines += ["", "## Mode 2: the %d constructions, and the bound each one exceeds" % len(doc["mode2"]), "",
              "| sequence | rounds | realised long-run rate | deviation from alpha | regret bound | "
              "exceeds bound | clip observable | envelope states | agrees |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in doc["mode2"]:
        cited = row.get("envelope_cited_rate")
        lines.append("| %s | %d | %.6f | %.6f | %.6f | %s | %s | %s | %s |" % (
            row["name"], row["rounds"], row["realised_long_run_rate"], row["deviation_from_alpha"],
            row["regret_bound"], row["violates_bound"], row["clip_observable"],
            "%.6f" % cited if cited is not None else "not stated",
            cited is not None and abs(row["realised_long_run_rate"] - cited) < 5e-4))
    lines += [""]
    lines += _wrap("Beside them sit %d controls, so the %d rows above read as a falsification and not as a "
                   "blanket \"nothing holds\": there the inequality holds, and no clip fires."
                   % (len(doc["mode2_controls"]), len(doc["mode2"])))
    lines += ["", "| control | rounds | realised long-run rate | deviation from alpha | regret bound | "
              "exceeds bound | clip observable |", "|---|---|---|---|---|---|---|"]
    for row in doc["mode2_controls"]:
        lines.append("| %s | %d | %.6f | %.6f | %.6f | %s | %s |" % (
            row["name"], row["rounds"], row["realised_long_run_rate"], row["deviation_from_alpha"],
            row["regret_bound"], row["violates_bound"], row["clip_observable"]))
    sweep = doc["mode2_sweep"]
    lines += ["", "## Mode 2: the mechanism sweep", ""]
    lines += _wrap(
        "%s constructed sequences (seed %s, T=%s, %s classes cycled) at alpha=%s gamma=%s, against a bound of "
        "%s: %s of them deviate more than the bound, %s of those fired without a single clipped round, and %s "
        "clipped sequences still held. The envelope states %s violated-without-a-clip and %s clipped-but-held. "
        "Both counts are re-run by `--check`: a violation firing with no clip would make the mechanism sentence "
        "in `ACI_ENVELOPE` wrong rather than merely unproven."
        % (sweep["sequences"], sweep["seed"], sweep["rounds"], sweep["classes"], _cell(sweep["alpha"]),
           _cell(sweep["gamma"]), _cell(sweep["bound"]), sweep["violations"], sweep["violated_without_clip"],
           sweep["held_clipped"], sweep["envelope_cited_violated_without_clip"],
           sweep["envelope_cited_held_clipped"]))
    lines += ["", "## What this artefact re-tests", ""]
    for check in reproduction["checks"]:
        lines.append("- `%s`: measured %s, envelope states %s, tolerance %s (%s) -- %s" % (
            check["id"], _cell(check["measured"]), _cell(check["envelope_states"]),
            "direction only" if check["tolerance"] is None else _cell(check["tolerance"]),
            check["tolerance_basis"], "agrees" if check["agrees"] else "DISAGREES"))
    lines += [""]
    lines += _wrap("Every figure in this section is read out of `%s`; the renderer takes no number from "
                   "anywhere else, and `--check` re-runs all of them." % doc["artefact_path"])
    lines += ["", "## The envelope, as the module states it", "", "`drift.WEIGHTED_ENVELOPE`, line by line:",
              ""]
    lines += ["> %s" % line for line in doc["weighted_envelope"]]
    lines += ["", "`drift.ACI_ENVELOPE`, line by line:", ""]
    lines += ["> %s" % line for line in doc["aci_envelope"]]
    lines += ["", "The flag a marginal-only certificate carries, `drift.NOT_CERTIFIABLE_UNDER_DRIFT`:", "",
              "> %s" % doc["not_certifiable_under_drift"], "", "## Provenance", ""]
    for key in sorted(provenance):
        lines.append("- `%s`: %s" % (key, _provenance_cell(provenance[key])))
    lines += ["", "## What each withdrawal replaced", ""]
    for mode in sorted(doc["withdrawals"]):
        block = doc["withdrawals"][mode]
        # MAJOR-2's other line: this row used to print `Owner: drift.WEIGHTED_ENVELOPE` beside a summary the
        # tool wrote, which read as though the module owned the whole bullet. The constant owns the reason --
        # and only the reason, because `check_envelope_copies` refuses when that sentence is not one of its
        # lines. The summary is this file's, and the document now says so.
        lines.append("- **%s** withdraws `%s`. Reason owner: `%s`, quoted verbatim above; the summary in this "
                     "line is %s's. What it buys instead: %s." % (
                         mode, block["statement_withdrawn"], block["reason_owner"], PRODUCER,
                         block["what_the_mode_buys"]))
    return "\n".join(lines) + "\n"


def _cell(value) -> str:
    """One published figure as text, at the precision the artefact stores it at.

    A float is never printed with the 17 significant digits `repr` gives it: the last bits of a double are a
    platform fact (ledger R-121), and this document is the prose a reader quotes.
    """
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, float):
        return format(value, "." + str(PUBLISHED_DECIMALS) + "f")
    return str(value)


def _provenance_cell(value) -> str:
    if isinstance(value, dict):
        return "; ".join("`%s`: %s" % (key, _provenance_cell(value[key])) for key in sorted(value))
    if isinstance(value, (list, tuple)):
        return ", ".join(_provenance_cell(item) for item in value)
    return "`%s`" % json.dumps(value)


# --------------------------------------------------------------------------------- read and check

def _refuse(declared: bool, kind_name: str, message: str):
    """Raise the refusal whose code is set by who named the path, not by the kind of defect.

    A declared-path problem belongs to the checkout (4); the identical defect in a file the operator named
    belongs to the operator (2), and their next action differs -- re-run the producer versus name the right
    path. One helper keeps that axis from being re-decided, and re-litigated, at every check site.
    """
    raise (DriftEnvelopeState if declared else DriftEnvelopeUsage)("%s: %s" % (kind_name, message))


def _unplanned_read(exc: BaseException, *, stored: bool) -> tuple:
    """(the name, the clause saying what was wanted) for an exception no check site raised on purpose.

    BLOCKER-1 measured the alternative: a top-level-valid artefact with ONE subkey removed made
    `check_provenance`, `rederive_and_compare` and `render_document` subscript a key that was not there, and
    because a `KeyError` is neither a `ValueError` nor a `TypeError` both catch-alls let it through -- so the
    operator got a traceback at exit 1, the one code this tool's contract says does not exist. The tuples at
    `_run_check` and `main` now carry `LookupError` and `AttributeError` (`main`'s also carries
    `ArithmeticError` and `OSError`), and this says what they caught: the kind of defect and the name that was
    wanted. It does not choose an exit code -- the caller still decides that from who named the path, which is
    the difference between a net under the contract and a swallow over it. `stored` says which side of the
    read the defect is on: bytes this build published, or bytes this run is trying to publish.
    """
    if isinstance(exc, LookupError):
        if stored:
            return ("ARTEFACT SHAPE", "%s: %s -- the subkey this build reads is not in the stored artefact"
                    % (type(exc).__name__, exc))
        return ("INVARIANT", "%s: %s -- this run built an artefact that does not carry the key its own "
                            "renderer reads" % (type(exc).__name__, exc))
    if isinstance(exc, AttributeError):
        return ("PUBLISHED SOURCE UNAVAILABLE",
                "%s: %s -- the module this artefact copies no longer holds that name"
                % (type(exc).__name__, exc))
    return type(exc).__name__, "%s: %s" % (type(exc).__name__, exc)


def read_artefact(path: Path, *, declared: bool) -> dict:
    """The artefact's bytes, or the named refusal that says why they are not an artefact."""
    if not path.is_file():
        _refuse(declared, "PUBLISHED ARTEFACT UNAVAILABLE" if declared else "ARTEFACT UNAVAILABLE",
                "%s does not exist -- there is nothing to re-derive" % path)
    try:
        loaded = json.loads(path.read_text())
    except ValueError as exc:
        _refuse(declared, "ARTEFACT SHAPE", "%s is not readable JSON: %s" % (path, exc))
    if not isinstance(loaded, dict):
        _refuse(declared, "ARTEFACT SHAPE", "%s is a JSON %s, not an artefact object"
                % (path, type(loaded).__name__))
    missing = [key for key in REQUIRED_KEYS if key not in loaded]
    if missing:
        _refuse(declared, "ARTEFACT SHAPE", "%s has no %s, so the envelope it publishes cannot be read from it"
                % (path, ", ".join(missing)))
    return loaded


def check_envelope_copies(doc: dict, *, declared: bool) -> None:
    """The stored envelope lines against the module's tuples, line for line."""
    for key, name in (("weighted_envelope", "WEIGHTED_ENVELOPE"), ("aci_envelope", "ACI_ENVELOPE")):
        stored = doc[key]
        if not isinstance(stored, list) or not all(isinstance(line, str) for line in stored):
            _refuse(declared, "ARTEFACT SHAPE", "the artefact's %s is a %s, not a list of lines"
                    % (key, type(stored).__name__))
        module_value = _checked_tuple(getattr(drift, name), name)
        if len(stored) != len(module_value):
            _refuse(declared, "ENVELOPE TRUNCATED",
                    "the artefact carries %d lines of drift.%s while the module states %d, so a withdrawal "
                    "sentence is missing from what this artefact publishes (or one was added that the module "
                    "does not make)" % (len(stored), name, len(module_value)))
        for index, (stored_line, module_line) in enumerate(zip(stored, module_value)):
            if stored_line != module_line:
                _refuse(declared, "ENVELOPE TRUNCATED",
                        "the artefact's line %d of drift.%s is not the module's line %d, so the published "
                        "withdrawal is not the one the module makes" % (index, name, index))
    if doc["not_certifiable_under_drift"] != drift.NOT_CERTIFIABLE_UNDER_DRIFT:
        _refuse(declared, "ENVELOPE TRUNCATED", "the stored marginal-only flag is not "
                "drift.NOT_CERTIFIABLE_UNDER_DRIFT")
    for mode, name in (("mode1", "WEIGHTED_ENVELOPE"), ("mode2", "ACI_ENVELOPE")):
        block = doc["withdrawals"][mode]
        if block.get("reason_owner") != "drift.%s" % name:
            _refuse(declared, "WITHDRAWAL PROSE", "the artefact's `withdrawals.%s` names %r as the owner of "
                    "its reason while the renderer prints that reason as the module's own words; the owner "
                    "must be `drift.%s`" % (mode, block.get("reason_owner"), name))
        if block["why"] not in _checked_tuple(getattr(drift, name), name):
            _refuse(declared, "WITHDRAWAL PROSE",
                    "the artefact's `withdrawals.%s.why` is a sentence drift.%s does not contain, and %s "
                    "quotes it verbatim after \"the module states the reason verbatim:\" -- a paraphrase stored "
                    "here is the defect MAJOR-2 measured, so the reason has to be one of the module's lines"
                    % (mode, name, DOC_REL))


def check_provenance(doc: dict, *, declared: bool) -> None:
    """The artefact's provenance against the figures read out of the module again, now.

    This is what makes a moved seed or trial count a refusal rather than a quiet restamp: the module owns those
    numbers, so an artefact that disagrees claims a measurement nobody ran.
    """
    module = read_module_provenance()
    stored = doc["provenance"]
    if not isinstance(stored, dict):
        _refuse(declared, "ARTEFACT SHAPE", "the artefact's provenance is a %s, not a mapping"
                % (type(stored).__name__,))
    for key in sorted(module):
        if key in stored and stored[key] != module[key]:
            _refuse(declared, "PROVENANCE", "the artefact's `%s` is %r while drift.py's envelope states %r -- "
                    "the published measurement is attributed to a provenance the module does not name"
                    % (key, stored[key], module[key]))
    for row in doc["mode1"]:
        if not isinstance(row, dict) or int(row["trials"]) != int(stored["trials_per_size"]):
            _refuse(declared, "PROVENANCE", "a mode-1 row states %r trials while the provenance block states "
                    "%r" % (row.get("trials") if isinstance(row, dict) else row,
                            stored.get("trials_per_size")))


def rederive_and_compare(doc: dict, *, declared: bool) -> list:
    """Re-run every measurement the artefact publishes; return the labels that disagree.

    Shared by the publishing run's own post-write self-check and by `--check`, which is the point: the gate the
    controller wires into `verify` and the run that wrote the bytes perform the same comparison, so a published
    figure cannot be true only on the machine that typed it.
    """
    trials = int(doc["provenance"]["trials_per_size"])
    provenance = read_module_provenance()
    if trials != int(provenance["trials_per_size"]):
        provenance = dict(provenance, trials_per_size=trials)
    mode1 = measure_mode1(trials, provenance)
    mode2 = measure_mode2(provenance, mode2_constructions())
    mode2_controls = measure_mode2_controls(provenance, mode2_control_constructions())
    sweep = measure_mode2_sweep(provenance)
    fresh = build_reproduction(mode1, mode2, mode2_controls, sweep)
    stored = doc["reproduction"]
    if not isinstance(stored, dict) or "checks" not in stored:
        _refuse(declared, "ARTEFACT SHAPE", "the artefact has no reproduction block to compare")
    by_id = {row["id"]: row for row in stored["checks"]}
    fresh_by_id = {row["id"]: row for row in fresh["checks"]}
    disagreements = []
    for label, row in fresh_by_id.items():
        earlier = by_id.get(label)
        if earlier is None:
            disagreements.append("claim %s is not in the artefact" % label)
        elif earlier["agrees"] != row["agrees"] or earlier["measured"] != row["measured"]:
            disagreements.append("%s: the artefact published agrees=%s measured=%s and the re-run gives "
                                 "agrees=%s measured=%s (envelope states %s)"
                                 % (label, earlier["agrees"], earlier["measured"], row["agrees"],
                                    row["measured"], row["envelope_states"]))
    disagreements.extend("claim %s is in the artefact but this producer no longer makes it" % label
                         for label in sorted(set(by_id) - set(fresh_by_id)))
    for stored_row, fresh_row in zip(doc["mode1"], mode1):
        for field in ("realised_miscoverage", "standard_error", "three_se", "vacuous_share"):
            if stored_row[field] != fresh_row[field]:
                disagreements.append("mode1 n=%d %s: artefact %r, re-run %r" % (
                    fresh_row["n"], field, stored_row[field], fresh_row[field]))
    for section, fresh_rows in (("mode2", mode2), ("mode2_controls", mode2_controls)):
        for stored_row in doc[section]:
            match = [row for row in fresh_rows if row["name"] == stored_row["name"]]
            if not match:
                disagreements.append("%s %s: this producer no longer publishes that sequence"
                                     % (section, stored_row["name"]))
                continue
            fresh_row = match[0]
            scores = materialise(stored_row["construction"])
            if sequence_digest(scores) != stored_row["sequence_digest_sha256"] or len(scores) != stored_row["rounds"]:
                disagreements.append("%s %s: the stored recipe no longer materialises the sequence the "
                                     "artefact measured" % (section, stored_row["name"]))
            # Exact, on the canonical grid both sides are produced at -- the same rule mode 1 uses above. The
            # `1e-9` this replaces was a tolerance on raw doubles: it could not tell a re-run on another
            # libm from a re-run that measured something else, and it went red the moment storage was
            # canonicalised because the stored value is the rounded one.
            for field in ("realised_long_run_rate", "regret_bound", "deviation_from_alpha"):
                if stored_row[field] != fresh_row[field]:
                    disagreements.append("%s %s %s: artefact %r, re-run %r"
                                         % (section, stored_row["name"], field, stored_row[field],
                                            fresh_row[field]))
    stored_sweep = doc["mode2_sweep"]
    for field in ("violations", "violated_without_clip", "clipped", "held_clipped", "sequences", "rounds",
                  "seed", "bound"):
        if stored_sweep[field] != sweep[field]:
            disagreements.append("mode2_sweep %s: artefact %r, re-run %r"
                                 % (field, stored_sweep[field], sweep[field]))
    return disagreements


# --------------------------------------------------------------------------------------------- CLI

def _is_declared(candidate, declared: Path) -> bool:
    """Whether an operator's path IS the path this build declares, resolved rather than string-compared.

    The documented invocation names `data/drift_envelope.json`, and the module constant resolves to the
    checkout's absolute path; a string comparison would refuse the command that writes the artefact. Resolving
    both sides is what makes the guard about identity instead of about spelling.
    """
    try:
        return Path(candidate).resolve() == declared.resolve()
    except OSError:
        return False


def _run_check(args) -> int:
    """Re-read and re-derive the published bytes; write nothing, and name every disagreement."""
    declared = args.artefact is None or _is_declared(args.artefact, ARTEFACT_PATH)
    path = ARTEFACT_PATH if declared else Path(args.artefact)
    try:
        doc = read_artefact(path, declared=declared)
        check_envelope_copies(doc, declared=declared)
        check_provenance(doc, declared=declared)
        # Everything the stored bytes alone can answer is read BEFORE the re-derivation is paid for: an
        # artefact this build cannot render is a shape problem, and discovering it after 4000 trials only
        # says the same sentence 0.7s later.
        rendered = render_document(doc)
        disagreements = rederive_and_compare(doc, declared=declared)
        if not DOC_PATH.is_file():
            disagreements.append("DOCUMENT: %s is missing, so the published prose cannot be compared"
                                 % DOC_PATH)
        elif DOC_PATH.read_text() != rendered:
            disagreements.append("DOCUMENT: %s is not a render of %s" % (DOC_PATH, path))
    except DriftEnvelopeState as exc:
        print("%s: %s" % (PRODUCER, exc), file=sys.stderr)
        return EXIT_DRIFT
    except DriftEnvelopeUsage as exc:
        print("%s: %s" % (PRODUCER, exc), file=sys.stderr)
        return EXIT_USAGE
    except (ValueError, TypeError, ArithmeticError, OSError, LookupError, AttributeError) as exc:
        # The net BLOCKER-1 needed: a stored row subscripts its own keys, so a shaped artefact missing one
        # subkey used to leave this function as a traceback at exit 1. It is a refusal here, named by the
        # class of defect and the key that was wanted, and the code is still decided by who named the path.
        kind_name, detail = _unplanned_read(exc, stored=True)
        whose = ("this is the artefact this build declares, so re-run "
                 "`python3 %s --out %s --doc %s --force` to rewrite it"
                 % (PRODUCER, ARTEFACT_REL, DOC_REL)) if declared else (
                "you named this path, so naming the published artefact is the next action")
        print("%s: %s: %s cannot be read as a published drift envelope (%s) -- %s"
              % (PRODUCER, kind_name, path, detail, whose), file=sys.stderr)
        return EXIT_DRIFT if declared else EXIT_USAGE
    if disagreements:
        # The same axis as every other check refusal: the defect's class names WHAT is wrong, and who named the
        # path decides whose fault it is. A scratch artefact the operator pointed at is their input (2); the
        # declared artefact is this build's own table, and a broken one there is the checkout's (4).
        code = EXIT_DRIFT if declared else EXIT_USAGE
        print("%s: %s: %s cannot reproduce what it publishes (%d claim%s)"
              % (PRODUCER, "ARTEFACT DRIFT" if declared else "NAMED ARTEFACT DOES NOT REPRODUCE", path,
                 len(disagreements), "" if len(disagreements) == 1 else "s"), file=sys.stderr)
        for label in disagreements:
            print("  DRIFT: %s" % label, file=sys.stderr)
        return code
    print("re-derived %d claims from %s; the document is a render of those bytes"
          % (len(doc["reproduction"]["checks"]), path))
    return EXIT_CERTIFIED


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PRODUCER, description="Publish B3's drift envelope.")
    parser.add_argument("--out", default=None, help="where to write the artefact (default %s)" % ARTEFACT_PATH)
    parser.add_argument("--doc", default=None,
                        help="also write the derived document (the published %s)" % DOC_PATH)
    parser.add_argument("--force", action="store_true", help="replace an existing --out")
    parser.add_argument("--trials", type=int, default=None,
                        help="trials per size; only the count drift.py's envelope states may be published")
    parser.add_argument("--check", action="store_true",
                        help="re-read the published artefact and re-derive it; writes nothing")
    parser.add_argument("--artefact", default=None,
                        help="with --check, an artefact path you are naming (default %s)" % ARTEFACT_REL)
    args = parser.parse_args(argv)

    if args.check:
        if args.out is not None or args.doc is not None or args.force:
            print("%s: CHECK: --check writes nothing, so --out, --doc and --force do not belong to it "
                  "(use --artefact to name a file to check). Nothing was written" % PRODUCER, file=sys.stderr)
            return EXIT_USAGE
        return _run_check(args)

    declared_artefact = _is_declared(args.out, ARTEFACT_PATH) if args.out is not None else True
    declared_document = _is_declared(args.doc, DOC_PATH) if args.doc is not None else True
    publishing = args.doc is not None or args.out is None
    # Bound before the try: the net below has to name the destination it refused to write, and a refusal
    # raised by `read_module_provenance()` earlier would otherwise reach its own handler unbound.
    out = ARTEFACT_PATH if args.out is None else Path(args.out)
    try:
        if args.doc is not None and args.out is None:
            print("%s: PAIR: --doc publishes %s, which is rendered from the artefact this run writes, so it "
                  "requires --out %s as well (no --out was given). Nothing was written"
                  % (PRODUCER, args.doc, ARTEFACT_REL), file=sys.stderr)
            return EXIT_USAGE
        if args.out is not None and args.doc is None and declared_artefact:
            print("%s: PAIR: --out names the published artefact path %s, and leaving %s stale beside it is "
                  "exactly the drift this gate exists to catch; pass --doc %s, or point --out somewhere else "
                  "for a scratch run. Nothing was written" % (PRODUCER, ARTEFACT_REL, DOC_REL, DOC_REL),
                  file=sys.stderr)
            return EXIT_USAGE
        if args.out is not None and args.doc is not None and not (declared_artefact and declared_document):
            print("%s: PAIR: --doc publishes the document that quotes the artefact at its declared path, so "
                  "the pair must be --out %s --doc %s (this run named --out %s --doc %s). Nothing was written"
                  % (PRODUCER, ARTEFACT_REL, DOC_REL, args.out, args.doc), file=sys.stderr)
            return EXIT_USAGE
        if publishing:
            stated = read_module_provenance()["trials_per_size"]
            if args.trials is not None and args.trials != stated:
                print("%s: SCALE: --trials %s is not the %d trials drift.py's envelope states, and this run "
                      "would publish %s and %s beside figures the envelope does not name. A reduced-scale "
                      "measurement is allowed only into a scratch --out that is not a published path. Nothing "
                      "was written" % (PRODUCER, args.trials, stated, ARTEFACT_REL, DOC_REL),
                      file=sys.stderr)
                return EXIT_USAGE
        if args.out is None and args.doc is None:
            # MINOR-6. The pair guard above keyed on the flags a reader typed, so naming `--out data/...`
            # explicitly was refused while reaching the SAME declared destination by defaulting `--out` was
            # not: `python3 tools/drift_envelope.py --force` rewrote the artefact and left the document that
            # quotes it untouched. The identity that matters is the destination, not the spelling.
            print("%s: PAIR: this run writes the published artefact %s (the default) and no document, which "
                  "leaves %s quoting figures that are no longer the ones on disk -- exactly the drift this "
                  "gate exists to catch. Pass --doc %s to write the pair, or point --out at a scratch path. "
                  "Nothing was written" % (PRODUCER, ARTEFACT_REL, DOC_REL, DOC_REL), file=sys.stderr)
            return EXIT_USAGE

        if out.exists() and not args.force:
            print("%s: %s already exists; pass --force to replace it" % (PRODUCER, out), file=sys.stderr)
            return EXIT_USAGE
        doc = build_artefact(args.trials if args.trials is not None
                             else read_module_provenance()["trials_per_size"])
        text = render_document(doc)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
            if args.doc is not None:
                Path(args.doc).write_text(text)
        except OSError as exc:
            print("%s: %s -- nothing further was written" % (PRODUCER, exc), file=sys.stderr)
            return EXIT_USAGE
    except DriftEnvelopeState as exc:
        print("%s: %s -- nothing was written" % (PRODUCER, exc), file=sys.stderr)
        return EXIT_DRIFT
    except DriftEnvelopeUsage as exc:
        print("%s: %s -- nothing was written" % (PRODUCER, exc), file=sys.stderr)
        return EXIT_USAGE
    except (ValueError, TypeError, ArithmeticError, OSError, LookupError, AttributeError) as exc:
        # BLOCKER-1's other half. This run had not reached its write yet, so nothing is on disk and the
        # operator needs the destination, the class, and the name that was wanted -- not a traceback. The
        # code is the destination's, not the exception's: a producer that cannot build the pair THIS build
        # declares is the checkout's defect (4); a run aimed at a path the operator typed is theirs (2).
        kind_name, detail = _unplanned_read(exc, stored=False)
        whose = ("this run would have written the artefact this build declares, so the producer is what "
                 "needs fixing") if declared_artefact else (
                "this run was aimed at a path you named, so its arguments are what to check")
        print("%s: %s: %s could not be published (%s) -- %s. Nothing was written"
              % (PRODUCER, kind_name, out, detail, whose), file=sys.stderr)
        return EXIT_DRIFT if declared_artefact else EXIT_USAGE

    disagreements = doc["reproduction"]["disagreements"]
    print("wrote %s%s" % (out, " and %s" % args.doc if args.doc is not None else ""))
    if args.doc is None:
        print("  %s was not written: this run named no --doc, so it published no document" % DOC_REL)
    provenance = doc["provenance"]
    print("  provenance: seed %s, %s trials per size at sizes %s, alpha=%s gamma=%s, target density %s"
          % (provenance["seed"], provenance["trials_per_size"], provenance["sizes"], provenance["alpha"],
             provenance["gamma"], provenance["target_density"]))
    for row in doc["mode1"]:
        print("  mode 1 n=%d: realised miscoverage %.6f (3SE %.6f) against the envelope's %.4f; vacuous share "
              "%.6f" % (row["n"], row["realised_miscoverage"], row["three_se"], row["envelope_cited"],
                        row["vacuous_share"]))
    for row in doc["mode2"]:
        print("  mode 2 %-36s T=%-6d realised %.6f, bound %.6f, exceeds: %s, clip observable: %s"
              % (row["name"], row["rounds"], row["realised_long_run_rate"], row["regret_bound"],
                 row["violates_bound"], row["clip_observable"]))
    sweep = doc["mode2_sweep"]
    print("  mode 2 sweep: %d sequences, %d violations, %d violated without a clip, %d clipped but held"
          % (sweep["sequences"], sweep["violations"], sweep["violated_without_clip"], sweep["held_clipped"]))
    print("  re-derived %d claims, %d disagree" % (len(doc["reproduction"]["checks"]), len(disagreements)))
    if disagreements:
        for label in disagreements:
            print("  NOT REPRODUCED: %s" % label, file=sys.stderr)
        print("  claim the drift envelope = not_reproduced: the artefact above carries both the figure the "
              "envelope states and the figure this run measured", file=sys.stderr)
        return EXIT_NOT_CERTIFIABLE
    return EXIT_CERTIFIED


if __name__ == "__main__":
    sys.exit(main())
