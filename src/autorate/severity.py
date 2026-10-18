"""The one-sided severity certificate (spec 6.2) and the tolerance band (spec 6.3) -- G3.

What is certified is a quantity the set gates cannot state: for a reported level rule ``ahat(X)``,
``P(Y > ahat(X)) <= alpha`` at confidence ``1 - delta``, read as "we never under-call severity by more
than this, at this confidence". A set certificate bounds ``P(Y not in C(X))``, which says nothing about
WHICH SIDE of the report the truth sits on, and this module's test file carries the constructed
comparison rather than the assertion: a population and its scale-reversal give the ordinal set gate and
APS byte-identical certificates while this gate answers them ``ahat=3`` (bound 0.038310, over-call
price 0.658075) against ``ahat=0`` (bound 0.014867, price 0.083335).

The construction (§6.2). For a candidate reported level ``a`` the loss ``1{Y > a}`` is monotone
decreasing in ``a``, so a binary search over the K levels returns the smallest ``a`` whose empirical
risk -- bounded one-sided by Clopper-Pearson over CASES -- meets the budget. The monotonicity is a
PRECONDITION and is measured on the population in front of it (§6: "we require monotonicity as a
precondition rather than assuming it away"), which is why ``direction="both_sides_sum"`` -- the naive
weighted loss of §6.1, the one that "is not monotone in tau and therefore does not satisfy the CRC
precondition" -- is refused here by its own measured curve and not by its name.

The three rules, and why they are three and not one (§6.1's precedent: "each certified separately and
both reported"). ``under`` lifts the model's own level to a floor, ``report_level = max(modal, a)``, and
its risk falls as ``a`` rises, so the search takes the SMALLEST feasible ``a`` (the least intervention
still certified). ``over`` clips it, ``report_ceiling = min(modal, a)``, whose risk RISES with ``a``, so
the search takes the LARGEST feasible ``a`` -- both are "the most faithful rule that meets the budget",
and getting the direction of the search wrong would silently certify the constant bottom of a rubric
and call it a guarantee. ``both_sides_sum`` reports the constant ``a`` and is in the table only so that
the precondition has something to refuse.

The certification unit is the CASE (R-36/R-44), and a case is counted as violating when ANY of its
records does -- the aggregation rule `case_count.count_outcome` uses for "a case is erroneous when any
automated record put forward a wrong label", restated for a one-sided loss because that counter
compares ``submitted != gold`` and cannot express ``>``. `case_count` is deliberately NOT widened for
this: a shared counter that learned severity vocabulary would make the two set gates depend on it. The
split is not a third copy either -- `severity.py` CALLS `certify_score.split_cal`, so the severity
certificate and the ordinal set certificate are computed on one held-out half, which is the only way
spec §6.4's "contrasted on the same records" is a property of the code.

The joint level, and the reading this module rejects (ruling R-160). §5.3 fixes coverage on one split
and bounds the conditional error on the other and says the pair "carries a union-bound confidence
level"; §6.1 certifies two one-sided risks at `alpha_miss` and `alpha_block`, i.e. ONE BUDGET PER
FAILURE EVENT. A union bound over distinct events is a sum of their budgets, and `correction.joint_level`
-- the one owner of the simultaneous arithmetic -- bounds every such sum by ``n_claims * max(budgets)``,
which is conservative for any assignment of budgets to envelopes. So the 0.85-against-0.90 discrepancy
R-160 recorded is not a max-versus-sum disagreement: with every envelope paid at the same budget the
two readings are the same arithmetic, and ``1 - (alpha + beta)`` = 0.90 is the level of the §5.3 PAIR,
i.e. TWO envelopes. What decides a published "joint confidence" is therefore the ENVELOPE COUNT, which
each gate must state: a severity certificate publishes three bounds (the requested one-sided risk, the
opposite-side price at the same rule, and the rate at which the rule replaces the model's own level),
so its level is `1 - N_CLAIMS * delta` = 0.85 -- the same number the set shape publishes at the same
rubric, and `tests/test_severity.py` asserts the agreement through `correction` rather than letting two
gates each ship a convention. `tolerance_band` publishes ONE bound, states ``n_claims = 1``, and
therefore says 0.95 under the same rule; that is the reading a reader who wants 0.90 for a run must
earn by naming the envelope they dropped.

Refusals, and which one belongs to which finding (ruling R-92b). Every family searched here contains a
candidate that never errs (the top of the rubric for a floor, the bottom for a clip), so an EMPTY
family is never a fact about the task: it is ``1 - delta**(1/n) > alpha``, a calibration half too small
for any bound in the family to be informative -- `Reason.N_BELOW_MIN`, "the sample is short". What IS a
fact about the task is a band that saturates: `tolerance_band` refuses with
`Reason.NO_AUTOMATION_AT_COVERAGE` when the only band the budget licenses is the whole rubric, because
that sentence contains every level whatever the data said and no amount of further data can shrink it
-- measured in the test file at 200 and at 2,000 calibration cases, where the bound on the next-narrower
band stays above three times the budget at both. This is the first gate to emit that reason; the two
dependent plans needed it in the closed set, and it is emitted here and nowhere else.

Prior art, stated as §12 requires. The ordinal set construction is Dey, Merugu and Kaveri (NeurIPS
2023) and Zhang et al. (AAAI-26); ordinal conformal risk control with two ordinal-specific losses is
Xu, Guo and Wei, UAI 2023 (PMLR 216:2346-2355) -- the venue the ERRATA settled after the design first
named another one, whose ledger row is ``ordinal-cp-aistats2023``, and the paper row is
``ordinal-crc-uai2023-two-losses``, opened at the proceedings' own PDF, which states no one-sided
``P(Y > ahat(X)) <= alpha``. So the delta here is the automation rule and the one-sided statement, not
the mathematics, and G3 is void if a systematic search starting from those two rows finds the
statement already made.

Evidence boundary. The offline archive carries no `score` answers at all -- measured across the four
committed records files: `data/records_feishu.jsonl` is `choice`+`noul`, and the three MASSIVE files are
`choice`, so not one of them holds an ordinal record and `certify_severity` refuses such a population by
name. Every figure this project demonstrates with this gate is therefore a function of synthetic ordinal
data with known answers: seeded, re-derivable, and not a measurement of any shipped model. The gate cannot
see provenance and claims none; a caller who hands in real records gets the same arithmetic over different
data, and the envelope says so. What Task 72 changed is REACH, not evidence: `autorate severity` produces
this artefact, `autorate verify` re-derives it in both lanes, and `docs/SEVERITY.md` renders it. The
published certificate is certified over the population `tests/_records.build_ordinal` owns, and
`test_the_committed_ordinal_records_file_is_the_owner_generator_output` pins the committed records byte for
byte against that generator -- which is also why the ordinal rows survive the corpus-absent lane: nothing in
them reads the vendored archive.

The automation-rate shape, so no sentence here leans on the wrong monotonicity (R-124). The severity
path IS monotone in its risk target, for a structural reason: the rule answers every case, so there is
no empty certified set to grow as the budget loosens. A SET rule is not -- measured on the same
generator, looser coverage produced 78 automated cases at alpha=0.01 and 74 at alpha=0.02, because a
wider set that is not a singleton is a refusal. "Looser coverage automates more" is false, and the
interesting corollary is G3's own argument: a rule that always answers can be made monotone and says
nothing about which side it missed, while a set rule refuses where it cannot say.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

from .case_count import case_key
from .certificate import N_CLAIMS, SHAPE_KEY, Reason, canonicalise_bound
from .certify_score import MIN_CAL, MIN_EVAL, split_cal
from .correction import JOINT_LEVEL_RULE, joint_level
from .ordinal import mode_index
from .tails import clopper_pearson_upper

# The subject this gate certifies. `score` is the ordinal primitive (spec 1); `choice` option lists
# carry no order, so `1{Y > a}` is not defined on them and a severity certificate over choice traffic
# would be a claim about a scale nobody declared.
SUBJECT = "score"

# The three loss families. `both_sides_sum` is §6.1's naive weighted loss -- present so the monotone
# precondition is a measurement with something to refuse, not a name lookup.
DIRECTIONS = ("under", "over", "both_sides_sum")

# A feasible severity certificate publishes exactly three canonical bounds, so the count of envelopes
# is taken from the shape that already owns it rather than restated here: two gates that each ship a
# 3 would be two owners of the number that decides a published joint confidence (R-160).
SEVERITY_N_CLAIMS = N_CLAIMS

# `alpha` on this gate is a RISK target, not a confidence. `delta` is the level each published bound is
# tested at, and `SEVERITY_N_CLAIMS` of them are made, so the joint confidence is
# `correction.joint_level(rubric={delta, delta}, n_groups=1, n_claims=3)`.
_BASE_ENVELOPE = (
    "exchangeability within group assumed; no group conditioning applied",
    "marginal certificate only - not group-conditional",
    "certified on the records handed in; no upstream provenance is checked here, and live traffic "
    "shift is not covered",
    "the offline archive carries no `score` answers: every figure demonstrated with this gate is "
    "synthetic ordinal data with known answers",
)

# Which way each family moves, and which end of the feasible set is the informative one. The two
# fields are one fact: a risk that falls as the parameter rises is searched from the small end, and
# one that rises is searched from the large end, so that both directions return "the most faithful
# rule that still meets the budget" instead of the most conservative rule available.
_SENSE = {"under": "non_increasing", "over": "non_decreasing", "both_sides_sum": "non_increasing"}
_PICK = {"under": "first", "over": "last", "both_sides_sum": "first"}
_SIDE = {"under": "P(Y > ahat(X))", "over": "P(Y < ahat(X))", "both_sides_sum": "P(Y != ahat(X))"}
# Which side of the reported level `_price` actually counts, per family -- not which side a reader
# would expect to be the interesting one. `under` lifts, so its price is the over-call the lift
# introduced (the lower tail is where a floor over-reports); `over` clips, so its price is the upper
# tail; `both_sides_sum` reports a constant, and `_price` falls through to `gold < reported`, so its
# price is the LOWER tail. The naive loss has no upper-tail cases at all on a peaked rubric, so an
# upper-tail label there attributes a probability to an event the population does not contain.
_OTHER_SIDE = {"under": "P(Y < ahat(X))", "over": "P(Y > ahat(X))",
               "both_sides_sum": "P(Y < ahat(X))"}
# The headline says how many tails the guarantee covers. Only the two one-sided families carry the
# §6.2 claim; `both_sides_sum` bounds `P(Y != ahat(X))`, which the envelope discloses as "not a
# one-sided severity guarantee in either direction" -- a summary calling it one-sided would contradict
# the artefact it belongs to.
_KIND = {"under": "one-sided", "over": "one-sided", "both_sides_sum": "two-sided"}
# The same sentence has to name this gate's contribution per family, or the headline and the clause
# contradict each other inside one artefact: for the naive loss the contribution is the disclosure
# that it bounds neither tail alone, not a one-sided statement.
_DELTA_CLAIM = {"under": "the automation rule and the one-sided statement",
                "over": "the automation rule and the one-sided statement",
                "both_sides_sum": "the automation rule and the disclosure that it bounds "
                                  "P(Y != ahat(X)), neither tail alone"}
_OPPOSITE = {"under": "over", "over": "under", "both_sides_sum": "under"}


class SeverityShapeMismatch(ValueError):
    """A severity certificate was constructed in a shape that states something impossible.

    A `ValueError` of its own class, following the precedent for a new refusal in this repository
    (`MissingRecordField` in `records.py`, `UndeclaredGroupKey` in `groups.py`,
    `CertificateShapeMismatch` in `certificate.py`): it reaches a documented exit code through BOTH doors a
    severity document can come in by, and the name keeps it greppable in the error stream. A path the
    operator typed goes through `cli.main`'s `(OSError, ValueError)` arm to EXIT_USAGE; a path this
    package's own publication table declares goes through `report.load_published`, which turns the same
    refusal into `PublishedArtefactUnavailable` at EXIT_DRIFT, because there nobody argued with a filename
    -- the checkout is what stopped matching what it publishes. Before `autorate severity` existed this
    class described a path no user could walk, which is the debt R-170 recorded;
    `tests/test_severity_surface.py` walks both arms at the entry point.

    It is not a `ReaderContractError`, which is deliberately
    NOT a `ValueError` so the reader's per-line quarantine cannot absorb a corpus refusal.
    """


def _severity_level(delta: float) -> float:
    """The joint confidence of the three bounds this gate publishes at `delta`.

    One owner for the ASSIGNMENT as well as the arithmetic: the envelope line that states the claim
    count and `SeverityCertificate.level` are the same call, so a budget at which `correction`
    refuses to derive a probability cannot reach an artefact through one path and not the other. An
    envelope that computed `1 - n * delta` itself printed "-0.20" beside bounds the same artefact
    claimed were tested at a level the one owner would have raised on.
    """
    return joint_level({"alpha": delta, "beta": delta}, n_groups=1, n_claims=SEVERITY_N_CLAIMS)


def _budget(name: str, value) -> float:
    """One nominal level in the open interval (0, 1), refused by NAME and by type.

    `correction._level`'s rule, not a shorter one: `not 0.0 < "0.05" < 1.0` raises `TypeError`, and
    `cli.py` maps no `TypeError` to an exit code, so a budget that arrives as text -- which is how a
    CLI flag arrives -- would leave the documented 0/2/3/4 contract at rc 1. `bool` is excluded even
    though `True` is an `int`, because a probability is not a flag; `nan` is excluded because the
    comparison form `v <= 0 or v >= 1` would let it through as legal.
    """
    if isinstance(value, (bool, str, bytes)) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number in (0,1), got %r (%s)"
                         % (name, value, type(value).__name__))
    v = float(value)
    if not 0.0 < v < 1.0:
        raise ValueError("%s must be in (0,1), got %r" % (name, v))
    return v


def _level_arg(name: str, value, k: int) -> int:
    """A reported level: an int inside the rubric, refused as usage otherwise."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be a level index (int), got %r (%s)"
                         % (name, value, type(value).__name__))
    if not 0 <= value < k:
        raise ValueError("%s=%r is not a level of a %d-level rubric: the reported level indexes the "
                         "presented options, and a level outside the rubric certifies nothing"
                         % (name, value, k))
    return int(value)


