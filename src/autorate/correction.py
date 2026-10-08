"""The simultaneous correction, and the size floor it shares its denominator with (spec §8.1, R-149).

A worst-of-G statement is a union bound: the chance that ANY slice misses its level is at most G
times the chance that one named slice misses its. So `bonferroni(alpha, n_groups)` divides by the
number of slices the data produced -- `len(by_group)` at the call site -- and by nothing else.

Three counts already live in this project and they are three different numbers over three different
claim sets. They are deliberately not unified:

* `certificate.N_CLAIMS` = 3 -- the envelopes ONE certificate claims in (conditional bound,
  marginal bound, automation-rate interval).
* `contamination.N_PIECES` = 4 -- the strata combined into ONE `delta_hat`.
* the `n_groups` here -- the slices ONE group-conditional run produced, which no constant may stand
  in for. Inheriting 3 from the envelope count would under-correct: an 8-slice run would be claimed
  at the joint level of a 3-slice one, and the whole point of §8.1 is that a "worst of 51 languages"
  number is a false claim unless 51 is what divides.

R-149 also says each number carries a one-line comment naming the claim set it divides. The naming
happens at this module's entrances (`group_alpha`, `group_beta`, `joint_level`, `corrected_delta`),
because the arithmetic is one division and writing it three ways is how the three counts start
standing in for one another.

Two rulings are recorded here rather than in prose elsewhere, because both are claims about this
module's arithmetic and one of them was contested until it was derived.

**The slice count does not move the joint level, and that is the correction working (R-158/R-159).**
`joint_level` computes `1 - G * n_claims * max(alpha/G, beta/G)`. Dividing both arguments of a `max`
by the same positive number cannot change which is larger, so `max(alpha/G, beta/G) = max(alpha,
beta)/G` and `G` cancels before any rounding: the level is `1 - n_claims * max(alpha, beta)` at 2
slices and at 51. A Bonferroni correction is *defined* by that invariance -- its purpose is that the
family-wise level stay constant as the family grows -- so a test asserting that the joint level
differs between `G=2` and `G=3` asserts the proposition the correction exists to avoid, and an
implementation bent to satisfy it would publish a confidence that decays with the census. What the
slice count does move is where the power goes: each slice's corrected budget (`group_alpha`,
`group_beta`, `corrected_delta`) shrinks strictly as `G` grows, the slice's own `n` shrinks with it,
the bound that `n` feeds widens (`tails.clopper_pearson_upper` on 16 cases at the same observed rate
is wider than on 128), and a slice under the size floor is refused by name. That is §8.1's
"upgrade to a step-wise procedure if the correction makes small groups uniformly uncertifiable --
decided by measurement", and the measurement lives in `tests/test_mondrian.py`.

**The two budgets combine by the looser one, not by their sum (the `max` vs `alpha + beta` question
R-159 left open).** The two readings give different published numbers -- 0.85 and 0.90 at
`alpha = beta = 0.05` -- so the choice is stated with its sources and its reconstruction, in
`joint_level`'s docstring, and the artefact carries the rule, `n_claims`, `n_groups` and both
uncorrected budgets so a reader holding a bare 0.85 can rebuild it and can see which claim set made
it (`worst_group`'s `joint_level_rule` / `joint_level_inputs`).

Every input rejection here is a `ValueError`, i.e. exit 2 (R-115). A `ZeroDivisionError` from a
slice count of zero and a `TypeError` from a level that is a string are the rc-1 escapes this module
closes; a split over no slices is a usage problem, not an arithmetic accident. A `KeyError` from a
slice that states its count under one name while the worst-of-G step reads it under another is the
same class of escape and is closed by `_as_row`, which normalises the count to one name before
anything reads it.

This module owns the arithmetic only. The floor the slices are measured against is the
certification lane's (`certify_choice.MIN_CASES_PER_SLICE`) and is passed in, because a floor stated
in cases belongs with the certificate that publishes the bound, while the corrected level belongs
with the claim. `worst_group` therefore takes rows rather than a `GroupsCertificate`: holding the
certificates would make this module an owner of the shape it reads.
"""
from __future__ import annotations

from typing import Optional, Sequence

# The number of envelopes a worst-of-G statement claims in. A group-conditional run makes G slices x
# this many claims, so `joint_level` multiplies the two; the value happens to equal
# `certificate.N_CLAIMS` (3) because a slice publishes the same three envelopes a pooled certificate
# does, and that equality is a claim about the shape which `tests/test_correction.py` pins rather
# than an import -- importing `certificate` here would be a cycle waiting to appear.
CORRECTED_CLAIMS = 3

