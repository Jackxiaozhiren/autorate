"""The simultaneous correction: who owns the division, and what makes it not a decoration.

`correction.py` exists because a worst-of-G claim is a union bound, and a union bound has to divide
by a count somebody owns. Three such counts already live in this project and they are three
different numbers over three different claim sets (R-149): `certificate.N_CLAIMS` = 3 is the number
of envelopes ONE certificate claims in; `contamination.N_PIECES` = 4 is the number of strata
combined into ONE delta-hat; and the number here is `len(by_group)`, which the data decides and no
constant may stand in for. Most of this file's tests are about keeping those three apart.

The brief's own falsification is the first row: at `n_groups == 1` the uncorrected level comes back,
and at 8 groups the corrected level is strictly smaller.
"""
from __future__ import annotations

import pytest

from autorate.certificate import N_CLAIMS
from autorate.correction import (CORRECTED_CLAIMS, GROUP_FLOOR_MESSAGE, bonferroni,
                                 corrected_delta, group_alpha, group_beta, joint_level,
                                 min_violations, size_floor, worst_group)
from autorate.groups import by_group
from autorate.report import ALPHA, BETA, RECORDS, load_records
from autorate.tails import clopper_pearson_upper


def test_bonferroni_divides_by_the_slice_count_and_nothing_else():
    assert bonferroni(0.05, 8) == pytest.approx(0.05 / 8)
    assert bonferroni(0.05, 51) == pytest.approx(0.05 / 51)
    assert bonferroni(0.05, 1) == pytest.approx(0.05)


def test_the_correction_is_not_a_no_op_constant():
    """One group is uncorrected; eight is strictly smaller; and it moves with the DATA count.

    The divisor is called with 2, 3, 8 and 51 slice counts. Three of those four are not any constant
    this project owns, so no implementation that substitutes `N_CLAIMS` (3) or `N_PIECES` (4) for the
    slice count survives this row -- which is the R-149 under-correction made expensive here rather
    than only in prose.
    """
    assert bonferroni(0.05, 1) == pytest.approx(0.05), "one group has nothing to correct"
    assert bonferroni(0.05, 8) == pytest.approx(0.00625)
    levels = [bonferroni(0.05, g) for g in range(1, 9)]
    assert all(b > c for b, c in zip(levels, levels[1:])), (
        "strictly smaller at every added group, not 'smaller on average'")
    assert bonferroni(0.05, 2) != pytest.approx(bonferroni(0.05, N_CLAIMS))
    assert bonferroni(0.05, 51) != pytest.approx(bonferroni(0.05, 4)), (
        "the stratum count belongs to the contamination probe, not to a slice census")


def test_the_division_is_exact_so_no_canonicalisation_is_needed_and_none_is_applied():
    """R-127 (one owner per precision): a corrected LEVEL needs no canonical pass, because IEEE 754
    requires `/` to be correctly rounded and both sides of this assertion compute the same quotient.
    The bounds the corrected level FEEDS are canonicalised at their own call sites, by
    `certificate.canonicalise_bound`; a plant that puts a corrected level through it is in the report
    (the endpoint moves 2.6e-17 upward, which is the wrong direction for a bound and buys nothing).
    """
    assert bonferroni(0.05, 8) == 0.05 / 8
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 8, n_claims=3) == 1.0 - 8 * 3 * (0.05 / 8)


def test_the_three_claim_sets_stay_three_numbers():
    """R-149 as an executable rule, not prose.

    GREEN-ON-ARRIVAL. `certificate.N_CLAIMS` and `contamination.N_PIECES` are imported, not read as
    text, so this row is an import-time bridge between three separately-owned constants and not a
    duplicate of them. It reddens when any of the three counts changes without the others being
    re-read: the 3 is what `joint_level` multiplies (one slice's envelopes), the 4 is what
    `contamination` divides a `delta_hat` by (one probe's strata), and neither is the divisor here.
    A plant that substitutes either constant for the slice count cannot be caught by this row while
    the fixture runs 3 slices -- that plant needs a count the data produced, and the drift that
    reddens it lives in `tests/test_mondrian.py`, where the fixture runs 2.
    """
    assert N_CLAIMS == 3, "the envelope count is the number this correction must never inherit"
    assert CORRECTED_CLAIMS == N_CLAIMS, (
        "a slice publishes the same three envelopes a pooled certificate does; if the shape grows a "
        "claim, `joint_level`'s product and this row change together")


