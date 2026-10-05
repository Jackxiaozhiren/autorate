# Plan B3 — Conditional and drifting regimes: Mondrian slices, simultaneous correction, drift envelope, and the contamination probe (G4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver spec §2's G4 -- worst-slice certification that **refuses** rather than averages -- plus the simultaneous multiple-testing correction across slices, the drift envelope flag, and the contamination-stratified certification of §9 that the technical report leads with.

**Architecture:** Group-conditional quantiles over the producer-declared slice keys, computed by the same certifiers that Plan B1/B2 built rather than beside them: a new `groups.py` supplies per-group calibration and the correction, and the certifiers gain a `groups=` parameter. Every guarantee states the condition it is valid under, in the certificate's envelope, and refuses to publish a worst-of-N number that the correction does not license.

**Tech Stack:** Python 3.12, stdlib only, offline, torch-free.

**Spec:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` §2 G4/G5, §5.3, §8.1, §8.2, §9, §10 (`n_min_violations`), §11.2, §13 weeks 9-10. The spec travels with this plan.

## Measured constraints that decide what this plan can promise

| question | measured answer (2026-10-03) | consequence |
|---|---|---|
| Which slice dimensions exist offline? | `feishu_zh` declares `family` (8 values), `mode`, `repeat`, `backend`; `language` is the constant `zh` and `option_count` the constant 4 | G4's per-language guarantee cannot be *evidenced* offline; B3 can build and property-test the machinery and certify the `family` slices, which are non-degenerate |
| Are MASSIVE's 51 language files independent samples? | **No.** All 51 share an identical `id` set: 2,974 items × 51 translations, `rows_total = 151,674` | Bonferroni across languages still controls the per-slice error rate, but the report may not describe a worst-of-51 selection as made from 51 samples. This is the same structure R-36 corrected, and it must be stated in the envelope of any per-language certificate |
| Is the ordinal `score` primitive present offline? | No `score` answers at all in the archive | per-slice ordinal certification rides on B2's synthetic generator or Plan C's real records, never on a claim about upstream data |
| Where does `in_training` actually exist, and at what granularity? | Declared by upstream `research/scripts/bench_apps.py:104,120,149` per **benchmark suite**, and 30 occurrences inside `research/results/app_benchmark_results.json`. That file has **no `cases` array and no probability lists** -- it is aggregate per suite (measured) | §9's probe is therefore a **between-suite contrast** (suites the checkpoint was tuned on vs suites it was not), never a within-benchmark stratification of held-out cases. Any Δ̂ published with this data must say so in the same sentence as its interval, and a within-suite version needs Plan C's per-case records |

## Global Constraints

- Offline, stdlib-only, no torch/model/network in the unit suite or `verify` (spec §11.5).
- The certification unit is the case; a row count is never an independent-case count (R-36, R-44). Group membership is decided **per case**, so a case with three repeats lands in one group three times and must not be counted as three observations.
- One owner per published number. Per-group `n`, per-group `qhat_g`, and the correction's `alpha/G` all come from the code that publishes them.
- A "worst of G groups" figure is only publishable with the simultaneous correction stated; without it the claim is false (spec §8.1 names this as the exact failure mode upstream's per-language tables invite).
- Exit codes 0/2/3/4; nothing escapes as rc 1. No absolute machine path in a tracked file. Never relax an assertion; no `# noqa`; label green-on-arrival tests; prove every guard can fail by planting its defect.
- `uv run --frozen`, `python3`, `-p no:randomly`, no `pytest` from PATH, exit codes not piped away. No test counts in commit messages (R-16). R-41 simulation before push.
- **Prerequisites:** B1 Task 3 (`case_count.count_outcome`), B1 Task 5 (`Reason.NO_AUTOMATION_AT_COVERAGE`, `SHAPE_VERSION`), B1 task #28 (MASSIVE basis "51/51 opened and hashed"), and B2 Tasks 1-2 (the ordinal family, so a group-conditional certificate can be produced for `score` too). Verify each against the shipped code before coding against it.

---

### Task 1: Group assignment and the per-group denominator, with leakage as the first test

**Files:**
- Create: `src/autorate/groups.py`
- Test: `tests/test_groups.py`

