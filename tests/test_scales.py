"""Which confidence scale is a published number? Decided by distance, per backend."""
import collections
import json
import math
import re
from pathlib import Path

import pytest

from _thresholds import p_max_for_entropy, scale_gap, scale_midpoint
from autorate.records import Record
from autorate.scales import scale_attribution

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"
SCALES_SOURCE = Path(__file__).resolve().parents[1] / "src" / "autorate" / "scales.py"


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


def _entropy_scale_owners(tests_dir):
    """Every helper under `tests/` that reads the entropy scale -- the suite's owner inventory.

    This is the single-owner guard for the derivation that turns an entropy target back into a `p_max`:
    the same search written twice is exactly how a transposed parameter order survived a whole review
    round, so the COUNT and LOCATION of owners is the fact worth guarding, not any one value.

    The rule is OWNERSHIP, not syntax. A helper is an owner if, and only if, it is a function or lambda
    -- `FunctionDef`, `AsyncFunctionDef` or `Lambda`, at any nesting depth, at module level, inside a
    class, or inside another function -- whose name does not begin with `test_`, in any `.py` file under
    `tests/` (subdirectories included), that references `entropy_confidence` at all: as a call, as a
    bare name, as an attribute, or by importing it. Looping, folding, comprehending, awaiting, unrolling
    or holding state in an object says nothing about whether a helper owns the derivation, so none of it
    is asked.

    Why the shape list was dropped. Three consecutive rounds each found a new syntactic form that
    escaped the previous round's list, and each time the exclusion came with a reason the next plant
    refuted: `for` only, and a `while` copy escaped; `while` plus recursion added, and a
    `functools.reduce` copy escaped (the accumulator carries the interval, so there is no loop
    statement to find); the fold arm added and comprehensions excluded because "each element is
    evaluated independently", and a walrus-carrying comprehension escaped -- state does cross elements.
    The independent review then put three more live second owners through the same list -- an `async def`
    with an ordinary `for`, that comprehension, and a `__call__` driven by `itertools.starmap` -- and the
    two guard tests stayed green (measured, in `/tmp/r4`: all four plants, each proven to return the
    shared solver's own `0.960919733`, give exit 0). A list of shapes is a promise about the shapes
    somebody has thought of; ownership is a promise about everything.

    What is NOT a read, and why that is not an exemption: a string constant. The name `entropy_confidence`
    inside a docstring, or inside a source snippet another test plants, is prose about the scale, not a
    second solver, and this function is itself the proof -- its own body contains that string three times
    and reports nothing. Only the syntax tree is consulted.

    Where the rule's two exemptions live, both name-based and both stated in the guard test's own
    assertions rather than hidden here: `test_*` functions, which legitimately call the scale to assert
    about it; and `tests/_thresholds.py`, the owner module, whose scale-reading helpers are the point of
    the inventory -- the guard test pins that every entry it returns lives in that file and names each
    one, so a new derivation there is a decision a reader sees rather than a silent widening.

    The residuals, each written as a case in
    `test_the_owner_fingerprint_reports_every_shape_that_can_hold_a_scale_read` rather than as prose:
    (1) a second owner hidden inside a `test_*` function body is not reported, because test bodies are
    allowed to read the scale -- the loophole is real and is the price of the `test_*` exemption;
    (2) a narrowing search that reaches the scale only through a shared helper (the `crossing` shape in
    the gate test) is not reported, because it holds no scale arithmetic of its own -- it owns an
    interval, not a scale; (3) a helper that RE-DERIVES the entropy scale from first principles under a
    different name is invisible to a rule keyed on the name, and no ownership rule can see it -- that one
    is the class's floor, and it is why the module's own figures stay pinned by tests.

    `src/autorate/` is never walked: `scales.py` imports `entropy_confidence` from `autorate.records` at
    module level, and production code computing with the scale is what this whole module exists to do, not
    a duplicate test helper. Only `tests/` is scanned.

    The concrete name it is watching for is `_pmax_reaching`, the transposed copy a previous round deleted
    from `tests/test_records.py`; the guard test that calls this helper also checks for that name in
    that file, so a re-added copy is caught both by ownership and by name.
    """
    import ast

    scale = "entropy_confidence"
    function_forms = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def reads_scale(node):
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant):
                continue
            if isinstance(inner, ast.Name) and inner.id == scale:
                return True
            if isinstance(inner, ast.Attribute) and inner.attr == scale:
                return True
            if isinstance(inner, (ast.Import, ast.ImportFrom)) and any(
                    alias.name == scale or alias.asname == scale for alias in inner.names):
                return True
        return False

    def label(node, parents):
        parts = [getattr(node, "name", None) or "<lambda>"]
        walk_up = parents.get(node)
        while isinstance(walk_up, ast.ClassDef):
            parts.append(walk_up.name)
            walk_up = parents.get(walk_up)
        return ".".join(reversed(parts))

    found = []
    for path in sorted(tests_dir.rglob("*.py")):
        tree = ast.parse(path.read_text())
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, function_forms):
                continue
            if getattr(node, "name", "").startswith("test_"):
                continue
            if reads_scale(node):
                found.append("%s::%s" % (path.relative_to(tests_dir), label(node, parents)))
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
    for both backends, because the module's `n`-versus-cases comment and README's
    exchangeability bullet both quote it: jev's cases carry between one and three DISTINCT
    probability vectors (so 191 rows are not 191 observations), while laya's 192 rows are 64
    cases x 3 repeats that publish the same vector, the same number and the same gold label
    each time -- identical as measurements, not identical as rows. The three sentences README
    writes on top of that ("the same 64 cases", "one case carries two rows, not three", "the
    repeat counter and its own elapsed time differ") are owned by the distribution, the set
    equality and the varying-key counts below, because a set of sizes and two matching lengths
    can all hold while those three are false.
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
    # "the SAME 64 cases" -- the README's word, and the claim that makes the case denominator comparable
    # across the two backends at all. Two lengths equal to 64 do not make two sets equal (five cases
    # missing on one side and five extra on the other keeps every count in this file true), so the sets
    # themselves are asserted, not their sizes. Measured: identical, nothing on either side.
    assert laya_cases == jev_cases, (sorted(laya_cases - jev_cases), sorted(jev_cases - laya_cases))

    # The repeat structure `scales.py` quotes about `n`, produced for both backends rather than
    # asserted in prose. laya: 64 cases x exactly 3 rows, and every case's rows carry ONE `probs`
    # vector, ONE published `reported_confidence` and ONE gold label -- while no case's three rows are
    # identical as rows, since each carries its own repeat counter and elapsed time. The distinction is
    # the whole point of the sentence: three rows that measure the same thing are not three
    # observations, and calling them byte-identical would claim something the file refutes.
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
        and len({json.dumps(r["gold"], sort_keys=True) for r in g}) == 1
        for g in laya_groups.values())
    assert one_measurement_per_case, \
        "laya's repeats no longer publish one vector, one number and one gold label per case"
    # README:33-35 says what a repeat shares is the measurement and NOT the row, naming the two fields
    # that differ. Both halves are now produced: no case's three rows are identical, and the keys that
    # vary are exactly `repeat`, `slices.repeat` and `meta.elapsed_ms` -- so the parenthetical is a
    # measurement of the archive rather than a guess about which field carries the difference.
    varying = collections.Counter()
    for g in laya_groups.values():
        assert len({json.dumps(r, sort_keys=True) for r in g}) > 1, "a laya case's rows became one row"
        for key in set().union(*(set(r) for r in g)):
            if len({json.dumps(r.get(key), sort_keys=True) for r in g}) > 1:
                varying[key] += 1
    assert dict(varying) == {"repeat": 64, "slices": 64, "meta": 64}, dict(varying)
    nested = collections.Counter()
    for g in laya_groups.values():
        for field in ("slices", "meta"):
            for key in set().union(*(set(r.get(field) or {}) for r in g)):
                if len({json.dumps((r.get(field) or {}).get(key)) for r in g}) > 1:
                    nested["%s.%s" % (field, key)] += 1
    assert dict(nested) == {"slices.repeat": 64, "meta.elapsed_ms": 64}, dict(nested)
    # jev: one case carries two rows and the other 63 carry three, and between 1 and 3 DISTINCT
    # probability vectors sit inside a case. Counted as a DISTRIBUTION, not as the set of sizes that
    # occur: `{2, 3} == {2, 3}` stays true if five cases carry two rows, and README:32's "one case
    # carries two rows, not three" is exactly the claim that would then be false.
    jev_groups = _groups("jev")
    assert collections.Counter(len(g) for g in jev_groups.values()) == {3: 63, 2: 1}, jev_groups
    assert len(jev_groups) == 64 and sum(len(g) for g in jev_groups.values()) == 191, jev_groups
    assert {len({json.dumps(r["probs"], sort_keys=True) for r in g})
            for g in jev_groups.values()} == {1, 2, 3}, jev_groups
    # Both new lines above are guards, and what they guard is shown rather than claimed. This plant is
    # in-memory over a copy of the parsed groups, so the archive is untouched: it is the case where the
    # two weaker forms this file used to carry -- a set of sizes, and two equal lengths -- still pass
    # while the README sentences they were quoted as owning are false. If the Counter or the set
    # equality is ever relaxed back to those forms, the last two assertions here stop being interesting
    # and the first two sentences above stop being owned, which is what a reader should notice.
    doctored = {c: list(g) for c, g in jev_groups.items()}
    for case_id in sorted(doctored)[:5]:
        doctored[case_id] = doctored[case_id][:-1]
    assert {len(g) for g in doctored.values()} == {2, 3}, \
        "the set-of-sizes form is no longer blind here, so the Counter is doing nothing"
    assert collections.Counter(len(g) for g in doctored.values()) != {3: 63, 2: 1}
    planted = set(jev_cases)
    moved = planted.pop()
    planted.add(moved + "-renamed")
    assert len(planted) == len(laya_cases) == 64, (len(planted), len(laya_cases))
    assert planted != laya_cases


