"""Task 6a: nonconformity scores. All scores are in [0,1], so a quantile above 1 is vacuous."""
from autorate.conformal import conformal_set, is_singleton
from autorate.nonconformity import aps_score, lac_score

# The real archived vector from feishu_zh lifecycle-05/repeat=1 (4 decimals, near tie).
P4 = (0.2955, 0.2984, 0.2973, 0.1087)


def test_aps_top_label_score_is_the_randomised_prefix_only():
    assert aps_score(P4, 1, 0.0) == 0.0
    assert abs(aps_score(P4, 1, 1.0) - 0.2984) < 1e-9


def test_aps_is_monotone_along_mass_order():
    order = sorted(range(4), key=lambda j: -P4[j])
    scores = [aps_score(P4, j, 0.0) for j in order]
    assert scores == sorted(scores)


def test_scores_stay_in_the_unit_interval_for_every_option():
    for j in range(4):
        for u in (0.0, 0.37, 0.999):
            s = aps_score(P4, j, u)
            assert 0.0 <= s <= 1.0, (j, u, s)


def test_the_set_is_contiguous_in_sorted_mass_by_construction():
    got = conformal_set(P4, 0.3, 0.0, "aps")
    ordered = sorted(got, key=lambda j: -P4[j])
    positions = sorted(range(4), key=lambda j: -P4[j])
    assert [positions.index(j) for j in ordered] == list(range(len(ordered)))


def test_lac_and_aps_disagree_on_the_same_vector_so_method_is_a_declared_choice():
    assert lac_score(P4, 0) != aps_score(P4, 0, 0.0)
    assert lac_score(P4, 2) != aps_score(P4, 2, 0.0)


def test_ties_sharing_one_u_admit_all_or_none_because_the_family_is_nested():
    p = (0.5, 0.5)
    assert aps_score(p, 0, 0.0) == 0.0 and aps_score(p, 1, 0.0) == 0.0
    assert aps_score(p, 1, 0.5) == 0.25
    assert conformal_set(p, 0.0, 0.0, "aps") == [0, 1]
    assert conformal_set(p, 0.2, 0.5, "aps") == []


def test_is_singleton_only_for_exactly_one_label():
    assert is_singleton([2]) is True
    assert is_singleton([]) is False
    assert is_singleton([0, 1]) is False


def test_an_extreme_sharp_answer_gives_a_singleton_under_a_loose_quantile():
    p = (0.97, 0.01, 0.01, 0.01)
    assert conformal_set(p, 0.5, 0.4, "aps") == [0]
    assert is_singleton(conformal_set(p, 0.5, 0.4, "aps")) is True


def test_unknown_method_is_rejected_rather_than_silently_defaulting():
    import pytest

    with pytest.raises(KeyError):
        conformal_set(P4, 0.5, 0.0, "crc")
