"""Two-way certification for `score`: the ordinal set gate, over the modal-anchored chain family.

Everything a reader would compare between this file and `certify_choice.py` is the same on purpose:
one case-level split rule, one `split_quantile` call, one shared counter (`case_count.count_outcome`)
driven by ONE `decide` callable, the same refusal ladder in the same order, the same evidence-only
diagnostic grid, the same three claims and union-bound level. Two gates whose numbers are computed
differently cannot be contrasted, and spec §6.4 asks for the contrast on the same records.

Three differences, each deliberate, each guarded by a test in `tests/test_certify_score.py`:

* **Subject.** This gate certifies `qtype == "score"` records and refuses outright a population that
  carries none, because a `score` certificate over `choice` records names the wrong subject -- and a
  certificate that names the wrong subject is a permission nobody asked for. It is also why this gate
  cannot call `certify_choice.split_cal`: that function's eligibility rule *is* the choice subject, so
  on score records it drops everything and hands back two empty halves. The partition rule it applies
  after that filter is mirrored here one for one, and one test pins the two partitions against each
  other so the mirror cannot quietly become two different held-out halves.
* **Family.** The sets come from `ordinal.interval_set` (ruling R-68: the modal-anchored chain, not
  the minimum-length reach-mass interval and not a top-mass prefix), and that function owns its own
  sublevel loop. Routing it through `conformal.conformal_set` would pass the recorded draw `u` per
  level, which R-78 rules out, so the ordinal family is deliberately NOT registered in
  `conformal.METHODS`. That allowlist is the two set-gate scores; widening it would let the CHOICE
  gate accept `method="ordinal"` on choice records, which is the subject mismatch the guard above
  exists to refuse. Recording `method="ordinal"` on the certificate is a different thing and is
  correct: `certify_threshold` already established that `method` names the rule that actually ran.
* **Threshold, not level.** The certified set is `{g : score_ordinal(probs, g) <= qhat}`, and the
  value handed to `interval_set` is the calibration quantile. `alpha` fixes WHICH order statistic
  qhat is; it is never itself the threshold (ruling R-92a). Passing `alpha` there produces a nominal
  1-alpha set with no finite-sample correction -- a number with no content, which is the failure
  `split_quantile`'s vacuity flag exists to catch, and the reason the parameter used to be called
  `alpha` is gone.

`alpha` is an INPUT, not a label (R-28), exactly as in the set gate: the operating point is one
calibration-half fact, chosen at the requested coverage and never swept on the evaluation half. The
grid survives only as a diagnostic that refusals are allowed to quote, and it says so.

Empty certified sets are refusals, not errors, and not automations (R-17): they are reported in
`empties` so the automation rate's denominator stays visible. On a clean ordinal task an empty set is
the ONLY way the truth escapes the certified interval, because every non-empty sublevel set contains
the modal level -- so the coverage mass and the refusal mass are the same cases, and the suite asserts
that rather than assuming it.

The CASE arithmetic is not owned here: `case_count.count_outcome` counts records and cases for
whichever rule is being certified, and this module supplies the chain-set rule as that counter's ONE
`decide` callable, which also declares the label the rule submits (R-34, R-66). `mean_interval_length`
is THIS gate's name for the counter's `mean_measure`, because shared arithmetic that names a published
figure would give that figure two owners; the shape has one mean field, so the value is carried in the
certificate's `mean_set_size` slot and the envelope says which name is which -- the same arrangement
the threshold gate documents for `mean_score`, and Task 5 owns versioning the shape.

Evidence boundary, stated so a later reader does not mistake the mechanism for a measurement: the
offline archive carries zero `score` answers (the counts are the inventory's, not restated here), so
every number this gate publishes is a function of the records the caller hands in, and Plan B2's
demonstration data is synthetic with known answers. The gate cannot see provenance, so it does not
claim any: the envelope says no upstream provenance was checked. The real ordinal certificate is
Plan C's driver, and the README must not blur the two.
"""
from __future__ import annotations

import random
from typing import Optional, Sequence

