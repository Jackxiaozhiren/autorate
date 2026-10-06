"""Plan C Task 2: the scoring driver's pure layer, and the exit codes of its real entry point.

Two rules shape this file. First: nothing here imports torch, laya or a model -- the conversion,
the `u` draw and the parity comparison are testable with no model in the room, which is the whole
point of the split (the unit suite runs offline forever, ledger R-12 condition 1). Second: a guard
is only real if it can be shown to fire, so every refusal -- a parity miss, a cache that disagrees
with the pin, a softmax that diverges from upstream's, a worker that dies -- is driven to its red
here with the defect planted in a fixture, never by relaxing an assertion.

The subprocess tests drive `python3 tools/build_records.py`, the documented invocation, and read
the exit code the shell sees. The model stage is replaced by a planted interpreter and a planted
upstream tree, so the code under test is the code the real build runs: argument handling, the pin
check, the payload checks, the conversion, the parity gate, and the refusal to write anything.
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
    PARITY,
    BuildError,
    DriftError,
    IncompleteBuildError,
    ParityError,
    UStreamExhausted,
    UsageRefusal,
    check_parity,
    draw_u,
    records_from_logits,
    report_from_records,
    softmax_t,
)

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / "tools" / "build_records.py"
PIN_SCHEMA = "autorate-massive-pin/1"
PROBE_KEYS = ("accuracy", "mean_confidence", "macro_f1", "ece")
REVISION = "940fd47a81eaa7f2cc7b129674d945d618ac38c2"


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


# ------------------------------------------------------------- the offline boundary itself
def test_the_build_layer_pulls_in_no_torch_and_no_laya():
    """Plan C Step 7: a build-only dependency in the import path is the unforgivable defect."""
    assert "torch" not in sys.modules and "laya" not in sys.modules
    head = DRIVER.read_text().split("def ", 1)[0]
    for forbidden in ("import torch", "import laya", "from laya", "from torch"):
        assert forbidden not in head, "%s is at module scope in the driver" % forbidden


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


def _payload(lang, n=2, k=20, temperature=0.5, ids=None, texts=None, stage="full",
             qtype="choice", regime="unclamped", upstream_report=None):
    """The shape `_score_batch` really returns, including the two fields that carry its identity.

    `qtype` and `regime` are what the stage knows and the build layer would otherwise assume, and
    `upstream_report` is the row upstream's own arithmetic produced from these logits -- the side of
    the parity comparison that is not this build's rounding, so its planted figures are the published
    ones unless a test deliberately disagrees with them.
    """
    keys = [["k%d" % j for j in range(k)] for _ in range(n)]
    logits = [[0.0 if j != (i % k) else 2.0 for j in range(k)] for i in range(n)]
    if upstream_report is None:
        upstream_report = dict({"n": n}, **{f: PARITY[f] for f in PROBE_KEYS})
    return {"lang": lang, "stage": stage, "n_cases": n, "n_opts": k, "seed": 13,
            "qtype": qtype, "regime": regime,
            "item_ids": ids if ids is not None else [str(i) for i in range(n)],
            "gold": [i % k for i in range(n)], "option_keys": keys, "logits": logits,
            "temperatures": [temperature] * n,
            "texts": texts if texts is not None else ["ask %d" % i for i in range(n)],
            "probs_probe": [softmax_t(z, temperature) for z in logits[:min(3, n)]],
            "upstream_report": upstream_report,
            "timing": {"load_s": 1.0, "score_s": 2.0, "device": "cpu",
                       "cases_per_s": float(n) / 2.0, "torch": "planted", "laya": "planted"}}


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
        # The real stage scores exactly `--per-lang` cases, so the planted one sizes itself the same
        # way: a probe run sized to the artefact instead of the published row then comes back with
        # the wrong n, which is what the driver has to notice.
        out = dict(out)
        want = int(flag("--per-lang"))
        got = min(want, len(out.get("logits") or []))
        out["n_cases"] = got
        for key in ("item_ids", "gold", "option_keys", "logits", "temperatures", "texts"):
            if isinstance(out.get(key), list):
                out[key] = out[key][:got]
        if isinstance(out.get("probs_probe"), list):
            out["probs_probe"] = out["probs_probe"][:min(len(out["probs_probe"]), got)]
        with open(flag("--payload"), "w") as fh:
            json.dump(out, fh)
        raise SystemExit(0)
    ''')
    body = body.replace("__FLAGS__", FLAG_HELPER.strip()).replace(
        "PAYLOADS_FILE", json.dumps(str(tmp_path / (name + ".payloads.json"))))
    return _script(tmp_path / name, body)


def _driver(tmp_path, cache=None, pin=None, python=None, extra=(), out="records.jsonl",
            upstream=None):
    """The real entry point, as a process, with the model stage planted."""
    if upstream is None:
        upstream, _ = _planted_upstream(tmp_path)
    report_path = Path(upstream) / "research" / "eval" / "planted_report.json"
    cmd = [sys.executable, str(DRIVER),
           "--cache", str(cache if cache is not None else tmp_path / "cache"),
           "--pin", str(pin if pin is not None else tmp_path / "pin.json"),
           "--out", str(tmp_path / out),
           "--upstream", str(upstream),
           "--python", str(python if python is not None else tmp_path / "no_worker.py")]
    cmd += list(extra)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PLANTC_PARITY_REPORT": str(report_path)}
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), env=env)


def _ok_driver(tmp_path, payloads=None, langs=("en",), per_lang=2, out="records.jsonl",
               report=None, extra=()):
    cache, pin = _planted_root(tmp_path, langs=langs)
    _planted_upstream(tmp_path, report=report)
    if payloads is None:
        payloads = {"en": _staged(_probe(), _payload("en", n=per_lang))}
        for lang in langs:
            if lang != "en":
                payloads[lang] = {"full": _payload(lang, n=per_lang)}
    python = _fake_worker(tmp_path, payloads)
    return _driver(tmp_path, cache=cache, pin=pin, python=python, out=out,
                   upstream=tmp_path / "upstream",
                   extra=["--langs", ",".join(langs), "--per-lang", str(per_lang), *extra])


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
    (lambda pl: pl.__setitem__("temperatures", pl["temperatures"][:-1]), "does not line up"),
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
    (lambda pl: pl.__setitem__("temperatures", ["hot"] * len(pl["temperatures"])), "temperature"),
    (lambda pl: pl.__setitem__("temperatures", [None] * len(pl["temperatures"])), "temperature"),
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
    payload = _payload("en", n=2)
    del payload["upstream_report"]
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
    """The driver re-implements softmax_t, so the re-implementation is checked against upstream's."""
    payload = _payload("en", n=2, temperature=0.5)
    wrong = [0.5, 0.5] + [0.0] * 18            # 20-wide, and not a softmax of anything
    payload["probs_probe"] = [list(wrong), list(wrong)]
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(),
                                              "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "differs from upstream" in p.stderr.lower(), p.stderr


