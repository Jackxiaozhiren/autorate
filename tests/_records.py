"""The shared record factories, with one owner across Plans B1-B3 (ruling R-69).

Two factories live here now: `choice_record` (the shape all three B-plans need) and `build_ordinal`
(the seeded ordinal population Plan B2 gates its whole G3 evidence on), which R-69 put in this
module's charge and Plan B2 Task 3 moved here verbatim from `tests/test_certify_score.py`.

Every module in `tests/` that needs a decision record builds its own: `test_certify_choice.py`
has `_records`, `test_certify_threshold.py`, `test_gate.py` and `test_records.py` have `_rec`,
`test_scales.py` has `_choice`. That is right for shape-specific fixtures -- a sweep over
difficulties is that file's business and nobody else's. What was missing is the one shape all
three B-plans need and none of them should redefine: a labelled choice record with a given `id`,
`case_id`, `repeat` and `slices`. Left unowned, each plan writes its own version, and a fixture
shaped by the consumer that uses it certifies a fiction -- it satisfies the assertions of the file
that made it and nothing else. So this module exists, under the name R-69 fixes, and the
certificate-producing tests reuse it rather than inventing a second way to build a record.

It builds REAL `autorate.records.Record` objects through the public constructor and nothing else,
so every validation a corpus row passes is a validation a fixture passes: option/probability
agreement, the probability sum, the gold label on the ballot, `u` in [0, 1), and the
copy-not-adopt freeze on the three mappings (`records.py:119-121`). A stand-in object with the
same attribute names would pass the grouping assertions here and then fail -- or worse, quietly
skip -- the moment a certifier called a `Record` property on it.

Every parameter is keyword-only, which is the lesson `_thresholds.py` records after one of its
solvers survived a review round with two positional parameters transposed: an `id` and a `case_id`
are the same shape and can trade places without any assertion noticing, and the only fix that holds
for EVERY value pair is to make the swap a `TypeError` at the call site.
"""
import math
import random

from autorate.records import Record

# The rubric width the ordinal factory defaults to. It is 5 because that is the width the Plan B2
# gates were measured at (spec 14's "score has K <= 5 levels" is upstream `laya`'s shape, not this
# repository's bound), and because the ordinal family's tie and nesting sweeps in
# `tests/test_ordinal.py` are stated over it.
K = 5

# "gold was not passed" must be expressible separately from "this record has no gold label",
# because the second one is a case under test (a certifier's eligibility rule), not a default.
_DERIVE = object()


def _leftmost_argmax(options, probs):
    """The option with the largest probability, ties to the leftmost index.

    The same rule `certify_threshold._submitted_label` uses for a record that states no answer, so
    a bare `choice_record(...)` is a decision whose label and its argmax agree -- and a fixture that
    mirrors production's tie rule cannot drift from it.
    """
    return list(options)[max(range(len(probs)), key=lambda j: probs[j])]


def choice_record(*, id="r0", case_id=None, repeat=0, backend="synthetic", options=None,
                  probs=None, gold=_DERIVE, predicted=None, slices=None, scores=None,
                  seed=0, u=0.0, meta=None) -> Record:
    """One `qtype="choice"` record, valid by construction.

    Defaults are chosen so a bare call is something a certifier can actually certify, and so that
    nothing here claims provenance it does not have:

    * `probs` defaults to (0.7, 0.1, 0.1, 0.1) over `opt0..opt3`, and `options` follows `probs`
      when not given -- one vector, one ballot, never two owners of the option count.
    * `gold` defaults to the ballot's argmax, so a bare call is a CORRECT decision. A fixture that
      cannot be wrong cannot be shown refusing one (`test_certify_choice.py` learned that the hard
      way); pass `gold=` for the wrong ones and `gold=None` for an unlabelled one.
    * `predicted` defaults to None -- "this record states no answer", which is a real upstream
      shape and whose fallback the rule owns, not the fixture.
    * `backend` defaults to "synthetic". It does NOT default to a shipped backend's name: a
      fixture that says `laya` is claiming provenance the data does not have, and `backend` is a
      published certificate field.
    * `case_id` defaults to None, which makes the record its own case (`case_key` falls back to
      `id`). Repeats pass the shared `case_id` explicitly, because the whole point of the field is
      that three rows can stand for one observation.
    """
    vector = tuple(probs) if probs is not None else (0.7, 0.1, 0.1, 0.1)
    ballot = tuple(options) if options is not None else tuple("opt%d" % j for j in range(len(vector)))
    label = _leftmost_argmax(ballot, vector) if gold is _DERIVE else gold
    return Record(id=id, qtype="choice", backend=backend, repeat=repeat,
                  options=ballot, probs=vector, gold=label, predicted=predicted,
                  case_id=case_id, slices=dict(slices or {}), scores=dict(scores or {}),
                  seed=seed, u=u, meta=dict(meta or {}))


