"""Modal-anchored chain sets: contiguous around the mode, nested by construction."""
import random

import pytest

from autorate.ordinal import (TOL, chain_masses, interval_set, is_contiguous, mode_index,
                              score_ordinal)


def test_the_set_is_the_sublevel_set_of_the_chain_score():
    # R-68: re-derived for the modal-anchored family. Chain scores of this ballot are
    # [0.45, 0.40, 0.75, 0.85, 0.95], so the sublevel sets below are what the code must return.
    # The name matters as much as the numbers: this is NOT "the shortest interval reaching the
    # requested mass". At 0.85 the cheapest contiguous span reaching that mass is [1, 2, 3]
    # (0.40+0.35+0.10 = 0.85), while the chain's sublevel set is [0, 1, 2, 3] at a mass of 0.90.
    # The extra level is the point -- membership is by chain score around the mode, so the family
    # stays nested, and this pair of expectations is what distinguishes the two constructions.
    p = [0.05, 0.4, 0.35, 0.1, 0.1]
    assert interval_set(p, 0.4) == [1]
    assert interval_set(p, 0.75) == [0, 1, 2]
    assert interval_set(p, 0.85) == [0, 1, 2, 3]


def test_mass_ordered_multiclass_sets_are_not_contiguous_and_this_refuses_to_be_one():
    """spec 5.4's actual claim, as an assertion: 'levels 0 or 4' is not an answer.

    A k-of-m top-mass set would pick {0,1,3} for the ballot below; the ordinal family must return a
    contiguous chain around the modal level instead.

    Rewritten after the review measured what this test's first draft claimed: at this budget the chain
    does not "cost an extra level", it returns the ENTIRE ballot (`[0, 1, 2, 3, 4]`, mass 1.00 against
    the greedy set's 0.94) -- two extra levels, which is the more striking and the honest statement.
    The budget is what does it: 0.94 exceeds this ballot's largest chain mass (0.70, the span from the
    mode to level 4), so every level is under it and the sublevel set is the whole span. The exact set
    is now pinned rather than described, because the draft's `sum(...) >=` line is satisfied by ANY set
    over the budget -- the review's plant A passed it with the non-contiguous `[0, 1, 3, 4]` -- and only
    `is_contiguous` and the pinned value discriminate.
    """
    p = [0.30, 0.34, 0.02, 0.30, 0.04]
    top_mass = sorted(range(5), key=lambda i: -p[i])
    greedy = sorted(top_mass[:3])                       # what mass-ordered CP returns
    assert greedy == [0, 1, 3] and not is_contiguous(greedy)
    ours = interval_set(p, sum(p[i] for i in greedy))   # same budget, chain construction
    assert ours == [0, 1, 2, 3, 4], ours
    assert is_contiguous(ours), ours
    assert sum(p[i] for i in ours) >= sum(p[i] for i in greedy) - 1e-12, (ours, greedy)
    # and at a budget the chain can actually meet, the cost IS one level: the cheapest contiguous span
    # reaching 0.64 is [0, 1] (0.64), the chain's sublevel set at 0.64 is [0, 1, 2] (0.66).
    assert interval_set(p, 0.64) == [0, 1, 2]


def test_the_family_is_nested_so_split_conformal_validity_carries_over():
    """Nesting is the property §5.4's validity argument rests on, so it is asserted as a
    subset relation -- not as the disjunction this test originally carried, which passed on
    ballots where the later set displaced the earlier one entirely."""
    rng = random.Random(11)
    for _ in range(200):
        k = rng.randrange(2, 8)
        w = [rng.random() + 0.05 for _ in range(k)]
        s = sum(w)
        p = [x / s for x in w]
        prev = []
        for q in sorted({round(x, 3) for x in p} | {0.5, 0.9, 0.99}):
            C = interval_set(p, q)
            assert is_contiguous(C), (p, q, C)
            assert set(prev) <= set(C), (p, q, C, prev)
            prev = C


