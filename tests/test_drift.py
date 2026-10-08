"""The drift module declares an envelope; it does not buy immunity.

What this suite CANNOT detect, stated up front because several of its claims are prose claims about
guarantees and a test cannot prove a guarantee:

* it cannot show that ACI's regret expression is *true of this recursion*. It is not: the inequality
  `|mean err - alpha| <= aci_regret_bound(T, alpha, gamma)` was published as mode 2's guarantee and
  has been withdrawn because accepted sequences violate it -- the all-ceiling, adversarial-ordering,
  constant-interior and all-floor classes are each pinned by a test here, on deterministic literal
  constructions. What the suite can and does check is the FORM of the expression, the classes it
  holds on, the classes it fails on, and that the envelope text still cites the measured failure
  rather than the formula's promise. Proving the quoted theorem belongs to nobody in this repository.
* it cannot detect a certificate whose producer declared a drift variable that does not exist in
  the data. `drift.py` reads a declaration; it has no record set to check it against, so a sincere
  lie ("variable: language" over a batch with no language slice) passes `marginal_only` and lands in
  a report. The guard for that belongs to the producer that holds the records (`groups.py` refuses
  an undeclared slice key), not here.
* it cannot see whether the caller-declared densities in `weighted_quantile` are the right ones.
  Every weighted-mode refusal below is about a *missing* or *malformed* declaration; a plausible
  wrong one moves the quantile and nothing here can tell that from a regime shift, which is exactly
  why the weighted envelope names the declaration as an assumption, not a measurement. What it now
  also does NOT hide: with the declaration EXACT (calibration ~ U[0,1], target density 10*s^9), the
  estimator still under-covers, because `+1` is the exchangeable correction and not the weighted one
  -- that is a measured arm of this suite, not a prose claim.
* it could not see the CERTIFICATION UNIT until this round. `drift.py` takes vectors and holds no case
  identity, so a row vector and a case vector are the same shape to it and to every numeric assertion
  that only compares two estimators over ONE vector -- which is why the flagship
  `assert weighted == plain` control is inert under a case->row substitution by construction. Two
  tests now own that gap: `test_the_fixture_actually_holds_three_disagreeing_repeats_per_case` keeps
  the fixture honest, and `test_the_published_drift_number_is_the_case_denominated_one_not_the_row_one`
  pins both arms and names which one is published. What remains undetectable is a CALLER that feeds
  rows anyway: this module cannot see where its vector came from.

The one real artefact used is `data/cert_laya.json`, a committed certificate produced by the real
certifier over the committed archive: it is the honest subject for the flag test, because nothing in
this project has ever conditioned on a declared drift variable.
"""
import dataclasses
import inspect
import json
import math
import random
import re
from pathlib import Path

import pytest

from _records import choice_record
from autorate.case_count import case_key
from autorate.certificate import Certificate
from autorate.conformal import split_quantile
from autorate.drift import (ACI_ENVELOPE, DRIFT_DECLARATION_KEY, NOT_CERTIFIABLE_UNDER_DRIFT,
                            WEIGHTED_ENVELOPE, aci_regret_bound, aci_threshold, marginal_only,
                            weighted_level, weighted_quantile, with_drift_envelope)
from autorate.nonconformity import aps_score

REPO = Path(__file__).resolve().parents[1]
LAYA_CERT = REPO / "data" / "cert_laya.json"


def _cert(meta=None, **kwargs):
    """A refused `Certificate` carrying the caller's meta: the shape owner validates every field.

    Refused rather than feasible on purpose. A feasible certificate needs six headline numbers
    that have nothing to do with the drift flag, and fabricating them here would put a synthetic
    automation rate in a test that is about an envelope line.
    """
    base = dict(feasible=False, reason="no_gold_labels", alpha=0.05, beta=0.05, delta=0.05,
                method="aps", backend="synthetic", qhat=None, autorate=None, autorate_ci=None,
                conditional_error_bound=None, marginal_error_bound=None, mean_set_size=None,
                n_cal=0, n_eval=0,
                envelope=("exchangeability within group assumed; no group conditioning applied",),
                meta=dict(meta or {}))
    base.update(kwargs)
    return Certificate(**base)


def _committed_certificate():
    return Certificate.from_dict(json.loads(LAYA_CERT.read_text()))


def _declaration(variable="language", declared_by="producer slices", evidence="Record.slices"):
    return {"variable": variable, "declared_by": declared_by, "evidence": evidence}


def _grid(count, modulus=100):
    """A deterministic pseudo-uniform sequence of scores in [0,1): no RNG, so a red is re-runnable."""
    return [((i * 37) % modulus) / float(modulus) for i in range(count)]


REPEATS_PER_CASE = 3


def _probs_for(case, repeat):
    """A deterministic, per-case-varying ballot: no RNG, so both units are re-derivable.

    The top probability walks the case index, so the CASE vector is a real distribution and not one
    repeated value -- a degenerate case vector would make a row/case swap invisible, which is the
    failure this fixture exists to make visible.
    """
    top = 0.05 + 0.90 * (((case * 17 + repeat * 11) % 40) / 39.0)
    rest = (1.0 - top) / 3.0
    return tuple(round(value, 4) for value in (top, rest, rest, rest))


def _repeat_rows(n_cases=60):
    """`n_cases` cases x three DISAGREEING repeats, built through the shared record factory.

    `tests/_records.py:choice_record(case_id=..., repeat=...)` is the project's one owner of this shape
    (ruling R-69). The repeats disagree on purpose -- the gold label moves with the repeat, so three
    rows of one case carry three different nonconformity scores.
    """
    rows = []
    for case in range(n_cases):
        case_id = "case-%03d" % case
        for repeat in range(REPEATS_PER_CASE):
            ballot = tuple("opt%d" % index for index in range(4))
            rows.append(choice_record(id="%s-r%d" % (case_id, repeat), case_id=case_id,
                                      repeat=repeat, probs=_probs_for(case, repeat),
                                      gold=ballot[(case + repeat) % 4], u=repeat / 3.0))
    return rows


def _row_and_case_vectors(rows):
    """(row_scores, case_scores, groups): the SAME evidence on the two units, deterministically.

    The case score is the mean of its repeats' scores -- one value per independent observation, which is
    the unit `case_count.case_key` names. The row score is the record's own APS value.
    """
    row_scores = [aps_score(record.probs, list(record.options).index(record.gold), record.u)
                  for record in rows]
    groups = {}
    for record, score in zip(rows, row_scores):
        groups.setdefault(case_key(record), []).append(score)
    case_ids = sorted(groups)
    case_scores = [math.fsum(groups[key]) / len(groups[key]) for key in case_ids]
    return row_scores, case_scores, groups


def test_the_fixture_actually_holds_three_disagreeing_repeats_per_case():
    """The precondition of every unit guard below, asserted rather than assumed.

    A fixture whose repeats AGREED would make the row and case vectors collapse towards each other and
    the unit guards would be inert in exactly the way the flagship reproduction control already is. This
    test reddens first if the fixture degenerates, so the guards below never have to be re-proved by
    hand.
    """
    rows = _repeat_rows()
    row_scores, case_scores, groups = _row_and_case_vectors(rows)
    assert len(rows) == REPEATS_PER_CASE * len(groups), (len(rows), len(groups))
    assert len(groups) == 60, len(groups)
    assert all(len(members) == REPEATS_PER_CASE for members in groups.values())
    for key, members in groups.items():
        assert len(set(members)) == REPEATS_PER_CASE, (key, members)
    assert len(set(row_scores)) > 1 and len(set(case_scores)) > 1, (
        "a constant vector on either unit makes the swap invisible")
    assert case_scores != row_scores, "the two units produced the same vector"


