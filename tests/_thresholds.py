"""Scale derivations the test suite shares -- one owner per derivation.

This module is the suite's OWNER FILE for arithmetic on the published scales: `tests/test_scales.py`
asserts that every helper in `tests/` which reads `entropy_confidence` lives here, and that inventory
by name. The rule is stated in `_entropy_scale_owners` there; what it means for a reader of this file
is that a new derivation over the entropy scale belongs in this module, not in a second test file,
because the last time the same derivation existed twice a transposed parameter order survived a whole
review round. Two boundaries on that claim, both measured rather than assumed: the rule is keyed on ONE
name, `entropy_confidence`, so a helper that re-derives the ANSWER scale or inverts `max_confidence` is
unreported by it -- the only thing that catches the narrowest case of that is
`tests/test_scales.py::_inline_scale_subtractions`, which watches one expression rather than one name --
and the inventory is of `tests/`, never of `src/autorate/`, because production code computing with the
scale is what that package exists to do.

`tests/test_records.py` and `tests/test_scales.py` both need the same question: "what `p_max`
makes the entropy scale reach `target` at option count k". A bisection written twice is two
owners of one derived figure, and the copies drift -- one of them gets edited, the other keeps
asserting the old number, and the suite stays green on a stale claim.

That is not hypothetical here. The second copy lived in `tests/test_records.py` as
`_pmax_reaching(k, target)`, its two parameters in the OPPOSITE order from this file's, and the file
that carried it is the one that polices the figures quoted in the design docs. Measured against the
pre-merge code, the naive merge of the two -- local copy deleted, its call sites pointed here with
the local order left alone -- dies with `TypeError: can't multiply sequence by non-int of type
'float'`. Loud, but by accident: `k` is only caught because the solver multiplies a list by it. Hand
the same swapped call int-shaped values and nothing complains at all; pre-merge
`p_max_for_entropy(2, 4)` returned 1.0, which is a plausible number that answers a different question.

So both parameters are keyword-only: the swap becomes a `TypeError` at the call site for EVERY value
pair rather than only the ones some arithmetic operation happens to reject. `tests/test_scales.py`
additionally asserts this function's two directions (rising with `target`, falling with `k`) at a
fixed reference point, which is what a body-level exchange of the two meanings inverts.

Scales here, not the figures: the k=4 / 0.85 anchor values themselves stay pinned where they
were first established (`tests/test_records.py`, which owns the cross-k spread argument).

Not every helper here is shared, and the honest reason for the two that are not: `scale_gap` and
`scale_midpoint` have exactly one importer each (`tests/test_scales.py`), so the suite's usual trigger
for a `tests/_name.py` module -- used by more than one test file -- is not what puts them here. They are
here because the ownership rule exempts only this file, and a derivation the rule is meant to police has
to be allowed to live somewhere; the alternative was to leave the subtraction of the two published scales
inside a `test_*` body, which is the scope the rule cannot see (see `_inline_scale_subtractions` there).

Both documents that quote these figures were retargeted to this function in the same commit that deleted
the second copy: `docs/ERRATA.md` and spec section 7.4 both name
`tests/_thresholds.py::p_max_for_entropy` as the producer of the table those sentences describe, and
`tests/test_records.py::test_the_errata_table_matches_the_function_that_produced_it` re-derives every
published cell through this function and checks each row against the header row of that same table.

The deleted name is a live symbol nowhere, and every place it still appears is history with a reason to
stand. `docs/ERRATA.md`'s entry "2026-10-01 -- an entropy-confidence figure was wrong in both value and
direction" carries TWO `2026-10-04` notes, and they are about different things: the FIRST opens "until the
Task 2 fix round 2 merged the suite's two copies of the bisection, this entry named
`tests/test_records.py::_pmax_reaching`, the local copy", and that is the one recording the deletion, the
history a reader of that correction needs; the SECOND opens "this entry's main paragraph says \"The table
above is byte-checked\"", and that one is about the guard's comparison and says nothing about the helper.
Plan A's completed task text still shows the old helper because that plan records what was executed, not
what the suite contains today. `tests/test_scales.py` names it twice in prose and once as an assertion --
the guard that reddens the moment a second copy is re-added to `tests/test_records.py`. Enumerated rather
than counted, because a count of these mentions has been wrong in three consecutive rounds.
"""
from autorate.records import entropy_confidence, max_confidence


def scale_gap(probs) -> float:
    """How far the two published scales sit apart on one probability vector.

    `|max(p) - (1 - H(p)/log k)|`, the quantity the tolerance window is compared against in
    `tests/test_scales.py`. It lives here because that file asserts that every helper reading the
    entropy scale has one owner, and this module is it; the gate test that quotes the gap keeps its own
    assertions and calls this for the arithmetic.
    """
    return abs(max_confidence(probs) - entropy_confidence(probs))


def scale_midpoint(probs) -> float:
    """The number sitting halfway between the two scales for one probability vector.

    A published confidence at this value is exactly `scale_gap(probs) / 2` from each scale, which is the
    row shape the tolerance comment calls "absorbed" -- counted in `both` rather than named. Same owner
    rule as `scale_gap`.
    """
    return (max_confidence(probs) + entropy_confidence(probs)) / 2


def p_max_for_entropy(*, target: float, k: int, iterations: int = 80) -> float:
    """Smallest `p_max` whose entropy-confidence reaches `target`, by bisection.

    The distribution shape is the one the README's gate is quoted against: one option holds
    `p_max`, the remaining k-1 share the rest equally.

    `target` and `k` are keyword-only; see this module's docstring for the transposition that used
    to be possible between them. `iterations` is left positional-or-keyword because it has one
    meaning, no twin to trade places with, and no caller that passes it today.
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
