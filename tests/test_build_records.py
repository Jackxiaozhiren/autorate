"""Plan C Task 2: the scoring driver's pure layer, and the exit codes of its real entry point.

Two rules shape this file. First: nothing here imports torch, laya or a model -- the conversion,
the `u` draw and the parity comparison are testable with no model in the room, which is the whole
point of the split (the unit suite runs offline forever, ledger R-12 condition 1). The one
exception is the chunking-equivalence test, which is the one claim here that cannot be settled by
arithmetic: it runs the real checkpoint as a *subprocess*, in the vendored interpreter, and still
imports nothing of its own. Second: a guard is only real if it can be shown to fire, so every
refusal -- a parity miss, a cache that disagrees with the pin, a softmax that diverges from
upstream's, a chunk layout that could not have produced its own case count, a worker that dies --
is driven to its red here with the defect planted in a fixture, never by relaxing an assertion.

The subprocess tests drive `python3 tools/build_records.py`, the documented invocation, and read
the exit code the shell sees. The model stage is replaced by a planted interpreter and a planted
upstream tree, so the code under test is the code the real build runs: argument handling, the pin
check, the payload checks, the conversion, the parity gate, the two regimes one pass writes, and
the refusal to write anything.
"""
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from autorate.records import Record
from tools.build_records import (
    CALIBRATION_CLAMPED,
    CALIBRATION_IN_RANGE,
    CALIBRATION_REJECTED,
    CERTIFIED_REGIME,
    DEFAULT_CHUNK_SIZE,
    PARITY,
    PARITY_REGIME,
    REGIMES,
    BuildError,
    DriftError,
    IncompleteBuildError,
    ParityError,
    UStreamExhausted,
    UsageRefusal,
    calibration_status,
    check_parity,
    chunk_sizes,
    draw_u,
    records_from_logits,
    report_from_records,
    score_cases_in_chunks,
    softmax_t,
)

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / "tools" / "build_records.py"
PIN_SCHEMA = "autorate-massive-pin/1"
PROBE_KEYS = ("accuracy", "mean_confidence", "macro_f1", "ece")
REVISION = "940fd47a81eaa7f2cc7b129674d945d618ac38c2"
# The two temperatures the two regimes really are on this checkpoint (R-118): the raw
# `choice:11+` bucket the published sweep was produced with, and the value upstream clamps it to.
RAW_TEMPERATURE = 0.10058280825614929
CLAMPED_TEMPERATURE = 0.5


# --------------------------------------------------------------------- the plan's own tests
def _fake_logits(k, gold, mass=0.6):
    z = [0.0] * k
    z[gold] = math.log(mass / (1 - mass)) * 4      # a clearly-peaked distribution
    return [x + 0.01 * i for i, x in enumerate(z)]


def test_probs_sum_to_one_and_gold_is_a_key_not_an_index():
    keys = ["label_%d" % i for i in range(5)]
    recs = records_from_logits([_fake_logits(5, 2)], [2], [keys], "en", iter([0.5]))
    r = recs[0]
    assert abs(sum(r["probs"]) - 1.0) <= 1e-6
    assert r["gold"] == keys[2] and r["options"] == keys
    assert r["probs"] == [round(x, 6) for x in r["probs"]], "4-decimal parity with upstream"


def test_the_randomisation_draw_is_recorded_and_reproducible_from_a_stated_seed():
    a = list(draw_u(seed=7, n=4))
    b = list(draw_u(seed=7, n=4))
    assert a == b and len(set(a)) == 4 and all(0.0 <= x < 1.0 for x in a)
    assert list(draw_u(seed=8, n=4)) != a, "a fixed u for every record would collapse ties"


def test_case_id_is_the_dataset_item_id_not_the_row_number():
    keys = ["a", "b"]
    recs = records_from_logits([_fake_logits(2, 0)] * 2, [0, 0], [keys, keys], "en",
                               iter([0.1, 0.2]), item_ids=["x1", "x2"])
    assert {r["case_id"] for r in recs} == {"x1", "x2"}


def test_six_decimals_is_a_stated_limit_not_an_implicit_one():
    """The archive rounds to 4 decimals and says so; our driver keeps 6 and must say that."""
    r = records_from_logits([_fake_logits(3, 1)], [1], [["a", "b", "c"]], "en", iter([0.3]))[0]
    assert r["meta"]["probability_precision"] == 6


def test_the_parity_target_is_the_number_we_claim_comparability_with():
    assert PARITY == {"lang": "en", "per_lang": 100, "n_opts": 20, "seed": 13,
                      "regime": "unclamped", "accuracy": 0.82, "mean_confidence": 0.9989,
                      "macro_f1": 0.7876, "ece": 0.1789}


# ------------------------------------------------------------------- the `u` draw, deeper
def test_the_u_stream_is_consumed_in_order_and_each_record_carries_its_own_draw():
    n = 5
    stream = list(draw_u(seed=13, n=n))
    logits = [_fake_logits(3, i % 3) for i in range(n)]
    recs = records_from_logits(logits, [0, 1, 2, 0, 1], [["a", "b", "c"]] * n, "en",
                               iter(stream), item_ids=[str(i) for i in range(n)])
    assert [r["u"] for r in recs] == stream, "u must be the stream in order, one per case"
    assert len({r["u"] for r in recs}) == n, "one u reused across cases ties-breaks identically"
    assert [r["meta"]["u_index"] for r in recs] == list(range(n)), \
        "the position in the stream is what lets a reader re-derive the draw"


def test_the_draw_is_pinned_to_the_values_stdlib_publishes_for_that_seed():
    """`random.Random(int)` is the one stream that is stable across interpreters.

    Measured on this repository's venv and the vendored one (both 3.12) and identical there, so
    a reader can re-derive every recorded `u` from the recorded seed without our run.
    """
    assert [round(x, 17) for x in draw_u(seed=7, n=4)] == \
        [0.32383276483316237, 0.15084917392450192, 0.6509344730398537, 0.07243628666754276]


def test_a_short_u_stream_is_named_and_never_zero_filled():
    """A missing draw landing on 0.0 is the defect spec 5.2 forbids: ties resolved by default."""
    with pytest.raises(UStreamExhausted):
        records_from_logits([_fake_logits(2, 0)] * 2, [0, 0], [["a", "b"], ["a", "b"]], "en",
                            iter([0.4]))
    assert not issubclass(UStreamExhausted, ValueError), \
        "a refusal must not be catchable as bad operator input"


# ---------------------------------------------------------------------------- the conversion
def test_softmax_t_matches_a_hand_computed_distribution():
    """`math` only: the conversion cannot depend on the thing it is compared against."""
    p = softmax_t([0.0, math.log(3.0)], temperature=1.0)
    assert abs(p[0] - 0.25) < 1e-12 and abs(p[1] - 0.75) < 1e-12
    sharpened = softmax_t([0.0, math.log(3.0)], temperature=0.5)
    assert sharpened[1] > p[1], "a temperature below 1 must sharpen, as upstream's does"
    flat = softmax_t([1.0, 1.0, 1.0], temperature=2.0)
    assert all(abs(x - 1 / 3) < 1e-12 for x in flat)
    assert abs(sum(p) - 1.0) < 1e-12


def test_the_rounded_distribution_closes_to_one_instead_of_hoping_it_does():
    """Naive per-entry rounding at k=20 drifts past the bound the plan states for the artefact."""
    from tools.build_records import rounded_probs

    raw = [1.0 / 20 + (0.0000004 if i % 2 else -0.0000004) for i in range(20)]
    probs = rounded_probs(raw)
    assert abs(sum(probs) - 1.0) <= 1e-12, sum(probs)
    assert all(abs(a - b) <= 1e-6 for a, b in zip(probs, raw))
    assert probs == [round(x, 6) for x in probs]
    tiny = [0.00000001] * 10 + [1.0 - 10 * 0.00000001]
    assert abs(sum(rounded_probs(tiny)) - 1.0) <= 1e-12


def test_the_temperature_is_applied_before_any_probability_is_recorded():
    logits = [_fake_logits(4, 1)]
    keys = [["a", "b", "c", "d"]]
    plain = records_from_logits(logits, [1], keys, "en", iter([0.5]), item_ids=["1"])[0]
    cooled = records_from_logits(logits, [1], keys, "en", iter([0.5]), item_ids=["1"],
                                 temperature=0.5)[0]
    heated = records_from_logits(logits, [1], keys, "en", iter([0.5]), item_ids=["1"],
                                 temperatures=[3.0])[0]
    assert plain["probs"] != cooled["probs"] != heated["probs"]
    assert max(cooled["probs"]) > max(plain["probs"]) > max(heated["probs"])
    from tools.build_records import rounded_probs
    assert cooled["probs"] == rounded_probs(softmax_t(logits[0], 0.5))
    assert all(abs(a - b) <= 1e-6 for a, b in zip(cooled["probs"], softmax_t(logits[0], 0.5)))
    assert cooled["meta"]["temperature"] == 0.5 and heated["meta"]["temperature"] == 3.0


def test_predicted_is_the_argmax_of_the_recorded_probabilities():
    """The artefact must be self-consistent: a reader recomputes `predicted` from `probs`."""
    for i, logits in enumerate([_fake_logits(6, g) for g in range(6)]):
        rec = records_from_logits([logits], [0], [["k%d" % j for j in range(6)]], "en",
                                  iter([0.5]), item_ids=[str(i)])[0]
        best = max(range(len(rec["probs"])), key=lambda j: rec["probs"][j])
        assert rec["predicted"] == rec["options"][best], (i, rec["probs"])
        assert Record.from_dict(rec).predicted in Record.from_dict(rec).options


def test_the_record_is_one_the_repos_own_contract_reads():
    """`Record` is the only public interface L1 has (spec 4): the driver emits that schema."""
    keys = ["label_%d" % i for i in range(4)]
    rec = records_from_logits([_fake_logits(4, 2)], [2], [keys], "en", iter([0.3712]),
                                 item_ids=["massive/en/17"], backend="laya", suite_seed=13, u_seed=7,
                                 dataset="mteb/amazon_massive_intent", revision=REVISION,
                                 license_id="Apache-2.0", checkpoint="convaiinnovations/laya",
                                 texts=["read the meter at six"])[0]
    r = Record.from_dict(rec)
    assert r.qtype == "choice" and r.backend == "laya" and r.repeat == 1
    assert r.gold == keys[2] and r.case_id == "massive/en/17"
    assert r.id == "massive/en/17/laya"
    assert r.u == pytest.approx(0.3712) and r.seed == 7, "u must travel with its own seed"
    assert r.slices["language"] == "en" and r.slices["option_count"] == 4
    assert r.slices["mode"] == "choice" and r.slices["regime"] == "unclamped"
    assert r.scores["answer_confidence"] == max(r.probs)
    assert rec["meta"]["dataset"] == "mteb/amazon_massive_intent"
    assert rec["meta"]["revision"] == REVISION
    assert rec["meta"]["license"] == "Apache-2.0", "attribution travels with the records"
    assert rec["meta"]["checkpoint"] == "convaiinnovations/laya"
    assert rec["meta"]["utterance"] == "read the meter at six"
    again = Record.from_dict(json.loads(json.dumps(rec)))
    assert again == r, "the line on disk must rebuild the same record"


def test_a_record_without_gold_is_still_emitted_as_the_contract_allows():
    """gold=None is legal (gateable, never calibratable); it must not crash the builder."""
    rec = records_from_logits([_fake_logits(3, 1)], [None], [["a", "b", "c"]], "en",
                              iter([0.1]), item_ids=["z"])[0]
    assert rec["gold"] is None
    Record.from_dict(rec)


def test_the_case_id_namespaces_the_item_id_so_two_languages_do_not_collapse():
    """The 51 shards share one 2,974-id set (R-36): a bare id is the same case in all 51.

    `records_from_logits` hands back exactly the identity it was given -- which is what the plan's
    own test asserts -- so the namespacing is `case_id_for`'s, and the build layer is what calls it.
    """
    from tools.build_records import case_id_for

    assert case_id_for("en", "7") == "massive/en/7" != case_id_for("de", "7")
    assert records_from_logits([_fake_logits(2, 0)], [0], [["a", "b"]], "en", iter([0.5]),
                               item_ids=[case_id_for("en", "7")])[0]["case_id"] == "massive/en/7"
    assert records_from_logits([_fake_logits(2, 0)], [0], [["a", "b"]], "en",
                               iter([0.5]))[0]["case_id"] != "massive/en/7", \
        "with no identity supplied the builder says so in meta rather than pretending"


