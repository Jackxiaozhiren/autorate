# The language-slice certification (G4)

Written by `python3 tools/language_slices.py --out data/slices_language.json` and re-checked by
`python -m autorate.cli verify`, which recomputes this run from the committed record files named
below and refuses the artefact at exit 4 if it is absent or unreadable.

G4 asks for a behaviour: with a simultaneous correction over the slices, the **worst slice must
refuse**, and the pooled bound must not be allowed to average that refusal away. This is that run.

- group key: `language`, backend `laya`
- slices: 3 (language), claims per slice: 3
- budgets as certified: alpha=0.05 beta=0.05 delta=0.05
- corrected per slice: alpha=0.016666666666666666 delta=0.016666666666666666 (beta is not divided, and says so below)
- joint level: 0.85
- worst slice named by the run: `de`
- the run certifies: False; any slice refused: True
- slices refused by the size floor: 0 (none)

## Per slice

| slice | feasible | reason | n_cal | n_eval | qhat | autorate |
|---|---|---|---|---|---|---|
| de | False | empty_feasible_set | 1487 | 1487 | None | None |
| en | False | empty_feasible_set | 1487 | 1487 | None | None |
| sw | False | empty_feasible_set | 1487 | 1487 | None | None |

## The pooled (marginal) certificate over the same records

Published beside the slices, never in place of them: it answers a different question, and a reader
who wants the worst-case permission has to read the slice rows above.

- feasible: False, reason: empty_feasible_set
- denominator: n_cal=4461 n_eval=4461, qhat=None, autorate=None
- exact bounds: conditional=None marginal=None

## Inputs this run is a function of

| path | rows | sha256 |
|---|---|---|
| data/records_massive_de.jsonl | 2974 | 2fb97c44e8209acbeadbda9db88e7887441891636c0f1a3ee325f8fa8b42c68f |
| data/records_massive_en.jsonl | 2974 | 432d7d10f53e5d148be8811dfe4d2f2e3ce4b7b97a2727445b2fd2f6d651f8db |
| data/records_massive_sw.jsonl | 2974 | f423fc0161fdcd0c6d85180728c59ae1ea39a2b8a31d4b75f7cde91fbf8c821c |

## Assumptions the run states about itself

- group-conditional (Mondrian): the guarantee is conditional on 'language', and exchangeability within group is ASSUMED here and not proved by this run
- worst-of-3 claim with the simultaneous correction: alpha 0.050 -> 0.016667 and delta 0.050 -> 0.016667 per slice, 3 claims per slice, so the family risk is 3 x 3 x 0.016667 = 0.1500 and the joint level is 0.8500
- beta is NOT divided and the divided budget is NOT spent: every slice's bound is tested against the uncorrected 0.050, which is the number that gates this run, and bounding each slice at 0.050 already bounds the worst at 0.050; 0.016667 is published as the counterfactual a divided budget would have cost, and no bound in this artefact is compared with it
- an UNCORRECTED worst-of-3 at delta=0.050 would claim 1 - 3 x 3 x 0.050 = 0.5500, which is a probability, but only until the census is large enough to break it: the line above is the claim this run actually makes, and it is paid for by the division this one undoes
- the pooled (marginal) certificate over these same records is published beside the slices and is NOT a substitute for them: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=4461 n_eval=4461; at coverage 0.950 the 850 automated cases include 63 carrying a wrong automated request; the exact case-level upper bound 0.091 exceeds the budget 0.050
- certified on archived responses; live traffic shift is not covered

## What this does not show

The criterion names a slice by example -- the one the upstream README documents as collapsed with
its own accuracy and confidence figures. That slice has no per-case rows in this tree, so its
literal row is unmeasured and the status the freeze prints for G4 says so. What is measured here is
the behaviour the criterion describes, on the slices this repository scored and committed: the
corrected worst-of-G permission refuses, the refusal is named slice by slice, and nothing in this
document averages it away.
