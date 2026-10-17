# B3's drift envelope, published

Written by `python3 tools/drift_envelope.py --out data/drift_envelope.json --doc docs/DRIFT.md --force`,
and re-checked by `python3 tools/drift_envelope.py --check`.

That check re-reads `src/autorate/drift.py`, re-runs every measurement below on the shipped
`weighted_quantile`, `aci_threshold` and `aci_regret_bound`, byte-compares this document
against a fresh render of the artefact, and refuses at exit 4 if the committed bytes cannot
reproduce what they publish. Exit 3 is a measured disagreement: the artefact is written
anyway, carrying both the figure the envelope states and the figure the arithmetic yielded.
Nothing here reads the corpus, so both lanes re-derive the same bytes, and this document
carries no timestamp and no machine path.

Every envelope sentence below is a copy of `drift.WEIGHTED_ENVELOPE` and
`drift.ACI_ENVELOPE`: the artefact stores those tuples verbatim and this renderer prints
them verbatim, so an edit to that prose changes this document or reddens a row -- it cannot
be quietly summarised.

## In plain words

**Mode 1 (a declared density ratio): the finite-sample statement is withdrawn.** What the
mode buys instead is a re-weighted estimate of the target-regime quantile, and no bound on
it. The shipped estimator adds the constant test-point weight named in the provenance block
below instead of the test point's own target-regime weight, which is not knowable at
calibration time; the module states the reason verbatim: "the finite-sample correction is
the EXCHANGEABLE case's: the denominator adds weight 1.0 for the test point, which is exact
for unit weights -- where the answer reproduces split_quantile value for value and flag for
flag -- and is not the weighted-conformal correction, whose denominator is sum(w) + w_{n+1}
with w_{n+1} the test point's own target-regime weight". On an exactly declared ratio it
therefore under-covers, and the Mode 1 table is that under-coverage measured against the
figure the envelope states.

