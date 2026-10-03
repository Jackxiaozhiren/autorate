"""Which confidence scale is a published number? Decided by distance, per backend."""
import json
import math
from pathlib import Path

import pytest

from _thresholds import p_max_for_entropy
from autorate.records import Record
from autorate.scales import scale_attribution

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"


def _choice(backend, probs, reported):
    keys = tuple("abcd")[:len(probs)]
    return Record(id="x", qtype="choice", backend=backend, repeat=0, options=keys,
                  probs=probs, gold=keys[0], predicted=keys[0], slices={},
                  scores={"reported_confidence": reported}, seed=0, u=0.0, meta={})


def _noul(backend, p_true, reported):
    """One noul row: upstream publishes P(true) under the SAME key name choice uses."""
    return Record(id="x", qtype="noul", backend=backend, repeat=0, options=("false", "true"),
                  probs=(round(1.0 - p_true, 6), p_true), gold="true", predicted="true",
                  slices={}, scores={"reported_confidence": reported}, seed=0, u=0.0, meta={})


def _archive_rows():
    return [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]


def _archive_slice(backend, qtype):
    return [Record.from_dict(d) for d in _archive_rows()
            if d["backend"] == backend and d["qtype"] == qtype]


def test_a_reported_entropy_value_is_attributed_to_the_entropy_scale():
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    d = scale_attribution([_choice("b", p, entropy_confidence(p))])
    assert d["verdict"] == "confidence_entropy", d


def test_a_reported_max_probability_is_attributed_to_answer_confidence():
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.5)])
    assert d["verdict"] == "answer_confidence", d


def test_a_number_that_is_a_function_of_neither_is_called_neither():
    # jev's published confidence is its own quantity; forcing it into one of the two
    # scales is exactly the misattribution this module exists to prevent.
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.77)])
    assert d["verdict"] == "neither", d


def test_absent_field_is_reported_absent_rather_than_zero():
    r = _choice("b", (0.5, 0.3, 0.2), None)
    assert scale_attribution([r])["verdict"] == "absent"


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_the_committed_archive_confirms_the_attribution_the_audit_rests_on():
    rows = [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]
    by = {}
    for d in rows:
        if d["qtype"] == "choice":
            by.setdefault(d["backend"], []).append(Record.from_dict(d))
    laya = scale_attribution(by["laya"])
    jev = scale_attribution(by["jev"])
    assert laya["verdict"] == "confidence_entropy", laya
    assert jev["verdict"] == "neither", jev
    # The direction is the finding: laya's published number sits inside the tolerance of
    # the entropy scale and 0.38 away from max(p) at worst. Asserting the reverse here
    # would be the misattribution this module exists to catch.
    assert laya["max_dev_entropy"] <= laya["tolerance"] < laya["max_dev_answer"], laya
    assert jev["max_dev_entropy"] > jev["tolerance"], jev
    assert jev["max_dev_answer"] > jev["tolerance"], jev


def test_a_partially_absent_batch_counts_only_the_records_that_were_measured():
    # An absent field must not become a distance of 0: a batch where most backends publish
    # nothing would otherwise "match" every scale at once and be attributed to whichever
    # the implementation compared first.
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    records = [_choice("b", p, None), _choice("b", p, None), _choice("b", p, entropy_confidence(p))]
    d = scale_attribution(records)
    assert d["verdict"] == "confidence_entropy", d
    assert d["n"] == 1, d
    assert d["n"] < len(records), d
    # `n` is what was measured; `n_rows` is what was handed over. Collapsing the two is how a
    # row count ends up read as a sample size.
    assert d["n_rows"] == len(records), d


def test_no_records_at_all_is_absent_rather_than_a_verdict_reached_vacuously():
    d = scale_attribution([])
    assert d["verdict"] == "absent", d
    assert d["n"] == 0, d
    assert d["n_rows"] == 0, d
    assert d["max_dev_answer"] is None and d["max_dev_entropy"] is None, d
    assert (d["both"], d["answer_only"], d["entropy_only"], d["neither"]) == (0, 0, 0, 0), d