def test_the_slice_count_is_data_dependent_and_the_certification_lane_uses_it():
    """The real corpus's slice count is not any constant in the project: 8 families, 16 cases each.

    GREEN-ON-ARRIVAL: green at step 1 because `by_group` is shipped and unmodified, and this row
    measures the committed archive. It reddens the moment the census and the records part company
    (a `by_group` whose grouping changes, or a committed records file whose `slices` change), and it
    is the divisor the certification call site actually passes -- asserted at the call site in
    `tests/test_mondrian.py`, which also plants `N_CLAIMS` there and must go red.
    """
    recs = load_records(RECORDS)["laya"]
    n_groups = len(by_group(recs, ("family",)))
    assert n_groups == 8, "eight families, and neither 3 (envelopes) nor 4 (strata) divides here"
    assert bonferroni(0.05, n_groups) == pytest.approx(0.00625)
    assert n_groups != N_CLAIMS, "the divisor this correction takes is the census, not the envelope"
    assert group_alpha({"alpha": ALPHA, "beta": BETA}, n_groups) == (ALPHA, ALPHA / 8)


def test_an_empty_split_and_a_non_integer_count_are_refused_before_the_division():
    """Red first: `bonferroni(0.05, 0)` raised `ZeroDivisionError` and every other mode below a
    `TypeError` -- rc 1, outside this project's 0/2/3/4 contract (R-115). All `ValueError` now.
    """
    for bad_n in (0, -1, 2.5, "8", None, True):
        with pytest.raises(ValueError):
            bonferroni(0.05, bad_n)


def test_a_level_that_is_not_a_probability_is_refused_by_name_not_by_a_silent_division():
    """Red first: 0.0 bought a corrected level of 0.0 (an invisible no-correcting), NaN and inf
    passed the chained comparison `0 < v < 1` (neither arm true), and `"0.05"` was silently
    `float`-ed into a level nobody typed -- `alpha` reaches the CLI as text."""
    for bad_alpha in (0.0, 1.0, 1.5, -0.05, float("nan"), float("inf"), "0.05", None):
        with pytest.raises(ValueError):
            bonferroni(bad_alpha, 8)


def test_the_floor_predicate_refuses_a_non_numeric_count_or_floor():
    """Red first: `size_floor(19, "20")` raised `TypeError: '<' not supported between instances of
    'int' and 'str'`, and `min_violations("km", floor=20)` iterated the characters of the string."""
    for bad_floor in ("20", None, -1, 2.5, True):
        with pytest.raises(ValueError):
            size_floor(19, bad_floor)
    for bad_count in ("19", None, True):
        with pytest.raises(ValueError):
            size_floor(bad_count, 20)
    with pytest.raises(ValueError):
        min_violations("km", floor=20)
    assert size_floor(19, 20) is True and size_floor(20, 20) is False


def test_the_floor_is_inclusive_and_the_predicate_and_the_census_never_disagree():
    counts = [{"group": "km", "n_cases": 4}, {"group": "de", "n_cases": 900},
              {"group": "sw", "n_cases": 52}]
    assert [row["group"] for row in min_violations(counts, floor=20)] == ["km"], (
        "the census names the refused slices, in the order the census gave them")
    # One rule, two spellings: a census row is refused exactly when the predicate says it is.
    assert [row["group"] for row in min_violations(counts, floor=20)] == [
        row["group"] for row in counts if size_floor(row["n_cases"], 20)]
    # A census row that states no count is a census bug; it used to escape as `KeyError` -> rc 1.
    with pytest.raises(ValueError, match="n_cases"):
        min_violations([{"group": "km"}], floor=20)


