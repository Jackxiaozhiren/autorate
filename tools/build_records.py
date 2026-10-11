"""Score a pinned corpus offline and write Records. Not on the test path, never on CI.

    uv run --frozen python tools/build_records.py --cache <massive-cache> \
        --out data/records_massive.jsonl --langs en,de,sw --chunk-size 150

One scoring pass, two artefacts, two temperature regimes. `--out` carries the **clamped** regime
and is the certified artefact; the sibling `<out stem>_unclamped_parity<suffix>` (or
`--out-parity`) carries the **unclamped** regime and is the parity control that reproduces
upstream's published row. Which regime a file holds is never something a reader has to remember:
it is in the filename, in the run summary's `artefacts` block, and in every record's
`slices.regime`, `meta.regime` and `meta.calibration_status` -- because a row that could be either
regime, with nothing saying which, is how a saturated `mean_confidence 0.9989` gets published as if
it were calibrated.

`--chunk-size` (R-117) is orthogonal to `--per-lang`: the first sizes the collated forward pass,
the second sizes the artefact. One collated 2,974-case batch projects to ~48.9 GB against a 16 GB
machine, so the suite is scored in batches and the batches are concatenated in the suite's own case
order -- a claim the driver does not assume, because `tests/test_build_records.py` scores a prefix
of a pinned shard at several layouts and asserts the distributions come out bit-identical. Every
artefact records the layout it was scored in (`chunk_size` and `chunks` in the run summary, per
stage), so the equivalence test is a statement about the shape this file actually used.

Two halves in one file, split by which interpreter runs them:

* the **build layer** (this file's default mode) runs in *this* repository's venv, imports only
  the standard library, and owns everything that can be checked without a model: the pin, the
  cache, the payload's self-consistency, the logits-to-Record conversion, the recorded `u` draw,
  the parity gate and the write.
* the **model stage** (`--worker`) runs in the *vendored* interpreter -- the one with torch and
  `laya` -- because this repository must never gain a runtime ML dependency (Global Constraints).
  It loads nothing at module scope except on that path, and the build layer reaches it the way
  `autorate.inventory.audit_command` reaches upstream's audit: a resolved interpreter plus
  `PYTHONDONTWRITEBYTECODE=1`, never a hardcoded path.

Why the split is the point: the archived corpus carries no `u` (`meta.u_source:
"absent_from_archive"` in `data/records_feishu.jsonl`), and spec 5.2 forbids certifying APS ties
resolved to a default, so these records carry a recorded draw per case -- which only matters if
the draw is reproducible from a stated seed. `records_from_logits`, `draw_u` and `PARITY` are
therefore pure and tested with no model in the room (`tests/test_build_records.py`), and the one
non-pure thing the build layer touches is upstream's own `summarise`, loaded by file path from the
resolved tree so the parity comparison is against *upstream's arithmetic*, not a copy of it.

Refuses to write anything unless the published `en` row reproduces. Comparability with upstream's
tables is a claim this artefact makes about itself, so the gate is run on the same conversion and
the same rounded probabilities that the records are written with *and* on the row the model stage
itself reported -- upstream's own `summarise` over the checkpoint's unrounded softmax, computed in
the vendored interpreter. One target, two sides, both must equal it: gating only this build's
conversion would let a rounding step that moved one prediction relative to upstream's own argmax
pass while the published row about the same logits said otherwise. The probe's cases must also be
present in both artefacts, so the proof travels inside the files it certifies. The gate is stated
under the unclamped regime and is applied to that regime's numbers only: `check_parity` refuses a
clamped report on identity grounds, which is what keeps the certified side from being "adjusted"
until it matches a row it is not the same quantity as. The certified side inherits the proof rather
than needing its own -- same cases, same forward pass, same recorded `u`, one different temperature.

Exceptions, and the exit code each one gets. rc 1 is unreachable by construction: every failure
this tool can name has a class, and every class has a clause.

    ParityError           the recomputed distribution does not match upstream's published row --
                          on either side of it -- or the artefact does not contain the cases that
                          were gated on -> 3, the code the CLI already reserves for "this evidence
                          refuses a certificate".
                          Deliberately NOT a `BuildError` and NOT a `ValueError`: a clause that
                          maps the build failures must never absorb the verdict (the I-2 lesson:
                          widening a catch once downgraded a policy refusal to success).
    DriftError            a published figure here cannot be re-derived: the cache on disk is not
                          the bytes the pin describes, the pin disagrees with itself, a model
                          stage answered for another language, or its arrays -- or the values inside
                          them -- do not line up. The payload is JSON from another interpreter, so
                          its value *types* are data here and not assumptions: a logit, temperature,
                          chunk size, gold index or `probs_probe` entry that is not a real number, a
                          gold index outside its ballot, a one-option ballot published as `choice`,
                          a `timing` that is not a mapping, a shard line that parses as JSON but is
                          not an object, a stage that scored a question type other than `choice`, a
                          stage whose declared chunk layout could not have produced its own case
                          count, a regime block that is missing or calls its own confidence something
                          other than what the regime and the checkpoint's warnings say -- all of those
                          are refusals, not `TypeError`s -> 4.
    IncompleteBuildError  the build could not run: no upstream tree, no interpreter, no numpy,
                          the stage crashed or was killed, the payload is not JSON, the out path
                          is not writable -> 4, the code the CLI gives a tool that cannot
                          reproduce its own inputs.
    BuildError            the base of the two above. `ParityError` is NOT built on it.
    UsageRefusal          the operator's input is wrong: a language that is not pinned, an option
                          count or `--seed` the published row is not stated under, a `--per-lang`
                          the shard cannot fill, a `--chunk-size` below one, or the two artefacts
                          pointed at the same path -> 2. argparse's own errors are 2 as well, which
                          is what `--regime` now is: the regime is a property of the artefact, not
                          something the operator types.
    UStreamExhausted      the `u` stream ran out; a missing draw would land on 0.0 and quietly
                          tie-break -> a `BuildError`, so 4, and never a zero fill.

Exit codes are exactly 0 (records written, parity held) / 2 (usage) / 3 (not certifiable) /
4 (drift or could not complete).

Regime: both, out of one forward pass, because `score_cases` deliberately applies no temperature
"so the caller can score under more than one regime from one pass" (R-118). `unclamped` is the
regime `PARITY` and `research/results/cpu_51_language_sweep.json` were produced at, so it is the
parity control and nothing else; `clamped` -- spec 7.2's clamp, the temperature upstream's own code
applies -- is the certified headline. The gate is stated under the unclamped row and `check_parity`
refuses the clamped report on identity grounds, so neither side can be adjusted into matching the
other. `CERTIFIED_REGIME` is a constant rather than a flag: the near-saturated column upstream
declines to treat as calibrated is not selectable as the headline by typing a word.
"""
import argparse
import gzip
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Script mode (`python3 tools/build_records.py`) puts `tools/` on sys.path, not the repo
    # root, so `tools.fetch_massive` would not resolve. Pytest's `pythonpath = ["."]` already
    # puts the root there, which makes this a no-op on the test path.
    sys.path.insert(0, str(ROOT))

from tools.fetch_massive import (
    GZIP_FAILURES,
    ManifestError,
    load_manifest,
    require_manifest,
    verify_provenance,
)

DEFAULT_PIN = ROOT / "data" / "massive_provenance.json"
BACKEND = "laya"
QTYPE = "choice"
PROB_DECIMALS = 6
INSTRUCTIONS = "What is the user asking for in `utterance`?"
EXIT_OK, EXIT_USAGE, EXIT_NOT_CERTIFIABLE, EXIT_DRIFT = 0, 2, 3, 4

# Upstream's published `en` row, n=100, k=20, raw (unclamped) temperatures. One owner for the
# figure this artefact claims comparability with: `PARITY_TARGET` is the same object, so an
# erratum lands in exactly one place.
PARITY = {"lang": "en", "per_lang": 100, "n_opts": 20, "seed": 13, "regime": "unclamped",
          "accuracy": 0.82, "mean_confidence": 0.9989, "macro_f1": 0.7876, "ece": 0.1789}
PARITY_TARGET = PARITY
PROBE_FIGURES = ("accuracy", "mean_confidence", "macro_f1", "ece")
PROBE_IDENTITY = ("lang", "n_opts", "seed", "regime")
# The two rows the gate compares against one target. `STAGE_SIDE` is upstream's own arithmetic run
# in the vendored interpreter on the checkpoint's unrounded softmax; `BUILT_SIDE` is this build's
# conversion -- the 6-decimal vector and its argmax, i.e. the numbers the records actually carry.
# Both must equal the published row, because a gate on one alone proves only that one.
STAGE_SIDE = "upstream's own row from the model stage"
BUILT_SIDE = "this build's written conversion"
PROBE_PROBS_CASES = 8
SOFTMAX_TOL = 1e-9
WORKER_STAGES = ("probe", "full", "equivalence")
# The two temperature regimes, scored out of ONE forward pass: `score_cases` applies no temperature
# on purpose ("so the caller can score under more than one regime from one pass"), and a second run
# of the model to obtain the other column would double the cost of the thing this build is gated on.
REGIMES = ("unclamped", "clamped")
# R-118: the certified number is the clamped one -- the temperature upstream's own code applies --
# and the unclamped run survives only as the parity control that proves the scoring path. This is a
# constant rather than a flag on purpose: an operator must not be able to ask for the saturated,
# upstream-rejected column as the headline by typing a word.
CERTIFIED_REGIME = "clamped"
PARITY_REGIME = PARITY["regime"]
# What a confidence column in a record means, in the record itself. Sentences rather than codes,
# because the reader this is for is `jq` and a human, not a lookup table in a document nobody opens.
CALIBRATION_CLAMPED = "clamped by upstream to [0.5, 5]"
CALIBRATION_REJECTED = "uncalibrated: upstream rejects this temperature (outside [0.5, 5])"
CALIBRATION_IN_RANGE = "upstream applied no clamp: raw temperature was already in range"
# R-117: one collated batch of a whole 2,974-case shard projects to ~48.9 GB against a 16 GB
# machine. 150 cases per batch is ~2.5 GiB of activations plus ~1.16 GiB fixed, i.e. ~3.6 GiB,
# which leaves the other lanes in this tree their memory. Orthogonal to `--per-lang`, which sizes
# the artefact and not the batch.
DEFAULT_CHUNK_SIZE = 150
# Every regime-block key `check_payload` and the conversion index without a `.get()`, so a stage
# that answers partially is a stage that did not run.
REQUIRED_REGIME_KEYS = ("temperatures", "probs_probe", "upstream_report", "calibration_status")
# A stage that answers partially is a stage that did not run. Every one of these is indexed later,
# so an absent key would surface as a `KeyError` -- rc 1, outside this tool's contract.
REQUIRED_PAYLOAD_KEYS = ("lang", "stage", "n_cases", "n_opts", "seed", "item_ids", "gold",
                         "option_keys", "logits", "texts", "timing", "qtype", "regimes",
                         "chunk_size", "chunks", "warnings")


class BuildError(RuntimeError):
    """The build itself failed: it could not complete, or what it found disagrees with the pin.

    Not a `ValueError`, on the precedent of `ReaderContractError`: a refusal must not be catchable
    by a clause that means "the operator passed a bad path".
    """