def _inline_scale_subtractions(tests_dir):
    """Every place a test computes `max_confidence(p) - entropy_confidence(p)` itself, at ANY scope.

    The ownership rule cannot see this shape at all: it reads helper definitions, and a `test_*` body is
    exempt, so the arithmetic the suite moved into `tests/_thresholds.py::scale_gap` survived a second
    copy 500 lines away in the same file that documents the rule. This detector is narrower on purpose
    and blind to no scope -- the subtraction of the two published scales has exactly one owner, and it
    fires wherever the expression is written, module level or test body alike.

    It is not a general single-owner guard. An indirect narrowing that reaches the scale through a
    shared helper, and a helper that re-derives the entropy scale under another name, stay invisible
    here exactly as they stay invisible to `_entropy_scale_owners`, and both are named there as
    residuals rather than papered over.
    """
    import ast

    scales = ("max_confidence", "entropy_confidence")
    hits = []
    for path in sorted(tests_dir.rglob("*.py")):
        if path.name == "_thresholds.py":
            continue  # the owner: this is the one file where the subtraction is allowed to live
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)):
                continue
            names = {c.func.id for c in (node.left, node.right)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                     and c.func.id in scales}
            if names == set(scales):
                hits.append("%s:%d" % (path.relative_to(tests_dir), node.lineno))
    return hits


