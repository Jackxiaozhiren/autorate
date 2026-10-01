"""Task 5: the feishu_zh reader. No field is invented, and no order is normalised.

Measured facts this suite encodes (2026-10-01, from the archive itself):
- laya presents options as urgent,todo,valuable,noise; jev presents the SAME case as
  noise,urgent,todo,valuable. So gold must be addressed by label, and `gold_index`
  is not comparable across backends.
- one `four_noul` archive LINE expands into four noul Records (asks related, action,
  urgent, value), and the fixtures supervise only the composite label, so those
  Records carry gold=None (ledger R-14).
"""
import json
from pathlib import Path

import pytest

from autorate.readers.feishu_zh import read_archive, records_from_line

UPSTREAM = Path(
    __import__("os").environ.get(
        "AUTORATE_FEISHU_ROOT",
        "/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh",
    )
)
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")
FIXTURE = Path(__file__).parent / "fixtures" / "feishu_sample.jsonl"


@skip
def test_choice_record_maps_the_archived_order_and_labels():
    recs = read_archive(UPSTREAM, backend="laya", mode="choice", repeat=1)
    r = next(x for x in recs if x.id == "lifecycle-05")
    assert r.qtype == "choice"
    assert r.options == ("urgent", "todo", "valuable", "noise")
    assert r.probs == (0.2955, 0.2984, 0.2973, 0.1087)
    assert r.gold == "valuable" and r.predicted == "todo"      # an actual wrong answer
    assert r.gold_index == 2                                   # by label, in archived order
    assert r.backend == "laya" and r.repeat == 1
    assert r.slices["family"] == "lifecycle" and r.slices["mode"] == "choice"
    assert r.meta["model"] == "laya-rl-agent"
    assert r.scores["reported_confidence"] == 0.0456
    assert r.calibratable is True


@skip
def test_the_same_case_on_jev_presents_a_different_order_so_indexes_are_not_comparable():
    laya = next(x for x in read_archive(UPSTREAM, backend="laya", mode="choice", repeat=1)
                if x.id == "lifecycle-05")
    jev = next(x for x in read_archive(UPSTREAM, backend="jev", mode="choice", repeat=1)
               if x.id == "lifecycle-05")
    assert jev.options == ("noise", "urgent", "todo", "valuable")
    assert laya.gold_index != jev.gold_index                    # 2 vs 3, same gold label
    assert laya.gold == jev.gold == "valuable"
    assert jev.probs == (0.0, 0.0, 0.0, 1.0) and jev.predicted == "valuable"
    assert jev.scores["reported_confidence"] == 1.0


@skip
def test_pairing_is_honest_only_when_the_request_bytes_match():
    laya = {(r.id, r.repeat, r.slices.get("ask", "category")): r.meta["request_sha256"]
            for r in read_archive(UPSTREAM, backend="laya")}
    jev = {(r.id, r.repeat, r.slices.get("ask", "category")): r.meta["request_sha256"]
           for r in read_archive(UPSTREAM, backend="jev")}
    common = set(laya) & set(jev)
    # laya has 192 category + 768 ask keys; jev has one fewer category because
    # lifecycle-01/repeat=1 is quarantined, so the intersection is the smaller side.
    assert len(common) == 959, len(common)
    mismatched = [k for k in common if laya[k] != jev[k]]
    assert not mismatched, "paired keys with different request digests: %r" % mismatched[:3]


@skip
def test_jev_records_carry_the_model_id_that_actually_responded():
    recs = read_archive(UPSTREAM, backend="jev", mode="choice", repeat=1)
    assert {r.meta["model"] for r in recs} == {"jev-1.13.0"}
    assert all(r.scores.get("act_probability") is None for r in recs)  # jev ships no action block