class DriftError(BuildError):
    """A figure this artefact publishes cannot be re-derived from the bytes it was built on."""


class IncompleteBuildError(BuildError):
    """The build could not be run at all: no tree, no interpreter, no model, no write."""


class ParityError(RuntimeError):
    """The evidence refuses the comparability claim. A verdict about the data, so it is not a
    `BuildError`: the clause that maps build failures to 4 must never be able to file this."""


class UsageRefusal(RuntimeError):
    """The operator's input cannot be honoured. Not a `BuildError` either: it is not the data."""


class UStreamExhausted(IncompleteBuildError):
    """The recorded `u` stream ended before the cases did. Never zero-filled (spec 5.2)."""


class UpstreamStageError(IncompleteBuildError):
    """Code this repository does not own raised while the model stage ran.

    `laya.load` reaches transformers, torch and the HF cache, none of which have a documented
    exception hierarchy a caller can enumerate -- and the brief's whole point is that a driver which
    crashes on a model error exits 1. So the catch is deliberately wide, and deliberately placed at
    exactly one line: the call into the checkpoint stack, with this tool's own refusals re-raised
    untouched first, so a parity verdict or a usage refusal can never be relabelled as a library
    failure (the widened-catch lesson). rc 4 says "the build did not complete", which is what
    happened; the exception's own type and message are printed so the cause is not lost.
    """


# ------------------------------------------------------------------------- the pure layer
def draw_u(seed: int, n: int):
    """`n` draws from a freshly seeded Mersenne Twister, as a generator.

    `random.Random(int)` is the stream that is byte-stable across the two interpreters in play
    here (verified on 3.12 in this repository's venv and the vendored one), which is what makes a
    recorded `u` re-derivable by a reader who never runs our model. `numpy`'s global state and
    torch's RNG are not: they are version- and device-sensitive, and a certificate that could not
    reproduce its own tie-breaks would not be a certificate.
    """
    rng = random.Random(int(seed))
    for _ in range(int(n)):
        yield rng.random()


def softmax_t(z, temperature: float = 1.0) -> list:
    """Temperature-scaled softmax, matching upstream's `laya_eval.softmax_t`.

    Kept here in pure `math` so the conversion is testable without numpy; the build layer checks
    it against upstream's own function on every case batch it scores (see `_check_probs_probe`),
    so this is a re-implementation that is watched, not one that is trusted.
    """
    t = max(1e-3, float(temperature))
    scaled = [float(x) / t for x in z]
    top = max(scaled)
    exps = [math.exp(x - top) for x in scaled]
    total = sum(exps)
    return [x / total for x in exps]


def answer_confidence(probs) -> float:
    """`laya`'s `answer_confidence`: mass on the reported answer (mirrors `autorate.records`)."""
    return max(float(x) for x in probs)


