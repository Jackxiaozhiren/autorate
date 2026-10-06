"""Groups are declared by the producer and split by CASE, never by row.

The three tests the brief specifies are verbatim; the rest each guard one branch of the refusal
contract, because a grouping that cannot fail is a grouping whose numbers nobody can question.
"""
import pytest

from autorate.case_count import case_key
from autorate.groups import by_group, group_counts, group_key
from autorate.records import Record

from _records import choice_record


def test_a_case_with_three_repeats_contributes_one_case_and_three_records():
    recs = [choice_record(id="c%d-%d" % (i, r), case_id="c%d" % i, repeat=r,
                         slices={"family": "f%d" % (i % 2)})
            for i in range(4) for r in range(3)]
    counts = group_counts(recs, ("family",))
    assert counts == {"f0": {"cases": 2, "records": 6},
                      "f1": {"cases": 2, "records": 6}}, counts


def test_an_undeclared_slice_key_is_a_refusal_not_a_silent_group():
    recs = [choice_record(slices={"family": "f0"})]
    with pytest.raises(KeyError):
        by_group(recs, ("language",)), "conditioning on a key the producer never set"


def test_a_case_whose_repeats_disagree_about_a_slice_key_does_not_split_in_two():
    """The producer's own inconsistency must surface, because it would leak a case
    across two groups and quietly double-count it."""
    recs = [choice_record(id="a-0", case_id="a", slices={"family": "f0"}),
            choice_record(id="a-1", case_id="a", slices={"family": "f1"})]
    with pytest.raises(ValueError, match="case a"):
        by_group(recs, ("family",))


def test_the_leakage_refusal_names_the_key_and_both_records_not_only_the_case():
    """Naming the case is what makes the refusal findable; naming the key and the record ids is
    what makes it fixable, because the bug is in the producer's own row builder."""
    recs = [choice_record(id="a-0", case_id="a", repeat=0, slices={"family": "f0"}),
            choice_record(id="a-1", case_id="a", repeat=1, slices={"family": "f1"})]
    with pytest.raises(ValueError) as excinfo:
        by_group(recs, ("family",))
    text = str(excinfo.value)
    assert "family" in text, text
    assert "a-0" in text and "a-1" in text, text
    assert "'f0'" in text and "'f1'" in text, text


def test_a_case_lands_in_exactly_one_group_and_no_case_is_dropped():
    """The positive half of the leakage rule: the groups partition the batch's CASES.

    Dropping an unclassifiable case would shrink the denominator without saying so, which moves an
    automation rate in the flattering direction; the refusal below is what this assertion assumes.
    """
    recs = ([choice_record(id="c1-%d" % r, case_id="c1", repeat=r,
                           slices={"family": "f1", "mode": "fast"}) for r in range(2)]
            + [choice_record(id="c0-%d" % r, case_id="c0", repeat=r,
                             slices={"family": "f0", "mode": "slow"}) for r in range(3)])
    grouped = by_group(recs, ("family", "mode"))
    per_group = [{case_key(r) for r in members} for members in grouped.values()]
    assert per_group == [{"c1"}, {"c0"}], per_group
    assert [len(m) for m in grouped.values()] == [2, 3], "records travel with their case"
    assert list(grouped) == [("f1", "fast"), ("f0", "slow")], (
        "first appearance, so a printed table has one order and not a hash's")


def test_group_key_returns_the_declared_values_in_the_order_declared():
    """`group_key` is the raw tuple the interface promises, and its order is part of the key."""
    rec = choice_record(id="a-0", case_id="a", slices={"family": "f0", "language": "en"})
    assert group_key(rec, ("family", "language")) == ("f0", "en")
    assert group_key(rec, ("language", "family")) == ("en", "f0")
    assert group_key(rec, ("family",)) == ("f0",)
    with pytest.raises(KeyError):
        group_key(rec, ("mode",))


def test_one_declared_key_names_a_group_by_its_value_and_several_by_their_tuple():
    """The published group name is what a certificate prints, so a 1-tuple is collapsed.

    `group_key` keeps returning the tuple; only the dict keys of `by_group`/`group_counts` collapse,
    which is why spec §8.1's slices can be named in a report as `km` and not as `('km',)`.
    """
    a = choice_record(id="a-0", case_id="a", slices={"family": "f0", "language": "en"})
    b = choice_record(id="b-0", case_id="b", slices={"family": "f1", "language": "en"})
    assert list(by_group((a, b), ("family",))) == ["f0", "f1"]
    assert list(by_group((a, b), ("family", "language"))) == [("f0", "en"), ("f1", "en")]
    assert group_key(a, ("family",)) == ("f0",)


def test_a_case_that_states_no_value_for_a_declared_key_is_a_refusal_not_a_dropped_case():
    """Part of the batch declares the key, so this is not "never declared" -- and the case cannot
    be placed, so it must not be silently left out of the denominator."""
    recs = [choice_record(id="a-0", case_id="a", slices={"family": "f0"}),
            choice_record(id="b-0", case_id="b", slices={"mode": "fast"})]
    with pytest.raises(ValueError, match="case b") as excinfo:
        by_group(recs, ("family",))
    assert "family" in str(excinfo.value), str(excinfo.value)


