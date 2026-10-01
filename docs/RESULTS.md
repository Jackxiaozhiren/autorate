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

| corpus | unique n | bound width at alpha=0.05 | feasible at 0.10 |
|---|---|---|---|
| feishu_zh | 64 | 0.3395 | no |
| massive_intent_per_language | 2974 | 0.0498 | yes |
| massive_intent_all_languages | 151674 | 0.0070 | yes |
| typed_decisions | not opened | - | - |

## Certificates at coverage 0.95 (alpha=0.05), beta=0.05, seed=7

| backend | verdict | autorate | ci | conditional <= | marginal <= | refusal | mean set size | n_cal/n_eval |
|---|---|---|---|---|---|---|---|---|
| laya | **NOT_CERTIFIABLE** (empty_feasible_set) | - | - | - | - | - | - | 96/96 |
| jev | certified | 1.000 | 0.861..1.000 | 0.031 | 0.031 | 0.000 | 1.00 | 95/96 |

### Verbatim summaries

```
laya: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=96 n_eval=96; at coverage 0.950 no evaluation case produced a singleton set (0 empty, 96 multi-label of 96)
```
```
jev: at coverage 0.950 (alpha=0.050), beta=0.050: autorate 1.000 (ci 0.861..1.000), conditional error <= 0.031, marginal error <= 0.031; refusal (empty or multi-label set) 0.000; mean set size 1.00; joint level 0.85 over 3 claims at delta=0.050; n_cal=95 n_eval=96
```

### What this does and does not establish

- The jev row is a **bound**, not a precision claim. With zero errors the exact one-sided bound is `clopper_pearson_upper(0, 96, 0.05)` = 0.0307, i.e. the 0.031 published above. It is a knife-edge: the same n gives 0.0485 with one error and 0.0641 with two, so the 0.05 budget holds only while the model keeps making none.
- The laya row is the project's point, not its problem: on a Chinese workplace corpus where the archived audit scores its choice answers 20/64, a certificate that refuses is the correct output. A published number here would be a number about nothing.
- The evaluation halves hold 96 and 96 RECORDS over 55 and 53 distinct request ids (the corpus repeats each case three times), and 52 request ids are in common. So the pair is a case-by-case comparison only where they overlap; the rest is two marginal certificates on the same corpus.
- n_eval is ~96 because the corpus has 64 unique cases. Per-slice certification, the ordinal `score` family and the `noul` budgets are Plan B, gated on a corpus with enough records to bound them.
- Exchangeability is assumed within a backend and a question shape, not proven; the envelope on each certificate is the machine-readable statement of that limit.
