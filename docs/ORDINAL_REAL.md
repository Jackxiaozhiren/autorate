# Published ordinal guarantee over a real corpus (Plan E)

Every number in this file is emitted by `python3 tools/certify_ordinal_real.py` and re-checked by
`python -m autorate.cli verify`, which re-derives the certificate from the records file named below
and re-measures the set gate's refusal over the same rows. None of them is typed, and the document
carries no timestamp, so a re-run is byte-comparable -- in the corpus-present lane and in the
corpus-absent one alike, because nothing here reads the vendored archive.

## The population

- dataset `LocalLLaMA/typed-decisions`, config `all`, split `test`
- shard `all/test-00000-of-00001.parquet`, 222140 bytes, sha256 `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`
- scored with `convaiinnovations/laya` revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, subfolder `typed-decisions`; the `main` revision is `incomplete cache` (all five typed-decisions files are absent from the cached `main` revision), so the hub id is not used here
- fetched 2026-10-24: http 200, `ssl_verify_result` 0, verified, no bypass, no --insecure, no proxy bypass
- decisions by type: `choice` 600, `noul` 600, `score` 800
- this question is `urgency` over 4 levels (`0`, `1`, `2`, `3`), 400 decisions, 400 cases, one record per case
- records file `data/records_typed_decisions_urgency.jsonl`, sha256 `b5a6aad006b923eb409ede86df3fabb275b48389f00e785a4cfa2992b8ed842c`; the scoring export it was built from is `the scoring export is not a committed file` and is pinned by sha256 `00a17550a874b6be020590fc6089b216546117ccce5d1bafb5e25ef21129ab60` (not a committed file)

This is the first population this repository publishes an ordinal certificate over that is not
generator output: the certificate beside it (`data/cert_severity_ordinal.json`) is measured on the
synthetic population `tests/_records.build_ordinal` owns, and its own envelope says so. The two
artefacts are separate rows of separate tables because the two populations are not the same subject.

## The one-sided certificate

- artefact: `data/cert_severity_typed_decisions.json`, direction `under` (the publication names the rule, and `verify` re-derives at it rather than reading it back out of the artefact)
- verdict: **certified**
- risk target `alpha`: 0.050, tested at `delta`: 0.050, split `seed`: 7
- reported level `ahat`: 3, over a rubric of 4 levels
- records calibration/evaluation: 200/200, cases calibration/evaluation: 200/200
- denominators: 200 calibration records over 200 distinct cases: `bound`, `price_bound` and `override_bound` divide by `n_cal_cases` (the calibration split's case count); `measured_violation` divides by `n_eval_cases` (the evaluation split's case count); both are 200 in this population, so which denominator a figure uses is stated here rather than left to be inferred from two counts that happen to agree
- the certified figure is `bound` = `0.014867039232`, which is the one-sided Clopper-Pearson upper on 0 evaluation violations out of `n_eval_cases` = 200 cases, and the measured held-out violation rate printed below is `measured_violation` = 0.0 over that same denominator
- the always-report rule's cost, beside the bound: `price_bound` = `0.725019771719`, `override_bound` = `0.739194103550`
- produced under the frozen protocol: `meta.protocol_digest` = `545e104a932562fb5526564aa5b056a06fda5665cacd7c0d44d24abf15ceea49`
- what `ahat` = 3 over a 4-level rubric means: the certified rule reports the TOP level on every case and reads no ballot, so the guarantee holds because nothing can exceed the top -- `137 of 200` calibration cases have their own level replaced by it, and that is the price, not a rounding

## The multiclass set gate over these same records

- `autorate.certify_score`: verdict **NOT_CERTIFIABLE** (empty_feasible_set), `reason` = `empty_feasible_set`
- measured at `alpha` 0.050, `beta` 0.050, `delta` 0.050, `seed` 7 -- the four values the set gate consumes, recorded inside the certificate's own `meta.set_gate_refusal` so the refusal is a stored fact and `verify` re-measures it rather than restating it

The gate's own verdict, verbatim:

> NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=200 n_eval=200; at coverage 0.950 the 35 automated cases include 4 carrying a wrong automated level; the exact case-level upper bound 0.243 exceeds the budget 0.050

A set-gate refusal on this population does not discharge the criterion's negative test, and it is not a near miss toward `met`; the refusal is published because it is a result, and the sentence above it is the reason `claims.G3.status` stays where it is.

## The disclosure that travels with the scores