@skip
def test_a_four_noul_line_expands_to_four_unsupervised_noul_records():
    recs = read_archive(UPSTREAM, backend="laya", mode="four_noul", repeat=0)
    per_case: dict = {}
    for r in recs:
        per_case.setdefault(r.id.split("#")[0], []).append(r)
    r = per_case["urgency-06"][0]
    assert sorted(x.slices["ask"] for x in per_case["urgency-06"]) == [
        "action", "related", "urgent", "value"]
    assert r.qtype == "noul" and r.options == ("false", "true")
    assert len(r.probs) == 2 and abs(sum(r.probs) - 1.0) < 5e-3
    assert r.scores["noul_confounded_with_yes"] is True
    # R-14: the fixtures supervise only the composite 4-way label, never a per-ask bit.
    assert r.gold is None and r.calibratable is False
    assert all(x.calibratable is False for x in recs), "a per-ask gold appeared: re-check R-14"
    assert {x.predicted for x in per_case["urgency-06"]} <= {"false", "true"}


@skip
def test_lines_and_records_are_reported_separately():
    stats = {}
    recs = read_archive(UPSTREAM, stats=stats)
    # 768 archive lines; one jev choice line is quarantined (see the test below), so it
    # yields no record and is not counted as kept.
    assert stats["lines_kept"] == 767
    assert stats["lines_dropped_not_ok"] == 0
    assert stats["lines_by_mode"] == {"choice": 383, "four_noul": 384}
    assert stats["records_kept"] == len(recs) == 383 + 4 * 384


@skip
def test_the_one_unclosing_record_is_named_not_absorbed_by_a_wider_tolerance():
    # Measured: jev / lifecycle-01 / repeat=1 publishes [0.0, 0.93, 0.01, 0.05] which
    # sums to 0.99. Upstream's guard (prompts.py:27) tolerates abs(sum-1) > 0.01, so it
    # passed there. This project keeps its contract at SUM_TOL and quarantines instead.
    stats = {}
    recs = read_archive(UPSTREAM, stats=stats)
    q = stats["quarantined"]
    assert len(q) == 1, q
    assert q[0]["id"] == "lifecycle-01" and q[0]["backend"] == "jev" and q[0]["repeat"] == 1
    assert q[0]["probs_sum"] == 0.99 and q[0]["tolerance"] == 5e-3
    assert q[0]["probs"] == [0.0, 0.93, 0.01, 0.05]
    assert not any(r.id == "lifecycle-01" and r.backend == "jev" and r.repeat == 1 for r in recs)
    # the other two repeats of the same case are still usable
    assert sum(1 for r in recs if r.id == "lifecycle-01" and r.backend == "jev") == 2


@skip
def test_no_laya_record_is_quarantined():
    stats = {}
    read_archive(UPSTREAM, backend="laya", stats=stats)
    assert stats["quarantined"] == []
    assert stats["lines_by_mode"] == {"choice": 192, "four_noul": 192}


@skip
def test_every_archived_record_has_u_zero_and_says_so():
    # The archive stored no randomisation draw, so APS ties resolve to the first slot.
    # Recorded as a fact about the corpus, not silently assumed by the certifier.
    recs = read_archive(UPSTREAM)
    assert all(r.u == 0.0 for r in recs)
    assert all("u_source" in r.meta and r.meta["u_source"] == "absent_from_archive" for r in recs)


@skip
def test_truncation_is_carried_because_a_truncated_state_is_a_different_question():
    recs = read_archive(UPSTREAM, backend="laya", mode="choice")
    assert all(r.meta["truncated"] is False for r in recs)


@skip
def test_reading_the_archive_never_writes_into_the_vendored_tree():
    before = _digest(UPSTREAM)
    read_archive(UPSTREAM)
    assert _digest(UPSTREAM) == before


def test_the_committed_six_record_fixture_reads_without_the_corpus():
    lines = [json.loads(l) for l in FIXTURE.read_text().splitlines() if l.strip()]
    assert lines, "fixture is empty"
    recs = [r for line in lines for r in records_from_line(line, backend(line))]
    assert len(recs) >= len(lines)
    assert {r.backend for r in recs} <= {"laya", "jev"}
    assert all(r.k >= 2 for r in recs)


def backend(line: dict) -> str:
    model = line["response"]["model"]
    return "laya" if model.startswith("laya") else "jev"


def _digest(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
            st = p.stat()
            out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out
