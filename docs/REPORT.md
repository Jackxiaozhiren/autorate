# autorate: technical report

One document for a reviewer to hold. It is generated: `python -m autorate.cli report --full`
writes it and `python -m autorate.cli verify` renders it again from the committed artefacts named
below and compares the bytes. No figure in it is typed into a string literal in the renderer, no
date here was computed by this run -- every date is a transcription of a committed artefact's own
date, the freeze's `frozen_at` and the claim ledger's `opened` column -- and no absolute machine
path appears, so a machine that never saw the corpus produces exactly these bytes.

- protocol described: version 1, frozen 2026-10-16, digest `358d17bd02b159e4520b9bd5651cd2d9952bbece86b98c9d1541049d5c84f5aa` (the file is `cli.PROTOCOL_JSON`)
- record contract: shape 2, primitives `choice`, `score`, `noul`
- rubric: `alpha`=0.05, `beta`=0.05, `delta`=0.05, `seed`=7, `method`=aps, `unit`=case, `n_claims`=3, `min_cal`=60, `min_eval`=60
- diagnostic grid: 29 points, 0.01 to 0.29 -- evidence only, nothing on it was certified
- artefacts this document reads: 6 set certificates, 1 ordinal one, 7 resplit tasks, 4 slice rows declared as inputs, 6 inventory gaps, 46 ledger rows of which 34 are quoted here

## What a certificate is

A benchmark answers "how good is the model". A certificate answers the question an operator can
be held to: what share of this model's decisions may run unattended while the probability that an
automated decision is wrong stays at most `beta`, given the held-out data that actually exists.
When the data cannot carry that claim the certificate says so, names the reason, and the command
exits with the not-certifiable code: a number about nothing is the one output this project
refuses to produce.

- stored shape: `autorate.certificate.Certificate`, shape version 2, 17 fields -- `feasible`, `reason`, `alpha`, `beta`, `delta`, `method`, `backend`, `qhat`, `autorate`, `autorate_ci`, `conditional_error_bound`, `marginal_error_bound`, `mean_set_size`, `n_cal`, `n_eval`, `envelope`, `meta`
- derived, never stored, because each is a pure function of a stored field: `level` = `1 - N_CLAIMS * delta` = `1 - 3 * 0.05`, and `refusal_rate` = `1 - autorate`
- the decision a certificate licenses, in the freeze's own words: singleton certified set automates; anything else escalates (an empty certified set or one carrying several labels) or abstains (a refused certificate, a record of another subject, a record of another question type) -- `gate.Gate.decide` is the owner of that behaviour
- a refusal names one of a closed set of 5 reasons (`certificate.Reason`): `empty_feasible_set`, `n_below_min`, `no_automation_at_coverage`, `no_gold_labels`, `vacuous_quantile`
- of those, the reasons this tree has actually published: `empty_feasible_set`
- a certificate cannot be constructed without an envelope, so the disclaimer survives
  serialization instead of living in a README someone has to remember to read. The 6 set artefacts carry between 2 and 2 envelope lines each, and the ordinal one carries 9.
- the ordinal certificate is a sibling shape, not a `Certificate`: it reports `ahat`=3 over 600 calibration and 600 evaluation records of the `ordinal` population, at direction `under`, and the refusal reasons it can name are its own closed set

## The mechanism

The parts, each with one owner in this tree. The report names the owner and quotes the value;
it never re-runs the arithmetic and never restates a bound, because a restated bound is a bound
with two owners and a gate that cannot see which one moved.

- **Nonconformity.** `conformal.METHODS` maps every name the certifier accepts to its score function: `aps` -> `aps_score`, `lac` -> `lac_score`. The published rubric runs `aps`, and the other name is the declared comparison arm -- it exists so that a claim about set size is measured rather than asserted, and it is not a second publication.
- **The split quantile.** `conformal.split_quantile` fixes the set size on the calibration half at the finite-sample-corrected index, and reports `vacuous_quantile` rather than clipping when that index runs past the sample. Selecting the size on the cases later held out to test it is snooping, so the published artefacts do not do it:
    - `data/cert_jev.json`: `ceil((1 - 0.05) * (95 + 1))` = 92 of 95 calibration scores, and this artefact publishes no `qhat` at all
    - `data/cert_laya.json`: `ceil((1 - 0.05) * (96 + 1))` = 93 of 96 calibration scores, and this artefact publishes no `qhat` at all
- **Clopper-Pearson.** Every error bound here is `tails.clopper_pearson_upper(k, n, delta)`, an exact one-sided binomial bound from inverting the binomial tail, and the width behind `autorate_ci` is `tails.bound_width`. The bounds themselves are quoted from the artefacts below, stored at 12 decimals by `certificate.canonicalise_bound`: the last bits of a transcendental are not the same number on every C library, and a published figure only one machine can reproduce certifies nothing.
- **The union bound.** One feasible certificate publishes 3 bounds -- the conditional error bound, the marginal error bound and the automation-rate interval -- each tested at `delta`=0.05, so its joint level is 1 - 3 * 0.05 = 0.85. A group-conditional run divides the budgets by the number of slices the data produced, and by nothing else; the rule it publishes is `correction.JOINT_LEVEL_RULE`, quoted verbatim below.

> 1 - n_claims * max(alpha, beta), after every slice's budgets are divided by n_groups; n_groups therefore cancels and the family-wise level is CONSTANT in n_groups, which is the Bonferroni property spec 8.1 buys rather than an oversight of it

G4's published run has 4 slices at `n_claims`=3, so `alpha` and `delta` become 0.0125 each, and the joint level the artefact states beside them is 0.85.