def test_a_batch_spanning_two_slices_raises_instead_of_answering_neither():
    # `reported_confidence` is one key name over two different published fields: laya's choice
    # rows carry the entropy scale and its noul rows carry P(true). Each slice is decisive on
    # its own; batched, the worst-case maxima are outside the window on BOTH scales, so the
    # function would print `neither` about data that answers the question cleanly slice by
    # slice. A mixed batch is therefore refused by name -- the same false verdict the archived
    # pipeline output would produce, and no caller who reads the docstring may make it.
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    choice = _choice("laya", p, entropy_confidence(p))
    noul = _noul("laya", 0.6213, 0.6213)
    assert scale_attribution([choice])["verdict"] == "confidence_entropy"
    assert scale_attribution([noul])["verdict"] == "answer_confidence"
    with pytest.raises(ValueError) as excinfo:
        scale_attribution([choice, noul])
    message = str(excinfo.value)
    assert "('laya', 'choice')" in message, message
    assert "('laya', 'noul')" in message, message


def test_a_batch_spanning_two_backends_raises_for_the_same_reason():
    # Two backends' same-named field is two quantities (the pairing section 14's neutrality
    # claim rests on not treating them as one), so the slice is (backend, qtype) and not qtype
    # alone: mixing backends would let jev's worst case decide laya's attribution.
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    laya = _choice("laya", p, entropy_confidence(p))
    jev = _choice("jev", p, 0.77)
    assert scale_attribution([laya])["verdict"] == "confidence_entropy"
    assert scale_attribution([jev])["verdict"] == "neither"
    with pytest.raises(ValueError) as excinfo:
        scale_attribution([laya, jev])
    message = str(excinfo.value)
    assert "('jev', 'choice')" in message, message
    assert "('laya', 'choice')" in message, message


def test_a_batch_of_one_slice_is_not_refused_by_the_slice_guard():
    # The guard refuses mixed slices, not small or single-qtype batches: one (backend, qtype)
    # repeated over rows is exactly what Task 4 hands over, and it must stay callable.
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    value = entropy_confidence(p)
    d = scale_attribution([_choice("laya", p, value) for _ in range(5)])
    assert d["verdict"] == "confidence_entropy", d
    assert d["n"] == 5 and d["n_rows"] == 5, d


def test_the_committed_archive_is_attributed_slice_by_slice_and_refused_as_one_backend_batch():
    """The batch shapes around the one call the reviewer measured as a false verdict.

    Over all 960 laya rows `scale_attribution` returned {'n': 960, 'verdict': 'neither'}
    while laya's two qtypes are individually decisive. That call mixes two published fields,
    so it is now refused; the per-slice calls are what Task 4 publishes a row for. The
    committed archive is read here with no skip guard: it is tracked, so its absence is a
    failure, not a skip.
    """
    by = {}
    for d in _archive_rows():
        by.setdefault((d["backend"], d["qtype"]), []).append(Record.from_dict(d))
    verdicts = {key: scale_attribution(recs)["verdict"] for key, recs in sorted(by.items())}
    assert verdicts == {
        ("jev", "choice"): "neither",
        ("jev", "noul"): "absent",
        ("laya", "choice"): "confidence_entropy",
        ("laya", "noul"): "answer_confidence",
    }, verdicts
    # Each slice's verdict is decisive; the headline backend read as one batch is not.
    assert scale_attribution(by[("laya", "choice")])["max_dev_entropy"] <= 1e-3
    assert scale_attribution(by[("laya", "noul")])["max_dev_answer"] == 0.0
    with pytest.raises(ValueError) as excinfo:
        scale_attribution(by[("laya", "choice")] + by[("laya", "noul")])
    assert "('laya', 'noul')" in str(excinfo.value), excinfo.value


