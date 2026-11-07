"""Task 8a: the certificate object's shape rules.

The envelope is the product: a serialized certificate without one must be
unconstructable, so the disclaimer cannot be lost by forgetting to copy a README
section (spec 10).
"""
import dataclasses
import inspect
import json

import pytest

from autorate.certificate import (CANONICALISED_BOUND_FIELDS, PUBLISHED_DECIMALS, SHAPE_VERSION,
                                  Certificate, CertificateShapeMismatch, Reason,
                                  canonicalise_bound)

_OK = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
           method="aps", backend="synthetic", qhat=0.4, autorate=0.6,
           autorate_ci=(0.55, 0.65), conditional_error_bound=0.04,
           marginal_error_bound=0.02, mean_set_size=1.05,
           n_cal=500, n_eval=500,
           envelope=("exchangeability within group assumed",), meta={})


def _ok(**kw):
    base = dict(_OK)
    base.update(kw)
    # When a test overrides only the point estimate, derive an interval that brackets it;
    # otherwise the ci guard fires first and the test measures the wrong rule.
    if "autorate" in kw and "autorate_ci" not in kw:
        a = kw["autorate"]
        base["autorate_ci"] = (max(0.0, a - 0.05), min(1.0, a + 0.05))
    return Certificate(**base)


def test_a_success_without_an_envelope_cannot_be_constructed():
    with pytest.raises(ValueError, match="envelope"):
        _ok(envelope=())


def test_a_refusal_without_a_reason_cannot_be_constructed():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason=None)


def test_a_reason_outside_the_closed_set_is_rejected():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason="because")
    # The set has five members now (I-10); a sixth invented the same way is still rejected.
    # The three near-misses are the shapes a guard written as a match in either direction --
    # `reason.startswith(member)` or `member.startswith(reason)`, rather than set membership --
    # would wave through: an extension of a real value, a truncation of one, and a real value
    # with trailing whitespace.
    for invented in ("no_automation_at_coverage_at_all", "no_automation", "n_below_min "):
        with pytest.raises(ValueError, match="reason"):
            _ok(feasible=False, reason=invented)


def test_the_fifth_member_names_the_task_and_travels_with_its_budgets():
    """I-10: `empty_feasible_set` covered two findings; the other one gets its own member.

    Constructible is the requirement here, not printable: no gate emits this reason yet (the
    `certify_*` lane owns the branch), and until one does, the two dependent plans need the
    member to be in the closed set so a refusal can be built and round-tripped with it.
    Spec 5.5/10 say what a reason travels with, so this asserts the pair (alpha, beta), the
    case counts and a non-empty envelope arrive inside the certificate rather than beside it.
    """
    c = Certificate.refused(Reason.NO_AUTOMATION_AT_COVERAGE, alpha=0.05, beta=0.05,
                            n_cal=96, n_eval=96, detail="nothing automated at coverage 0.95",
                            meta={})
    assert c.feasible is False
    assert c.reason == Reason.NO_AUTOMATION_AT_COVERAGE.value == "no_automation_at_coverage"
    assert (c.alpha, c.beta, c.n_cal, c.n_eval) == (0.05, 0.05, 96, 96), c
    assert c.envelope, "a refusal is still conditioned by assumptions"
    assert c.autorate is None and c.autorate_ci is None
    summary = c.summary()
    for required in ("no_automation_at_coverage", "alpha=0.050", "beta=0.050"):
        assert required in summary, (required, summary)


def test_a_feasible_certificate_may_not_carry_a_reason():
    with pytest.raises(ValueError, match="reason"):
        _ok(reason=Reason.N_BELOW_MIN.value)


def test_the_interval_must_bracket_the_point_estimate():
    with pytest.raises(ValueError, match="ci"):
        _ok(autorate=0.6, autorate_ci=(0.7, 0.8))
    with pytest.raises(ValueError, match="ci"):
        _ok(autorate_ci=(0.55, 0.5))


def test_the_refusal_mass_is_derived_from_the_automation_rate_not_supplied():
    # R-17 + R-20: every evaluated case is empty, singleton, or multi-label, so
    # refusal = 1 - autorate. It used to be a second field guarded only by `<= 1`,
    # which let 0.6 + 0.01 through: one number, two owners, and a guard that missed
    # everything between.
    assert _ok(autorate=0.6).refusal_rate == 0.4
    assert _ok(autorate=1.0).refusal_rate == 0.0
    with pytest.raises(TypeError):
        Certificate(**{**_OK, "refusal_rate": 0.05})
    with pytest.raises(ValueError, match="autorate"):
        _ok(autorate=1.01)


