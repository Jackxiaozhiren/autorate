"""Drift: two ways to relax the exchangeability assumption, and the envelope each one pays for.

Spec §8.2 names two modes for a regime that may move. This module implements both and refuses to
let either read as immunity. The project's posture is to **declare its envelope**: a certificate
states the condition it was measured under, and where that condition is an assumption the assumption
is printed instead of being quietly relied on. Three things live here for that reason and not for
algorithmic reasons:

* `weighted_quantile` (mode 1) trades the marginal assumption for a DECLARED density ratio. The
  weights are not estimated here and cannot be: an estimated ratio would be a second assumption
  wearing the clothing of a measurement. Unit weights reproduce `conformal.split_quantile` bit for
  bit, including the vacuity flag, because a generalisation that does not reduce to its special
  case is a second owner of that special case's number. WHAT MODE 1 DOES NOT BUY: a finite-sample
  bound. The correction this module applies is the `+1` of the EXCHANGEABLE case, and under a
  non-unit declaration the weighted-conformal denominator is `sum(w) + w_{n+1}`, where `w_{n+1}` is
  the test point's own weight -- drawn from the target regime, so unknown at calibration time. With
  an exactly declared ratio the shipped threshold therefore under-covers: measured 0.0933 realised
  miscoverage at n=100 against nominal 0.05 (seed 20261008, 4000 trials x 2000 test points, 3SE
  0.0040), 0.1411 at n=25. `WEIGHTED_ENVELOPE` says this; a certificate stamped with mode 1 states
  a re-weighted estimate, not a bound.
* `aci_threshold` (mode 2) trades the finite-sample statement itself for an adaptive threshold. Its
  published guarantee WAS a bound on the long-run regret of the average miscoverage rate, in the
  form `|mean err - alpha| <= aci_regret_bound(T, alpha, gamma)`. That inequality is FALSE on inputs
  this module's own validator accepts, and it is therefore withdrawn rather than defended: at
  alpha=gamma=0.05 an all-1.0 sequence -- the module's own `SCORE_CEILING`, the value its vacuous arm
  returns -- converges to a long-run error rate of 0.500250 against a bound of 0.028778, an
  alternating 0.99/0.01 ordering reaches 0.166740 against 0.027978, a constant 0.99 sequence to
  0.167100, and an all-0.0 sequence to 0.000000 (all deterministic constructions; see
  `ACI_ENVELOPE` for the mechanism and the 400-sequence sweep). What mode 2 does buy is a threshold
  that tracks the target rate while its iterate stays inside (0,1); the clip that keeps it there
  discards the update whenever it fires, and every measured violation coincides with a fired clip.
  An implementation dressed up as finite-sample would be this repository's worst failure mode, and an
  implementation dressed up as a regret theorem is the same failure wearing the other hat.
* `NOT_CERTIFIABLE_UNDER_DRIFT` is an envelope FLAG, not a return value. Any certificate that never
  conditioned on a declared drift variable is marginal-only, and marginal-only carries the flag.
  Absence of a declaration is read as marginal-only (the conservative direction); a declaration that
  is present but malformed is a `ValueError`, because "the caller tried to say something and we
  cannot parse it" is a usage problem, not a licence to pick either reading.

Like `conformal.py`, this module knows numbers and never field names: it takes score vectors, not
records. The case denominator therefore belongs to its callers, and the unit rule is stated in
`case_count.py` and `groups.py` -- three repeats of one case are one observation, so a score vector
built from rows would silently inflate the sample every bound here is computed on. Because this module
cannot see case identity, the rule used to be backed by prose only; it is now backed by an executable
arm. `tests/test_drift.py` builds 60 cases x three DISAGREEING repeats through
`tests/_records.py:choice_record(case_id=..., repeat=...)`, runs them through `weighted_quantile` and
`aci_regret_bound` on the row vector AND the case vector, and pins which number is the published one
(0.780900 versus 0.950100 for the threshold; 0.361111 versus 0.138889 for the regret expression, so a
row-denominated caller understates the price by a factor of 0.384615). `groups.group_counts` publishes
both `cases` and `records` for the same reason (`groups.py:12-17`), and a caller of this module owes
the reader the same two counts.

Exit codes (R-115, and the same discipline as every other module here): every input problem is a
`ValueError`, which `cli.main()` maps to 2; the single `ArithmeticError` site is the quantile
cross-check, which maps to 4 because it means this project's own published arithmetic contradicted
itself. Nothing here escapes as rc 1: `alpha` is checked before it reaches a denominator, `rounds`
and the weight sum are checked before any division, and no dict lookup is left to raise `KeyError`
on operator-supplied data.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Iterator, NamedTuple

# --------------------------------------------------------------------------- the envelope flag

#: The line a marginal-only certificate must carry. It names itself so a published document can be
#: grepped for it, and it refuses something in plain words: under an undeclared regime shift the
#: finite-sample bounds in that certificate are not available.
NOT_CERTIFIABLE_UNDER_DRIFT = (
    "NOT_CERTIFIABLE_UNDER_DRIFT: this certificate is marginal-only -- it never conditioned on a "
    "declared drift variable, so its finite-sample bounds hold only while the calibration regime "
    "holds and a shift in the score distribution is not bounded by anything in it"
)

#: The `Certificate.meta` key a producer states when it did condition on a drift variable. Nothing
#: in `src/` writes this key today (measured over the tree), which is the honest reason every
#: certificate in the repository currently carries the flag.
DRIFT_DECLARATION_KEY = "drift_declaration"

#: The three names a caller can put in `variable` that mean "I conditioned on nothing". A
#: declaration whose variable is one of these does not buy the exemption: a silent pass for the
#: word that describes having no condition is the exact failure this flag exists to prevent.
NON_CONDITIONING_VARIABLES = frozenset(("marginal", "none", "unconditional"))

#: The keys a declaration must state, all non-empty strings: which variable, who declared it, and
#: where the declaration comes from. `variable` alone would be a claim with no source.
DECLARATION_FIELDS = ("variable", "declared_by", "evidence")

WEIGHTED_ENVELOPE = (
    "weighted conformal (mode 1): the density weights are DECLARED by the caller and never "
    "estimated here, so the bound is only as good as that declaration",
    "assumed: the declared weights are the density ratio between the calibration regime and the "
    "regime the decision runs in; nothing in this module tests that assumption",
    "the finite-sample correction is the EXCHANGEABLE case's: the denominator adds weight 1.0 for "
    "the test point, which is exact for unit weights -- where the answer reproduces split_quantile "
    "value for value and flag for flag -- and is not the weighted-conformal correction, whose "
    "denominator is sum(w) + w_{n+1} with w_{n+1} the test point's own target-regime weight",
    "so mode 1 buys a re-weighted estimate of the target-regime quantile and NO finite-sample "
    "bound: measured on an exactly declared ratio (calibration ~ U[0,1], target density 10*s^9, "
    "E_F0[w] = 1, alpha = 0.05, seed 20261008, 4000 trials x 2000 test points), realised "
    "miscoverage is 0.0933 at n=100 (3SE 0.0040) and 0.1411 at n=25 against a nominal 0.05, with "
    "0.3058 of those n=25 trials returning the vacuous ceiling",
)

ACI_ENVELOPE = (
    "adaptive conformal inference (mode 2): what this recursion buys is a threshold that tracks the "
    "target error rate while its iterate stays inside (0,1). It is not a bound on the average "
    "miscoverage, and aci_regret_bound is not this mode's guarantee -- the inequality it used to "
    "state, |mean err - alpha| <= aci_regret_bound(T, alpha, gamma), is withdrawn below",
    "no per-round and no finite-sample statement, and no long-run regret statement either: on inputs "
    "_checked_round_scores accepts, at alpha=gamma=0.05 an all-1.0 sequence (this module's own "
    "SCORE_CEILING, the value its vacuous arm returns) converges to a long-run error rate of "
    "0.500250 against a bound of 0.028778; an alternating 0.99/0.01 ordering reaches 0.166740 "
    "against 0.027978; a constant 0.99 sequence reaches 0.167100; an all-0.0 sequence reaches "
    "0.000000 against the same formula",
    "the mechanism, stated because a withdrawal without one is a retraction and not a fix: the step "
    "is clipped to [0,1] every round and a clip DISCARDS the update, so when the target rate is not "
    "reachable on the score sequence's own atoms the recursion settles into a cycle instead of a "
    "fixed point -- period 2 at the ceiling, which is exactly the 1/2 above. Over 400 constructed "
    "sequences (seed 20261008, T=2000) no violation fired without a clip (0 of 400), while 112 of "
    "400 clipped sequences still held: the clip is necessary, not sufficient, and it is observable "
    "in the trace this function returns as step.lam in (0.0, 1.0)",
    "stated for nonconformity scores in [0,1] and alpha in (0,0.5); a certificate built on this "
    "threshold carries this line and the trace check, not the split bound",
)

#: The test point's own weight in the mode-1 correction. Read this as the EXCHANGEABLE case's
#: correction, not as the weighted-conformal one: with unit weights `sum(weights) + 1` is `n + 1`,
#: so `split_quantile` is reproduced exactly (measured, tests/test_drift.py, sizes 1..400 x 9
#: alphas). Under a NON-unit declaration the denominator of the weighted argument is
#: `sum(w) + w_{n+1}`, where `w_{n+1}` is the test point's own density ratio: a draw from the
#: target regime, so not knowable at calibration time, because the score that names it needs the
#: label. Setting it to 1.0 therefore under-corrects by O(1/n_eff), which is the whole size of the
#: correction -- hence `WEIGHTED_ENVELOPE` withdraws the finite-sample sentence instead of restating
#: it, and the measured deficit is in that line rather than hidden in a comment.
#: Restoring a finite-sample statement here needs a DECLARED test-point weight (an upper bound on
#: `w_{n+1}`, or its target-regime mean `E_F0[w^2]`) added to `DECLARATION_FIELDS`, i.e. a
#: declaration-shape change whose producer is B3 Task 5 and whose meta-versus-shape ruling is ledger
#: R-149's. That is not this round's call to make, so the shape is untouched and the text is fixed.
#: R-127: this line names its derivation -- a definition of the estimator, not a tuned constant and
#: not a precision tolerance; the two precision constants that already have owners (`tails.py`,
#: `HALF_STEP`) stay untouched.
TEST_POINT_WEIGHT = 1.0

#: The ceiling a conformal threshold cannot exceed on this project's scores, and the value the
#: vacuous arm answers with. `split_quantile` uses the same one; it is named here because
#: `weighted_quantile` refuses scores outside it rather than letting the ceiling stop being a
#: ceiling.
SCORE_CEILING = 1.0


# --------------------------------------------------------------------------------- validation

def _number(what: str, index: int, value, allow_negative: bool) -> float:
    """One element of a caller's declaration, as a finite number or as a usage refusal.

    Finiteness is checked before sign, because `nan < 0.0` is False: letting the sign arm answer
    first would report a non-finite weight as a negative one and send the reader to the wrong fix.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("a %s at index %d is not a number: %r" % (what, index, value)) from None
    if not math.isfinite(number):
        raise ValueError("non-finite %s at index %d: %r; a NaN in a declared density silently "
                         "unweights a sample instead of refusing it" % (what, index, value))
    if not allow_negative and number < 0.0:
        raise ValueError("negative %s at index %d: %r; a declared density cannot be below zero"
                         % (what, index, value))
    return number


