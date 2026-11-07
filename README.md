# autorate

[![autorate gate](.github/badges/autorate-badge.svg)](.github/badges/autorate-badge.json)

Certified automation rates for decision models: confidence is not permission.

A benchmark answers "how good is the model". A certificate answers a question an
operator can actually be held to: "what share of this model's decisions may run
unattended while keeping the probability that an automated decision is wrong at most
`beta`, given the held-out data we really have". When the data cannot support that
claim, `autorate` prints `NOT_CERTIFIABLE` with a reason code, the observation at the
requested coverage that caused it, and a diagnostic sweep of the neighbouring coverage
levels -- evidence for the refusal, not a certificate. It exits 3 and does not publish a
number about nothing.

## Verification-first navigation

- [Verification status](docs/VERIFICATION.md) · [Known errata](docs/ERRATA.md) · [Results](docs/RESULTS.md)
- The present implementation covers the decision-certification primitives described below; planned certificate families and guarantees are **not** implemented claims.
- This is a public repository. No public licensing or release rights are implied.

## What a certificate carries

Stored: `feasible`, `reason`, `backend`, `method`, `alpha`, `beta`, `delta`, `autorate`,
`autorate_ci`, `conditional_error_bound`, `marginal_error_bound`, `mean_set_size`,
`qhat`, `n_cal`, `n_eval`, `envelope`, `meta`.

Derived, never stored, because each is a pure function of a stored field -- storing them
gave one number two owners and a guard that could not see the disagreement: `refusal_rate`
= `1 - autorate` (every evaluated case is empty, singleton, or multi-label) and `level`
= `1 - N_CLAIMS * delta` (three bounds are published per certificate).

Two of those rows carry the whole argument:

- `conditional_error_bound` is `P(wrong | automated) <= beta`. `marginal_error_bound`
  is `P(wrong AND automated)`. They are different quantities, and a paper or a dashboard
  that quotes one while meaning the other is the failure mode this tool exists to stop.
- Both are over **cases**, not archive rows. Repeats of one case are one observation, and on this
  corpus they are not even evenly counted: laya's archived choice slice is 64 cases x 3 rows (192
  rows), while jev's is 191 rows over the same 64 cases -- one case carries two rows, not three -- and
  a jev case carries between one and three *distinct* probability vectors. What a repeat shares is the
  measurement, not the row: laya's three repeats per case carry byte-identical probability vectors,
  scores and gold labels (not identical rows: the repeat counter and its own elapsed time differ),
  while jev's repeats need not carry the same vector at all -- so the `n` in every bound counts cases
  and the record counts are published beside it instead of standing in for it.
- `envelope` is the machine-readable statement of what the bound assumed -- coverage
  level, group conditioning, drift, and how empty sets were counted. A certificate read
  without its envelope is invalid output, so `certify`, `compare` and `gate` all print it.
- `alpha` is the coverage floor the certificate is held to, not a label on it. An earlier version
  swept a grid of coverage levels for the largest automation rate and tested the winner on
  the same evaluation half, then printed "at alpha=0.050" while operating at 0.89
  coverage (fixed in `241e395`). The pre-fix quantity is still checkable rather than asserted:
  `data/cert_*.json` carries `meta.diagnostic_curve`, the sweep of coverage levels the old code
  maximised over, and `meta.closest_attempt`, the point that came closest to the budget.
  Selecting on the test half is snooping, so the set size now comes from the
  calibration half at exactly the requested `alpha`; the grid survives only as diagnostic
  evidence attached to a refusal.

`refusal_rate` and `mean_set_size` exist because an empty certified set is a refusal,
not a free correct answer: counting it as automation would inflate the rate.

## Commands

```bash
uv sync --frozen --extra dev

uv run --frozen autorate snapshot --out data/inventory.md   # corpus -> committed inventory
uv run --frozen autorate export-feishu --out data/records_feishu.jsonl
uv run --frozen autorate certify data/records_feishu.jsonl --backend laya --out cert.json
uv run --frozen autorate compare data/cert_laya.json data/cert_jev.json
uv run --frozen autorate gate data/records_feishu.jsonl --cert data/cert_jev.json --limit 5
uv run --frozen autorate report --out docs/RESULTS.md   # write the published numbers
uv run --frozen autorate report --full               # write docs/REPORT.md, one document for a reviewer
uv run --frozen autorate verify                          # re-derive them, fail on drift
```

The `uv run --frozen` prefix is not decoration: the console script is not on `PATH`
after `uv sync`, and a bare `pytest` on this machine resolves to a different
interpreter entirely.