def test_a_probs_probe_that_covers_no_case_checks_nothing_and_is_refused(tmp_path):
    """An empty probe would let the softmax self-check pass vacuously."""
    payload = _payload("en", n=2)
    payload["probs_probe"] = []
    p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
    assert p.returncode == 4, (p.returncode, p.stdout, p.stderr)
    assert "carried no probs_probe" in p.stderr.lower(), p.stderr


def test_unclamped_is_the_only_regime_the_parity_row_is_stated_under(tmp_path):
    """PARITY says `unclamped`; asking for the clamped regime must stop, not silently re-quote it."""
    cache, pin = _planted_root(tmp_path)
    p = _driver(tmp_path, cache=cache, pin=pin, extra=["--langs", "en", "--regime", "clamped"])
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "unclamped" in p.stderr, p.stderr


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


def test_a_payload_missing_a_key_the_build_indexes_is_refused_not_a_keyerror(tmp_path):
    """rc 1 must stay unreachable, and an absent telemetry key is a reachable payload shape.

    The list is every key `build()` indexes with `payload[...]` rather than `.get()`, so a new
    indexed field has to be named here before the stage can omit it -- which is how `upstream_report`
    and `qtype` got away: both are indexed, neither was required, and the inherited suite only
    deleted the four that were. (`n_cases` is not in the list because the stage re-states it from the
    arrays it built, so a payload cannot arrive without it.)
    """
    for key in ("timing", "texts", "probs_probe", "item_ids", "gold", "option_keys", "logits",
                "temperatures", "upstream_report", "qtype", "regime", "n_opts", "seed", "lang",
                "stage"):
        payload = _payload("en", n=2)
        del payload[key]
        p = _ok_driver(tmp_path, payloads={"en": {"probe": _probe(), "full": payload}})
        assert p.returncode == 4, (key, p.returncode, p.stderr[-400:])
        assert "Traceback" not in p.stderr, (key, p.stderr[-400:])
        assert "carries no %s" % key in p.stderr, (key, p.stderr[-400:])


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
           "--regime", "unclamped", "--per-lang", "100", "--n-opts", "20", "--seed", "13"]
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
