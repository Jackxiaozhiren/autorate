"""Two-way certification for `choice`: how much may run unattended, and how wrong that may be.

Split halves, joint bound (arXiv 2110.01052 section 3.2): the coverage half fixes the
set size at the requested level `1 - alpha`, the error half bounds the conditional error
among automated points, and the composition is a union bound over the claims made.
Marginal and conditional error are reported as two different numbers and never
conflated: the conditional one is what a deployment asks and can be far larger than
alpha, while the marginal one is what the set construction actually bounds.

`alpha` is an INPUT, not a label. The first version of this module swept a 0.01..0.29
grid for the largest automation rate and then tested that rate on the same evaluation
half, so the published summary read "at alpha=0.050" while the operating point was
alpha=0.11 -- coverage 0.89 under a 0.95 heading, selected on the data that certified
it (ledger R-28). Selecting on the test half is snooping; a bound after snooping needs
a correction the corpus cannot pay. The set size is therefore fixed by `alpha` alone,
and the grid survives only as a diagnostic that refuses are allowed to quote.

Empty certified sets are refusals, not errors, and not automations (R-17): they are
reported in `refusal_rate` so the automation rate's denominator is visible.
"""
from __future__ import annotations

import random
from typing import Optional, Sequence

from .certificate import N_CLAIMS, Certificate, Reason
from .conformal import METHODS, classify_set, conformal_set, split_quantile
from .tails import clopper_pearson_upper
from .inventory import bound_width

MIN_CAL = 60
MIN_EVAL = 60
DIAGNOSTIC_GRID = tuple(round(0.01 * i, 2) for i in range(1, 30))
_BASE_ENVELOPE = (
    "exchangeability within group assumed; no group conditioning applied",
    "marginal certificate only - not group-conditional",
    "certified on archived responses; live traffic shift is not covered",
)


def _eligible(records: Sequence):
    kept, dropped = [], {"skipped_no_gold": 0, "skipped_wrong_qtype": 0}
    for r in records:
        if r.qtype != "choice":
            dropped["skipped_wrong_qtype"] += 1
        elif not r.calibratable:
            dropped["skipped_no_gold"] += 1
        else:
            kept.append(r)
    return kept, dropped


def split_cal(records: Sequence, seed: int = 0):
    recs, dropped = _eligible(records)
    rng = random.Random(seed)
    idx = list(range(len(recs)))
    rng.shuffle(idx)
    half = len(idx) // 2
    return [recs[i] for i in idx[:half]], [recs[i] for i in idx[half:]], dropped


def _scores(records, method: str) -> list:
    fn = METHODS[method]
    return [fn(r.probs, r.gold_index, r.u) for r in records]


def _outcome(ev, qhat, method):
    """Apply one threshold to the evaluation half. The gate uses the same classification."""
    autom = err = empties = multi = size_sum = 0
    for r in ev:
        C = conformal_set(r.probs, qhat, r.u, method)
        size_sum += len(C)
        kind = classify_set(C)
        if kind == "empty":
            empties += 1
        elif kind == "auto":
            autom += 1
            if C[0] != r.gold_index:
                err += 1
        else:
            multi += 1
    return {"automated": autom, "errors": err, "empties": empties, "multi_label": multi,
            "mean_set_size": size_sum / len(ev) if ev else 0.0}