def chunk_sizes(n: int, chunk_size: int) -> list:
    """How many cases each collated batch of a `n`-case suite holds, in scoring order.

    One owner for the shape, so the stage that scores and the build layer that audits the score
    cannot disagree about what "chunked at 150" was supposed to look like.
    """
    n, chunk_size = int(n), int(chunk_size)
    if n < 0 or chunk_size < 1:
        raise DriftError("cannot lay out %r cases in batches of %r" % (n, chunk_size))
    sizes = [chunk_size] * (n // chunk_size)
    if n % chunk_size:
        sizes.append(n % chunk_size)
    return sizes


def score_cases_in_chunks(score_fn, cases, chunk_size: int):
    """Score a suite in batches of at most `chunk_size` cases: (concatenated logits, sizes).

    This is the whole of R-117's memory answer -- upstream's `score_cases` builds one collated
    batch, and a collated batch of 2,974 cases projects to ~48.9 GB against a 16 GB machine -- and
    it is a *function* rather than a line inside the worker so that the two properties it has to
    have are testable without a model: the batches are contiguous, in order, and cover the suite
    exactly once (so the concatenation is the suite's own case order), and a batch that answers for
    the wrong number of cases is a refusal instead of a silent off-by-one against `gold`.

    Whether the *checkpoint* gives the same probabilities at two batch sizes is not testable here
    and is not assumed: that claim is asserted, bit-for-bit, against the real model in
    `tests/test_build_records.py`.
    """
    cases = list(cases)
    chunk_size = int(chunk_size)
    if chunk_size < 1:
        raise DriftError("a chunk size of %d would score nothing at all" % chunk_size)
    out, sizes = [], chunk_sizes(len(cases), chunk_size)
    start = 0
    for position, size in enumerate(sizes):
        part = cases[start:start + size]
        got = list(score_fn(part))
        if len(got) != size:
            raise DriftError("chunk %d of %d was asked for %d cases and answered with %d: a batch "
                             "that returns the wrong count would put every later case's logits "
                             "against the wrong gold label"
                             % (position + 1, len(sizes), size, len(got)))
        out.extend(got)
        start += size
    if start != len(cases):
        raise DriftError("the chunk layout covered %d of %d cases" % (start, len(cases)))
    return out, sizes


def calibration_status(regime: str, warning_emitted: bool = True) -> str:
    """What a reader may conclude about a confidence column, before they read anything else.

    R-118's whole point: the regime is a property of the numbers, and the *library's* verdict -- not
    this tool's name for the regime -- is what says whether that confidence is calibrated. Every
    load of this checkpoint warns that `choice:11+ = 0.10058` sits outside the range upstream will
    apply, so the unclamped column is published as rejected-by-upstream and the clamped one as what
    upstream itself scores with. A checkpoint whose raw temperatures were already inside the range
    gets the third value, which says so instead of borrowing a warning it never triggered.
    """
    if regime not in REGIMES:
        raise DriftError("%r is not a regime this tool names (%s), so it cannot say what its "
                         "confidence means" % (regime, " or ".join(REGIMES)))
    if regime == "clamped":
        return CALIBRATION_CLAMPED
    return CALIBRATION_REJECTED if warning_emitted else CALIBRATION_IN_RANGE


def entropy_confidence(probs) -> float:
    """`laya`'s `confidence`: 1 - H(p)/log(k), concentration and not accuracy.

    Mirrors `autorate.records.entropy_confidence`, which `tests/test_build_records.py` pins this
    against -- the definition has one owner in the package, and this copy is checked, not assumed.
    """
    p = [float(x) for x in probs]
    k = len(p)
    if k < 2:
        return None
    ent = -sum(x * math.log(x) for x in p if x > 0.0)
    return max(0.0, min(1.0, 1.0 - ent / math.log(k)))


def rounded_probs(raw, decimals: int = PROB_DECIMALS) -> list:
    """Close the distribution at the published precision instead of hoping rounding adds up.

    Naive per-entry rounding breaks the sum-to-one bound the brief states: 20 entries each rounded
    half-a-unit-in-the-6th-place can leave an error of 1e-5, twice the 1e-6 a reader is told to
    expect, and `autorate.records.SUM_TOL` (5e-3) would swallow it silently. This is the largest
    remainder allocation -- floor every entry, then hand the missing units to the entries whose
    rounding was least favourable -- so the parts sum to exactly one whole and every entry stays
    within one unit of the value the softmax produced.
    """
    scale = 10 ** int(decimals)
    exact = [float(x) * scale for x in raw]
    floors = [int(math.floor(v)) for v in exact]
    missing = scale - sum(floors)
    if missing > 0:
        order = sorted(range(len(exact)), key=lambda i: -(exact[i] - floors[i]))
        for i in order[:missing]:
            floors[i] += 1
    elif missing < 0:
        # Only reachable if `raw` itself summed to more than one; take the surplus back from the
        # entries that were rounded up most generously rather than inventing a second rule.
        order = sorted(range(len(exact)), key=lambda i: (exact[i] - floors[i]))
        for i in order[:(-missing)]:
            floors[i] -= 1
    return [u / scale for u in floors]


def _number(value, lang: str, index: int, what: str, integer: bool = False) -> float:
    """One value from the model stage, proven to be the number the arithmetic below assumes.

    The payload is JSON produced by a different interpreter, so its value *types* are not this
    layer's to assume. `float("0.5")` succeeds, which is precisely why a string logit has to be
    refused rather than coerced: coercion would let a shape change into the checkpoint stack land in
    the published distribution. Non-finite values are refused for the same reason -- a NaN becomes a
    zero or a one inside a softmax and every certificate downstream quotes it.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DriftError("%s case %d: the %s is %r, a %s rather than a number; the payload is JSON "
                         "from the model stage and its value types are checked here, not assumed -- "
                         "a string that happens to parse would otherwise be coerced silently into "
                         "the distribution this artefact publishes"
                         % (lang, index, what, value, type(value).__name__))
    x = float(value)
    if not math.isfinite(x):
        raise DriftError("%s case %d: the %s is %r, which is not finite; a NaN or inf would become "
                         "a zero or a one in the probability vector, and every certificate built on "
                         "the row would quote it" % (lang, index, what, value))
    if integer and int(x) != x:
        raise DriftError("%s case %d: the %s is %r, which is not a whole option index"
                         % (lang, index, what, value))
    return x


def case_id_for(lang: str, item_id: str) -> str:
    """The case identity the artefact carries: the dataset item id, under the corpus namespace.

    `records_from_logits` makes `case_id` whatever `item_ids` says, so a caller that passes the raw
    shard id gets the raw shard id back -- and the 51 shards share one 2,974-id set, which would
    make id `7` the same case in every language (R-36, R-44). The build layer therefore namespaces
    the id here, and this function is the only place that shape is written.
    """
    return "massive/%s/%s" % (lang, item_id)


def records_from_logits(logits, gold, option_keys, lang, u_stream, item_ids=None,
                        temperature: float = 1.0, temperatures=None, texts=None, *,
                        backend: str = BACKEND, regime: str = "unclamped",
                        calibration: str | None = None,
                        suite_seed: int = PARITY["seed"], u_seed: int = PARITY["seed"],
                        dataset: str | None = None, revision: str | None = None,
                        license_id: str | None = None, checkpoint: str | None = None,
                        device: str | None = None) -> list:
    """Logits -> one `Record` dict per case, in presented option order, with a recorded `u`.

    `probs` are rounded to `PROB_DECIMALS` and the rounding is *stated* in `meta`, because the
    archived corpus is 4-decimal and says so (`autorate.records.SUM_TOL`); this one is 6.
    `predicted` is the argmax of the rounded vector that is written, not of an unrounded one, so a
    reader can recompute every field of every record from the line itself. `gold` and `predicted`
    are option keys, never indices (spec 4), and `case_id` is the dataset item id qualified by the
    language -- the 51 shards share one 2,974-id set, so a bare id would be the same case in all
    of them (R-36, R-44).

    `meta.calibration_status` states, in words, what the confidence column on this row means and
    who says so (R-118). It is derived from the regime by `calibration_status` and the build layer
    overrides the derivation with the warning the library actually emitted, so a row can never be
    read as calibrated because a reader forgot which of the two files it came from.
    """
    n = len(logits)
    # Checked once here, before any row is built, so an unknown regime cannot ride in on a record
    # that supplied its own `calibration` string: the regime is the thing a reader trusts that
    # string to describe.
    derived_calibration = calibration_status(regime)
    if len(gold) != n or len(option_keys) != n:
        raise DriftError("%s: %d logits but %d gold and %d option sets; the conversion refuses to "
                         "guess which case is which" % (lang, n, len(gold), len(option_keys)))
    if item_ids is not None and len(item_ids) != n:
        raise DriftError("%s: %d item ids for %d cases" % (lang, len(item_ids), n))
    if texts is not None and len(texts) != n:
        raise DriftError("%s: %d utterances for %d cases" % (lang, len(texts), n))
    if temperatures is not None and len(temperatures) != n:
        raise DriftError("%s: %d temperatures for %d cases" % (lang, len(temperatures), n))

    records = []
    for i, z in enumerate(logits):
        keys = list(option_keys[i])
        if len(keys) < 2:
            raise DriftError("%s case %d: the ballot has %d option(s) and a `choice` record needs at "
                             "least 2. This function publishes every row as qtype=%r, and a one-slot "
                             "distribution is laya's `noul`/`score` shape rather than a choice "
                             "question -- `autorate.records.validate` refuses to certify it at all, "
                             "and the write path never builds a `Record`, so the refusal belongs here"
                             % (lang, i, len(keys), QTYPE))
        t = _number(temperatures[i] if temperatures is not None else temperature,
                    lang, i, "temperature")
        values = [_number(v, lang, i, "logit %d" % j) for j, v in enumerate(z)]
        probs = rounded_probs(softmax_t(values, t))
        if len(keys) != len(probs):
            raise DriftError("%s case %d: %d options for %d probabilities"
                             % (lang, i, len(keys), len(probs)))
        if len(set(keys)) != len(keys):
            raise DriftError("%s case %d: duplicate option keys, so a gold key would name two "
                             "slots" % (lang, i))
        if abs(sum(probs) - 1.0) > 1e-9:
            raise DriftError("%s case %d: the rounded distribution sums to %.9f, not to one; the "
                             "artefact would carry a probability vector that is not one"
                             % (lang, i, sum(probs)))
        try:
            u = float(next(u_stream))
        except StopIteration as exc:
            raise UStreamExhausted("%s: the u stream ended at case %d of %d; a missing draw would "
                                   "be recorded as 0.0 and silently decide every APS tie, which "
                                   "spec 5.2 forbids" % (lang, i, n)) from exc
        # `gold` arrives as an option *index* from the stage and is published as a key (spec 4), so
        # it is bounded against the ballot here: `keys[-1]` is legal Python that names the wrong
        # option, and an index past the end would leave as an `IndexError` with exit code 1.
        g = gold[i]
        g_index = None
        if g is not None:
            g_index = int(_number(g, lang, i, "gold index", integer=True))
            if not 0 <= g_index < len(keys):
                raise DriftError("%s case %d: the gold index %d is outside the %d-option ballot, so "
                                 "the row would publish a gold label that is not one of the options "
                                 "it lists (or would wrap to the last one)"
                                 % (lang, i, g_index, len(keys)))
        gold_key = None if g_index is None else keys[g_index]
        predicted_key = keys[max(range(len(probs)), key=lambda j: probs[j])]
        # `case_id` is whatever identity the caller supplied -- the build layer hands over the
        # dataset item id under the corpus namespace (`case_id_for`), and never a row number.
        case_id = (str(item_ids[i]) if item_ids is not None
                   else "massive/%s/row-%05d" % (lang, i))
        meta = {"probability_precision": PROB_DECIMALS, "regime": regime, "temperature": t,
                "calibration_status": calibration or derived_calibration,
                "u_seed": int(u_seed), "u_index": i, "u_source": "recorded_draw",
                "suite_seed": int(suite_seed), "source": "tools/build_records.py",
                "instructions": INSTRUCTIONS,
                "case_id_source": "caller_supplied_identity" if item_ids is not None else "row_index"}
        for key, value in (("dataset", dataset), ("revision", revision), ("license", license_id),
                           ("checkpoint", checkpoint), ("device", device),
                           ("utterance", None if texts is None else texts[i])):
            if value is not None:
                meta[key] = value
        scores = {"answer_confidence": answer_confidence(probs),
                  "confidence": entropy_confidence(probs)}
        if gold_key is not None:
            scores["p_gold"] = probs[g_index]
        records.append({
            "id": "%s/%s" % (case_id, backend),
            "qtype": QTYPE,
            "backend": backend,
            "repeat": 1,
            "options": keys,
            "probs": probs,
            "gold": gold_key,
            "predicted": predicted_key,
            "case_id": case_id,
            "slices": {"language": lang, "mode": QTYPE, "regime": regime, "option_count": len(keys)},
            "scores": scores,
            "seed": int(u_seed),
            "u": u,
            "meta": meta,
        })
    return records


def report_from_records(records, summarise) -> dict:
    """Upstream's `summarise` over the numbers the artefact actually carries, plus its identity.

    The gate is only a parity proof if it reads the written values: confidence is `max(probs)`, the
    prediction is the argmax of the rounded vector, and both come out of the record dict. A case
    with no gold contributes `correct=None` rather than a fabricated 0 -- the arrays handed to
    upstream's metric code say what the artefact says.

    The identity fields (`lang`, `n_opts`, `seed`, `regime`) are taken from the records too,
    because "the same four figures" is not the same *row* without them. `n_opts` is None when the
    suite mixed option counts, which the gate then refuses rather than averaging. `calibration_status`
    travels with the row for the same reason the regime does: four figures whose confidence column
    upstream declines to treat as calibrated are not interchangeable with four that are not.
    """
    confs, corrects, golds, preds = [], [], [], []
    for rec in records:
        probs = [float(x) for x in rec["probs"]]
        keys = list(rec["options"])
        pred = keys.index(rec["predicted"])
        confs.append(max(probs))
        preds.append(pred)
        if rec["gold"] is None:
            golds.append(None)
            corrects.append(None)
        else:
            g = keys.index(rec["gold"])
            golds.append(g)
            corrects.append(float(pred == g))
    report = dict(summarise(confs, corrects, golds, preds))
    langs = {rec["slices"]["language"] for rec in records}
    regimes = {rec["slices"]["regime"] for rec in records}
    seeds = {rec["meta"]["suite_seed"] for rec in records}
    counts = {rec["slices"]["option_count"] for rec in records}
    calibrations = {rec["meta"]["calibration_status"] for rec in records}
    report["lang"] = langs.pop() if len(langs) == 1 else None
    report["regime"] = regimes.pop() if len(regimes) == 1 else None
    report["seed"] = seeds.pop() if len(seeds) == 1 else None
    report["n_opts"] = counts.pop() if len(counts) == 1 else None
    report["calibration_status"] = calibrations.pop() if len(calibrations) == 1 else None
    return report


def check_parity(report, target=PARITY_TARGET, side: str = BUILT_SIDE) -> dict:
    """Stop unless the recomputed row *is* the published row, at the precision it is published at.

    The tolerance is the publication: upstream's figures are quoted to 4 decimals, so the comparison
    is `round(got, 4) == round(want, 4)` per figure. An identity that is not the published row's
    (n, language, option count, seed, regime) is refused however close its numbers look -- a
    2,974-case run is not the n=100 row, and a clamped run is not the unclamped one.

    `side` names which of the two rows is being compared, because the build asks the same question
    of two different computations (see `build`): upstream's own arithmetic inside the vendored
    interpreter, and this build's written conversion. A refusal has to say which one moved.
    """
    if not isinstance(report, dict):
        raise ParityError("the recomputed report from %s is %s, not a mapping, so nothing can be "
                          "compared" % (side, type(report).__name__))
    problems = []
    for key in PROBE_IDENTITY:
        if report.get(key) != target[key]:
            problems.append("%s %r is not the published %r" % (key, report.get(key), target[key]))
    if report.get("n") != target["per_lang"]:
        problems.append("n %r is not the published per_lang %r" % (report.get("n"),
                                                                   target["per_lang"]))
    got = {}
    for key in PROBE_FIGURES:
        want = target[key]
        if report.get(key) is None:
            problems.append("%s was not recomputed at all (published value %.4f)" % (key, want))
            continue
        have = round(float(report[key]), 4)
        got[key] = have
        if have != round(float(want), 4):
            problems.append("%s %.4f is not the published %.4f" % (key, have, want))
    if problems:
        raise ParityError("parity failed on %s: %s -- refusing to write records, because these "
                          "distributions cannot support the comparability claim this artefact "
                          "makes about itself" % (side, "; ".join(problems)))
    return got


def regime_block(payload: dict, regime: str) -> dict:
    """One regime's slice of a stage payload, refused rather than assumed if it is not there.

    The payload is JSON from another interpreter and it now carries a column per regime, so "which
    numbers go with which temperature" is a lookup this tool performs on somebody else's data. A
    payload missing one of the two is a stage that answered partially.
    """
    if regime not in REGIMES:
        raise DriftError("%r is not a regime this tool names (%s), so the build cannot say which "
                         "temperature produced these numbers"
                         % (regime, " or ".join(REGIMES)))
    regimes = payload.get("regimes")
    if not isinstance(regimes, dict):
        raise DriftError("the %s/%s payload's `regimes` is a %s, not an object; both temperature "
                         "regimes come out of one forward pass and each has to say so separately"
                         % (payload.get("lang"), payload.get("stage"), type(regimes).__name__))
    if regime not in regimes:
        raise DriftError("the %s/%s payload carries no block for regime %r (it has: %s); a run that "
                         "scored one regime cannot fill an artefact for the other"
                         % (payload.get("lang"), payload.get("stage"), regime,
                            ", ".join(sorted(regimes)) or "nothing"))
    block = regimes[regime]
    if not isinstance(block, dict):
        raise DriftError("the %s/%s payload's block for regime %r is a %s, not an object"
                         % (payload.get("lang"), payload.get("stage"), regime,
                            type(block).__name__))
    absent = [key for key in REQUIRED_REGIME_KEYS if key not in block]
    if absent:
        raise DriftError("the %s/%s payload's block for regime %r carries no %s: the temperatures "
                         "are what turn these logits into the published probabilities, so a regime "
                         "that does not name them cannot be written at all"
                         % (payload.get("lang"), payload.get("stage"), regime,
                            ", ".join(absent)))
    return block


def payload_warnings(payload: dict) -> list:
    """What the checkpoint stack warned about while this stage ran, as data rather than as stderr.

    Upstream's clamp warning is the fact R-118 turns into a publication policy, and the build layer
    runs the stage with its stderr captured -- so a warning that only lived on the child's stderr
    reached the build log as the last 400 characters of a tail, if that. The stage now records it.
    """
    seen = payload.get("warnings")
    return seen if isinstance(seen, list) else []


def stage_report(payload: dict, regime: str) -> dict:
    """The model stage's own row for one regime: upstream's `summarise`, on the checkpoint's output.

    This is the side of the parity comparison that is *not* this build: computed in the vendored
    interpreter, from the probabilities the checkpoint produced, with upstream's argmax rather than
    the argmax of the 6-decimal vector we write. The published figures alone are not the published
    row, so the identity travels with it from the same payload -- including which of the two regimes
    scored out of the one forward pass these numbers belong to.
    """
    block = regime_block(payload, regime)
    if not isinstance(block["upstream_report"], dict):
        raise DriftError("%s/%s/%s: the payload's upstream_report is a %s, not a mapping; the parity "
                         "gate compares upstream's own arithmetic, so it has to be able to read it"
                         % (payload.get("lang"), payload.get("stage"), regime,
                            type(block["upstream_report"]).__name__))
    report = dict(block["upstream_report"])
    for key in ("lang", "n_opts", "seed"):
        report[key] = payload[key]
    report["regime"] = regime
    report["calibration_status"] = block["calibration_status"]
    return report


# ------------------------------------------------------------------- the build layer's plumbing
def summarise_with(module, records):
    """Upstream's `summarise`, with whatever it raises turned into a named refusal.

    The metric bodies import numpy inside the function, so an `ImportError` here is this
    interpreter lacking numpy and `IncompleteBuildError` is its code; a `ValueError` or
    `TypeError` from the arrays (an empty suite, a `None` among the labels) is the payload
    disagreeing with the metric definition, and `ArithmeticError` covers numpy's own
    floating-point complaints. Naming them is what keeps rc 1 unreachable at the one place this
    process calls code it does not own.
    """
    try:
        return report_from_records(records, module.summarise)
    except ImportError as exc:
        raise IncompleteBuildError("upstream's metric code could not import its numeric stack: "
                                   "%s: %s (run the build layer with `uv run --frozen python "
                                   "...`, the interpreter that has numpy)"
                                   % (type(exc).__name__, exc)) from exc
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise DriftError("upstream's summarise refused these arrays: %s: %s; the gate compares "
                         "this build's numbers with the published row using upstream's own code, "
                         "so a refusal there is a refusal here"
                         % (type(exc).__name__, exc)) from exc


def resolve_upstream(explicit=None) -> Path:
    """The vendored tree, found the way `autorate.cli._default_corpus` finds it: no literal.

    A hard-coded absolute home-directory default passes every local gate, survives a clean-clone
    re-run on the same disk, and only breaks in the one environment nobody can see. `--upstream`
    and the `AUTORATE_UPSTREAM_ROOT` override are how a checkout elsewhere is pointed at.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get("AUTORATE_UPSTREAM_ROOT")
    if env:
        return Path(env)
    checkout = ROOT.parent
    found = sorted(checkout.glob("laya*/research/eval/laya_eval.py"))
    return found[0].parents[2] if found else None


def upstream_python(upstream: Path) -> str:
    """The vendored interpreter, derived from the tree -- mirroring `inventory._audit_python`.

    Deliberately NOT `resolve()`d, which is where this repo's existing helper goes wrong:
    `<tree>/.venv/bin/python` is a symlink, and resolving it hands back the *base* interpreter
    outside the venv -- measured here, `sys.prefix` moves to the Homebrew framework and `numpy` and
    `torch` both disappear from an environment that has them. The venv is found from the path it was
    invoked by, so the symlink has to stay.
    """
    override = (os.environ.get("LAYA_INFER_PYTHON") or os.environ.get("AUTORATE_UPSTREAM_PYTHON")
                or os.environ.get("AUTORATE_AUDIT_PYTHON"))
    if override:
        return override
    venv = Path(upstream) / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def load_upstream_eval(upstream: Path):
    """Upstream's `laya_eval` by file path, for `summarise` only.

    Importing it pulls in no torch (upstream keeps torch behind its own function bodies), and it
    means the parity comparison is computed by the code that published the row rather than by a
    copy of its arithmetic that could drift from it.
    """
    path = Path(upstream) / "research" / "eval" / "laya_eval.py"
    if not path.is_file():
        raise IncompleteBuildError("no upstream harness at %s: the parity gate compares against "
                                   "upstream's own metric code, so this build cannot proceed "
                                   "without the tree (pass --upstream or set AUTORATE_UPSTREAM_ROOT)"
                                   % path)
    spec = importlib.util.spec_from_file_location("autorate_build_laya_eval", path)
    if spec is None or spec.loader is None:
        raise IncompleteBuildError("%s could not be loaded as a module; the parity gate has nothing "
                                   "to compare with" % path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:                    # upstream's metric bodies import numpy
        raise IncompleteBuildError("%s could not be imported: %s: %s (the interpreter running the "
                                   "build layer needs numpy: use `uv run --frozen python ...`)"
                                   % (path, type(exc).__name__, exc)) from exc
    for name in ("summarise", "softmax_t"):
        if not hasattr(module, name):
            raise IncompleteBuildError("upstream harness %s exposes no %s(); the parity gate has "
                                       "nothing to compare with" % (path, name))
    return module


def pin_shard(pin: dict, lang: str) -> dict:
    """The pinned entry for one language, or a refusal naming what was asked for.

    Matched on the shard file's own name because the pin records `lang` as e.g. `en.json`; a second
    shard for the same language would double-count the same cases, and neither is honoured.
    """
    matches = [e for e in pin["files"] if Path(e["path"]).name.partition(".")[0] == lang]
    if not matches:
        raise UsageRefusal("no shard for language %r is pinned in the manifest (%d shards: %s...)"
                           % (lang, len(pin["files"]),
                              ", ".join(sorted(Path(e["path"]).name.partition(".")[0]
                                               for e in pin["files"])[:6])))
    if len(matches) > 1:
        raise DriftError("%d pinned shards claim language %r; one language must contribute one "
                         "case set" % (len(matches), lang))
    return matches[0]


def check_cache(cache, pin: dict, langs, per_lang) -> dict:
    """The cache against the pin, before a model is loaded for a corpus that is not what we say."""
    report = verify_provenance(Path(cache), pin)
    if not report["cache_present"]:
        raise DriftError("the cache %s is not a directory: nothing was checked, so no record here "
                         "could be attributed to the pinned corpus" % cache)
    if report["mismatched"]:
        named = ", ".join("%s (%s)" % (m["path"], m["reason"]) for m in report["mismatched"][:5])
        raise DriftError("%d of %d pinned shards do not match the pin: %s"
                         % (len(report["mismatched"]), report["checked"], named))
    if report["missing"]:
        raise DriftError("%d of %d pinned shards are absent: %s"
                         % (len(report["missing"]), report["checked"],
                            ", ".join(report["missing"][:5])))
    short = {}
    for lang in langs:
        entry = pin_shard(pin, lang)
        if entry["rows"] < per_lang:
            short[lang] = entry["rows"]
    if short:
        raise UsageRefusal("--per-lang %d asks for more cases than the shard holds: %s"
                           % (per_lang, "; ".join("%s has %d" % (k, v) for k, v in short.items())))
    return report


def load_rows(cache, lang: str, id_key: str = "id", text_key: str = "text",
              label_key: str = "label_text") -> list:
    """Read one pinned shard: id, utterance and gold label text, in file order.

    Every row keeps its dataset `id` because `case_id` must be that id and not the row number
    (R-44); a shard whose rows carry no id is refused rather than silently renumbered. Every way a
    body can fail to be gzipped JSONL is named here -- `tools.fetch_massive.GZIP_FAILURES` is the
    one list of those families, and a missing key is a `KeyError` that would otherwise leave as rc 1.
    """
    path = Path(cache) / "test" / ("%s.json.gz" % lang)
    if not path.is_file():
        raise DriftError("%s is not in the cache" % path)
    try:
        raw = gzip.decompress(path.read_bytes())
    except GZIP_FAILURES as exc:
        raise DriftError("%s did not gunzip: %s: %s" % (path, type(exc).__name__, exc)) from exc
    rows, missing, malformed, no_fields = [], 0, 0, 0
    # `first` is the one sighting every refusal below quotes. It starts as "nothing seen yet" and
    # each branch fills it only if it is still empty: leaving it unbound in the not-an-object branch
    # was enough to make the refusal itself raise `UnboundLocalError` -- a `ValueError`, so it walked
    # straight out of `main`'s map as exit code 1.
    first = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            malformed += 1
            if first is None:
                first = "%s: %s: %s" % (path, type(exc).__name__, exc)
            continue
        if not isinstance(row, dict):
            malformed += 1
            if first is None:
                first = "%s: a JSON %s, not a mapping" % (path, type(row).__name__)
            continue
        if not isinstance(row.get(id_key), (str, int)):
            missing += 1
            continue
        try:
            rows.append({"id": str(row[id_key]), "text": row[text_key],
                         "label_text": row[label_key]})
        except KeyError as exc:
            no_fields += 1
            if first is None:
                first = "%s: no %s field" % (path, exc)
    if malformed:
        raise DriftError("%s: %d row(s) are not JSON objects (first: %s); a shard that does not "
                         "parse cannot be scored" % (path, malformed, first))
    if no_fields:
        raise DriftError("%s: %d row(s) lack a field the suite needs (first: %s)"
                         % (path, no_fields, first))
    if missing:
        raise DriftError("%s: %d row(s) carry no %r; case_id would have to fall back to a row "
                         "number, which is not an identity" % (path, missing, id_key))
    return rows


def payload_path_for(directory: Path, lang: str, stage: str) -> Path:
    return Path(directory) / ("payload-%s-%s.json" % (stage, lang))


def artefact_paths(out, out_parity=None) -> tuple:
    """The two files one scoring pass writes: the certified artefact and its parity control.

    The control's default name is derived from `--out` rather than left to the operator, because a
    control nobody can predict the location of is a control nobody finds -- and the filename is one
    of the three places R-118 requires the regime to be recorded (the others being the summary's
    `artefacts` block and every row's `slices.regime` / `meta.calibration_status`).
    """
    out = Path(out)
    if out_parity:
        return out, Path(out_parity)
    return out, out.parent / ("%s_%s_parity%s" % (out.stem, PARITY_REGIME, out.suffix))


def run_model_stage(args, upstream: Path, lang: str, stage: str, per_lang: int,
                    payload_dir: Path) -> dict:
    """Score one language in the vendored interpreter and read its payload back.

    The stage's own exit code never becomes this tool's: a nonzero is "the model stage did not
    complete", which is one thing and gets one code, and its stderr is handed to the operator.
    """
    payload = payload_path_for(payload_dir, lang, stage)
    if payload.exists():
        payload.unlink()
    cmd = [args.python, str(Path(__file__).resolve()), "--worker",
           "--lang", lang, "--stage", stage, "--payload", str(payload),
           "--cache", str(args.cache), "--pin", str(args.pin), "--upstream", str(upstream),
           "--model", args.model, "--device", args.device or "",
           "--per-lang", str(per_lang), "--n-opts", str(args.n_opts), "--seed", str(args.seed),
           "--chunk-size", str(args.chunk_size)]
    if args.subfolder:
        cmd += ["--subfolder", args.subfolder]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT))
    except OSError as exc:
        raise IncompleteBuildError("the model stage could not be started with interpreter %r: "
                                   "%s: %s (pass --python or set AUTORATE_UPSTREAM_PYTHON)"
                                   % (args.python, type(exc).__name__, exc)) from exc
    if proc.returncode != 0:
        raise IncompleteBuildError("the model stage for %s/%s exited %d; stderr tail: %s"
                                   % (lang, stage, proc.returncode, proc.stderr[-800:]))
    if not payload.is_file():
        raise IncompleteBuildError("the model stage for %s/%s exited %d but wrote no payload at %s"
                                   % (lang, stage, proc.returncode, payload))
    try:
        data = json.loads(payload.read_text())
    except ValueError as exc:
        raise IncompleteBuildError("the model stage payload for %s/%s is not JSON (%s); the first "
                                   "200 characters: %r"
                                   % (lang, stage, exc, payload.read_text()[:200])) from exc
    data["_stage_wall_s"] = round(time.time() - started, 3)
    data["_stage_rc"] = proc.returncode
    if proc.stderr.strip():
        data["_stage_stderr_tail"] = proc.stderr[-400:]
    return data