**Interfaces:**
- Consumes: `Record.slices`, and `case_key` — which since Plan B1 Task 3 lives in `autorate.case_count` (import `from .case_count import case_key`, not from `certify_choice`, and re-verify the symbol exists before writing code against this line: it moved once already).
- Produces: `group_key(record, groups: Sequence[str]) -> tuple` over declared keys only; `by_group(records, groups) -> dict[key -> list[Record]]`; `group_counts(...) -> dict[key -> {"cases": int, "records": int}]`.

- [ ] **Step 1: Write the failing tests.**

```python
"""Groups are declared by the producer and split by CASE, never by row."""
import pytest

from autorate.groups import by_group, group_counts

from _fixtures import choice_record     # existing test helper; see note


def test_a_case_with_three_repeats_contributes_one_case_and_three_records():
    recs = [choice_record(id="c%d-%d" % (i, r), case_id="c%d" % i, repeat=r,
                         slices={"family": "f%d" % (i % 2)})
            for i in range(4) for r in range(3)]
    counts = group_counts(recs, ("family",))
    assert counts == {"f0": {"cases": 2, "records": 6},
                      "f1": {"cases": 2, "records": 6}}, counts


def test_an_undeclared_slice_key_is_a_refusal_not_a_silent_group():
    recs = [choice_record(slices={"family": "f0"})]
    with pytest.raises(KeyError):
        by_group(recs, ("language",)), "conditioning on a key the producer never set"


def test_a_case_whose_repeats_disagree_about_a_slice_key_does_not_split_in_two():
    """The producer's own inconsistency must surface, because it would leak a case
    across two groups and quietly double-count it."""
    recs = [choice_record(id="a-0", case_id="a", slices={"family": "f0"}),
            choice_record(id="a-1", case_id="a", slices={"family": "f1"})]
    with pytest.raises(ValueError, match="case a"):
        by_group(recs, ("family",))
```

`_fixtures.choice_record`: **corrected 2026-10-05 — neither `tests/_fixtures.py` nor any `conftest.py` exists in this suite** (checked: no `conftest.py` anywhere outside `.venv`, and `tests/fixtures/` holds one data file, `feishu_sample.jsonl`). Each test module defines its own local factory — `test_certify_choice.py:16 _records`, `test_certify_threshold.py:19 _rec`, `test_gate.py:10 _rec`, `test_records.py:28 _rec`, `test_scales.py:15 _choice` — and the convention that actually holds is that a helper shared by more than one module lives in a non-test module named `_name.py` (`tests/_thresholds.py` is the existing example), which is also why the fingerprint guards can tell a shared helper from a test. So: create `tests/_record_factory.py` with the one function this task needs, import it the way `test_certify_threshold.py` imports `_thresholds`, and do not add a `conftest.py` — a fixture-returning factory would be a second way to build records, and the next reader would have to guess which one the certificate-producing tests use.

- [ ] **Step 2: Verify RED**, **Step 3: Implement** (the disagreement check is not optional: it is the only thing that turns a producer bug into a loud failure instead of a shifted denominator), **Step 4: Green**, **Step 5: commit** `feat(groups): declared-slice grouping with case-level denominators and a leakage refusal`.

---

### Task 2: Group-conditional quantiles and the simultaneous correction -- G4's engine

**Files:**
- Modify: `src/autorate/certify_choice.py`, `src/autorate/certify_score.py`
- Create: `src/autorate/correction.py`
- Test: `tests/test_mondrian.py`

**Interfaces:**
- Produces: `certify_choice(records, alpha=..., beta=..., groups=("family",)) -> GroupsCertificate`; `correction.bonferroni(alpha, n_groups) -> float`; `worst_group(certificates) -> dict` carrying the corrected level, the per-group `n`, and which groups refused and why.

- [ ] **Step 1: Write the failing tests.** Each one must be about a *claim*, not a code path.

