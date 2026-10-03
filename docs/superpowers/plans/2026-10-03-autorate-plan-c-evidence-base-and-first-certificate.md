# Plan C — The evidence base: a pinned MASSIVE build, full-distribution records, and G1's first certified number

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce per-case decision records with complete probability distributions from a pinned, offline checkpoint, and use them to obtain spec §2's G1 -- a certified `autorate(alpha=0.05)` with an upper risk bound on at least three decision tasks, checked by a 200-resplit Monte-Carlo violation rate.

**Architecture:** A build step outside the test path (fetch → verify digests → score → write records) produces committed JSONL; the existing L2 certifiers consume it unchanged. The build refuses to emit records unless it reproduces the upstream published row it claims comparability with, so the artifact carries its own parity proof.

**Tech Stack:** Python 3.12; `uv` for this repo; the vendored `laya` package and its own venv for the scoring step only; `torch`/MPS exist **only** inside the build step and never inside `pytest` or `autorate verify`.

**Spec:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` (§2 G1/G5, §3 L1 sources, §4 Record contract, §5.2 APS, §11.1/§11.5/§11.6, §13 weeks 1-4 and 11-12). The spec travels with this plan.

**Prerequisites from Plan B1:** `Record.from_dict` must round-trip `case_id` (B1 Task 2b) before any per-case grouping of new records; the reader's malformed-line quarantine shape (B1 Task 1/1b) is reused rather than re-invented.

## Measured facts this plan is built on (2026-10-03, not assumed)

| fact | value | how |
|---|---|---|
| upstream's published `en` row, n=100, k=20, raw temps | accuracy **0.82**, mean_confidence **0.9989**, macro_f1 **0.7876**, ece **0.1789** | `research/results/cpu_51_language_sweep.json`, and reproduced by us |
| our reproduction of that row, through the harness's own `build_suite`/`summarise` | **0.8200 / 0.9989 / 0.7876 / 0.1789** | `/tmp/planC_parity.py`, MPS, offline cache |
| clamped regime on the same records | 0.8200 / 0.9582 / 0.7876 / 0.1382 | same run; accuracy and macro-F1 unchanged, ECE moves -- spec §7.2's clamp effect, reproduced |
| model load / scoring cost | 90.3 s once; 100 sequences of k=20 in one collated pass in 23.7 s (~4.2 decisions/s) | same run |
| one language's full test split | 2,974 cases, ~12 min | extrapolated from the measured rate, stated as an estimate |
| dataset identity | `mteb/amazon_massive_intent` @ `940fd47a81eaa7f2cc7b129674d945d618ac38c2`; 51 files, 3,221,662 B; **every language 2,974 rows, identical `id` sets across all 51** | fetched and hashed; `provenance.json` |
| checkpoint | root `model.safetensors` 842,609,210 B; `multilingual/` 643,835,514 B; snapshot `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` | HF API + `ls -lL` on the cache |
| is `laya_eval.py`'s output usable as an L1 source? | **No.** It emits `probability`, `p_gold`, `confidence`, never the full vector, so APS' nonconformity cannot be reconstructed | read at `laya_eval.py:244-266` |

Feasibility arithmetic, so the plan does not promise a number the corpus cannot support: `bound_width(2974, 0.05) = 0.0498`, i.e. an automation rate quoted to about ±0.025, and `n_feasible(2974, 0.05, 0.10) is True`. Against 64 cases the same function said no -- which is why Plan A shipped refusals and this plan can honestly aim at a certificate.

## Global Constraints

- The unit suite and `autorate verify` run offline forever, with no torch, no model, no network (ledger R-12 condition 1, spec §11.5). Anything touching the checkpoint lives in the build step.
- No new runtime dependency for this repo. `torch`, `transformers`, `numpy` belong to the **vendored** environment, not to `pyproject.toml`.
- The fetch is pinned by revision and per-file SHA-256 so a third party re-derives without trusting our download (R-12 condition 2); the committed artifact is records JSONL plus its digests (condition 3); Apache-2.0 attribution travels with it (condition 4).
- `probs` are in **presented** option order; `gold` is an option key, never an index; `u` is recorded so every certified set is exactly reproducible (spec §4).
- The certification unit is the case (R-44). A row count may never be published as an independent-case count (R-36).
- Exit codes 0/2/3/4; nothing escapes as rc 1. No absolute machine path in any tracked file. Never relax an assertion; no `# noqa`, no lint excludes. `uv run --frozen`, interpreter `python3`, never `python`, never a `pytest` from PATH. Commit messages carry no test counts (R-16).
- The vendored tree is read-only: `PYTHONDONTWRITEBYTECODE=1` on every invocation that imports it, because importing upstream drops `.pyc` files beside its sources.

