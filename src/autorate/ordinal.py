"""Ordinal nonconformity: the modal-anchored chain family (spec §5.4, as corrected by ruling R-68).

The construction is deliberately not the "shortest contiguous interval whose mass reaches `q`" family
this spec first named. That one is contiguous but not nested, and the score-derived family that does
nest is non-contiguous, so neither reading gives both properties and split-conformal validity cannot
be argued from either. Anchoring a chain at the modal level gives both: `score_ordinal` is the mass of
the minimum-mass contiguous span containing the level in question and `argmax`, which grows
monotonically as a level recedes from the mode, so every NON-EMPTY sublevel set is a single span around
it (contiguity -- the qualification is a fact about the construction, owned by `interval_set` below:
below the modal level's own chain mass there is no span at all, and that set is the refusal), and a
sublevel set of a fixed function is nested in its threshold by construction (validity). Mass at least
`q` is then a consequence to be reported, not the definition.

Ownership of the probe figures, so a reader does not mistake them for repository facts: the counts
this ruling replaced the first family on -- 3,333 nesting violations in 17,788 adjacent threshold
pairs, and 3,057 non-contiguous sets in 14,540, over 2,000 random ballots -- are the controller's
throwaway probe quoted in spec §5.4 and disclaimed in the ERRATA §5.4/R-68 row as not reproducible
from this repository. What the repository does own is the sweep in
`tests/test_ordinal.py::test_each_rejected_family_fails_exactly_the_property_r_68_attributed_to_it`,
which re-derives the same pattern from committed code: over 1,492 sets the mass-ordered family is 201
contiguity / 0 nesting violations, the shortest-span family is 0 / 246, and this chain is (0, 0).

Both properties are properties of a DISTRIBUTION, so the module validates its own input at its own
boundary (ruling R-106): a mass vector must have at least two levels, be finite, be non-negative, and
sum to 1 within `records.SUM_TOL`, or it is refused with `ValueError`. Usage is the right class -- the
caller handed the library a non-distribution -- and `ArithmeticError` is reserved for drift in this
project's own published arithmetic. The premise is not a formality: non-negative masses are the single
step that makes chain mass monotone away from the mode, and before the guard
`interval_set([0.5, -0.4, 0.3, 0.6, 0.0], 0.6)` answered the non-contiguous `[1, 3, 4]` silently.
Filtering that result, or relaxing `is_contiguous`, would have made the assertion pass while the
construction stayed broken; the only correct move is to refuse the input.

Ballot width is bounded by the option list, so neither the O(k) production path here nor the O(k^2)
span enumeration kept in the test is a performance question: `records.validate` refuses a ballot with
fewer than two options, and the committed corpus tops out at 4 levels (over
`data/records_feishu.jsonl` the option counts are 1,536 records at k=2 and 383 at k=4). That is the
owner of the size bound -- `k <= 51` was upstream `laya`'s number, not this repository's.

Dey et al. (NeurIPS 2023) and Zhang et al. (AAAI-26) already build contiguous/minimal ordinal sets,
so nothing here claims a novel set construction; the delta this project contributes is the
automation rule, the recorded randomisation, and the two-way bound (spec §12).
"""
from __future__ import annotations

import math
from typing import Sequence

from .records import SUM_TOL

# Masses are sums of doubles, so a threshold the caller rounded to two decimals can land one
# ulp below the span that equals it. Compared with a tolerance, not by exact equality: an exact
# `<=` would drop a level whose chain mass IS the requested threshold, and the set would then be
# nested-looking but wrong at its own boundary. Measured owner: `[0.4, 0.2, 0.3, 0.1]`'s whole-ballot
# chain mass is 1.0000000000000002, so at the maximum threshold `<= 1.0` alone answers [0, 1, 2]
# instead of the entire ballot -- see
# `tests/test_ordinal.py::test_the_tolerance_is_what_keeps_the_whole_ballot_at_the_maximum_threshold`,
# which is red when `TOL` is planted at 0.0.
TOL = 1e-12


def _check(probs: Sequence[float]) -> int:
    """Validate the premise every property above is stated over, at this module's own boundary.

    R-106: `ValueError` (usage) rather than `ArithmeticError` (reserved for drift in this project's
    published arithmetic) and rather than silence. One boundary, called by `mode_index` and therefore
    by `chain_masses` and both public entry points, so no path reaches the construction with a vector
    that is not a distribution.
    """
    k = len(probs)
    if k < 2:
        raise ValueError(
            "degenerate: %d level(s) leaves no set to certify -- a ballot of at most one level is "
            "answered by construction, so a coverage guarantee over it would be a claim about "
            "the number 1, not about the model" % k)
    p = [float(x) for x in probs]
    if not all(math.isfinite(x) for x in p):
        raise ValueError(
            "not a distribution: non-finite mass in a %d-level ballot -- a nan or an inf makes every "
            "chain mass a comparison against nan, so the set would come back empty instead of "
            "refusing" % k)
    if any(x < 0.0 for x in p):
        raise ValueError(
            "not a distribution: negative mass in a %d-level ballot -- chain mass stops being "
            "monotone away from the mode, which is the one step that makes a sublevel set a single "
            "span; a signed vector can and did answer a non-contiguous set" % k)
    total = sum(p)
    if abs(total - 1.0) > SUM_TOL:
        raise ValueError(
            "not a distribution: %d masses sum to %.6f, not 1 within %g -- every chain mass is then "
            "a fraction of something that is not a probability, so the threshold that selects them "
            "certifies no coverage" % (k, total, SUM_TOL))
    return k