from .case_count import Verdict, case_key, count_outcome
from .certificate import BOUND_UNIT_CASE, BOUND_UNIT_RECORD, N_CLAIMS, Certificate, Reason
from .conformal import classify_set, split_quantile
from .ordinal import interval_set, score_ordinal
from .tails import bound_width, clopper_pearson_upper

MIN_CAL = 60
MIN_EVAL = 60
METHOD = "ordinal"
# The subject this gate will certify. Named, because the guard that refuses a foreign population and
# the eligibility filter that drops foreign records are the same fact stated twice.
SUBJECT = "score"
DIAGNOSTIC_GRID = tuple(round(0.01 * i, 2) for i in range(1, 30))
_BASE_ENVELOPE = (
    "exchangeability within group assumed; no group conditioning applied",
    "marginal certificate only - not group-conditional",
    "certified on the records handed in; no upstream provenance is checked here, and live traffic "
    "shift is not covered",
)

# `classify_set` spells its multi-label outcome "escalate"; the shared counter's published name for
# that bucket is "multi" (it is what `multi_label` counts). The translation is the set rule's own
# business: `case_count` must not learn set vocabulary, or the threshold gate would depend on the set
# gate's internals. This is the choice gate's map restated for this rule, not imported from it --
# `_SET_KINDS` there is one rule's vocabulary, and two rules that share a private dict stop being able
# to disagree about a name, which is the accident this project keeps having to un-share.
_SET_KINDS = {"auto": "auto", "empty": "empty", "escalate": "multi"}


def _eligible(records: Sequence):
    """Keep the records THIS gate may certify, and count the ones it dropped.

    Same two buckets as the set gate, in the same order, so a reader comparing two certificates can
    tell "no gold labels" from "wrong subject" without reading either module's source.
    """
    kept, dropped = [], {"skipped_no_gold": 0, "skipped_wrong_qtype": 0}
    for r in records:
        if r.qtype != SUBJECT:
            dropped["skipped_wrong_qtype"] += 1
        elif not r.calibratable:
            dropped["skipped_no_gold"] += 1
        else:
            kept.append(r)
    return kept, dropped


def split_cal(records: Sequence, seed: int = 0):
    """Split by CASE, not by record -- the choice gate's rule, applied to this gate's subject.

    Whole cases go to one side. The set gate's docstring records what a record-level split did to the
    committed archive (44 of 53 evaluation cases also sat in the calibration half, so the quantile was
    fixed on the cases later held out to test it); the violation is of the exchangeability unit, not
    of a looseness budget, and it applies identically to ordinal records. The halves stay balanced by
    record count, and the partition is the one `tests/test_certify_score.py` pins byte-for-byte
    against `certify_choice.split_cal`: this copy exists only because that function's filter is the
    choice subject, which would drop every record this gate is about.
    """
    recs, dropped = _eligible(records)
    groups = {}
    for r in recs:
        groups.setdefault(case_key(r), []).append(r)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    half = len(recs) // 2
    cal_keys = []
    seen = 0
    for k in keys:
        if seen >= half:
            break
        cal_keys.append(k)
        seen += len(groups[k])
    inplace = set(cal_keys)
    cal = [r for k in cal_keys for r in groups[k]]
    ev = [r for r in recs if case_key(r) not in inplace]
    return cal, ev, dropped


def _scores(records) -> list:
    """The chain score of each record's gold level: the mass of its minimum span to the modal level.

    `u` is not passed. The family accepts it and must not read it (R-78), and a scoring function that
    threaded the draw through "for symmetry" is how a randomised threshold comes back by the side
    door; the gate's own test re-draws every `u` and asserts the certificate does not move.
    """
    return [score_ordinal(r.probs, r.gold_index) for r in records]