_NOTE_FIRST_LINE = "The pair the old comment forecast"
_NOTE_LAST_LINE = "test_collapsing_jev_to_one_row_per_case"
_CASE_CLAIM = re.compile(r"(answer|entropy)-scale case: repeats \[([\d, ]+)\]")
_ROW_CLAIM = re.compile(
    r"(published maximum|forecast figure|lowest-repeat row) (0\.\d+) at row index (\d+), "
    r"repeat (\d+), (lowest|middle|highest) of its repeats")
_NOTE_ROLES = ("published maximum", "forecast figure", "lowest-repeat row")


def _scale_note_lines():
    """The collapse note inside `src/autorate/scales.py`, as text.

    That note is prose about the committed archive, and before this helper nothing in the suite opened
    `scales.py` as text -- so the note had no failure path whatsoever: a sentence in it that the rows
    contradict would ship green forever, which is the defect class this lane keeps being dispatched for.
    The note is delimited by its own first line and by the pointer to the test that checks it, so a
    deleted, moved or truncated note reddens here instead of quietly stopping being read.
    """
    lines = SCALES_SOURCE.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if _NOTE_FIRST_LINE in line]
    assert len(starts) == 1, starts
    body = lines[starts[0]:]
    ends = [i for i, line in enumerate(body) if _NOTE_LAST_LINE in line]
    assert len(ends) == 1, ends
    return body[:ends[0] + 1]


def _scale_note_claims():
    """Parse the note's per-case claim lines into {scale: {"repeats": [...], "claims": [...]}}.

    The grammar is the note's own: one `repeats [...]` line per case, then exactly one line per role
    (`published maximum`, `forecast figure`, `lowest-repeat row`) carrying the figure, the row index, the
    repeat on that row, and the ordinal word claimed for it. Shape is asserted here, not assumed, so a
    claim that goes missing or is reworded out of the grammar is a failure rather than a skipped check.
    """
    parsed = {}
    current = None
    for line in _scale_note_lines():
        case = _CASE_CLAIM.search(line)
        if case:
            current = case.group(1)
            parsed[current] = {"repeats": [int(x) for x in case.group(2).split(",")], "claims": []}
            continue
        row = _ROW_CLAIM.search(line)
        if row:
            assert current is not None, "a claim line outside any case block: %r" % line
            role, figure, index, repeat, ordinal = row.groups()
            parsed[current]["claims"].append((role, figure, int(index), int(repeat), ordinal))
    assert sorted(parsed) == ["answer", "entropy"], parsed
    for scale, block in parsed.items():
        assert len(block["claims"]) == 3, (scale, block["claims"])
        assert {c[0] for c in block["claims"]} == set(_NOTE_ROLES), (scale, block["claims"])
    return parsed


