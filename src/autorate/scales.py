"""Decide what a published confidence number *is*, from the probabilities beside it.

G2's headline claim is an attribution claim about a third party's data: that the field the
reference README tells callers to gate on is ``confidence = 1 - H(p)/log k``. Prose in a spec
cannot be re-derived by anyone, so this module measures the distance from each candidate scale
instead, and refuses to guess when the distance does not answer the question. A name may not
claim a quantity the code never measured -- including a name this module returns.

One call answers one slice. `reported_confidence` is a key name, not a quantity: measured on
the committed archive, laya's choice rows publish the entropy scale under it and its noul rows
publish P(true). A batch spanning two `(backend, qtype)` slices therefore holds two fields and
has no single answer, so it is refused rather than averaged.
"""
from __future__ import annotations

import math
from typing import Sequence

from .records import entropy_confidence, max_confidence

# Served probabilities and served confidences are both rounded to 4 decimals, so agreement
# inside 1e-3 is the same quantity rather than a coincidence. The headroom is measured, not
# assumed (tests/test_scales.py re-derives both figures from the committed archive and from
# `entropy_confidence`): the narrowest gap between the two scales over laya's 192 archived
# choice records is 0.0526 -- 52x this window -- and a k=4 record reading the README's own
# 0.85 gate on the entropy scale needs p_max = 0.9609, which sits 0.1109 from the answer
# scale. Measured over those records, no row has both scales inside this window while they
# differ; that is a statement about laya's archived choice rows, not about every backend. A
# near-one-hot row (p_max 0.9995 at k=4) does sit inside it on both scales at once, and the
# outcome of meeting one is safe only because it falls into the `else` below -- it is reported
# as `neither`, never renamed to whichever scale the comparison reached first.
TOLERANCE = 1e-3


def scale_attribution(records: Sequence) -> dict:
    """Attribute one slice's published `reported_confidence` to a scale, by distance.

    The batch must be ONE slice -- one backend, one qtype, hence one `(qtype, field)`, since
    the qtype decides which upstream field the key name carries. A batch spanning slices
    raises `ValueError` naming the keys it mixed; it is deliberately not answered with
    `neither`. The gate takes the max of every row's distance, so laya's choice rows
    (decisively `confidence_entropy`) batched with its noul rows (decisively
    `answer_confidence`) would be called a number that is neither scale -- a false verdict
    about data that answers the question cleanly slice by slice. Task 4 publishes one row per
    `(backend, qtype)`, so the refused call is one no consumer needs to make.

    The verdict is a worst-case gate over whatever rows were passed: every measured row must
    sit inside `TOLERANCE` of one scale and outside it on the other. It is NOT a statement
    about any individual record. Printing "jev: `neither`" says something false for 97 of
    jev's 191 archived choice rows, each of which does match a scale; the per-record mixture
    in the returned dict is the only part of this result that may be read per record, and a
    published table must carry it beside the aggregate word. The four verdicts:

    * `answer_confidence` / `confidence_entropy` -- the worst-case distance to that scale is
      inside `TOLERANCE` and the worst-case distance to the other scale is outside it.
    * `neither` -- a first-class result, not a failure, reached from either of two shapes: the
      worst row's number is a third quantity (measured: jev's choice `confidence` sits up to
      0.157 from the entropy scale and 0.170 from `max(p)`), or the rows match both scales at
      once (on a one-hot record both scales are 1.0, so naming either would be a coin flip).
      Both are claims about the batch's worst case, not about its records. Nothing here picks
      the closer scale, because "closer" is not "is".
    * `absent` -- no row carried a number. Reported as absent and never as a distance of 0: an
      absent field is "this backend publishes nothing to attribute", while a 0 distance is a
      match, and conflating them manufactures a false attribution.

    Beside the verdict the dict carries the evidence and both denominators: `max_dev_answer`,
    `max_dev_entropy`, `tolerance`; `n_rows` (records handed over) and `n` (rows actually
    measured); and the mixture `both` / `answer_only` / `entropy_only` / `neither`, one count
    per measured row, summing to `n`.
    """
    batch = list(records)
    slice_keys = sorted({(r.backend, r.qtype) for r in batch})
    if len(slice_keys) > 1:
        raise ValueError(
            "scale_attribution takes one (backend, qtype) slice; the batch mixed %d of them: "
            "%r. Different qtypes publish different fields under the same `reported_confidence` "
            "key name, so a batch spanning them has no single scale to attribute; call this once "
            "per slice." % (len(slice_keys), slice_keys))
    # One accumulated structure, so `n` and the two maxima cannot come from different lists:
    # every entry is the (distance to max(p), distance to entropy) pair of one measured row.
    measured: list = []
    for r in batch:
        reported = (r.scores or {}).get("reported_confidence")
        if reported is None or len(r.probs) < 2:
            continue
        # `records.py` raises for a non-finite probability ("it would poison a quantile
        # silently"); the same input here poisons `max()` instead, which returns whichever
        # operand it compares first, so an absorbed NaN makes the verdict depend on row order
        # and puts nan/inf in a published maximum. Refuse it the same way the sibling does.
        if not math.isfinite(reported):
            raise ValueError("non-finite reported_confidence (%r) in a confidence scale"
                             % (reported,))
        measured.append((abs(reported - max_confidence(r.probs)),
                         abs(reported - entropy_confidence(r.probs))))
    counts = {"both": 0, "answer_only": 0, "entropy_only": 0, "neither": 0}
    for dev_answer, dev_entropy in measured:
        if dev_answer <= TOLERANCE and dev_entropy <= TOLERANCE:
            counts["both"] += 1
        elif dev_answer <= TOLERANCE:
            counts["answer_only"] += 1
        elif dev_entropy <= TOLERANCE:
            counts["entropy_only"] += 1
        else:
            counts["neither"] += 1
    if not measured:
        return {"n": 0, "n_rows": len(batch), "max_dev_answer": None, "max_dev_entropy": None,
                "verdict": "absent", "tolerance": TOLERANCE, **counts}
    da, de = max(m[0] for m in measured), max(m[1] for m in measured)
    near_answer, near_entropy = da <= TOLERANCE, de <= TOLERANCE
    if near_answer and not near_entropy:
        verdict = "answer_confidence"
    elif near_entropy and not near_answer:
        verdict = "confidence_entropy"
    else:
        # Either the worst-case row matches no scale, or the rows match both at once; neither
        # shape is attributable by distance. A batch spanning two slices never lands here --
        # it raised above, instead of being labelled `neither`.
        verdict = "neither"
    # n == rows MEASURED, not cases and not the batch. assert n_cases != n on the committed
    # archive: laya's 192 choice rows are 64 cases x 3 byte-identical repeats, and jev's 191
    # rows are 64 cases carrying 1-3 DISTINCT probability vectors each. So `n` is not a
    # binomial denominator and must never be handed to one -- and neither is `n_rows`.
    # Follow-up, blocked on `Record.from_dict` round-tripping `case_id` (owned by records.py)
    # and on Task 4's row shape: collapse to one row per case, which moves jev choice's
    # published maxima from 0.170 to 0.160 and from 0.157315 to 0.147315.
    return {"n": len(measured), "n_rows": len(batch), "max_dev_answer": da,
            "max_dev_entropy": de, "verdict": verdict, "tolerance": TOLERANCE, **counts}