def _ballot(rng, centre, k, temp, jitter):
    """One ordinal ballot: exponential decay away from `centre`, jittered so scores are not tied.

    The jitter is not decoration. With `jitter=0` every ballot of a given shape is the same ballot,
    the calibration scores collapse onto k distinct values, and the quantile stops being a sample
    statistic at all -- the coverage row of the gate suites would then be asserting the arithmetic of
    one fixed vector. Ruling R-78 puts tie-breaking in the quantile, so the scores have to be distinct
    for a gate's threshold to mean anything.
    """
    w = [math.exp(-temp * abs(j - centre)) * (1.0 + jitter * (rng.random() - 0.5)) for j in range(k)]
    s = sum(w)
    p = [round(x / s, 4) for x in w]
    p[centre] = round(p[centre] + (1.0 - sum(p)), 4)
    return tuple(p)


def build_ordinal(*, n=1200, seed=1, k=K, shift=0.0, error_rate=0.0, temp=1.4, jitter=0.8, repeats=3,
                  backend="synthetic-ordinal", unlabelled=0):
    """`n` labelled `score` records over ceil(n/repeats) cases. Synthetic, with known answers.

    THIS MODULE OWNS IT (ruling R-69, carried out by Plan B2 Task 3). The body moved verbatim from
    `tests/test_certify_score.py`, so every number that file pins -- its certified `qhat`, its
    automation rates, its split pin -- is produced by the same arithmetic on the same seed; the move
    changed no statement of the generator, only where it lives. Plan B2 Task 3's own rows call it
    through the thin `ordinal_records` wrapper in `tests/test_severity.py`.

    `n` counts RECORDS, not cases: the loop stops when `len(out) >= n`, so `n=1200, repeats=3` is
    400 cases and `n=1200, repeats=1` is 1,200 cases. The dispatch that merged the two factories
    asked for exactly this to be re-checked, because the certification unit -- and therefore every
    binomial denominator in the gates that consume this -- is the CASE.

    `shift` is the probability that the reported centre sits one level BELOW the gold level -- a model
    that under-calls severity, which is the failure spec §6.2 is about. `error_rate` overrides it with
    a random displacement of one or two levels in either direction, and is the knob that makes the
    peak wrong at all: a generator that is never wrong cannot be shown refusing an error, which is the
    defect ledger D12 records for the choice gate's first generator.

    `repeats` is what makes the certification unit visible: a case's repeats carry byte-identical
    probabilities and gold, as the committed archive does (laya: three records per case), and only the
    draw `u` differs -- which is also the inertness probe, since the chain family may not read `u`.
    It is also the trap the task-2 review's MINOR-1 names: on this population the record unit and the
    case unit are the SAME numbers, so a guard about the denominator cannot fail here and needs a
    disagreeing-repeat arm built elsewhere (`_mixed_repeat_cases` in `tests/test_severity.py`).

    Like `choice_record`, every parameter is keyword-only: an `n` and a `seed` traded places would
    change the population without changing any assertion's shape, and the only fix that holds for
    every value pair is to make the swap a `TypeError` at the call site.
    """
    rng = random.Random(seed)
    options = tuple(str(j) for j in range(k))
    out = []
    case = 0
    while len(out) < n:
        cid = "case%04d" % case
        case += 1
        gold = rng.randrange(k)
        centre = gold
        if error_rate and rng.random() < error_rate:
            centre = gold + rng.choice([-2, -1, 1, 2])
        elif rng.random() < shift:
            centre = gold - 1
        centre = max(0, min(k - 1, centre))
        probs = _ballot(rng, centre, k, temp, jitter)
        for rep in range(repeats):
            if len(out) >= n:
                break
            out.append(Record(id="%s.r%d" % (cid, rep), qtype="score", backend=backend, repeat=rep,
                              options=options, probs=probs,
                              gold=None if len(out) < unlabelled else options[gold],
                              predicted=options[centre], case_id=cid, seed=seed, u=rng.random()))
    return out

def g3_pair(rows):
    """The set certificate and the severity certificate for one ordinal population.

    Shared because two rows ask about the same pair from different sides: `tests/test_g3_contrast.py` asks
    whether the contrast holds, and the note-digit guard in `tests/test_verify_protocol.py` asks whether the
    digits G3's frozen note states are the ones this pair actually produces. A helper, not a second copy.
    """
    from autorate.certify_score import certify_score
    from autorate.severity import certify_severity
    from autorate.certificate import ALPHA, BETA, DELTA, SEED
    return (certify_score(rows, alpha=ALPHA, beta=BETA, delta=DELTA, seed=SEED),
            certify_severity(rows, alpha=ALPHA, delta=DELTA, direction="under", seed=SEED))

