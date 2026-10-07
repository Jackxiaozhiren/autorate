"""Task 7b: the two-way choice certifier.

Every assertion here is about a number the certificate claims, so the tests check the
claim, not the code path: an automation rate that ignores refusals, or a conditional
bound that quietly equals the marginal one, both pass a weaker suite.
"""
import importlib
import json
import math
import random
import shutil
from pathlib import Path

import pytest

from autorate.certificate import CANONICALISED_BOUND_FIELDS, Reason, canonicalise_bound
from autorate.certify_choice import certify_choice
from autorate.nonconformity import aps_score
from autorate.records import Record
from autorate.tails import clopper_pearson_upper

REPO = Path(__file__).resolve().parents[1]
CERT_FILES = ("data/cert_laya.json", "data/cert_jev.json")


def _records(n, k=4, sharpness=6.0, seed=1, backend="synthetic", unlabelled=0,
             error_rate=0.0):
    """Synthetic labelled decisions.

    `error_rate` matters: the first version always peaked the probability vector on the
    gold label, so the argmax was never wrong, `errors_among_automated` came out 0 for
    every difficulty, and the whole error-budget sweep was vacuous. A certifier that is
    never shown a wrong answer cannot be shown refusing one.
    """
    rng = random.Random(seed)
    out = []
    for i in range(n):
        g = rng.randrange(k)
        peaked = g if rng.random() >= error_rate else (g + 1 + rng.randrange(k - 1)) % k
        w = [1.0] * k
        w[peaked] = sharpness
        tot = sum(w) + k * 0.05
        p = [x / tot for x in w]
        p = [round(x, 4) for x in p]
        p[peaked] = round(p[peaked] + (1.0 - sum(p)), 4)
        options = tuple("opt%d" % j for j in range(k))
        gold = None if i < unlabelled else options[g]
        out.append(Record(id=str(i), qtype="choice", backend=backend, repeat=0,
                          options=options, probs=tuple(p), gold=gold,
                          predicted=options[peaked], slices={}, scores={}, seed=seed,
                          u=rng.random(), meta={}))
    return out


def test_the_generator_actually_makes_wrong_argmaxes_when_asked():
    # Guards the vacuity of the error sweep: with error_rate=0.5 about half the
    # records must have predicted != gold, and with 0.0 none.
    clean = _records(400, sharpness=6.0, error_rate=0.0)
    noisy = _records(400, sharpness=6.0, error_rate=0.5)
    assert sum(r.predicted != r.gold for r in clean) == 0
    wrong = sum(r.predicted != r.gold for r in noisy)
    assert 120 < wrong < 280, wrong


def test_a_sharp_easy_task_produces_a_number_and_both_bounds():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is True, cert.summary()
    assert 0.0 < cert.autorate <= 1.0
    lo, hi = cert.autorate_ci
    assert lo <= cert.autorate <= hi
    assert cert.conditional_error_bound <= 0.05 + 1e-9
    assert cert.marginal_error_bound <= cert.conditional_error_bound
    assert cert.n_cal + cert.n_eval == 1200


