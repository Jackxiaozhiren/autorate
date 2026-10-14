# Prepared issue text — not submitted

> **Status: drafted, not filed.** No issue has been opened on `NandhaKishorM/laya`; the author still has
> zero issues and zero PRs on that repository (re-checked 2026-10-14, see `SUBMISSION.md`). This file is
> the text that would be filed, rewritten against what a re-measurement found: of the four findings the
> original draft carried, **one** still describes the current release. Filing all four today would post
> three duplicates and a patch for code that has already moved.

---

## Title

`tests/test_packaging.py` cannot run from the published sdist: it reads `.github/workflows/ci.yml` and
asserts `compose.*.yaml` files that the artifact does not ship

## Body

Reported against the published source distributions of `laya`, Python 3.12, CPU, no model, no network.
This is a packaging-harness finding, not a runtime one: nothing about inference changes.

### What happens

`tests/test_packaging.py` is the suite that guards the PyPI metadata. It is a plain script that reads
repository files, and two of the things it reads are not in the artifact anyone gets from
`pip download --no-binary :all: laya`:

- it reads `.github/workflows/ci.yml` (line 196 in the 0.4.6 copy) to compare the CI matrix against
  `requires-python` and the advertised classifiers;
- it then asserts that six `compose.*.yaml` files exist (lines 568-570).

The sdist ships neither. Enumerating `laya-0.4.6.tar.gz` gives `laya/`, `tests/`, `laya.egg-info/`,
`setup.py`, `setup.cfg`, `pyproject.toml`, `README.md`, `PKG-INFO`, `LICENSE` — zero `.github/` entries
and one `compose` name, which is `tests/test_compose_env.py`, not a compose file. `laya-0.3.20.tar.gz`
is the same shape, and its copy of the suite reads `.github/workflows/ci.yml` at line 84 and asserts
five compose files at lines 200-203.

So the suite dies before its first assertion, and the check that exists to protect the published
metadata cannot be run against the published artifact:

```
$ python3 tests/test_packaging.py
rc=1
Traceback (most recent call last):
  File "<scratch>/laya-0.4.6/tests/test_packaging.py", line 196, in <module>
    workflow = read(os.path.join(".github", "workflows", "ci.yml"))
  File "<scratch>/laya-0.4.6/tests/test_packaging.py", line 32, in read
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
FileNotFoundError: [Errno 2] No such file or directory: '<scratch>/laya-0.4.6/.github/workflows/ci.yml'
```

Measured here, not transcribed: the 0.4.6 sdist was downloaded from the registry, unpacked, and the
script executed from its root on 2026-10-14. `<scratch>` is the directory the copy lived in; the
traceback is otherwise verbatim.

### Why it matters more than a skipped test

Anyone reproducing a packaging claim from the registry hits this crash instead of the assertion they
came for, and CI never sees it because CI runs in a checkout. The suite is the repository's own guard
on the PyPI metadata and it is the one check that is unreachable from the artifact being guarded.

### Proposed fix

Two ways, and the choice is yours:

1. **Guard it.** Skip the whole suite with one printed line when `.github/workflows/ci.yml` is absent,
   and exit 0. This is what the prepared patch in this directory's `patch/` does; it is non-controversial
   and it keeps the CI signal, since the files are present in every checkout CI runs on.
2. **Ship what the suite reads.** Put `.github/workflows/` and the compose files in the sdist, so the
   suite is meaningful from the artifact. This drags CI configuration into every user's download, which
   is why the prepared patch did not do it.

Either way, one adjacent observation while that file is open: the `onnx` extra describes an export path
whose script is not distributed. `pyproject.toml` declares the extra, `scripts/export_onnx.py` calls
`torch.onnx.export`, and the sdist carries no `scripts/` entry in either release, so installing
`laya[onnx]` from the registry yields a dependency set with nothing to run. The dependency declaration
itself was fixed by PR #504; the missing script is a separate question from that patch.

### The three findings this issue used to carry, and does not

The draft this file replaces reported four findings against `v0.3.20`. Re-measuring against the current
tree found upstream had already taken three of them, independently and in a different shape, so they are
recorded here as context rather than filed as bugs:

| finding | taken by | dated |
|---|---|---|
| the `onnx` extra did not declare `onnxscript` | commit `1c3360d5`, merged as PR #504 (`PerryLink/fix/onnx-extra-onnxscript`), released in 0.3.21 | 2026-09-25, merged 2026-09-27 |
| `LayaGuardrail` compared a `score` answer to the `noul` probability cutoff | PR #598 (`fix/guardrail-score-threshold`), then commit `0a06f662` gating a score question on its upper-half violation probability | merged 2026-09-27, 2026-10-01 |
| which field `confidence_threshold` gates on was undocumented and untested | commit `4e552251` (`gate thresholds on answer_confidence, never entropy confidence`), made fail-closed by `93bf34a6` via `_gate_confidence` | 2026-09-29, 2026-09-30 |

The `research/eval/` lane is, as it was, occupied by contributors who merge quickly; that is one reason
this text stays a reduction to the one finding that is still live rather than a bundle.

### What this issue does not claim

The guardrail severity anecdote that motivated the original draft is **not** in this text, and no number
from it appears anywhere in `docs/upstream/`. Its ledger row is `id=guard-preset-overlap`, whose ledger
status is `withdrawn`, and spec §7.1 allows it back only when all three reproduction conditions hold.
Two of them do not hold in this tree, measured rather than asserted:

- `patch_on_clean_checkout` — **met**: `docs/upstream/patch/` applies to a clean `v0.3.20` checkout
  (`git apply --check` exits 0 over all four files, with the four target blobs matching the tag);
- `prompts_committed_as_records` — **not met**: no committed record file under `data/` carries the
  guardrail prompts or their labels;
- `ranges_rederived_by_verify` — **not met**: neither `protocol.json` nor any module under
  `src/autorate/` names the guardrail question, so `autorate verify` re-derives no such range.

Because a condition is unmet, the claim stays `withdrawn`, and the report does not quote it. This issue
therefore rests only on what a reader can open in the tree: the suite's own line numbers, and the two
sdist listings.