# --------------------------------------------------------------------- the parity comparison
def _report(**over):
    base = {k: PARITY[k] for k in PROBE_KEYS}
    base.update({"n": PARITY["per_lang"], "lang": PARITY["lang"], "n_opts": PARITY["n_opts"],
                 "seed": PARITY["seed"], "regime": PARITY["regime"]})
    base.update(over)
    return base


def test_the_parity_gate_passes_the_published_row_and_returns_the_compared_figures():
    assert check_parity(_report(), PARITY) == {k: PARITY[k] for k in PROBE_KEYS}


def test_the_parity_gate_refuses_a_figure_that_misses_the_published_row():
    """Planted: ece one ten-thousandth off, which is outside a 4-decimal comparison."""
    with pytest.raises(ParityError) as excinfo:
        check_parity(_report(ece=0.1799), PARITY)
    message = str(excinfo.value)
    assert "ece" in message and "0.1789" in message and "0.1799" in message, message
    assert not issubclass(ParityError, (ValueError, BuildError)), \
        "a parity refusal must not be absorbable by a wider catch, and must not share a base " \
        "with the drift/incomplete refusals that map to a different code"


@pytest.mark.parametrize("key", PROBE_KEYS)
def test_every_published_figure_is_compared_not_just_accuracy(key):
    with pytest.raises(ParityError):
        check_parity(_report(**{key: round(PARITY[key] + 0.01, 4)}), PARITY)


def test_the_parity_gate_checks_the_row_identity_not_only_its_figures():
    """A 2,974-case run is not the published n=100 row even if four figures happened to agree."""
    for over in ({"n": 2974}, {"lang": "de"}, {"n_opts": 5}, {"seed": 14}, {"regime": "clamped"}):
        with pytest.raises(ParityError):
            check_parity(_report(**over), PARITY)


def test_a_missing_figure_in_the_recomputed_report_is_a_refusal_not_a_vacuous_pass():
    incomplete = _report()
    del incomplete["macro_f1"]
    with pytest.raises(ParityError, match="macro_f1"):
        check_parity(incomplete, PARITY)
    with pytest.raises(ParityError, match="not a mapping"):
        check_parity(None, PARITY)


def test_report_from_records_hands_upstream_the_arrays_of_the_written_records():
    """The gate reads the artefact, so what reaches `summarise` must be the written numbers."""
    seen = {}

    def summarise(confs, corrects, golds, preds):
        seen.update(n=len(confs), confs=list(confs), corrects=list(corrects),
                    golds=list(golds), preds=list(preds))
        return {"n": len(confs)}

    logits = [_fake_logits(3, 0), _fake_logits(3, 2)]
    keys = [["a", "b", "c"], ["a", "b", "c"]]
    recs = records_from_logits(logits, [0, 2], keys, "en", iter([0.2, 0.9]), item_ids=["1", "2"])
    report_from_records(recs, summarise)
    assert seen["n"] == 2
    assert seen["confs"] == [max(r["probs"]) for r in recs]
    assert seen["corrects"] == [1.0, 1.0]
    assert seen["golds"] == [0, 2]
    assert seen["preds"] == [recs[0]["options"].index(recs[0]["predicted"]),
                             recs[1]["options"].index(recs[1]["predicted"])]


def test_a_gold_less_record_is_left_out_of_the_comparisons_arrays_not_counted_wrong():
    """`correct` for a record with no gold is not 0: it is absent, and n says how many are."""
    held = {}

    def summarise(confs, corrects, golds, preds):
        held.update(confs=list(confs), corrects=list(corrects), golds=list(golds))
        return {"n": len(confs)}

    recs = records_from_logits([_fake_logits(3, 0), _fake_logits(3, 1)], [0, None],
                               [["a", "b", "c"]] * 2, "en", iter([0.2, 0.3]),
                               item_ids=["1", "2"])
    report_from_records(recs, summarise)
    assert held["confs"] == [max(r["probs"]) for r in recs], "every written case is still scored"
    assert held["golds"] == [0, None] and held["corrects"] == [1.0, None]


# ------------------------------------------------------------------- the chunking (R-117), pure
def test_chunk_sizes_cover_the_suite_in_order_and_exactly_once():
    """The layout is arithmetic, so it is checked as arithmetic: no model, no cache, no tolerance.

    `--per-lang` sizes the artefact and `--chunk-size` sizes the collated batch, and the two are
    orthogonal -- so the shape of a chunked run has exactly one owner, used by the stage that scores
    and by the build layer that audits what the stage declared.
    """
    assert chunk_sizes(10, 3) == [3, 3, 3, 1]
    assert chunk_sizes(9, 3) == [3, 3, 3]
    assert chunk_sizes(2, 5) == [2], "a suite shorter than the batch is one shorter batch"
    assert chunk_sizes(0, 3) == []
    assert chunk_sizes(2974, DEFAULT_CHUNK_SIZE) == \
        [DEFAULT_CHUNK_SIZE] * (2974 // DEFAULT_CHUNK_SIZE) + [2974 % DEFAULT_CHUNK_SIZE]
    for n, size in ((0, 1), (1, 1), (7, 7), (8, 7), (2974, 1)):
        sizes = chunk_sizes(n, size)
        assert sum(sizes) == n, (n, size, sizes)
        assert all(s == size for s in sizes[:-1]) and (not sizes or sizes[-1] <= size), (n, size)
    with pytest.raises(DriftError):
        chunk_sizes(10, 0)


def test_a_batch_that_answers_the_wrong_count_is_refused_not_off_by_one_against_gold():
    """`score_cases_in_chunks` concatenates, so a short batch would shift every later case's gold.

    The logits array is matched to `gold` by position, and nothing downstream can tell a suite that
    was scored in six batches from one that was scored in five and re-labelled. This is the only
    place that could find out, so it is a refusal and not an assertion about shape.
    """
    cases = list(range(7))
    answered = []

    def score(batch):
        answered.append(len(batch))
        if len(batch) == 3:
            return [float(c) for c in batch[:2]]          # planted: one case missing
        return [float(c) for c in batch]

    with pytest.raises(DriftError, match="answered with 2"):
        score_cases_in_chunks(score, cases, 3)
    batches = []

    def honest(batch):
        batches.append(list(batch))
        return list(batch)

    logits, sizes = score_cases_in_chunks(honest, cases, 3)
    assert sizes == [3, 3, 1], sizes
    assert logits == cases, \
        "each batch's answer must arrive in the suite's own order, or `gold` is misaligned"
    assert batches == [[0, 1, 2], [3, 4, 5], [6]], batches
    assert score_cases_in_chunks(honest, [], 3) == ([], []), "an empty suite is not a crash"
    with pytest.raises(DriftError, match="chunk size of 0"):
        score_cases_in_chunks(score, cases, 0)


def test_a_stage_that_declared_a_layout_it_could_not_have_run_is_refused(tmp_path):
    """The chunk layout in the artefact is the evidence for the equivalence claim, so it must add up.

    A payload that says 2 cases in batches of [1, 1, 1] describes a run that cannot have produced it;
    the driver refuses rather than publishing a `chunks` field a later reader would quote.
    """
    payload = _payload("en", n=2, chunk_size=DEFAULT_CHUNK_SIZE)
    payload["chunks"] = [1, 1, 1]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-400:])
    assert "could not have produced" in p.stderr, p.stderr[-400:]
    assert "[2]" in p.stderr, p.stderr[-400:]
    payload = _payload("en", n=2, chunk_size=DEFAULT_CHUNK_SIZE)
    payload["chunks"] = [2, 2]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-400:])
    assert "could not have produced" in p.stderr, p.stderr[-400:]
    assert not (tmp_path / "records.jsonl").exists()


def test_a_stage_that_ignored_the_asked_chunk_size_is_refused(tmp_path):
    """`--chunk-size` is a memory claim about the artefact, so the stage has to have honoured it.

    The real worker echoes what it was passed, which makes this guard look vacuous until it is
    planted: a stale payload, a wrapper that drops the flag, or a worker built from another revision
    would all write an artefact whose recorded layout is not the layout the operator asked for -- and
    the equivalence test would then be a statement about a shape this file never used.
    """
    cache, pin = _planted_root(tmp_path)
    payloads = {"en": {"probe": _probe(), "full": _payload("en", n=2, chunk_size=150)}}
    python = _fake_worker(tmp_path, payloads, name="stubborn_worker.py")
    # The planted worker re-states the layout it was asked for, so the refusal has to be planted in
    # the payload it serves: 150 reported against a build asked for 100.
    p = _driver(tmp_path, cache=cache, pin=pin, python=python,
                extra=["--langs", "en", "--per-lang", "2", "--chunk-size", "100"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr[-500:])
    assert "being asked for 100" in p.stderr, p.stderr[-500:]
    assert not (tmp_path / "records.jsonl").exists()


def test_a_chunk_size_below_one_is_a_usage_refusal_and_not_an_empty_batch(tmp_path):
    """Zero would score nothing at all, and every case would arrive with no probability."""
    p = _ok_driver(tmp_path, extra=["--chunk-size", "0"])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr[-300:])
    assert "--chunk-size" in p.stderr, p.stderr[-300:]
    assert not (tmp_path / "records.jsonl").exists()
    p = _ok_driver(tmp_path, extra=["--chunk-size", "-3"])
    assert p.returncode == 2, (p.returncode, p.stderr[-300:])


def test_the_default_chunk_is_the_one_r_117_ruled_for():
    """150 cases is ~3.6 GiB per batch on a 16 GB machine; the number is a ruling, so it is pinned.

    Measured at 16.5 MiB per case plus ~1.16 GiB fixed (pilot, mps): 150 x 16.5 MiB + 1.16 GiB is
    ~3.5 GiB, which leaves the other lanes in this tree their memory. A silent change to this constant
    changes the peak of the real build, so it is asserted here rather than left in a comment.
    """
    assert DEFAULT_CHUNK_SIZE == 150
    assert chunk_sizes(PARITY["per_lang"], DEFAULT_CHUNK_SIZE) == [100], \
        "the published-row probe already fits one batch, so the gate is not re-chunked by this"


# ------------------------------------------------------------- both regimes, one pass (R-118)
def test_calibration_status_is_the_librarys_verdict_and_not_a_label_each_side_may_choose():
    """Three states, named: what upstream applies, what upstream rejects, and what needed no clamp.

    The third exists because a checkpoint whose raw temperatures were already inside [0.5, 5] emits
    no warning, and a row that borrowed the rejection of a warning it never triggered would be a
    false statement about the numbers -- in the artefact, where no reader can check it.
    """
    assert calibration_status("clamped") == CALIBRATION_CLAMPED
    assert calibration_status("clamped", warning_emitted=False) == CALIBRATION_CLAMPED
    assert calibration_status("unclamped") == CALIBRATION_REJECTED
    assert calibration_status("unclamped", warning_emitted=False) == CALIBRATION_IN_RANGE
    assert "uncalibrated" in CALIBRATION_REJECTED, "the library's own word, not a softer one"
    with pytest.raises(DriftError, match="not a regime"):
        calibration_status("half-clamped")


def test_a_record_states_its_regime_and_what_its_confidence_means():
    """`meta.calibration_status` is a sentence, because the reader is a human with `jq`.

    A code would need the document nobody opens; the row that carries a near-saturated confidence
    column has to say, in the row, that upstream declines to treat it as calibrated.
    """
    logits, keys = [_fake_logits(3, 1)], [["a", "b", "c"]]
    for regime, want in ((PARITY_REGIME, CALIBRATION_REJECTED),
                         (CERTIFIED_REGIME, CALIBRATION_CLAMPED)):
        rec = records_from_logits(logits, [1], keys, "en", iter([0.4]), item_ids=["1"],
                                  temperatures=[REGIME_TEMPERATURES[regime]],
                                  regime=regime)[0]
        assert rec["slices"]["regime"] == regime
        assert rec["meta"]["regime"] == regime
        assert rec["meta"]["calibration_status"] == want, rec["meta"]
        assert rec["meta"]["temperature"] == REGIME_TEMPERATURES[regime]
    with pytest.raises(DriftError, match="not a regime"):
        records_from_logits(logits, [1], keys, "en", iter([0.4]), regime="neither")