Exit codes: `0` certified, `3` `NOT_CERTIFIABLE`, `2` usage error -- an input this
command was handed is wrong, whether you named its path or a default supplied it --
`4` the committed state cannot reproduce what it publishes: a number that disagrees,
or a published artefact this repository's own tables declare that this run cannot
read -- because nothing is at its path, because the path itself refuses the open, or
because what is there is not the artefact that table publishes: a corrupt certificate,
a records line that is not a record, a document that is not text, a certificate stored
in a shape this build does not read, a committed inventory snapshot that will not load
or is not the mapping its renderers index.
One table-declared path stays `2` by ruling rather than oversight:
`data/records_feishu.jsonl` is the default every command reads -- `verify` and `report`
with no flag, `audit --records` with one -- absent or unreadable alike, and a default is
something its operator can name and repair.
A missing `data/inventory.md.json` alongside no corpus is `2` for a reason the refusal
does not cover -- there is nothing to verify against, which is a different statement
from a published artefact that cannot be read -- while a snapshot that is present and
will not load is `4` like any other published artefact.

`snapshot` and `export-feishu` read the corpus: pass `--root`, set
`AUTORATE_FEISHU_ROOT`, or place the checkout as a sibling of this repo
(`<workspace>/laya*/research/benchmarks/feishu_zh`). No source file carries an absolute
machine path, and `tests/test_cli.py` fails the build if one reappears -- a literal like
that passes every local gate and only breaks in the environment nobody can see.

Everything else runs offline on committed files; no command reaches the network.

## GitHub Action and badge

[`action.yml`](action.yml) is a composite action. It shells out to the CLI and implements **no**
statistics: no bound, rate or aggregate is computed in the action or in
[`tools/action_report.py`](tools/action_report.py), which only maps the CLI's own exit code to a state and
formats what the CLI printed. The one number it parses is the denominator out of the tool's
`re-derived N /M values` line, so the badge can carry it instead of standing alone.

| input | default | meaning |
|---|---|---|
| `version` | empty | run `autorate==<version>` from PyPI through `uvx` |
| `ref` | empty | run the CLI from a detached worktree at that ref of this repository (needs full history) |
| `alpha`, `beta` | empty | passed to `certify`; empty means "use the frozen protocol's rubric" |
| `path` | `protocol.json` | read from the **working tree**, never `git show <rev>:protocol.json` |
| `records` | empty | when set, `certify` runs too, and its exit 3 is the verdict |
| `fail_on` | `drift,not-run` | states that fail the job |
| `badge_dir` | `.autorate` | where the `.svg` and its `.json` record are written |
| `comment` | `true` | post a PR comment quoting `autorate compare` verbatim (both denominators, no bound diff) |

The states are a closed vocabulary, and none of them is a boolean:

| state | when | what it does **not** mean |
|---|---|---|
| `certified` | `verify` exited 0 (and `certify` exited 0, if a records file was given) | not "the model is certified": `protocol.json`'s `claims[]` is where a certificate claim is made or refused |
| `not-certifiable` | `certify` exited 3 | not a broken pipeline -- a refusal is a result, and the badge says so |
| `drift` | `verify` exited 4 | not "the numbers moved slightly": the tree cannot reproduce what it publishes |
| `not-run` | no verdict was produced -- no CLI, no network, a usage error, a shallow checkout for `ref`, or a missing denominator line | never a pass |

`fail_on` defaults to `drift,not-run`: exit 4 fails the job, exit 3 is reported rather than red, and a run
that produced no verdict is never green. Add `not-certifiable` to make a refusal fail the job as well.

**What the PR comment is, and is not.** F8 rule 4 asks for a bound-versus-previous-bound diff with both
denominators. The shipped `autorate compare` prints each side's own `n_cal` / `n_eval` but states in its
own source that it "has no authority to pair anything", and returns a usage error rather than a
before/after table when the two certificates were frozen under different protocols. The comment therefore
quotes the command's output verbatim, carries both denominators as the tool printed them, and says plainly
that it computes no bound; claiming a bound diff would assert a capability the tool does not have
(PRD §13.3 item 4). When no certificate under `data/` changed — the usual case here — the comment says
`not-run`, and a comment that cannot be delivered is a named `not-run` in the job summary rather than a
silent stderr line. The literal rule 4 wording is recorded as a deviation in the milestone report.

Two things about checkouts, because both have already broken this repository's CI once:

