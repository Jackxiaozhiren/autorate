"""Task #97: G1's feasibility ceiling, published as an arm `verify` re-derives.

Spec §2's G1 asks for ">=3 decision tasks certified at `autorate(alpha = 0.05)`". This tree publishes five
scored decision tasks and certifies none of them, and `data/resplit_200.json` shows 0 of 200 splits
certifying for all five. The stronger statement -- that **no automated size certifies on this evidence base
at this budget** -- existed only in an untracked scratch probe, which by this project's own ruling
(`docs/G5.md` exists because of exactly that ruling) is not evidence. This file is what turns the ceiling
into a committed artefact with a producer, a document rendered from its bytes, and a `verify` arm that
re-derives every figure in it from `tails.py` and the published certificates.

Three rules the rows below enforce, in this repository's currency:

*The arithmetic has one owner and it is not this file.* `autorate.tails` owns the bounds
(`clopper_pearson_upper`, `bound_width`, `n_feasible`) and `autorate.certificate.canonicalise_bound` owns the
precision a published bound is stored at -- which is the mechanism the existing arms use to compare
`0.064239163974` against a value that computes as `...973`. Nothing here reimplements a bound.

*The unit is named at every column.* The certificate's unit is the case (R-44), while `meta.closest_attempt`
carries record counts: 628 automated of 1,487 records for `en`, 96 of 96 records but 32 of 32 cases for
`jev`. Each row therefore publishes both denominators, each ceiling is computed over its own unit's
automated size, and no column compares a `k_max` from one unit against an error count from the other.

*A missing input is published as `null` with the input named.* The oracle ceiling needs the error count of
the whole evaluated pool; the artefacts publish only the errors *inside* the automated set. Where the
automated set is not the pool, the column is `null` plus the field that would have supplied it -- the same
shape `data/resplit_200.json` uses for a rate over a zero denominator, and never an imputed `0.000`.
"""
from pathlib import Path

import pytest

from autorate import report
from autorate.certificate import canonicalise_bound
from autorate.cli import load_protocol
from autorate.tails import bound_width, clopper_pearson_upper, n_feasible

REPO = Path(report.__file__).resolve().parents[2]


@pytest.fixture
def rubric():
    """The freeze's own rubric object -- the way the other arms get alpha, beta, delta, method, seed."""
    return load_protocol(REPO / "protocol.json").rubric


def _reference_by_n(doc, n):
    return {row["n"]: row for row in doc["reference"]}[n]


def _row_by_task(doc, task):
    rows = [row for row in doc["rows"] if row["task"] == task]
    assert len(rows) == 1, (task, [r["task"] for r in doc["rows"]])
    return rows[0]


def test_the_arm_publishes_one_row_per_published_decision_task_and_one_for_typed_decisions(rubric):
    """Five certificate rows, taken from the tables -- plus the sixth corpus, which has no certificate."""
    from autorate.report import CERTS, MASSIVE_CERTIFICATES

    doc = report.build_g1_feasibility(rubric)
    expected_tasks = sorted({**CERTS, **MASSIVE_CERTIFICATES}) + ["typed_decisions"]
    assert sorted(row["task"] for row in doc["rows"]) == expected_tasks, doc["rows"]
    for task, cert_path in sorted(CERTS.items()):
        row = _row_by_task(doc, task)
        assert row["artefact"] == cert_path, row
        assert row["table"] == "report.CERTS", row
    for label, (_records, cert_path) in sorted(MASSIVE_CERTIFICATES.items()):
        row = _row_by_task(doc, label)
        assert row["artefact"] == cert_path, row
        assert row["table"] == "report.MASSIVE_CERTIFICATES", row