def _upstream_softmax(upstream_module, values, temperature):
    """Call the harness's own `softmax_t`, naming a missing numeric stack the way the metric path does.

    Measured: a build layer run by an interpreter without numpy exited **1** with a traceback out of
    `check_payload`, while this module's docstring lists "no numpy" as an `IncompleteBuildError` case and
    the metric call beside it already names that refusal. rc 1 is the outcome this tool says is
    unreachable, and the parity gate was the one place it called code it does not own unwrapped.
    """
    try:
        return [float(x) for x in upstream_module.softmax_t(values, temperature)]
    except ImportError as exc:
        raise IncompleteBuildError("upstream's softmax_t could not import its numeric stack: %s: %s "
                                   "(run the build layer with `uv run --frozen python ...`, the "
                                   "interpreter that has numpy)" % (type(exc).__name__, exc)) from exc


def check_payload(payload: dict, lang: str, stage: str, per_lang: int,
                  upstream_module, asked_chunk_size: int | None = None) -> dict:
    """A model stage answers for itself: right language, right size, arrays that line up.

    `probs_probe` is upstream's own `softmax_t` on the first cases, per regime; the build layer
    recomputes it with `softmax_t` above and refuses the batch if the two diverge, because that is
    the one place here where a re-implementation could silently change every probability. Each
    regime is checked against *its own* temperatures, which is what makes the two columns separate
    facts about one forward pass rather than one number with two labels.

    The chunk layout is checked twice (R-117): against the case count the stage served, so a declared
    layout that could not have produced its own suite is refused, and against the `--chunk-size` the
    operator asked for, so the memory claim in the artefact is the claim that was actually honoured.
    Without the second one, `--chunk-size 150` would be a word typed into a command line rather than
    a property of the file, and the equivalence test in `tests/test_build_records.py` would be a
    statement about a shape this artefact did not use.
    """
    if not isinstance(payload, dict):
        raise DriftError("the %s/%s payload is a %s, not an object"
                         % (lang, stage, type(payload).__name__))
    absent = [key for key in REQUIRED_PAYLOAD_KEYS if key not in payload]
    if absent:
        raise DriftError("the %s/%s payload carries no %s: a stage that answers partially is a "
                         "stage that did not run, and the missing key would surface as a KeyError "
                         "with exit code 1 -- outside this tool's contract"
                         % (lang, stage, ", ".join(absent)))
    reported = payload["regimes"]
    extra = sorted(set(reported) - set(REGIMES)) if isinstance(reported, dict) else []
    if extra:
        raise DriftError("the %s/%s payload reports regime(s) %s, which this tool does not name or "
                         "score: a column nobody can say the temperature of cannot be published"
                         % (lang, stage, ", ".join(repr(e) for e in extra)))
    if payload.get("lang") != lang:
        raise DriftError("the %s/%s payload answers for language %r: the stages must not be "
                         "confused for one another" % (lang, stage, payload.get("lang")))
    if payload.get("stage") != stage:
        raise DriftError("the payload at %s/%s names stage %r" % (lang, stage, payload.get("stage")))
    if payload["qtype"] != QTYPE:
        raise DriftError("the %s/%s payload reports qtype %r, not %r: every record this build writes "
                         "is published as a `choice` decision, so a stage that scored a `noul` or a "
                         "`score` question would put its numbers under the wrong qtype -- and under "
                         "the wrong temperature bucket, which is chosen by qtype"
                         % (lang, stage, payload["qtype"], QTYPE))
    if not isinstance(payload["timing"], dict):
        raise DriftError("the %s/%s payload's timing is a %s, not a mapping; the build layer reads "
                         "its telemetry with .get(), so anything else would raise AttributeError at "
                         "the log line with exit code 1 -- absent telemetry is a gap, a non-mapping "
                         "is a payload that does not know its own shape"
                         % (lang, stage, type(payload["timing"]).__name__))
    arrays = ("item_ids", "gold", "option_keys", "logits", "texts")
    not_lists = [key for key in arrays if not isinstance(payload.get(key), list)]
    if not_lists:
        raise DriftError("the %s/%s payload's %s %s not a list"
                         % (lang, stage, ", ".join(not_lists),
                            "are" if len(not_lists) > 1 else "is"))
    n_cases = payload.get("n_cases")
    if n_cases != per_lang:
        raise DriftError("the %s/%s stage returned %s cases for a run of %d: a suite that came "
                         "back short would publish fewer cases than the artefact claims"
                         % (lang, stage, n_cases, per_lang))
    uneven = {key: len(payload[key]) for key in arrays if len(payload[key]) != per_lang}
    if uneven:
        raise DriftError("the %s/%s payload does not line up: %s (expected %d each); refusing to "
                         "guess which case is which" % (lang, stage,
                                                        ", ".join("%s=%d" % kv for kv in uneven.items()),
                                                        per_lang))
    chunk_size = _number(payload["chunk_size"], "%s/%s" % (lang, stage), 0, "chunk size",
                         integer=True)
    if chunk_size < 1:
        raise DriftError("the %s/%s payload reports a chunk size of %r: a batch of nothing scores "
                         "nothing, and every case would arrive with no probability at all"
                         % (lang, stage, payload["chunk_size"]))
    chunks = payload["chunks"]
    if not isinstance(chunks, list) or not chunks:
        raise DriftError("the %s/%s payload's chunks is %r, not a non-empty list of batch sizes: "
                         "the chunk layout is the only record of how this suite was collated, and "
                         "without it the chunking-equivalence claim has no subject"
                         % (lang, stage, chunks))
    sizes = [int(_number(c, "%s/%s" % (lang, stage), i, "chunk size %d" % i, integer=True))
             for i, c in enumerate(chunks)]
    if asked_chunk_size is not None and int(chunk_size) != int(asked_chunk_size):
        raise DriftError("the %s/%s stage scored in batches of %d after being asked for %d: the "
                         "chunk size is this artefact's memory claim, so a stage that ran a "
                         "different layout has to say so rather than be believed"
                         % (lang, stage, int(chunk_size), int(asked_chunk_size)))
    want_sizes = chunk_sizes(per_lang, int(chunk_size))
    if sizes != want_sizes:
        raise DriftError("the %s/%s payload says it scored %d cases in batches of %s (%d batches), "
                         "which is not %s -- a stage whose declared layout could not have produced "
                         "its own case count cannot be the evidence for a claim about layouts"
                         % (lang, stage, per_lang, sizes, len(sizes), want_sizes))
    value_sets = []
    for i, (z, keys) in enumerate(zip(payload["logits"], payload["option_keys"])):
        if len(z) != len(keys):
            raise DriftError("%s/%s case %d: %d logits for %d options"
                             % (lang, stage, i, len(z), len(keys)))
        if len(keys) < 2:
            raise DriftError("%s/%s case %d: the ballot has %d option(s), which is not a choice "
                             "question whatever the stage reported as its qtype"
                             % (lang, stage, i, len(keys)))
        # Checked as numbers, not as things that coerce to numbers: `float("0.5")` succeeds, and a
        # value the stage serialized oddly would otherwise be averaged into the distribution.
        value_sets.append([_number(v, "%s/%s" % (lang, stage), i, "logit %d" % j)
                           for j, v in enumerate(z)])
    probes = {}
    warnings_list = payload["warnings"]
    if not isinstance(warnings_list, list) or any(not isinstance(w, dict) for w in warnings_list):
        raise DriftError("the %s/%s payload's warnings is %s rather than a list of objects; the "
                         "clamp warning is the fact R-118 turns into a publication policy, so it "
                         "travels as data and not as a line of captured stderr"
                         % (lang, stage, type(warnings_list).__name__))
    for regime in REGIMES:
        block = regime_block(payload, regime)
        temps = block["temperatures"]
        if not isinstance(temps, list):
            raise DriftError("the %s/%s payload's temperatures for regime %r is not a list"
                             % (lang, stage, regime))
        if len(temps) != per_lang:
            raise DriftError("the %s/%s payload does not line up: temperatures=%d for regime %r "
                             "(expected %d); refusing to guess which case is which"
                             % (lang, stage, len(temps), regime, per_lang))
        for i in range(per_lang):
            _number(temps[i], "%s/%s" % (lang, stage), i, "temperature")
        # The stage says what its own confidence means; this layer says so again, from the regime
        # name and the warnings the checkpoint stack actually emitted. Two interpreters, one fact,
        # and a disagreement is a refusal -- a column that could be read as calibrated because the
        # side that wrote it was feeling generous is exactly the defect R-118 exists to prevent.
        stated = block["calibration_status"]
        expected = calibration_status(regime, warning_emitted=bool(warnings_list))
        if stated != expected:
            raise DriftError("the %s/%s payload's block for regime %r calls its confidence %r, but "
                             "this build derives %r from the regime and the %d upstream warning(s); "
                             "the calibration status of a published number is not a label each side "
                             "may choose" % (lang, stage, regime, stated, expected,
                                             len(warnings_list)))
        probe = block["probs_probe"]
        if not isinstance(probe, list) or not probe:
            raise DriftError("the %s/%s payload carried no probs_probe for regime %r: the build "
                             "layer checks its own softmax against upstream's, and an empty probe "
                             "would check nothing" % (lang, stage, regime))
        limit = min(len(probe), PROBE_PROBS_CASES)
        rows = [[_number(v, "%s/%s/%s" % (lang, stage, regime), i, "probs_probe entry %d" % j)
                 for j, v in enumerate(probe[i])] for i in range(limit)]
        for i in range(limit):
            want = rows[i]
            got = softmax_t(value_sets[i], temps[i])
            if len(want) != len(got):
                raise DriftError("%s/%s/%s case %d: probs_probe has %d entries for %d options"
                                 % (lang, stage, regime, i, len(want), len(got)))
            worst = max(abs(a - b) for a, b in zip(want, got))
            if worst > SOFTMAX_TOL:
                raise DriftError("%s/%s regime=%s: this build's softmax_t differs from upstream's by "
                                 "%.3g on case %d, which is more than %.1e; every probability in "
                                 "the artefact would be ours rather than the harness's"
                                 % (lang, stage, regime, worst, i, SOFTMAX_TOL))
        if upstream_module is not None:
            for i in range(limit):
                theirs = _upstream_softmax(upstream_module, value_sets[i], temps[i])
                worst = max(abs(a - b) for a, b in zip(theirs, rows[i]))
                if worst > SOFTMAX_TOL:
                    raise DriftError("%s/%s regime=%s: the payload's probs_probe is not what "
                                     "upstream's softmax_t returns here (max diff %.3g); the stage "
                                     "and the tree disagree" % (lang, stage, regime, worst))
        probes[regime] = probe
    return probes


