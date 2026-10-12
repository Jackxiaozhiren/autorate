"""The certificate object: a number, its bound, and the conditions under which it is void.

The shape is part of the product. A certificate cannot be constructed without an
envelope, so the disclaimer survives serialization instead of living in a README
someone has to remember to read (spec 10).
"""
from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Optional


# --- the published rubric: one owner for the numbers every certificate is measured at --------
#
# Before this mapping existed, alpha/beta/seed lived in `report.py` (a module whose name says
# prose), delta had three statements (`audit.DEFAULT_DELTA`, `cli`'s `--delta` default and the
# certifier signatures), the two sample floors had three declarations and the diagnostic grid two,
# and no row said that what the suites reuse IS the published rubric. R-184 measured the consumers
# and kept the conclusion: reuse is not attribution, so an import cannot notice the day the value
# stops being the promise. Everything below is that one promise; consumers import these names and
# `test_no_module_inside_the_fence_redeclares_a_rubric_name_it_could_import` makes restating one of
# them expensive rather than silent.
#
# Why a mapping AND names. The mapping is the declaration -- the only place any of these values is
# written as a literal -- and the names are what the consumers import, because a key string spelled
# two ways is the same defect in a new costume. It is a read-only view: a consumer that wrote
# `PUBLISHED_RUBRIC["alpha"] = ...` would move every published number in its own process without
# touching a file, and no gate could see it happen.
#
# What is deliberately NOT here. `audit.DEFAULT_GATE` (0.85) is the gate G2 compares against and
# `audit.DEFAULT_GRID` is the audit's risk-coverage frontier: five points chosen to bracket that
# gate, not the 29-point coverage sweep a certificate publishes as `meta.diagnostic_curve`. They
# have another owner and another denominator, and substituting one grid for the other leaves every
# name plausible while changing which curve was measured.
PUBLISHED_RUBRIC = MappingProxyType({
    "alpha": 0.05,        # the set gate's coverage level: certify at 1 - alpha
    "beta": 0.05,         # P(wrong | automated)
    "delta": 0.05,        # the level each of the N_CLAIMS published bounds is tested at
    "seed": 7,            # the split the published artefacts were made on, not the library default
    "method": "aps",      # the nonconformity the published certificates were measured with
    "unit": "case",       # the certification unit: the CASE, never the row (R-36/R-44)
    "n_claims": 3,        # conditional bound, marginal bound, autorate interval
    "min_cal": 60,        # the smallest calibration half any bound in the family can be informative
    "min_eval": 60,       # ...and the evaluation half
    "grid": tuple(round(0.01 * i, 2) for i in range(1, 30)),
})

# The names above, spelled once. `SPLIT_SEED_DEFAULT` is the other half of a pair that must not be
# collapsed: the certifiers' own signature default is 0 (a library default, for a caller who has not
# chosen a split), while the published rubric's seed is 7. They are two facts, not one value typed
# twice -- the split is a shuffle over sorted case keys, so a seed that changes re-rolls the
# partition and moves every bound that was measured on it. Pinning both, and pinning that they
# differ, is `test_the_published_seed_and_the_library_split_default_stay_apart_on_purpose`.
ALPHA = PUBLISHED_RUBRIC["alpha"]
BETA = PUBLISHED_RUBRIC["beta"]
DELTA = PUBLISHED_RUBRIC["delta"]
SEED = PUBLISHED_RUBRIC["seed"]
METHOD = PUBLISHED_RUBRIC["method"]
UNIT = PUBLISHED_RUBRIC["unit"]
MIN_CAL = PUBLISHED_RUBRIC["min_cal"]
MIN_EVAL = PUBLISHED_RUBRIC["min_eval"]
DIAGNOSTIC_GRID = PUBLISHED_RUBRIC["grid"]
SPLIT_SEED_DEFAULT = 0


# A feasible certificate makes exactly this many claims, each tested at `delta`:
# the conditional error bound, the marginal error bound, and the automation-rate
# interval. The published joint level is 1 - N_CLAIMS * delta by the union bound, and
# the count lives in the rubric mapping so no caller can restate it differently.
N_CLAIMS = PUBLISHED_RUBRIC["n_claims"]