# The reason text a size-floor refusal carries. It lives here because `worst_group` attributes the
# refusal and the certification lane states the floor: two names for one reason is how a reader
# cannot grep the refusal they were given.
GROUP_FLOOR_MESSAGE = "below the group size floor: no slice-level bound exists at this n"
_REFUSAL_REASONS = (GROUP_FLOOR_MESSAGE,)
# What "worst" means per claim, because the two sides of the certificate move in opposite
# directions: the slice a deployment can automate LEAST is the worst on `autorate`, while the slice
# whose bound is HIGHEST is the worst on a risk column. A single `max` over both would read the
# automation side backwards.
_METRICS = {"autorate": ("autorate", "min"), "conditional": ("conditional_error_bound", "max"),
            "marginal": ("marginal_error_bound", "max")}


def _level(name: str, value) -> float:
    """One nominal level in (0, 1), refused as a `ValueError` (exit 2) rather than corrected blindly.

    Non-numeric and non-finite are refused by NAME. `float("0.05")` succeeds, so a string that
    contains a number is not a level: `alpha` reaches the CLI as text and a correction that silently
    divided a string would publish a level nobody typed. `bool` is excluded although `True` is an
    `int`: a probability is not a flag.
    """
    if isinstance(value, (bool, str, bytes)) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number in (0,1), got %r (%s)"
                         % (name, value, type(value).__name__))
    v = float(value)
    # `not (0 < v < 1)` rather than `v <= 0 or v >= 1`: a NaN satisfies neither comparison, so the
    # second form would pass an untestable level through as legal.
    if not 0.0 < v < 1.0:
        raise ValueError("%s must be in (0,1), got %r" % (name, value))
    return v


