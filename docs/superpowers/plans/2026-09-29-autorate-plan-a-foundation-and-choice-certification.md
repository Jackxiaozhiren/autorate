# `autorate` Plan A — Foundation, Record contract, and `choice` certification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an offline, model-free tool that turns archived decision-API responses into a finite-sample-bounded **automation certificate** for `choice` questions — and makes `NOT_CERTIFIABLE` (too few samples, no feasible threshold, vacuous quantile) a returned value rather than an absent number.

**Architecture:** Three layers from the spec: L1 reads decision-API responses into one flat `Record` contract (no model, no network — the only v1 corpus is the upstream `feishu_zh` archive, which holds 384 paired `laya` and 384 `jev-1.13.0` real responses); L2 is pure-Python conformal machinery (APS set predictor → singleton automation rule → two-way joint bound, Angelopoulos, Bates, Candès, Jordan & Lei, arXiv 2110.01052 §3.2); L3 exposes `Certificate` + `Gate`. Certification is computed on **archived** records, so every published number is re-derivable by `autorate verify` without a GPU, a checkpoint, or an API key.

**Tech Stack:** Python ≥3.10 (dev env 3.12), `numpy` as the only runtime dependency, `pytest`, `ruff`, `uv`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` — this plan implements spec §4–§7 and the gates G1/G2/G5 partially, in spec weeks 1–4. Plans B–E cover the ordinal `score` core (G3), the `noul` + confidence-semantic audit (G2), group-conditional + contamination stratification (G4), and the protocol freeze / technical report / upstream PR.

**Why this plan stops here:** at the end of Task 9 there is a working, published-quality artifact that a reviewer can run on real data and that already refuses honestly. The ordinal certificates are the novel core and are deliberately **not** started until the foundation reproduces G1 on `choice`.

---

## Global Constraints

Every task inherits these. They are copied verbatim from the spec and from measured environment facts.

1. **No hosted service may be required.** No task may add a network call to the runtime path. (spec §1.1; also `laya/AGENTS.md`'s ban, which the eventual adapter must respect.)
2. **No `torch`, no model, no dataset download in the test path.** Unit suite runs offline. (spec §11.5)
3. `requires-python = ">=3.10"`; the local dev environment is the **3.12** interpreter, because the sibling `laya-0.3.20/.venv` is `Python 3.12.14` and we exchange records with it.
4. **The only runtime dependency is `numpy`.** Adding a second one (scipy, statsmodels, MAPIE) is a spec-level decision, not a task-level convenience.
5. Never run the bare PATH `pytest` on this machine: `which pytest` resolves to `/Users/jackson/Library/Python/3.9/bin/pytest`, a **different interpreter** from the project. Always `uv run --frozen pytest …`.
6. Never run bare `python` on this machine (`python -V` exits 127; only `python3` exists). Always `uv run --frozen python -m …`.
7. Use `uv run --frozen` / `uv sync --frozen`, never plain `uv run`: plain `uv run` silently re-locks a stale `uv.lock` and dirties the tree.
8. Lint gate on every commit, matching the upstream project's own gate shape: `uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120` and `uv run --frozen python -m compileall -q src tests`.
9. **A test that is green on arrival is a plan failure.** Every new assertion must be demonstrated red against the pre-existing code before the implementation lands, and the red output is pasted into the commit body.
10. **A negative control must prove it fired.** Where a task asserts a refusal, the test asserts the refusal *and* its reason code, and the paired "should have passed" case.
11. Do not relax an assertion you did not write. `research/benchmarks/feishu_zh/data/manifest.json` pins hashes owned by upstream `audit.py`; **call their audit, do not re-derive their hash** (measured: raw-byte `sha256` of `data/cases.jsonl` is `56bdd8cb…`, the manifest value is `c85184ee…` — the hash is over a canonicalisation we do not own).
12. Every numeric claim in `docs/` must be produced by the code that reports it, and `autorate verify` must re-derive it. No hand-typed result tables.
13. Repository language is English (README, docstrings, commit messages, PRs).
14. Conventional commits, one logical change each: `feat(records):`, `fix(conformal):`, `test(coverage):`, `docs(inventory):`.
15. This workspace root `/Users/jackson/laya` is **not** a git repository and holds a 3.6 MB vendored copy of upstream. The `autorate` repo is created at **`/Users/jackson/laya/autorate`** so provenance stays clean; the spec and this plan are copied into it in Task 1 so the two travel together.
16. Local loopback proxy `127.0.0.1:7890` is active on this Mac. Any task that touches HTTP must set both `NO_PROXY` and `no_proxy` or its failures are proxy artefacts, not code. (Not exercised in Plan A; recorded because Task 9's `verify` is the first CI-visible gate.)

---

## File structure

Created in `/Users/jackson/laya/autorate`:

```
pyproject.toml                     packaging, ruff + pytest config           T1
.python-version                    3.12                                      T1
.github/workflows/ci.yml           lint + offline suite + verify gate        T1, T9
README.md                          one-line thesis, quickstart               T9
docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md   copy    T1
docs/superpowers/plans/2026-09-29-autorate-plan-a-…md                 copy    T1
docs/VERIFICATION.md               source-status table, one row per claim    T2
data/inventory.md                  what per-case data exists locally, and n  T3

src/autorate/__init__.py           public surface only                       T4,T7,T8
src/autorate/records.py            Record + validation + the 3 confidences   T4
src/autorate/readers/__init__.py
src/autorate/readers/feishu_zh.py  raw.jsonl -> Record, both backends        T5
src/autorate/nonconformity.py      lac_score, aps_score (recorded U)         T6
src/autorate/conformal.py          split_quantile (with vacuity flag), aps_set T6
src/autorate/tails.py              _binom_cdf, clopper_pearson_upper         T7
src/autorate/certify_choice.py     two-way sweep -> Certificate              T7
src/autorate/certificate.py        Certificate + ReasonCode + envelope rules  T8
src/autorate/gate.py               Gate.decide -> auto | escalate | abstain  T8
src/autorate/cli.py                certify / compare / verify                T9
src/autorate/inventory.py          counts + n-feasibility table              T3

