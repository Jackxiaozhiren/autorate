"""The report's narrative is derived, so a changed certificate changes the sentence.

Five published defects are what these tests exist for. The first printed one fixed sentence per
backend, so a regenerated artifact could assert the opposite of the counts inside it. The second
surfaced in review of that repair: the zero-error counterfactual was quoted at `n_eval_cases`, which for
laya is 32 while its own bound was computed over 2 automated cases -- the row published another row's
number (0.089 instead of its own 0.776). The third was that the new tests all swapped jev and asserted
only jev, so the misattribution rendered eight times and nothing read it. Hence: assertions name the
backend clause they read, and the shipped laya row is asserted directly.

The next three are the same three shapes in the repair itself, found by the re-review: the *certified*
branch asserted "none of them is wrong" for a row certifying 9 erroneous cases of 15 (a feasible row is
admitted at a loose `beta`, not an errorless one); a certificate that never reached the case stage had
its counters defaulted to zero in prose and hard-indexed in the table, so one slot raised `KeyError` and
the other narrated label shape for a refusal about sample size; and the record clause paired a record
count taken at the requested alpha with a bound taken at a different grid point, silent only because jev's
two points coincide. Every one of them is a sentence contradicting the artifact printed beside it.
"""
import json
from dataclasses import replace
from pathlib import Path

from autorate.certify_choice import certify_choice
from autorate.report import build_report, load_records, read_certificate
from autorate.tails import clopper_pearson_upper
from test_certify_choice import _records

NO_BOUND = object()
NO_ATTEMPT = object()


def _swap(cert, overrides: dict, bound, attempt=None):
    """Patch one certificate's refusal facts. Record counts are given, never inferred.

    A case is erroneous when ANY automated record in it is wrong, and repeats are not necessarily
    identical across backends -- the shipped jev certificate has 1 erroneous CASE and 1 erroneous RECORD,
    laya has 1 and 3 -- so scaling errors by a repeat factor would hand the renderer an artifact the
    corpus contradicts. Every fixture therefore states both denominators.

    Every nested structure is copied before it is touched: `build_report` reloads the shipped
    certificates on each call today, but a fixture that mutated `cert.meta["at_requested_alpha"]` in
    place would leak its patch into the next test the moment that stopped being true.
    """
    meta = dict(cert.meta)
    meta.update(overrides)
    if bound is NO_BOUND:
        alpha = dict(meta.get("at_requested_alpha") or {})
        alpha.pop("conditional_error_bound", None)
        meta["at_requested_alpha"] = alpha
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


