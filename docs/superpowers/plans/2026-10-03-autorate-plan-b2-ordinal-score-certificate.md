# Plan B2 — Ordinal `score`: nested interval sets, the one-sided severity certificate, and G3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `autorate` the ordinal `score` primitive -- nested minimum-length interval sets, a one-sided severity certificate `P(Y > â(X)) ≤ α`, and a tolerance band -- and demonstrate **G3**: a guarantee that multiclass set prediction cannot express.

**Architecture:** A pure ordinal layer (`ordinal.py`) supplies the set construction and the nonconformity; `certify_score.py` consumes it exactly the way `certify_choice.py` consumes `conformal.py`, sharing the split and the case-level counting that Plan B1 extracted. The severity certificate is a separate one-sided family because its loss is a different monotone function of a different parameter, not a variant of the set gate.

**Tech Stack:** Python 3.12, stdlib only. No model, no network, no dataset.

**Spec:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` §5.4, §6.2, §6.3, §6.4, §11.1, §11.2, §12 rows 2 and 4; §2's G3. The spec travels with this plan.

## What this plan's evidence can and cannot say (measured, not assumed)

| question | measured answer | consequence |
|---|---|---|
| Is there any ordinal `score` response in the offline corpus? | **No.** `feishu_zh` archive holds 192 `choice` + 768 `noul` answers per backend and **zero `score` answers** | G3's evidence is synthetic-with-known-answers (spec §11.1), and must be labelled that way in every published line |
| Does `score` already exist in the contract? | Yes -- `records.py:13` `QTYPES = ("choice", "score", "noul")`; upstream `laya/common.py:12` maps `score -> 1` | No contract extension is needed to carry ordinal records, only an interval construction |
| Can real ordinal probabilities be obtained? | Only by scoring a `score`-qtype task with the checkpoint (Plan C's driver, which already knows how to emit full distributions) | B2 ends with a mechanism plus a synthetic demonstration; the real-data certificate is a Plan C follow-up, and the README must not blur them |
| Is the construction itself novel? | **No, and the plan says so out loud** -- Dey et al. NeurIPS 2023 generate contiguous ordinal sets with guaranteed coverage and minimal cardinality; Zhang et al. AAAI-26 prove minimum-length ordinal intervals and ship code | The delta is the automation rule, the recorded randomisation, and the two-way bound (§12 row 2). A reviewer who finds "novel ordinal CP" phrasing anywhere in this plan should reject it |

## Global Constraints

- Python 3.12, stdlib only; unit suite and `autorate verify` offline forever; no torch, no model, no network (spec §11.5).
- The certification unit is the case; a row count is never an independent-case count (R-36, R-44).
- One owner per published number; derived values are not stored (R-31, R-34).
- Exit codes 0/2/3/4, nothing escapes as rc 1. No absolute machine path in any tracked file.
- Never relax an assertion to pass a check; no `# noqa`, no lint excludes. A green-on-arrival test must be labelled as such in its docstring.
- A negative control must prove it fired: for every guard this plan adds, plant the defect and show red.
- `uv run --frozen`; `python3`; never a `pytest` from PATH; `-p no:randomly`; exit codes obtained without a pipe swallowing them.
- Commit messages carry no test counts (R-16). Run the corpus-less simulation before any push (R-41).

**Prerequisites from Plan B1:** `case_count.count_outcome(half, decide) -> dict` (Task 3) is the single owner of record-and-case accounting, and `Reason.NO_AUTOMATION_AT_COVERAGE` (Task 5) distinguishes "nothing automates" from "budget unmet". Verify both against the shipped files before writing code against them; if either differs, rule and ledger rather than conforming to this text.

---

### Task 1: The ordinal interval family, with contiguity and nesting as properties

**Files:**
- Create: `src/autorate/ordinal.py`
- Test: `tests/test_ordinal.py`

