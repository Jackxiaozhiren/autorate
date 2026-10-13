# autorate

Certified automation rates for decision models: confidence is not permission.

A benchmark answers "how good is the model". A certificate answers a question an
operator can actually be held to: "what share of this model's decisions may run
unattended while keeping the probability that an automated decision is wrong at most
`beta`, given the held-out data we really have". When the data cannot support that
claim, `autorate` prints `NOT_CERTIFIABLE` with a reason code, the observation at the
requested coverage that caused it, and a diagnostic sweep of the neighbouring coverage
levels -- evidence for the refusal, not a certificate. It exits 3 and does not publish a
number about nothing.

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

## Reproduction

`docs/RESULTS.md` is generated, never typed: `autorate report` emits it and `autorate
verify` re-derives every value in it and prints `re-derived N /N values`. It carries no
timestamp, so a re-run is byte-comparable, and it quotes no path or machine name, so a
machine without the corpus reproduces the same bytes -- which is what lets CI run the
gate at all.

That fallback has a stated limit, and `verify` prints it: with the corpus absent, the
upstream `SOURCE.json` digests and the inventory snapshot are transcribed from
`data/inventory.md.json`, not recomputed. The snapshot is policed from the environment
that can see the corpus, where a stale key goes red.

Those two environments are not two speeds of the same gate, and the denominators `verify`
prints say so: `re-derived 166 /166 values` where the corpus is absent, `re-derived 201 /201
values` where it is present. Both exit 0, both are green, and they are not the same claim.

The corpus is not a committed file. It is the sibling `laya*/research/benchmarks/feishu_zh`
checkout, which lives outside this repository, so a runner that checks out this repository
alone can never reach the 201: every CI run is a 166 run, on both of its arms. Green CI is
therefore evidence about the transcribed lane and nothing else.

A 166 run proves a lot inside that lane. Every published number that is a function of a
committed input re-derives there -- all six published certificates, each from the committed
records it was actually made from, the whole
of `docs/RESULTS.md` byte for byte, `data/inventory.md` byte for byte, `docs/AUDIT.md` byte
for byte, `docs/SEVERITY.md` byte for byte, `docs/RESPLIT.md` byte for byte, and the MASSIVE rows
from their committed pin. What a 166 run cannot prove is what its own disclosure says in so
many words -- `this run cannot see whether that snapshot went stale`. The gap is exactly 35
checks: the 9 upstream `SOURCE.json` digests and the 26 snapshot keys a corpus-present run
recomputes instead of reading back. On a machine without the archive those 35 do not run at
all; the figures they would test exist there only as the transcription, so a snapshot that
had drifted from the corpus would agree with itself and report 166 /166.

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
  violation rate: `not_certifiable`.** Five decision tasks have been scored and their records committed;
  zero of the five yield a certificate, and the refusals are published as artefacts rather than rounded
  away. The binding quantity is the evaluation half's case count: the exact one-sided bound on a small
  number of automated cases sits above a 5% budget no matter how few are wrong. The criterion's second
  column is now measured and published rather than promised: `tools/resplit_experiment.py` re-splits every
  scored task 200 times at the rubric this freeze owns, and `data/resplit_200.json` with `docs/RESPLIT.md`
  carries what came out. All five published tasks certify in **0 of 200** splits, so their empirical violation
  rate is recorded as undefined with a zero denominator instead of being imputed as `0.000`; the one row that
  does produce a rate is the synthetic control (200 of 200 splits certify, rate 0.000 over 200 certificates),
  which tests the machinery and is labelled as nothing else. `verify` compares the artefact's own arithmetic —
  certificates plus refusals per task, the rate against its denominator, the rows against the splits — and the
  rubric it recorded against the freeze's, in both lanes. The row is still not close to met: the second column
  exists, the first is zero.
- **G2, the reference README's gate demonstrably violating its implied error rate: `measured_not_bounded`.**
  `autorate audit` measures the gate upstream instructs and `docs/AUDIT.md` publishes the multiplier, but the
  sample cannot bound the claim: on the 2 cases one backend automates, one is wrong, and the exact one-sided
  bound is 0.975. The point estimate misses upward; what the corpus says is that it cannot carry the claim.