def _checked_declaration(scores, weights) -> tuple:
    """Validate a score vector and its CALLER-DECLARED densities; return (pairs, total weight)."""
    if scores is None or isinstance(scores, (str, bytes)):
        raise ValueError("scores must be a sequence of nonconformity scores, got %r"
                         % (type(scores).__name__,))
    if weights is None:
        raise ValueError(
            "no declared density vector: weighted_quantile implements the weighted mode, whose "
            "weights are DECLARED by the caller. Pass [1.0] * len(scores) to say 'uniform' out "
            "loud; there is no default, because an omitted declaration is not a uniform one")
    if isinstance(weights, (str, bytes)):
        raise ValueError("weights must be a sequence of declared densities, not a bare string")
    scored = list(scores)
    try:
        weight_list = list(weights)
    except TypeError:
        raise ValueError("the declared density vector is not a sequence: %r"
                         % (type(weights).__name__,)) from None
    if not scored:
        raise ValueError("empty score vector: no quantile is certifiable from nothing")
    if not weight_list:
        raise ValueError(
            "the declared density vector is empty while the score vector is not: mode 1 needs a "
            "declared weight for every score")
    if len(weight_list) != len(scored):
        raise ValueError("scores/weights length mismatch: %d scores over %d declared densities"
                         % (len(scored), len(weight_list)))
    pairs = [(_number("score", i, score, True), _number("weight", i, weight, False))
             for i, (score, weight) in enumerate(zip(scored, weight_list))]
    for score, _weight in pairs:
        if not 0.0 <= score <= SCORE_CEILING:
            raise ValueError("scores are nonconformity scores bounded in [0,1] (the vacuous arm "
                             "answers with the ceiling 1.0, which is only a ceiling for a score "
                             "inside that range); got %r" % (score,))
    total = math.fsum(weight for _score, weight in pairs)
    if total <= 0.0:
        raise ValueError("the declared densities sum to zero: every sample was declared to have no "
                         "mass in the target regime, so there is no weighted quantile to take")
    return pairs, total