def test_the_group_levels_read_from_the_slice_rubric_and_not_from_the_pooled_one():
    for name, fn in (("group_alpha", group_alpha), ("group_beta", group_beta)):
        assert fn({"alpha": 0.05, "beta": 0.05}, 8) == (0.05, 0.05 / 8)
        with pytest.raises(ValueError):
            fn({}, 8)
        with pytest.raises(ValueError):
            fn({"alpha": 0.05}, 8)
        with pytest.raises(ValueError):
            fn("alpha", 8)
    assert group_alpha({"alpha": 0.05, "beta": 0.05}, 8)[0] == 0.05, (
        "the uncorrected level is published beside the corrected one so a reader can see the work")
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 8, n_claims=3) == pytest.approx(
        1.0 - 8 * 3 * (0.05 / 8))
    # One group is exactly the uncorrected joint level a pooled certificate already publishes.
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 1, n_claims=3) == pytest.approx(
        1.0 - N_CLAIMS * 0.05)
    assert corrected_delta(0.05, 8) == pytest.approx(0.05 / 8)
    assert corrected_delta(0.05, 1) == pytest.approx(0.05)
    # The product, not the division, is where a simultaneous claim stops being a probability.
    with pytest.raises(ValueError, match="not a probability"):
        joint_level({"alpha": 0.5, "beta": 0.5}, 1)


def _slice(name, autorate=None, feasible=None, conditional=None, n_cases=100, detail=None):
    """One slice's published row, in the shape `worst_group` reads from a certificate's meta."""
    meta = {"slices": name, "n_eval_cases": n_cases}
    if detail:
        meta["detail"] = detail
    return {"group": name, "feasible": feasible if feasible is not None else autorate is not None,
            "autorate": autorate, "conditional_error_bound": conditional, "meta": meta}


def test_a_refused_slice_is_the_worst_and_is_attributed_only_to_the_reason_that_is_evidence():
    groups = [_slice("km", feasible=False, n_cases=4, detail="at coverage 0.950 no evaluation case "
                                                             "produced a singleton set"),
              _slice("de", autorate=0.0, conditional=0.0, n_cases=900)]
    worst = worst_group(groups, metric="autorate", floor=20)
    assert worst["any_slice_refused"] is True
    assert worst["worst"]["autorate"] is None
    assert worst["refusals"][0]["group"] == "km" and worst["refusals"][0]["n"] == 4
    assert GROUP_FLOOR_MESSAGE in worst["refusals"][0]["why"], (
        "a size-floor refusal has to be attributable to the size floor, since that is the one reason "
        "a group-conditional certificate refuses that the pooled one cannot produce")
    # The same slice NOT below the floor: the refusal is a slice-level finding and must not be
    # re-labelled as a slice-structure story. Reddened by a plant that attributes every refusal to
    # the floor (the report's plant row).
    fat = worst_group([_slice("km", feasible=False, n_cases=900, detail="budget exceeded")],
                      metric="autorate", floor=20)
    assert fat["any_slice_refused"] is True
    assert "NOT attributed to the slice structure" in fat["refusals"][0]["why"]
    assert GROUP_FLOOR_MESSAGE not in fat["refusals"][0]["why"]