def test_the_refusal_mass_is_reported_and_consistent_with_the_automation_rate():
    cert = certify_choice(_records(1200, sharpness=4.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.refusal_rate is not None and cert.refusal_rate >= 0.0
    assert cert.autorate + cert.refusal_rate <= 1.0 + 1e-9
    assert cert.mean_set_size > 0.0


def test_an_uninformative_task_with_real_errors_is_refused_not_certified():
    # Uniform mass AND a wrong argmax half the time: there is nothing to automate and
    # the conditional budget cannot be met. This is the case the old generator could
    # not express, because its argmax was never wrong.
    cert = certify_choice(_records(1200, sharpness=1.0, error_rate=0.5),
                          alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False, cert.summary()
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    assert cert.autorate is None and cert.qhat is None
    # R-21: a refusal carries the observation that caused it, not just a label.
    closest = cert.meta["closest_attempt"]
    assert closest is not None and closest["errors"] > 0
    assert closest["conditional_error_bound"] > 0.05
    assert "exceeds the budget" in cert.summary(), cert.summary()
    curve = cert.meta["diagnostic_curve"]
    assert curve and "evidence only" in cert.meta["diagnostic_note"]
    # R-21's name is now honest: closest_attempt is the point whose bound comes CLOSEST
    # to beta. It used to be the point with the HIGHEST automation rate, which on a
    # failing curve is the one furthest from the budget.
    assert cert.meta["closest_attempt"]["conditional_error_bound"] == min(
        c["conditional_error_bound"] for c in curve), cert.meta["closest_attempt"]


def test_error_mass_alone_degrades_the_automation_rate():
    """Same shapes, same seed, only the wrongness differs."""
    clean = certify_choice(_records(1600, sharpness=5.0, error_rate=0.0),
                           alpha=0.05, beta=0.05, seed=13)
    noisy = certify_choice(_records(1600, sharpness=5.0, error_rate=0.35),
                           alpha=0.05, beta=0.05, seed=13)
    assert clean.feasible is True
    assert (noisy.autorate or 0.0) < clean.autorate, (clean.summary(), noisy.summary())
    assert noisy.meta["errors_among_automated"] > 0 or not noisy.feasible


def test_too_few_labelled_cases_is_its_own_refusal_reason():
    cert = certify_choice(_records(12), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False
    assert cert.reason == Reason.N_BELOW_MIN.value
    assert cert.n_cal + cert.n_eval == 12


def test_unlabelled_records_are_never_used_for_calibration_but_are_counted():
    labelled = _records(400, sharpness=8.0, seed=3)
    unlabelled = _records(400, sharpness=8.0, seed=2, unlabelled=400)
    cert = certify_choice(labelled + unlabelled, alpha=0.05, beta=0.05, seed=7)
    assert cert.n_cal + cert.n_eval == 400
    assert cert.meta["skipped_no_gold"] == 400
    assert cert.meta["skipped_wrong_qtype"] == 0


def test_other_question_types_are_not_silently_certified_as_choice():
    from autorate.records import Record as R

    noul = [R(id=str(i), qtype="noul", backend="synthetic", repeat=0,
              options=("false", "true"), probs=(0.2, 0.8), gold="true",
              predicted="true", slices={}, scores={}, seed=1, u=0.5, meta={})
            for i in range(300)]
    cert = certify_choice(noul, alpha=0.05, beta=0.05, seed=5)
    assert cert.feasible is False
    assert cert.reason == Reason.NO_GOLD_LABELS.value or cert.meta["skipped_wrong_qtype"] == 300
    assert cert.meta["skipped_wrong_qtype"] == 300


def test_envelope_is_never_empty_even_on_success():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert any("exchangeability" in s for s in cert.envelope)
    assert any("group" in s for s in cert.envelope)
    assert any("archived" in s or "shift" in s for s in cert.envelope)


def test_a_sharper_task_automates_more_at_the_same_budget():
    easy = certify_choice(_records(1200, sharpness=9.0, error_rate=0.01),
                          alpha=0.05, beta=0.05, seed=21)
    hard = certify_choice(_records(1200, sharpness=2.0, error_rate=0.35),
                          alpha=0.05, beta=0.05, seed=21)
    assert easy.feasible is True
    assert easy.autorate > (hard.autorate or 0.0)


def test_tighter_error_budgets_never_increase_the_automation_rate():
    recs = _records(1600, sharpness=4.0, error_rate=0.15)
    loose = certify_choice(recs, alpha=0.10, beta=0.10, seed=11)
    mid = certify_choice(recs, alpha=0.05, beta=0.05, seed=11)
    tight = certify_choice(recs, alpha=0.01, beta=0.01, seed=11)
    rates = [c.autorate if c.feasible else 0.0 for c in (loose, mid, tight)]
    assert rates == sorted(rates, reverse=True), rates


def test_alpha_moves_the_operating_point_instead_of_labeling_it():
    """R-28. The first version stored and printed `alpha` while the sweep picked its set
    size from a 0.01..0.29 grid on the evaluation half, so four different requested
    alphas produced byte-identical certificates and a summary reading "at alpha=0.050"
    under a 0.89-coverage operating point."""
    recs = _records(1600, sharpness=4.0)
    certs = {a: certify_choice(recs, alpha=a, beta=0.05, seed=7) for a in (0.01, 0.05, 0.20)}
    for a, c in certs.items():
        assert c.feasible is True, (a, c.summary())
    assert certs[0.01].qhat > certs[0.05].qhat > certs[0.20].qhat, [c.qhat for c in certs.values()]
    assert "coverage 0.950 (alpha=0.050)" in certs[0.05].summary(), certs[0.05].summary()
    rates = [c.autorate for c in certs.values()]
    assert len(set(rates)) == 3, rates


def test_the_certified_threshold_is_the_one_the_summary_quotes():
    # No selection on the test half: qhat must be the alpha-quantile of the calibration
    # scores, recomputed here from the calibration half the certificate names.
    from autorate.certify_choice import split_cal
    from autorate.conformal import split_quantile

    recs = _records(1200, sharpness=6.0, seed=3)
    cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is True, cert.summary()
    cal, ev, _ = split_cal(recs, 7)
    assert {r.id for r in ev} == set(cert.meta["eval_ids"])
    scores = [aps_score(r.probs, r.gold_index, r.u) for r in cal]
    q, vacuous = split_quantile(scores, 0.05)
    assert vacuous is False and q == cert.qhat


def test_a_requested_coverage_level_outside_the_unit_interval_is_a_usage_error():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="must be in"):
            certify_choice(_records(200), alpha=bad, beta=0.05, seed=7)
        with pytest.raises(ValueError, match="must be in"):
            certify_choice(_records(200), alpha=0.05, beta=bad, seed=7)


def test_the_same_records_produce_the_same_certificate_twice():
    recs = _records(800, sharpness=6.0, seed=3)
    a = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    b = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    assert a.autorate == b.autorate
    assert a.conditional_error_bound == b.conditional_error_bound
    assert a.qhat == b.qhat and a.refusal_rate == b.refusal_rate


def test_method_is_a_declared_choice_and_lac_certifies_a_different_frontier():
    recs = _records(1200, sharpness=6.0, seed=5)
    aps = certify_choice(recs, alpha=0.05, beta=0.05, seed=9, method="aps")
    lac = certify_choice(recs, alpha=0.05, beta=0.05, seed=9, method="lac")
    assert aps.method == "aps" and lac.method == "lac"
    assert aps.qhat != lac.qhat

# --- R-121: the precision a published bound is stored at --------------------------
#
# The reproduction gate re-derives every published number and compares it with `==`. A
# Clopper-Pearson bound is the output of 80 `math.log`/`math.exp` comparisons, and the last
# bits of those are not the same on Apple libm and glibc, so at `351845e` the runner
# recomputed `cert laya.meta` as 0.7884344428029711 where the artefact said
# 0.7884344428029715: gate red on Linux, green on the Mac that wrote the file. The fix is
# that the certifier publishes a canonical number. The pair at the end of this file is what
# keeps that honest -- one unit in the last place must not move the gate, and a move in the
# tenth decimal must.


def _published_bounds(node):
    """Every value stored under a named bound key in a certificate dict, however nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CANONICALISED_BOUND_FIELDS:
                if value is not None:
                    yield value
            else:
                yield from _published_bounds(value)
    elif isinstance(node, list):
        for item in node:
            yield from _published_bounds(item)


def test_the_committed_artefacts_store_only_reproducible_bounds():
    """A committed bound must be its own canonical value, or another machine cannot rerun it.

    This is the artefact-side half of the fix. The two files are the published surface, and
    every bound on them -- headline, `at_requested_alpha`, `closest_attempt` and all 28 curve
    points -- went through `certify`, so if anything still wrote a raw double this is where it
    shows, and it shows in the lane that has no corpus and no excuse.
    """
    total = 0
    for rel in CERT_FILES:
        doc = json.loads((REPO / rel).read_text())
        bounds = list(_published_bounds(doc))
        assert bounds, "%s publishes no bound at all" % rel
        for value in bounds:
            assert canonicalise_bound(value) == value, (rel, repr(value))
            assert len(repr(value).split(".")[-1]) <= 12, (rel, repr(value))
        total += len(bounds)
    assert total >= 28, "the diagnostic curve is no longer on the published surface"


def test_the_canonicalisation_is_by_field_name_and_left_the_other_fields_alone():
    """The sweep is `CANONICALISED_BOUND_FIELDS`, not "does it look like a float".

    Rounding the rest of a curve row buys nothing -- a quotient of two integers is correctly
    rounded by every IEEE 754 implementation, which is why 25 of the 28 points matched on the
    runner -- and it would cost the gate its ability to see a changed automation rate. So the
    raw doubles must still be on the published surface.
    """
    doc = json.loads((REPO / "data" / "cert_laya.json").read_text())
    rows = doc["meta"]["diagnostic_curve"]
    assert rows, "the refusal no longer publishes its sweep"
    keys = {key for row in rows for key in row}
    assert "conditional_error_bound" in keys
    non_bounds = [(key, value) for row in rows for key, value in row.items()
                  if isinstance(value, float) and key not in CANONICALISED_BOUND_FIELDS]
    assert {key for key, _ in non_bounds} >= {"qhat", "observed_conditional_error"}, non_bounds
    # 7/11 and 0.9813999999999999 are the kind of double only the records can produce, and
    # they are still stored at full precision: the fix did not sweep them up.
    assert any(value != canonicalise_bound(value) for _, value in non_bounds), non_bounds


def test_the_certifier_decides_on_the_number_it_publishes():
    """Canonicalise at the source, so the budget test and the artefact read one number.

    If the raw inversion were compared against `beta` and the canonical value published
    instead, a bound within 5e-13 of the budget could certify while printing a number the
    certificate's own decision had already exceeded. Ceiling at the source makes that
    impossible in both directions at once, and the interval is left alone: with a canonical
    width, each endpoint is a correctly-rounded subtraction, reproducible bit for bit.
    """
    from autorate.certify_choice import _canonicalised
    from autorate.tails import bound_width

    cert = certify_choice(_records(1600, sharpness=8.0, error_rate=0.02, seed=13),
                          alpha=0.05, beta=0.05, seed=11)
    assert cert.feasible is True, cert.summary()
    assert cert.meta["erroneous_cases"] > 0, "a certificate with no errors bounds nothing"
    exact = clopper_pearson_upper(cert.meta["erroneous_cases"], cert.meta["automated_cases"],
                                  cert.delta)
    assert canonicalise_bound(exact) == cert.conditional_error_bound
    assert exact <= cert.conditional_error_bound < exact + 1e-12, (exact,
                                                                   cert.conditional_error_bound)
    assert cert.conditional_error_bound <= cert.beta, "a feasible certificate may not exceed " \
        "its budget: %r vs beta %r" % (cert.conditional_error_bound, cert.beta)
    assert cert.marginal_error_bound <= cert.conditional_error_bound
    half = canonicalise_bound(bound_width(cert.meta["n_eval_cases"], cert.delta)) / 2.0
    lo, hi = cert.autorate_ci
    assert lo == max(0.0, cert.autorate - half) and hi == min(1.0, cert.autorate + half)
    # the row walk and the attribute walk are one mapping, so a curve point cannot disagree
    # with the headline bound derived from the same inversion, and only the bound moved
    row = _canonicalised({"conditional_error_bound": exact, "qhat": cert.qhat, "errors": 1})
    assert row["conditional_error_bound"] == cert.conditional_error_bound
    assert row["qhat"] == cert.qhat and row["errors"] == 1


def _checkout(tmp_path):
    """A copy of the committed artefacts and renderings, so the gate can be run and tampered."""
    work = tmp_path / "checkout"
    for directory in ("data", "docs"):
        shutil.copytree(REPO / directory, work / directory)
    return work


def _run_gate(work, monkeypatch, capsys):
    """Run the shipped `verify` over that copy, in the corpus-absent lane CI can only ever see."""
    from autorate.cli import main

    monkeypatch.chdir(work)
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(work.parent / "no_corpus"))
    rc = main(["verify"])
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _bounds_drift_by(monkeypatch, move):
    """Make the choice certifier's bound producer answer like a different C library.

    `move(raw)` is what a foreign libm would have returned for the same query. The calls are
    recorded so a test can prove the patch fired rather than quietly never being reached --
    and `autorate/__init__` re-exports the FUNCTION named certify_choice, so the module
    object has to be fetched by name or the patch lands on nothing.
    """
    calls = []

    def drifting(k, n, delta):
        raw = clopper_pearson_upper(k, n, delta)
        moved = move(raw)
        calls.append((k, n, delta, raw, moved))
        return moved

    monkeypatch.setattr(importlib.import_module("autorate.certify_choice"),
                        "clopper_pearson_upper", drifting)
    return calls


def _one_ulp(raw, direction):
    """One unit in the last place up or down: the size of the drift R-121 measured.

    A bound of exactly 1.0 is left alone. The bisection brackets [0, 1], so 1.0 is the
    bracket's own endpoint and not an answer `math.exp` produced; no two libms disagree
    about it, and moving it would test a drift that cannot occur.
    """
    return raw if raw >= 1.0 else math.nextafter(raw, direction)


def test_verify_absorbs_a_last_bit_libm_drift_and_stays_green(tmp_path, monkeypatch, capsys):
    """Guard pair (a): a platform difference in the 16th decimal is not drift.

    This is the red the runner printed twice, from both ends of the number. The assertions
    after the gate runs are what keep the green honest: the patch must have fired, the move
    must really be one ULP, and every drifted bound must canonicalise back to the stored
    number -- otherwise the gate would be green because nothing reached it.
    """
    work = _checkout(tmp_path)
    rc, out, err = _run_gate(work, monkeypatch, capsys)
    assert rc == 0, (out, err)                       # the control: the copy verifies as published

    for direction in (math.inf, 0.0):
        calls = _bounds_drift_by(monkeypatch, lambda raw, d=direction: _one_ulp(raw, d))
        rc, out, err = _run_gate(work, monkeypatch, capsys)
        assert calls, "the producer was never asked for a bound"
        moved_apart = [(raw, moved) for _, _, _, raw, moved in calls if moved != raw]
        assert moved_apart, "a one-ULP drift moved nothing: the instrument is blind"
        assert all(abs(moved - raw) < 1e-15 for raw, moved in moved_apart), moved_apart[:3]
        assert all(canonicalise_bound(moved) == canonicalise_bound(raw)
                   for _, _, _, raw, moved in calls), \
            [repr((raw, moved)) for raw, moved in moved_apart
             if canonicalise_bound(moved) != canonicalise_bound(raw)][:3]
        assert rc == 0, (direction, out, err)
        assert "DRIFT" not in err, (direction, err)
        assert "re-derived" in out, (direction, out)
        monkeypatch.undo()


def test_verify_reds_when_a_bound_moves_in_the_tenth_decimal(tmp_path, monkeypatch, capsys):
    """Guard pair (b): a bound that actually MOVED must still turn the gate red, by name.

    Absorbing 4e-16 is only a fix and not a blinder if 1e-10 is still caught. The planted
    drift is the same producer, the same field and the same gate as the test above, two
    orders of magnitude further along the number, so the pair differs only in size -- which
    is exactly the claim `PUBLISHED_DECIMALS` makes.
    """
    from autorate.cli import EXIT_DRIFT

    work = _checkout(tmp_path)
    rc, out, err = _run_gate(work, monkeypatch, capsys)
    assert rc == 0, (out, err)

    published = json.loads((work / "data" / "cert_laya.json").read_text())["meta"]
    row = next(c for c in published["diagnostic_curve"] if c["conditional_error_bound"] < 1.0)
    exact = clopper_pearson_upper(row["errors"], row["automated"], 0.05)
    assert canonicalise_bound(exact) == row["conditional_error_bound"], \
        "the stored artefact is not what this machine derives"
    recomputed = canonicalise_bound(exact + 1e-10)
    assert recomputed != row["conditional_error_bound"], "the planted drift did not take"

    calls = _bounds_drift_by(monkeypatch, lambda raw: raw + 1e-10)
    rc, out, err = _run_gate(work, monkeypatch, capsys)
    assert calls and all(moved != raw for _, _, _, raw, moved in calls)
    assert rc == EXIT_DRIFT, (rc, out, err)
    assert "cert laya.meta" in err, err
    assert "cert jev.meta" in err, err
    # the drift is named by both numbers, at the digits that differ
    assert repr(row["conditional_error_bound"]) in err, err[:400]
    assert repr(recomputed) in err, err[:400]
    assert "recomputed" in err and "published" in err, err[:400]


def test_a_foreign_libm_writes_the_same_bytes_for_the_same_certificate(monkeypatch):
    """The artefact surface itself must stop being platform-dependent, not just the comparison.

    R-121's claim is that the stored number is the only number the artefact can ever hold.
    Measured directly: re-derive both committed certificates with the bound producer answering
    as the other C library did -- up to four ULPs away, which is more than the 4e-16 actually
    observed -- and the serialised certificate must be the committed bytes, character for
    character. A comparison-layer tolerance cannot make that claim; it would still let two
    machines write two different files.
    """
    from autorate.report import load_records

    records = load_records(REPO / "data" / "records_feishu.jsonl")
    for raw_offset in (1, 2, 4):
        def drifting(k, n, delta, offset=raw_offset):
            raw = clopper_pearson_upper(k, n, delta)
            if raw >= 1.0:
                return raw
            moved = raw
            for _ in range(offset):
                moved = math.nextafter(moved, math.inf)
            assert moved - raw < 1e-15, (k, n, moved, raw)
            return moved

        monkeypatch.setattr(importlib.import_module("autorate.certify_choice"),
                            "clopper_pearson_upper", drifting)
        for backend, rel in (("laya", "data/cert_laya.json"), ("jev", "data/cert_jev.json")):
            cert = certify_choice(records.get(backend, []), alpha=0.05, beta=0.05,
                                  delta=0.05, seed=7)
            committed = (REPO / rel).read_text()
            assert cert.to_json() == committed, "%s at %d ULP of drift" % (rel, raw_offset)


def test_a_stored_bound_the_producer_cannot_write_is_still_drift(tmp_path, monkeypatch, capsys):
    """...and the gate says so, because canonicalisation closed the artefact's format.

    The pre-fix value is the one to plant: 16 decimals, the digits glibc and Apple libm
    disagree over, and a number the fixed certifier can no longer emit. Absorbing it would be
    the blind gate this fix is accused of creating, so the pair is read together with
    `test_verify_absorbs_a_last_bit_libm_drift_and_stays_green`: the drift a machine can
    compute is absorbed by the grid, and a stored value outside the grid is named.
    """
    from autorate.cli import EXIT_DRIFT

    work = _checkout(tmp_path)
    cert_path = work / "data" / "cert_laya.json"
    doc = json.loads(cert_path.read_text())
    row = next(c for c in doc["meta"]["diagnostic_curve"] if c["conditional_error_bound"] < 1.0)
    published_bound = row["conditional_error_bound"]
    unreproducible = clopper_pearson_upper(row["errors"], row["automated"], doc["delta"])
    assert unreproducible != published_bound, "the plant is not a stored edit"
    assert canonicalise_bound(unreproducible) == published_bound
    row["conditional_error_bound"] = unreproducible
    cert_path.write_text(json.dumps(doc, sort_keys=True))
    assert row["conditional_error_bound"] == unreproducible, "tampering did not land"

    rc, out, err = _run_gate(work, monkeypatch, capsys)
    assert rc == EXIT_DRIFT, (rc, out, err)
    assert "cert laya.meta" in err, err
    assert "cert jev" not in err, err              # only the field that was moved may object
    assert "byte-identical" not in err, err        # and nothing else may be blamed for it
    # both numbers are printed, so the reader can see which digits the two disagree in
    assert repr(unreproducible) in err and repr(published_bound) in err, err[:600]
    assert "recomputed" in err and "published" in err, err[:400]