def _alpha_check(alpha, low: float, high: float, name: str, why: str) -> float:
    """One alpha domain check with the reason printed, shared by every entry point here."""
    try:
        value = float(alpha)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number in (%g,%g): %r" % (name, low, high, alpha)) from None
    if not (low < value < high):
        raise ValueError("%s must be in (%g,%g) -- %s -- got %r" % (name, low, high, why, alpha))
    return value


# ------------------------------------------------------------------------ mode 1: weighted

def weighted_level(scores, weights, value) -> tuple:
    """(total declared weight at or below `value`, total strictly below it).

    The definition, computed directly from the pairs the caller declared. `weighted_quantile`
    selects with a one-pass scan and then checks its choice against this, so the selection and the
    predicate that justifies it are two different computations -- the same shape as the invariant
    `tails.clopper_pearson_upper` asserts against its own bisection. It is public because a reader
    can legitimately ask what level a threshold actually buys.
    """
    pairs, _total = _checked_declaration(scores, weights)
    at_or_below = math.fsum(w for s, w in pairs if s <= float(value))
    strictly_below = math.fsum(w for s, w in pairs if s < float(value))
    return at_or_below, strictly_below


def weighted_quantile(scores, weights, alpha) -> tuple:
    """The weighted-conformal threshold at level 1 - alpha, plus the vacuity flag.

    `target = (1 - alpha) * (sum(weights) + TEST_POINT_WEIGHT)`, and the answer is the smallest
    declared score whose cumulative weight reaches it. With UNIT weights that is exactly
    `split_quantile`'s `ceil((1-alpha)(n+1))` order statistic, and the two agree value for value and
    flag for flag (pinned by tests/test_drift.py over sizes 1..400). With NON-unit weights it is NOT
    the weighted analogue of that statement: the weighted-conformal denominator is
    `sum(w) + w_{n+1}` and this module supplies `1`, so the correction is the exchangeable case's
    only. The consequence is measured, not argued -- on an exactly declared ratio the realised
    miscoverage is 0.0933 at n=100 and 0.1411 at n=25 against a nominal 0.05 (seed 20261008, 4000
    trials x 2000 test points; `WEIGHTED_ENVELOPE`), so a caller gets a re-weighted estimate of the
    target-regime quantile and must not present it as a bound.

    Scores are grouped by value before the cumulative is taken: the crossing is a property of the
    multiset of declared pairs, not of the order the caller typed them in, and a scan that walked
    insertion order would return a threshold below the level it claims. That is the anti-conservative
    direction, so it is also what the cross-check below refuses as `ArithmeticError` rather than
    returning it.

    Returns `(1.0, True)` when no declared sample reaches the level, exactly as `split_quantile`
    does. The flag is a result, not an error: the set would cover every label.
    """
    level = _alpha_check(alpha, 0.0, 1.0, "alpha", "the conformal level is a probability")
    pairs, total = _checked_declaration(scores, weights)
    target = (1.0 - level) * (total + TEST_POINT_WEIGHT)
    by_value: dict = {}
    for score, weight in pairs:
        by_value[score] = by_value.get(score, 0.0) + weight
    chosen = None
    running = 0.0
    for value in sorted(by_value):
        running += by_value[value]
        if running >= target:
            chosen = value
            break
    if chosen is None:
        return SCORE_CEILING, True
    at_or_below, strictly_below = weighted_level(scores, weights, chosen)
    if not (strictly_below < target <= at_or_below):
        raise ArithmeticError(
            "the weighted quantile %.6f does not sit on its own crossing: declared weight at or "
            "below it is %.6f and strictly below it is %.6f, while level 1-alpha=%g of "
            "sum(weights)+%g needs %.6f. A threshold below its level would automate more than the "
            "declaration buys, which is this project's arithmetic contradicting itself, not a bad "
            "request" % (chosen, at_or_below, strictly_below, level, TEST_POINT_WEIGHT, target))
    return float(chosen), False