```python
"""G4: refuse the thin slices, and never publish a worst-of-G without the correction."""
from pathlib import Path

import pytest

from autorate.certificate import N_CLAIMS
from autorate.certify_choice import certify_choice
from autorate.correction import bonferroni, worst_group

from _fixtures import choice_record


def test_a_slice_too_small_to_bound_is_refused_by_name_not_averaged_away(recs_8_families):
    cert = certify_choice(recs_8_families, alpha=0.05, beta=0.05, groups=("family",))
    assert cert.worst.autorate is None
    assert cert.n_min_violations, "the slices that could not be certified must be listed"
    assert any(v["group"] == cert.thinnest for v in cert.n_min_violations)
    assert "not certified" in cert.summary().lower() or "refused" in cert.summary().lower()


def test_the_worst_of_g_claim_is_stated_at_the_corrected_level(recs_8_families):
    cert = certify_choice(recs_8_families, alpha=0.05, beta=0.05, groups=("family",))
    g = len(cert.per_group)
    assert cert.level == pytest.approx(1.0 - g * 0.05 * N_CLAIMS, abs=1e-9), (
        "an uncorrected worst-of-%d is a false claim, spec 8.1" % g)
    assert bonferroni(0.05, 8) == 0.05 / 8


def test_within_group_exchangeability_is_the_envelope_line_and_it_is_not_proved(recs_8_families):
    cert = certify_choice(recs_8_families, alpha=0.05, beta=0.05, groups=("family",))
    assert any("within group" in line.lower() for line in cert.envelope)
    assert any("assumed" in line.lower() for line in cert.envelope), (
        "the guarantee is conditional on an assumption we do not test here")


def test_no_published_document_calls_the_51_languages_independent_samples():
    """A prose guard, not a decorative xfail: it can go red, and it is the sentence at risk.

    The corpus fact is measured (51 files, identical `id` sets, 2,974 items), so the
    framing this test forbids is not a style preference. Extend the pattern list as new
    documents are published; never narrow it to make a draft pass.
    """
    offenders = []
    for doc in ("README.md", "docs/RESULTS.md", "docs/AUDIT.md"):
        path = Path(doc)
        if not path.exists():
            continue
        text = path.read_text()
        for pat in ("51 independent samples", "51x the data", "151,674 cases",
                    "151674 independent"):
            if pat in text:
                offenders.append((doc, pat))
    assert not offenders, offenders

- [ ] **Step 2: Verify RED**, **Step 3: Implement** `GroupsCertificate` as a thin container over per-group `Certificate`s -- no duplicated statistics, and `worst_group` computed from the per-group objects so a stale hand-picked maximum cannot appear.
- [ ] **Step 4: Green**, then **Step 5: prove the correction can fail**: set the group count to 1 in a test and assert the level equals the uncorrected joint level, so the correction is shown to do work rather than decorate. Commit `feat(mondrian): group-conditional quantiles with a bonferroni-corrected worst-slice claim`.

---

### Task 3: Drift -- a declared envelope, not a claimed immunity

**Files:**
- Create: `src/autorate/drift.py`
- Test: `tests/test_drift.py`

**Interfaces:**
- Produces: `weighted_quantile(scores, weights, alpha) -> tuple[float, bool]` (weighted conformal, spec §8.2 mode 1, requires caller-declared densities); `aci_threshold(scores, alpha, gamma) -> iterator` (adaptive conformal inference, mode 2, whose guarantee is a long-run regret bound); `NOT_CERTIFIABLE_UNDER_DRIFT` as an **envelope flag** on any marginal-only certificate.

- [ ] **Step 1: Write the failing tests** -- a certificate that never conditioned on a declared drift variable carries the flag; the ACI path's test asserts the *regret* form and explicitly **not** a finite-sample statement (a test that let ACI look finite-sample would be the project's own worst failure mode); weighted quantile with unit weights reproduces the unweighted `split_quantile` exactly, which is the control that keeps the generalisation honest.
- [ ] **Step 2-4: RED, implement, Green.** **Step 5:** the envelope text is the deliverable here -- commit `feat(drift): weighted and ACI modes with the finite-sample claim withdrawn where it does not hold`.

---

### Task 4: The contamination probe -- Δ̂ with an interval, and a refusal when the strata are not real

**Files:**
- Create: `src/autorate/contamination.py`
- Test: `tests/test_contamination.py`
- Modify: `docs/RESULTS.md` via `autorate report`, `README.md`

**Interfaces:**
- Produces: `stratified(certificates_by_stratum) -> dict` with `R_in`, `R_out`, `delta_hat`, a two-sided interval, and an `interpretation` line; refuses when either stratum is too thin or when `in_training` is not genuinely declared.

- [ ] **Step 1: Write the failing tests, including the degeneracy refusal.**

```python
"""The probe is a diagnostic with an interpretation rule, not a proof of leakage."""
import pytest

