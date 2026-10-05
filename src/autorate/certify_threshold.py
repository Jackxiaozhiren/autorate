"""The threshold gate of spec 6.4: automate iff `score >= lambda`, and certify what that buys.

Two gates, one set of records, deliberately contrasted. The set gate asks how small a
certified answer set can be made at a requested coverage and refuses to automate anything
whose set is not a singleton. This gate asks a different question -- where does a single
published number have to sit for the decision to run unattended -- and it is the rule most
deployments actually apply today, which is exactly why it needs a bound rather than a
default. Spec 6.4 requires both gates implemented and contrasted on the SAME records,
because a threshold's appeal is that it looks like less machinery, and the only way to
show what that costs is to measure it against the set rule on the same data.

`method` is recorded as `"threshold"`, not `"aps"`. The certificate shape treats `method` as
a rubric field that `compare()` matches on, and a gate that reported the set rule's method
while running `score >= lambda` would be recording a rule it never ran -- the same defect the
refusal path already refuses to have.

Where the operating point comes from, and where it does not (R-28, restated for this gate):
lambda is selected on the CALIBRATION half only, at the budget `beta` rather than `alpha`.
The evaluation half never picks its own threshold. `alpha` is accepted, recorded and used for
nothing here: it is the coverage level of the *set* rule, and a threshold gate that consulted
it would be silently importing a quantile it does not compute. `beta` is what moves this
gate's operating point, so the test that proves the budget bites moves `beta` and the test
that proves `alpha` does not is its other half.

The case arithmetic is not owned here either: `case_count.count_outcome` does it for both
gates (R-34), and this module supplies the threshold rule as the counter's `kind`/`measure`
callables. One published figure has one owner: the shared counter returns `mean_measure`, and
`mean_score` is THIS gate's name for it.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .case_count import case_key, count_outcome
from .certificate import N_CLAIMS, Certificate, Reason
from .certify_choice import split_cal
from .tails import bound_width, clopper_pearson_upper

MIN_CAL = 60
MIN_EVAL = 60
METHOD = "threshold"
# The non-automating outcome's name in the shared vocabulary. It is `refuse`, never `empty`:
# this rule produces no set, so writing its refusals into `empties` would put a false
# statement on a certificate (R-53).
_REFUSE = "refuse"


def _scores_of(records: Sequence, score_field: str) -> dict:
    """Every value of `score_field` this population carries, by record id.

    Returns the map rather than a boolean so the caller can count the records that carry
    nothing: a rule that automates on a number must say how many of its inputs had none.
    """
    out = {}
    for r in records:
        value = (r.scores or {}).get(score_field)
        if value is not None:
            out[r.id] = float(value)
    return out


def _known_fields(records: Sequence) -> list:
    seen = set()
    for r in records:
        seen.update((r.scores or {}).keys())
    return sorted(seen)


def _rule(score_field: str, lam: float):
    """The gate's rule as the shared counter's `kind`, plus its `measure`.

    A record with no value for the field is NOT automatable, and it is not an error either: it
    is a refusal. Counting a missing score as a low score would make an absent field decide the
    automation rate, which is the same mistake as a blank label deciding a quantile.
    """
    def kind(r):
        value = (r.scores or {}).get(score_field)
        if value is None:
            return _REFUSE
        return "auto" if float(value) >= lam else _REFUSE

    def measure(r):
        value = (r.scores or {}).get(score_field)
        return 1.0 if value is not None and float(value) >= lam else 0.0

    return kind, measure


def sweep_thresholds(records: Sequence, score_field: str,
                     grid: Optional[Sequence[float]] = None) -> list:
    """What each candidate lambda would have automated, over the records handed in.

    No bound and no selection here: this is the evidence table the gate is read against, and
    the monotonicity spec 6.1/6.4 makes a precondition of the gate is checked on it -- the
    marginal risk of an automated error must fall as lambda rises. A weighted loss that mixes
    "wrong" and "not automated" into one number cannot express that, which is why the two
    counts stay in separate columns.

    Each row: `lambda`, `automated` and `marginal_errors` at the record denominator, and
    `automated_cases` / `erroneous_cases` at the case denominator the bound uses.
    """
    batch = list(records)
    points = list(grid) if grid is not None else sorted(set(_scores_of(batch, score_field).values()))
    rows = []
    for lam in points:
        obs = count_outcome(batch, *_rule(score_field, lam))
        rows.append({"lambda": lam, "automated": obs["automated"],
                     "marginal_errors": obs["errors"],
                     "automated_cases": obs["automated_cases"],
                     "erroneous_cases": obs["erroneous_cases"],
                     "refused": obs["refused"], "refused_cases": obs["refused_cases"],
                     "n_cases": obs["n_cases"]})
    return rows


def _select_lambda(cal: Sequence, score_field: str, points: Sequence[float],
                   beta: float, delta: float):
    """The most automation the calibration half will pay for at budget `beta`, or None.

    Ties go to the HIGHER lambda: two points that automate the same number of cases are the
    same promise, and the stricter rule is the one that also automates the fewer marginal
    records, so it is the smaller claim. Nothing on this line reads the evaluation half --
    that is the whole content of R-28.
    """
    best = None
    for lam in points:
        obs = count_outcome(cal, *_rule(score_field, lam))
        if obs["automated"] == 0:
            continue
        bound = clopper_pearson_upper(obs["errors"], obs["automated"], delta)
        if bound > beta:
            continue
        key = (obs["automated_cases"], obs["automated"], lam)
        if best is None or key > best[0]:
            best = (key, lam, obs, bound)
    return None if best is None else best[1:]


def _diagnostic(points, ev, score_field, beta: float, delta: float) -> dict:
    """The held-out sweep a refusal may quote, labelled as the evidence-only thing it is.

    Same treatment as the set gate's `_with_diagnostic`, on purpose: a refusal that names the
    point closest to meeting the budget is auditable, and a refusal that names none invites a
    reader to assume the rule was never tried. It is swept on the EVALUATION half and says so,
    because that is exactly the number a selector must not use (R-28). `closest_attempt` is the
    point whose bound comes closest to meeting beta, not the busiest one.
    """
    curve = []
    for lam in points:
        obs = count_outcome(ev, *_rule(score_field, lam))
        if obs["automated"] == 0:
            continue
        curve.append({"lambda": lam, "automated": obs["automated"], "errors": obs["errors"],
                      "automated_cases": obs["automated_cases"],
                      "erroneous_cases": obs["erroneous_cases"],
                      "n_cases": obs["n_cases"],
                      "observed_automation_rate": obs["automated"] / len(ev),
                      "observed_conditional_error": obs["errors"] / obs["automated"],
                      "conditional_error_bound": clopper_pearson_upper(
                          obs["erroneous_cases"], obs["automated_cases"], delta)})
    if not curve:
        return {"closest_attempt": None, "diagnostic_curve": []}
    best = min(curve, key=lambda c: (c["conditional_error_bound"],
                                     -c["observed_automation_rate"]))
    return {"closest_attempt": best, "diagnostic_curve": curve,
            "diagnostic_note": "the grid below was swept on the evaluation half for "
                               "evidence only; nothing on it was certified",
            "beta": beta}


def certify_threshold(records: Sequence, score_field: str = "confidence",
                      alpha: float = 0.05, beta: float = 0.05, delta: float = 0.05,
                      seed: int = 0,
                      grid: Optional[Sequence[float]] = None) -> Certificate:
    """Certify the automation rate `score >= lambda` buys, under budget `beta`.

    `alpha` is recorded, not used: it is the set rule's coverage level and this gate computes no
    quantile (see the module docstring, and the two-sided test that moves `beta` and the one
    that proves `alpha` does nothing). `beta` bounds P(wrong | automated) at the CASE
    denominator; `delta` is the level each published bound is tested at, and `N_CLAIMS` of them
    are made, so the joint confidence is 1 - N_CLAIMS*delta.

    Raises `ValueError` -- a usage error, which the CLI maps to exit 2 -- for a budget outside
    (0, 1), for a population that spans more than one `backend`, and for a `score_field` no
    record carries. The third one matters: `score >= lambda` with an absent score automates
    nothing, so a typo would otherwise come back as a clean-looking refusal instead of a typo.
    """
    batch = list(records)
    for name, value in (("alpha", alpha), ("beta", beta), ("delta", delta)):
        if not 0.0 < value < 1.0:
            raise ValueError("%s must be strictly between 0 and 1, got %r" % (name, value))
    cal, ev, dropped = split_cal(batch, seed)
    subjects = {r.backend for r in batch if r.backend}
    backend = subjects.pop() if len(subjects) == 1 else None
    present = _scores_of(cal + ev, score_field)
    if not present:
        raise ValueError("no record carries a score field named %r; the fields this population "
                         "does carry are %s" % (score_field, _known_fields(cal + ev)))
    points = sorted(set(grid)) if grid is not None else sorted(set(present.values()))
    meta = {"score_field": score_field, "lambda_grid": points, "dropped": dropped,
            "total_labelled": len(cal) + len(ev),
            "eval_ids": sorted(r.id for r in ev), "cal_ids": sorted(r.id for r in cal)}
    if not (cal or ev):
        return Certificate.refused(Reason.NO_GOLD_LABELS, alpha=alpha, beta=beta, n_cal=0,
                                   n_eval=0, delta=delta, backend=backend, method=METHOD,
                                   detail="no labelled choice records to calibrate on", meta=meta)
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(
            Reason.N_BELOW_MIN, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=len(ev),
            delta=delta, backend=backend, method=METHOD,
            detail="need %d/%d, have %d/%d" % (MIN_CAL, MIN_EVAL, len(cal), len(ev)), meta=meta)
    n_ev = len(ev)
    n_case = len({case_key(r) for r in ev})
    meta.update(n_eval_cases=n_case, n_cal_cases=len({case_key(r) for r in cal}),
                missing_score=n_ev - len([r for r in ev if r.id in present]),
                unit_note="%d evaluation records over %d distinct cases: the bounds use the case "
                          "denominator, because repeats of one case are one observation"
                          % (n_ev, n_case))
    chosen = _select_lambda(cal, score_field, points, beta, delta)
    if chosen is None:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="no lambda on the %d-point grid met the %.3f budget on the calibration half; "
                   "%r takes %d distinct value(s) over the %d records it was handed, so either "
                   "every record automates and is wrong together, or nothing automates"
                   % (len(points), beta, score_field, len(points), len(cal) + n_ev),
            meta={**meta, **_diagnostic(points, ev, score_field, beta, delta)})
    lam, obs_cal = chosen[0], chosen[1]
    observed = count_outcome(ev, *_rule(score_field, lam))
    autom, err = observed["automated"], observed["errors"]
    auto_case, err_case, n_case = (observed["automated_cases"], observed["erroneous_cases"],
                                   observed["n_cases"])
    # `lambda` is a keyword in Python, so this is a dict literal rather than kwargs -- and the
    # published key stays `lambda`, because that is what the rule is.
    meta.update({"lambda": lam, "automated": autom, "errors_among_automated": err,
                 "refused": observed["refused"], "refused_cases": observed["refused_cases"],
                 "n_eval_cases": n_case, "automated_cases": auto_case,
                 "erroneous_cases": err_case, "cal_automated": obs_cal["automated"],
                 "cal_errors": obs_cal["errors"],
                 "cal_automated_cases": obs_cal["automated_cases"],
                 "cal_conditional_error_bound": chosen[2]})
    if autom == 0 or auto_case == 0:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="lambda=%.4f met the %.3f budget on the calibration half but automated no "
                   "evaluation case (%d of %d records handed in carried a value for %r)"
                   % (lam, beta, len(present), len(cal) + n_ev, score_field),
            meta={**meta, **_diagnostic(points, ev, score_field, beta, delta)})
    cond_hi = clopper_pearson_upper(err_case, auto_case, delta)
    marg_hi = clopper_pearson_upper(err_case, n_case, delta)
    rate = auto_case / n_case
    half_width = bound_width(n_case, delta) / 2.0
    envelope = (
        "rule: automate iff %s >= %.6f; this is the threshold gate of spec 6.4, not the APS "
        "set gate" % (score_field, lam),
        "lambda selected on the calibration half at beta=%.3f; the evaluation half never picks "
        "its own threshold, and alpha=%.3f is recorded but not used by this gate"
        % (beta, alpha),
        "mean score is carried in the certificate's mean_set_size slot and published as "
        "meta.mean_score: the shape has one mean field and it names the set rule (Task 5 versions "
        "the shape); nothing here is a set size",
        "exchangeability within group assumed; no group conditioning applied",
        "marginal certificate only - not group-conditional",
        "certified on archived responses; live traffic shift is not covered",
        "finite-sample: bounds on CASES -- %d of %d evaluation cases automated, %d refused; "
        "record counts n_cal=%d n_eval=%d (%d records refused the rule, %d carried no value for "
        "%r); %d claims at delta=%.3f, joint level %.2f" % (
            auto_case, n_case, observed["refused_cases"], len(cal), n_ev, observed["refused"],
            meta["missing_score"], score_field, N_CLAIMS, delta, 1.0 - N_CLAIMS * delta),
    )
    cert = Certificate(
        feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta, method=METHOD,
        backend=backend, qhat=lam, autorate=rate,
        autorate_ci=(max(0.0, rate - half_width), min(1.0, rate + half_width)),
        conditional_error_bound=cond_hi, marginal_error_bound=marg_hi,
        mean_set_size=observed["mean_measure"],
        n_cal=len(cal), n_eval=n_ev, envelope=envelope,
        meta={**meta, "mean_score": observed["mean_measure"], "closest_attempt": None},
    )
    if cond_hi > beta:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="at lambda=%.4f the %d automated cases include %d carrying a wrong automated "
                   "request; the exact case-level upper bound %.3f exceeds the budget %.3f -- the "
                   "calibration half met the budget and the held-out half did not"
                   % (lam, auto_case, err_case, cond_hi, beta),
            meta={**meta, **_diagnostic(points, ev, score_field, beta, delta)})
    return cert
