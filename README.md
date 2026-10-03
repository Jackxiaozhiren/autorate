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
- Both are over **cases**, not archive rows. Repeats of one case are one observation -- on
  this corpus each case appears three times per backend, and one backend's repeats are
  byte-identical -- so the `n` in every bound counts cases and the record counts are
  published beside it instead of standing in for it.
- `envelope` is the machine-readable statement of what the bound assumed -- coverage
  level, group conditioning, drift, and how empty sets were counted. A certificate read
  without its envelope is invalid output, so `certify`, `compare` and `gate` all print it.
- `alpha` is the coverage floor the certificate is held to, not a label on it. An earlier version
  swept a grid of coverage levels for the largest automation rate and tested the winner on
  the same evaluation half, then printed "at alpha=0.050" while operating at 0.89
  coverage. Selecting on the test half is snooping, so the set size now comes from the
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

Exit codes: `0` certified, `3` `NOT_CERTIFIABLE`, `2` usage error, `4` reproduced
number does not match the published one.

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

Covered: the `choice` primitive, marginal two-sided control, APS and LAC set sizes,
Clopper-Pearson one-sided bounds, and the gate that turns a certificate into
`auto` / `escalate` / `abstain`.

Not covered yet, and gated on a corpus large enough to bound them: the ordinal `score`
family and its one-sided severity certificate, per-ask `noul` budgets, group-conditional
(Mondrian) and simultaneous per-slice control, drift-adaptive conformal, and the
contamination stratification. `docs/superpowers/specs/` states the design;
`docs/superpowers/plans/` states the order.

Read `docs/ERRATA.md` before quoting any number from this project's history, and
`docs/VERIFICATION.md` for which external claims were checked against sources and which
were withdrawn.