def test_a_key_no_record_states_is_never_declared_while_a_gap_in_one_case_is_not():
    """The two refusals are different stories for the producer: `KeyError` means the caller asked
    for a condition the data never carries; `ValueError` means the data carries it unevenly."""
    recs = [choice_record(id="a-0", case_id="a", slices={"family": "f0"}),
            choice_record(id="b-0", case_id="b", slices={"mode": "fast"})]
    with pytest.raises(KeyError):
        by_group(recs, ("language",))
    with pytest.raises(ValueError, match="case b"):
        by_group(recs, ("family",))


def test_the_per_group_case_counts_add_up_to_the_batch_and_are_not_the_row_count():
    recs = [choice_record(id="c%d-%d" % (i, r), case_id="c%d" % i, repeat=r,
                          slices={"family": "f%d" % (i % 2)})
            for i in range(4) for r in range(3)]
    counts = group_counts(recs, ("family",))
    assert sum(c["cases"] for c in counts.values()) == len({case_key(r) for r in recs}) == 4
    assert sum(c["records"] for c in counts.values()) == len(recs) == 12
    assert all(c["cases"] < c["records"] for c in counts.values()), (
        "12 rows are 4 observations; a bound on the rows would claim three times the evidence")


def test_a_slice_value_that_cannot_be_a_dict_key_is_refused_before_the_grouping_raises():
    """A list-valued slice would otherwise escape as a bare `TypeError` from a dict insert, naming
    neither the case nor the key -- an unclassified library failure, which has no exit code here."""
    recs = [choice_record(id="a-0", case_id="a", slices={"family": ["f0", "f1"]})]
    with pytest.raises(ValueError, match="case a") as excinfo:
        by_group(recs, ("family",))
    assert "family" in str(excinfo.value), str(excinfo.value)


def test_an_empty_batch_names_no_groups_instead_of_one_empty_group():
    """A corpus filter that removed everything must not reach the caller as "0 groups".

    `by_group` could answer `{}` here, and a worst-of-G step downstream would then divide by a
    group count of zero or publish "worst of none" -- so the refusal is the same one the producer
    gets for any key nothing states.
    """
    with pytest.raises(KeyError):
        by_group([], ("family",))
    with pytest.raises(KeyError):
        group_counts((), ("family",))


def test_a_slice_whose_declared_value_is_none_is_a_group_of_its_own_not_a_missing_field():
    """"Absent" and "null" are two facts, and reading them as one hides a missing field.

    Collapsing the two -- `slices.get(key)` and treating None as the gap -- makes this record raise
    as unplaceable instead of forming the group it names, and a producer that states `family: null`
    would then be reported as one that states nothing.
    """
    recs = [choice_record(id="a-0", case_id="a", slices={"family": None}),
            choice_record(id="b-0", case_id="b", slices={"family": "f0"})]
    assert list(by_group(recs, ("family",))) == [None, "f0"]
    assert group_counts(recs, ("family",)) == {None: {"cases": 1, "records": 1},
                                               "f0": {"cases": 1, "records": 1}}
    assert group_key(recs[0], ("family",)) == (None,)


def test_the_group_declaration_must_be_a_sequence_of_names():
    """`--groups family,option_count` arrives as one string on its way to being a tuple; the
    failure mode is iterating it character by character and then reporting a KeyError for `f`."""
    recs = [choice_record(slices={"family": "f0"})]
    with pytest.raises(ValueError, match="family"):
        by_group(recs, "family")
    with pytest.raises(ValueError):
        by_group(recs, ())
    with pytest.raises(ValueError):
        by_group(recs, (1,))
    with pytest.raises(ValueError):
        group_counts(recs, ("",))
    with pytest.raises(ValueError):
        group_key(recs[0], ())


def test_the_shared_factory_builds_a_real_record_that_record_validation_still_owns():
    """The factory is not a stand-in: `Record`'s own gates run on every fixture it produces.

    A local object with the right attribute names would let an invalid decision into a certificate
    test, and the freeze at `records.py:119-121` is exactly the protection a shared factory must
    hand down rather than re-implement.
    """
    caller_dict = {"family": "f0"}
    rec = choice_record(id="a-0", case_id="a", repeat=1, slices=caller_dict)
    assert isinstance(rec, Record)
    caller_dict["family"] = "rewritten"
    assert rec.slices == {"family": "f0"}, "the record adopted the caller's dict"
    assert case_key(rec) == "a", "case_id is the field the grouping reads"
    assert case_key(choice_record(id="z9")) == "z9", "and falls back to the record id"
    assert rec.gold == "opt0" and rec.calibratable, "a bare call is a correct, labelled decision"
    assert rec.predicted is None, "a bare call states no answer; the rule owns that fallback"
    assert choice_record(gold=None).gold is None, "unlabelled stays expressible"
    with pytest.raises(ValueError):
        choice_record(probs=(0.6, 0.6))
    with pytest.raises(ValueError):
        choice_record(probs=(0.9, 0.1), gold="opt3")
