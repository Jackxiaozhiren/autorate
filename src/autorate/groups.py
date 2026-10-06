"""Group-conditional (Mondrian) splitting over the producer's own declared slice keys (spec §8.1).

A Mondrian bound is a bound *conditional on a group*, so the group has to come from somewhere the
evidence can name. Here it comes from the producer: `Record.slices` carries the slice keys an
upstream row actually states, and this module refuses to condition on any key that is not among
them. An invented key does not yield an empty grouping -- it yields a `KeyError` -- because a
group nobody can point at in the data is a denominator with no owner, and silence about the
condition a guarantee is valid under is the exact failure §8.1 exists to avoid.

The unit is the CASE, never the row (`case_count.case_key`; ledger R-36/R-44). Three repeats of one
case are one observation, so `group_counts` publishes BOTH `cases` and `records` and they are not
interchangeable: a per-group binomial denominator built from `records` would claim three times the
independent evidence the corpus holds, which is the failure the repository's case-vs-row rule
exists to prevent.

Leakage is checked rather than assumed away. A case whose repeats disagree about a declared key
would land in two groups at once, so the two groups each receive part of one observation and the
sum of the per-group `cases` exceeds the number of independent cases -- a denominator that quietly
double-counts. That is a bug in the producer's own row builder, and the only honest response is to
name the case and stop.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from .case_count import case_key
from .records import is_hashable_key

# "This record states no value for the declared key" must not be read as "the value it states is
# None": None is a value a producer can genuinely put in a slice dict, and collapsing the two makes
# a missing field indistinguishable from a null one -- the same mistake as a blank label deciding
# a quantile. A fresh `object()` rather than a sentinel STRING, because a string is a value the
# producer's own data can contain, and a group named like the marker would then read as a gap.
_ABSENT = object()


def _declared_keys(groups: Sequence[str]) -> tuple:
    """Validate the declaration itself and return it as a tuple of names.

    Every entry point runs this first, so a malformed declaration fails the same way whichever
    function received it, and never after a partial read of the data.
    """
    if isinstance(groups, str):
        raise ValueError(
            "groups must be a sequence of slice names, not one bare name: got %r. A string "
            "iterates character by character, so this would ask for the keys 'f', 'a', 'm'..."
            % (groups,))
    keys = tuple(groups)
    if not keys:
        raise ValueError(
            "no slice keys declared. A split conditioned on nothing is the MARGINAL, and the "
            "marginal already has an owner (a certificate with no groups); publishing it as a "
            "group would attach a condition to a number that has none")
    for key in keys:
        if not isinstance(key, str) or not key:
            raise ValueError("slice keys are non-empty names; got %r" % (key,))
    return keys


def _shown(value) -> str:
    """A slice value as a refusal message reads it."""
    return "absent" if value is _ABSENT else repr(value)


def _undeclared_message(key: str, records: Iterable) -> str:
    stated = sorted({k for r in records for k in r.slices})
    return ("%r is not a slice key the producer declared; this batch states %s. Conditioning on a "
            "key nobody set is a refusal, not an empty group"
            % (key, ", ".join(repr(k) for k in stated) if stated else "nothing"))


def _leakage_message(case, key: str, seen: dict) -> str:
    halves = "; ".join("%s on %s" % (_shown(v), ", ".join(ids)) for v, ids in seen.items())
    return ("case %s cannot be placed in one group: its records disagree about the declared slice "
            "key %r (%s). Splitting it would put one observation in two groups and count it twice "
            "in the per-group denominators, so the producer's slice assignment is what has to be "
            "fixed" % (case, key, halves))


def _unplaced_message(case, key: str, members: Sequence) -> str:
    return ("case %s states no value for the declared slice key %r, so it belongs to no group "
            "(records: %s). Leaving it out would shrink the denominator without saying so"
            % (case, key, ", ".join(r.id for r in members)))


def _unhashable_message(record, case, key: str) -> str:
    return ("the value of the declared slice key %r on record %s (case %s) is a %s, which cannot "
            "be a group key: a published group has to be nameable, and an unhashable value cannot "
            "even be a dict key here" % (key, record.id, case, type(record.slices[key]).__name__))


def group_key(record, groups: Sequence[str]) -> tuple:
    """The values of every declared slice key that `record` states, in the order declared.

    The raw tuple, always: one key gives a 1-tuple. The names `by_group` and `group_counts` publish
    collapse a 1-tuple to its value, because that is what a certificate and a report have to print
    -- §8.1's groups are named `km`, not `('km',)` -- and the collapse is pinned by
    tests/test_groups.py rather than left to the reader.

    `KeyError` when this record states no value for one of the keys: the domain of a Mondrian group
    is the producer's declared slices and nothing else.
    """
    keys = _declared_keys(groups)
    values = []
    for key in keys:
        if key not in record.slices:
            raise KeyError(_undeclared_message(key, (record,)))
        values.append(record.slices[key])
    return tuple(values)


def _grouped_by_case(recs: list, keys: tuple) -> dict:
    """Case key -> (group tuple, records), after refusing anything that cannot be placed once."""
    cases: dict = {}
    for r in recs:
        cases.setdefault(case_key(r), []).append(r)

    placed: dict = {}
    for case, members in cases.items():
        values = []
        for key in keys:
            seen: dict = {}
            for r in members:
                value = r.slices.get(key, _ABSENT)
                if value is not _ABSENT and not is_hashable_key(value):
                    raise ValueError(_unhashable_message(r, case, key))
                seen.setdefault(value, []).append(r.id)
            if len(seen) > 1:
                # `ValueError`, not `ArithmeticError`: nothing moved. The drift class would say a
                # number shifted under a regime change, and the reader would go looking for drift
                # instead of the producer bug this is -- an input record set that cannot be
                # partitioned, which is the usage class.
                raise ValueError(_leakage_message(case, key, seen))
            value = next(iter(seen))
            if value is _ABSENT:
                raise ValueError(_unplaced_message(case, key, members))
            values.append(value)
        placed[case] = (tuple(values), members)
    return placed


def by_group(records: Iterable, groups: Sequence[str]) -> dict:
    """Partition records into groups by CASE, and refuse a case that would split across two.

    A case's records all land in the same list, which is what makes a per-group `cases` count
    meaningful; the groups come back in the order their first case appeared, so a table built from
    them has one order instead of a hash's.

    `KeyError` when no record in the batch declares one of the keys (the producer never set it),
    `ValueError` when the batch declares a key but some case cannot be placed by it -- either its
    records disagree, or none of them states it.
    """
    keys = _declared_keys(groups)
    recs = list(records)
    for key in keys:
        if not any(key in r.slices for r in recs):
            raise KeyError(_undeclared_message(key, recs))
    out: dict = {}
    for values, members in _grouped_by_case(recs, keys).values():
        # The collapse is the published-name rule, not the tuple contract: `group_key` keeps
        # returning a 1-tuple. A list would not be a dict key at all, hence the explicit tuple.
        name = values[0] if len(values) == 1 else tuple(values)
        out.setdefault(name, []).extend(members)
    return out


def group_counts(records: Iterable, groups: Sequence[str]) -> dict:
    """Per group: how many independent CASES it holds and how many RECORDS stand for them."""
    grouped = by_group(records, groups)
    return {
        name: {
            # Exact only because `by_group` already refused a split case: a case in two groups would
            # be counted in both, and the sum over groups would exceed the number of observations
            # the bound is computed on.
            "cases": len({case_key(r) for r in members}),
            "records": len(members),
        }
        for name, members in grouped.items()
    }
