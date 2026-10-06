"""Score a pinned corpus offline and write Records. Not on the test path, never on CI.

    uv run --frozen python tools/build_records.py --cache <massive-cache> \
        --out data/records_massive.jsonl --langs en,de,sw

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
present in the artefact, so the proof travels inside the file it certifies.

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
                          gold index or `probs_probe` entry that is not a real number, a gold index
                          outside its ballot, a one-option ballot published as `choice`, a `timing`
                          that is not a mapping, a shard line that parses as JSON but is not an
                          object, and a stage that scored a question type other than `choice` are
                          all refusals, not `TypeError`s -> 4.
    IncompleteBuildError  the build could not run: no upstream tree, no interpreter, no numpy,
                          the stage crashed or was killed, the payload is not JSON, the out path
                          is not writable -> 4, the code the CLI gives a tool that cannot
                          reproduce its own inputs.
    BuildError            the base of the two above. `ParityError` is NOT built on it.
    UsageRefusal          the operator's input is wrong: a language that is not pinned, a regime
                          or option count the published row is not stated under, a `--per-lang`
                          the shard cannot fill -> 2. argparse's own errors are 2 as well.
    UStreamExhausted      the `u` stream ran out; a missing draw would land on 0.0 and quietly
                          tie-break -> a `BuildError`, so 4, and never a zero fill.

Exit codes are exactly 0 (records written, parity held) / 2 (usage) / 3 (not certifiable) /
4 (drift or could not complete).

Regime: `unclamped` only, because that is what `PARITY` is stated under and what
`research/results/cpu_51_language_sweep.json` was produced with; the clamped regime is a real and
different number (spec 7.2's clamp), so asking for it while quoting the unclamped row is refused.
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
WORKER_STAGES = ("probe", "full")
# A stage that answers partially is a stage that did not run. Every one of these is indexed later,
# so an absent key would surface as a `KeyError` -- rc 1, outside this tool's contract.
REQUIRED_PAYLOAD_KEYS = ("lang", "stage", "n_cases", "item_ids", "gold", "option_keys", "logits",
                         "temperatures", "texts", "probs_probe", "timing", "upstream_report",
                         "qtype", "regime", "n_opts", "seed")


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
    """
    n = len(logits)
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
    suite mixed option counts, which the gate then refuses rather than averaging.
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
    report["lang"] = langs.pop() if len(langs) == 1 else None
    report["regime"] = regimes.pop() if len(regimes) == 1 else None
    report["seed"] = seeds.pop() if len(seeds) == 1 else None
    report["n_opts"] = counts.pop() if len(counts) == 1 else None
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


def stage_report(payload: dict) -> dict:
    """The model stage's own row: upstream's `summarise`, on the checkpoint's unrounded softmax.

    This is the side of the parity comparison that is *not* this build: computed in the vendored
    interpreter, from the probabilities the checkpoint produced, with upstream's argmax rather than
    the argmax of the 6-decimal vector we write. The published figures alone are not the published
    row, so the identity travels with it from the same payload.
    """
    if not isinstance(payload["upstream_report"], dict):
        raise DriftError("%s/%s: the payload's upstream_report is a %s, not a mapping; the parity "
                         "gate compares upstream's own arithmetic, so it has to be able to read it"
                         % (payload.get("lang"), payload.get("stage"),
                            type(payload["upstream_report"]).__name__))
    report = dict(payload["upstream_report"])
    for key in ("lang", "n_opts", "seed", "regime"):
        report[key] = payload[key]
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
    override = os.environ.get("AUTORATE_UPSTREAM_PYTHON") or os.environ.get("AUTORATE_AUDIT_PYTHON")
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
           "--model", args.model, "--device", args.device or "", "--regime", args.regime,
           "--per-lang", str(per_lang), "--n-opts", str(args.n_opts), "--seed", str(args.seed)]
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