def test_the_score_of_the_gold_label_is_the_smallest_q_that_includes_it():
    p = [0.1, 0.6, 0.3]
    assert abs(score_ordinal(p, 1, 0.0) - 0.6) < 1e-12
    assert abs(score_ordinal(p, 0, 0.0) - 0.7) < 1e-12
    # Two-sided, like the two lines above it. This one shipped as `<= 0.9 + 1e-12`, which the review
    # measured against a plant that under-reports every score right of the mode by 0.2: the one-sided
    # form is satisfied by 0.7 while the true chain mass is 0.9. The test name claims "the smallest q
    # that includes it", so the assertion has to say the value, not just bound it from above.
    assert abs(score_ordinal(p, 2, 0.0) - 0.9) < 1e-12


def test_a_single_level_distribution_cannot_be_certified_and_says_so():
    with pytest.raises(ValueError, match="degenerate"):
        interval_set([1.0], 0.5)


def test_the_closed_form_matches_a_brute_force_span_search():
    """Step 3's cross-check: `prefix[max+1] - prefix[min]` must be the minimum-mass span.

    The O(k^2) enumeration is kept here and nowhere in the production path -- R-68 replaced the
    definition that needed it -- so that the closed form is checked against the thing it is
    supposed to compute rather than against itself. Zero-probability levels are included on
    purpose: they are where two spans can tie on mass, which is the only case where the closed
    form and a naive "strictly growing away from the mode" reading differ.
    """
    rng = random.Random(23)
    for _ in range(300):
        k = rng.randrange(2, 8)
        w = [rng.choice([0.0, rng.random() + 0.02]) for _ in range(k)]
        if sum(w) <= 0.0:
            continue
        p = [x / sum(w) for x in w]
        mode = min(range(k), key=lambda i: (-p[i], i))
        for g in range(k):
            brute = min(sum(p[lo:hi + 1])
                        for lo in range(0, min(g, mode) + 1)
                        for hi in range(max(g, mode), k))
            assert abs(score_ordinal(p, g) - brute) < 1e-12, (p, g, brute)


def test_membership_ignores_the_recorded_draw_because_a_jittered_score_would_split_the_chain():
    """`u` is in the signature for symmetry with the set gate, and it must NOT move membership.

    Adding a per-level randomisation to the score is what APS does to break ties, and here it would
    destroy the monotonicity away from the mode that makes every sublevel set one span: the set could
    keep a far level and drop a near one, which is the very "urgency is 0 or 4" outcome §5.4 exists to
    refuse. Ties between scores from DIFFERENT ballots are broken one step later, in the calibration
    quantile, where the randomisation belongs. Asserted rather than commented, because a silent unused
    parameter is how a later "improvement" adds the jitter back.
    """
    p = [0.05, 0.4, 0.35, 0.1, 0.1]
    for alpha in (0.4, 0.75, 0.85, 0.95, 1.0):
        assert interval_set(p, alpha, 0.0) == interval_set(p, alpha, 0.99), alpha
    assert abs(score_ordinal(p, 0, 0.0) - score_ordinal(p, 0, 0.77)) < 1e-15


def _greedy_top_mass(p, q):
    """The set multiclass CP builds: the smallest top-mass prefix whose mass passes `q`."""
    picked, acc = [], 0.0
    for i in sorted(range(len(p)), key=lambda j: (-p[j], j)):
        if acc > q + 1e-12:
            break
        picked.append(i)
        acc += p[i]
    return sorted(picked)


def _min_length_reach_mass(p, q):
    """The family ruling R-68 rejected: the shortest contiguous span whose mass reaches `q`."""
    k, best = len(p), None
    for lo in range(k):
        acc = 0.0
        for hi in range(lo, k):
            acc += p[hi]
            if acc >= q - 1e-12:
                if best is None or (hi - lo + 1, lo) < (best[0], best[1]):
                    best = (hi - lo + 1, lo, hi)
                break
    return [] if best is None else list(range(best[1], best[2] + 1))