def test_worst_group_is_the_sliced_maximum_and_never_a_restatement_of_the_pooled_one():
    groups = [_slice("de", autorate=0.0, conditional=0.0, n_cases=900),
              _slice("sw", autorate=0.625, conditional=0.477, n_cases=52),
              _slice("en", autorate=0.7, conditional=0.2, n_cases=200)]
    worst = worst_group(groups, metric="autorate")
    assert worst["worst"]["group"] == "de"
    assert worst["refusals"] == [] and worst["any_slice_refused"] is False
    # The pooled 95%-coverage rate of the very population these three slices were cut from is
    # 0.367769 (measured; Step 2 publishes the pair from the artefact as `pooled_vs_slices`).
    # GREEN-ON-ARRIVAL: `_worst_row` already takes the maximum over the rows it is handed, so no
    # plant on this file reddens this line -- the drift it pins (a pool reading as comfort while a
    # slice refuses) is constructed for real in `tests/test_mondrian.py`.
    assert worst["worst"]["autorate"] < 0.367769, "the worst slice must not be averaged away"
    assert [row["group"] for row in worst["groups"]] == ["de", "sw", "en"]
    # The risk side of the same claim, and the two ways this reading can stop being honest.
    #
    # The retired expectation on this line was `"en"`. It contradicted the module's own documented
    # rule (`correction.py:49-54`: "the slice whose bound is HIGHEST is the worst on a risk column",
    # and `_METRICS["conditional"] = (…, "max")`), the real corpus the fixture mirrors (the brief
    # publishes `sw` at observed 0.333 / bound 0.477 against `de` at 0 automated), and §8.1's reason
    # for existing ("a 'worst of 51 languages' number is a false claim" -- naming a mid-pack slice
    # worst is that same false claim inside the tool). So the expected VALUE was corrected, not
    # relaxed: the row still pins one exact group, and it would go red on a plant that flips
    # `_METRICS["conditional"]` to `"min"` or that sorts by `n_cases` instead of by the bound.
    assert worst_group(groups, metric="conditional")["worst"]["group"] == "sw"
    marginal = worst_group(groups, metric="marginal")
    assert marginal["any_slice_refused"] is True, (
        "marginal bounds are not published on these rows: a metric with nothing to compare must "
        "refuse rather than rank a column of None")
    # ...and the refusal is attributed to the missing column, not to a certification refusal that
    # never happened. Without this field a reader of `any_slice_refused` would go looking for a
    # slice the certifier turned down.
    assert [row["group"] for row in marginal["groups"]] == marginal["slices_without_the_metric"]
    assert all("marginal_error_bound" in row["why"] for row in marginal["refusals"])
    assert all(row["reason"] is None for row in marginal["refusals"]), (
        "these slices were never refused: they simply publish nothing on the column asked about")
    assert worst_group(groups, metric="autorate")["slices_without_the_metric"] == []
    with pytest.raises(ValueError, match="unknown worst-slice metric"):
        worst_group(groups, metric="n_cal")
    with pytest.raises(ValueError, match="worst-of-0"):
        worst_group([], metric="autorate")
    with pytest.raises(ValueError, match="no case count"):
        worst_group([{"group": "km", "feasible": True, "autorate": 0.5}], metric="autorate")


def _claim_rows():
    """Two slices carrying the rubric the way `certify_choice`'s meta does, so the claim is derivable.

    Constructed, not read off the corpus: the point of these rows is the arithmetic the artefact
    states, and a fixture that had to wait for a real group-conditional run could not be written
    before it. The levels are the published rubric (`report.ALPHA`, `report.BETA`).
    """
    rows = [_slice("de", autorate=0.0, conditional=0.0, n_cases=900),
            _slice("sw", autorate=0.625, conditional=0.477, n_cases=52)]
    for row in rows:
        row["meta"].update({"alpha": 0.05, "beta": 0.05, "delta": 0.05})
    return rows


def test_the_artefact_states_the_rule_and_the_envelope_count_so_0_85_can_be_rebuilt():
    """R-159's standing requirement: a reader holding a bare 0.85 must be able to reconstruct it.

    Red first (the artefact published `alpha`, `beta` and `n_groups` but no `n_claims` and no rule,
    so 0.85 was reconstructible only by guessing whether the multiplier was 2 or 3, and whether the
    two budgets combined by `max` or by `alpha + beta` -- the two readings differ, 0.85 vs 0.90).
    """
    worst = worst_group(_claim_rows(), metric="autorate")
    assert worst["joint_level"] == pytest.approx(
        1.0 - worst["n_claims"] * max(worst["alpha"], worst["beta"])), (
        "the number, the multiplier and the combination rule all have to be on the page")
    assert worst["n_claims"] == CORRECTED_CLAIMS == N_CLAIMS, (
        "the envelope count is stated, not inherited silently from the shape")
    assert worst["n_groups"] == 2 and worst["joint_level_inputs"]["n_groups"] == 2
    assert worst["joint_level_risk"] == pytest.approx(
        worst["n_groups"] * worst["n_claims"] * max(worst["joint_level_inputs"]["corrected_alpha"],
                                                    worst["joint_level_inputs"]["corrected_beta"]))
    assert "max" in worst["joint_level_rule"] and "n_claims" in worst["joint_level_rule"], (
        "the rule is named where the number is, because a bare 0.85 does not say which rule made it")
    # A reader with ONLY the artefact's own fields, no source code:
    rebuilt = 1.0 - worst["n_claims"] * max(worst["alpha"], worst["beta"])
    assert rebuilt == pytest.approx(worst["joint_level"])
    # And the §5.3 pair alone -- two envelopes, not three -- is a DIFFERENT claim set, which is why
    # the multiplier has to be published: 1 - (alpha + beta) = 0.90 is that claim's level at this
    # rubric, and it is not what a three-envelope run is allowed to print.
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 2, n_claims=2) == pytest.approx(0.90)
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 2, n_claims=3) == pytest.approx(0.85)