def test_k_max_is_the_largest_error_count_whose_canonicalised_upper_clears_alpha(rubric):
    """`k_max(n)` is defined by the gate's own pass condition, on the gate's own canonicalised bound.

    `certify_choice` tests `cond_hi > beta` with `cond_hi = canonicalise_bound(clopper_pearson_upper(...))`,
    so the ceiling is stated in the same comparison the committed refusals were produced by -- not against a
    raw double whose last bits are a platform fact (`tails.py` documents the drift, ledger R-121).
    """
    alpha, delta = rubric["alpha"], rubric["delta"]
    doc = report.build_g1_feasibility(rubric)
    for row in doc["reference"]:
        n, k = row["n"], row["k_max"]
        assert k is not None, row
        assert canonicalise_bound(clopper_pearson_upper(k, n, delta)) < alpha, row
        assert canonicalise_bound(clopper_pearson_upper(k + 1, n, delta)) >= alpha, row
        assert row["cp_k_max"] == canonicalise_bound(clopper_pearson_upper(k, n, delta)), row
        assert row["cp_k_max_plus_1"] == canonicalise_bound(clopper_pearson_upper(k + 1, n, delta)), row
        # `k_max` is the LAST k that clears: k+1 must not, and k-1 (where it exists) must.
        if k > 0:
            assert canonicalise_bound(clopper_pearson_upper(k - 1, n, delta)) < alpha, row
            assert report.g1_k_max(n, alpha, delta) == k, row


def test_the_ceiling_comparison_reads_the_published_precision_not_a_raw_double(rubric, monkeypatch):
    """The `k_max` above is a function of `canonicalise_bound`; a shifted canonicalisation must move it.

    Green-on-arrival proofs are not this row's job -- this one is the perturbation that shows the arm's
    central predicate is wired to the mechanism the existing arms use, rather than to a bare `==` on a raw
    float. `n=1000` is chosen because its `k_max=38` sits one error away from the threshold:
    `cp(39, 1000) = 0.050634` is 0.000634 over alpha, so a canonicalisation that reads 0.001 low puts it
    under and the ceiling slides to 39 -- and stops there, because `cp(40, 1000) = 0.051753` does not follow.
    """
    alpha, delta = rubric["alpha"], rubric["delta"]
    before = report.build_g1_feasibility(rubric)
    assert _reference_by_n(before, 1000)["k_max"] == 38, before["reference"]

    def shifted(value):
        return None if value is None else canonicalise_bound(value) - 0.001

    monkeypatch.setattr(report, "canonicalise_bound", shifted)
    after = report.build_g1_feasibility(rubric)
    assert _reference_by_n(after, 1000)["k_max"] == 39, _reference_by_n(after, 1000)
    assert _reference_by_n(after, 1000)["cp_k_max"] != _reference_by_n(before, 1000)["cp_k_max"]
    assert canonicalise_bound(clopper_pearson_upper(39, 1000, delta)) >= alpha, \
        "the perturbation moved nothing that the honest predicate would not have moved"


def test_the_probe_reference_table_is_reproduced_by_the_repo_functions(rubric):
    """The scratch probe's four size rows, re-derived -- the probe's digits are inputs to nothing here.

    The probe published `k_max` 1 / 8 / 38 / 128 at n = 100 / 300 / 1000 / 2974 with `cp(k_max)`
    0.046560 / 0.047600 / 0.049513 / 0.049672, widths 0.2716 / 0.1568 / 0.0859 / 0.0498 and bars
    no/no, no/yes, yes/yes, yes/yes. Those figures are quoted only as the thing this arm must reproduce from
    `tails.py`; the artefact's bytes come from the functions, and a disagreeing digit is drift the gate names.
    """
    alpha, delta = rubric["alpha"], rubric["delta"]
    doc = report.build_g1_feasibility(rubric)
    for n, k_max, width, bar_010, bar_025 in ((100, 1, 0.2716, False, False),
                                              (300, 8, 0.1568, False, True),
                                              (1000, 38, 0.0859, True, True),
                                              (2974, 128, 0.0498, True, True)):
        row = _reference_by_n(doc, n)
        assert row["k_max"] == k_max, row
        assert row["bound_width"] == round(bound_width(n, alpha), 4) == width, row
        assert row["feasible_at_0.10"] is n_feasible(n, alpha=alpha, max_bound_width=0.10) is bar_010, row
        assert row["feasible_at_0.25"] is n_feasible(n, alpha=alpha, max_bound_width=0.25) is bar_025, row
    assert _reference_by_n(doc, 2974)["size_from"] == (
        "n_eval + n_cal of data/cert_massive_de_laya.json, data/cert_massive_en_laya.json, "
        "data/cert_massive_sw_laya.json"), _reference_by_n(doc, 2974)
    # The probe's pure-zero context, one column of the same rows: cp(0, n) at each size.
    for n, zero in ((100, 0.029513), (300, 0.009936), (1000, 0.002991), (2974, 0.001007)):
        assert _reference_by_n(doc, n)["cp_zero_errors"] == round(zero, 6), _reference_by_n(doc, n)