def test_a_refusal_still_reports_n_so_small_n_is_visible_as_the_cause():
    c = Certificate.refused(Reason.N_BELOW_MIN, alpha=0.05, beta=0.05, n_cal=12, n_eval=0,
                           detail="need 60/60", meta={})
    assert c.feasible is False and c.n_cal == 12
    assert c.reason == Reason.N_BELOW_MIN.value == "n_below_min"
    assert c.autorate is None and c.autorate_ci is None
    assert c.envelope  # a refusal is still conditioned by assumptions


def test_the_joint_level_is_derived_from_delta_and_the_claim_count():
    assert _ok(delta=0.05).level == 1.0 - 3 * 0.05
    assert _ok(delta=0.01).level == 0.97
    with pytest.raises(TypeError):
        Certificate(**{**_OK, "level": 0.9})


def test_json_round_trip_is_exact_for_both_poles():
    for c in (_ok(), Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                        n_cal=500, n_eval=500, detail="none", meta={})):
        assert Certificate.from_dict(c.to_dict()) == c


def test_summary_names_the_budgets_a_refusal_failed():
    c = Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                            n_cal=500, n_eval=500, detail="none", meta={})
    assert "NOT_CERTIFIABLE" in c.summary() and "beta=0.05" in c.summary()
    assert "empty_feasible_set" in c.summary()


def test_a_feasible_summary_states_both_error_notions_and_never_conflates_them():
    s = _ok().summary()
    assert "conditional" in s and "marginal" in s
    assert "refusal" in s  # R-17
    # conditional is a rate among automated; marginal is a rate over all evaluated
    assert _ok(conditional_error_bound=0.5, marginal_error_bound=0.01).feasible is True


def test_reason_codes_are_a_closed_enumeration():
    assert {r.value for r in Reason} == {
        "n_below_min", "empty_feasible_set", "vacuous_quantile", "no_gold_labels",
        "no_automation_at_coverage"}


def _findings_in_the_enumeration_text():
    """The sentences `Reason`'s own docstring dedicates to its members, as (value, text) pairs.

    Read rather than retyped: the closed set is the only place a reader of a refusal learns
    which finding a code names, so the distinction this file guards has to live in that text
    and nowhere else. A member with no sentence, and a sentence shared by two members, are
    both visible here and nowhere else.
    """
    doc = inspect.getdoc(Reason) or ""
    members = [r.value for r in Reason]
    found, current = [], None
    for line in doc.splitlines():
        head = line.strip()
        label = next((m for m in members if head.startswith(m + ":")), None)
        if label is not None:
            current = label
            found.append([label, head[len(label) + 1:].strip()])
        elif current is not None and head:
            found[-1][1] += " " + head
        else:
            current = None
    return found


def test_the_enumeration_text_keeps_the_two_findings_i_10_split_apart():
    """One sentence per member, and the two that shared a label must not share a finding.

    I-10 is not closed by adding a member: `empty_feasible_set` and
    `no_automation_at_coverage` are different claims a reader acts on differently -- one says
    the task is not automatable at these budgets, the other says the data cannot certify it.
    The text is the only owner of that difference in this lane (no gate emits the new reason
    yet), so it is pinned here, and a plant that writes one sentence for both codes reddens it.
    """
    found = _findings_in_the_enumeration_text()
    labels = [label for label, _ in found]
    assert len(labels) == len(set(labels)) == len(list(Reason)), found
    texts = dict(found)
    task = texts[Reason.NO_AUTOMATION_AT_COVERAGE.value]
    data = texts[Reason.EMPTY_FEASIBLE_SET.value]
    assert task and data, (task, data)
    assert task != data, "the two findings collapsed back into one sentence"
    assert "not automatable" in task.lower() and "task" in task.lower(), task
    assert "cannot certify" in data.lower() and "data" in data.lower(), data


def test_marginal_can_never_exceed_conditional_because_p_auto_is_at_most_one():
    # P(wrong) = P(wrong | auto) * P(auto), and P(auto) <= 1.
    with pytest.raises(ValueError, match="marginal"):
        _ok(marginal_error_bound=0.30, conditional_error_bound=0.04)


def test_a_refusal_cannot_carry_headline_numbers():
    # A refused certificate has measured nothing. Publishing an automation rate next to
    # "NOT_CERTIFIABLE" is how a refusal gets read as a small success downstream.
    for field, value in (("autorate", 0.6), ("qhat", 0.4), ("mean_set_size", 1.1),
                        ("conditional_error_bound", 0.01), ("autorate_ci", (0.1, 0.2))):
        kw = dict(_OK)
        kw.update(feasible=False, reason=Reason.N_BELOW_MIN.value, autorate_ci=None,
                  autorate=None, qhat=None, mean_set_size=None,
                  conditional_error_bound=None, marginal_error_bound=None)
        kw[field] = value
        with pytest.raises(ValueError, match="headline numbers"):
            Certificate(**kw)


