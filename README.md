# autorate

Certified automation rates for decision models: confidence is not permission.

An `autorate` certificate states how much of a decision model's traffic may run
unattended under a stated error budget, together with a finite-sample bound on
that claim. When the bound cannot be supported, the tool returns
`NOT_CERTIFIABLE` with a reason code rather than an unbounded number.

## Quickstart

```bash
uv sync --frozen --extra dev
uv run --frozen pytest -q
```