def report_level(probs: Sequence[float], ahat: int) -> int:
    """The under-call floor: the level the deployment reports, ``max(modal level, ahat)``.

    The floor can only RAISE a report, which is what makes §6.2's guarantee a statement about the rule
    a deployment runs rather than about a bare constant: if ``P(Y > ahat) <= alpha`` then
    ``P(Y > max(modal, ahat)) <= alpha`` a fortiori, and the certificate measures the second quantity
    directly. The anchor is the ballot's modal level -- `ordinal.mode_index`, ties to the leftmost --
    because that is the label every other gate in this project submits (`gate.py` delivers
    ``options[C[0]]``, the modal level, for a singleton of the chain family), and a severity rule that
    read `predicted` instead would be answering a different question about the same record.
    """
    k = len(tuple(probs))
    ahat = _level_arg("ahat", ahat, k)
    return max(mode_index(probs), ahat)


def report_ceiling(probs: Sequence[float], ahat: int) -> int:
    """The over-call clip: the level the deployment reports, ``min(modal level, ahat)``.

    The mirror image of `report_level`, and the reason §6.2's "over-call is certified symmetrically"
    is not the same search: clipping the report lowers it, so the over-call risk rises with `ahat` and
    the informative feasible point is the LARGEST one, not the smallest.
    """
    k = len(tuple(probs))
    ahat = _level_arg("ahat", ahat, k)
    return min(mode_index(probs), ahat)