def test_mean_set_size_below_one_is_legal_because_empty_sets_are_refusals():
    # R-17 again: measured 0.948 on synthetic data; a guard demanding >= 1 would reject truth.
    assert _ok(mean_set_size=0.948, autorate=0.94).mean_set_size < 1.0


def test_a_success_missing_a_bound_is_a_readable_error_not_a_typeerror():
    # The from_dict path took `lo, hi = self.autorate_ci` before any None check, so a
    # stored certificate without its bounds raised TypeError on the CLI and escaped the
    # documented exit codes.
    for field in ("autorate_ci", "conditional_error_bound", "marginal_error_bound",
                  "mean_set_size", "qhat", "autorate"):
        kw = dict(_OK)
        kw[field] = None
        with pytest.raises(ValueError, match="must carry"):
            Certificate(**kw)


def test_the_canonical_field_list_is_exactly_the_bounds_the_shape_publishes():
    """R-121: the canonicalisation is by field NAME, and this is the list it reads.

    Two directions are checked, because either alone is satisfiable by accident. The bounds
    must all be in the list -- a published `marginal_error_bound` left raw is a number the
    runner cannot reproduce, which is the defect. And the fields NOT derived from a
    transcendental must all be out of it -- `autorate`, `mean_set_size` and `qhat` are
    quotients of integers or correctly-rounded sums, so rounding them buys nothing and buys
    it only by teaching the gate to ignore a real change in them. Adding a name here is
    therefore a deliberate edit to two files, not a widening of a catch.
    """
    floats = {f.name for f in dataclasses.fields(Certificate)
              if f.type in ("float", "Optional[float]")}
    assert set(CANONICALISED_BOUND_FIELDS) <= floats, CANONICALISED_BOUND_FIELDS
    assert set(CANONICALISED_BOUND_FIELDS) == {"conditional_error_bound",
                                              "marginal_error_bound"}
    for not_a_bound in ("autorate", "mean_set_size", "qhat", "alpha", "beta", "delta"):
        assert not_a_bound in floats, not_a_bound
        assert not_a_bound not in CANONICALISED_BOUND_FIELDS, not_a_bound


def test_the_canonical_form_is_idempotent_a_ceiling_and_swamps_the_libm_drift():
    """The gate compares canonical values with `==`, so the mapping itself is load-bearing.

    Idempotent, because the producer rounds and the artefact stores what it rounded: a
    second pass that moved a canonical value would be a gate red on its own rounding. A
    ceiling, because `tails.clopper_pearson_upper` raises `ArithmeticError` rather than
    publish a bound its own data beats, and a nearest `round` can step 5e-13 DOWN. And it
    must swallow the drift that was actually measured -- the 16th-decimal pair R-121 quotes
    -- while a 10th-decimal move stays a different number, which is the pair the reproduction
    gate depends on.
    """
    assert PUBLISHED_DECIMALS == 12
    for value in (0.7884344428029715, 0.7884344428029711, 0.9746794344808963,
                  0.139849460274226, 0.04846207170505716, 1.0, 0.0, 0.5, 2 / 3):
        canon = canonicalise_bound(value)
        assert canonicalise_bound(canon) == canon, value
        assert canon >= value, (value, canon)
        assert canon - value < 10 ** -PUBLISHED_DECIMALS + 1e-15, (value, canon)
    assert canonicalise_bound(None) is None
    assert canonicalise_bound(float("inf")) == float("inf")
    # the drift class collapses; a real move does not
    low, high = 0.7884344428029711, 0.7884344428029715
    assert canonicalise_bound(low) == canonicalise_bound(high)
    assert canonicalise_bound(high + 1e-10) != canonicalise_bound(high)
    # monotone, so `marginal <= conditional` cannot be inverted by the trip
    series = [canonicalise_bound(v / 7) for v in range(0, 7)]
    assert series == sorted(series), series


# ------------------------------------------------------------------ the shape tag (D14)