- Every checkout in a workflow that uses the action sets `fetch-depth: 0`
  ([`.github/workflows/action-gate.yml`](.github/workflows/action-gate.yml)). A shallow runner keeps one
  commit in its object database, so `git show <rev>:<path>` fails there while passing in every real clone.
  The action reads `protocol.json` from the working tree and states, in the job summary, which store it
  read the *base revision* from: `history source: object-db` (full history), `shallow`, or `no-object-db`.
  `tests/test_action_f8.py` refuses both a workflow that drops the flag and a summary that stops saying it.
- The committed badge in `.github/badges/` is produced by the same code path the action runs, and it
  records the protocol digest it was minted under. A re-freeze makes it stale and the test that reads it
  goes red rather than leaving a green pill describing a superseded protocol.

  It is minted in the **corpus-absent** lane, because that is the lane a clone and the runner see: the
  corpus is not in the repository, so a stranger reproduces `re-derived 612 /612 values`, and the badge
  carries that number and `corpus absent` in its tooltip and in `autorate-badge.json`. On a machine that
  also holds the corpus the same command prints `re-derived 649 /649 values` and writes a badge saying
  `corpus present`; both are the tool's own labels, and the badge never carries one lane's number under
  the other lane's name. Re-mint the committed one from an export:

  ```bash
  exp=$(mktemp -d) && git archive HEAD | tar -x -C "$exp"
  (cd "$exp" && uv run --frozen python3 tools/action_report.py --path protocol.json --badge-dir badges)
  cp "$exp"/badges/autorate-badge.svg "$exp"/badges/autorate-badge.json .github/badges/
  ```

## Reproduction

`docs/RESULTS.md` is generated, never typed: `autorate report` emits it and `autorate
verify` re-derives every value in it and prints `re-derived N /N values`. It carries no
timestamp, so a re-run is byte-comparable, and it quotes no path or machine name, so a
machine without the corpus reproduces the same bytes -- which is what lets CI run the
gate at all.

`docs/REPORT.md` is the same kind of file for a reader who wants one document instead of
seven: `autorate report --full` emits it, `verify` re-derives it byte for byte under the same
rule, and every figure in it is read out of an artefact rather than typed into a sentence --
the certificate shape from `certificate.py`, the five gates from `protocol.json`'s `claims`
array, each refusal from the artefact that refused, the related work from the rows of
`docs/VERIFICATION.md` that are `verified`. The flag is additive on purpose: `autorate report`
with no flag still writes `docs/RESULTS.md`, byte for byte the file this gate has always
compared.

That fallback has a stated limit, and `verify` prints it: with the corpus absent, the
upstream `SOURCE.json` digests and the inventory snapshot are transcribed from
`data/inventory.md.json`, not recomputed. The snapshot is policed from the environment
that can see the corpus, where a stale key goes red.

Those two environments are not two speeds of the same gate, and the denominators `verify`
prints say so: `re-derived 612 /612 values` where the corpus is absent, `re-derived 649 /649
values` where it is present. Both exit 0, both are green, and they are not the same claim.

The corpus is not a committed file. It is the sibling `laya*/research/benchmarks/feishu_zh`
checkout, which lives outside this repository, so a runner that checks out this repository
alone can never reach the 649: every CI run is a 612 run, on both of its arms. Green CI is
therefore evidence about the transcribed lane and nothing else.

A 612 run proves a lot inside that lane. Every published number that is a function of a
committed input re-derives there -- all seven published certificates, each from the committed
records it was actually made from, G4's slice run from the four committed MASSIVE record files
it names inside itself, the whole
of `docs/RESULTS.md` byte for byte, `data/inventory.md` byte for byte, `docs/AUDIT.md` byte
for byte, `docs/SEVERITY.md` byte for byte, `docs/RESPLIT.md` byte for byte, `docs/SLICES.md` byte
for byte, `docs/CONTAMINATION.md` byte for byte, `docs/REPORT.md` byte for byte, and the MASSIVE rows
from their committed pin. What a 612 run
cannot prove is what its own disclosure says in so many words --
`this run cannot see whether that snapshot went stale`. The gap is exactly 37
checks: the 9 upstream `SOURCE.json` digests, the 26 snapshot keys a corpus-present run
recomputes instead of reading back. On a machine without the archive those 35 do not run at
all; the figures they would test exist there only as the transcription, so a snapshot that
had drifted from the corpus would agree with itself and report 612 /612.

So the corpus-present run is not a slower, fussier version of the CI job; it is the only one
in which the transcription has an owner, and it is a local obligation, run before a push,
because no runner can run it for you.