# ---------------------------------------------------------------------------- mode 2: ACI

class AciStep(NamedTuple):
    """One round of adaptive conformal inference: the threshold USED, the score, the error."""

    t: int
    lam: float
    score: float
    err: int


def _checked_round_scores(scores) -> list:
    """Scores on the bounded range the ACI analysis is stated on, validated eagerly."""
    if scores is None or isinstance(scores, (str, bytes)):
        raise ValueError("scores must be a sequence of nonconformity scores, got %r"
                         % (type(scores).__name__,))
    values = []
    for index, raw in enumerate(scores):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError("a score at index %d is not a number: %r" % (index, raw)) from None
        if not math.isfinite(value):
            raise ValueError("non-finite score at index %d: %r" % (index, raw))
        if not 0.0 <= value <= SCORE_CEILING:
            raise ValueError("scores are nonconformity scores bounded in [0,1] for the adaptive "
                             "mode (its regret statement is stated on that range and the "
                             "threshold is clipped to it); got %r at index %d" % (value, index))
        values.append(value)
    if not values:
        raise ValueError("empty score sequence: the adaptive mode bounds an average over rounds, "
                         "and zero rounds has no average to bound")
    return values


def aci_threshold(scores, alpha, gamma, lam0=0.5) -> Iterator:
    """Iterate the adaptive threshold, one `AciStep` per round: `lam` is the value used at `t`.

    `lam_{t+1} = clip(lam_t + gamma * (err_t - alpha), 0, 1)` with `err_t = 1[score_t > lam_t]`, the
    ascent step whose fixed point is the target miscoverage rate: an error raises the threshold,
    which lowers the error rate. The published ACI update is written `a_{t+1} = a_t + gamma *
    (alpha - err_t)` because there the iterate is the nominal MISCOVERAGE LEVEL, not a threshold on
    the score -- and a larger level buys a larger set, so the sign that is stable in that
    parametrisation is the mirror of the one that is stable here. Do not "correct" this line toward
    the paper's sign without changing the parametrisation too: with `lam` as a score threshold and
    `err = 1[score > lam]`, `gamma * (alpha - err)` is the unstable direction (measured: lam
    collapses to its lower bound and the realised error rate to 0.99 on stationary scores, and the
    plant is in tests/test_drift.py's report). `lam0` is recorded, not inferred -- the analysis
    admits any start in [0,1] and this module declines to make the first threshold look like
    evidence.

    Every argument is validated BEFORE the iterator is returned, because a usage error raised from
    inside a generator surfaces at the consumer's first `next()`, far from the call that caused it.

    What this is NOT: it carries no finite-sample correction and returns no vacuity flag, and it does
    not come with the regret statement `aci_regret_bound` names either -- that sentence used to be
    published as this mode's guarantee and is withdrawn, because it is violated by an all-1.0
    sequence (long-run rate 0.500250 against 0.028778 at alpha=gamma=0.05, T=20000) and by an
    alternating 0.99/0.01 ordering (0.166740 against 0.027978 at T=100000), both of which
    `_checked_round_scores` accepts. Nothing in this module can refuse them: whether the recursion
    stays in the interior where it tracks its target is a property of the realised TRAJECTORY, not of
    the input vector, so the check belongs to the caller and is cheap -- `any(step.lam in (0.0, 1.0)
    for step in steps)` names the rounds whose update was discarded. A caller who wants a
    per-decision bound needs `split_quantile` or `weighted_quantile` and pays their assumptions
    instead; a certificate built on this threshold must carry `ACI_ENVELOPE`.
    """
    values = _checked_round_scores(scores)
    level = _alpha_check(alpha, 0.0, 0.5, "alpha",
                         "the adaptive regret term is gamma / (2(1-2*alpha)), which diverges at "
                         "0.5 and above")
    step = _alpha_check(gamma, 0.0, 1.0, "gamma",
                        "the step size is a fraction of one round's correction")
    start = _alpha_check(lam0, 0.0, 1.0, "lam0", "the starting threshold lives on the score range")
    return _walk(values, level, step, start)