**Interfaces:**
- Consumes: nothing from this repo except `random`-drawn `u` supplied by the caller.
- Produces: `interval_set(probs: Sequence[float], q: float, u: float = 0.0) -> list[int]` returning the **minimum-length contiguous** index interval whose mass is `>= q`, ties broken leftmost then by `u`; `score_ordinal(probs, gold_index, u) -> float` = `inf{q : gold in C_q}` snapped to the achievable masses; `is_contiguous(indices) -> bool`.

- [ ] **Step 1: Write the failing tests.** The point of these is that they encode *why* multiclass sets are invalid here, not just that the function returns something.

```python
"""Minimum-length contiguous ordinal intervals: nested, contiguous, and mass-ordered."""
import random

import pytest

from autorate.ordinal import interval_set, is_contiguous, score_ordinal


def test_the_interval_is_the_shortest_one_reaching_the_requested_mass():
    p = [0.05, 0.4, 0.35, 0.1, 0.1]
    assert interval_set(p, 0.4) == [1]
    assert interval_set(p, 0.75) == [1, 2]
    assert interval_set(p, 0.85) == [0, 1, 2], "0.05+0.4+0.35 is the cheapest way to 0.8"


def test_mass_ordered_multiclass_sets_are_not_contiguous_and_this_refuses_to_be_one():
    """spec 5.4's actual claim, as an assertion: 'levels 0 or 4' is not an answer.

    A k-of-m top-mass set would pick {1,3,4} for q=0.85 below; the ordinal family
    must return a contiguous span instead, even at the cost of one extra level.
    """
    p = [0.30, 0.34, 0.02, 0.30, 0.04]
    top_mass = sorted(range(5), key=lambda i: -p[i])
    greedy = sorted(top_mass[:3])                       # what mass-ordered CP returns
    assert greedy == [0, 1, 3] and not is_contiguous(greedy)
    ours = interval_set(p, sum(p[i] for i in greedy))
    assert is_contiguous(ours), ours


def test_the_family_is_nested_so_split_conformal_validity_carries_over():
    rng = random.Random(11)
    for _ in range(200):
        k = rng.randrange(2, 8)
        w = [rng.random() + 0.05 for _ in range(k)]
        s = sum(w)
        p = [x / s for x in w]
        u = rng.random()
        prev = None
        for q in sorted({round(x, 3) for x in p} | {0.5, 0.9, 0.99}):
            C = interval_set(p, q, u)
            if prev is not None and q > 0:
                assert all(min(prev) <= x <= max(prev) for x in C) or len(C) >= len(prev), (
                    p, q, C, prev)
            prev = C


def test_the_score_of_the_gold_label_is_the_smallest_q_that_includes_it():
    p = [0.1, 0.6, 0.3]
    assert abs(score_ordinal(p, 1, 0.0) - 0.6) < 1e-12
    assert abs(score_ordinal(p, 0, 0.0) - 0.7) < 1e-12
    assert score_ordinal(p, 2, 0.0) <= 0.9 + 1e-12


def test_a_single_level_distribution_cannot_be_certified_and_says_so():
    with pytest.raises(ValueError, match="degenerate"):
        interval_set([1.0], 0.5)
```

- [ ] **Step 2: Verify RED** (`ModuleNotFoundError: autorate.ordinal`), then **Step 3: Implement** with the O(k²) enumeration the docstring promises and a comment saying why it is acceptable (k ≤ 51 and `predict_shortlist` caps ballots; a heap-based interval would be premature).
- [ ] **Step 4: Green**, then **Step 5: prove the guards can fail** -- replace the contiguity requirement with top-mass selection and confirm the two structural tests go red; restore byte-identically and record the hashes.
- [ ] **Step 6: Commit** — `git commit -m "feat(ordinal): minimum-length contiguous interval sets with contiguity and nesting as properties"`.

---

### Task 2: `certify_score` -- the set gate over the ordinal family

**Files:**
- Create: `src/autorate/certify_score.py`
- Test: `tests/test_certify_score.py`

