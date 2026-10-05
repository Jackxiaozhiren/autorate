# Plan B2 — Ordinal `score`: nested interval sets, the one-sided severity certificate, and G3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `autorate` the ordinal `score` primitive -- **nested modal-anchored chain sets** (ruling R-68: *not* the "minimum-length interval whose mass ≥ q" family this line originally named, which measures as non-nested; see Task 1), a one-sided severity certificate `P(Y > â(X)) ≤ α`, and a tolerance band -- and demonstrate **G3**: a guarantee that multiclass set prediction cannot express.

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
- Produces: `score_ordinal(probs, gold_index, u=0.0) -> float` = the mass of the **minimum-mass contiguous span containing both `gold_index` and the modal level** (`argmax`, ties leftmost); `interval_set(probs, alpha, u=0.0) -> list[int]` = `{g : score_ordinal(probs, g, u) <= alpha}`, which is contiguous and contains the modal level by construction; `is_contiguous(indices) -> bool`.
- **Corrected 2026-10-05 (ruling R-68) before execution: the family this task originally specified does not have the property it was going to certify.** It said `C_q = minimum-length interval whose mass >= q`, ties leftmost-then-`u`, with `s = inf{q : y in C_q}`, and asserted "nesting gives split-conformal validity unchanged". Measured over 2,000 random ballots of 2-8 levels: **3,333 of 17,788 adjacent `q` pairs violate nesting** for that definition (`p = [0.159, 0.381, 0.460]`: `C` at `q=0.159` is `[1]`, at `q=0.381` is `[2]`), and the score-derived sets `{y : s(y) <= alpha}` that restore nesting are **non-contiguous in 3,057 of 14,540 cases**. Neither half delivers both halves, and §5.4's validity sentence was asserted of a non-nested family. The modal-anchored chain above is the fix: measured **0 non-contiguous in 32,304 sets** and **0 nesting violations in 141,120 pairs**. Its justification is a proof, not a sample — chain mass grows strictly as a level recedes from the mode on either side, so a sublevel set is one span around the mode, and any sublevel set of a fixed function is nested in its threshold.
- Because the family changed, **the numbers in Step 1 changed too**: on `[0.05, 0.4, 0.35, 0.1, 0.1]` the chain scores are `[0.45, 0.40, 0.75, 0.85, 0.95]`, so `C(0.4) = [1]`, `C(0.75) = [0,1,2]`, `C(0.85) = [0,1,2,3]`. The original text's third line (`C(0.85) == [0,1,2]`) was wrong under BOTH definitions — its own mass note ("the cheapest way to 0.8") quoted a mass of 0.80 against a requested 0.85.

- [ ] **Step 1: Write the failing tests.** The point of these is that they encode *why* multiclass sets are invalid here, not just that the function returns something.

```python
"""Minimum-length contiguous ordinal intervals: nested, contiguous, and mass-ordered."""
import random

import pytest

from autorate.ordinal import interval_set, is_contiguous, score_ordinal


def test_the_interval_is_the_shortest_one_reaching_the_requested_mass():
    # R-68: re-derived for the modal-anchored family. Chain scores of this ballot are
    # [0.45, 0.40, 0.75, 0.85, 0.95], so the sublevel sets below are what the code must return.
    p = [0.05, 0.4, 0.35, 0.1, 0.1]
    assert interval_set(p, 0.4) == [1]
    assert interval_set(p, 0.75) == [0, 1, 2]
    assert interval_set(p, 0.85) == [0, 1, 2, 3]


def test_mass_ordered_multiclass_sets_are_not_contiguous_and_this_refuses_to_be_one():
    """spec 5.4's actual claim, as an assertion: 'levels 0 or 4' is not an answer.

    A k-of-m top-mass set would pick {0,1,3} for the ballot below; the ordinal family
    must return a contiguous chain around the modal level instead, even where that costs
    an extra level.
    """
    p = [0.30, 0.34, 0.02, 0.30, 0.04]
    top_mass = sorted(range(5), key=lambda i: -p[i])
    greedy = sorted(top_mass[:3])                       # what mass-ordered CP returns
    assert greedy == [0, 1, 3] and not is_contiguous(greedy)
    ours = interval_set(p, sum(p[i] for i in greedy))   # same budget, chain construction
    assert is_contiguous(ours), ours
    assert sum(p[i] for i in ours) >= sum(p[i] for i in greedy) - 1e-12, (ours, greedy)


def test_the_family_is_nested_so_split_conformal_validity_carries_over():
    """Nesting is the property §5.4's validity argument rests on, so it is asserted as a
    subset relation -- not as the disjunction this test originally carried, which passed on
    ballots where the later set displaced the earlier one entirely."""
    rng = random.Random(11)
    for _ in range(200):
        k = rng.randrange(2, 8)
        w = [rng.random() + 0.05 for _ in range(k)]
        s = sum(w)
        p = [x / s for x in w]
        prev = []
        for q in sorted({round(x, 3) for x in p} | {0.5, 0.9, 0.99}):
            C = interval_set(p, q)
            assert is_contiguous(C), (p, q, C)
            assert set(prev) <= set(C), (p, q, C, prev)
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

- [ ] **Step 2: Verify RED** (`ModuleNotFoundError: autorate.ordinal`), then **Step 3: Implement** with prefix sums: `score_ordinal` is `O(k)` once the modal index is known (chain mass = `prefix[max(a,g)+1] - prefix[min(a,g)]`), and `interval_set` is one pass over those scores. The O(k²) span enumeration this step originally prescribed belonged to the minimum-length-reach-mass definition that ruling R-68 replaced; keep enumeration only inside a test that cross-checks the closed form against brute force. `k ≤ 51` and `predict_shortlist` caps ballots, so neither shape is a performance question — say that in the comment rather than optimizing.
- [ ] **Step 4: Green**, then **Step 5: prove the guards can fail** -- plant the mass-ordered alternative (§5.4's semantically-invalid set: the smallest top-mass prefix of levels) in place of the chain, and confirm the contiguity assertions AND the nesting subset assertion both go red; restore byte-identically and record the hashes. That plant is the only way these two tests show they are guards rather than descriptions of whatever the code happens to do: under the pre-R-68 definition the nesting assertion was a disjunction that the mass-ordered family can satisfy.
- [ ] **Step 6: Commit** — `git commit -m "feat(ordinal): modal-anchored chain sets with contiguity and nesting as properties"`. The subject must name the family the code implements: "minimum-length" describes the pre-R-68 construction, and a commit message that mislabels the primitive is the first place a later reader will be misled.

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
    """Factory for synthetic ordinal decisions, in the shared helper module `tests/_records.py`.

    Corrected 2026-10-05 (ruling R-69). This docstring used to say "Plan B1 Task 5 ruled that shared
    generators live in `tests/conftest.py`" -- a future ruling cited as a present fact: there is no
    `conftest.py` in this repository, and B1 Task 5 has not run. The convention that actually holds is
    a non-test helper module imported by name (`tests/_thresholds.py` is the precedent, and the
    duplicate-owner fingerprints already depend on being able to tell a helper from a test), so a
    shared record factory goes in `tests/_records.py` and is imported the same way. A fixture-returning
    factory would be a second way to build records, and the module-scope alias B1's draft used to work
    around it (`_records = records_factory`) mutates a test file that other rounds gate on being
    byte-unchanged.
    """
    return _build_ordinal          # defined in tests/_records.py, returns list[Record]


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