def _walk(values: list, alpha: float, gamma: float, lam: float) -> Iterator:
    """The recursion itself, kept separate so `aci_threshold` can refuse before returning."""
    for index, score in enumerate(values, 1):
        err = 1 if score > lam else 0
        yield AciStep(index, lam, score, err)
        lam = min(SCORE_CEILING, max(0.0, lam + gamma * (err - alpha)))


def aci_regret_bound(rounds, alpha, gamma) -> float:
    """The quoted ACI regret expression, 1/(gamma*T) + gamma/(2(1-2*alpha)) -- a formula, NOT a promise.

    WHAT IT IS NOT: it is not this module's guarantee, and the sentence that said it was has been
    withdrawn. The published inequality |mean err - alpha| <= this(T, alpha, gamma) is violated by
    inputs `aci_threshold` accepts, measured on the shipped recursion: all-1.0 scores give a
    long-run rate of 0.500250 against 0.028778 (T=20000, alpha=gamma=0.05), an alternating
    0.99/0.01 ordering 0.166740 against 0.027978 (T=100000), a constant 0.99 sequence 0.167100, and
    an all-0.0 sequence 0.000000 against 0.028778. `tests/test_drift.py` pins each class.

    SOURCE RELIED ON, and its limits stated rather than assumed away: the expression is quoted from
    the adaptive-conformal-inference analysis of Gibbs and Candes (NeurIPS 2021, "Adaptive Conformal
    Inference Under Distribution Shift"), whose iterate is the nominal MISCOVERAGE LEVEL projected
    onto [0,1] and whose abstract claims the target error frequency "irrespective of the true data
    generating process". This module iterates a THRESHOLD clamped by min/max, which is a different
    recursion -- see the sign note below -- and the literal theorem statement could not be extracted
    from a reachable copy in the session that fixed this, so no claim here rests on it: the
    withdrawal rests on the measurements above, which are of this code.

    Both terms are still the point of the expression. The first is the price of a short sequence and
    the second the price of a coarse step, so it is a trade-off and NOT a width that shrinks to zero:
    with gamma fixed it tends to `gamma / (2(1-2*alpha))` rather than to 0, and it is monotone
    increasing in alpha at fixed gamma. Its vacuity is a property of the (alpha, gamma) PAIR and must
    not be stated without naming gamma: at alpha=0.05, gamma=0.05 it exceeds 1.0 through round 10
    (20.028 at T=1 down to 2.028 at T=10) and first comes under 0.10 at round 277, but at gamma
    0.107 and above it is already under 1.0 by round 10 (measured: 1.00229 at gamma=0.106, 0.99402 at
    0.107), and this function admits gamma anywhere in the open interval (0,1).

    A quotation, not a derivation of it (see tests/test_drift.py's docstring for what the suite
    cannot prove). `rounds` is a count of ROUNDS, and a round here is one decision; the
    case-versus-row rule that says three repeats are one observation lives in `case_count.py`, and a
    caller who feeds this T rows is overstating the sequence length.
    """
    if isinstance(rounds, bool) or not isinstance(rounds, (int, float)):
        raise ValueError("rounds must be a positive whole number of rounds, got %r" % (rounds,))
    if not math.isfinite(float(rounds)) or float(rounds) != int(rounds) or rounds < 1:
        raise ValueError("rounds must be a positive whole number of rounds, got %r" % (rounds,))
    level = _alpha_check(alpha, 0.0, 0.5, "alpha",
                         "the regret term diverges at 0.5, so no bound exists at or above it")
    step = _alpha_check(gamma, 0.0, 1.0, "gamma", "the step size must be a fraction")
    return 1.0 / (step * float(rounds)) + step / (2.0 * (1.0 - 2.0 * level))


