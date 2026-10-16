# The G1 feasibility ceiling

Written by `python3 tools/g1_feasibility.py --out data/g1_feasibility.json --doc docs/FEASIBILITY.md --force` and re-checked by
`python -m autorate.cli verify`, which recomputes every figure below from `src/autorate/tails.py`
and the published certificates -- in both lanes, because nothing here reads the corpus -- and
refuses the artefact at exit 4 if it is absent or unreadable. The document carries no timestamp
and no machine path, so the two lanes byte-compare the same bytes.

G1 asks for at least three decision tasks certified at `autorate(alpha)` for the freeze's
published alpha. This tree scores 6 and certifies none; `data/resplit_200.json` shows no seeded split certifying for any of them. The stronger statement -- that **no automated size
certifies on this evidence base at this budget** -- lived in an untracked scratch probe until
this arm, and by this repository's own ruling (`docs/G5.md` is that ruling's artefact) a
simulation performed and deleted is not evidence. Everything below is re-derived from committed
bytes on every `verify` run.

- rubric the ceiling is measured at: alpha=0.05 beta=0.05 delta=0.05 method `aps`, seed 7
- producer: `tools/g1_feasibility.py`
- scored decision tasks read from their certificates: 6; corpora carried as refusals: 1
- tasks that certify at their published size: none

The gate's own pass condition, as the committed refusals were produced by it: a task certifies
only if `clopper_pearson_upper(errors, automated, delta) < alpha` once the bound is canonicalised
onto `certificate.PUBLISHED_DECIMALS` -- the stored precision the artefacts answer at (the last
ULP of the raw double is a platform fact, ledger R-121, so this arm never compares raw doubles).
`k_max(n)` below is the largest error count that still clears alpha at an automated size of `n`;
`k_max = null` means the size has no certifiable error count at all -- even a zero-error run
fails there -- which is a result, never a zero.

## The size ladder: what an automated set of n may get wrong and still clear alpha

| n | k_max | cp(k_max) | cp(k_max + 1) | largest certifiable error rate | required observed accuracy | cp(0 errors) | bound width | feasible @0.10 | feasible @0.25 |
|---|---|---|---|---|---|---|---|---|---|
| 100 | 1 | 0.046559811454 | 0.061619200397 | 0.01 | 0.99 | 0.029513 | 0.2716 | False | False |
| 191 | 4 | 0.04728049036 | 0.054250738409 | 0.020942 | 0.979058 | 0.015562 | 0.1965 | False | True |
| 192 | 4 | 0.047037558348 | 0.053972267026 | 0.020833 | 0.979167 | 0.015482 | 0.196 | False | True |
| 300 | 8 | 0.047600074415 | 0.0517660619 | 0.026667 | 0.973333 | 0.009936 | 0.1568 | False | True |
| 1000 | 38 | 0.049512870256 | 0.050634006795 | 0.038 | 0.962 | 0.002991 | 0.0859 | True | True |
| 2974 | 128 | 0.049671998194 | 0.050030703834 | 0.04304 | 0.95696 | 0.001007 | 0.0498 | True | True |

Sizes and where each one comes from (`size_from`, read, not remembered):

