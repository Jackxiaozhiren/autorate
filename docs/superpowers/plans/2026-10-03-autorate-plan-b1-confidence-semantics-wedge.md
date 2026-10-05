# Plan B1 — The confidence-semantics wedge: threshold gates, field attribution, and the exit-code contract

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `autorate` able to certify a *threshold* rule as well as a set rule, use that to reproduce G2 on real archived third-party responses, and state which confidence scale each backend actually publishes — then close the four contract items the whole-branch review ruled into Plan B.

**Architecture:** Everything here stays in L2 (pure Python, torch-free, offline). The set-gate path (`certify_choice`) gains a sibling (`certify_threshold`) that shares its case-level counting, so one rule cannot be certified by one implementation and deployed by another. The audit reads `data/records_feishu.jsonl`, which is committed, so every number this plan publishes is re-derivable by CI without the vendored corpus.

**Tech Stack:** Python 3.12, stdlib only (`math`, `json`, `argparse`, `random`), `uv` for the environment, `pytest` + `ruff` as the gate, GitHub Actions (`job: offline`).

**Spec:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` — this plan implements §6.4 (threshold gate, for comparison), §7.1/§7.3 (the three-field audit, G2), §10's `autorate audit` CLI, and the ledger's I-9/I-10/D14 closures. **The spec travels with this plan; executors read both.**

**Ledger:** `.superpowers/sdd/2026-09-29-autorate-plan-a-foundation-and-choice-certification/progress.md` (gitignored, local). Rulings this plan obeys: R-28 (a requested budget may not be met by relabelling), R-34 (one owner for the auto/escalate rule), R-36 (a bound keys on independent cases), R-44 (the certification unit is the case), R-16 (no suite counts in commit messages), R-41 (simulate the runner's corpus-less lane before pushing), PF-12 (substring checks do not certify structure).

## Why this plan is B1 and not "Plan B"

Spec §13 weeks 5–12 covers four separable subsystems, and one of them turned out not to be offline. Measured on 2026-10-03 rather than assumed:

| question | measured answer | consequence |
|---|---|---|
| Is any per-case probability committed besides `feishu_zh`? | No. All 16 other `research/results/*.json` carry aggregates; `eval_english_51_languages.json` has a `cases_note` key, matching the gap line this repo already publishes | a second real `choice` corpus needs inference, not download |
| Is the laya checkpoint cached locally? | No. `~/.cache/huggingface/hub/models--convaiinnovations--laya` is 3.5 MB and `model.safetensors` is a 76-byte LFS pointer | "run the harness" is a ~0.84 GB download first |
| What does the model repo actually hold? | 38 files, 2.37 GB total: `model.safetensors` 842.61 MB, `typed-decisions/` 842.61 MB, `multilingual/` 643.84 MB (HF API, `?blobs=true`, 2026-10-03) | the evidence base has a cost and a network dependency, so it is its own plan (Plan C) and needs the human partner's explicit go-ahead |
| Can G2 be reproduced without any of that? | **Yes.** `data/records_feishu.jsonl` is committed and carries `reported_confidence`, `act_probability`, `probs`, `gold`, `predicted`, `case_id` | the wedge — the project's declared first public artefact (§7) — ships now |

So: **B1 = the offline wedge and the contract closures (this plan). B2 = ordinal `score` (G3, §5.4/§6.2/§6.3). B3 = Mondrian + simultaneous correction + drift + contamination (G4, §8/§9). C = the inference corpus and G1.** Each is independently testable software; bundling them would make B1's reviewable unit a 25-task plan.

## Global Constraints

- Python floor 3.12; **no new runtime dependencies** — spec §11.5 keeps the suite torch-free, model-free and network-free.
- The unit suite and `autorate verify` run offline forever (ledger R-12 condition 1). A pinned download may exist only as a build step in Plan C.
- Exit codes are `0` certified / `2` usage / `3` NOT_CERTIFIABLE / `4` drift. **Nothing may escape as rc 1** (R-43, and Task 1's whole point).
- No absolute machine path in any tracked file (`tests/test_cli.py` fails the build on a username-shaped path); the vendored corpus is addressed only through the sibling-checkout resolver.
- The vendored corpus at `<workspace>/laya-0.3.20` (a sibling checkout of this repo, resolved by `autorate.cli._default_corpus()`) is **read-only**: every test that needs a corpus of its own builds one under `tmp_path`.
- Published numbers have one owner, and the certification denominator is the **case**, not the archive row (R-36, R-44).
- Run everything through `uv run --frozen`; the interpreter on PATH is `python3`, never `python`.
- Commit messages carry no suite counts (R-16); the honest place for a count is CI's own output.
- Deliverable prose (code comments, docs, commit messages) is English; conversation with the human partner is Chinese.

## File structure

| file | responsibility | change |
|---|---|---|
| `src/autorate/readers/feishu_zh.py` | archive → `Record`, and what a refused line means | Task 1: malformed lines become quarantine entries, not exceptions |
| `src/autorate/scales.py` | which confidence scale a number is, decided by measurement | Task 2: new |
| `src/autorate/case_count.py` | apply one decision rule to a half, counting records AND cases | Task 3: extracted from `certify_choice._outcome` so the two certifiers cannot diverge |
| `src/autorate/certify_threshold.py` | the §6.4 threshold gate | Task 3: new |
| `src/autorate/audit.py` | the three-field comparison, as data | Task 4: new |
| `src/autorate/cli.py` | `autorate audit` + wiring into `verify` | Tasks 4, 6 |
| `src/autorate/certificate.py` | the published shape | Task 5: fifth `Reason`, `SHAPE_VERSION` |
| `docs/AUDIT.md` | the published G2 table | Task 4: new; Task 6: re-derived by `verify` |

---

### Task 1: A malformed archive line is a quarantine entry, not a crash

**Files:**
- Modify: `src/autorate/readers/feishu_zh.py` (`read_archive`, `records_from_line`)
- Test: `tests/test_reader_feishu.py`

**Interfaces:**
- Consumes: `read_archive(root, backend=None, repeat=None, mode=None, stats=None) -> list`, and the conservation identity it already enforces (`lines_read` = kept + quarantined + dropped).
- Produces: `stats["lines_malformed"]` (int) and quarantine entries carrying `"reason": "malformed_line"` with the parse error named. Unchanged for every well-formed line.

The ledger's I-9: one malformed line escapes as `KeyError` → rc 1, outside the documented contract. Plan B reads downloaded JSON rather than a curated archive, so this is the task that makes the reader safe on data it did not hand-pick.

- [ ] **Step 1: Write the failing tests.** The repository has no corpus-building fixture -- `tests/test_reader_feishu.py:214-236` builds one inline out of the module's `_line(**kw)` helper, and that is the pattern to follow. Add a shared builder beside `_line` and two tests that use it:

```python
def _archive(tmp_path, objs, backends=("laya", "jev")):
    """A corpus root of raw lines, built the way this file already builds them."""
    import json
    for b in backends:
        f = tmp_path / "results" / "v1" / b / "raw.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(l if l.endswith("\n") else l + "\n" for l in objs))
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "manifest.json").write_text(json.dumps({"asks": ["urgent"]}))
    (tmp_path / "data" / "cases.jsonl").write_text(
        json.dumps({"id": "k-0", "expected": "a"}) + "\n")
    return tmp_path


def test_a_line_that_is_not_json_is_quarantined_not_raised(tmp_path):
    """I-9: measured against the pre-fix reader, a non-JSON line reached cli as ValueError
    (rc 2, the wrong contract but non-zero), while a line missing a key the contract needs
    reached it as KeyError -- rc 1, the one outcome the exit-code set forbids."""
    from autorate.readers.feishu_zh import read_archive
    root = _archive(tmp_path, ['{"id": "broken"\n', json.dumps(_line(id="ok-0")) + "\n"])
    stats = {}
    recs = read_archive(root, stats=stats)
    assert len(recs) == 1, stats
    assert stats["lines_malformed"] == 2, stats          # once per backend
    assert stats["lines_read"] == 4, stats               # the bad line still counts as seen
    assert stats["lines_kept"] + sum(stats["lines_quarantined_only"].values()) \
        == stats["lines_read"], stats


def test_a_line_missing_a_key_the_contract_needs_is_named_not_fatal(tmp_path):
    from autorate.readers.feishu_zh import read_archive
    root = _archive(tmp_path, [json.dumps({"id": "x", "mode": "choice",
                                           "repeat": 0, "status": "ok",
                                           "response": {"model": "m"}}) + "\n"],
                    backends=("laya",))
    stats = {}
    read_archive(root, stats=stats)
    q = [e for e in stats["quarantined"] if e["reason"] == "malformed_line"]
    assert len(q) == 1, q
    assert q[0]["backend"] == "laya" and q[0]["line_no"] == 1, q
    assert "answers" in q[0]["error"] or "KeyError" in q[0]["error"], q[0]
    assert "raw" not in q[0], "the archive line's bytes are not copied into the artifact"
```

- [ ] **Step 2: Run them and watch them fail for the right reason.**

Run: `uv run --frozen pytest tests/test_reader_feishu.py -k "malformed or malformed_line" -q -p no:randomly`
Expected: FAIL — `json.decoder.JSONDecodeWerror` propagates out of `read_archive` (that is the defect), not an `assert` about a missing counter. If it fails with a fixture error instead, fix the fixture first.

- [ ] **Step 3: Implement.** The real loop (as of `d82b300`) reads `for line in path.read_text().splitlines():` and increments `lines_read` **after** `json.loads(line)` -- so a line that fails to parse never enters the count the conservation identity closes over. That is the mechanism, not a side detail: the identity cannot report what was never counted. Restructure the loop head and wrap both raising operations:

```python
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            lines_read += 1          # before parsing: an unread line is still a line seen
            try:
                obj = json.loads(line)
                made = records_from_line(obj, b, quarantine, gold)
            except (ValueError, KeyError, TypeError) as exc:
                # A line this contract cannot read is named, not dropped and not fatal:
                # rc 1 is not in the exit-code set, and a malformed line in a corpus we
                # downloaded (Plan C) is ordinary, not exceptional. The bytes stay out --
                # an archive line can carry content no reader should republish.
                quarantine.append({"id": None, "backend": b, "mode": None, "repeat": None,
                                   "probs": [], "probs_sum": 0.0, "tolerance": SUM_TOL,
                                   "reason": "malformed_line", "line_no": line_no,
                                   "error": "%s: %s" % (type(exc).__name__, exc)})
                lines_malformed += 1
                continue
```

Add `lines_malformed = 0` beside the existing `lines_read = lines_kept = lines_dropped = lines_filtered = 0`, publish `stats["lines_malformed"]`, and extend `lines_quarantined_only` so the existing identity `lines_read == lines_kept + lines_quarantined_only + lines_dropped + lines_filtered` still closes. Keep `records_from_line` itself unchanged -- it is correct to raise; the caller is what must not. Note the loop body below the `try` also uses `obj["repeat"]` and `obj["mode"]` directly (lines 172-173), so those reads belong inside the same `try`.

- [ ] **Step 4: Run the full reader suite** — `uv run --frozen pytest tests/test_reader_feishu.py -q -p no:randomly` — expected: all pass, and the pre-existing conservation test still passes, which is the proof the new branch is accounted for rather than absorbed.
- [ ] **Step 5: Re-derive the published artifacts** (`uv run --frozen autorate snapshot && uv run --frozen autorate report`) and confirm with `git diff --stat data/ docs/RESULTS.md` that no count moved: the real archive has no malformed lines, so this task must change zero published numbers. **A published number moving here means the accounting changed, and that is a finding, not a re-gen.**
- [ ] **Step 6: Commit** — `git commit -m "fix(reader): a malformed archive line is a named quarantine, not rc 1"`.

---

### Task 2: Say which confidence scale each backend publishes, and let the data say it

**Files:**
- Create: `src/autorate/scales.py`
- Test: `tests/test_scales.py`

**Interfaces:**
- Consumes: `Record.probs`, `Record.scores["reported_confidence"]`, `records.max_confidence`, `records.entropy_confidence`.
- Produces: `scale_attribution(records) -> dict` with keys `"n"`, `"max_dev_answer"` (largest distance to `max(p)`), `"max_dev_entropy"` (largest distance to `1 − H/log k`), `"verdict"` ∈ `{"answer_confidence", "confidence_entropy", "neither", "absent"}`, `"tolerance"`.

The G2 claim is an attribution claim: it says the field the README tells you to gate on is `confidence = 1 − H/log k`. Measured on 2026-10-03 over the committed records, laya's `reported_confidence` matches the entropy scale to **2.23e-4** and differs from `max(p)` by up to **0.3837**; jev matches **neither** (up to 0.157 from entropy, 0.170 from max). So "confidence" is not one quantity across backends, and the audit must name that rather than average it. This task makes the attribution a computation instead of a sentence in a spec.

- [ ] **Step 1: Write the failing test.**

```python
"""Which confidence scale is a published number? Decided by distance, per backend."""
import json
from pathlib import Path

import pytest

from autorate.records import Record
from autorate.scales import scale_attribution

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"


def _choice(backend, probs, reported):
    keys = tuple("abcd")[:len(probs)]
    return Record(id="x", qtype="choice", backend=backend, repeat=0, options=keys,
                  probs=probs, gold=keys[0], predicted=keys[0], slices={},
                  scores={"reported_confidence": reported}, seed=0, u=0.0, meta={})


def test_a_reported_entropy_value_is_attributed_to_the_entropy_scale():
    from autorate.records import entropy_confidence
    p = (0.5, 0.3, 0.2)
    d = scale_attribution([_choice("b", p, entropy_confidence(p))])
    assert d["verdict"] == "confidence_entropy", d


def test_a_reported_max_probability_is_attributed_to_answer_confidence():
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.5)])
    assert d["verdict"] == "answer_confidence", d


def test_a_number_that_is_a_function_of_neither_is_called_neither():
    # jev's published confidence is its own quantity; forcing it into one of the two
    # scales is exactly the misattribution this module exists to prevent.
    d = scale_attribution([_choice("b", (0.5, 0.3, 0.2), 0.77)])
    assert d["verdict"] == "neither", d


def test_absent_field_is_reported_absent_rather_than_zero():
    r = _choice("b", (0.5, 0.3, 0.2), None)
    assert scale_attribution([r])["verdict"] == "absent"


@pytest.mark.skipif(not COMMITTED.exists(), reason="committed records not present")
def test_the_committed_archive_confirms_the_attribution_the_audit_rests_on():
    rows = [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]
    by = {}
    for d in rows:
        if d["qtype"] == "choice":
            by.setdefault(d["backend"], []).append(Record.from_dict(d))
    laya = scale_attribution(by["laya"])
    jev = scale_attribution(by["jev"])
    assert laya["verdict"] == "confidence_entropy", laya
    assert jev["verdict"] == "neither", jev
    # The direction is the finding: laya's published number sits inside the tolerance of
    # the entropy scale and 0.38 away from max(p) at worst. Asserting the reverse here
    # would be the misattribution this module exists to catch.
    assert laya["max_dev_entropy"] <= laya["tolerance"] < laya["max_dev_answer"], laya
    assert jev["max_dev_entropy"] > jev["tolerance"], jev
    assert jev["max_dev_answer"] > jev["tolerance"], jev
```

- [ ] **Step 2: Verify RED** — `uv run --frozen pytest tests/test_scales.py -q -p no:randomly`; expected: collection error `ModuleNotFoundError: No module named 'autorate.scales'`.
- [ ] **Step 3: Implement** `scale_attribution`:

```python
"""Decide what a published confidence number *is*, from the probabilities beside it."""
from __future__ import annotations

from typing import Sequence

from .records import entropy_confidence, max_confidence

# Served probabilities are rounded to 4 decimals, so agreement inside 1e-3 is the same
# quantity rather than a coincidence: at k=4 the README's own 0.85 gate requires
# p_max = 0.9609 (spec 7.4), which puts the two scales 0.1109 apart at that point -- 111x
# this tolerance. (The 0.0582 figure belongs to a different quantity: the spread of
# required p_max across option counts at gate 0.85, pinned in tests/test_records.py.)
TOLERANCE = 1e-3


def scale_attribution(records: Sequence) -> dict:
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
        verdict = "neither"
    return {"n": len(dev_answer), "max_dev_answer": da, "max_dev_entropy": de,
            "verdict": verdict, "tolerance": TOLERANCE}
```

The `neither` branch is not a failure of this function: jev's `confidence` is genuinely its own quantity, and reporting it as `neither` is what stops a later task from treating two backends' same-named fields as one measurement -- which would silently unmake the pairing §14's neutrality claim rests on.

- [ ] **Step 4: Verify GREEN** on the same command; expected: `5 passed`. If the committed-archive test fails, **read the numbers before editing anything** — a changed archive would be a finding about the data, and the tolerance is the thing under test, not the thing to relax.
- [ ] **Step 5: Commit** — `git commit -m "feat(scales): attribute a published confidence to the scale it actually is"`.

---

### Task 3: The threshold gate, sharing its case arithmetic with the set gate

**Files:**
- Create: `src/autorate/case_count.py`, `src/autorate/certify_threshold.py`
- Modify: `src/autorate/certify_choice.py:90-124` (delete `_outcome`, import the shared one)
- Test: `tests/test_certify_threshold.py`, plus the existing `tests/test_certify_choice.py` unchanged

**Interfaces:**
- Consumes: `split_cal(records, seed)`, `case_key(record)`, `clopper_pearson_upper`, `bound_width`, `Certificate`, `Reason`, `N_CLAIMS`.
- Produces: `count_outcome(half, kind, measure=None) -> dict` where `kind(record) -> str` returns one of `"auto" | "multi" | "empty" | "refuse"` and `measure(record) -> float` is optional — returning a dict with the keys `_outcome` returns today (`automated, errors, empties, multi_label, n_cases, automated_cases, erroneous_cases`) plus `refused` and `refused_cases`, and `mean_measure` only when `measure` is supplied. A **bool** cannot carry that shape: the buckets `empties` and `multi_label` come from the three-way `classify_set`, so a `decide(record) -> bool` counter would either drop two published keys or invent them. `"refuse"` exists because the threshold gate's non-automated decision is neither an empty set nor a multi-label one — borrowing either name would put a false statement into `empties`/`multi_label` on the certificate. Each certifier publishes the mean under its OWN meta key (`certify_choice` → `mean_set_size`, `certify_threshold` → `mean_score`), so the shared arithmetic never names a published figure and no number acquires a second owner. Also produces `sweep_thresholds(records, score_field, grid=None) -> list[dict]`, each row `{"lambda", "automated", "marginal_errors", "automated_cases", "erroneous_cases"}`; and `certify_threshold(records, score_field="confidence", alpha=0.05, beta=0.05, delta=0.05, seed=0, grid=None) -> Certificate`.

§6.4 requires both gates implemented and **contrasted on the same records**, and R-34 requires the auto/escalate rule to have one owner. So the counting moves out of `certify_choice` first; the new certifier then consumes it. `certify_threshold` selects λ on the **calibration half only** (R-28's rule, restated for this gate: the evaluation half never picks its own threshold).

- [ ] **Step 1: Write the failing tests for the extraction** — put these in `tests/test_certify_threshold.py`:

```python
"""The threshold gate, and the case arithmetic both certifiers share."""
import random

import pytest

from autorate.case_count import count_outcome
from autorate.certificate import Reason
from autorate.certify_choice import certify_choice
from autorate.certify_threshold import certify_threshold
from autorate.records import Record


def _rec(i, backend, case, probs, gold, predicted, conf, seed=0):
    keys = tuple("abc"[:len(probs)])
    # `case_id` is the field `case_key` reads; `meta.request_sha256` is provenance only.
    # Setting the latter and not the former would make every repeat its own case and the
    # grouping assertions below pass for the wrong reason.
    return Record(id="%s-%d" % (case, i), qtype="choice", backend=backend, repeat=i,
                  options=keys, probs=probs, gold=keys[gold], predicted=keys[predicted],
                  slices={"family": "f%d" % (i % 4)}, scores={"confidence": conf},
                  seed=seed, u=0.0, meta={"request_sha256": case}, case_id=case)


def _mixed(n=200, seed=7):
    """Half right, half wrong, with confidence separated so a threshold exists."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        ok = i % 2 == 0
        conf = 0.95 if ok else 0.40
        gold, pred = (0, 0) if ok else (0, 1)
        out.append(_rec(i % 3, "b", "case-%03d" % (i // 3),
                        (conf, 1 - conf, 0.0), gold, pred, conf, seed))
    return out


def test_count_outcome_automates_a_case_only_when_every_record_in_it_automates():
    recs = _mixed(6)
    recs += [_rec(0, "b", "extra", (0.9, 0.1, 0.0), 0, 0, 0.95)]
    d = count_outcome(recs, lambda r: "auto" if r.scores["confidence"] >= 0.9 else "refuse")
    assert d["n_cases"] == len({r.case_id for r in recs})
    assert d["automated"] == sum(1 for r in recs if r.scores["confidence"] >= 0.9)
    # The rule is per-case, not per-record: one failing record in a case refuses it all.
    assert d["automated_cases"] < d["n_cases"], d
    # Exhaustiveness: every case is automated or refused, and the counts add up.
    assert d["automated_cases"] + d["refused_cases"] == d["n_cases"], d
    assert d["erroneous_cases"] <= d["automated_cases"], d


def test_the_two_certifiers_count_the_same_split_the_same_way():
    # R-34: one rule, one counter. If either certifier re-implements the buckets, this
    # is the test that says so.
    recs = _mixed(300)
    set_cert = certify_choice(recs, alpha=0.05, beta=0.05, seed=3)
    thr_cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05,
                                 seed=3)
    for key in ("n_eval_cases", "automated_cases", "erroneous_cases", "n_cal_cases"):
        assert set_cert.meta[key] == thr_cert.meta[key], (key, set_cert.meta[key],
                                                          thr_cert.meta[key])
```

- [ ] **Step 2: Verify RED** — expected: `ModuleNotFoundError` for `autorate.case_count`.
- [ ] **Step 3: Extract.** Move `_outcome`'s bucket logic into `case_count.count_outcome(half, kind, measure=None)` where `kind(record) -> str` replaces the `kind == "auto"` test; `conformal_set`/`classify_set` stay in `certify_choice`, which now passes `lambda r: classify_set(conformal_set(r.probs, qhat, r.u, method))`. Keep every existing key name exactly — `certify_choice`, `verify` and the published `meta` all read them — and ADD `refused` (records not automated) and `refused_cases` (cases with at least one non-automated record, so `automated_cases + refused_cases == n_cases` is assertable). `_outcome`'s `size_sum / len(ev)` becomes `mean_measure` computed from the optional `measure` callable, which `certify_choice` supplies as `len(conformal_set(...))` and publishes into its own meta as `mean_set_size`. The extraction is a move, not a rewrite: if any existing key changes name or value, that is a regression in this step, not an improvement.
- [ ] **Step 4: Run the *unchanged* set-gate suite** — `uv run --frozen pytest tests/test_certify_choice.py -q -p no:randomly`. Expected: all pass. This is the refactor's real gate: 40-odd assertions about the set certificate, none of which was touched.
- [ ] **Step 5: Write the failing threshold tests**:

```python
def test_lambda_is_chosen_on_the_calibration_half_and_never_moves_on_the_eval_half():
    # R-28 restated for this gate: a threshold tuned to the evaluation numbers is not a
    # calibrated rule, it is the answer dressed as a method.
    recs = _mixed(300)
    a = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.20, seed=3)
    b = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05, seed=3)
    assert a.qhat != b.qhat, "the budget must actually move the operating point"
    assert a.autorate > b.autorate, (a.autorate, b.autorate)
    # R-54: this test moves `beta`, never `alpha`. At the published rubric alpha == beta == 0.05, so
    # a variant that gated on the wrong symbol would still pass a test that varied alpha.
    c = certify_threshold(recs, score_field="confidence", alpha=0.20, beta=0.05, seed=3)
    assert c.qhat == b.qhat and c.autorate == b.autorate, (
        "alpha must not move the threshold gate's operating point; it gates the set rule only")


def test_the_marginal_risk_of_an_automated_error_is_monotone_in_lambda():
    # §6.1/§6.4's precondition, and exactly what the naive weighted loss violated.
    from autorate.certify_threshold import sweep_thresholds
    recs = _mixed(300)
    rows = sweep_thresholds(recs, "confidence", grid=(0.0, 0.3, 0.6, 0.9, 0.99))
    marg = [r["marginal_errors"] for r in rows]
    assert marg == sorted(marg, reverse=True), marg
    assert [r["automated"] for r in rows] == sorted([r["automated"] for r in rows],
                                                    reverse=True), rows


def test_a_field_that_is_constant_cannot_be_certified_and_says_which_failure_it_is():
    recs = [_rec(i, "b", "c%d" % i, (0.6, 0.3, 0.1), 0, 0, 0.5) for i in range(200)]
    # Structural, not wording: a constant field collapses the grid to two distinct operating
    # points, so the failure is a property of the data and no phrasing choice can satisfy it.
    from autorate.certify_threshold import sweep_thresholds
    rows = sweep_thresholds(recs, "confidence", grid=(0.0, 0.3, 0.6, 0.9, 0.99))
    assert len({r["automated"] for r in rows}) == 2, rows
    cert = certify_threshold(recs, score_field="confidence", alpha=0.05, beta=0.05)
    assert cert.feasible is False
    # By symbol, not by literal: Task 5 splits this label in two (PF-B1-2), and an
    # assertion naming the enum member is one the rename can find.
    assert cert.reason == Reason.EMPTY_FEASIBLE_SET.value, cert.reason
    # The closest-to-meeting point is recorded, not invented: this is the artefact that makes the
    # refusal auditable, so assert its shape rather than a sentence inside it.
    assert cert.meta.get("closest_attempt"), cert.meta


def test_an_unknown_score_field_is_a_usage_error_not_a_silent_zero():
    with pytest.raises(ValueError, match="confidence"):
        certify_threshold(_mixed(6), score_field="nope")
```

- [ ] **Step 6: Implement `certify_threshold`.** Structure mirrors `certify_choice` deliberately, so a reader comparing the two gates compares like with like: validate budgets; `split_cal`; refuse `NO_GOLD_LABELS` / `N_BELOW_MIN`; select λ as the grid point maximising calibration-half automation subject to `clopper_pearson_upper(cal_errors, cal_automated, delta) <= beta` computed **on the calibration half**; then evaluate on the held-out half through `count_outcome` and publish `conditional_error_bound` / `marginal_error_bound` / `autorate` on **cases**; refuse with `cond_hi > beta` after recording `closest_attempt`. `mean_score` replaces `mean_set_size` in `meta` (the set shape is meaningless here) and the envelope carries one extra line: `"rule: automate iff <field> >= lambda; this is the threshold gate of spec 6.4, not the APS set gate"`.
  **Corrected on pre-flight (R-54): the selection constraint is β, not α.** The plan first said `<= alpha`. That is a semantics bug the tests could never catch, because the published rubric has `alpha == beta == 0.05` — the two are numerically identical at every default in this repository, so an implementation gating on α would pass green while answering a different question. `beta` is the budget on `P(wrong | automated)` (spec §2, §5.5); `alpha` is the coverage level of the SET gate, and the threshold gate has no coverage set at all. Consequently Step 5's operating-point test varies **beta**, not alpha, and `alpha` is carried in the threshold certificate for rubric comparability with `compare` — with an envelope line saying plainly that α does not gate λ here. A parameter that silently means nothing is how two gates stop being comparable.
- [ ] **Step 7: Run both suites**, `uv run --frozen pytest tests/test_certify_choice.py tests/test_certify_threshold.py -q -p no:randomly`; expected: all pass.
- [ ] **Step 8: Commit** — `git commit -m "feat(threshold): the 6.4 gate, sharing case arithmetic with the set gate so one rule has one owner"`.

---

### Task 4: `autorate audit` — the three-field comparison, and G2's multiple

**Files:**
- Create: `src/autorate/audit.py`
- Modify: `src/autorate/cli.py` (`build_parser`, `cmd_audit`, `CERT_COMPARE_FIELDS` if the shape grows)
- Create: `docs/AUDIT.md`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: `count_outcome`, `clopper_pearson_upper`, `scale_attribution`, `Record.scores`, committed `data/records_feishu.jsonl`, `records.load_records`.
- Produces: `audit_fields(records, gate=0.85, delta=0.05) -> dict` keyed by field, each row `{"n_records", "n_cases", "automated_cases", "erroneous_cases", "measured_error", "implied_error", "multiple", "bound", "informative", "attributed_scale"}`; `frontier(records, fields, grid) -> list[dict]`, one row per `(field, lambda)` with `automated_cases` and `erroneous_cases`, which is §7.3's risk-coverage curve as data rather than as prose; and the rendered `docs/AUDIT.md`.

G2 asks for "measured error among automated decisions vs the 15% that sentence implies; report the multiple by which it misses". Measured on the committed archive at `>= 0.85`, deduplicated to cases: laya `confidence` automates 2 of 64 cases and 1 of those is wrong (**0.5000**, 3.33×), `answer_confidence` automates 9 and misses 5 (**0.5556**, 3.70×), `act_probability` automates all 64 with 44 wrong (**0.6875**, 4.58×). Every one of those is above the 15% the README's own sentence implies — and at n=2 the Clopper–Pearson upper bound is ≈0.92, so **the corpus cannot bound the gate it is being asked to certify**. Both halves are results; the plan publishes both and refuses to quote the bound as if it were tight.

- [ ] **Step 1: Write the failing test.** Assert relationships the code produces, never a hand-typed multiple:

```python
"""G2: the gate the reference README instructs, measured against what it implies."""
import json
from pathlib import Path

import pytest

from autorate.audit import audit_fields, render_audit
from autorate.records import Record

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "records_feishu.jsonl"


@pytest.fixture(scope="module")
def laya():
    rows = [json.loads(l) for l in COMMITTED.read_text().splitlines() if l.strip()]
    return [Record.from_dict(d) for d in rows if d["backend"] == "laya"
            and d["qtype"] == "choice"]


def test_every_field_the_readme_offers_misses_its_own_implied_error_rate(laya):
    rows = audit_fields(laya, gate=0.85)
    assert set(rows) == {"confidence", "answer_confidence", "act_probability"}, rows
    for name, r in rows.items():
        assert r["automated_cases"] > 0, name
        assert r["measured_error"] > r["implied_error"], (name, r)
        assert r["multiple"] > 1.0, (name, r["multiple"])


def test_the_denominator_is_cases_and_says_so(laya):
    # 192 archived laya choice rows are 64 cases x 3 repeats carrying the SAME probability vector and
    # the SAME published confidence -- not identical ROWS, since `meta`, `repeat` and `slices` differ
    # (jev's 191 rows are the same 64 cases carrying 1-3 distinct vectors). Counting rows would print a
    # 3x larger sample than the one that exists (R-36, R-44). Do not write "byte-identical repeats": the
    # archive refutes it of the rows, and tests/test_report_prose.py reddens the sentence if it is typed.
    rows = audit_fields(laya, gate=0.85)
    assert rows["confidence"]["n_records"] == 192
    assert rows["confidence"]["n_cases"] == 64


def test_where_the_sample_cannot_bound_the_gate_the_audit_reports_that_instead(laya):
    rows = audit_fields(laya, gate=0.85)
    r = rows["confidence"]
    assert r["bound"] is not None and r["bound"] > 0.9, r
    assert r["informative"] is False, "a 0.92 bound is not a certificate of anything"


def test_the_audit_names_the_scale_each_field_actually_is(laya):
    rows = audit_fields(laya, gate=0.85)
    assert rows["confidence"]["attributed_scale"] == "confidence_entropy", rows["confidence"]


def test_the_published_curve_exists_and_rises_with_the_gate(laya):
    # 7.3 asks for a frontier per field, not one number at one gate: a single point is
    # the shape of claim this project exists to refuse.
    from autorate.audit import frontier
    rows = frontier(laya, ("confidence", "answer_confidence"),
                    grid=(0.0, 0.3, 0.6, 0.85, 0.99))
    for field in ("confidence", "answer_confidence"):
        pts = [r for r in rows if r["field"] == field]
        assert [r["automated_cases"] for r in pts] == sorted(
            [r["automated_cases"] for r in pts], reverse=True), pts
    assert {r["field"] for r in rows} == {"confidence", "answer_confidence"}


def test_rendered_audit_contains_no_machine_path_and_no_unproduced_number(tmp_path, laya):
    text = render_audit({"laya": audit_fields(laya, gate=0.85)})
    assert "laya-0.3.20/" not in text or "research/benchmarks" in text
    for tok in ("/Users/", "/home/"):
        assert tok not in text, tok
    assert "3.33" in text or "3.3" in text, "the multiple must be produced, not narrated"
```

- [ ] **Step 2: Verify RED** (`ModuleNotFoundError: autorate.audit`).
- [ ] **Step 3: Implement `audit_fields`.** For each field, build `decide = lambda r: value_of(r, field) >= gate`, run `count_outcome` over the records, take `measured_error = erroneous_cases / automated_cases`, `implied_error = 1 - gate`, `multiple = measured_error / implied_error`, `bound = clopper_pearson_upper(erroneous_cases, automated_cases, delta)`, `informative = bound <= implied_error`, and `attributed_scale = scale_attribution(...)`'s verdict for the fields that are functions of `probs`. `act_probability` is carried, not scored by attribution. Emit an explicit `NOT_INFORMATIVE` note on any row where `informative is False` — spec §7.3's requirement is that the tool "never returns a number for a field that cannot support one", and here the honest rendering is the point estimate plus the refusal to bound it.
  **Corrected on pre-flight (R-56): attribution is per slice, not per field over a flat list.** This step as first written calls `scale_attribution` once per field over `records`, but Task 2's guard (`scales.py:36-42`) requires one `(backend, qtype)` per batch and raises `ValueError` naming the mixed keys otherwise — and `data/records_feishu.jsonl` holds laya choice, laya noul and jev choice together, so the sketch raises before producing any row. Group by `(backend, qtype)`, attribute each slice once, and have the row name its slice; a row that spans slices says so rather than averaging. Carried with it: publish the mixture counts beside the aggregate verdict (a bare `jev: neither` is false for 97 of its 191 attributable rows), and do not inherit `readers/feishu_zh.py`'s comment as fact — measured, `reported_confidence == max(p)` for 768/768 laya noul rows including 9 where `P(true) < 0.5`, so the comment states a coincidence of the data as upstream's semantics and the flag name repeats it (obligations #31/#32).
- [ ] **Step 4: Add the CLI.** `autorate audit [backend] --gate 0.85 --out docs/AUDIT.md`, writing through the same exit-code map as the other commands (no corpus → rc 2 via `UsageError`, not rc 1).
- [ ] **Step 5: Run it and read the artifact** — `uv run --frozen autorate audit laya --out docs/AUDIT.md`; confirm the table matches the fixture's assertions in its own words.
- [ ] **Step 6: Commit** — `git commit -m "feat(audit): the three-field gate comparison G2 asks for, on committed records"`.

---

### Task 5: Split the refusal that names two failures, and tag the shape

**Files:**
- Modify: `src/autorate/certificate.py`
- Test: `tests/test_certificate.py`, `tests/test_certify_threshold.py`

**Interfaces:**
- Produces: `Reason.NO_AUTOMATION_AT_COVERAGE = "no_automation_at_coverage"` and `SHAPE_VERSION = 2`, emitted as `"shape": 2` in `to_dict()` and required by `from_dict`.

I-10: `empty_feasible_set` currently covers "nothing automates" (laya, Task 4 of Plan A) and "something automates but its bound misses the budget" (jev). They are different findings — one says the task is not automatable, the other says the data cannot certify it — and §5.5's whole claim is that the reason travels inside the certificate. D14 separately ruled in a version tag, because `from_dict` currently refuses a stale artifact by field-name diff alone.

- [ ] **Step 1: Share the generator, then write the failing tests.** `tests/test_certify_choice.py:16` already owns the only good synthetic labelled-record generator in the repo (`_records(n, k=4, sharpness=6.0, seed=1, backend="synthetic", unlabelled=0, error_rate=0.0)`), and this task needs two of its shapes. No test module in this suite imports another, and `tests/` has no `__init__.py` (PF-B1-4), so the shared helper goes where pytest guarantees it: a new `tests/conftest.py` exposing a `records_factory` fixture that wraps the generator verbatim, with `test_certify_choice.py` re-exporting it as `_records = records_factory` at module scope so its 40-odd existing call sites stay untouched.

```python
"""Shared synthetic-record source. Tests import this; nothing else crosses modules."""
import pytest

def _build(n, k=4, sharpness=6.0, seed=1, backend="synthetic", unlabelled=0,
           error_rate=0.0):
    """Moved verbatim from tests/test_certify_choice.py:16 -- see its docstring for why
    `error_rate` exists: a generator that can never be wrong cannot show a refusal.
    """
    ...   # the body, copied unchanged


@pytest.fixture
def records_factory():
    return _build
```

Copy the body unchanged; the `...` above is this plan pointing at 18 lines that already exist in the repository, at a named line, in the file the task is moving them out of -- not a step to invent.

```python
"""Two refusals that used to share one label, and the tag the shape was written in."""
import pytest
from _synthetic import _records

from autorate.certificate import SHAPE_VERSION, Certificate
from autorate.certify_choice import certify_choice


@pytest.fixture(scope="module")
def pair():
    # The flat shape is spec 5.5's own anchor case: nothing automates at coverage 0.95.
    # The noisy shape automates and misses: its bound over the automated cases is above
    # beta. Both used to print `empty_feasible_set`, which read as one finding.
    return (certify_choice(_records(1200, sharpness=1.0, error_rate=0.5), alpha=0.05,
                           beta=0.05, seed=7),
            certify_choice(_records(1600, sharpness=5.0, error_rate=0.35), alpha=0.05,
                           beta=0.05, seed=7))


def test_nothing_automating_and_the_budget_missing_are_different_reasons(pair):
    flat, noisy = pair
    assert flat.feasible is False and noisy.feasible is False, (flat, noisy)
    assert flat.reason == Reason.NO_AUTOMATION_AT_COVERAGE.value, flat.reason
    assert noisy.reason == Reason.EMPTY_FEASIBLE_SET.value, noisy.reason


def test_a_stored_certificate_without_a_shape_version_is_refused_by_name(pair):
    cert = next(c for c in pair if c.feasible) if any(c.feasible for c in pair) \
        else _cert_ok()
    d = cert.to_dict()
    del d["shape"]
    with pytest.raises(ValueError, match="shape"):
        Certificate.from_dict(d)


def _cert_ok():
    # A feasible certificate, built here rather than assumed by the caller.
    cert = certify_choice(_records(1600, sharpness=8.0), alpha=0.05, beta=0.20, seed=7)
    assert cert.feasible is True, cert.summary()
    return cert


def test_the_shape_version_is_one_number_with_one_owner():
    d = _cert_ok().to_dict()
    assert d["shape"] == SHAPE_VERSION
    assert Certificate.from_dict(d).to_dict()["shape"] == SHAPE_VERSION
```

If `_records(1600, sharpness=5.0, error_rate=0.35)` turns out to produce a *feasible* certificate at these budgets rather than an over-budget one, do not bend the assertion to match: read what `test_certify_choice.py:98-101` already proves about that generator, and pick the shape from the case the existing suite shows misses `beta`.

- [ ] **Step 2: Verify RED**, then **Step 3: Implement** — add the enum member, move the `autom == 0 or auto_case == 0` branch in both certifiers to it (the `cond_hi > beta` branch keeps `EMPTY_FEASIBLE_SET`), and add `SHAPE_VERSION` to `to_dict`/`from_dict`.
- [ ] **Step 4: Fix the closed-set guard, not the count.** `tests/test_gate.py` asserts `reason` is in the `Reason` set; run the full suite and check that the *only* red tests are ones pinning the old string, which you update with a reason, never by deletion.
- [ ] **Step 5: Regenerate `data/cert_laya.json` and `data/cert_jev.json`** and show the diff: `reason` changes on one file, `shape` is added to both, and **no bound, rate or count may move**. Commit: `git commit -m "feat(certificate): name the two refusals differently, and tag the shape both were written in"`.

---

### Task 6: Make `verify` own every new number, and let the runner prove it

**Files:**
- Modify: `src/autorate/cli.py` (`cmd_verify`), `README.md`, `docs/RESULTS.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything Tasks 1–5 published.
- Produces: extra `verify` rows for the audit table and the reader's malformed-line count, and a README that states the B1 scope boundary.

G5 is the criterion this project is judged by, and it says *every* published number re-derives. A new document (`docs/AUDIT.md`) without a `verify` row would be the exact thing §10 was written to prevent.

- [ ] **Step 1: Write the failing test** in `tests/test_cli.py`, following `test_verify_catches_an_inventory_snapshot_that_went_stale`: plant a one-character edit to a number in `docs/AUDIT.md`, run `main(["verify"])`, and assert rc `EXIT_DRIFT` — then assert the unmodified tree returns 0, and that the row count is **produced**, not typed:

```python
def test_verify_row_count_is_the_list_verify_walks():
    from autorate.cli import PUBLISHED_ROWS

    out = subprocess.run([sys.executable, "-m", "autorate.cli", "verify"],
                         capture_output=True, text=True)
    m = re.search(r"re-derived (\d+) /(\d+)", out.stdout)
    assert m, out.stdout
    printed, total = int(m.group(1)), int(m.group(2))
    assert printed == total, "a row that claimed a re-derivation it could not perform"
    assert total == len(PUBLISHED_ROWS) + UNREACHABLE_ROWS_HERE, (out.stdout,
                                                                 len(PUBLISHED_ROWS))
```

`PUBLISHED_ROWS` is the list `cmd_verify` walks to emit its rows, which today is built inline; pulling it out is part of this task, because a count that is a literal in a test is the second owner of a number the tool already owns. `UNREACHABLE_ROWS_HERE` is the corpus-dependent remainder, and in this lane it is 0 — `data/records_feishu.jsonl` is committed, which is exactly why the audit can be policed on a runner. Assert the same equality with `AUTORATE_FEISHU_ROOT=/nonexistent`, where the vendored-corpus rows do become unreachable: the two lanes must differ by the named rows and nothing else.
- [ ] **Step 2: Verify RED** — the planted edit must currently pass `verify`, because nothing reads the file. That red is the proof the check was missing, and it is the honest reason this task exists.
- [ ] **Step 3: Implement** the rows; keep the corpus-less disclosure convention: when `data/records_feishu.jsonl` is absent (it never is — it is committed), the row reports `unreachable here`, and the count of unreachable rows is asserted in the corpus-less lane exactly as R-27 does today.
- [ ] **Step 4: Simulate the runner before pushing (R-41).**
`AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest -q -p no:randomly` and the same for `autorate verify`; both must exit 0, and the skip count must stay 27 — a new skip here means a test was written against the corpus that should not have been.
- [ ] **Step 5: README and RESULTS.** State what B1 does *not* claim: no certified row at α=0.05 exists yet (Plan A's two refusals stand), G3/G4 are B2/B3, and G1 needs the inference corpus whose cost this plan measured. Commit: `git commit -m "docs(verify): the audit is a published artefact, so the reproduction gate reads it"`.

---

## Gates every task ends at

```bash
uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120
uv run --frozen pytest -q -p no:randomly
uv run --frozen autorate verify
AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest -q -p no:randomly
```

Per R-16 the plan states no expected counts: the pass count of record is the one the gate prints, and the corpus-less lane's is the one the runner prints.

## Out of scope for this plan (so a dispatch does not drift into it)

Ordinal nested intervals and the severity certificate (G3) → Plan B2. Mondrian, the simultaneous correction, `n_min_violations`, ACI and the contamination Δ̂ (G4, §9) → Plan B3, where the §10 spec amendment I-8 belongs. The MASSIVE/`typed-decisions` build and any checkpoint download → Plan C, which needs the human partner's explicit go-ahead for a ~0.84 GB fetch and a long inference job before a single line of it runs.
