"""Task 8b: turn a certificate into an action for one record. No threshold is invented here."""
import pytest

from autorate.certificate import Certificate, Reason
from autorate.certify_choice import certify_choice, split_cal
from autorate.gate import Gate
from autorate.records import Record


def _rec(probs, gold="opt0", u=0.0, qtype="choice", backend="laya", case_id=None,
         rid="x", repeat=0):
    return Record(id=rid, qtype=qtype, backend=backend, repeat=repeat, case_id=case_id,
                  options=tuple("opt%d" % i for i in range(len(probs))),
                  probs=tuple(probs), gold=gold, predicted=None, slices={},
                  scores={}, seed=13, u=u, meta={})


def _cert(qhat=0.3, feasible=True, **kw):
    if not feasible:
        return Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                   n_cal=500, n_eval=500, detail="none", meta={})
    base = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
                method="aps", backend="laya", qhat=qhat, autorate=0.5,
                autorate_ci=(0.45, 0.55), conditional_error_bound=0.04,
                marginal_error_bound=0.02, mean_set_size=1.2,
                n_cal=500, n_eval=500,
                envelope=("exchangeability within group assumed",), meta={})
    base.update(kw)
    return Certificate(**base)


def test_a_sharp_answer_in_a_singleton_set_is_automated_with_the_reason_stated():
    d = Gate(_cert()).decide(_rec([0.93, 0.02, 0.03, 0.02]))
    assert d["action"] == "auto"
    assert d["certified"] is True
    # The decision row must distinguish the coverage level from the budget from the bound
    # that actually limits an automated decision; it used to label alpha "bound".
    assert d["coverage_alpha"] == 0.05 and d["beta"] == 0.05
    assert d["error_bound"] == 0.04, d
    assert d["label"] == "opt0" and d["set"] == [0]
    assert "singleton" in d["why"]


def test_an_ambiguous_answer_escalates_rather_than_automating():
    d = Gate(_cert(qhat=0.99)).decide(_rec([0.2955, 0.2984, 0.2973, 0.1087]))
    assert d["action"] == "escalate"
    assert len(d["set"]) > 1


def test_an_empty_certified_set_is_a_named_refusal_not_zero_options():
    # Reachable because one u is shared across labels: an exact tie admits all or none.
    d = Gate(_cert(qhat=0.001)).decide(_rec([0.5, 0.5], u=0.9))
    assert d["action"] == "escalate" and d["set"] == []
    assert d["why"] == "empty certified set"


def test_a_refused_certificate_automates_nothing_at_all():
    d = Gate(_cert(feasible=False)).decide(_rec([0.99, 0.01]))
    assert d["action"] == "abstain"
    assert d["reason"] == Reason.EMPTY_FEASIBLE_SET.value
    assert d["certified"] is False and d["set"] is None


def test_the_gate_never_invents_a_threshold_for_a_refused_certificate():
    with pytest.raises(ValueError, match="authorises no threshold"):
        Gate(_cert(feasible=False)).with_qhat(0.5)


def test_with_qhat_moves_the_operating_point_without_minting_a_certificate():
    cert = _cert(qhat=0.3)
    tight = Gate(cert).with_qhat(0.05)
    assert tight.threshold == 0.05 and cert.qhat == 0.3
    # The override changes WHERE the gate cuts, never WHAT was measured. It used to
    # return a Gate holding a fresh feasible Certificate carrying the old automation
    # rate and error bounds at the new qhat -- a serialisable certificate describing a
    # threshold nobody ever ran.
    assert tight.cert is cert
    d = tight.decide(_rec([0.93, 0.02, 0.03, 0.02]))
    assert d["qhat"] == 0.05
    assert any("OVERRIDDEN" in s and "do not describe this threshold" in s
               for s in d["envelope"]), d["envelope"]
    # A warning string alone is not machine-readable certification. The
    # threshold was never evaluated, so old error bounds must not be published.
    assert d["certified"] is False
    assert d["error_bound"] is None
    assert d["coverage_alpha"] is None and d["beta"] is None
    assert d["reason"] == "operating_override_not_certified"
    assert "uncertified" in d["why"]
    assert Gate(cert).decide(_rec([0.93, 0.02, 0.03, 0.02]))["certified"] is True


@pytest.mark.parametrize("qhat", [-0.01, 1.01, float("nan"), float("inf"), "bad"])
def test_invalid_operating_overrides_are_rejected(qhat):
    with pytest.raises(ValueError, match="qhat override"):
        Gate(_cert()).with_qhat(qhat)


