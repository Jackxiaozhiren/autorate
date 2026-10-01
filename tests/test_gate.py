"""Task 8b: turn a certificate into an action for one record. No threshold is invented here."""
import pytest

from autorate.certificate import Certificate, Reason
from autorate.gate import Gate
from autorate.records import Record


def _rec(probs, gold="opt0", u=0.0, qtype="choice"):
    return Record(id="x", qtype=qtype, backend="laya", repeat=0,
                  options=tuple("opt%d" % i for i in range(len(probs))),
                  probs=tuple(probs), gold=gold, predicted=None, slices={},
                  scores={}, seed=13, u=u, meta={})


def _cert(qhat=0.3, feasible=True, **kw):
    if not feasible:
        return Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                   n_cal=500, n_eval=500, detail="none", meta={})
    base = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
                method="aps", grid_alpha=0.05, qhat=qhat, autorate=0.5,
                autorate_ci=(0.45, 0.55), conditional_error_bound=0.04,
                marginal_error_bound=0.02, refusal_rate=0.1, mean_set_size=1.2,
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


def test_with_qhat_returns_a_new_gate_and_leaves_the_original_alone():
    cert = _cert(qhat=0.3)
    tight = Gate(cert).with_qhat(0.05)
    assert tight.qhat == 0.05 and cert.qhat == 0.3
    assert tight.cert.qhat == 0.05


def test_every_decision_carries_the_envelope_so_no_downstream_can_lose_it():
    for cert in (_cert(), _cert(feasible=False)):
        d = Gate(cert).decide(_rec([0.6, 0.4]))
        assert d["envelope"] == list(cert.envelope) and d["envelope"]


def test_the_gate_does_not_need_a_gold_label_to_act():
    r = _rec([0.93, 0.02, 0.03, 0.02], gold=None)
    assert r.calibratable is False
    assert Gate(_cert()).decide(r)["action"] == "auto"


def test_a_non_choice_record_is_refused_rather_than_gated_on_the_wrong_scale():
    d = Gate(_cert()).decide(_rec([0.2, 0.8], gold="opt1", qtype="noul"))
    assert d["action"] == "abstain"
    assert "not a choice" in d["why"]


def test_the_automated_label_is_reported_by_name_not_only_by_index():
    rec = _rec([0.02, 0.03, 0.93, 0.02], gold="opt2")
    d = Gate(_cert()).decide(rec)
    assert d["action"] == "auto" and d["label"] == "opt2"