def test_one_pass_writes_the_certified_artefact_and_its_parity_control(tmp_path):
    """Two files, one forward pass, same cases, same recorded `u`, one different temperature.

    The certified file is the clamped column and the parity file is the unclamped one; every row of
    each says which it is, in three places. The `u` must match case for case across the two files,
    because a certificate that could not reproduce its own tie-breaks is not a certificate -- so the
    only intended difference between the two artefacts is the probability vector and the regime that
    produced it.
    """
    p = _ok_driver(tmp_path)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr[-400:])
    certified, parity, parity_path = _artefacts(tmp_path)
    assert "_unclamped_parity" in parity_path.name, parity_path.name
    assert len(certified) == len(parity) == 2
    for rec in certified + parity:
        Record.from_dict(rec)
    assert [r["case_id"] for r in certified] == [r["case_id"] for r in parity]
    assert [r["u"] for r in certified] == [r["u"] for r in parity], \
        "the tie-break is one draw per case, shared by both regimes of the same pass"
    assert {r["slices"]["regime"] for r in certified} == {CERTIFIED_REGIME}
    assert {r["slices"]["regime"] for r in parity} == {PARITY_REGIME}
    assert {r["meta"]["calibration_status"] for r in certified} == {CALIBRATION_CLAMPED}
    assert {r["meta"]["calibration_status"] for r in parity} == {CALIBRATION_REJECTED}
    for a, b in zip(certified, parity):
        assert a["probs"] != b["probs"], (a["probs"], b["probs"])
        assert a["meta"]["temperature"] == CLAMPED_TEMPERATURE
        assert b["meta"]["temperature"] == RAW_TEMPERATURE
        assert a["options"] == b["options"] and a["gold"] == b["gold"]
    assert "certified regime: clamped" in p.stdout, p.stdout
    assert "parity ok: probe lang=en n=100" in p.stdout, p.stdout


def test_the_two_destinations_may_not_be_the_same_file(tmp_path):
    """One pass, two numbers: a file that holds whichever regime was written last holds neither."""
    p = _ok_driver(tmp_path, extra=["--out-parity", str(tmp_path / "records.jsonl")])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr[-300:])
    assert "same path" in p.stderr, p.stderr[-300:]


def test_the_parity_control_path_is_derived_from_the_certified_one(tmp_path):
    """A control nobody can predict the location of is a control nobody finds.

    `--out-parity` is an escape hatch, not a requirement: the default name has to state the regime,
    because the regime is the thing a reader must not have to infer.
    """
    from tools.build_records import artefact_paths

    out, parity = artefact_paths(Path("/tmp/x/records_massive.jsonl"))
    assert out.name == "records_massive.jsonl"
    assert parity.name == "records_massive_unclamped_parity.jsonl"
    assert artefact_paths(out, "/tmp/x/other.jsonl")[1].name == "other.jsonl"
    p = _ok_driver(tmp_path, out="custom.jsonl")
    assert p.returncode == 0, p.stderr[-400:]
    assert (tmp_path / "custom_unclamped_parity.jsonl").is_file()


def test_a_stage_that_labels_its_own_confidence_differently_is_refused(tmp_path):
    """Two interpreters, one fact, and a disagreement is a refusal.

    The stage runs where the checkpoint does, so it could claim its unclamped column was calibrated
    and nothing else in the pipeline would know. `check_payload` re-derives the sentence from the
    regime name and the warnings the library actually emitted, and refuses when they differ -- which
    is the whole reason the warnings travel as data.
    """
    for regime, plant in ((PARITY_REGIME, CALIBRATION_CLAMPED),
                          (CERTIFIED_REGIME, CALIBRATION_REJECTED)):
        payload = _payload("en", n=2)
        payload["regimes"][regime]["calibration_status"] = plant
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (regime, p.returncode, p.stderr[-400:])
        assert "calibration status of a published number is not a label" in p.stderr, p.stderr[-400:]
        assert regime in p.stderr, (regime, p.stderr[-400:])


def test_a_payload_missing_a_regime_block_is_refused(tmp_path):
    """A run that scored one regime cannot fill an artefact for the other -- and it cannot be silent."""
    for regime in REGIMES:
        payload = _payload("en", n=2)
        del payload["regimes"][regime]
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (regime, p.returncode, p.stderr[-400:])
        assert "carries no block for regime" in p.stderr, (regime, p.stderr[-400:])
    payload = _payload("en", n=2)
    payload["regimes"]["half_clamped"] = payload["regimes"]["clamped"]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-400:])
    assert "half_clamped" in p.stderr, p.stderr[-400:]


def test_a_checkpoint_that_warned_about_nothing_is_stated_as_in_range(tmp_path):
    """The third calibration state, reached by the absence of the warning rather than by a flag.

    Planting an empty `warnings` list is what a quiet checkpoint really returns. If the driver
    hardcoded `REJECTED` for the unclamped column, a calibrated checkpoint's raw column would be
    published as rejected-by-upstream: wrong in the conservative direction is still wrong, and it is
    the kind of statement a certificate gets quoted for.
    """
    payload = _payload("en", n=2, warnings=[])
    probe = _probe(warnings=[])
    p = _ok_driver(tmp_path, payloads={"en": _staged(probe, payload)})
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr[-400:])
    _certified, parity, _ = _artefacts(tmp_path)
    assert {r["meta"]["calibration_status"] for r in parity} == {CALIBRATION_IN_RANGE}, parity[0]


def test_the_run_summary_names_both_artefacts_and_the_layout_they_were_scored_in(tmp_path):
    """The regime is a property of the artefact, so the summary that describes the artefact carries it.

    `report_from_records` already stamps `regime` and `calibration_status` onto each row's report, so
    the flat `report` a reader of an old summary expects is the CERTIFIED one, and the other column
    is under `regimes` -- never merged, never averaged, never the one written last.
    """
    p = _ok_driver(tmp_path, extra=["--summary", str(tmp_path / "summary.json")])
    assert p.returncode == 0, (p.returncode, p.stderr[-400:])
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["certified_regime"] == CERTIFIED_REGIME
    assert summary["parity_regime"] == PARITY_REGIME
    assert summary["chunk_size"] == DEFAULT_CHUNK_SIZE
    assert set(summary["artefacts"]) == set(REGIMES)
    assert summary["artefacts"][CERTIFIED_REGIME]["role"] == "certified"
    assert summary["artefacts"][PARITY_REGIME]["role"] == "parity control"
    assert summary["artefacts"][CERTIFIED_REGIME]["calibration_status"] == CALIBRATION_CLAMPED
    assert summary["artefacts"][PARITY_REGIME]["calibration_status"] == CALIBRATION_REJECTED
    assert summary["artefacts"][CERTIFIED_REGIME]["path"].endswith("records.jsonl")
    assert summary["artefacts"][PARITY_REGIME]["path"].endswith("unclamped_parity.jsonl")
    for lang_block in summary["languages"].values():
        assert set(lang_block["regimes"]) == set(REGIMES)
        assert lang_block["regime"] == CERTIFIED_REGIME
        assert lang_block["chunks"] == chunk_sizes(2, DEFAULT_CHUNK_SIZE)
        assert lang_block["report"] == lang_block["regimes"][CERTIFIED_REGIME]["report"]
        assert lang_block["regimes"][CERTIFIED_REGIME]["report"]["regime"] == CERTIFIED_REGIME
        assert lang_block["regimes"][PARITY_REGIME]["report"]["calibration_status"] == \
            CALIBRATION_REJECTED
        assert lang_block["warnings"][0]["category"] == "RuntimeWarning", lang_block["warnings"]
    assert summary["probe"]["regime"] == PARITY_REGIME
    assert summary["probe"]["stage_reports"][CERTIFIED_REGIME]["regime"] == CERTIFIED_REGIME


def test_the_control_row_is_gated_and_the_certified_row_is_not(tmp_path):
    """The gate compares the unclamped column against upstream's table; nothing gates the clamped one.

    Planting a clamped `upstream_report` that disagrees with the published row must NOT stop the
    build: the certified side inherits the proof rather than carrying its own, and a gate on it would
    be a gate on a quantity upstream never published. The same plant on the unclamped side must stop
    it. Two colours from one fixture, and between them they pin down which side is being claimed.
    """
    wrong = dict({f: PARITY[f] for f in PROBE_KEYS}, n=PARITY["per_lang"])
    wrong["accuracy"] = 0.5
    good = {f: PARITY[f] for f in PROBE_KEYS}
    probe = _probe()
    probe["regimes"][CERTIFIED_REGIME]["upstream_report"] = dict(wrong)
    p = _ok_driver(tmp_path, payloads={"en": _staged(probe, _payload("en", n=2))}, per_lang=2)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr[-400:])
    certified, _parity, _ = _artefacts(tmp_path)
    assert len(certified) == 2

    probe = _probe()
    probe["regimes"][PARITY_REGIME]["upstream_report"] = dict(wrong)
    p = _ok_driver(tmp_path, payloads={"en": _staged(probe, _payload("en", n=2))}, per_lang=2)
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr[-400:])
    assert "upstream" in p.stderr.lower() and "accuracy" in p.stderr, p.stderr[-400:]


# --------------------------------------------------- the cache gate itself, and what it protects
CACHE_ENV = os.environ.get("AUTORATE_MASSIVE_CACHE")
CACHE_PIN = REPO / "data" / "massive_provenance.json"
# 48 cases, cut two ways: four collated batches of 12, and the whole prefix as one batch -- the shape
# a 2,974-case run degenerates to when `--chunk-size` is larger than the suite. Measured on the pilot:
# one load and two forward passes, so this is the expensive test in the file and it is bounded here.
EQUIV_CASES = 48
EQUIV_LAYOUTS = (12, EQUIV_CASES)


def _cache_gate_missing(cache_env=None):
    """Why this machine cannot run the real-checkpoint test, or None when it can.

    Two preconditions and no more: the pinned bytes, and an interpreter that can load the checkpoint.
    The gate has to be exactly those, because a third condition nobody thought of is how a test that
    is supposed to prove something ends up skipped forever on the one machine where it would have
    fired. `cache_env` is a parameter so the guard test below can drive it with a planted value
    instead of exec'ing source.
    """
    if cache_env is None:
        cache_env = CACHE_ENV
    if not cache_env:
        return ("AUTORATE_MASSIVE_CACHE is unset, so the pinned MASSIVE shards are not on this "
                "machine: `tools/fetch_massive.py fetch --dest <dir>` then point the variable at it")
    cache = Path(cache_env)
    if not cache.is_dir():
        return "AUTORATE_MASSIVE_CACHE=%r is not a directory" % (cache_env,)
    if not (cache / "test" / "en.json.gz").is_file():
        return "%s has no `test/en.json.gz`, so there is no pinned prefix to score" % cache
    if not CACHE_PIN.is_file():
        return "%s is absent, so the shards could not be checked against the pin" % CACHE_PIN
    from tools.build_records import resolve_upstream, upstream_python

    upstream = resolve_upstream(None)
    if upstream is None:
        return ("no vendored `laya*` tree beside this repository, so no interpreter can load the "
                "checkpoint (set AUTORATE_UPSTREAM_ROOT)")
    python = Path(upstream_python(Path(upstream)))
    if not python.is_file():
        return "the vendored tree %s has no .venv interpreter at %s" % (upstream, python)
    return None


CACHE_GATE_MISSING = _cache_gate_missing()
cache_gated = pytest.mark.skipif(
    bool(CACHE_GATE_MISSING),
    reason=CACHE_GATE_MISSING or "the pinned cache and the checkpoint interpreter are both present")