def test_each_rejected_family_fails_exactly_the_property_r_68_attributed_to_it():
    """R-68 is a claim about two families, so it is tested as one -- and it corrects Step 5.

    The plan's Step 5 says to plant the mass-ordered set and watch BOTH the contiguity and the
    nesting assertion go red. Measured over the same 200 ballots and threshold grid that
    `test_the_family_is_nested...` walks, that is wrong about half of it: a top-mass prefix is
    monotone in its threshold, so it violates contiguity 201 times and nesting **never**. The
    family that breaks nesting is the one R-68 actually replaced -- shortest-span-reaching-mass,
    246 nesting violations in 1,492 sets and 0 contiguity violations, its first counterexample
    being the documented `p = [0.1589, 0.3806, 0.4605]`, `C` at `q = 0.381` is `[2]` after `[1]`.

    So each property needs its own plant, and this test is that proof in permanent form: two
    violations counts and two zeros, with the production chain swept on the same ballots to show
    it is the only one of the three that satisfies both.
    """
    def contiguous(C):
        return not C or max(C) - min(C) + 1 == len(set(C))

    def sweep(family):
        rng = random.Random(11)
        bad_contig = bad_nest = sets = 0
        for _ in range(200):
            k = rng.randrange(2, 8)
            w = [rng.random() + 0.05 for _ in range(k)]
            s = sum(w)
            p = [x / s for x in w]
            prev = []
            for q in sorted({round(x, 3) for x in p} | {0.5, 0.9, 0.99}):
                C = family(p, q)
                sets += 1
                if not contiguous(C):
                    bad_contig += 1
                if not set(prev) <= set(C):
                    bad_nest += 1
                prev = C
        return sets, bad_contig, bad_nest

    sets, contig, nest = sweep(_greedy_top_mass)
    assert contig > 0 and nest == 0, ("mass-ordered", sets, contig, nest)
    sets, contig, nest = sweep(_min_length_reach_mass)
    assert nest > 0 and contig == 0, ("min-length-reach-mass", sets, contig, nest)
    sets, contig, nest = sweep(lambda p, q: interval_set(p, q))
    assert (contig, nest) == (0, 0), ("chain", sets, contig, nest)
    assert sets > 1000, sets        # the sweep must actually have walked the grid


# --- R-106 (finding M3): the two properties are properties of a DISTRIBUTION ------------------
#
# Measured against the module as it shipped at `7931046`, before the boundary below existed, at the
# threshold this fixture uses (`0.6`): `[0.5, -0.4, 0.3, 0.6, 0.0]` answered `[1, 3, 4]` --
# non-contiguous, no exception, and `is_contiguous([1, 3, 4])` is False -- while `[0.7, 0.7, 0.2]`
# (mass 1.6), `[2.0, 3.0]`, `[nan, 0.5, 0.5]` and `[inf, 0.0, 0.0]` each answered `[]`. At `0.7` the
# mass-1.6 ballot answers `[0]`, which is the reading the review quoted. Five of the seven vectors in
# `_NON_DISTRIBUTIONS` are those silent answers; the other two are the `k < 2` cases the module already
# refused, kept here because R-106 names them and because the boundary has to cover them too.

_NON_DISTRIBUTIONS = [
    ([0.5, -0.4, 0.3, 0.6, 0.0], "negative mass"),
    ([0.7, 0.7, 0.2], "sum to 1.600000"),
    ([2.0, 3.0], "sum to 5.000000"),
    ([float("nan"), 0.5, 0.5], "non-finite mass"),
    ([float("inf"), 0.0, 0.0], "non-finite mass"),
    ([1.0], "degenerate"),
    ([], "degenerate"),
]


def test_a_non_distribution_is_refused_by_the_same_boundary_at_every_entry_point():
    """M3 / R-106: negative, non-finite, non-summing or `k < 2` mass vectors do not reach the chain.

    One boundary, four entry points: `mode_index`, `chain_masses`, `interval_set` and `score_ordinal`
    all refuse the same vector with the same words, because `chain_masses` and `mode_index` both call
    `_check` and the two public entry points both call `chain_masses`. Asserted over all four because
    a guard on one entry only is a guard the other three can walk past -- and `score_ordinal` is the
    one the calibration half goes through (`certify_score._scores`), while `interval_set` is the one
    the certified set goes through.

    The class matters as much as the raise. `ValueError` is the usage class the CLI maps to exit code
    2; `ArithmeticError` is reserved for drift in this project's own published arithmetic and would
    map to exit 3, claiming a reproduction failure that never happened; a `TypeError` (what the
    unguarded module raised for a bad `gold_index`) is rc 1, outside the published 0/2/3/4 contract.
    So the assertion is on the exact class, not merely that it is an exception.
    """
    for probs, reason in _NON_DISTRIBUTIONS:
        for entry in (lambda: mode_index(probs), lambda: chain_masses(probs),
                      lambda: interval_set(probs, 0.6), lambda: score_ordinal(probs, 0)):
            with pytest.raises(ValueError, match=reason) as raised:
                entry()
            assert type(raised.value) is ValueError, (probs, reason, raised.value)
            assert not isinstance(raised.value, ArithmeticError), (probs, reason)