---

### Task 1: Pin the corpus -- a fetcher that verifies, and a manifest the repo can check

**Files:**
- Create: `tools/fetch_massive.py`, `data/massive_provenance.json`
- Test: `tests/test_provenance.py`

**Interfaces:**
- Produces: `data/massive_provenance.json` with `dataset`, `revision`, `n_files`, `rows_total`, `files: [{path, sha256, bytes, rows, lang}]`; `verify_provenance(cache_dir) -> dict` re-hashing what is on disk; `fetch(revision, dest) -> None`.
- Consumes: nothing from this repo.

The build step's honesty rests on this file: a reader must be able to check our numbers without trusting our network.

- [ ] **Step 1: Write the failing test.**

```python
"""The pinned corpus must be checkable without trusting our download."""
import json
from pathlib import Path

from tools.fetch_massive import verify_provenance

PROV = Path("data/massive_provenance.json")


def test_the_manifest_is_self_describing_and_complete():
    d = json.loads(PROV.read_text())
    assert d["n_files"] == len(d["files"]) == 51, d["n_files"]
    assert d["revision"] == "940fd47a81eaa7f2cc7b129674d945d618ac38c2"
    assert {f["rows"] for f in d["files"]} == {2974}, "row counts drifted from the measured value"
    assert d["rows_total"] == sum(f["rows"] for f in d["files"])


def test_every_language_shares_the_same_item_ids():
    """The 51 files are translations of one 2,974-item set, not 51 samples (R-36)."""
    d = json.loads(PROV.read_text())
    assert len({f["sha256"] for f in d["files"]}) == 51, "digests must be per file"
    assert d["independent_cases"] == 2974
    assert d["rows_total"] == 51 * 2974, "151,674 is a row count, never an n"
```

- [ ] **Step 2: Verify RED** (`ModuleNotFoundError: tools.fetch_massive`), then **Step 3: Implement** `fetch()` using `urllib` against `.../resolve/<revision>/<path>` with **curl-equivalent redirect following**, and -- because a silent omission was measured here (the first fetch loop skipped `test/zh-TW.json.gz` and still exited 0) -- make `fetch()` assert `len(Downloaded) == 51` and re-raise on any missing path rather than continuing.
- [ ] **Step 4: `verify_provenance`** recomputes sha256 and row counts from a cache directory and returns the diff; it is the function CI can run against a cache that CI does not have, so it must also accept `absent` and say so rather than fail:

```python
def verify_provenance(cache_dir: Path, manifest: dict) -> dict:
    """Check what is on disk against what the manifest promises. Never downloads."""
    missing, mismatched, ok = [], [], 0
    for e in manifest["files"]:
        p = Path(cache_dir) / e["path"]
        if not p.exists():
            missing.append(e["path"]); continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        rows = sum(1 for l in gzip.decompress(p.read_bytes()).splitlines() if l.strip())
        if digest != e["sha256"] or rows != e["rows"]:
            mismatched.append({"path": e["path"], "sha256_ok": digest == e["sha256"],
                               "rows": rows})
        else:
            ok += 1
    return {"checked": len(manifest["files"]), "ok": ok, "missing": missing,
            "mismatched": mismatched}
```

- [ ] **Step 5: Run the gates** (ruff, `pytest -q -p no:randomly`, `autorate verify`, and the corpus-less simulation) and commit: `git commit -m "feat(tools): pin MASSIVE by revision and per-file digest, and refuse a short fetch"`.

---

### Task 2: The scoring driver -- full distributions, recorded `u`, and a parity gate that can stop the build

**Files:**
- Create: `tools/build_records.py`
- Test: `tests/test_build_records.py` (pure logic only: the conversion, the `u` draw, the parity comparison -- no torch import anywhere in the test)

**Interfaces:**
- Consumes: `data/massive_provenance.json`; upstream `laya_eval.build_suite`, `score_cases`, `temperature_for`, `softmax_t`, `summarise`; `laya.load`.
- Produces: `data/records_massive.jsonl` (one `Record` per case per backend), and `records_from_logits(logits, gold, option_keys, lang, u_stream) -> list[dict]` -- the pure function that a test can drive without a model.