# ------------------------------------------------------------------- the flag's decision and use

def marginal_only(certificate) -> bool:
    """Whether a certificate is marginal-only, i.e. never conditioned on a declared drift variable.

    Absent, or present as None, is marginal-only: the conservative direction, and the reason a
    certificate from before this key existed cannot quietly count as conditioned. A present-but-
    malformed declaration raises `ValueError` (exit 2) instead of choosing either reading -- a
    caller who half-declared something has to finish declaring it.
    """
    meta = getattr(certificate, "meta", None)
    if not isinstance(meta, dict):
        raise ValueError("the drift declaration is read from a certificate's meta mapping; this "
                         "object carries %r instead" % (type(meta).__name__,))
    if DRIFT_DECLARATION_KEY not in meta or meta[DRIFT_DECLARATION_KEY] is None:
        return True
    declaration = meta[DRIFT_DECLARATION_KEY]
    if not isinstance(declaration, dict):
        raise ValueError("the certificate's drift declaration is malformed: %r is not a mapping "
                         "with keys %s" % (declaration, ", ".join(DECLARATION_FIELDS)))
    missing = [key for key in DECLARATION_FIELDS if key not in declaration]
    if missing:
        raise ValueError("the certificate's drift declaration is malformed: missing %s; it must "
                         "name the variable, who declared it, and where that declaration lives"
                         % ", ".join(repr(k) for k in missing))
    values = {}
    for key in DECLARATION_FIELDS:
        raw = declaration[key]
        if not isinstance(raw, str):
            raise ValueError("the certificate's drift declaration is malformed: %r must be a "
                             "non-empty string, got %r" % (key, raw))
        if not raw.strip():
            raise ValueError("the certificate's drift declaration is malformed: %r is blank; a "
                             "declaration has to name the variable, who declared it, and where "
                             "that declaration lives" % (key,))
        values[key] = raw
    variable = values["variable"].strip()
    # first token, not the whole string: "none declared" and "marginal only" declare nothing in
    # exactly the way "none" does, and an exact-match rule would let them buy the exemption.
    return variable.lower().split()[0] in NON_CONDITIONING_VARIABLES


def with_drift_envelope(certificate):
    """Return a certificate whose envelope states its drift envelope. Never a silent pass.

    Marginal-only certificates gain `NOT_CERTIFIABLE_UNDER_DRIFT`; a certificate that declared a
    drift variable comes back untouched, and so does one that already carries the line, so the
    function is idempotent and cannot double-print it. Measured numbers are never edited: the flag
    is a statement about the claim, and a helper that also moved a bound would be the opposite
    defect. Wiring this into the certifiers is a surface task -- `certificate.py` and the certifier
    are not this module's to edit -- so the flag's owner raises it here and callers apply it.
    """
    if not marginal_only(certificate):
        return certificate
    if NOT_CERTIFIABLE_UNDER_DRIFT in tuple(certificate.envelope):
        return certificate
    return dataclasses.replace(certificate,
                               envelope=tuple(certificate.envelope) + (NOT_CERTIFIABLE_UNDER_DRIFT,))