def check_payload(payload: dict, lang: str, stage: str, per_lang: int,
                  upstream_module) -> list:
    """A model stage answers for itself: right language, right size, arrays that line up.

    `probs_probe` is upstream's own `softmax_t` on the first cases; the build layer recomputes it
    with `softmax_t` above and refuses the batch if the two diverge, because that is the one place
    here where a re-implementation could silently change every probability.
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
    arrays = ("item_ids", "gold", "option_keys", "logits", "temperatures", "texts")
    not_lists = [key for key in arrays + ("probs_probe",) if not isinstance(payload.get(key), list)]
    if not_lists:
        raise DriftError("the %s/%s payload's %s %s not a list"
                         % (lang, stage, ", ".join(not_lists),
                            "are" if len(not_lists) > 1 else "is"))
    lengths = {key: len(payload[key]) for key in arrays}
    n_cases = payload.get("n_cases")
    if n_cases != per_lang:
        raise DriftError("the %s/%s stage returned %s cases for a run of %d: a suite that came "
                         "back short would publish fewer cases than the artefact claims"
                         % (lang, stage, n_cases, per_lang))
    uneven = {key: lengths[key] for key in arrays if lengths[key] != per_lang}
    if uneven:
        raise DriftError("the %s/%s payload does not line up: %s (expected %d each); refusing to "
                         "guess which case is which" % (lang, stage,
                                                        ", ".join("%s=%d" % kv for kv in uneven.items()),
                                                        per_lang))
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
        _number(payload["temperatures"][i], "%s/%s" % (lang, stage), i, "temperature")
    probe = payload.get("probs_probe")
    if not isinstance(probe, list) or not probe:
        raise DriftError("the %s/%s payload carried no probs_probe: the build layer checks its own "
                         "softmax against upstream's, and an empty probe would check nothing"
                         % (lang, stage))
    limit = min(len(probe), PROBE_PROBS_CASES)
    probes = [[_number(v, "%s/%s" % (lang, stage), i, "probs_probe entry %d" % j)
               for j, v in enumerate(payload["probs_probe"][i])] for i in range(limit)]
    for i in range(limit):
        want = probes[i]
        got = softmax_t(value_sets[i], payload["temperatures"][i])
        if len(want) != len(got):
            raise DriftError("%s/%s case %d: probs_probe has %d entries for %d options"
                             % (lang, stage, i, len(want), len(got)))
        worst = max(abs(a - b) for a, b in zip(want, got))
        if worst > SOFTMAX_TOL:
            raise DriftError("%s/%s: this build's softmax_t differs from upstream's by %.3g on "
                             "case %d, which is more than %.1e; every probability in the artefact "
                             "would be ours rather than the harness's"
                             % (lang, stage, worst, i, SOFTMAX_TOL))
    if upstream_module is not None:
        for i in range(limit):
            theirs = [float(x) for x in upstream_module.softmax_t(value_sets[i],
                                                                  payload["temperatures"][i])]
            worst = max(abs(a - b) for a, b in zip(theirs, probes[i]))
            if worst > SOFTMAX_TOL:
                raise DriftError("%s/%s: the payload's probs_probe is not what upstream's "
                                 "softmax_t returns here (max diff %.3g); the stage and the tree "
                                 "disagree" % (lang, stage, worst))
    return probe


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
def _score_batch(laya, le, np, QTYPES, args, rows, unclamped):
    """Every call into the checkpoint stack, in one place, so one clause can name what they raise.

    Upstream's own `build_suite` is what orders the sampling -- "that is what made the parity row
    reproduce" -- and the label pool is every label in the shard, exactly as upstream's
    `run_language` builds it. Slicing the shard before computing the pool is the one way to change
    every ballot, and the parity gate is what would notice.
    """
    started = time.time()
    agent = laya.load(args.model, device=args.device or None, subfolder=args.subfolder or None)
    agent.model.eval()
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
    logits = le.score_cases(agent, cases)
    score_s = time.time() - scored
    temperatures = [float(le.temperature_for(agent, QTYPES["choice"], len(z), unclamped))
                    for z in logits]
    confs, cors, preds = [], [], []
    for z, t, g in zip(logits, temperatures, gold):
        p = le.softmax_t(z, t)
        confs.append(float(p.max()))
        preds.append(int(np.argmax(p)))
        cors.append(float(int(preds[-1] == int(g))))
    upstream_report = le.summarise(confs, cors, gold, preds)
    probs_probe = [[float(x) for x in le.softmax_t(z, t)]
                   for z, t in list(zip(logits, temperatures))[:PROBE_PROBS_CASES]]
    import torch
    return {
        "lang": args.lang, "stage": args.stage, "n_cases": len(cases), "n_opts": args.n_opts,
        "seed": args.seed, "regime": args.regime, "qtype": qtypes[0],
        "item_ids": [r["id"] for r in rows[:len(cases)]],
        "texts": [r["text"] for r in rows[:len(cases)]],
        "gold": [int(g) for g in gold],
        "option_keys": [list(k) for k in option_keys],
        "logits": [[float(x) for x in z] for z in logits],
        "temperatures": temperatures,
        "probs_probe": probs_probe,
        "upstream_report": {k: round(float(v), 6) if isinstance(v, (int, float)) else v
                            for k, v in upstream_report.items()},
        "timing": {"load_s": round(load_s, 3), "score_s": round(score_s, 3),
                   "cases_per_s": round(len(cases) / score_s, 4) if score_s > 0 else None,
                   "device": str(agent.device),
                   "torch": getattr(torch, "__version__", "unknown"),
                   "laya": getattr(laya, "__version__", "unknown")},
    }


def worker_main(args) -> int:
    """One language, one batch, raw logits out. Runs ONLY in the vendored interpreter.

    Nothing in this function reaches the checkpoint stack except through `_score_batch`, and that
    call is the single place in the repository where an exception we do not own is caught broadly.
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
    if args.regime not in ("unclamped", "clamped"):
        raise UsageRefusal("--regime must be unclamped or clamped, not %r" % args.regime)

    try:
        payload = _score_batch(laya, le, np, QTYPES, args, rows, args.regime == "unclamped")
    except (BuildError, ParityError, UsageRefusal):
        raise
    except Exception as exc:
        raise UpstreamStageError("the model stage for %s/%s failed inside the checkpoint stack: "
                                 "%s: %s" % (args.lang, args.stage, type(exc).__name__, exc)) from exc
    Path(args.payload).write_text(json.dumps(payload))
    print("worker %s/%s n=%d score_s=%.1f device=%s"
          % (args.lang, args.stage, payload["n_cases"], payload["timing"]["score_s"],
             payload["timing"]["device"]), file=sys.stderr)
    return EXIT_OK


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
    if args.regime != PARITY["regime"]:
        raise UsageRefusal("--regime %r is not the regime PARITY is stated under (%r); the "
                           "clamped figures are a different published number, not a looser gate"
                           % (args.regime, PARITY["regime"]))
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
    summary = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "pin": {"path": str(args.pin), "revision": pin["revision"], "dataset": pin["dataset"],
                       "n_files": pin["n_files"], "rows_total": pin["rows_total"],
                       "license": pin["license"]},
               "cache": str(args.cache), "out": str(args.out), "langs": list(dict.fromkeys(langs)),
               "per_lang": args.per_lang, "n_opts": args.n_opts, "suite_seed": args.seed,
               "u_seed": args.u_seed, "regime": args.regime, "backend": args.backend,
               "model": args.model, "subfolder": args.subfolder, "python": args.python,
               "upstream": str(upstream), "probability_decimals": PROB_DECIMALS,
               "parity_target": {k: PARITY[k] for k in PROBE_FIGURES},
               "identity": {k: PARITY[k] for k in PROBE_IDENTITY},
               "interpreter": {"executable": sys.executable, "version": sys.version.split()[0]}}

    # The corpus before the checkpoint: a cache that is not the pinned bytes would make every
    # figure downstream unattributable, and loading a 90-second model to find that out is the
    # wrong order.
    report = check_cache(args.cache, pin, languages, max(args.per_lang, PARITY["per_lang"]))
    le = load_upstream_eval(upstream)
    summary.update({"cache_check": {"checked": report["checked"], "ok": report["ok"],
                                    "missing": len(report["missing"]),
                                    "mismatched": len(report["mismatched"])}})
    out = Path(args.out)
    if not out.parent.is_dir():
        raise IncompleteBuildError("--out %s: its directory does not exist; nothing was created "
                                   "and nothing was written" % out)
    started = time.time()
    tmp = out.parent / (out.name + ".tmp")
    positions = {lang: i for i, lang in enumerate(languages)}
    probe_u_seed = args.u_seed + positions.get(PARITY["lang"], 0)
    written: dict = {}
    try:
        with tempfile.TemporaryDirectory(prefix="planC-payloads-") as payload_dir:
            payloads = Path(payload_dir)

            # 1. the gate. The published row, on the published conditions, through this tool's own
            # conversion -- not through a side path that could pass while the artefact fails.
            probe_payload = run_model_stage(args, upstream, PARITY["lang"], "probe",
                                            PARITY["per_lang"], payloads)
            check_payload(probe_payload, PARITY["lang"], "probe", PARITY["per_lang"], le)
            probe_records = records_from_logits(
                probe_payload["logits"], probe_payload["gold"], probe_payload["option_keys"],
                PARITY["lang"], draw_u(seed=probe_u_seed, n=probe_payload["n_cases"]),
                item_ids=[case_id_for(PARITY["lang"], i) for i in probe_payload["item_ids"]],
                temperatures=probe_payload["temperatures"],
                texts=probe_payload["texts"], backend=args.backend, regime=args.regime,
                suite_seed=args.seed, u_seed=probe_u_seed, dataset=pin["dataset"],
                revision=pin["revision"], license_id=pin["license"], checkpoint=args.model,
                device=stage_device(probe_payload))
            probe_report = summarise_with(le, probe_records)
            # Two sides of one claim, both against the published row. The stage's own report is
            # upstream's arithmetic on the checkpoint's unrounded softmax in the vendored
            # interpreter; `probe_report` is this build's 6-decimal vector and the argmax of that
            # vector, i.e. the numbers the records actually carry. Gating only the second would let
            # a conversion that moved one prediction relative to upstream's own choice pass while
            # the row upstream published about the same logits said otherwise.
            check_parity(stage_report(probe_payload), PARITY, side=STAGE_SIDE)
            got = check_parity(probe_report, PARITY, side=BUILT_SIDE)
            print("parity ok: probe lang=%s n=%s n_opts=%s seed=%s regime=%s %s"
                  % (PARITY["lang"], PARITY["per_lang"], PARITY["n_opts"], PARITY["seed"],
                     PARITY["regime"], " ".join("%s=%.4f" % (k, got[k]) for k in PROBE_FIGURES)))
            summary["probe"] = {"report": probe_report,
                                "upstream_report": probe_payload["upstream_report"],
                                "timing": probe_payload["timing"],
                                "u_seed": probe_u_seed,
                                "wall_s": probe_payload["_stage_wall_s"]}

            # 2. the artefact, one language per pass, streamed to a temp sibling of `out`, and
            # renamed into place only once every language is in it.
            with tmp.open("w") as fh:
                for lang in languages:
                    payload = run_model_stage(args, upstream, lang, "full", args.per_lang, payloads)
                    check_payload(payload, lang, "full", args.per_lang, le)
                    u_seed = args.u_seed + positions[lang]
                    records = records_from_logits(
                        payload["logits"], payload["gold"], payload["option_keys"], lang,
                        draw_u(seed=u_seed, n=payload["n_cases"]),
                        item_ids=[case_id_for(lang, i) for i in payload["item_ids"]],
                        temperatures=payload["temperatures"],
                        texts=payload["texts"], backend=args.backend, regime=args.regime,
                        suite_seed=args.seed, u_seed=u_seed, dataset=pin["dataset"],
                        revision=pin["revision"], license_id=pin["license"],
                        checkpoint=args.model, device=stage_device(payload))
                    if lang == PARITY["lang"]:
                        overlap = check_artefact_covers_probe(records, probe_records, lang)
                        summary["probe_prefix_overlap"] = overlap
                    for rec in records:
                        fh.write(record_line(rec) + "\n")
                    fh.flush()
                    report = summarise_with(le, records)
                    written[lang] = {"report": report,
                                     "upstream_report": payload["upstream_report"],
                                     "timing": payload["timing"], "u_seed": u_seed,
                                     "records": len(records),
                                     "wall_s": payload["_stage_wall_s"],
                                     "stderr_tail": payload.get("_stage_stderr_tail", "")}
                    print("lang=%s n=%d %s cases_per_s=%s stage_wall_s=%s"
                          % (lang, len(records),
                             " ".join("%s=%.4f" % (k, round(float(report[k]), 4))
                                      for k in PROBE_FIGURES),
                             payload["timing"].get("cases_per_s"), payload["_stage_wall_s"]))
                os.fsync(fh.fileno())
            os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    summary["languages"] = written
    summary["records_written"] = sum(v["records"] for v in written.values())
    summary["wall_s"] = round(time.time() - started, 3)
    summary["device"] = stage_device(written[languages[0]]["timing"]) if written else None
    print("wrote %d records for %d languages to %s in %.1f s"
          % (summary["records_written"], len(written), out, summary["wall_s"]))
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
    ap.add_argument("--out", default=None, help="where to write the records JSONL")
    ap.add_argument("--pin", default=str(DEFAULT_PIN))
    ap.add_argument("--langs", default="en,de,sw")
    ap.add_argument("--per-lang", type=int, default=2974)
    ap.add_argument("--n-opts", type=int, default=PARITY["n_opts"])
    ap.add_argument("--seed", type=int, default=PARITY["seed"])
    ap.add_argument("--u-seed", type=int, default=PARITY["seed"], dest="u_seed")
    ap.add_argument("--regime", default=PARITY["regime"], choices=("unclamped", "clamped"))
    ap.add_argument("--backend", default=BACKEND)
    ap.add_argument("--model", default="convaiinnovations/laya")
    ap.add_argument("--subfolder", default=None)
    ap.add_argument("--device", default=None, help="cpu, cuda, mps (default: upstream's auto)")
    ap.add_argument("--upstream", default=None, help="the vendored tree (default: discovered)")
    ap.add_argument("--python", default=None, help="interpreter for the model stage")
    ap.add_argument("--payload", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--lang", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--stage", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--summary", default=None, help="write the measured facts of this run here")
    return parser


def main(argv=None) -> int:
    """Map every reachable outcome onto 0 / 2 / 3 / 4. An rc 1 is a failure this tool did not name."""
    args = build_parser().parse_args(argv)
    try:
        if args.worker:
            if not args.payload or not args.lang or args.stage not in WORKER_STAGES:
                raise UsageRefusal("--worker needs --lang, --stage and --payload")
            return worker_main(args)
        if args.out is None:
            raise UsageRefusal("--out is required unless --worker is set")
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