def test_the_published_drift_number_is_the_case_denominated_one_not_the_row_one():
    """MAJOR-B1's missing shape: certification is by CASE, and both arms are measured here.

    The precedent is `groups.py:12-17`, which publishes BOTH `cases` and `records` because they are not
    interchangeable. On this evidence (60 cases / 180 rows, three disagreeing repeats each):

      * the weighted threshold is 0.780900 on the case vector and 0.950100 on the row vector, so the
        published number moves by 0.169200 purely from the unit;
      * `aci_regret_bound` is 0.361111 on 60 cases and 0.138889 on 180 rows -- feeding rows does not
        restate the same bound, it makes it 0.384615 of its size, i.e. it UNDERSTATES the price of a
        short sequence, which is the anti-conservative direction.

    The reproduction control cannot see this, and that is asserted here too: `weighted_quantile` agrees
    with `split_quantile` on BOTH vectors, so `assert weighted == plain` survives any unit swap -- the
    old flagship guard was inert by construction, not by accident.
    """
    rows = _repeat_rows()
    row_scores, case_scores, _groups = _row_and_case_vectors(rows)
    alpha = 0.05
    q_case, _ = weighted_quantile(case_scores, [1.0] * len(case_scores), alpha)
    q_row, _ = weighted_quantile(row_scores, [1.0] * len(row_scores), alpha)
    assert len(case_scores) == 60 and len(row_scores) == 180, (len(case_scores), len(row_scores))
    assert q_case == pytest.approx(0.780900, abs=1e-6), q_case
    assert q_row == pytest.approx(0.950100, abs=1e-6), q_row
    assert q_case != q_row, (q_case, q_row)
    assert abs(q_row - q_case) > 0.1, (q_row, q_case)
    bound_case = aci_regret_bound(len(case_scores), alpha, alpha)
    bound_row = aci_regret_bound(len(row_scores), alpha, alpha)
    assert bound_case == pytest.approx(0.361111, abs=1e-6), bound_case
    assert bound_row == pytest.approx(0.138889, abs=1e-6), bound_row
    assert bound_row < bound_case, "rows must not read as a longer, cheaper sequence"
    assert bound_row / bound_case == pytest.approx(0.384615, abs=1e-4)
    # and the flagship control is unit-blind: it agrees on both arms, which is why it never reddened
    assert weighted_quantile(row_scores, [1.0] * len(row_scores), alpha) == split_quantile(row_scores,
                                                                                           alpha)
    assert weighted_quantile(case_scores, [1.0] * len(case_scores), alpha) == split_quantile(
        case_scores, alpha)


def test_every_documented_error_path_lands_on_a_documented_exit_code():
    """The reviewer's unfinished Axis D, executed: each refusal's class IS its exit code.

    `cli.main()` maps `ReaderContractError` -> 2, `ArithmeticError` -> 4, `(OSError, ValueError)` -> 2
    and has NO catch-all, so a `TypeError`, `AttributeError`, `KeyError`, `IndexError`,
    `ZeroDivisionError` or `OverflowError` escaping this module reaches the operator as rc 1 -- a
    traceback, not a refusal, and outside the contract the module docstring publishes.

    The table is the population the brief named (empty population, all-equal weights, zero weights, an
    undeclared key, non-finite input, a single calibration point) plus the shapes a caller can actually
    hand a vector-taking module: a non-iterable score vector, a declared sum that overflows the
    accumulator, a candidate threshold that is not a number, a one-shot iterable declaration, and an
    object that has `meta` but no `envelope`. Every `rc` below is what cli's mapping produces FROM the
    class raised, so a future escape is a red here rather than a surprise in the field.
    """
    good = [0.1, 0.5, 0.9]
    cases = [
        # (label, callable, args, expected rc: 0 = answers, 2 = usage, 4 = arithmetic)
        ("empty population, empty weights", weighted_quantile, ([], [], 0.1), 2),
        ("empty population, one weight given", weighted_quantile, ([], [1.0], 0.1), 2),
        ("all-equal weights", weighted_quantile, (good, [2.0, 2.0, 2.0], 0.05), 0),
        ("all-zero weights", weighted_quantile, (good, [0.0, 0.0, 0.0], 0.05), 2),
        ("non-finite score (nan)", weighted_quantile, ([0.1, float("nan")], [1.0, 1.0], 0.05), 2),
        ("non-finite density (inf)", weighted_quantile, (good, [float("inf"), 1.0, 1.0], 0.05), 2),
        ("declared densities that overflow the accumulator", weighted_quantile,
         ([0.5, 0.6], [1e308, 1e308], 0.05), 2),
        ("single calibration point", weighted_quantile, ([0.5], [1.0], 0.05), 0),
        ("single point carrying the mass", weighted_quantile, ([0.5], [100.0], 0.05), 0),
        ("scores is not a sequence", weighted_quantile, (5, [1.0], 0.05), 2),
        ("scores is a bare string", weighted_quantile, ("0.5", [1.0], 0.05), 2),
        ("weights is not a sequence", weighted_quantile, (good, 7, 0.05), 2),
        ("one-shot iterables, non-vacuous answer", weighted_quantile,
         (iter(good), iter([10.0, 10.0, 10.0]), 0.2), 0),
        ("candidate threshold is None", weighted_level, (good, [1.0, 1.0, 1.0], None), 2),
        ("candidate threshold is a mapping", weighted_level, (good, [1.0, 1.0, 1.0], {}), 2),
        ("aci: empty sequence", aci_threshold, ([], 0.05, 0.05), 2),
        ("aci: scores is not a sequence", aci_threshold, (5, 0.05, 0.05), 2),
        ("aci: single round", aci_threshold, ([0.5], 0.05, 0.05), 0),
        ("aci: score above the ceiling", aci_threshold, ([1.4], 0.05, 0.05), 2),
        ("aci: alpha at the divergence", aci_threshold, ([0.5], 0.5, 0.05), 2),
        ("bound: rounds zero", aci_regret_bound, (0, 0.05, 0.05), 2),
        ("bound: rounds fractional", aci_regret_bound, (2.5, 0.05, 0.05), 2),
        ("bound: rounds infinite", aci_regret_bound, (float("inf"), 0.05, 0.05), 2),
        ("bound: rounds is a bool", aci_regret_bound, (True, 0.05, 0.05), 2),
        ("bound: alpha at the pole", aci_regret_bound, (100, 0.5, 0.05), 2),
        ("bound: gamma zero", aci_regret_bound, (100, 0.05, 0.0), 2),
        ("flag: undeclared drift key is absence, not a refusal", marginal_only,
         (_cert(meta={}),), 0),
        ("flag: malformed declaration", marginal_only, (_cert(meta={"drift_declaration": 7}),), 2),
        ("flag: half-filled declaration", marginal_only,
         (_cert(meta={"drift_declaration": {"variable": "language"}}),), 2),
        ("flag: certificate object without a meta mapping", marginal_only, (object(),), 2),
        ("envelope: object with meta but no envelope slot", with_drift_envelope, (_NoEnvelope(),), 2),
    ]
    for label, fn, args, want in cases:
        kind = _rc_of(fn, *args)
        assert kind == want, "%s: raised a class cli maps to rc %r, expected rc %r" % (label, kind, want)
    # and the one site that is deliberately NOT a usage refusal stays rc 4. The helper already maps
    # the class to a code, so it is called directly -- wrapping it in `_rc_of` again would read the
    # returned integer as a clean answer and report rc 0, which is how this line first misled me.
    assert _broken_cross_check() == 4, "the ArithmeticError site lost its exit code"


