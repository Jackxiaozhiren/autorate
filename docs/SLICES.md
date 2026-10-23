# The language-slice certification (G4)

Written by `python3 tools/language_slices.py --out data/slices_language.json` and re-checked by
`python -m autorate.cli verify`, which recomputes this run from the committed record files named
below and refuses the artefact at exit 4 if it is absent or unreadable.

G4 asks for a behaviour: with a simultaneous correction over the slices, the **worst slice must
refuse**, and the pooled bound must not be allowed to average that refusal away. This is that run.

- group key: `language`, backend `laya`
- slices: 5 (language), claims per slice: 3
- budgets as certified: alpha=0.05 beta=0.05 delta=0.05
- corrected per slice: alpha=0.01 delta=0.01 (beta is not divided, and says so below)
- joint level: 0.85
- thinnest slice by case count: `de`
- worst slice of the joint claim: `de`, ranked on `autorate`; `autorate` is null in 5 of the 5 slices, so the field names a tie-break and not a measured worst
- the run certifies: False; any slice refused: True
- slices refused by the size floor (`n_min_violations`): 0 (none)

## Per slice

| slice | feasible | reason | n_cal | n_eval | qhat | autorate |
|---|---|---|---|---|---|---|
| de | False | empty_feasible_set | 1487 | 1487 | None | None |
| en | False | empty_feasible_set | 1487 | 1487 | None | None |
| es | False | empty_feasible_set | 1487 | 1487 | None | None |
| km | False | empty_feasible_set | 1487 | 1487 | None | None |
| sw | False | empty_feasible_set | 1487 | 1487 | None | None |

## The pooled (marginal) certificate over the same records

Published beside the slices, never in place of them: it answers a different question, and a reader
who wants the worst-case permission has to read the slice rows above.

- feasible: False, reason: empty_feasible_set
- denominator: n_cal=7435 n_eval=7435, qhat=None, autorate=None
- exact bounds: conditional=None marginal=None

## Inputs this run is a function of

| path | rows | sha256 |
|---|---|---|
| data/records_massive_de.jsonl | 2974 | 2fb97c44e8209acbeadbda9db88e7887441891636c0f1a3ee325f8fa8b42c68f |
| data/records_massive_en.jsonl | 2974 | 432d7d10f53e5d148be8811dfe4d2f2e3ce4b7b97a2727445b2fd2f6d651f8db |
| data/records_massive_es.jsonl | 2974 | 3f2b7c4e64d16cfebc03ce83c597aee1575d3c68cb7f7a02746e795657a39caf |
| data/records_massive_km.jsonl | 2974 | dd302722ed49cef88e33deb9d8673faf18d54752f224ac867686917aae057239 |
| data/records_massive_sw.jsonl | 2974 | f423fc0161fdcd0c6d85180728c59ae1ea39a2b8a31d4b75f7cde91fbf8c821c |

## Assumptions the run states about itself

- group-conditional (Mondrian): the guarantee is conditional on 'language', and exchangeability within group is ASSUMED here and not proved by this run
- worst-of-5 claim with the simultaneous correction: alpha 0.050 -> 0.010000 and delta 0.050 -> 0.010000 per slice, 3 claims per slice, so the family risk is 5 x 3 x 0.010000 = 0.1500 and the joint level is 0.8500
- beta is NOT divided and the divided budget is NOT spent: every slice's bound is tested against the uncorrected 0.050, which is the number that gates this run, and bounding each slice at 0.050 already bounds the worst at 0.050; 0.010000 is published as the counterfactual a divided budget would have cost, and no bound in this artefact is compared with it
- an UNCORRECTED worst-of-5 at delta=0.050 would claim 1 - 5 x 3 x 0.050 = 0.2500, which is a probability, but only until the census is large enough to break it: the line above is the claim this run actually makes, and it is paid for by the division this one undoes
- the pooled (marginal) certificate over these same records is published beside the slices and is NOT a substitute for them: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=7435 n_eval=7435; at coverage 0.950 no evaluation case produced a singleton set (0 empty, 7435 multi-label of 7435)
- certified on archived responses; live traffic shift is not covered

## What this does not show

The criterion names its example slice by name, and that slice is in this run: it is certified at
the divided budget like every other slice, and it refuses here rather than being quoted from
upstream's README. What the run still does not show is the second axis the criterion names. This
is a run over the one key the producer declares, so a cross of (language x option-count) is not
published here, and a table that pretended to condition on the count would be an overclaim about
a quantity that does not vary across these records. And the accuracy and mean-confidence figures
the criterion quotes beside its example are upstream's measurement on its own sample: this
artefact publishes a refusal, a denominator and a bound-or-no-bound per slice, and it is not the
owner of anyone's accuracy. The reconciliation of those two readings is `docs/ERRATA.md`'s.