## The five criteria, and what this tree can show for each

v1 is defined by five criteria, G1–G5. `autorate verify` prints one line per criterion with a status that
can say no -- `not_certifiable`, `measured_not_bounded`, `not_measured` -- read from `protocol.json`, the
frozen protocol document, which is emitted by a command and never typed. The statuses below are what that
command prints at this revision; the document is their owner, so this section is a reading of it and not a
second place to keep them.

- **G1, at least three decision tasks certified at `autorate(α = 0.05)` with a 200-resplit empirical
  violation rate: `not_certifiable`.** Six decision tasks have been scored and their records committed;
  zero of the six yield a certificate, and the refusals are published as artefacts rather than rounded
  away. The binding quantity is the evaluation half's case count: the exact one-sided bound on a small
  number of automated cases sits above a 5% budget no matter how few are wrong. The criterion's second
  column is now measured and published rather than promised: `tools/resplit_experiment.py` re-splits every
  scored task 200 times at the rubric this freeze owns, and `data/resplit_200.json` with `docs/RESPLIT.md`
  carries what came out. All six published tasks certify in **0 of 200** splits, so their empirical violation
  rate is recorded as undefined with a zero denominator instead of being imputed as `0.000`; the one row that
  does produce a rate is the synthetic control (200 of 200 splits certify, rate 0.000 over 200 certificates),
  which tests the machinery and is labelled as nothing else. `verify` compares the artefact's own arithmetic —
  certificates plus refusals per task, the rate against its denominator, the rows against the splits — and the
  rubric it recorded against the freeze's, in both lanes. The row is still not close to met: the second column
  exists, the first is zero. What replaces the missing certificate is the ceiling, published rather than
  asserted: `tools/g1_feasibility.py` computes, for each pool size this checkout can actually build, how wide
  the exact one-sided bound is and what error rate would therefore be certifiable at `α = 0.05`, and
  `verify` recomputes every figure in both lanes from `src/autorate/tails.py` and the published certificates.
  So `not_certifiable` is now a measured claim about n and bound width, not an absence of an answer -- which
  is the outcome spec §14 names as a result ("bound width is a first-class output; 'the bound is useless
  here' *is* a certification result"). §14's kill criterion for this row is not evaluable rather than
  fired: its condition compares a worst-group certified `autorate` with 0.30, and with nothing certified there
  is no certified `autorate` to put in that comparison -- the same refusal that keeps the violation rate
  undefined. Both halves of the pivot are published now: the audit multiple G2 measures, and the
  contamination gap section 9 defines, frozen as `data/contamination_probe.json` with its interval and its
  `claim = False` (see the G4 bullet). So the headline this project ships is the audit multiple G2
  measures and the worst-slice refusal G4 names. Read the G1 row as unmet; that is what it says.
- **G2, the reference README's gate demonstrably violating its implied error rate: `measured_not_bounded`.**
  `autorate audit` measures the gate upstream instructs and `docs/AUDIT.md` publishes the multiplier, but the
  sample cannot bound the claim: on the 2 cases one backend automates, one is wrong, and the exact one-sided
  bound is 0.975. The point estimate misses upward; what the corpus says is that it cannot carry the claim.
- **G3, at least one ordinal guarantee multiclass conformal prediction cannot express: `not_measured`.** The
  one-sided severity certificate (`P(Y > â(X)) ≤ α`, three canonical bounds, its own refusal reasons) is a
  command, an artefact and a gate row now: `autorate severity` writes `data/cert_severity_ordinal.json` from
  the committed ordinal population, `docs/SEVERITY.md` renders it from those bytes, and `verify` re-derives
  every published quantity of it in both lanes. The status does not move, because the criterion is a contrast
  and not a certificate. A first measured contrast is committed (`tests/test_g3_contrast.py`): on the published
  ordinal population, at the rubric this freeze owns, this repository's ordinal set gate refuses --
  `empty_feasible_set`, publishing no `qhat`, no automation rate and no error bound of any kind -- while the
  severity gate certifies the one-sided bound, reports its measured held-out violation rate and states the
  rule's price; the set gate refuses on all four population variants that file walks. That is silence in a
  named direction, and it is not the criterion -- because the criterion's own wording lost. On the corner of
  the generator where the set gate does certify (`shift = 0`, `error_rate = 0`; 4 of the 64 knob cells
  searched), its interval's top endpoint sits above the gold level in none of the 600 evaluated records
  (200 cases), so
  `P(Y > hi(X)) = 0` lies inside that certificate's own marginal bound of 0.014867 -- computed by
  `tests/test_g3_contrast.py`'s builder in memory and written to no artefact, which is why the digit names its
  producer instead of calling itself published: a coverage claim
  over ordered intervals *does* yield a one-sided bound, and "multiclass conformal prediction cannot express
  one" is false for that construction. The difference that survives is narrower, and it is measured rather
  than asserted: taking that rule costs reporting above the model's own modal level on a large share of cases
  and leaves 36 evaluated records with an empty certified set and so with no top endpoint at all, while the set
  certificate publishes no price, no override rate and no named rule -- the severity artefact certifies a rule
  and states both quantities beside its bound, at the same `delta`. The status stays `not_measured` because the
  criterion is the wider sentence, and the narrowing lives in the frozen document that carries it
  (`protocol.json`'s G3 note, at this digest) rather than in a re-worded criterion: retiring the wider wording
  is a decision with a new freeze, and this section reads its statuses off that document instead of keeping a
  second copy of them.
- **G4, worst-slice certification refusing rather than averaging: `not_met`.** The behaviour is published now
  rather than printed and discarded: `tools/language_slices.py` certifies the four committed MASSIVE record
  files (11,896 cases) as slices of `slices.language` -- the key the producer declares, not a key invented for
  the run -- and `verify` recomputes that run from the same bytes, 92 field comparisons plus 5 rubric
  rows, in
  both lanes. What it publishes is a refusal: 4 slices, 0 certified, each slice refused at
  the corrected budget (alpha and delta 0.05 / 4 = 0.0125, joint level 0.85), and `n_min_violations` empty --
  so this is a bound failure, not the size floor. The pooled marginal certificate over the same records is
  published beside the slices and refuses too, which is the "rather than averaging" half: nothing in the
  artefact lets the pooled number stand in for the worst slice. Two things keep the row short of met: it is
  per-language only, because `option_count` is 20 for every committed MASSIVE row -- Khmer included, measured
  across all 11,896 rows -- so the (language x option-count) cross the criterion names would be the same four
  slices; and the ranking the criterion's word `worst` asks for cannot be published from a run where
  nothing certifies: `run.worst_claim.worst.group` is `de`, but that is a tie-break, not a measurement -- its
  `run.worst_claim.metric` is `autorate`, and `autorate` is null in all four rows, so the artefact names a
  slice without demonstrating that it is the worst one. The slice the criterion names by example, Khmer, is no longer a gap:
  `data/records_massive_km.jsonl` commits 2,974 per-case rows and this tree measures it, refusing like the
  other three at the same rubric. Upstream's `accuracy 0.000 at mean confidence 0.952` remains upstream's own
  100-case read, which these 1,487 evaluated Khmer cases neither replicate nor contradict. What the run does
  say is the criterion's own word:
  every refused slice's summary carries `NOT_CERTIFIABLE: reason=empty_feasible_set`, and the command over
  these records exits 3, `EXIT_NOT_CERTIFIABLE`. The criterion's second named output is published beside
  that run: `tools/contamination_probe.py` pools `data/pin_app_benchmark.json` -- upstream's own per-suite
  `in_training` declarations, 27 usable rows and 3 excluded by name because their rounded rate is not a whole
  number of cases -- and publishes `delta_hat` = -0.235208 over [-0.262646, -0.207502], so the in-training
  stratum errs less and the interval is clear of zero. `verify` re-pools it (29 quantities plus 4 budget
  values in both lanes, and re-digests the upstream file where the corpus is visible), and the artefact's
  `claim` is false: the strata are different suites, so task difficulty is confounded with the flag and a gap
  between aggregate rates is a diagnostic, not a proof of leakage. The four marginal certificates, read from their own `detail`, are the at-a-glance version of
  the same evidence: `de` automates 0 of 1,487 cases (no singleton at that coverage, so nothing to bound);
  `en` automates 709 with 43 wrong, upper bound 0.078; `km` 11 with 5 wrong, 0.729; `sw` 39 with 13 wrong,
  0.477. Every non-empty slice is above the 0.050 budget, and none of the four certifies.
- **G5, reproducible from a commit with no GPU, no network, no model: `certified`, and the proof is a
  committed transcript.**
  `docs/G5.md` is the record: `tools/g5_export.sh` unpacks a `git archive` of commit `9e6363a` into a scratch
  directory with its own HOME and runs `autorate verify --protocol protocol.json` there --
  `249/249` values with the corpus absent at rc=0 and `284/284` with
  it present at rc=0, and four planted defects that each come back inside the documented
  exit-code contract (rc=2, 4, 4, 4) and are restored byte-identically with the restore
  checked. `tests/test_g5_transcript.py` refuses the file if a recorded code escapes the contract, if a
  lane's two halves disagree, if the digest printed is not the digest of the commit the transcript names,
  if the sentence counting the plants disagrees with the number of plant blocks, or if a single line still
  names a machine path. Both CI jobs run the `--protocol` form on every push, so each tip gets its own
  platform witness of the frozen comparison; `docs/G5.md` states that workflow fact without quoting a run
  id, because a run belongs to the push that produced it and the transcript names a commit instead.
  Three limits stay stated: the archive lane is a local obligation, the
  no-network claim covers the gate steps and not the dependency install, and the drift and contamination
  figures are unpublished, so they are absent from both denominators instead of re-derived.

The honest summary is that the gate's reproduction story is the strongest part of this tree today. G4's
slice criterion now has published evidence and is short of its own wording, not short of an artefact; the
ordinal criterion is the one whose engine, evidence and wording disagree in a measured way; and G1 remains
the criterion this corpus cannot meet at all.

## What is here, and what is not

The first paired certificate pair is published in `docs/RESULTS.md`: on the archived
Chinese workplace corpus **both backends refuse** at alpha = beta = 0.05, for different
reasons. One automates 2 of its 32 evaluation cases and one of those is wrong, so its case
bound is 0.975. The other automates all 32 with one wrong, and the exact case bound is 0.140
-- above a 0.05 budget. Even had that one request been right, a zero-error run over n=32
would have bounded at 0.089, so the corpus cannot support a 5% claim at any error count.

That is the result, not a shortfall: the corpus holds 64 independent cases, and the
project's own feasibility table -- computed as a scratch probe before any certificate was written, and now a
published artefact, `tools/g1_feasibility.py` writing `data/g1_feasibility.json` and `docs/FEASIBILITY.md`
with every figure recomputed by `verify` in both lanes -- said a 5% claim was out of reach here.
A tool that certified anyway would have been selling the exact thing this one
refuses to sell. Both evaluation halves cover the same 32 cases, so the pair is compared
case by case on identical inputs.

Covered by code and by tests: the `choice` primitive, marginal two-sided control, APS and LAC set sizes,
Clopper-Pearson one-sided bounds, and the gate that turns a certificate into
`auto` / `escalate` / `abstain`.

Written and tested, but not yet published as evidence: the threshold certifier (`certify_threshold.py`),
drift-adaptive conformal (`drift.py`), and the contamination stratification (`contamination.py`). Each of
them is a library with unit tests and no committed artefact that `verify` re-derives, which is the
difference between "implemented" and "certified" in this project -- see the criteria above. The
group-conditional (Mondrian) surface and its simultaneous per-slice correction
(`certify_choice.certify_groups`, `correction.py`) left that list when `tools/language_slices.py` published
`data/slices_language.json` and `docs/SLICES.md`: those are the artefacts the G4 row above is about, and
`verify` recomputes the run from the committed records field by field.

Published, re-derived, and still not the evidence its criterion asks for: the ordinal one-sided severity
certificate (`severity.py`), reachable as `autorate severity`, committed as `data/cert_severity_ordinal.json`
over `data/records_ordinal_synthetic.jsonl`, rendered into `docs/SEVERITY.md` and re-derived by `verify` in
both lanes. `claim G3` prints `not_measured` beside an artefact that exists, because the criterion is the
wider sentence -- "multiclass conformal prediction *cannot express* a one-sided ordinal guarantee" -- and the
control that would establish the contrast has now been run and did not go that way: at the corner of the
generator where the set gate certifies at all, its interval already yields the bound. What survives is
narrower and measured, and the narrowing lives in the frozen G3 note rather than in a re-worded criterion. Its
population is synthetic ordinal data with known answers: no committed records file in this checkout carries a
`qtype="score"` record, and the artefact's own envelope says so, so nothing here is a measurement of a shipped
model's ordinal risk.

Not implemented at all: per-ask `noul` budgets. The `noul` question type is read, counted and quarantined
by the same loaders as the others, and there is no certifier for it.

`docs/superpowers/specs/` states the design; `docs/superpowers/plans/` states the order.

Read `docs/ERRATA.md` before quoting any number from this project's history, and
`docs/VERIFICATION.md` for which external claims were checked against sources and which
were withdrawn.