- **The unit.** `case`: the certification unit is the case, never the archive row. Each artefact states the denominator it used in its own words, and the report quotes that field rather than writing a second justification for it:
- `data/cert_jev.json`: 96 evaluation records over 32 distinct cases: the bounds use the case denominator, because repeats of one case are one observation
- `data/cert_laya.json`: 96 evaluation records over 32 distinct cases: the bounds use the case denominator, because repeats of one case are one observation
- `data/cert_massive_de_laya.json`: 1487 evaluation records over 1487 distinct cases: the bounds use the case denominator, because repeats of one case are one observation
- `data/cert_massive_en_laya.json`: 1487 evaluation records over 1487 distinct cases: the bounds use the case denominator, because repeats of one case are one observation
- `data/cert_massive_km_laya.json`: 1487 evaluation records over 1487 distinct cases: the bounds use the case denominator, because repeats of one case are one observation
- `data/cert_massive_sw_laya.json`: 1487 evaluation records over 1487 distinct cases: the bounds use the case denominator, because repeats of one case are one observation

### What this rubric does not govern

The freeze carries its own scope limitation as a field, and a report that restated the rubric
without it would be the misreading the field exists to prevent:

> The `rubric` block is the published choice rule's rubric and nothing wider: it is `certificate.PUBLISHED_RUBRIC`, which `report.certify_all` and `autorate certify` read. It does not govern every rubric in this tree. `certify_score.py` and `certify_threshold.py` still declare their own `MIN_CAL`/`MIN_EVAL`/`DIAGNOSTIC_GRID`, the signature defaults of `certify_score`, `certify_threshold` and `severity.py` still write 0.05, and `tails.ALPHA_DEFAULT` remains; those copies are pinned against this owner by `test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner` rather than deleted. `seed` here is the published split (7); the certifiers' library default (`certificate.SPLIT_SEED_DEFAULT`, 0) is a different fact and the two are deliberately not collapsed, because the split is a shuffle over sorted case keys and a seed that changes re-rolls every bound measured on it.

### The evidence base, and how big it is

The bound is computed on independent cases, not on rows, so the count a reader divides by is the
`n_independent` column below -- quoted from the inventory `verify` polices, with each option's
own recorded basis beside it rather than a paraphrase of it.

| corpus option | unit | n_independent | n_rows | count basis |
|---|---|---|---|---|
| `feishu_zh` | unique labelled cases, each answered twice per backend over 3 repeats | 64 | - | scanned from results/v1/{laya,jev}/raw.jsonl |
| `massive_intent_per_language` | labelled decision rows (one utterance, one intent) | 2974 | 2974 | each of the data/massive_provenance.json pinned test shards opened and counted, 2974 rows per shard |
| `massive_intent_all_languages` | (language, utterance) pairs -- NOT independent cases | 2974 | 151674 | 51 of 51 pinned shards opened, hashed and row-counted on 2026-10-06 at revision 940fd47a81eaa7f2cc7b129674d945d618ac38c2 |
| `typed_decisions` | labelled decisions | not opened | - | dataset card size category 1K<n<10K only |

The archived corpus behind the first pair holds 64 unique cases, repeated 0, 1, 2, over 8 slice keys; 768 archive lines were read to build it, and 9 provenance digests and 6 recorded gaps travel with it.

## The five gates, as the freeze states them

One owner for this list: `protocol.json`'s `claims` array, in the order the emitter writes it.
The statuses below are properties of the same document `verify` enforces, so a status that moves
in the freeze moves here and nothing else can disagree with it. The ids are the criteria spec §2
names: `G1`, `G2`, `G3`, `G4`, `G5`.

### G1 -- `not_certifiable`

- criterion: ≥3 decision tasks yield a certified `autorate(α=0.05)` with an upper risk bound
- measurement: 200-resplit Monte-Carlo per task; report the empirical violation rate of the claimed bound, not just the bound
- artefacts: 6 -- `data/cert_jev.json`, `data/cert_laya.json`, `data/cert_massive_de_laya.json`, `data/cert_massive_en_laya.json`, `data/cert_massive_km_laya.json`, `data/cert_massive_sw_laya.json`
- `certified_tasks`: 0
- `published_certificates`: 6
- `refusal_reasons`: `empty_feasible_set`
- note: every certificate this tree publishes refuses, so G1's certified task count is zero and the criterion is not met. The refusals are the artefacts named above, and `verify` re-derives them rather than transcribing them. The 200-resplit measurement the criterion's second column names is now published -- `tools/resplit_experiment.py` is its producer, `data/resplit_200.json` and `docs/RESPLIT.md` its record, and `verify` compares 37 quantities the artefact asserts about itself plus its rubric against this freeze -- and what it shows is a refusal pattern: all six decision tasks certify in 0 of 200 splits, so their violation rate is published as undefined over a zero denominator rather than imputed as 0.000, and the only rate in the table belongs to a synthetic control that tests the machinery and is labelled as such. Published beside it is the ceiling itself: `tools/g1_feasibility.py` writes `data/g1_feasibility.json` and `docs/FEASIBILITY.md`, `verify` recomputes every figure in both lanes from `src/autorate/tails.py` and the published certificates, and what the table states is how wide the bound is at each pool size this checkout can actually build and what error rate would therefore be certifiable there -- which is why this row prints `not_certifiable` as a measured claim about the evidence rather than as an absence of an answer. Spec §14 anticipated exactly this shape of result ("bound width is a first-class output; 'the bound is useless here' *is* a certification result"), and the same section's kill criterion for this criterion has fired: no real task certifies at the published alpha, so the headline this project publishes is the audit multiple G2 measures and the worst-slice refusal G4 names, not a certified automation rate. Nothing in this row licenses reading G1 as met.

### G2 -- `measured_not_bounded`