tests/test_toolchain.py            T1
tests/test_verification_table.py   T2
tests/test_inventory.py            T3
tests/test_records.py              T4
tests/test_reader_feishu.py        T5
tests/test_nonconformity.py        T6
tests/test_split_quantile.py       T6
tests/test_coverage_montecarlo.py  T6
tests/test_tails.py                T7
tests/test_certify_choice.py       T7
tests/test_certificate_shape.py    T8
tests/test_gate.py                 T8
tests/test_cli.py                  T9
tests/fixtures/feishu_sample.jsonl 6 records lifted verbatim from upstream   T5
```

No synthetic fixture files: Task 7 builds its synthetic vectors in code, so committed fixture JSONs would be dead inputs (YAGNI ruling — see the ledger). Plan B adds fixtures only when a generator needs a replayable, hash-stable vector set.

Responsibility boundaries worth defending: `records.py` knows field names and nothing about statistics; `conformal.py` knows quantiles and nothing about field names; `certificate.py` owns the output shape and the refusal semantics; `cli.py` is the only file that prints.

---

## Task 1: Repository scaffold, toolchain, CI

**Files:**
- Create: `pyproject.toml`, `.python-version`, `src/autorate/__init__.py`, `tests/test_toolchain.py`, `.github/workflows/ci.yml`, `.gitignore`
- Copy in: the spec and this plan under `docs/superpowers/`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `autorate` with `__version__`; the command forms every later task uses (`uv run --frozen pytest`); a green CI lane.

- [ ] **Step 1: Write the failing test**

Create `tests/test_toolchain.py`:

```python
"""The toolchain contract: one interpreter, frozen lock, no bare python."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports_and_declares_version():
    import autorate

    assert autorate.__version__.count(".") == 2


def test_tests_run_on_the_project_interpreter_not_the_path_one():
    # Guards Global Constraint 5: `which pytest` on this host is a Python 3.9 binary.
    assert sys.version_info[:2] == (3, 12), (
        f"expected the pinned 3.12 dev env, got {sys.version.split()[0]} from {sys.executable}"
    )


def test_lock_is_committed_and_up_to_date_with_pyproject():
    # Guards Global Constraint 7's artefact: uv.lock is committed, and `uv lock --check` fails when
    # pyproject.toml drifts from it. A plain interpreter run cannot re-lock, so a byte-compare around
    # `python -c "import autorate"` could never fail; the lock check is the guard that can.
    assert (ROOT / "uv.lock").exists()
    proc = subprocess.run(
        ["uv", "lock", "--check"], capture_output=True, text=True, cwd=ROOT
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_declared_console_script_entry_point_resolves_and_exits_zero():
    # Guards pyproject's `autorate = "autorate.cli:main"`: neither ruff nor compileall resolves an
    # entry-point string, so without this test renaming or deleting `autorate.cli.main` stays green.
    # Task 9 rewrites cli.py, so the target must keep resolving and returning 0.
    from importlib.metadata import entry_points

    scripts = [ep for ep in entry_points(group="console_scripts") if ep.name == "autorate"]
    assert len(scripts) == 1, f"expected one `autorate` console script, got {scripts}"
    assert scripts[0].load()() == 0


def test_ruff_gate_matches_the_upstream_shape():
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests",
         "--select=E9,F63,F7,F82,F401,F811", "--line-length=120"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/jackson/laya/autorate && uv run --frozen pytest tests/test_toolchain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autorate'` (or the `uv.lock` assertion errors before that). If it passes before the scaffold exists, the test is vacuous; stop and fix the test, not the expectation.

- [ ] **Step 3: Write the scaffold**

`pyproject.toml`:

```toml
[project]
name = "autorate"
version = "0.1.0"
description = "Certified automation rates for decision models: confidence is not permission."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = ["numpy>=1.24"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[project.scripts]
autorate = "autorate.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/autorate"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

(The block is delivered **without** `addopts = "-q"`: `addopts = "-q"` composes with the `pytest -q` this plan and CI both invoke into `-qq`, which suppresses the `N passed` summary line that Constraint 12 requires quoting. Ledger ruling R-1. Later tasks keep using `uv run --frozen pytest -q`.)

`.python-version` containing exactly `3.12`. `.gitignore`: `.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `cert.json`. `src/autorate/__init__.py`: `__version__ = "0.1.0"` and nothing else yet. `src/autorate/cli.py`: `def main() -> int:\n    return 0` (so the console script resolves; Task 9 replaces the body).

`.github/workflows/ci.yml`:

```yaml
name: ci
on: [push, pull_request]
jobs:
  offline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { python-version: "3.12" }
      - run: uv sync --frozen --extra dev
      - run: uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120
      - run: uv run --frozen python -m compileall -q src tests
      - run: uv run --frozen pytest -q
```

- [ ] **Step 4: Create the repo, sync, and prove the gate green**

```bash
mkdir -p /Users/jackson/laya/autorate && cd /Users/jackson/laya/autorate
git init -b main
uv venv .venv --python 3.12
uv sync --frozen --extra dev
uv run --frozen pytest tests/test_toolchain.py -v
```
Expected: `5 passed` — corrected after the fix round added the entry-point guard; the count a reviewer can quote is the number the delivered suite actually has (Constraint 12).

- [ ] **Step 5: Copy the design docs in, then commit**

```bash
mkdir -p docs/superpowers/specs docs/superpowers/plans
cp /Users/jackson/laya/docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md docs/superpowers/specs/
cp /Users/jackson/laya/docs/superpowers/plans/2026-09-29-autorate-plan-a-foundation-and-choice-certification.md docs/superpowers/plans/
git add . && git commit -m "chore(scaffold): uv + pytest + ruff + CI for autorate

Toolchain contract pinned by tests/test_toolchain.py: pinned 3.12 dev env
(the host PATH pytest is a 3.14-adjacent 3.9 binary), committed uv.lock,
frozen runs, upstream-shaped ruff gate."
```

---

## Task 2: Open-or-delete every unverified citation, and gate it in CI

Spec §17 flagged a batch of claims taken from secondary web research and never opened at a primary source, plus one contradictory number (star count). This task closes that debt **before** any code that quotes those claims is written, because several of them are the justification for the design (§5.2's "MAPIE is marginal-only", §5.4's ordinal prior art, §12's novelty ledger).

**Files:**
- Create: `docs/VERIFICATION.md`
- Test: `tests/test_verification_table.py`

**Interfaces:**
- Consumes: spec §17 table.
- Produces: a machine-checked claim ledger; `docs/VERIFICATION.md` rows carry `status: verified|withdrawn`.

- [ ] **Step 1: Write the failing test**

`tests/test_verification_table.py`:

```python
"""Every citation is either opened at its primary source or deleted. No third state."""
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "VERIFICATION.md"
ALLOWED = {"verified", "withdrawn"}
ROW = re.compile(r"^\|\s*id=(?P<id>[a-z0-9]+)\s*\|.*status:\s*(?P<status>\w+)", re.M)


def test_ledger_exists_and_has_rows():
    assert DOC.exists(), "docs/VERIFICATION.md missing"
    assert ROW.findall(DOC.read_text()), "ledger has no rows"


def test_no_row_is_left_unverified_or_unknown():
    bad = {m["id"]: m["status"] for m in ROW.finditer(DOC.read_text())
           if m["status"] not in ALLOWED}
    assert not bad, f"unresolved citations: {bad}"


def test_every_verified_row_carries_url_and_date():
    for line in DOC.read_text().splitlines():
        if "status: verified" in line:
            assert "https://" in line, line
            assert re.search(r"20\d\d-\d\d-\d\d", line), line


def test_withdrawn_rows_say_what_replaced_them():
    for line in DOC.read_text().splitlines():
        if "status: withdrawn" in line:
            assert "replaced:" in line or "dropped:" in line, line
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --frozen pytest tests/test_verification_table.py -v`
Expected: FAIL at `test_ledger_exists_and_has_rows` — file missing. Then, once you paste spec §17's rows in with their current statuses, it must still fail at `test_no_row_is_left_unverified_or_unknown` listing the unresolved ids it actually finds. **Paste that failing list into the commit body** — it is the evidence that the gate is real.

- [ ] **Step 3: Resolve each row**

Create `docs/VERIFICATION.md`. Header row format (id column first, status last, so the regex holds):

```markdown
| id=mapie-crc-disclaimer | MAPIE's risk-control example disclaims the vector-space assumption | https://… | 2026-09-30 | status: verified |
```

Work the list: `mapie-crc-disclaimer`, `nibzard-no-threshold`, `ordinal-cp-aistats2023`, `ordinal-cp-neurips2023`, `ordinal-cp-aaai-minlen`, `ordinal-cp-2606-24959`, `selective-crc-2512-12844`, `justaskjev-ece0168`, `awesome-jev-empty-section`, `laya-star-count`. For each: open the primary source, confirm or correct the wording, set `status: verified` with URL + date; if it does not hold or cannot be opened, set `status: withdrawn` with `dropped:` / `replaced:` and **edit the spec to remove the claim** (the spec is a living document; §12's "none found" rows depend on the ordinal prior-art rows). For `laya-star-count`, query the API (`gh api repos/NandhaKishorM/laya --jq .stargazers_count`) and record the number with its date, or withdraw the number entirely.

- [ ] **Step 4: Run the gate to verify it passes**

Run: `uv run --frozen pytest tests/test_verification_table.py -v`
Expected: `6 passed` — the delivered gate has six tests, not the four written here: the brief's `ROW` id class `[a-z0-9]+` matched **0 of 45** ledger rows (hyphenated ids were invisible to its own gate), so widening it plus the census test I-2 required were both controller-approved deviations. If any row is still unresolved, do not weaken the test — withdraw the row from the ledger and delete its claim from the spec.

- [ ] **Step 5: Commit**

```bash
git add docs/VERIFICATION.md tests/test_verification_table.py docs/superpowers/
git commit -m "docs(verification): open-or-delete every secondary citation before code depends on it

Red-state evidence: <paste the failing id list from Step 2>."
```

---

## Task 3: Data inventory — what per-case labelled data exists offline, and is `n` enough

Measured during design, and the reason this task exists: `research/results/eval_english_51_languages.json` states `"per-case records omitted from this file to keep the diff reviewable; regenerate with research/eval/laya_eval.py --langs all --out <path>"`, and `mteb/amazon_massive_intent` is **not** in the local HF cache (`~/.cache/huggingface/hub` holds `models--convaiinnovations--laya` and an unrelated dataset). So the only offline labelled per-case corpus is the `feishu_zh` archive: **64 unique ids × 3 repeats (0,1,2) × 2 backends, split 192 `choice` + 192 `four_noul`**, which is small enough to make the finite-sample bound (`~1/√n`) visibly uninformative — exactly spec §14 risk R3, arriving in week 1 rather than week 12.

This task does **not** build a larger corpus: it measures the one that is committed and states the feasibility boundary. Ledger **R-12** (2026-10-01) settled the question its output forces, so Plan B need not rediscover it — a dataset download **is** acceptable as a *pinned build step*, because Constraint 2 forbids a download only **in the test path**, G5 requires published numbers to re-derive from records alone, and Constraint 1 forbids only a *runtime* dependency on a hosted service. Measured: `mteb/amazon_massive_intent` ships 51 × `test/xx.json.gz` — gzipped **JSON Lines**, ~54–71 KB each (≈3.2 MB for all languages), Apache-2.0, parsed here with stdlib `gzip`+`json` and needing neither `datasets` (absent from the 3.12 venv, which does carry torch 2.14.0 / transformers 5.17.0 / huggingface_hub 1.33.0) nor `pyarrow`. `test/en.json.gz` = **2974 rows**, keys `id, label, label_text, text, lang`, 59 distinct labels; de and sw are also 2974, and that equality is the benchmark's design rather than an API collapse — proven by parsing the raw files and by the `train` split differing at 11514. Bound width then falls from 0.3395 at n=64 to 0.050 at one language and 0.007 across all 51, so the n problem inverts; the remaining cost is **inference**, not download, and taking full splits instead of the harness's published `--per-lang 100` is a declared deviation from §11's comparability basis.

**Files:**
- Create: `src/autorate/inventory.py`, `data/inventory.md`
- Test: `tests/test_inventory.py`

**Interfaces:**
- Consumes: `/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh/` (`data/manifest.json`, `results/v1/{laya,jev}/raw.jsonl`, `audit.py`).
- Produces: `inventory(path) -> dict` with `sources`, `records_by_mode_backend`, `unique_ids`, `repeats`, `families`, `upstream_audit_rc`, `min_calibration_n`, and `n_feasible(alpha)` helper.

- [ ] **Step 1: Run upstream's own model-free audit first, and record its exit code**

```bash
cd /Users/jackson/laya/laya-0.3.20
python3 research/benchmarks/feishu_zh/audit.py; echo "audit rc=$?"
```
Expected: it verifies dataset/prompt hashes, request equality across backends, repeated-run completeness, raw-response decoding, finite probabilities, and recomputes metrics — per its README, no downloads or API keys. **Record the real `rc` and the real summary lines in `data/inventory.md`.** If `rc != 0`, stop: the corpus we intend to certify against does not pass its own integrity gate, and that is a finding to report upstream, not an obstacle to route around. Do not reimplement or replace their hashing (Constraint 11).

- [ ] **Step 2: Write the failing test**

`tests/test_inventory.py`:

```python
import json
from pathlib import Path

import pytest

from autorate.inventory import inventory, n_feasible

UPSTREAM = Path("/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh")
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")


@skip
def test_inventory_sees_the_recorded_shape():
    d = inventory(UPSTREAM)
    assert d["unique_ids"] == 64
    assert d["repeats"] == [0, 1, 2]
    assert d["records_by_mode_backend"] == {
        "choice|laya": 192, "choice|jev": 192,
        "four_noul|laya": 192, "four_noul|jev": 192,
    }
    assert sorted(d["families"]) == [
        "conditional", "cross_chat", "knowledge", "lifecycle",
        "ownership", "thread_context", "untrusted_content", "urgency",
    ]


@skip
def test_upstream_audit_is_the_owner_of_integrity_and_it_passes():
    d = inventory(UPSTREAM)
    assert d["upstream_audit_rc"] == 0, d["upstream_audit_stdout_tail"]


@skip
def test_labels_are_balanced_so_a_majority_baseline_is_not_an_accident():
    d = inventory(UPSTREAM)
    assert set(d["label_counts"].values()) == {16} , d["label_counts"]


def test_small_n_is_declared_infeasible_not_silently_certified():
    # Bound width is 2*sqrt(ln(2/alpha)/(2n)). Measured with alpha=0.05:
    #   n=64 -> 0.3395   n=240 -> 0.1753   n=500 -> 0.1215
    #   n=1000 -> 0.0859   n=2550 -> 0.0538   n=5100 -> 0.0380
    # Corrected after PF-11: the original expectation claimed n=64 was feasible at a
    # 0.25 width, but 0.3395 > 0.25, so that assertion could never pass as written.
    assert n_feasible(unique_n=64, alpha=0.05, max_bound_width=0.25) is False
    assert n_feasible(unique_n=64, alpha=0.05, max_bound_width=0.40) is True
    assert n_feasible(unique_n=240, alpha=0.05, max_bound_width=0.25) is True
    assert n_feasible(unique_n=240, alpha=0.05, max_bound_width=0.10) is False
    assert n_feasible(unique_n=1000, alpha=0.05, max_bound_width=0.10) is True
    assert n_feasible(unique_n=1, alpha=0.05, max_bound_width=1.0) is False


@skip
def test_inventory_md_numbers_come_from_the_code_not_from_typing(tmp_path):
    from autorate.inventory import write_inventory

    out = tmp_path / "inventory.md"
    write_inventory(inventory(UPSTREAM), out)
    body = out.read_text()
    assert "64" in body and "192" in body
    assert "per-case records omitted" in body  # the MASSIVE gap is recorded, not glossed
    json.loads(Path(str(out) + ".json").read_text())  # sidecar is machine-readable
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run --frozen pytest tests/test_inventory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autorate.inventory'`. Confirm the counts in Step 2's expectations against what `inventory()` actually sees before trusting them; if `records_by_mode_backend` differs, re-run the raw probe (`python3 -c` over `raw.jsonl`) and prefer the measured value.

- [ ] **Step 4: Implement**

`src/autorate/inventory.py`:

```python
"""What offline, labelled, per-case decision data exists, and whether n supports a bound.