# --- the precision a published number is stored at -------------------------------
#
# `verify` re-derives every published number and compares it with `==`. That is an
# honest gate only if a committed number is one any C library reproduces bit for bit,
# and two families of certificate numbers are not: a Clopper-Pearson bound, from
# `tails.clopper_pearson_upper` inverting a binomial tail through `math.log`/`math.exp`
# 80 times, and the DKW half-width behind `autorate_ci`, from `tails.bound_width`
# through `math.log`. The last bits of those transcendentals are NOT identical between
# Apple libm and glibc, so at `351845e` the same commit re-derived `cert laya.meta` as
# 0.7884344428029711 where the artefact said 0.7884344428029715 -- four units in the last
# place of a double, gate red on the runner and green on the machine that wrote the file
# (ledger R-121). The artefact therefore stops storing bits nobody else can produce: a
# bound is stored at `PUBLISHED_DECIMALS`, and that canonical number is what both the
# producer and the loaded artefact hold, so the gate's comparison stays exact.
#
# Why 12 decimals. The measured inter-libm drift is 4e-16 on a bound of order 0.79, so a
# 1e-12 grid is 2500 times that drift -- about 9000 ULPs wide at that magnitude -- and it
# swamps the disagreement, while 1e-12 sits 8 orders below the 4 decimals `docs/RESULTS.md`
# renders and 6 below the 6 decimals `data/inventory.md` renders (ledger R-122: the rendered
# documents cannot see this drift at all, so canonicalising moves stored bytes and no
# published figure). Anything coarser starts eating real signal; anything finer stops
# eating the drift.
#
# Why these fields and no others. The rest of the certificate's floats are quotients of
# integers or correctly-rounded sums -- `autorate`, `mean_set_size`, `qhat`, the two
# `observed_*` ratios -- and IEEE 754 requires + - * / and sqrt to be correctly rounded,
# so those already agree bit for bit on every platform. The incident is the evidence:
# 25 of the 28 curve points matched on the runner, and every mismatch was a bound. A
# sweep over all floats would be exactly the blanket tolerance R-121 forbids, because it
# would absorb a genuinely changed automation rate as cheerfully as it absorbs a libm
# difference. Adding a name here is a deliberate edit, and
# `test_the_canonical_field_list_is_exactly_the_bounds_the_shape_publishes` is what makes
# adding one without a reason expensive.
#
# Why nearest-`round` and then a step up, rather than a bare `round`: the canonical form
# must be idempotent, because the producer rounds, the artefact stores what it rounded, and
# the gate compares the two -- so a canonical value has to canonicalise to itself. Nearest
# `round(x, 12)` is idempotent (a midpoint between grid points would be a 13-decimal
# fraction with an odd numerator over 2^13 * 5^13, hence never dyadic, so no double is ever
# exactly halfway and a second pass cannot move it), but it rounds an UPPER bound DOWN by up
# to 5e-13, and this repository does not publish a bound its own data can beat --
# `tails.clopper_pearson_upper` raises `ArithmeticError` over exactly that. So the mapping
# is the ceiling onto the grid, taken from the nearest value rather than from
# `math.ceil(x * 1e12) / 1e12`: that scale-up is not idempotent, because multiplying a
# canonical value back up can land a hair above the grid point it was made from and push it
# a further ULP on the next pass, which is a gate that reds on its own rounding. A ceiling
# is monotone, so `marginal <= conditional` survives the trip, and the most a published
# bound can move is 1e-12 -- four orders below the precision anything renders at.
PUBLISHED_DECIMALS = 12
CANONICALISED_BOUND_FIELDS = ("conditional_error_bound", "marginal_error_bound")
_GRID = 10.0 ** -PUBLISHED_DECIMALS


def canonicalise_bound(value: Optional[float]) -> Optional[float]:
    """One transcendental-derived published number, ceiled onto `PUBLISHED_DECIMALS`.

    Named `bound` on purpose: it belongs on the numbers in
    `CANONICALISED_BOUND_FIELDS`, on the `conditional_error_bound` of every row a
    refusal publishes beside them, and on the half-width that feeds `autorate_ci` --
    because that width is the last transcendental input to the interval, and once it is
    canonical both endpoints are a correctly-rounded function of reproducible numbers,
    so the interval needs no rounding of its own. It is not a general-purpose tidy-up
    for floats, and it does not belong in `tails`, whose job is the exact arithmetic.
    """
    if value is None:
        return None
    v = float(value)
    snapped = round(v, PUBLISHED_DECIMALS)
    if snapped < v:                       # nearest went down; an upper bound goes up
        snapped = round(snapped + _GRID, PUBLISHED_DECIMALS)
    return snapped