def check_artefact_covers_probe(records: list, probe_records: list, lang: str) -> int:
    """The gate was run on cases that must be in the file it certifies. Returns the overlap.

    Upstream's `build_suite` draws each case from a fresh `random.Random(seed)` walk, so the first
    `min(n)` cases of a longer run are the shorter run's cases -- same item, same ballot, same gold.
    If they are not, the parity row was not a statement about this artefact and the build stops.
    """
    limit = min(len(records), len(probe_records))
    if not limit:
        raise ParityError("the artefact and the gated probe share no case at all, so the parity "
                          "proof would not be a proof about this file")
    for i in range(limit):
        for key in ("case_id", "gold", "options"):
            if records[i][key] != probe_records[i][key]:
                raise ParityError("the artefact's prefix diverges from the gated probe at case %d "
                                  "(%s=%r against the probe's %s=%r): the probe would not be a "
                                  "statement about the rows this file contains"
                                  % (i, key, records[i][key], key, probe_records[i][key]))
    return limit


def stage_device(payload: dict):
    """The device the stage reported, or None -- a missing telemetry key is never a crash."""
    timing = payload.get("timing")
    return timing.get("device") if isinstance(timing, dict) else None


def record_line(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True)


# --------------------------------------------------------------------------- the model stage
def warning_dict(w) -> dict:
    """One warning the checkpoint stack emitted, as payload data rather than as a line of stderr.

    R-118 turns this library's clamp warning into a publication policy, and a policy needs the fact
    it rests on: which bucket was rejected, what was applied instead, and which code said so. The
    build layer runs the stage with stderr captured and only ever tails it, so a warning that lived
    only there would reach the artefact as nothing at all.
    """
    return {"category": getattr(w.category, "__name__", str(w.category)),
            "message": str(w.message),
            "where": "%s:%s" % (Path(str(w.filename)).name, w.lineno)}