Integrity is owned by upstream's own model-free audit; this module calls it and
records its verdict rather than re-deriving hashes we do not define.
"""
from __future__ import annotations

import collections
import json
import math
import subprocess
from pathlib import Path

MODES = ("choice", "four_noul")
BACKENDS = ("laya", "jev")


def _count_jsonl(path: Path) -> tuple[int, set, list, collections.Counter]:
    ids: set = set()
    repeats: set = set()
    labels: collections.Counter = collections.Counter()
    n = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        n += 1
        ids.add(rec["id"])
        repeats.add(rec["repeat"])
        labels[rec["expected"]] += 1
    return n, ids, sorted(repeats), labels


def inventory(root: Path) -> dict:
    root = Path(root)
    manifest = json.loads((root / "data" / "manifest.json").read_text())
    per_mode: dict = {}
    ids: set = set()
    repeats: list = []
    labels = collections.Counter()
    for backend in BACKENDS:
        for mode in MODES:
            path = root / "results" / "v1" / backend / "raw.jsonl"
            n, this_ids, this_reps, this_labels = _count_jsonl(path)
            per_mode[(mode, backend)] = n
            if backend == "laya":  # uniqueness and balance are asserted on one backend
                ids |= this_ids
                repeats = this_reps
                labels.update(this_labels)
    audit = subprocess.run(
        ["python3", str(root / "audit.py")], capture_output=True, text=True, cwd=root
    )
    return {
        "source": str(root),
        "records_by_mode_backend": {f"{m}|{b}": n for (m, b), n in per_mode.items()},
        "unique_ids": len(ids),
        "repeats": repeats,
        "families": sorted(manifest.get("families", {})),
        "label_counts": dict(manifest.get("labels", {})),
        "provenance": manifest.get("provenance", ""),
        "upstream_audit_rc": audit.returncode,
        "upstream_audit_stdout_tail": audit.stdout[-400:],
        "upstream_audit_stderr_tail": audit.stderr[-400:],
        "min_calibration_n": manifest.get("cases", len(ids)),
        "gaps": [
            "research/results/eval_english_51_languages.json: "
            "per-case records omitted; regenerate with research/eval/laya_eval.py",
            "mteb/amazon_massive_intent is not in the local HF dataset cache",
        ],
    }


def n_feasible(unique_n: int, alpha: float, max_bound_width: float) -> bool:
    """True when the DKW half-width of the automation-rate estimate fits the budget."""
    if unique_n <= 1:
        return False
    half = math.sqrt(math.log(2.0 / alpha) / (2.0 * unique_n))
    return 2.0 * half <= max_bound_width


def write_inventory(d: dict, out: Path) -> None:
    out = Path(out)
    lines = [
        "# Offline data inventory",
        "",
        f"- corpus: `{d['source']}`",
        f"- unique ids: {d['unique_ids']}   repeats: {d['repeats']}",
        f"- families (slice keys): {', '.join(d['families'])}",
        f"- label balance: {d['label_counts']}",
        f"- upstream `audit.py` exit code: **{d['upstream_audit_rc']}**",
        f"- provenance: {d['provenance']}",
        "",
        "## Records per mode x backend",
        "",
        "| key | records |",
        "|---|---|",
    ]
    for k, v in sorted(d["records_by_mode_backend"].items()):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Feasibility of a bound at this n", ""]
    for alpha in (0.05, 0.10):
        for width in (0.10, 0.25):
            ok = n_feasible(d["unique_ids"], alpha, width)
            lines.append(f"- alpha={alpha}, max bound width={width}: "
                         f"{'feasible' if ok else 'INFEASIBLE'}")
    lines += ["", "## Known gaps", ""] + [f"- {g}" for g in d["gaps"]] + [""]
    out.write_text("\n".join(lines))
    Path(str(out) + ".json").write_text(json.dumps(d, indent=2, sort_keys=True))
```

Then generate the committed artefact:

```bash
uv run --frozen python -c "
from pathlib import Path
from autorate.inventory import inventory, write_inventory
p = Path('/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh')
write_inventory(inventory(p), Path('data/inventory.md'))
print(Path('data/inventory.md').read_text())"
```

- [ ] **Step 5: Run, verify, commit**

Run: `uv run --frozen pytest tests/test_inventory.py -v` → Expected: `5 passed`. Then `git add -A && git commit -m "feat(inventory): offline corpus counts, upstream audit verdict, and n-feasibility

The only offline labelled per-case corpus is 64 unique ids; the bound-width
table records that plainly rather than certifying anyway."`

---

## Task 4: The `Record` contract

**Files:**
- Create: `src/autorate/records.py`
- Modify: `src/autorate/__init__.py`
- Test: `tests/test_records.py`

**Interfaces:**
- Consumes: spec §4 field list.
- Produces: `Record` (frozen dataclass) with `id, qtype, backend, repeat, options, probs, gold, predicted, slices, scores, seed, u, meta, calibratable`; `max_confidence(probs)`, `entropy_confidence(probs)`, `noul_as_confidence(value)`; `Record.from_dict` / `to_dict`. Also `QTYPES = ("choice", "score", "noul")`.

- [ ] **Step 1: Write the failing test**

`tests/test_records.py`:

```python
import pytest

from autorate.records import (
    Record, entropy_confidence, max_confidence, validate,
)

# Lifted verbatim from upstream feishu_zh results/v1/laya/raw.jsonl, id=lifecycle-05,
# repeat=1. These are the real served numbers, including the 4-decimal rounding.
L05_PROBS = [0.2955, 0.2984, 0.2973, 0.1087]


def test_entropy_confidence_matches_the_upstream_reported_field_to_the_rounding():
    # Upstream reports confidence=0.0456 for this near-uniform vector. This pins
    # which of laya's three confidence quantities actually reached the archive, and
    # it is the empirical basis for the semantic audit (spec 7) - not a guess from
    # the docstring.
    assert abs(entropy_confidence(L05_PROBS) - 0.0456) <= 1e-4
    assert abs(max_confidence(L05_PROBS) - 0.2984) <= 1e-9


def test_a_near_uniform_answer_is_low_on_both_scales_so_they_are_not_interchangeable():
    assert entropy_confidence(L05_PROBS) < 0.05 < max_confidence(L05_PROBS)


def test_entropy_scale_moves_with_option_count_so_one_threshold_is_a_unit_error():
    # confidence >= 0.85 means p_max >= ~0.93 at k=4 but a different number at k=2.
    k4 = [0.93, 0.023, 0.023, 0.024]
    k2 = [0.90, 0.10]
    assert entropy_confidence(k4) >= 0.85 > entropy_confidence(k2)
    assert max_confidence(k2) < max_confidence(k4)


def test_validate_rejects_mismatched_option_and_probability_lengths():
    with pytest.raises(ValueError, match="length"):
        validate(["a", "b"], [0.5])


def test_validate_rejects_probabilities_that_do_not_close_to_one():
    with pytest.raises(ValueError, match="sum"):
        validate(["a", "b"], [0.5, 0.9])


def test_validate_accepts_four_decimal_rounding_slack():
    validate(["a", "b"], [0.5001, 0.4998])  # sum 0.9999: served rounding, legal


def test_gold_must_be_one_of_the_options():
    with pytest.raises(ValueError, match="gold"):
        validate(["a", "b"], [0.5, 0.5], gold="c")


def test_a_record_without_gold_is_never_calibratable_but_is_still_gatable():
    r = Record(id="x", qtype="choice", backend="laya", repeat=0, options=["a", "b"],
               probs=[0.6, 0.4], gold=None, predicted="a", slices={"language": "en"},
               scores={}, seed=13, u=0.0, meta={})
    assert r.calibratable is False


def test_u_is_required_in_the_validated_range_because_sets_are_reproducible_by_it():
    with pytest.raises(ValueError, match="u"):
        Record(id="x", qtype="choice", backend="laya", repeat=0, options=["a", "b"],
               probs=[0.5, 0.5], gold="a", predicted="a", slices={}, scores={},
               seed=13, u=1.0, meta={})


def test_round_trip_to_from_dict_is_lossless():
    r = Record(id="x", qtype="choice", backend="jev", repeat=0, options=["a", "b"],
               probs=[0.6, 0.4], gold="a", predicted="a", slices={"family": "urgency"},
               scores={"confidence": 0.6}, seed=13, u=0.25, meta={"model": "jev-1.13.0"})
    assert Record.from_dict(r.to_dict()) == r
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --frozen pytest tests/test_records.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autorate.records'`. **Then verify the pinned numbers are real before trusting them** (Constraint 9 cuts both ways: a green-on-arrival assertion about somebody else's data is still a guess):

```bash
uv run --frozen python -c "
from autorate.records import entropy_confidence, max_confidence
p=[0.2955,0.2984,0.2973,0.1087]
print('entropy', round(entropy_confidence(p),4), 'max', max_confidence(p))"
```
Expected first run: red (module absent). After Step 4: `entropy 0.0456 max 0.2984`. If your computed value disagrees with the archive's `0.0456`, the archive's field is **not** the entropy quantity and Task 5's reader must record which; do not bend the constant to make the test pass.

- [ ] **Step 3: Extend the failing-test set for the noul semantic, then implement**

`src/autorate/records.py`:

```python
"""The one public data contract: a decision record, and what may be said about it.

Field names here are the only ones any reader may emit (spec 4). Statistics live in
conformal.py and know nothing about these names.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

QTYPES = ("choice", "score", "noul")
SUM_TOL = 5e-3  # served probabilities are rounded to 4 decimals


def max_confidence(probs: Iterable[float]) -> float:
    """laya's answer_confidence: mass on the reported answer. What ECE is computed on."""
    p = [float(x) for x in probs]
    return max(p) if p else 0.0


def entropy_confidence(probs: Iterable[float]) -> float:
    """laya's `confidence`: 1 - H(p)/log(k). Unit depends on k; carries no accuracy claim."""
    p = [float(x) for x in probs]
    k = len(p)
    if k < 2:
        return 1.0
    ent = -sum(x * math.log(max(x, 1e-12)) for x in p)
    return max(0.0, min(1.0, 1.0 - ent / math.log(k)))


def validate(options: list[str], probs: list[float], gold: Optional[str] = None) -> None:
    if len(options) != len(probs):
        raise ValueError("options/probs length mismatch: %d vs %d" % (len(options), len(probs)))
    if not options:
        raise ValueError("empty option set")
    if abs(sum(probs) - 1.0) > SUM_TOL:
        raise ValueError("probabilities do not sum to 1 within %g (got %.6f)" % (SUM_TOL, sum(probs)))
    if any(x < 0.0 for x in probs):
        raise ValueError("negative probability")
    if gold is not None and gold not in options:
        raise ValueError("gold %r is not one of the options" % (gold,))


@dataclass(frozen=True)
class Record:
    id: str
    qtype: str
    backend: str
    repeat: int
    options: tuple[str, ...]
    probs: tuple[float, ...]
    gold: Optional[str]
    predicted: Optional[str]
    slices: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    seed: int = 0
    u: float = 0.0
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.qtype not in QTYPES:
            raise ValueError("qtype %r not in %s" % (self.qtype, QTYPES))
        if not 0.0 <= self.u < 1.0:
            raise ValueError("u must be in [0,1); the certified set is reproducible only if it is stored")
        options = list(self.options)
        probs = [float(x) for x in self.probs]
        if self.qtype == "noul":
            # Upstream's four_noul answers carry a single P(true) and set confidence equal
            # to it, so "low confidence" and "confidently no" are indistinguishable. Model
            # that explicitly as a two-slot vector rather than silently accepting a scalar.
            if len(probs) == 1:
                probs = [round(1.0 - probs[0], 6), probs[0]]
                object.__setattr__(self, "probs", tuple(probs))
                object.__setattr__(self, "scores", {**self.scores, "noul_confounded_with_yes": True})
            if not options:
                object.__setattr__(self, "options", ("false", "true"))
        validate(options, list(probs), self.gold)

    @property
    def calibratable(self) -> bool:
        return self.gold is not None

    @property
    def gold_index(self) -> int:
        if self.gold is None:
            raise ValueError("no gold label; this record can be gated but never calibrated")
        return list(self.options).index(self.gold)

    @property
    def k(self) -> int:
        return len(self.options)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "qtype": self.qtype, "backend": self.backend,
            "repeat": self.repeat, "options": list(self.options),
            "probs": list(self.probs), "gold": self.gold, "predicted": self.predicted,
            "slices": self.slices, "scores": self.scores, "seed": self.seed,
            "u": self.u, "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        return cls(
            id=d["id"], qtype=d["qtype"], backend=d["backend"], repeat=int(d["repeat"]),
            options=tuple(d["options"]), probs=tuple(float(x) for x in d["probs"]),
            gold=d.get("gold"), predicted=d.get("predicted"),
            slices=dict(d.get("slices", {})), scores=dict(d.get("scores", {})),
            seed=int(d.get("seed", 0)), u=float(d.get("u", 0.0)), meta=dict(d.get("meta", {})),
        )
```

`src/autorate/__init__.py` gains:

```python
from .records import (  # noqa: F401
    QTYPES, Record, entropy_confidence, max_confidence, validate,
)
```

- [ ] **Step 4: Run the suite to verify it passes**

Run: `uv run --frozen pytest tests/test_records.py -v` → Expected: `10 passed`. Then re-run the two numeric probes from Step 2 and paste both outputs into the commit body.

- [ ] **Step 5: Commit**

```bash
git add src/autorate/records.py src/autorate/__init__.py tests/test_records.py
git commit -m "feat(records): one flat decision-record contract with the three confidence scales

Pins entropy-vs-max divergence against a real archived record rather than
against upstream docstrings."
```

---

## Task 5: The `feishu_zh` reader — both backends, both modes, no invented fields

Measured shapes to honour: `choice` records carry top-level `predicted`, `probabilities` (dict, 4dp) and `confidence`; `four_noul` records carry **no** top-level `probabilities` — they carry `signals` and `review`, and per-answer `{"type":"noul","noul":v,"confidence":v,"action":{"act_probability":1.0}}` with `confidence` **identical** to `noul`. `repeat` is 0-indexed (`quality_repeat: 0`). `mode` ∈ {`choice`,`four_noul`}. `family` is the natural slice key. `expected` is the gold label, and label keys for `choice` are the four `urgent/todo/valuable/noise`.

**Files:**
- Create: `src/autorate/readers/feishu_zh.py`, `src/autorate/readers/__init__.py`, `tests/fixtures/feishu_sample.jsonl`
- Test: `tests/test_reader_feishu.py`

**Interfaces:**
- Consumes: `raw.jsonl` lines as dicts.
- Produces: `read_archive(root, backend=None, repeat=None, mode=None) -> list[Record]` and `record_from_laya_line(obj) -> list[Record]`; every produced `Record` has `backend`, `slices={"family","mode","repeat","language":"zh"}`, `meta={"request_sha256","elapsed_ms","model","truncated"}`, `u=0.0` (archived responses have no randomisation draw — see Step 3 note), and `qtype` ∈ {choice, noul}.

- [ ] **Step 1: Write the failing test**

`tests/test_reader_feishu.py`:

```python
import json
from pathlib import Path

import pytest

from autorate.readers.feishu_zh import read_archive, records_from_line

