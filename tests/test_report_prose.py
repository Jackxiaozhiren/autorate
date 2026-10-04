"""The report's narrative is derived, so a changed certificate changes the sentence.

Three published defects are what these tests exist for. The first printed one fixed sentence per
backend, so a regenerated artifact could assert the opposite of the counts inside it. The second
surfaced in review of that repair: the zero-error counterfactual was quoted at `n_eval_cases`, which for
laya is 32 while its own bound was computed over 2 automated cases -- the row published another row's
number (0.089 instead of its own 0.776). The third was that the new tests all swapped jev and asserted
only jev, so the misattribution rendered eight times and nothing read it. Hence: assertions name the
backend clause they read, and the shipped laya row is asserted directly.
"""
import json
from dataclasses import replace
from pathlib import Path

from autorate.report import build_report, load_records, read_certificate
from autorate.tails import clopper_pearson_upper

NO_BOUND = object()
NO_ATTEMPT = object()


def _swap(cert, overrides: dict, bound, attempt=None):
    """Patch one certificate's refusal facts. Record counts are given, never inferred.

    A case is erroneous when ANY automated record in it is wrong, and repeats are not necessarily
    identical across backends -- the shipped jev certificate has 1 erroneous CASE and 1 erroneous RECORD,
    laya has 1 and 3 -- so scaling errors by a repeat factor would hand the renderer an artifact the
    corpus contradicts. Every fixture therefore states both denominators.
    """
    meta = dict(cert.meta)
    meta.update(overrides)
    if bound is NO_BOUND:
        (meta.get("at_requested_alpha") or {}).pop("conditional_error_bound", None)
    elif bound is not None:
        alpha = dict(meta.get("at_requested_alpha") or {})
        alpha["conditional_error_bound"] = bound
        meta["at_requested_alpha"] = alpha
    if attempt is NO_ATTEMPT:
        meta.pop("closest_attempt", None)
    elif attempt is not None:
        ca = dict(meta.get("closest_attempt") or {})
        ca["conditional_error_bound"] = attempt
        meta["closest_attempt"] = ca
    return replace(cert, meta=meta)


def _render(jev_overrides=None, jev_bound=None, attempt=None, laya_overrides=None):
    inv = json.loads(Path("data/inventory.md.json").read_text())
    laya = read_certificate(Path("data/cert_laya.json"))
    jev = read_certificate(Path("data/cert_jev.json"))
    if laya_overrides:
        laya = replace(laya, meta={**laya.meta, **laya_overrides})
    if jev_overrides or jev_bound is not None or attempt is not None:
        jev = _swap(jev, jev_overrides or {}, jev_bound, attempt)
    records = load_records(Path("data/records_feishu.jsonl"))
    text = build_report(inv, {"laya": laya, "jev": jev},
                        {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- Both rows refuse")
                or l.startswith("- Both rows certify") or " rows refuse" in l)
    after_laya = line.partition(" laya: ")[2]
    return line, after_laya.partition(" jev: ")[0], after_laya.partition(" jev: ")[2]


def test_the_shipped_laya_row_quotes_its_own_denominator_not_jeVs():
    """The regression I-1: laya automates 2 cases, so its counterfactual is CP(0, 2), not CP(0, 32)."""
    _, laya, jev = _render()
    assert "those same 2 automated cases would still have bounded at 0.776" in laya, laya
    assert "0.089" not in laya, laya
    assert "those same 32 automated cases would still have bounded at 0.089" in jev, jev
    # the claim is measured, not remembered
    assert abs(clopper_pearson_upper(0, 2, 0.05) - 0.776393) < 1e-6


def test_a_row_that_automates_nothing_gets_the_other_shape():
    _, _, jev = _render({"automated_cases": 0, "automated": 0, "erroneous_cases": 0,
                        "empties": 0, "multi_label": 90}, 0.9746)
    assert jev.startswith("not one evaluation case produced a single-label set (0 empty, 90 "
                          "multi-label of "), jev
    assert "upper bound" not in jev, jev


def test_the_record_clause_reads_the_certificate_and_does_not_recompute_it():
    """I-4: the record-denominator figure has one owner, and this proves which one."""
    _, _, tail = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                         "errors_among_automated": 1}, 0.1398, attempt=0.4242)
    assert "would bound at 0.424" in tail, tail
    assert "0.048" not in tail, tail          # CP(1, 96) -- the value a re-derivation would print
    assert "inside its 0.050 budget" not in tail, tail


