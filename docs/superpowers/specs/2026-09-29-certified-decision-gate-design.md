# `autorate` — Certified Automation Rates for Decision Models

**Status:** design spec, approved in concept by the author's human partner on 2026-09-29, pending written-spec review.
**Date:** 2026-09-29 · **Author:** Zhiren Xiao (`Jackxiaozhiren`) · **Working name:** `autorate` (PyPI name verified free on 2026-09-29; `ratify`, `warrant`, `certior`, `attest` are all taken)
**Tagline:** confidence is not permission.

---

## 1. Thesis

Decision models (a.k.a. System 1 models) return typed decisions — `choice` over named options, `score` on an ordinal rubric, `noul` as a probability — instead of text. The category has one unanswered question, and it is the question every deployment review asks first:

> *At an error budget of α, how much of this may run unattended?*

Nobody can answer it. The category's own tables already quote the quantity — `laya`'s published Jev comparison row carries `coverage_at_5pct_error: 0.860` (`laya-0.3.20/research/scripts/bench_apps.py:47`) — but as an **unqualified empirical number with no guarantee attached**. `nibzard/decision-model-benchmark` states plainly that "confidence curves do not select a deployment threshold". MAPIE's own documentation disclaims the theoretical assumption behind the risk-control variant it ships. Ordinal conformal prediction has roughly four papers and no implementation, while `score` *is* an ordinal primitive. And the flagship usage instruction of a ~20k-star reference implementation tells you to gate on a field its own source declares uncalibrated (§7).

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
Business asks for the **conditional** rate, `P(Ŷ ≠ Y | auto) ≤ β`, which equals (marginal risk)/(automation rate) and can be far larger than α. `autorate` reports both and never conflates them, and implements **two-way finite-sample control** using the "Calibrated Errors" construction (Angelopoulos, Bates, Fannjiang, Jordan, Zrnić, ICML 2022; method acronym KIGEL — acronym expansion to be verified against the paper before it appears in any public text): the calibration set is split, one half fixes the set size to achieve the coverage target, the other bounds the error rate among automated points, and the reported pair carries a union-bound confidence level. G1's Monte-Carlo resplitting is the empirical check that the composition is stated honestly.

### 5.4 `score` → nested interval sets (ordinal-aware)
Multiclass set predictors are **semantically invalid** on an ordinal scale: mass-ordered sets can be non-contiguous, i.e. "urgency is either level 0 or level 4". Use the nested family `C_q(x) = the minimum-length interval of levels whose probability mass is ≥ q` (ties broken leftmost, then by recorded `u`), with nonconformity `s(x,y) = inf{q : y ∈ C_q(x)}`. Nesting gives split-conformal validity unchanged. Automate iff `l == u`. **Novelty is deliberately narrow** (§12): the interval-set construction is adjacent to published ordinal CP; our delta is the automation decision rule, the recorded randomization, and the two-way bound — not a new theorem.

### 5.5 `NOT_CERTIFIABLE` is a product, not an error
Returned with a reason code when no rule in the family meets the budget, or when `n` is too small for the bound to be informative. Two anchor cases this must reproduce:
* **The guardrail preset.** Measured on 24 benign / 15 harmful prompts, `harm_severity` for harmful content spans 0.90–2.42 and benign spans 0.39–1.66, so the ranges overlap and no single threshold separates them. Note that each *one-sided* budget of §6.1 is individually satisfiable — pushing τ high drives false-block to 0 and lets everything through — which is exactly why the refusal must be stated over **jointly** imposed budgets. At `(α_block, α_miss) = (0.05, 0.20)` the feasible set on this preset is empty, and the correct output is **"this task is not automatable at these budgets"**, not a suggested threshold. No existing artifact in this niche will say that sentence, because it is bad news; it is more informative than any number.
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

### 7.4 The unit error, measured

Bisection over `entropy_confidence` (reproduced by `tests/test_records.py::_pmax_reaching`) gives the `p_max` a single entropy threshold actually demands, per option count:

| gate | k=2 | k=4 | k=10 | k=20 | k=51 |
|---|---|---|---|---|---|
| `confidence >= 0.85` | 0.9785 | 0.9609 | 0.9427 | 0.9319 | 0.9203 |
| `confidence >= 0.50` | 0.8900 | 0.8107 | 0.7379 | 0.6990 | 0.6611 |