- **G3, at least one ordinal guarantee multiclass conformal prediction cannot express: `not_measured`.** The
  one-sided severity certificate (`P(Y > â(X)) ≤ α`, three canonical bounds, its own refusal reasons) is a
  command, an artefact and a gate row now: `autorate severity` writes `data/cert_severity_ordinal.json` from
  the committed ordinal population, `docs/SEVERITY.md` renders it from those bytes, and `verify` re-derives
  twenty comparisons of it in both lanes. The status does not move, because the criterion is a contrast and
  not a certificate. A first measured contrast is committed (`tests/test_g3_contrast.py`): on the published
  ordinal population, at the rubric this freeze owns, this repository's ordinal set gate refuses --
  `empty_feasible_set`, publishing no `qhat`, no automation rate and no error bound of any kind -- while the
  severity gate certifies the one-sided bound, reports its measured held-out violation rate and states the
  rule's price; the set gate refuses on all four population variants that file walks. That is silence in a
  named direction, and it is not yet the criterion. For an interval `C(X) = [lo, hi]` a coverage claim would
  bound `P(Y > hi(X))` directly, so "cannot express" needs a population where the set gate *does* certify and
  its published fields still fail to bound the one-sided risk of the rule it deploys. Such populations exist:
  4 of the 64 knob combinations this project searched (the perfectly-calibrated corner, `shift = 0` and
  `error_rate = 0`) let the set gate certify, so the experiment is answerable and has not been run. If that experiment shows the set
  gate expresses the statement after all, the honest outcome is that G3 fails and the claim is removed rather
  than reworded.
- **G4, worst-slice certification refusing rather than averaging: `not_measured`.** The mechanism is on the
  CLI (`certify --groups`, plus the simultaneous correction), and a slice below the size floor is refused by
  name with its case count; what is missing is a published artefact for a slice this project scored. The two
  collapsed slices the project measured (`de` automates 0 of 1,487 cases; `sw` 39 with 13 wrong) are
  published as marginal certificates, not as slice certificates, and the slice the criterion names by name
  has no per-case data in this tree.
- **G5, reproducible from a commit with no GPU, no network, no model: `not_measured` at the freeze.**
  `autorate verify --protocol protocol.json` is now a real command, `protocol.json` is committed and frozen,
  every published certificate carries its digest inside, and the corpus-less reproduction has been measured
  inside a clean `git archive` export. What is still missing is the transcript that makes that a published
  measurement rather than a local run, and CI's own witness of the current tip. The status line stays
  `not_measured` until both exist: it is the frozen document's word, and re-stating a criterion is a new
  freeze, not an edit.

The honest summary is that the gate's reproduction story is the strongest part of this tree today, and the
ordinal and slice criteria are the weakest: their engines exist, their evidence does not.

## What is here, and what is not

The first paired certificate pair is published in `docs/RESULTS.md`: on the archived
Chinese workplace corpus **both backends refuse** at alpha = beta = 0.05, for different
reasons. One automates 2 of its 32 evaluation cases and one of those is wrong, so its case
bound is 0.975. The other automates all 32 with one wrong, and the exact case bound is 0.140
-- above a 0.05 budget. Even had that one request been right, a zero-error run over n=32
would have bounded at 0.089, so the corpus cannot support a 5% claim at any error count.

That is the result, not a shortfall: the corpus holds 64 independent cases, and the
project's own feasibility table said a 5% claim was out of reach before any certificate was
written. A tool that certified anyway would have been selling the exact thing this one
refuses to sell. Both evaluation halves cover the same 32 cases, so the pair is compared
case by case on identical inputs.

Covered by code and by tests: the `choice` primitive, marginal two-sided control, APS and LAC set sizes,
Clopper-Pearson one-sided bounds, and the gate that turns a certificate into
`auto` / `escalate` / `abstain`.

Written and tested, but not yet published as evidence: the threshold certifier (`certify_threshold.py`),
the group-conditional (Mondrian) surface and its simultaneous per-slice correction
(`certify_choice.certify_groups`, `correction.py`), drift-adaptive conformal (`drift.py`), and the
contamination stratification (`contamination.py`). Each of them is a library with unit tests and no
committed artefact that `verify` re-derives, which is the difference between "implemented" and "certified"
in this project -- see the criteria above.

Published, re-derived, and still not the evidence its criterion asks for: the ordinal one-sided severity
certificate (`severity.py`), reachable as `autorate severity`, committed as `data/cert_severity_ordinal.json`
over `data/records_ordinal_synthetic.jsonl`, rendered into `docs/SEVERITY.md` and re-derived by `verify` in
both lanes. `claim G3` prints `not_measured` beside an artefact that exists, because G3 asks for a guarantee
multiclass CP *cannot express* and the control that would establish the contrast has not been run. Its
population is synthetic ordinal data with known answers: no committed records file in this checkout carries a
`qtype="score"` record, and the artefact's own envelope says so, so nothing here is a measurement of a shipped
model's ordinal risk.

Not implemented at all: per-ask `noul` budgets. The `noul` question type is read, counted and quarantined
by the same loaders as the others, and there is no certifier for it.

`docs/superpowers/specs/` states the design; `docs/superpowers/plans/` states the order.

Read `docs/ERRATA.md` before quoting any number from this project's history, and
`docs/VERIFICATION.md` for which external claims were checked against sources and which
were withdrawn.