def _rc_of(fn, *args):
    """The exit code `cli.main()` would print for one call: 0, 2, 4, or 1 for anything else."""
    try:
        result = fn(*args)
        if hasattr(result, "__next__"):
            next(result)  # a generator refuses lazily; this module promises it does not
        return 0
    except (OSError, ValueError):
        return 2
    except ArithmeticError:
        return 4
    except BaseException:
        return 1


class _NoEnvelope(object):
    """The shape `marginal_only` accepts and `with_drift_envelope` used to crash on."""

    meta: dict = {}


def _broken_cross_check():
    """Force the one `ArithmeticError` site and confirm it still leaves as rc 4, not rc 1.

    `weighted_quantile` compares its own scan against `weighted_level`; to reach the contradiction
    without editing production code, the predicate is temporarily replaced by one returning a crossing
    the scan cannot have produced -- which is exactly what that site exists to refuse loudly. The
    original is restored in `finally`, and the guard below asserts the class, not the message.
    """
    import autorate.drift as module

    real = module._level_from_pairs

    def lying(_pairs, _value):
        return 0.0, 0.0

    module._level_from_pairs = lying
    try:
        # a non-vacuous declaration (the crossing exists), or the check is never reached
        return _rc_of(module.weighted_quantile, [0.1, 0.5, 0.9], [10.0, 10.0, 10.0], 0.2)
    finally:
        module._level_from_pairs = real


def test_a_declaration_handed_as_one_shot_iterables_is_answered_not_refused_as_empty():
    """Axis D's misleading refusal: a valid declaration is refused as "empty score vector".

    `_checked_declaration` consumed the caller's generators to build its pairs, and the cross-check then
    re-read the SAME exhausted objects, so a non-vacuous declaration was refused with a message about an
    empty vector -- rc 2 for a refusal that should not exist, and a wrong reason for a caller who
    followed the signature. The list form and the iterator form must give the same answer.
    """
    scores, weights, alpha = [0.1, 0.5, 0.9], [10.0, 10.0, 10.0], 0.2
    as_lists = weighted_quantile(scores, weights, alpha)
    as_iterators = weighted_quantile(iter(scores), iter(weights), alpha)
    assert as_iterators == as_lists, (as_iterators, as_lists)
    assert as_lists == (0.9, False), as_lists
    # a generator is single-use by contract, so the refusal for an exhausted one must name THAT
    exhausted = iter(scores)
    list(exhausted)
    with pytest.raises(ValueError, match="empty score vector"):
        weighted_quantile(exhausted, [1.0, 1.0, 1.0], alpha)


# ----------------------------------------------------------------------------- the envelope flag

def test_a_marginal_only_certificate_carries_the_flag_and_it_is_the_committed_one():
    """The flag on real evidence: the archived laya certificate conditioned on nothing.

    `data/cert_laya.json` came out of `certify_choice` over the committed archive, so this is not a
    fixture shaped to pass. It states no drift declaration, therefore it is marginal-only, therefore
    the flag applies.
    """
    cert = _committed_certificate()
    assert DRIFT_DECLARATION_KEY not in cert.meta, sorted(cert.meta)
    assert marginal_only(cert) is True
    flagged = with_drift_envelope(cert)
    assert NOT_CERTIFIABLE_UNDER_DRIFT in flagged.envelope, flagged.envelope
    assert flagged.envelope[:len(cert.envelope)] == cert.envelope, "the flag is added, not swapped"
    assert with_drift_envelope(flagged) is flagged, "applying it twice must not double-print it"


def _numbered_certificate(**kwargs):
    """A FEASIBLE certificate that carries headline numbers, labelled as constructed.

    Needed because no committed certificate can: `certificate.py` refuses headline numbers on a
    refusal -- measured, both `data/cert_laya.json` and `data/cert_jev.json` answer
    `qhat/autorate/conditional_error_bound/marginal_error_bound/mean_set_size = None` -- so a guard
    that wants to see a number MOVED has to build the only shape that can hold one. The values obey
    the shape owner's own grammar (`marginal_error_bound <= conditional_error_bound`, the CI brackets
    the rate), so this is the owner's rules and not a fixture shaped to pass.
    """
    base = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05, method="aps",
                backend="synthetic", qhat=0.8659, autorate=0.34375, autorate_ci=(0.2201, 0.4889),
                conditional_error_bound=0.774992335230, marginal_error_bound=0.05,
                mean_set_size=2.5, n_cal=96, n_eval=96,
                envelope=("exchangeability within group assumed; no group conditioning applied",),
                meta={"automated_cases": 33, "seed": 7})
    base.update(kwargs)
    return Certificate(**base)


def test_the_flag_names_the_condition_it_withdraws_and_moves_no_number():
    """A reader has to learn from the line itself what it voids, and the certificate stays intact.

    MAJOR-C2's correction. This guard used to iterate six fields on a deliberately REFUSED certificate
    and assert they were unchanged -- while all six were already `None`, so clearing a bound was
    invisible and plant M8 left the suite green. Two subjects are used now, and the comparison is over
    EVERY field rather than a chosen six:

    * `data/cert_laya.json`, the real artefact, which does carry alpha/beta/delta/n_cal/n_eval/reason/
      method/backend/envelope and a 40-key meta mapping;
    * `_numbered_certificate()`, which carries the headline numbers a refusal is not allowed to hold,
      so a cleared or injected bound reddens here rather than passing silently.
    """
    text = NOT_CERTIFIABLE_UNDER_DRIFT.lower()
    assert "marginal" in text, NOT_CERTIFIABLE_UNDER_DRIFT
    assert "not_certifiable_under_drift" in text, (
        "the flag names itself, so a report can be grepped for it")
    subjects = ((_committed_certificate(), "committed cert_laya.json"),
                (_numbered_certificate(), "constructed feasible certificate"))
    for subject, label in subjects:
        if label.startswith("constructed"):
            for measured_field in ("qhat", "autorate", "conditional_error_bound",
                                   "marginal_error_bound", "mean_set_size", "autorate_ci"):
                assert getattr(subject, measured_field) is not None, (label, measured_field)
        fields_before = {field.name: getattr(subject, field.name)
                         for field in dataclasses.fields(subject)}
        meta_before = dict(subject.meta)
        flagged = with_drift_envelope(subject)
        # (1) the envelope is the ONLY field that may differ, and it differs by exactly the flag
        changed = sorted(field.name for field in dataclasses.fields(subject)
                         if getattr(flagged, field.name) != getattr(subject, field.name))
        assert changed == ["envelope"], (label, changed)
        assert flagged.envelope == subject.envelope + (NOT_CERTIFIABLE_UNDER_DRIFT,), (
            label, flagged.envelope)
        # (2) every measured value survives verbatim, including the fields the old list omitted
        for name, value in fields_before.items():
            if name == "envelope":
                continue  # the flag's own slot, already pinned exactly by arm (1)
            assert getattr(flagged, name) == value, (label, name)
        # (3) nobody's meta was edited in place, and the flag did not add a key to it
        assert subject.meta == meta_before, (label, "the input certificate was mutated")
        assert flagged.meta == meta_before, (label, "the flag wrote into meta")
        assert DRIFT_DECLARATION_KEY not in flagged.meta, sorted(flagged.meta)
    real = _committed_certificate()
    assert len(with_drift_envelope(real).envelope) == len(real.envelope) + 1
    assert with_drift_envelope(_cert()).envelope[-1] == NOT_CERTIFIABLE_UNDER_DRIFT


