"""The contamination probe: a stratified delta-hat, an interval, and a refusal when the strata
are not real.

What this suite CANNOT detect, stated because the probe is a diagnostic and the honest failure of a
diagnostic is to look like a measurement:

* it cannot produce a real number. Nothing in the committed corpus declares training membership
  (measured: no `in_training` key in `data/records_feishu.jsonl`, in `data/cert_laya.json` or in
  `data/cert_jev.json`, and nothing in `src/` writes one), so every arithmetic assertion below runs
  on constructed counts and is labelled as constructed. The refusal tests are the ones with real
  subjects, and they are the finding.
* it cannot tell a true declaration from a sincere false one. `in_training_by` and its `evidence`
  are checked for presence, for not being this probe's own output, and for not naming a field that
  lives inside the archive (`repeat`, `seed`, `u`, `id`) -- the derivation the brief names as
  forbidden. A producer that declares membership from a manifest that is simply wrong passes every
  guard here.
* it cannot see a case that was split across the two strata under two different record ids. The
  disjointness check compares the ids the certifier published in `meta.eval_ids`; two ids for one
  case look like two cases, and the strata then share an observation invisibly.
* it cannot see the *magnitude* of leakage, only the difference in observed error rates between the
  two strata, and a difference can come from anything that differs between the strata. That is why
  `claim` is False in every result, and why the interval is a statement about the estimate rather
  than a licence to act.
"""
import json
from pathlib import Path

import pytest

from autorate.certificate import Certificate, Reason
from autorate.contamination import (DERIVED_MEMBERSHIP_FIELDS, IN_TRAINING_BY, IN_TRAINING_KEY,
                                    MIN_CASES_PER_STRATUM, N_PIECES, PROBE_DELTA, stratified)

REPO = Path(__file__).resolve().parents[1]
LAYA_CERT = REPO / "data" / "cert_laya.json"
JEV_CERT = REPO / "data" / "cert_jev.json"
RECORDS = REPO / "data" / "records_feishu.jsonl"

# the committed archive's own exclusion census, measured from the bytes and from both artefacts
NOUL_ROWS, CHOICE_ROWS, ROWS = 1536, 383, 1919
SKIPPED_WRONG_QTYPE = 768


def _stratum(cases, wrong, *, in_training=True, declared_by="laya split manifest v1",
             evidence="research/splits/frozen_holdout.json", by=None, skipped_no_gold=0,
             skipped_wrong_qtype=0, eval_ids=None, backend="synthetic", alpha=0.05, beta=0.05,
             delta=PROBE_DELTA, method="aps", feasible=True, reason="empty_feasible_set",
             **extra_meta):
    """A stratum as a real `Certificate` carrying constructed case counts and a membership claim.

    The counts use the case-denominated names `case_count.count_outcome` publishes; this helper
    invents no denominator of its own and `stratified` reads no other. `feasible=False` goes through
    the shape owner's own `Certificate.refused`, which is how the committed artefacts are shaped.
    """
    meta = {"automated_cases": cases, "erroneous_cases": wrong, "n_eval_cases": cases,
            "skipped_no_gold": skipped_no_gold, "skipped_wrong_qtype": skipped_wrong_qtype,
            IN_TRAINING_BY: ({"declared_by": declared_by, "evidence": evidence}
                             if by is None else by),
            "eval_ids": list(eval_ids if eval_ids is not None
                             else ["case-%03d" % i for i in range(cases)])}
    meta[IN_TRAINING_KEY] = in_training
    meta.update(extra_meta)
    if not feasible:
        return Certificate.refused(_REASONS[reason], alpha=alpha, beta=beta, n_cal=200, n_eval=200,
                                   detail="constructed", delta=delta, backend=backend,
                                   method=method, meta=meta)
    return Certificate(feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta,
                       method=method, backend=backend, qhat=0.9, autorate=0.5,
                       autorate_ci=(0.4, 0.6), conditional_error_bound=0.2,
                       marginal_error_bound=0.1, mean_set_size=1.4, n_cal=200, n_eval=200,
                       envelope=("exchangeability within group assumed; no group conditioning "
                                 "applied",), meta=meta)


_REASONS = {r.value: r for r in Reason}


def _without(mapping, *keys):
    """The same certificate with a meta key removed -- the absence case, built from a real object."""
    document = mapping.to_dict()
    for key in keys:
        document["meta"].pop(key, None)
    return Certificate.from_dict(document)


def _with_meta(mapping, **updates):
    document = mapping.to_dict()
    document["meta"].update(updates)
    return Certificate.from_dict(document)