def _reported(probs: Sequence[float], a: int, direction: str) -> int:
    """The level the rule of `direction` reports at candidate `a`."""
    if direction == "under":
        return report_level(probs, a)
    if direction == "over":
        return report_ceiling(probs, a)
    return _level_arg("ahat", a, len(tuple(probs)))


def _loss(record, a: int, direction: str) -> bool:
    """The loss §6.2 is about: strictly one side of the reported level.

    `both_sides_sum` is the naive weighted loss -- both sides added, which is `1{Y != a}` -- and it is
    here so the precondition can be measured against it rather than asserted about it.
    """
    gold = record.gold_index
    reported = _reported(record.probs, a, direction)
    if direction == "under":
        return gold > reported
    if direction == "over":
        return gold < reported
    return gold != reported


def _price(record, a: int, direction: str) -> bool:
    """The other side of the SAME rule: what the floor (or the clip) costs in the opposite direction.

    A certificate that publishes the discount and not the price is the thing §6.1 refuses to do. This
    is measured at the certified rule, so for `under` it is the over-call the lift introduced -- not
    the separately certified over-call budget, which is `over_call_bound`'s own search.
    """
    gold = record.gold_index
    reported = _reported(record.probs, a, direction)
    if direction == "over":
        return gold > reported
    return gold < reported


def _override(record, a: int, direction: str) -> bool:
    """Whether the certified rule had to replace the model's own level to meet the budget.

    The severity analogue of an automation rate, and the number that tells a reader how much of the
    certificate is about the model and how much is about the rubric's end.
    """
    modal = mode_index(record.probs)
    if direction == "over":
        return modal > a
    return modal < a


def _cases(records: Sequence) -> dict:
    """Group a half by case, in first-seen order, so the case unit is the denominator."""
    groups: dict = {}
    for r in records:
        groups.setdefault(case_key(r), []).append(r)
    return groups


def _case_count(groups: dict, a: int, predicate) -> int:
    """Cases that violate: a case counts when ANY of its records does (R-34's aggregation, restated)."""
    return sum(1 for rows in groups.values() if any(predicate(r, a) for r in rows))


def _require_monotone(counts: Sequence[int], direction: str, n_cases: int) -> None:
    """The precondition §6 states and this module enforces: the loss family is monotone in the level.

    Measured on the population in front of it, not looked up in the direction table -- which is why a
    caller who asks for `both_sides_sum` gets a refusal naming the two candidates whose counts disagree
    with the search direction that family would need, and why the refusal cannot be quietly deleted:
    §6.1's naive weighted loss is not monotone in its parameter, so a search over it returns a level
    that bounds nothing. `n_cases` is in the message because the rates are the case unit and a reader
    comparing this against a record-level sweep needs to know which denominator spoke.
    """
    sense = _SENSE[direction]
    for i in range(len(counts) - 1):
        step_ok = (counts[i + 1] <= counts[i] if sense == "non_increasing"
                   else counts[i + 1] >= counts[i])
        if not step_ok:
            raise ValueError(
                "direction=%r is not monotone in the reported level, so no level in the family can be "
                "certified by searching it: candidate %d violates %d of %d cases and candidate %d "
                "violates %d, and the search for this direction needs a %s curve. Spec 6.1 is the "
                "precedent -- the naive loss that sums both sides is not monotone in its parameter and "
                "therefore does not satisfy the CRC precondition."
                % (direction, i, counts[i], n_cases, i + 1, counts[i + 1], sense))


def _bounds(counts: Sequence[int], n_cases: int, delta: float) -> list:
    """One canonical exact binomial upper bound per candidate, from the only owner of that arithmetic.

    Canonicalised BEFORE the budget is tested, in the same order `certify_choice` uses: the number the
    gate compares against `alpha` is the number it publishes, so a certificate cannot print a bound
    above the budget it just claimed to meet, and no platform's libm gets a vote (R-121/R-127).
    """
    return [canonicalise_bound(clopper_pearson_upper(c, n_cases, delta)) for c in counts]


def _search(bounds: Sequence[float], alpha: float, pick: str) -> Optional[int]:
    """The extreme feasible candidate, by binary search, cross-checked against a scan of the same array.

    §6.2 names a binary search and this gate ships one. The scan is not a second implementation of the
    machinery -- it is the search's own falsifier: the search is valid only if the bound array is
    monotone in the direction the counts were, and if `tails.clopper_pearson_upper` ever inverts a tail
    out of order (the `binom_cdf` underflow this project has already fixed once, which produced an
    upper bound below its own observed rate) the two disagree and the run raises `ArithmeticError`
    instead of publishing a level that bounds nothing. `tests/test_severity.py` shows the guard fire by
    patching the inversion, and `>`-versus-`>=` drifts in the search itself land here too.
    """
    feasible = [i for i, b in enumerate(bounds) if b <= alpha]
    if not feasible:
        return None
    want = feasible[0] if pick == "first" else feasible[-1]
    lo, hi = 0, len(bounds) - 1
    if pick == "first":
        while lo < hi:
            mid = (lo + hi) // 2
            if bounds[mid] <= alpha:
                hi = mid
            else:
                lo = mid + 1
    else:
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if bounds[mid] <= alpha:
                lo = mid
            else:
                hi = mid - 1
    if lo != want:
        raise ArithmeticError(
            "the severity search landed on candidate %d while a scan of the same canonical bounds "
            "found the %s feasible one at %d; the bounds are not monotone in the count even though "
            "the counts are monotone in the candidate, which is an inversion drift in "
            "tails.clopper_pearson_upper and not a property of the data" % (lo, pick, want))
    return lo