- [ ] **Step 1: Write the failing tests for the pure part.**

```python
"""The conversion from logits to Records, with no model in the room."""
import math

from tools.build_records import PARITY, draw_u, records_from_logits


def _fake_logits(k, gold, mass=0.6):
    z = [0.0] * k
    z[gold] = math.log(mass / (1 - mass)) * 4      # a clearly-peaked distribution
    return [x + 0.01 * i for i, x in enumerate(z)]


def test_probs_sum_to_one_and_gold_is_a_key_not_an_index():
    keys = ["label_%d" % i for i in range(5)]
    recs = records_from_logits([_fake_logits(5, 2)], [2], [keys], "en", iter([0.5]))
    r = recs[0]
    assert abs(sum(r["probs"]) - 1.0) <= 1e-6
    assert r["gold"] == keys[2] and r["options"] == keys
    assert r["probs"] == [round(x, 6) for x in r["probs"]], "4-decimal parity with upstream"


def test_the_randomisation_draw_is_recorded_and_reproducible_from_a_stated_seed():
    a = list(draw_u(seed=7, n=4))
    b = list(draw_u(seed=7, n=4))
    assert a == b and len(set(a)) == 4 and all(0.0 <= x < 1.0 for x in a)
    assert list(draw_u(seed=8, n=4)) != a, "a fixed u for every record would collapse ties"


def test_case_id_is_the_dataset_item_id_not_the_row_number():
    keys = ["a", "b"]
    recs = records_from_logits([_fake_logits(2, 0)] * 2, [0, 0], [keys, keys], "en",
                               iter([0.1, 0.2]), item_ids=["x1", "x2"])
    assert {r["case_id"] for r in recs} == {"x1", "x2"}


def test_six_decimals_is_a_stated_limit_not_an_implicit_one():
    """The archive rounds to 4 decimals and says so; our driver keeps 6 and must say that."""
    r = records_from_logits([_fake_logits(3, 1)], [1], [["a", "b", "c"]], "en", iter([0.3]))[0]
    assert r["meta"]["probability_precision"] == 6


def test_the_parity_target_is_the_number_we_claim_comparability_with():
    assert PARITY == {"lang": "en", "per_lang": 100, "n_opts": 20, "seed": 13,
                      "regime": "unclamped", "accuracy": 0.82, "mean_confidence": 0.9989,
                      "macro_f1": 0.7876, "ece": 0.1789}
```

- [ ] **Step 2: Verify RED**, **Step 3: Implement** the pure functions, then **Step 4: implement the driver** around them:

```python
"""Score a pinned corpus offline and write Records. Not on the test path, never on CI.

    uv run --frozen python tools/build_records.py --cache <dir> --out data/records_massive.jsonl

Refuses to write anything unless the `en` parity row reproduces, because comparability with
upstream's published tables is a claim we make about these records: emitting numbers that do
not check out would make every certificate built on them unverifiable by the very project
they are comparable to.
"""
import argparse, gzip, json, sys
from pathlib import Path

sys.path.insert(0, str(VENDORED_EVAL_DIR))   # <workspace>/laya-0.3.20/research/eval
sys.path.insert(0, str(VENDORED_ROOT))      # <workspace>/laya-0.3.20, resolved not typed


def load_lite(cache_dir, lang):
    p = Path(cache_dir) / "test" / ("%s.json.gz" % lang)
    return [{"text": json.loads(l)["text"], "label_text": json.loads(l)["label_text"]}
            for l in gzip.decompress(p.read_bytes()).splitlines() if l.strip()]


def score_language(agent, lite_rows, unclamped, per_lang, n_opts, seed, lang, u_seed):
    """One language -> (report, records). Reuses upstream's suite builder so the sampling
    order is theirs, not ours -- that is what made the parity row reproduce."""
    import laya_eval as le
    from laya.common import QTYPES
    import numpy as np

    cases, gold, option_keys = le.build_suite(
        lite_rows, sorted({r["label_text"] for r in lite_rows}), per_lang, n_opts, seed)
    logits = le.score_cases(agent, cases)
    confs, cors, preds = [], [], []
    for z, g in zip(logits, gold):
        p = le.softmax_t(z, le.temperature_for(agent, QTYPES["choice"], len(z), unclamped))
        confs.append(float(p.max())); cors.append(float(int(np.argmax(p) == g)))
        preds.append(int(np.argmax(p)))
    report = le.summarise(confs, cors, gold, preds)
    return report, logits, gold, option_keys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", default="en,de,sw")
    ap.add_argument("--per-lang", type=int, default=2974)
    ap.add_argument("--device", default=None)
    args = ap.parse_args(argv)

    import laya
    cache = Path(args.cache)
    agent = laya.load("convaiinnovations/laya", device=args.device)

    probe, _, _, _ = score_language(agent, load_lite(cache, "en")[:100], True,
                                     100, 20, 13, "en", 0)
    got = {k: round(float(probe[k]), 4) for k in
           ("accuracy", "mean_confidence", "macro_f1", "ece")}
    want = {k: PARITY_TARGET[k] for k in ("accuracy", "mean_confidence", "macro_f1", "ece")}
    if got != want:
        sys.stderr.write("parity failed: got %s, expected %s -- refusing to write records\n"
                         % (got, want))
        return 2

    out = Path(args.out)
    with out.open("w") as fh:
        for lang in args.langs.split(","):
            report, logits, gold, keys = score_language(
                agent, load_lite(cache, lang), True, args.per_lang, 20, 13, lang, 13)
            for rec in records_from_logits(logits, gold, keys, lang,
                                           draw_u(seed=13, n=len(logits)),
                                           item_ids=[r["id"] for r in load_lite(cache, lang)][:len(logits)]):
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            print("%s: n=%d accuracy=%.4f ece=%.4f" % (
                lang, len(logits), report["accuracy"], report["ece"]), file=sys.stderr)
    return 0
```

