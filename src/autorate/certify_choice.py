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

The CASE arithmetic is not owned here: `case_count.count_outcome` counts records and cases
for whichever rule is being certified, and this module supplies the set rule as that counter's
ONE `decide` callable -- which also declares the label the rule submits, because the counter
compares that label to gold and guesses none (R-34, R-66). Two certifiers with two copies of the
counting is how a published automation rate stops describing the rule the deployment applies.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .case_count import Verdict, case_key, count_outcome
# The rubric is IMPORTED here and never restated (#62, R-187). The two floors used to be declared in
# this module, in `certify_score.py` and in `certify_threshold.py`, and the diagnostic grid in this
# module and in `certify_score.py` as two textually identical expressions -- five copies of three
# numbers, with no row that could notice one of them moving. `MIN_CASES_PER_SLICE` below stays,
# because it is a derived fact (the two halves of the split this rule certifies on) and not a
# restatement of one. `SPLIT_SEED_DEFAULT` is the library default for a shuffle and is deliberately
# NOT `SEED`, the published rubric's 7: the two are separate promises, and a seed that changes
# re-rolls the partition every published bound was measured on.
from .certificate import (ALPHA, BETA, CANONICALISED_BOUND_FIELDS, DELTA, DIAGNOSTIC_GRID, METHOD,
                          MIN_CAL, MIN_EVAL, N_CLAIMS, SPLIT_SEED_DEFAULT, Certificate, Reason,
                          canonicalise_bound)
from .conformal import METHODS, classify_set, conformal_set, split_quantile
from .correction import (GROUP_FLOOR_MESSAGE, corrected_delta, group_alpha, group_beta,
                         joint_level_inputs, size_floor, worst_group)
from .groups import by_group
from .tails import bound_width, clopper_pearson_upper

_BASE_ENVELOPE = (
    "exchangeability within group assumed; no group conditioning applied",
    "marginal certificate only - not group-conditional",
    "certified on archived responses; live traffic shift is not covered",
)

# The floor a slice has to clear before it is certified at all, stated in CASES because the
# denominator of every slice-level bound is cases, not records. `MIN_CAL + MIN_EVAL` is not a taste
# and not a second threshold: a slice below it cannot supply both halves the two-way construction of
# spec 5.3 runs on, so the floor and the shipped minima have one owner. `correction.py` reads the
# floor as a parameter for exactly that reason -- a floor stated in cases belongs with the
# certificate that publishes the bound, while the corrected level belongs with the claim (spec 8.1).
MIN_CASES_PER_SLICE = MIN_CAL + MIN_EVAL


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


