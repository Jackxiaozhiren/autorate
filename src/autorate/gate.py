"""Turn a certificate into an action for one record.

The gate has no authority to invent a threshold: it can only apply the one a
certificate was built with, so a refusal propagates as a refusal.
"""
from __future__ import annotations

from .certificate import Certificate
from .conformal import conformal_set


class Gate:
    def __init__(self, certificate: Certificate):
        self.cert = certificate
        self.qhat = certificate.qhat if certificate.feasible else None
        self.method = certificate.method

    def with_qhat(self, qhat: float) -> "Gate":
        """A tighter or looser set size, on a copy. A refusal authorises none."""
        if not self.cert.feasible:
            raise ValueError("a refused certificate authorises no threshold; pass none")
        return Gate(Certificate(**{**self.cert.to_dict(), "qhat": float(qhat)}))

    def decide(self, record) -> dict:
        envelope = list(self.cert.envelope)
        if record.qtype != "choice":
            return {"action": "abstain", "certified": False, "set": None, "label": None,
                    "reason": self.cert.reason or "unverified",
                    "why": "not a choice question; this certificate covers choice only",
                    "u": record.u, "envelope": envelope}
        if not self.cert.feasible:
            return {"action": "abstain", "certified": False, "set": None, "label": None,
                    "reason": self.cert.reason, "why": "certificate refused",
                    "u": record.u, "envelope": envelope}
        C = conformal_set(record.probs, self.qhat, record.u, self.method)
        if len(C) == 1:
            action, why, label = "auto", "singleton %s set" % self.method.upper(), \
                record.options[C[0]]
        elif not C:
            action, why, label = "escalate", "empty certified set", None
        else:
            action, why, label = "escalate", "certified set has %d labels" % len(C), None
        return {
            "action": action, "certified": True, "bound": self.cert.alpha,
            "beta": self.cert.beta, "why": why, "set": C, "label": label,
            "u": record.u, "method": self.method, "qhat": self.qhat,
            "envelope": envelope,
        }