`load_lite` is called twice per language by design in the sketch above; the implementation should read the rows once and pass them to both places, and a reviewer should flag the duplicate decompression as the cost it is rather than let it become a 2x runtime.

- [ ] **Step 5: Run the build for `en`, `de`, `sw`** (three measured-opened languages, ~36 min at the recorded rate) and keep the JSONL. Then run it for one more language as a control and confirm the report's numbers change but the pipeline does not.
- [ ] **Step 6: Commit** the driver and the three-language records with attribution: `git commit -m "feat(tools): full-distribution records from a pinned checkpoint, gated on upstream's own published row"`.
- [ ] **Step 7: Prove the suite is still offline-clean:** the four gates, and `grep -rn "import torch" src tests` must print nothing. A build-only dependency leaking into `src/` or `tests/` is the failure this project's reproducibility claim cannot survive.

---

### Task 3: Read the new records through the existing contract

**Files:**
- Create: `src/autorate/readers/massive.py`
- Test: `tests/test_reader_massive.py`

**Interfaces:**
- Consumes: `Record`, `validate`, `SUM_TOL`, the quarantine shape from B1 Task 1 (`reason`, `line_no`, `error`, one entry per line, `_quarantine` as the single schema owner).
- Produces: `read_massive(path, stats=None) -> list[Record]`.