**Interfaces:**
- Consumes: `split_cal`, `case_key`, `count_outcome`, `split_quantile`, `clopper_pearson_upper`, `bound_width`, `Certificate`, `Reason`, `N_CLAIMS`.
- Produces: `certify_score(records, alpha=0.05, beta=0.05, delta=0.05, seed=0) -> Certificate` with `method="ordinal"` and `meta["mean_interval_length"]`; automation rule: act iff the certified interval is a single level.

- [ ] **Step 1: Write the failing tests**: the same structural guarantees the set gate has -- α moves the operating point rather than relabelling it (R-28), λ/q̂ chosen on the calibration half only, case denominators, refusal decomposition exhaustive (empty / singleton / wider, one owner each), `refusal == 1 - autorate` surviving, and a `subject_mismatch`-style guard so a `score` certificate cannot be applied to `choice` records.
- [ ] **Step 2: Verify RED**, **Step 3: Implement** by mirroring `certify_choice`'s shape deliberately, so a reader comparing the two gates compares like with like.
- [ ] **Step 4: Coverage check on synthetic ordinal data** -- 200 resplits, empirical coverage of `C_q` against the claimed `1 - alpha`, with the tolerance derived from the published bound rather than typed (the R-19 lesson: state what this suite can and cannot detect).
- [ ] **Step 5: Commit** — `git commit -m "feat(score): the ordinal set gate, sharing split and case accounting with the choice gate"`.

---

### Task 3: The one-sided severity certificate -- G3 itself

**Files:**
- Create: `src/autorate/severity.py`
- Test: `tests/test_severity.py`

**Interfaces:**
- Produces: `certify_severity(records, alpha=0.05, delta=0.05, direction="under", seed=0) -> SeverityCertificate` where the guarantee is `P(Y > â(X)) <= alpha` for a *stated* reported level â, plus `report_level(probs, â) -> int` and `tolerance_band(...) -> int` for §6.3.

The construction: for a candidate reported level `a`, the loss `1{Y > a}` is monotone decreasing in `a`, so binary search returns the smallest `a` whose empirical risk, bounded one-sided by Clopper-Pearson over **cases**, meets the budget. Multiclass set CP cannot state this quantity at all -- it can bound `P(Y ∉ C(X))`, which says nothing about which side the miss is on -- and that is what G3 requires us to demonstrate rather than assert.

- [ ] **Step 1: Write the failing tests, including the control that makes G3 mean something.**

```python
"""G3: an ordinal one-sided guarantee, and the control that multiclass CP cannot state it."""
import pytest

from autorate.certify_choice import certify_choice
from autorate.severity import certify_severity


@pytest.fixture
def ordinal_records():
    """Factory for synthetic ordinal decisions, registered in tests/conftest.py.

    Plan B1 Task 5 ruled that shared generators live in `tests/conftest.py` as fixtures
    (no test module imports another in this suite, and `tests/` has no `__init__.py`), so
    this task adds `ordinal_records` there rather than inventing an import path.
    """
    return _build_ordinal          # defined in conftest, returns list[Record]


def test_the_under_call_bound_holds_on_the_evaluation_half(ordinal_records):
    recs = ordinal_records(n=1200, seed=5, shift=0.9)     # model under-reports severity
    cert = certify_severity(recs, alpha=0.05, delta=0.05, direction="under", seed=3)
    assert cert.feasible is True, cert.summary()
    assert cert.bound <= 0.05 + 1e-9
    assert cert.measured_violation <= cert.bound, (
        "a bound below its own observed rate is the arithmetic bug this project already "
        "fixed once in tails.binom_cdf")


def test_a_monotone_loss_is_a_precondition_and_is_enforced_not_assumed(ordinal_records):
    recs = ordinal_records(n=800, seed=6)
    risks = [sum(1 for r in recs if r.gold_index > a) / len(recs) for a in range(5)]
    assert risks == sorted(risks, reverse=True), risks
    with pytest.raises(ValueError, match="monotone"):
        certify_severity(recs, alpha=0.05, direction="both_sides_sum", seed=3)


def test_multiclass_cp_bounds_membership_not_the_side_of_the_miss(ordinal_records):
    """The control. If APS can be made to state `P(Y > a_hat) <= alpha`, G3 has failed."""
    recs = ordinal_records(n=1200, seed=5, shift=0.9)
    aps = certify_choice(recs, alpha=0.05, beta=0.05, method="aps", seed=3)
    sev = certify_severity(recs, alpha=0.05, delta=0.05, direction="under", seed=3)
    assert hasattr(sev, "bound") and sev.bound <= 0.05
    for name in ("marginal_error_bound", "conditional_error_bound"):
        assert getattr(aps, name) is not None
    assert "P(Y >" in sev.summary() and "P(Y >" not in aps.summary(), (
        "the quantity G3 claims to add must be the one the control cannot print")
```