Two consequences, and they are why the README's example is a unit error rather than merely a loose one: the same number means a different requirement for every question shape, and **the spread widens as the threshold loosens** (0.058 points between k=2 and k=51 at 0.85, but 0.229 points at 0.50). Also corrected here against an earlier draft of this spec: a `0.93` answer over four options is `0.7616` on the entropy scale, so it does **not** clear the documented `0.85` gate; and the requirement is *stricter* at small k, not looser. Neither direction is asserted from prose — `autorate` publishes the curve.

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
| split conformal, APS, CRC, KIGEL, Mondrian, ACI | all published and, in places, packaged (MAPIE, TorchCP, `salesforce/online_conformal`) | packaging behind one decision-API contract; no theoretical claim |
| interval/nested-set CP for ordinal outputs | AISTATS 2023, NeurIPS 2023 ordinal sets, AAAI minimum-length ordinal sets, arXiv 2606.24959 | automation decision rule + recorded randomization + two-way finite-sample bound; **not** a new construction |
| one-sided severity certificate for a decision-API `score` | none found | G3; requires a systematic literature search before the claim is published |
| three-field confidence-semantic audit of a shipped reference implementation | none found | §7; the wedge for upstream adoption |
| contamination-stratified certification as benchmark methodology | none found in this niche | §9; primary report claim |

Any "none found" row is a **task** (systematic search, protocol pre-registered before the search) until it is a fact.

---

## 13. Twelve-week plan, with gates

| wk | deliverable | exit gate |
|---|---|---|
| 1–2 | Record contract + L1 readers for `laya_eval` JSON and the 768 archived paired responses; split-CRC correct on synthetics | G5 skeleton passes; `verify` runs end-to-end with no model |
| 3–4 | `choice`: APS + singleton gate + KIGEL two-way | G1 on ≥1 task; Monte-Carlo violation rate inside bound |
| 5–6 | `score`: nested interval sets + one-sided severity + tolerance band | **G3** demonstrated against multiclass CP as control |
| 7–8 | `noul` two one-sided gates + three-field audit + `NOT_CERTIFIABLE` semantics | **G2** reproduced with a measured multiple; guard preset returns a refusal |
| 9–10 | Mondrian + simultaneous correction + ACI + contamination stratification | **G4**: Khmer-class slices refused, not averaged; `Δ̂` published with interval |
| 11–12 | frozen `protocol.json`, `verify`, technical report, `laya` adapter PR, `awesome-jev` entry | **G5** on a clean export; report numbers all re-derived by the tool that emits them |

**Upstream channel, in this order:** the author's 4-finding issue and round-trip-verified patch are still **unsubmitted** (`gh search issues --author=Jackxiaozhiren repo=NandhaKishorM/laya` → `[]` as of 2026-09-29). Submit the patch first as a self-contained contribution; the §7 audit and the adapter follow as a second, separate PR. The `research/eval/` lane is already occupied by four other contributors who merged within 2026-09-23…25, so we consume their harnesses rather than competing with them.

---

## 14. Risks, and what would make us stop

| risk | why it is real | mitigation | kill criterion / pivot |
|---|---|---|---|
| **Exchangeability fails in production** | a hosted decision API's traffic regime is not i.i.d.; `laya` itself documents regime-dependent calibration collapse | machine-readable `envelope`, group-conditional mode, ACI mode | none available — this is a property of the problem. Report the envelope rather than implying immunity |
| **"It's just MAPIE"** | MAPIE is mature and does ship a risk-control track | MAPIE needs an sklearn-shaped estimator, is marginal-only, has no ordinal one-sided family, no two-way bound, no decision-API record | if a head-to-head (§6.4 comparison harness) shows MAPIE matching on all four deltas, fold into upstream and retreat to direction D |
| **Small `n` after slicing** | `score` has K ≤ 5 levels; per-group `n` shrinks the bound until it is uninformative | bound width is a first-class output; "the bound is useless here" *is* a certification result; publish per-group `n_min` | if worst-group certified autorate < 0.30 on all tasks at α = 0.05, the headline number is uninteresting → promote §7/§9 (audit + contamination) to primary |
| **Vendor overlap** | TypeSafe sells threshold routing | no hosted dependency; neutrality comes from certifying both backends on identical records | — |
| **Adoption** | 5-star repos don't get cited | upstream adapter, the empty `awesome-jev` calibration section, report with a DOI-ready citation block | if no third party runs `verify` by week 16, treat as methodology paper, not standard |

---

## 15. Evidence anchors (every motivating claim is re-openable)

