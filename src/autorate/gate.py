"""Turn a certificate into an action for one record.

The gate has no authority to invent a threshold: it can only apply the one a
certificate was built with, so a refusal propagates as a refusal.
"""
from __future__ import annotations

from .certificate import Certificate
from .conformal import classify_set, conformal_set


class Gate:
    def __init__(self, certificate: Certificate, qhat_override=None):
        self.cert = certificate
        self.method = certificate.method
        self.qhat = certificate.qhat if certificate.feasible else None
        # An override is an OPERATING CHOICE, not a certificate. It used to return a
        # Gate holding a fresh feasible Certificate with the new qhat and the old
        # statistics, which serialized as a certificate claiming an automation rate
        # measured at a threshold nobody ran.
        self.qhat_override = None if qhat_override is None else float(qhat_override)

    @property
    def threshold(self):
        return self.qhat if self.qhat_override is None else self.qhat_override

    def with_qhat(self, qhat: float) -> "Gate":
        """Apply a different set size on a copy. It authorises nothing it did not measure."""
        if not self.cert.feasible:
            raise ValueError("a refused certificate authorises no threshold; pass none")
        return Gate(self.cert, qhat_override=qhat)

    def decide(self, record) -> dict:
        envelope = list(self.cert.envelope)
        if self.qhat_override is not None:
            envelope = envelope + [
                "set size OVERRIDDEN to qhat=%.4f (certificate measured %.4f); the "
                "published automation rate and error bounds do not describe this "
                "threshold" % (self.qhat_override, self.cert.qhat)]
        if not self.cert.feasible:
            # Ordered first on purpose: a refusal has no threshold to apply to anything,
            # so its reason is more fundamental than whose traffic this is.
            return {"action": "abstain", "certified": False, "set": None, "label": None,
                    "reason": self.cert.reason, "why": "certificate refused",
                    "u": record.u, "envelope": envelope}
        if self.cert.backend != record.backend:
            # A certificate certifies ONE model's traffic. Applying jev's threshold to a
            # laya record published "auto" for a backend that was never calibrated. The
            # test is equality rather than "skip when unknown": a mixed-subject
            # certificate (backend None) measured nobody's traffic, so it authorises
            # nothing -- leaving it unguarded made the R-29 guard inert for exactly the
            # certificate whose subject is least certain.
            return {"action": "abstain", "certified": False, "set": None, "label": None,
                    "reason": "subject_mismatch",
                    "why": "this certificate was measured on %r, not %r" % (
                        self.cert.backend, record.backend),
                    "u": record.u, "envelope": envelope}
        if record.qtype != "choice":
            return {"action": "abstain", "certified": False, "set": None, "label": None,
                    "reason": "qtype_not_covered",
                    "why": "not a choice question; this certificate covers choice only",
                    "u": record.u, "envelope": envelope}
        C = conformal_set(record.probs, self.threshold, record.u, self.method)
        kind = classify_set(C)
        if kind == "auto":
            action, why, label = "auto", "singleton %s set" % self.method.upper(), \
                record.options[C[0]]
        elif kind == "empty":
            action, why, label = "escalate", "empty certified set", None
        else:
            action, why, label = "escalate", "certified set has %d labels" % len(C), None
        return {
            # `bound` used to hold alpha -- the coverage level -- next to `beta`, which
            # is not a bound on anything either. The number that bounds an automated
            # decision is the certificate's conditional error bound, so it is on the row.
            "action": action, "certified": True, "coverage_alpha": self.cert.alpha,
            "error_bound": self.cert.conditional_error_bound,
            "beta": self.cert.beta, "why": why, "set": C, "label": label,
            "u": record.u, "method": self.method, "qhat": self.threshold,
            "envelope": envelope,
        }