def _score_rule(qhat):
    """The chain-set rule as the shared counter's ONE `decide` callable (R-66).

    The label this rule submits is the one inside its certified singleton, because that is the label
    `gate.py:66-67` delivers when the set is a singleton -- `options[C[0]]`, not the record's
    `predicted`. For THIS family the two readings coincide on every well-formed record, and that is
    worth stating because it is not the archive's accident: a sublevel set always contains the modal
    level, so a one-level set IS the argmax. The submission is still read from the set rather than
    from the record, so a record that declares an answer other than the level its certified singleton
    contains is scored on what the gate would have sent (the suite builds exactly that population).

    The measure is the interval's length in levels, carried for EVERY evaluated record: a refusal
    contributes 0, not a missing value, because the mean this gate publishes is over all of them --
    which is what the set gate's mean has always been, and the contrast with the threshold gate's
    `measure=None` (a score that does not exist must not enter a mean of scores).
    """
    def decide(r):
        C = interval_set(r.probs, qhat)
        kind = classify_set(C)
        outcome = _SET_KINDS.get(kind)
        if outcome is None:
            # This gate's own guard, deliberately ahead of `count_outcome`'s: the counter raises a
            # `ValueError` for an unknown outcome too, but it can only name the buckets IT knows, and
            # a raw `_SET_KINDS[...]` here would raise `KeyError` instead -- which `cli.py` does not
            # map to any exit code, so an unmapped set outcome would break the documented 0/2/3/4
            # contract at rc 1. Naming the unknown outcome and the keys this map knows keeps the
            # failure a usage error (rc 2) and points the reader at the translation, not the counter.
            raise ValueError("the chain-set rule produced an outcome %r this gate does not name; "
                             "_SET_KINDS knows %s" % (kind, sorted(_SET_KINDS)))
        return Verdict(outcome, r.options[C[0]] if outcome == "auto" else None, len(C))

    return decide


def _outcome(ev, qhat):
    """One application of the chain-set rule, counted by the shared case arithmetic (R-34)."""
    observed = count_outcome(ev, _score_rule(qhat))
    observed["mean_interval_length"] = observed.pop("mean_measure")
    return observed