def _load_agent(laya, args):
    """`laya.load`, with everything it warns about kept.

    The warning is emitted once per Agent construction, at `laya/agent.py`, and Python's default
    filter would show it once per location for the life of the process -- so `record=True` plus
    `simplefilter("always")` is what makes "did this load reject a bucket?" an answerable question
    instead of a guess about stderr ordering.
    """
    import warnings

    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        agent = laya.load(args.model, device=args.device or None,
                          subfolder=args.subfolder or None)
    agent.model.eval()
    return agent, [warning_dict(w) for w in seen]


def peak_rss_mib():
    """The stage's own peak resident set in MiB, or None where the platform reports no such thing.

    `--chunk-size` is a claim about bytes, so the run that produces the artefact records what it
    actually used; `ru_maxrss` is bytes on darwin and kilobytes on linux, which is why the divisor
    is chosen by platform rather than assumed. Measured through `resource` and not by wrapping the
    driver in `/usr/bin/time -l`, because the grandchild's peak does not propagate through an
    interpreter hand-off and the number that arrives then is the parent's (8.4 MB, measured).
    """
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(float(peak) / divisor, 3)


def regime_column(le, QTYPES, np, agent, logits, gold, regime, seen_warnings):
    """One regime's numbers, from logits that are already in hand -- no second forward pass.

    `temperature_for(..., unclamped=…)` is the whole difference between the two columns: the same
    logits read at the checkpoint's raw bucket temperature, or at the value upstream clamps it to.
    Upstream's own `summarise` runs per regime so each side of the parity gate is stated under the
    temperature it was actually computed at, and the calibration status is the library's verdict
    (`calibration_status`), not this tool's name for the column.
    """
    unclamped = regime == "unclamped"
    temperatures = [float(le.temperature_for(agent, QTYPES["choice"], len(z), unclamped))
                    for z in logits]
    confs, cors, preds = [], [], []
    for z, t, g in zip(logits, temperatures, gold):
        p = le.softmax_t(z, t)
        confs.append(float(p.max()))
        preds.append(int(np.argmax(p)))
        cors.append(float(int(preds[-1] == int(g))))
    upstream_report = le.summarise(confs, cors, gold, preds)
    return {
        "temperatures": temperatures,
        "probs_probe": [[float(x) for x in le.softmax_t(z, t)]
                        for z, t in list(zip(logits, temperatures))[:PROBE_PROBS_CASES]],
        "upstream_report": {k: round(float(v), 6) if isinstance(v, (int, float)) else v
                            for k, v in upstream_report.items()},
        "calibration_status": calibration_status(regime, warning_emitted=bool(seen_warnings)),
    }


def _score_batch(laya, le, np, QTYPES, args, rows):
    """Every call into the checkpoint stack, in one place, so one clause can name what they raise.

    Upstream's own `build_suite` is what orders the sampling -- "that is what made the parity row
    reproduce" -- and the label pool is every label in the shard, exactly as upstream's
    `run_language` builds it. Slicing the shard before computing the pool is the one way to change
    every ballot, and the parity gate is what would notice.

    The suite is then scored in chunks (R-117) and both regimes are read off the one set of logits
    (R-118), so the cost of the second artefact is a second softmax over numbers already in memory.
    """
    started = time.time()
    agent, seen_warnings = _load_agent(laya, args)
    load_s = time.time() - started
    cases, gold, option_keys = le.build_suite(
        rows, sorted({r["label_text"] for r in rows}), args.per_lang, args.n_opts, args.seed)
    if len(cases) != args.per_lang:
        raise DriftError("upstream's build_suite returned %d cases for a run of %d"
                         % (len(cases), args.per_lang))
    # The qtype is read off the questions that were actually built, not typed in. `build_suite`
    # emits `choice` today, but the temperature bucket, the record's `qtype`, and the comparability
    # claim all key off it -- and Task 4's other certified tasks point at checkpoints that answer
    # `score` and `noul` questions, where a silently mislabelled ballot is the whole defect.
    qtypes = sorted({qdef["type"] for _state, questions in cases
                     for qdef in questions.values()})
    if qtypes != [QTYPE]:
        raise DriftError("upstream's build_suite returned question type(s) %s, not just %r: this "
                         "driver scores one ballot shape and publishes every record as qtype=%r, so "
                         "a suite of any other shape is refused at the stage rather than labelled "
                         "with the wrong qtype and scored at the wrong bucket"
                         % (", ".join(repr(q) for q in qtypes), QTYPE, QTYPE))
    scored = time.time()
    logits, chunks = score_cases_in_chunks(lambda part: le.score_cases(agent, part),
                                           cases, args.chunk_size)
    score_s = time.time() - scored
    regimes = {regime: regime_column(le, QTYPES, np, agent, logits, gold, regime, seen_warnings)
               for regime in REGIMES}
    import torch
    return {
        "lang": args.lang, "stage": args.stage, "n_cases": len(cases), "n_opts": args.n_opts,
        "seed": args.seed, "qtype": qtypes[0],
        "item_ids": [r["id"] for r in rows[:len(cases)]],
        "texts": [r["text"] for r in rows[:len(cases)]],
        "gold": [int(g) for g in gold],
        "option_keys": [list(k) for k in option_keys],
        "logits": [[float(x) for x in z] for z in logits],
        "regimes": regimes,
        "chunk_size": int(args.chunk_size), "chunks": [int(c) for c in chunks],
        "warnings": seen_warnings,
        "timing": {"load_s": round(load_s, 3), "score_s": round(score_s, 3),
                   "cases_per_s": round(len(cases) / score_s, 4) if score_s > 0 else None,
                   "chunks": len(chunks), "chunk_size": int(args.chunk_size),
                   "peak_rss_mib": peak_rss_mib(),
                   "device": str(agent.device),
                   "torch": getattr(torch, "__version__", "unknown"),
                   "laya": getattr(laya, "__version__", "unknown")},
    }


def compare_layouts(samples: dict) -> float:
    """Worst difference between chunk layouts, and a refusal when there is any at all.

    R-117's safety claim is that cutting the suite into batches moves nothing: the same cases, in the
    same order, collated differently, must come back with the same logits and the same probabilities.
    `float32` marker logits have no room for a tolerance argument -- if a batch had moved a number it
    would have moved it by far more than an ulp, and a "small" difference would be the beginning of
    every certificate downstream quoting a different probability than the one this file holds. So the
    comparison is bit-for-bit, in both directions: the exact value, and the maximum absolute
    difference, which is 0.0 or a refusal naming the case, the option and the layout that disagreed.

    The samples are `{label: {"logits": [...], "chunk_size": int, "chunks": [...], "regimes":
    {regime: {"probs": [...]}}}}`. Only the first sample's shapes are trusted; a layout that answered
    with a different count is the same off-by-one the chunker itself refuses.
    """
    labels = list(samples)
    if len(labels) < 2:
        raise DriftError("chunk equivalence needs at least two layouts to compare and was given %s: "
                         "one layout compared with itself proves nothing about chunking"
                         % (", ".join(labels) or "nothing"))
    worst = 0.0
    first = samples[labels[0]]
    for label in labels[1:]:
        other = samples[label]
        if len(other["logits"]) != len(first["logits"]):
            raise DriftError("layout %r scored %d cases and layout %r scored %d: the equivalence "
                             "claim would be about two different suites"
                             % (label, len(other["logits"]), labels[0], len(first["logits"])))
        for i, (a, b) in enumerate(zip(first["logits"], other["logits"])):
            if len(a) != len(b):
                raise DriftError("layout %r case %d has %d options against layout %r's %d"
                                 % (label, i, len(b), labels[0], len(a)))
            for j, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    raise DriftError("chunking is not free: layout %r case %d option %d returned %r "
                                     "where layout %r returned %r (difference %.3g). Every "
                                     "probability in the artefact would depend on how the suite was "
                                     "batched, so the equivalence claim fails and nothing is "
                                     "published" % (label, i, j, y, labels[0], x, abs(x - y)))
                worst = max(worst, abs(x - y))
        for regime in sorted(first["regimes"]):
            if regime not in other["regimes"]:
                raise DriftError("layout %r scored regime %r and layout %r did not: both regimes come "
                                 "out of the one forward pass, in every layout"
                                 % (labels[0], regime, label))
            mine = first["regimes"][regime]["probs"]
            theirs = other["regimes"][regime]["probs"]
            if len(mine) != len(theirs):
                raise DriftError("layout %r regime %r scored %d distributions against %d"
                                 % (label, regime, len(theirs), len(mine)))
            for i, (a, b) in enumerate(zip(mine, theirs)):
                if a != b:
                    raise DriftError("chunking is not free: layout %r regime %r case %d returns a "
                                     "different distribution from layout %r (%r against %r). A "
                                     "certificate built on either file would be certifying a batch "
                                     "shape, not a model"
                                     % (label, regime, i, labels[0], b, a))
                worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
    return worst