def test_a_neither_verdict_travels_with_the_evidence_that_produced_it():
    # Task 4 publishes the distances, not just the label: a reader has to be able to see
    # how far off both scales the number is, or the verdict is a second assertion.
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.77)])
    assert set(d) == {"n", "n_rows", "max_dev_answer", "max_dev_entropy", "verdict", "tolerance",
                      "both", "answer_only", "entropy_only", "neither"}, d
    assert d["tolerance"] == pytest.approx(1e-3), d
    assert d["max_dev_answer"] > d["tolerance"] and d["max_dev_entropy"] > d["tolerance"], d
    # The closest scale is max(p) at 0.27 away, and the function still refuses to name it.
    assert d["max_dev_answer"] < d["max_dev_entropy"], d


def test_the_mixture_counts_are_the_per_record_half_of_the_result():
    """One row per bucket, so the aggregate word and the record-level facts cannot be confused.

    Every bucket is filled by a row whose distance is known by construction, and the batch also
    carries a row that is skipped entirely: `n` counts measurements, `n_rows` counts the batch.
    """
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    batch = [
        _choice("b", p, entropy_confidence(p)),          # entropy scale only
        _choice("b", p, 0.5),                            # max(p) only
        _choice("b", (1.0, 0.0, 0.0, 0.0), 1.0),         # both scales are 1.0 at once
        _choice("b", p, 0.77),                           # neither scale
        _choice("b", p, None),                           # carried no number: not measured
    ]
    d = scale_attribution(batch)
    assert (d["both"], d["answer_only"], d["entropy_only"], d["neither"]) == (1, 1, 1, 1), d
    assert d["n"] == 4 and d["n_rows"] == 5, d
    assert d["both"] + d["answer_only"] + d["entropy_only"] + d["neither"] == d["n"], d
    # The gate is a worst case over the rows passed, so this batch says `neither` even though
    # three of its four measured rows do match one scale each.
    assert d["verdict"] == "neither", d


def test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides():
    """Print "jev: neither" and you have said something false for 97 of jev's 191 rows.

    The counts are what Task 4 must publish beside the aggregate, so they are measured here
    against the archive rather than asserted about synthetic rows: 74 rows match both scales
    (one-hot rows publishing 1.0), 23 match max(p) alone, none match entropy alone, and 94
    match neither. The `n` of 191 rows is 64 cases, and the repeats are not byte-identical the
    way laya's are, so 191 is not a binomial denominator either.
    """
    rows = _archive_rows()
    jev_cases = {r["case_id"] for r in rows if r["backend"] == "jev" and r["qtype"] == "choice"}
    jev = scale_attribution(_archive_slice("jev", "choice"))
    assert jev["verdict"] == "neither", jev
    assert jev["n"] == 191 and jev["n_rows"] == 191, jev
    assert (jev["both"], jev["answer_only"], jev["entropy_only"], jev["neither"]) == (74, 23, 0, 94), jev
    assert jev["both"] + jev["answer_only"] == 97, jev
    # Read as cases, the same batch is 64 observations; `n` is neither of those by itself.
    assert len(jev_cases) == 64 and jev["n"] != len(jev_cases), (sorted(jev_cases), jev["n"])

    laya_cases = {r["case_id"] for r in rows if r["backend"] == "laya" and r["qtype"] == "choice"}
    laya = scale_attribution(_archive_slice("laya", "choice"))
    assert laya["n"] == 192 and len(laya_cases) == 64, (laya["n"], sorted(laya_cases))
    assert laya["entropy_only"] == 192, laya
    assert (laya["both"], laya["answer_only"], laya["neither"]) == (0, 0, 0), laya