`laya-0.3.20/laya/common.py:273,289,307-310` · `README.md:567-581,870-883,884-956` · `research/scripts/bench_apps.py:43-53,62-120` · `research/eval/README.md` (per-case fields, 4-decimal parity, #208 clamp table, #131 position-prior gates) · `research/eval/metamorphic.py` (no-universal-threshold stance) · `research/benchmarks/feishu_zh/` (768 archived paired responses; Laya 20/64 vs Jev 64/64) · `laya/hooks.py` (`PredictContext`, `skip()`, end-hook rewriting) · `laya/serve.py` (`/v1/systemone` compatibility) · `laya/integrations/langchain.py` (threshold/`confidence` semantics) · the author's `../laya-0.3.20-upstream-issue.md` and `../laya-0.3.20-fixes.patch`.

---

## 16. Deferred past v1

Cross-model threshold transfer certificates; label-noise-robust CRC; conformal sets for high-cardinality `choice` beyond `predict_shortlist`'s top-k; a hosted HTTP gateway wrapper; any GUI or dashboard; fine-tuning for calibration repair; CJK/中文 decision data (blocked on data residency, and the archived-response path covers the need for v1).

---

## 17. Sources, with verification status stated per row

Two provenances, deliberately kept apart: **[local]** re-read from the vendored tree during this design session; **[web]** from secondary web research, **not yet opened at the primary source**. Every `[web]` row is a week-1 task, not a fact this spec may lean on.

| claim in this spec | source | status |
|---|---|---|
| `answer_confidence = max(p)` vs `confidence = 1 − H(p)/log k`, and the "not calibrated" docstring | `laya/common.py:273,289` | **[local] verified** |
| shipped `choice:11+` temperature 0.1006, clamp to [0.5, 5.0], "coin flip published as certainty" | `laya/common.py:307-310` | **[local] verified** |
| README instructs gating at `conf >= 0.85` | `README.md:567-581` | **[local] verified** |
| Khmer 0.000 accuracy @ 0.952 confidence; macro ECE 0.733; `score` weakest at SST-5 0.372; `act_probability` AUROC 0.30 vs `confidence` 0.77 | `README.md:884-956`, `research/README.md` | **[local] verified** |
| clamp moves macro ECE 0.7331 → 0.5709 with accuracy/macro-F1 identical 51/51 | `research/eval/README.md` | **[local] verified** |
| per-case fields include `probability`/`p_gold`/`confidence`/`correct`; 4-decimal parity max \|Δp\| 4.98e-5 | `research/eval/README.md` | **[local] verified** |
| `metamorphic.py` defines no universal pass/fail threshold | `research/eval/metamorphic.py`, its README section | **[local] verified** |
| 768 archived paired Laya/Jev responses; Laya 20/64 vs Jev 64/64 | `research/benchmarks/feishu_zh/README.md` | **[local] verified** |
| `coverage_at_5pct_error: 0.860`, and the `in_training` register flag | `research/scripts/bench_apps.py:43-66` | **[local] verified** |
| hooks permit end-hook result rewriting and `ctx.skip()` | `laya/hooks.py` docstrings | **[local] verified** |
| guard-preset overlap and 24/24 default blocks | `../laya-0.3.20-upstream-issue.md` (author's own measurement, 4-decimal detail re-openable only against the archived run log) | **[local, single-observer]** — re-measure before publishing |
| `research/eval/` merged by four other contributors 2026-09-23…25; author has no upstream issues/PRs | `gh api repos/NandhaKishorM/laya/commits?path=research/eval`, `gh search issues` | **[verified via API]** |
| MAPIE disclaims its risk-control variant's vector-space assumption | MAPIE docs, Blot et al. 2025 example | **[web] unverified** |
| `nibzard/decision-model-benchmark`: "confidence curves do not select a deployment threshold" | that repo README | **[web] unverified** |
| ordinal conformal prior art (AISTATS 2023, NeurIPS 2023, AAAI minimum-length, arXiv 2606.24959) | secondary search results | **[web] unverified** — arXiv ids especially |
| Selective Conformal Risk Control (arXiv 2512.12844); cost-sensitive conformal (arXiv 2607.27143) | secondary search results | **[web] unverified** |
| "Just Ask Jev" median ECE 0.168 / AUROC 0.886 over 44 benchmarks (arXiv 2609.29429) | secondary search results | **[web] unverified** |
| `awesome-jev` "Evaluation and calibration" section is empty | secondary search results, one list contradicted by another | **[web] unverified** |
| `laya` star count | reported variously as 19,301 and ~28k across sources | **[web] contradictory** — query the API, do not quote either number |
| Jev funding stage, pricing, ≤255-option cap, no on-prem | press + TrueFoundry/Businesswire secondary coverage | **[web] unverified** |
| PyPI names `autorate`/`riskgate` free | HTTP 404 from `pypi.org/pypi/<name>/json`, 2026-09-29 | **[verified]** |

**Week-1 task 0:** every `[web]` and `[contradictory]` row above is either opened at its primary source and re-stated with a URL + date, or deleted from this spec and from any derived text. A number that cannot be opened does not appear in the report, the README, or a PR description.

