"""Ordinal nonconformity: the modal-anchored chain family (spec §5.4, as corrected by ruling R-68).

The construction is deliberately not the "shortest contiguous interval whose mass reaches `q`"
family this spec first named. That one is contiguous but not nested -- measured over 2,000 random
ballots, 3,333 of 17,788 adjacent threshold pairs violate nesting -- and the score-derived family
that does nest is non-contiguous in 3,057 of 14,540 sets, so neither reading gives both properties
and split-conformal validity cannot be argued from either. Anchoring a chain at the modal level
gives both: `score_ordinal` is the mass of the minimum-mass contiguous span containing the level in
question and `argmax`, which grows monotonically as a level recedes from the mode, so a sublevel set
is a single span around it (contiguity), and a sublevel set of a fixed function is nested in its
threshold by construction (validity). Mass at least `q` is then a consequence to be reported, not
the definition.

Dey et al. (NeurIPS 2023) and Zhang et al. (AAAI-26) already build contiguous/minimal ordinal sets,
so nothing here claims a novel set construction; the delta this project contributes is the
automation rule, the recorded randomisation, and the two-way bound (spec §12).
"""
from __future__ import annotations

from typing import Sequence

# Masses are sums of doubles, so a threshold the caller rounded to two decimals can land one
# ulp below the span that equals it. Compared with a tolerance, not by exact equality: an exact
# `<=` would drop a level whose chain mass IS the requested alpha, and the set would then be
# nested-looking but wrong at its own boundary.
TOL = 1e-12


def _check(probs: Sequence[float]) -> int:
    k = len(probs)
    if k < 2:
        raise ValueError(
            "degenerate: %d level(s) leaves no set to certify -- a single-level ballot is "
            "answered by construction, so a coverage guarantee over it would be a claim about "
            "the number 1, not about the model" % k)
    return k


def mode_index(probs: Sequence[float]) -> int:
    """The anchor level: highest probability, ties to the leftmost index."""
    _check(probs)
    return min(range(len(probs)), key=lambda i: (-float(probs[i]), i))


def chain_masses(probs: Sequence[float]) -> list:
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
    masses = chain_masses(probs)
    if not 0 <= gold_index < len(masses):
        raise ValueError(
            "gold_index %r is outside a %d-level ballot" % (gold_index, len(masses)))
    return masses[gold_index]


def interval_set(probs: Sequence[float], alpha: float, u: float = 0.0) -> list:
    """`{g : score_ordinal(probs, g) <= alpha}`: contiguous, mode-containing, nested in `alpha`.

    `u` -- the recorded randomisation draw the `Record` contract carries -- is part of the
    signature for symmetry with the set gate and is **not** allowed to move membership here.
    Jittering a per-level score by `u * p_g` is what APS does to break ties, and here it would
    destroy the monotonicity away from the mode that makes every sublevel set one span: the set
    could keep a far level and drop a near one, which is the very "urgency is 0 or 4" outcome
    §5.4 exists to refuse. Ties between scores from DIFFERENT ballots are broken one step later,
    in the calibration quantile, where the randomisation belongs.
    """
    masses = chain_masses(probs)
    return [g for g, m in enumerate(masses) if m <= alpha + TOL]


def is_contiguous(indices: Sequence[int]) -> bool:
    """True for an empty set, a singleton, or a run of consecutive indices."""
    if not indices:
        return True
    values = sorted(set(indices))
    return values[-1] - values[0] + 1 == len(values)