def _equivalence_batch(laya, le, np, QTYPES, args, rows):
    """One load, several chunk layouts, the same cases: R-117's claim as a command.

    The build scores every stage in one layout, so this is the only place the driver ever cuts the
    same suite two ways -- which is why the equivalence test drives it through `--worker` rather than
    through a script written by the test: the claim has to be about the call shape the artefact was
    produced with, in the interpreter that produced it.
    """
    started = time.time()
    agent, seen_warnings = _load_agent(laya, args)
    cases, gold, option_keys = le.build_suite(
        rows, sorted({r["label_text"] for r in rows}), args.per_lang, args.n_opts, args.seed)
    layouts = [int(x) for x in str(args.layouts).split(",") if x.strip()]
    if len(set(layouts)) < 2:
        raise UsageRefusal("--layouts %r needs at least two distinct chunk sizes to compare"
                           % args.layouts)
    samples = {}
    for size in layouts:
        logits, chunks = score_cases_in_chunks(lambda part: le.score_cases(agent, part),
                                               cases, size)
        regimes = {}
        for regime in REGIMES:
            temperatures = [float(le.temperature_for(agent, QTYPES["choice"], len(z),
                                                    regime == "unclamped")) for z in logits]
            regimes[regime] = {
                "temperatures": temperatures,
                "probs": [[float(x) for x in le.softmax_t(z, t)]
                          for z, t in zip(logits, temperatures)],
                "rounded_probs": [rounded_probs(softmax_t([float(v) for v in z], t))
                                  for z, t in zip(logits, temperatures)]}
        samples[str(size)] = {"chunk_size": int(size), "chunks": [int(c) for c in chunks],
                              "logits": [[float(x) for x in z] for z in logits],
                              "regimes": regimes}
    worst = compare_layouts(samples)
    import torch
    return {
        "lang": args.lang, "stage": args.stage, "n_cases": len(cases), "n_opts": args.n_opts,
        "seed": args.seed, "qtype": QTYPE,
        "item_ids": [r["id"] for r in rows[:len(cases)]],
        "gold": [int(g) for g in gold],
        "option_keys": [list(k) for k in option_keys],
        "layouts": [str(s) for s in layouts], "samples": samples,
        "max_abs_difference": worst,
        "bit_identical": worst == 0.0,
        "warnings": seen_warnings,
        "chunk_size": int(layouts[0]), "chunks": samples[str(layouts[0])]["chunks"],
        "timing": {"load_s": round(time.time() - started, 3), "device": str(agent.device),
                   "peak_rss_mib": peak_rss_mib(), "prefix": sys.prefix,
                   "torch": getattr(torch, "__version__", "unknown"),
                   "laya": getattr(laya, "__version__", "unknown")},
    }


def worker_main(args) -> int:
    """One language, one chunked forward pass, both regimes' logits and temperatures out.

    Runs ONLY in the vendored interpreter. Nothing in this function reaches the checkpoint stack
    except through `_score_batch`, and that call is the single place in the repository where an
    exception we do not own is caught broadly.
    """
    sys.path.insert(0, str(Path(args.upstream)))
    sys.path.insert(0, str(Path(args.upstream) / "research" / "eval"))
    try:
        import laya
        import laya_eval as le
        import numpy as np
        from laya.common import QTYPES
    except ImportError as exc:
        raise IncompleteBuildError("the model stage could not import the checkpoint stack: %s: %s "
                                   "(is this the vendored interpreter? pass --python)"
                                   % (type(exc).__name__, exc)) from exc

    pin = require_manifest(load_manifest(args.pin))
    rows = load_rows(args.cache, args.lang)
    if len(rows) < args.per_lang:
        raise DriftError("shard %s holds %d rows, the run asked for %d"
                         % (args.lang, len(rows), args.per_lang))
    if args.chunk_size < 1:
        raise UsageRefusal("--chunk-size must be at least 1 case, not %d: a batch of nothing scores "
                           "nothing, and every case would arrive with no probability at all"
                           % args.chunk_size)

    if args.stage == "equivalence":
        try:
            payload = _equivalence_batch(laya, le, np, QTYPES, args, rows)
        except (BuildError, ParityError, UsageRefusal):
            raise
        except Exception as exc:
            raise UpstreamStageError("the equivalence stage for %s failed inside the checkpoint "
                                     "stack: %s: %s" % (args.lang, type(exc).__name__, exc)) from exc
        Path(args.payload).write_text(json.dumps(payload))
        print("worker %s/%s n=%d layouts=%s max_abs_difference=%r bit_identical=%s prefix=%s"
              % (args.lang, args.stage, payload["n_cases"], ",".join(payload["layouts"]),
                 payload["max_abs_difference"], payload["bit_identical"],
                 payload["timing"]["prefix"]), file=sys.stderr)
        return EXIT_OK

    try:
        payload = _score_batch(laya, le, np, QTYPES, args, rows)
    except (BuildError, ParityError, UsageRefusal):
        raise
    except Exception as exc:
        raise UpstreamStageError("the model stage for %s/%s failed inside the checkpoint stack: "
                                 "%s: %s" % (args.lang, args.stage, type(exc).__name__, exc)) from exc
    Path(args.payload).write_text(json.dumps(payload))
    print("worker %s/%s n=%d chunks=%d score_s=%.1f device=%s regimes=%s"
          % (args.lang, args.stage, payload["n_cases"], payload["timing"]["chunks"],
             payload["timing"]["score_s"], payload["timing"]["device"], ",".join(REGIMES)),
          file=sys.stderr)
    return EXIT_OK


def records_for_regime(payload: dict, regime: str, lang: str, u_seed: int,
                        pin: dict, args) -> list:
    """One regime's Records from one stage payload: same cases, same `u`, different temperature.

    The block's own `calibration_status` is handed over rather than re-derived here, because
    `check_payload` has already refused the payload when what it states and what the regime plus the
    checkpoint's warnings imply are not the same sentence. Two interpreters agreeing on one fact is
    the only thing that lets a reader take a row's word for what its confidence means.

    Both regimes draw from the same seed, so the recorded `u` of a case is identical in the certified
    file and in the parity control: the two artefacts differ in one temperature and in nothing else
    that a certificate depends on.
    """
    block = regime_block(payload, regime)
    return records_from_logits(
        payload["logits"], payload["gold"], payload["option_keys"], lang,
        draw_u(seed=u_seed, n=payload["n_cases"]),
        item_ids=[case_id_for(lang, i) for i in payload["item_ids"]],
        temperatures=block["temperatures"], texts=payload["texts"],
        backend=args.backend, regime=regime, calibration=block["calibration_status"],
        suite_seed=args.seed, u_seed=u_seed, dataset=pin["dataset"], revision=pin["revision"],
        license_id=pin["license"], checkpoint=args.model, device=stage_device(payload))