- [ ] **Step 1: Write the failing tests** -- a well-formed line reads; a line whose probabilities do not close is quarantined and named; a line that is not JSON is quarantined with `line_no`; the conservation identity closes; and `case_id` survives the round trip (the B1 Task 2b guarantee, exercised on this reader rather than assumed).
- [ ] **Step 2: Verify RED**, **Step 3: Implement** reusing the reader helpers (no second quarantine implementation -- that is B1 Task 1's whole point).
- [ ] **Step 4: Green** on the four gates, including the corpus-less simulation: this reader reads a **committed** file, so its tests must run on the runner. Any skip added here is a design error to fix, not a fact to accept.
- [ ] **Step 5: Commit** — `git commit -m "feat(readers): massive records through the same contract, same quarantine owner"`.

---

### Task 4: G1 -- three certified tasks, and the Monte-Carlo that checks the claim

**Predecessor (added by Plan D's ruling D-a, 2026-10-03):** `protocol.json` must be committed by Plan
D Task 1 *before* this task produces its first certificate, and this task is dispatched with the
protocol digest as an input. A protocol frozen after the run is a transcript of the result, and the
certificates' `meta["protocol_digest"]` would have nothing to point at. Tasks 1-3 are unaffected;
Task 1's pins are the protocol's own input.

**Files:**
- Create: `tests/test_g1_certification.py`
- Modify: `src/autorate/cli.py` (`certify` gains `--records data/records_massive.jsonl`), `docs/RESULTS.md` via `autorate report`

**Interfaces:**
- Consumes: `certify_choice`, `split_cal`, the committed records.
- Produces: `data/cert_massive_<lang>.json` per language, and the violation-rate table in `docs/RESULTS.md`.

- [ ] **Step 1: Write the failing test for the criterion itself.**

```python
"""G1: >=3 tasks yield a certified autorate(alpha=0.05) with an upper risk bound, and the
bound's own violation rate is measured by 200 resplits rather than asserted."""
import json
from pathlib import Path

import pytest

from autorate.certify_choice import certify_choice
from autorate.readers.massive import read_massive

RECORDS = Path("data/records_massive.jsonl")


@pytest.mark.skipif(not RECORDS.exists(), reason="build step not run")
def test_three_languages_certify_at_alpha_005():
    done = []
    for lang in sorted({json.loads(l)["slices"]["language"]
                        for l in RECORDS.read_text().splitlines() if l.strip()}):
        recs = [r for r in read_massive(RECORDS) if r.slices["language"] == lang]
        cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=13)
        if cert.feasible:
            done.append((lang, cert))
    assert len(done) >= 3, [d[0] for d in done]
    for lang, cert in done:
        assert cert.conditional_error_bound <= 0.05 + 1e-9, lang
        assert cert.meta["n_eval_cases"] > 500, (lang, cert.meta["n_eval_cases"])
```

- [ ] **Step 2: Verify RED for the honest reason** (records absent, or fewer than three languages certified). **If the honest result is that nothing certifies, that is a finding about the corpus, not a cue to loosen `alpha`.** Report it and let the controller re-plan; do not convert G1 into "certified at a budget we chose because 0.05 failed".
- [ ] **Step 3: Add the violation-rate test** -- 200 seeded resplits, each recomputing `qhat` and the conditional bound, asserting the empirical rate at which the claim `P(wrong | auto) <= beta` fails is itself within the level published. Quote the measured number in the test name/comment only as produced output.
- [ ] **Step 4: Wire the certificates into `autorate report`** so `docs/RESULTS.md` carries them, and every number in it remains re-derived (G5).
- [ ] **Step 5: Commit** — `git commit -m "feat(g1): the first certified automation rates, with the violation rate measured rather than asserted"`.

---

### Task 5: Make the new artifacts checkable where CI can see them

**Files:**
- Modify: `src/autorate/cli.py` (`cmd_verify`, `PUBLISHED_ROWS`), `.github/workflows/ci.yml` (a provenance check step, no network), `README.md`

**Interfaces:**
- Consumes: Tasks 1-4 artifacts.
- Produces: `verify` rows for `data/records_massive.jsonl` (row count, distinct cases, digest of the file) and for each certificate; a `data/inventory.md` line stating the corpus option's basis as **51 of 51 files opened and hashed** (B1 task #28's upgrade, which this plan now makes possible).

- [ ] **Step 1: Write the failing test** (plant a one-character edit to a published number in the records digest row and expect rc 4), **Step 2: verify RED**, **Step 3: implement**.
- [ ] **Step 4: CI stays offline.** The workflow may run `verify_provenance` against a cache it does not have and must then report `missing: 51` as disclosure, not failure -- the same convention `verify` already uses for the corpus it cannot see.
- [ ] **Step 5: README.** State the boundary in the same breath as the achievement: which numbers are offline-reproducible from committed records, which required the pinned build step, and what the exchangeability envelope says about a checkpoint fine-tuned on this benchmark's own training split (spec §9's contamination question, whose stratification lands in Plan B3).
- [ ] **Step 6: Commit**, then run the four gates plus the corpus-less simulation and push the branch.

---

## Gates every task ends at

```bash
uv run --frozen ruff check src tests tools --select=E9,F63,F7,F82,F401,F811 --line-length=120
uv run --frozen pytest -q -p no:randomly
uv run --frozen autorate verify
AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest -q -p no:randomly
```

The first line gains `tools` deliberately: a directory nothing lints is a directory nothing checks.

## Out of scope here

Per-language Mondrian control, the simultaneous correction, the contamination Δ̂ and drift modes → Plan B3. The ordinal `score` certificate → Plan B2, which needs an ordinal corpus this plan does not produce: the archived `feishu_zh` responses contain zero `score` answers (measured: 192 `choice` + 768 `noul` per backend), so ordinal evidence is synthetic-with-known-answers or waits for a scored run here.