def mode_index(probs: Sequence[float]) -> int:
    """The anchor level: highest probability, ties to the LEFTMOST index.

    The tie rule is published interface, not an implementation detail, and it has a consequence:
    served probabilities are rounded to 4 decimals, so `[0.4, 0.4, 0.2]` is a routine ballot rather
    than an edge case, and on a tied ballot the anchor decides WHICH LEVEL a singleton set certifies
    -- which is the level the automation rule (`|C| == 1`) would act on. Taking the rightmost tie
    turns that singleton from `[0]` into `[1]` while leaving its size at 1, so nothing downstream
    notices; `tests/test_ordinal.py::test_the_anchor_ties_leftmost_and_that_choice_is_the_certified_level`
    pins the certified level, and the set's size is asserted separately so the guard cannot be
    satisfied by the size alone.
    """
    _check(probs)
    return min(range(len(probs)), key=lambda i: (-float(probs[i]), i))


def chain_masses(probs: Sequence[float]) -> list[float]:
    """`score_ordinal` for every level: the minimum-mass contiguous span containing level and mode."""
    k = _check(probs)
    mode = mode_index(probs)
    prefix = [0.0] * (k + 1)
    for i, p in enumerate(probs):
        prefix[i + 1] = prefix[i] + float(p)
    out = []
    for g in range(k):
        lo, hi = min(g, mode), max(g, mode)
        out.append(prefix[hi + 1] - prefix[lo])
    return out


def score_ordinal(probs: Sequence[float], gold_index: int, u: float = 0.0) -> float:
    """The nonconformity of one level. `u` is accepted and deliberately not used; see `interval_set`.

    The value is a probability mass, so it is in [0, 1] and it is the smallest span mass that
    covers both `gold_index` and the modal level -- the quantity a one-sided severity or coverage
    statement is made over.
    """
    if isinstance(gold_index, bool) or not isinstance(gold_index, int):
        # A float or None index used to escape as `TypeError` from the list lookup below, which the
        # CLI maps to exit code 1 -- outside the published 0/2/3/4 contract. Usage, so: ValueError.
        raise ValueError("gold_index must be a level index (int), got %r" % (gold_index,))
    masses = chain_masses(probs)
    if not 0 <= gold_index < len(masses):
        raise ValueError(
            "gold_index %r is outside a %d-level ballot" % (gold_index, len(masses)))
    return masses[gold_index]


def interval_set(probs: Sequence[float], threshold: float, u: float = 0.0) -> list[int]:
    """`{g : score_ordinal(probs, g) <= threshold + TOL}` -- contiguous, nested in `threshold`, and
    mode-containing exactly when it is not empty.

    The qualification is a fact about the construction, not an escape hatch. Every span
    `[min(g, mode), max(g, mode)]` contains the modal level, and validation above has made every mass
    non-negative, so every chain mass is at least the modal level's own mass. Therefore no level can
    enter the sublevel set before the mode does: the set is empty precisely below the modal mass, and
    from the modal mass up it is one span holding the mode. Nothing here relaxes contiguity or nesting
    -- the empty set keeps both, it only costs the mode-containment half of the claim.

    The empty set is a real outcome and it is the family's REFUSAL, not an error: at the published
    alpha the set is empty whenever the calibration quantile lands under a ballot's own peak mass
    (`interval_set([0.4, 0.35, 0.25], 0.05) == []`), and `certify_score` counts those cases in
    `empties`, contributes 0 to the mean interval length, and refuses with
    `Reason.EMPTY_FEASIBLE_SET` when nothing automates. Measured on that gate's own synthetic
    population, 24 of 600 evaluated records answer `[]` at alpha=0.05, so the region is routine and not
    a corner; `tests/test_ordinal.py::test_no_non_empty_sublevel_set_ever_omits_the_modal_level` owns
    the qualifier over the input class. On a clean ordinal task an empty set is also the only way the
    truth escapes a certified set, because every non-empty one holds the modal level.

    `u` -- the recorded randomisation draw the `Record` contract carries -- is part of the
    signature for symmetry with the set gate and is **not** allowed to move membership here.
    Jittering a per-level score by `u * p_g` is what APS does to break ties, and here it would
    destroy the monotonicity away from the mode that makes every sublevel set one span: the set
    could keep a far level and drop a near one, which is the very "urgency is 0 or 4" outcome
    §5.4 exists to refuse. Ties between scores from DIFFERENT ballots are broken one step later,
    in the calibration quantile, where the randomisation belongs.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be a real number (the calibration quantile), got %r"
                         % (threshold,))
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite: %r is not a calibration quantile -- +inf would "
                         "certify every level of every ballot and nan would certify none, and "
                         "neither is a coverage statement" % (threshold,))
    masses = chain_masses(probs)
    return [g for g, m in enumerate(masses) if m <= threshold + TOL]


def is_contiguous(indices: Sequence[int]) -> bool:
    """True for an empty set, a singleton, or a run of consecutive indices."""
    if not indices:
        return True
    values = sorted(set(indices))
    return values[-1] - values[0] + 1 == len(values)
