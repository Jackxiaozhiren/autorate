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

# Served probabilities and served confidences are both rounded to 4 decimals, so agreement inside
# 1e-3 is the same quantity rather than a coincidence. That premise is itself an artifact reading, not
# prose: tests/test_scales.py::test_the_archive_publishes_every_served_figure_at_four_decimals checks
# that every `probs` value and every published `reported_confidence` in the committed archive equals
# its own 4-decimal rounding, and counts the 4604 probability values and 1151 published confidences it
# covered. Every figure below is either produced by a named test or arithmetic on a figure a named test
# produces, so a reader can re-derive it instead of trusting prose. "The gate test" below means
# `test_the_tolerance_sits_far_inside_the_gap_the_attribution_claims_to_tell_apart`, in
# tests/test_scales.py: it reads the committed archive and prints every p_max figure quoted here,
# including the slice size it is asked to call "laya's 192 archived choice records" (`len(laya) == 192`)
# and the headroom ratio, which is arithmetic on the gap it prints -- 0.0526 / 1e-3 = 52.6, asserted as
# the band `52 <= gap / TOLERANCE < 53`. The band's own failure mode is a moved WINDOW (measured: with
# TOLERANCE planted at 1e-4 the ratio is 526.4 and exactly that line reddens); a moved archive reddens
# the gap assertion above it first, which is why the two lines are not the same guard.
#   HEADROOM, over laya's 192 archived choice records (the gate test): the narrowest gap between
#     the two scales is 0.0526, 52x this window -- so no archived laya row is anywhere near the
#     sharpness described below, though whether some other archive holds such a row is not claimed.
#   UNIT ERROR at the README's own 0.85 gate (the gate test): a k=4 record reading 0.85 on the
#     entropy scale sits 0.1109 from the answer scale and needs p_max = 0.9609 to get there, a figure
#     pinned in tests/test_records.py::test_one_entropy_threshold_means_a_different_p_max_for_every_option_count,
#     because one figure has one owner. Over those same records no row has both scales
#     inside this window while they differ -- a statement about laya's archived choice rows, not
#     about every backend.
# The window does stop separating the scales on a very sharp k=4 row, and that phrasing invites TWO
# questions with two different answers. What holds by construction, for any window and any remainder
# shape, is the pair of PREDICATES: SOME published value is inside both radius-TOLERANCE windows
# exactly when the two scales are no further apart than 2 * TOLERANCE (that is when the windows
# intersect at all), and a row's OWN p_max is inside both exactly when the gap is no wider than
# TOLERANCE (such a row sits at distance 0 from max(p), so it carries the whole gap alone).
# Where those lines fall on the p_max axis is a FIGURE, and it depends on the remainder shape, so the
# shape is named and the gate test prints both crossings for it -- p_max on the answer, the other
# k-1 options sharing the rest EQUALLY: gap = p_max - entropy_confidence(p_max) is 0.002998 at
# p_max 0.9995, reaches 2 * TOLERANCE at p_max 0.999684 (the SOME-value line) and TOLERANCE at
# p_max 0.999855 (the OWN-p_max line). A lumpy ((1-p)/2, (1-p)/6, (1-p)/6) or sparse (all remaining
# mass on one option) remainder crosses either line 2e-5 to 8e-5 EARLIER, so it is absorbed sooner:
# the figures above understate absorption rather than overstate it, and the same test shows which
# bucket the gate actually files each row in. Meeting an absorbed row is safe only because it falls
# into the `else` below: it is reported as `neither`, never renamed to whichever scale the comparison
# reached first.
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

    The verdict is a worst-case gate over whatever rows were passed: the batch's LARGEST distance to
    one scale must sit inside `TOLERANCE` while its largest distance to the other sits outside it,
    and no part of the gate reads a row on its own. A decisive verdict therefore does not mean every
    row was decisive -- only the two maxima decide, so a batch named after one scale can still carry
    rows inside BOTH windows, or rows matching the other scale alone. It is NOT a statement about any
    individual record: printing "jev: `neither`" says something false for 97 of jev's 191 archived
    choice rows, each of which does match a scale, 74 of them by matching BOTH at once. Those counts,
    and that slice's two maxima, are measured against the committed archive in tests/test_scales.py by
    `test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides`; the
    decisive-batch-with-an-absorbed-row SHAPE they illustrate is produced separately, on two synthetic
    rows, by `test_a_decisive_verdict_does_not_mean_every_measured_row_was_decisive`. The per-record
    mixture is the only part of this result that may be read per record, and a published table must
    carry it beside the aggregate word.

    Raises `ValueError` from exactly two places, and only these two:

    * the batch spans more than one `(backend, qtype)` slice -- the check runs before any distance
      is measured, and the message names the slice keys it mixed;
    * a row that carries a `reported_confidence` at all carries one that is not finite (`nan`,
      `inf` or `-inf`), which is refused for the same reason `records.py` refuses a non-finite
      probability: `max()` would otherwise let row order decide the verdict and publish nan or inf
      as a distance.

    Anything else bad is not this function's call to make: a non-numeric `reported_confidence`
    propagates the `TypeError` its own comparison raises.

    The four verdicts:

    * `answer_confidence` / `confidence_entropy` -- the worst-case distance to that scale is
      inside `TOLERANCE` and the worst-case distance to the other scale is outside it.
    * `neither` -- a first-class result, not a failure, reached from either of two shapes: the
      worst row's number is a third quantity (measured on the committed archive, and pinned there by
      the archive test named one paragraph above --
      `test_the_archive_verdict_is_a_worst_case_gate_and_the_mixture_is_what_it_hides`, not the
      tolerance gate test of the module comment: jev's choice `confidence` sits up to 0.157315 from
      the entropy scale and up to 0.170 from `max(p)`), or the rows match both scales at
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
    # archive: laya's 192 choice rows are 64 cases x 3 repeats carrying the SAME `probs` and the SAME
    # published `reported_confidence` (they differ only in the repeat counter and its own elapsed-time
    # metadata, which is why the rows themselves are not byte-identical and the sentence may not claim
    # that), and jev's 191 rows are 64 cases carrying 1-3 DISTINCT probability vectors each. So `n` is
    # not a binomial denominator and must never be handed to one -- and neither is `n_rows`. Both
    # repeat shapes are produced by the archive test named above.
    # Follow-up, no longer blocked: `Record.from_dict` has round-tripped `case_id` since 12c87d7,
    # pinned by tests/test_records.py::test_case_id_survives_both_round_trips_because_it_is_the_bound_denominator,
    # so one-row-per-case could be measured instead of predicted. It was.
    # The pair the old comment forecast -- 0.170 to 0.160 and 0.157315 to 0.147315 -- is not what
    # collapsing to cases does; it is what collapsing to each case's FIRST ROW IN ARCHIVE ORDER does, the
    # order a reader gets by grouping the file without sorting, and it appears only because that tie-break
    # discards the row carrying each published maximum -- each case's last ROW, which is NOT its last
    # REPEAT: 52 of the 64 jev cases are not in ascending `repeat` order in the file, and keeping each
    # case's lowest repeat instead gives 0.160 and 0.150882, not this pair. Keep each case's worst row --
    # the only collapse that preserves a gate defined as a maximum over rows -- and both maxima stay
    # exactly where they are. Every figure in this sentence, the 52 and the 0.150882 included, is produced
    # by the test named below; which collapse Task 4 publishes is still its own decision, and this module
    # no longer forecasts it.
    # tests/test_scales.py::test_collapsing_jev_to_one_row_per_case_does_not_move_the_published_maxima
    return {"n": len(measured), "n_rows": len(batch), "max_dev_answer": da,
            "max_dev_entropy": de, "verdict": verdict, "tolerance": TOLERANCE, **counts}
