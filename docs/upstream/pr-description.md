# Prepared PR description — PR 1 of 2, not submitted

> **Status: drafted, not filed.** No branch was pushed, no PR was opened, no fork was created, and this
> text has not been pasted into any form. `SUBMISSION.md` names the human approval that would be needed
> first, and the 2026-10-14 re-measurement that changed what this PR would contain.

Per spec §13's upstream-channel order, this is **PR 1: the self-contained packaging fix**. The
confidence-semantics audit and the `laya` adapter follow as a **second, separate PR**, and this
description does not carry either of them — a PR that bundles a behavioural change with an audit of the
project's documentation is a PR a maintainer has to split before reading it.

## Title

`test(packaging): skip the repository suite when it is run from an unpacked sdist`

## Body

### What changes

`tests/test_packaging.py` reads `.github/workflows/ci.yml` and asserts that the `compose.*.yaml` files
exist. Neither is in the source distribution on PyPI, so `python3 tests/test_packaging.py` from an
unpacked sdist raises `FileNotFoundError` before the suite's first assertion, and the one check that
guards the published metadata cannot be run against the published artifact.

The change is a guard, not a new assertion: when `.github/workflows/ci.yml` is absent, print one line
saying the suite checks a git checkout and exit 0. The files are present in every checkout CI runs on,
so CI is unaffected; what changes is that `pip download --no-binary :all: laya` stops being a crash.

Shipping `.github/` and the compose files inside the sdist is the alternative, and it is the maintainer's
call — it puts CI configuration into every user's download, which is why this patch takes the
non-controversial guard instead.

### Evidence a reviewer can open

- `tests/test_packaging.py:196` (the 0.4.6 copy of the suite) reads `.github/workflows/ci.yml`;
  `:568-570` asserts six compose files exist; `:32` is the `open()` that raises.
- `laya-0.4.6.tar.gz` from the registry contains `laya/`, `tests/`, `laya.egg-info/`, `setup.py`,
  `setup.cfg`, `pyproject.toml`, `README.md`, `PKG-INFO`, `LICENSE`. It contains no `.github/` entry and
  no compose file — the only `compose` name in the listing is `tests/test_compose_env.py`.
- Reproduced on 2026-10-14 by unpacking that sdist and running the script from its root; exit 1,
  traceback ending in `FileNotFoundError: '<scratch>/laya-0.4.6/.github/workflows/ci.yml'`.

### Commands a reviewer can run

`<scratch>` is any empty directory the reviewer owns; `<repo>` is the `autorate` checkout holding
`docs/upstream/`. Nothing here needs a model, a GPU, or the corpus.

```sh
mkdir -p <scratch> && unzip -q laya-0.3.20.zip -d <scratch>       # the tag archive, commit 23a17522…
cd <scratch>/laya-0.3.20
git hash-object pyproject.toml laya/integrations/langchain.py tests/test_langchain.py tests/test_packaging.py
git apply --check --verbose -p1 <repo>/docs/upstream/patch/laya-0.3.20-fixes.patch   # rc=0, four lines
```

The four blobs the check compares against are the `v0.3.20` tag's own, listed with both sources in
`patch/README.md`.

### Scope, and what this PR does not do

The patch under `docs/upstream/patch/` is the four-finding diff written against a clean `v0.3.20`
checkout, and it still touches four files: `pyproject.toml`, `laya/integrations/langchain.py`,
`tests/test_langchain.py`, `tests/test_packaging.py`. Re-measuring `main` on 2026-10-14 found that three
of its four findings had already been taken upstream — `1c3360d5` / PR #504 for the `onnx` extra,
PR #598 and `0a06f662` for the guardrail score cutoff, `4e552251` and `93bf34a6` for which field the
router gate reads. Filing the diff as-is would re-propose code that has already moved, in a shape
upstream did not choose. **So this PR must be rebased onto `main` and reduced to the packaging guard
before submission**; the full four-finding diff is kept here because the reproduction condition in the
section below is stated against it, and because `patch/README.md` records which hunks are now dead.

This PR does not change any runtime behaviour, does not touch `laya/common.py`, does not add a
dependency, does not propose a calibration, and does not carry the `laya` adapter or the
confidence-semantics audit — those are the second, separate PR.

### What this PR does not claim

No number from the guardrail severity observation appears in this description or anywhere in
`docs/upstream/`. Its ledger row is `id=guard-preset-overlap`, whose ledger status is `withdrawn`, and
spec §7.1 permits those figures back into a report, README or PR description only when all three
reproduction conditions hold. Measured in this tree on 2026-10-14:

| condition | measured | how |
|---|---|---|
| `patch_on_clean_checkout` | met | `git apply --check` exits 0 against a clean `v0.3.20` checkout whose four target blobs match the tag |
| `prompts_committed_as_records` | **not met** | no committed file under `data/` carries the guardrail prompts or their labels |
| `ranges_rederived_by_verify` | **not met** | neither `protocol.json` nor `src/autorate/` names the guardrail question, so `autorate verify` re-derives no such range |

Because a condition is unmet, the claim stays `withdrawn`, and the report does not quote it. That is not
a hedge added for this description's benefit: the same three measurements are what
`tests/test_upstream_artifacts.py` re-runs on every test session, so the sentence cannot outlive the
state of the tree.

### The second PR, stated so this one stays clean

Spec §13 fixes the order — patch first, then the §7 confidence-semantics audit and the adapter as a
second, separate PR. The re-measurement on 2026-10-14 moved that one too: `main`'s README no longer
presents a literal threshold as permission to act (PR #378, merged 2026-09-24; upstream issue #394,
closed), the option-count non-transferability of the gate is documented in the tree, and the router now
gates on `answer_confidence` fail-closed. What the audit would still own is the certified half — a
finite-sample bound carried with each answer — and this directory does not draft that PR, because its
opening sentence would have to be written against a tree this repository has not re-read since
2026-10-14.