def _intake(records: Sequence, alpha: float, delta: float, direction: str, seed: int) -> dict:
    """Everything the search needs, validated once, in the order a reader can check.

    Usage errors first (a budget that is not a level, a direction that is not in the closed set, a
    population with no `score` record, a population that spans more than one rubric width or more than
    one backend), then the mechanical refusals (`no_gold_labels`, `n_below_min`) that belong inside a
    certificate. The rubric-width guard is this gate's own addition: the candidate domain ``0..k-1``
    and "the degenerate end of the family" are facts about ONE rubric, and a population that presents
    two widths has no single top level to be pushed into -- so it is a mistake about what was certified
    rather than a result about a task.
    """
    batch = list(records)
    if direction not in DIRECTIONS:
        raise ValueError("unknown direction %r; this gate knows %s, and `both_sides_sum` is refused "
                         "by its own measured curve because it is not monotone in the level"
                         % (direction, ", ".join(DIRECTIONS)))
    eligible = [r for r in batch if r.qtype == SUBJECT]
    if batch and not eligible:
        raise ValueError(
            "the severity gate certifies qtype=%r records and this population carries %s; a level is "
            "an ordinal position, so `1{Y > a}` is not defined on a nominal ballot and a certificate "
            "over the wrong subject is a permission for a decision nobody calibrated"
            % (SUBJECT, sorted({r.qtype for r in batch})))
    widths = sorted({len(r.options) for r in eligible})
    if len(widths) > 1:
        raise ValueError(
            "a severity certificate is stated over one rubric and this population presents %d widths "
            "(%s): the candidate domain is 0..k-1 and the degenerate end of the family is k-1, so with "
            "more than one rubric there is no single level to certify"
            % (len(widths), widths))
    cal, ev, dropped = split_cal(batch, seed)
    subjects = {r.backend for r in cal + ev}
    if len(subjects) > 1:
        raise ValueError("a certificate names one subject; this population spans backends %s -- "
                         "certify one backend at a time" % ", ".join(sorted(subjects)))
    backend = subjects.pop() if len(subjects) == 1 else None
    meta = {**dropped, "seed": seed, "alpha": alpha, "delta": delta,
            "direction": direction, "total_labelled": len(cal) + len(ev),
            "eval_ids": sorted(r.id for r in ev), "cal_ids": sorted(r.id for r in cal)}
    return {"batch": batch, "cal": cal, "ev": ev, "dropped": dropped, "backend": backend,
            "meta": meta, "k": widths[0] if widths else 0, "cal_cases": _cases(cal),
            "ev_cases": _cases(ev), "seed": seed}


def _refused(reason: Reason, run: dict, alpha: float, delta: float, direction: str, detail: str,
             meta: Optional[dict] = None) -> "SeverityCertificate":
    return SeverityCertificate.refused(reason, alpha=alpha, delta=delta, direction=direction,
                                       n_cal=len(run["cal"]), n_eval=len(run["ev"]), detail=detail,
                                       meta=meta or run["meta"], backend=run["backend"])