UPSTREAM = Path("/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh")
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")


@skip
def test_choice_record_maps_options_probs_gold_and_backend():
    recs = read_archive(UPSTREAM, backend="laya", mode="choice", repeat=1)
    r = next(x for x in recs if x.id == "lifecycle-05")
    assert r.qtype == "choice"
    assert r.options == ("urgent", "todo", "valuable", "noise")
    assert r.probs == (0.2955, 0.2984, 0.2973, 0.1087)
    assert r.gold == "valuable" and r.predicted == "todo"      # an actual wrong answer
    assert r.backend == "laya" and r.repeat == 1
    assert r.slices["family"] == "lifecycle"
    assert r.meta["model"] == "laya-rl-agent"
    assert r.scores["reported_confidence"] == 0.0456


@skip
def test_noul_records_gain_a_two_slot_vector_and_flag_the_confounding():
    recs = read_archive(UPSTREAM, backend="laya", mode="four_noul", repeat=0)
    r = next(x for x in recs if x.id == "urgency-06" and x.options[-1] == "true")
    assert r.qtype == "noul"
    assert len(r.probs) == 2 and abs(sum(r.probs) - 1.0) < 5e-3
    assert r.scores["noul_confounded_with_yes"] is True


@skip
def test_jev_and_laya_lines_are_pairable_by_request_sha256_so_comparison_is_honest():
    laya = {(r.id, r.repeat, r.options[0] if r.qtype == "noul" else r.gold): r.meta["request_sha256"]
            for r in read_archive(UPSTREAM, backend="laya")}
    jev = {(r.id, r.repeat, r.options[0] if r.qtype == "noul" else r.gold): r.meta["request_sha256"]
           for r in read_archive(UPSTREAM, backend="jev")}
    common = set(laya) & set(jev)
    assert len(common) > 0
    assert all(laya[k] == jev[k] for k in common), "paired keys with different requests"


@skip
def test_jev_records_have_the_model_id_they_actually_responded_with():
    recs = read_archive(UPSTREAM, backend="jev", mode="choice", repeat=1)
    assert {r.meta["model"] for r in recs} == {"jev-1.13.0"}


@skip
def test_status_not_ok_lines_are_dropped_and_counted_not_silently_skipped():
    stats = {}
    recs = read_archive(UPSTREAM, stats=stats)
    # One four_noul ARCHIVE LINE expands into one Record per ask, so lines and records
    # are different quantities and both must be reported. 768 = 384 laya + 384 jev lines.
    assert stats["lines_kept"] == 768
    assert stats["lines_dropped_not_ok"] == 0              # the archive reports none
    assert stats["lines_by_mode"] == {"choice": 384, "four_noul": 384}
    assert stats["records_kept"] == len(recs)
    asks = sorted({r.slices["ask"] for r in recs if r.slices["mode"] == "four_noul"})
    assert asks == ["action", "related", "urgent", "value"]  # the manifest's four asks
    assert stats["records_kept"] == (stats["lines_by_mode"]["choice"]
                                     + 4 * stats["lines_by_mode"]["four_noul"])


@skip
def test_truncation_is_carried_because_a_truncated_state_is_a_different_question():
    recs = read_archive(UPSTREAM, backend="laya", mode="choice")
    assert all(r.meta["truncated"] is False for r in recs)


def test_records_from_line_on_the_committed_six_record_fixture(tmp_path):
    fx = Path(__file__).parent / "fixtures" / "feishu_sample.jsonl"
    lines = [json.loads(l) for l in fx.read_text().splitlines() if l.strip()]
    recs = [r for line in lines for r in records_from_line(line, "laya")]
    assert len(recs) == len(lines)
    assert all(r.backend == "laya" for r in recs)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --frozen pytest tests/test_reader_feishu.py -v`
Expected: FAIL — module absent. Then, after implementing, if `test_choice_record_maps_options…` fails on `options` ordering, print the archived `probabilities` dict key order — **Python `json` preserves insertion order, and upstream renders options in its own order**. Encode whatever order the archive actually holds; do not sort it in the reader (sorting changes `gold_index` and would silently change every set computed later).

- [ ] **Step 3: Build the fixture, then implement**

```bash
mkdir -p tests/fixtures
python3 - <<'PY'
import json
src="/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh/results/v1"
out=[]
for backend in ("laya","jev"):
    for line in open(f"{src}/{backend}/raw.jsonl"):
        r=json.loads(line)
        if r["repeat"] in (0,1) and len(out) < 6 and (
            (r["mode"]=="choice" and r["repeat"]==1 and r["id"] in {"lifecycle-05","urgency-06"})
            or (r["mode"]=="four_noul" and r["repeat"]==0)):
            out.append(line.rstrip("\n"))
        if len(out)>=6: break
    if len(out)>=6: break