def test_the_published_closest_attempt_bound_reproduces_from_the_certificates_own_digits(rubric):
    """The identity that makes a row a reading of the certificate rather than a fresh claim.

    `data/cert_massive_en_laya.json` publishes `meta.closest_attempt.conditional_error_bound` =
    `0.064239163974` over 30 errors in 628 automated records; this machine's libm answers `...973` for the
    raw double, and the published figure is that double after `canonicalise_bound` ceiled onto the
    certificate's 12-decimal grid. `43 of 709` reproduces without moving. Both directions are on this row:
    one pair needs the ceil, the other is exact, and a bare `==` on the raw double would fail the first and
    silently pass a tampered second.
    """
    doc = report.build_g1_feasibility(rubric)
    en = _row_by_task(doc, "massive/en")
    assert (en["automated_records"], en["errors_records"]) == (628, 30), en
    assert en["published_closest_bound"] == 0.064239163974, en
    assert en["recomputed_closest_bound"] == en["published_closest_bound"], en
    assert clopper_pearson_upper(30, 628, rubric["delta"]) != en["published_closest_bound"], \
        "the raw double must NOT equal the published bound, or this row proves nothing about canonicalisation"

    # The case-unit pair, from `meta.at_requested_alpha`: the bound the refusal sentence quotes.
    assert (en["automated_cases"], en["errors_cases"]) == (709, 43), en
    assert en["published_case_bound"] == 0.077514686246, en
    assert en["recomputed_case_bound"] == 0.077514686246, en
    for row in doc["rows"]:
        if row["closest_attempt_published"]:
            assert row["recomputed_closest_bound"] == row["published_closest_bound"], row
        if row["published_case_bound"] is not None:
            assert row["recomputed_case_bound"] == row["published_case_bound"], row


def test_each_row_publishes_both_denominators_and_never_mixes_them(rubric):
    """R-44's unit rule, checked as an invariant of every row rather than as a sentence in the document."""
    alpha, delta = rubric["alpha"], rubric["delta"]
    doc = report.build_g1_feasibility(rubric)
    for row in doc["rows"]:
        if not row["closest_attempt_published"]:
            continue
        assert row["errors_records"] <= row["automated_records"] <= row["n_eval_records"], row
        assert row["errors_cases"] <= row["automated_cases"] <= row["n_eval_cases"], row
        assert row["n_eval_cases"] <= row["n_eval_records"], row
        # Each ceiling is over its OWN unit's automated size.
        for unit in ("records", "cases"):
            n = row["automated_" + unit]
            k = row["k_max_" + unit]
            assert k == report.g1_k_max(n, alpha, delta), (row["task"], unit, n, k)
    jev = _row_by_task(doc, "jev")
    assert jev["n_eval_records"] == 96 and jev["n_eval_cases"] == 32, jev
    assert jev["k_max_records"] != jev["k_max_cases"], jev


def test_a_diagnostic_bound_is_never_published_as_a_certificate_bound(rubric):
    """The one sentence §4 forbids: `closest_attempt.conditional_error_bound` is not a certificate bound.

    Every published decision task carries `conditional_error_bound: null` at the top level -- the certificate
    issued nothing -- while its diagnostic `closest_attempt` carries a non-null bound. This row pins the
    difference from the artefact's own bytes: a row may name a bound, and must name which object it came
    from, so no document can be re-read as claiming a certification that no artefact holds.
    """
    from autorate.report import read_certificate

    doc = report.build_g1_feasibility(rubric)
    for row in doc["rows"]:
        if row["table"] == "inventory.corpus_options":
            continue
        cert = read_certificate(REPO / row["artefact"])
        assert cert.conditional_error_bound is None, row["artefact"]
        assert cert.autorate is None, row["artefact"]
        assert cert.feasible is False and cert.reason == "empty_feasible_set", row["artefact"]
        assert row["published_closest_bound"] is not None, row
        assert row["published_closest_bound"] != cert.conditional_error_bound, row


