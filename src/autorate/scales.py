"""Decide what a published confidence number *is*, from the probabilities beside it.

G2's headline claim is an attribution claim about a third party's data: that the field the
reference README tells callers to gate on is ``confidence = 1 - H(p)/log k``. Prose in a spec
cannot be re-derived by anyone, so this module measures the distance from each candidate scale
instead, and refuses to guess when the distance does not answer the question. A name may not
claim a quantity the code never measured -- including a name this module returns.
"""
from __future__ import annotations

from typing import Sequence

from .records import entropy_confidence, max_confidence

# Served probabilities and served confidences are both rounded to 4 decimals, so agreement
# inside 1e-3 is the same quantity rather than a coincidence. The headroom is measured, not
# assumed (tests/test_scales.py re-derives both figures from the committed archive and from
# `entropy_confidence`): the narrowest gap between the two scales over laya's 192 archived
# choice records is 0.0526 -- 52x this window -- and a k=4 record reading the README's own
# 0.85 gate on the entropy scale needs p_max = 0.9609, which sits 0.1109 from the answer
# scale. A window that wide cannot straddle both scales on any record where they differ.
TOLERANCE = 1e-3


def scale_attribution(records: Sequence) -> dict:
    """Attribute one backend's published `reported_confidence` to a scale, by distance.

    Every record with a number contributes its worst-case distance to each candidate scale;
    the verdict is read off the batch maxima, so one record outside the tolerance is enough
    to stop the attribution. The four verdicts:

    * `answer_confidence` / `confidence_entropy` -- every distance to that scale is inside
      `TOLERANCE` and the other scale's worst distance is outside it.
    * `neither` -- a first-class result, not a failure. It means the published number is a
      third quantity (measured: jev's choice `confidence` sits up to 0.157 from the entropy
      scale and 0.170 from `max(p)`), or that distance cannot separate the scales at all
      (on a one-hot record both scales are 1.0, so naming either would be a coin flip).
      Nothing here picks the closer scale, because "closer" is not "is".
    * `absent` -- no record carried a number. Reported as absent and never as a distance of
      0: an absent field is "this backend publishes nothing to attribute", while a 0 distance
      is a match, and conflating them manufactures a false attribution.

    The dict carries the two maxima and the tolerance beside the verdict so a caller can
    publish the evidence rather than the label alone.
    """
    dev_answer: list = []
    dev_entropy: list = []
    for r in records:
        reported = (r.scores or {}).get("reported_confidence")
        if reported is None or len(r.probs) < 2:
            continue
        dev_answer.append(abs(reported - max_confidence(r.probs)))
        dev_entropy.append(abs(reported - entropy_confidence(r.probs)))
    if not dev_answer:
        return {"n": 0, "max_dev_answer": None, "max_dev_entropy": None,
                "verdict": "absent", "tolerance": TOLERANCE}
    da, de = max(dev_answer), max(dev_entropy)
    near_answer, near_entropy = da <= TOLERANCE, de <= TOLERANCE
    if near_answer and not near_entropy:
        verdict = "answer_confidence"
    elif near_entropy and not near_answer:
        verdict = "confidence_entropy"
    else:
        # Either matches no scale, or both match every scale at once; neither is attributable.
        verdict = "neither"
    return {"n": len(dev_answer), "max_dev_answer": da, "max_dev_entropy": de,
            "verdict": verdict, "tolerance": TOLERANCE}
