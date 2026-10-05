"""The case arithmetic both certifiers share: one rule, one counter (R-34).

`certify_choice` and `certify_threshold` apply different rules to the same records -- an
APS singleton set versus `score >= lambda` -- and both then have to answer the same three
questions: which decisions ran unattended, which of those were wrong, and how many
INDEPENDENT CASES (never archive rows: ledger R-36/R-44) each of those counts covers.
Answering them twice is how a published automation rate comes to describe a rule the
deployment does not apply, so the answers are computed once, here.

This module deliberately knows nothing about sets or thresholds: it receives a `kind`
callable that names what a rule did with one record, and an optional `measure` callable
for whatever that rule averages over a record. It returns `mean_measure`, never
`mean_set_size` or `mean_score`: the shared arithmetic does not name a published figure,
because a figure needs exactly one owner. Each certifier publishes the mean under its own
meta key.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

# The outcome vocabulary. `auto` is the decision to run unattended; `empty` and `multi`
# are the set rule's two ways of not doing that, kept separate because both are PUBLISHED
# (`empties`, `multi_label`); `refuse` is the fourth bucket the threshold gate needs --
# its non-automated decision is neither an empty set nor a multi-label one, and borrowing
# either name would write a false statement into `empties`/`multi_label` on a certificate.
KINDS = ("auto", "empty", "multi", "refuse")
AUTO = "auto"


def case_key(record) -> str:
    """The identity of the independent observation a record belongs to.

    Lives here because grouping by it is what the counter does. The domain is unchanged
    from the extraction: `case_id`, else the record id. Changing which strings are keys
    re-rolls every seeded split and moves every published bound, so this is not a
    two-line function -- it is the partition the corpus certificates were measured on.
    """
    return record.case_id or record.id


def decision_is_wrong(record) -> bool:
    """Whether the answer this record would automate is not the gold answer.

    `predicted` is the record's own statement of the answer it gives -- `records.py` names
    it that and refuses an answer outside the ballot. A record stating none answers with
    its largest probability, which is also the only label an APS singleton can hold.
    Measured on the committed archive: on all 383 calibratable choice records, and on every
    singleton set the set gate automated, the two readings agree, so moving this test out
    of `_outcome`'s `C[0] != r.gold_index` moved no published number (`verify` compares
    `meta` by name, so a single disagreement there would be a red gate, not a note).
    """
    if record.gold is None:
        raise ValueError("a record with no gold label cannot be counted right or wrong; "
                         "filter it before counting (certify_choice's eligibility rule does)")
    chosen = record.predicted
    if chosen is None:
        chosen = list(record.options)[max(
            range(len(record.probs)), key=lambda j: record.probs[j])]
    return chosen != record.gold


def count_outcome(half: Sequence, kind: Callable[[object], str],
                  measure: Optional[Callable[[object], float]] = None) -> dict:
    """Apply one rule to one half, counting RECORDS and the CASES they stand for.

    A case is automated only when every one of its records automates -- running a case
    unattended means running all of it -- and it is erroneous when any automated record in
    it is wrong. Those two buckets are exhaustive, so `automated_cases + refused_cases ==
    n_cases` and refusal = 1 - autorate hold at the unit the bound is computed on. Record
    counts stay because they are what the gate acts on; they are not a binomial
    denominator, because repeats of one case are one observation (the committed archive
    measures it: laya's three records per case carry byte-identical probability vectors,
    scores and gold labels, though not identical rows -- pinned by
    tests/test_report_prose.py).

    `kind(record)` must return a name in `KINDS`; anything else is a rule this counter does
    not know, and it raises rather than choosing a bucket for it. `measure(record)` is the
    rule's own per-record quantity, averaged over the records of the half.
    """
    autom = err = empties = multi = refused = 0
    measure_sum = 0.0
    cases = {}
    for r in half:
        k = kind(r)
        if k not in KINDS:
            raise ValueError("unknown outcome kind %r; count_outcome knows %s"
                             % (k, ", ".join(KINDS)))
        if measure is not None:
            measure_sum += float(measure(r))
        wrong = k == AUTO and decision_is_wrong(r)
        if k == "empty":
            empties += 1
        elif k == "multi":
            multi += 1
        if k == AUTO:
            autom += 1
            if wrong:
                err += 1
        else:
            refused += 1
        g = cases.setdefault(case_key(r), {"decisions": 0, "automated": 0, "wrong": 0})
        g["decisions"] += 1
        if k == AUTO:
            g["automated"] += 1
            if wrong:
                g["wrong"] += 1
    auto_cases = [g for g in cases.values() if g["automated"] == g["decisions"]]
    out = {"automated": autom, "errors": err, "empties": empties, "multi_label": multi,
           "refused": refused, "n_cases": len(cases), "automated_cases": len(auto_cases),
           "refused_cases": len(cases) - len(auto_cases),
           "erroneous_cases": sum(1 for g in auto_cases if g["wrong"])}
    if measure is not None:
        out["mean_measure"] = measure_sum / len(half) if half else 0.0
    return out
