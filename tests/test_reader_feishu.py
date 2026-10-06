"""Task 5: the feishu_zh reader. No field is invented, and no OPTION order is normalised.

Asks inside a `four_noul` line are emitted in sorted order, which is a stable record order
for the archive; the option order of a `choice` line is never touched, because that is the
order the backend published and the probabilities are keyed to it.

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
        # One owner for corpus discovery: the same resolver the CLI uses, so a test
        # default cannot drift from the shipped default and disagree about what ran.
        str(__import__("autorate.cli", fromlist=["_default_corpus"])._default_corpus()
            or "/no/corpus/on/this/machine"),
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


def _line(**kw):
    base = {"id": "k-0", "mode": "choice", "repeat": 0, "status": "ok", "expected": "a",
            "family": "f", "response": {"model": "m", "answers": {"category": {
                "type": "choice", "choice": "a",
                "probabilities": {"a": 0.5, "b": 0.5}}}}}
    base.update(kw)
    return base


def _archive(tmp_path, objs, backends=("laya", "jev")):
    """A corpus root of raw lines, built the way this file already builds them."""
    import json
    for b in backends:
        f = tmp_path / "results" / "v1" / b / "raw.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(l if l.endswith("\n") else l + "\n" for l in objs))
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "manifest.json").write_text(json.dumps({"asks": ["urgent"]}))
    (tmp_path / "data" / "cases.jsonl").write_text(
        json.dumps({"id": "k-0", "expected": "a"}) + "\n")
    return tmp_path


def test_an_unknown_mode_line_raises_rather_than_vanishing():
    # The first version returned [] for any mode outside {choice, four_noul}: a corpus
    # that gained a mode would silently shrink the sample every certificate bounds.
    from autorate.readers.feishu_zh import records_from_line

    q = []
    assert records_from_line(_line(mode="ranked"), "laya", q) == []
    assert q and "not readable" in q[0]["reason"], q


def test_a_four_noul_line_with_no_noul_answer_is_not_silently_empty():
    from autorate.readers.feishu_zh import records_from_line

    q = []
    obj = _line(mode="four_noul", response={"model": "m", "answers": {
        "urgent": {"type": "score", "noul": 0.9}}})
    assert records_from_line(obj, "laya", q) == []
    assert q and "no noul-typed answer" in q[0]["reason"], q


def test_read_archive_conserves_every_line_it_read(tmp_path):
    """I-2: `records_kept` could not previously prove that nothing was lost.

    The identity is asserted by the reader itself, so a future branch that drops a line
    without a counter raises instead of shrinking the corpus.
    """
    import json

    from autorate.readers.feishu_zh import read_archive
    for b in ("laya", "jev"):
        f = tmp_path / "results" / "v1" / b / "raw.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        lines = [_line(id="a%d" % i) for i in range(3)]
        lines.append(_line(id="bad", mode="choice", response={"model": "m", "answers": {
            "category": {"type": "choice", "choice": "a",
                         "probabilities": {"a": 0.4, "b": 0.4}}}}))
        lines.append(_line(id="weird", mode="ranked"))
        lines.append(_line(id="emptynoul", mode="four_noul", response={"model": "m", "answers": {
            "urgent": {"type": "score", "noul": 0.5}}}))
        f.write_text("".join(json.dumps(l) + "\n" for l in lines))
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "manifest.json").write_text(json.dumps({"asks": ["urgent"]}))
    (tmp_path / "data" / "cases.jsonl").write_text(json.dumps({"id": "a0", "expected": "a"}) + "\n")

    stats = {}
    recs = read_archive(tmp_path, stats=stats)
    assert stats["lines_read"] == 6 * 2, stats
    assert stats["lines_kept"] == 3 * 2, stats
    # one unclosing choice line, one noul-less four_noul line and one unknown mode, per
    # backend: each is named, none is silently dropped.
    assert stats["lines_quarantined_only"] == {"choice": 2, "four_noul": 2, "ranked": 2}, stats
    assert stats["records_kept"] == len(recs) == 3 * 2, stats
    assert len(stats["quarantined"]) == 6, stats
    assert sum(stats["lines_by_mode"].values()) == stats["lines_kept"]


def test_a_line_that_is_not_json_is_quarantined_not_raised(tmp_path):
    """I-9: measured against the pre-fix reader, this line exited 2 -- the rc-1 shape is below.

    `json.JSONDecodeError` subclasses `ValueError`, and `cli.main` maps `ValueError` to
    EXIT_USAGE, so a line that failed to parse was already inside the documented exit set.
    What genuinely escaped as rc 1, uncaught and with a traceback, was a line that parsed and
    then raised `KeyError` on a key the contract needs (`test_a_line_missing_a_key...`), and a
    line that parsed as a JSON non-object and raised `AttributeError` (I-1).
    """
    from autorate.readers.feishu_zh import read_archive
    root = _archive(tmp_path, ['{"id": "broken"\n', json.dumps(_line(id="ok-0")) + "\n"])
    stats = {}
    recs = read_archive(root, stats=stats)
    # One well-formed line per backend: the builder writes the same two lines to both, so
    # 4 lines read is 2 malformed + 2 kept, and each kept line is one record.
    assert len(recs) == 2, stats
    assert stats["lines_malformed"] == 2, stats          # once per backend
    assert stats["lines_read"] == 4, stats               # the bad line still counts as seen
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"], stats


def test_a_line_missing_a_key_the_contract_needs_is_named_not_fatal(tmp_path):
    from autorate.readers.feishu_zh import read_archive
    root = _archive(tmp_path, [json.dumps({"id": "x", "mode": "choice",
                                           "repeat": 0, "status": "ok",
                                           "response": {"model": "m"}}) + "\n"],
                    backends=("laya",))
    stats = {}
    read_archive(root, backend="laya", stats=stats)
    q = [e for e in stats["quarantined"] if e["reason"] == "malformed_line"]
    assert len(q) == 1, q
    assert q[0]["backend"] == "laya" and q[0]["line_no"] == 1, q
    assert "answers" in q[0]["error"] or "KeyError" in q[0]["error"], q[0]
    assert "raw" not in q[0], "the archive line's bytes are not copied into the artifact"


def test_a_line_that_is_valid_json_but_not_an_object_is_quarantined_not_fatal(tmp_path):
    """I-1: `null`/`123`/`"x"`/`[...]` parse, then reach `obj.get` and raise AttributeError.

    AttributeError is outside the guard's catch set and outside `cli.main`'s mapping, so the
    class of line the task exists to close was still escaping as rc 1.
    """
    from autorate.readers.feishu_zh import read_archive
    shapes = ["null", "123", '"x"', "[1, 2]"]
    root = _archive(tmp_path, list(shapes), backends=("laya",))
    stats = {}
    assert read_archive(root, backend="laya", stats=stats) == []
    assert stats["lines_read"] == 4, stats           # every unread line is still a line seen
    assert stats["lines_malformed"] == 4, stats
    assert stats["lines_quarantined_only"] == {"malformed_line": 4}, stats
    q = stats["quarantined"]
    assert len(q) == 4, q
    assert [e["line_no"] for e in q] == [1, 2, 3, 4], q
    for e, shape in zip(q, shapes):
        assert e["reason"] == "malformed_line", shape
        # The shape is named by the reader, not by an attribute lookup three frames down.
        assert e["error"].startswith("TypeError"), (shape, e["error"])
        assert "not an object" in e["error"], (shape, e["error"])
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"], stats


def test_a_line_that_fails_after_quarantining_publishes_one_entry_not_two(tmp_path):
    """M-3: one line, one quarantine entry, identity closed.

    `records_from_line` appends to the caller's shared list as it goes, so a line whose
    first ask is quarantined and whose second ask raises used to publish two entries for a
    line the accounting counts once -- and `inventory.py` publishes `len(quarantined)`.
    """
    from autorate.readers.feishu_zh import read_archive
    bad_then_worse = _line(mode="four_noul", response={"model": "m", "answers": {
        "action": {"type": "noul", "noul": 1.5},          # outside [0,1]: quarantined
        "urgent": {"type": "noul", "confidence": 0.8}}})  # no `noul`: raises KeyError
    root = _archive(tmp_path, [json.dumps(bad_then_worse)], backends=("laya",))
    stats = {}
    read_archive(root, backend="laya", stats=stats)
    assert stats["lines_read"] == 1, stats
    assert stats["lines_malformed"] == 1, stats
    assert len(stats["quarantined"]) == 1, stats["quarantined"]
    # the entry that survives is the one for the line, not the orphan from the failed call
    assert [e["reason"] for e in stats["quarantined"]] == ["malformed_line"], stats["quarantined"]
    assert stats["lines_quarantined_only"] == {"malformed_line": 1}, stats
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"], stats


def test_a_malformed_entry_has_the_quarantine_schema_and_the_id_it_parsed(tmp_path):
    """M-4: one owner for the quarantine shape, and `id` is the join key to `cases.jsonl`.

    The malformed branch hand-rolled its own field set, so a field added to `_quarantine`
    would skip the malformed class; and it hardcoded `"id": None` even for a line that
    parsed and carried an id.
    """
    from autorate.readers.feishu_zh import _quarantine, read_archive
    root = _archive(tmp_path, [json.dumps({"id": "x", "mode": "choice", "repeat": 0,
                                           "status": "ok",
                                           "response": {"model": "m"}})],
                    backends=("laya",))
    stats = {}
    read_archive(root, backend="laya", stats=stats)
    q = stats["quarantined"]
    assert len(q) == 1, q
    malformed = q[0]
    assert malformed["id"] == "x", malformed      # the key that joins to cases.jsonl
    assert malformed["mode"] == "choice" and malformed["repeat"] == 0, malformed
    # Every field a well-formed-but-refused line carries is present here too, because the
    # same builder owns both; only the two malformed-only fields may differ.
    schema = set(_quarantine({"id": "y"}, "laya", (), "some other reason"))
    assert set(malformed) - schema == {"line_no", "error"}, malformed
    assert schema <= set(malformed), schema ^ set(malformed)


def test_a_key_missing_line_under_an_active_filter_is_malformed_not_fatal(tmp_path):
    """M-7: the filter reads live inside the guard, and nothing proves it but this test.

    Under `--repeat`/`--mode` the loop reads `obj["repeat"]`/`obj["mode"]` straight off the
    line before any status check, so a line missing that key is the last place rc 1 could
    still escape. Negative control (measured, see the fix report): with those reads outside
    the `try` the same corpus exits 1 with `KeyError: 'mode'`.
    """
    from autorate.readers.feishu_zh import read_archive
    no_mode = {"id": "k-0", "repeat": 0, "status": "ok", "expected": "a",
               "response": {"model": "m", "answers": {"category": {
                   "type": "choice", "choice": "a",
                   "probabilities": {"a": 0.5, "b": 0.5}}}}}
    root = _archive(tmp_path, [json.dumps(no_mode)], backends=("laya",))
    stats = {}
    read_archive(root, backend="laya", mode="choice", stats=stats)
    assert stats["lines_read"] == 1, stats
    assert stats["lines_filtered"] == 0, stats
    assert stats["lines_malformed"] == 1, stats
    q = [e for e in stats["quarantined"] if e["reason"] == "malformed_line"]
    assert len(q) == 1 and q[0]["line_no"] == 1, q
    assert "mode" in q[0]["error"] and "KeyError" in q[0]["error"], q[0]
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"], stats


def test_a_filter_that_matches_nothing_says_so(tmp_path):
    # Green-on-empty was the old shape: a filter typo returned [] with no counter.
    import json

    from autorate.readers.feishu_zh import read_archive
    f = tmp_path / "results" / "v1" / "laya" / "raw.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(_line(id="a0")) + "\n")
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "manifest.json").write_text(json.dumps({"asks": []}))
    (tmp_path / "data" / "cases.jsonl").write_text("{}\n")
    stats = {}
    assert read_archive(tmp_path, backend="laya", repeat=99, stats=stats) == []
    assert stats["lines_read"] == 1 and stats["lines_filtered"] == 1
    assert stats["lines_kept"] == 0 and stats["records_kept"] == 0


def test_the_per_ask_gold_tripwire_can_fire():
    # I-4: `_ask_gold` hardcoded None, so the "a per-ask gold appeared" branch was
    # unreachable and the guard proved nothing. It now consumes the measured set.
    #
    # I-2 changed the exception CLASS, deliberately: as a ValueError the refusal was swallowed
    # by `read_archive`'s per-line guard, counted as `malformed_line`, and the run exited 0.
    # A refusal is a RuntimeError here so the guard cannot catch it.
    from autorate.readers.feishu_zh import ReaderContractError, records_from_line

    obj = _line(mode="four_noul", response={"model": "m", "answers": {
        "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.8}}})
    assert records_from_line(obj, "laya", [])[0].gold is None
    import pytest
    with pytest.raises(ReaderContractError, match="now supervised"):
        records_from_line(obj, "laya", [], asks_with_gold=("urgent",))


def test_a_supervised_per_ask_gold_escapes_the_guard_and_is_never_a_malformed_line(tmp_path):
    """I-2: a corpus that supervises an ask is READABLE, so it is not a parse failure.

    The guard catches ValueError/KeyError/TypeError -- the errors of a line the reader cannot
    read. Before the refusal had its own class, the same corpus reached `lines_malformed`,
    published a quarantine entry, and exited 0: a policy refusal filed under "cannot read
    this line" and a certificate built on invented labels with nothing to show for it.
    """
    from autorate.readers.feishu_zh import ReaderContractError, read_archive
    # The class is only outside the catch set if it is not a ValueError in disguise.
    assert not issubclass(ReaderContractError, ValueError), "the guard would absorb it again"
    noul = _line(mode="four_noul", response={"model": "m", "answers": {
        "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.8}}})
    root = _archive(tmp_path, [json.dumps(noul)], backends=("laya",))
    (root / "data" / "cases.jsonl").write_text(
        json.dumps({"id": "k-0", "expected": "a", "urgent": "true"}) + "\n")
    stats: dict = {}
    with pytest.raises(ReaderContractError, match="now supervised"):
        read_archive(root, backend="laya", stats=stats)
    # Nothing gets published, so nothing was counted as a line that could not be read.
    assert stats == {}, stats


def test_a_mode_that_spells_the_internal_bucket_does_not_borrow_its_name(tmp_path):
    """R-81 (review MA-6): a corpus string may not occupy `malformed_line`, because that bucket
    is policed, and a refusal is an exit code.

    The reader files a readable-but-unbucketable line under `str(mode)` and an unreadable line
    under `MALFORMED_LINE`. Nothing stopped an archive line whose `mode` literally read
    `malformed_line` from landing in the second bucket: the two counts of one quantity then
    disagreed (`lines_malformed` from the reason, the bucket from the key), which is the refusal
    the inventory's conservation check exists to raise -- so ordinary corpus content selected
    EXIT_DRIFT. The key now comes from one function the reader owns, and it namespaces a colliding
    mode string while leaving every other key as it was.
    """
    from autorate.readers.feishu_zh import MALFORMED_LINE, mode_bucket_key, read_archive

    assert mode_bucket_key(MALFORMED_LINE) == "mode:malformed_line"
    assert mode_bucket_key("ranked") == "ranked", "the shipped keys must not move"
    assert mode_bucket_key(None) == "None"
    # The invariant the defect needs: no key produced from corpus content can equal the internal
    # label, because the namespaced form is prefixed and `MALFORMED_LINE` does not start with it.
    assert mode_bucket_key(MALFORMED_LINE) != MALFORMED_LINE
    for spelling in ("malformed_line", "mode:malformed_line", "", "None", "mode"):
        assert mode_bucket_key(spelling) != MALFORMED_LINE, spelling
    # Measured boundary, recorded so nobody reads the namespace as injectivity: a mode string that
    # already carries the prefix is returned unchanged, so it shares a key with the namespaced form
    # of the bare label. That merges two READABLE lines in one ledger row -- both are counted, so
    # the conservation identity and the malformed total are untouched and no exit code moves. It is
    # a loss of attribution, not of arithmetic, and R-81's ruling ("every other key is `str(mode)`
    # unchanged") accepts it rather than renaming the shipped keys.
    assert mode_bucket_key("mode:malformed_line") == mode_bucket_key(MALFORMED_LINE)

    lines = [json.dumps(_line(id="collide", mode=MALFORMED_LINE)),
             json.dumps(_line(id="other", mode="ranked")),
             "null"]
    root = _archive(tmp_path, lines, backends=("laya",))
    stats = {}
    read_archive(root, backend="laya", stats=stats)
    assert stats["lines_quarantined_only"] == {"mode:malformed_line": 1, "ranked": 1,
                                              "malformed_line": 1}, stats
    assert stats["lines_malformed"] == 1, stats
    # The identity the collision used to break still closes over all three lines.
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"] == 3, stats
    # The entry still names the corpus's own string; only the LEDGER key is namespaced.
    collide = [e for e in stats["quarantined"] if e["mode"] == MALFORMED_LINE]
    assert len(collide) == 1, stats["quarantined"]
    assert collide[0]["reason"] == "mode 'malformed_line' is not readable by this reader", collide
    assert collide[0]["id"] == "collide" and collide[0]["backend"] == "laya", collide

    # And the boundary, run rather than asserted: the prefixed spelling shares that key, so the
    # two lines merge into one ledger row -- both counted, `lines_malformed` untouched, identity
    # closed, and no exit code reachable from corpus content.
    both = lines + [json.dumps(_line(id="prefixed", mode="mode:malformed_line"))]
    root2 = _archive(tmp_path / "two", both, backends=("laya",))
    stats2 = {}
    read_archive(root2, backend="laya", stats=stats2)
    assert stats2["lines_quarantined_only"] == {"mode:malformed_line": 2, "ranked": 1,
                                               "malformed_line": 1}, stats2
    assert stats2["lines_malformed"] == 1, stats2
    assert stats2["lines_kept"] + sum(stats2["lines_quarantined_only"].values()) \
        == stats2["lines_read"] == 4, stats2