def test_contiguity_is_protected_by_the_boundary_rather_than_happening_to_hold():
    """M3 asks for the invariant, not a sample: no vector may be answered a split set.

    Swept over deliberately malformed ballots -- signed, non-normalised, zero-mass -- across the
    threshold range. Every point on the grid is therefore either REFUSED (counted in `refused`) or
    answered with a contiguous, nested set (counted in `answered`), and both arms must be populated.
    That is what makes this a guard on the premise rather than a re-run of the eight tests that shipped
    with Task 1, which only ever walked valid ballots and so said nothing about how a bad one is
    handled: `refused == 0` there would be invisible, and `answered` alone never contradicts the
    properties.

    Two forbidden "fixes" are refused by construction here, which is why the counters are asserted:
    filtering the result would leave `refused` at 0 (the module answers, so the sweep never sees a
    raise), and relaxing `is_contiguous` to accept a signed-vector answer would need this test to stop
    calling the published predicate.
    """
    rng = random.Random(101)
    refused = answered = 0
    for i in range(300):
        k = rng.randrange(2, 7)
        # Two thirds of the draw is normalised non-negative -- a distribution, so the answer arm is
        # exercised -- and every third draw keeps its sign and its raw sum: this is the input class the
        # pre-R-106 module accepted, and it is not the one the eight shipped tests ever walked.
        w = [max(0.0, rng.uniform(-0.4, 1.0)) if i % 3 else rng.uniform(-0.4, 1.0) for _ in range(k)]
        total = sum(w)
        p = [round(x / total, 4) for x in w] if total > 0.0 else [round(x, 4) for x in w]
        prev = []
        for q in (0.0, 0.5, 0.6, 1.0):
            try:
                C = interval_set(p, q)
            except ValueError:
                refused += 1
                continue
            answered += 1
            assert is_contiguous(C), (p, q, C)
            assert set(prev) <= set(C), (p, q, C, prev)
            prev = C
    assert refused > 0 and answered > 0, (refused, answered)