def test_the_cache_gate_is_the_cache_and_the_checkpoint_and_nothing_else(tmp_path):
    """The gate can be shown to close, so a skipped equivalence test is a visible skip and not a pass.

    Asserting the reason is what makes this falsifiable: with the variable unset the predicate names
    `AUTORATE_MASSIVE_CACHE`, and with it naming an empty directory the predicate says the shards are
    missing rather than staying quiet. A guard whose reason could not be printed would let the
    expensive test below disappear without a trace.
    """
    condition, = cache_gated.mark.args
    assert condition == (CACHE_GATE_MISSING is not None)
    assert cache_gated.mark.kwargs["reason"], "a skip with no reason is a skip nobody can audit"
    if condition:
        assert "AUTORATE_MASSIVE_CACHE" in cache_gated.mark.kwargs["reason"] or \
            "checkpoint" in cache_gated.mark.kwargs["reason"], cache_gated.mark.kwargs["reason"]
    assert "AUTORATE_MASSIVE_CACHE" in _cache_gate_missing("")
    empty = tmp_path / "empty-cache"
    empty.mkdir()
    reason = _cache_gate_missing(str(empty))
    assert "test/en.json.gz" in reason, reason
    assert str(empty) in reason, reason
    assert "is not a directory" in _cache_gate_missing(str(tmp_path / "nope"))


@cache_gated
def test_chunking_the_suite_changes_not_a_single_probability_on_the_real_checkpoint(tmp_path):
    """R-117 as a claim about the model, not about the arithmetic.

    `chunk_sizes` and `score_cases_in_chunks` are proven elsewhere without a GPU; what cannot be
    settled there is whether this checkpoint's marker logits depend on how many cases were collated
    into the batch. They must not: the build scores 2,974 cases in ~20 batches because one batch would
    need ~48.9 GB, and if batching moved a probability, every certificate downstream would be a
    statement about batch shape. So the same 48 cases of the pinned `en` shard are scored twice, in
    two layouts, by the driver's own `--worker --stage equivalence` path in the vendored interpreter,
    and the comparison is bit-for-bit -- logits, both regimes' unrounded softmax, and the 6-decimal
    records the artefact actually carries, line for line.

    It is cache-gated because it needs the pinned bytes and the model, and it is a skip rather than a
    pass when either is absent: a green that measured nothing is the failure mode here.
    """
    from tools.build_records import case_id_for, resolve_upstream, upstream_python

    cache = Path(CACHE_ENV)
    upstream = Path(resolve_upstream(None))
    python = upstream_python(upstream)
    payload = tmp_path / "equivalence.json"
    cmd = [python, str(DRIVER), "--worker", "--stage", "equivalence", "--lang", "en",
           "--payload", str(payload), "--cache", str(cache), "--pin", str(CACHE_PIN),
           "--upstream", str(upstream), "--model", "convaiinnovations/laya", "--device", "",
           "--per-lang", str(EQUIV_CASES), "--n-opts", str(PARITY["n_opts"]),
           "--seed", str(PARITY["seed"]), "--chunk-size", str(DEFAULT_CHUNK_SIZE),
           "--layouts", ",".join(str(x) for x in EQUIV_LAYOUTS)]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1"}
    done = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), env=env)
    assert done.returncode == 0, (done.returncode, done.stdout[-600:], done.stderr[-1500:])
    data = json.loads(payload.read_text())

    layouts = data["layouts"]
    assert layouts == [str(x) for x in EQUIV_LAYOUTS], layouts
    assert data["n_cases"] == EQUIV_CASES, data["n_cases"]
    # The two layouts really were two different collations of the same cases.
    assert data["samples"][layouts[0]]["chunks"] == [12, 12, 12, 12], data["samples"][layouts[0]]
    assert data["samples"][layouts[1]]["chunks"] == [EQUIV_CASES], data["samples"][layouts[1]]
    assert data["bit_identical"] is True, data["max_abs_difference"]
    assert data["max_abs_difference"] == 0.0, data["max_abs_difference"]
    # The child proves where it ran: an unresolved venv symlink is the trap that killed one attempt,
    # and `sys.prefix` read inside the child is the only evidence that it was the venv.
    assert data["timing"]["prefix"] != sys.prefix, data["timing"]["prefix"]
    assert data["timing"]["device"] in ("mps", "cpu", "cuda"), data["timing"]

    # Re-derived here rather than taken on trust: the raw logits, both regimes' distributions, and
    # the serialised Records are identical across the two layouts.
    written = {}
    for regime in REGIMES:
        lines = {}
        for label in layouts:
            sample = data["samples"][label]
            assert len(sample["regimes"][regime]["probs"]) == EQUIV_CASES
            assert [len(p) for p in sample["regimes"][regime]["probs"]] == \
                [len(k) for k in data["option_keys"]]
            assert sample["logits"] == data["samples"][layouts[0]]["logits"], \
                "the logits of layout %s differ" % label
            recs = records_from_logits(
                sample["logits"], data["gold"], data["option_keys"], "en",
                draw_u(seed=PARITY["seed"], n=EQUIV_CASES),
                item_ids=[case_id_for("en", i) for i in data["item_ids"]],
                temperatures=sample["regimes"][regime]["temperatures"], regime=regime)
            lines[label] = [json.dumps(r, sort_keys=True) for r in recs]
        distinct = {tuple(v) for v in lines.values()}
        assert len(distinct) == 1, "layout moved a probability: %s regime=%s" % (list(lines), regime)
        written[regime] = lines[layouts[0]]

    # And the two regimes are still two different columns of the one pass, so the equality above is
    # not one column being compared with itself.
    assert written[PARITY_REGIME] != written[CERTIFIED_REGIME], \
        "one forward pass produced one column, not the two R-118 says it does"
    assert {json.loads(l)["meta"]["temperature"] for l in written[CERTIFIED_REGIME]} == \
        {json.loads(written[CERTIFIED_REGIME][0])["meta"]["temperature"]}
    assert {json.loads(l)["meta"]["calibration_status"] for l in written[CERTIFIED_REGIME]} == \
        {CALIBRATION_CLAMPED}


def test_compare_layouts_refuses_a_probability_that_moved_by_anything(tmp_path):
    """The equivalence claim is falsifiable without a GPU: nudge one number and it must say so.

    Without this, the cache-gated test above is the only thing standing between a chunking change
    that moves a probability and a green suite -- and on the machine where the guard would have to
    fire, the guard is skipped. So the comparison itself is driven to its red here, four ways: a
    nudged logit, a nudged probability, a short suite, and one layout that scored one regime.
    """
    from tools.build_records import compare_layouts

    def samples(first, second):
        return {"48": {"chunk_size": 48, "chunks": [48], "logits": [first],
                       "regimes": {r: {"probs": [first]} for r in REGIMES}},
                "12": {"chunk_size": 12, "chunks": [12], "logits": [second],
                       "regimes": {r: {"probs": [second]} for r in REGIMES}}}

    base = [0.1, 0.2, 0.7]
    assert compare_layouts(samples(base, list(base))) == 0.0
    with pytest.raises(DriftError, match="chunking is not free"):
        compare_layouts(samples(base, [0.1, 0.2, 0.7000001]))
    nudged = samples(base, list(base))
    nudged["12"]["regimes"][CERTIFIED_REGIME]["probs"] = [[0.1, 0.2, 0.6999999999]]
    with pytest.raises(DriftError, match="different distribution"):
        compare_layouts(nudged)
    short = samples(base, list(base))
    short["12"]["logits"] = []
    with pytest.raises(DriftError, match="scored 0 cases"):
        compare_layouts(short)
    one_regime = samples(base, list(base))
    del one_regime["12"]["regimes"][CERTIFIED_REGIME]
    with pytest.raises(DriftError, match="the one forward pass"):
        compare_layouts(one_regime)
    with pytest.raises(DriftError, match="at least two layouts"):
        compare_layouts({"48": one_regime["48"]})


# ------------------------------------------------------------- the offline boundary itself
def test_the_build_layer_pulls_in_no_torch_and_no_laya():
    """Plan C Step 7: a build-only dependency in the import path is the unforgivable defect.

    The four phrases are assembled rather than written out, because Step 7's own gate greps the
    `src` and `tests` roots for the torch import phrase and has to print *nothing*. A guard that
    trips the gate it implements leaves a reader to re-litigate one grep line every time, which is
    how gates get ignored; the assertion below is unchanged in force, and the last loop proves it
    still fires when a module-scope import really is there.
    """
    assert "torch" not in sys.modules and "laya" not in sys.modules
    forbidden = ["%s %s" % (verb, mod)
                 for verb in ("import", "from") for mod in ("torch", "laya")]
    head = DRIVER.read_text().split("def ", 1)[0]
    for phrase in forbidden:
        assert phrase not in head, "%s is at module scope in the driver" % phrase
    for bad_head in ("%s torch\n" % "import", "%s laya.common import QTYPES\n" % "from"):
        assert [p for p in forbidden if p in bad_head], bad_head


def test_no_tracked_line_of_the_driver_carries_a_machine_path():
    """The class of defect tests/test_cli.py scans the tracked set for, asserted locally too."""
    home = str(Path.home())
    offenders = [(i, line) for i, line in enumerate(DRIVER.read_text().splitlines(), 1)
                 if home in line or "/%s/" % "Users" in line]
    assert not offenders, offenders


def test_the_published_row_has_one_owner_in_the_module():
    """One name for the figure the gate quotes, so an erratum has a single place to land."""
    from tools import build_records as br

    assert br.PARITY_TARGET is PARITY


# ------------------------------------------- the planted build (no model, real entry point)
def _shard_entry(lang="en", rows=100):
    body = [{"id": str(i), "text": "%s utterance %d" % (lang, i), "label_text": "intent_%d" % (i % 7)}
            for i in range(rows)]
    gz = gzip.compress(("\n".join(json.dumps(r) for r in body)).encode())
    return {"path": "test/%s.json.gz" % lang, "sha256": hashlib.sha256(gz).hexdigest(),
            "bytes": len(gz), "rows": rows, "lang": "%s.json" % lang}, gz


def _planted_root(tmp_path, langs=("en",), rows=100):
    """A cache plus the pin that describes it, digests computed here -- never the pinned values."""
    cache = tmp_path / "cache"
    files = []
    for lang in langs:
        entry, gz = _shard_entry(lang, rows)
        target = cache / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gz)
        files.append(entry)
    pin = {"schema": PIN_SCHEMA, "dataset": "mteb/amazon_massive_intent", "license": "Apache-2.0",
           "resolve_route": "https://huggingface.co/datasets/mteb/amazon_massive_intent/"
                            "resolve/<rev>/<path>",
           "revision": REVISION,
           "n_files": len(files), "rows_total": sum(f["rows"] for f in files),
           "bytes_total": sum(f["bytes"] for f in files),
           "distinct_row_counts": sorted({f["rows"] for f in files}), "files": files}
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(json.dumps(pin))
    return cache, pin_path


def _planted_upstream(tmp_path, report=None):
    """Stand-in for the vendored tree: upstream's `summarise` signature, with a planted verdict.

    `n` stays derived from the arrays it is handed, so a driver that fed the gate the wrong case
    count is refused by this fixture rather than by an assertion about plumbing.
    """
    planted = dict(report) if report is not None else {k: PARITY[k] for k in PROBE_KEYS}
    eval_dir = tmp_path / "upstream" / "research" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "laya_eval.py").write_text(textwrap.dedent('''
        """Planted stand-in for upstream's harness: no torch, upstream's metric signatures."""
        import json
        import math
        import os

        def _planted():
            with open(os.environ["PLANTC_PARITY_REPORT"]) as fh:
                return json.load(fh)

        def summarise(confidence, correct, gold, pred, bins=15):
            out = {"n": len(confidence)}
            out.update(_planted())
            return out

        def softmax_t(z, temperature=1.0):
            z = [float(x) / max(1e-3, float(temperature)) for x in z]
            m = max(z)
            e = [math.exp(x - m) for x in z]
            s = sum(e)
            return [x / s for x in e]

        def build_suite(rows, labels, per_lang, n_opts, seed=13):
            raise AssertionError("the planted tree never builds a suite: the model stage is "
                                 "the planted interpreter")

        def temperature_for(agent, qtype, k, unclamped=False):
            raise AssertionError("the planted tree has no checkpoint to read temperatures from")
    '''))
    report_path = eval_dir / "planted_report.json"
    report_path.write_text(json.dumps(planted))
    return tmp_path / "upstream", report_path


