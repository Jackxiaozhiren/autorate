"""The one public data contract: a decision record, and what may be said about it.

Field names live here and nowhere else; `conformal.py` knows numbers and never these
names. Three different quantities are published by upstream under confidence-flavoured
names, so all three are modelled explicitly rather than collapsed into one field.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

QTYPES = ("choice", "score", "noul")
SUM_TOL = 5e-3  # served probabilities are rounded to 4 decimals
NOUL_SLOTS = ("false", "true")

# The fields a stored record has to state, because `Record.from_dict` reads them blind. Named here
# rather than left implicit in the constructor call, so the guard, its message and its test all read
# one list.
REQUIRED_FIELDS = ("id", "qtype", "backend", "repeat", "options", "probs")
# The fields whose absence is a shape under test or legal history rather than a defect: `gold`
# absent is a record that may be gated and never calibrated, `case_id` absent is an artefact stored
# before the field existed, and the rest carry a dataclass default. `u` landing on 0.0 when absent
# is the one entry here worth a second look -- the constructor calls the draw the certified set is
# reproducible only with -- and it is recorded, not changed, by this guard.
OPTIONAL_FIELDS = ("gold", "predicted", "case_id", "slices", "scores", "seed", "u", "meta")


class MissingRecordField(ValueError):
    """A stored record does not state a field this contract reads blind.

    Raised at the raising site -- `Record.from_dict` is the one place that holds both the row and
    the field list -- rather than by giving `cli.main` a `KeyError` arm. That is ledger R-115's
    ruling on the identical escape (`groups.py`'s `UndeclaredGroupKey(ValueError)`): `KeyError` is
    ordinary dict access everywhere in this codebase, so catching it centrally would turn unrelated
    bugs into a usage exit carrying a helpful-looking message.

    The class chosen is a `ValueError` subclass, and the two neighbouring candidates were rejected
    on purpose. It is not a bare `ValueError` because a dedicated name stays greppable and is
    separately testable -- any other `ValueError` from the constructor (a probability that does not
    close, a `gold` off the ballot) already exits 2 on this path, and a refusal an operator cannot
    tell them apart from is a refusal with no owner. It is not a `ReaderContractError` because that
    class names something else: a reader refusing a corpus *condition* (R-14), deliberately a
    `RuntimeError` so it escapes `read_archive`'s per-line `ValueError` quarantine instead of
    being filed under `malformed_line` and ending a run at rc 0 on a corpus it refused. A row that
    is not a record is not a policy refusal -- it is exactly the unreadable input the quarantine
    bucket is for, and the CLI's existing `ValueError` arm maps it to `EXIT_USAGE` (2). Both kinds
    therefore exit 2, neither escapes as rc 1, and the two failure kinds stay distinguishable by
    name.

    It is never a success path: no field is defaulted here, no row is skipped, and nothing on the
    load path (`report.load_records`, `cli._records_from`) catches it.
    """


def _missing_field_message(d: dict, missing: Sequence[str]) -> str:
    """The refusal in the two things an operator needs: which row, which field.

    The id is quoted only when the row states one: putting an id in a refusal about a row that
    states none is how a message starts asserting facts the input does not carry.
    """
    who = "record %r" % (d["id"],) if "id" in d else "a row with no 'id' field"
    return ("%s is missing %s. A stored record must state %s; only %s may be absent, and there the "
            "constructor's own default applies. The loader reads the first set blind, so an "
            "absent one is refused here rather than invented -- and not a `KeyError` handed to the "
            "operator as a traceback."
            % (who, ", ".join(repr(key) for key in missing),
               ", ".join(repr(key) for key in REQUIRED_FIELDS),
               ", ".join(repr(key) for key in OPTIONAL_FIELDS)))


def _finite_probs(probs: Iterable[float]) -> list:
    """A scale is only meaningful over a finite, non-empty distribution."""
    p = [float(x) for x in probs]
    if not p:
        raise ValueError("empty probability vector; a confidence scale over nothing is 0 by "
                         "convention and 1 by another, and neither means anything")
    if not all(math.isfinite(x) for x in p):
        raise ValueError("non-finite probability in a confidence scale")
    return p


def max_confidence(probs: Iterable[float]) -> float:
    """laya's `answer_confidence`: mass on the reported answer.

    The quantity temperature scaling fits and the one every published ECE figure is
    computed on, so it is the only scale with the property the README's gating section
    relies on ("of the answers returned at c, about c are right").
    """
    return max(_finite_probs(probs))


def entropy_confidence(probs: Iterable[float]) -> float:
    """laya's `confidence`: 1 - H(p)/log(k). Concentration, not accuracy.

    Its unit depends on the option count k, so one threshold across differently sized
    question sets is a unit error, and nothing here attaches an error rate to it.
    """
    p = _finite_probs(probs)
    k = len(p)
    if k < 2:
        raise ValueError("entropy is undefined relative to log(k) at k=%d; a one-option "
                         "decision has no confidence to report" % k)
    ent = -sum(x * math.log(x) for x in p if x > 0.0)
    return max(0.0, min(1.0, 1.0 - ent / math.log(k)))


def validate(options: Sequence[str], probs: Sequence[float], gold: Optional[str] = None,
             predicted: Optional[str] = None) -> None:
    """Raise unless (options, probs, gold, predicted) is a decision that can be certified."""
    if len(options) != len(probs):
        raise ValueError("options/probs length mismatch: %d vs %d" % (len(options), len(probs)))
    if not options:
        raise ValueError("empty option set; a certificate over nothing is a vacuity bug, not a result")
    p = [float(x) for x in probs]
    if not all(math.isfinite(x) for x in p):
        raise ValueError("non-finite probability; it would poison a quantile silently")
    if any(x < 0.0 for x in p):
        raise ValueError("negative probability")
    if abs(sum(p) - 1.0) > SUM_TOL:
        raise ValueError("probabilities do not sum to 1 within %g (got %.6f)" % (SUM_TOL, sum(p)))
    if len(set(options)) != len(options):
        raise ValueError("duplicate option keys: %r" % (list(options),))
    if len(options) < 2:
        raise ValueError("a one-option decision certifies nothing: %r" % (list(options),))
    if gold is not None and gold not in options:
        raise ValueError("gold %r is not one of the options" % (gold,))
    # `predicted` is what the automated decision would BE. Letting it name an option
    # that is not on the ballot turns into a silent wrong answer in every certificate.
    if predicted is not None and predicted not in options:
        raise ValueError("predicted %r is not one of the options" % (predicted,))


def is_hashable_key(obj: object) -> bool:
    """Whether `obj` can be a dict key. Records cannot, and that is a documented limit."""
    try:
        hash(obj)
    except TypeError:
        return False
    return True


@dataclass(frozen=True)
class Record:
    id: str
    qtype: str
    backend: str
    repeat: int
    options: tuple
    probs: tuple
    gold: Optional[str]
    predicted: Optional[str]
    # Upstream's own case identity (`request_sha256`). Repeats of one case are NOT
    # independent observations -- measured on the committed archive: laya's three repeats
    # per case carry byte-identical probability vectors, so 192 records are 64
    # observations -- and a split that ignores this puts the same case in both halves.
    case_id: Optional[str] = None
    slices: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    seed: int = 0
    u: float = 0.0
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.qtype not in QTYPES:
            raise ValueError("qtype %r not in %s" % (self.qtype, QTYPES))
        if not 0.0 <= float(self.u) < 1.0:
            raise ValueError("u must be in [0,1): the certified set is reproducible only if the draw is stored")
        object.__setattr__(self, "u", float(self.u))
        object.__setattr__(self, "options", tuple(self.options))
        probs = [float(x) for x in self.probs]
        # The three mappings are copied, not adopted: a caller who mutates the dict they
        # passed in afterwards must not be able to rewrite a certified record's slices
        # behind its back. (The record's own mappings stay mutable; to_dict copies out.)
        for name in ("slices", "scores", "meta"):
            object.__setattr__(self, name, dict(getattr(self, name)))
        if self.qtype == "noul" and len(probs) == 1:
            # Upstream's four_noul answers carry a single P(true) and set confidence
            # equal to it, so a low number cannot be told apart from a confident "no".
            # Expand to two slots rather than silently accepting a scalar -- and align
            # the pair to the slots the CALLER named, because ("true","false") and
            # ("false","true") are different records and a positional guess inverts one.
            p_true = probs[0]
            slots = tuple(self.options) if self.options else NOUL_SLOTS
            if len(slots) != 2 or set(slots) != set(NOUL_SLOTS):
                raise ValueError("a 1-probability noul record must name both slots as %s, "
                                 "in either order; got %r" % (NOUL_SLOTS, slots))
            p_false = round(1.0 - p_true, 6)
            probs = [p_false, p_true] if slots[1] == "true" else [p_true, p_false]
            object.__setattr__(self, "options", slots)
            object.__setattr__(self, "scores",
                               {**self.scores, "noul_scalar_expanded": True})
        object.__setattr__(self, "probs", tuple(probs))
        validate(list(self.options), probs, self.gold, self.predicted)

    @property
    def calibratable(self) -> bool:
        return self.gold is not None

    @property
    def k(self) -> int:
        return len(self.options)

    @property
    def gold_index(self) -> int:
        if self.gold is None:
            raise ValueError("no gold label; this record can be gated but never calibrated")
        return list(self.options).index(self.gold)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "qtype": self.qtype, "backend": self.backend,
            "repeat": self.repeat, "options": list(self.options),
            "probs": list(self.probs), "gold": self.gold, "predicted": self.predicted,
            "case_id": self.case_id,
            "slices": dict(self.slices), "scores": dict(self.scores),
            "seed": self.seed, "u": self.u, "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        """Rebuild a record from one stored line, refusing a row that states too little.

        The six names in `REQUIRED_FIELDS` are read blind, and this is where a row missing one used
        to raise `KeyError` -- rc 1, outside the 0/2/3/4 contract, for `audit`, `certify` and `gate`
        alike. See `MissingRecordField` for why the refusal is a `ValueError` of its own class.
        """
        missing = [key for key in REQUIRED_FIELDS if key not in d]
        if missing:
            raise MissingRecordField(_missing_field_message(d, missing))
        return cls(
            id=d["id"], qtype=d["qtype"], backend=d["backend"], repeat=int(d["repeat"]),
            options=tuple(d["options"]), probs=tuple(float(x) for x in d["probs"]),
            gold=d.get("gold"), predicted=d.get("predicted"),
            case_id=d.get("case_id"),
            slices=dict(d.get("slices", {})), scores=dict(d.get("scores", {})),
            seed=int(d.get("seed", 0)), u=float(d.get("u", 0.0)), meta=dict(d.get("meta", {})),
        )