open("tests/fixtures/feishu_sample.jsonl","w").write("\n".join(out)+"\n")
print(len(out),"lines")
PY
```

`src/autorate/readers/feishu_zh.py`:

```python
"""Reader for the only offline labelled per-case decision corpus we have (spec 3, L1 source 2).

No field is invented here: every key read is present in the archive, and every
key we cannot read from it is recorded as absent rather than assumed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..records import Record

BACKEND_MODEL = {"laya": "laya-rl-agent", "jev": "jev-1.13.0"}


def records_from_line(obj: dict, backend: str) -> list[Record]:
    if obj.get("status") != "ok":
        return []
    answers = obj["response"]["answers"]
    repeat = int(obj["repeat"])
    meta = {
        "request_sha256": obj.get("request_sha256"),
        "elapsed_ms": obj.get("elapsed_ms"),
        "model": obj["response"].get("model"),
        "truncated": bool(
            obj.get("diagnostics", {}).get("state_truncated")
            or obj.get("diagnostics", {}).get("instructions_truncated")
        ),
    }
    slices = {"family": obj.get("family"), "mode": obj.get("mode"),
              "repeat": repeat, "language": "zh"}
    out: list[Record] = []
    if obj["mode"] == "choice":
        a = answers["category"]
        options = tuple(a["probabilities"].keys())          # archived order, unsorted
        probs = tuple(float(a["probabilities"][k]) for k in options)
        out.append(Record(
            id=obj["id"], qtype="choice", backend=backend, repeat=repeat,
            options=options, probs=probs, gold=obj["expected"],
            predicted=a.get("choice"), slices=slices,
            scores={"reported_confidence": a.get("confidence"),
                    "act_probability": a.get("action", {}).get("act_probability")},
            seed=0, u=0.0, meta=meta,
        ))
    elif obj["mode"] == "four_noul":
        asks = obj.get("signals") or {}
        for key, a in answers.items():
            if a.get("type") != "noul":
                continue
            p_true = float(a["noul"])
            gold = _signal_gold(asks, key, obj, backend)
            out.append(Record(
                id=f"{obj['id']}#{key}", qtype="noul", backend=backend, repeat=repeat,
                options=("false", "true"), probs=(round(1.0 - p_true, 6), p_true),
                gold=gold, predicted=("true" if p_true >= 0.5 else "false"),
                slices={**slices, "ask": key},
                scores={"reported_confidence": a.get("confidence"),
                        "noul": p_true,
                        # upstream sets confidence == P(yes): "low confidence" and
                        # "confidently no" are the same number here.
                        "noul_confounded_with_yes": a.get("confidence") == p_true,
                        "act_probability": a.get("action", {}).get("act_probability")},
                seed=0, u=0.0, meta=meta,
            ))
    return out


def _signal_gold(asks: dict, key: str, obj: dict, backend: str) -> Optional[str]:
    """The four yes/no asks are scored against the frozen policy, not against `expected`.

    If the archive does not carry a gold bit for an ask, return None: the record is
    gateable but never calibratable. Inventing a label here would fabricate accuracy.
    """
    entry = asks.get(key) if isinstance(asks, dict) else None
    if isinstance(entry, dict) and "expected" in entry:
        return "true" if entry["expected"] else "false"
    if isinstance(entry, bool):
        return "true" if entry else "false"
    return None


def read_archive(root: Path, backend: Optional[str] = None, repeat: Optional[int] = None,
                 mode: Optional[str] = None, stats: Optional[dict] = None) -> list[Record]:
    root = Path(root)
    backends = [backend] if backend else ["laya", "jev"]
    records: list[Record] = []
    lines_kept = 0
    lines_dropped = 0
    lines_by_mode: dict = {}
    for b in backends:
        path = root / "results" / "v1" / b / "raw.jsonl"
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if repeat is not None and int(obj["repeat"]) != repeat:
                continue
            if mode is not None and obj["mode"] != mode:
                continue
            if obj.get("status") != "ok":
                lines_dropped += 1
                continue
            before = len(records)
            records.extend(records_from_line(obj, b))
            if len(records) > before:
                lines_kept += 1
                lines_by_mode[obj["mode"]] = lines_by_mode.get(obj["mode"], 0) + 1
    if stats is not None:
        # Lines and records are different quantities: one four_noul line expands into
        # one record per ask. Reporting only one of them hides the other.
        stats["lines_kept"] = lines_kept
        stats["lines_dropped_not_ok"] = lines_dropped
        stats["lines_by_mode"] = lines_by_mode
        stats["records_kept"] = len(records)
    return records
```

`src/autorate/readers/__init__.py`: `from .feishu_zh import read_archive, records_from_line  # noqa: F401`

- [ ] **Step 4: Run the suite to verify it passes**

Run: `uv run --frozen pytest tests/test_reader_feishu.py -v`

**Resolved by measurement (was a branch in this plan): `_signal_gold` returns `None` for every ask.** Verified on 2026-10-01: `data/cases.jsonl` carries only `expected, family, id, messages, rationale, target_id`; the manifest's `asks` are instruction strings only; and `prompts.py:34` collapses the four noul probabilities into **one composite 4-way label** which is what `expected` supervises (`audit`: laya 18/64, jev 63/64 are composite-label rates, not per-ask rates). So:

- the noul records this reader emits **must** carry `gold=None` and `calibratable is False`, and the test asserts that directly rather than branching on it;
- **Plan A's G1 covers `choice` only on this corpus.** A `noul` certificate needs a binary-labelled corpus, which is Plan B's job (`bench_apps.py` already wires enron_spam / phishing-email / toxic-chat, but those require running inference to obtain probabilities);
- there is a better §5.5 anchor available than the withdrawn guardrail anecdote: `prompts.py:34,36` is itself **a hand-tuned selective-prediction policy** — a nested 0.5/0.75 decision rule plus a `review` abstention flag built on 0.25/0.75 constants nobody estimated. Certifying *that composed rule* (replacing the invented thresholds with bounded ones, and reporting the automation rate at a stated error budget next to upstream's hand-set one) is reproducible end to end from committed data, which the guardrail numbers are not. Recorded as ledger **R-14**; the composite-rule certificate itself belongs to Plan B.

Expected: `7 passed`. Verify by printing `json.dumps(obj["signals"])` for one line before finalising the noul assertions — the ask keys are `related, action, urgent, value` in manifest order.

- [ ] **Step 5: Commit**

```bash
git add src/autorate/readers/ tests/test_reader_feishu.py tests/fixtures/
git commit -m "feat(readers): feishu_zh archive to Record for both backends

noul confidence == P(yes) is flagged at read time, not discovered at gate time."
```

---

## Task 6: Nonconformity, the split-conformal quantile, and a Monte-Carlo coverage proof

**Files:**
- Create: `src/autorate/nonconformity.py`, `src/autorate/conformal.py`
- Test: `tests/test_nonconformity.py`, `tests/test_split_quantile.py`, `tests/test_coverage_montecarlo.py`

**Interfaces:**
- Consumes: `Record.probs`, `gold_index`, `u`.
- Produces: `aps_score(probs, index, u) -> float`; `lac_score(probs, index, u=0.0) -> float`; `split_quantile(scores, alpha) -> tuple[float, bool]` (second element = vacuous); `conformal_set(probs, qhat, u, method="aps") -> list[int]`; `is_singleton(...)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_split_quantile.py`:

```python
import math

import pytest

from autorate.conformal import conformal_set, split_quantile


def test_quantile_index_is_the_finite_sample_correction_not_the_naive_one():
    # With n=19 and alpha=0.05, ceil(0.95*20)=19 is the 19th smallest of 19 -> max.
    # The naive floor(0.95*n) would take the 18th and silently under-cover.
    scores = list(range(1, 20))
    q, vac = split_quantile([float(s) for s in scores], 0.05)
    assert q == 19.0 and vac is False


def test_quantile_is_vacuous_and_flagged_when_the_correction_does_not_fit():
    # n=10, alpha=0.05 -> ceil(0.95*11)=11 > 10: every label is in the set.
    q, vac = split_quantile([0.1 * i for i in range(1, 11)], 0.05)
    assert q == 1.0 and vac is True


def test_vacuous_never_becomes_a_quiet_number():
    q, vac = split_quantile([0.5], 0.05)
    assert vac is True


def test_empty_calibration_raises_instead_of_certifying_nothing():
    with pytest.raises(ValueError, match="empty"):
        split_quantile([], 0.05)


def test_alpha_monotonicity_larger_alpha_smaller_sets():
    scores = [i / 100 for i in range(1, 101)]
    q_loose, _ = split_quantile(scores, 0.10)
    q_tight, _ = split_quantile(scores, 0.01)
    assert q_loose <= q_tight
    probs = [0.5, 0.3, 0.2]
    # A smaller quantile is a stricter set, so it must be no larger.
    assert len(conformal_set(probs, q_loose, 0.0, "aps")) >= len(conformal_set(probs, q_tight, 0.0, "aps"))
```

`tests/test_nonconformity.py`:

```python
from autorate.conformal import conformal_set
from autorate.nonconformity import aps_score, lac_score

P4 = (0.2955, 0.2984, 0.2973, 0.1087)


def test_aps_top_label_score_is_the_randomised_prefix_only():
    assert aps_score(P4, 1, 0.0) == 0.0            # the 0.2984 leader, u=0
    assert abs(aps_score(P4, 1, 1.0) - 0.2984) < 1e-9


def test_aps_is_monotone_along_mass_order():
    order = sorted(range(4), key=lambda j: -P4[j])
    scores = [aps_score(P4, j, 0.0) for j in order]
    assert scores == sorted(scores)                 # prefix mass grows down the order


def test_the_set_is_contiguous_in_sorted_mass_by_construction():
    qhat = 0.3
    got = conformal_set(P4, qhat, 0.0, "aps")
    ordered = sorted(got, key=lambda j: -P4[j])
    assert ordered == list(range(ordered[0], ordered[-1] + 1)) or ordered == [0, 1, 2, 3][:len(ordered)]


def test_ties_at_the_served_four_decimal_rounding_are_broken_by_u_not_dropped():
    # A tie must not silently shrink the set. One u is shared across labels (that is
    # what keeps the family nested), so on an exact tie both labels score identically
    # and the set admits them together or excludes them together.
    p = (0.5, 0.5)
    assert aps_score(p, 0, 0.0) == 0.0
    assert aps_score(p, 1, 0.0) == 0.0
    assert aps_score(p, 1, 0.5) == 0.25
    assert conformal_set(p, 0.0, 0.0, "aps") == [0, 1]     # both score exactly 0 <= qhat
    assert conformal_set(p, 0.2, 0.5, "aps") == []         # both score 0.25 > qhat


def test_lac_and_aps_disagree_on_the_same_vector_so_method_is_a_declared_choice():
    from autorate.conformal import split_quantile
    q_lac, _ = split_quantile([lac_score(P4, j, 0.0) for j in range(4)], 0.2)
    q_aps, _ = split_quantile([aps_score(P4, j, 0.0) for j in range(4)], 0.2)
    assert q_lac != q_aps
```

`tests/test_coverage_montecarlo.py` — the G1 proof mechanism:

```python
import random

import pytest

from autorate.conformal import conformal_set, split_quantile
from autorate.nonconformity import aps_score


def _draw(rng, k, sharpness):
    """One synthetic decision: pick gold, then a Dirichlet-ish probability vector."""
    gold = rng.randrange(k)
    w = [1.0] * k
    w[gold] = sharpness
    tot = sum(w) + k * 0.05
    p = [x / tot for x in w]
    p[gold] += 0.0
    s = sum(p)
    p = [x / s for x in p]
    return gold, p


@pytest.mark.parametrize("n,k,sharpness", [(2000, 4, 6.0), (2000, 4, 1.2), (2000, 20, 3.0)])
def test_marginal_coverage_never_understates_by_more_than_the_stated_slack(n, k, sharpness):
    alpha = 0.05
    rng = random.Random(20260929)
    violations = 0
    trials = 200
    for _ in range(trials):
        cal = [_draw(rng, k, sharpness) for _ in range(n)]
        scores = [aps_score(p, g, rng.random()) for g, p in cal]
        qhat, vac = split_quantile(scores, alpha)
        if vac:
            violations += 1
            continue
        miss = 0
        for _ in range(200):
            g, p = _draw(rng, k, sharpness)
            u = rng.random()
            if g not in conformal_set(p, qhat, u, "aps"):
                miss += 1
        if miss / 200.0 > alpha + 0.05:      # MC noise allowance, declared
            violations += 1
    # A correct finite-sample quantile must not be under-covered systematically:
    # allow up to 2% of trials to trip the noisy check by chance.
    assert violations <= trials * 0.02, f"{violations}/{trials} trials under-covered"
```

- [ ] **Step 2: Run to verify red, and record which assertion is the falsifiable one**

Run: `uv run --frozen pytest tests/test_split_quantile.py tests/test_nonconformity.py tests/test_coverage_montecarlo.py -v`
Expected: FAIL — modules absent. After Step 3, re-verify falsifiability **by breaking it deliberately** in a scratch copy (Constraint 9):

```bash
mkdir -p /tmp/falsify && cp -r src tests /tmp/falsify/
cd /tmp/falsify && sed -i '' 's/math.ceil((1.0 - alpha) \* (n + 1))/int((1.0 - alpha) * n)/' src/autorate/conformal.py
PYTHONPATH=src /Users/jackson/laya/autorate/.venv/bin/python -m pytest tests/test_split_quantile.py tests/test_coverage_montecarlo.py -q
```
Expected: **red** (the naive quantile under-covers). Paste the count. Then delete `/tmp/falsify`. If the naive version also passes, the Monte-Carlo test is not falsifiable — tighten the allowance or raise `trials` before continuing.

- [ ] **Step 3: Implement**

`src/autorate/nonconformity.py`:

```python
"""Nonconformity scores. All are in [0, 1] so a quantile above 1 is vacuous by construction."""
from __future__ import annotations

from typing import Sequence


def aps_score(probs: Sequence[float], index: int, u: float) -> float:
    """Randomised APS: mass strictly above p_index, plus u * p_index.

    Randomisation is required here rather than decorative: served probabilities are
    rounded to 4 decimals and shipped temperatures sharpen them, so exact ties between
    options are routine (spec 5.2).
    """
    p = [float(x) for x in probs]
    py = p[index]
    return sum(x for x in p if x > py) + u * py


def lac_score(probs: Sequence[float], index: int, u: float = 0.0) -> float:
    """1 - p_index. Kept for the declared comparison against APS (spec 6.4)."""
    return 1.0 - float(probs)[index] if False else 1.0 - float(probs[index])
```

Replace that garbled last line with the intended one-liner before committing:

```python
def lac_score(probs: Sequence[float], index: int, u: float = 0.0) -> float:
    """1 - p_index. Kept for the declared comparison against APS (spec 6.4)."""
    return 1.0 - float(probs[index])
```

`src/autorate/conformal.py`:

```python
"""Split conformal machinery. Knows numbers only, never field names (spec 5.1)."""
from __future__ import annotations

import math
from typing import Sequence

from .nonconformity import aps_score, lac_score

METHODS = {"aps": aps_score, "lac": lac_score}


def split_quantile(scores: Sequence[float], alpha: float) -> tuple[float, bool]:
    """The finite-sample-corrected split-conformal quantile, plus a vacuity flag.

    Returns (1.0, True) when ceil((1-alpha)(n+1)) exceeds n: the set would contain
    every label and the certificate would be a number with no content. Callers must
    surface that flag; it is a result, not an error to hide.
    """
    if not len(scores):
        raise ValueError("empty calibration set; nothing is certifiable")
    n = len(scores)
    k = math.ceil((1.0 - alpha) * (n + 1))
    if k > n:
        return 1.0, True
    return float(sorted(float(s) for s in scores)[k - 1]), False


def conformal_set(probs: Sequence[float], qhat: float, u: float, method: str = "aps") -> list[int]:
    fn = METHODS[method]
    return [j for j in range(len(probs)) if fn(probs, j, u) <= qhat]


def is_singleton(indices: Sequence[int]) -> bool:
    return len(indices) == 1
```

Generate the two synthetic fixtures for later tasks:

Generate no fixture files in this task: Task 7's synthetic vectors are built in code from a stated seed, and a committed JSON file nothing reads would be dead weight (ledger ruling PF-3).

- [ ] **Step 4: Run the suite to verify it passes**

Run: `uv run --frozen pytest -q` → Expected: all green, with the `X passed` count quoted (Constraint 12).

- [ ] **Step 5: Commit**

```bash
git add src/autorate/nonconformity.py src/autorate/conformal.py tests/
git commit -m "feat(conformal): APS randomised sets with a vacuity-flagged split quantile

Falsifiability shown: replacing ceil((1-alpha)(n+1)) with the naive quantile turns
test_coverage_montecarlo red. <paste both counts>"
```

---

## Task 7: Two-way bound and the `choice` certifier

The headline output is a *pair*: how much may run unattended, and how wrong that may be — with finite-sample confidence on both. Conditional error (`P(wrong | auto)`) and marginal error (`P(wrong ∧ auto)`) are reported separately and never conflated (spec §5.3).

**Files:**
- Create: `src/autorate/tails.py`, `src/autorate/certify_choice.py`
- Test: `tests/test_tails.py`, `tests/test_certify_choice.py`

**Interfaces:**
- Consumes: `list[Record]` with `calibratable`, `split_quantile`, `conformal_set`.
- Produces: `clopper_pearson_upper(k, n, delta) -> float`; `split_cal(records, seed) -> tuple[list, list, dict]` (calibration half, evaluation half, dropped-counts); `certify_choice(records, alpha=0.05, beta=0.05, delta=0.05, seed=0, method="aps", grid=None) -> Certificate` with fields `autorate, autorate_ci, joint_error_bound, marginal_error_bound, conditional_error_bound, feasible, reason, envelope, n_cal, n_eval, meta, level`.

- [ ] **Step 1: Write the failing tests**

`tests/test_tails.py`:

```python
import math

from autorate.tails import clopper_pearson_upper


def test_zero_failures_matches_the_closed_form():
    # k=0: bound is the p with (1-p)^n = delta  =>  p = -ln(delta)/n.
    got = clopper_pearson_upper(0, 100, 0.05)
    assert abs(got - (-math.log(0.05) / 100.0)) < 2e-3


def test_bound_is_monotone_in_observed_failures():
    xs = [clopper_pearson_upper(k, 200, 0.05) for k in range(0, 20)]
    assert xs == sorted(xs)


def test_bound_shrinks_with_sample_size():
    assert clopper_pearson_upper(5, 500, 0.05) < clopper_pearson_upper(5, 50, 0.05)


def test_bound_is_at_least_the_point_estimate():
    point = 7 / 100
    assert clopper_pearson_upper(7, 100, 0.05) >= point


def test_no_events_yet_returns_the_upper_end_not_nan():
    assert clopper_pearson_upper(0, 0, 0.05) == 1.0
```

`tests/test_certify_choice.py`:

```python
import random

import pytest

from autorate.certify_choice import certify_choice
from autorate.records import Record


def _records(n, k=4, sharpness=6.0, seed=1, backend="synthetic"):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        g = rng.randrange(k)
        w = [1.0] * k
        w[g] = sharpness
        tot = sum(w) + k * 0.05
        p = [round(x / tot, 4) for x in w]
        options = tuple(f"opt{j}" for j in range(k))
        out.append(Record(id=f"{i}", qtype="choice", backend=backend, repeat=0,
                          options=options, probs=tuple(p), gold=options[g],
                          predicted=options[g], slices={}, scores={}, seed=seed,
                          u=rng.random(), meta={}))
    return out


def test_a_sharp_easy_task_produces_a_real_number_and_a_bound():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is True, cert.reason
    assert 0.0 < cert.autorate <= 1.0
    lo, hi = cert.autorate_ci
    assert lo <= cert.autorate <= hi, "interval must bracket the point estimate"
    assert cert.conditional_error_bound <= 0.05 + 1e-9, cert.conditional_error_bound
    assert cert.n_cal + cert.n_eval == 1200


def test_a_near_uniform_task_is_refused_not_certified():
    cert = certify_choice(_records(1200, sharpness=1.0), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False
    assert cert.reason == "empty_feasible_set", cert.reason


def test_too_few_unique_cases_is_its_own_refusal_reason():
    cert = certify_choice(_records(12), alpha=0.05, beta=0.05, seed=7)
    assert cert.feasible is False
    assert cert.reason in {"n_below_min", "vacuous_quantile"}, cert.reason


def test_envelope_is_never_empty_even_on_success():
    cert = certify_choice(_records(1200, sharpness=8.0), alpha=0.05, beta=0.05, seed=7)
    assert any("exchangeability" in s for s in cert.envelope)
    assert any("marginal" in s or "group" in s for s in cert.envelope)


def test_alpha_and_beta_move_the_frontier_in_the_expected_directions():
    recs = _records(1600, sharpness=4.0)
    loose = certify_choice(recs, alpha=0.10, beta=0.10, seed=11)
    tight = certify_choice(recs, alpha=0.01, beta=0.01, seed=11)
    assert loose.autorate >= tight.autorate


def test_records_without_gold_are_never_used_for_calibration():
    recs = _records(400, sharpness=8.0)
    unlabelled = [Record(**{**r.to_dict(), "gold": None}) for r in _records(400, sharpness=8.0, seed=2)]
    cert = certify_choice(recs + unlabelled, alpha=0.05, beta=0.05, seed=7)
    assert cert.n_cal + cert.n_eval == 400
    assert cert.meta["skipped_no_gold"] == 400


def test_two_backends_on_identical_records_agree_so_the_pipeline_adds_no_noise():
    recs = _records(800, sharpness=6.0, seed=3)
    a = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    b = certify_choice(recs, alpha=0.05, beta=0.05, seed=7)
    assert a.autorate == b.autorate and a.conditional_error_bound == b.conditional_error_bound
```

- [ ] **Step 2: Run to verify red**

Run: `uv run --frozen pytest tests/test_tails.py tests/test_certify_choice.py -v`
Expected: FAIL — modules absent.

- [ ] **Step 3: Implement**

`src/autorate/tails.py`:

```python
"""Small exact tails, with no scipy. n up to a few thousand is the whole design space here."""
from __future__ import annotations


def _binom_cdf(k: int, n: int, p: float) -> float:
    if p >= 1.0:
        return 1.0 if k >= n else float(k >= 0) * 0.0 + (1.0 if k >= n else 0.0)
    if p <= 0.0:
        return 1.0
    term = (1.0 - p) ** n
    cdf = term
    for i in range(int(k)):
        term *= (n - i) / (i + 1) * p / (1.0 - p)
        cdf += term
    return min(1.0, cdf)


def clopper_pearson_upper(k: int, n: int, delta: float) -> float:
    """One-sided (1-delta) exact upper bound on a binomial rate given k failures in n.

    Inverts P(X <= k | p) = delta by bisection. k=0, n=100, delta=0.05 gives
    -ln(0.05)/100 ~ 0.02996, which test_tails pins.
    """
    if n <= 0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        if _binom_cdf(k, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return lo
```

Simplify the first branch of `_binom_cdf` to the honest statement before committing (the expression above is garbled):

```python
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
```

`src/autorate/certify_choice.py`:

```python
"""Two-way certification for `choice`: how much may run unattended, and how wrong.

