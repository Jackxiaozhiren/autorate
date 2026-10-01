"""The certificate object: a number, its bound, and the conditions under which it is void.

The shape is part of the product. A certificate cannot be constructed without an
envelope, so the disclaimer survives serialization instead of living in a README
someone has to remember to read (spec 10).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Reason(str, Enum):
    N_BELOW_MIN = "n_below_min"
    EMPTY_FEASIBLE_SET = "empty_feasible_set"
    VACUOUS_QUANTILE = "vacuous_quantile"
    NO_GOLD_LABELS = "no_gold_labels"


@dataclass(frozen=True)
class Certificate:
    feasible: bool
    reason: Optional[str]
    alpha: float
    beta: float
    delta: float
    method: str
    grid_alpha: Optional[float]
    qhat: Optional[float]
    autorate: Optional[float]
    autorate_ci: Optional[tuple]
    conditional_error_bound: Optional[float]
    marginal_error_bound: Optional[float]
    joint_error_bound: Optional[float]
    refusal_rate: Optional[float]
    mean_set_size: Optional[float]
    n_cal: int
    n_eval: int
    level: float
    envelope: tuple
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "envelope", tuple(self.envelope))
        if self.autorate_ci is not None:
            object.__setattr__(self, "autorate_ci", tuple(self.autorate_ci))
        if not self.envelope:
            raise ValueError("every certificate needs a non-empty envelope of assumptions")
        if self.feasible:
            if self.reason is not None:
                raise ValueError("a feasible certificate cannot carry a refusal reason")
            if self.autorate is None or self.qhat is None:
                raise ValueError("a feasible certificate must carry a number")
            if self.autorate > 1.0 + 1e-9:
                raise ValueError("autorate is a fraction of evaluated decisions: %r" % (self.autorate,))
            lo, hi = self.autorate_ci
            if not lo <= self.autorate <= hi:
                raise ValueError("ci must bracket the point estimate: %r vs %r"
                                 % (self.autorate_ci, self.autorate))
            # P(wrong) = P(wrong | auto) * P(auto) and P(auto) <= 1.
            if self.marginal_error_bound > self.conditional_error_bound + 1e-9:
                raise ValueError("marginal error bound cannot exceed the conditional one: %r > %r"
                                 % (self.marginal_error_bound, self.conditional_error_bound))
            # R-17: an empty certified set is a refusal, and refusals are part of the
            # evaluated mass, not of the automated mass.
            if self.autorate + self.refusal_rate > 1.0 + 1e-9:
                raise ValueError("autorate + refusal exceed the evaluated mass: %r + %r"
                                 % (self.autorate, self.refusal_rate))
        else:
            if self.reason is None:
                raise ValueError("a refusal must name its reason")
            if self.reason not in {r.value for r in Reason}:
                raise ValueError("unknown reason %r" % (self.reason,))

    @property
    def mean_size(self) -> Optional[float]:
        return self.mean_set_size

    @classmethod
    def refused(cls, reason: Reason, alpha: float, beta: float, n_cal: int, n_eval: int,
                detail: str, meta: Optional[dict] = None, delta: float = 0.05) -> "Certificate":
        return cls(
            feasible=False, reason=reason.value, alpha=alpha, beta=beta, delta=delta,
            method="aps", grid_alpha=None, qhat=None, autorate=None, autorate_ci=None,
            conditional_error_bound=None, marginal_error_bound=None, joint_error_bound=None,
            refusal_rate=None, mean_set_size=None,
            n_cal=n_cal, n_eval=n_eval, level=1.0 - 2.0 * delta,
            envelope=("no certificate exists, so no action is certified",
                      "exchangeability within group assumed; none of it is usable here"),
            meta={"detail": detail, **(meta or {})},
        )

    def summary(self) -> str:
        if self.feasible:
            lo, hi = self.autorate_ci
            return ("at alpha=%.3f, beta=%.3f: autorate %.3f (ci %.3f..%.3f), "
                    "conditional error <= %.3f, marginal error <= %.3f, joint <= %.3f; "
                    "refusal (empty or multi-label set) %.3f; mean set size %.2f; "
                    "level %.2f; n_cal=%d n_eval=%d"
                    % (self.alpha, self.beta, self.autorate, lo, hi,
                       self.conditional_error_bound, self.marginal_error_bound,
                       self.joint_error_bound, self.refusal_rate, self.mean_set_size,
                       self.level, self.n_cal, self.n_eval))
        return ("NOT_CERTIFIABLE: reason=%s at alpha=%.3f, beta=%.3f; n_cal=%d n_eval=%d; %s"
                % (self.reason, self.alpha, self.beta, self.n_cal, self.n_eval,
                   self.meta.get("detail", "")))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["envelope"] = list(self.envelope)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        kw = dict(d)
        kw["envelope"] = tuple(d["envelope"])
        if d.get("autorate_ci") is not None:
            kw["autorate_ci"] = tuple(d["autorate_ci"])
        return cls(**kw)