def test_the_oracle_ceiling_is_the_largest_n_a_the_pool_errors_fit(rubric):
    """`max(0, E - (P - n_a)) <= k_max(n_a)`, on inputs that make the answer move.

    The published rows only ever show a ceiling of 96 or 0, so the arithmetic is also exercised on pools
    where the answer is strictly between: `pool=96, errors=2` loses the full pool (2 > k_max(96) = 1) and
    lands on 95; `pool=32, errors=0` stays 0, because a 32-case denominator cannot bound under alpha even
    with nothing wrong. The last pair is the probe's `typed_decisions` arithmetic run on the PROBE's quoted
    accuracy (468 errors over 2,000 decisions, from upstream `BENCHMARKS.md`) to check this function against
    the probe's published 1,597 -- a validation of the function on inputs this repository does NOT publish,
    never a figure the artefact is allowed to carry.
    """
    alpha, delta = rubric["alpha"], rubric["delta"]
    assert report.g1_oracle_ceiling(96, 1, alpha, delta) == 96
    assert report.g1_oracle_ceiling(96, 2, alpha, delta) == 95
    assert report.g1_oracle_ceiling(32, 0, alpha, delta) == 0
    assert report.g1_oracle_ceiling(32, 1, alpha, delta) == 0
    assert report.g1_oracle_ceiling(100, 0, alpha, delta) == 100
    assert report.g1_oracle_ceiling(2000, 468, alpha, delta) == 1597
    doc = report.build_g1_feasibility(rubric)
    jev = _row_by_task(doc, "jev")
    assert jev["pool_is_automated_set"] is True, jev
    assert (jev["oracle_ceiling_records"], jev["oracle_ceiling_cases"]) == (96, 0), jev


def test_a_row_without_a_published_pool_error_count_is_null_with_the_input_named(rubric):
    """The null rule, in the resplit arm's own shape: undefined is stated, never imputed.

    A ceiling is a number exactly when the artefact states that the automated set IS the evaluated pool;
    otherwise both ceilings are null and `missing_pool_input` names the field a reader would need. Proven
    able to fail below, by building a row on a certificate whose automated subset is the whole pool.
    """
    doc = report.build_g1_feasibility(rubric)
    for row in doc["rows"]:
        ceilings = (row["oracle_ceiling_records"], row["oracle_ceiling_cases"])
        if row["pool_is_automated_set"]:
            assert all(isinstance(c, int) for c in ceilings), row
            assert row["missing_pool_input"] is None, row
        else:
            assert ceilings == (None, None), row
            assert row["missing_pool_input"], row
            assert "errors_among_automated" in row["missing_pool_input"] or \
                row["missing_pool_input"] == "no gold labels in this offline cache", row
    typed = _row_by_task(doc, "typed_decisions")
    assert typed["row_refusal"] == "no gold labels in this offline cache", typed
    assert [value for name, value in sorted(typed.items())
            if name not in ("task", "artefact", "table", "row_refusal", "missing_pool_input")] \
        == [None] * (len(report.G1_FEASIBILITY_ROW_FIELDS) - 5), typed