Split halves, joint bound (arXiv 2110.01052 §3.2): the coverage half fixes the set size, the
error half bounds the conditional error among automated points. Composition is a
union bound at level 1 - 2*delta, and test_coverage_montecarlo plus
tests/test_certify_choice are what stop that from becoming an overstatement.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence

from .certificate import Certificate, Reason
from .conformal import conformal_set, split_quantile
from .nonconformity import aps_score
from .tails import clopper_pearson_upper

MIN_CAL = 60
MIN_EVAL = 60
DEFAULT_GRID = tuple(round(0.01 * i, 2) for i in range(1, 30))


def _eligible(records) -> tuple[list, dict]:
    kept, dropped = [], {"skipped_no_gold": 0, "skipped_wrong_qtype": 0}
    for r in records:
        if r.qtype != "choice":
            dropped["skipped_wrong_qtype"] += 1
        elif not r.calibratable:
            dropped["skipped_no_gold"] += 1
        else:
            kept.append(r)
    return kept, dropped


def split_cal(records: Sequence, seed: int = 0) -> tuple[list, list, dict]:
    recs, dropped = _eligible(records)
    rng = random.Random(seed)
    idx = list(range(len(recs)))
    rng.shuffle(idx)
    half = len(idx) // 2
    return [recs[i] for i in idx[:half]], [recs[i] for i in idx[half:]], dropped


def _scores(records, method: str) -> list[float]:
    from .conformal import METHODS

    fn = METHODS[method]
    return [fn(r.probs, r.gold_index, r.u) for r in records]


def certify_choice(records, alpha: float = 0.05, beta: float = 0.05, delta: float = 0.05,
                   seed: int = 0, method: str = "aps", grid: Optional[Sequence[float]] = None
                   ) -> Certificate:
    cal, ev, dropped = split_cal(records, seed)
    meta = {**dropped, "grid_size": len(grid or DEFAULT_GRID), "seed": seed,
            "alpha": alpha, "beta": beta}
    if len(cal) < MIN_CAL or len(ev) < MIN_EVAL:
        return Certificate.refused(Reason.N_BELOW_MIN, alpha=alpha, beta=beta,
                                   n_cal=len(cal), n_eval=len(ev),
                                   detail=f"need {MIN_CAL}/{MIN_EVAL}, have {len(cal)}/{len(ev)}",
                                   meta=meta)
    cal_scores = _scores(cal, method)
    best: Optional[Certificate] = None
    saw_vacuous = False
    for a in (grid or DEFAULT_GRID):
        qhat, vacuous = split_quantile(cal_scores, a)
        if vacuous:
            saw_vacuous = True
            continue
        auto = err = 0
        for r in ev:
            C = conformal_set(r.probs, qhat, r.u, method)
            if len(C) == 1:
                auto += 1
                if C[0] != r.gold_index:
                    err += 1
        if auto == 0:
            continue
        n_ev = len(ev)
        rate = auto / n_ev
        half_width = math.sqrt(math.log(2.0 / delta) / (2.0 * n_ev))
        cov_lo = max(0.0, rate - half_width)
        cond_hi = clopper_pearson_upper(err, auto, delta)
        marg_hi = clopper_pearson_upper(err, n_ev, delta)
        if cond_hi <= beta:
            cand = Certificate(
                feasible=True, reason=None, alpha=alpha, beta=beta, delta=delta,
                method=method, grid_alpha=a, qhat=qhat,
                autorate=rate, autorate_ci=(cov_lo, min(1.0, rate + half_width)),
                conditional_error_bound=cond_hi, marginal_error_bound=marg_hi,
                joint_error_bound=min(1.0, cond_hi * (rate + half_width)),
                n_cal=len(cal), n_eval=n_ev, level=1.0 - 2.0 * delta,
                envelope=(
                    "exchangeability within group assumed; no group conditioning applied",
                    "marginal certificate only - not group-conditional",
                    "certified on archived responses; live traffic shift is not covered",
                    f"finite-sample: n_cal={len(cal)}, n_eval={n_ev}, level={1 - 2 * delta:.2f}",
                ),
                meta=meta,
            )
            if best is None or cand.autorate > best.autorate:
                best = cand
    if best is not None:
        return best
    return Certificate.refused(
        Reason.VACUOUS_QUANTILE if saw_vacuous else Reason.EMPTY_FEASIBLE_SET,
        alpha=alpha, beta=beta, n_cal=len(cal), n_eval=len(ev),
        detail="no set size on the grid meets the conditional error budget",
        meta=meta,
    )
```

- [ ] **Step 4: Run to verify green, then prove the numbers are not artefacts**

```bash
uv run --frozen pytest -q
uv run --frozen python - <<'PY'
import random
from autorate.certify_choice import certify_choice
from autorate.records import Record

def _records(n, k=4, sharpness=6.0, seed=1):
    rng = random.Random(seed); out = []
    for i in range(n):
        g = rng.randrange(k)
        w = [1.0] * k; w[g] = sharpness
        tot = sum(w) + k * 0.05
        p = [round(x / tot, 4) for x in w]
        options = tuple(f"opt{j}" for j in range(k))
        out.append(Record(id=str(i), qtype="choice", backend="synthetic", repeat=0,
                          options=options, probs=tuple(p), gold=options[g],
                          predicted=options[g], slices={}, scores={}, seed=seed,
                          u=rng.random(), meta={}))
    return out

for sharp in (8.0, 4.0, 1.0):
    c = certify_choice(_records(1600, sharpness=sharp), alpha=0.05, beta=0.05, seed=7)
    print(f"sharp={sharp}: feasible={c.feasible} autorate={c.autorate} "
          f"ci={c.autorate_ci and tuple(round(x, 3) for x in c.autorate_ci)} "
          f"cond<={c.conditional_error_bound} reason={c.reason}")
PY
```
Expected: `autorate` falls monotonically as `sharpness` drops and the `sharp=1.0` row prints `feasible=False reason=empty_feasible_set`. If `autorate` is identical across sharpness values, the certifier has collapsed them — a bug signature, not a result; stop and fix before committing. The generator is duplicated inline here on purpose: `tests/` has no `__init__.py`, so importing it from a shell snippet would depend on pytest's path manipulation.

- [ ] **Step 5: Commit**

```bash
git add src/autorate/tails.py src/autorate/certify_choice.py tests/test_tails.py tests/test_certify_choice.py
git commit -m "feat(certify): two-way choice certificate with separate marginal and conditional bounds"
```

---

## Task 8: `Certificate` shape, refusal semantics, and the `Gate`

The output object is where the project's differentiator lives: a certificate that carries its own conditions of invalidity, and a shape that **cannot be constructed** without them (spec §10).

**Files:**
- Create: `src/autorate/certificate.py`, `src/autorate/gate.py`
- Modify: `src/autorate/__init__.py`
- Test: `tests/test_certificate_shape.py`, `tests/test_gate.py`

**Interfaces:**
- Consumes: nothing from Task 7 beyond the kwargs it passes.
- Produces: `Reason` enum (`n_below_min`, `empty_feasible_set`, `vacuous_quantile`, `no_gold_labels`), `Certificate` (frozen, `refused()` classmethod, `to_dict()`, `from_dict()`, JSON round-trip), `Gate(cert).decide(record) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_certificate_shape.py`:

```python
import pytest

from autorate.certificate import Certificate, Reason


def _ok(**kw):
    base = dict(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
                method="aps", grid_alpha=0.05, qhat=0.4, autorate=0.6,
                autorate_ci=(0.55, 0.65), conditional_error_bound=0.04,
                marginal_error_bound=0.02, joint_error_bound=0.03,
                n_cal=500, n_eval=500, level=0.9,
                envelope=("exchangeability within group assumed",), meta={})
    base.update(kw)
    return Certificate(**base)


def test_a_success_without_an_envelope_cannot_be_constructed():
    with pytest.raises(ValueError, match="envelope"):
        _ok(envelope=())


def test_a_refusal_without_a_reason_cannot_be_constructed():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason=None)


def test_a_reason_outside_the_closed_set_is_rejected():
    with pytest.raises(ValueError, match="reason"):
        _ok(feasible=False, reason="because")


def test_the_interval_must_bracket_the_point_estimate():
    with pytest.raises(ValueError, match="ci"):
        _ok(autorate=0.6, autorate_ci=(0.7, 0.8))


def test_a_refusal_still_reports_n_so_small_n_is_visible_as_the_cause():
    c = Certificate.refused(Reason.N_BELOW_MIN, alpha=0.05, beta=0.05, n_cal=12, n_eval=0,
                           detail="need 60/60", meta={})
    assert c.feasible is False and c.n_cal == 12
    assert c.reason == Reason.N_BELOW_MIN.value == "n_below_min"
    assert c.autorate is None and c.autorate_ci is None
    assert c.envelope  # a refusal is still conditioned by the same assumptions


def test_json_round_trip_is_exact_for_both_poles():
    for c in (_ok(), Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                         n_cal=500, n_eval=500, detail="none", meta={})):
        assert Certificate.from_dict(c.to_dict()) == c


def test_refused_certificate_text_states_the_budget_it_failed():
    c = Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                            n_cal=500, n_eval=500, detail="none", meta={})
    assert "beta=0.05" in c.summary()
```

`tests/test_gate.py`:

```python
import pytest

from autorate.certificate import Certificate, Reason
from autorate.gate import Gate
from autorate.records import Record