def _thin_in():
    """24 automated cases, 1 wrong: above the floor, and the smaller of the two strata."""
    return _stratum(24, 1)


def _wide_out():
    """200 automated cases, 1 wrong: the fresh stratum, under ids that cannot collide."""
    return _stratum(200, 1, in_training=False, eval_ids=["fresh-%03d" % i for i in range(200)])


def _committed(path):
    return Certificate.from_dict(json.loads(path.read_text()))


def _declared_real(cert, in_training):
    """A real certificate plus a synthetic declaration, labelled as synthetic in the evidence.

    Used only to reach the denominator guards with the corpus's own counts. It publishes nothing:
    no module in `verify`'s subject set imports this one.
    """
    return _with_meta(cert, **{IN_TRAINING_KEY: in_training,
                               IN_TRAINING_BY: {"declared_by": "constructed for the boundary tests",
                                                "evidence": "tests/test_contamination.py (NOT a "
                                                            "real split)"}})


# --------------------------------------------------------------------- the refusal, on real data

def test_the_committed_certificates_refuse_the_probe_because_nothing_declares_membership():
    """The finding, on the project's own artefacts: the probe cannot be run here yet.

    Both committed certificates are real `certify_choice` output over the committed archive. Neither
    states training membership, so the probe refuses and names `in_training` -- it does not fall back
    to inventing strata from the repeats, from the split halves, or from the backend name.
    """
    laya, jev = _committed(LAYA_CERT), _committed(JEV_CERT)
    assert IN_TRAINING_KEY not in laya.meta and IN_TRAINING_KEY not in jev.meta, sorted(laya.meta)
    with pytest.raises(ValueError, match="in_training") as excinfo:
        stratified({"laya": laya, "jev": jev})
    text = str(excinfo.value)
    assert "laya" in text and "jev" in text, text
    assert "declare" in text.lower(), text


def test_the_offline_corpus_states_no_membership_and_the_exclusion_is_named_by_count():
    """The three measured facts that make the probe un-runnable here, asserted not recalled.

    1,536 of the 1,919 archived rows are `qtype="noul"` and every one of them carries `gold = null`;
    the certifier's eligibility rule excludes them by qtype first, so both committed artefacts
    report `skipped_no_gold = 0` and `skipped_wrong_qtype = 768` per backend. A stratum built from
    the archive's rows is therefore 80% unlabelled upstream of this module, and the count that
    reaches the probe is the certificate's census -- which is exactly why the census must arrive
    printed rather than as a denominator that quietly got smaller.
    """
    rows = [json.loads(line) for line in RECORDS.read_text().splitlines() if line.strip()]
    assert len(rows) == ROWS, len(rows)
    by_qtype = {}
    for row in rows:
        by_qtype.setdefault(row["qtype"], []).append(row)
    assert len(by_qtype["noul"]) == NOUL_ROWS and len(by_qtype["choice"]) == CHOICE_ROWS, (
        {key: len(value) for key, value in by_qtype.items()})
    assert all(row["gold"] is None for row in by_qtype["noul"]), "the noul rows are unlabelled"
    assert all(IN_TRAINING_KEY not in row and IN_TRAINING_KEY not in (row.get("slices") or {})
               for row in rows), "nothing in the archive declares training membership"
    laya, jev = _committed(LAYA_CERT), _committed(JEV_CERT)
    for cert in (laya, jev):
        assert cert.meta["skipped_no_gold"] == 0, cert.meta["skipped_no_gold"]
        assert cert.meta["skipped_wrong_qtype"] == SKIPPED_WRONG_QTYPE, (
            cert.meta["skipped_wrong_qtype"])
    with pytest.raises(ValueError, match="in_training"):
        stratified({"seen": laya, "fresh": jev})


# ------------------------------------------------------------------------ the refusal, on shape

def test_a_missing_or_constant_in_training_flag_refuses_the_probe():
    """The brief's two arms: nothing stated, and the same thing stated twice.

    A constant flag is the degeneracy that matters -- one sample cut in two is still one sample --
    and it is refused with the same word, so an operator searching for `in_training` finds both.
    """
    with pytest.raises(ValueError, match="in_training"):
        stratified({"in": _without(_thin_in(), IN_TRAINING_KEY)})
    with pytest.raises(ValueError, match="in_training"):
        stratified({"in": _without(_thin_in(), IN_TRAINING_KEY),
                    "out": _without(_wide_out(), IN_TRAINING_KEY)})
    with pytest.raises(ValueError, match="in_training") as excinfo:
        stratified({"in": _thin_in(), "out": _stratum(200, 1, in_training=True,
                                                      eval_ids=["fresh-%03d" % i
                                                                for i in range(200)])})
    assert "constant" in str(excinfo.value).lower(), str(excinfo.value)
    with pytest.raises(ValueError, match="in_training"):
        stratified({"in": _stratum(24, 1, in_training="true"), "out": _wide_out()})
    with pytest.raises(ValueError, match="in_training"):
        stratified({"in": _stratum(24, 1, in_training=None), "out": _wide_out()})
    with pytest.raises(ValueError, match="in_training"):
        stratified({"in": _stratum(24, 1, in_training=1), "out": _wide_out()})