def test_the_shape_tag_is_written_at_the_version_that_can_detect_a_stale_one():
    """`to_dict` writes `"shape": 2`; `from_dict` requires it.

    A field-name diff alone cannot tell an older shape from a corrupt file, which is why D14
    ruled a tag in. Two properties are pinned together: the number on the wire, and the fact
    that the tag is metadata about the shape rather than a field of the object -- so it cannot
    become a second owner of anything the certificate already carries.
    """
    d = _ok().to_dict()
    assert d["shape"] == SHAPE_VERSION == 2, sorted(d)
    assert json.loads(_ok().to_json())["shape"] == 2, "on the wire, not only in the dict"
    refusal = Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                  n_cal=500, n_eval=500, detail="none", meta={})
    assert refusal.to_dict()["shape"] == SHAPE_VERSION, "the tag is the shape's, not the verdict's"
    assert Certificate.from_dict(d) == _ok()
    assert "shape" not in {f.name for f in dataclasses.fields(Certificate)}


def test_a_shape_that_is_not_the_required_one_is_refused_by_its_number():
    for stale in (1, 0, 3, "2"):
        d = _ok().to_dict()
        d["shape"] = stale
        with pytest.raises(CertificateShapeMismatch) as caught:
            Certificate.from_dict(d)
        text = str(caught.value)
        assert "found shape %r" % (stale,) in text, (stale, text)
        assert "required shape %r" % (SHAPE_VERSION,) in text, (stale, text)
        assert "autorate certify" in text, "actionable: name the command that rewrites it"


def test_a_missing_shape_is_blamed_as_a_shape_and_not_as_a_field_diff():
    """The exact state the committed artefacts were in before they were regenerated.

    They carry every field shape 2 carries and no field it does not, so without the tag the
    only available complaint was a key list. The tag has to be what fails, and it has to fail
    by name -- leniency for an absent `shape` is precisely what D14 exists to prevent, since a
    version tag that forgives the untagged shape certifies nothing.
    """
    d = _ok().to_dict()
    del d["shape"]
    with pytest.raises(CertificateShapeMismatch) as caught:
        Certificate.from_dict(d)
    text = str(caught.value)
    assert "found shape" in text, text
    assert "required shape %r" % (SHAPE_VERSION,) in text, text
    assert "unknown" not in text and "missing" not in text, text


def test_a_stale_artefact_reaches_an_exit_code_the_cli_already_has(tmp_path, capsys):
    """rc 1 is a defect in this repository; 0/2/3/4 is the published contract.

    The class has to be a `ValueError` for `main`'s existing arm to map it, and it must stay
    greppable in the error stream. It is deliberately not a `ReaderContractError`, which is not
    a `ValueError` so that a per-line quarantine guard cannot absorb a corpus refusal -- reusing
    it here would put a schema mismatch in the wrong arm for the wrong reason.
    """
    assert issubclass(CertificateShapeMismatch, ValueError)
    from autorate.cli import EXIT_USAGE, main
    from autorate.readers.feishu_zh import ReaderContractError

    assert not issubclass(CertificateShapeMismatch, ReaderContractError)
    assert not issubclass(ReaderContractError, ValueError), "the arm it would join is not ours"

    docs = []
    for name in ("cert_laya.json", "cert_jev.json"):
        doc = json.loads(_ok().to_json())
        del doc["shape"]
        path = tmp_path / name
        path.write_text(json.dumps(doc, sort_keys=True))
        docs.append(path)

    rc = main(["compare", str(docs[0]), str(docs[1])])
    assert rc == EXIT_USAGE == 2, (rc, rc)
    err = capsys.readouterr().err
    assert "Traceback" not in err, err
    assert err.startswith("CertificateShapeMismatch: "), err
    assert "found shape" in err and "required shape 2" in err, err
    assert "autorate certify" in err, err


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    [
        ("qhat", float("nan")),
        ("qhat", float("inf")),
        ("qhat", -0.01),
        ("conditional_error_bound", float("nan")),
        ("conditional_error_bound", -0.01),
        ("marginal_error_bound", float("nan")),
        ("marginal_error_bound", -0.01),
        ("mean_set_size", float("nan")),
        ("mean_set_size", -0.01),
        ("autorate", float("nan")),
    ],
)
def test_feasible_certificate_rejects_invalid_headline_statistics(field_name, invalid):
    with pytest.raises(ValueError, match=field_name):
        _ok(**{field_name: invalid})


@pytest.mark.parametrize(
    "interval",
    [(-0.1, 0.7), (0.5, 1.2), (float("nan"), 0.7), (0.5, float("nan"))],
)
def test_feasible_certificate_rejects_invalid_automation_interval(interval):
    with pytest.raises(ValueError, match="autorate_ci"):
        _ok(autorate_ci=interval)


def test_deserialized_certificate_cannot_bypass_numeric_checks():
    d = _ok().to_dict()
    d["conditional_error_bound"] = float("nan")
    with pytest.raises(ValueError, match="conditional_error_bound"):
        Certificate.from_dict(d)