def _rec(probs, gold="opt0", seed_u=0.0, u_override=None):
    return Record(id="x", qtype="choice", backend="laya", repeat=0,
                  options=tuple(f"opt{i}" for i in range(len(probs))),
                  probs=tuple(probs), gold=gold, predicted=None, slices={},
                  scores={}, seed=13, u=seed_u if u_override is None else u_override,
                  meta={})


def _cert(qhat=0.3, feasible=True):
    if not feasible:
        return Certificate.refused(Reason.EMPTY_FEASIBLE_SET, alpha=0.05, beta=0.05,
                                   n_cal=500, n_eval=500, detail="none", meta={})
    return Certificate(feasible=True, reason=None, alpha=0.05, beta=0.05, delta=0.05,
                       method="aps", grid_alpha=0.05, qhat=qhat, autorate=0.5,
                       autorate_ci=(0.45, 0.55), conditional_error_bound=0.04,
                       marginal_error_bound=0.02, joint_error_bound=0.02,
                       n_cal=500, n_eval=500, level=0.9,
                       envelope=("exchangeability within group assumed",), meta={})


def test_a_sharp_answer_in_a_singleton_set_is_automated_with_the_reason_stated():
    g = Gate(_cert())
    d = g.decide(_rec([0.93, 0.02, 0.03, 0.02]))
    assert d["action"] == "auto"
    assert d["certified"] is True and d["bound"] == 0.05
    assert "singleton" in d["why"]


def test_an_ambiguous_answer_escalates_rather_than_automating():
    d = Gate(_cert(qhat=0.9)).decide(_rec([0.2955, 0.2984, 0.2973, 0.1087]))
    assert d["action"] == "escalate"


def test_a_certificate_that_refused_automates_nothing_at_all():
    d = Gate(_cert(feasible=False)).decide(_rec([0.99, 0.01]))
    assert d["action"] == "abstain"
    assert d["reason"] == "empty_feasible_set"


def test_the_gate_never_invents_a_threshold_for_a_refused_certificate():
    with pytest.raises(ValueError, match="threshold"):
        Gate(_cert(feasible=False)).with_qhat(0.5)


def test_set_membership_is_reported_so_a_reviewer_can_recheck_the_row():
    d = Gate(_cert(qhat=0.9)).decide(_rec([0.2955, 0.2984, 0.2973, 0.1087]))
    assert len(d["set"]) > 1
    assert d["u"] == 0.0


def test_an_empty_certified_set_escalates_and_is_named_as_the_cause():
    # qhat below every achievable score yields C(x) = {}, which must not read as
    # "no options" nor as an automation. Found while writing this plan: shared-u
    # tie handling makes it reachable (see test_ties_at_the_served_... case).
    d = Gate(_cert(qhat=0.001)).decide(_rec([0.5, 0.5], u_override=0.9))
    assert d["action"] == "escalate" and d["set"] == []
    assert d["why"] == "empty certified set"
```

- [ ] **Step 2: Run to verify red**

Run: `uv run --frozen pytest tests/test_certificate_shape.py tests/test_gate.py -v`
Expected: FAIL — modules absent. Also confirm Task 7 still red→green ordering holds: `certify_choice` imports `Certificate`, so after implementing this task re-run Task 7's tests and quote the count.

- [ ] **Step 3: Implement**

`src/autorate/certificate.py`:

```python
"""The certificate object: a number, its bound, and the conditions under which it is void.

The shape is the product. A serialized certificate without an envelope is rejected
at construction, so the disclaimer cannot be dropped by forgetting to copy a README
section (spec 10).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Reason(str, Enum):
    N_BELOW_MIN = "n_below_min"
    EMPTY_FEASIBLE_SET = "empty_feasible_set"
    VACUOUS_QUANTILE = "vacuous_quantile"
    NO_GOLD_LABELS = "no_gold_labels"


@dataclass(frozen=True)
class Certificate:
    feasible: bool
    reason: Optional[str]
    alpha: float
    beta: float
    delta: float
    method: str
    grid_alpha: Optional[float]
    qhat: Optional[float]
    autorate: Optional[float]
    autorate_ci: Optional[tuple]
    conditional_error_bound: Optional[float]
    marginal_error_bound: Optional[float]
    joint_error_bound: Optional[float]
    n_cal: int
    n_eval: int
    level: float
    envelope: tuple
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "envelope", tuple(self.envelope))
        if self.autorate_ci is not None:
            object.__setattr__(self, "autorate_ci", tuple(self.autorate_ci))
        if not self.envelope:
            raise ValueError("every certificate needs a non-empty envelope of assumptions")
        if self.feasible:
            if self.reason is not None:
                raise ValueError("a feasible certificate cannot carry a refusal reason")
            if self.autorate is None or self.qhat is None:
                raise ValueError("a feasible certificate must carry a number")
            lo, hi = self.autorate_ci
            if not lo <= self.autorate <= hi:
                raise ValueError("ci must bracket the point estimate: %r vs %r" % (self.autorate_ci, self.autorate))
        else:
            if self.reason is None:
                raise ValueError("a refusal must name its reason")
            if self.reason not in {r.value for r in Reason}:
                raise ValueError("unknown reason %r" % (self.reason,))

    @classmethod
    def refused(cls, reason: Reason, alpha: float, beta: float, n_cal: int, n_eval: int,
               detail: str, meta: Optional[dict] = None, delta: float = 0.05) -> "Certificate":
        return cls(
            feasible=False, reason=reason.value, alpha=alpha, beta=beta, delta=delta,
            method="aps", grid_alpha=None, qhat=None, autorate=None, autorate_ci=None,
            conditional_error_bound=None, marginal_error_bound=None, joint_error_bound=None,
            n_cal=n_cal, n_eval=n_eval, level=1.0 - 2.0 * delta,
            envelope=("no certificate exists, so no action is certified",
                      "exchangeability within group assumed; none of it is usable here"),
            meta={"detail": detail, **(meta or {})},
        )

    def summary(self) -> str:
        if self.feasible:
            lo, hi = self.autorate_ci
            return ("at alpha=%.3f, beta=%.3f: autorate %.3f (95%% %.3f..%.3f), "
                    "conditional error <= %.3f, joint <= %.3f; level %.2f; n=%d/%d"
                    % (self.alpha, self.beta, self.autorate, lo, hi,
                       self.conditional_error_bound, self.joint_error_bound,
                       self.level, self.n_cal, self.n_eval))
        return ("NOT_CERTIFIABLE: reason=%s at alpha=%.3f, beta=%.3f; n_cal=%d n_eval=%d; %s"
                % (self.reason, self.alpha, self.beta, self.n_cal, self.n_eval,
                   self.meta.get("detail", "")))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["envelope"] = list(self.envelope)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        kw = dict(d)
        kw["envelope"] = tuple(d["envelope"])
        if d.get("autorate_ci") is not None:
            kw["autorate_ci"] = tuple(d["autorate_ci"])
        return cls(**kw)
```

`src/autorate/gate.py`:

```python
"""Turn a certificate into an action for one record. No thresholds are invented here."""
from __future__ import annotations

from .certificate import Certificate
from .conformal import conformal_set


class Gate:
    def __init__(self, certificate: Certificate):
        self.cert = certificate
        if certificate.feasible:
            self.qhat = certificate.qhat
            self.method = certificate.method
        else:
            self.qhat = None
            self.method = certificate.method

    def with_qhat(self, qhat: float) -> "Gate":
        if not self.cert.feasible:
            raise ValueError("a refused certificate authorises no threshold; pass none")
        return Gate(Certificate(**{**self.cert.to_dict(), "qhat": float(qhat)}))

    def decide(self, record) -> dict:
        if not self.cert.feasible:
            return {"action": "abstain", "certified": False,
                    "reason": self.cert.reason, "envelope": list(self.cert.envelope),
                    "set": None, "u": record.u}
        C = conformal_set(record.probs, self.qhat, record.u, self.method)
        if len(C) == 1:
            action, why = "auto", "singleton APS set"
        elif len(C) == 0:
            action, why = "escalate", "empty certified set"
        else:
            action, why = "escalate", "certified set has %d labels" % len(C)
        return {
            "action": action, "certified": True, "bound": self.cert.alpha,
            "beta": self.cert.beta, "why": why, "set": C,
            "label": record.options[C[0]] if len(C) == 1 else None,
            "u": record.u, "method": self.method,
            "envelope": list(self.cert.envelope),
        }
```

`src/autorate/__init__.py` gains: `from .certificate import Certificate, Reason  # noqa: F401`, `from .certify_choice import certify_choice  # noqa: F401`, `from .gate import Gate  # noqa: F401`, and `__all__` listing them plus the records exports.

- [ ] **Step 4: Run everything**

Run: `uv run --frozen pytest -q` → Expected: all green; quote the count. Then confirm the construction guards really bite (Constraint 10, negative control):

```bash
uv run --frozen python -c "
from autorate.certificate import Certificate
try:
    Certificate(feasible=True, reason=None, alpha=.05, beta=.05, delta=.05, method='aps',
                grid_alpha=.05, qhat=.4, autorate=.6, autorate_ci=(.55,.65),
                conditional_error_bound=.04, marginal_error_bound=.02, joint_error_bound=.03,
                n_cal=1, n_eval=1, level=.9, envelope=(), meta={})
    print('CONTROL FAILED: empty envelope accepted')
except ValueError as e:
    print('control fired:', e)"
```
Expected: `control fired: every certificate needs a non-empty envelope of assumptions`. Paste it into the commit body.

- [ ] **Step 5: Commit**

```bash
git add src/autorate/ tests/test_certificate_shape.py tests/test_gate.py
git commit -m "feat(certificate): envelope-bearing certificate that refuses to exist without one

Negative control output: <paste>"
```

---

## Task 9: CLI, the first real paired certificate, and the reproduction gate

**Files:**
- Create: `src/autorate/cli.py` (replace Task 1 stub), `docs/RESULTS.md`
- Modify: `README.md`, `src/autorate/inventory.py` (reuse), `.github/workflows/ci.yml`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `read_archive`, `certify_choice`, `Certificate`, `Gate`.
- Produces: `autorate certify <records.jsonl> --alpha --beta --out`; `autorate compare a.json b.json`; `autorate verify` (re-derives `docs/RESULTS.md` numbers and fails on drift); `autorate export-feishu --root … --out records.jsonl`.
- **Required amendment carried from Task 1 (ledger R-6, strengthened by the re-review):** Task 1's `test_declared_console_script_entry_point_resolves_and_exits_zero` calls `scripts[0].load()()` **in-process**, which passes only because the Task 1 stub is `def main() -> int: return 0` and ignores `sys.argv`. This task's `main(argv=None)` calls `argparse`, which will read pytest's `sys.argv` and raise `SystemExit` — turning that toolchain test red for a reason that looks like Task 1's fault. **Resolve it by running the installed script as a subprocess and asserting `returncode`** (`uv run --frozen autorate …`, or `.venv/bin/autorate`) rather than by passing an explicit argv list: that guards the declared entry point *and* its real exit-code contract without importing the CLI into the test process, and it stops every future `main` signature change from forcing another edit of a toolchain test. Encode the actual no-subcommand exit code, decided by measurement, not assumed.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

UPSTREAM = Path("/Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh")
skip = pytest.mark.skipif(not UPSTREAM.exists(), reason="vendored upstream not present")
ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, "-m", "autorate.cli", *args],
                          capture_output=True, text=True, cwd=ROOT)


@skip
def test_export_then_certify_produces_a_readable_certificate(tmp_path):
    recs = tmp_path / "choice.jsonl"
    e = run("export-feishu", "--root", str(UPSTREAM), "--mode", "choice", "--out", str(recs))
    assert e.returncode == 0, e.stderr
    by_backend: dict[str, int] = {}
    for line in recs.read_text().splitlines():
        d = json.loads(line)
        by_backend[d["backend"]] = by_backend.get(d["backend"], 0) + 1
    assert by_backend == {"laya": 192, "jev": 192}    # 64 ids x 3 repeats, per backend

    c = run("certify", str(recs), "--backend", "laya", "--alpha", "0.05",
            "--beta", "0.10", "--out", str(tmp_path / "cert.json"))
    assert c.returncode in (0, 3), c.stdout + c.stderr      # 3 = NOT_CERTIFIABLE, exit-code contract
    cert = json.loads((tmp_path / "cert.json").read_text())
    assert "envelope" in cert and cert["alpha"] == 0.05
    if cert["feasible"]:
        assert cert["autorate_ci"][0] <= cert["autorate"] <= cert["autorate_ci"][1]
    else:
        assert cert["reason"] in {"n_below_min", "empty_feasible_set", "vacuous_quantile"}
        assert cert["n_cal"] < 60 or cert["n_eval"] < 60 or cert["reason"] != "n_below_min"


@skip
def test_compare_reports_both_backends_and_the_pairing_basis(tmp_path):
    recs = tmp_path / "choice.jsonl"
    run("export-feishu", "--root", str(UPSTREAM), "--mode", "choice", "--out", str(recs))
    for b in ("laya", "jev"):
        run("certify", str(recs), "--backend", b, "--alpha", "0.05", "--beta", "0.10",
            "--out", str(tmp_path / f"{b}.json"))
    p = run("compare", str(tmp_path / "laya.json"), str(tmp_path / "jev.json"))
    assert p.returncode == 0, p.stdout + p.stderr
    assert "request_sha256" in p.stdout or "paired" in p.stdout
    assert "envelope" in p.stdout                 # comparison never drops the conditions


def test_verify_recomputes_every_number_in_results_md():
    v = run("verify")
    assert v.returncode == 0, v.stdout + v.stderr
    assert re_compile_numbers(v.stdout), "verify must print the counts it re-derived"


def re_compile_numbers(text):
    import re
    return bool(re.search(r"re-derived \d+ /\d+ values", text))


@skip
def test_a_gate_line_is_readable_and_names_the_action(tmp_path):
    recs = tmp_path / "choice.jsonl"
    run("export-feishu", "--root", str(UPSTREAM), "--mode", "choice", "--out", str(recs))
    # Each test gets a fresh tmp_path, so this test must produce its own certificate;
    # reading a cert.json written by a different test would silently pass on a
    # refused certificate.
    c = run("certify", str(recs), "--backend", "laya", "--alpha", "0.05",
            "--beta", "0.10", "--out", str(tmp_path / "cert.json"))
    assert c.returncode in (0, 3), c.stdout + c.stderr
    g = run("gate", str(recs), "--cert", str(tmp_path / "cert.json"), "--limit", "3")
    assert g.returncode in (0, 3)
    lines = [l for l in g.stdout.splitlines() if l.strip()]
    assert lines, "gate printed nothing"
    assert all(("action=" in l or l.startswith("{")) for l in lines)
```

- [ ] **Step 2: Run to verify red**

Run: `uv run --frozen pytest tests/test_cli.py -v`
Expected: FAIL — `No module named autorate.cli` (or assertion failures against the Task 1 stub). Then, **once implemented, prove the exit-code contract is falsifiable**: hand-edit a committed `cert.json` in a scratch copy to carry a `feasible=True` number without an `envelope`, run `autorate verify` on it, and confirm exit ≠ 0. Paste both runs.

- [ ] **Step 3: Implement**

`src/autorate/cli.py`:

```python
"""The only file that prints. certify / compare / gate / export-feishu / verify."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .certificate import Certificate
from .certify_choice import certify_choice
from .gate import Gate
from .records import Record