def test_a_declaration_derived_from_a_field_inside_the_archive_is_refused_by_name():
    """The specific thing this task exists to refuse: treating a repeat as a stratum.

    `repeat` is a slice key on all 1,919 committed rows, so `in_training = (repeat == 0)` is the
    cheapest way to make the probe run -- and it would compare one draw of a case against the other
    draws of the same cases, which is not a comparison at all. `seed` and `u` are the same trap one
    field over, and `id` is the leak a split causes when it ignores case identity.
    """
    for field in DERIVED_MEMBERSHIP_FIELDS:
        cert = _stratum(24, 1, by={"declared_by": "derived here",
                                   "evidence": "row.%s == 0" % field})
        with pytest.raises(ValueError, match="in_training") as excinfo:
            stratified({"in": cert, "out": _wide_out()})
        assert field in str(excinfo.value), str(excinfo.value)
    assert set(DERIVED_MEMBERSHIP_FIELDS) >= {"repeat", "seed", "u", "id"}, DERIVED_MEMBERSHIP_FIELDS


def test_a_declaration_with_no_source_is_refused_and_the_probe_may_not_declare_its_own_strata():
    """`in_training: True` is a claim; who stated it and where is the evidence.

    A flag with no source lets the caller's expectation become the stratum, and a declaration this
    probe wrote itself would be a loop -- the diagnostic certifying its own input.
    """
    cases = {
        "blank source": _stratum(24, 1, by={"declared_by": "  ", "evidence": "x"}),
        "no source block": _without(_thin_in(), IN_TRAINING_BY),
        "self-declared": _stratum(24, 1, declared_by="autorate.contamination"),
        "not a mapping": _stratum(24, 1, by="the split manifest says so"),
        "no evidence": _stratum(24, 1, by={"declared_by": "who", "evidence": ""}),
    }
    for name, cert in cases.items():
        with pytest.raises(ValueError, match="in_training") as excinfo:
            stratified({"in": cert, "out": _wide_out()})
        assert "declar" in str(excinfo.value).lower(), (name, str(excinfo.value))


def test_a_pair_from_two_different_rules_is_refused_because_delta_would_mix_two_changes():
    """Two numbers from two rules are not a pair -- `certificate.py` already says that of backends.

    Same method, same coverage level, same budget, same subject: otherwise the strata differ by the
    rule and the sign of delta_hat says nothing about membership.
    """
    for kwargs in ({"method": "lac"}, {"alpha": 0.1}, {"beta": 0.1}, {"delta": 0.01},
                   {"backend": "other"}):
        with pytest.raises(ValueError, match="same|compar") as excinfo:
            stratified({"in": _stratum(24, 1, **kwargs), "out": _wide_out()})
        assert "in_training" not in str(excinfo.value), "the declaration is not what failed here"


def test_a_third_stratum_is_refused_because_the_probe_carries_no_multiplicity_correction():
    """Spec 8.1's own failure mode: a worst-of-G figure without the correction is a false claim.

    The correction is B3 Task 2's owner (`correction.bonferroni`), which does not exist in the tree
    yet (measured: no `src/autorate/correction.py`), so three strata here would be two uncorrected
    comparisons wearing one name. Refusing is the honest move; silently comparing pairs is not.
    """
    third = _stratum(60, 2, in_training=False, eval_ids=["t-%03d" % i for i in range(60)])
    with pytest.raises(ValueError, match="two") as excinfo:
        stratified({"in": _thin_in(), "out": _wide_out(), "extra": third})
    assert "correction" in str(excinfo.value).lower(), str(excinfo.value)
    with pytest.raises(ValueError, match="two"):
        stratified({"in": _thin_in()})
    with pytest.raises(ValueError, match="mapping"):
        stratified([_thin_in(), _wide_out()])
    with pytest.raises(ValueError, match="mapping"):
        stratified(None)


# ------------------------------------------------------------------ the refusal, on denominators