**Mode 2 (an adaptive threshold): the regret statement is withdrawn.** The inequality this
module used to publish as mode 2's guarantee -- `|mean err - alpha| <= aci_regret_bound(T,
alpha, gamma)` -- is false on sequences the module's own validator accepts, and the 4 below
are among them, each with its realised long-run rate, its deviation from the target, and the
bound it exceeds. The clip that keeps the iterate inside the score range discards the update
whenever it fires, and every violation below has a fired clip beside it; a clip is necessary
for a violation, not sufficient, which is what the sweep counts say. The module states the
reason verbatim: "the mechanism, stated because a withdrawal without one is a retraction and
not a fix: the step is clipped to [0,1] every round and a clip DISCARDS the update, so when
the target rate is not reachable on the score sequence's own atoms the recursion settles
into a cycle instead of a fixed point -- period 2 at the ceiling, which is exactly the 1/2
above. Over 400 constructed sequences (seed 20261008, T=2000) no violation fired without a
clip (0 of 400), while 112 of 400 clipped sequences still held: the clip is necessary, not
sufficient, and it is observable in the trace this function returns as step.lam in (0.0,
1.0)".

## Mode 1: the declared ratio, measured

Calibration regime U[0,1], declared target density 10*s^9, `E_F0[w] = 1.0`, nominal alpha
0.05, seed 20261008, 4000 trials per size at sizes [25, 100], streams derived as
`random.Random(seed + n) per size, so the two sizes are different streams`. Coverage: closed
form under the declared target regime: P(score > q) = 1 - q^10, so this measurement carries
one Monte-Carlo layer (the calibration draws) and not a second over test points. The
envelope's own provenance names 2000 test points per trial, and this run does not sample
them, so the figure below and the figure the envelope quotes share one Monte-Carlo layer and
not two.

| n | trials | realised miscoverage | standard error | 3SE | envelope states | agrees | vacuous trials | vacuous share | vacuous 3SE | vacuous envelope states |
|---|---|---|---|---|---|---|---|---|---|---|
| 25 | 4000 | 0.140066 | 0.002435 | 0.007305 | 0.1411 | True | 1248 | 0.312000 | 0.021977 | 0.3058 |
| 100 | 4000 | 0.090745 | 0.001298 | 0.003894 | 0.0933 | True | 0 | 0.000000 | 0.000000 | not stated |

The point of these rows is the direction, not the width of the gap: the realised rate sits
*above* the nominal rate at every published size, and the 3SE column is what lets a reader
judge whether the envelope's figure and this measurement are the same measurement.

## Mode 2: the 4 constructions, and the bound each one exceeds

| sequence | rounds | realised long-run rate | deviation from alpha | regret bound | exceeds bound | clip observable | envelope states | agrees |
|---|---|---|---|---|---|---|---|---|
| every score == SCORE_CEILING | 20000 | 0.500250 | 0.450250 | 0.028778 | True | True | 0.500250 | True |
| adversarial period-2 0.99/0.01 | 100000 | 0.166740 | 0.116740 | 0.027978 | True | True | 0.166740 | True |
| constant 0.99, below the ceiling | 20000 | 0.167100 | 0.117100 | 0.028778 | True | True | 0.167100 | True |
| every score == the floor 0.0 | 20000 | 0.000000 | 0.050000 | 0.028778 | True | True | 0.000000 | True |

Beside them sit 2 controls, so the 4 rows above read as a falsification and not as a blanket
"nothing holds": there the inequality holds, and no clip fires.

| control | rounds | realised long-run rate | deviation from alpha | regret bound | exceeds bound | clip observable |
|---|---|---|---|---|---|---|
| grid control | 2000 | 0.054500 | 0.004500 | 0.037778 | False | False |
| constant 0.95 control | 2000 | 0.054500 | 0.004500 | 0.037778 | False | False |

## Mode 2: the mechanism sweep

400 constructed sequences (seed 20261008, T=2000, 8 classes cycled) at alpha=0.050000
gamma=0.050000, against a bound of 0.037778: 200 of them deviate more than the bound, 0 of
those fired without a single clipped round, and 112 clipped sequences still held. The
envelope states 0 violated-without-a-clip and 112 clipped-but-held. Both counts are re-run
by `--check`: a violation firing with no clip would make the mechanism sentence in
`ACI_ENVELOPE` wrong rather than merely unproven.

## What this artefact re-tests

- `mode1 realised miscoverage at n=25`: measured 0.140066, envelope states 0.141100, tolerance 0.007305 (the measurement's own 3 standard errors) -- agrees
- `mode1 vacuous-ceiling share at n=25`: measured 0.312000, envelope states 0.305800, tolerance 0.021977 (3 standard errors of a share over the stated trials) -- agrees
- `mode1 realised miscoverage at n=100`: measured 0.090745, envelope states 0.093300, tolerance 0.003894 (the measurement's own 3 standard errors) -- agrees
- `mode2 long-run rate: every score == SCORE_CEILING`: measured 0.500250, envelope states 0.500250, tolerance 0.000500 (the precision the envelope quotes its rates at) -- agrees
- `mode2 regret inequality violated: every score == SCORE_CEILING`: measured 0.450250, envelope states 0.028778, tolerance direction only (a direction, not a band: the deviation must EXCEED the bound) -- agrees
- `mode2 clip observable: every score == SCORE_CEILING`: measured true, envelope states true, tolerance direction only (the envelope names a fired clip beside every one of these) -- agrees
- `mode2 long-run rate: adversarial period-2 0.99/0.01`: measured 0.166740, envelope states 0.166740, tolerance 0.000500 (the precision the envelope quotes its rates at) -- agrees
- `mode2 regret inequality violated: adversarial period-2 0.99/0.01`: measured 0.116740, envelope states 0.027978, tolerance direction only (a direction, not a band: the deviation must EXCEED the bound) -- agrees
- `mode2 clip observable: adversarial period-2 0.99/0.01`: measured true, envelope states true, tolerance direction only (the envelope names a fired clip beside every one of these) -- agrees
- `mode2 long-run rate: constant 0.99, below the ceiling`: measured 0.167100, envelope states 0.167100, tolerance 0.000500 (the precision the envelope quotes its rates at) -- agrees
- `mode2 regret inequality violated: constant 0.99, below the ceiling`: measured 0.117100, envelope states 0.028778, tolerance direction only (a direction, not a band: the deviation must EXCEED the bound) -- agrees
- `mode2 clip observable: constant 0.99, below the ceiling`: measured true, envelope states true, tolerance direction only (the envelope names a fired clip beside every one of these) -- agrees
- `mode2 long-run rate: every score == the floor 0.0`: measured 0.000000, envelope states 0.000000, tolerance 0.000500 (the precision the envelope quotes its rates at) -- agrees
- `mode2 regret inequality violated: every score == the floor 0.0`: measured 0.050000, envelope states 0.028778, tolerance direction only (a direction, not a band: the deviation must EXCEED the bound) -- agrees
- `mode2 clip observable: every score == the floor 0.0`: measured true, envelope states true, tolerance direction only (the envelope names a fired clip beside every one of these) -- agrees
- `mode2 control holds: grid control`: measured 0.004500, envelope states 0.037778, tolerance direction only (a direction, not a band: the control must sit INSIDE the bound) -- agrees
- `mode2 control holds: constant 0.95 control`: measured 0.004500, envelope states 0.037778, tolerance direction only (a direction, not a band: the control must sit INSIDE the bound) -- agrees
- `mode2 sweep: no violation fired without a clip`: measured 0, envelope states 0, tolerance 0 (an exact count over the sweep's own sequences) -- agrees
- `mode2 sweep: clipped sequences that still held`: measured 112, envelope states 112, tolerance 0 (an exact count over the sweep's own sequences) -- agrees

Every figure in this section is read out of `data/drift_envelope.json`; the renderer takes
no number from anywhere else, and `--check` re-runs all of them.

## The envelope, as the module states it

`drift.WEIGHTED_ENVELOPE`, line by line:

> weighted conformal (mode 1): the density weights are DECLARED by the caller and never estimated here, so the bound is only as good as that declaration
> assumed: the declared weights are the density ratio between the calibration regime and the regime the decision runs in; nothing in this module tests that assumption
> the finite-sample correction is the EXCHANGEABLE case's: the denominator adds weight 1.0 for the test point, which is exact for unit weights -- where the answer reproduces split_quantile value for value and flag for flag -- and is not the weighted-conformal correction, whose denominator is sum(w) + w_{n+1} with w_{n+1} the test point's own target-regime weight
> so mode 1 buys a re-weighted estimate of the target-regime quantile and NO finite-sample bound: measured on an exactly declared ratio (calibration ~ U[0,1], target density 10*s^9, E_F0[w] = 1, alpha = 0.05, seed 20261008, 4000 trials x 2000 test points), realised miscoverage is 0.0933 at n=100 (3SE 0.0040) and 0.1411 at n=25 against a nominal 0.05, with 0.3058 of those n=25 trials returning the vacuous ceiling

`drift.ACI_ENVELOPE`, line by line:

> adaptive conformal inference (mode 2): what this recursion buys is a threshold that tracks the target error rate while its iterate stays inside (0,1). It is not a bound on the average miscoverage, and aci_regret_bound is not this mode's guarantee -- the inequality it used to state, |mean err - alpha| <= aci_regret_bound(T, alpha, gamma), is withdrawn below
> no per-round and no finite-sample statement, and no long-run regret statement either: on inputs _checked_round_scores accepts, at alpha=gamma=0.05 an all-1.0 sequence (this module's own SCORE_CEILING, the value its vacuous arm returns) converges to a long-run error rate of 0.500250 against a bound of 0.028778; an alternating 0.99/0.01 ordering reaches 0.166740 against 0.027978; a constant 0.99 sequence reaches 0.167100; an all-0.0 sequence reaches 0.000000 against the same formula
> the mechanism, stated because a withdrawal without one is a retraction and not a fix: the step is clipped to [0,1] every round and a clip DISCARDS the update, so when the target rate is not reachable on the score sequence's own atoms the recursion settles into a cycle instead of a fixed point -- period 2 at the ceiling, which is exactly the 1/2 above. Over 400 constructed sequences (seed 20261008, T=2000) no violation fired without a clip (0 of 400), while 112 of 400 clipped sequences still held: the clip is necessary, not sufficient, and it is observable in the trace this function returns as step.lam in (0.0, 1.0)
> stated for nonconformity scores in [0,1] and alpha in (0,0.5); a certificate built on this threshold carries this line and the trace check, not the split bound

The flag a marginal-only certificate carries, `drift.NOT_CERTIFIABLE_UNDER_DRIFT`:

> NOT_CERTIFIABLE_UNDER_DRIFT: this certificate is marginal-only -- it never conditioned on a declared drift variable, so its finite-sample bounds hold only while the calibration regime holds and a shift in the score distribution is not bounded by anything in it

## Provenance

- `alpha`: `0.05`
- `calibration_regime`: `"U[0,1]"`
- `cited_miscoverage_by_size`: `100`: `0.0933`; `25`: `0.1411`
- `expected_weight_under_calibration`: `1.0`
- `gamma`: `0.05`
- `mode1_coverage_method`: `"closed form under the declared target regime: P(score > q) = 1 - q^10, so this measurement carries one Monte-Carlo layer (the calibration draws) and not a second over test points"`
- `mode1_stream_rule`: `"random.Random(seed + n) per size, so the two sizes are different streams"`
- `mode2_rounds_by_control`: `constant 0.95 control`: `2000`; `grid control`: `2000`
- `mode2_rounds_by_sequence`: `adversarial period-2 0.99/0.01`: `100000`; `constant 0.99, below the ceiling`: `20000`; `every score == SCORE_CEILING`: `20000`; `every score == the floor 0.0`: `20000`
- `module_constants`: `DRIFT_DECLARATION_KEY`: `"drift_declaration"`; `SCORE_CEILING`: `1.0`; `TEST_POINT_WEIGHT`: `1.0`
- `produced_by`: `aci_regret_bound`: `"aci_regret_bound"`; `aci_threshold`: `"aci_threshold"`; `weighted_quantile`: `"weighted_quantile"`
- `published_decimals`: `6`
- `read_from`: `"autorate.drift"`
- `seed`: `20261008`
- `sizes`: `25`, `100`
- `target_density`: `"10*s^9"`
- `test_points_stated_by_envelope`: `2000`
- `three_se_stated_by_envelope`: `0.004`
- `trials_per_size`: `4000`
- `vacuous_share_cited_in_envelope`: `0.3058`
- `vacuous_share_stated_for_size`: `25`

## What each withdrawal replaced

- **mode1** withdraws `the finite-sample coverage statement`. Reason owner: `drift.WEIGHTED_ENVELOPE`, quoted verbatim above; the summary in this line is tools/drift_envelope.py's. What it buys instead: a re-weighted estimate of the target-regime quantile, and no bound on it.
- **mode2** withdraws `the long-run regret statement |mean err - alpha| <= aci_regret_bound(T, alpha, gamma)`. Reason owner: `drift.ACI_ENVELOPE`, quoted verbatim above; the summary in this line is tools/drift_envelope.py's. What it buys instead: a threshold that tracks the target rate while its iterate stays inside (0,1).
