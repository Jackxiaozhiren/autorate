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


def max_confidence(probs: Iterable[float]) -> float:
    """laya's `answer_confidence`: mass on the reported answer.

    The quantity temperature scaling fits and the one every published ECE figure is
    computed on, so it is the only scale with the property the README's gating section
    relies on ("of the answers returned at c, about c are right").
    """
    p = [float(x) for x in probs]
    return max(p) if p else 0.0


def entropy_confidence(probs: Iterable[float]) -> float:
    """laya's `confidence`: 1 - H(p)/log(k). Concentration, not accuracy.

    Its unit depends on the option count k, so one threshold across differently sized
    question sets is a unit error, and nothing here attaches an error rate to it.
    """
    p = [float(x) for x in probs]
    k = len(p)
    if k < 2:
        return 1.0
    ent = -sum(x * math.log(x) for x in p if x > 0.0)
    return max(0.0, min(1.0, 1.0 - ent / math.log(k)))


def validate(options: Sequence[str], probs: Sequence[float], gold: Optional[str] = None) -> None:
    """Raise unless (options, probs, gold) is a decision that can be certified."""
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
    if gold is not None and gold not in options:
        raise ValueError("gold %r is not one of the options" % (gold,))


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
        if self.qtype == "noul" and len(probs) == 1:
            # Upstream's four_noul answers carry a single P(true) and set confidence
            # equal to it, so a low number cannot be told apart from a confident "no".
            # Expand to two slots rather than silently accepting a scalar.
            p_true = probs[0]
            probs = [round(1.0 - p_true, 6), p_true]
            object.__setattr__(self, "options", NOUL_SLOTS if not self.options else tuple(self.options))
            object.__setattr__(self, "scores", {**self.scores, "noul_confounded_with_yes": True})
        object.__setattr__(self, "probs", tuple(probs))
        validate(list(self.options), probs, self.gold)

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