def test_a_non_numeric_argument_refuses_with_valueerror_because_rc_1_is_not_publishable():
    """The two argument guards R-106 implies, measured against the pre-guard module.

    Measured at `7931046`, on `probs=[0.5, 0.5]`. Four of the five `gold_index` values escaped as
    `TypeError` -- `None`, `1.0`, `"1"` and `[0]` -- and the fifth, `True`, was silently accepted and
    read as level 1. All six thresholds were accepted or escaped: `None` and `"0.5"` raised
    `TypeError`, `True` was read as 1 and answered `[0, 1]`, `+inf` answered the WHOLE ballot and
    `-inf`/`nan` answered `[]`. A non-finite quantile is therefore a coverage statement that certifies
    everything or nothing, which is the failure `split_quantile`'s vacuity flag exists to catch.

    `TypeError` is the reason this is a guard and not a nicety: `cli.main` maps only
    `ReaderContractError`, `ArithmeticError` and `(OSError, ValueError)`, so a `TypeError` is exit code
    1 -- a class this project publishes as unreachable (`certificate.py:169-184` records exactly that
    fix for another module). `ValueError` is exit 2. Booleans are refused rather than read as 1,
    because a bool reaching a numeric slot is a caller bug and the answer it produces looks legitimate.
    """
    for bad in (None, 1.0, "1", [0], True):
        with pytest.raises(ValueError, match="gold_index must be a level index") as raised:
            score_ordinal([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad
    for bad in (None, "0.5", True):
        with pytest.raises(ValueError, match="threshold must be a real number") as raised:
            interval_set([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="threshold must be finite") as raised:
            interval_set([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad
    for bad in (None, 1.0, "1", [0], True):
        with pytest.raises(ValueError, match="gold_index must be a level index") as raised:
            score_ordinal([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad
    for bad in (None, "0.5", True):
        with pytest.raises(ValueError, match="threshold must be a real number") as raised:
            interval_set([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="threshold must be finite") as raised:
            interval_set([0.5, 0.5], bad)
        assert type(raised.value) is ValueError, bad


# --- the anchor's tie rule (finding M1) --------------------------------------------------------
#
# `mode_index` ties leftmost, the brief's Produces line makes that interface, and served
# probabilities are rounded to 4 decimals -- so a tie is a routine ballot. The review planted a
# rightmost implementation (`max(range(n), key=lambda i: (p[i], -i))`) and all eight shipped tests
# stayed green.


def test_the_anchor_ties_leftmost_and_that_choice_is_the_certified_level():
    """M1: the guard is on the CONSEQUENCE, because the helper alone guards nothing.

    `[0.4, 0.4, 0.2]` at the threshold 0.4 certifies the singleton `[0]`. Under a rightmost-tie
    `mode_index` the chain masses re-shape and it certifies `[1]` -- the same SIZE, so the automation
    rule `|C| == 1` still fires and the gate automates a DIFFERENT LEVEL. A test that only checked
    `mode_index(p) == 0` would not have caught the case that matters here, and a test that checked the
    set's SIZE would not either: what is pinned below is which level the family puts in the set.

    The second ballot puts the tie at the far end (`[0.1, 0.45, 0.45]` -> `[1]`, plant -> `[2]`) so a
    fix cannot special-case index 0. The last loop pins the other half of the published claim -- a
    singleton of this family IS the level `mode_index` names -- which is what `certify_score`'s
    `_score_rule` reads `options[C[0]]` off. It dies when the two anchors disagree: a module whose
    `chain_masses` anchors rightmost while `mode_index` still reports leftmost answers `[1]` for
    `[0.4, 0.4, 0.2]` while naming 0, and this loop is the only thing in the file that says so.
    """
    p = [0.4, 0.4, 0.2]                       # a 4-decimal-rounded server can ship this exactly
    assert mode_index(p) == 0
    assert chain_masses(p) == [0.4, 0.8, 1.0]
    assert interval_set(p, 0.4) == [0]        # the certified LEVEL, not merely its count
    assert len(interval_set(p, 0.4)) == 1
    assert interval_set(p, 0.8) == [0, 1]

    q = [0.1, 0.45, 0.45]
    assert mode_index(q) == 1
    assert interval_set(q, 0.45) == [1]
    assert len(interval_set(q, 0.45)) == 1

    for ballot in ([0.4, 0.4, 0.2], [0.1, 0.45, 0.45], [0.25, 0.25, 0.25, 0.25], [0.3, 0.3, 0.4]):
        anchor = mode_index(ballot)
        for threshold in (0.0, 0.25, 0.3, 0.4, 0.45, 0.5, 0.7, 1.0):
            C = interval_set(ballot, threshold)
            if len(C) == 1:
                assert C == [anchor], (ballot, threshold, C, anchor)


# --- the empty region (finding M2) -------------------------------------------------------------


def test_the_empty_set_is_the_refusal_region_and_the_modal_level_enters_at_its_own_mass():
    """M2: `mode-containing` is true of every NON-EMPTY result, and the empty region is reachable.

    Measured at `7931046` and unchanged by this round -- the fix here is the claim's domain, not the
    construction: `interval_set([0.6, 0.2, 0.2], 0.5)`, `interval_set([0.4, 0.35, 0.25], 0.05)` (the
    published rubric's own alpha) and `interval_set([0.9, 0.05, 0.05], 0.3)` all answer `[]`.

    The qualifier is a fact about the construction rather than an escape hatch, and the two sides below
    are what make it one: the level at which the set stops being empty is exactly the modal level's own
    chain mass, because every span `[min(g, mode), max(g, mode)]` contains the mode and non-negative
    masses make every chain mass at least the modal one. So emptiness is not a hole in the guarantee --
    it is the region where no level qualifies, and the first level to qualify is the mode.

    `[]` stays a RESULT and not an error, on evidence from the consumer: `certify_score` classifies it
    through `classify_set` -> "empty", counts it in `meta["empties"]`, submits no label (so
    `options[C[0]]` is never reached with an empty `C`), contributes a measure of 0 to
    `mean_interval_length`, and refuses with `Reason.EMPTY_FEASIBLE_SET` when nothing automates. On the
    gate's own synthetic population the region is routine: 24 of 600 evaluated records answer `[]` at
    the published alpha (seed 3, shift 0.0), and `tests/test_certify_score.py` already asserts
    `empties > 0` there. A family that refused instead would replace a counted refusal with an
    exception in the middle of a calibration loop.
    """
    assert interval_set([0.6, 0.2, 0.2], 0.5) == []
    assert interval_set([0.4, 0.35, 0.25], 0.05) == []
    assert interval_set([0.9, 0.05, 0.05], 0.3) == []

    # both sides of the modal chain mass, which is the first-entry threshold:
    p = [0.6, 0.2, 0.2]
    modal = chain_masses(p)[mode_index(p)]
    assert interval_set(p, modal - 1e-9) == []
    assert interval_set(p, modal) == [0]              # the mode is the only member
    assert interval_set([0.2, 0.2, 0.6], 0.6) == [2]  # and it is the mode, not index 0
    assert interval_set([0.5, 0.25, 0.25], 0.5) == [0]

    # the empty set keeps the other two properties -- nothing about it needs relaxing:
    for empty in ([], interval_set(p, 0.5), interval_set([0.4, 0.35, 0.25], 0.05)):
        assert is_contiguous(empty), empty


def test_no_non_empty_sublevel_set_ever_omits_the_modal_level():
    """M2's claim, asserted over the input class instead of sampled once.

    For every valid ballot and every threshold: the set is contiguous, nested in the threshold, and
    holds the modal level -- unless it is empty, in which case the threshold is below the modal chain
    mass. Both arms must be populated or the qualifier is doing no work: an all-non-empty sweep would
    pass on the docstring's original unconditional claim, and an all-empty one would pass on a module
    that always returns `[]`.

    Red under the plant that replaces `interval_set`'s body with the family R-68 rejected (the
    shortest contiguous span whose mass reaches the threshold): that construction is contiguous but
    answers `[2]` for `[0.5, 0.05, 0.45]` at 0.45 -- a non-empty set, holding the modal level nowhere
    in it. That is the plant the review measured as "3 failed, 5 passed", and it is why the domain
    qualifier names emptiness as the ONLY exception rather than hedging.
    """
    rng = random.Random(7)
    empties = holding = 0
    for _ in range(200):
        k = rng.randrange(2, 8)
        w = [rng.random() + 0.05 for _ in range(k)]
        s = sum(w)
        p = [x / s for x in w]
        mode = mode_index(p)
        modal = chain_masses(p)[mode]
        prev = []
        for q in sorted({round(x, 3) for x in p} | {0.0, modal, modal - 1e-9, 0.5, 0.9, 1.0}):
            C = interval_set(p, q)
            assert is_contiguous(C), (p, q, C)
            assert set(prev) <= set(C), (p, q, C, prev)
            prev = C
            if C:
                holding += 1
                assert mode in C, (p, q, C, mode)
            else:
                empties += 1
                assert q + TOL < modal, (p, q, C, modal)
    assert holding > 0 and empties > 0, (holding, empties)


def test_the_tolerance_is_what_keeps_the_whole_ballot_at_the_maximum_threshold():
    """m2: `TOL` now has an owner -- the hazard its comment describes is measured, not asserted.

    The review measured two things about this constant: setting `TOL = 0.0` left all eight shipped
    tests green, and over a 400-ballot sweep exactly 8 of 6,741 threshold pairs differ from the
    tolerance-free sublevel set, all of them at the maximum threshold where a ballot's chain masses sum
    to just over 1. This is that pair, pinned as a fixture: `[0.4, 0.2, 0.3, 0.1]`'s whole-ballot chain
    mass is `1.0000000000000002`, so at threshold 1.0 an exact `<=` answers `[0, 1, 2]` and drops the
    level whose chain mass IS the requested threshold -- a set that is nested-looking and wrong at its
    own boundary, exactly the comment's claim.

    The third line keeps the tolerance honest in the other direction: it is one ulp of slack, not a
    general fudge. At `1.0 - 1e-9` the same ballot still answers three levels, so a module that widened
    membership to "close enough" would be caught by the pair of lines rather than by either alone.
    """
    p = [0.4, 0.2, 0.3, 0.1]
    assert chain_masses(p) == [0.4, 0.6000000000000001, 0.9000000000000001, 1.0000000000000002]
    assert interval_set(p, 1.0) == [0, 1, 2, 3]
    assert interval_set(p, 1.0 - 1e-9) == [0, 1, 2]