def certify_severity(records: Sequence, alpha: float = 0.05, delta: float = 0.05,
                     direction: str = "under", seed: int = 0) -> "SeverityCertificate":
    """Certify ``P(Y > ahat(X)) <= alpha`` (or the over-call mirror) at confidence ``1 - delta``.

    The search is §6.2's; the unit is the CASE; the operating point is a calibration-half fact, chosen
    at the requested budgets and never swept on the evaluation half (R-28, which the set gates carry in
    the same words). `alpha` is a RISK TARGET and `delta` is the level each published bound is tested
    at -- the two are not the same kind of number, and this gate's `alpha` is not the set shape's
    `alpha`, which also fixes which order statistic its threshold is.

    Raises `ValueError` (exit 2) for a budget outside (0,1) or not a number, an unknown direction, a
    population with no `score` record, more than one rubric width, or more than one backend. Returns a
    refusal for a population with no labels (`no_gold_labels`), a half below the shipped minima or too
    short for any bound in the family to meet the target (`n_below_min`), and nothing else: the family
    always contains a candidate that never errs, so the only way to refuse a well-formed severity run
    is the sample.

    The `0.05`s in this signature are LIBRARY DEFAULTS, for a caller who has not chosen a budget, and the
    published path never consults them: `autorate severity` passes `alpha`, `delta` and `seed` explicitly
    from `certificate.PUBLISHED_RUBRIC`'s own names (and, under `--protocol`, from the freeze), so the
    numbers a certificate publishes have one owner even though this signature carries a second copy. That
    is the half of #62 this file could finish: `protocol.RUBRIC_SCOPE` states in the frozen document itself
    that these defaults live outside the published rubric's fence, and
    `test_the_published_path_never_consults_the_library_defaults` moves them to prove the published
    artefact does not move with them. `certificate.PUBLISHED_RUBRIC["alpha"]` is the set gate's coverage
    level and this gate's RISK TARGET -- one value, two kinds of promise, and every severity envelope says
    which one it is measured against.
    """
    alpha = _budget("alpha", alpha)
    delta = _budget("delta", delta)
    run = _intake(records, alpha, delta, direction, seed)
    k, cal_cases, ev_cases = run["k"], run["cal_cases"], run["ev_cases"]
    n_case, n_ev_case = len(cal_cases), len(ev_cases)
    if not (run["cal"] or run["ev"]):
        return _refused(Reason.NO_GOLD_LABELS, run, alpha, delta, direction,
                        "no labelled %s records to calibrate on" % SUBJECT)
    if len(run["cal"]) < MIN_CAL or len(run["ev"]) < MIN_EVAL:
        return _refused(Reason.N_BELOW_MIN, run, alpha, delta, direction,
                        "need %d/%d records, have %d/%d" % (MIN_CAL, MIN_EVAL, len(run["cal"]),
                                                            len(run["ev"])))
    counts = [_case_count(cal_cases, a, lambda r, a: _loss(r, a, direction)) for a in range(k)]
    _require_monotone(counts, direction, n_case)
    bounds = _bounds(counts, n_case, delta)
    index = _search(bounds, alpha, _PICK[direction])
    if index is None:
        best = min(bounds)
        return _refused(
            Reason.N_BELOW_MIN, run, alpha, delta, direction,
            "no level in the %d-candidate family meets the risk target alpha=%.3f: the tightest bound "
            "these %d calibration cases can state is %.6f (at candidate %d, %d of %d cases violating), "
            "and a rule that never errs is still bounded only by 1 - delta**(1/n) = %.6f, so the "
            "sample is short and the task is not on trial" % (
                k, alpha, n_case, best, bounds.index(best), counts[bounds.index(best)], n_case, best),
            meta={**run["meta"], "family_floor_bound": best, "n_cal_cases": n_case})
    ahat = index
    bound = bounds[ahat]
    price_cases = _case_count(cal_cases, ahat, lambda r, a: _price(r, a, direction))
    override_cases = _case_count(cal_cases, ahat, lambda r, a: _override(r, a, direction))
    price_bound = canonicalise_bound(clopper_pearson_upper(price_cases, n_case, delta))
    override_bound = canonicalise_bound(clopper_pearson_upper(override_cases, n_case, delta))
    measured_cases = _case_count(ev_cases, ahat, lambda r, a: _loss(r, a, direction))
    measured = measured_cases / n_ev_case
    degenerate = (direction == "under" and ahat == k - 1) or (direction == "over" and ahat == 0)
    envelope = _BASE_ENVELOPE + (
        "rule: report %s; the guarantee is %s <= alpha=%.3f, measured on %d evaluation cases as "
        "%.6f (%d violating), which is the empirical check G1 asks for and not the bound" % (
            "max(modal level, ahat)" if direction == "under" else
            ("min(modal level, ahat)" if direction == "over" else "the constant ahat"),
            _SIDE[direction], alpha, n_ev_case, measured, measured_cases),
        "the risk target alpha=%.3f is a RISK, not a confidence: every bound here is tested at "
        "delta=%.3f on %d calibration cases, and no grid was swept on the evaluation half" % (
            alpha, delta, n_case),
        "finite-sample: bounds on CASES -- %d calibration cases over %d records, %d evaluation cases "
        "over %d records; %d claims at delta=%.3f, joint level %.2f by the rule: %s" % (
            n_case, len(run["cal"]), n_ev_case, len(run["ev"]), SEVERITY_N_CLAIMS, delta,
            _severity_level(delta), JOINT_LEVEL_RULE),
        "the price of the rule is stated beside it, not inside it: %s <= %.6f at the same ahat, and "
        "the rule replaces the model's own level on <= %.6f of cases; both are separate claims at the "
        "same delta, which is why they are counted in the joint level" % (
            _OTHER_SIDE[direction], price_bound, override_bound),
        "prior art: Dey, Merugu and Kaveri (NeurIPS 2023) and Zhang et al. (AAAI-26) own the ordinal "
        "set construction, and Xu, Guo and Wei (UAI 2023, PMLR 216:2346-2355) control two "
        "ordinal-specific losses; the delta here is the automation rule and the one-sided statement",
    )
    if degenerate:
        envelope = envelope + (
            "the certified level is the %s of the rubric, so the rule reports a constant answer and "
            "reads no ballot: the guarantee is true and is a statement about this task's severity "
            "distribution, not about the model's judgement -- %d of %d calibration cases have their "
            "own level replaced by it" % (
                "top" if direction == "under" else "bottom", override_cases, n_case),)
    if direction == "both_sides_sum":
        envelope = envelope + (
            "this is the naive two-sided loss of spec 6.1, published as a comparison only: it bounds "
            "P(Y != ahat(X)), which is not a one-sided severity guarantee in either direction",)
    # #113: `n_cal_cases` and `n_eval_cases` are the two denominators this certificate divides by, and in the
    # published population they are EQUAL -- so a reader (or a guard) that only has the numbers cannot tell
    # which one a given figure used, and an assertion written on the bytes passes for either reading. The note
    # therefore names the key per figure group, and says outright that the equality is why the note, not the
    # numbers, carries it. `tests/test_severity_surface.py` reads `certify_severity`'s own operands to check
    # the names match the arithmetic.
    unit_note = ("%d calibration records over %d distinct cases: `bound`, `price_bound` and `override_bound` "
                 "divide by `n_cal_cases` (the calibration split's case count); `measured_violation` divides "
                 "by `n_eval_cases` (the evaluation split's case count)" % (len(run["cal"]), n_case))
    if n_case == n_ev_case:
        unit_note += ("; both are %d in this population, so which denominator a figure uses is stated here "
                      "rather than left to be inferred from two counts that happen to agree" % n_case)
    return SeverityCertificate(
        feasible=True, reason=None, direction=direction, alpha=alpha, delta=delta,
        backend=run["backend"], ahat=ahat, bound=bound, price_bound=price_bound,
        override_bound=override_bound, measured_violation=measured,
        n_cal=len(run["cal"]), n_eval=len(run["ev"]), envelope=envelope,
        meta={**run["meta"], "candidate_domain": list(range(k)), "rubric_levels": k,
              "n_cal_cases": n_case, "n_eval_cases": n_ev_case, "violating_cases": counts[ahat],
              "price_cases": price_cases, "override_cases": override_cases,
              "eval_violating_cases": measured_cases, "degenerate_end": degenerate,
              "rule": JOINT_LEVEL_RULE,
              "unit_note": unit_note},
    )


def severity_band(records: Sequence, alpha: float = 0.05, delta: float = 0.05, seed: int = 0,
                  direction: str = "under") -> Optional[int]:
    """The smallest integer radius around what the MODEL reports whose one-sided risk meets `alpha`.

    Read as "the truth is never more than this many levels above (or below) what the model said, at
    this confidence" -- §6.3's sentence, on one side and anchored at the model's own level rather than
    at the certified floor. The anchor is the deliberate choice: around `ahat` the one-sided radius is
    structurally 0 whenever the severity certificate is feasible, and a function that can only return 0
    is a decoration, not a radius.

    Returns `None` when no radius in the rubric meets the budget. That state is the sample, not the
    task, and it is carried by the certificate that names it (`certify_severity` refuses with
    `n_below_min` and its bound); a bare integer function does not get to invent a second refusal
    channel (R-92b: no new labels).
    """
    alpha = _budget("alpha", alpha)
    delta = _budget("delta", delta)
    if direction == "both_sides_sum":
        raise ValueError(
            "severity_band is one-sided by definition: direction=%r sums both sides, which is the "
            "loss spec 6.1 refuses as not monotone, so it has no radius to report" % (direction,))
    run = _intake(records, alpha, delta, direction, seed)
    k, cal_cases = run["k"], run["cal_cases"]
    n_case = len(cal_cases)
    if n_case == 0:
        return None

    def radius(record, r: int) -> bool:
        gold, modal = record.gold_index, mode_index(record.probs)
        return gold > modal + r if direction == "under" else gold < modal - r

    counts = [_case_count(cal_cases, r, radius) for r in range(k)]
    _require_monotone(counts, direction, n_case)
    index = _search(_bounds(counts, n_case, delta), alpha, "first")
    return index


def over_call_bound(records: Sequence, alpha: float = 0.05, delta: float = 0.05,
                    seed: int = 0) -> "SeverityCertificate":
    """§6.2's symmetric direction: certify ``P(Y < ahat(X)) <= alpha`` with the clip rule.

    Deliberately a name and not a mechanism -- it returns exactly what `certify_severity` returns for
    ``direction="over"``, and `tests/test_severity.py` asserts the two objects are equal, so "the
    over-call side is the same search" is a checked property rather than a comment. §6.1's rule is the
    reason it is a second certificate and not one two-sided certificate: two one-sided risks, each
    certified separately and both reported.
    """
    return certify_severity(records, alpha=alpha, delta=delta, direction="over", seed=seed)