- criterion: The gate `laya`'s README instructs demonstrably violates its own implied error rate
- measurement: at `confidence >= 0.85`, measured error among automated decisions vs the 15% that sentence implies; report the multiple by which it misses
- artefacts: 1 -- `docs/AUDIT.md`
- note: measured, and re-derived by `autorate verify` as document bytes: on `laya` the instruction's own `confidence` row automates 2 of 64 cases with 1 wrong, so the measured error is 0.50 against the 0.15 the sentence implies (3.33x). The criterion asks for a demonstration, and the exact one-sided Clopper-Pearson bound on those 2 cases is 0.9747 -- above the implied rate -- so this corpus does not BOUND the gate it is asked to certify, which is what `NOT_INFORMATIVE` prints beside the row. The point estimate misses upward; the bound says the sample cannot carry the claim.

### G3 -- `not_measured`

- criterion: ≥1 ordinal guarantee that multiclass CP cannot express
- measurement: the one-sided severity certificate (§6.4): `P(Y > â(X)) ≤ α`. If vanilla multiclass set CP reproduces it, this criterion fails
- artefacts: 3 -- `data/cert_severity_ordinal.json`, `docs/SEVERITY.md`, `tests/test_g3_contrast.py`
- note: the ordinal certificate is published and re-derived (`autorate severity`, `data/cert_severity_ordinal.json`, `docs/SEVERITY.md`, 19 comparisons in `verify`), and the contrast the criterion asks for has now been counted -- and it went against this row's original wording. On the population where this repository's ordinal SET gate certifies (`shift = 0`, `error_rate = 0`; 4 of the 64 knob cells searched), the interval top is above the gold level in none of the 600 evaluated records (200 cases), so `P(Y > hi(X)) = 0` lies inside that certificate's own published marginal bound of 0.014867: a coverage claim over ordered intervals yields a one-sided bound by itself. The bare sentence 'multiclass CP cannot express one' is therefore false for the ordinal interval construction, and what survives is narrower -- the set certificate publishes no named reporting rule, no price and no override rate, and its certified set is empty on 36 evaluated records, so the reader who wants the one-sided number must derive it for a rule nobody certified; the severity artefact certifies a named rule and states both quantities beside its bound. Status stays `not_measured` because the criterion is worded as the wider claim, and this document records the narrowing rather than quietly re-defining the row to fit it.

### G4 -- `not_met`