def certify_score(records: Sequence, alpha: float = 0.05, beta: float = 0.05, delta: float = 0.05,
                  seed: int = 0, grid: Optional[Sequence[float]] = None) -> Certificate:
    """Certify the automation rate the coverage level `1 - alpha` buys for ordinal sets, under `beta`.

    Act iff the certified interval is a single level. `beta` bounds P(wrong | automated); `delta` is
    the level each published bound is tested at, and `N_CLAIMS` of them are made, so the joint
    confidence is 1 - N_CLAIMS*delta.

    Raises `ValueError` -- a usage error, which the CLI maps to exit 2 -- for a level outside (0,1),
    for a population that spans more than one `backend`, and for a population that carries no `score`
    record at all. The last one is the subject guard: `score >= lambda` on a foreign qtype automates
    nothing and would otherwise come back as a clean-looking refusal instead of a mistake about what
    was being certified, and this gate computes no certificate over choice traffic in any form.
    """
    for name, v in (("alpha", alpha), ("beta", beta), ("delta", delta)):
        if not 0.0 < v < 1.0:
            raise ValueError("%s must be in (0,1), got %r" % (name, v))
    batch = list(records)
    counts = {}
    for r in batch:
        counts[r.qtype] = counts.get(r.qtype, 0) + 1
    if batch and SUBJECT not in counts:
        raise ValueError(
            "the ordinal set gate certifies qtype=%r records and this population carries %s; a "
            "certificate over the wrong subject is a permission for a decision nobody calibrated"
            % (SUBJECT, sorted(counts)))
    cal, ev, dropped = split_cal(batch, seed)
    subjects = {r.backend for r in cal + ev}
    if len(subjects) > 1:
        # certify_threshold.py:247-255 owns this correction for its own traffic and this gate inherits
        # it rather than the set gate's older `backend=None` answer: a certificate that names no
        # subject names no model, so `cli.py` refuses to pair it and `gate.py:46-57` treats it as
        # authorising NOTHING -- it would certify traffic its own deployment declines to act on.
        raise ValueError("a certificate names one subject; this population spans backends %s -- "
                         "certify one backend at a time" % ", ".join(sorted(subjects)))
    backend = subjects.pop() if len(subjects) == 1 else None
    grid = tuple(grid or DIAGNOSTIC_GRID)
    # The evaluation half is named, not summarised, exactly as in the set gate: "the two certificates
    # were compared case by case" is only checkable if the cases are on the record.
    meta = {**dropped, "diagnostic_grid_size": len(grid), "seed": seed,
            "alpha": alpha, "beta": beta, "total_labelled": len(cal) + len(ev),
            "eval_ids": sorted(r.id for r in ev), "cal_ids": sorted(r.id for r in cal)}
    if not (cal or ev):
        return Certificate.refused(Reason.NO_GOLD_LABELS, alpha=alpha, beta=beta,
                                   n_cal=0, n_eval=0, delta=delta, backend=backend, method=METHOD,
                                   detail="no labelled %s records to calibrate on" % SUBJECT,
                                   meta=meta)
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(Reason.N_BELOW_MIN, alpha=alpha, beta=beta,
                                   n_cal=len(cal), n_eval=len(ev), delta=delta, backend=backend,
                                   method=METHOD,
                                   detail="need %d/%d, have %d/%d" % (MIN_CAL, MIN_EVAL,
                                                                      len(cal), len(ev)),
                                   meta=meta)
    cal_scores = _scores(cal)
    n_ev = len(ev)
    # (probs, qhat): the second positional is the quantile. `alpha` never appears in this argument
    # slot, and the rename in ordinal.py is what keeps that visible at the call site (R-92a).
    qhat, vacuous = split_quantile(cal_scores, alpha)
    observed = _outcome(ev, qhat)
    autom, err = observed["automated"], observed["errors"]
    n_case, auto_case, err_case = (observed["n_cases"], observed["automated_cases"],
                                   observed["erroneous_cases"])
    half_width = bound_width(n_case, delta) / 2.0
    meta.update(empties=observed["empties"], multi_label=observed["multi_label"],
                automated=autom, errors_among_automated=err, n_eval_cases=n_case,
                automated_cases=auto_case, erroneous_cases=err_case,
                n_cal_cases=len({case_key(r) for r in cal}),
                # The choice gate's note, and the same split it now has to state: three headline
                # bounds over cases, every curve row and its `closest_attempt` over records
                # (ledger #37/#71).
                unit_note="%d evaluation records over %d distinct cases: the certificate's own bounds "
                          "-- conditional, marginal and the automation-rate interval -- use the %s "
                          "denominator, because repeats of one case are one observation, while every "
                          "diagnostic curve row and its closest_attempt copy bounds the %s denominator "
                          "and names its own operands beside it"
                          % (n_ev, n_case, BOUND_UNIT_CASE, BOUND_UNIT_RECORD))
    if vacuous:
        return Certificate.refused(
            Reason.VACUOUS_QUANTILE, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="the %.3f-quantile of %d calibration chain masses is %.3f, so every level of "
                   "every ballot would be certified: a set that is the whole interval automates "
                   "nothing and bounds nothing" % (alpha, len(cal), qhat),
            meta=_with_diagnostic(meta, cal_scores, ev, grid, beta, delta))
    if autom == 0 or auto_case == 0:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="at coverage %.3f no evaluation case produced a singleton interval (%d empty, "
                   "%d wider than one level, of %d)" % (1.0 - alpha, observed["empties"],
                                                        observed["multi_label"], n_ev),
            meta=_with_diagnostic(meta, cal_scores, ev, grid, beta, delta))
    cond_hi = clopper_pearson_upper(err_case, auto_case, delta)
    marg_hi = clopper_pearson_upper(err_case, n_case, delta)
    rate = auto_case / n_case
    envelope = _BASE_ENVELOPE + (
        "rule: act iff the certified chain interval is a single level; the sets are "
        "ordinal.interval_set -- the modal-anchored chain family of ruling R-68, not APS/LAC -- and "
        "a singleton of this family is always its modal level",
        "threshold: qhat=%.6f is the ceil((1-alpha)(n+1)) order statistic of %d calibration chain "
        "masses; alpha=%.3f (coverage %.3f) fixes which order statistic that is and is not itself "
        "the threshold, and no grid was swept on the evaluation half" % (
            qhat, len(cal), alpha, 1.0 - alpha),
        "no recorded randomisation is read by this rule: the draw stays on the record, because a "
        "per-level u would split the chain (R-78); ties between different ballots are broken in the "
        "calibration quantile, which is where they belong",
        "mean interval length is the mean NUMBER OF LEVELS in the certified set over the %d "
        "evaluated records (an empty set contributes 0, not a missing value); it is carried in the "
        "certificate's mean_set_size slot and published as meta.mean_interval_length, because the "
        "shape has one mean field and that field names the set rule -- Task 5 versions the shape, "
        "and nothing here is an APS set size" % n_ev,
        "finite-sample: bounds on CASES -- %d of %d evaluation cases automated, %d refused; "
        "record counts n_cal=%d n_eval=%d (%d empty sets, %d multi-level); %d claims at delta=%.3f, "
        "joint level %.2f" % (
            auto_case, n_case, n_case - auto_case, len(cal), n_ev, observed["empties"],
            observed["multi_label"], N_CLAIMS, delta, 1.0 - N_CLAIMS * delta),
        "empty certified sets counted as refusal, not automation",
    )
    cert = Certificate(
        feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta, method=METHOD,
        backend=backend, qhat=qhat, autorate=rate,
        autorate_ci=(max(0.0, rate - half_width), min(1.0, rate + half_width)),
        conditional_error_bound=cond_hi, marginal_error_bound=marg_hi,
        mean_set_size=observed["mean_interval_length"],
        n_cal=len(cal), n_eval=n_ev, envelope=envelope,
        meta={**meta, "mean_interval_length": observed["mean_interval_length"],
              "closest_attempt": None},
    )
    if cond_hi > beta:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="at coverage %.3f the %d automated cases include %d carrying a wrong automated "
                   "level; the exact case-level upper bound %.3f exceeds the budget %.3f" % (
                       1.0 - alpha, auto_case, err_case, cond_hi, beta),
            meta=_with_diagnostic({**meta, "at_requested_alpha": {
                # Case operands beside a case bound, named as the choice gate names them
                # (ledger #37/#71).
                "automated": autom, "errors": err,
                "automated_cases": auto_case, "errors_cases": err_case,
                "bound_unit": BOUND_UNIT_CASE,
                "conditional_error_bound": cond_hi}},
                cal_scores, ev, grid, beta, delta))
    return cert