def split_cal(records: Sequence, seed: int = SPLIT_SEED_DEFAULT):
    """Split by CASE, not by record.

    A random record-level split put repeats of the same case in both halves: measured on
    the committed archive, 44 of the 53 cases in jev's evaluation half also sat in its
    calibration half, so the quantile was fixed on the very cases later held out to test
    it. That violates the exchangeability unit of the guarantee rather than loosening it.
    Whole cases now go to one side; the halves stay balanced by record count.
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


def _scores(records, method: str) -> list:
    fn = METHODS[method]
    return [fn(r.probs, r.gold_index, r.u) for r in records]


# `classify_set` spells its multi-label outcome "escalate"; the shared counter's name for
# that published bucket is "multi" (it is what `multi_label` counts). The translation is
# the set rule's own business: `case_count` must not learn set vocabulary, or the threshold
# gate would depend on the set gate's internals.
_SET_KINDS = {"auto": "auto", "empty": "empty", "escalate": "multi"}


def _set_rule(qhat, method):
    """The APS/LAC rule as the shared counter's ONE `decide` callable (R-66).

    The label this rule submits is the one inside its certified singleton, because that is the
    label `gate.py:66-67` delivers when the set is a singleton -- `options[C[0]]`, not the record's
    `predicted`. Saying so here is the rule's job: the counter compares a submitted label to gold
    and guesses none, and the archive's own `predicted == argmax` coincidence is not a reason for
    two rules to share one assumed answer.
    """
    def decide(r):
        C = conformal_set(r.probs, qhat, r.u, method)
        outcome = _SET_KINDS[classify_set(C)]
        return Verdict(outcome, r.options[C[0]] if outcome == "auto" else None, len(C))

    return decide


def _outcome(ev, qhat, method):
    """One application of the set rule, counted by the shared case arithmetic (R-34).

    The counting lives in `case_count`; what stays here is the set rule itself and the rename
    the shared module deliberately does not do: it publishes its average as `mean_measure`,
    because shared arithmetic that names a published figure would give that figure two owners,
    and `mean_set_size` is THIS gate's name for it -- the name on `Certificate` and in the
    fields `verify` compares. Every record's verdict carries a set size, so this gate's mean is
    over all of its evaluated records, exactly as it was before the extraction.
    """
    observed = count_outcome(ev, _set_rule(qhat, method))
    observed["mean_set_size"] = observed.pop("mean_measure")
    return observed


def certify_choice(records: Sequence, alpha: float = ALPHA, beta: float = BETA,
                   delta: float = DELTA, seed: int = SPLIT_SEED_DEFAULT, method: str = METHOD,
                   grid: Optional[Sequence[float]] = None,
                   groups: Optional[Sequence[str]] = None):
    """Certify the automation rate the coverage level `1 - alpha` buys, under budget `beta`.

    `beta` bounds P(wrong | automated); `delta` is the level each published bound is
    tested at, and `N_CLAIMS` of them are made, so the joint confidence is 1 - N_CLAIMS*delta.

    `groups` switches the same function onto the group-conditional (Mondrian) surface of spec 8.1:
    with it, the return is a `GroupsCertificate` -- one certificate per declared slice at the
    corrected budgets, plus the simultaneous worst-of-G claim and the pooled certificate these slices
    were cut from. Left as `None`, every number below is exactly what it was, and the certificate
    stays the marginal one `verify` re-derives.
    """
    if method not in METHODS:
        raise ValueError("unknown method %r; choose from %s" % (method, sorted(METHODS)))
    for name, v in (("alpha", alpha), ("beta", beta), ("delta", delta)):
        if not 0.0 < v < 1.0:
            raise ValueError("%s must be in (0,1), got %r" % (name, v))
    if groups is not None:
        return certify_groups(records, alpha=alpha, beta=beta, delta=delta, seed=seed,
                              method=method, grid=grid, groups=groups)
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
                                   n_cal=0, n_eval=0, delta=delta, backend=backend, method=method,
                                   detail="no labelled choice records to calibrate on", meta=meta)
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(Reason.N_BELOW_MIN, alpha=alpha, beta=beta,
                                   n_cal=len(cal), n_eval=len(ev), delta=delta, backend=backend, method=method,
                                   detail="need %d/%d, have %d/%d" % (MIN_CAL, MIN_EVAL,
                                                                      len(cal), len(ev)),
                                   meta=meta)
    cal_scores = _scores(cal, method)
    n_ev = len(ev)
    qhat, vacuous = split_quantile(cal_scores, alpha)
    observed = _outcome(ev, qhat, method)
    autom, err = observed["automated"], observed["errors"]
    n_case, auto_case, err_case = (observed["n_cases"], observed["automated_cases"],
                                   observed["erroneous_cases"])
    # `bound_width` is `math.log`'s output, so it is canonicalised here rather than at the
    # two endpoints it feeds: with a canonical width and a canonical rate, each endpoint is
    # a correctly-rounded subtraction, which every platform reproduces bit for bit.
    half_width = canonicalise_bound(bound_width(n_case, delta)) / 2.0
    meta.update(empties=observed["empties"], multi_label=observed["multi_label"],
                automated=autom, errors_among_automated=err, n_eval_cases=n_case,
                automated_cases=auto_case, erroneous_cases=err_case,
                n_cal_cases=len({case_key(r) for r in cal}),
                unit_note="%d evaluation records over %d distinct cases: the bounds use the "
                          "case denominator, because repeats of one case are one "
                          "observation" % (n_ev, n_case))
    if vacuous:
        return Certificate.refused(
            Reason.VACUOUS_QUANTILE, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=method,
            detail="the %.3f-quantile of %d calibration scores is above 1, so every label "
                   "would be certified" % (alpha, len(cal)),
            meta=_with_diagnostic(meta, cal_scores, ev, method, grid, beta, delta))
    if autom == 0 or auto_case == 0:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=method,
            detail="at coverage %.3f no evaluation case produced a singleton set (%d empty, "
                   "%d multi-label of %d)" % (1.0 - alpha, observed["empties"],
                                              observed["multi_label"], n_ev),
            meta=_with_diagnostic(meta, cal_scores, ev, method, grid, beta, delta))
    # Canonicalised at the source, so the number the budget test below reads is the number
    # the certificate publishes: a refusal and its published bound cannot disagree by
    # rounding, and neither depends on which C library ran `math.exp` (R-121).
    cond_hi = canonicalise_bound(clopper_pearson_upper(err_case, auto_case, delta))
    marg_hi = canonicalise_bound(clopper_pearson_upper(err_case, n_case, delta))
    rate = auto_case / n_case
    envelope = _BASE_ENVELOPE + (
        "set size fixed by the requested alpha=%.3f (coverage %.3f); no grid selection on "
        "the evaluation half" % (alpha, 1.0 - alpha),
        "finite-sample: bounds on CASES -- %d of %d evaluation cases automated, %d refused; "
        "record counts n_cal=%d n_eval=%d (%d empty sets, %d multi-label); %d claims at "
        "delta=%.3f, joint level %.2f" % (
            auto_case, n_case, n_case - auto_case, len(cal), n_ev, observed["empties"],
            observed["multi_label"], N_CLAIMS, delta, 1.0 - N_CLAIMS * delta),
        "empty certified sets counted as refusal, not automation",
    )
    cert = Certificate(
        feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta, method=method,
        backend=backend, qhat=qhat, autorate=rate,
        autorate_ci=(max(0.0, rate - half_width), min(1.0, rate + half_width)),
        conditional_error_bound=cond_hi, marginal_error_bound=marg_hi,
        mean_set_size=observed["mean_set_size"],
        n_cal=len(cal), n_eval=n_ev, envelope=envelope,
        meta={**meta, "closest_attempt": None},
    )
    if cond_hi > beta:
        return Certificate.refused(
            Reason.EMPTY_FEASIBLE_SET, alpha=alpha, beta=beta, n_cal=len(cal), n_eval=n_ev,
            delta=delta, backend=backend, method=method,
            detail="at coverage %.3f the %d automated cases include %d carrying a wrong "
                   "automated request; the exact case-level upper bound %.3f exceeds the "
                   "budget %.3f" % (1.0 - alpha, auto_case, err_case, cond_hi, beta),
            meta=_with_diagnostic({**meta, "at_requested_alpha": {
                "automated": autom, "errors": err, "conditional_error_bound": cond_hi}},
                cal_scores, ev, method, grid, beta, delta))
    return cert


def _canonicalised(row: dict) -> dict:
    """Round the named bound fields of one published row, and only those (R-121).

    `CANONICALISED_BOUND_FIELDS` drives the walk, so a point of the diagnostic curve, the
    `closest_attempt` copy taken from it, and the certificate's own headline attributes all
    publish the identical canonical number -- while the fields of the same row that are NOT
    bounds (`qhat`, the two `observed_*` ratios, the counts) keep the exact double the
    records determine. That difference is the point: the sweep is by field name, not by
    "it looks like a float", and a blanket pass would be the tolerance this replaces.
    """
    return {key: (canonicalise_bound(value) if key in CANONICALISED_BOUND_FIELDS else value)
            for key, value in row.items()}


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
        curve.append(_canonicalised({
            "grid_alpha": a, "qhat": q, "automated": obs["automated"],
            "errors": obs["errors"], "empties": obs["empties"],
            "multi_label": obs["multi_label"],
            "observed_automation_rate": obs["automated"] / len(ev),
            "observed_conditional_error": obs["errors"] / obs["automated"],
            "conditional_error_bound": bound}))
    if not curve:
        return {**meta, "closest_attempt": None, "diagnostic_curve": []}
    best = min(curve, key=lambda c: (c["conditional_error_bound"],
                                     -c["observed_automation_rate"]))
    return {**meta, "closest_attempt": best, "diagnostic_curve": curve,
            "diagnostic_note": "the grid below was swept on the evaluation half for "
                               "evidence only; nothing on it was certified"}


def _group_row(name, cert: Certificate, n_cases: int, groups_declared, corrected: dict) -> dict:
    """One slice, in the shape `correction.worst_group` reads.

    Deliberately not a `Certificate`: the correction module owns arithmetic and must not become an
    owner of the shape it reads (`correction.py`'s own rule), and this row is where the case count
    that the size floor and the worst-of-G tie-break both read gets stated under one name.

    No simultaneous level is derived from these rows, and the caller says so (`derive_joint_level=False`
    on the `worst_group` call). A shipped certificate's meta carries `alpha` and `beta` as RISK TARGETS
    -- the coverage level that sized the set, and the budget the bound had to beat -- while the two
    budgets that actually pay for the published envelopes are `N_CLAIMS` bounds each tested at
    `delta / G`. Feeding the targets to the derivation would print a level that coincides with the
    right one at the published rubric (where `alpha == beta == delta`) and is 0.91 instead of 0.85 the
    moment `beta` moves. The family level therefore has exactly one publisher: `GroupsCertificate.
    level`, derived below from `delta`.
    """
    return {
        "group": name,
        "feasible": cert.feasible,
        "reason": cert.reason,
        "autorate": cert.autorate,
        "conditional_error_bound": cert.conditional_error_bound,
        "marginal_error_bound": cert.marginal_error_bound,
        "level": cert.level,
        "n_cases": n_cases,
        "meta": {**cert.meta, "slices": name, "n_eval_cases": n_cases,
                 "groups_declared": groups_declared, **corrected},
    }


@dataclass(frozen=True)
class GroupsCertificate:
    """The Mondrian run: one certificate per declared slice, and ONE simultaneous claim over them.

    The pooled certificate travels with the slices (`pooled`) because spec 8.1's failure mode is a
    reader who sees one number and infers the other. They are not interchangeable and this object
    never collapses them: a pooled certificate over a population whose thin slice refused says the
    deployment is inside budget while the run that conditioned on the slice says it is not.

    Fields the artefact has to state, per R-149 and R-159: `n_groups` (the data's slice count, the
    only thing that may divide a budget), the uncorrected `alpha`/`beta`/`delta`, the corrected
    budgets -- of which `corrected_alpha` and `corrected_delta` are what this run SPENDS and
    `corrected_beta` is the counterfactual it does not -- `n_claims` per slice, and the resulting
    family `level`.

    `n_min_violations` is the name spec §10 gives it (line 208, and line 214 makes it and `envelope`
    non-optional in the output shape): which slices refused, and why. Its entries are the richer record
    `{group, n, floor, reason}` rather than the spec's example string
    `"option_count:11+ : n=41 < 120"` -- that is the spec's fact carried in full, not a deviation from
    it: the string states one slice's count and floor, and the row states the same two numbers plus the
    slice as a name and the sentence that refused it, so a reader never has to re-run the floor to check
    the published refusal. The requirement §10:214 places on this field is PRESENCE, not non-emptiness:
    an empty list is the fact that no slice fell below the floor -- which is what the published language
    run states -- while a serialized run lacking the key is a shape violation and `__post_init__` refuses
    it. It was called `refused_by_size` until B3 Task 5 landed this name and this shape change together
    (the deferral R-149/2 recorded); nothing in this build reads or writes that name any more, and no
    alias bridges them -- a stale artefact is refused, not renamed. The count of these rows stays
    published as `meta.n_refused_by_size`, which is the same fact in numbers.
    """

    groups: tuple
    n_groups: int
    alpha: float
    beta: float
    delta: float
    corrected_alpha: float
    corrected_beta: float
    corrected_delta: float
    n_claims: int
    per_group: dict = field(default_factory=dict)
    pooled: Optional[Certificate] = None
    worst: Optional[Certificate] = None
    worst_claim: dict = field(default_factory=dict)
    n_min_violations: list = field(default_factory=list)
    slice_census: list = field(default_factory=list)
    envelope: tuple = ()
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(self, "envelope", tuple(self.envelope))
        if len(self.per_group) != self.n_groups:
            raise ValueError("a worst-of-%d claim has %d certificates: the slice count that divides "
                             "the budgets and the slices actually certified have to be the same "
                             "number, or the correction is applied to a family that does not exist"
                             % (self.n_groups, len(self.per_group)))
        if not self.envelope:
            raise ValueError("every certificate needs a non-empty envelope of assumptions")
        # Same enforcement STYLE as `envelope` above and `certificate.py:243-244`, opposite requirement:
        # `envelope` has to be non-empty to mean anything, while `n_min_violations` only has to be
        # PRESENT -- `[]` is a result and `None` is a shape violation (spec §10:214).
        if self.n_min_violations is None:
            raise ValueError("a Mondrian certificate cannot serialize without `n_min_violations`: "
                             "spec §10:214 makes the key non-optional in the output shape, and an "
                             "empty list already states that no slice was refused by the size floor")
        if self.n_groups < 1:
            raise ValueError("no slices to certify; a worst-of-0 claim is not a claim")

    @property
    def level(self) -> float:
        """The joint confidence of the whole worst-of-G statement: 1 - n_claims * delta.

        Derived, in one place, from the same arithmetic `correction.joint_level` publishes -- and it
        is CONSTANT in `n_groups`, which is not an oversight but the Bonferroni property the
        correction exists to buy: each slice's `N_CLAIMS` bounds are tested at `delta / n_groups`, so
        the union over `n_groups * N_CLAIMS` envelopes is `n_groups * N_CLAIMS * (delta/n_groups) =
        N_CLAIMS * delta` however many slices the census produced. The slices' own certificates each
        read a *higher* level (1 - N_CLAIMS*delta/n_groups); the family reads 0.85, the same number a
        single pooled certificate publishes. See `correction.py`'s module docstring for the ruling.
        """
        return joint_level_inputs({"alpha": self.delta, "beta": self.delta}, self.n_groups,
                                  self.n_claims)["level"]

    @property
    def feasible(self) -> bool:
        """A worst-of-G permission exists only if EVERY slice certified -- so does the worst one.

        This is what `cli.cmd_certify` maps to exit 0 or exit 3, and it is deliberately the
        conjunction over the slices rather than `pooled.feasible`: the pooled certificate is a
        different (marginal) claim about the same records, and answering 0 because the pool certified
        while a slice has no bound at all is the move spec 8.1 exists to forbid.
        """
        return all(cert.feasible for cert in self.per_group.values())

    @property
    def slice_cases(self) -> dict:
        """Group name -> independent CASES, read from the census rather than stored beside it.

        The floor and the worst-of-G tie-break both read this, and `slice_census` already carries it
        per slice: a second stored map would be a second owner of a count that decides refusals.
        """
        return {row["group"]: row["cases"] for row in self.slice_census}

    @property
    def slice_eligible_cases(self) -> dict:
        """Group name -> the CASES THE CERTIFIER WAS HANDED, read from the same census rows.

        The sibling of `slice_cases`, and derived the same way for the same reason: a rendered slice
        line has to say which of the two numbers it is stating, and the two must be reconstructible
        from one artefact rather than from a map somebody kept beside it.
        """
        return {row["group"]: row["eligible_cases"] for row in self.slice_census}

    @property
    def thinnest(self):
        """The slice with the fewest independent CASES -- the one the census can refuse first."""
        return min(self.slice_census, key=lambda row: (row["cases"], str(row["group"])))["group"]

    @property
    def any_slice_refused(self) -> bool:
        return bool(self.worst_claim.get("any_slice_refused"))

    def summary(self) -> str:
        head = ("group-conditional (Mondrian) run over %d slices declared as %s: %d certified, %d "
                "refused" % (self.n_groups, ", ".join(repr(g) for g in self.groups),
                             sum(1 for c in self.per_group.values() if c.feasible),
                             sum(1 for c in self.per_group.values() if not c.feasible)))
        verdict = ("NOT_CERTIFIED: the worst slice (%s) refused, so no worst-of-%d permission exists"
                   % (self.worst_claim.get("worst", {}).get("group"), self.n_groups)
                   if self.any_slice_refused else
                   "certified: worst slice %s autorate %s"
                   % (self.worst_claim.get("worst", {}).get("group"),
                      self.worst_claim.get("worst", {}).get("autorate")))
        sizes = ("; refused by size (below the floor of %d cases, named, never averaged away): %s"
                 % (self.meta.get("min_cases_per_slice"),
                    ", ".join("%s(n=%d)" % (row["group"], row["n"])
                              for row in self.n_min_violations)) if self.n_min_violations else "")
        joint = ("; joint level %.4f over %d slices x %d claims at delta=%.3f corrected to %.6f per "
                 "slice (uncorrected alpha=%.3f beta=%.3f delta=%.3f)"
                 % (self.level, self.n_groups, self.n_claims, self.delta, self.corrected_delta,
                    self.alpha, self.beta, self.delta))
        pooled = ("; the POOLED certificate over these same records says feasible=%s autorate=%s "
                  "conditional bound=%s -- a slice refusal is not averaged away by that number"
                  % (self.pooled.feasible, self.pooled.autorate, self.pooled.conditional_error_bound))
        return head + " | " + verdict + sizes + joint + pooled

    def to_dict(self) -> dict:
        return {
            "groups": list(self.groups), "n_groups": self.n_groups, "alpha": self.alpha,
            "beta": self.beta, "delta": self.delta, "corrected_alpha": self.corrected_alpha,
            "corrected_beta": self.corrected_beta, "corrected_delta": self.corrected_delta,
            # `feasible` is the derived conjunction, published because it is what the CLI's exit code
            # answers: an artefact whose rc cannot be reconstructed from its own fields lets a re-run
            # and a read disagree about whether the worst-of-G permission exists.
            "n_claims": self.n_claims, "level": self.level, "feasible": self.feasible,
            "thinnest": self.thinnest,
            "any_slice_refused": self.any_slice_refused,
            "n_min_violations": self.n_min_violations, "slice_census": self.slice_census,
            # Stringified exactly like `per_group` below, and for the same reason: a two-key
            # declaration (`--groups family,mode`) makes the group a TUPLE, and `json.dumps` refuses a
            # tuple key with `TypeError: keys must be str, int, float, bool or None` -- measured as rc
            # 1 through the real CLI before this line was rendered, which is outside the 0/2/3/4
            # contract. Values may be tuples (they serialize as lists); keys may not.
            "slice_cases": {str(name): n_cases for name, n_cases in self.slice_cases.items()},
            "slice_eligible_cases": {str(name): n for name, n
                                     in self.slice_eligible_cases.items()},
            # `str(name)` is not cosmetic: `by_group` names a one-key slice by its value and a
            # multi-key slice by a tuple, and a tuple is not a JSON object key. One rendering rule,
            # applied to every map keyed by a group, so the two cannot disagree about what a slice
            # is called.
            "per_group": {str(name): cert.to_dict() for name, cert in self.per_group.items()},
            "pooled": self.pooled.to_dict() if self.pooled else None,
            "worst_claim": self.worst_claim, "envelope": list(self.envelope), "meta": self.meta,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def certify_groups(records: Sequence, alpha: float = ALPHA, beta: float = BETA,
                   delta: float = DELTA,
                   seed: int = SPLIT_SEED_DEFAULT, method: str = METHOD,
                   groups: Sequence[str] = ("family",),
                   floor: int = MIN_CASES_PER_SLICE,
                   grid: Optional[Sequence[float]] = None) -> GroupsCertificate:
    """Group-conditional (Mondrian) certification with the simultaneous correction applied (spec 8.1).

    The construction, and the three numbers that must not be confused:

    * `alpha` is divided by the slice count. That is §8.1's literal "Bonferroni on alpha", and it is
      where the correction actually bites: a smaller `alpha` sizes a LARGER set, so a slice automates
      less, and a thin slice can stop automating at all.
    * `delta` is divided by the slice count, because each slice publishes `N_CLAIMS` bounds and the
      family claims `n_groups * N_CLAIMS` of them. This is the division `certificate.py`'s
      `level = 1 - N_CLAIMS * delta` is the other half of.
    * `beta` is NOT divided, and that is a decision rather than an oversight. `beta` is the budget a
      slice's conditional-error bound has to beat, and bounding every slice at `beta` already bounds
      the worst one at `beta`; bounding each at `beta / n_groups` would promise something the
      deployment did not ask for and would make the pooled-vs-slice divergence an artefact of a
      self-imposed straitjacket instead of the slice structure §8.1 is about. The divided value is
      computed and PUBLISHED (`corrected_beta`) as the counterfactual a divided budget would have
      cost, and nothing in this module compares a bound with it -- the envelope line says so, because
      a sentence implying the reader could see the spent budget in the pair would describe a control
      flow that does not exist (F-8 of the Task 2 review). R-124 respected: none of this says looser
      coverage automates more -- an empty set is a refusal, and automation is non-monotone in `alpha`.

    A slice below `floor` CASES is refused BY NAME and never certified: no slice-level bound exists at
    that `n`, and averaging its records into the neighbours is precisely the move that produces the
    false claim §8.1 names. The pooled certificate over the same records is still computed and still
    published beside the slices, so the divergence is on the artefact rather than in a reader's head.
    """
    slices = by_group(records, groups)
    g = len(slices)
    subjects = {r.backend for r in records if r.backend}
    if len(subjects) > 1:
        # The same correction `certify_score.py:219-225` and `certify_threshold.py:301-310` make: a
        # certificate names one subject, and a worst-of-G over two models states one permission for
        # two deployments. The marginal set gate answers a mixed batch with `backend=None` (its own
        # published behaviour, which `verify` compares and this function does not change); a
        # group-conditional claim cannot inherit that silence.
        raise ValueError("a certificate names one subject; this population spans backends %s -- "
                         "certify one backend at a time" % ", ".join(sorted(subjects)))
    backend = subjects.pop() if len(subjects) == 1 else None
    declared = tuple(groups)
    rubric = {"alpha": alpha, "beta": beta}
    uncorrected_alpha, corrected_alpha = group_alpha(rubric, g)
    _b0, corrected_beta = group_beta(rubric, g)
    corrected_delta_value = corrected_delta(delta, g)
    per_group: dict = {}
    rows: list = []
    census: list = []
    n_min_violations: list = []
    corrected_fields = {"corrected_alpha": corrected_alpha, "corrected_beta": corrected_beta,
                        "corrected_delta": corrected_delta_value, "n_claims": N_CLAIMS}
    for name, members in slices.items():
        kept, dropped = _eligible(members)
        n_cases = len({case_key(r) for r in members})
        # The population the certifier is actually handed below, counted in the same unit. `cases` is
        # the slice's HOLDING and is what the floor is priced on; `eligible_cases` is what a slice's
        # bound rests on, and printing only the first tells a reader 140 labelled cases were refused
        # when the certificate was built from zero of them (G2/F-5 of the Plan B3 Task 2 review).
        n_eligible_cases = len({case_key(r) for r in kept})
        census.append({"group": name, "cases": n_cases, "records": len(members),
                       "kept": len(kept), "eligible_cases": n_eligible_cases, **dropped})
        detail_meta = {"groups_declared": declared, "n_eval_cases": n_cases,
                       "min_cases_per_slice": floor, "backend": backend}
        if size_floor(n_cases, floor):
            why = ("%s (slice %r holds %d independent cases; the floor is %d, which is MIN_CAL + "
                   "MIN_EVAL -- the two halves of the split this rule certifies on)"
                   % (GROUP_FLOOR_MESSAGE, name, n_cases, floor))
            cert = Certificate.refused(Reason.N_BELOW_MIN, alpha=corrected_alpha, beta=beta,
                                       n_cal=0, n_eval=len(members), delta=corrected_delta_value,
                                       detail=why, meta=detail_meta, backend=backend, method=method)
            n_min_violations.append({"group": name, "n": n_cases, "floor": floor, "reason": why})
        else:
            # One rule, one code path: the slice is certified by the pooled certifier at the
            # corrected budgets, so a slice-level bound and the published marginal bound cannot be
            # produced by two different implementations that drift apart.
            cert = certify_choice(kept, alpha=corrected_alpha, beta=beta,
                                  delta=corrected_delta_value, seed=seed, method=method, grid=grid)
            cert.meta["groups_declared"] = declared
            cert.meta["min_cases_per_slice"] = floor
        per_group[name] = cert
        rows.append(_group_row(name, cert, n_cases, declared, corrected_fields))
    pooled = certify_choice(records, alpha=alpha, beta=beta, delta=delta, seed=seed, method=method,
                            grid=grid)
    claim = worst_group(rows, metric="autorate", floor=floor, derive_joint_level=False)
    corrected_union = g * N_CLAIMS * corrected_delta_value
    uncorrected_union = g * N_CLAIMS * delta
    uncorrected_level = 1.0 - uncorrected_union
    envelope = (
        "group-conditional (Mondrian): the guarantee is conditional on %s, and exchangeability "
        "within group is ASSUMED here and not proved by this run" % (", ".join(repr(x) for x in declared),),
        "worst-of-%d claim with the simultaneous correction: alpha %.3f -> %.6f and delta %.3f -> "
        "%.6f per slice, %d claims per slice, so the family risk is %d x %d x %.6f = %.4f and the "
        "joint level is %.4f"
        % (g, uncorrected_alpha, corrected_alpha, delta, corrected_delta_value, N_CLAIMS, g, N_CLAIMS,
           corrected_delta_value, corrected_union, 1.0 - corrected_union),
        "beta is NOT divided and the divided budget is NOT spent: every slice's bound is tested "
        "against the uncorrected %.3f, which is the number that gates this run, and bounding each "
        "slice at %.3f already bounds the worst at %.3f; %.6f is published as the counterfactual a "
        "divided budget would have cost, and no bound in this artefact is compared with it"
        % (beta, beta, beta, corrected_beta),
        "an UNCORRECTED worst-of-%d at delta=%.3f would claim 1 - %d x %d x %.3f = %.4f, %s" % (
            g, delta, g, N_CLAIMS, delta, uncorrected_level,
            ("which is NOT a probability -- this is why the correction is not decorative"
             if not (0.0 < uncorrected_level < 1.0) else
             "which is a probability, but only until the census is large enough to break it: the "
             "line above is the claim this run actually makes, and it is paid for by the division "
             "this one undoes"),
        ),
        "the pooled (marginal) certificate over these same records is published beside the slices "
        "and is NOT a substitute for them: %s" % pooled.summary(),
        "certified on archived responses; live traffic shift is not covered",
    )
    return GroupsCertificate(
        groups=declared, n_groups=g, alpha=alpha, beta=beta, delta=delta,
        corrected_alpha=corrected_alpha, corrected_beta=corrected_beta,
        corrected_delta=corrected_delta_value, n_claims=N_CLAIMS, per_group=per_group, pooled=pooled,
        worst=per_group[claim["worst"]["group"]], worst_claim=claim, n_min_violations=n_min_violations,
        slice_census=census, envelope=envelope,
        meta={"seed": seed, "method": method, "min_cases_per_slice": floor,
              "groups_declared": declared, "backend": backend,
              "n_refused_by_size": len(n_min_violations),
              "slices_declared_but_empty": [row["group"] for row in census if not row["kept"]],
              "census_note": "every slice is in slice_census with its own skipped_no_gold / "
                             "skipped_wrong_qtype counts; a slice whose records all lack gold is "
                             "reported as skipped and refused, never filtered out of the run"},
    )