def test_collapsing_jev_to_one_row_per_case_does_not_move_the_published_maxima():
    """What the follow-up note predicted, measured: its pair is a tie-break, not a consequence.

    `scales.py` carried a note claiming that collapsing jev's 191 archived choice rows to its 64
    cases "moves the published maxima from 0.170 to 0.160 and from 0.157315 to 0.147315". The blocker
    it named -- `Record.from_dict` dropping `case_id` -- landed before this could be reasoned about,
    so it could be RUN, and the result is that both halves of the pair are real numbers whose
    appearance depends entirely on which row a collapsed case keeps:

    * a collapse that keeps each case's WORST row -- the only one that preserves what the gate is,
      since the gate takes a maximum over rows -- leaves both maxima exactly where they are. That first
      bullet is a PROOF and not a measurement: a maximum over per-case maxima is the maximum over all
      rows for any archive whatsoever, so no file could redden it, and what is falsifiable instead is
      where inside the case the published maximum sits -- it is its own case's worst row on that scale,
      at a row index the archive-order tie-break throws away;
    * a collapse that keeps each case's FIRST ROW IN ARCHIVE ORDER -- what grouping the file without
      sorting gives a reader -- produces 0.160 and 0.147315, precisely by discarding those two cases'
      worst row.

    The second bullet is not the same operation as "keep the first repeat", and the difference is a
    number: 52 of the 64 cases are not in ascending `repeat` order in the file, so the ordinal reading
    gives 0.160 and **0.150882**. The module comment used to name the ordinal while printing the
    archive-order figure; both readings are asserted below from the same rows, so the two cannot be
    confused again. The predicted pair is therefore reachable -- but only through an aggregation this
    gate must not use, and only under a tie-break whose name is not the one the comment gave it.

    The two tie-breaks are distinguishable on the entropy scale ALONE. On the answer scale the case
    carrying the maximum keeps the same row under both readings -- its first row is also its lowest
    repeat -- so both give 0.160; only the entropy case's rows separate, 0.147315 from 0.150882. The
    last block below checks `scales.py`'s own note as text: every figure it prints, every row index,
    repeat and ordinal word it claims is re-derived from the rows computed here, so the comment is
    derived prose with a failure path rather than a sentence nobody reads.
    """
    from autorate.records import entropy_confidence, max_confidence

    archived = _archive_slice("jev", "choice")
    rows = []
    repeats = {}
    for r in archived:
        reported = (r.scores or {}).get("reported_confidence")
        if reported is None or len(r.probs) < 2:
            continue
        rows.append((r.case_id, abs(reported - max_confidence(r.probs)),
                     abs(reported - entropy_confidence(r.probs))))
        repeats.setdefault(r.case_id, []).append(r.repeat)
    assert len(rows) == 191, len(rows)
    # The denominator every figure in this file and in the module comment is quoted over: the filter
    # above drops NOTHING from the jev choice slice, so "52 of the 64 jev cases" and the collapse
    # figures describe the same 191 rows / 64 cases the archive test counts. If a future case lost its
    # `reported_confidence`, the population these numbers belong to would change and this line reddens
    # first -- a filtered denominator silently narrower than the sentence's is the defect, not this assert.
    assert len(archived) == len(rows) == 191, (len(archived), len(rows))
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

    # The worst-row collapse, kept only as the tie from the two figures above to the collapse itself. It
    # cannot go red for any archive: `max` over per-case `max`es IS `max` over rows. Named here so a
    # reader does not mistake it for the measurement the bullet claims.
    worst = [(max(p[0] for p in v), max(p[1] for p in v)) for v in by_case.values()]
    assert max(w[0] for w in worst) == pytest.approx(published_answer, abs=1e-12)
    assert max(w[1] for w in worst) == pytest.approx(published_entropy, abs=1e-12)

    first = [v[0] for v in by_case.values()]
    first_max_answer = max(f[0] for f in first)
    first_max_entropy = max(f[1] for f in first)
    assert first_max_answer == pytest.approx(0.160, abs=5e-7), first_max_answer
    assert first_max_entropy == pytest.approx(0.147315, abs=5e-7), first_max_entropy

    # Reading the tie-break by ordinal rather than by file position, measured rather than argued: 52 of
    # the 64 jev cases are not in ascending `repeat` order in the file, and the ordinal reading gives a
    # different entropy maximum -- 0.150882, which sits on the entropy case's middle ROW, the row that
    # carries its LOWEST repeat (0), while the case's first row carries repeat 1. The comment in
    # `scales.py` used to call that figure "the middle repeat", which is true of the row's position and
    # false of its ordinal; this line is the measurement that separated the two, and it is why the
    # comment now says "first row in archive order".
    not_ascending = [c for c in by_case if repeats[c] != sorted(repeats[c])]
    assert len(not_ascending) == 52, (len(not_ascending), len(by_case))
    lowest_repeat = [by_case[c][repeats[c].index(min(repeats[c]))] for c in by_case]
    low_max_answer = max(x[0] for x in lowest_repeat)
    low_max_entropy = max(x[1] for x in lowest_repeat)
    assert low_max_answer == pytest.approx(0.160, abs=5e-7)
    assert low_max_entropy == pytest.approx(0.150882, abs=5e-7)
    # The two tie-breaks on one line each way: identical on the answer scale (the same row survives),
    # 3.6e-3 apart on the entropy scale. `abs=1e-12` is 5e7 times tighter than the 5e-7 the published
    # figures are quoted at, so the equality is a real assertion, not the printed number re-labelled.
    assert first_max_answer == pytest.approx(low_max_answer, abs=1e-12), (first_max_answer,
                                                                          low_max_answer)
    assert abs(first_max_entropy - low_max_entropy) > 1e-3, (first_max_entropy, low_max_entropy)

    # And the structural fact that lets both readings coexist, stated per case because no universal
    # holds. Inside each of the two cases the published maximum sits in the LAST ROW and the forecast
    # figure in the FIRST ROW, and the archive files these rows out of `repeat` order -- but the two
    # cases part ways differently: the answer case's last row is its MIDDLE repeat (repeats [0, 2, 1],
    # so the last row carries repeat 1) while the entropy case's last row IS its HIGHEST repeat
    # (repeats [1, 0, 2]); symmetrically the answer case's first row IS its lowest repeat, while the
    # entropy case's first row carries repeat 1 and its lowest repeat sits in the middle row. That is
    # exactly why the two tie-breaks separate on the entropy scale alone. Pinned case by case so the
    # universal reading cannot quietly come back:
    answer_case = max(by_case, key=lambda c: max(p[0] for p in by_case[c]))
    entropy_case = max(by_case, key=lambda c: max(p[1] for p in by_case[c]))
    assert repeats[answer_case] == [0, 2, 1], repeats[answer_case]
    assert repeats[entropy_case] == [1, 0, 2], repeats[entropy_case]
    assert by_case[answer_case][-1][0] == pytest.approx(0.170, abs=5e-7)
    assert by_case[answer_case][0][0] == pytest.approx(0.160, abs=5e-7)
    assert by_case[entropy_case][-1][1] == pytest.approx(0.157315, abs=5e-7)
    assert by_case[entropy_case][0][1] == pytest.approx(0.147315, abs=5e-7)
    assert by_case[entropy_case][repeats[entropy_case].index(0)][1] == pytest.approx(0.150882, abs=5e-7)
    assert sorted(round(p[0], 6) for p in by_case[answer_case]) == [0.16, 0.16, 0.17]
    assert sorted(round(p[1], 6) for p in by_case[entropy_case]) == [0.147315, 0.150882, 0.157315]
    # What the falsifiable half of the first bullet is: each published maximum sits on its own case's
    # worst row on its own scale, at an index the archive-order tie-break discards -- which is a fact
    # about this archive, not an identity, and the only version of the bullet that can go red.
    max_row = {
        "answer": max(range(len(by_case[answer_case])), key=lambda i: by_case[answer_case][i][0]),
        "entropy": max(range(len(by_case[entropy_case])), key=lambda i: by_case[entropy_case][i][1]),
    }
    assert max_row == {"answer": 2, "entropy": 2}, max_row
    assert all(index != 0 for index in max_row.values()), max_row

    # `scales.py`'s note, read as text and checked against everything computed above.
    note = _scale_note_claims()
    note_text = "\n".join(_scale_note_lines())
    for scale, case_id, published, forecast, kept in (
            ("answer", answer_case, published_answer, first_max_answer, low_max_answer),
            ("entropy", entropy_case, published_entropy, first_max_entropy, low_max_entropy)):
        block = note[scale]
        assert block["repeats"] == repeats[case_id], (scale, block["repeats"], repeats[case_id])
        ranks = sorted(set(repeats[case_id]))
        for role, figure, index, repeat, ordinal in block["claims"]:
            assert 0 <= index < len(repeats[case_id]), (scale, role, index)
            assert repeats[case_id][index] == repeat, (scale, role, index, repeat)
            rank = ranks.index(repeat)
            expected = ("lowest" if rank == 0 else
                        "highest" if rank == len(ranks) - 1 else "middle")
            assert ordinal == expected, (scale, role, repeat, ordinal, expected)
            if role == "published maximum":
                assert index == max_row[scale], (scale, index, max_row[scale])
                assert abs(float(figure) - published) <= 5e-7, (figure, published)
            elif role == "forecast figure":
                assert index == 0, (scale, index)
                assert abs(float(figure) - forecast) <= 5e-7, (figure, forecast)
            else:
                assert repeat == min(repeats[case_id]), (scale, repeat)
                assert abs(float(figure) - kept) <= 5e-7, (figure, kept)
        # The same-row claim the note makes about the answer scale, and the different-row claim it makes
        # about the entropy scale -- both read out of the parsed lines rather than trusted.
        by_role = {c[0]: c for c in block["claims"]}
        assert (by_role["forecast figure"][2] == by_role["lowest-repeat row"][2]) == (scale == "answer"), \
            (scale, by_role)
    quoted = set(re.findall(r"\b0\.\d{3,6}\b", note_text))
    assert quoted == {"0.170", "0.160", "0.157315", "0.147315", "0.150882"}, sorted(quoted)
    counts = re.search(r"(\d+) of the (\d+) jev cases", note_text)
    assert counts is not None, note_text
    assert (int(counts.group(1)), int(counts.group(2))) == (len(not_ascending), len(by_case)), \
        counts.groups()