class Reason(str, Enum):
    """The closed set of refusals a certificate may name, one finding per member (spec 5.5).

    I-10 is why the set has five members and not four: `empty_feasible_set` was made to carry
    two different findings, which read as one result to anyone downstream. The enumeration's
    own text is where the difference lives -- one sentence per member, and a member with no
    sentence, or two members sharing one, is red in `tests/test_certificate_shape.py`.

    n_below_min: the calibration or evaluation half is too small for any bound in the family
        to be informative. It is the sample that is short.

    vacuous_quantile: the coverage quantile of the calibration scores is above 1, so the rule
        would certify every label whatever the data said.

    no_gold_labels: no record carries a gold label, so there is nothing to score a rule
        against and no error rate can be measured at all.

    no_automation_at_coverage: nothing automated at coverage 1 - alpha -- the TASK is not
        automatable at these budgets, and more data would not change that verdict.

    empty_feasible_set: something automated and its bound missed beta -- the DATA cannot
        certify the task at this budget, which more evaluation cases might yet do.

    A refusal travels inside the certificate with the budget pair (alpha, beta) that made it
    infeasible, its case counts and a non-empty envelope: spec 5.5's claim is that a reason
    and its budgets are fields of the returned object, not a line printed beside it.
    """
    N_BELOW_MIN = "n_below_min"
    EMPTY_FEASIBLE_SET = "empty_feasible_set"
    NO_AUTOMATION_AT_COVERAGE = "no_automation_at_coverage"
    VACUOUS_QUANTILE = "vacuous_quantile"
    NO_GOLD_LABELS = "no_gold_labels"


# --- the shape a serialized certificate was written in (D14) -------------------------
#
# `from_dict` could formerly refuse a stale artefact only by diffing field names, which cannot
# tell "written by an older shape" from "corrupted on disk". Measured at the moment this tag
# landed: the two committed certificates differ from what this build writes by exactly one
# key, and the complaint the field diff produced was `unknown ['shape'], missing []` -- a
# statement about keys, not about versions. D14 ruled the tag in for exactly that reason.
#
# The tag is a property of the SERIALIZED shape, not a field of the object: it appears in
# `to_dict`/`from_dict` alone, so no caller of `Certificate` carries it, no rubric comparison
# reads it, and it cannot become a second owner of anything the object already holds.
#
# Why 2, and why an absent key is refused rather than forgiven. Shape 1 is every artefact
# written without a tag, so the absence of the key IS the old shape; accepting it would mean
# the tag forgives precisely the shape it exists to detect, which certifies nothing.
SHAPE_VERSION = 2
SHAPE_KEY = "shape"