def test_the_case_floor_is_stated_in_cases_and_bites_at_the_stated_number():
    """20 cases is the floor, and the boundary is the assertion -- an unfindable threshold is a
    decoration. At the floor's own per-piece level the best-case two-sided exact interval spans
    0.19676 at 20 cases and 0.20597 at 19 (measured through `tails.clopper_pearson_upper`), so 20 is
    the smallest case count whose best case is under 0.20.

    What this cannot detect: that 0.20 is the wrong width to demand of a diagnostic. That is a design
    choice, stated here rather than hidden inside a constant.
    """
    assert MIN_CASES_PER_STRATUM == 20
    with pytest.raises(ValueError, match="thin") as excinfo:
        stratified({"in": _stratum(19, 0), "out": _wide_out()})
    assert "19 cases" in str(excinfo.value), str(excinfo.value)
    assert "in" in str(excinfo.value), str(excinfo.value)
    assert stratified({"in": _stratum(20, 0), "out": _wide_out()})["n_cases_in"] == 20
    with pytest.raises(ValueError, match="thin"):
        stratified({"in": _thin_in(),
                    "out": _stratum(19, 0, in_training=False,
                                    eval_ids=["f-%02d" % i for i in range(19)])})


def test_the_case_floor_refuses_the_committed_laya_stratum_on_its_real_denominator():
    """Real counts, synthetic declaration: the corpus's own laya stratum is 2 cases.

    `data/cert_laya.json` measured 2 automated cases against jev's 32, so even a genuine membership
    declaration could not run the probe on laya today -- and the two artefacts are different
    backends besides, which is a second refusal the real corpus hits. This is the floor and the
    comparability rule doing work on the project's own arithmetic, not on a fixture chosen to clear
    them.
    """
    laya = _declared_real(_committed(LAYA_CERT), True)
    jev = _declared_real(_committed(JEV_CERT), False)
    assert laya.meta["automated_cases"] == 2 and jev.meta["automated_cases"] == 32
    with pytest.raises(ValueError, match="comparable") as pair:
        stratified({"seen": laya, "fresh": jev})
    assert "backend" in str(pair.value), str(pair.value)
    fresh = _stratum(200, 1, in_training=False, backend="laya",
                     eval_ids=["fresh-%03d" % i for i in range(200)])
    with pytest.raises(ValueError, match="thin") as excinfo:
        stratified({"seen": laya, "fresh": fresh})
    text = str(excinfo.value)
    assert "2 cases" in text and "seen" in text, text


def test_a_zero_denominator_is_a_refusal_and_not_a_division_by_zero():
    """A stratum that automated nothing has no error rate, and the honest answer is not 0.0.

    `erroneous / automated` with `automated == 0` would raise `ZeroDivisionError`, which has no exit
    code in this project (rc 1 is unreachable by contract), so it is refused as a usage error at the
    raising site instead -- the shape R-115 rules on.
    """
    with pytest.raises(ValueError, match="no automated case") as excinfo:
        stratified({"in": _stratum(0, 0, eval_ids=[]), "out": _wide_out()})
    assert not isinstance(excinfo.value, ZeroDivisionError)
    assert "0" in str(excinfo.value), str(excinfo.value)
    with pytest.raises(ValueError, match="no automated case"):
        stratified({"in": _thin_in(),
                    "out": _stratum(0, 0, in_training=False, eval_ids=[])})


def test_record_counts_masquerading_as_case_counts_are_refused():
    """The denominator must be a case count, or the interval is paid for by rows.

    The committed archive measures the pair a caller can confuse: jev carries 96 automated RECORDS
    over 32 automated CASES, so reading the row count as the sample triples the evidence claimed.
    `erroneous_cases <= automated_cases <= n_eval_cases` is the published identity that catches it.
    """
    confused = _with_meta(_thin_in(), automated_cases=96, n_eval_cases=24)
    with pytest.raises(ValueError, match="case") as excinfo:
        stratified({"in": confused, "out": _wide_out()})
    assert "96" in str(excinfo.value), str(excinfo.value)
    with pytest.raises(ValueError, match="case"):
        stratified({"in": _stratum(24, 30), "out": _wide_out()})
    missing = _without(_thin_in(), "automated_cases")
    with pytest.raises(ValueError, match="case"):
        stratified({"in": missing, "out": _wide_out()})