# What the checkpoint stack emits on every load of this model, and what R-118 turns into a
# publication policy: the unclamped column is the library's own rejected temperature.
CLAMP_WARNING = {"category": "RuntimeWarning",
                 "message": "laya: this checkpoint ships invalid temperatures or values outside "
                            "[0.5, 5]; using choice:11+%r -> 0.5. Treat confidence from the "
                            "affected entries as uncalibrated." % RAW_TEMPERATURE,
                 "where": "agent.py:928"}
REGIME_TEMPERATURES = {"unclamped": RAW_TEMPERATURE, "clamped": CLAMPED_TEMPERATURE}


def _regime_block(logits, regime, upstream_report, seen_warnings):
    """One regime's column: its own temperatures, its own probe, its own verdict on itself.

    Both blocks are built from the *same* logits, which is the point of R-118 -- one forward pass,
    two regimes -- so a fixture that gave them different logits would let the driver be written
    against a second pass and still pass here.
    """
    temperature = REGIME_TEMPERATURES[regime]
    return {"temperatures": [temperature] * len(logits),
            "probs_probe": [softmax_t(z, temperature) for z in logits[:min(3, len(logits))]],
            "upstream_report": dict(upstream_report),
            "calibration_status": calibration_status(regime, warning_emitted=bool(seen_warnings))}


def _payload(lang, n=2, k=20, ids=None, texts=None, stage="full",
             qtype="choice", upstream_report=None, warnings=None, chunk_size=None):
    """The shape `_score_batch` really returns, including the two fields that carry its identity.

    `qtype` is what the stage knows and the build layer would otherwise assume. `regimes` carries one
    block per temperature regime -- `upstream_report` is the row upstream's own arithmetic produced
    from these logits *at that regime*, so its planted figures are the published ones unless a test
    deliberately disagrees with them -- and `chunk_size`/`chunks` are the layout the suite was
    actually collated in (R-117). The legacy single-regime `regime`/`temperatures`/`probs_probe`
    fields are gone from the contract, so nothing here emits them.
    """
    keys = [["k%d" % j for j in range(k)] for _ in range(n)]
    logits = [[0.0 if j != (i % k) else 2.0 for j in range(k)] for i in range(n)]
    if upstream_report is None:
        upstream_report = dict({"n": n}, **{f: PARITY[f] for f in PROBE_KEYS})
    seen_warnings = [CLAMP_WARNING] if warnings is None else list(warnings)
    chunk_size = DEFAULT_CHUNK_SIZE if chunk_size is None else chunk_size
    return {"lang": lang, "stage": stage, "n_cases": n, "n_opts": k, "seed": 13,
            "qtype": qtype,
            "item_ids": ids if ids is not None else [str(i) for i in range(n)],
            "gold": [i % k for i in range(n)], "option_keys": keys, "logits": logits,
            "texts": texts if texts is not None else ["ask %d" % i for i in range(n)],
            "regimes": {r: _regime_block(logits, r, upstream_report, seen_warnings)
                        for r in REGIMES},
            "chunk_size": chunk_size, "chunks": chunk_sizes(n, chunk_size),
            "warnings": seen_warnings,
            "timing": {"load_s": 1.0, "score_s": 2.0, "device": "cpu",
                       "cases_per_s": float(n) / 2.0, "chunks": len(chunk_sizes(n, chunk_size)),
                       "chunk_size": chunk_size, "peak_rss_mib": 2.0,
                       "torch": "planted", "laya": "planted"}}


def _probe(lang="en", **over):
    """The published row's own conditions: n=100, and the stage the gate was run under."""
    over.setdefault("n", PARITY["per_lang"])
    return _payload(lang, stage="probe", **over)


def _staged(probe, full):
    """One language's two stages: the published-row probe, then the artefact run."""
    return {"probe": probe, "full": full}


FLAG_HELPER = '''
def flag(name):
    """Order-independent: the planted worker only needs to find its payload path."""
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None
'''


def _script(path: Path, text: str) -> Path:
    """Write a planted executable.

    `textwrap.dedent` leaves the leading newline in place, which puts the shebang on line 2 and
    makes the kernel refuse the file with `Exec format error` -- measured, and the reason every
    planted script here goes through this one writer.
    """
    path.write_text(textwrap.dedent(text).lstrip("\n"))
    path.chmod(0o755)
    return path


def _fake_worker(tmp_path, payloads, name="fake_python.py"):
    """A planted interpreter: it writes the payload the model stage would have written.

    The payloads travel in a JSON side file rather than as an inlined literal, because `json.dumps`
    writes `NaN` for a non-finite float and that is not a Python literal -- and a non-finite logit
    is one of the defects this suite needs to be able to plant.
    """
    (tmp_path / (name + ".payloads.json")).write_text(json.dumps(payloads))
    # `dedent` runs on the template alone: the flag helper is inserted afterwards, at column 0,
    # and dedenting after it would leave the shebang indented and the file unexecutable.
    body = textwrap.dedent('''
        #!/usr/bin/env python3
        """Planted stand-in for the upstream interpreter. Writes a payload, loads no model."""
        import json
        import sys

        __FLAGS__

        with open(PAYLOADS_FILE) as fh:
            payloads = json.load(fh)
        lang, stage = flag("--lang"), flag("--stage")
        try:
            out = payloads[lang][stage]
        except KeyError:
            sys.stderr.write("planted worker has nothing to serve for %s/%s\\n" % (lang, stage))
            raise SystemExit(7)
        # The real stage scores exactly `--per-lang` cases in batches of `--chunk-size`, so the
        # planted one does the same arithmetic: a probe run sized to the artefact instead of the
        # published row comes back with the wrong n, and a layout that does not match the case count
        # is refused by the driver rather than quietly published.
        out = dict(out)
        declared = out.get("n_cases")
        want = int(flag("--per-lang"))
        chunk_size = int(flag("--chunk-size"))
        got = min(want, len(out.get("logits") or []))
        out["n_cases"] = got
        for key in ("item_ids", "gold", "option_keys", "logits", "texts"):
            if isinstance(out.get(key), list):
                out[key] = out[key][:got]
        sizes, left = [], got
        while left > 0:
            sizes.append(min(chunk_size, left))
            left -= sizes[-1]
        # Three cases, deliberately different:
        # * the stage served the number of cases its fixture describes -> the fixture's own layout
        #   travels verbatim, so a planted layout that cannot add up reaches the driver;
        # * the stage served a different number and described a layout -> re-state it for the count
        #   actually served, which is what a real worker would have done;
        # * the stage described no layout at all -> it stays silent, or the driver's missing-key
        #   refusal could never be reached through this worker.
        had_layout = "chunk_size" in out and "chunks" in out
        if got != declared and had_layout:
            out["chunk_size"] = chunk_size
            out["chunks"] = sizes
        for block in (out.get("regimes") or {}).values():
            if isinstance(block.get("temperatures"), list):
                block["temperatures"] = block["temperatures"][:got]
            if isinstance(block.get("probs_probe"), list):
                block["probs_probe"] = block["probs_probe"][:min(len(block["probs_probe"]), got)]
        with open(flag("--payload"), "w") as fh:
            json.dump(out, fh)
        raise SystemExit(0)
    ''')
    body = body.replace("__FLAGS__", FLAG_HELPER.strip()).replace(
        "PAYLOADS_FILE", json.dumps(str(tmp_path / (name + ".payloads.json"))))
    return _script(tmp_path / name, body)


def _driver(tmp_path, cache=None, pin=None, python=None, extra=(), out="records.jsonl",
            upstream=None, force=True):
    """The real entry point, as a process, with the model stage planted.

    Several rows drive the same `tmp_path` twice on purpose -- a control run then a claiming run,
    over the same destination -- so the harness passes `--force`: it is the operator who means to
    replace the file. A caller that wants the overwrite refusal itself sets `force=False`; the
    refusal is not the behaviour of the tool being softened here, only of this fixture's intent.
    """
    if upstream is None:
        upstream, _ = _planted_upstream(tmp_path)
    report_path = Path(upstream) / "research" / "eval" / "planted_report.json"
    cmd = [sys.executable, str(DRIVER),
           "--cache", str(cache if cache is not None else tmp_path / "cache"),
           "--pin", str(pin if pin is not None else tmp_path / "pin.json"),
           "--out", str(tmp_path / out),
           "--upstream", str(upstream),
           "--python", str(python if python is not None else tmp_path / "no_worker.py")]
    if force:
        cmd += ["--force"]
    cmd += list(extra)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PLANTC_PARITY_REPORT": str(report_path)}
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), env=env)


def _ok_driver(tmp_path, payloads=None, langs=("en",), per_lang=2, out="records.jsonl",
               report=None, extra=(), chunk_size=None):
    cache, pin = _planted_root(tmp_path, langs=langs)
    _planted_upstream(tmp_path, report=report)
    if payloads is None:
        payloads = {"en": _staged(_probe(), _payload("en", n=per_lang))}
        for lang in langs:
            if lang != "en":
                payloads[lang] = {"full": _payload(lang, n=per_lang)}
    python = _fake_worker(tmp_path, payloads)
    args = ["--langs", ",".join(langs), "--per-lang", str(per_lang)]
    if chunk_size is not None:
        args += ["--chunk-size", str(chunk_size)]
    return _driver(tmp_path, cache=cache, pin=pin, python=python, out=out,
                   upstream=tmp_path / "upstream", extra=args + list(extra))


def _artefacts(tmp_path, out="records.jsonl"):
    """Both files one pass writes: (certified clamped rows, parity-control unclamped rows, path)."""
    name = Path(out).name
    certified = [json.loads(l) for l in (tmp_path / name).read_text().splitlines()]
    parity_path = tmp_path / ("%s_%s_parity%s"
                              % (Path(name).stem, PARITY_REGIME, Path(name).suffix))
    parity = [json.loads(l) for l in parity_path.read_text().splitlines()]
    return certified, parity, parity_path


def test_a_clean_build_exits_zero_and_writes_only_records_the_contract_reads(tmp_path):
    p = _ok_driver(tmp_path)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    lines = (tmp_path / "records.jsonl").read_text().splitlines()
    assert len(lines) == 2, lines
    recs = [json.loads(line) for line in lines]
    for rec in recs:
        Record.from_dict(rec)
    assert recs[0]["meta"]["probability_precision"] == 6
    assert recs[0]["meta"]["revision"] == REVISION
    assert recs[0]["meta"]["u_seed"] == 13 and recs[0]["seed"] == 13
    assert lines[0].startswith('{"backend"'), "keys sorted, so the artefact diffs cleanly"
    assert recs[0]["u"] != recs[1]["u"], "one draw per case, in stream order"


def test_the_probe_row_is_the_gate_and_a_planted_miss_stops_the_build_writing_nothing(tmp_path):
    """Parity is a gate, not a log line: the guard firing is the behaviour under test."""
    wrong = {k: PARITY[k] for k in PROBE_KEYS}
    wrong["ece"] = 0.9999                      # planted: a distribution that is not the published one
    p = _ok_driver(tmp_path, report=wrong)
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert "ece" in p.stderr and "0.1789" in p.stderr and "0.9999" in p.stderr, p.stderr
    assert not (tmp_path / "records.jsonl").exists(), "a refused build wrote an artefact"
    assert list(tmp_path.glob("*.tmp")) == [], "a temp artefact outlived the refusal"


@pytest.mark.parametrize("key", PROBE_KEYS)
def test_a_miss_on_any_published_figure_stops_the_build(tmp_path, key):
    wrong = {k: PARITY[k] for k in PROBE_KEYS}
    wrong[key] = round(PARITY[key] + 0.02, 4)
    p = _ok_driver(tmp_path, report=wrong)
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert key in p.stderr, p.stderr
    assert not (tmp_path / "records.jsonl").exists()


