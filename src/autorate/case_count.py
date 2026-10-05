"""The case arithmetic both certifiers share: one rule, one counter (R-34, R-66).

`certify_choice` and `certify_threshold` apply different rules to the same records -- an
APS singleton set versus `score >= lambda` -- and both then have to answer the same three
questions: which decisions ran unattended, which ANSWER each of those put forward, and how
many INDEPENDENT CASES (never archive rows: ledger R-36/R-44) each of those counts covers.
Answering them twice is how a published automation rate comes to describe a rule the
deployment does not apply, so the answers are computed once, here.

This module knows nothing about sets or thresholds. It receives ONE `decide` callable and asks
it for a verdict (R-66, which supersedes the plan's R-53 `(half, kind, measure=None)` shape):
what the rule did with one record, the label the rule would put forward when it automates, and
the rule's own per-record quantity. The counter compares the SUBMITTED label to gold and
nothing else, because it has no reading of "what the rule submitted" of its own -- that is what
the deleted `decision_is_wrong` was: a guess, shared by two rules that do not share an answer.
`certify_choice` submits the label inside its certified singleton (`gate.py:66-67` delivers
`options[C[0]]`); `certify_threshold` submits the answer the record states. On the committed
archive those two readings and the guess all coincide -- `predicted == argmax` on 383/383
calibratable choice records, with zero ties at the maximum probability -- which is why the guess
moved no published number; on constructed data they diverge in both directions, and one of those
directions LOOSENS a bound (1.0000 -> 0.9500). Agreement by coincidence of the data is not
ownership.

It returns `mean_measure`, never `mean_set_size` or `mean_score`: the shared arithmetic does not
name a published figure, because a figure needs exactly one owner. Each certifier publishes the
mean under its own name -- in the certificate's mean slot, and in `meta` where the gate has one.
"""
from __future__ import annotations

from typing import Callable, NamedTuple, Optional, Sequence

# The outcome vocabulary. `auto` is the decision to run unattended; `empty` and `multi`
# are the set rule's two ways of not doing that, kept separate because both are PUBLISHED
# (`empties`, `multi_label`); `refuse` is the fourth bucket the threshold gate needs --
# its non-automated decision is neither an empty set nor a multi-label one, and borrowing
# either name would write a false statement into `empties`/`multi_label` on a certificate.
# The names are published buckets, not set vocabulary: only `certify_choice` translates
# `classify_set`'s "escalate" into "multi", which is that rule's business, never this one's.
KINDS = ("auto", "empty", "multi", "refuse")
AUTO = "auto"


class Verdict(NamedTuple):
    """What one rule did with one record (R-66).

    `outcome` is a name in `KINDS`; `submitted` is the label the rule WOULD put forward when
    `outcome == "auto"`, and None when it does not automate; `measure` is the rule's own
    per-record quantity (set size, score value) or None when this record carries none. A rule
    may return this type or any 3-tuple in the same order -- the shape is the contract, not
    the class.
    """

    outcome: str
    submitted: Optional[str]
    measure: Optional[float]


def case_key(record) -> str:
    """The identity of the independent observation a record belongs to.

    Lives here because grouping by it is what the counter does. The domain is unchanged
    from the extraction: `case_id`, else the record id. Changing which strings are keys
    re-rolls every seeded split and moves every published bound, so this is not a
    two-line function -- it is the partition the corpus certificates were measured on.
    """
    return record.case_id or record.id


def count_outcome(half: Sequence, decide: Callable[[object], Verdict]) -> dict:
    """Apply one rule to one half, counting RECORDS and the CASES they stand for.

    A case is automated only when every one of its records automates -- running a case
    unattended means running all of it -- and it is erroneous when any automated record in
    it put forward a label that is not the gold one. Those two buckets are exhaustive, so
    `automated_cases + refused_cases == n_cases` and refusal = 1 - autorate hold at the unit
    the bound is computed on. Record counts stay because they are what the gate acts on; they
    are not a binomial denominator, because repeats of one case are one observation (the
    committed archive measures it: laya's three records per case carry byte-identical
    probability vectors, scores and gold labels, though not identical rows -- pinned by
    tests/test_report_prose.py).

    Right and wrong are decided exactly one way: `submitted != record.gold`. `decide(record)`
    must return a verdict whose `outcome` is a name in `KINDS` -- anything else is a rule this
    counter does not know, and it raises rather than choosing a bucket for it -- and must name
    the label it submits whenever it automates, because an automated decision with no answer
    cannot be compared to gold at all. Neither is guessed here: the reading that used to be
    (`predicted`, falling back to argmax) was one rule's answer imposed on the other.

    `measure` is averaged over the records whose verdict CARRIED one: a verdict with
    `measure=None` is out of the numerator and out of the denominator, so a gate whose field is
    absent on some records publishes a mean of the values that exist and names the excluded
    count beside it (`missing_score`) rather than letting an absent value decide the average.
    """
    autom = err = empties = multi = refused = 0
    measure_sum = 0.0
    measured = 0
    cases = {}
    for r in half:
        outcome, submitted, measure = decide(r)
        if outcome not in KINDS:
            raise ValueError("unknown outcome kind %r; count_outcome knows %s"
                             % (outcome, ", ".join(KINDS)))
        if outcome == AUTO:
            if submitted is None:
                raise ValueError("a rule that automates must name the label it submits: %s "
                                 "automates record %r while submitting nothing, so there is "
                                 "nothing to compare with gold" % (decide, r.id))
            if r.gold is None:
                raise ValueError("a record with no gold label cannot be counted right or wrong; "
                                 "filter it before counting (certify_choice's eligibility rule does)")
        if measure is not None:
            measure_sum += float(measure)
            measured += 1
        wrong = outcome == AUTO and submitted != r.gold
        if outcome == "empty":
            empties += 1
        elif outcome == "multi":
            multi += 1
        if outcome == AUTO:
            autom += 1
            if wrong:
                err += 1
        else:
            refused += 1
        g = cases.setdefault(case_key(r), {"decisions": 0, "automated": 0, "wrong": 0})
        g["decisions"] += 1
        if outcome == AUTO:
            g["automated"] += 1
            if wrong:
                g["wrong"] += 1
    auto_cases = [g for g in cases.values() if g["automated"] == g["decisions"]]
    out = {"automated": autom, "errors": err, "empties": empties, "multi_label": multi,
           "refused": refused, "n_cases": len(cases), "automated_cases": len(auto_cases),
           # `refused_cases` is derived, so `automated_cases + refused_cases == n_cases` is an
           # arithmetic identity rather than a partition check: it is kept because a published
           # bucket must be nameable, and the per-case RULE that makes it true is guarded by
           # tests/test_certify_threshold.py and tests/test_gate.py, not by this subtraction.
           "refused_cases": len(cases) - len(auto_cases),
           "erroneous_cases": sum(1 for g in auto_cases if g["wrong"])}
    out["mean_measure"] = measure_sum / measured if measured else 0.0
    return out
