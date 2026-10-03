"""Threshold solvers shared by the test suite -- one owner per derivation.

`tests/test_records.py` and `tests/test_scales.py` both need the same question: "what `p_max`
makes the entropy scale reach `target` at option count k". A bisection written twice is two
owners of one derived figure, and the copies drift -- one of them gets edited, the other keeps
asserting the old number, and the suite stays green on a stale claim.

Scales here, not the figures: the k=4 / 0.85 anchor values themselves stay pinned where they
were first established (`tests/test_records.py`, which owns the cross-k spread argument).
Follow-up for that file's owner: replace its local `_pmax_reaching` with an import of
`p_max_for_entropy` -- a one-line change, deliberately not made here because that file is
being edited in parallel.
"""
from autorate.records import entropy_confidence


def p_max_for_entropy(target: float, k: int, iterations: int = 80) -> float:
    """Smallest `p_max` whose entropy-confidence reaches `target`, by bisection.

    The distribution shape is the one the README's gate is quoted against: one option holds
    `p_max`, the remaining k-1 share the rest equally.
    """
    lo, hi = 1.0 / k, 1.0
    for _ in range(iterations):
        mid = (lo + hi) / 2
        probs = [mid] + [(1 - mid) / (k - 1)] * (k - 1)
        if entropy_confidence(probs) < target:
            lo = mid
        else:
            hi = mid
    return hi