def test_a_declared_drift_variable_exempts_the_certificate_from_the_flag():
    """The exemption is reachable, which is what makes the flag a statement rather than a stamp.

    It cannot detect a false declaration (module docstring): it checks the shape of the declaration,
    and only the producer holding the records can check its truth.
    """
    cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration()})
    assert marginal_only(cert) is False
    assert with_drift_envelope(cert) is cert
    assert NOT_CERTIFIABLE_UNDER_DRIFT not in cert.envelope


def test_a_declaration_that_declares_no_conditioning_still_carries_the_flag():
    """`variable: "marginal"` is a caller buying the exemption with the word for having none."""
    for worthless in ("marginal", "MARGINAL", "none", "none declared", "unconditional"):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration(variable=worthless)})
        assert marginal_only(cert) is True, worthless
    for nameless in ("", " ", "\t"):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: _declaration(variable=nameless)})
        with pytest.raises(ValueError, match="variable"):
            marginal_only(cert)


def test_a_malformed_declaration_is_a_usage_refusal_not_a_pass_and_not_a_flag():
    """Absence means marginal-only; a garbled statement means nobody knows, and those differ.

    Reading a half-filled declaration as absence would refuse certification loudly (safe), and
    reading it as a declaration would exempt it silently (unsafe). Neither is chosen: the caller
    gets exit code 2 and a message naming the key it got wrong.
    """
    for bad in (["not", "a", "mapping"], "language", 7, {}, {"variable": "language"},
                {"variable": "", "declared_by": "x", "evidence": "y"},
                {"variable": "language", "declared_by": None, "evidence": "y"},
                {"variable": "language", "declared_by": "x", "evidence": ""},
                {"variable": None, "declared_by": "x", "evidence": "y"}):
        cert = _cert(meta={DRIFT_DECLARATION_KEY: bad})
        with pytest.raises(ValueError, match="declaration") as excinfo:
            marginal_only(cert)
        assert "drift" in str(excinfo.value).lower(), str(excinfo.value)
    # and a key holding None is the absence case, which is a flag, not a refusal
    assert marginal_only(_cert(meta={DRIFT_DECLARATION_KEY: None})) is True


def test_the_envelope_lines_must_negate_or_evidence_every_guarantee_word_they_use():
    """MAJOR-C1: the deliverable is prose, so the guard has to police CLAIMS, not vocabulary.

    The old arm forbade nine words. Plant M6b re-granted mode 2's immunity in a sentence that used
    none of them -- "the finite-sample behaviour is met from round one ... needs no further
    correction" -- and the guard passed. What replaces it is a per-line rule with the same teeth as
    the measurements: any published line that uses a guarantee word (`finite-sample`, `bound`,
    `guarantee`, `regret`) must negate it IN THAT SAME LINE. A line may not simply state that a
    guarantee is met; it has to say which measurement it stands on, and the figures it cites are the
    ones the two simulation guards in this file re-derive from the shipped code.

    The word list is kept as a second line of defence -- it is cheap and it catches the lazy re-grant
    -- but it is no longer load-bearing, and the docstring says so because that is exactly the
    difference between a guard and a ritual.
    """
    guarantee_words = ("finite-sample", "bound", "guarantee", "regret")
    negations = ("not", "no ", "never", "withdraw", "false", "violate", "only as good as",
                 "instead of to zero", "rather than to zero")
    lines = tuple(WEIGHTED_ENVELOPE) + tuple(ACI_ENVELOPE) + (NOT_CERTIFIABLE_UNDER_DRIFT,)
    policed = 0
    for line in lines:
        low = line.lower()
        if not any(word in low for word in guarantee_words):
            continue
        policed += 1
        assert any(negation in low for negation in negations), (
            "a published line uses a guarantee word without negating it in the same sentence, which "
            "is precisely how plant M6b read: %r" % line)
        if not re.search(r"\d\.\d{2,6}", low):
            assert ("not" in low or "no " in low or "never" in low), (
                "a guarantee line that cites no measured figure must be an explicit negation: %r"
                % line)
    assert policed >= 4, (
        "the guarantee lines vanished from the envelopes, so this guard is checking nothing: %d"
        % policed)
    # and a line may not affirm a guarantee in passing while negating it elsewhere: plant M6b's
    # second line kept the words "no per-round" and still said the behaviour "is met"
    affirmations = ("is met", "retained", "holds for", "is what this mode buys",
                    "no further correction", "is satisfied", "valid for", "serves as a bound")
    for line in lines:
        low = line.lower()
        for claim in affirmations:
            assert claim not in low, (line, claim)
    forbidden = ("immune", "immunity", "no drift", "drift-free", "guarantees coverage",
                 "protected against", "regardless of drift", "unaffected by", "always valid")
    for line in lines:
        low = line.lower()
        for pattern in forbidden:
            assert pattern not in low, (line, pattern)
    # the four propositions the measurements force, named rather than left to paraphrase
    weighted_joined = " ".join(WEIGHTED_ENVELOPE).lower()
    assert "exchangeable" in weighted_joined, (
        "mode 1 must name which case its +1 correction belongs to")
    assert "no finite-sample bound" in weighted_joined, WEIGHTED_ENVELOPE
    aci_joined = " ".join(ACI_ENVELOPE).lower()
    assert "withdraw" in aci_joined, ACI_ENVELOPE
    assert "necessary, not sufficient" in aci_joined, (
        "the clip condition must be stated at the strength the 400-sequence sweep supports, no more")
    assert any("declared" in line.lower() for line in WEIGHTED_ENVELOPE), WEIGHTED_ENVELOPE
    assert any("assum" in line.lower() for line in WEIGHTED_ENVELOPE), (
        "an assumption, not a measurement")
    assert any("per-round" in line.lower() for line in ACI_ENVELOPE), ACI_ENVELOPE


# ---------------------------------------------------------------------------- the weighted mode

