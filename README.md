# autorate

Certified automation rates for decision models: confidence is not permission.

A benchmark answers "how good is the model". A certificate answers a question an
operator can actually be held to: "what share of this model's decisions may run
unattended while keeping the probability that an automated decision is wrong at most
`beta`, given the held-out data we really have". When the data cannot support that
claim, `autorate` prints `NOT_CERTIFIABLE` with a reason code and the closest attempt
it made, and exits 3. It does not publish a number about nothing.

## What a certificate carries

`feasible`, `reason`, `alpha`, `beta`, `delta`, `level`, `method`, `grid_alpha`,
`autorate`, `autorate_ci`, `conditional_error_bound`, `marginal_error_bound`,
`refusal_rate`, `mean_set_size`, `qhat`, `n_cal`, `n_eval`, `envelope`, `meta`.

Two of those rows carry the whole argument:

- `conditional_error_bound` is `P(wrong | automated) <= beta`. `marginal_error_bound`
  is `P(wrong AND automated)`. They are different quantities, and a paper or a dashboard
  that quotes one while meaning the other is the failure mode this tool exists to stop.
- `envelope` is the machine-readable statement of what the bound assumed -- group
  conditioning, drift, and how empty sets were counted. A certificate read without its
  envelope is invalid output, so every printing path prints it.

`refusal_rate` and `mean_set_size` exist because an empty certified set is a refusal,
not a free correct answer: counting it as automation would inflate the rate.

## Commands

```bash
uv sync --frozen --extra dev

autorate export-feishu --out data/records_feishu.jsonl   # archive responses -> records
autorate certify data/records_feishu.jsonl --backend laya --out cert.json
autorate compare data/cert_laya.json data/cert_jev.json
autorate gate data/records_feishu.jsonl --cert data/cert_jev.json --limit 5
autorate report --out docs/RESULTS.md                    # write the published numbers
autorate verify                                          # re-derive them, fail on drift
```

Exit codes: `0` certified, `3` `NOT_CERTIFIABLE`, `2` usage error, `4` reproduced
number does not match the published one.

`export-feishu` reads the vendored corpus at `AUTORATE_FEISHU_ROOT`
(default `../laya-0.3.20/research/benchmarks/feishu_zh`). Everything else runs offline
on committed files; no command reaches the network.

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
Chinese workplace corpus, one backend certifies and the other refuses at the same
budgets. The refusal is the finding, not a defect -- a model that scores poorly on a
corpus should not be able to buy an automation rate on it.

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