def test_a_record_whose_two_scales_are_the_same_number_is_attributed_to_neither():
    # A one-hot distribution reads 1.0 on BOTH scales, so distance cannot separate them here
    # -- and 94 of jev's 191 archived choice records are one-hot, counted below rather than
    # quoted. Naming one scale would be a coin flip dressed as a measurement, so the function
    # says neither and leaves the choosing to a caller with better evidence than it has.
    from autorate.records import entropy_confidence, max_confidence
    one_hot = (1.0, 0.0, 0.0, 0.0)
    assert abs(max_confidence(one_hot) - entropy_confidence(one_hot)) < 1e-12
    d = scale_attribution([_choice("b", one_hot, 1.0)])
    assert d["verdict"] == "neither", d
    assert d["max_dev_answer"] == 0.0 and d["max_dev_entropy"] == 0.0, d

    archived = _archive_slice("jev", "choice")
    assert len(archived) == 191, len(archived)
    one_hot_rows = [r for r in archived if max(r.probs) == 1.0]
    assert len(one_hot_rows) == 94, len(one_hot_rows)
    # The two 94s are different sets: 20 of the one-hot rows publish 0.99 and so match no
    # scale, while the 74 that publish 1.0 match both.
    publishing_one = [r for r in one_hot_rows if r.scores["reported_confidence"] == 1.0]
    assert len(publishing_one) == 74, len(publishing_one)
    assert len(one_hot_rows) - len(publishing_one) == 20, len(one_hot_rows)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_reported_confidence_raises_whatever_order_it_arrives_in(bad):
    """The module's stated contract for bad input, not a fix to a live wrong number.

    The committed archive carries no non-finite `reported_confidence` (counted below), so
    nothing published today is wrong because of this. What was wrong was the claim: a NaN
    reached the maxima and `max()` decided the verdict by list order -- [ok, nan] answered
    `confidence_entropy`, [nan, ok] answered `neither`, both for the same two rows. That is
    the same class of input `records.py` already refuses for probabilities, so this guard
    mirrors it. Do not delete it as dead weight: it is the only thing keeping a future
    archive, or a future caller, from getting an order-dependent verdict.
    """
    from autorate.records import entropy_confidence
    non_finite = sum(1 for d in _archive_rows()
                     for value in [d["scores"]["reported_confidence"]]
                     if isinstance(value, float) and not math.isfinite(value))
    assert non_finite == 0, "the archive changed shape; this guard is now load-bearing, not belt"

    p = (0.5, 0.3, 0.2)
    ok = _choice("b", p, entropy_confidence(p))
    broken = _choice("b", p, bad)
    for batch in ([ok, broken], [broken, ok]):
        with pytest.raises(ValueError, match="non-finite"):
            scale_attribution(batch)


def test_a_non_numeric_reported_confidence_is_not_absorbed_into_absent():
    # The Task 2 report's decision 8 claims bad input raises. It was true of a string and false
    # of NaN/inf; both must raise, and neither may be relabelled as "publishes nothing".
    with pytest.raises(TypeError):
        scale_attribution([_choice("b", (0.5, 0.3, 0.2), "0.5")])


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_the_tolerance_sits_far_inside_the_gap_the_attribution_claims_to_tell_apart():
    """The numbers the shipped TOLERANCE is justified by, re-derived rather than quoted.

    A coincidence window is only safe if the two quantities it separates are far apart on the
    data it runs on. Both figures below come out of the code and the archive, so a widening of
    the window or a changed archive fails here instead of quietly making the comment a lie.
    """
    from autorate.records import entropy_confidence, max_confidence
    from autorate.scales import TOLERANCE

    laya = _archive_slice("laya", "choice")
    gap = min(abs(max_confidence(r.probs) - entropy_confidence(r.probs)) for r in laya)
    assert gap == pytest.approx(0.0526, abs=1e-4), (gap, len(laya))
    # 52x headroom: no archived laya record is close enough to both scales for the verdict to
    # be decided by which comparison the implementation happened to run first.
    assert TOLERANCE * 50 <= gap, (TOLERANCE, gap)

    # At the README's own 0.85 gate the two units are 0.1109 apart for a k=4 question: the
    # entropy scale reaches 0.85 only once the mass on the answer is that much higher, so a
    # caller gating on 0.85 of "confidence" is gating on a different number than 0.85 of
    # mass-on-the-answer. `p_max_for_entropy` is the suite's single solver for this; the
    # anchor p_max figure itself stays owned by tests/test_records.py.
    separation = p_max_for_entropy(0.85, 4) - 0.85
    assert separation == pytest.approx(0.1109, abs=6e-4), separation
    assert TOLERANCE * 100 <= separation, (TOLERANCE, separation)