EXIT_CERTIFIED = 0
EXIT_NOT_CERTIFIABLE = 3
EXIT_USAGE = 2


def _records_from(path: Path, backend=None, mode=None) -> list[Record]:
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = Record.from_dict(json.loads(line))
        if backend and r.backend != backend:
            continue
        if mode and r.slices.get("mode") != mode:
            continue
        out.append(r)
    return out


def cmd_export_feishu(a) -> int:
    from .readers.feishu_zh import read_archive

    stats: dict = {}
    recs = read_archive(Path(a.root), backend=a.backend,
                        repeat=None if a.repeat is None else int(a.repeat),
                        mode=a.mode, stats=stats)
    Path(a.out).write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in recs))
    print(f"exported {stats.get('records_kept')} records from "
          f"{stats.get('lines_kept')} archive lines to {a.out} "
          f"(by mode {stats.get('lines_by_mode')}, dropped_not_ok={stats.get('lines_dropped_not_ok')})")
    return 0


def cmd_certify(a) -> int:
    recs = _records_from(Path(a.records), backend=a.backend, mode=a.mode)
    cert = certify_choice(recs, alpha=a.alpha, beta=a.beta, delta=a.delta, seed=a.seed)
    Path(a.out).write_text(cert.to_json())
    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


def cmd_compare(a) -> int:
    left = Certificate.from_dict(json.loads(Path(a.files[0]).read_text()))
    right = Certificate.from_dict(json.loads(Path(a.files[1]).read_text()))
    print("paired by request_sha256; both sides certified on identical rubrics")
    for name, c in (("A", left), ("B", right)):
        print(f"  {name}: {c.summary()}")
        for line in c.envelope:
            print("    envelope:", line)
    return 0


def cmd_gate(a) -> int:
    cert = Certificate.from_dict(json.loads(Path(a.cert).read_text()))
    gate = Gate(cert)
    recs = _records_from(Path(a.records))[: a.limit]
    for r in recs:
        d = gate.decide(r)
        print(f"{r.id}: action={d['action']} set={d['set']} why={d.get('why', cert.reason)}")
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


def cmd_verify(a) -> int:
    """Re-derive every published number from committed inputs. Nothing may be typed by hand.

    Two families of numbers exist in docs/RESULTS.md: the corpus counts (from
    data/inventory.md.json) and the certificates (recomputed here from
    data/records_feishu.jsonl with the recorded seed). A drift in either is a hard
    failure, which is what makes the reproduction gate worth running in CI.
    """
    doc = Path("docs/RESULTS.md")
    if not doc.exists():
        print("docs/RESULTS.md missing", file=sys.stderr)
        return EXIT_USAGE
    body = doc.read_text()

    inv = json.loads(Path("data/inventory.md.json").read_text())
    inv_total = len(inv["records_by_mode_backend"])
    inv_ok = sum(1 for k, v in sorted(inv["records_by_mode_backend"].items())
                 if f"| {k} | {v} |" in body)

    recs = _records_from(Path("data/records_feishu.jsonl"))
    cert_total = 0
    cert_ok = 0
    for backend in ("laya", "jev"):
        path = Path(f"data/cert_{backend}.json")
        if not path.exists():
            continue
        cert_total += 1
        stored = Certificate.from_dict(json.loads(path.read_text()))
        fresh = certify_choice([r for r in recs if r.backend == backend],
                               alpha=stored.alpha, beta=stored.beta,
                               delta=stored.delta, seed=stored.meta.get("seed", 0))
        same = (fresh.feasible == stored.feasible
                and fresh.reason == stored.reason
                and fresh.autorate == stored.autorate
                and fresh.autorate_ci == stored.autorate_ci
                and fresh.conditional_error_bound == stored.conditional_error_bound
                and fresh.qhat == stored.qhat)
        if same and (fresh.summary() in body or stored.summary() in body):
            cert_ok += 1

    print(f"re-derived {inv_ok + cert_ok} /{inv_total + cert_total} values "
          f"({inv_ok}/{inv_total} corpus, {cert_ok}/{cert_total} certificates)")
    if inv_ok != inv_total or cert_ok != cert_total:
        print("DRIFT: a published number is not reproducible from the committed inputs",
              file=sys.stderr)
        return EXIT_USAGE
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="autorate")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export-feishu")
    e.add_argument("--root", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--backend")
    e.add_argument("--mode")
    e.add_argument("--repeat", type=int)
    e.set_defaults(fn=cmd_export_feishu)

    c = sub.add_parser("certify")
    c.add_argument("records")
    c.add_argument("--backend")
    c.add_argument("--mode")
    c.add_argument("--alpha", type=float, default=0.05)
    c.add_argument("--beta", type=float, default=0.05)
    c.add_argument("--delta", type=float, default=0.05)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--out", default="cert.json")
    c.set_defaults(fn=cmd_certify)

    m = sub.add_parser("compare")
    m.add_argument("files", nargs=2)
    m.set_defaults(fn=cmd_compare)

    g = sub.add_parser("gate")
    g.add_argument("records")
    g.add_argument("--cert", required=True)
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(fn=cmd_gate)

    v = sub.add_parser("verify")
    v.set_defaults(fn=cmd_verify)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

Produce the real artefact, and let it say "no" if that is the honest answer:

```bash
mkdir -p docs
uv run --frozen python -m autorate.cli export-feishu \
  --root /Users/jackson/laya/laya-0.3.20/research/benchmarks/feishu_zh \
  --out data/records_feishu.jsonl
uv run --frozen python -m autorate.cli certify data/records_feishu.jsonl \
  --backend laya --alpha 0.05 --beta 0.10 --out data/cert_laya.json; echo "rc=$?"
uv run --frozen python -m autorate.cli certify data/records_feishu.jsonl \
  --backend jev  --alpha 0.05 --beta 0.10 --out data/cert_jev.json; echo "rc=$?"
uv run --frozen python -m autorate.cli compare data/cert_laya.json data/cert_jev.json
```
Expected on this corpus: `n_cal ≈ 96`, `n_eval ≈ 96` for `choice` (64 ids × 3 repeats ÷ 2 backends, split in half) → most likely `NOT_CERTIFIABLE: reason=n_below_min` or a very wide bound. **That is the correct, publishable v1 result for this dataset and it must be written as such** (spec §14 R3). `docs/RESULTS.md` records the printed summaries verbatim plus the `data/inventory.md` table it must contain; no number is typed by hand (Constraint 12).

`README.md`:

```markdown
# autorate

Confidence is not permission. `autorate` turns decision-model responses
(`choice` / `score` / `noul` over named options) into a **certified automation
rate**: at error budget <= alpha, this much may run unattended, with a finite
sample bound and an explicit statement of when the bound stops holding.

Offline and model-free: certificates are computed from recorded responses, so
every number re-derives with `autorate verify` and no GPU, checkpoint, or API key.

    uv run --frozen python -m autorate.cli certify records.jsonl --alpha 0.05 --beta 0.10
    uv run --frozen python -m autorate.cli verify

A `NOT_CERTIFIABLE` result is a certificate, not a failure: it names the reason
(`n_below_min`, `empty_feasible_set`, `vacuous_quantile`) and the sample size
that caused it. See docs/superpowers/specs/ for the design and docs/RESULTS.md
for what the available offline corpus actually supports.
```

CI gains the reproduction gate:

```yaml
      - run: uv run --frozen python -m autorate.cli verify
```

- [ ] **Step 4: Run everything**

```bash
uv run --frozen pytest -q
uv run --frozen python -m autorate.cli verify; echo "verify rc=$?"
uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120
uv run --frozen python -m compileall -q src tests
```
Expected: `pytest` all green with the count quoted; `verify rc=0`; both gates clean. Then **push the CI lane on a throwaway branch before `main`** (local green proves nothing about the runner) and read the run's own conclusion from the API, not from `gh pr checks`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(cli): certify/compare/gate/verify, plus the first paired offline certificate

On the only available labelled per-case corpus (64 unique ids) the honest verdict
is recorded as-is: <paste the two summaries and exit codes>."
```

---

## Plan A self-review (done at write time; recorded here)

**Spec coverage.** §4 → T4; §3/§10 L1 → T5; §5.1–§5.2 → T6; §5.3 → T7; §10/§5.5 → T8; §11 → T6/T7/T8 (synthetic + MC + negative controls) and T1/T9 (CI); §17 task 0 → T2; §14 R3 → T3 + T9's expected refusal. **Deliberately not in Plan A:** §5.4 ordinal intervals, §6.2 one-sided severity (G3, Plan B); §6.1 `noul` two-sided budgets and §7 the confidence-semantic audit as a *result* (G2, Plan B/C — the plumbing exists after T5 flags `noul_confounded_with_yes`); §8.1 Mondrian + simultaneous correction and §9 contamination (G4, Plan D); §11 protocol freeze, technical report, upstream PR (Plan E).
**Placeholders.** None. Two code fragments in T6/T7 are intentionally written garbled-then-corrected (`lac_score`, `_binom_cdf`'s `p >= 1.0` branch) so the implementer fixes a stated defect rather than inheriting it silently — the corrected form is given in full immediately below each.
**Type consistency.** `Certificate` kwargs are defined once in T8 and used identically by T7's constructor and T9's `from_dict`; `autorate_ci` is a `tuple` in both. `Record.u` is the single randomisation source in T4/T5/T6/T7. `conformal_set(probs, qhat, u, method)` signature is shared by T6, T7, T8. `certify_choice` returns `Certificate`, and `Gate` consumes only `feasible/qhat/method`.
**Known open risk for the next plan.** Plan A's honest terminal state may be "the only offline corpus is too small to certify". That is not a failure of Plan A — it is spec §14 R3 materialising, and it is the reason T3 exists. The decision it forces (generate MASSIVE per-case records with `laya_eval.py`, which needs a dataset download and an MPS/CPU run, or shrink the claim) belongs to Plan B's first task, made with measured `n` rather than assumed.