def _count(name: str, value) -> int:
    """A count of slices or claims: an int at least 1, refused as a `ValueError` otherwise.

    `n_groups = 0` is the empty split, and a bare division there is `ZeroDivisionError` -- rc 1,
    outside this project's 0/2/3/4 contract (R-115). A float count is refused rather than rounded:
    `2.5` slices is a census bug, and rounding it silently changes the claim.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s is a count and must be an int, got %r (%s)"
                         % (name, value, type(value).__name__))
    if value < 1:
        raise ValueError("%s is a count and must be at least 1, got %d; over nothing there is no "
                         "worst to claim about" % (name, value))
    return int(value)


def _divide(level: float, n_groups: int) -> float:
    """The one division every corrected level in this module is made from."""
    return level / n_groups


def bonferroni(alpha: float, n_groups: int) -> float:
    """The per-slice level a worst-of-`n_groups` claim may be stated at.

    At one group there is nothing to correct and the uncorrected level comes back, which is the
    falsification of "the correction is a decoration": the value must move with the DATA count, and
    strictly (`tests/test_correction.py` walks 1..8). The quotient is exact by IEEE 754, so the
    corrected level is the same number on every platform without a canonicalisation pass -- the two
    bounds it feeds are canonicalised at their own call sites instead (`certificate.canonicalise_bound`).
    """
    return _divide(_level("alpha", alpha), _count("n_groups", n_groups))


def corrected_delta(delta: float, n_groups: int) -> float:
    """The same correction applied to `delta`, the level each published bound is tested at.

    A group-conditional certificate still publishes three claims, so its `level` attribute is
    `1 - N_CLAIMS * delta`: leaving `delta` uncorrected would let the artefact claim a joint
    confidence of 0.85 on an 8-slice run whose actual joint confidence is 0.15. Correcting it is what
    makes the published level the one the slices were actually tested at.
    """
    return bonferroni(delta, n_groups)


def _rubric_levels(rubric: dict) -> tuple:
    """The two nominal levels a slice was certified at, read from one dict so they have one owner.

    `alpha` bounds coverage and `beta` bounds the error among automated cases; a group-conditional
    claim is a claim about both, and neither correction can be derived from the other. A rubric
    missing either is refused: the corpus rubric (`report.ALPHA`, `report.BETA`) carries both per
    committed certificate, and a caller that passes something else is asking for a correction at an
    unnamed level. A level of 0.0 or 1.0 is refused by `_level`, so a rubric cannot smuggle an
    untestable budget in as "no budget".
    """
    if not isinstance(rubric, dict):
        raise ValueError("the slice rubric must be a mapping of the declared levels, got %s"
                         % (type(rubric).__name__,))
    levels = []
    for name in ("alpha", "beta"):
        if rubric.get(name) is None:
            raise ValueError("the slice rubric states no %r, so its corrected level cannot be "
                             "derived; a group-conditional claim names the levels it divides"
                             % (name,))
        levels.append(_level(name, rubric[name]))
    return levels[0], levels[1]


def group_alpha(rubric: dict, n_groups: int) -> tuple:
    """`(uncorrected, corrected alpha)` -- both, because the artefact has to show the reader the work."""
    alpha, _beta = _rubric_levels(rubric)
    g = _count("n_groups", n_groups)
    return alpha, _divide(alpha, g)


def group_beta(rubric: dict, n_groups: int) -> tuple:
    """`(uncorrected, corrected beta)`, the same pair for the conditional-error budget.

    Splitting `beta` as well as `alpha` is what §8.1's "Bonferroni on alpha" means operationally
    here: the budget a deployment imposes is `beta`, and a worst-of-G certificate that corrected only
    the coverage level would state its bound at one level and its budget at another.
    """
    _alpha, beta = _rubric_levels(rubric)
    g = _count("n_groups", n_groups)
    return beta, _divide(beta, g)


# The combination rule `joint_level` publishes under, named once so the artefact can carry it beside
# the number it made. A bare 0.85 does not say whether its multiplier was 2 or 3, nor whether the
# two budgets combined by `max` or by their sum, and those two readings differ by five points of
# published confidence -- so the rule travels with the level (`worst_group`).
JOINT_LEVEL_RULE = (
    "1 - n_claims * max(alpha, beta), after every slice's budgets are divided by n_groups; n_groups "
    "therefore cancels and the family-wise level is CONSTANT in n_groups, which is the Bonferroni "
    "property spec 8.1 buys rather than an oversight of it")


def joint_level_inputs(rubric: dict, n_groups: int, n_claims: int = CORRECTED_CLAIMS) -> dict:
    """Every number the joint level is made of, in one dict, so a published level can be rebuilt.

    This is the one owner of the simultaneous arithmetic: `joint_level` returns the `level` field of
    this dict, so the number an artefact prints and the inputs it prints beside it cannot come from
    two different readings of the same product.

    The combination rule, and why it is `max` and not `alpha + beta` (the question R-159 left open
    for the reviewer). The spec's own construction is the authority on what the events are:

    * §5.3 fixes coverage on one split and bounds the conditional error on the other, and "the
      reported pair carries a union-bound confidence level" -- a union bound over the pair of
      *distinct* failure events, which is a SUM of their budgets.
    * §5.2 nests the marginal side inside the coverage side: `P(err AND auto) <= P(Y not in C(X)) <=
      alpha`. The marginal automated-error event is therefore not a third budget; it is paid for by
      `alpha` already.
    * §6.1 is this repository's precedent for two separately certified one-sided risks ("each
      certified separately and both reported", at `alpha_miss` and `alpha_block`): the level of the
      conjunction is `1 - sum(budgets)`, one budget per event.
    * "Learn then Test" §3.2 (arXiv 2110.01052) supplies the exact binomial bound on
      `P(T(X) != Y | T(X) != empty)` at a chosen level. It fixes one family's level; it does not say
      how two families combine.

    `joint_level` is handed the two risk TARGETS (`alpha`, `beta`) and a count of ENVELOPES
    (`n_claims`), and is deliberately not told which envelope carries which budget -- this module
    owns arithmetic, not the shape. Over every assignment of the two budgets to the envelopes, the
    union bound is `sum_e budget_e <= n_claims * max(alpha, beta)`, so `max` is the rule that is
    conservative for every reading of the shape, and it is the rule `certificate.py` already ships
    one instance of: its published level is `1 - N_CLAIMS * delta`, three envelopes at one budget
    each, which is `1 - n_claims * max(alpha, beta)` at `alpha = beta = delta` -- the published
    rubric, where `tests/test_correction.py` pins the two to the same 0.85.

    `1 - (alpha + beta)` = 0.90 is not a rival formula for the same claim; it is the level of the
    §5.3 PAIR alone, i.e. `n_claims = 2` at `alpha = beta` (there, `2 * max(alpha, beta)` and
    `alpha + beta` are the same number). Publishing 0.90 for a three-envelope run would let the
    automation-rate interval into the artefact without paying for it, so the caller that wants it
    passes `n_claims=2` and says so. `n_claims` is therefore in the output, and
    `tests/test_correction.py` pins 0.85 at 3 envelopes against 0.90 at 2.

    The product, not the division, is where a simultaneous claim can stop being a probability: G x
    n_claims x (level / G) can reach 1 while every corrected level is comfortably inside (0,1), and
    a "joint confidence" outside (0,1) is not a confidence. Refused loudly rather than published.
    """
    alpha, beta = _rubric_levels(rubric)
    g = _count("n_groups", n_groups)
    claims = _count("n_claims", n_claims)
    corrected_alpha, corrected_beta = _divide(alpha, g), _divide(beta, g)
    worst = max(corrected_alpha, corrected_beta)
    risk = g * claims * worst
    level = 1.0 - risk
    if not 0.0 < level < 1.0:
        raise ValueError("the joint level %r over %d slices x %d claims at %.6f is not a probability; "
                         "this run cannot state a simultaneous claim at these budgets"
                         % (level, g, claims, worst))
    return {"rule": JOINT_LEVEL_RULE, "formula": "1 - n_groups * n_claims * max(alpha/n_groups, "
                                                 "beta/n_groups)", "alpha": alpha, "beta": beta,
            "n_groups": g, "n_claims": claims, "corrected_alpha": corrected_alpha,
            "corrected_beta": corrected_beta, "risk": risk, "level": level}


def joint_level(rubric: dict, n_groups: int, n_claims: int = CORRECTED_CLAIMS) -> float:
    """The joint confidence a worst-of-`n_groups` statement actually carries.

    `1 - n_groups x n_claims x (level / n_groups)` over the LARGER of the two corrected levels --
    see `joint_level_inputs` for the sources of that combination rule and for why the `n_groups`
    cancels instead of decaying. `n_claims` defaults to `CORRECTED_CLAIMS`; the certification lane
    passes the shape's own `N_CLAIMS`, so the count of envelopes has one owner while the arithmetic
    still lives here.
    """
    return joint_level_inputs(rubric, n_groups, n_claims)["level"]


def size_floor(n_cases, floor: int) -> bool:
    """Whether one slice is too small to bound. The floor is inclusive: `n >= floor` is certifiable.

    Both arguments are validated because this is the predicate the census and the certifier share,
    and a non-numeric floor or count used to reach a comparison and raise `TypeError` -- rc 1.
    """
    if isinstance(floor, (bool, str, bytes)) or not isinstance(floor, int) or floor < 0:
        raise ValueError("floor is a count of cases and must be an int >= 0, got %r" % (floor,))
    if isinstance(n_cases, (bool, str, bytes)) or not isinstance(n_cases, (int, float)):
        raise ValueError("n_cases is a count of independent cases and must be a number, got %r (%s)"
                         % (n_cases, type(n_cases).__name__))
    return n_cases < floor


def min_violations(subject, floor: int):
    """The size floor as a predicate, or the census of slices that fell below it.

    A number first argument is one slice's case count and a bool comes back; a sequence of census
    rows comes back as the list of rows below the floor, in the order given, so the artefact can name
    them. Two spellings, one rule -- the rule the certification lane's floor constant decides, so a
    caller cannot get a different boundary from the arithmetic than from the constant. A census row
    that states no `n_cases` is refused: a missing count is a bug in the census builder, and it used
    to escape as `KeyError` -- rc 1 (R-115).
    """
    if isinstance(subject, (int, float)) and not isinstance(subject, bool):
        return size_floor(subject, floor)
    if isinstance(subject, (str, bytes)) or not hasattr(subject, "__iter__"):
        raise ValueError("min_violations takes one case count or a sequence of census rows, got %s"
                         % (type(subject).__name__,))
    out = []
    for row in list(subject):
        if "n_cases" not in row:
            raise ValueError("a slice census row states no 'n_cases' (%r), so the size floor cannot "
                             "be applied to it; the census has to carry the count it is refused on"
                             % (row.get("group")))
        if size_floor(row["n_cases"], floor):
            out.append(row)
    return out


def _worst_row(rows: Sequence[dict], key: str, direction: str) -> dict:
    """The worst row on `key`, with a `None` winning (a refusal is the worst case).

    Read from the rows rather than hand-picked, so a stale maximum cannot be published: the caller
    that changes a slice's numbers changes the worst slice with them. `direction` is the metric's,
    because the two sides of a certificate move opposite ways -- the slice a deployment may automate
    LEAST is the worst `autorate`, the slice whose bound is HIGHEST is the worst risk. Ties go to the
    slice with the fewest independent cases, because on equal numbers that is the claim with the
    least evidence behind it.
    """
    def rank(row):
        value = row.get(key)
        if value is None:
            return (1, 0.0, -row["n_cases"])
        return (0, -value if direction == "min" else value, -row["n_cases"])

    return max(rows, key=rank)


def _as_row(group) -> dict:
    """A slice's published numbers, from either the artefact row or the certificate itself.

    The case count is normalised to a top-level `n_cases` because it is what the worst-of-G tie-break
    and the refusal attribution both read: a `Certificate` carries it as `meta["n_eval_cases"]` (the
    name both shipped certifiers publish), and an artefact row may already state it at the top. Two
    names for one count in one dict is a census bug waiting to disagree, so the second one is dropped
    -- and reading the wrong one used to escape as `KeyError`, i.e. rc 1 (R-115).

    The two budgets and the envelope count are normalised the same way because `worst_group` states
    the simultaneous claim: a `Certificate` holds `alpha`/`beta`/`delta` as attributes, `certify_choice`
    also mirrors `alpha` and `beta` into `meta`, and an artefact row may carry either. A count that is
    simply absent stays absent -- `None` here means "this artefact does not state it", which is a
    different fact from "it is zero", and the difference is what `_shared_claim` refuses on.
    """
    if isinstance(group, dict):
        row = dict(group)
        meta = row.get("meta") or {}
        if "group" not in row:
            row["group"] = meta.get("slices")
        if "n_cases" not in row:
            row["n_cases"] = meta.get("n_eval_cases")
    else:
        meta = getattr(group, "meta", None) or {}
        row = {"group": meta.get("slices"), "feasible": bool(group.feasible),
               "reason": group.reason, "autorate": group.autorate,
               "conditional_error_bound": group.conditional_error_bound,
               "marginal_error_bound": group.marginal_error_bound, "level": group.level,
               "n_cases": meta.get("n_eval_cases"), "meta": meta,
               "alpha": getattr(group, "alpha", None), "beta": getattr(group, "beta", None),
               "delta": getattr(group, "delta", None)}
    for name in ("alpha", "beta", "delta", "n_claims"):
        if row.get(name) is None:
            row[name] = meta.get(name)
    if row.get("n_cases") is None:
        raise ValueError("slice %r states no case count, so the worst of it cannot be broken by "
                         "evidence and its refusal cannot be attributed to a size floor"
                         % (row.get("group"),))
    row["feasible"] = bool(row.get("feasible"))
    return row


def _shared_claim(rows: Sequence[dict]):
    """The one rubric these slices were certified at, or None when the artefact does not state it.

    `joint_level` is a statement about a FAMILY, so it needs one budget for the whole family. Slices
    certified at different levels are not one family, and the honest output is a refusal naming every
    slice's own budgets rather than `rows[0]`'s standing in for all of them -- which is what the
    first version of this function did, and which would have published the first slice's `beta` as
    the family's while a later slice was tested at another.
    """
    declared = []
    for row in rows:
        if row.get("alpha") is None or row.get("beta") is None:
            continue
        declared.append((row["group"], _rubric_levels({"alpha": row["alpha"], "beta": row["beta"]}),
                         CORRECTED_CLAIMS if row.get("n_claims") is None
                         else _count("n_claims", row["n_claims"])))
    if not declared:
        return None
    if len({pair for _name, pair, _c in declared}) > 1 or len({c for _n, _p, c in declared}) > 1:
        raise ValueError("slices certified at different budgets -- %s -- so there is not one "
                         "simultaneous claim here: a worst-of-G over mixed rubrics would publish a "
                         "single joint level for two families"
                         % ", ".join("%s=(alpha=%r, beta=%r, n_claims=%r)" % (name, pair[0], pair[1],
                                                                              c)
                                     for name, pair, c in declared))
    name, (alpha, beta), claims = declared[0]
    return {"group": name, "alpha": alpha, "beta": beta, "n_claims": claims}


def worst_group(groups, metric: str = "autorate", floor: Optional[int] = None) -> dict:
    """The worst slice of a group-conditional run, and every slice that refused with its reason.

    `metric` is the quantity a deployment acts on, so it is what "worst" means; `conditional` and
    `marginal` are accepted for the risk side of the same claim. A refused slice is the worst by
    construction -- it has no bound at all -- so `any_slice_refused` says so at the top rather than
    leaving a reader to compare `None` values.

    `any_slice_refused` covers two causes, and `slices_without_the_metric` separates them, because a
    reader who is told a slice refused when the column is merely unpublished would go looking for a
    certification refusal that never happened: (1) a slice that was refused certification, attributed
    only to the size floor when the floor is what it fell below; (2) a slice that carries no value
    for the metric asked about, which makes the worst-of-`metric` claim unreconstructable -- a column
    of `None` is a refusal to rank, not a maximum.

    The corrected levels, `n_groups`, `n_claims` and the combination rule ride along (as
    `joint_level`, `joint_level_inputs` and `joint_level_rule`), since a worst-of-G number without
    them is the false claim §8.1 names -- and, per R-159, a bare joint level cannot be rebuilt by a
    reader who cannot see whether the multiplier was 2 or 3 or how the two budgets combined. The
    plan's own Step 3 stands: compute the worst FROM the per-group objects, never a hand-picked
    maximum.
    """
    rows = [_as_row(g) for g in (groups or [])]
    if not rows:
        raise ValueError("no slices to take a worst of; a worst-of-0 claim is not a claim")
    if metric not in _METRICS:
        raise ValueError("unknown worst-slice metric %r; this claim is about %s"
                         % (metric, ", ".join(sorted(_METRICS))))
    key, direction = _METRICS[metric]
    claim = _shared_claim(rows)
    inputs = (None if claim is None else
              joint_level_inputs({"alpha": claim["alpha"], "beta": claim["beta"]},
                                 len(rows), claim["n_claims"]))
    refusals, unrankable = [], []
    for row in rows:
        missing_column = row.get(key) is None
        if row["feasible"] and not missing_column:
            continue
        if not row["feasible"]:
            why = row["meta"].get("detail") or "refused"
            if floor is not None and size_floor(row["n_cases"], floor):
                why = GROUP_FLOOR_MESSAGE
            elif not any(reason in why for reason in _REFUSAL_REASONS):
                # R-149's other half: a group-conditional refusal that is NOT the size floor is a
                # slice-level finding, and nothing here is evidence that slice structure caused it.
                # `elif`, not `else`: a detail that ALREADY names the floor must keep that
                # attribution when the caller passed no floor to re-derive it from.
                why = ("%s; NOT attributed to the slice structure -- only the size floor is a "
                       "group-conditional refusal this tool can name" % why)
        else:
            why = ("this artefact publishes no %r for slice %r, so there is nothing to rank on the "
                   "%r claim: a column of None is a refusal to state a worst, not a maximum"
                   % (key, row["group"], metric))
            unrankable.append(row["group"])
        refusals.append({"group": row["group"], "n": row["n_cases"],
                         "reason": row.get("reason"), "why": why})
    first = rows[0]
    return {
        "level": first.get("level"),
        "metric": metric,
        "alpha": first.get("alpha"),
        "beta": first.get("beta"),
        "delta": first.get("delta"),
        "corrected_alpha": (inputs or {}).get("corrected_alpha", first["meta"].get("corrected_alpha")),
        "corrected_beta": (inputs or {}).get("corrected_beta", first["meta"].get("corrected_beta")),
        "corrected_delta": first["meta"].get("corrected_delta"),
        "n_groups": len(rows),
        "n_claims": None if inputs is None else inputs["n_claims"],
        "joint_level": None if inputs is None else inputs["level"],
        "joint_level_risk": None if inputs is None else inputs["risk"],
        "joint_level_rule": JOINT_LEVEL_RULE,
        "joint_level_inputs": inputs,
        "joint_level_note": (
            "the slices publish no alpha/beta, so no simultaneous level is derived here; the rule "
            "above is what would have made it" if inputs is None else
            "stated from the rule and the inputs beside it: 1 - n_claims * max(alpha, beta) after "
            "each slice's budgets are divided by n_groups"),
        "groups_declared": first["meta"].get("groups_declared"),
        "worst": _worst_row(rows, key, direction),
        "refusals": refusals,
        "slices_without_the_metric": unrankable,
        "any_slice_refused": bool(refusals),
        "groups": rows,
    }