def _render(jev_overrides=None, jev_bound=None, attempt=None, laya_cert=None, jev_cert=None):
    """Render the published bullet. A slot may be replaced whole, not only patched.

    `laya_cert`/`jev_cert` exist because the two backends are not symmetric in the renderer: some site
    guards with `.get` and some hard-indexes, and a fixture that can only ever put a shape in the
    guarded slot is how `KeyError` survived a round that claimed to fix the generator's totality.
    """
    inv = json.loads(Path("data/inventory.md.json").read_text())
    laya = laya_cert if laya_cert is not None else read_certificate(Path("data/cert_laya.json"))
    jev = jev_cert if jev_cert is not None else read_certificate(Path("data/cert_jev.json"))
    if jev_overrides or jev_bound is not None or attempt is not None:
        jev = _swap(jev, jev_overrides or {}, jev_bound, attempt)
    records = load_records(Path("data/records_feishu.jsonl"))
    text = build_report(inv, {"laya": laya, "jev": jev},
                        {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- ")
                and " laya: " in l and " jev: " in l)
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


def test_the_record_clause_names_one_experiment_per_figure():
    """Item 3: the printed count came from one operating point, the printed bound from another.

    laya is the shape the shipped jev bullet cannot show, because jev's two points coincide at 96 records
    at both. At the certified alpha=0.050 laya automates 6 RECORDS, while its `closest_attempt` is the
    grid point alpha=0.260 -- 33 records, 21 of them wrong, bound 0.775. The sentence read
    "laya's 6 automated records would bound at 0.775", which is neither experiment: 6 records bound at
    0.975 (that is the case figure, over 2 automated cases) and 33 records bound at 0.775.
    """
    from autorate.report import _record_clause

    laya = read_certificate(Path("data/cert_laya.json"))
    attempt = laya.meta["closest_attempt"]
    assert (attempt["automated"], attempt["errors"], attempt["grid_alpha"]) == (33, 21, 0.26), attempt
    assert (laya.meta["automated"], laya.meta["automated_cases"]) == (6, 2), laya.meta
    clause = _record_clause(laya)
    assert "33 automated records" in clause, clause
    assert "6 automated records" not in clause, clause
    assert "21 of them wrong" in clause and "0.775" in clause, clause
    assert "2 automated cases" in clause and "1 of them wrong" in clause and "0.975" in clause, clause
    assert "alpha=0.260" in clause, clause


def test_a_record_clause_without_the_case_figure_drops_rather_than_substitutes():
    """Item 3's fallback: the case slot defaulted to the record bound.

    `at_requested_alpha` is written on one path only (`certify_choice.py:218-220`), so a refusal such as
    `vacuous_quantile` carries `closest_attempt` and no case figure at all. Substituting the record bound
    printed one number twice, about two different denominators.
    """
    from autorate.report import _record_clause

    jev = read_certificate(Path("data/cert_jev.json"))
    stripped = replace(jev, meta={k: v for k, v in jev.meta.items() if k != "at_requested_alpha"})
    assert stripped.meta["closest_attempt"] is not None
    assert _record_clause(stripped) == "", _record_clause(stripped)


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
    """The shape that used to render `nan` into a reproduction-policed artifact.

    Separated from the zero-automation guard (item 5): this fixture leaves the record counts alone and
    removes `closest_attempt`, so the guard it reaches is the missing record bound, which is what I-3
    named. The old version also set `automated=0`, which short-circuited a different guard and let this
    one go untested.
    """
    _, laya, jev = _render(attempt=NO_ATTEMPT)
    assert "record denominator" not in jev and "nan" not in jev, jev
    assert "even had that request been right" in jev, jev
    assert "those same 2 automated cases" in laya, laya


def test_a_record_point_that_automates_no_records_prints_no_record_clause():
    """Item 5's other guard, now reachable on its own: a record denominator of zero."""
    from autorate.report import _record_clause

    jev = read_certificate(Path("data/cert_jev.json"))
    empty_attempt = replace(jev, meta={**jev.meta, "closest_attempt": {
        **jev.meta["closest_attempt"], "automated": 0, "errors": 0}})
    assert _record_clause(empty_attempt) == "", _record_clause(empty_attempt)
    # and a divided-by-zero re-derivation would have raised instead: the clause reads, it does not compute
    assert jev.meta["closest_attempt"]["automated"] == 96


def test_a_dropped_record_clause_leaves_no_trailing_space():
    """Item 6: the bullet kept the space that separated it from a sentence that was never printed."""
    line, laya, jev = _render({"automated_cases": 0, "automated": 0, "erroneous_cases": 0},
                              NO_BOUND, attempt=NO_ATTEMPT)
    assert "record denominator" not in line, line
    assert line == line.rstrip(), repr(line[-60:])


def test_the_pair_lead_counts_the_rows_it_was_given():
    """Item 6: "Both rows refuse" printed for a lone certificate, and "1 of 2 rows refuse".

    The lead is the one sentence in the bullet that is about the pair rather than a row, so it has to
    agree with how many rows are in the call and with how many of them refused.
    """
    from autorate.report import _pair_lead

    records = load_records(Path("data/records_feishu.jsonl"))
    early = _early_certificates()["laya"]["n_below_min"]
    shipped_jev = read_certificate(Path("data/cert_jev.json"))
    certified = certify_choice(records["laya"], alpha=0.5, beta=0.95, seed=7)
    assert _pair_lead(early) == "The row refuses at alpha=beta=0.05.", _pair_lead(early)
    assert _pair_lead(certified) == "The row certifies at alpha=0.50, beta=0.95.", _pair_lead(certified)
    assert _pair_lead(early, shipped_jev) == "Both rows refuse at alpha=beta=0.05.", \
        _pair_lead(early, shipped_jev)
    assert _pair_lead(early, early) == "Both rows refuse at alpha=beta=0.05.", _pair_lead(early, early)
    assert _pair_lead(certified, certified) == "Both rows certify at alpha=0.50, beta=0.95.", \
        _pair_lead(certified, certified)
    # the mixed pair, and the budgets differ, so only the count and its verb are under test here
    mixed = _pair_lead(certified, early)
    assert mixed.startswith("1 of 2 rows refuses at "), mixed


def test_a_certified_row_is_not_described_as_a_refusal():
    """M-1 and item 1: the certified clause must report the errors feasibility did not forbid.

    Built from a real certifier run rather than by patching fields onto a refusal: `Certificate` refuses
    to hold `feasible=True` alongside a refusal reason or without the fields a certificate must carry,
    and a fixture that fought that invariant would be testing the fixture.

    The numbers are the point. `certify_choice` admits a row when `cond_hi <= beta`, and a row with
    errors can satisfy that at a loose `beta`: at alpha=0.50/beta=0.95 the shipped laya records certify
    15 of 32 cases with 9 of them erroneous. The sentence used to add "and none of them is wrong" to
    every feasible row, so it refuted the count printed three words earlier. Four substring assertions
    all survived that lie; these assert the shape's numbers instead.
    """
    records = load_records(Path("data/records_feishu.jsonl"))
    certs = {b: certify_choice(records[b], alpha=0.5, beta=0.95, seed=7) for b in ("laya", "jev")}
    assert all(c.feasible for c in certs.values()), {b: (c.feasible, c.reason)
                                                    for b, c in certs.items()}
    laya_meta = certs["laya"].meta
    assert (laya_meta["automated_cases"], laya_meta["n_eval_cases"],
            laya_meta["erroneous_cases"]) == (15, 32, 9), laya_meta
    assert abs(certs["laya"].conditional_error_bound - 0.809135) < 1e-6
    inv = json.loads(Path("data/inventory.md.json").read_text())
    text = build_report(inv, certs, {b: len(rs) for b, rs in records.items()})
    line = next(l for l in text.splitlines() if l.startswith("- ")
                and " laya: " in l and " jev: " in l)
    assert line.startswith("- Both rows certify at alpha=0.50, beta=0.95."), line
    assert "refuses is the correct output" not in line, line
    laya = line.partition(" laya: ")[2].partition(" jev: ")[0]
    jev = line.partition(" jev: ")[2]
    assert "15 of its 32 evaluation cases automate" in laya, laya
    assert "9 of those carry a wrong automated request" in laya, laya
    assert "upper bound is 0.809" in laya, laya
    assert "none of them is wrong" not in line, line
    # the same sentence must hold for the row that certifies everything it evaluated
    assert "32 of its 32 evaluation cases automate" in jev, jev
    assert "1 of those carries a wrong automated request" in jev, jev


def test_a_certified_row_without_errors_says_none_of_them_is_wrong():
    """Item 1's other arm: the zero-error wording is kept where the certificate earns it.

    A real certifier run on synthetic labelled decisions whose argmax is never wrong, so
    `erroneous_cases` is genuinely 0 and the phrase is a report, not a template.
    """
    from autorate.report import _decision_clause

    cert = certify_choice(_records(200, sharpness=8.0, error_rate=0.0, seed=3),
                          alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible and cert.meta["erroneous_cases"] == 0, cert.summary()
    clause = _decision_clause(cert)
    assert ("%d of its %d evaluation cases automate and none of them is wrong"
            % (cert.meta["automated_cases"], cert.meta["n_eval_cases"])) in clause, clause
    assert "upper bound is %.3f" % cert.conditional_error_bound in clause, clause
    assert abs(cert.conditional_error_bound
               - clopper_pearson_upper(0, cert.meta["automated_cases"], cert.delta)) < 1e-9


def _early_certificates():
    """The two refusals that return before `certify_choice` counts a case, for both backends.

    Built by the certifier itself: the defect is that the counters are ABSENT, and a fixture that zeroes
    them tests a different certificate than the one the defect ships. Both backends because the two
    slots are not symmetric in the renderer -- the refusal's table row guards with `.get` while the
    per-CASE bullet indexes `certs["jev"]` directly.
    """
    records = load_records(Path("data/records_feishu.jsonl"))
    out = {}
    for b in ("laya", "jev"):
        short = certify_choice(records[b][:40], alpha=0.05, beta=0.05, seed=7)
        assert not short.feasible and short.reason == "n_below_min", short.summary()
        unlabelled = certify_choice([r for r in records[b] if r.qtype != "choice"],
                                    alpha=0.05, beta=0.05, seed=7)
        assert not unlabelled.feasible and unlabelled.reason == "no_gold_labels", unlabelled.summary()
        for cert in (short, unlabelled):
            assert "automated_cases" not in cert.meta, sorted(cert.meta)
            assert "n_eval_cases" not in cert.meta, sorted(cert.meta)
            assert "erroneous_cases" not in cert.meta, sorted(cert.meta)
        out[b] = {"n_below_min": short, "no_gold_labels": unlabelled}
    return out


def test_the_earliest_refusals_render_without_raising_in_either_slot():
    """Items 2 and 4, on real certificates: both backends x both reasons.

    Item 4's defect was a narrative about the wrong reason: an `n_below_min` row rendered "not one
    evaluation case produced a single-label set (0 empty, 0 multi-label of 6 records)", which is
    internally incoherent (0 + 0 != 6) and about label shape when the refusal is about sample size. The
    guard that was supposed to catch it asserted `"n_below_min" in line or "not one evaluation case" in
    line`, so it passed on the very wording this test now forbids -- hence one conjunctive assertion.
    """
    for slot in ("laya", "jev"):
        for reason, cert in _early_certificates()[slot].items():
            line, laya, jev = _render(**{"%s_cert" % slot: cert})
            clause = laya if slot == "laya" else jev
            assert reason in clause and "before any case was counted" in clause, (slot, reason, clause)
            assert cert.meta["detail"] in clause, (slot, reason, clause)
            assert "not one evaluation case" not in clause, (slot, reason, clause)
            assert "empty, " not in clause, (slot, reason, clause)
            assert line, (slot, reason)


def test_the_per_case_bullet_is_dropped_when_the_jev_row_never_counted_a_case():
    """Item 2's measured crash: `build_report` raised `KeyError: 'n_eval_cases'` for the jev row.

    The bullet reads jev and only jev -- quoting the other row's case count instead would be the
    misattribution this file exists to prevent -- so an absent figure drops the sentence rather than
    substituting a zero or another backend's number.
    """
    records = load_records(Path("data/records_feishu.jsonl"))
    inv = json.loads(Path("data/inventory.md.json").read_text())
    counts = {b: len(rs) for b, rs in records.items()}
    early = _early_certificates()["jev"]["n_below_min"]
    text = build_report(inv, {"laya": read_certificate(Path("data/cert_laya.json")), "jev": early},
                        counts)
    assert not [l for l in text.splitlines()
                if l.startswith("- The bounds are per CASE")], text
    jev_row = next(l for l in text.splitlines() if l.startswith("| jev |"))
    assert jev_row.endswith("| -/- |"), jev_row


def test_a_certified_row_without_case_counters_invents_none():
    """Item 2's second site: the certified table row hard-indexed the same keys.

    `certify_choice` records the counters on every feasible path, so this shape arrives only from a
    certificate written by something else -- exactly when a published-artifact generator may not raise,
    and may not print "0 of its 0 evaluation cases automate and none of them is wrong" beside a row that
    certified 15 of 32 with 9 wrong.
    """
    records = load_records(Path("data/records_feishu.jsonl"))
    inv = json.loads(Path("data/inventory.md.json").read_text())
    counts = {b: len(rs) for b, rs in records.items()}
    feasible = certify_choice(records["laya"], alpha=0.5, beta=0.95, seed=7)
    assert feasible.feasible and feasible.meta["automated_cases"] == 15, feasible.summary()
    stripped = replace(feasible, meta={k: v for k, v in feasible.meta.items()
                                       if k not in ("automated_cases", "n_eval_cases",
                                                    "erroneous_cases", "n_cal_cases")})
    text = build_report(inv, {"laya": stripped, "jev": read_certificate(Path("data/cert_jev.json"))},
                        counts)
    laya_row = next(l for l in text.splitlines() if l.startswith("| laya |"))
    assert laya_row.startswith("| laya | certified"), laya_row
    assert laya_row.endswith("| -/- |"), laya_row
    assert "0 of its 0 evaluation cases" not in text, text
    bullet = next(l for l in text.splitlines() if l.startswith("- ")
                  and " laya: " in l and " jev: " in l)
    assert "carries no case counters" in bullet.partition(" laya: ")[2].partition(" jev: ")[0], bullet


def test_a_zero_error_refusal_is_positive_about_being_zero_error():
    """Item 5: the `wrong == 0` refusal branch lost its positive test when its two tests were deleted.

    A real certifier run whose automated cases are all correct but whose zero-error bound still misses a
    tight budget -- the shape where "not one of them is wrong" and "this corpus cannot certify" are both
    true at once. The figures come from the same derivation the sentence uses.
    """
    from autorate.report import _decision_clause

    cert = certify_choice(_records(122, sharpness=8.0, error_rate=0.0, seed=3),
                          alpha=0.29, beta=0.05, seed=7)
    assert not cert.feasible and cert.reason == "empty_feasible_set", cert.summary()
    assert cert.meta["erroneous_cases"] == 0 and cert.meta["automated_cases"] > 0, sorted(cert.meta)
    # a refusal carries no headline bound (`Certificate` forbids it), so the sentence's figure is the
    # diagnostic one recorded at the requested alpha -- the same source the clause reads.
    bound = cert.meta["at_requested_alpha"]["conditional_error_bound"]
    clause = _decision_clause(cert)
    assert ("%d of its %d evaluation cases with zero errors"
            % (cert.meta["automated_cases"], cert.meta["n_eval_cases"])) in clause, clause
    assert "upper bound on that run is %.3f" % bound in clause, clause
    assert abs(bound - clopper_pearson_upper(0, cert.meta["automated_cases"], cert.delta)) < 1e-9
    assert "even had that request been right" not in clause, clause


def test_the_counterfactual_is_kept_and_labelled_as_one():
    """Item 5: the shipped rows are the counterfactual shape, and its wording was unpinned.

    "even had that request been right" is a counterfactual about a run that was not this run; the
    deletion of its test left the phrase reachable with no assertion on it.
    """
    line, laya, jev = _render()
    for clause, cases, bound in ((laya, 2, 0.776), (jev, 32, 0.089)):
        assert "even had that request been right" in clause, clause
        assert ("a zero-error run over those same %d automated cases would still have bounded at %.3f"
                % (cases, bound)) in clause, clause


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


def test_the_denominator_note_quotes_the_inventory_rather_than_a_memory_of_it():
    """#33's last typed figures: prose said "MASSIVE's 51 files" beside an inventory saying 3 of 51.

    Every number must move with `inv`, and the translation claim must go quiet when the two options stop
    agreeing, because a sentence that asserts the claim regardless of the data is the same defect class
    as the one this file exists to prevent.
    """
    from autorate.report import _denominator_note

    inv = json.loads(Path("data/inventory.md.json").read_text())
    note = _denominator_note(inv)
    assert "768 archived lines are 64 unique cases" in note, note
    assert "2974 independent rows" in note, note
    assert "51" not in note, note
    assert "384" not in note, note

    moved = json.loads(Path("data/inventory.md.json").read_text())
    moved["reader_lines_read"] = 999
    assert "999 archived lines" in _denominator_note(moved), _denominator_note(moved)

    disagree = json.loads(Path("data/inventory.md.json").read_text())
    for option in disagree["corpus_options"]:
        if option["id"] == "massive_intent_per_language":
            option["n_independent"] = 1234
    assert "translations" not in _denominator_note(disagree), _denominator_note(disagree)