def test_the_verdict_word_is_derived_from_the_comparison():
    """`inside`/`above` cannot be asserted when the numbers say otherwise."""
    _, _, low = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                        "errors_among_automated": 1}, 0.1398, attempt=0.0137)
    assert "at 0.014, inside its 0.050 budget" in low, low
    _, _, high = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                         "errors_among_automated": 1}, 0.1398, attempt=0.3012)
    assert "at 0.301, above its 0.050 budget" in high, high


def test_a_certificate_with_no_attempt_record_prints_no_record_clause():
    """The shape that used to render `nan` into a reproduction-policed artifact."""
    _, laya, jev = _render({"automated_cases": 0, "automated": 0, "erroneous_cases": 0,
                           "n_eval_cases": 32}, NO_BOUND, attempt=NO_ATTEMPT)
    assert "record denominator" not in jev and "nan" not in jev, jev
    assert laya, "the laya clause must still render"


def test_a_certified_row_is_not_described_as_a_refusal():
    """M-1: the bullet began "Both rows refuse" whatever the certificates actually said.

    Built from a real certifier run rather than by patching fields onto a refusal: `Certificate` refuses
    to hold `feasible=True` alongside a refusal reason or without the fields a certificate must carry,
    and a fixture that fought that invariant would be testing the fixture.
    """
    from autorate.certify_choice import certify_choice

    records = load_records(Path("data/records_feishu.jsonl"))
    certs = {b: certify_choice(records[b], alpha=0.5, beta=0.95, seed=7) for b in ("laya", "jev")}
    assert all(c.feasible for c in certs.values()), {b: (c.feasible, c.reason)
                                                    for b, c in certs.items()}
    inv = json.loads(Path("data/inventory.md.json").read_text())
    text = build_report(inv, certs, {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- Both rows"))
    assert line.startswith("- Both rows certify at alpha=0.50, beta=0.95."), line
    assert "it certifies:" in line, line
    assert "refuses is the correct output" not in line, line
    assert "does not license" not in line, line


def test_the_earliest_refusals_render_without_raising():
    """M-2, on a real certificate: `n_below_min` returns before ANY case counter is recorded.

    A fixture that merely overrides the counters to zero cannot find this -- the defect is that the
    keys are absent, not that they are zero -- so the certificate is produced by the certifier itself.
    """
    from autorate.certify_choice import certify_choice

    records = load_records(Path("data/records_feishu.jsonl"))
    small = records["laya"][:40]                      # under MIN_CAL/MIN_EVAL, so it refuses early
    early = certify_choice(small, alpha=0.05, beta=0.05, seed=7)
    assert not early.feasible and early.reason == "n_below_min", (early.feasible, early.reason)
    assert "automated_cases" not in early.meta, sorted(early.meta)
    inv = json.loads(Path("data/inventory.md.json").read_text())
    text = build_report(inv, {"laya": early, "jev": read_certificate(Path("data/cert_jev.json"))},
                        {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- Both rows"))
    assert "n_below_min" in line or "not one evaluation case" in line, line


def test_the_bound_is_read_from_the_certificate_and_not_recomputed():
    _, _, jev = _render({"automated_cases": 40, "automated": 40, "erroneous_cases": 2,
                        "n_eval_cases": 40, "errors_among_automated": 2}, 0.9999)
    assert "upper bound is 1.000" in jev, jev
    assert "0.139" not in jev, jev


def test_a_refusal_that_never_reached_the_bound_step_invents_none():
    _, _, jev = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                        "errors_among_automated": 1}, NO_BOUND)
    assert "carries a wrong automated request, which the 0.050 budget does not license." in jev, jev
    assert "upper bound" not in jev, jev


def test_the_error_wording_agrees_with_the_number():
    """`1 of those carries`, `2 of those carry` -- rendered prose, not a template with a hole."""
    _, _, one = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                        "errors_among_automated": 1}, 0.1398)
    assert "1 of those carries" in one, one
    _, _, many = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 2,
                         "errors_among_automated": 2}, 0.1969)
    assert "2 of those carry" in many, many


def test_the_two_shapes_do_not_render_identically():
    """Kept although the original bug passed it: difference alone is not evidence of derivation."""
    a = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 1,
                "errors_among_automated": 1}, 0.1398)[2]
    b = _render({"automated_cases": 32, "automated": 96, "erroneous_cases": 0,
                "errors_among_automated": 0}, 0.0893)[2]
    assert a != b, "the refusal sentence does not depend on the certificate"