def _with_diagnostic(meta: dict, cal_scores, ev, grid, beta: float, delta: float) -> dict:
    """Sweep coverage levels for the refusal's evidence, and say it is only evidence.

    The set gate's `_with_diagnostic` treatment, on purpose: `closest_attempt` is the point whose
    bound comes CLOSEST to meeting `beta` -- the least-failing point on the curve, not the point with
    the highest automation rate, which on a failing curve is the furthest from the budget. Nothing
    here is certified: the grid is swept on the evaluation half for the refusal to quote, and the note
    says which half it came from.
    """
    curve = []
    for a in grid:
        try:
            q, vac = split_quantile(cal_scores, a)
        except ValueError:
            continue
        if vac:
            continue
        obs = _outcome(ev, q)
        if obs["automated"] == 0:
            continue
        bound = clopper_pearson_upper(obs["errors"], obs["automated"], delta)
        curve.append({"grid_alpha": a, "qhat": q, "automated": obs["automated"],
                      "errors": obs["errors"], "empties": obs["empties"],
                      "multi_label": obs["multi_label"],
                      "observed_automation_rate": obs["automated"] / len(ev),
                      "observed_conditional_error": obs["errors"] / obs["automated"],
                      # The choice gate's naming, on the same arithmetic: this `bound` is over the
                      # RECORD counts, the certificate's headline field of the same name is over
                      # cases, and `evaluated_records` is the divisor of the rate above
                      # (ledger #37/#71).
                      "bound_unit": BOUND_UNIT_RECORD,
                      "evaluated_records": len(ev),
                      "conditional_error_bound": bound})
    if not curve:
        return {**meta, "closest_attempt": None, "diagnostic_curve": []}
    best = min(curve, key=lambda c: (c["conditional_error_bound"],
                                     -c["observed_automation_rate"]))
    return {**meta, "closest_attempt": best, "diagnostic_curve": curve,
            "diagnostic_note": "the grid below was swept on the evaluation half for "
                               "evidence only; nothing on it was certified"}
