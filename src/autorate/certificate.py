"""The certificate object: a number, its bound, and the conditions under which it is void.

The shape is part of the product. A certificate cannot be constructed without an
envelope, so the disclaimer survives serialization instead of living in a README
someone has to remember to read (spec 10).
"""
from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, field
from enum import Enum
from typing import Optional


# A feasible certificate makes exactly this many claims, each tested at `delta`:
# the conditional error bound, the marginal error bound, and the automation-rate
# interval. The published joint level is 1 - N_CLAIMS * delta by the union bound, and
# the count lives here so no caller can restate it differently.
N_CLAIMS = 3


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
    # Whose model this is. A certificate that does not name its subject cannot be
    # compared with another one, and a pair of numbers from two models is not a pair.
    backend: Optional[str]
    qhat: Optional[float]
    autorate: Optional[float]
    autorate_ci: Optional[tuple]
    conditional_error_bound: Optional[float]
    marginal_error_bound: Optional[float]
    mean_set_size: Optional[float]
    n_cal: int
    n_eval: int
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
            missing = [f for f in ("autorate", "qhat", "autorate_ci", "mean_set_size",
                                   "conditional_error_bound", "marginal_error_bound")
                       if getattr(self, f) is None]
            if missing:
                raise ValueError("a feasible certificate must carry %s" % ", ".join(missing))
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
            if not 0.0 <= self.autorate <= 1.0 + 1e-9:
                raise ValueError("autorate is a fraction of evaluated decisions: %r"
                                 % (self.autorate,))
        else:
            if self.reason is None:
                raise ValueError("a refusal must name its reason")
            if self.reason not in {r.value for r in Reason}:
                raise ValueError("unknown reason %r" % (self.reason,))
            # A refused certificate has no measured quantity to report. Carrying one
            # would let a reader automate on a number the tool said it could not bound.
            carried = [f for f in ("autorate", "autorate_ci", "qhat", "mean_set_size",
                                   "conditional_error_bound", "marginal_error_bound")
                       if getattr(self, f) is not None]
            if carried:
                raise ValueError("a refusal cannot carry headline numbers: %s"
                                 % ", ".join(carried))

    @property
    def level(self) -> float:
        """1 - N_CLAIMS * delta: the joint confidence of the bounds actually published.

        Derived, because a stored `level` was a second owner of a number that is a pure
        function of `delta` -- and nothing checked that the two agreed.
        """
        return 1.0 - N_CLAIMS * self.delta

    @property
    def refusal_rate(self) -> Optional[float]:
        """1 - autorate, derived: every evaluated case is empty, singleton, or multi-label.

        It was a stored field guarded only by `autorate + refusal <= 1`, which let an
        arbitrary refusal through -- one number, one owner (R-20).
        """
        return None if self.autorate is None else 1.0 - self.autorate

    @classmethod
    def refused(cls, reason: Reason, alpha: float, beta: float, n_cal: int, n_eval: int,
                detail: str, meta: Optional[dict] = None, delta: float = 0.05,
                backend: Optional[str] = None) -> "Certificate":
        return cls(
            feasible=False, reason=reason.value, alpha=alpha, beta=beta, delta=delta,
            method="aps", backend=backend, qhat=None, autorate=None, autorate_ci=None,
            conditional_error_bound=None, marginal_error_bound=None, mean_set_size=None,
            n_cal=n_cal, n_eval=n_eval,
            envelope=("no certificate exists, so no action is certified",
                      "exchangeability within group assumed; none of it is usable here"),
            meta={"detail": detail, **(meta or {})},
        )

    def summary(self) -> str:
        if self.feasible:
            lo, hi = self.autorate_ci
            return ("at coverage %.3f (alpha=%.3f), beta=%.3f: autorate %.3f (ci %.3f..%.3f), "
                    "conditional error <= %.3f, marginal error <= %.3f; "
                    "refusal (empty or multi-label set) %.3f; mean set size %.2f; "
                    "joint level %.2f over %d claims at delta=%.3f; n_cal=%d n_eval=%d"
                    % (1.0 - self.alpha, self.alpha, self.beta, self.autorate, lo, hi,
                       self.conditional_error_bound, self.marginal_error_bound,
                       self.refusal_rate, self.mean_set_size,
                       self.level, N_CLAIMS, self.delta, self.n_cal, self.n_eval))
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
        """Read a stored certificate, and name a schema mismatch instead of crashing on it.

        A certificate written by an older shape is an INPUT problem, not a code bug: it
        used to escape as a `TypeError` with a traceback and rc 1, outside the documented
        0/2/3/4 exit-code contract, and `verify` printed nothing the reader could act on.
        """
        from dataclasses import fields

        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - names)
        defaulted = {f.name for f in fields(cls) if f.default is not MISSING}
        missing = sorted(names - set(d) - defaulted)
        if unknown or missing:
            raise ValueError(
                "stored certificate does not match the certificate shape: unknown %s, "
                "missing %s -- regenerate it with `autorate certify`" % (unknown, missing))
        kw = dict(d)
        kw["envelope"] = tuple(d["envelope"])
        if d.get("autorate_ci") is not None:
            kw["autorate_ci"] = tuple(d["autorate_ci"])
        return cls(**kw)