def test_the_gate_is_run_on_the_probe_cases_and_the_probe_cases_are_in_the_artefact(tmp_path):
    """The artefact carries its own parity proof: the probe rows are the artefact's own rows."""
    n = PARITY["per_lang"]
    probe = _probe(n=n, ids=[str(i) for i in range(n)])
    full = _payload("en", n=n, ids=[str(i) for i in range(n)])
    p = _ok_driver(tmp_path, payloads={"en": _staged(probe, full)}, per_lang=n)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    recs = [json.loads(l) for l in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert len(recs) == n
    assert {r["case_id"] for r in recs} == {"massive/en/%d" % i for i in range(n)}


def test_two_languages_are_both_written_and_each_carries_its_own_language_slice(tmp_path):
    n, per = PARITY["per_lang"], 2
    payloads = {"en": _staged(_probe(n=n), _payload("en", n=per)),
                "de": {"full": _payload("de", n=per, ids=[str(i + 500) for i in range(per)])}}
    p = _ok_driver(tmp_path, payloads=payloads, langs=("en", "de"), per_lang=per)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    recs = [json.loads(l) for l in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert len(recs) == 2 * per, [r["case_id"] for r in recs]
    assert sorted({r["slices"]["language"] for r in recs}) == ["de", "en"]
    assert len({r["case_id"] for r in recs}) == len(recs), "ids must not collide across languages"
    assert {r["meta"]["u_seed"] for r in recs} == {13, 14}, \
        "each language gets its own draw, so one u is not reused across tasks"


def test_a_destination_whose_parent_is_absent_is_refused_and_nothing_is_made(tmp_path):
    """The driver writes where it is told or not at all: no surprise directories."""
    p = _ok_driver(tmp_path, out="nested/records.jsonl")
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert not (tmp_path / "nested").exists(), "a refused build created a directory"


def test_missing_required_arguments_are_rc_2_and_never_1():
    p = subprocess.run([sys.executable, str(DRIVER)], capture_output=True, text=True, cwd=str(REPO))
    assert p.returncode == 2, (p.returncode, p.stderr)
    p = subprocess.run([sys.executable, str(DRIVER), "--cache", "x"], capture_output=True,
                       text=True, cwd=str(REPO))
    assert p.returncode == 2, (p.returncode, p.stderr)


def test_a_worker_command_line_that_names_no_upstream_tree_is_rc_2_and_not_a_traceback():
    """The stage resolves the checkpoint stack from `--upstream`, and the build layer always passes it.

    So the hole was invisible to every other test here until the equivalence stage was run by hand:
    a bare `--worker` reached `Path(None)` inside the stage and left as a `TypeError` with exit code
    1, the one outcome the module docstring calls unreachable "by construction". The refusal is the
    operator's, so it is rc 2 -- and it is a usage refusal rather than an `IncompleteBuildError`,
    because nothing about the machine is wrong.
    """
    base = [sys.executable, str(DRIVER), "--worker", "--lang", "en", "--stage", "probe",
            "--payload", "/tmp/unused-payload.json", "--cache", "x", "--pin", "y"]
    p = subprocess.run(base, capture_output=True, text=True, cwd=str(REPO))
    assert p.returncode == 2, (p.returncode, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert "--upstream" in p.stderr, p.stderr
    # The equivalence stage is reachable through the same door, so it is refused the same way.
    p = subprocess.run(base + ["--stage", "equivalence", "--layouts", "12,48"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert p.returncode == 2, (p.returncode, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    p = subprocess.run(base + ["--upstream", "z", "--stage", "not_a_stage"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert p.returncode == 2, (p.returncode, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr


def test_an_unpinned_language_is_a_usage_error_and_not_a_silent_skip(tmp_path):
    cache, pin = _planted_root(tmp_path)
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en,zz"])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "zz" in p.stderr, p.stderr
    assert not (tmp_path / "records.jsonl").exists()


def test_a_cache_that_disagrees_with_the_pin_is_drift_and_names_the_shard(tmp_path):
    cache, pin = _planted_root(tmp_path)
    (cache / "test" / "en.json.gz").write_bytes(
        gzip.compress(b'{"id": "0", "text": "one", "label_text": "a"}\n'))
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en", "--per-lang", "1"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "en.json.gz" in p.stderr, p.stderr
    assert "parity" not in p.stderr.lower(), "a cache defect must not read as a parity verdict"


def test_an_absent_cache_is_a_refusal_and_not_a_crash(tmp_path):
    _, pin = _planted_root(tmp_path)
    p = _driver(tmp_path, cache=tmp_path / "nowhere", pin=pin, extra=["--langs", "en"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "cache" in p.stderr.lower(), p.stderr


def test_a_pin_that_disagrees_with_itself_is_drift(tmp_path):
    cache, pin = _planted_root(tmp_path)
    broken = json.loads(pin.read_text())
    broken["rows_total"] += 1
    pin.write_text(json.dumps(broken))
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)


def test_a_worker_that_dies_is_rc_4_and_its_stderr_reaches_the_operator(tmp_path):
    cache, pin = _planted_root(tmp_path)
    path = _script(tmp_path / "dying_worker.py", '''
        #!/usr/bin/env python3
        import sys
        sys.stderr.write("out of memory (planted)\\n")
        raise SystemExit(3)
    ''')
    p = _driver(tmp_path, cache=cache, pin=pin, python=path,
                extra=["--langs", "en", "--per-lang", "1"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "planted" in p.stderr, p.stderr


def test_a_worker_that_raises_an_unnamed_exception_is_rc_4_not_rc_1(tmp_path):
    """`torch` absent and `No model on Cuda backend` are reachable inputs, not tracebacks."""
    cache, pin = _planted_root(tmp_path)
    path = _script(tmp_path / "traceback_worker.py", '''
        #!/usr/bin/env python3
        raise RuntimeError("the checkpoint is not in the local cache")
    ''')
    p = _driver(tmp_path, cache=cache, pin=pin, python=path,
                extra=["--langs", "en", "--per-lang", "1"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "checkpoint" in p.stderr, p.stderr


def test_a_stage_that_comes_back_short_is_refused(tmp_path):
    """`build_suite` slicing a shard that is shorter than the run is the reachable version."""
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": _payload("en", n=1)}})
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert not (tmp_path / "records.jsonl").exists()


def test_a_payload_that_answers_for_another_language_is_refused(tmp_path):
    payload = _payload("en", n=2)
    payload["lang"] = "de"
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(),
                                              "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert not (tmp_path / "records.jsonl").exists()


@pytest.mark.parametrize("mutate,expect", [
    (lambda pl: pl.__setitem__("gold", pl["gold"][:-1]), "does not line up"),
    (lambda pl: pl.__setitem__("option_keys", pl["option_keys"][:-1]), "does not line up"),
    (lambda pl: pl.__setitem__("item_ids", pl["item_ids"][:-1]), "does not line up"),
    (lambda pl: pl.__setitem__("texts", pl["texts"][:-1]), "does not line up"),
    (lambda pl: pl["regimes"]["unclamped"].__setitem__("temperatures",
                                                       pl["regimes"]["unclamped"]
                                                       ["temperatures"][:-1]), "does not line up"),
    (lambda pl: pl["logits"].__setitem__(0, pl["logits"][0][:-1]), "19 logits for 20 options"),
    (lambda pl: pl.__setitem__("logits", []), "for a run of"),
])
def test_a_payload_whose_arrays_do_not_line_up_is_refused(tmp_path, mutate, expect):
    """The mutation must reach the driver, not be swallowed on the way to it.

    `dict.__setitem__` and `list.__setitem__` both return `None`, so an earlier version of this test
    assigned `payload = mutate(_payload(...))` and handed the driver a literal `null`: every one of
    the seven cases then proved only that a null payload is refused, and the array-length checks
    themselves stayed unexecuted while the test stayed green. The payload is built first and mutated
    in place, and the refusal is matched on the message the array check writes, so a missing check
    would let the build succeed rather than fail somewhere else.

    The temperature case is inside one regime block, because that is where a temperature lives now:
    a column per regime, each with its own length to keep.
    """
    payload = _payload("en", n=2)
    mutate(payload)
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (expect, p.returncode, p.stderr[-400:])
    assert "Traceback" not in p.stderr, p.stderr[-400:]
    assert expect in p.stderr, (expect, p.stderr[-400:])
    assert not (tmp_path / "records.jsonl").exists()


@pytest.mark.parametrize("mutate,expect", [
    (lambda pl: pl["logits"][0].__setitem__(1, "0.5"), "logit"),
    (lambda pl: pl["logits"][0].__setitem__(1, None), "logit"),
    (lambda pl: pl["logits"][0].__setitem__(1, {}), "logit"),
    (lambda pl: pl["regimes"]["unclamped"].__setitem__(
        "temperatures", ["hot"] * len(pl["regimes"]["unclamped"]["temperatures"])), "temperature"),
    (lambda pl: pl["regimes"]["clamped"].__setitem__(
        "temperatures", [None] * len(pl["regimes"]["clamped"]["temperatures"])), "temperature"),
    (lambda pl: pl.__setitem__("timing", "no telemetry"), "timing"),
])
def test_a_payload_value_of_the_wrong_type_is_a_named_refusal_and_not_rc_1(tmp_path, mutate,
                                                                           expect):
    """`float()` and `.get()` are the two places a JSON value of the wrong shape becomes a traceback.

    The module promises rc 1 is unreachable "by construction"; a logit that is a string raises
    `ValueError` inside the finite check, a temperature that is a word raises inside `softmax_t`, and
    a `timing` that is a string raises `AttributeError` at the telemetry line. Each is a payload the
    stage could hand back, so each must be a named refusal with the field named.
    """
    payload = _payload("en", n=2)
    mutate(payload)
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (expect, p.returncode, p.stderr[-400:])
    assert "Traceback" not in p.stderr, (expect, p.stderr[-400:])
    assert expect in p.stderr.lower(), (expect, p.stderr[-400:])
    assert not (tmp_path / "records.jsonl").exists()


@pytest.mark.parametrize("qtype", ["noul", "score", "choice2"])
def test_a_stage_that_scored_something_other_than_choice_cannot_label_it_choice(tmp_path, qtype):
    """`records_from_logits` publishes every row as `qtype="choice"`, so the stage has to prove it.

    Nothing in the inherited payload said which question type was actually scored: the build layer
    assumed it. A stage run against a `noul` or `score` task -- which is where Task 4's other
    certified tasks go -- would have had its rows labelled `choice` with no refusal anywhere, and the
    temperature the checkpoint applies per qtype would have been quoted under the wrong bucket too.
    """
    full = _payload("en", n=2, qtype=qtype)
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": full}})
    assert p.returncode == 4, (qtype, p.returncode, p.stderr[-300:])
    assert "qtype" in p.stderr, (qtype, p.stderr[-300:])
    assert not (tmp_path / "records.jsonl").exists()


def test_a_payload_that_reports_no_qtype_is_a_refusal_not_an_assumption(tmp_path):
    payload = _payload("en", n=2)
    del payload["qtype"]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-300:])
    assert "carries no qtype" in p.stderr, p.stderr[-300:]


def test_the_parity_gate_compares_upstream_s_own_choice_not_only_our_conversion(tmp_path):
    """The stage hands back the row upstream's arithmetic produced from these very logits.

    `report_from_records` feeds upstream's `summarise` this build's *rounded* probabilities and
    *this build's* argmax of them, which is the right thing to certify -- but it is not the only
    side. The inherited driver collected `upstream_report` (the checkpoint stack's own unrounded
    argmax and confidences, computed in the vendored interpreter) into the run summary and never
    compared it to the published row, so a conversion that moved one prediction relative to
    upstream's own choice could pass the gate while the row upstream published said otherwise. The
    planted `summarise` returns the published figures, so the only thing that can refuse here is the
    stage's own report.
    """
    for figure, value in (("macro_f1", 0.1234), ("accuracy", 0.9), ("ece", 0.5),
                          ("mean_confidence", 0.5)):
        theirs = {f: PARITY[f] for f in PROBE_KEYS}
        theirs[figure] = value
        probe = _probe(upstream_report=dict({"n": PARITY["per_lang"]}, **theirs))
        p = _ok_driver(tmp_path, payloads={"en": _staged(probe, _payload("en", n=2))}, per_lang=2)
        assert p.returncode == 3, (figure, p.returncode, p.stderr[-400:])
        assert figure in p.stderr, (figure, p.stderr[-400:])
        assert "upstream" in p.stderr.lower(), (figure, p.stderr[-400:])
        assert not (tmp_path / "records.jsonl").exists()


def test_a_stage_that_says_nothing_about_its_own_row_cannot_be_gated(tmp_path):
    """A regime block with no `upstream_report` is a stage that answered partially.

    The report is per regime now, so the deletion is per block: the gate asks upstream's own
    arithmetic for *that* temperature, and a block that cannot say what its row was cannot be the
    side of a parity comparison whatever the other block says.
    """
    payload = _payload("en", n=2)
    for block in payload["regimes"].values():
        del block["upstream_report"]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-300:])
    assert "carries no upstream_report" in p.stderr, p.stderr[-300:]


def test_a_payload_that_is_not_json_is_refused(tmp_path):
    cache, pin = _planted_root(tmp_path)
    path = _script(tmp_path / "junk_worker.py", textwrap.dedent('''
        #!/usr/bin/env python3
        import sys

        __FLAGS__

        open(flag("--payload"), "w").write("<html>502 bad gateway</html>")
        raise SystemExit(0)
    ''').replace("__FLAGS__", FLAG_HELPER.strip()))
    path.chmod(0o755)
    p = _driver(tmp_path, cache=cache, pin=pin, python=path,
                extra=["--langs", "en", "--per-lang", "2"])
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)


def test_a_softmax_that_diverges_from_upstreams_is_refused(tmp_path):
    """The driver re-implements softmax_t, so the re-implementation is checked against upstream's.

    Checked per regime, against that regime's own temperatures: one shared probe would let a driver
    that scored the clamped column at the unclamped temperature pass, which is the exact defect
    R-118's two-block payload exists to make impossible.
    """
    for regime in REGIMES:
        payload = _payload("en", n=2)
        wrong = [0.5, 0.5] + [0.0] * 18            # 20-wide, and not a softmax of anything
        payload["regimes"][regime]["probs_probe"] = [list(wrong), list(wrong)]
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (regime, p.returncode, p.stdout, p.stderr)
        assert "differs from upstream" in p.stderr.lower(), (regime, p.stderr)
        assert "regime=%s" % regime in p.stderr, (regime, p.stderr)


def test_a_probs_probe_that_covers_no_case_checks_nothing_and_is_refused(tmp_path):
    """An empty probe would let the softmax self-check pass vacuously."""
    for regime in REGIMES:
        payload = _payload("en", n=2)
        payload["regimes"][regime]["probs_probe"] = []
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (regime, p.returncode, p.stdout, p.stderr)
        assert "carried no probs_probe" in p.stderr.lower(), (regime, p.stderr)
        assert regime in p.stderr, (regime, p.stderr)


def test_the_certified_regime_is_a_constant_and_not_something_the_operator_types(tmp_path):
    """R-118: `--regime` is gone, because the headline column must not be a word away.

    The parity row is stated under `unclamped`, whose temperature upstream's own code rejects
    (`choice:11+ = 0.10058`, outside [0.5, 5]), and whose `mean_confidence` is 0.9989 -- a column
    upstream declines to treat as calibrated. If a flag selected which artefact was the certified
    one, a typo would publish that saturated column as G1's number. So the driver scores both regimes
    out of one pass, names the certified one in code (`CERTIFIED_REGIME`), and refuses the flag the
    way argparse refuses anything it does not know: exit 2, the usage code, with nothing written.
    """
    from tools import build_records as br

    assert br.CERTIFIED_REGIME == "clamped" and br.PARITY_REGIME == PARITY["regime"]
    assert CERTIFIED_REGIME != PARITY_REGIME, \
        "one of the two rulings is being mis-stated: the certified regime is not the parity regime"
    cache, pin = _planted_root(tmp_path)
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en", "--regime", "clamped"])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "--regime" in p.stderr, p.stderr
    assert "unrecognized" in p.stderr, p.stderr
    assert not (tmp_path / "records.jsonl").exists()


def test_the_parity_gate_refuses_the_certified_regime_on_identity_alone(tmp_path):
    """Four figures equal to the published row, under the wrong regime, are not the published row.

    This is what stops a future parity miss from being "fixed" by comparing the clamped column
    against `PARITY`: the certified side inherits the proof (same cases, same forward pass, same
    recorded `u`) rather than carrying its own, and `check_parity` is the guard that keeps the two
    from being interchanged.
    """
    figures = {k: PARITY[k] for k in PROBE_KEYS}
    with pytest.raises(ParityError, match="regime"):
        check_parity(_report(regime=CERTIFIED_REGIME, **figures), PARITY)
    check_parity(_report(regime=PARITY_REGIME, **figures), PARITY)


def test_per_lang_beyond_the_shard_on_disk_is_refused_before_any_model_runs(tmp_path):
    cache, pin = _planted_root(tmp_path, rows=100)
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en", "--per-lang", "5000"])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "100" in p.stderr, p.stderr


def test_the_gate_quotes_the_probe_conditions_even_when_the_artefact_is_larger(tmp_path):
    """--per-lang sizes the artefact; the gate stays at n=100 or it is not the published row."""
    cache, pin = _planted_root(tmp_path)
    n = PARITY["per_lang"]
    python = _fake_worker(tmp_path, {"en": {"probe": _probe(n=n),
                                            "full": _payload("en", n=5)}})
    p = _driver(tmp_path, cache=cache, pin=pin, python=python,
                extra=["--langs", "en", "--per-lang", "5"])
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert len((tmp_path / "records.jsonl").read_text().splitlines()) == 5
    assert "n=100" in p.stdout or "probe" in p.stdout.lower(), p.stdout


def test_the_artefact_must_contain_the_cases_it_was_gated_on(tmp_path):
    """The parity proof is about this file: if the probe rows are not the artefact's rows, stop."""
    full = _payload("en", n=2, ids=["900", "901"])
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(),
                                              "full": full}})
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert "prefix" in p.stderr.lower(), p.stderr
    assert not (tmp_path / "records.jsonl").exists()


def test_an_artefact_that_omits_the_gated_language_is_refused(tmp_path):
    """--langs without `en` would publish a file the parity row says nothing about."""
    cache, pin = _planted_root(tmp_path, langs=("en", "de"))
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "de", "--per-lang", "2"])
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert "en" in p.stderr, p.stderr
    assert not (tmp_path / "records.jsonl").exists()


def test_absent_telemetry_is_a_gap_in_the_log_and_not_a_refusal(tmp_path):
    """`timing` says how fast the stage ran; a stage that reported nothing still ran."""
    payload = _payload("en", n=2)
    payload["timing"] = {}
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr[-400:])
    rec = json.loads((tmp_path / "records.jsonl").read_text().splitlines()[0])
    assert "device" not in rec["meta"], rec["meta"]
    assert rec["meta"]["probability_precision"] == 6


def test_the_run_summary_reports_the_device_the_stages_actually_ran_on(tmp_path):
    """`device` is the only field in the run summary that says *where* these numbers came from.

    `stage_device` takes a payload and digs out `payload["timing"]["device"]`, and the summary line
    handed it the timing dict instead of the payload -- so it returned None on every run, including
    the real pilot where both stages reported mps. A build log that cannot say whether the certified
    figures came off mps, cpu or cuda is not an audit trail, and the mistake is invisible unless the
    field is asserted: a None is a perfectly valid JSON value.
    """
    p = _ok_driver(tmp_path, extra=["--summary", str(tmp_path / "summary.json")])
    assert p.returncode == 0, (p.returncode, p.stderr[-400:])
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["device"] == "cpu", summary["device"]
    assert summary["probe"]["device"] == "cpu", summary["probe"]
    assert {v["device"] for v in summary["languages"].values()} == {"cpu"}, summary["languages"]


def test_a_payload_missing_a_key_the_build_indexes_is_refused_not_a_keyerror(tmp_path):
    """rc 1 must stay unreachable, and an absent telemetry key is a reachable payload shape.

    The two lists are every key the build layer indexes with `payload[...]` / `block[...]` rather
    than `.get()`, so a new indexed field has to be named here before the stage can omit it -- which
    is how `upstream_report` and `qtype` got away: both are indexed, neither was required, and the
    inherited suite only deleted the four that were. (`n_cases` is not in the list because the stage
    re-states it from the arrays it built, so a payload cannot arrive without it.)

    The regime-block keys are deleted from *both* blocks: one block missing a key is a stage that
    scored one regime and not the other, and the driver has to say so before it writes either file.
    """
    for key in ("timing", "texts", "item_ids", "gold", "option_keys", "logits",
                "regimes", "chunk_size", "chunks", "warnings",
                "qtype", "n_opts", "seed", "lang", "stage"):
        payload = _payload("en", n=2)
        del payload[key]
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (key, p.returncode, p.stderr[-400:])
        assert "Traceback" not in p.stderr, (key, p.stderr[-400:])
        assert "carries no %s" % key in p.stderr, (key, p.stderr[-400:])
    from tools.build_records import REQUIRED_REGIME_KEYS

    for key in REQUIRED_REGIME_KEYS:
        payload = _payload("en", n=2)
        for block in payload["regimes"].values():
            del block[key]
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (key, p.returncode, p.stderr[-400:])
        assert "Traceback" not in p.stderr, (key, p.stderr[-400:])
        assert "carries no %s" % key in p.stderr, (key, p.stderr[-400:])
        assert PARITY_REGIME in p.stderr, (key, p.stderr[-400:])


def test_a_non_finite_logit_is_refused_rather_than_becoming_a_zero(tmp_path):
    payload = _payload("en", n=2)
    payload["logits"][1][3] = float("nan")
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stderr[-400:])
    assert "finite" in p.stderr, p.stderr


def test_the_conversion_refuses_a_non_finite_logit_when_called_directly():
    from tools.build_records import DriftError as _DriftError

    with pytest.raises(_DriftError, match="finite"):
        records_from_logits([[0.0, float("inf"), 1.0]], [0], [["a", "b", "c"]], "en", iter([0.5]))


@pytest.mark.parametrize("bad", ["0.5", None, {}, [1.0]])
def test_a_logit_that_is_not_a_number_is_a_refusal_however_it_parses(bad):
    """`float("0.5")` succeeds, which is exactly why a string logit must still be refused.

    The payload is JSON from another interpreter, so the values it carries are whatever that side
    had in hand; the build layer's own contract is a vector of real numbers, and a value that only
    *coerces* to one is a shape change, not a number.
    """
    from tools.build_records import DriftError as _DriftError

    with pytest.raises(_DriftError, match="logit"):
        records_from_logits([[0.0, bad, 1.0]], [0], [["a", "b", "c"]], "en", iter([0.5]))


def test_a_gold_index_outside_the_ballot_is_a_refusal_not_an_index_error():
    """`keys[int(g)]` is what publishes gold; an out-of-range index leaves as rc 1 without this."""
    from tools.build_records import DriftError as _DriftError

    for g in (3, 99, -1):
        with pytest.raises(_DriftError, match="gold"):
            records_from_logits([_fake_logits(3, 0)], [g], [["a", "b", "c"]], "en", iter([0.5]))


def test_a_ballot_of_one_option_is_refused_because_it_is_not_a_choice_question():
    """`records_from_logits` hardcodes `qtype="choice"`, and a 1-slot vector is not one.

    `autorate.records.validate` refuses a one-option decision -- "a certificate over nothing is a
    vacuity bug" -- but the build layer writes dicts and never builds a `Record`, so nothing on the
    write path enforced it: a shard whose label pool collapsed (upstream's `build_suite` shrinks the
    ballot to `min(n_opts - 1, len(pool))` without saying so) would have been published as a
    well-formed `choice` row with `probs: [1.0]`.
    """
    from tools.build_records import DriftError as _DriftError

    with pytest.raises(_DriftError, match="at least 2"):
        records_from_logits([[0.0]], [0], [["a"]], "en", iter([0.5]))
    assert records_from_logits([[0.0, 1.0]], [0], [["a", "b"]], "en",
                               iter([0.5]))[0]["qtype"] == "choice", \
        "a real two-slot ballot is a choice question and must still be written"


def test_a_shard_line_that_is_not_json_is_a_named_refusal_not_a_traceback(tmp_path):
    """`load_rows` reads the pinned bytes in the model stage; a torn body must be named."""
    from tools.build_records import load_rows

    cache, _ = _planted_root(tmp_path, rows=3)
    shard = cache / "test" / "en.json.gz"
    shard.write_bytes(gzip.compress(b'{"id": "0", "text": "a", "label_text": "b"}\nnot json\n'))
    with pytest.raises(DriftError, match="not JSON"):
        load_rows(cache, "en")
    shard.write_bytes(b"this is not gzip at all")
    with pytest.raises(DriftError, match="gunzip"):
        load_rows(cache, "en")
    shard.write_bytes(gzip.compress(b'{"id": "0", "text": "a"}\n'))
    with pytest.raises(DriftError, match="label_text"):
        load_rows(cache, "en")
    with pytest.raises(DriftError, match="carry no"):
        load_rows(cache, "en", id_key="absent_id_key")
    shard.write_bytes(gzip.compress(
        b'{"id": "0", "text": "a", "label_text": "b"}\n\n'
        b'{"id": "1", "text": "c", "label_text": "d"}\n'))
    assert [r["id"] for r in load_rows(cache, "en")] == ["0", "1"], "blank lines are not rows"


def test_a_shard_line_that_is_valid_json_but_not_an_object_names_itself(tmp_path):
    """`first` is the message every `load_rows` refusal quotes, and one branch never set it.

    A line that parses but is not a mapping -- `null`, `123`, `[1, 2]`, a body truncated at a
    newline -- incremented the malformed count without recording what it saw, and the raise then
    formatted an unbound local: `UnboundLocalError`, a `ValueError` subclass, so `main`'s map let it
    through as exit code 1 -- the one outcome the module docstring says is unreachable "by
    construction". A `DriftError` naming the line is what a reader of the build log needs.
    """
    from tools.build_records import load_rows

    cache, _ = _planted_root(tmp_path, rows=3)
    shard = cache / "test" / "en.json.gz"
    for body, named in ((b'{"id": "0", "text": "a", "label_text": "b"}\n[1, 2]\n', "list"),
                        (b'{"id": "0", "text": "a", "label_text": "b"}\nnull\n', "NoneType"),
                        (b'{"id": "0", "text": "a", "label_text": "b"}\n123\n', "int")):
        shard.write_bytes(gzip.compress(body))
        with pytest.raises(DriftError, match="not JSON objects") as excinfo:
            load_rows(cache, "en")
        assert named in str(excinfo.value), (named, str(excinfo.value))
        assert "UnboundLocalError" not in str(excinfo.value)
    # A non-object line alone is a refusal too, and so is one that follows a field-less row: the
    # malformed count is reported first, and `first` must name whichever defect was seen first.
    shard.write_bytes(gzip.compress(b'["whole file is a list"]\n'))
    with pytest.raises(DriftError, match="not JSON objects"):
        load_rows(cache, "en")
    shard.write_bytes(gzip.compress(b'{"id": "0", "text": "a", "label_text": "b"}\n123\n'
                                    b'{"id": "1", "text": "c"}\n'))
    with pytest.raises(DriftError, match="not JSON objects") as excinfo:
        load_rows(cache, "en")
    assert "int" in str(excinfo.value), str(excinfo.value)


def test_the_worker_entry_point_maps_a_missing_checkpoint_stack_to_rc_4(tmp_path):
    """The planted `laya` raises the way a real load failure does, in a torch-free interpreter."""
    cache, pin = _planted_root(tmp_path)
    laya_dir = tmp_path / "upstream" / "laya"
    laya_dir.mkdir(parents=True, exist_ok=True)
    (laya_dir / "__init__.py").write_text(textwrap.dedent('''
        """Planted checkpoint stack: importable, and it fails like a real load failure."""
        __version__ = "planted"

        def load(*a, **kw):
            raise RuntimeError("no kernel image is available for execution on the device (planted)")
    '''))
    (laya_dir / "common.py").write_text('QTYPES = {"choice": 0, "score": 1, "noul": 2}\n')
    _planted_upstream(tmp_path)
    cmd = [sys.executable, str(DRIVER), "--worker", "--lang", "en", "--stage", "probe",
           "--payload", str(tmp_path / "p.json"), "--cache", str(cache), "--pin", str(pin),
           "--upstream", str(tmp_path / "upstream"), "--model", "planted", "--device", "",
           "--per-lang", "100", "--n-opts", "20", "--seed", "13", "--chunk-size", "150"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "Traceback" not in p.stderr, p.stderr
    assert "planted" in p.stderr, p.stderr


def test_no_reachable_planted_input_leaks_rc_1(tmp_path):
    """Every failure this tool can name, driven through the real entry point, landing in 0/2/3/4."""
    cache, pin = _planted_root(tmp_path, langs=("en", "de"))
    n, per = PARITY["per_lang"], 2
    dying = _script(tmp_path / "dying.py", '''
        #!/usr/bin/env python3
        raise SystemExit(9)
    ''')
    clean_python = _fake_worker(tmp_path, {"en": _staged(_probe(n=n), _payload("en", n=per)),
                                           "de": {"full": _payload("de", n=per)}},
                                name="clean_worker.py")
    short_python = _fake_worker(tmp_path, {"en": {"probe": _probe(n=n),
                                                  "full": _payload("en", n=per)}},
                                name="short_worker.py")
    runs = {
        "clean": (_driver(tmp_path, cache=cache, pin=pin, python=clean_python, out="ok.jsonl",
                          extra=["--langs", "en,de", "--per-lang", str(per)]), 0),
        "no-cache": (_driver(tmp_path, cache=tmp_path / "gone", pin=pin, out="a.jsonl",
                             extra=["--langs", "en"]), 4),
        "no-pin": (_driver(tmp_path, cache=cache, pin=tmp_path / "nope.json", out="b.jsonl",
                           extra=["--langs", "en"]), 4),
        "bad-lang": (_driver(tmp_path, cache=cache, pin=pin, out="c.jsonl",
                             extra=["--langs", "zz"]), 2),
        "worker-dies": (_driver(tmp_path, cache=cache, pin=pin, python=dying, out="d.jsonl",
                                extra=["--langs", "en", "--per-lang", "100"]), 4),
        "no-worker": (_driver(tmp_path, cache=cache, pin=pin, out="e.jsonl",
                              extra=["--langs", "en", "--per-lang", "100"]), 4),
        "no-stage": (_driver(tmp_path, cache=cache, pin=pin, python=short_python, out="f.jsonl",
                             extra=["--langs", "en,de", "--per-lang", str(per)]), 4),
        "bad-out-dir": (_driver(tmp_path, cache=cache, pin=pin, out="nowhere/records.jsonl",
                                extra=["--langs", "en", "--per-lang", "100"]), 4),
    }
    off_contract = {k: (p.returncode, p.stderr[-300:]) for k, (p, want) in runs.items()
                    if p.returncode not in (0, 2, 3, 4)}
    assert off_contract == {}, off_contract
    wrong_code = {k: (p.returncode, want, p.stderr[-300:]) for k, (p, want) in runs.items()
                  if p.returncode != want}
    assert wrong_code == {}, wrong_code


def test_the_refusals_are_not_value_errors_so_no_wider_catch_can_file_them():
    """Precedent: ReaderContractError is deliberately not a ValueError (cli.py I-2)."""
    for cls in (DriftError, IncompleteBuildError, UsageRefusal, ParityError, UStreamExhausted):
        assert issubclass(cls, RuntimeError), cls
        assert not issubclass(cls, ValueError), cls
    assert issubclass(DriftError, BuildError) and issubclass(IncompleteBuildError, BuildError)
    assert not issubclass(ParityError, BuildError), \
        "the parity verdict must never be caught by the clause that maps 4"
    assert not issubclass(UsageRefusal, BuildError)


def test_an_upstream_softmax_that_cannot_import_numpy_is_a_named_refusal(monkeypatch):
    """#67: the parity path called the harness's `softmax_t` with no numeric-stack wrapper.

    Reproduced on the real tree with `/opt/homebrew/opt/python@3.12/bin/python3.12`, which has no
    numpy: the run exited **1** with a traceback out of `check_payload`, while this module's own
    docstring lists "no numpy" as an `IncompleteBuildError` case. The metric path already names that
    refusal; the parity path was the one place that called code it does not own and let the import
    error through. rc 1 is the outcome this tool says is unreachable.
    """
    from tools.build_records import PARITY, IncompleteBuildError, check_payload

    class _NoNumericStack:
        @staticmethod
        def softmax_t(values, temperature):
            raise ModuleNotFoundError("No module named 'numpy'")

    # The probe payload, driven the way `build` drives it (same stage, same per_lang), so the call
    # reaches the upstream comparison instead of tripping an earlier shape check.
    with pytest.raises(IncompleteBuildError) as excinfo:
        check_payload(_probe(), PARITY["lang"], "probe", PARITY["per_lang"], _NoNumericStack())
    message = str(excinfo.value)
    assert "numpy" in message, message[:300]
    assert "ModuleNotFoundError" in message, message[:300]


def test_the_driver_refuses_to_overwrite_an_existing_artefact_before_it_works(tmp_path, monkeypatch):
    """#67: `--out` replaced a file without confirmation, and the parity sibling's name makes it
    easy to aim at the published records file. The guard has to run before the build, because a
    guard that fires after the scoring pass has protected nothing the operator did not already lose.
    """
    from tools import build_records as br

    out = tmp_path / "records_certified.jsonl"
    out.write_text("PRECIOUS CERTIFIED ROWS\n")
    ran = []
    monkeypatch.setattr(br, "build", lambda args: ran.append("build") or 0)

    rc = br.main(["--cache", str(tmp_path), "--out", str(out)])
    assert rc == br.EXIT_USAGE, (rc, out.read_text())
    assert not ran, "the build ran anyway, so the refusal came after the work it was meant to skip"
    assert out.read_text() == "PRECIOUS CERTIFIED ROWS\n"

    rc = br.main(["--cache", str(tmp_path), "--out", str(out), "--force"])
    assert rc == 0, rc
    assert ran == ["build"], "with --force the build must proceed"


def test_the_parity_control_is_protected_by_the_same_guard(tmp_path, monkeypatch):
    """The two destinations are separate regimes; the sibling default must not be able to clobber
    a file the operator did not name, so the guard covers `--out-parity` too and says which one."""
    from tools import build_records as br

    parity = tmp_path / "records_parity.jsonl"
    parity.write_text("PRECIOUS PARITY CONTROL\n")
    ran = []
    monkeypatch.setattr(br, "build", lambda args: ran.append("build") or 0)

    rc = br.main(["--cache", str(tmp_path), "--out", str(tmp_path / "fresh.jsonl"),
                  "--out-parity", str(parity)])
    assert rc == br.EXIT_USAGE, rc
    assert not ran
    assert parity.read_text() == "PRECIOUS PARITY CONTROL\n"


def test_the_real_process_refuses_a_second_run_at_the_same_destination(tmp_path):
    """The overwrite guard on the documented invocation path, in a process, not only in `main`.

    The harness above runs twice per test by intent; this row is the case where that intent is
    absent, and the second run must be refused before it writes. `--force` is then the only way
    through, which is the point of having a flag rather than a warning line nobody reads.
    """
    first = _ok_driver(tmp_path)
    assert first.returncode == 0, (first.returncode, first.stderr[-400:])
    out = tmp_path / "records.jsonl"
    assert out.exists(), "the first run wrote nothing, so the second has no destination to refuse"
    written = out.read_text()

    cache, pin = _planted_root(tmp_path, langs=("en",))
    upstream, _ = _planted_upstream(tmp_path)
    # The same language set the first run used. `--langs` defaults to `en,de,sw`, and both a missing
    # shard pin and the overwrite guard answer rc 2, so an unasserted message here would let a
    # different usage error satisfy `returncode == 2`; the message is the assertion, the code is not.
    asked = ("--langs", "en", "--per-lang", "2")
    second = _driver(tmp_path, cache=cache, pin=pin, upstream=upstream, extra=asked, force=False)
    assert second.returncode == 2, (second.returncode, second.stderr[-500:])
    assert "refusing to overwrite" in second.stderr, second.stderr[-500:]
    assert out.read_text() == written, "the refused run still changed the artefact"

    # No third run here. Driving a successful `--force` build through a real process needs the planted
    # worker interpreter that `_ok_driver` builds and does not hand back, and reconstructing that
    # private fixture to prove a half this file already covers elsewhere would be a test reading its own
    # plumbing: `test_the_driver_refuses_to_overwrite_an_existing_artefact_before_it_works` asserts
    # `main` proceeds with `--force`, and the first run above is a real process writing a real file.