def test_unit_weights_reproduce_split_quantile_exactly_on_every_alpha_and_size():
    """The control that keeps the generalisation honest (the brief's own words).

    Checked over sizes 1..400 on a tie-heavy and tie-free score grid at nine alphas, comparing the
    whole answer -- quantile AND vacuity flag. It cannot detect a weighted path that is wrong for
    NON-unit weights (the tilt, order and zero-weight tests below reach that), and it cannot detect
    an agreement that holds because both arms return the same ceiling for different reasons -- the
    flag comparison is what narrows that.
    """
    scores = [0.0, 0.25, 0.25, 0.5, 0.75, 0.75, 0.75, 1.0]
    for n in range(1, 401):
        s = [scores[i % len(scores)] for i in range(n)]
        for alpha in (0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99):
            plain = split_quantile(s, alpha)
            weighted = weighted_quantile(s, [1.0] * n, alpha)
            assert weighted == plain, (n, alpha, weighted, plain)


def test_the_declared_ratio_case_measures_the_deficit_the_envelope_admits():
    """BLOCKER-1's arithmetic, run in the suite so the withdrawn sentence cannot go stale.

    Calibration ~ U[0,1] (regime F0), declared ratio w(s) = 10*s^9 = f1/f0, so the declaration is
    EXACT and `E_F0[w] = 1`: the only error available to the estimator is the finite-sample one. The
    test regime's own CDF is F1(s) = s^10, so the coverage a threshold q buys is q^10 in closed form
    -- no test-point sampling, hence no second Monte-Carlo layer.

    Provenance, stated because a Monte-Carlo number without it is not evidence: seed 20261008,
    4000 trials per size, `random.Random(seed + n)` so the two sizes are different streams.
    Deterministic across libc: the assertions are bands around the mean with a Monte-Carlo tolerance,
    never an exact float.
    """
    seed, trials, alpha = 20261008, 4000, 0.05
    measured = {}
    for n in (25, 100):
        rng = random.Random(seed + n)
        misses, vacuous = [], 0
        for _ in range(trials):
            cal = [rng.random() for _ in range(n)]
            q, flag = weighted_quantile(cal, [10.0 * s ** 9 for s in cal], alpha)
            if flag:
                vacuous += 1
            misses.append(1.0 - q ** 10)  # P(score > q) under the declared target regime
        mean = math.fsum(misses) / trials
        se = math.sqrt(math.fsum((m - mean) ** 2 for m in misses) / (trials - 1) / trials)
        measured[n] = (mean, se, vacuous / float(trials))
    for n in (25, 100):
        mean, se, vac = measured[n]
        assert mean > alpha, (n, mean, se)
        assert mean > 1.5 * alpha, ("n=%d realised miscoverage %.4f is not 1.5x nominal" % (n, mean))
        assert abs(mean - (0.1411 if n == 25 else 0.0933)) < 6.0 * se + 0.01, (n, mean, se)
        if n == 25:
            assert abs(vac - 0.3058) < 0.03, vac
    # the envelope cites these figures; if the arithmetic moves, the citation goes stale and reddens
    cited = [float(t) for t in re.findall(r"\d\.\d{4}", " ".join(WEIGHTED_ENVELOPE))]
    for n in (25, 100):
        assert any(abs(c - measured[n][0]) < 6.0 * measured[n][1] + 0.005 for c in cited), (
            "WEIGHTED_ENVELOPE must carry the measured miscoverage at n=%d (%.4f), not a claim "
            "about it: %r" % (n, measured[n][0], WEIGHTED_ENVELOPE))


def test_the_density_vector_has_no_default_and_an_absent_one_is_a_refusal():
    """Mode 1 requires caller-declared densities: no uniform fallback may be reachable by omission.

    The signature check is the part a `weights=None` arm alone cannot satisfy -- a default
    parameter would let a caller take a weighted answer while declaring nothing at all.
    """
    parameters = inspect.signature(weighted_quantile).parameters
    assert parameters["weights"].default is inspect.Parameter.empty, (
        "a default density is an undeclared density")
    with pytest.raises(ValueError, match="declar"):
        weighted_quantile([0.5, 0.4], None, 0.1)
    with pytest.raises(ValueError, match="declar"):
        weighted_quantile([0.5, 0.4], (), 0.1)


def test_declared_densities_that_tilt_upward_cannot_lower_the_threshold():
    """The weighted mode must move in the direction the declaration says it will.

    Weights concentrated on the large scores raise the quantile; weights concentrated on the small
    ones lower it; the unit declaration sits between them. A sign error here is the
    anti-conservative direction, and both strict arms are what catch it.
    """
    scores = [0.1, 0.2, 0.3, 0.4, 0.9]
    alpha = 0.4
    middle, _ = weighted_quantile(scores, [1.0] * 5, alpha)
    high, _ = weighted_quantile(scores, [0.1, 0.1, 0.1, 0.1, 5.0], alpha)
    low, _ = weighted_quantile(scores, [5.0, 5.0, 5.0, 5.0, 0.1], alpha)
    assert high > middle > low, (high, middle, low)
    assert high in scores and low in scores and middle in scores, (high, low, middle)


def test_the_weighted_answer_does_not_depend_on_the_order_the_declaration_is_written_in():
    """A scan that accumulated in insertion order instead of score order would be wrong here.

    The permutation is over (score, weight) PAIRS, so the multiset is identical and every answer
    must be bit-identical -- including the flag, which is where an unordered scan shows up first.
    """
    pairs = [(0.9, 3.0), (0.1, 1.0), (0.5, 2.0), (0.5, 0.5), (0.2, 4.0)]
    reference = weighted_quantile([p[0] for p in pairs], [p[1] for p in pairs], 0.2)
    for rotated in range(len(pairs)):
        turned = pairs[rotated:] + pairs[:rotated]
        for alpha in (0.05, 0.2, 0.35, 0.5, 0.8):
            got = weighted_quantile([p[0] for p in turned], [p[1] for p in turned], alpha)
            want = weighted_quantile([p[0] for p in pairs], [p[1] for p in pairs], alpha)
            assert got == want, (turned, alpha, got, want)
    assert reference[0] in [p[0] for p in pairs], reference


def test_weighted_level_states_the_level_a_threshold_buys_and_the_selection_uses_it():
    """The cross-check's predicate is public, so its non-vacuity is testable without an edit.

    `weighted_level` returns (weight at-or-below, weight strictly-below) for a candidate threshold.
    The selected quantile must satisfy at-or-below >= target > strictly-below, and a threshold one
    step too LOW must fail the first half -- which is the shape of the anti-conservative error the
    internal cross-check refuses as `ArithmeticError`. What is tested is that the predicate
    discriminates; a wrong threshold is not a parameter this module can be handed.
    """
    scores = [0.1, 0.5, 0.9]
    weights = [1.0, 2.0, 4.0]
    alpha = 0.2
    target = (1.0 - alpha) * (sum(weights) + 1.0)
    q, vacuous = weighted_quantile(scores, weights, alpha)
    assert vacuous is False
    at_or_below, strictly_below = weighted_level(scores, weights, q)
    assert at_or_below >= target, (at_or_below, target)
    assert strictly_below < target, "q is the smallest value that reaches the level"
    too_low, _ = weighted_level(scores, weights, 0.5)
    assert too_low < target, too_low
    too_high, _ = weighted_level(scores, weights, 1.0)
    assert too_high > target, too_high