def test_two_strata_that_share_a_case_are_refused_as_leakage():
    """One observation inside both strata makes the difference meaningless, not conservative.

    Compared on the ids the certifier published in `meta.eval_ids`; a case split under two ids stays
    invisible (module docstring), which is why the refusal names the ids it did find.
    """
    in_cert = _stratum(24, 1, eval_ids=["shared-%02d" % i for i in range(24)])
    out_cert = _stratum(200, 1, in_training=False,
                        eval_ids=["shared-%02d" % i for i in range(3)]
                        + ["fresh-%03d" % i for i in range(197)])
    with pytest.raises(ValueError, match="both strata") as excinfo:
        stratified({"in": in_cert, "out": out_cert})
    assert "shared-00" in str(excinfo.value), str(excinfo.value)
    with pytest.raises(ValueError, match="eval_ids"):
        stratified({"in": _without(_thin_in(), "eval_ids"), "out": _wide_out()})


# ------------------------------------------------------------------------- the arithmetic

def test_delta_hat_carries_an_interval_and_says_which_direction_is_worse():
    """The brief's own test, assertions verbatim.

    24 cases with 1 wrong against 200 cases with 1 wrong -- constructed counts, labelled as
    constructed in the module docstring, because no real strata exist yet.
    """
    thin_in, wide_out = _thin_in(), _wide_out()
    d = stratified({"in": thin_in, "out": wide_out})
    assert d["interval"][0] <= d["delta_hat"] <= d["interval"][1]
    assert "diagnostic" in d["interpretation"] and "proof" in d["interpretation"].lower()
    assert d["claim"] is False, "no threshold on delta_hat is licensed by these numbers"


def test_the_point_estimate_and_the_two_rates_are_one_subtraction_of_two_published_quotients():
    """R_in, R_out and delta_hat come out of the counts, and nothing here averages a bound.

    Asserted against the counts themselves, so a later edit that subtracted the two strata's
    certificate `conditional_error_bound`s -- bounds, not rates -- would go red here. The
    direction test is the other half: an in-training stratum that is WORSE is not the contamination
    signature, and the result has to say which stratum is worse instead of leaving a reader to guess
    the sign convention.
    """
    d = stratified({"in": _thin_in(), "out": _wide_out()})
    assert d["R_in"] == pytest.approx(1 / 24.0), d["R_in"]
    assert d["R_out"] == pytest.approx(1 / 200.0), d["R_out"]
    assert d["delta_hat"] == pytest.approx(d["R_in"] - d["R_out"])
    assert d["delta_hat"] > 0 and d["worse"] == "in", (
        "the in-training stratum is the worse one here, which is NOT the contamination signature")
    assert "out" in d["expected_under_contamination"].lower()
    clean = stratified({"in": _stratum(24, 0),
                        "out": _stratum(200, 40, in_training=False,
                                        eval_ids=["f%d" % i for i in range(200)])})
    assert clean["delta_hat"] < 0 and clean["worse"] == "out", clean["delta_hat"]
    assert clean["n_cases_in"] == 24 and clean["n_cases_out"] == 200, clean


def test_the_lower_tail_is_a_second_inversion_and_not_a_doubled_upper_tail():
    """A two-sided interval needs both tails; faking it by doubling one is the named defect.

    The lower tail is the exact bound on the COMPLEMENT count, `1 - upper(n-k, n, piece)`: a
    different binomial inverted, not a mirrored gap. Measured on 1 wrong of 24 cases the exact lower
    bound is 0.000524 while the mirrored upper would sit at -0.15460, below zero. The strata here put
    the fake interval's lower end more than 0.05 below the true one, so an edit that mirrored a tail
    cannot pass. What this cannot detect: that the Minkowski combination of two single-parameter
    intervals is conservative for a difference -- it is wider than the exact two-sided interval on
    `p_in - p_out`, and the interpretation says so instead of pretending otherwise.
    """
    d = stratified({"in": _thin_in(), "out": _wide_out()})
    lo, hi = d["interval"]
    assert lo <= d["delta_hat"] <= hi
    assert hi - lo > 0.2, "the interval is wide, and saying so is the point"
    fake_lo = d["delta_hat"] - ((d["rate_upper_in"] - d["R_in"]) + (d["rate_upper_out"] - d["R_out"]))
    assert fake_lo < lo - 0.05, (fake_lo, lo)
    assert d["rate_lower_in"] == pytest.approx(0.000524, abs=1e-6), d["rate_lower_in"]
    assert d["rate_lower_in"] <= d["R_in"] <= d["rate_upper_in"], d
    assert d["rate_lower_out"] <= d["R_out"] <= d["rate_upper_out"], d
    assert "conservative" in d["interpretation"].lower(), d["interpretation"]


