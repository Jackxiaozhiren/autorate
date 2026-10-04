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


def _entropy_bisectors(tests_dir):
    """Helpers under tests/ that evaluate the entropy scale INSIDE a loop, at any nesting depth.

    This is the single-owner fingerprint for the bisection that turns an entropy target back into a
    `p_max`: the same search written twice is exactly how a transposed parameter order survived a
    whole review round, so the COUNT of owners is the fact worth guarding, not any one value.

    The class it covers, stated because a guard that is not self-describing gets widened or trusted
    wrongly: any `FunctionDef` in any tests/*.py file, module-level OR nested inside another function,
    whose name does not begin with `test_` and which calls `entropy_confidence` DIRECTLY from inside
    a repetition -- a loop STATEMENT in any of its three forms (`For`, `AsyncFor`, `While`) or its own
    body (recursion). Nested coverage is the point -- a second copy re-added inside a test body is the
    regression this guards, and a module-level-only walk would have passed it. Read as a syntax-tree
    question rather than a substring, because a docstring that merely names the scale is not a second
    solver.

    The `While` and recursion arms are not decoration. Measured with only the `For` arm -- the shape
    the first version of this fingerprint knew -- a second bisection written as `while n < iterations:`
    keeps the suite GREEN: the detector looked for the shape it had seen, so the property it polices
    was narrower than its name. Both planted shapes now go red.

    What is deliberately NOT covered, and why: `test_*` functions, which assert about the scale
    instead of deriving from it (several loop over bad inputs calling `entropy_confidence`); a
    comprehension, which carries no interval state to narrow and so cannot hold this search; and a
    search that reaches the scale INDIRECTLY, like the nested `crossing` below -- that helper bisects
    WHERE THE TWO SCALES CONVERGE, a different question with one reader, which is why it stays in
    this file rather than joining `tests/_thresholds.py`.

    The concrete name it is watching for is `_pmax_reaching`, the transposed copy this round deleted
    from `tests/test_records.py`; the guard test that calls this helper also checks for that name in
    that file, so a re-added copy is caught by shape and by name.
    """
    import ast

    loop_forms = (ast.For, ast.AsyncFor, ast.While)

    def calls_scale(node):
        return any(isinstance(call, ast.Call)
                   and getattr(call.func, "id", None) == "entropy_confidence"
                   for call in ast.walk(node))

    found = []
    for path in sorted(tests_dir.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("test_"):
                continue
            for stmt in ast.walk(node):
                if isinstance(stmt, loop_forms) and calls_scale(stmt):
                    found.append("%s::%s" % (path.name, node.name))
                    break
                # A recursive bisection repeats through its own body instead of a loop statement.
                if any(isinstance(call, ast.Call) and getattr(call.func, "id", None) == node.name
                       for call in ast.walk(node)) and calls_scale(node):
                    found.append("%s::%s" % (path.name, node.name))
                    break
    return sorted(set(found))


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


def test_a_decisive_verdict_does_not_mean_every_measured_row_was_decisive():
    """The summary sentence's own reading, produced: only the two maxima decide the word.

    The shipped docstring used to claim "every measured row must sit inside `TOLERANCE` of one scale
    and outside it on the other", which is a per-row gate the code never implements. This batch is
    the difference between the two readings: the gate is decisive for `answer_confidence` because
    the MAXIMUM distance to max(p) is 0.0, while one of its rows sits inside both windows at once
    and is therefore counted in `both`, not named. A per-row gate would refuse this batch instead.
    """
    sharp = (0.9995, (1 - 0.9995) / 3, (1 - 0.9995) / 3, (1 - 0.9995) / 3)
    d = scale_attribution([_choice("b", sharp, 0.9995),          # answer scale only
                           _choice("b", (1.0, 0.0, 0.0, 0.0), 1.0)])  # inside BOTH windows
    assert d["verdict"] == "answer_confidence", d
    assert d["max_dev_answer"] == 0.0, d
    assert d["max_dev_entropy"] > d["tolerance"], d
    assert (d["both"], d["answer_only"], d["entropy_only"], d["neither"]) == (1, 1, 0, 0), d
    assert d["n"] == 2 and d["n_rows"] == 2, d


def test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides():
    """Print "jev: neither" and you have said something false for 97 of jev's 191 rows.

    The counts are what Task 4 must publish beside the aggregate, so they are measured here
    against the archive rather than asserted about synthetic rows: 74 rows match both scales
    (one-hot rows publishing 1.0), 23 match max(p) alone, none match entropy alone, and 94
    match neither. The `n` of 191 rows is 64 cases whose repeat structure is produced below,
    for both backends, because the module's `n`-versus-cases comment quotes it: jev's cases carry
    between one and three DISTINCT probability vectors (so 191 rows are not 191 observations),
    while laya's 192 rows are 64 cases x 3 repeats that publish the same vector and the same
    number each time -- identical as measurements, not identical as rows.
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
    # The two maxima the module's docstring publishes for this slice, pinned at the precision it
    # prints them at: jev's choice `confidence` sits up to 0.170 from `max(p)` and 0.157315 from the
    # entropy scale. Both are far outside `tolerance`, so the `neither` above is a statement about
    # what the published number IS, not about which comparison the implementation ran first.
    assert jev["max_dev_answer"] == pytest.approx(0.170, abs=5e-7), jev["max_dev_answer"]
    assert jev["max_dev_entropy"] == pytest.approx(0.157315, abs=5e-7), jev["max_dev_entropy"]

    laya_cases = {r["case_id"] for r in rows if r["backend"] == "laya" and r["qtype"] == "choice"}
    laya = scale_attribution(_archive_slice("laya", "choice"))
    assert laya["n"] == 192 and len(laya_cases) == 64, (laya["n"], sorted(laya_cases))
    assert laya["entropy_only"] == 192, laya
    assert (laya["both"], laya["answer_only"], laya["neither"]) == (0, 0, 0), laya

    # The repeat structure `scales.py` quotes about `n`, produced for both backends rather than
    # asserted in prose. laya: 64 cases x exactly 3 rows, and every case's rows carry ONE `probs`
    # vector and ONE published `reported_confidence` -- while no case's three rows are identical as
    # rows, since each carries its own repeat counter and elapsed time. The distinction is the whole
    # point of the sentence: three rows that measure the same thing are not three observations, and
    # calling them byte-identical would claim something the file refutes.
    def _groups(backend):
        grouped = {}
        for r in rows:
            if r["backend"] == backend and r["qtype"] == "choice":
                grouped.setdefault(r["case_id"], []).append(r)
        return grouped

    laya_groups = _groups("laya")
    assert len(laya_groups) == 64 and {len(g) for g in laya_groups.values()} == {3}, len(laya_groups)
    one_measurement_per_case = all(
        len({json.dumps(r["probs"], sort_keys=True) for r in g}) == 1
        and len({json.dumps(r["scores"], sort_keys=True) for r in g}) == 1
        for g in laya_groups.values())
    assert one_measurement_per_case, "laya's repeats no longer publish one vector and one number per case"
    identical_rows = any(len({json.dumps(r, sort_keys=True) for r in g}) == 1
                         for g in laya_groups.values())
    assert not identical_rows, "laya's repeats became identical as ROWS; the comment's wording must follow"
    # jev: 2 or 3 rows per case, and between 1 and 3 DISTINCT probability vectors inside a case.
    # Pin, not a guard: nothing else in the suite reads this shape, so these two lines exist to keep
    # the module comment's "1-3 DISTINCT probability vectors" figure owned by an artifact instead of
    # restated from memory. The counts they depend on (191 rows, 64 cases) are guarded above.
    jev_groups = _groups("jev")
    assert len(jev_groups) == 64 and {len(g) for g in jev_groups.values()} == {2, 3}, len(jev_groups)
    assert {len({json.dumps(r["probs"], sort_keys=True) for r in g})
            for g in jev_groups.values()} == {1, 2, 3}, jev_groups


def test_collapsing_jev_to_one_row_per_case_does_not_move_the_published_maxima():
    """What the follow-up note predicted, measured: its pair is a tie-break, not a consequence.

    `scales.py` carried a note claiming that collapsing jev's 191 archived choice rows to its 64
    cases "moves the published maxima from 0.170 to 0.160 and from 0.157315 to 0.147315". The blocker
    it named -- `Record.from_dict` dropping `case_id` -- landed before this could be reasoned about,
    so it could be RUN, and the result is that both halves of the pair are real numbers whose
    appearance depends entirely on which row a collapsed case keeps:

    * a collapse that keeps each case's WORST row -- the only one that preserves what the gate is,
      since the gate takes a maximum over rows -- leaves both maxima exactly where they are, because
      the row carrying each published maximum is already its own case's worst on that scale;
    * a collapse that keeps each case's FIRST row in archive order produces 0.160 and 0.147315,
      precisely by discarding those two cases' worst row -- which in both cases is the third repeat.

    So the predicted pair is reachable, but only through an aggregation this gate must not use. The
    comment now says that instead of forecasting a number.
    """
    from autorate.records import entropy_confidence, max_confidence

    rows = []
    for r in _archive_slice("jev", "choice"):
        reported = (r.scores or {}).get("reported_confidence")
        if reported is None or len(r.probs) < 2:
            continue
        rows.append((r.case_id, abs(reported - max_confidence(r.probs)),
                     abs(reported - entropy_confidence(r.probs))))
    assert len(rows) == 191, len(rows)
    published_answer = max(r[1] for r in rows)
    published_entropy = max(r[2] for r in rows)
    # The same two figures the archive test above reads out of `scale_attribution`, recomputed from
    # the rows here: pin, not a second guard -- it exists so the collapse below starts from a number
    # this file has already shown matches the module's own output.
    assert published_answer == pytest.approx(0.170, abs=5e-7), published_answer
    assert published_entropy == pytest.approx(0.157315, abs=5e-7), published_entropy

    by_case = {}
    for case_id, dev_answer, dev_entropy in rows:
        by_case.setdefault(case_id, []).append((dev_answer, dev_entropy))
    assert len(by_case) == 64, len(by_case)

    worst = [(max(p[0] for p in v), max(p[1] for p in v)) for v in by_case.values()]
    assert max(w[0] for w in worst) == pytest.approx(published_answer, abs=1e-12)
    assert max(w[1] for w in worst) == pytest.approx(published_entropy, abs=1e-12)

    first = [v[0] for v in by_case.values()]
    assert max(f[0] for f in first) == pytest.approx(0.160, abs=5e-7), max(f[0] for f in first)
    assert max(f[1] for f in first) == pytest.approx(0.147315, abs=5e-7), max(f[1] for f in first)

    # And the structural fact that lets both answers coexist: in each of the two cases the maximum is
    # the LAST repeat and the predicted figure is the FIRST, so the collapse's tie-break decides
    # whether the published maximum survives the collapse at all.
    answer_case = max(by_case, key=lambda c: max(p[0] for p in by_case[c]))
    entropy_case = max(by_case, key=lambda c: max(p[1] for p in by_case[c]))
    assert by_case[answer_case][-1][0] == pytest.approx(0.170, abs=5e-7)
    assert by_case[answer_case][0][0] == pytest.approx(0.160, abs=5e-7)
    assert by_case[entropy_case][-1][1] == pytest.approx(0.157315, abs=5e-7)
    assert by_case[entropy_case][0][1] == pytest.approx(0.147315, abs=5e-7)
    assert sorted(round(p[0], 6) for p in by_case[answer_case]) == [0.16, 0.16, 0.17]
    assert sorted(round(p[1], 6) for p in by_case[entropy_case]) == [0.147315, 0.150882, 0.157315]


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
def test_the_archive_publishes_every_served_figure_at_four_decimals():
    """The premise under `TOLERANCE`, produced: the archive's own numbers are 4-decimal quantities.

    `scales.py` justifies a 1e-3 agreement window by saying served probabilities and served
    confidences are both rounded to 4 decimals, so a match inside the window is the same quantity
    rather than a coincidence. That is a claim about the committed records, and until now nothing
    in the suite read it: the window could have been justified by prose about a file nobody checks.
    Every `probs` value and every `reported_confidence` in the archive is asserted to be exactly
    its own 4-decimal rounding, so if an upstream export ever starts carrying more precision the
    premise fails here instead of quietly making the comment a lie.
    """
    rows = _archive_rows()
    assert rows, "the committed archive is empty"
    probs_values = [float(v) for d in rows for v in d["probs"]]
    reported = [float(d["scores"]["reported_confidence"]) for d in rows
                if d["scores"].get("reported_confidence") is not None]
    off_grid_probs = [(d["backend"], d["qtype"], v) for d in rows for v in d["probs"]
                      if round(float(v), 4) != float(v)]
    off_grid_reported = [(d["backend"], d["qtype"], d["scores"]["reported_confidence"])
                         for d in rows
                         if d["scores"].get("reported_confidence") is not None
                         and round(float(d["scores"]["reported_confidence"]), 4)
                         != float(d["scores"]["reported_confidence"])]
    assert not off_grid_probs, off_grid_probs[:5]
    assert not off_grid_reported, off_grid_reported[:5]
    # The counts travel with the claim so a reader sees what was actually covered: 4 decimals was
    # checked on every served number in the file, not on a sample of it. Of the archive's 1919 rows,
    # 768 (jev's noul slice) publish no confidence at all, so the second count is rows carrying one.
    assert (len(probs_values), len(reported)) == (4604, 1151), (len(probs_values), len(reported))


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_the_tolerance_sits_far_inside_the_gap_the_attribution_claims_to_tell_apart():
    """The numbers the shipped TOLERANCE is justified by, re-derived rather than quoted.

    A coincidence window is only safe if the two quantities it separates are far apart on the
    data it runs on. Every figure below comes out of the code and the archive, so a widening of
    the window or a changed archive fails here instead of quietly making the comment a lie.
    """
    from autorate.records import entropy_confidence, max_confidence
    from autorate.scales import TOLERANCE

    laya = _archive_slice("laya", "choice")
    # The comment's slice size is asserted, not assumed: the headroom claim below is a statement about
    # THIS slice, so the count it quotes ("laya's 192 archived choice records") is produced here too.
    # Redundant by design -- the same 192 is pinned in
    # `test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides`, so this line
    # cannot go red while that one is green -- and it exists only so the module comment's pointer
    # resolves in this test. It is not inert: dropping any laya choice row reddens both lines.
    assert len(laya) == 192, len(laya)
    gap = min(abs(max_confidence(r.probs) - entropy_confidence(r.probs)) for r in laya)
    assert gap == pytest.approx(0.0526, abs=1e-4), (gap, len(laya))
    # 52x headroom: no archived laya record is close enough to both scales for the verdict to
    # be decided by which comparison the implementation happened to run first. The multiplier is
    # arithmetic on the gap above, so it is printed rather than quoted: 0.0526 is 52.6 windows wide.
    # The band guards the WINDOW, not the archive -- with `gap` pinned one line above, the ratio can
    # only leave [52, 53) if `TOLERANCE` moves, which is what makes it worth asserting separately
    # (measured: TOLERANCE at 1e-4 puts the ratio at 526.45 and reddens exactly this line).
    headroom = gap / TOLERANCE
    assert 52 <= headroom < 53, (TOLERANCE, gap, headroom)

    # At the README's own 0.85 gate the two units are 0.1109 apart for a k=4 question: the
    # entropy scale reaches 0.85 only once the mass on the answer is that much higher, so a
    # caller gating on 0.85 of "confidence" is gating on a different number than 0.85 of
    # mass-on-the-answer. `p_max_for_entropy` is the suite's single solver for this; the
    # anchor p_max figure itself stays owned by tests/test_records.py.
    separation = p_max_for_entropy(target=0.85, k=4) - 0.85
    assert separation == pytest.approx(0.1109, abs=6e-4), separation
    assert TOLERANCE * 100 <= separation, (TOLERANCE, separation)

    # The tolerance comment's other claim, produced AND scoped: the window stops separating the
    # two scales once a k=4 row is near enough to one-hot, and such a row is absorbed by the `else`
    # branch as `neither` (counted in `both`) instead of being named after a scale. Where exactly
    # that happens is a DIFFERENT NUMBER for the two questions a reader can ask, and a different
    # number again for each remainder shape, so all of them are printed here rather than quoted.
    def remainder_uniform(p_max):
        rest = (1.0 - p_max) / 3.0
        return [p_max, rest, rest, rest]

    def remainder_lumpy(p_max):
        rest = 1.0 - p_max
        return [p_max, rest / 2, rest / 6, rest / 6]

    def remainder_sparse(p_max):
        return [p_max, 1.0 - p_max, 0.0, 0.0]

    def scale_gap(shape, p_max):
        probs = shape(p_max)
        return abs(max_confidence(probs) - entropy_confidence(probs))

    def crossing(shape, threshold):
        """Smallest p_max whose scale gap is no wider than `threshold`, by bisection.

        A second bisection belongs here and not in `tests/_thresholds.py`, because it answers a
        different question (where the two scales converge) and has exactly one reader.
        """
        lo, hi = 0.99, 0.9999999
        for _ in range(200):
            mid = (lo + hi) / 2
            if scale_gap(shape, mid) > threshold:
                lo = mid
            else:
                hi = mid
        return hi

    # Question P_own: does THIS row's own published number sit inside both radius-TOLERANCE windows?
    # A row that publishes its `p_max` is at distance 0 from `max(p)`, so its entropy distance IS the
    # whole gap and the answer is gap <= TOLERANCE.
    p_own = crossing(remainder_uniform, TOLERANCE)
    # Question P_some: may SOME published value sit inside both windows at once? The two windows
    # intersect exactly when the gap is no wider than 2 * TOLERANCE, so the answer is that predicate
    # and the crossing sits lower -- a gap of up to 2 * TOLERANCE still has a value inside both, the
    # midpoint, which is why the two questions cannot share one number.
    p_some = crossing(remainder_uniform, 2 * TOLERANCE)
    assert p_own == pytest.approx(0.999855, abs=1e-5), p_own
    assert p_some == pytest.approx(0.999684, abs=1e-5), p_some
    assert scale_gap(remainder_uniform, 0.9995) == pytest.approx(0.002998, abs=1e-5)
    # The two questions are ~1.7e-4 apart on ONE shape. Each answer then moves again across shapes,
    # which is why the shipped comment could not be checked while it named neither the question nor
    # the shape. The bound below is what the comment states as "2e-5 to 8e-5 earlier", so the claim
    # is enforced here instead of living only in prose.
    assert 1e-4 < p_own - p_some < 2e-4, (p_own, p_some)
    lumpy, sparse = (crossing(remainder_lumpy, 2 * TOLERANCE), crossing(remainder_sparse, 2 * TOLERANCE))
    assert (lumpy, sparse) == (pytest.approx(0.999609, abs=1e-5), pytest.approx(0.999631, abs=1e-5))
    lumpy_own, sparse_own = (crossing(remainder_lumpy, TOLERANCE),
                             crossing(remainder_sparse, TOLERANCE))
    assert (lumpy_own, sparse_own) == (pytest.approx(0.999821, abs=1e-5),
                                       pytest.approx(0.999833, abs=1e-5))
    shifts = [p_some - lumpy, p_some - sparse, p_own - lumpy_own, p_own - sparse_own]
    assert all(2e-5 <= s <= 8e-5 for s in shifts), shifts
    # The shape the comment quotes is the LAST to absorb on both lines, so its figures are the
    # most conservative of the three: a lumpy or sparse row is inside both windows at a lower
    # p_max than 0.999855 / 0.999684, which is exactly why naming the shape is not a nicety.
    assert p_own == max(p_own, lumpy_own, sparse_own), (p_own, lumpy_own, sparse_own)
    assert p_some == max(p_some, lumpy, sparse), (p_some, lumpy, sparse)
    assert lumpy == min(lumpy, sparse, p_some), (lumpy, sparse, p_some)

    # Both predicates tied to the gate's own behaviour, not just to the arithmetic: which bucket a
    # row actually lands in. All four counts are compared, because "not `both`" splits into two
    # different answers -- a row can match exactly one scale, or match none.
    def buckets(d):
        return (d["both"], d["answer_only"], d["entropy_only"], d["neither"])

    def attributed(p_max, published):
        probs = tuple(remainder_uniform(p_max))
        return scale_attribution([_choice("b", probs, published)])

    def midpoint(p_max):
        probs = remainder_uniform(p_max)
        return (max_confidence(probs) + entropy_confidence(probs)) / 2

    # Above P_own the row's own number is inside both windows -- the absorbed case the comment names.
    absorbed = attributed(p_own, p_own)
    assert absorbed["verdict"] == "neither", absorbed
    assert buckets(absorbed) == (1, 0, 0, 0), absorbed
    # Between the two crossings the row's own number is NOT inside both windows: distance 0 from
    # max(p) and TOLERANCE < gap from the entropy scale, so it is `answer_only` and gets attributed.
    between_own = attributed(0.99975, 0.99975)
    assert between_own["verdict"] == "answer_confidence", between_own
    assert buckets(between_own) == (0, 1, 0, 0), between_own
    # ... while the value halfway between the scales IS inside both, which is what P_some counts.
    between_mid = attributed(0.99975, midpoint(0.99975))
    assert buckets(between_mid) == (1, 0, 0, 0), between_mid
    # Below P_some the gap exceeds 2 * TOLERANCE, so the midpoint of the two scales is already more
    # than TOLERANCE away from each and no published value can be counted `both`. 0.9995 sits below
    # the P_some crossing of all three shapes measured above (uniform 0.999684, sparse 0.999631,
    # lumpy 0.999609), so at that sharpness no k=4 row is absorbed on any of them; between the
    # lowest and the highest of those three, absorption is a property of the shape, not of the row.
    below = attributed(0.9995, midpoint(0.9995))
    assert buckets(below) == (0, 0, 0, 1), below


def test_the_shared_bisection_has_one_owner_and_no_argument_order_to_transpose():
    """The p_max solver is shared, so its call shape is a contract rather than a local style.

    `tests/_thresholds.py` is the only owner of the bisection and `tests/test_records.py` imports it.
    Before that merge the same search existed twice with the parameters in opposite orders --
    `p_max_for_entropy(target, k)` and `_pmax_reaching(k, target)` -- and the second copy is the one
    that polices figures quoted in the design docs. Two positional parameters meant a transposed call
    was legal syntax: measured on the pre-merge code, the swap that today raises was caught only
    because the solver multiplies a list by `k`, and an int-shaped pair of values was silent
    (`p_max_for_entropy(2, 4)` returned 1.0 -- a plausible number answering a different question).
    Keyword-only parameters close the whole class at the call site, and the two direction assertions
    below are what a body-level swap (parameters kept, meanings exchanged) would invert.
    """
    ref = p_max_for_entropy(target=0.85, k=4)
    # Increasing in `k`'s opposite: a fixed entropy target demands LESS mass on the answer as the
    # ballot grows, so the reference point must sit above the k=51 answer.
    wider = p_max_for_entropy(target=0.85, k=51)
    assert ref > wider, (ref, wider)
    # Increasing in `target`: demanding more entropy-confidence can never need less probability.
    higher = p_max_for_entropy(target=0.90, k=4)
    assert higher > ref, (higher, ref)

    # The call shape the deleted copy invited is now unrepresentable.
    with pytest.raises(TypeError):
        p_max_for_entropy(0.85, 4)
    with pytest.raises(TypeError):
        p_max_for_entropy(4, 0.85)
    # Feeding the right keywords the wrong values is not a second quiet answer either: k is an
    # option count and target is a probability, so the mismatch trips before the search converges.
    with pytest.raises(TypeError):
        p_max_for_entropy(target=4, k=0.85)

    # One owner, checkable rather than promised: a function at ANY nesting depth that repeats a search
    # over `entropy_confidence` -- in a `for`, an `async for`, a `while`, or through its own body -- is
    # the fingerprint of the duplicated search, and exactly one may carry it. A nested copy re-added
    # inside a test body is caught, which a module-level-only walk missed, and a `while`-loop copy is
    # caught too, which the first version of this fingerprint could not see (see `_entropy_bisectors`).
    owners = _entropy_bisectors(Path(__file__).resolve().parent)
    assert owners == ["_thresholds.py::p_max_for_entropy"], owners
    assert "_pmax_reaching" not in (Path(__file__).resolve().parent / "test_records.py").read_text(), \
        "the transposed copy is back: two owners of one derivation again"