def test_weighted_quantile_refuses_inputs_that_cannot_be_a_density_declaration():
    """Every one of these is exit code 2 (usage), not a vacuous answer: the input is the problem."""
    good = [0.1, 0.5, 0.9]
    for bad_alpha in (0.0, 1.0, -0.1, 1.5, float("nan")):
        with pytest.raises(ValueError, match="alpha"):
            weighted_quantile(good, [1.0, 1.0, 1.0], bad_alpha)
    with pytest.raises(ValueError, match="empty"):
        weighted_quantile([], [], 0.1)
    with pytest.raises(ValueError, match="length"):
        weighted_quantile(good, [1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="negative"):
        weighted_quantile(good, [1.0, -2.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile(good, [float("nan"), 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile(good, [float("inf"), 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="finite"):
        weighted_quantile([0.1, float("nan"), 0.9], [1.0, 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match="sum to zero"):
        weighted_quantile(good, [0.0, 0.0, 0.0], 0.1)
    # an unbounded score would make the vacuous arm's 1.0 a threshold instead of a ceiling
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        weighted_quantile([0.1, 3.5, 0.9], [1.0, 1.0, 1.0], 0.1)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        weighted_quantile([0.1, -0.5, 0.9], [1.0, 1.0, 1.0], 0.1)


def test_a_zero_weight_sample_is_kept_and_never_selected_as_the_threshold():
    """A density of zero is a declaration with content: this score has no mass in that regime.

    It must not be dropped -- the denominator is the sum of the declared weights -- and it must not
    become the selected threshold, because a value carrying no weight cannot be where the declared
    mass crosses.
    """
    scores = [0.1, 0.2, 0.8]
    weights = [0.0, 3.0, 3.0]
    total = sum(weights)
    for alpha in (0.1, 0.4, 0.6):
        target = (1.0 - alpha) * (total + 1.0)
        q, vacuous = weighted_quantile(scores, weights, alpha)
        assert q != 0.1, "a zero-weight score was selected at alpha=%r" % alpha
        at_or_below, strictly_below = weighted_level(scores, weights, q)
        if not vacuous:
            assert at_or_below >= target > strictly_below, (q, target, at_or_below)
        assert at_or_below <= total, at_or_below


def test_the_vacuous_arm_is_the_ceiling_and_not_an_invented_value():
    """A small alpha asks for a high level and no declared sample reaches it.

    The answer is the ceiling 1.0 plus the flag, exactly as `split_quantile` does it: a weighted
    mode that answered with an interpolated value here would publish a threshold no declaration
    supports, with a clean flag beside it.
    """
    scores = [0.1, 0.2, 0.3]
    q, vacuous = weighted_quantile(scores, [1.0, 1.0, 1.0], 0.01)
    assert (q, vacuous) == (1.0, True), (q, vacuous)
    assert (q, vacuous) == split_quantile(scores, 0.01)
    assert weighted_quantile(scores, [0.5, 0.5, 0.5], 0.01) == (1.0, True)
    assert weighted_quantile(scores, [2.0, 2.0, 2.0], 0.05) == (1.0, True)


# ------------------------------------------------------------------------------- the ACI mode

def _steps(scores, alpha=0.05, gamma=0.05, **kwargs):
    return list(aci_threshold(scores, alpha, gamma, **kwargs))


def _long_run_rate(scores, alpha=0.05, gamma=0.05):
    """Average error over the whole sequence, streamed so a long T costs no memory."""
    total = 0
    count = 0
    for step in aci_threshold(scores, alpha, gamma):
        total += step.err
        count += 1
    return total / float(count)


def test_the_published_regret_inequality_fails_on_every_class_the_validator_accepts():
    """BLOCKER-2: the withdrawn sentence, falsified class by class on the shipped recursion.

    Every sequence here is DETERMINISTIC (a literal construction, no RNG), so the deviation and the
    bound are exact and re-runnable. All four are accepted by `_checked_round_scores`, which is the
    point: the fix is the withdrawal, not a refusal, because the condition that separates them from a
    tracking run is a property of the realised trajectory and no predicate on the input vector can
    see it. The two controls at the end are what stop this test from being a blanket "nothing holds":
    they are the fixture classes the old suite used, and there the inequality does hold.
    """
    alpha, gamma = 0.05, 0.05
    violations = [
        ("every score == SCORE_CEILING", [1.0] * 20000, 0.50025),
        ("adversarial period-2 0.99/0.01", ([0.99, 0.01] * 50000)[:100000], 0.16674),
        ("constant 0.99, below the ceiling", [0.99] * 20000, 0.16710),
        ("every score == the floor 0.0", [0.0] * 20000, 0.0),
    ]
    for name, scores, want in violations:
        realised = _long_run_rate(scores, alpha, gamma)
        bound = aci_regret_bound(len(scores), alpha, gamma)
        deviation = abs(realised - alpha)
        assert deviation > bound, (name, realised, deviation, bound)
        assert realised == pytest.approx(want, abs=1e-4), (name, realised, want)
    # and none of them is refused: the module accepted all four before and accepts them now
    for _name, scores, _want in violations:
        assert len(_steps(scores, alpha, gamma)) == len(scores)
    for name, scores in (("grid control", _grid(2000)), ("constant 0.95 control", [0.95] * 2000)):
        realised = _long_run_rate(scores, alpha, gamma)
        assert abs(realised - alpha) <= aci_regret_bound(len(scores), alpha, gamma), (
            name, realised)


def test_the_withdrawn_text_cannot_be_re_granted_and_cites_the_measured_rate():
    """The envelope is checked against the arithmetic, the same coupling as mode 1's guard.

    `ACI_ENVELOPE` must carry a figure for the all-ceiling long-run rate, and that figure must still
    match what the shipped recursion does: re-granting the guarantee, or letting the citation go
    stale because the recursion changed, both redden here. No word list is involved.
    """
    realised = _long_run_rate([1.0] * 20000, 0.05, 0.05)
    cited = [float(t) for t in re.findall(r"\d\.\d{3,6}", " ".join(ACI_ENVELOPE))]
    assert any(abs(c - realised) < 5e-4 for c in cited), (
        "ACI_ENVELOPE must carry the measured all-ceiling long-run rate (%.6f), not a claim about "
        "it: %r" % (realised, ACI_ENVELOPE))
    # the inequality's own form must not be published as what mode 2 buys
    joined = " ".join(ACI_ENVELOPE).lower()
    assert "withdraw" in joined, ACI_ENVELOPE
    # and the trace check the withdrawal points the caller at is real: clip is necessary for a
    # violation on the two sides of the boundary, so naming it must not become a dead sentence
    ceiling = _steps([1.0] * 200, 0.05, 0.05)
    assert any(step.lam in (0.0, 1.0) for step in ceiling), "the ceiling cycle never touched a clip"
    tracking = _steps(_grid(2000), 0.05, 0.05)
    assert not any(step.lam in (0.0, 1.0) for step in tracking), (
        "the control run now touches a clip, so the necessary-condition sentence has to be re-read")


def test_the_regret_bound_says_what_the_envelope_claims_about_alpha_and_gamma():
    """MINOR-1's correction pinned: the vacuity is a property of the (alpha, gamma) pair.

    The withdrawn text said the bound "exceeds 1.0 for the first ten rounds" without naming gamma,
    which is false for gamma >= 0.107 -- measured here on either side of the flip so the sentence in
    `aci_regret_bound` cannot quietly become a universal again.
    """
    assert aci_regret_bound(10, 0.05, 0.106) > 1.0, aci_regret_bound(10, 0.05, 0.106)
    assert aci_regret_bound(10, 0.05, 0.107) < 1.0, aci_regret_bound(10, 0.05, 0.107)
    assert aci_regret_bound(1, 0.05, 0.05) == pytest.approx(20.0278, abs=1e-3)
    assert aci_regret_bound(10, 0.05, 0.05) == pytest.approx(2.0278, abs=1e-3)
    for gamma in (0.107, 0.2, 0.5, 0.99):
        assert aci_regret_bound(10, 0.05, gamma) < 1.0, gamma
    # monotone in alpha at fixed gamma, so a larger target buys a looser statement
    alphas = (0.01, 0.05, 0.25, 0.49)
    bounds = [aci_regret_bound(100, a, 0.05) for a in alphas]
    assert bounds == sorted(bounds), (alphas, bounds)


def test_a_clip_is_necessary_for_a_violation_over_the_swept_sequence_classes():
    """The mechanism claim in `ACI_ENVELOPE`, re-run at the scale that claim cites.

    Provenance: seed 20261008, 400 sequences, T=2000, eight constructed classes (uniform, two
    Gaussians clipped to the range, two-point ties, the two degenerate constants, an alternating
    pair, the module's own grid), alpha=gamma=0.05. Streamed, never materialised. The claim is
    deliberately one-sided and stays that way: no violation WITHOUT a clip fired, while some clipped
    sequences still hold. A theorem is not available here -- this is 400 measurements of this
    recursion -- so the envelope words it as necessary-not-sufficient and this test re-derives
    exactly that.
    """
    seed, sequences, rounds, alpha, gamma = 20261008, 400, 2000, 0.05, 0.05
    rng = random.Random(seed)
    bound = aci_regret_bound(rounds, alpha, gamma)
    assert bound == pytest.approx(0.037778, abs=1e-6)
    violated_unclipped = 0
    held_clipped = 0
    violations = 0
    for k in range(sequences):
        kind = k % 8
        if kind == 0:
            scores = [rng.random() for _ in range(rounds)]
        elif kind == 1:
            scores = [min(1.0, max(0.0, rng.gauss(0.9, 0.05))) for _ in range(rounds)]
        elif kind == 2:
            scores = [min(1.0, max(0.0, rng.gauss(0.5, 0.2))) for _ in range(rounds)]
        elif kind == 3:
            scores = [rng.choice((0.0, 1.0)) for _ in range(rounds)]
        elif kind == 4:
            scores = [rng.choice((0.99, 0.01)) for _ in range(rounds)]
        elif kind == 5:
            scores = [1.0] * rounds
        elif kind == 6:
            scores = [0.0] * rounds
        else:
            scores = _grid(rounds)
        total = 0
        clipped = False
        for step in aci_threshold(scores, alpha, gamma):
            total += step.err
            if step.lam in (0.0, 1.0):
                clipped = True
        violated = abs(total / float(rounds) - alpha) > bound
        if violated:
            violations += 1
        if violated and not clipped:
            violated_unclipped += 1
        if clipped and not violated:
            held_clipped += 1
    assert violated_unclipped == 0, (
        "%d sequences violated with no round sitting on a clip: the mechanism sentence in "
        "ACI_ENVELOPE is now wrong, and so is the withdrawal's explanation of it"
        % violated_unclipped)
    assert violations > 0, "the sweep found no violation at all: the classes stopped discriminating"
    assert held_clipped > 0, "every clipped sequence violated: 'necessary, not sufficient' is wrong"
    assert any("400" in line and "0 of 400" in line for line in ACI_ENVELOPE), ACI_ENVELOPE


def test_aci_yields_the_threshold_it_used_before_it_saw_the_score():
    """The ordering is the guarantee's whole content: a threshold chosen after the score is not one.

    Round t's `lam` is round t-1's updated value, and the first round's is the declared start --
    recorded, never presented as informative. A raise-on-error step is what keeps the recursion
    stable, so the sign is asserted too: an error at round 1 must push the next threshold UP.
    """
    scores = [0.9, 0.1, 0.9, 0.9]
    steps = _steps(scores, alpha=0.05, gamma=0.1, lam0=0.5)
    assert [s.t for s in steps] == [1, 2, 3, 4], steps
    assert steps[0].lam == 0.5, "the declared start is used, not a fitted one"
    assert steps[0].score == 0.9 and steps[0].err == 1
    assert steps[1].lam == pytest.approx(0.595), steps[1].lam
    assert steps[1].err == 0
    assert steps[2].lam == pytest.approx(0.59), steps[2].lam
    assert all(0.0 <= s.lam <= 1.0 for s in steps), steps


def test_the_iterator_is_an_iterator_and_a_prefix_is_the_same_answer_as_the_full_run():
    """The API promise is an iterator, and partial consumption must not change any answer.

    What this CANNOT detect: that the score list itself is held in memory (it must be, the input is
    a sequence), and that a list-returning implementation would satisfy the prefix arm -- which is
    why the iterator-protocol arm is asserted separately.
    """
    scores = [0.5] * 10000
    it = aci_threshold(scores, 0.05, 0.05)
    assert iter(it) is it, "not an iterator: %r" % type(it)
    first_three = [next(it) for _ in range(3)]
    assert [s.t for s in first_three] == [1, 2, 3]
    full = _steps(scores)
    assert [(s.t, s.lam, s.err) for s in first_three] == [(s.t, s.lam, s.err) for s in full[:3]]


def test_the_regret_bound_is_a_regret_bound_and_says_nothing_about_one_round():
    """The brief's central requirement: assert the regret form, and explicitly NOT finite-sample.

    Three properties, each of which an implementation dressed up as finite-sample would fail:
      at T=1 and T=10 the bound exceeds 1.0, so it permits ANY realised error rate;
      with gamma fixed it tends to gamma / (2(1-2 alpha)) as T grows and never to zero;
      it is not monotone in gamma -- one term wants a large step and the other a small one -- which
        is what a regret trade-off looks like and never what a confidence width looks like.
    The measured crossing this module has to state honestly: at alpha=0.05 and gamma=0.05 the
    bound first comes under 0.10 at round 277. A drift mode that said anything earlier would be
    saying more than its analysis does.
    """
    alpha, gamma = 0.05, 0.05
    assert aci_regret_bound(1, alpha, gamma) > 1.0, "a one-round guarantee would be a lie"
    assert aci_regret_bound(10, alpha, gamma) > 1.0
    assert aci_regret_bound(100, alpha, gamma) > 0.10
    assert aci_regret_bound(277, alpha, gamma) <= 0.10
    tail = gamma / (2.0 * (1.0 - 2.0 * alpha))
    assert aci_regret_bound(10 ** 9, alpha, gamma) == pytest.approx(tail, rel=1e-6)
    assert aci_regret_bound(10 ** 9, alpha, gamma) > 0.0
    large_t = [aci_regret_bound(t, alpha, gamma) for t in (100, 1000, 10000)]
    assert large_t == sorted(large_t, reverse=True), large_t
    sweeping = [aci_regret_bound(5000, alpha, g) for g in
                (0.005, 0.01, 0.02, 0.04, 0.08, 0.2, 0.5)]
    assert sweeping[0] > min(sweeping) and sweeping[-1] > min(sweeping), sweeping
    assert math.isfinite(aci_regret_bound(277, alpha, gamma))


def test_aci_regret_bound_refuses_a_request_outside_the_range_it_was_stated_for():
    """alpha >= 0.5 makes the second term infinite: a formula's domain is its owner's business.

    `tails.bound_width` refuses n <= 1 the same way, and an unguarded alpha=0.5 here would return
    a division-by-zero `ZeroDivisionError`, which has no exit code in this project.
    """
    # the explosion the refusal exists to prevent, shown rather than asserted about python
    assert aci_regret_bound(100, 0.49, 0.05) > 1.0, aci_regret_bound(100, 0.49, 0.05)
    assert aci_regret_bound(100, 0.4999, 0.05) > 100.0, aci_regret_bound(100, 0.4999, 0.05)
    for bad_alpha in (0.5, 0.75, 1.0, 0.0, -0.2):
        with pytest.raises(ValueError, match="alpha"):
            aci_regret_bound(100, bad_alpha, 0.05)
    with pytest.raises(ValueError, match="rounds"):
        aci_regret_bound(0, 0.05, 0.05)
    with pytest.raises(ValueError, match="rounds"):
        aci_regret_bound(-1, 0.05, 0.05)
    for bad_gamma in (0.0, 1.0, 1.5, -0.5):
        with pytest.raises(ValueError, match="gamma"):
            aci_regret_bound(100, 0.05, bad_gamma)


def test_aci_tracks_the_target_rate_on_stationary_and_shifted_scores_within_the_bound():
    """Numeric agreement with the stated form, including a sequence that shifts mid-run.

    This is evidence for the implementation, not for the theorem (module docstring). It also shows
    what the mode trades: on 12 scores at alpha=0.05 `split_quantile` answers vacuously, while ACI
    returns a working threshold -- a threshold with no finite-sample statement attached to it.
    """
    stationary = _grid(2000)
    shifted = _grid(1000) + [((i * 37) % 50 + 50) / 100.0 for i in range(1000)]
    constant = [0.95] * 2000
    for name, scores in (("stationary", stationary), ("shifted", shifted), ("constant", constant)):
        steps = _steps(scores, alpha=0.05, gamma=0.05)
        realised = sum(s.err for s in steps) / len(steps)
        limit = aci_regret_bound(len(steps), 0.05, 0.05)
        assert abs(realised - 0.05) <= limit, (name, realised, limit)
    small = _steps(_grid(4, modulus=10) * 3, alpha=0.05, gamma=0.05)
    assert len(small) == 12
    q_hat, vacuous = split_quantile([s.score for s in small], 0.05)
    assert vacuous is True and q_hat == 1.0, (q_hat, vacuous)
    assert any(0.0 < s.lam < 1.0 for s in small), "ACI answered with a working threshold"


def test_aci_under_a_shift_makes_no_per_round_promise():
    """The failure mode this test exists to forbid: reading a mid-adaptation threshold as a bound.

    Right after the shift the realised window error rate is far above alpha -- drift doing what
    drift does -- and no finite-sample statement is available to soften it. Measured here: 6/10 of
    the first ten rounds after the shift are errors at gamma=0.005, and the window rate stays above
    0.3. If a future edit made those look bounded, this test reddens and the envelope line has to
    be re-read, which is the intended behaviour.
    """
    before = _grid(500)
    after = [(90 + (i * 7) % 10) / 100.0 for i in range(50)]
    steps = _steps(before + after, alpha=0.05, gamma=0.005)
    window = steps[500:550]
    assert sum(s.err for s in window[:10]) / 10.0 == 0.6, [s.err for s in window[:10]]
    assert sum(s.err for s in window) / len(window) > 0.3
    carried = min(1.0, max(0.0, steps[499].lam + 0.005 * (steps[499].err - 0.05)))
    assert window[0].lam == pytest.approx(carried), (
        "the threshold carries over the shift instead of restarting at a fitted value")
    assert any("per-round" in l.lower() for l in ACI_ENVELOPE), ACI_ENVELOPE


def test_aci_refuses_inputs_that_would_silently_widen_its_stated_range():
    """Scores outside [0,1] leave the bounded range the analysis is stated on; an empty sequence has
    no rounds to bound; and a declared start outside [0,1] would break the clipping the proof uses."""
    with pytest.raises(ValueError, match="empty"):
        _steps([])
    for bad_alpha in (0.0, 0.5, 0.9):
        with pytest.raises(ValueError, match="alpha"):
            _steps([0.1, 0.2], alpha=bad_alpha, gamma=0.05)
    for bad_gamma in (0.0, 1.0, 2.0):
        with pytest.raises(ValueError, match="gamma"):
            _steps([0.1, 0.2], alpha=0.05, gamma=bad_gamma)
    with pytest.raises(ValueError, match="0,1"):
        _steps([0.1, 1.4], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="0,1"):
        _steps([0.1, -0.2], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="finite"):
        _steps([0.1, float("nan")], alpha=0.05, gamma=0.05)
    with pytest.raises(ValueError, match="lam0"):
        _steps([0.1, 0.2], lam0=1.5)
    with pytest.raises(ValueError, match="lam0"):
        _steps([0.1, 0.2], lam0=-0.5)


def test_aci_threshold_is_not_a_renamed_split_quantile():
    """Two different guarantees, so a caller cannot mix them up by accident.

    The ACI step carries no vacuity flag and no finite-sample correction: at alpha=0.95 over three
    scores `split_quantile` selects the LOWEST order statistic while ACI sits at the declared start
    and reports each round's error. Asserting the two disagree is what stops a later edit from
    "unifying" them, which would smuggle the finite-sample claim back in.
    """
    scores = [0.2, 0.5, 0.9]
    plain = split_quantile(scores, 0.95)
    steps = _steps(scores, alpha=0.05, gamma=0.05, lam0=0.5)
    assert plain == (0.2, False), plain
    assert steps[0].lam == 0.5
    assert steps[0].err == 0
    assert not hasattr(steps[0], "vacuous"), "ACI has no finite-sample vacuity to report"


def test_the_weighted_and_aci_modes_are_stated_as_two_modes_and_never_combined():
    """Mode 1 assumes a declared density ratio; mode 2 assumes nothing and pays regret.

    A single call that did both would be an unnameable guarantee, so neither function accepts the
    other's control: `weighted_quantile` has no gamma and `aci_threshold` has no weights.
    """
    w_params = set(inspect.signature(weighted_quantile).parameters)
    a_params = set(inspect.signature(aci_threshold).parameters)
    assert w_params == {"scores", "weights", "alpha"}, w_params
    assert a_params == {"scores", "alpha", "gamma", "lam0"}, a_params
    assert math.isfinite(aci_regret_bound(1000, 0.05, 0.05))