# ---------------------------------------------------------------------------- the build layer
def build(args) -> int:
    pin = require_manifest(load_manifest(args.pin))
    for key in ("dataset", "revision", "license"):
        if not pin.get(key):
            raise DriftError("%s declares no %r, so the records would publish numbers with no "
                             "owner and no attribution" % (args.pin, key))
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    if not langs:
        raise UsageRefusal("--langs resolved to nothing: %r" % args.langs)
    languages = list(dict.fromkeys(langs))
    for lang in languages:
        # Resolved before anything expensive: a language that is not pinned is the operator's
        # mistake, and skipping it silently would publish an artefact with a hole in it.
        pin_shard(pin, lang)
    if PARITY["lang"] not in languages:
        raise ParityError("--langs %r does not include %r, the language the published parity row "
                          "is stated for: the gate could not be a claim about this artefact"
                          % (languages, PARITY["lang"]))
    if args.chunk_size < 1:
        raise UsageRefusal("--chunk-size %d is not a batch size: at least one case per collated "
                           "forward pass, or nothing is scored and every case arrives with no "
                           "probability at all" % args.chunk_size)
    if args.n_opts != PARITY["n_opts"]:
        raise UsageRefusal("--n-opts %d is not the option count PARITY is stated under (%d)"
                           % (args.n_opts, PARITY["n_opts"]))
    if args.seed != PARITY["seed"]:
        raise UsageRefusal("--seed %d is not the seed PARITY is stated under (%d)"
                           % (args.seed, PARITY["seed"]))

    upstream = resolve_upstream(args.upstream)
    if upstream is None:
        raise IncompleteBuildError("no vendored tree found: pass --upstream, set "
                                   "AUTORATE_UPSTREAM_ROOT, or check out a `laya*` sibling of this "
                                   "repository")
    upstream = Path(upstream)
    args.cache, args.pin = Path(args.cache), Path(args.pin)
    args.python = args.python or upstream_python(upstream)
    out, out_parity = artefact_paths(args.out, args.out_parity)
    if out == out_parity:
        raise UsageRefusal("--out and --out-parity name the same path (%s): one pass produces two "
                           "different numbers, and a file that holds whichever regime was written "
                           "last holds neither" % out)
    summary = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "pin": {"path": str(args.pin), "revision": pin["revision"], "dataset": pin["dataset"],
                       "n_files": pin["n_files"], "rows_total": pin["rows_total"],
                       "license": pin["license"]},
               "cache": str(args.cache), "out": str(out), "langs": list(dict.fromkeys(langs)),
               "per_lang": args.per_lang, "n_opts": args.n_opts, "suite_seed": args.seed,
               "u_seed": args.u_seed, "backend": args.backend,
               # The regime is not an input to this build: one pass answers both, and which column
               # each artefact holds is stated here and in the file names and in every row (R-118).
               "regimes": list(REGIMES), "certified_regime": CERTIFIED_REGIME,
               "parity_regime": PARITY_REGIME,
               "chunk_size": int(args.chunk_size),
               "model": args.model, "subfolder": args.subfolder, "python": args.python,
               "upstream": str(upstream), "probability_decimals": PROB_DECIMALS,
               "parity_target": {k: PARITY[k] for k in PROBE_FIGURES},
               "identity": {k: PARITY[k] for k in PROBE_IDENTITY},
               "interpreter": {"executable": sys.executable, "version": sys.version.split()[0]}}

    # The corpus before the checkpoint: a cache that is not the pinned bytes would make every
    # figure downstream unattributable, and loading the model to find that out is the wrong order.
    report = check_cache(args.cache, pin, languages, max(args.per_lang, PARITY["per_lang"]))
    le = load_upstream_eval(upstream)
    summary.update({"cache_check": {"checked": report["checked"], "ok": report["ok"],
                                    "missing": len(report["missing"]),
                                    "mismatched": len(report["mismatched"])}})
    # Both destinations are checked before either is written, and neither directory is created:
    # a build that half-lands because the second path was typoed is a build with two artefacts and
    # no statement of which one it meant to have.
    destinations = {CERTIFIED_REGIME: out, PARITY_REGIME: out_parity}
    for regime, path in destinations.items():
        if not path.parent.is_dir():
            raise IncompleteBuildError("--out%s %s (regime %s): its directory does not exist; "
                                       "nothing was created and nothing was written"
                                       % ("" if regime == CERTIFIED_REGIME else "-parity",
                                          path, regime))
    started = time.time()
    tmp_paths = {regime: (path.parent / (path.name + ".tmp"))
                 for regime, path in destinations.items()}
    positions = {lang: i for i, lang in enumerate(languages)}
    probe_u_seed = args.u_seed + positions.get(PARITY["lang"], 0)
    written: dict = {}
    overlaps: dict = {}
    try:
        with tempfile.TemporaryDirectory(prefix="planC-payloads-") as payload_dir:
            payloads = Path(payload_dir)

            # 1. the gate. The published row, on the published conditions, through this tool's own
            # conversion -- not through a side path that could pass while the artefact fails. It is
            # stated under `PARITY_REGIME` and applied to that regime's numbers only: the certified
            # column is a different quantity and must never be nudged until it matches this row.
            probe_payload = run_model_stage(args, upstream, PARITY["lang"], "probe",
                                            PARITY["per_lang"], payloads)
            check_payload(probe_payload, PARITY["lang"], "probe", PARITY["per_lang"], le,
                                asked_chunk_size=args.chunk_size)
            probe_records = {regime: records_for_regime(
                probe_payload, regime, PARITY["lang"], probe_u_seed, pin, args)
                for regime in REGIMES}
            probe_reports = {regime: summarise_with(le, probe_records[regime])
                             for regime in REGIMES}
            # Two sides of one claim, both against the published row. The stage's own report is
            # upstream's arithmetic on the checkpoint's unrounded softmax in the vendored
            # interpreter; `probe_reports` is this build's 6-decimal vector and the argmax of that
            # vector, i.e. the numbers the records actually carry. Gating only the second would let
            # a conversion that moved one prediction relative to upstream's own choice pass while
            # the row upstream published about the same logits said otherwise.
            check_parity(stage_report(probe_payload, PARITY_REGIME), PARITY, side=STAGE_SIDE)
            got = check_parity(probe_reports[PARITY_REGIME], PARITY, side=BUILT_SIDE)
            print("parity ok: probe lang=%s n=%s n_opts=%s seed=%s regime=%s %s"
                  % (PARITY["lang"], PARITY["per_lang"], PARITY["n_opts"], PARITY["seed"],
                     PARITY_REGIME, " ".join("%s=%.4f" % (k, got[k]) for k in PROBE_FIGURES)))
            print("certified regime: %s (%s); the unclamped run above is the parity control"
                  % (CERTIFIED_REGIME,
                     regime_block(probe_payload, CERTIFIED_REGIME)["calibration_status"]))
            summary["probe"] = {
                "regime": PARITY_REGIME,
                "report": probe_reports[PARITY_REGIME],
                "reports": probe_reports,
                "stage_reports": {regime: stage_report(probe_payload, regime)
                                  for regime in REGIMES},
                "calibration_status": {regime: regime_block(probe_payload, regime)
                                       ["calibration_status"] for regime in REGIMES},
                "upstream_report": regime_block(probe_payload, PARITY_REGIME)["upstream_report"],
                "warnings": payload_warnings(probe_payload),
                "chunks": probe_payload["chunks"], "chunk_size": probe_payload["chunk_size"],
                "timing": probe_payload["timing"],
                "device": stage_device(probe_payload),
                "u_seed": probe_u_seed,
                "wall_s": probe_payload["_stage_wall_s"]}

            # 2. the two artefacts, one language per pass, both streamed to temp siblings of their
            # own destination and renamed into place only once every language is in both of them.
            files = {regime: tmp_paths[regime].open("w") for regime in REGIMES}
            try:
                for lang in languages:
                    payload = run_model_stage(args, upstream, lang, "full", args.per_lang, payloads)
                    check_payload(payload, lang, "full", args.per_lang, le,
                            asked_chunk_size=args.chunk_size)
                    u_seed = args.u_seed + positions[lang]
                    records = {regime: records_for_regime(payload, regime, lang, u_seed, pin, args)
                               for regime in REGIMES}
                    per_regime = {}
                    for regime in REGIMES:
                        recs = records[regime]
                        if lang == PARITY["lang"]:
                            overlaps[regime] = check_artefact_covers_probe(
                                recs, probe_records[regime], lang)
                        for rec in recs:
                            files[regime].write(record_line(rec) + "\n")
                        files[regime].flush()
                        per_regime[regime] = {
                            "report": summarise_with(le, recs),
                            "upstream_report": regime_block(payload, regime)["upstream_report"],
                            "calibration_status": regime_block(payload, regime)
                                                  ["calibration_status"],
                            "records": len(recs)}
                    written[lang] = {
                        "regimes": per_regime,
                        # The certified column is the one this artefact is *for*; the flat keys stay
                        # as its mirror, so a reader of an old summary field gets the published
                        # number rather than whichever regime happened to be written first.
                        "report": per_regime[CERTIFIED_REGIME]["report"],
                        "upstream_report": per_regime[CERTIFIED_REGIME]["upstream_report"],
                        "records": per_regime[CERTIFIED_REGIME]["records"],
                        "regime": CERTIFIED_REGIME,
                        "calibration_status": per_regime[CERTIFIED_REGIME]["calibration_status"],
                        "parity_control_regime": PARITY_REGIME,
                        "timing": payload["timing"], "u_seed": u_seed,
                        "device": stage_device(payload),
                        "chunks": payload["chunks"], "chunk_size": payload["chunk_size"],
                        "warnings": payload_warnings(payload),
                        "wall_s": payload["_stage_wall_s"],
                        "stderr_tail": payload.get("_stage_stderr_tail", "")}
                    for regime in REGIMES:
                        # Every regime's row is printed and kept, but only the control's is a claim
                        # about upstream's table: the headline figures in the log are the certified
                        # ones, labelled, so `lang=en …` cannot be read as the parity row.
                        print("lang=%s regime=%s n=%d %s"
                              % (lang, regime, per_regime[regime]["records"],
                                 " ".join("%s=%.4f" % (k, round(float(per_regime[regime]
                                          ["report"][k]), 4)) for k in PROBE_FIGURES)))
                    print("lang=%s n=%d cases_per_s=%s chunks=%s stage_wall_s=%s"
                          % (lang, len(records[CERTIFIED_REGIME]),
                             payload["timing"].get("cases_per_s"), len(payload["chunks"]),
                             payload["_stage_wall_s"]))
            finally:
                for handle in files.values():
                    # fsync then close, on the handle that is still open: reopening the temp file to
                    # sync it would be a second writer on a file this build is about to rename.
                    os.fsync(handle.fileno())
                    handle.close()
            for regime in REGIMES:
                os.replace(tmp_paths[regime], destinations[regime])
    finally:
        for temp in tmp_paths.values():
            if temp.exists():
                temp.unlink()
    summary["languages"] = written
    summary["records_written"] = sum(v["records"] for v in written.values())
    # The overlap is what `check_artefact_covers_probe` measured, per regime, not what the
    # conditions imply: the same number computed two ways would let a build that compared nothing
    # report the overlap it was supposed to have.
    summary["probe_prefix_overlap"] = overlaps
    summary["artefacts"] = {
        regime: {"path": str(destinations[regime]),
                 "role": "certified" if regime == CERTIFIED_REGIME else "parity control",
                 "regime": regime,
                 "calibration_status": written[languages[0]]["regimes"][regime]
                                       ["calibration_status"] if written else None,
                 "records": sum(v["regimes"][regime]["records"] for v in written.values()),
                 "chunk_size": int(args.chunk_size)}
        for regime in REGIMES}
    summary["wall_s"] = round(time.time() - started, 3)
    # `stage_device` digs the device out of a *payload*; handed the timing sub-dict it returned None
    # for every run, so the summary of a real build said nothing about which device produced its
    # numbers -- measured on the pilot, where every stage reported mps and the field read None.
    summary["device"] = written[languages[0]]["device"] if written else None
    print("wrote %d records for %d languages, regimes %s, chunk_size %d, to %s and %s in %.1f s"
          % (summary["records_written"], len(written), " and ".join(REGIMES), args.chunk_size,
             destinations[CERTIFIED_REGIME], destinations[PARITY_REGIME], summary["wall_s"]))
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=2, sort_keys=True))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/build_records.py",
        description="Score a pinned MASSIVE cache offline and write full-distribution Records.")
    parser.add_argument("--worker", action="store_true",
        help=argparse.SUPPRESS)
    ap = parser
    ap.add_argument("--cache", required=True, help="the pinned MASSIVE cache directory")
    ap.add_argument("--out", default=None,
                    help="the CERTIFIED records JSONL (regime %r)" % CERTIFIED_REGIME)
    ap.add_argument("--out-parity", default=None, dest="out_parity",
                    help="the parity-control JSONL (regime %r); defaults to the sibling of --out "
                         "named for its regime" % PARITY_REGIME)
    ap.add_argument("--pin", default=str(DEFAULT_PIN))
    ap.add_argument("--langs", default="en,de,sw")
    ap.add_argument("--per-lang", type=int, default=2974,
                    help="cases per language in the artefact; it does not size the batch, which "
                         "--chunk-size does")
    ap.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, dest="chunk_size",
                    help="cases per collated forward pass (R-117); ~%.1f GiB per %d cases on this "
                         "checkpoint, and one 2,974-case batch is ~48.9 GB"
                         % (3.6, DEFAULT_CHUNK_SIZE))
    ap.add_argument("--n-opts", type=int, default=PARITY["n_opts"])
    ap.add_argument("--seed", type=int, default=PARITY["seed"])
    ap.add_argument("--u-seed", type=int, default=PARITY["seed"], dest="u_seed")
    ap.add_argument("--backend", default=BACKEND)
    ap.add_argument("--model", default="convaiinnovations/laya")
    ap.add_argument("--subfolder", default=None)
    ap.add_argument("--device", default=None, help="cpu, cuda, mps (default: upstream's auto)")
    ap.add_argument("--upstream", default=None, help="the vendored tree (default: discovered)")
    ap.add_argument("--python", default=None, help="interpreter for the model stage")
    ap.add_argument("--payload", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--layouts", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--lang", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--stage", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--summary", default=None, help="write the measured facts of this run here")
    ap.add_argument("--force", action="store_true", help="replace an existing --out or "
                    "--out-parity file; without it the driver refuses before it works")
    return parser


def _refuse_existing_destinations(args):
    """Refuse to replace an existing artefact unless `--force` was passed, before the build starts.

    Both destinations of one pass are separate regimes of the same run, and `--out-parity` defaults to a
    sibling name, so a mistyped `--out` can point straight at a published records file. The guard runs in
    `main`, not in `build`, so nothing expensive has happened by the time it speaks.
    """
    if args.force:
        return
    out, out_parity = artefact_paths(args.out, args.out_parity)
    existing = sorted({str(path) for path in (out, out_parity)
                       if path is not None and path.exists()})
    if existing:
        raise UsageRefusal("refusing to overwrite %s: pass --force to replace it (the certified and "
                           "parity regimes are separate files and --out-parity defaults to a sibling "
                           "of --out, so a mistyped destination is easy to aim at a real artefact)"
                           % ", ".join(existing))


def main(argv=None) -> int:
    """Map every reachable outcome onto 0 / 2 / 3 / 4. An rc 1 is a failure this tool did not name."""
    args = build_parser().parse_args(argv)
    try:
        if args.worker:
            if not args.payload or not args.lang or args.stage not in WORKER_STAGES:
                raise UsageRefusal("--worker needs --lang, --stage and --payload")
            if not args.upstream:
                # The build layer always passes it, so a bare `--worker` on a command line reached
                # `Path(None)` inside the stage: a `TypeError`, and exit code 1 -- the one outcome
                # this module says is unreachable. Found by running the equivalence stage by hand.
                raise UsageRefusal("--worker needs --upstream: the stage imports the checkpoint "
                                   "stack from the tree it is told about, and does not guess one")
            return worker_main(args)
        if args.out is None:
            raise UsageRefusal("--out is required unless --worker is set")
        _refuse_existing_destinations(args)
        return build(args)
    except ParityError as exc:
        print("NOT CERTIFIABLE: %s" % exc, file=sys.stderr)
        return EXIT_NOT_CERTIFIABLE
    except UsageRefusal as exc:
        print("USAGE: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except (DriftError, IncompleteBuildError) as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_DRIFT
    except ManifestError as exc:
        print("PIN: %s" % exc, file=sys.stderr)
        return EXIT_DRIFT
    except OSError as exc:
        print("COULD NOT WRITE OR READ: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