- [ ] **Step 2: Verify RED**, **Step 3: Implement** the binary search with the monotonicity precondition raised as `ValueError` naming the direction that violated it, **Step 4: Green**.
- [ ] **Step 5: Publish the honest framing.** `summary()` and any doc line must carry "synthetic ordinal data with known answers" and the §12 prior-art concession (Dey NeurIPS 2023, Zhang AAAI-26 own the construction; ours is the automation rule plus the one-sided statement). Commit: `git commit -m "feat(severity): the one-sided ordinal certificate G3, with multiclass CP as the control"`.

---

### Task 4: The tolerance band, and both directions when the deployment wants both

**Files:**
- Modify: `src/autorate/severity.py`
- Test: `tests/test_severity.py` (append)

**Interfaces:**
- Produces: `tolerance_band(records, alpha=0.05, delta=0.05, seed=0) -> dict` with `d` = smallest integer such that `P(|Y - â(X)| > d) <= alpha` (spec §6.3), and `over_call_bound(...)` for the symmetric direction.

- [ ] **Step 1: Write the failing tests** -- `d` indexes a monotone family so the search is the same shape as §6.2's (no new machinery, and a test that the code adds none); a distribution that never misses by more than one level yields `d == 1`, and a test asserts the guard's own arithmetic: `d` cannot be reported as 0 while any automated case missed.
- [ ] **Step 2-4: RED, implement, Green.**
- [ ] **Step 5: Commit** — `git commit -m "feat(severity): tolerance band and the over-call direction"` (exact subject is yours to improve; the content is the requirement).

---

### Task 5: Wire it to the surface, and make `verify` own every new number

**Files:**
- Modify: `src/autorate/cli.py` (`certify --qtype score`, `report`), `src/autorate/gate.py` (the `qtype_not_covered` branch must stop firing for `score`), `docs/RESULTS.md`, `README.md`
- Test: `tests/test_certify_score_cli.py`

- [ ] **Step 1: Write the failing tests** -- a `score` record set reaches `certify_score` rather than being skipped as `qtype_not_covered`; the gate decides on a `score` certificate; `autorate verify` re-derives every published severity number from committed inputs; and the exit-code contract holds for a `score` corpus that cannot certify (rc 3, not rc 1).
- [ ] **Step 2: Verify RED**, **Step 3: Implement**, **Step 4: run all four gates** plus the corpus-less simulation.
- [ ] **Step 5: README and RESULTS wording.** G3's line must say which numbers are synthetic-with-known-answers, which mechanism is real and reusable, and that no real ordinal probabilities exist offline (the measured zero `score` answers), pointing at Plan C's driver for the real-data version.
- [ ] **Step 6: Commit**, push the branch, and read the runner's own per-step conclusions before claiming anything about CI.

---

## Gates every task ends at

```bash
uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120
uv run --frozen pytest -q -p no:randomly
uv run --frozen autorate verify
AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest -q -p no:randomly
```

## Out of scope

Real ordinal data → Plan C's driver (same code path, a `score` qtype task). Per-slice Mondrian control and the simultaneous correction → Plan B3. The spec §10 `n_min_violations` amendment (I-8) was ruled to land with B3's Mondrian work, and it must not be half-implemented here.
