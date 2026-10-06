"""Modal-anchored chain sets: contiguous around the mode, nested by construction."""
import random

import pytest

from autorate.ordinal import interval_set, is_contiguous, score_ordinal


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

    A k-of-m top-mass set would pick {0,1,3} for the ballot below; the ordinal family
    must return a contiguous chain around the modal level instead, even where that costs
    an extra level.
    """
    p = [0.30, 0.34, 0.02, 0.30, 0.04]
    top_mass = sorted(range(5), key=lambda i: -p[i])
    greedy = sorted(top_mass[:3])                       # what mass-ordered CP returns
    assert greedy == [0, 1, 3] and not is_contiguous(greedy)
    ours = interval_set(p, sum(p[i] for i in greedy))   # same budget, chain construction
    assert is_contiguous(ours), ours
    assert sum(p[i] for i in ours) >= sum(p[i] for i in greedy) - 1e-12, (ours, greedy)


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
    assert score_ordinal(p, 2, 0.0) <= 0.9 + 1e-12


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

