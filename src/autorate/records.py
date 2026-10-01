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
            "slices": dict(self.slices), "scores": dict(self.scores),
            "seed": self.seed, "u": self.u, "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        return cls(
            id=d["id"], qtype=d["qtype"], backend=d["backend"], repeat=int(d["repeat"]),
            options=tuple(d["options"]), probs=tuple(float(x) for x in d["probs"]),
            gold=d.get("gold"), predicted=d.get("predicted"),
            slices=dict(d.get("slices", {})), scores=dict(d.get("scores", {})),
            seed=int(d.get("seed", 0)), u=float(d.get("u", 0.0)), meta=dict(d.get("meta", {})),
        )