def test_an_override_can_change_the_action_but_not_certify_it():
    rec = _rec([0.99, 0.01], u=0.5)
    cert = _cert(qhat=0.3)
    normal = Gate(cert).decide(rec)
    changed = Gate(cert).with_qhat(0.9).decide(rec)
    assert normal["action"] == "escalate" and normal["certified"] is True
    assert changed["action"] == "auto" and changed["certified"] is False
    assert changed["error_bound"] is None
    assert cert.qhat == 0.3 and cert.conditional_error_bound == 0.04


def test_every_decision_carries_the_envelope_so_no_downstream_can_lose_it():
    # Three branches, not two: auto/escalate under a live certificate, a refusal, and
    # the abstain path -- the one a non-choice record takes, which used to go unasserted.
    cases = ((_cert(), _rec([0.6, 0.4])),
             (_cert(feasible=False), _rec([0.6, 0.4])),
             (_cert(), _rec([0.2, 0.8], gold="opt1", qtype="noul")))
    for cert, rec in cases:
        d = Gate(cert).decide(rec)
        assert d["envelope"] == list(cert.envelope) and d["envelope"], (cert, d)
    assert {Gate(c).decide(r)["action"] for c, r in cases} == {"auto", "abstain"}


def test_the_gate_does_not_need_a_gold_label_to_act():
    r = _rec([0.93, 0.02, 0.03, 0.02], gold=None)
    assert r.calibratable is False
    assert Gate(_cert()).decide(r)["action"] == "auto"


def test_a_non_choice_record_is_refused_rather_than_gated_on_the_wrong_scale():
    d = Gate(_cert()).decide(_rec([0.2, 0.8], gold="opt1", qtype="noul"))
    assert d["action"] == "abstain"
    assert "not a choice" in d["why"]
    # `reason` used to fall back to the certificate's refusal reason, so a live
    # certificate plus a noul record reported "empty_feasible_set" -- a code from the
    # closed refusal enumeration, describing something that had not happened.
    assert d["reason"] == "qtype_not_covered", d


def test_the_gate_automates_exactly_the_cases_the_certificate_counted():
    # One rule, one owner: certify_choice counted the automated cases, the gate decides
    # them. If the two disagree, the published automation rate describes a rule no
    # deployment applies -- which is the whole product claim.
    from autorate.certify_choice import certify_choice
    import random

    rng = random.Random(4)
    recs = []
    for i in range(200):
        p = [rng.random() for _ in range(4)]
        s = sum(p)
        p = [x / s for x in p]
        g = max(range(4), key=lambda j: p[j])
        recs.append(Record(id=str(i), qtype="choice", backend="laya", repeat=0,
                           options=tuple("opt%d" % j for j in range(4)), probs=tuple(p),
                           gold="opt%d" % g, predicted=None, slices={}, scores={},
                           seed=4, u=rng.random(), meta={}))
    cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=11)
    assert cert.feasible is True, cert.summary()
    _, ev, _ = split_cal(recs, 11)
    assert {r.id for r in ev} == set(cert.meta["eval_ids"])
    gate = Gate(cert)
    automated = sum(1 for r in ev if gate.decide(r)["action"] == "auto")
    assert automated == cert.meta["automated"] == round(cert.autorate * cert.n_eval)


def test_a_split_never_puts_two_repeats_of_one_case_on_opposite_sides():
    """The group is the case, not the row.

    40 cases x 3 byte-identical repeats. On the committed corpus a record-level split put
    44 of jev's 53 evaluation cases in its calibration half too, which is not a looser
    guarantee but a violated exchangeability unit.
    """
    recs = []
    for i in range(40):
        for rep in range(3):
            recs.append(_rec([0.61, 0.13, 0.13, 0.13], gold="opt0",
                             case_id="digest-%02d" % i, rid="case-%02d" % i, repeat=rep))
    cal, ev, dropped = split_cal(recs, seed=7)
    cal_keys = {r.case_id for r in cal}
    ev_keys = {r.case_id for r in ev}
    assert not (cal_keys & ev_keys), cal_keys & ev_keys
    assert len(cal_keys) + len(ev_keys) == 40
    assert len(cal) + len(ev) == 120 and not dropped["skipped_no_gold"]


