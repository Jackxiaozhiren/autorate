# `autorate` — Certified Automation Rates for Decision Models

**Status:** design spec, approved in concept by the author's human partner on 2026-09-29, pending written-spec review.
**Date:** 2026-09-29 · **Author:** Zhiren Xiao (`Jackxiaozhiren`) · **Working name:** `autorate` (PyPI name verified free on 2026-09-29; `ratify`, `warrant`, `certior`, `attest` are all taken)
**Tagline:** confidence is not permission.

---

## 1. Thesis

Decision models (a.k.a. System 1 models) return typed decisions — `choice` over named options, `score` on an ordinal rubric, `noul` as a probability — instead of text. The category has one unanswered question, and it is the question every deployment review asks first:

> *At an error budget of α, how much of this may run unattended?*

Nobody publishes it as a certificate. The category's own tables already quote the quantity — `laya`'s published Jev comparison row carries `coverage_at_5pct_error: 0.860` (`laya-0.3.20/research/scripts/bench_apps.py:47`, itself copied from a third-party benchmark under that file's own "NOT measured here" header) — but as an **unqualified empirical number with no guarantee attached**, and the vendor's own guidance is to pick the threshold by eye: TypeSafe describes `confidence` as "a statistic computed from the probability distribution the answer already gives you" and tells the reader to "start with conservative thresholds, test with your own data". `nibzard/decision-model-benchmark` states plainly that "confidence curves do not select a deployment threshold".

What is *not* missing is the statistics, and this design loses nothing by saying so out loud: MAPIE's risk-control track (CRC, RCPS, LTT, AA-CRC) already ships an example that finds thresholds guaranteeing, at confidence 0.9, two precisions **and an abstention rate of at most 0.2**, then picks the feasible pair that minimises abstention. The difference is scope, and the scope was opened rather than assumed on 2026-09-30: MAPIE's risk control has no multiclass mode and no ordinal family (zero occurrences of "ordinal" in its risk-control API reference), its own documentation disclaims the vector-space assumption for the clipped variant of AA-CRC that its published example uses, and what it returns is a threshold, not an automation rate that travels with the answer carrying its bound and the conditions under which the bound goes void. Even the "conditions" half is now shared rather than owned: MAPIE ships exchangeability **testing** as public API — `mapie/exchangeability_testing/` exports `FixedDatasetExchangeabilityTest`, `OnlineExchangeabilityTest`, `OnlineMartingaleTest`, `PermutationTest`, `PValuePermutationTest`, `SequentialMonteCarloTest` and `RiskMonitoring` (opened at commit `7e888f5`, 2026-09-30; its README says the feature exists "to help users verify when MAPIE can be legitimately applied") — so what this design claims is not the act of checking the assumption but carrying the checked condition inside the returned object, where it can void a specific answer. Ordinal conformal prediction is likewise a real literature rather than an empty field — at least six papers, from a 2022 medical-imaging application through UAI 2023, NeurIPS 2023, COPA 2024 and AAAI-26 to arXiv 2026, four of them with public research code, two of them already building minimum-length contiguous ordinal intervals (§5.4, §12) — none of them a maintained library, while `score` *is* an ordinal primitive. And the flagship usage instruction of a 28,750-star reference implementation (GitHub API, 2026-09-30) tells you to gate on a field its own source declares uncalibrated (§7).

The niche is also not silent about guarantees, which the first draft of this document did not know — and the concession is now read out of code rather than out of taglines. **Two** open projects in exactly this space ship a conformal abstention or auto-release rule. `Manavarya09/verdict` (Apache-2.0, 3 stars, created 2026-09-23) computes the split-conformal order statistic `min(1, ceil((n+1)(1-alpha))/n)` in `ConformalCalibrator.fit` (`src/verdict/calibration/conformal.py:45-55`), sets `abstain = len(sets) > 1` and carries `conformal_set` inside the returned `Confidence` (`core.py:Decider._answer:162-206`), then prints `automation_rate = commit.mean()` over singleton sets (`core.py:Decider.evaluate:276-309`). `FeiLiuEM/open-medical-jev` (MIT, 38 stars, created 2026-09-25) decides `auto = conf >= 1.0 - cost_ratio` by Chow's rule (`router.py:Router.route:124`) alongside a genuine `conformal_quantile` order statistic (`calibration.py:47-58`). A third project the first draft counted among them does not belong there: `rupeshpoojary9/poorjev`'s advertised "conformal abstention" is, in its source, `fit_abstention_threshold` (`src/poorjev/calibration.py:126-149`) — a sweep that keeps the largest coverage whose *realised* error is within budget **on that same set**, and the word "conformal" appears once in the package's own code — in that file's section comment "conformal-style thresholding" — against fourteen occurrences across the whole tree at `7e684e95` (the other thirteen are PRD.md ×7, README.md ×3, RESULTS.md, CLAUDE.md and a `pyproject.toml` keyword), with `ceil(`, `quantile`, `exchangeab` and `finite-sample` returning zero hits across all 54 files of the clone rather than of the twelve-file sample the first read had to work from; what it actually ships is cross-validated temperature scaling and ECE, and calibration is precisely the thing this design argues is not permission. The claim runs the other way as well: the code of the two survivors bounds **marginal set coverage** and neither bounds the error among the decisions it automates — `verdict`'s `accuracy_when_committed` and open-medical-jev's `fit_tau_for_target`, which its own docstring says is fit "on this set", are empirical, and open-medical-jev's `auto` flag keys on a two-model agreement heuristic (`synth_confidence`) while the conformal `single_option` is reported beside it and never gates it. All three are days old, tiny (3, 38 and 11 stars) and unpackaged. **The remaining delta** is therefore: the **conditional** bound `P(Ŷ ≠ Y | auto) ≤ β` carried in the returned object rather than an empirical accuracy-when-committed, a simultaneous correction across slices, a machine-readable envelope of the conditions under which the bound goes void, an ordinal one-sided certificate, and contamination stratification. That list is materially smaller than the one this section asserted on 2026-09-29, and it no longer rests on a README: the ledger rows are `verdict-automation-guarantee`, `open-medical-jev-auto-release` (both code-cited at pinned commits `76bc1fe` and `ad22e32`), `poorjev-conformal-abstention` (withdrawn after reading the code), `mapie-exchangeability-tests`. The name "verdict" is overloaded and the referent is pinned to `Manavarya09/verdict` only; `haizelabs/verdict` (348★, LLM-as-a-judge inference-time scaling), `verdict-project/verdict` (251★, approximate query processing) and the same-niche `Heman10x-NGU/openJev-verdict-2.0` (293★, no longer README-only: cloned and searched at code level at `bff28567` on 2026-09-30, it has no finite-sample machinery outside its shipped tokenizer vocabularies and its calibration figures are empirical — rows `openjev-verdict-2-refusal-reporting`, `openjev-verdict-2-confidence-channels`) are different projects and are not what this paragraph claims.

**`autorate` turns that quantity into a certificate**: a finite-sample-bounded automation rate at a stated risk level, per question type, per slice, with an explicit statement of the conditions under which the bound stops holding — carried in the returned object, not in a README.

### 1.1 What this is not (non-goals)

* Not a model, not a trainer, not a fine-tuning recipe.
* Not a leaderboard: it emits no rankings and no "best model" claim.
* Not an online serving system; it never **requires** a hosted backend (this also keeps any `laya` adapter compliant with that project's `AGENTS.md` ban on hosted dependencies). Live `/v1/systemone` endpoints are an optional L1 source; the whole v1 evidence base is offline.
* Not a general conformal-prediction library. MAPIE/TorchCP own that ground; we own one narrow contract: **decision-API responses in, automation certificates out** (§4).
* Not a claim that any particular model is safe. `NOT_CERTIFIABLE` is a first-class result (§5.5).

---

## 2. Success criteria (falsifiable, measured at week 12)

| id | criterion | measurement |
|---|---|---|
| **G1** | ≥3 decision tasks yield a certified `autorate(α=0.05)` with an upper risk bound | 200-resplit Monte-Carlo per task; report the **empirical violation rate** of the claimed bound, not just the bound |
| **G2** | The gate `laya`'s README instructs demonstrably violates its own implied error rate | at `confidence >= 0.85`, measured error among automated decisions vs the 15% that sentence implies; report the multiple by which it misses |
| **G3** | ≥1 ordinal guarantee that multiclass CP cannot express | the one-sided severity certificate (§6.4): `P(Y > â(X)) ≤ α`. If vanilla multiclass set CP reproduces it, this criterion fails |
| **G4** | Worst-slice certification refuses rather than averages | per (language × option-count) bounds with a simultaneous multiple-testing correction; must return `NOT_CERTIFIABLE` for the slices `laya` documents as collapsed (e.g. Khmer: accuracy 0.000 at mean confidence 0.952) |
| **G5** | Reproducible from a commit with no GPU, no network, no model | `autorate verify --protocol protocol.json` re-derives every published number from per-case records alone; exit code + counts printed |

If G1–G3 fail, the project is not a certification tool and §14's pivot applies.

---

## 3. System overview

Three layers. **The middle layer needs no model access at all**, which is the load-bearing design decision.

```
L1  Record      decision-API responses  ->  one flat JSONL contract        (read-only, offline)
L2  Certify     records + labels         ->  Certificate objects            (pure Python, torch-free)
L3  Act         Certificate             ->  auto | escalate | abstain       (adapter per backend)
```

**L1 input sources, all of which already exist:**
1. `laya-0.3.20/research/eval/laya_eval.py` per-case JSON — already carries `state`, `options`, `gold_index`, `pred_index`, `probability`, `p_gold`, `confidence`, `correct`, `temperature`. That *is* a conformal calibration stream, already emitted.
2. `laya-0.3.20/research/benchmarks/feishu_zh/results/v1/{laya,jev}/raw.jsonl` — 768 archived, paired, **real** responses, including `jev-1.13.0` actual API output. This is what lets v1 certify both the leading open model and the hosted market leader with **zero API spend and zero cross-border data transfer** — the two costs that otherwise sink a neutral evaluator.
3. `research/eval/metamorphic.py` option-permutation variants → certificate stability under input perturbation (§8.3).
4. Any `/v1/systemone`-compatible live response body (the protocol `laya/serve.py` implements for Jev wire compatibility).

**L2** is the math (§5–§9). **L3** in `laya` is a single `on_predict_end` hook — `laya/hooks.py` explicitly permits an end hook to rewrite the result and a start hook to `ctx.skip(...)` — so no `DecisionModel.forward` change and no public-API change.

---

## 4. The Record contract (the only public interface L1 has)

```json
{"id":"massive/en/00017","qtype":"choice","instructions":"What is the user asking for in `utterance`?","options":["a","b","c"],
 "probs":[0.90,0.06,0.04],"gold":"a",
 "slices":{"language":"en","option_count":3,"backend":"laya","checkpoint":"english","in_training":false},
 "scores":{"answer_confidence":0.90,"confidence":0.4417,"act_probability":1.0},
 "seed":13,"u":0.3712,"meta":{"temperature":0.5,"head_max_len":192}}
```

Rules: `probs` are in **presented** option order; `gold` is an option key, not an index; `u` is the randomization draw used by the set predictor and is **recorded** so every certified set is exactly reproducible; unknown `scores` keys are carried but never silently used; `slices` are declared by the producer and are the only fields `autorate` may condition on. A record missing `gold` is eligible for prediction-time gating but never for calibration — enforced, not documented.

---

## 5. Certification core

### 5.1 Common machinery
Given i.i.d. (or exchangeable) calibration records `{(x_i, y_i)}_{i=1..n}` and a nonconformity `s(x, y) ∈ [0,1]`, the split-conformal quantile is `q̂ = the ⌈(1−α)(n+1)⌉-th smallest of {s_i}`, and `C(x) = {y : s(x,y) ≤ q̂}` satisfies `P(Y ∈ C(X)) ≥ 1−α`. All guarantees below are finite-sample and distribution-free, and inherit the standard exchangeability assumption — which §9 makes an explicit, machine-readable part of every certificate.

### 5.2 `choice` → set predictor, automate on singleton
Use **APS** with recorded randomization, not LAC. The reason is situational rather than general: `laya`'s served probabilities are rounded to 4 decimals (`research/eval/README.md` reports max |Δp| = 4.98e-5 against `system_one`) and shipped temperatures sharpen logits (§7.2), so **ties are a routine occurrence, not an edge case**, and LAC's coverage at ties is brittle.

Automation rule: act iff `|C(x)| = 1`. Since a singleton `{ŷ}` containing `y` implies `ŷ = y`,
`P(Ŷ ≠ Y ∧ auto) ≤ P(Y ∉ C(X)) ≤ α` — the *marginal* risk of an automated error is bounded by α directly.

### 5.3 Marginal vs conditional: the distinction the category skips
Business asks for the **conditional** rate, `P(Ŷ ≠ Y | auto) ≤ β`, which equals (marginal risk)/(automation rate) and can be far larger than α. `autorate` reports both and never conflates them, and implements **two-way finite-sample control**: the calibration set is split, one half fixes the set size to achieve the coverage target, the other bounds the error rate among automated points, and the reported pair carries a union-bound confidence level. G1's Monte-Carlo resplitting is the empirical check that the composition is stated honestly. The second half is published work and is cited by title, authors and identifier rather than by an acronym this design could not confirm: Angelopoulos, Bates, Candès, Jordan and Lei, "Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control" (arXiv 2110.01052; v1 2021-10-03, v5 2022-09-29), whose §3.2 "Selective Classification with Accuracy Control" defines exactly this quantity — "The risk is the error conditionally on predicting", `E(T) = P(T(X) ≠ Y | T(X) ≠ ∅)` — over a thresholded rule that either returns the top-1 prediction or abstains, and controls it with "the exact binomial tail bound" computed only on the subsample that passes the threshold. **The acronym formerly carried here, "KIGEL", is gone**: it appears zero times in that paper's PDF at v1, v3 and v5, an arXiv search across all indexed fields for the string turns up no machine-learning paper at all, and the citation it was attached to was itself a conflation — "ICML 2022" is not this paper's venue (the registry lists no journal reference for it) and the author names "Fannjiang … Zrnić" belong to a different paper by the first two authors, Prediction-Powered Inference (arXiv 2301.09633). What is not in that paper, and what this section still claims, is only the composition and its reporting: coverage fixed on the first split by the APS set-size rule, the conditional error bounded on the second, both numbers plus their union-bound level returned together in one object. The two-stage select-then-control shape as such is prior art either way (Selective Conformal Risk Control, Xu, Guo & Wei, arXiv 2512.12844; §5.4, §12).

### 5.4 `score` → nested interval sets (ordinal-aware)
Multiclass set predictors are **semantically invalid** on an ordinal scale: mass-ordered sets can be non-contiguous, i.e. "urgency is either level 0 or level 4". Use the nested family `C_q(x) = the minimum-length interval of levels whose probability mass is ≥ q` (ties broken leftmost, then by recorded `u`), with nonconformity `s(x,y) = inf{q : y ∈ C_q(x)}`. Nesting gives split-conformal validity unchanged. Automate iff `l == u`. **Novelty is deliberately narrow** (§12), and after opening the prior art on 2026-09-30 it is narrower than the first draft admitted: the construction is *published and named*, not merely adjacent — Dey et al. (NeurIPS 2023) already generate contiguous ordinal sets "with guaranteed coverage and minimal cardinality", and Zhang et al. (AAAI-26) prove instance-level minimum-length ordinal intervals and ship code. Our delta is the automation decision rule, the recorded randomization, and the two-way bound; `C_q` itself is not a contribution, and neither is the select-then-control shape of §5.3, which is published as Selective Conformal Risk Control (Xu, Guo & Wei, arXiv 2512.12844).

### 5.5 `NOT_CERTIFIABLE` is a product, not an error
Returned with a reason code when no rule in the family meets the budget, or when `n` is too small for the bound to be informative. The mechanism is justified by the case Plan A Task 7 reproduces deterministically; the guardrail preset is kept below as the reason the feature was designed, labelled for what it is.

* **The anchor case is synthetic, seeded and shipped in the test suite.** Task 7's `test_a_near_uniform_task_is_refused_not_certified` builds 1200 `choice` records from a stated seed — `_records(1200, sharpness=1.0)`, gold drawn uniformly, every option's mass within 5% of its neighbours — and asserts `cert.feasible is False` with `cert.reason == "empty_feasible_set"` at `(α, β) = (0.05, 0.05)`. The same task's sharpness sweep prints `feasible=False reason=empty_feasible_set` for `sharp=1.0` while `sharp=8.0` produces a certificate with a bound, so the refusal is an observable property of one code path rather than a judgment about a particular model: a task whose probability mass is flat enough that the feasible set over the family is empty at those budgets, and the honest output is **"this task is not automatable at these budgets"**, not a suggested threshold. No model, no network, no GPU; the same seed re-derives it forever, which is why G5's `verify` can be said to reproduce a refusal.
* **Why the budgets must be imposed jointly.** Each *one-sided* budget of §6.1 is individually satisfiable — pushing τ high drives false-block to 0 and lets everything through — which is exactly why the refusal is stated over a **pair**. The refusal itself is not unprecedented: MAPIE's controller raises `ValueError("… calibration was not successful")` when no threshold pair survives (verified 2026-09-30), so the delta is the *stated* verdict with its reason code and the budget pair that made it infeasible, not the willingness to refuse at all. Reading the niche's code narrowed this further, and the narrowing is now stated per project rather than as a niche-wide negative, because a repo-wide "nothing shipped prints X" is exactly the kind of claim this task exists to remove. Five shipped artefacts were opened at whole-tree code level on 2026-09-30 — MAPIE at `7e888f5`, `Manavarya09/verdict`@`76bc1fe`, `FeiLiuEM/open-medical-jev`@`ad22e32`, `rupeshpoojary9/poorjev`@`7e684e95`, `Heman10x-NGU/openJev-verdict-2.0`@`bff28567` (rows `mapie-abstention-rate-example`, `verdict-refusal-reporting`, `open-medical-jev-refusal-reporting`, `poorjev-refusal-reporting`, `openjev-verdict-2-refusal-reporting`) — and none of them returns a **refusal as the value of a decision, naming the budget pair that made the feasible set empty**. What each does instead: MAPIE raises `ValueError("… calibration was not successful")`; `verdict` sets a boolean `abstain` on `Confidence` (`types.py:72-88`) with no reason field and refuses only as a calibration-time `ValueError` naming an n floor (`conformal.py:50`, `core.py:255`) — its `prediction_set` is documented "Never empty", so it has no infeasibility state to report; open-medical-jev returns the prose note `"recommend human review"` beside the answer (`router.py:139-140`) while `cost_ratio` and `epsilon` stay arguments and no `reason` occurs anywhere in its `src/`; `openJev-verdict-2.0` abstains by selecting the `__insufficient_evidence__` option and prints an escalation note only from an example script, against a hard-coded 0.85; and **poorjev is the one that cuts against us** — its CLI prints `selective @ risk<=0.10: coverage=0.00 (threshold 1.010)` (`cli.py:71-73`), so a shipped artefact *does* print a budget beside an infeasible result, as a calibration-summary line about a set rather than a refusal carrying a reason code. The delta is therefore the reason code and the budget pair travelling inside the returned certificate, which is smaller than the negative this section asserted on 2026-09-29 and is the last form of claim this section will make: no "nothing shipped prints …" sentence is supported by these five rows, and a sixth project not opened here could change it.
* **The guardrail preset — the author's unreproduced observation, kept as motivation only.** On 2026-09-25 the author measured, alone, in a private note and with no public artifact, that on 24 benign / 15 harmful prompts `laya`'s `harm_severity` spans 0.90–2.42 for harmful against 0.39–1.66 for benign — overlapping ranges, so no single threshold separates them — that all 24 benign prompts were blocked at the default 0.5, and that the best swept point reached recall 11/15 with 2/24 false blocks at F1 0.786 (`../laya-0.3.20-upstream-issue.md` §2 and §4; the upstream issue remains unsubmitted, re-checked as an empty result set on 2026-09-30). Its ledger row `guard-preset-overlap` is **`withdrawn`** precisely because no third party can open those numbers, and this design's own rule is that a withdrawn claim may not read as established: what the anecdote supports is *the shape of the failure* (jointly infeasible budgets, an empty feasible set, a refusal that should be printed rather than softened into a threshold), and it supports nothing beyond that. The budget pair it was quoted at — `(α_block, α_miss) = (0.05, 0.20)` — is the author's choice of budgets, not a measured infeasibility, so the reproduced version of this bullet is the synthetic one above. It may not be quoted from this repository in a report, README or PR description until a reproduction exists, which takes all three of: the fix patch applied to a clean `v0.3.20` checkout; the 39 prompts and their labels committed as per-case records; and both ranges re-derived by `autorate verify` — a Task 3 deliverable. If the reproduction does not return the recorded ranges, §13's week 7–8 gate ("guard preset returns a refusal") is the thing that changes; the numbers do not stay citable by having once been written down.
* **`score` on `laya-multilingual`.** The README calls `score` the weakest primitive (SST-5 0.372) and documents a measured position prior (#131: first-slot rate 0.017 against an order-invariant expectation of 1/3). The certificate should refuse, not publish an average.

---

## 6. One-sided certificates (the risk-control contribution)

For a monotone-in-parameter loss, conformal risk control gives `E[ℓ_λ(X,Y)] ≤ α` with `λ` chosen on calibration data. We apply it to the errors that actually cost money, and we require monotonicity as a precondition rather than assuming it away.

### 6.1 Blocking gate (`noul`, and binary reductions of `choice`)
Rule: block iff `p_harm ≥ τ`. Two losses, **each monotone in τ**, each certified separately and both reported:
* missed-harm risk `E[1{Y = 1 ∧ p_harm < τ}]` — non-decreasing in τ. Certify an upper bound α_miss.
* false-block risk `E[1{Y = 0 ∧ p_harm ≥ τ}]` — non-increasing in τ. Certify α_block.

This replaces the naive single weighted loss `c_FP·1{false block} + c_FN·1{miss}`, which is **not monotone** in τ and therefore does not satisfy the CRC precondition. Reporting two one-sided certificates is both correct and more useful: risk-control practice needs "漏放率 ≤ α" and "误拦率 ≤ α" as separate, differently-priced numbers.

### 6.2 Severity under-call (`score`) — G3
With reported level `â ∈ {0..K−1}`, loss `ℓ(a, Y) = 1{Y > a}` is monotone decreasing in `a`, so binary search over the K levels yields the smallest certified `â` with `P(Y > â(X)) ≤ α`. Read as: **"we never under-call severity by more than this, at this confidence."** Multiclass set CP cannot express this quantity at all. Over-call (`1{Y < a}`) is certified symmetrically when the deployment wants both directions bounded.

### 6.3 Tolerance band
Given `â`, certify the smallest `d` with `P(|Y − â(X)| > d) ≤ α` — "the answer is never off by more than one level". `d` indexes a monotone family, so no new machinery is required.

### 6.4 Threshold gate, for comparison
The set-gate (§5.2) and the threshold-gate (automate iff `answer_confidence ≥ λ`, risk monotone in λ) are both implemented, and every report **contrasts them on the same records**. If the simpler rule matches the certified set-gate on automation rate at equal risk, we say so rather than defaulting to the fashionable construction.

---

## 7. The confidence-semantics audit (first public artifact, and the wedge)

### 7.1 Three fields, one of which the README tells you to gate on
`laya/common.py` defines three different quantities: `answer_confidence(p,k) = max(p)` — documented as "the quantity every calibration figure in this repository is computed on" — versus `confidence_from_probs(p,k) = 1 − H(p)/log k`, documented as "**not calibrated**: it is not what temperature scaling fits and not what the reported ECE measures" (`common.py:273`, `common.py:289`). The README's "Automated Confidence Gating" section instructs `if conf >= 0.85: route_automatically(...)` on the second one. The published `LayaRouter` integration also gates on `confidence`, where measured disagreement is `p = 0.973 / answer_confidence = 0.973 / confidence = 0.819`.

### 7.2 The shipped sharpening
`common.py:307-310` documents that the fitted `choice:11+` temperature is `0.1006`, which multiplies logits ~10×, so "a 0.24 top probability is published as 0.99, so a caller gating on confidence is told a coin flip is a certainty"; the loader clamps to `[0.5, 5.0]`, and the 51-language re-run shows the clamp alone moves macro ECE 0.7331 → 0.5709 while leaving accuracy and macro-F1 identical in 51/51.

### 7.3 The audit
Run the whole pipeline three times per task, once per field, and publish three risk-coverage frontiers plus each field's certified α-vs-autorate curve. Expected outcomes, each of which is a result: `answer_confidence` certifies; `confidence` fails G2 by a reported multiple; `act_probability` (README: AUROC 0.30 against correctness, i.e. an **anti**-signal, versus `confidence` at 0.77) yields an empty feasible set and must be reported as `NOT_CERTIFIABLE`. The tool's correctness requirement here is that it **never** returns a number for a field that cannot support one.

---

## 8. Conditional and drifting regimes

### 8.1 Group-conditional (Mondrian)
Fit `q̂_g` per group `g` over the declared slice keys (`language`, `option_count`, `backend`, `in_training`). Guarantee is conditional on `G = g` and needs exchangeability **within** group. The worst-group report applies a simultaneous multiple-testing correction across groups (Bonferroni on `α`; upgrade to a step-wise procedure if the correction makes small groups uniformly uncertifiable — decided by measurement, recorded either way). Without the correction, a "worst of 51 languages" number is a false claim, and this is the exact failure mode `laya_eval`'s per-language tables invite.

### 8.2 Drift
Two modes behind one call: **weighted conformal** with declared covariate-shift densities when the caller supplies them, and an **online/ACI** mode whose guarantee is a regret-style long-run bound rather than a finite-sample one. Both are existing theory; our contribution is exposing them through the same `autorate(α)` surface for decision APIs. A `NOT_CERTIFIABLE_UNDER_DRIFT` envelope flag is set whenever a certificate is marginal-only.

### 8.3 Perturbation stability
From `metamorphic.py` records: does the *certified decision* survive an option-order permutation? `metamorphic` explicitly declines to define a pass/fail threshold ("the report deliberately defines no universal pass/fail threshold"); the certificate supplies the missing decision rule by reporting automation rate conditional on agreement, and the fraction of decisions whose automation eligibility flips under permutation.

---

## 9. Contamination stratification (methodological headline)

`bench_apps.py`'s `register(...)` already records an `in_training` flag, and the README concedes that the headline 0.766 comes from a checkpoint fine-tuned on that benchmark's own training split (base checkpoints: 0.362/0.352 against a 0.318 random and 0.461 majority baseline). Unverifiable benchmark contamination is the most-cited credibility failure in this niche.

Method: certify the **same** model on the in-training stratum and the held-out stratum separately, and publish the gap `Δ̂ = R̂_in − R̂_out` with a two-sided interval as a **contamination probe** — explicitly labelled a diagnostic with an interpretation rule, not a proof of leakage. This is statistics rather than engineering, which is why it is hard to copy, and it is the primary claim of the technical report.

---

## 10. Public API surface

```python
from autorate import certify, Gate

cert = certify(records, alpha=0.05, beta=0.01,
               groups=["language", "option_count"], score_field="answer_confidence")

cert.autorate            # 0.612  -- fraction automatable at alpha, point estimate
cert.autorate_ci         # (0.571, 0.651)  Clopper-Pearson at cert.level; lower < upper asserted
cert.risk_bound          # joint and conditional, labelled separately
cert.feasible            # True, or False + reason code
cert.envelope            # ["exchangeability within group assumed", "marginal, not group-conditional",
                         #  "no label-noise allowance", "n_g >= n_min in 48 of 51 groups"]
cert.n_min_violations    # ["option_count:11+ : n=41 < 120"]  -- which slices refused, and why

g = Gate(cert)
g.decide(record)         # {"action": "auto"|"escalate"|"abstain", "certified": true, "bound": 0.05, "why": "singleton APS set"}
```

`envelope` and `n_min_violations` are **not optional in the output shape**: any serialized certificate lacking them fails validation. That is the encoding of the author's standing "Evidence boundary" practice into a runtime artifact, and it is the difference between this and a metrics script.

CLI: `autorate certify records.jsonl --alpha 0.05 --out cert.json` · `autorate audit laya` · `autorate verify --protocol protocol.json` · `autorate compare cert_a.json cert_b.json`.

---

## 11. Testing strategy

1. **Synthetic first, with known answers.** Generators with controlled Bayes error and a closed-form or Monte-Carlo-known automation frontier. Assert empirical coverage ≈ claimed at `n ∈ {100, 500, 2000}` and that violation rates sit inside the stated bound.
2. **Structural properties.** Nestedness of `C_q`; contiguity of every ordinal interval; monotonicity of each one-sided risk in its parameter (a property test per §6, which is precisely the assumption the naive weighted loss violated); monotone dependence of automation rate on α.
3. **Negative controls that prove they fired.** A uniformly random `probs` vector must yield `NOT_CERTIFIABLE`, and the test asserts the refusal *and* its reason code, plus `start < end` on any injected-degradation comparison.
4. **Falsifiability against the pre-fix state.** The G2 test must be red against `confidence_from_probs` and green against `answer_confidence`; a test that is green on arrival is labelled as such.
5. **Offline-only unit suite** (no torch, no model, no network), mirroring the upstream convention that evaluation code stays out of `import laya`.
6. **Reproduction gate.** `autorate verify` recomputes every number in the technical report from committed records; CI runs it.

---

## 12. Novelty ledger (stated against prior art, to survive review)

| component | prior art | our delta |
|---|---|---|
| split conformal, APS, CRC, LTT (selective classification with accuracy control), Mondrian, ACI, select-then-control | all published and, in places, packaged: MAPIE ships CRC/RCPS/LTT/AA-CRC for binary, multi-label and segmentation — including an example that jointly guarantees two precisions and an abstention rate at confidence 0.9 — plus Mondrian group-conditional CP and the exchangeability-test package (`mapie-exchangeability-tests`); also TorchCP, `salesforce/online_conformal`; SCRC (arXiv 2512.12844) is the published two-stage select-then-control, and Angelopoulos, Bates, Candès, Jordan & Lei, "Learn then Test" (arXiv 2110.01052) §3.2 is the published bound on `P(T(X) ≠ Y | T(X) ≠ ∅)`; the acronym this row previously carried for that construction, "KIGEL", is dropped — it is not in the paper (§5.3) | packaging behind one decision-API contract; no theoretical claim |
| interval/nested-set CP for ordinal outputs | **opened 2026-09-30, at least six works**: NeurIPS 2023 (Dey, Merugu & Kaveri — contiguous sets with guaranteed coverage and minimal cardinality), UAI 2023 (Xu, Guo & Wei, PMLR 216:2346-2355; the earlier draft's "AISTATS 2023" was a mis-transcribed venue and no such AISTATS paper exists), COPA 2024 (Chakraborty et al., PMLR 230:120-139), AAAI-26 (Zhang et al., provably minimum-length intervals, code at `xrty/OCP`), arXiv 2606.24959 (RPS nonconformity, contiguous by construction), arXiv 2207.02238 (MICCAI 2022 application) | automation decision rule + recorded randomization + two-way finite-sample bound; **not** a new construction, and the minimum-length property in particular is published |
| automation rate published beside a distribution-free conformal guarantee, in this exact niche | **found on 2026-09-30 and read in code at pinned commits, two projects, neither in the original §17**: `Manavarya09/verdict`@`76bc1fe` (`calibration/conformal.py:ConformalCalibrator.fit` computes the `ceil((n+1)(1-alpha))/n` order statistic; `core.py:Decider._answer` sets `abstain = len(sets) > 1`; `Decider.evaluate` prints `automation_rate = commit.mean()`, and `bench/typed_decisions.py:72` refits the threshold per suite — per-slice fitting with no simultaneous correction across slices), `FeiLiuEM/open-medical-jev`@`ad22e32` (`router.py:Router.route:124` decides `auto = conf >= 1 - cost_ratio`; `calibration.py:conformal_quantile` is the standard order statistic, but the shipped `CONFORMAL_Q` is hard-coded from an in-house set). `rupeshpoojary9/poorjev` was counted here on its tagline and is **withdrawn**: its `fit_abstention_threshold` maximises coverage subject to the realised error **on the same set**, and its own comment calls the method "conformal-style thresholding" — calibration (cross-validated temperature scaling, ECE), not a finite-sample gate | the **conditional** bound `P(Ŷ ≠ Y | auto) ≤ β` instead of an empirical accuracy-when-committed; simultaneous correction across slices; the machine-readable envelope and `NOT_CERTIFIABLE` reason codes; the ordinal one-sided family; contamination stratification |
| one-sided severity certificate for a decision-API `score` | none found — **weakened on 2026-09-30**: Xu et al. (UAI 2023) already control two ordinal-specific losses under CRC — that sentence now rests on its own row, `ordinal-crc-uai2023-two-losses`, opened at the proceedings' own PDF, which names the two losses (weight-based §2.3, divergence-based §2.4) and, searched across its whole extracted text, contains no one-sided `P(Y > ŷ(X)) ≤ α` statement, so this delta survives the paper rather than resting on the withdrawn venue row; cost-controlled abstention is benchmarked at scale in arXiv 2607.27143 (row `cost-sensitive-crc-2607-27143`) | G3; the systematic search must start from those two, and G3 is void if either already states `P(Y > â(X)) ≤ α` |
| three-field confidence-semantic audit of a shipped reference implementation | none found — but the field is not empty: `jev-trust` measures per-domain ECE/Brier on shipped APIs — that now rests on its own row, `jev-trust-per-domain-calibration`, opened at the PyPI registry and at source pinned to `328b58e3`, which confirms the per-domain ECE/Brier machinery in code and equally confirms it bounds nothing (zero `conformal`/`finite-sample`/`bound` hits across the package) — and the `awesome-jev` calibration sections are populated (verified 2026-09-30) | §7; the wedge for upstream adoption, narrowed twice and now again by code: not "nobody looks at shipped confidence fields", and no longer "nobody decomposes them by field" either — `openJev-verdict-2.0` decomposes its own model's two heads in code, `verdict2/metrics.py:113-114` returning `ece_distribution` and `ece_confidence` side by side, empirically and with no bound (row `openjev-verdict-2-confidence-channels`) — the surviving claim is "nobody audits a **third-party** shipped implementation's fields and certifies each" |
| contamination-stratified certification as benchmark methodology | none found in this niche | §9; primary report claim |

Any "none found" row is a **task** (systematic search, protocol pre-registered before the search) until it is a fact. That is not a hedge added for style: on 2026-09-30 the secondary search that fed this table turned out to have **invented a venue** in row 2, **undercounted the same literature** (four papers claimed, at least six found), **asserted that no implementations exist** when four are public, and — in the row added that same day — missed two shipped conformal automation gates in this niche outright (a third project it listed there, `poorjev`, turned out to be calibration-only once its code was read). A negative in this column is a statement about the search that produced it, not about the field, which is why the remaining "none found" rows stay written as tasks.

---

## 13. Twelve-week plan, with gates

| wk | deliverable | exit gate |
|---|---|---|
| 1–2 | Record contract + L1 readers for `laya_eval` JSON and the 768 archived paired responses; split-CRC correct on synthetics | G5 skeleton passes; `verify` runs end-to-end with no model |
| 3–4 | `choice`: APS + singleton gate + two-way bound (coverage on split 1, conditional-error bound on split 2; §5.3, "Learn then Test" §3.2 is prior art for the second half) | G1 on ≥1 task; Monte-Carlo violation rate inside bound |
| 5–6 | `score`: nested interval sets + one-sided severity + tolerance band | **G3** demonstrated against multiclass CP as control |
| 7–8 | `noul` two one-sided gates + three-field audit + `NOT_CERTIFIABLE` semantics | **G2** reproduced with a measured multiple; guard preset returns a refusal |
| 9–10 | Mondrian + simultaneous correction + ACI + contamination stratification | **G4**: Khmer-class slices refused, not averaged; `Δ̂` published with interval |
| 11–12 | frozen `protocol.json`, `verify`, technical report, `laya` adapter PR, `awesome-jev` entry | **G5** on a clean export; report numbers all re-derived by the tool that emits them |

**Upstream channel, in this order:** the author's 4-finding issue and round-trip-verified patch are still **unsubmitted** (`gh search issues --author=Jackxiaozhiren repo=NandhaKishorM/laya` → `[]`, and the same query for PRs → `[]`, both re-run 2026-09-30; ledger row `laya-research-eval-contributors`). Submit the patch first as a self-contained contribution; the §7 audit and the adapter follow as a second, separate PR. The `research/eval/` lane is already occupied by four other contributors who merged within 2026-09-23…25, so we consume their harnesses rather than competing with them.

---

## 14. Risks, and what would make us stop

| risk | why it is real | mitigation | kill criterion / pivot |
|---|---|---|---|
| **Exchangeability fails in production** | a hosted decision API's traffic regime is not i.i.d.; `laya` itself documents regime-dependent calibration collapse | machine-readable `envelope`, group-conditional mode, ACI mode | none available — this is a property of the problem. Report the envelope rather than implying immunity |
| **"It's just MAPIE"** | MAPIE is mature, ships a risk-control track whose example already guarantees two precisions **and an abstention rate** jointly at confidence 0.9, and — opened in code at commit `7e888f5` on 2026-09-30 rather than in a tagline — ships exchangeability **testing** as public API: `mapie/exchangeability_testing/__init__.py` exports `FixedDatasetExchangeabilityTest`, `OnlineExchangeabilityTest`, `OnlineMartingaleTest`, `PermutationTest`, `PValuePermutationTest`, `SequentialMonteCarloTest` and `RiskMonitoring`, with the martingale machinery in `bounds.py` (`GammaExponentialMixtureBound`, `hoeffding_bound`, `conjugate_mixture_empirical_bernstein_bound`) and `RiskMonitoring`, which takes a `mapie.risk_control.risks` object and monitors it sequentially against those bounds | What actually survives verification: MAPIE's risk control needs an estimator-shaped API, has no multiclass and no ordinal mode (zero "ordinal" hits in its risk-control reference), and returns a threshold rather than a certificate that travels with the answer. Three earlier deltas are now **dropped**: "is marginal-only" (it ships Mondrian group-conditional CP), "no two-way bound" (multi-risk control with abstention exists), and — the one this pass found — "nobody tests the exchangeability assumption" (`mapie-exchangeability-tests`); the surviving version of that claim is narrower and structural: MAPIE's test is a separate object run before fitting, so the verdict is not carried on the prediction, and no shipped artifact states per answer the conditions under which its own bound goes void | if a head-to-head (§6.4 comparison harness) shows MAPIE matching on the surviving deltas — decision-API record, ordinal one-sided family, per-answer envelope that *carries* the conditions rather than testing them upstream of the call — fold into upstream and retreat to direction D |
| **Small `n` after slicing** | `score` has K ≤ 5 levels; per-group `n` shrinks the bound until it is uninformative. Independently measured on 2026-09-30 (arXiv 2607.27143): marginal CP's minority-class coverage falls to as low as 0.5% across 15 imbalanced datasets, and Mondrian recovers 61.7 percentage points on average | bound width is a first-class output; "the bound is useless here" *is* a certification result; publish per-group `n_min` | if worst-group certified autorate < 0.30 on all tasks at α = 0.05, the headline number is uninteresting → promote §7/§9 (audit + contamination) to primary |
| **Vendor overlap** | TypeSafe sells threshold routing | no hosted dependency; neutrality comes from certifying both backends on identical records | — |
| **Adoption** | 5-star repos don't get cited | upstream adapter, and a report with a DOI-ready citation block — **not** the `awesome-jev` calibration section, which the 2026-09-30 pass found to be populated rather than empty (24 entries in `cobanov/awesome-jev`, two populated sections in `yibie/awesome-jev`); and the wedge there is narrower than the draft claimed: scanning those sections for guarantee language surfaced candidates that are now split by reading their code — `verdict` and `open-medical-jev` do ship conformal abstention/auto-release rules in code, `poorjev` does not (withdrawn; calibration only), and the 293★ same-niche `openJev-verdict-2.0` appears in neither list — so the wedge is not "nobody attaches a bound" but "nobody carries a conditional bound, a per-slice correction and an envelope in the returned object" | if no third party runs `verify` by week 16, treat as methodology paper, not standard |

---

## 15. Evidence anchors (every motivating claim is re-openable)

`laya-0.3.20/laya/common.py:273,289,307-310` · `README.md:567-581,870-883,884-956` · `research/scripts/bench_apps.py:43-53,62-120` · `research/eval/README.md` (per-case fields, 4-decimal parity, #208 clamp table, #131 position-prior gates) · `research/eval/metamorphic.py` (no-universal-threshold stance) · `research/benchmarks/feishu_zh/` (768 archived paired responses; Laya 20/64 vs Jev 64/64) · `laya/hooks.py` (`PredictContext`, `skip()`, end-hook rewriting) · `laya/serve.py` (`/v1/systemone` compatibility) · `laya/integrations/langchain.py` (threshold/`confidence` semantics) · the author's `../laya-0.3.20-upstream-issue.md` and `../laya-0.3.20-fixes.patch`.

---

## 16. Deferred past v1

Cross-model threshold transfer certificates; label-noise-robust CRC; conformal sets for high-cardinality `choice` beyond `predict_shortlist`'s top-k; a hosted HTTP gateway wrapper; any GUI or dashboard; fine-tuning for calibration repair; CJK/中文 decision data (blocked on data residency, and the archived-response path covers the need for v1).

---

## 17. Sources, with verification status stated per row

Provenance is no longer a column in this section; it is a machine-checked file. `docs/VERIFICATION.md` carries one row per claim and `tests/test_verification_table.py` fails CI unless every row is `verified` (with a URL and the date the source was opened) or `withdrawn` (with a `dropped:` or `replaced:` note). The table below keeps the wording the design session wrote and records where each row landed on 2026-09-30.

| claim in this spec | ledger row | outcome on 2026-09-30 |
|---|---|---|
| artifacts the design never itemised, surfaced while opening the rows above | `mapie-risk-control-coverage`, `mapie-abstention-rate-example`, `mapie-exchangeability-tests`, `ordinal-cp-literature-size`, `awesome-jev-guarantee-scan`, `verdict-automation-guarantee`, `open-medical-jev-auto-release`, `poorjev-conformal-abstention`, `laya-vendored-tree-matches-tag` | nine new rows, and they are the expensive ones: MAPIE jointly guarantees an abstention rate **and tests exchangeability in code** (`FixedDatasetExchangeabilityTest`, `OnlineMartingaleTest`, `RiskMonitoring`), the ordinal literature is twice as large as remembered, and two shipped conformal automation gates exist in this niche — so §1's thesis and §14's mitigations were narrowed. The third gate the first pass listed (`poorjev`) was read in code on 2026-09-30 and **withdrawn**: `fit_abstention_threshold` maximises coverage against the realised error on the same set, and the only "conformal" in the package is its own comment "conformal-style thresholding" |
| `answer_confidence = max(p)` vs `confidence = 1 − H(p)/log k`, and the "not calibrated" docstring | `laya-confidence-docstrings` | verified at the `v0.3.20` tag, docstrings quoted in full |
| shipped `choice:11+` temperature 0.1006, clamp to [0.5, 5.0], "coin flip published as certainty" | `laya-shipped-temperature` | verified at `laya/common.py:306-312` |
| README instructs gating at `conf >= 0.85` | `laya-readme-gating-instruction` | verified at `README.md:567-581` |
| Khmer 0.000 accuracy @ 0.952 confidence; macro ECE 0.733; `score` weakest at SST-5 0.372; `act_probability` AUROC 0.30 vs `confidence` 0.77 | `laya-readme-collapse-table` | verified; line anchors corrected to 855 / 868 / 930 / 954 |
| clamp moves macro ECE 0.7331 → 0.5709 with accuracy/macro-F1 identical 51/51 | `laya-clamp-ece-table` | verified at `research/eval/README.md:108` |
| per-case fields include `probability`/`p_gold`/`confidence`/`correct`; 4-decimal parity max \|Δp\| 4.98e-5 | `laya-per-case-fields-parity` | verified at L69 and L267 (english parity 4.92e-5) |
| `metamorphic.py` defines no universal pass/fail threshold | `laya-metamorphic-no-threshold` | verified; the quoted sentence is in the eval README at L389, the code docstring at L281 |
| 768 archived paired Laya/Jev responses; Laya 20/64 vs Jev 64/64 | `laya-feishu-archived-pairs` | verified at `research/benchmarks/feishu_zh/README.md:24-25, 80` |
| `coverage_at_5pct_error: 0.860`, and the `in_training` register flag | `laya-bench-apps-published-row` | verified, with two corrections: the number is a **quoted third-party** Jev figure under a "NOT measured here" header, and `in_training` lives at L88+, not in the cited range |
| hooks permit end-hook result rewriting and `ctx.skip()` | `laya-hooks-rewrite-skip` | verified at `laya/hooks.py:23-46` |
| guard-preset overlap and 24/24 default blocks | `guard-preset-overlap` | **withdrawn** — the author's own single-observer measurement with no public artifact (the upstream issue is still unsubmitted). Under R-8 §5.5 keeps the example but demotes it: the mechanism's anchor is now Plan A Task 7's deterministic synthetic refusal (`reason=empty_feasible_set` on a seeded near-uniform task), the guardrail numbers are labelled as unreproduced motivation, and Task 3 must still re-derive them before any public quote |
| `research/eval/` merged by four other contributors 2026-09-23…25; author has no upstream issues/PRs | `laya-research-eval-contributors` | verified through the API: exactly four distinct non-maintainer authors in that window, three more since, and zero issues and zero PRs by the author |
| MAPIE disclaims its risk-control variant's vector-space assumption | `mapie-crc-disclaimer` | verified but **scoped**: the disclaimer is about the clipped variant of one method (AA-CRC) used in one example, and the same page cites Blot et al. as AISTATS **2025** |
| the risk-control track MAPIE ships | `mapie-risk-control-coverage`, `mapie-abstention-rate-example` | **new rows, and they narrowed §1 and §14**: MAPIE already jointly guarantees two precisions *and* an abstention rate at confidence 0.9, and ships Mondrian group-conditional CP, so "marginal-only" and "no two-way bound" are withdrawn from §14; what survives is the missing multiclass/ordinal mode and the missing per-slice certificate |
| `nibzard/decision-model-benchmark`: "confidence curves do not select a deployment threshold" | `nibzard-no-threshold` | verified verbatim at README L240-241 of a pinned commit, with the repo's weight (9 stars) stated |
| ordinal conformal prior art (AISTATS 2023, NeurIPS 2023, AAAI minimum-length, arXiv 2606.24959) | `ordinal-cp-neurips2023`, `ordinal-cp-aistats2023`, `ordinal-cp-aaai-minlen`, `ordinal-cp-2606-24959`, `ordinal-cp-literature-size` | three of four verified; **`AISTATS 2023` withdrawn — that venue does not exist for this literature** (the paper is UAI 2023, PMLR 216:2346-2355). The arXiv id flagged as possibly invented is real. §1's "roughly four papers and no implementation" is false in both halves: at least six papers, four with public code |
| Selective Conformal Risk Control (arXiv 2512.12844); cost-sensitive conformal (arXiv 2607.27143) | `selective-crc-2512-12844`, `cost-sensitive-crc-2607-27143` | both verified at the registry, and both now sit in §12's ledger: SCRC is published select-then-control prior art for §5.3, and 2607.27143 measures the minority under-coverage §8.1 assumes |
| §5.3's two-way construction, named in that section as "Calibrated Errors" with "method acronym KIGEL" | `kigel-acronym` (**withdrawn**), `two-way-bound-construction-source` (**verified**) | the acronym is **gone**, because it could not be confirmed at the primary source: `KIGEL` occurs zero times in the paper's PDF at v1, v3 and v5, an arXiv search for it returns no ML paper, "ICML 2022" is not that paper's venue (the registry carries no journal ref or DOI), and the author names attached to it are Prediction-Powered Inference's (arXiv 2301.09633). The citation now reads by title + authors + arXiv id + section — Angelopoulos, Bates, Candès, Jordan & Lei, "Learn then Test", arXiv 2110.01052, §3.2, which states the conditional-on-predicting risk and bounds it with an exact binomial tail bound. §12 row 1 and §13's week 3–4 deliverable were renamed in the same commit |
| "Just Ask Jev" median ECE 0.168 / AUROC 0.886 over 44 benchmarks (arXiv 2609.29429) | `justaskjev-ece0168` | verified with the scope corrected: both medians are over the **31** benchmarks with a Noul form (the *suite* spans 44), and 0.168 is the per-benchmark median against a 0.074 null while pooled ECE is 0.047 |
| `awesome-jev` "Evaluation and calibration" section is empty | `awesome-jev-empty-section` | **withdrawn — it is not empty.** `cobanov/awesome-jev` has 24 entries under that exact heading; `yibie/awesome-jev` has two populated calibration sections. §14's adoption wedge restated |
| `laya` star count | `laya-star-count` | resolved at the API: **28,750** on 2026-09-30; the 19,301 figure is not reproducible and §1's "~20k-star" is replaced by the dated number |
| Jev funding stage, pricing, ≤255-option cap, no on-prem | `jev-api-limits`, `jev-funding-and-deployment` | split: the 255-option cap and the per-token price are verified at the vendor docs; **funding stage and "no on-prem" are dropped** — no primary source exists for either and nothing in §1–§16 leaned on them |
| PyPI names `autorate`/`riskgate` free | `pypi-names-free` | re-verified: both endpoints still return HTTP 404 |
| the vendored tree is the published tree | `laya-vendored-tree-matches-tag` | new row: every `[local]` file's `git hash-object` equals its blob SHA at tag `v0.3.20`; the only divergence is `laya/integrations/langchain.py`, which carries the author's own unsubmitted patch and is therefore cited by no row |

**Week-1 task 0 is closed.** The gate's red state named fourteen unresolved rows; opening them produced fifteen ledger rows, eleven verified at a primary source with a URL and a date and four withdrawn (one row split in two because half of it had a vendor source and half did not). Eight further rows were added for sources the design had never itemised, and a ninth (`mapie-exchangeability-tests`) when the controller's R-7 ruling sent the competitor claims back to code. **After the R-7, R-8 and R-9 rulings the ledger stands at 38 rows: 32 `verified`, 6 `withdrawn`**, and `tests/test_verification_table.py` keeps it closed in CI. — the change from the first count is that `poorjev-conformal-abstention` moved from `verified` to `withdrawn`, `verdict-automation-guarantee` and `open-medical-jev-auto-release` stayed `verified` but now cite `path:symbol` at pinned commits instead of README anchors, and MAPIE gained a row for a capability this design does not own; R-9 then added `two-way-bound-construction-source` (verified at the paper's own PDF) and `kigel-acronym` (withdrawn — the acronym does not exist in the paper it was attributed to). A number that cannot be opened does not appear in the report, the README, or a PR description. What the pass also produced, and what the design should not forget: among those fourteen rows, **one cited a venue that does not exist** (the ordinal CRC paper is UAI 2023, not AISTATS 2023), **one called a populated section empty**, **one row of four prior-art claims was three real papers plus that one invented venue**, **one attached two medians to the wrong benchmark denominator** (31, not 44), **one business row mixed a vendor-documented API limit with two press-only facts**, and **one star count was wrong by 49%** — the API reports 28,750 where one source reported 19,301. And the search that produced the table found two shipped conformal automation gates in the same niche that §17 had never listed, while **a third "gate" it reported from a tagline did not survive reading the code** — which is the empirical base rate for why §11's tests and §15's anchors — not memory, not a search snippet, and not a repository's own description of itself — carry this project's credibility.

