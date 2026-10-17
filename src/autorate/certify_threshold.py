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
lambda is selected on the CALIBRATION half only, at the budget `beta` rather than `alpha`, and
at the CASE denominator the certificate publishes its bounds at. The candidate grid is a
calibration-half fact too -- the distinct values of `score_field` over the records the selector
actually scores, collected per record because the archive reuses ids -- since an operating point
chosen from a grid the held-out half supplied is chosen on the data meant to test it. A
caller-supplied `grid` is used verbatim. The evaluation half never picks its own threshold.
`alpha` is accepted, recorded and used for nothing here: it is the coverage level of the *set*
rule, and a threshold gate that consulted it would be silently importing a quantile it does not
compute. `beta` is what moves this gate's operating point, so the test that proves the budget
bites moves `beta` and the test that proves `alpha` does not is its other half. Ties in cases
break to the HIGHER lambda (R-62): the promise is the cases, and the stricter rule is the
smaller claim.

The case arithmetic is not owned here either: `case_count.count_outcome` does it for both
gates (R-34), and this module supplies the threshold rule as that counter's ONE `decide`
callable, which names the label the rule submits and the score it measures (R-66). One published
figure has one owner: the shared counter returns `mean_measure`, and `mean_score` is THIS gate's
name for it -- the mean of the field's values over the evaluated records that carry one, with
`missing_score` named beside it.

Published precision, and why this module has any business with it (R-121). Every bound this gate
emits -- the headline `conditional_error_bound` and `marginal_error_bound`, the calibration bound
`meta.cal_conditional_error_bound` the selection budget was decided on, and both bounds on every
row of a refusal's diagnostic curve -- is the output of `clopper_pearson_upper` inverting a binomial
tail through `math.log`/`math.exp`, or of `bound_width` through `math.log`. The last bits of those
transcendentals are not identical between Apple libm and glibc, so a full-precision double taken
from one C library is not a number the other can re-derive: an exact re-derivation gate would then
red on the machine that did not write the artefact, which is the incident R-121 records on the set
gate. The same fix applies here and it is the SAME helper, at the same place -- the producer: every
bound-valued output is passed through `certificate.canonicalise_bound`, which ceils it onto the
12-decimal grid, is idempotent (so the stored number canonicalises to itself) and monotone (so
`marginal <= conditional` survives the trip). The quotients of integers stay raw and unrounded:
`autorate`, `observed_automation_rate`, `observed_conditional_error` and `mean_score` are divisions
and sums, and IEEE 754 requires those to be correctly rounded, so they already agree bit for bit
everywhere -- rounding them would be the blanket tolerance R-121 forbids, absorbing a genuinely
changed automation rate as cheerfully as it absorbs a libm difference.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .case_count import AUTO, Verdict, case_key, count_outcome
from .certificate import (BOUND_UNIT_CASE, BOUND_UNIT_RECORD, CANONICALISED_BOUND_FIELDS, N_CLAIMS,
                          Certificate, Reason, canonicalise_bound)
from .certify_choice import split_cal
from .tails import bound_width, clopper_pearson_upper

MIN_CAL = 60
MIN_EVAL = 60
METHOD = "threshold"
# The non-automating outcome's name in the shared vocabulary. It is `refuse`, never `empty`:
# this rule produces no set, so writing its refusals into `empties` would put a false
# statement on a certificate (R-53).
_REFUSE = "refuse"

# The bound-valued fields THIS gate publishes, as one list. `CANONICALISED_BOUND_FIELDS` is the
# certificate shape's own two headline attributes and is owned by `certificate.py`; a threshold
# refusal's diagnostic rows carry a third bound -- the record-denominator one, named for its unit
# so a reader cannot mistake it for the case-level figure (ledger #37 is the same confusion on the
# set gate). It is the same transcendental with the same last-ULP exposure (R-121), and it is NOT
# added to that shared tuple: a guard test outside this fence pins that tuple to the shape's
# attributes, and widening it to reach a row that is not a shape attribute would be one lane
# editing another's guard. So the extra name is declared here, and the helper below walks the
# union of the two lists rather than a second list of "floats that look like bounds".
_BOUND_FIELDS = CANONICALISED_BOUND_FIELDS + ("record_conditional_error_bound",)