def certify_choice(records: Sequence, alpha: float = 0.05, beta: float = 0.05,
                   delta: float = 0.05, seed: int = 0, method: str = "aps",
                   grid: Optional[Sequence[float]] = None) -> Certificate:
    """Certify the automation rate the coverage level `1 - alpha` buys, under budget `beta`.

    `beta` bounds P(wrong | automated); `delta` is the level each published bound is
    tested at, and `N_CLAIMS` of them are made, so the joint confidence is 1 - N_CLAIMS*delta.
    """
    if method not in METHODS:
        raise ValueError("unknown method %r; choose from %s" % (method, sorted(METHODS)))
    for name, v in (("alpha", alpha), ("beta", beta), ("delta", delta)):
        if not 0.0 < v < 1.0:
            raise ValueError("%s must be in (0,1), got %r" % (name, v))
    cal, ev, dropped = split_cal(records, seed)
    subjects = {r.backend for r in cal + ev}
    backend = subjects.pop() if len(subjects) == 1 else None
    grid = tuple(grid or DIAGNOSTIC_GRID)
    # The evaluation half is named, not summarised: "the two certificates were
    # compared case by case" is only checkable if the cases are on the record.
    meta = {**dropped, "diagnostic_grid_size": len(grid), "seed": seed,
            "alpha": alpha, "beta": beta, "total_labelled": len(cal) + len(ev),
            "eval_ids": sorted(r.id for r in ev), "cal_ids": sorted(r.id for r in cal)}
    if not (cal or ev):
        return Certificate.refused(Reason.NO_GOLD_LABELS, alpha=alpha, beta=beta,
                                   n_cal=0, n_eval=0, delta=delta, backend=backend,
                                   detail="no labelled choice records to calibrate on", meta=meta)
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(Reason.N_BELOW_MIN, alpha=alpha, beta=beta,
                                   n_cal=len(cal), n_eval=len(ev), delta=delta, backend=backend,
                                   detail="need %d/%d, have %d/%d" % (MIN_CAL, MIN_EVAL,
                                                                      len(cal), len(ev)),
                                   meta=meta)
    cal_scores = _scores(cal, method)
    n_ev = len(ev)
    qhat, vacuous = split_quantile(cal_scores, alpha)
    half_width = bound_width(n_ev, delta) / 2.0
    observed = _outcome(ev, qhat, method)
    autom, err = observed["automated"], observed["errors"]
    meta.update(empties=observed["empties"], multi_label=observed["multi_label"],
                automated=autom, errors_among_automated=err)
    if vacuous:
        return Certificate.refused(
            Reason.VACUOUS_QUANTILE, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend,
            detail="the %.3f-quantile of %d calibration scores is above 1, so every label "
                   "would be certified" % (alpha, len(cal)),
            meta=_with_diagnostic(meta, cal_scores, ev, method, grid, beta, delta))
    if autom == 0:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend,
            detail="at coverage %.3f no evaluation case produced a singleton set (%d empty, "
                   "%d multi-label of %d)" % (1.0 - alpha, observed["empties"],
                                              observed["multi_label"], n_ev),
            meta=_with_diagnostic(meta, cal_scores, ev, method, grid, beta, delta))
    cond_hi = clopper_pearson_upper(err, autom, delta)
    marg_hi = clopper_pearson_upper(err, n_ev, delta)
    rate = autom / n_ev
    envelope = _BASE_ENVELOPE + (
        "set size fixed by the requested alpha=%.3f (coverage %.3f); no grid selection on "
        "the evaluation half" % (alpha, 1.0 - alpha),
        "finite-sample: n_cal=%d, n_eval=%d, %d claims at delta=%.3f, joint level %.2f" % (
            len(cal), n_ev, N_CLAIMS, delta, 1.0 - N_CLAIMS * delta),
        "empty certified sets counted as refusal, not automation (refusal %.3f)"
        % ((observed["empties"] + observed["multi_label"]) / n_ev),
    )
    cert = Certificate(
        feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta, method=method,
        backend=backend, qhat=qhat, autorate=rate,
        autorate_ci=(max(0.0, rate - half_width), min(1.0, rate + half_width)),
        conditional_error_bound=cond_hi, marginal_error_bound=marg_hi,
        mean_set_size=observed["mean_set_size"],
        n_cal=len(cal), n_eval=n_ev, level=1.0 - N_CLAIMS * delta, envelope=envelope,
        meta={**meta, "closest_attempt": None},
    )
    if cond_hi > beta:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend,
            detail="at coverage %.3f the automated set has %d/%d errors, whose exact upper "
                   "bound %.3f exceeds the budget %.3f" % (1.0 - alpha, err, autom, cond_hi,
                                                            beta),
            meta=_with_diagnostic({**meta, "at_requested_alpha": {
                "automated": autom, "errors": err, "conditional_error_bound": cond_hi}},
                cal_scores, ev, method, grid, beta, delta))
    return cert


def _with_diagnostic(meta: dict, cal_scores, ev, method: str, grid, beta: float,
                      delta: float) -> dict:
    """Sweep coverage levels for the refusal's evidence, and say it is only evidence.

    `closest_attempt` is the point whose bound comes CLOSEST to meeting beta -- the
    least-failing point on the curve. It used to be the point with the highest
    automation rate, which is the furthest from the budget by construction: a refusal
    quoting it was naming the worst case and calling it the closest.
    """
    curve = []
    for a in grid:
        try:
            q, vac = split_quantile(cal_scores, a)
        except ValueError:
            continue
        if vac:
            continue
        obs = _outcome(ev, q, method)
        if obs["automated"] == 0:
            continue
        bound = clopper_pearson_upper(obs["errors"], obs["automated"], delta)
        curve.append({"grid_alpha": a, "qhat": q, "automated": obs["automated"],
                      "errors": obs["errors"], "empties": obs["empties"],
                      "multi_label": obs["multi_label"],
                      "observed_automation_rate": obs["automated"] / len(ev),
                      "observed_conditional_error": obs["errors"] / obs["automated"],
                      "conditional_error_bound": bound})
    if not curve:
        return {**meta, "closest_attempt": None, "diagnostic_curve": []}
    best = min(curve, key=lambda c: (c["conditional_error_bound"],
                                     -c["observed_automation_rate"]))
    return {**meta, "closest_attempt": best, "diagnostic_curve": curve,
            "diagnostic_note": "the grid below was swept on the evaluation half for "
                               "evidence only; nothing on it was certified"}