this checkpoint ships an illegal `choice:11+` temperature, which upstream's loader clamps to 0.5 at load time, so confidence on affected entries is not calibrated
- affected: the `choice` question type at key `11+`, one entry of the checkpoint's own temperature table; clamped to `0.5` at load time
- consequence: confidence on the affected entries is not calibrated. Confidence on the affected entries is not calibrated, so a certificate over this checkpoint's probabilities carries that limit whether or not the bound holds.

## What this does NOT move

This does not move `G3`. `claims.G3.status` stays `not_measured`, and this document does not
describe progress toward `met`.
The criterion is `>=1 ordinal guarantee that multiclass CP cannot express`, and its measurement is
the negative test: if vanilla multiclass set CP reproduces the one-sided bound, the criterion fails.
What exists here is a one-sided bound that multiclass set CP did not produce on this population,
because that gate refused -- and a refusal reproduces nothing, so it cannot answer the test either
way. The test is answered only on a population where the set gate CERTIFIES, and the corner of the
generator where that happens is not committed as records the gate re-derives; until those bytes
exist, moving the row would be the over-claim this repository exists to refuse. The row's pointer
list names this artefact as evidence of the measured half, and its status names the missing half:
those two statements are not the same claim, and the frozen note is where the difference lives.

## Verbatim summary

```
one-sided severity certificate, direction=under: P(Y > ahat(X)) <= 0.014867 at ahat=3, tested at delta=0.050 on 200 calibration cases (alpha=0.050 is the risk target, not a confidence); the price is P(Y < ahat(X)) <= 0.725020 at the same rule and the rule replaces the model's own level on <= 0.739194 of cases; measured on 200 held-out cases: 0.000000; joint level 0.85 over 3 claims at delta=0.050; n_cal=200 n_eval=200; the population the caller names: `LocalLLaMA/typed-decisions (config `all`, split `test`, file `all/test-00000-of-00001.parquet`) scored by convaiinnovations/laya@55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851, subfolder `typed-decisions``, and the construction is prior art -- Dey et al. NeurIPS 2023, Zhang et al. AAAI-26, Xu-Guo-Wei UAI 2023 (PMLR 216:2346-2355), ours being the automation rule and the one-sided statement
```

## Envelope

- exchangeability within group assumed; no group conditioning applied
- marginal certificate only - not group-conditional
- certified on the records handed in; no upstream provenance is checked here, and live traffic shift is not covered
- the population is `LocalLLaMA/typed-decisions (config `all`, split `test`, file `all/test-00000-of-00001.parquet`) scored by convaiinnovations/laya@55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851, subfolder `typed-decisions``, named by the caller and read from committed records: this gate checks no upstream provenance, so the label states where the rows came from according to the publication, not what this certificate verified
- rule: report max(modal level, ahat); the guarantee is P(Y > ahat(X)) <= alpha=0.050, measured on 200 evaluation cases as 0.000000 (0 violating), which is the empirical check G1 asks for and not the bound
- the risk target alpha=0.050 is a RISK, not a confidence: every bound here is tested at delta=0.050 on 200 calibration cases, and no grid was swept on the evaluation half
- finite-sample: bounds on CASES -- 200 calibration cases over 200 records, 200 evaluation cases over 200 records; 3 claims at delta=0.050, joint level 0.85 by the rule: 1 - n_claims * max(alpha, beta), after every slice's budgets are divided by n_groups; n_groups therefore cancels and the family-wise level is CONSTANT in n_groups, which is the Bonferroni property spec 8.1 buys rather than an oversight of it
- the price of the rule is stated beside it, not inside it: P(Y < ahat(X)) <= 0.725020 at the same ahat, and the rule replaces the model's own level on <= 0.739194 of cases; both are separate claims at the same delta, which is why they are counted in the joint level
- prior art: Dey, Merugu and Kaveri (NeurIPS 2023) and Zhang et al. (AAAI-26) own the ordinal set construction, and Xu, Guo and Wei (UAI 2023, PMLR 216:2346-2355) control two ordinal-specific losses; the delta here is the automation rule and the one-sided statement
- the certified level is the top of the rubric, so the rule reports a constant answer and reads no ballot: the guarantee is true and is a statement about this task's severity distribution, not about the model's judgement -- 137 of 200 calibration cases have their own level replaced by it

Re-produce: `python3 tools/certify_ordinal_real.py --records data/records_typed_decisions_urgency.jsonl --out data/cert_severity_typed_decisions.json --doc docs/ORDINAL_REAL.md --force`.
Re-check: `python -m autorate.cli verify`.