- `n = 100` -- declared by report.G1_FEASIBILITY_SIZES (the probe's scale)
- `n = 191` -- n_eval + n_cal of data/cert_jev.json
- `n = 192` -- n_eval + n_cal of data/cert_laya.json
- `n = 300` -- declared by report.G1_FEASIBILITY_SIZES (the probe's scale)
- `n = 1000` -- declared by report.G1_FEASIBILITY_SIZES (the probe's scale)
- `n = 2974` -- n_eval + n_cal of data/cert_massive_de_laya.json, data/cert_massive_en_laya.json, data/cert_massive_km_laya.json, data/cert_massive_sw_laya.json

The widths and the two bars are `inventory.py`'s own currency: `bound_width(n)` from
`tails.bound_width` at four decimals, and `feasible_at_0.10` / `feasible_at_0.25` from
`tails.n_feasible` against the inventory's declared bars -- so this ladder and
`data/inventory.md` state size in the same units and cannot quietly disagree.

## Per task

Each row reads the certificate's own bytes. The record unit is the refusal's diagnostic
`meta.closest_attempt` grid point (its counts, its stored bound); the case unit is the
certificate's own unit, R-44, taken from `meta.automated_cases` and `meta.erroneous_cases`
at `meta.at_requested_alpha`. A `k_max` from one unit is never compared against an error
count from the other, and the two denominators are different quantities on purpose: `en`
automates 628 of 1,487 records but 709 of 1,487 cases.

### `jev` (data/cert_jev.json, report.CERTS)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.02): 96 of 96 evaluated (95 calibration), 1 error; k_max at that size = 1
- cases unit (the certificate's own unit, R-44): 32 of 32 evaluated (32 calibration), 1 error; k_max at that size = null
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.048462071706 (recomputed 0.048462071706), cases 0.139849460275 (recomputed 0.139849460275) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.2772 feasible@0.10=False @0.25=False; cases bound_width=0.4802 feasible@0.10=False @0.25=False
- oracle ceiling (the largest automated size a perfect gate could certify): 96 records, 0 cases -- a number because this artefact states the automated set IS the evaluated pool

### `laya` (data/cert_laya.json, report.CERTS)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.26): 33 of 96 evaluated (96 calibration), 21 errors; k_max at that size = null
- cases unit (the certificate's own unit, R-44): 2 of 32 evaluated (32 calibration), 1 error; k_max at that size = null
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.77499233523 (recomputed 0.77499233523), cases 0.974679434481 (recomputed 0.974679434481) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.2772 feasible@0.10=False @0.25=False; cases bound_width=0.4802 feasible@0.10=False @0.25=False
- oracle ceiling: null records, null cases -- null, because meta.errors_among_automated counts the errors INSIDE the automated set, not the errors of the evaluated pool; no published field of this certificate gives the pool count, so the oracle ceiling is not computable from these bytes

### `massive/de` (data/cert_massive_de_laya.json, report.MASSIVE_CERTIFICATES)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.07): 267 of 1487 evaluated (1487 calibration), 35 errors; k_max at that size = 7
- cases unit (the certificate's own unit, R-44): 0 of 1487 evaluated (1487 calibration), 0 errors; k_max at that size = null
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.170019570979 (recomputed 0.170019570979), cases null (recomputed null) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.0704 feasible@0.10=True @0.25=True; cases bound_width=0.0704 feasible@0.10=True @0.25=True
- oracle ceiling: null records, null cases -- null, because meta.errors_among_automated counts the errors INSIDE the automated set, not the errors of the evaluated pool; no published field of this certificate gives the pool count, so the oracle ceiling is not computable from these bytes

### `massive/en` (data/cert_massive_en_laya.json, report.MASSIVE_CERTIFICATES)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.04): 628 of 1487 evaluated (1487 calibration), 30 errors; k_max at that size = 22
- cases unit (the certificate's own unit, R-44): 709 of 1487 evaluated (1487 calibration), 43 errors; k_max at that size = 25
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.064239163974 (recomputed 0.064239163974), cases 0.077514686246 (recomputed 0.077514686246) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.0704 feasible@0.10=True @0.25=True; cases bound_width=0.0704 feasible@0.10=True @0.25=True
- oracle ceiling: null records, null cases -- null, because meta.errors_among_automated counts the errors INSIDE the automated set, not the errors of the evaluated pool; no published field of this certificate gives the pool count, so the oracle ceiling is not computable from these bytes

### `massive/km` (data/cert_massive_km_laya.json, report.MASSIVE_CERTIFICATES)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.03): 7 of 1487 evaluated (1487 calibration), 2 errors; k_max at that size = null
- cases unit (the certificate's own unit, R-44): 11 of 1487 evaluated (1487 calibration), 5 errors; k_max at that size = null
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.658738563845 (recomputed 0.658738563845), cases 0.728750085923 (recomputed 0.728750085923) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.0704 feasible@0.10=True @0.25=True; cases bound_width=0.0704 feasible@0.10=True @0.25=True
- oracle ceiling: null records, null cases -- null, because meta.errors_among_automated counts the errors INSIDE the automated set, not the errors of the evaluated pool; no published field of this certificate gives the pool count, so the oracle ceiling is not computable from these bytes

### `massive/sw` (data/cert_massive_sw_laya.json, report.MASSIVE_CERTIFICATES)

- published verdict: feasible=False, reason=`empty_feasible_set` -- the certificate issued no bound
- records unit (diagnostic `meta.closest_attempt`, grid alpha 0.05): 39 of 1487 evaluated (1487 calibration), 13 errors; k_max at that size = null
- cases unit (the certificate's own unit, R-44): 39 of 1487 evaluated (1487 calibration), 13 errors; k_max at that size = null
- the diagnostic bounds reproduce from the artefact's own digits at the certificate's stored precision: records 0.47688805462 (recomputed 0.47688805462), cases 0.47688805462 (recomputed 0.47688805462) -- diagnostic values beside a refusal, NOT certificate bounds; the certificate published null
- inventory bars at this task's own sizes: records bound_width=0.0704 feasible@0.10=True @0.25=True; cases bound_width=0.0704 feasible@0.10=True @0.25=True
- oracle ceiling: null records, null cases -- null, because meta.errors_among_automated counts the errors INSIDE the automated set, not the errors of the evaluated pool; no published field of this certificate gives the pool count, so the oracle ceiling is not computable from these bytes

### `typed_decisions` (data/inventory.md.json, inventory.corpus_options)

- published verdict: `no gold labels in this offline cache`
- missing input: no gold labels in this offline cache
- this corpus is the one where the wall is the error rate rather than the bound
  width -- and it is not scored here: no gold labels, so every computed column
  is null with its missing input named above, and nothing else is claimed.

## What this ceiling is, and what it is not

- It is size arithmetic at the freeze's rubric over published counts: the same
  `build_g1_feasibility` the producer wrote these bytes with, re-run by `verify` and compared
  field by field, so a stale ceiling is drift the gate names rather than a sentence in a file.
- It is not the empirical column. G1's second column is the 200-resplit violation rate,
  owned by `data/resplit_200.json` and `docs/RESPLIT.md`; this arm publishes the closed-form
  ceiling beside it, not a re-run of the sweep.
- The bounds printed for the scored tasks are the refusals' DIAGNOSTIC values. Every one of
  these certificates published `conditional_error_bound: null` and `autorate: null` -- nothing
  certified, and no row above may be read as a certificate bound.
- A `null` column names the field that would have supplied it (`missing_pool_input`,
  `row_refusal`); this project does not impute zeros, and `data/resplit_200.json`'s
  rate-over-a-zero-denominator shape is the precedent.
- The scratch probe quoted upstream figures for `typed_decisions` (a held-out accuracy read
  from `BENCHMARKS.md`). No committed byte of this repository states them, so the artefact
  carries none of them and this document only names their exclusion. What the oracle ceiling
  needs and the certificates do not publish is the error count of the evaluated POOL; the
  published counts are the errors INSIDE the automated set, so the ceiling is a number
  exactly where the artefact states the automated set is the pool (`jev`) -- and null with
  the missing field named everywhere else.