def test_the_interval_is_paid_for_by_four_named_single_tail_pieces():
    """Two strata, two tails each: four claims, one union-bound split, and the level derived.

    The split is `delta / N_PIECES` with `N_PIECES = 4` counted from those four named bounds. It is
    the same shape `certificate.N_CLAIMS` applies to a certificate's three claims, and deliberately
    not that number: a certificate's claims and a probe's claims are different sets. At the default
    budget every piece is 0.0125, under the 0.5 `tails.clopper_pearson_upper` requires before it
    asserts its own bracketing invariant -- so the interval contains the observed rates with no
    tolerance of this module's own, and R-127's precision constants stay with their owners.
    """
    d = stratified({"in": _thin_in(), "out": _wide_out()})
    assert d["n_pieces"] == N_PIECES == 4
    assert d["piece"] == pytest.approx(PROBE_DELTA / N_PIECES)
    assert d["level"] == pytest.approx(1.0 - PROBE_DELTA)
    assert d["rate_upper_in"] > d["rate_upper_out"], "the thin stratum's bound is the loose one"
    # a probe asked for LESS confidence (the larger tail budget) gets the NARROWER interval, and the
    # one asked for more confidence gets the wider one: the direction a reader gets backwards
    looser = stratified({"in": _thin_in(), "out": _wide_out()}, delta=0.20)
    assert looser["piece"] == pytest.approx(0.20 / N_PIECES)
    assert looser["interval"][0] > d["interval"][0], (looser["interval"], d["interval"])
    assert looser["interval"][1] < d["interval"][1], (looser["interval"], d["interval"])
    hungrier = stratified({"in": _thin_in(), "out": _wide_out()}, delta=0.0125)
    assert hungrier["interval"][0] < d["interval"][0], hungrier["interval"]
    assert hungrier["interval"][1] > d["interval"][1], hungrier["interval"]
    assert hungrier["level"] == pytest.approx(1.0 - 0.0125)
    for bad in (0.0, 1.0, 2.0, -0.5):
        with pytest.raises(ValueError, match="delta"):
            stratified({"in": _thin_in(), "out": _wide_out()}, delta=bad)


def test_the_exclusion_census_is_carried_into_the_result_and_its_absence_is_a_refusal():
    """A stratum that states no drop census cannot be compared: silence is the failure mode.

    1,536 of the 1,919 archived rows are `noul` with `gold = null`, and both committed artefacts
    report `skipped_wrong_qtype = 768` for their own backend. A stratum that reports no exclusions
    either saw only eligible rows or filtered something without saying what, and the probe cannot
    tell those apart -- so it requires the census and prints it.
    """
    d = stratified({"in": _stratum(24, 1, skipped_no_gold=NOUL_ROWS,
                                   skipped_wrong_qtype=SKIPPED_WRONG_QTYPE),
                    "out": _wide_out()})
    assert d["exclusions"]["in"]["skipped_no_gold"] == NOUL_ROWS, d["exclusions"]
    assert d["exclusions"]["out"]["skipped_wrong_qtype"] == 0, d["exclusions"]
    assert str(NOUL_ROWS) in d["interpretation"], d["interpretation"]
    assert str(SKIPPED_WRONG_QTYPE) in d["interpretation"], d["interpretation"]
    with pytest.raises(ValueError, match="skipped_no_gold"):
        stratified({"in": _without(_thin_in(), "skipped_no_gold"), "out": _wide_out()})
    with pytest.raises(ValueError, match="skipped_wrong_qtype"):
        stratified({"in": _thin_in(), "out": _without(_wide_out(), "skipped_wrong_qtype")})


def test_a_refused_stratum_is_usable_evidence_and_says_that_it_is():
    """The probe reads observed counts, and both committed certificates are refusals.

    A refused certificate certifies nothing, so a delta built from two of them is a statement about
    observations rather than about certified rules, and the result has to carry that qualifier
    instead of printing the sentence it would print for feasible strata.
    """
    d = stratified({"in": _stratum(24, 1, feasible=False),
                    "out": _stratum(200, 1, in_training=False, feasible=False,
                                    eval_ids=["fresh-%03d" % i for i in range(200)])})
    assert d["feasible"] == {"in": False, "out": False}, d["feasible"]
    assert "refus" in d["interpretation"].lower(), d["interpretation"]
    assert d["claim"] is False
    assert d["reason"] == {"in": "empty_feasible_set", "out": "empty_feasible_set"}, d["reason"]


