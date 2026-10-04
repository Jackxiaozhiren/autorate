# Published results

Every number in this file is emitted by `python -m autorate.cli report` and
re-checked by `python -m autorate.cli verify`. None is typed, and the document
carries no timestamp so a re-run is byte-comparable.

## Corpus

- archive: upstream `research/benchmarks/feishu_zh` (MIT, Adkid-Zephyr; `results/v1/{laya,jev}/raw.jsonl`)
- unique cases: **64**, repeats [0, 1, 2], slice keys: conditional, cross_chat, knowledge, lifecycle, ownership, thread_context, untrusted_content, urgency
- upstream `audit.py` exit code: **0** (values as recorded in `data/inventory.md.json`)
- records per backend (lines are counted separately, above): laya=960, jev=959
- upstream's own scores on it (read from its stdout, not recomputed here): laya/choice = 20/64, laya/four_noul = 18/64, jev/choice = 64/64, jev/four_noul = 63/64
- provenance digests (owner: upstream `SOURCE.json`): **9/9 match**
- gaps: 5 recorded, first clause each (full text in `data/inventory.md.json`): research/results/eval_english_51_languages.json: per-case records omitted; mteb/amazon_massive_intent is not in the local HF dataset cache; the archived corpus carries no randomisation draw (u), so APS ties resolve to ...; the four `noul` asks carry no per-ask ground truth anywhere in the fixtures (a...; 1 archived choice line(s) publish probabilities that do not close to 1 within ...

## Is n big enough to certify?

The bound is computed on independent cases, not on rows: feishu's 768 archived lines are 64 unique cases; MASSIVE's per-language and pooled options both report 2974 independent rows, which is what translations of one utterance set must give; counting rows instead of cases flatters the bound. Each option's own count basis is in the table below, quoted from the inventory rather than restated here.

| corpus | n_independent | n_rows | count basis | bound width at alpha=0.05 | feasible at 0.10 |
|---|---|---|---|---|---|
| feishu_zh | 64 | - | scanned from results/v1/{laya,jev}/raw.jsonl | 0.3395 | no |
| massive_intent_per_language | 2974 | 2974 | test/de, en, sw.json.gz opened and counted | 0.0498 | yes |
| massive_intent_all_languages | 2974 | 151674 | 3 of 51 files opened; the rest counted from the repo listing, and the rows are translations of the same utterances | 0.0498 | yes |
| typed_decisions | not opened | - | dataset card size category 1K<n<10K only; no file opened | - | - |

## Certificates at coverage 0.95 (alpha=0.05), beta=0.05, seed=7

| backend | verdict | autorate (cases) | ci | conditional <= | marginal <= | refusal | mean set size | records cal/eval | cases cal/eval |
|---|---|---|---|---|---|---|---|---|---|
| laya | **NOT_CERTIFIABLE** (empty_feasible_set) | - | - | - | - | - | - | 96/96 | 32/32 |
| jev | **NOT_CERTIFIABLE** (empty_feasible_set) | - | - | - | - | - | - | 95/96 | 32/32 |

### Verbatim summaries

```
laya: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=96 n_eval=96; at coverage 0.950 the 2 automated cases include 1 carrying a wrong automated request; the exact case-level upper bound 0.975 exceeds the budget 0.050
```
```
jev: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=95 n_eval=96; at coverage 0.950 the 32 automated cases include 1 carrying a wrong automated request; the exact case-level upper bound 0.140 exceeds the budget 0.050
```

### What this does and does not establish

- Both rows refuse at alpha=beta=0.05. laya: it automates 2 of its 32 evaluation cases and 1 of those carries a wrong automated request, so the exact case-level upper bound is 0.975 -- above the 0.050 budget; even had that request been right, a zero-error run over those same 2 automated cases would still have bounded at 0.776, so this corpus cannot support a 5% claim at any error count. jev: it automates 32 of its 32 evaluation cases and 1 of those carries a wrong automated request, so the exact case-level upper bound is 0.140 -- above the 0.050 budget; even had that request been right, a zero-error run over those same 32 automated cases would still have bounded at 0.089, so this corpus cannot support a 5% claim at any error count. The record denominator is what flatters this corpus: at its own grid point alpha=0.020, jev's 96 automated records, 1 of them wrong, would bound at 0.048, inside its 0.050 budget, while at the certified alpha=0.050 its 32 automated cases, 1 of them wrong, bound at 0.140 -- and the case is the unit a bound may divide by (R-44).
- The laya row is the project's point, not its problem: on a Chinese workplace corpus where the archived audit scores its choice answers 20/64, a certificate that refuses is the correct output. A published number here would be a number about nothing.
- The evaluation halves hold 96 and 96 RECORDS over 32 and 32 distinct cases (the corpus repeats each case 3 times) and 32 cases are in common, so the pair is a case-by-case comparison on identical inputs.
- The bounds are per CASE: repeats of one case are one observation (laya's three per case carry byte-identical probability vectors, scores and gold labels, though not identical rows -- `meta`, `repeat` and `slices` differ), so 96 records are 32 cases and the denominators above say which is which. Per-slice certification, the ordinal `score` family and the `noul` budgets are Plan B, gated on a corpus with enough independent cases to bound them.
- Exchangeability is assumed within a backend and a question shape, not proven; the envelope on each certificate is the machine-readable statement of that limit.