def test_slices_certified_at_different_levels_are_not_one_worst_of_g_claim():
    """One claim, one rubric: a worst-of-G over two rubrics would state one level for two budgets.

    Green on arrival against the shipped `joint_level` (it is a pure function of its inputs); it
    reddens under a `worst_group` that reads the rubric off `rows[0]` only -- which is what the
    inherited code did, so a run whose slices disagree published the first slice's budgets as the
    family's. The plant named in the report replaces the agreement check with `rows[0]` and reddens
    this row while every other row in the file stays green.
    """
    rows = _claim_rows()
    rows[1]["meta"]["beta"] = 0.20
    with pytest.raises(ValueError, match="one simultaneous claim"):
        worst_group(rows, metric="autorate")
    # And a rubric the artefact cannot see is stated as unavailable, never invented from a default.
    bare = worst_group([_slice("de", autorate=0.0, conditional=0.0, n_cases=900)], metric="autorate")
    assert bare["joint_level"] is None
    assert "no" in bare["joint_level_note"].lower()
    assert bare["joint_level_rule"]  # the rule is still named, so the gap is auditable


def test_the_joint_level_is_constant_in_g_because_that_is_what_the_correction_buys():
    """R-158/R-159: the retired row asserted `joint_level(G=2) != joint_level(G=3)`, i.e. 0.85 != 0.85.

    That is the opposite of what a Bonferroni correction is for. `joint_level` divides each slice's
    budget by `G` and multiplies the sum back by `G`, so `G` cancels:

        1 - G*n_claims*max(alpha/G, beta/G)  ==  1 - n_claims*max(alpha, beta)

    because dividing both arguments of a `max` by the same positive number cannot change which one
    is larger -- no arithmetic luck, no dependence on `alpha == beta`. The family-wise level therefore
    stays fixed as slices are added, and that is the claim §8.1 needs: "without the correction, a
    'worst of 51 languages' number is a false claim". The correction's job is to keep the level where
    it was while 51 divides; an implementation made G-dependent to turn the old row green would
    publish a joint confidence that decays with the census, which is an *under*-claim that moves on
    its own.

    Measured on this machine over rubrics chosen so the `max()` arm switches sides -- `alpha > beta`
    and `beta > alpha`, not only the retired row's `alpha == beta` -- and over `G` in {1,2,3,7,51}:
    the closed form matches exactly for most pairs, and at most 1.11e-16 (one ULP of 0.4) apart for
    `(0.05, 0.20)` at `G=3` and `(0.19, 0.01)` at `G=7`, because `alpha/G` is not representable for
    every pair. The tolerance below IS that measurement: distinct rubrics here differ by >= 0.02, so
    a hundredth of a percent of it still separates the cancellation from any real drift.

    GREEN-ON-ARRIVAL against the shipped `joint_level`, which this ruling leaves alone. Plants that
    redden it (both run, both reported): `worst = max(alpha, beta)` (correct nothing -- the level
    then decays with `G` and every row here except `G=1` goes red), and
    `worst = _divide(alpha, g)` (correct only `alpha`, which §8.1's literal "Bonferroni on alpha"
    would license and §5.3's two-way construction does not: it reddens on every rubric where
    `beta > alpha`).
    """
    rubrics = ((0.05, 0.05), (0.05, 0.20), (0.20, 0.05), (0.02, 0.03), (0.19, 0.01), (0.01, 0.19))
    for alpha, beta in rubrics:
        for claims in (2, 3):
            closed = 1.0 - claims * max(alpha, beta)
            seen = [joint_level({"alpha": alpha, "beta": beta}, g, n_claims=claims)
                    for g in (1, 2, 3, 7, 51)]
            for g, level in zip((1, 2, 3, 7, 51), seen):
                assert level == pytest.approx(closed, abs=1e-15), (
                    "(%.2f, %.2f) over %d claims at G=%d: the level moved with the slice count, "
                    "which is the failure §8.1 names" % (alpha, beta, claims, g))
            assert max(seen) - min(seen) <= 1e-15, (
                "the whole spread across G must sit inside float noise, not inside a tolerance")
    # The `max()` arm genuinely switches across these rubrics, so the row is not three copies of one
    # fixture: alpha-wins, beta-wins and tied are all present, and the closed form is the same number
    # whichever arm is taken.
    assert max(0.05, 0.20) != min(0.20, 0.05) + 0.1
    assert joint_level({"alpha": 0.05, "beta": 0.20}, 7) == joint_level({"alpha": 0.20,
                                                                        "beta": 0.05}, 7)