def test_no_threshold_on_delta_hat_is_licensed_even_when_the_interval_excludes_zero():
    """The strongest-looking evidence still buys nothing.

    200 in-training cases with 20 wrong against 200 fresh cases with 2 wrong separates cleanly and
    the interval's lower end is above zero -- and `claim` stays False, because the numbers can say
    the strata differ and not that the difference is leakage. A plant that set `claim` from the
    interval excluding zero is exactly what this assertion is for.
    """
    d = stratified({"in": _stratum(200, 20),
                    "out": _stratum(200, 2, in_training=False,
                                    eval_ids=["fresh-%03d" % i for i in range(200)])})
    assert d["interval"][0] > 0.0, d["interval"]
    assert d["claim"] is False
    assert d["delta_hat"] > 0 and d["worse"] == "in", d
    assert "not a proof" in d["interpretation"].lower(), d["interpretation"]


def test_the_interpretation_never_reads_as_an_immunity_claim():
    """A prose guard on the probe's own output line, in the shape of the plan's Task 2 guard.

    The forbidden list only grows; narrowing it to let a draft pass would be the defect. The line
    must name what it is (a diagnostic), what it is not (a proof), and the assumption the whole
    comparison rests on -- that membership was declared rather than inferred.
    """
    forbidden = ("immune", "immunity", "no contamination", "contamination-free", "proves",
                 "guarantees", "definitely", "regardless of")
    d = stratified({"in": _thin_in(), "out": _wide_out()})
    low = d["interpretation"].lower()
    for pattern in forbidden:
        assert pattern not in low, (pattern, d["interpretation"])
    assert "diagnostic" in low and "proof" in low
    assert "declared" in low, low
    assert str(d["n_cases_in"]) in d["interpretation"], d["interpretation"]


def test_the_probe_reads_the_denominators_the_certifier_published_and_counts_nothing_itself():
    """No second counter and no second interval: the owners are `case_count` and `tails`.

    The probe imports no record-level counting and calls `clopper_pearson_upper` for every bound, so
    a row count cannot become a denominator here and no binomial machinery is re-implemented. The
    source-text arms are how that is checked, rather than by suppressing a lint rule or adding an
    ignore list -- the two moves this repository has already ruled out.
    """
    moved = stratified({"in": _stratum(24, 3), "out": _wide_out()})
    assert moved["R_in"] == pytest.approx(3 / 24.0), moved["R_in"]
    assert moved["delta_hat"] > stratified({"in": _thin_in(), "out": _wide_out()})["delta_hat"]
    source = (REPO / "src" / "autorate" / "contamination.py").read_text()
    assert "count_outcome(" not in source, "the probe must not count cases a second time"
    assert "binom_cdf" not in source, "the binomial machinery has one owner: tails.py"
    assert source.count("clopper_pearson_upper") >= 2, "both tails go through the owner"


class TestFromCounts:
    """`from_counts` is the probe's aggregate door: two strata of (errors, cases), no certificate.

    Why this exists beside `stratified`: spec section 9 asks for `delta_hat` with an interval, and the only
    in-training-vs-held-out census that exists at all is upstream's own per-suite aggregate results, which
    carry `n` and `accuracy` and no per-case probabilities. A certificate cannot be built from them, so the
    alternative was to state the gap without the library that owns the interval arithmetic. This takes the
    counts and reuses `_exact_two_sided`, so the pieces, the level and the reflection of the lower tail have
    exactly one owner, and it keeps `claim: False` because an aggregate gap is a diagnostic by construction.
    """

    def test_the_gap_and_its_interval_come_from_the_two_strata_counts(self):
        from autorate.contamination import from_counts

        out = from_counts(in_stratum={"errors": 300, "cases": 6000},
                          out_stratum={"errors": 1500, "cases": 6000})
        assert out["R_in"] == 0.05, out
        assert out["R_out"] == 0.25, out
        assert out["delta_hat"] == out["R_in"] - out["R_out"], out
        low, high = out["interval"]
        assert low < out["delta_hat"] < high, out
        assert high - low <= 0.05, out
        assert out["claim"] is False, out

    def test_a_count_that_is_not_an_integer_number_of_cases_is_refused_by_name(self):
        from autorate.contamination import from_counts

        with pytest.raises(ValueError, match="in_stratum"):
            from_counts(in_stratum={"errors": 300.5, "cases": 6000},
                        out_stratum={"errors": 1500, "cases": 6000})

    def test_errors_above_the_case_count_is_refused_as_the_impossible_thing_it_is(self):
        from autorate.contamination import from_counts

        with pytest.raises(ValueError, match="out_stratum"):
            from_counts(in_stratum={"errors": 300, "cases": 6000},
                        out_stratum={"errors": 6001, "cases": 6000})

    def test_a_stratum_thinner_than_the_published_floor_is_refused_rather_than_pooled_away(self):
        from autorate.contamination import MIN_CASES_PER_STRATUM, from_counts

        with pytest.raises(ValueError, match="in_stratum"):
            from_counts(in_stratum={"errors": 1, "cases": MIN_CASES_PER_STRATUM - 1},
                        out_stratum={"errors": 1500, "cases": 6000})

    def test_the_denominators_are_published_beside_the_rates_they_divide(self):
        from autorate.contamination import from_counts

        out = from_counts(in_stratum={"errors": 300, "cases": 6000},
                          out_stratum={"errors": 1500, "cases": 4800})
        assert out["cases"] == {"in_stratum": 6000, "out_stratum": 4800}, out
        low, high = out["strata"]["in_stratum"]["bounds"]
        assert low <= out["R_in"] <= high, out
        assert out["strata"]["in_stratum"]["errors"] == 300, out
        assert out["strata"]["out_stratum"]["cases"] == 4800, out

    def test_an_interval_wider_than_the_published_ceiling_is_refused_not_printed_as_a_result(self):
        from autorate.contamination import MAX_STRATUM_INTERVAL_WIDTH, from_counts

        with pytest.raises(ValueError, match="interval"):
            from_counts(in_stratum={"errors": 1, "cases": 21},
                        out_stratum={"errors": 20, "cases": 21})
        assert MAX_STRATUM_INTERVAL_WIDTH == 0.20

    def test_which_stratum_is_worse_is_stated_and_never_called_a_contamination_claim(self):
        from autorate.contamination import from_counts

        out = from_counts(in_stratum={"errors": 1500, "cases": 6000},
                          out_stratum={"errors": 300, "cases": 6000})
        assert out["worse"] == "in_stratum", out
        assert out["sign"] == "in-training worse", out
        assert "not a proof" in out["interpretation"], out
        assert out["claim"] is False


