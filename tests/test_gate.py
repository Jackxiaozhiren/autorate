"""Task 8b: turn a certificate into an action for one record. No threshold is invented here."""
import pytest

from autorate.certificate import Certificate, Reason
from autorate.certify_choice import split_cal
from autorate.gate import Gate
from autorate.records import Record


def _rec(probs, gold="opt0", u=0.0, qtype="choice", backend="laya"):
    return Record(id="x", qtype=qtype, backend=backend, repeat=0,
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
                n_cal=500, n_eval=500, level=0.9,
                envelope=("exchangeability within group assumed",), meta={})
    base.update(kw)
    return Certificate(**base)


def test_a_sharp_answer_in_a_singleton_set_is_automated_with_the_reason_stated():
    d = Gate(_cert()).decide(_rec([0.93, 0.02, 0.03, 0.02]))
    assert d["action"] == "auto"
    assert d["certified"] is True and d["bound"] == 0.05 and d["beta"] == 0.05
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


def test_the_automated_label_is_reported_by_name_not_only_by_index():
    rec = _rec([0.02, 0.03, 0.93, 0.02], gold="opt2")
    d = Gate(_cert()).decide(rec)
    assert d["action"] == "auto" and d["label"] == "opt2"
