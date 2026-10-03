"""Which confidence scale is a published number? Decided by distance, per backend."""
import json
from pathlib import Path

import pytest

from autorate.records import Record
from autorate.scales import scale_attribution

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"


def _choice(backend, probs, reported):
    keys = tuple("abcd")[:len(probs)]
    return Record(id="x", qtype="choice", backend=backend, repeat=0, options=keys,
                  probs=probs, gold=keys[0], predicted=keys[0], slices={},
                  scores={"reported_confidence": reported}, seed=0, u=0.0, meta={})


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


def test_no_records_at_all_is_absent_rather_than_a_verdict_reached_vacuously():
    d = scale_attribution([])
    assert d["verdict"] == "absent", d
    assert d["n"] == 0, d
    assert d["max_dev_answer"] is None and d["max_dev_entropy"] is None, d


def test_a_neither_verdict_travels_with_the_evidence_that_produced_it():
    # Task 4 publishes the distances, not just the label: a reader has to be able to see
    # how far off both scales the number is, or the verdict is a second assertion.
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.77)])
    assert set(d) == {"n", "max_dev_answer", "max_dev_entropy", "verdict", "tolerance"}, d
    assert d["tolerance"] == pytest.approx(1e-3), d
    assert d["max_dev_answer"] > d["tolerance"] and d["max_dev_entropy"] > d["tolerance"], d
    # The closest scale is max(p) at 0.27 away, and the function still refuses to name it.
    assert d["max_dev_answer"] < d["max_dev_entropy"], d


def test_a_record_whose_two_scales_are_the_same_number_is_attributed_to_neither():
    # A one-hot distribution reads 1.0 on BOTH scales, so distance cannot separate them here
    # -- and 94 of jev's 191 archived choice records are one-hot. Naming one scale would be a
    # coin flip dressed as a measurement, so the function says neither and leaves the choosing
    # to a caller with better evidence than this function has.
    from autorate.records import entropy_confidence, max_confidence
    one_hot = (1.0, 0.0, 0.0, 0.0)
    assert abs(max_confidence(one_hot) - entropy_confidence(one_hot)) < 1e-12
    d = scale_attribution([_choice("b", one_hot, 1.0)])
    assert d["verdict"] == "neither", d
    assert d["max_dev_answer"] == 0.0 and d["max_dev_entropy"] == 0.0, d


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_the_tolerance_sits_far_inside_the_gap_the_attribution_claims_to_tell_apart():
    """The numbers the shipped TOLERANCE is justified by, re-derived rather than quoted.

    A coincidence window is only safe if the two quantities it separates are far apart on the
    data it runs on. Both figures below come out of the code and the archive, so a widening of
    the window or a changed archive fails here instead of quietly making the comment a lie.
    """
    from autorate.records import entropy_confidence, max_confidence
    from autorate.scales import TOLERANCE

    rows = [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]
    laya = [Record.from_dict(d) for d in rows
            if d["qtype"] == "choice" and d["backend"] == "laya"]
    gap = min(abs(max_confidence(r.probs) - entropy_confidence(r.probs)) for r in laya)
    assert gap == pytest.approx(0.0526, abs=1e-4), (gap, len(laya))
    # 52x headroom: no archived laya record is close enough to both scales for the verdict to
    # be decided by which comparison the implementation happened to run first.
    assert TOLERANCE * 50 <= gap, (TOLERANCE, gap)

    # At the README's own 0.85 gate the two units are 0.1109 apart for a k=4 question: the
    # entropy scale reaches 0.85 only once p_max is 0.9609, and a caller gating on 0.85 of
    # "confidence" is therefore gating on a different number than 0.85 of mass-on-the-answer.
    def p_max_reaching(target, k):
        lo, hi = 1.0 / k, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if entropy_confidence([mid] + [(1 - mid) / (k - 1)] * (k - 1)) < target:
                lo = mid
            else:
                hi = mid
        return hi

    p_max_085 = p_max_reaching(0.85, 4)
    assert p_max_085 == pytest.approx(0.9609, abs=6e-4), p_max_085
    assert p_max_085 - 0.85 == pytest.approx(0.1109, abs=6e-4)
    assert TOLERANCE * 100 <= p_max_085 - 0.85, (TOLERANCE, p_max_085)