def test_bounds_use_the_case_denominator_not_the_record_count():
    """A case automates only if every one of its requests does; any error voids it.

    The flattering version counted 60 records; the honest one sees 20 cases, and a
    zero-error bound at n=20 cannot meet a 0.05 budget. That the certificate refuses here
    is the point of the change.
    """
    recs = []
    for i in range(40):
        for rep in range(3):
            recs.append(_rec([0.61, 0.13, 0.13, 0.13], gold="opt0",
                             case_id="d-%02d" % i, rid="c-%02d" % i, repeat=rep))
    cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False, cert.summary()
    assert cert.meta["n_eval_cases"] == 20 and cert.meta["n_cal_cases"] == 20
    assert cert.n_eval == 60, "records are still published, just not as the denominator"
    assert cert.meta["automated_cases"] == cert.meta["n_eval_cases"]
    assert cert.meta["erroneous_cases"] == 0
    # A refusal carries no headline number by design, so the bound is checked where it is
    # published (the detail) and against the arithmetic it came from.
    from autorate.tails import clopper_pearson_upper

    case_bound = clopper_pearson_upper(0, cert.meta["n_eval_cases"], 0.05)
    assert case_bound > 0.05, case_bound
    assert str(round(case_bound, 3)) in cert.meta["detail"], cert.meta["detail"]


def test_case_buckets_are_exhaustive_so_refusal_stays_derived():
    """refusal = 1 - autorate, at the case unit, on a certificate that is neither pole.

    Two of the twenty-five evaluation cases carry a near-uniform repeat, so they cannot
    run unattended even though nothing is wrong: the refused share must be non-zero and
    below one, or this asserts an identity no data was asked to contradict.
    """
    recs = []
    for i in range(150):
        probs = ([0.25, 0.25, 0.25, 0.25] if i % 3 == 2 and (i // 3) % 7 == 0
                 else [0.61, 0.13, 0.13, 0.13])
        # u varies: with the archive's u = 0 every set is either the argmax or the whole
        # ballot, and the case buckets would be 0-or-all by construction.
        recs.append(_rec(probs, gold="opt0", case_id="c-%03d" % (i // 3),
                         rid="r-%03d" % i, repeat=i % 3, u=((i * 37) % 100) / 100.0))
    cert = certify_choice(recs, alpha=0.05, beta=0.20, seed=5)
    assert cert.feasible is True, cert.summary()
    cases, automated = cert.meta["n_eval_cases"], cert.meta["automated_cases"]
    assert 0 < automated < cases, (automated, cases)
    assert cert.meta["erroneous_cases"] == 0
    assert abs(cert.autorate - automated / cases) < 1e-12
    assert abs(cert.refusal_rate - (cases - automated) / cases) < 1e-12
    assert abs(cert.autorate + cert.refusal_rate - 1.0) < 1e-12


def test_a_certificate_gates_only_the_backend_it_was_measured_on():
    # The jev certificate applied to a laya record printed action=auto at qhat=0.0:
    # a threshold calibrated on one model's scores automating another model's traffic.
    cert = _cert()
    assert cert.backend == "laya"
    d = Gate(cert).decide(_rec([0.93, 0.02, 0.03, 0.02], backend="jev"))
    assert d["action"] == "abstain" and d["certified"] is False
    assert d["reason"] == "subject_mismatch" and d["envelope"]
    assert "not 'jev'" in d["why"] or "jev" in d["why"], d["why"]
    assert Gate(cert).decide(_rec([0.93, 0.02, 0.03, 0.02]))["action"] == "auto"


def test_the_fields_a_reviewer_needs_to_recheck_a_row_are_asserted():
    # u, qhat and method are published on every decision. They were asserted nowhere, so
    # the brief's own `d["u"] == 0.0` rule was silently dropped when its test was folded
    # into another case: a reader cannot recheck a row whose draw is not on it.
    rec = _rec([0.93, 0.02, 0.03, 0.02], u=0.0)
    d = Gate(_cert(qhat=0.3)).decide(rec)
    assert d["u"] == 0.0 and d["qhat"] == 0.3 and d["method"] == "aps", d
    # The archive carries no APS draw, so every record arrives with u = 0.0 and the set
    # is reproducible from the published row alone.
    rec2 = _rec([0.93, 0.02, 0.03, 0.02], u=0.4)
    d2 = Gate(_cert(qhat=0.3)).decide(rec2)
    assert d2["u"] == 0.4, d2
    abstain = Gate(_cert()).decide(_rec([0.2, 0.8], gold="opt1", qtype="noul", u=0.25))
    assert abstain["u"] == 0.25, abstain


def test_the_automated_label_is_reported_by_name_not_only_by_index():
    rec = _rec([0.02, 0.03, 0.93, 0.02], gold="opt2")
    d = Gate(_cert()).decide(rec)
    assert d["action"] == "auto" and d["label"] == "opt2"
