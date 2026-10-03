"""The report's refusal narrative is derived, so a changed certificate changes the sentence.

`report.py` used to print one fixed sentence per backend. Each became a published contradiction once
the case denominator was repaired: one clause asserted "not one evaluation case produced a
single-label set" beside counts showing otherwise, and another interpolated a zero-error
Clopper-Pearson bound and called the run zero-error. These tests render the shipped template over
certificates whose refusal facts are swapped and require the wording to follow the data -- the property
hardcoded prose cannot pass. Assertions name the backend clause they read, because the bullet carries
both rows and one row's wording can otherwise satisfy the other row's assertion.
"""
import json
from dataclasses import replace
from pathlib import Path

from autorate.report import build_report, load_records, read_certificate
from autorate.tails import clopper_pearson_upper

NO_BOUND = object()
REPEATS = 3  # this corpus archives each case three times, byte-identical


def _swap(cert, meta_overrides: dict, bound):
    cases = meta_overrides.get("automated_cases", cert.meta["automated_cases"])
    wrong = meta_overrides.get("erroneous_cases", cert.meta["erroneous_cases"])
    # `automated_cases`/`erroneous_cases` and `automated`/`errors_among_automated` are the same
    # decisions at two denominators and the report quotes both, so a fixture that moves one and not the
    # other hands the renderer an incoherent certificate -- a bug in the fixture, not in the prose.
    overrides = {"automated": cases * REPEATS, "errors_among_automated": wrong * REPEATS}
    overrides.update(meta_overrides)
    attempt = dict(cert.meta.get("at_requested_alpha") or {})
    if bound is NO_BOUND:
        attempt.pop("conditional_error_bound", None)
    else:
        attempt["conditional_error_bound"] = bound
    return replace(cert, meta={**cert.meta, **overrides, "at_requested_alpha": attempt})


def _clauses(jev_meta: dict, bound) -> tuple:
    """Render the shipped report with jev's refusal facts swapped. Returns (laya, jev, whole line)."""
    inv = json.loads(Path("data/inventory.md.json").read_text())
    laya = read_certificate(Path("data/cert_laya.json"))
    jev = _swap(read_certificate(Path("data/cert_jev.json")), jev_meta, bound)
    records = load_records(Path("data/records_feishu.jsonl"))
    text = build_report(inv, {"laya": laya, "jev": jev},
                        {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- Both rows refuse"))
    after_laya = line.partition(" laya: ")[2]
    return after_laya.partition(" jev: ")[0], after_laya.partition(" jev: ")[2], line


def test_the_narrative_names_the_errors_the_certificate_actually_has():
    _, jev, _ = _clauses({"automated_cases": 32, "erroneous_cases": 3}, 0.2713)
    assert "3 of those carries a wrong automated request" in jev, jev
    assert "upper bound is 0.271" in jev, jev
    assert "with zero errors, yet" not in jev, jev


def test_the_counterfactual_is_kept_but_labelled_as_one():
    _, jev, _ = _clauses({"automated_cases": 32, "erroneous_cases": 2}, 0.1969)
    assert ("even had that request been right, a zero-error run over the same n=32 would still "
            "have bounded at 0.089") in jev, jev


def test_a_zero_error_certificate_gets_a_zero_error_sentence():
    _, jev, _ = _clauses({"automated_cases": 32, "erroneous_cases": 0}, 0.0893)
    assert "with zero errors, yet the exact case-level upper bound on that run is 0.089" in jev, jev
    assert "carries a wrong automated request" not in jev, jev


def test_a_certificate_that_automates_nothing_gets_the_refusal_shape():
    """The `automated == 0` branch, which the shipped laya row no longer occupies."""
    _, jev, _ = _clauses({"automated_cases": 0, "erroneous_cases": 0, "empties": 0,
                         "multi_label": 90}, 0.9746)
    assert jev.startswith("not one evaluation case produced a single-label set (0 empty, 90 "
                          "multi-label of "), jev
    assert "upper bound" not in jev, jev


def test_the_bound_is_read_from_the_certificate_and_not_recomputed():
    """`certify_choice` owns the case bound; the report must not derive its own."""
    _, jev, _ = _clauses({"automated_cases": 40, "erroneous_cases": 2}, 0.9999)
    assert "upper bound is 1.000" in jev, jev
    assert "0.139" not in jev, jev


def test_a_refusal_that_never_reached_the_bound_step_invents_none():
    _, jev, _ = _clauses({"automated_cases": 32, "erroneous_cases": 1}, NO_BOUND)
    assert "carries a wrong automated request, which the 0.050 budget does not license." in jev, jev
    assert "upper bound" not in jev, jev


def test_the_record_denominator_clause_is_derived_too():
    _, _, line = _clauses({"automated_cases": 32, "erroneous_cases": 3}, 0.1398)
    jev = read_certificate(Path("data/cert_jev.json"))
    wanted = clopper_pearson_upper(3 * REPEATS, 32 * REPEATS, jev.delta)
    assert "would bound at %.3f" % wanted in line, line
    assert "0.048" not in line, line


def test_the_two_shapes_do_not_render_identically():
    """Kept although the old bug passed it: difference alone is not enough, which is the lesson."""
    a = _clauses({"automated_cases": 32, "erroneous_cases": 1}, 0.1398)[1]
    b = _clauses({"automated_cases": 32, "erroneous_cases": 0}, 0.0893)[1]
    assert a != b, "the refusal sentence does not depend on the certificate"