class CertificateShapeMismatch(ValueError):
    """A stored certificate was not written in the shape this build reads (D14).

    A `ValueError` of its own class, following the precedent for a new refusal in this
    repository (`MissingRecordField` in `records.py`, `UndeclaredGroupKey` in `groups.py`):
    `cli.main` already maps `(OSError, ValueError)` to EXIT_USAGE, so the refusal reaches a
    documented exit code instead of escaping as a traceback with rc 1, and the class name
    keeps it greppable in the error stream.

    It is deliberately NOT a `ReaderContractError`, which is a `RuntimeError` and not a
    `ValueError` precisely so the reader's per-line quarantine guard cannot absorb a corpus
    refusal (`readers/feishu_zh.py`). A schema mismatch is an input problem of a different
    kind, and reusing that class would route it through the wrong arm for the wrong reason.
    """


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
                detail: str, meta: Optional[dict] = None, delta: float = DELTA,
                backend: Optional[str] = None,
                method: str = METHOD) -> "Certificate":
        # `method` is a rubric field: compare() treats it as one, and a refusal that
        # reports "aps" while the caller asked for LAC records a rule it never ran.
        return cls(
            feasible=False, reason=reason.value, alpha=alpha, beta=beta, delta=delta,
            method=method, backend=backend, qhat=None, autorate=None, autorate_ci=None,
            conditional_error_bound=None, marginal_error_bound=None, mean_set_size=None,
            n_cal=n_cal, n_eval=n_eval,
            envelope=("no certificate exists, so no action is certified",
                      "exchangeability within group assumed; none of it is usable here"),
            meta={"detail": detail, **(meta or {})},
        )

    def summary(self) -> str:
        if self.feasible:
            lo, hi = self.autorate_ci
            if self.method == "threshold":
                # The threshold gate of spec 6.4 runs no coverage quantile and produces no sets, so
                # the sentence above would print three claims about a rule this certificate's own
                # envelope denies: "at coverage" (alpha is recorded, not used), "empty or
                # multi-label set" (its refusal is a score below lambda) and "mean set size" (its
                # mean is of scores). One renderer per rule, inside this method only -- the shape,
                # its fields and its version are Task 5's to change.
                return ("threshold rule: automate iff %s >= %.6f (alpha=%.3f is recorded and not "
                        "used by this gate), beta=%.3f: autorate %.3f (ci %.3f..%.3f), conditional "
                        "error <= %.3f, marginal error <= %.3f; refusal (no value for %s, or a "
                        "value below lambda) %.3f; mean score %.4f; joint level %.2f over %d "
                        "claims at delta=%.3f; n_cal=%d n_eval=%d"
                        % (self.meta.get("score_field", "score"), self.qhat, self.alpha, self.beta,
                           self.autorate, lo, hi,
                           self.conditional_error_bound, self.marginal_error_bound,
                           self.meta.get("score_field", "score"), self.refusal_rate,
                           self.mean_set_size,
                           self.level, N_CLAIMS, self.delta, self.n_cal, self.n_eval))
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
        # Written here and nowhere else, so a certificate and its serialization cannot
        # disagree about which shape they are in.
        d[SHAPE_KEY] = SHAPE_VERSION
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        """Read a stored certificate, and name a schema mismatch instead of crashing on it.

        A certificate written by an older shape is an INPUT problem, not a code bug: it
        used to escape as a `TypeError` with a traceback and rc 1, outside the documented
        0/2/3/4 exit-code contract, and `verify` printed nothing the reader could act on.

        The shape is checked BEFORE the field diff, so a pre-2 artefact is told it is a
        pre-2 artefact. The field-name diff alone would report `unknown ['shape'], missing []`
        for it, which names keys where the finding is a version (D14).
        """
        from dataclasses import fields

        found = d.get(SHAPE_KEY)
        if found != SHAPE_VERSION:
            named = (repr(found) if SHAPE_KEY in d else
                     "none (no %r key at all: a certificate written before shape %d existed)"
                     % (SHAPE_KEY, SHAPE_VERSION))
            # The other shape this build publishes is the severity certificate (Plan B2 Task 72), whose
            # tag lives in `severity.SEVERITY_SHAPE_VERSION` and whose field set shares nothing load-bearing
            # with this one. Naming it costs one clause and closes a wrong instruction: "regenerate it with
            # `autorate certify`" sent a reader holding an ordinal artefact to the command that cannot
            # produce it, which is the misattribution this class exists to prevent.
            foreign = sorted({name for name in ("ahat", "direction", "price_bound", "override_bound",
                                                "measured_violation") if name in d})
            raise CertificateShapeMismatch(
                "stored certificate is not in the shape this build reads: found shape %s, "
                "required shape %d%s -- regenerate it with `autorate certify`"
                % (named, SHAPE_VERSION,
                   "; it carries %s, so it is a severity certificate and `autorate severity` is its "
                   "producer" % ", ".join(foreign) if foreign else ""))
        names = {f.name for f in fields(cls)}
        unknown = sorted(set(d) - names - {SHAPE_KEY})
        defaulted = {f.name for f in fields(cls) if f.default is not MISSING}
        missing = sorted(names - set(d) - defaulted)
        if unknown or missing:
            raise ValueError(
                "stored certificate does not match the certificate shape: unknown %s, "
                "missing %s -- regenerate it with `autorate certify`" % (unknown, missing))
        kw = dict(d)
        kw.pop(SHAPE_KEY)
        kw["envelope"] = tuple(d["envelope"])
        if d.get("autorate_ci") is not None:
            kw["autorate_ci"] = tuple(d["autorate_ci"])
        return cls(**kw)
