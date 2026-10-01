"""Two-way certification for `choice`: how much may run unattended, and how wrong that may be.

Split halves, joint bound (arXiv 2110.01052 section 3.2): the coverage half fixes the
set size, the error half bounds the conditional error among automated points, and the
composition is a union bound at level 1 - 2*delta. Marginal and conditional error are
reported as two different numbers and never conflated: the conditional one is what a
deployment asks and can be far larger than alpha, while the marginal one is what the
set construction actually bounds.

Empty certified sets are refusals, not errors, and not automations (R-17): they are
reported in `refusal_rate` so the automation rate's denominator is visible.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence

from .certificate import Certificate, Reason
from .conformal import METHODS, conformal_set, split_quantile
from .tails import clopper_pearson_upper

MIN_CAL = 60
MIN_EVAL = 60
DEFAULT_GRID = tuple(round(0.01 * i, 2) for i in range(1, 30))
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


def certify_choice(records: Sequence, alpha: float = 0.05, beta: float = 0.05,
                   delta: float = 0.05, seed: int = 0, method: str = "aps",
                   grid: Optional[Sequence[float]] = None) -> Certificate:
    """Return the widest automation the error budget `beta` allows, with a bound."""
    if method not in METHODS:
        raise ValueError("unknown method %r; choose from %s" % (method, sorted(METHODS)))
    cal, ev, dropped = split_cal(records, seed)
    meta = {**dropped, "grid_size": len(grid or DEFAULT_GRID), "seed": seed,
            "alpha": alpha, "beta": beta, "total_labelled": len(cal) + len(ev)}
    if not (cal or ev):
        return Certificate.refused(Reason.NO_GOLD_LABELS, alpha=alpha, beta=beta,
                                   n_cal=0, n_eval=0, delta=delta,
                                   detail="no labelled choice records to calibrate on", meta=meta)
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(Reason.N_BELOW_MIN, alpha=alpha, beta=beta,
                                   n_cal=len(cal), n_eval=len(ev), delta=delta,
                                   detail="need %d/%d, have %d/%d" % (MIN_CAL, MIN_EVAL,
                                                                      len(cal), len(ev)),
                                   meta=meta)
    cal_scores = _scores(cal, method)
    n_ev = len(ev)
    half_width = math.sqrt(math.log(2.0 / delta) / (2.0 * n_ev))
    best: Optional[Certificate] = None
    saw_vacuous = False
    saw_automatable = False
    # The widest automation seen at ANY grid point, feasible or not. A refusal that
    # carries no observation is a verdict with no evidence behind it (R-21).
    closest: Optional[dict] = None
    for a in (grid or DEFAULT_GRID):
        qhat, vacuous = split_quantile(cal_scores, a)
        if vacuous:
            saw_vacuous = True
            continue
        autom = err = empties = multi = size_sum = 0
        for r in ev:
            C = conformal_set(r.probs, qhat, r.u, method)
            size_sum += len(C)
            if not C:
                empties += 1
            elif len(C) == 1:
                autom += 1
                if C[0] != r.gold_index:
                    err += 1
            else:
                multi += 1
        if autom == 0:
            continue
        saw_automatable = True
        rate = autom / n_ev
        cond_hi = clopper_pearson_upper(err, autom, delta)
        obs = {"grid_alpha": a, "qhat": qhat, "automated": autom, "errors": err,
               "empties": empties, "multi_label": multi,
               "observed_conditional_error": err / autom,
               "conditional_error_bound": cond_hi,
               "observed_automation_rate": rate}
        if closest is None or rate > closest["observed_automation_rate"]:
            closest = obs
        if cond_hi > beta:
            continue
        cand = Certificate(
            feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta, method=method,
            grid_alpha=a, qhat=qhat, autorate=rate,
            autorate_ci=(max(0.0, rate - half_width), min(1.0, rate + half_width)),
            conditional_error_bound=cond_hi,
            marginal_error_bound=clopper_pearson_upper(err, n_ev, delta),
            refusal_rate=(empties + multi) / n_ev, mean_set_size=size_sum / n_ev,
            n_cal=len(cal), n_eval=n_ev, level=1.0 - 2.0 * delta,
            envelope=_BASE_ENVELOPE + (
                "finite-sample: n_cal=%d, n_eval=%d, joint level %.2f" % (
                    len(cal), n_ev, 1.0 - 2.0 * delta),
                "empty certified sets counted as refusal, not automation (refusal %.3f)"
                % ((empties + multi) / n_ev),
            ),
            meta={**meta, "empties": empties, "multi_label": multi, "automated": autom,
                  "errors_among_automated": err},
        )
        if best is None or cand.autorate > best.autorate:
            best = cand
    if best is not None:
        return best
    return Certificate.refused(
        Reason.VACUOUS_QUANTILE if (saw_vacuous and not saw_automatable)
        else Reason.EMPTY_FEASIBLE_SET,
        alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev, delta=delta,
        detail="no set size on the grid meets the conditional error budget %.3f%s" % (
            beta, "" if closest is None else "; closest attempt at grid_alpha=%.2f automated "
            "%d/%d with %d errors (bound %.3f)" % (closest["grid_alpha"], closest["automated"],
                                                   n_ev, closest["errors"],
                                                   closest["conditional_error_bound"])),
        meta={**meta, "closest_attempt": closest,
              "errors_among_automated": (closest or {}).get("errors", 0),
              "automated": (closest or {}).get("automated", 0)},
    )