def _values_of(records: Sequence, score_field: str) -> list:
    """Every value of `score_field` these records carry, ONE ENTRY PER RECORD that carries it.

    A list rather than an `{id: value}` map or a boolean, because both of the things the caller
    does with it are per-record facts: the candidate grid is the DISTINCT values of the population
    it selects on, and `missing_score` / the "does anyone carry this field at all" check count
    records. The archive reuses ids (measured on the committed one: 1919 rows over 320 ids, 383
    calibratable choice rows over 64), so a map keyed by `record.id` silently keeps one repeat per
    id: it is then neither the calibration population nor a multiset, and values the population
    really carries vanish from the grid while `len(map)` understates the carriers.
    """
    out = []
    for r in records:
        value = (r.scores or {}).get(score_field)
        if value is not None:
            out.append(float(value))
    return out


def _known_fields(records: Sequence) -> list:
    seen = set()
    for r in records:
        seen.update((r.scores or {}).keys())
    return sorted(seen)


def _submitted_label(record):
    """The answer this rule puts forward when it automates: the record's own, else its argmax.

    `records.py:74-77` names `predicted` "what the automated decision would BE" and refuses an
    answer outside the ballot, so it IS the deployment's answer for a threshold rule. A record
    that states none still has to be answered, and the only label it carries is its largest
    probability. This is one rule's reading and it lives with the rule (R-66): the set gate
    submits something else entirely -- the label inside its certified singleton.
    """
    if record.predicted is not None:
        return record.predicted
    return list(record.options)[max(range(len(record.probs)), key=lambda j: record.probs[j])]