def tolerance_band(records: Sequence, alpha: float = 0.05, delta: float = 0.05,
                   seed: int = 0) -> dict:
    """The smallest integer `d` with ``P(|Y - ahat(X)| > d) <= alpha`` (spec §6.3), as a dict.

    "Given â" is this module's own under-direction certificate at the same `alpha`, `delta` and `seed`,
    so the band and the severity guarantee are computed on one split of one population and cannot
    describe different halves. `d` indexes a monotone family (the indicator ``|Y - ahat(X)| > d`` falls
    as `d` rises), so the search is the same shape as §6.2's and this function adds no machinery: the
    same `_cases`, `_require_monotone`, `_bounds` and `_search`, over the same
    `tails.clopper_pearson_upper` that every other bound in the repository comes from -- and
    `tests/test_severity.py` proves the equality against a linear scan derived in the test, because a
    `>` written as a `>=` moves `d` by one level and nothing else here would notice.

    It publishes ONE bound, so it states ``n_claims = 1`` and its joint level is 0.95 under the same
    `correction.joint_level` call the severity certificate uses; R-160's 0.85-versus-0.90 question is
    an envelope count, and every artefact that prints a confidence prints the count with it.

    Refusals carry no `d` and no `bound`, exactly as `Certificate` refuses headline numbers on a
    refusal. A band of `k - 1` -- the whole rubric -- is refused with
    `Reason.NO_AUTOMATION_AT_COVERAGE` rather than published, because it contains every level whatever
    the data said and no further data shrinks it; that is the first emission of that reason by any
    gate, and `tests/test_severity.py` shows it survives a ten-fold increase in cases while a
    `n_below_min` refusal does not.
    """
    alpha = _budget("alpha", alpha)
    delta = _budget("delta", delta)
    cert = certify_severity(records, alpha=alpha, delta=delta, direction="under", seed=seed)
    if not cert.feasible:
        return {"feasible": False, "reason": cert.reason, "alpha": alpha, "delta": delta,
                "seed": seed, "direction": "under", "n_cal": cert.n_cal, "n_eval": cert.n_eval,
                "n_cal_cases": cert.meta.get("n_cal_cases"),
                "n_eval_cases": cert.meta.get("n_eval_cases"),
                "rubric_levels": cert.meta.get("rubric_levels"),
                "detail": "the severity certificate this band is anchored on refused: %s"
                          % cert.meta["detail"],
                "envelope": cert.envelope}
    run = _intake(records, alpha, delta, "under", seed)
    k, cal_cases, ev_cases = run["k"], run["cal_cases"], run["ev_cases"]
    n_case, n_ev_case = len(cal_cases), len(ev_cases)
    ahat = cert.ahat

    def miss(record, d: int) -> bool:
        return abs(record.gold_index - report_level(record.probs, ahat)) > d

    counts = [_case_count(cal_cases, d, miss) for d in range(k)]
    _require_monotone(counts, "under", n_case)
    bounds = _bounds(counts, n_case, delta)
    d = _search(bounds, alpha, "first")
    missing_cases = counts[0]
    if d is None:
        best = min(bounds)
        return _band_refusal(
            Reason.N_BELOW_MIN, alpha, delta, seed, ahat, k, run, n_case, n_ev_case, missing_cases,
            "no band in the %d-candidate family meets the target alpha=%.3f: the tightest bound these "
            "%d calibration cases can state is %.6f, so the sample is short and not the task" % (
                k, alpha, n_case, best))
    if d == k - 1:
        return _band_refusal(
            Reason.NO_AUTOMATION_AT_COVERAGE, alpha, delta, seed, ahat, k, run, n_case, n_ev_case,
            missing_cases,
            "the smallest band the budget licenses is the whole rubric: at ahat=%d, %d of %d "
            "calibration cases sit the maximum %d levels away, whose exact upper bound %.6f is above "
            "alpha=%.3f, so d=%d -- `the answer is off by at most the rubric' -- contains every level "
            "whatever the data said and automates nothing. More data would not change this verdict: "
            "the obstruction is the mass at maximal error, not 1 - delta**(1/n)" % (
                ahat, counts[k - 2], n_case, k - 1, bounds[k - 2], alpha, k - 1))
    bound = bounds[d]
    measured_cases = _case_count(ev_cases, d, miss)
    return {
        "feasible": True, "d": d, "bound": bound, "ahat": ahat, "alpha": alpha, "delta": delta,
        "seed": seed, "direction": "under", "rubric_levels": k,
        "violating_cases": counts[d], "missing_cases": missing_cases,
        "exact_cases": n_case - missing_cases,
        "n_cal": len(run["cal"]), "n_eval": len(run["ev"]),
        "n_cal_cases": n_case, "n_eval_cases": n_ev_case,
        "measured_violation": measured_cases / n_ev_case,
        "n_claims": 1, "level": joint_level({"alpha": delta, "beta": delta}, n_groups=1, n_claims=1),
        "envelope": _BASE_ENVELOPE + (
            "rule: |Y - ahat(X)| > d, with ahat(X) = max(modal level, %d) from the under-direction "
            "certificate at the same alpha/delta/seed; the band is the smallest d whose exact "
            "one-sided upper bound on %d calibration CASES is <= alpha=%.3f, and the search is the "
            "same monotone-family search as spec 6.2 with no machinery of its own" % (
                ahat, n_case, alpha),
            "%d of %d calibration cases are not exact at the certified rule, which is why d is %d and "
            "not 0: d = 0 claims exactness except on at most alpha of cases" % (
                missing_cases, n_case, d),
            "%d claim at delta=%.3f, joint level %.2f by the rule: %s" % (
                1, delta, joint_level({"alpha": delta, "beta": delta}, 1, 1), JOINT_LEVEL_RULE),
        ),
        "detail": "the answer is never off by more than %d level(s) at confidence %.2f" % (
            d, joint_level({"alpha": delta, "beta": delta}, 1, 1)),
    }


def _band_refusal(reason: Reason, alpha: float, delta: float, seed: int, ahat: int, k: int, run: dict,
                  n_case: int, n_ev_case: int, missing_cases: int, detail: str) -> dict:
    """A band refusal: the budgets, the counts, and no number a reader could automate on."""
    return {"feasible": False, "reason": reason.value, "alpha": alpha, "delta": delta, "seed": seed,
            "direction": "under", "ahat": ahat, "rubric_levels": k, "n_cal": len(run["cal"]),
            "n_eval": len(run["ev"]), "n_cal_cases": n_case, "n_eval_cases": n_ev_case,
            "missing_cases": missing_cases, "detail": detail, "envelope": _BASE_ENVELOPE + (
                "no band is published, so no tolerance travels with any answer",
                "the refusal names %r: %s" % (reason.value, _REASON_MEANING[reason]),)}


# The refusal text an operator reads, in the words the closed set uses for each finding. `Reason` owns
# the difference between them; this only restates it where a band reader will look.
_REASON_MEANING = {
    Reason.N_BELOW_MIN: "the sample is short -- a bigger calibration half would state a bound",
    Reason.NO_AUTOMATION_AT_COVERAGE: "the task is not automatable at these budgets, and more data "
                                      "would not change that verdict",
}


