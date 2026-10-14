# The four-finding patch, and what "a clean checkout" has to mean

**Prepared, not submitted.** `../SUBMISSION.md` names the approval this needs before any of it leaves
the machine, and carries the dated read-only re-measurement (2026-10-14) that found three of the four
findings already taken upstream. Nothing in this directory has been filed, pushed, commented on, or
turned into a branch on a remote.

## The diff

| | |
|---|---|
| file | `laya-0.3.20-fixes.patch` |
| sha256 | `e1aad33a46a62a2066037f74a41228cad0384e47bfe69827d952486e095b5c76` |
| shape | 171 lines, 4 files, `-p1`, no mode-only hunks |
| revision it expects | tag `v0.3.20` → tag object `412531034634775c2c102fac8d160e84203cfae4` → commit `23a17522aa4942da6cce53a995a275760320b691` |
| authored against | the published `laya==0.3.20` source distribution; re-checked here against the tag tree |
| provenance | the author's off-tree file, copied byte-for-byte; the copy in this directory is what `SUBMISSION.md` pins by digest |

The four target files, and the blob each must carry before the patch means anything. Both columns were
read on 2026-10-14: the left from the repository contents API at `ref=v0.3.20`, the right from
`git hash-object` over a scratch copy of the downloaded tag archive. They agree, which is what makes
"clean checkout" a measurement instead of an adjective.

| file | blob at `v0.3.20` | scratch copy, same day |
|---|---|---|
| `pyproject.toml` | `ee375c7114df2d2465f46664eec14042553ff107` | `ee375c7114df2d2465f46664eec14042553ff107` |
| `laya/integrations/langchain.py` | `f7e5cb9bb42c6804d38a380e79bdfb52a79c70db` | `f7e5cb9bb42c6804d38a380e79bdfb52a79c70db` |
| `tests/test_langchain.py` | `ad12bf45175613626776ecd8244c26fc4a19f451` | `ad12bf45175613626776ecd8244c26fc4a19f451` |
| `tests/test_packaging.py` | `5a133cb95db194309461fe189f87c1fc9ff2092c` | `5a133cb95db194309461fe189f87c1fc9ff2092c` |

## What each finding asserts, and where a reader can check it without running anything

Every line anchor is the pristine `v0.3.20` tree, not the patched one.

| # | finding | the code that shows it | status measured at `main`, 2026-10-14 |
|---|---|---|---|
| 1 | the `onnx` extra declares a dependency set for an export path the distribution does not carry | `pyproject.toml:52` reads `onnx = ["onnx", "onnxruntime"]`; `scripts/export_onnx.py:63` calls `torch.onnx.export(`; the published `laya-0.3.20.tar.gz` and `laya-0.4.6.tar.gz` both contain no `scripts/` entry | **taken upstream** — commit `1c3360d5` (2026-09-25) `fix(packaging): the onnx extra must declare onnxscript`, merged as PR #504, released in 0.3.21; `main`'s `pyproject.toml:70` declares `onnxscript` |
| 2 | `LayaGuardrail` compares a `score` answer against the same cutoff it uses for `noul` probabilities | `laya/integrations/langchain.py:343` gates `ans["score"] >= self.threshold`, with `threshold: float = 0.5` at `:268`; `laya/presets.py:97` makes `harm_severity` a `score` question over 4 anchors, i.e. a 0..3 range, so the default cutoff sits low on that scale and not at the middle of a probability | **taken upstream** — PR #598 (merged 2026-09-27) and commit `0a06f662` (2026-10-01) convert the ordinal answer to an upper-half violation probability before the comparison; `tests/test_langchain.py:133` pinned the mock at a single low score, and `main`'s suite now shapes a score answer the way the decoder returns one |
| 3 | `tests/test_packaging.py` only runs in a git checkout, in two different ways | (a) its markdown walk prunes four directory names at `:121-122` and not the virtualenv the README tells contributors to create; (b) it reads `.github/workflows/ci.yml` at `:84` and asserts five `compose.*.yaml` files exist at `:200-203`, neither of which the sdist ships | **(a) taken, (b) still live** — `main` prunes `.venv` (and `.hf-cache`), but the copy inside the published `laya-0.4.6.tar.gz` still reads `.github/workflows/ci.yml` at `:196` and asserts six compose files at `:568-570`, with no existence guard and no skip: that artifact ships neither |
| 4 | which field `LayaRouter`'s `confidence_threshold` gates on is a contract with no test | `main`'s docstring now states the rule and a `_gate_confidence` helper resolves it; at `v0.3.20` the class simply read `ans["confidence"]` (`laya/integrations/langchain.py:247`) while `common.py` documents two different quantities — `id=laya-confidence-docstrings` | **taken upstream** — commit `4e552251` (2026-09-29) `fix(integrations): gate thresholds on answer_confidence, never entropy confidence`, made fail-closed by `93bf34a6` (2026-09-30) |

So the patch as written is a `v0.3.20` artefact: three of its four findings have been fixed upstream in
a different shape than this diff proposes, and only finding 3(b) still describes the current release. A
submission would be rebased onto `main` and reduced to that finding, with the rest recorded as already
taken. `SUBMISSION.md` states the order and the dates.

## How to verify the patch applies — in a copy, never against the corpus

The vendored `laya-0.3.20` tree on the author's machine is read-only and already carries this patch in
`pyproject.toml` and `laya/integrations/langchain.py`, so it is not a clean checkout and applying
anything to it would write into the corpus. `<scratch>` below is any empty directory the reader owns;
`<repo>` is this repository.

```sh
# 1. Unpack a pristine v0.3.20 tree (the GitHub tag archive, commit 23a17522...).
mkdir -p <scratch> && unzip -q laya-0.3.20.zip -d <scratch>

# 2. Confirm the four target files are the tag's blobs before trusting the check.
cd <scratch>/laya-0.3.20 && git hash-object pyproject.toml laya/integrations/langchain.py \
    tests/test_langchain.py tests/test_packaging.py

# 3. Check without writing. `--check` exits 0 and prints one line per file.
cd <scratch>/laya-0.3.20 && git apply --check --verbose -p1 <repo>/docs/upstream/patch/laya-0.3.20-fixes.patch
```

`tests/test_upstream_artifacts.py` runs exactly that staging and `git apply --check` inside a scratch
copy on every test run, and re-reads the source digests afterwards to prove the check never wrote back.
The measured result recorded in `SUBMISSION.md` is `rc=0` over all four files.

## What this patch is not

The new cases it adds to `tests/test_langchain.py` carry the author's measured model outputs as their
mock values, and those outputs are the numbers of the withdrawn guardrail observation
(`id=guard-preset-overlap`, whose ledger status is `withdrawn`). Because two of spec §7.1's three
reproduction conditions are unmet — `prompts_committed_as_records` and `ranges_rederived_by_verify` —
the claim stays withdrawn, this repository's report does not quote it, and this directory does not
restate those values in prose either. A reviewer reading this file should treat the fixture values as
part of a proposed diff under the same embargo as the claim they came from, not as established
measurements.