# -----------------------------------------------------------------------------------------------
# Cross-platform reproducibility of the published interval (CI, run 39013012554).
# -----------------------------------------------------------------------------------------------

def test_the_published_interval_is_a_function_of_grid_values_not_of_raw_libm_bits():
    """`verify` compares these numbers with `==`, so they have to be on the published grid.

    The first run of this row reddened on GitHub's Linux and passed on macOS: the artefact published
    `interval_width` 0.05514434488839934 while the same counts recomputed to 0.055144344888399005 --
    the last two bits of a double that came out of two binomial inversions. `certificate.py:145` already
    answers that class for bounds: quantise the transcendental number once, onto `PUBLISHED_DECIMALS`,
    and let everything derived from it be a correctly-rounded function of reproducible values. A value on
    that grid rounds to itself, which is what this row reads.
    """
    from autorate.certificate import PUBLISHED_DECIMALS

    doc = json.loads((REPO / "data" / "contamination_probe.json").read_text())
    low, high = doc["probe"]["interval"]
    for name, value in (("interval[0]", low), ("interval[1]", high)):
        assert round(value, PUBLISHED_DECIMALS) == value, (name, repr(value))
    # The width is NOT quantised of its own: `canonicalise_bound`'s rule is that once the transcendental
    # inputs are canonical, what is derived from them is a correctly-rounded function of reproducible
    # numbers and needs no rounding of its own. So the honest statement here is that the published width
    # is exactly the published pair's difference -- which is what makes the two a single fact instead of
    # three numbers that can each drift apart.
    assert doc["probe"]["interval_width"] == high - low, (repr(doc["probe"]["interval_width"]), repr(high - low))


def test_the_two_sided_exact_bounds_are_quantised_outwards_at_their_one_source():
    """Outward only: a lower end snapped up would shrink the interval the probe calls conservative.

    The direction is the whole content of the row. Both ends land on the same 1e-12 grid, so a check that
    only asks "is it on the grid" passes for either direction; this one compares against the unquantised
    inversion and requires the published bracket to contain it.
    """
    from autorate.certificate import PUBLISHED_DECIMALS
    from autorate.contamination import N_PIECES, _exact_two_sided
    from autorate.tails import clopper_pearson_upper

    piece = PROBE_DELTA / N_PIECES
    k, n = 1150, 6000
    raw_high = clopper_pearson_upper(k, n, piece)
    raw_low = 1.0 - clopper_pearson_upper(n - k, n, piece)
    low, high = _exact_two_sided(k, n, piece)
    assert low <= raw_low and high >= raw_high, (low, raw_low, high, raw_high)
    assert round(low, PUBLISHED_DECIMALS) == low and round(high, PUBLISHED_DECIMALS) == high, (low, high)
    assert low < high and raw_low < raw_high