# The shape a serialized severity certificate is written in, declared beside the fields it describes.
#
# It is NOT `certificate.SHAPE_VERSION` (2), and reusing that number would be a false statement about the
# artefact rather than a convenience: a shape tag says which field set the bytes are in, and two shapes
# sharing one tag is a tag that cannot fail. `certificate.py:329`'s loader diffs the top-level field names
# of `Certificate`, so a severity document handed to it would come back as
# `unknown ['ahat', 'direction', 'price_bound', ...]` -- and `certificate`'s version stayed at 2 when
# `meta.protocol_digest` landed, because a key added INSIDE `meta` is not a top-level shape change (Plan D
# Task 2's ruling). The same rule reads back here: nothing in this task adds a top-level field, so the
# severity shape stays 1.
#
# The KEY is shared with `certificate.SHAPE_KEY` on purpose: one spelling of "which shape am I" across the
# two shapes is what lets a reader tell them apart, and two spellings of the same question is how a
# document ends up answering neither.
SEVERITY_SHAPE_VERSION = 1
SEVERITY_SHAPE_KEY = SHAPE_KEY


@dataclass(frozen=True)
class SeverityCertificate:
    """A one-sided guarantee, the budgets it was made at, and the conditions that void it (spec 10).

    A sibling of `Certificate`, not an instance of it: the set shape's fields are a coverage quantile,
    a set size and a conditional error rate, and none of them is what is measured here -- a
    `Certificate` forced to hold this would have to put an integer level in `qhat` and a one-sided risk
    in a slot named for membership. The invariants that ARE shared are carried by choice: a non-empty
    envelope, a reason from the closed set, no headline numbers on a refusal, and a joint level derived
    from `delta` rather than stored beside it.
    """

    feasible: bool
    reason: Optional[str]
    direction: str
    alpha: float
    delta: float
    backend: Optional[str]
    ahat: Optional[int]
    bound: Optional[float]
    price_bound: Optional[float]
    override_bound: Optional[float]
    measured_violation: Optional[float]
    n_cal: int
    n_eval: int
    envelope: tuple = ()
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        # The type arms come first, and they are not decoration: every one of the comparisons below is
        # `0.0 <= value <= 1.0` or `bound > alpha`, and a JSON string in a numeric slot answers them with a
        # `TypeError`. `cli.main` maps no `TypeError` to an exit code, so a tampered or foreign artefact
        # would leave the documented 0/2/3/4 contract at rc 1 -- the exact defect Plan D Task 2 found four
        # times on subscripted reads of a frozen `Protocol`, arriving here through the contents rather than
        # through the call shape. Refusing by name is also what makes the loader's "unknown shape"
        # statement true for a document that has the right keys and the wrong types.
        if isinstance(self.envelope, (str, bytes)) or not isinstance(self.envelope, (list, tuple)):
            raise SeverityShapeMismatch("envelope must be a list of assumption lines, got %s (%r)"
                                        % (type(self.envelope).__name__, self.envelope))
        if any(not isinstance(line, str) or not line for line in self.envelope):
            raise SeverityShapeMismatch("every envelope line must be a non-empty string; found %r"
                                        % (self.envelope,))
        if not isinstance(self.meta, dict):
            raise SeverityShapeMismatch("meta must be a mapping of the run's own counters, got %s"
                                        % type(self.meta).__name__)
        # The budgets, too: `bound > alpha` below and `correction.joint_level` behind `level` are both
        # arithmetic on them, and `certify_severity` validates them through `_budget` before it constructs
        # anything. A document that skipped that door must not be allowed to answer with a `TypeError`.
        for name in ("alpha", "delta"):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not 0.0 < value < 1.0):
                raise SeverityShapeMismatch("%s must be a number in (0,1), got %r (%s)"
                                            % (name, value, type(value).__name__))
        object.__setattr__(self, "envelope", tuple(self.envelope))
        object.__setattr__(self, "meta", dict(self.meta))
        if not self.envelope:
            raise SeverityShapeMismatch("every certificate needs a non-empty envelope of assumptions")
        if self.direction not in DIRECTIONS:
            raise SeverityShapeMismatch("unknown direction %r; this certificate can only name %s"
                                        % (self.direction, ", ".join(DIRECTIONS)))
        headline = ("ahat", "bound", "price_bound", "override_bound", "measured_violation")
        if self.feasible:
            if self.reason is not None:
                raise SeverityShapeMismatch("a feasible certificate cannot carry a refusal reason")
            missing = [f for f in headline if getattr(self, f) is None]
            if missing:
                raise SeverityShapeMismatch("a feasible severity certificate must carry %s"
                                            % ", ".join(missing))
            if isinstance(self.ahat, bool) or not isinstance(self.ahat, int) or not 0 <= self.ahat:
                raise SeverityShapeMismatch("a reported level indexes the rubric and must be an int: %r"
                                            % (self.ahat,))
            for name in ("bound", "price_bound", "override_bound"):
                value = getattr(self, name)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not 0.0 <= value <= 1.0):
                    raise SeverityShapeMismatch("%s is a probability: %r" % (name, value))
            if self.bound > self.alpha:
                raise SeverityShapeMismatch(
                    "a severity certificate cannot publish a bound above its own risk target: "
                    "bound=%r > alpha=%r -- the feasibility test and the published number must be the "
                    "same canonical value" % (self.bound, self.alpha))
            measured = self.measured_violation
            if (isinstance(measured, bool) or not isinstance(measured, (int, float))
                    or not 0.0 <= measured <= 1.0):
                raise SeverityShapeMismatch("measured_violation is a fraction of evaluated cases: %r"
                                            % (measured,))
        else:
            if self.reason is None:
                raise SeverityShapeMismatch("a refusal must name its reason")
            if self.reason not in {r.value for r in Reason}:
                raise SeverityShapeMismatch("unknown reason %r" % (self.reason,))
            carried = [f for f in headline if getattr(self, f) is not None]
            if carried:
                raise SeverityShapeMismatch("a refusal cannot carry headline numbers: %s"
                                            % ", ".join(carried))
            if not self.meta.get("detail"):
                raise SeverityShapeMismatch("a refusal must say what refused, in the artefact")

    @property
    def level(self) -> float:
        """The joint confidence of the bounds this certificate actually publishes.

        Derived, and derived by the one owner of the simultaneous arithmetic (R-160): the severity gate
        does not restate `1 - n * delta`, it calls `correction.joint_level` with its own envelope count
        and both budgets equal to `delta`, which is what makes its number agree with the set shape's
        instead of merely looking the same. The envelope that states the claim count asks the same
        function (`_severity_level`), so no printed level in this artefact has a second producer.
        """
        return _severity_level(self.delta)

    @classmethod
    def refused(cls, reason: Reason, alpha: float, delta: float, direction: str, n_cal: int,
                n_eval: int, detail: str, meta: Optional[dict] = None,
                backend: Optional[str] = None) -> "SeverityCertificate":
        return cls(feasible=False, reason=reason.value, direction=direction, alpha=alpha,
                   delta=delta, backend=backend, ahat=None, bound=None, price_bound=None,
                   override_bound=None, measured_violation=None, n_cal=n_cal, n_eval=n_eval,
                   envelope=_BASE_ENVELOPE + ("no certificate exists, so no action is certified",),
                   meta={"detail": detail, **(meta or {})})

    def to_dict(self) -> dict:
        """The artefact as JSON-ready data, with the shape tag written here and nowhere else.

        `certificate.py`'s precedent: the tag is a property of the SERIALIZED shape, not a field of the
        object, so no caller of `SeverityCertificate` carries it and it cannot become a second owner of
        anything the object already holds. A producer and its bytes therefore cannot disagree about which
        shape they are in.
        """
        d = asdict(self)
        d["envelope"] = list(self.envelope)
        d[SEVERITY_SHAPE_KEY] = SEVERITY_SHAPE_VERSION
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "SeverityCertificate":
        """Read a stored severity certificate, naming the shape it found before anything else.

        Four arms, in this order, each with its own statement:
        the OBJECT (a JSON array or scalar is not this shape, and reading a key off it would answer with an
        `AttributeError` no exit-code arm maps); the SHAPE (a tag that is not this build's severity shape,
        including a set certificate's tag -- the two shapes refuse each other, and a field diff would have
        said `unknown ['ahat', ...]` about what is really a version); the FIELD NAMES (unknown or missing --
        and every field is required, because `to_dict` writes all of them, so an artefact missing `envelope`
        or `meta` is incomplete rather than old); and the slots this function reads before the dataclass can
        check them (`n_cal`, `n_eval`, `backend`, `envelope`), each refused by name. What is left goes to the
        shape's own invariants, which `__post_init__` polices -- the probability and level slots, where a
        string used to answer a comparison with `TypeError` and rc 1.

        Every refusal is a `SeverityShapeMismatch`, which is a `ValueError`: `load_published` answers it
        with the named refusal at exit 4 for a table-declared artefact. Neither reading may be silent, and
        neither may escape the documented 0/2/3/4 contract -- the four slots guarded by hand here are exactly
        where it escaped, and `test_a_published_severity_artefact_with_a_wrongly_typed_slot_refuses_at_four_not_one`
        walks each through `main(["verify"])`.
        """
        from dataclasses import fields

        if not isinstance(d, dict):
            # `.get` is the first thing this function does, so a document that is a JSON array answered with
            # an `AttributeError` no exit-code arm maps -- rc 1 on a path whose whole contract is 0/2/3/4.
            raise SeverityShapeMismatch(
                "stored severity certificate is a JSON %s, not an object: this shape is one mapping of the "
                "certificate's fields -- regenerate it with `autorate severity`"
                % ("array" if isinstance(d, list) else type(d).__name__))
        found = d.get(SEVERITY_SHAPE_KEY)
        if found != SEVERITY_SHAPE_VERSION:
            named = (repr(found) if SEVERITY_SHAPE_KEY in d else
                     "none (no %r key at all: a certificate written before severity shape %d existed)"
                     % (SEVERITY_SHAPE_KEY, SEVERITY_SHAPE_VERSION))
            # The one foreign shape this repository actually publishes is the set certificate, and a reader
            # who is handed one deserves its name rather than a version number: `certificate.SHAPE_VERSION`
            # is 2 and belongs to a different field set.
            foreign = (set(d) & {"qhat", "autorate", "mean_set_size", "beta", "method"})
            raise SeverityShapeMismatch(
                "stored certificate is not in the severity shape this build reads: found shape %s, "
                "required severity shape %d%s -- regenerate it with `autorate severity`"
                % (named, SEVERITY_SHAPE_VERSION,
                   ", which is the shape of a SET certificate (it carries %s)"
                   % ", ".join(sorted(foreign)) if foreign else ""))
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - names - {SEVERITY_SHAPE_KEY})
        # Every field is required, including the two that carry a dataclass default: `to_dict` writes all of
        # them, so an artefact missing `envelope` or `meta` is not an older certificate, it is an incomplete
        # one -- and reading it with the default substituted made `d["envelope"]` below raise `KeyError`, an
        # exception no exit-code arm maps. The rc 1 escaped through the door that is supposed to name the
        # artefact at rc 4.
        missing = sorted(names - set(d))
        if unknown or missing:
            raise SeverityShapeMismatch(
                "stored certificate does not match the severity certificate shape: unknown %s, "
                "missing %s -- regenerate it with `autorate severity`" % (unknown, missing))
        # The slots whose wrong type answers with an exception rather than a refusal, checked before anything
        # reads them: the summary formats `n_cal`/`n_eval` with `%d`, and `verify` looks the records up by
        # `stored.backend`, so a list there is `TypeError: unhashable type`. `bool` is an `int` subclass and a
        # case count is never a flag, so it is refused beside the strings and the nulls.
        counts = sorted(name for name in ("n_cal", "n_eval")
                        if not isinstance(d[name], int) or isinstance(d[name], bool))
        if counts:
            raise SeverityShapeMismatch(
                "severity certificate's %s must be an integer case count, found %s -- regenerate it with "
                "`autorate severity`" % (", ".join(counts), [repr(d[n]) for n in counts]))
        if not isinstance(d["backend"], str):
            raise SeverityShapeMismatch(
                "severity certificate's `backend` must be a backend name, found %r -- regenerate it with "
                "`autorate severity`" % (d["backend"],))
        if not isinstance(d["envelope"], list) or not all(isinstance(line, str) for line in d["envelope"]):
            raise SeverityShapeMismatch(
                "severity certificate's `envelope` must be a list of assumption lines, found %s -- "
                "regenerate it with `autorate severity`" % (type(d["envelope"]).__name__,))
        kw = dict(d)
        kw.pop(SEVERITY_SHAPE_KEY)
        kw["envelope"] = tuple(d["envelope"])
        return cls(**kw)

    def summary(self) -> str:
        side = _SIDE[self.direction]
        if self.feasible:
            return ("%s severity certificate, direction=%s: %s <= %.6f at ahat=%s, tested at "
                    "delta=%.3f on %d calibration cases (alpha=%.3f is the risk target, not a "
                    "confidence); the price is %s <= %.6f at the same rule and the rule replaces the "
                    "model's own level on <= %.6f of cases; measured on %d held-out cases: %.6f; "
                    "joint level %.2f over %d claims at delta=%.3f; n_cal=%d n_eval=%d; "
                    "synthetic ordinal data with known answers (the offline archive carries no `score` "
                    "answers), and the construction is prior art -- Dey et al. NeurIPS 2023, Zhang et "
                    "al. AAAI-26, Xu-Guo-Wei UAI 2023 (PMLR 216:2346-2355), ours being %s"
                    % (_KIND[self.direction], self.direction, side, self.bound, self.ahat, self.delta,
                       self.meta.get("n_cal_cases", -1), self.alpha, _OTHER_SIDE[self.direction],
                       self.price_bound, self.override_bound,
                       self.meta.get("n_eval_cases", -1), self.measured_violation, self.level,
                       SEVERITY_N_CLAIMS, self.delta, self.n_cal, self.n_eval,
                       _DELTA_CLAIM[self.direction]))
        return ("NOT_CERTIFIABLE: reason=%s for direction=%s at alpha=%.3f, delta=%.3f; n_cal=%d "
                "n_eval=%d; %s" % (self.reason, self.direction, self.alpha, self.delta, self.n_cal,
                                   self.n_eval, self.meta.get("detail", "")))
