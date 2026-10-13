# Published ordinal guarantee (G3)

Every number in this file is emitted by `python -m autorate.cli severity` and re-checked
by `python -m autorate.cli verify`, which re-derives the certificate from the records file
named below. None of them is typed, and the document carries no timestamp, so a re-run is
byte-comparable -- in the corpus-present lane and in the corpus-absent one alike.

## The certificate

- artefact: `data/cert_severity_ordinal.json`, direction `under` (the publication names the rule, and `verify` re-derives at it rather than reading it back out of the artefact)
- certified from: `data/records_ordinal_synthetic.jsonl`
- verdict: **certified**
- risk target `alpha`: 0.050, tested at `delta`: 0.050, split `seed`: 7
- reported level `ahat`: 3, over a rubric of 5 levels
- records calibration/evaluation: 600/600, cases calibration/evaluation: 200/200
- produced under the frozen protocol: `meta.protocol_digest` = `4d06ffa482eb4ad7a5b1fc5f7d560aafcd364cbeafa9969522bd5c0ed700497c`

## Verbatim summary

```
one-sided severity certificate, direction=under: P(Y > ahat(X)) <= 0.045180 at ahat=3, tested at delta=0.050 on 200 calibration cases (alpha=0.050 is the risk target, not a confidence); the price is P(Y < ahat(X)) <= 0.686921 at the same rule and the rule replaces the model's own level on <= 0.701258 of cases; measured on 200 held-out cases: 0.005000; joint level 0.85 over 3 claims at delta=0.050; n_cal=600 n_eval=600; synthetic ordinal data with known answers (the offline archive carries no `score` answers), and the construction is prior art -- Dey et al. NeurIPS 2023, Zhang et al. AAAI-26, Xu-Guo-Wei UAI 2023 (PMLR 216:2346-2355), ours being the automation rule and the one-sided statement
```

## Envelope

- exchangeability within group assumed; no group conditioning applied
- marginal certificate only - not group-conditional
- certified on the records handed in; no upstream provenance is checked here, and live traffic shift is not covered
- the offline archive carries no `score` answers: every figure demonstrated with this gate is synthetic ordinal data with known answers
- rule: report max(modal level, ahat); the guarantee is P(Y > ahat(X)) <= alpha=0.050, measured on 200 evaluation cases as 0.005000 (1 violating), which is the empirical check G1 asks for and not the bound
- the risk target alpha=0.050 is a RISK, not a confidence: every bound here is tested at delta=0.050 on 200 calibration cases, and no grid was swept on the evaluation half
- finite-sample: bounds on CASES -- 200 calibration cases over 600 records, 200 evaluation cases over 600 records; 3 claims at delta=0.050, joint level 0.85 by the rule: 1 - n_claims * max(alpha, beta), after every slice's budgets are divided by n_groups; n_groups therefore cancels and the family-wise level is CONSTANT in n_groups, which is the Bonferroni property spec 8.1 buys rather than an oversight of it
- the price of the rule is stated beside it, not inside it: P(Y < ahat(X)) <= 0.686921 at the same ahat, and the rule replaces the model's own level on <= 0.701258 of cases; both are separate claims at the same delta, which is why they are counted in the joint level
- prior art: Dey, Merugu and Kaveri (NeurIPS 2023) and Zhang et al. (AAAI-26) own the ordinal set construction, and Xu, Guo and Wei (UAI 2023, PMLR 216:2346-2355) control two ordinal-specific losses; the delta here is the automation rule and the one-sided statement