def test_a_certificate_with_no_closest_attempt_is_a_refusal_row_not_a_row_of_zeros(rubric):
    """`certify_score.py`'s refusals publish `closest_attempt: None`; a row over one must say so.

    Built from the published `jev` certificate with its diagnostic attempt removed, because no committed
    decision artefact has that shape today -- and the rule still has to be code, not intent, before the next
    refusal walks in. The record-unit columns go null with the field named; the case-unit columns are still
    this artefact's own bytes, so they stay.
    """
    from dataclasses import replace

    from autorate.report import read_certificate

    cert = read_certificate(REPO / "data" / "cert_jev.json")
    stripped = replace(cert, meta={**cert.meta, "closest_attempt": None})
    row = report.g1_task_row("jev", "data/cert_jev.json", "report.CERTS", stripped,
                            rubric["alpha"], rubric["delta"])
    assert row["closest_attempt_published"] is False, row
    assert row["automated_records"] is None and row["errors_records"] is None, row
    assert row["k_max_records"] is None and row["published_closest_bound"] is None, row
    assert row["oracle_ceiling_records"] is None, row
    assert "meta.closest_attempt" in row["row_refusal"], row
    assert row["n_eval_records"] == 96 and row["automated_cases"] == 32, row
    # The same builder on the unstripped certificate fills every one of those columns: the nulls above are
    # the missing input, not a builder that never reaches them.
    filled = report.g1_task_row("jev", "data/cert_jev.json", "report.CERTS", cert,
                                rubric["alpha"], rubric["delta"])
    assert filled["closest_attempt_published"] is True, filled
    assert (filled["automated_records"], filled["errors_records"], filled["grid_alpha"]) == (96, 1, 0.02)
    assert filled["row_refusal"] is None, filled


def test_the_feasibility_rows_reuse_the_certifier_denominators_not_a_second_definition(rubric):
    """The row's inputs are the certificate's own fields, read off `meta` by name.

    `closest_attempt.automated` is 628 records for `en` while `meta.automated_cases` is 709 cases: a row that
    took one denominator and labelled it the other would be #37 all over again, so this row names the exact
    field each column came from, from the bytes on disk.
    """
    import json

    raw = json.loads((REPO / "data" / "cert_massive_en_laya.json").read_text())
    doc = report.build_g1_feasibility(rubric)
    en = _row_by_task(doc, "massive/en")
    assert en["automated_records"] == raw["meta"]["closest_attempt"]["automated"] == 628, en
    assert en["errors_records"] == raw["meta"]["closest_attempt"]["errors"] == 30, en
    assert en["published_closest_bound"] == raw["meta"]["closest_attempt"]["conditional_error_bound"], en
    assert en["grid_alpha"] == raw["meta"]["closest_attempt"]["grid_alpha"], en
    assert en["automated_cases"] == raw["meta"]["automated_cases"] == 709, en
    assert en["errors_cases"] == raw["meta"]["erroneous_cases"] == 43, en
    assert en["published_case_bound"] == raw["meta"]["at_requested_alpha"]["conditional_error_bound"], en
    assert en["n_eval_records"] == raw["n_eval"] == 1487, en
    assert en["n_eval_cases"] == raw["meta"]["n_eval_cases"] == 1487, en


def test_the_rubric_is_the_freezes_and_nobody_retypes_a_zero_five(rubric):
    """No literal `0.05` in the producer's arithmetic path: the document's rubric is the loaded freeze's.

    Checked two ways, because a value comparison cannot tell an imported constant from a re-typed literal
    while alpha, beta and delta are numerically identical: the document's rubric block must equal the loaded
    protocol's, and a rubric edited in the loaded object (not on disk) must move the document with it.
    """
    from copy import deepcopy

    doc = report.build_g1_feasibility(rubric)
    assert doc["rubric"] == {key: rubric[key] for key in report.G1_FEASIBILITY_RUBRIC_FIELDS}, doc["rubric"]
    assert doc["producer"] == "tools/g1_feasibility.py", doc["producer"]
    assert sorted(doc) == ["producer", "reference", "rows", "rubric"], sorted(doc)

    moved = deepcopy(rubric)
    moved["delta"] = 0.01
    shifted = report.build_g1_feasibility(moved)
    assert shifted["rubric"]["delta"] == 0.01, shifted["rubric"]
    assert _reference_by_n(shifted, 2974)["k_max"] < _reference_by_n(doc, 2974)["k_max"], \
        "a tighter delta must buy a smaller ceiling, or the ceiling ignores the freeze"
    producer_text = (REPO / "tools" / "g1_feasibility.py").read_text()
    assert "0.05" not in producer_text, "the producer retyped the rubric it is handed"