def test_the_correction_uses_the_slice_count_a_pooled_certificate_never_has():
    """The name the retired row carried, kept for the proposition it was reaching for.

    R-158/R-159 superseded this row's *assertion* (`joint_level(G=2) != joint_level(G=3)`); the
    claim its title makes is true and is what the correction actually does with the slice count.
    A pooled certificate has one `n` and never divides by a census; a group-conditional run divides
    each slice's budget by `len(by_group)`, and the slice count then reappears as the *width* of the
    bound and as the floor that refuses thin slices by name. See
    `test_the_joint_level_is_constant_in_g_because_that_is_what_the_correction_buys` for the half
    that must NOT move.

    Reddened by: a `bonferroni` that ignores its second argument (every corrected budget here is
    then flat), and a `joint_level` that stops multiplying by `n_groups` (the last line goes red).
    """
    for name, fn in (("alpha", group_alpha), ("beta", group_beta)):
        corrected = [fn({"alpha": 0.05, "beta": 0.05}, g)[1] for g in (1, 2, 3, 7, 51)]
        assert all(b > c for b, c in zip(corrected, corrected[1:])), (
            "%s's corrected budget must shrink strictly as slices are added" % name)
        assert corrected[0] == 0.05, "one slice has nothing to correct"
    assert [corrected_delta(0.05, g) for g in (1, 2, 51)] == [0.05, 0.025, 0.05 / 51]
    assert [bonferroni(0.05, g) for g in (1, 2, 51)] == [0.05, 0.025, 0.05 / 51]

    # The bound width, at an IDENTICAL observed error rate (1/16 == 8/128): the thinner slice the
    # census made pays a wider bound, and that is where a worst-of-G loses its power.
    pooled = clopper_pearson_upper(8, 128, 0.05)
    sliced = clopper_pearson_upper(1, 16, 0.05)
    assert sliced > pooled, (
        "equal rates, unequal evidence: 16 cases cannot bound what 128 bound")
    assert joint_level({"alpha": 0.05, "beta": 0.05}, 8) == joint_level({"alpha": 0.05,
                                                                        "beta": 0.05}, 1), (
        "the level is where the constancy lives while the width moves through n")

    # And the refusal is by name, at the floor, in census order.
    census = [{"group": "en", "n_cases": 900}, {"group": "sw", "n_cases": 52},
              {"group": "km", "n_cases": 4}]
    assert [row["group"] for row in min_violations(census, floor=60)] == ["sw", "km"]
    assert min_violations(census, floor=60)[1]["n_cases"] == 4
    assert [row["group"] for row in min_violations(census, floor=20)] == ["km"]
    # Neither constant this project owns is a slice count here (R-149, the real census's 8).
    recs = load_records(RECORDS)["laya"]
    n_groups = len(by_group(recs, ("family",)))
    assert n_groups not in (N_CLAIMS, 4)
    assert group_alpha({"alpha": ALPHA, "beta": BETA}, n_groups)[1] == ALPHA / n_groups