def test_a_record_whose_two_scales_are_the_same_number_is_attributed_to_neither():
    # A one-hot distribution reads 1.0 on BOTH scales, so distance cannot separate them here
    # -- and 94 of jev's 191 archived choice records are one-hot, counted below rather than
    # quoted. Naming one scale would be a coin flip dressed as a measurement, so the function
    # says neither and leaves the choosing to a caller with better evidence than it has.
    # The gap is asked of the owner module (`_thresholds.scale_gap`): this file's rule is that
    # `|max(p) - entropy|` is derived in one place, and a test body writing the expression inline
    # is the one loophole that rule cannot see by name.
    one_hot = (1.0, 0.0, 0.0, 0.0)
    assert scale_gap(one_hot) < 1e-12
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
    from autorate.scales import TOLERANCE

    laya = _archive_slice("laya", "choice")
    # The comment's slice size is asserted, not assumed: the headroom claim below is a statement about
    # THIS slice, so the count it quotes ("laya's 192 archived choice records") is produced here too.
    # Redundant by design -- the same 192 is pinned in
    # `test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides`, so this line
    # cannot go red while that one is green -- and it exists only so the module comment's pointer
    # resolves in this test. It is not inert: dropping any laya choice row reddens both lines.
    assert len(laya) == 192, len(laya)
    # `scale_gap` is the owner of this subtraction and this test quotes its result as the module's
    # headroom figure, so the arithmetic is asked of the owner rather than restated inline: an inline
    # copy is exactly the second derivation the ownership rule exists to prevent, and it is invisible
    # to that rule by construction because the rule reads helper definitions, not `test_*` bodies.
    gap = min(scale_gap(r.probs) for r in laya)
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

    def scale_gap_at(shape, p_max):
        # Thin shape adapter: it picks the probability vector, then asks the OWNER module for the gap.
        # That is why this helper is not a second reader of the entropy scale -- the reference is to
        # `scale_gap`, not to `entropy_confidence` -- and why the owner guard reports nothing here.
        return scale_gap(shape(p_max))

    def crossing(shape, threshold):
        """Smallest p_max whose scale gap is no wider than `threshold`, by bisection.

        A second narrowing search belongs here and not in `tests/_thresholds.py`, because it owns no
        scale arithmetic of its own: it asks the owner module for the gap and bisects WHERE THE TWO
        SCALES CONVERGE, a different question with one reader. The ownership rule reports it for exactly
        that reason, and the report is tested (the `indirect_narrowing` case in
        `test_the_owner_fingerprint_reports_every_shape_that_can_hold_a_scale_read`), not asserted here.
        """
        lo, hi = 0.99, 0.9999999
        for _ in range(200):
            mid = (lo + hi) / 2
            if scale_gap_at(shape, mid) > threshold:
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
    assert scale_gap_at(remainder_uniform, 0.9995) == pytest.approx(0.002998, abs=1e-5)
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
        # The value a published confidence must take to sit exactly between the two scales. The
        # arithmetic is the owner module's (`scale_midpoint`, which is what reads the scale); this
        # adapter only supplies the uniform-remainder shape the comment quotes.
        return scale_midpoint(remainder_uniform(p_max))

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

    # One owner, checkable rather than promised. The rule is ownership, not syntax: every helper in
    # `tests/` that reads the entropy scale must live in the owner module, and this pins both halves --
    # nothing outside it (the shape list this replaced was found blind three rounds running, see
    # `_entropy_scale_owners`), and the exact inventory inside it, so a new derivation there is a named
    # decision rather than a silent widening.
    owners = _entropy_scale_owners(Path(__file__).resolve().parent)
    assert [o for o in owners if not o.startswith("_thresholds.py::")] == [], owners
    assert owners == ["_thresholds.py::p_max_for_entropy", "_thresholds.py::scale_gap",
                      "_thresholds.py::scale_midpoint"], owners
    assert "_pmax_reaching" not in (Path(__file__).resolve().parent / "test_records.py").read_text(), \
        "the transposed copy is back: two owners of one derivation again"
    # The shape ownership cannot see, policed separately: the two scales subtracted from each other
    # inline. Zero hits across `tests/` today because the two copies this file carried now call
    # `scale_gap`; the `inline_gap_in_test_body` case in the plant test writes it where the ownership
    # rule is blind to it and requires this detector to report it, so the count here is a guard with a
    # demonstrated failure path and not an empty sweep.
    assert _inline_scale_subtractions(Path(__file__).resolve().parent) == [], \
        _inline_scale_subtractions(Path(__file__).resolve().parent)