- criterion: Worst-slice certification refuses rather than averages
- measurement: per (language x option-count) bounds with a simultaneous multiple-testing correction; must return `NOT_CERTIFIABLE` for the slices `laya` documents as collapsed (e.g. Khmer: accuracy 0.000 at mean confidence 0.952)
- artefacts: 4 -- `data/slices_language.json`, `docs/SLICES.md`, `tools/language_slices.py`, `tests/test_slice_surface.py`
- note: measured, and short of its own wording -- which is why this row reads `not_met` and not `not_measured` any more. The behaviour the criterion describes is now a published artefact rather than terminal scrollback: `tools/language_slices.py` certifies the four committed MASSIVE record files (11,896 cases, one per row) as slices of the key the producer itself declares (`slices.language`), at the rubric this freeze owns, and `verify` recomputes that run from the same bytes -- 92 field comparisons plus 5 rubric rows. The published run refuses: 4 slices, 0 certified, `any_slice_refused` true, and no slice is named as the worst, because the metric that would rank them (`autorate`) is null in all four rows -- so what this artefact demonstrates is every slice refusing, not one worst slice beaten; every slice refused at the corrected budget (alpha and delta 0.05 / 4 = 0.0125, and the artefact's own envelope does that family arithmetic: 4 x 3 x 0.0125 = 0.1500, joint level 0.85), and `n_min_violations` empty -- so the refusal is a bound failure, not a thin-slice floor. The pooled marginal certificate over the same records is published beside the slices and refuses too (`empty_feasible_set`, exact bound above the budget), which is the 'rather than averages' half of the sentence: nothing in the artefact lets the pooled number stand in for the worst slice. Two things keep the row from `certified`. It is per-language only: `option_count` is 20 for every committed MASSIVE row -- measured across all four files, Khmer included -- so the (language x option-count) cross the measurement names would be the same four slices, and no cross-slice evidence exists to publish. And the ranking the criterion's word 'worst' asks for cannot be published from a run where nothing certifies. The slice the criterion names by example, Khmer, is no longer one of the gaps: `data/records_massive_km.jsonl` is committed and measured here, and it refuses like the other three; upstream's `accuracy 0.000 at mean confidence 0.952` is its own 100-case read, which this corpus neither replicates nor contradicts -- it is a fourth refusal at a different sample size, and the claim ledger records the line. What the run does emit is the criterion's own word: each refused slice's summary carries `NOT_CERTIFIABLE: reason=empty_feasible_set`, and `certify --groups language` over these records exits 3, which is `EXIT_NOT_CERTIFIABLE`. An earlier draft of this note claimed the opposite and was corrected by review, not by the author noticing; a later draft named `de` as the worst slice, and the row in `tests/test_verify_protocol.py` that counts this arm is what showed the artefact names no worst at all.

### G5 -- `certified`

- criterion: Reproducible from a commit with no GPU, no network, no model
- measurement: `autorate verify --protocol protocol.json` re-derives every published number from per-case records alone; exit code + counts printed
- artefacts: 4 -- `docs/G5.md`, `tools/g5_export.sh`, `tools/g5_transcript.py`, `tests/test_g5_transcript.py`
- note: measured, and now published as a record rather than as a simulation I perform and delete. `tools/g5_export.sh` unpacks a `git archive` of commit 9e6363a into a scratch directory with its own HOME, asks that environment what it can see -- `.git` ABSENT, torch and transformers answered by the export's own interpreter, a deliberate HTTPS fetch failing -- and runs the criterion's literal command in both lanes, which `docs/G5.md` transcribes: absent-lane rc=0 at 249/249 values and corpus-present rc=0 at 284/284, the 35-check difference being the upstream digests and snapshot keys only a corpus can recompute. Four falsifications are planted in the same export and restored byte-identically with the restore checked: a rubric value moved inside the frozen file, refused at rc=2 by the loader's freeze-consistency check before the drift comparison is even reached; the records file replaced by another valid, self-consistent records file, refused at rc=4 because the certificates built from it name no record for a backend the published table declares; the inventory snapshot reduced to an empty JSON array, refused at rc=4 as a named unusable artefact rather than a traceback; and one hex digit of a published certificate's stamped digest, refused at rc=4 because the meta block is compared whole. `tests/test_g5_transcript.py` is what keeps the record honest: it reads the digest of the commit the transcript names (not of the reader's tree, which is what made a transcript that re-freezes impossible to publish), refuses any recorded exit code outside the contract, requires each lane's two halves to agree and the two lanes to differ by the checks the corpus owns, counts the plant blocks against the sentence that counts them, and refuses the document if one line still names a machine path. What the row does not license: the no-network claim covers the gate steps, not the `uv sync` that provisions them; the corpus-present lane needs an archive that is not a committed file, so no runner reproduces that lane and it stays a local obligation; 'every published number' means the numbers this gate owns, and `drift.py` and `contamination.py` have no published artefact, so those figures are absent from both denominators rather than re-derived. The record is a record OF a revision, so the revision is named twice rather than related: `docs/G5.md` opens by saying it was produced from commit 9e6363a, which is the commit this note says the export unpacked, and the row named above is what makes that pairing checked rather than remembered: it takes the digest from the named commit's own object, so a re-freeze cannot make the record lie and a transcript cannot be smuggled in from a branch that never landed. Nothing here turns on which document a reader is holding: `docs/REPORT.md` quotes this note verbatim, so a phrase that points at "this document" would name one file inside the protocol and another inside the report, and would be wrong from the next commit onward even in the protocol. The platform half is stated the same way. `.github/workflows/ci.yml` triggers on push and runs the criterion's literal command in both of its jobs -- `offline`, and the cross-libc matrix over ubuntu and macOS. The witness of any tip is that tip's own run, so it is read from the runner's log rather than asserted here: this note claims no result of a run it cannot see, and `tests/test_ci_workflow.py` is the row that refuses a workflow edited back to the unfrozen form.

## Every refusal, and what it refused

This is the half of the record a summary usually drops, so it is printed artefact by artefact.
Each line names the file it quotes and then that file's own summary sentence, verbatim: the
digits in the sentence are the digits in the artefact, and `verify` re-derives the artefact from
the committed records beside it.

| artefact | declared by | subject | verdict | reason | coverage | beta | n_cal | n_eval |
|---|---|---|---|---|---|---|---|---|
| `data/cert_jev.json` | `report.CERTS` | `jev` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 95 | 96 |
| `data/cert_laya.json` | `report.CERTS` | `laya` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 96 | 96 |
| `data/cert_massive_de_laya.json` | `report.MASSIVE_CERTIFICATES` | `laya` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 1487 | 1487 |
| `data/cert_massive_en_laya.json` | `report.MASSIVE_CERTIFICATES` | `laya` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 1487 | 1487 |
| `data/cert_massive_km_laya.json` | `report.MASSIVE_CERTIFICATES` | `laya` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 1487 | 1487 |
| `data/cert_massive_sw_laya.json` | `report.MASSIVE_CERTIFICATES` | `laya` | **refused** | `empty_feasible_set` | 0.95 | 0.05 | 1487 | 1487 |

Verbatim, because the summary is the certifier's own sentence and not this document's:

- `data/cert_jev.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=95 n_eval=96; at coverage 0.950 the 32 automated cases include 1 carrying a wrong automated request; the exact case-level upper bound 0.140 exceeds the budget 0.050
- `data/cert_laya.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=96 n_eval=96; at coverage 0.950 the 2 automated cases include 1 carrying a wrong automated request; the exact case-level upper bound 0.975 exceeds the budget 0.050
- `data/cert_massive_de_laya.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=1487 n_eval=1487; at coverage 0.950 no evaluation case produced a singleton set (0 empty, 1487 multi-label of 1487)
- `data/cert_massive_en_laya.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=1487 n_eval=1487; at coverage 0.950 the 709 automated cases include 43 carrying a wrong automated request; the exact case-level upper bound 0.078 exceeds the budget 0.050
- `data/cert_massive_km_laya.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=1487 n_eval=1487; at coverage 0.950 the 11 automated cases include 5 carrying a wrong automated request; the exact case-level upper bound 0.729 exceeds the budget 0.050
- `data/cert_massive_sw_laya.json`: NOT_CERTIFIABLE: reason=empty_feasible_set at alpha=0.050, beta=0.050; n_cal=1487 n_eval=1487; at coverage 0.950 the 39 automated cases include 13 carrying a wrong automated request; the exact case-level upper bound 0.477 exceeds the budget 0.050

0 of the 6 published set certificates certify. The reasons named above are the whole of what the rest refused, and each refusal travels inside its artefact with the budget pair that made it, its case counts and its envelope.

### The ordinal certificate (G3)

- artefact `data/cert_severity_ordinal.json`, certified from `data/records_ordinal_synthetic.jsonl`, at direction `under`: the publication table `report.SEVERITY_CERTS` names the rule and `verify` re-derives at it, rather than reading the rule back out of the bytes it is checking
- verdict: certified
- `data/cert_severity_ordinal.json`: one-sided severity certificate, direction=under: P(Y > ahat(X)) <= 0.045180 at ahat=3, tested at delta=0.050 on 200 calibration cases (alpha=0.050 is the risk target, not a confidence); the price is P(Y < ahat(X)) <= 0.686921 at the same rule and the rule replaces the model's own level on <= 0.701258 of cases; measured on 200 held-out cases: 0.005000; joint level 0.85 over 3 claims at delta=0.050; n_cal=600 n_eval=600; synthetic ordinal data with known answers (the offline archive carries no `score` answers), and the construction is prior art -- Dey et al. NeurIPS 2023, Zhang et al. AAAI-26, Xu-Guo-Wei UAI 2023 (PMLR 216:2346-2355), ours being the automation rule and the one-sided statement
- its population is synthetic ordinal data with known answers, and the artefact states that in 9 envelope lines of its own: no committed records file in this checkout carries a `score` record, which is why the ordinal guarantee is measured on a synthetic population at all.

### The resplit experiment (G1's second column)

200 splits per task, and what came out of them. A task that issued no certificate has no violation rate to report, and the artefact leaves it undefined instead of imputing a zero:

| task | certified | refusals | violations / denominator | rate |
|---|---|---|---|---|
| `jev` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `laya` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `massive/de` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `massive/en` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `massive/km` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `massive/sw` | 0 of 200 | `empty_feasible_set`:200 | 0 / 0 | undefined (no certificates) |
| `synthetic/sharp-k4-e0.02` | 200 of 200 | - | 0 / 200 | 0.0 |

### The slice run (G4)

Slices are named by the key the producer declares (`language`), refused by name, and the pooled certificate is published beside them rather than in place of them.

| slice | feasible | reason | n_cal | n_eval |
|---|---|---|---|---|
| `de` | False | empty_feasible_set | 1487 | 1487 |
| `en` | False | empty_feasible_set | 1487 | 1487 |
| `km` | False | empty_feasible_set | 1487 | 1487 |
| `sw` | False | empty_feasible_set | 1487 | 1487 |

- worst slice of the joint claim: `de` on metric `autorate`; any slice refused: True
- slices refused by the size floor rather than by a bound: 0
- pooled over the same records: feasible=False, reason=empty_feasible_set, n_eval=5948
- inputs this run is a function of, with the digests that pin it: `data/records_massive_de.jsonl` (2974 rows, `2fb97c44e8209acbeadbda9db88e7887441891636c0f1a3ee325f8fa8b42c68f`), `data/records_massive_en.jsonl` (2974 rows, `432d7d10f53e5d148be8811dfe4d2f2e3ce4b7b97a2727445b2fd2f6d651f8db`), `data/records_massive_km.jsonl` (2974 rows, `dd302722ed49cef88e33deb9d8673faf18d54752f224ac867686917aae057239`), `data/records_massive_sw.jsonl` (2974 rows, `f423fc0161fdcd0c6d85180728c59ae1ea39a2b8a31d4b75f7cde91fbf8c821c`)

### The gate the reference README instructs (G2)

G2's measurement is `docs/AUDIT.md`, written by `autorate audit` from the committed records and
byte-compared by `verify`. Its verdict is the freeze's row above, quoted in the claims section
rather than restated here, and that row reads: `measured_not_bounded`.

### What a refusal costs the caller

A refusal is a result, so it is loud in the exit code and never in a traceback. The codes this
project publishes, read from `cli.py`'s constants:

- `0` -- certified: the certificate holds, or every published number reproduced
- `2` -- usage: an input this command was handed is wrong, whether the operator named its path or a default supplied it
- `3` -- not certifiable: the run measured and refused. A result, printed and written, not a crash
- `4` -- drift: the committed state cannot reproduce what it publishes -- a number that disagrees, or a published artefact this repository's own tables declare and this run cannot read

A published artefact this checkout cannot read -- nothing at its path, the path refusing the
open, or bytes that are not the artefact the table declares -- is a named refusal at the drift
code and not a usage error: no argument selected that path, the publication table did, and no
argument can repair it. Nothing is allowed to escape as code 1.

## The envelope and known limits, copied from the protocol

A certificate read without its envelope is invalid output, so the assumptions travel inside the
artefact. `protocol.json`'s `known_limits` block is the union of the envelope lines the published
set certificates actually carry, sorted -- 2 lines, quoted rather than paraphrased:

- exchangeability within group assumed; none of it is usable here
- no certificate exists, so no action is certified

What those lines do not cover is stated by the artefacts that do, each in its own envelope:
the ordinal certificate in 9 lines, naming the population it was measured on and the rule it
certifies, and the slice run in 6, saying which budgets were divided, which were not, and what
the pooled certificate may not stand in for. Those documents are `docs/SEVERITY.md` and
`docs/SLICES.md`, each byte-compared by `verify`.

### The pinned build behind the MASSIVE figures

Read from `data/massive_provenance.json` through `inventory.massive_pin`, which polices its counts against each other before anything is printed:

- `dataset`: mteb/amazon_massive_intent
- `revision`: 940fd47a81eaa7f2cc7b129674d945d618ac38c2
- `license`: Apache-2.0
- `n_files`: 51
- `rows_total`: 151674
- `distinct_ids`: 2974
- `distinct_row_counts`: [2974]
- `id_sets_identical`: True
- `bytes_total`: 3221662

The id sets across the shards are identical (`id_sets_identical`: True) and the per-shard row
counts collapse to 1 distinct value (2974), which is why a bound may sit on 2974 independent
utterances and not on 151674 rows.
That is the difference between a certificate and a restatement of the same sentence 51 times.

This report prints no per-shard digest: `data/massive_provenance.json` owns the 51 of them, and the freeze pins that file
by its own digest (`654e03e75da34c51a8872e1eb7877088e2ce60c5ee408d8ae25c01e0ea785e76`) instead of transcribing it, because a published figure with two owners
is two figures.

## Reproduction (G5)

`autorate verify --protocol protocol.json` is the claim. It needs no GPU, no network, no model
and no corpus: every input is a committed file, and the two lanes the command can run in print
different denominators on purpose -- the corpus-absent lane transcribes the inventory snapshot it
cannot contradict and says so in its own disclosure line.

- documents `verify` byte-compares (`cli.PUBLISHED_DOCS`, 8 of them, this file among them): `docs/RESULTS.md`, `data/inventory.md`, `docs/AUDIT.md`, `docs/SEVERITY.md`, `docs/RESPLIT.md`, `docs/SLICES.md`, `docs/FEASIBILITY.md`, `docs/REPORT.md`
- the records every table above is built on: `data/records_feishu.jsonl` (jev=959 rows, laya=960 rows)
- the inventory the document arm read: `data/inventory.md.json`
- digests the freeze named in advance, which are the two checks in that gate that are not fixed
  points: `data/records_feishu.jsonl` -> `d06e7e87f4de31e287f7900dc1662ea0c5c845b3b5cac592bff3612d33593026`, and `data/inventory.md.json` -> `be0f8e8d93fec3d67487ba8d771334ddf5ed8c533b2257c17d92b920b9e48b77`
- the corpus is not a committed file: it is a sibling `laya*/research/benchmarks/feishu_zh`
  checkout, resolved from the environment, then the flag, then the sibling glob. No source file
  carries an absolute path to it, and a test fails the build if one reappears.

G5's own row states what is still owed, and this document quotes it instead of settling it:

> measured, and now published as a record rather than as a simulation I perform and delete. `tools/g5_export.sh` unpacks a `git archive` of commit 9e6363a into a scratch directory with its own HOME, asks that environment what it can see -- `.git` ABSENT, torch and transformers answered by the export's own interpreter, a deliberate HTTPS fetch failing -- and runs the criterion's literal command in both lanes, which `docs/G5.md` transcribes: absent-lane rc=0 at 249/249 values and corpus-present rc=0 at 284/284, the 35-check difference being the upstream digests and snapshot keys only a corpus can recompute. Four falsifications are planted in the same export and restored byte-identically with the restore checked: a rubric value moved inside the frozen file, refused at rc=2 by the loader's freeze-consistency check before the drift comparison is even reached; the records file replaced by another valid, self-consistent records file, refused at rc=4 because the certificates built from it name no record for a backend the published table declares; the inventory snapshot reduced to an empty JSON array, refused at rc=4 as a named unusable artefact rather than a traceback; and one hex digit of a published certificate's stamped digest, refused at rc=4 because the meta block is compared whole. `tests/test_g5_transcript.py` is what keeps the record honest: it reads the digest of the commit the transcript names (not of the reader's tree, which is what made a transcript that re-freezes impossible to publish), refuses any recorded exit code outside the contract, requires each lane's two halves to agree and the two lanes to differ by the checks the corpus owns, counts the plant blocks against the sentence that counts them, and refuses the document if one line still names a machine path. What the row does not license: the no-network claim covers the gate steps, not the `uv sync` that provisions them; the corpus-present lane needs an archive that is not a committed file, so no runner reproduces that lane and it stays a local obligation; 'every published number' means the numbers this gate owns, and `drift.py` and `contamination.py` have no published artefact, so those figures are absent from both denominators rather than re-derived. The record is a record OF a revision, so the revision is named twice rather than related: `docs/G5.md` opens by saying it was produced from commit 9e6363a, which is the commit this note says the export unpacked, and the row named above is what makes that pairing checked rather than remembered: it takes the digest from the named commit's own object, so a re-freeze cannot make the record lie and a transcript cannot be smuggled in from a branch that never landed. Nothing here turns on which document a reader is holding: `docs/REPORT.md` quotes this note verbatim, so a phrase that points at "this document" would name one file inside the protocol and another inside the report, and would be wrong from the next commit onward even in the protocol. The platform half is stated the same way. `.github/workflows/ci.yml` triggers on push and runs the criterion's literal command in both of its jobs -- `offline`, and the cross-libc matrix over ubuntu and macOS. The witness of any tip is that tip's own run, so it is read from the runner's log rather than asserted here: this note claims no result of a run it cannot see, and `tests/test_ci_workflow.py` is the row that refuses a workflow edited back to the unfrozen form.

## Related work, cited only where the ledger opened it

`docs/VERIFICATION.md` holds 46 rows: 40 `verified`, 6 `withdrawn`. Only a `verified` row is quotable here as a claim about somebody else's work, and every bullet below IS that row's own claim cell -- cut to 240 characters with a visible marker, with the row id, the date the source was opened and the status printed beside it. A row this document cites that the ledger does not carry, or that has left `verified` since, makes the renderer refuse instead of printing the sentence, so 34 ids are re-checked against the ledger on every render.

### The reference implementation whose gate this project audits

- `laya-readme-gating-instruction` (the instruction G2 measures) -- opened 2026-09-30, status `verified`: the README's "Automated Confidence Gating" section instructs `if conf >= 0.85: route_automatically(dept)` on the `confidence` field
- `laya-confidence-docstrings` (the two definitions the name `confidence` carries upstream) -- opened 2026-09-30, status `verified`: `answer_confidence` is `max(p)` and its docstring calls it "the quantity every calibration figure in this repository is computed on"; `confidence_from_probs` is `1 − H(p)/log k` and its docstring says "not calibrated: it is not what tempera...
- `laya-shipped-temperature` (the shipped temperature that sharpens the reported confidence) -- opened 2026-09-30, status `verified`: the shipped `choice:11+` temperature is 0.1006, which multiplies logits ~10x, so "a 0.24 top probability is published as 0.99, so a caller gating on confidence is told a coin flip is a certainty", and the clamp constants are `TEMP_MIN = 0.5...
- `laya-readme-collapse-table` (the collapsed slice G4 names by example) -- opened 2026-09-30, status `verified`: Khmer scores 0.000 accuracy at 95.2% confidence and macro ECE is 0.733 (L855), ordinal `score` is the weakest primitive at SST-5 0.372 (L868, L930), and `act_probability` reads AUROC 0.30 against correctness where `confidence` reaches 0.77 ...
- `laya-feishu-archived-pairs` (the archive these records were exported from) -- opened 2026-09-30, status `verified`: the archive holds all 768 timed raw responses for both backends (L80) and the headline row is Laya 20/64 against Jev 64/64 (L24-L25)
- `laya-per-case-fields-parity` (what upstream publishes its per-case records as) -- opened 2026-09-30, status `verified`: per-case records carry `probability`, `p_gold`, `confidence`, `correct` (L69) and parity with `Agent.system_one` is max abs delta-p 4.98e-5 multilingual, 4.92e-5 english (L267)
- `laya-vendored-tree-matches-tag` (the check that makes the vendored tree the tagged tree) -- opened 2026-09-30, status `verified`: the ten `[local]` rows above are re-openable at the tag, not merely on this laptop: `git hash-object` of each vendored file equals the blob SHA listed by the v0.3.20 recursive tree for `laya/common.py`, `README.md`, `laya/hooks.py`, `laya/s...

### Conformal risk control and conformal tooling that already ship

- `mapie-risk-control-coverage` (what the risk-control track actually covers) -- opened 2026-09-30, status `verified`: the claim that MAPIE "is marginal-only" is false as written. MAPIE's risk-control track covers binary classification, multi-label classification and semantic segmentation (plus input-adaptive AA-CRC regression intervals) with method-by-meth...
- `mapie-abstention-rate-example` (the shipped abstention-rate control this project does not claim) -- opened 2026-09-30, status `verified`: MAPIE already ships the shape §1 claims nobody publishes: an LLM-as-judge example that finds thresholds which "guarantee with a confidence of 0.9" two precisions and "an abstention rate of at most 0.2", choosing the feasible pair that minim...
- `mapie-crc-disclaimer` (the clipped-variant disclaimer, in the library's own words) -- opened 2026-09-30, status `verified`: MAPIE's AA-CRC example says of itself: "This practical bounded variant does not strictly satisfy the vector-space assumption of the theoretical AA-CRC guarantee", and the API reference repeats it for `predict_param_range`: "the clipped pred...
- `mapie-exchangeability-tests` (assumption testing MAPIE owns, not this project) -- opened 2026-09-30, status `verified`: a capability the spec does **not** own, recorded because the previous pass noted it and then did not write it down. MAPIE's README L21: "In addition, **exchangeability tests** have been introduced to help users verify when MAPIE can be legi...
- `two-way-bound-construction-source` (the conditional-risk construction the two-stage rule uses) -- opened 2026-09-30, status `verified`: replaced: the source the second half of §5.3's two-way control actually rests on. Anastasios N. Angelopoulos, Stephen Bates, Emmanuel J. Candès, Michael I. Jordan and Lihua Lei, "Learn then Test: Calibrating Predictive Algorithms to Achieve...
- `selective-crc-2512-12844` (select-then-control as published prior art) -- opened 2026-09-30, status `verified`: the identifier is real: Xu, Guo and Wei, "Selective Conformal Risk Control", submitted 2025-12-14 (v2 2026-04-27), which "formulates uncertainty control as a two-stage problem: the first stage selects confident samples for prediction, and t...
- `cost-sensitive-crc-2607-27143` (Mondrian recovery under cost, measured across 15 datasets) -- opened 2026-09-30, status `verified`: Singh, Srikantha and Lakhanpal, "Cost-Sensitive Conformal Prediction and Human-in-the-Loop Abstention for Imbalanced High-Stakes Decision Support: A Multi-Domain Benchmark", submitted 2026-07-29: marginal CP under-covers costly minority cla...

### Ordinal conformal prediction, the immediate prior art

- `ordinal-cp-neurips2023` (the contiguous minimal-cardinality set construction) -- opened 2026-09-30, status `verified`: Dey, Merugu and Kaveri, "Conformal Prediction Sets for Ordinal Classification", NeurIPS 2023 main conference track: proposes a framework "to adapt existing CP methods to generate contiguous sets with guaranteed coverage and minimal cardinal...
- `ordinal-crc-uai2023-two-losses` (the two ordinal-specific losses already controlled under CRC) -- opened 2026-09-30, status `verified`: opened at the primary source so §12's prior-art cell no longer rests on the withdrawn row above, whose text never states this fact (R-11, finding I-4). Xu, Guo and Wei, "Conformal Risk Control for Ordinal Classification", UAI 2023, PMLR 216...
- `ordinal-cp-aaai-minlen` (the minimum-length ordinal interval, and its released code) -- opened 2026-09-30, status `verified`: Zhang, Chen, Shi, Ma, Xu and Yan, "Minimum-Length Conformal Prediction Sets for Ordinal Classification", The Fortieth AAAI Conference on Artificial Intelligence (AAAI-26), proceedings PDF, p. 28662: model-agnostic instance-level optimal (mi...
- `ordinal-cp-2606-24959` (the RPS nonconformity that yields median-centred intervals) -- opened 2026-09-30, status `verified`: the identifier is real and resolves at the arXiv registry: Haas, Killmaier, Javanmardi and Hüllermeier, "Reliable Conformal Prediction for Ordinal Classification Using the Ranked Probability Score", submitted 2026-06-23, whose RPS nonconfor...

### Neighbours in the same niche, read at pinned commits

- `verdict-automation-guarantee` (a shipped conformal automation rule, and the guarantee it carries) -- opened 2026-09-30, status `verified`: "`verdict`" is an overloaded name, so the referent is pinned to one exact `owner/repo`: **`Manavarya09/verdict`** (Apache-2.0, 3 stars, created 2026-09-23; description "Small, fast, honest decision models. Open alternative to Jev: zero-shot...
- `verdict-refusal-reporting` (what that project says when it will not commit) -- opened 2026-09-30, status `verified`: what `verdict` actually does when it will not commit, searched for rather than assumed (R-11, finding I-3). Whole repository cloned at `76bc1fe` — 90 files, 42 of them `*.py` — and grepped tree-wide for `refus|reason|infeasib|not.certifi|es...
- `open-medical-jev-auto-release` (Chow's rule on a caller-supplied cost ratio) -- opened 2026-09-30, status `verified`: `FeiLiuEM/open-medical-jev` (MIT, 38 stars, created 2026-09-25), read from **code at commit `ad22e32`** rather than from its tagline ("four readings, one routed decision, zero training" — that describes a decision *service* and records neit...
- `open-medical-jev-refusal-reporting` (a prose note beside the answer, and no bound) -- opened 2026-09-30, status `verified`: the same search on the second survivor (R-11, finding I-3). `git clone` failed again for this repository (HTTP2 framing error), so the tree was taken as the API tarball at `ad22e32` — 43 files, 15 `*.py` — and grepped tree-wide. At the deci...
- `jev-trust-per-domain-calibration` (per-domain ECE and Brier, with zero bound machinery) -- opened 2026-09-30, status `verified`: opened at the primary source so §12's audit cell no longer rests on a bare name living inside the withdrawn row above (R-11, finding I-4). `jev-trust` is a shipped package, not a list entry: PyPI carries releases 0.1.0, 0.2.0 and 0.2.1 with...
- `openjev-verdict-2-refusal-reporting` (the same search in a same-named project) -- opened 2026-09-30, status `verified`: `Heman10x-NGU/openJev-verdict-2.0` (293 stars, same niche, in neither awesome-list) had been opened at README level only; it is now cloned at `bff28567` (189 files, 65 `*.py`) and searched the same way (R-11, finding I-3). Its abstention is...
- `openjev-verdict-2-confidence-channels` (a two-channel confidence decomposition, measured empirically) -- opened 2026-09-30, status `verified`: the README-level figure this ledger owed, settled at code level — and it cuts against §12's audit row rather than for it (R-11, findings I-3 and I-4). In the clone at `bff28567`, `verdict2/metrics.py` returns `"ece_distribution": ece(dist_c...
- `poorjev-refusal-reporting` (the budget printed beside an infeasible result) -- opened 2026-09-30, status `verified`: the same search in the project whose conformal claim this ledger withdrew, and **the finding does not go our way** (R-11, finding I-3). Whole tree at `7e684e95` (54 files, 26 `*.py`). `fit_abstention_threshold` has two silent sentinels — `(...
- `nibzard-no-threshold` (a community benchmark's own refusal to pick a threshold) -- opened 2026-09-30, status `verified`: the README states verbatim: "Confidence curves do not select a deployment threshold. Choose a threshold on separate held-out data and evaluate its coverage and error rate." Weight noted honestly: a 9-star community benchmark, quoted as the ...

### Dated observations, which any text re-quoting them has to re-open

- `laya-star-count` (a star count, recorded as an observation with its date) -- opened 2026-09-30, status `verified`: 28,750 stars, a dated and volatile observation. The two figures the earlier research pass reported (19,301 and about 28k) are resolved in favour of the second; 19,301 is not reproducible from the API on this date. Spec §1's "~20k-star" is c...
- `competitor-age-stars-packaging` (age, stars and packaging of the neighbours above) -- opened 2026-10-01, status `verified`: age, stars and packaging of the three open conformal-gate projects cited in §1 | `gh api repos/<r>`: Manavarya09/verdict 2 stars created 2026-09-23 pushed 2026-09-24; FeiLiuEM/open-medical-jev 38 created 2026-09-25; rupeshpoojary9/poorjev 1...
- `justaskjev-ece0168` (two medians, with the denominator each was computed over) -- opened 2026-09-30, status `verified`: Guo et al., "Just Ask Jev: Reinforcement Learning for Calibrated Decisions as a Zero-Shot Detector of AI Alignment Failures", submitted 2026-09-24. Both numbers are real but the scope in the spec was wrong: the paper reports a median **per-...
- `jev-vendor-confidence-guidance` (the vendor's own guidance on threshold choice) -- opened 2026-09-30, status `verified`: the vendor's own confidence page: "`confidence` is a statistic computed from the probability distribution the answer already gives you" and "The correct threshold values depend on your domain and the performance of the model for your use ca...
- `jev-api-limits` (the option ceiling the vendor's reference states) -- opened 2026-09-30, status `verified`: the vendor's API reference states "You can have a maximum of 255 options per Choice", and the models page prices jev-1.13.0 at $42 per Btok / $0.042 per Mtok on input with output free, 100K tokens per second and 40 requests per second, 64k ...

### Searches, recorded as tasks with the date they ran -- never as statements about the field

- `ordinal-cp-literature-size` (the query that enumerated the ordinal literature behind §5.4) -- opened 2026-09-30, status `verified`: §1's "roughly four papers and no implementation" is wrong in both halves (counted 2026-09-30 by one arXiv abstract query, so the count is a floor, not a census). Six ordinal-CP works are openable: arXiv 2207.02238 (Lu, Angelopoulos and Pome...
- `awesome-jev-guarantee-scan` (the scan that found the neighbours above, with its own reach limit) -- opened 2026-09-30, status `verified`: how the three rows above were found, recorded so the search is re-runnable: both lists' calibration sections were scanned programmatically for `conformal`, `finite-sample`, `guarantee`, `risk control`, `bound` — 24 entries in `cobanov/aweso...

### Why a null result is written as a task

The last group above is not a finding about the field; it is a record of a search, and the only
date attached to it is the date the ledger says that search ran (`ordinal-cp-literature-size` opened 2026-09-30, `awesome-jev-guarantee-scan` opened 2026-09-30).
A `none found` in this repository therefore means "not found by this search on this date",
never "does not exist"; the row's own claim cell, quoted above, is what states its scope.

The severity summary quoted in the refusal section names prior art inside its own sentence. This
document does not restate that sentence: the rows which opened those sources are cited above -- `ordinal-cp-neurips2023`, `ordinal-cp-aaai-minlen`, `ordinal-crc-uai2023-two-losses` -- so the summary stays the artefact's and the evidence stays the ledger's.