def _rule(score_field: str, lam: float):
    """The gate's rule as the shared counter's ONE `decide` callable (R-66).

    A record with no value for the field is NOT automatable, and it is not an error either: it
    is a refusal. Counting a missing score as a low score would make an absent field decide the
    automation rate, which is the same mistake as a blank label deciding a quantile -- and it is
    why its verdict carries `measure=None` rather than a made-up number.

    The measure is the field's own value, for every record that carries one, automated or not:
    `mean_score` is the mean of scores (item 2). The automation share is not published here under
    a mean's name -- the certificate already carries it as `automated` over `n_eval`.
    """
    def decide(r):
        value = (r.scores or {}).get(score_field)
        if value is None:
            return Verdict(_REFUSE, None, None)
        value = float(value)
        if value < lam:
            return Verdict(_REFUSE, None, value)
        return Verdict(AUTO, _submitted_label(r), value)

    return decide


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
    points = list(grid) if grid is not None else sorted(set(_values_of(batch, score_field)))
    rows = []
    for lam in points:
        obs = count_outcome(batch, _rule(score_field, lam))
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

    The budget is tested at the CASE denominator -- the same unit `conditional_error_bound`,
    `marginal_error_bound` and `autorate` are published on (item 4, R-36/R-44). It used to be
    tested on records, which let a lambda satisfy `beta` on a unit the certificate never names and
    then be refused downstream on the unit it does; with repeats of a case carrying the same
    verdict the record bound is strictly looser, because an exact Clopper-Pearson upper bound
    tightens with n (measured: 0.361174 on 180 records against 0.411737 on the same 60 cases).

    The bound is canonicalised at the call that makes it, which is also the call that compares it
    with `beta`: `meta.cal_conditional_error_bound` publishes this exact number, so the operating
    point is decided on the figure the certificate states, and neither half of that depends on
    which C library ran `math.exp` (R-121). The ceiling moves a bound by at most 1e-12, and it
    moves it UP, so a lambda this test accepts is never accepted on a rounding -- the grid can only
    make the budget harder to meet, never easier.

    Ties go to the HIGHER lambda: two points that automate the same number of cases are the
    same promise, and the stricter rule is the one that also automates the fewer marginal
    records, so it is the smaller claim. Nothing on this line reads the evaluation half --
    that is the whole content of R-28.
    """
    best = None
    for lam in points:
        obs = count_outcome(cal, _rule(score_field, lam))
        if obs["automated_cases"] == 0:
            # A point that automates no case makes no case-level claim at all: `beta` bounds the
            # error rate of the cases that run unattended, and there are none to bound.
            continue
        bound = canonicalise_bound(
            clopper_pearson_upper(obs["erroneous_cases"], obs["automated_cases"], delta))
        if bound > beta:
            continue
        # R-62, as the docstring above states it: the promise is the number of CASES automated, so
        # ties break on lambda and on nothing else. The record count used to sit in this key ahead
        # of lambda, which ranked the LOOSER rule first whenever two points automated the same
        # cases -- the objective and the tie-break then disagreed by construction.
        key = (obs["automated_cases"], lam)
        if best is None or key > best[0]:
            best = (key, lam, obs, bound)
    return None if best is None else best[1:]


def _canonicalised(row: dict) -> dict:
    """Round the bound-named fields of one published row, and only those (R-121).

    `_BOUND_FIELDS` drives the walk, exactly as `certify_choice._canonicalised` is driven by the
    shape's own list: the two bounds a curve row carries, and the `closest_attempt` copy taken from
    one of them, all publish the identical canonical number, while the counts and the two ratio
    columns of the same row keep the exact double the records determine. The sweep is by field NAME,
    not by "this looks like a float" -- a blanket pass over floats is the tolerance this replaces.
    """
    return {key: (canonicalise_bound(value) if key in _BOUND_FIELDS else value)
            for key, value in row.items()}


def _diagnostic(points, ev, score_field, delta: float) -> dict:
    """The held-out sweep a refusal may quote, labelled as the evidence-only thing it is.

    Same treatment as the set gate's `_with_diagnostic`, on purpose: a refusal that names the
    point closest to meeting the budget is auditable, and a refusal that names none invites a
    reader to assume the rule was never tried. It is swept on the EVALUATION half and says so,
    because that is exactly the number a selector must not use (R-28). `closest_attempt` is the
    point whose bound comes closest to meeting the certificate's `beta` -- which `meta` publishes
    beside it, so this dict does not carry a second copy of the budget.

    Each row carries BOTH denominators and names which is which: `automated` / `errors` are
    records, `automated_cases` / `erroneous_cases` / `n_cases` are cases, and beside
    `conditional_error_bound` -- the CASE-level bound, the one unit this module's
    `conditional_error_bound` ever means -- the record-level bound is published under the name
    that says so, `record_conditional_error_bound`. A row of one unit with another unit's name on
    it is the defect ledger #37 tracks on the set gate; this gate does not repeat it. Both bounds
    go through `_canonicalised`, so a curve a Mac wrote is the curve a Linux runner re-derives
    (R-121), and the `closest_attempt` selection below ranks on the canonical numbers -- the ones
    it publishes -- not on bits only one platform can produce.
    """
    curve = []
    for lam in points:
        obs = count_outcome(ev, _rule(score_field, lam))
        if obs["automated"] == 0:
            continue
        curve.append(_canonicalised({
            "lambda": lam, "automated": obs["automated"], "errors": obs["errors"],
            "automated_cases": obs["automated_cases"],
            "erroneous_cases": obs["erroneous_cases"],
            "n_cases": obs["n_cases"],
            "observed_automation_rate": obs["automated"] / len(ev),
            "observed_conditional_error": obs["errors"] / obs["automated"],
            "conditional_error_bound": clopper_pearson_upper(
                obs["erroneous_cases"], obs["automated_cases"], delta),
            "record_conditional_error_bound": clopper_pearson_upper(
                obs["errors"], obs["automated"], delta)}))
    if not curve:
        return {"closest_attempt": None, "diagnostic_curve": []}
    best = min(curve, key=lambda c: (c["conditional_error_bound"],
                                     -c["observed_automation_rate"]))
    return {"closest_attempt": best, "diagnostic_curve": curve,
            "diagnostic_note": "the grid below was swept on the evaluation half for "
                               "evidence only; nothing on it was certified"}


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
    if len(subjects) > 1:
        # The docstring has always promised this, and the code used to answer a mixed batch by
        # setting `backend=None` and certifying it anyway. A certificate that names no subject
        # names no model, so it cannot be paired (`cli.py` refuses it) and `gate.py:46-57` treats
        # it as authorising NOTHING -- the gate would have certified traffic its own deployment
        # declines to act on. `cli.py` maps ValueError to exit 2, so the documented exit codes
        # already cover this path.
        raise ValueError("a certificate names one subject; this population spans backends %s -- "
                         "certify one backend at a time" % ", ".join(sorted(subjects)))
    backend = subjects.pop() if len(subjects) == 1 else None
    cal_values = _values_of(cal, score_field)
    carriers = len(cal_values) + len(_values_of(ev, score_field))
    if not carriers:
        raise ValueError("no record carries a score field named %r; the fields this population "
                         "does carry are %s" % (score_field, _known_fields(cal + ev)))
    # R-28 applies to the CANDIDATE SET, not only to the bound: an operating point selected from
    # a grid the held-out half supplied is chosen on the data that is supposed to test it. So the
    # grid is the calibration half's own distinct values, collected per record; a caller-supplied
    # `grid` is used verbatim, and neither arm ever consults `ev`.
    points = sorted(set(grid)) if grid is not None else sorted(set(cal_values))
    # The rubric lives in `meta` as well as on the certificate, because `cli.RUBRIC_FIELDS` reads
    # the seed out of `meta` (`_rubric`) and the set gate has published it there from the start:
    # without it `autorate compare <set> <threshold>` reported the two gates as non-comparable on
    # `seed (3, None)` and exited 2 on the pairing spec 6.4 asks for. `alpha` and `beta` join it so
    # a feasible path and a refusal carry the same keys.
    meta = {"score_field": score_field, "lambda_grid": points, "dropped": dropped,
            "alpha": alpha, "beta": beta, "seed": seed,
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
    ev_carriers = len(_values_of(ev, score_field))
    meta.update(n_eval_cases=n_case, n_cal_cases=len({case_key(r) for r in cal}),
                missing_score=n_ev - ev_carriers,
                unit_note="%d evaluation records over %d distinct cases: the certificate's own bounds "
                          "-- conditional, marginal and the automation-rate interval -- use the %s "
                          "denominator, because repeats of one case are one observation, while every "
                          "diagnostic curve row, and its closest_attempt copy, publishes both: "
                          "conditional_error_bound on the %s denominator beside "
                          "record_conditional_error_bound on the %s denominator"
                          % (n_ev, n_case, BOUND_UNIT_CASE, BOUND_UNIT_CASE, BOUND_UNIT_RECORD))
    chosen = _select_lambda(cal, score_field, points, beta, delta)
    if chosen is None:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=METHOD,
            detail="no lambda on the %d-point grid met the %.3f budget on the calibration half; "
                   "%r carries %d distinct value(s) over the %d calibration records that grid was "
                   "built from (%d of the %d records handed in carry a value at all), so either "
                   "every calibration case automates and is wrong together, or nothing automates"
                   % (len(points), beta, score_field, len(points), len(cal), carriers,
                      len(cal) + n_ev),
            meta={**meta, **_diagnostic(points, ev, score_field, delta)})
    lam, obs_cal = chosen[0], chosen[1]
    observed = count_outcome(ev, _rule(score_field, lam))
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
                   "evaluation case (%d of the %d records handed in carried a value for %r)"
                   % (lam, beta, carriers, len(cal) + n_ev, score_field),
            meta={**meta, **_diagnostic(points, ev, score_field, delta)})
    cond_hi = canonicalise_bound(clopper_pearson_upper(err_case, auto_case, delta))
    marg_hi = canonicalise_bound(clopper_pearson_upper(err_case, n_case, delta))
    rate = auto_case / n_case
    # `bound_width` is `math.log`'s output, so the width is canonicalised rather than the two
    # endpoints it feeds: with a canonical width and a canonical rate, each endpoint is a
    # correctly-rounded subtraction, which every platform reproduces bit for bit.
    half_width = canonicalise_bound(bound_width(n_case, delta)) / 2.0
    envelope = (
        "rule: automate iff %s has a value and that value is >= %.6f -- a record carrying no "
        "value is refused, never read as a low one; this is the threshold gate of spec 6.4, not "
        "the APS set gate" % (score_field, lam),
        "lambda and the %d-point grid it was chosen from are both calibration-half facts, taken "
        "at beta=%.3f on the CASE denominator the bounds below use; the evaluation half never "
        "picks its own threshold, and alpha=%.3f is recorded but not used by this gate"
        % (len(points), beta, alpha),
        "mean score is the mean of %r over the %d evaluated records that carry it (the "
        "%d records carrying no value are named by meta.missing_score, not counted as zeros); it "
        "is carried in the certificate's mean_set_size slot and published as meta.mean_score, "
        "because the shape has one mean field and it names the set rule (Task 5 versions the "
        "shape) -- nothing here is a set size"
        % (score_field, len(_values_of(ev, score_field)), meta["missing_score"]),
        "qhat carries lambda, not a set quantile: this gate computes no quantile, and the shape "
        "has one operating-point slot (Task 5 versions the shape)",
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
            meta={**meta, **_diagnostic(points, ev, score_field, delta)})
    return cert