def test_the_owner_fingerprint_reports_every_shape_that_can_hold_a_scale_read(tmp_path):
    """The ownership rule is tested by planting owners, and by planting the exclusions it claims.

    `test_the_shared_bisection_has_one_owner_and_no_argument_order_to_transpose` asks the live question
    (who reads the scale, and does every reader live in the owner module). This asks whether the detector
    can fail at all, in both directions. Every shape that has escaped it is planted here and must be
    reported: the `while` copy, the recursive copy, the `functools.reduce` copy, the three the independent
    review found live while both guard tests stayed green -- an `async def` with an ordinary `for`, a
    walrus-carrying comprehension, and a `__call__` driven by `itertools.starmap` -- and the straight-line
    unrolled copy the previous docstring conceded as its residual. A bare single read in a helper is
    reported too: the question was never whether a helper repeats, so the exemption it used to enjoy is
    gone. (Liveness of the planted copies was measured outside the suite: in `/tmp/r4` each of the four
    new shapes returns the shared solver's own 0.960919733 for target 0.85 / k 4, delta 0.00e+00, so the
    plant is a working second solver and not a decorative stub.)

    Each exclusion is planted as well, because a reason for an exclusion that is never tested is the exact
    mistake this rule replaces: a `test_*` body reading the scale is legitimate -- and so is a second owner
    hidden inside one, which is the residual this pins as accepted rather than denied -- a helper that
    bisects by asking the owner module for the gap is not a reader, and a docstring or a source string that
    only NAMES the scale is prose.
    """
    import textwrap

    header = "import functools\n\nfrom autorate.records import entropy_confidence\n\n"
    shapes = {
        "while_loop": textwrap.dedent("""
            def pmax(target, k):
                lo, hi = 1.0 / k, 1.0
                n = 0
                while n < 80:
                    n += 1
                    mid = (lo + hi) / 2
                    probs = [mid] + [(1 - mid) / (k - 1)] * (k - 1)
                    if entropy_confidence(tuple(probs)) < target:
                        lo = mid
                    else:
                        hi = mid
                return lo
        """),
        "recursion": textwrap.dedent("""
            def pmax(target, k, lo=None, hi=1.0):
                lo = 1.0 / k if lo is None else lo
                if hi - lo < 1e-9:
                    return lo
                mid = (lo + hi) / 2
                probs = [mid] + [(1 - mid) / (k - 1)] * (k - 1)
                if entropy_confidence(tuple(probs)) < target:
                    return pmax(target, k, mid, hi)
                return pmax(target, k, lo, mid)
        """),
        "fold": textwrap.dedent("""
            def pmax(target, k):
                def step(state, _):
                    lo, hi = state
                    mid = (lo + hi) / 2
                    probs = [mid] + [(1 - mid) / (k - 1)] * (k - 1)
                    return (mid, hi) if entropy_confidence(tuple(probs)) < target else (lo, mid)
                return functools.reduce(step, range(80), (1.0 / k, 1.0))
        """),
        # The three shapes the review planted while both guard tests passed, plus the conceded residual.
        "async_def": textwrap.dedent("""
            async def pmax(target, k):
                lo, hi = 1.0 / k, 1.0
                for _ in range(80):
                    mid = (lo + hi) / 2
                    probs = [mid] + [(1 - mid) / (k - 1)] * (k - 1)
                    if entropy_confidence(tuple(probs)) < target:
                        lo = mid
                    else:
                        hi = mid
                return hi
        """),
        "walrus_comprehension": textwrap.dedent("""
            def pmax(target, k):
                lo, hi = 1.0 / k, 1.0
                [
                    (mid := (lo + hi) / 2,
                     (lo := mid) if entropy_confidence([mid] + [(1 - mid) / (k - 1)] * (k - 1)) < target
                     else (hi := mid))
                    for _ in range(80)
                ]
                return hi
        """),
        "starmap_callable": textwrap.dedent("""
            class Solver:
                def __init__(self, target, k):
                    self.target = target
                    self.k = k
                    self.lo = 1.0 / k
                    self.hi = 1.0

                def __call__(self, _):
                    mid = (self.lo + self.hi) / 2
                    probs = [mid] + [(1 - mid) / (self.k - 1)] * (self.k - 1)
                    if entropy_confidence(tuple(probs)) < self.target:
                        self.lo = mid
                    else:
                        self.hi = mid
                    return self.hi


            def pmax(target, k):
                import itertools
                return list(itertools.starmap(Solver(target, k), [(None,)] * 80))[-1]
        """),
        # The residual the shape rule admitted: no loop, no fold, no self-reference. Under ownership it is
        # not a residual -- reading the scale in a helper is the whole test, repeated or not.
        "straight_line": textwrap.dedent("""
            def pmax(target, k):
                lo, hi = 1.0 / k, 1.0
                mid = (lo + hi) / 2
                lo = mid if entropy_confidence([mid] + [(1 - mid) / 3] * 3) < target else lo
                mid = (lo + hi) / 2
                hi = mid if entropy_confidence([mid] + [(1 - mid) / 3] * 3) >= target else hi
                mid = (lo + hi) / 2
                lo = mid if entropy_confidence([mid] + [(1 - mid) / 3] * 3) < target else lo
                return hi
        """),
        # Reported now, exempt before: one read in a helper is still a second site owning a read.
        "plain_read": textwrap.dedent("""
            def score(p):
                return entropy_confidence(p) > 0.5
        """),
        # The loophole the ownership rule is structurally blind to, written out: the two published scales
        # subtracted from each other inside a `test_*` body. Ownership reports nothing there -- test
        # bodies may read the scale -- and the gap detector reports the line, because that subtraction has
        # exactly one owner. This is the copy that survived the rule for a whole round.
        "inline_gap_in_test_body": textwrap.dedent("""
            from autorate.records import max_confidence


            def test_the_narrowest_gap_is_the_smallest_of_them():
                return abs(max_confidence([0.7, 0.3]) - entropy_confidence([0.7, 0.3]))
        """),
        # --- the exclusions, each planted so that the claim is measured rather than asserted ---
        # A test body asserts about the scale. This is also the accepted loophole: a second owner written
        # inside a test function is invisible to this rule by construction.
        "test_body_read": textwrap.dedent("""
            def test_the_scale_reads_zero_on_uniform_mass():
                assert entropy_confidence([0.25, 0.25, 0.25, 0.25]) == 0.0
        """),
        # A helper that owns an interval and asks the owner module for the scale is not a second reader --
        # the `crossing` shape in the gate test above, written out so the exclusion has a case.
        "indirect_narrowing": textwrap.dedent("""
            from _thresholds import scale_gap


            def crossing(shape, threshold):
                lo, hi = 0.99, 0.9999999
                for _ in range(200):
                    mid = (lo + hi) / 2
                    if scale_gap(shape(mid)) > threshold:
                        lo = mid
                    else:
                        hi = mid
                return hi
        """),
        # Prose about the scale, and source code inside a string, are not reads. This very file is the
        # real-tree instance of both forms, which is why the rule consults the tree and not the text.
        "prose_mention": textwrap.dedent('''
            """Documents the entropy scale without evaluating it."""

            SOURCE = "def pmax(target, k): return entropy_confidence([target])"


            def describe():
                """`entropy_confidence` appears in this docstring only."""
                return SOURCE
        '''),
        # A solver in a package under tests/ escapes a one-level walk. The review measured that escape on
        # the previous fingerprint; the scan is recursive now, so this shape is reported with its path.
        "nested_package": textwrap.dedent("""
            from autorate.records import entropy_confidence


            def pmax(target, k):
                lo, hi = 1.0 / k, 1.0
                for _ in range(80):
                    mid = (lo + hi) / 2
                    if entropy_confidence([mid] + [(1 - mid) / (k - 1)] * (k - 1)) < target:
                        lo = mid
                    else:
                        hi = mid
                return hi
        """),
    }
    expected = {
        "while_loop": ["plant_while_loop.py::pmax"],
        "recursion": ["plant_recursion.py::pmax"],
        # The outer `pmax` is reported as well as its inner `step`: the outer function's body contains
        # the read, so it owns the read too. Two names, one plant, and the count is the point.
        "fold": ["plant_fold.py::pmax", "plant_fold.py::step"],
        "async_def": ["plant_async_def.py::pmax"],
        "walrus_comprehension": ["plant_walrus_comprehension.py::pmax"],
        "starmap_callable": ["plant_starmap_callable.py::Solver.__call__"],
        "straight_line": ["plant_straight_line.py::pmax"],
        "plain_read": ["plant_plain_read.py::score"],
        "test_body_read": [],
        "indirect_narrowing": [],
        "prose_mention": [],
        "nested_package": ["pkg/sub.py::pmax"],
        "inline_gap_in_test_body": [],
    }
    # The plant list and the expectation table are policed as a pair: a shape added here and left out
    # there KeyErrors, and an expectation with no shape behind it would silently stop being executed.
    assert set(shapes) == set(expected), (sorted(set(shapes) ^ set(expected)),)
    for name, body in shapes.items():
        lane = tmp_path / name
        lane.mkdir()
        if name == "nested_package":
            (lane / "pkg").mkdir()
            (lane / "pkg" / "sub.py").write_text(body)
        else:
            (lane / ("plant_%s.py" % name)).write_text(header + body)
        owners = _entropy_scale_owners(lane)
        assert owners == expected[name], (name, owners)
        gap_hits = _inline_scale_subtractions(lane)
        if name != "inline_gap_in_test_body":
            # No other plant writes the two scales against each other: a narrowing, a fold or a plain
            # read over `entropy_confidence` is not the gap, and the detector must not shout at those.
            assert gap_hits == [], (name, gap_hits)
    gap_lane = tmp_path / "inline_gap_in_test_body"
    gap_hits = _inline_scale_subtractions(gap_lane)
    assert [h.split(":")[0] for h in gap_hits] == ["plant_inline_gap_in_test_body.py"], gap_hits
    assert len(gap_hits) == 1, gap_hits
    hit_line = (gap_lane / "plant_inline_gap_in_test_body.py").read_text().splitlines()[
        int(gap_hits[0].split(":")[1]) - 1]
    assert "max_confidence" in hit_line and "entropy_confidence" in hit_line, hit_line
    assert _entropy_scale_owners(gap_lane) == [], "ownership now sees the test body too"