from autorate.contamination import stratified


def test_a_missing_or_constant_in_training_flag_refuses_the_probe(instained_none):
    with pytest.raises(ValueError, match="in_training"):
        stratified(intrained_none)


def test_delta_hat_carries_an_interval_and_says_which_direction_is_worse(thin_in, wide_out):
    d = stratified({"in": thin_in, "out": wide_out})
    assert d["interval"][0] <= d["delta_hat"] <= d["interval"][1]
    assert "diagnostic" in d["interpretation"] and "proof" in d["interpretation"].lower()
    assert d["claim"] is False, "no threshold on delta_hat is licensed by these numbers"
```

- [ ] **Step 2: Verify RED**, **Step 3: Implement** with the two-sided interval produced from the same `clopper_pearson_upper` machinery (a two-sided interval needs both tails -- do not fake it by doubling one tail and say nothing).
- [ ] **Step 4: Green**, then **Step 5:** publish or refuse. With only the feishu archive this probe has **no real strata** (measured: nothing in the corpus declares `in_training`), so the honest deliverable is the mechanism, its refusal path, and a `docs/RESULTS.md` line saying the probe awaits Plan C's records. Writing a Δ̂ number anyway -- for instance by treating a repeat as a stratum -- is the specific thing this task exists to refuse. Commit `feat(contamination): stratified delta-hat with an interval and a real refusal when the strata are absent`.

---

### Task 5: Surface, docs, and the reproduction gate

**Files:**
- Modify: `src/autorate/cli.py`, `src/autorate/inventory.py` (the §10 `n_min_violations` amendment, ledger I-8), `README.md`, `docs/RESULTS.md`, `src/autorate/certificate.py` (`N_CLAIMS` recount if the group case changes the claim count)
- Test: `tests/test_mondrian_cli.py`, updates to `tests/test_verification_table.py` if a citation moves

- [ ] **Step 1: Write the failing tests**: `certify --groups family,option_count` end-to-end; `verify` re-derives every per-group number it publishes, including the corrected level; `n_min_violations` appears in spec §10's shape and in the artifact, and the spec section is amended in the same commit (I-8 was ruled a spec amendment, so a code change without it is a contract mismatch).
- [ ] **Step 2: Verify RED**, **Step 3: Implement**, **Step 4: run all four gates** plus the corpus-less simulation.
- [ ] **Step 5: README boundary.** G4's line must state: which slices were certified, which refused for thinness, that the language dimension is degenerate in the offline corpus, and that MASSIVE's 51 language files share their 2,974 items so a per-language worst case is 51 views of one sample.
- [ ] **Step 6: Commit, push, then read the runner's per-step conclusions** before saying anything about CI.

---

## Gates every task ends at

```bash
uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120
uv run --frozen pytest -q -p no:randomly
uv run --frozen autorate verify
AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest -q -p no:randomly
```

## Out of scope

Real per-language evidence and the within-suite version of the probe → Plan C. The guardrail-preset reproduction §5.5 owes → Plan D per ledger I-11; it is not reintroduced here.

## Unassigned spec item found by audit, with its owner

§8.3 perturbation stability -- "does the *certified decision* survive an option-order permutation", reported as automation rate conditional on agreement plus the fraction of decisions whose eligibility flips -- appeared in **no plan** when the spec surface was grepped on 2026-10-03. It belongs here, after Task 2 and before Task 5, because it consumes group-conditional certificates. Its first step must be measurement, not code: `research/eval/metamorphic.py` accepts `--out` and prints a per-language `report` (`:297`, `:332`, `:337-338`), and whether a usable per-case permutation record exists has **not** been established. If only aggregate data exists, the task's deliverable is the mechanism plus a refusal, and §8.3's numbers must not appear in the report until Plan C supplies per-case permutations.

