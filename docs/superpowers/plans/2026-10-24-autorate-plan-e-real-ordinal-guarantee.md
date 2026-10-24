# Plan E — publish the first real-corpus ordinal one-sided guarantee (route A, phase 4)

Spec: `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` §2 (G3), §6.4, §10.
Origin: task #125, ruling R-330/R-331 in `.superpowers/sdd/2026-10-03-autorate-plan-d-protocol-freeze-and-g5/progress.md`.

## What is measured and already true (do not re-derive, cite these)

- Corpus: `LocalLLaMA/typed-decisions`, config `all`, split `test`. File `all/test-00000-of-00001.parquet`,
  222,140 bytes, sha256 `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`. 400 cases,
  2,000 decisions: `choice` 600, `noul` 600, `score` 800. Fetched 2026-10-24 over verified TLS (http 200,
  `ssl_verify_result` 0), no `--insecure`, no proxy bypass.
- Scored with the cached `convaiinnovations/laya` revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`,
  `subfolder="typed-decisions"`. The `main` revision is cached INCOMPLETE (all five typed-decisions files
  absent), so the hub id must not be used. Engine copied verbatim from upstream
  `research/scripts/bench_local.py` (`to_internal`, `score_cases`, `softmax_t`, `temp_for`) for parity;
  2,000 decisions, 0 dropped, 7.0 decisions/s, 286 s. Load-time upstream warning: this checkpoint ships an
  illegal `choice:11+` temperature clamped to 0.5, so confidence on affected entries is not calibrated.
- Result at the frozen budget (alpha=beta=delta=0.05, seed=7), per question, never pooled:
  - `urgency` (4 levels, 400 records / 400 cases, split 200 cal / 200 eval):
    `certify_severity(direction="under")` **feasible**, `ahat=3`, `bound=0.014867039232`,
    `measured_violation=0.0`; `bound` is independently confirmed to equal
    `tails.clopper_pearson_upper(0, 200, 0.05)`.
    `certify_score` on the same records: **refuses** (`feasible=False`).
  - `risk`, `severity` (5 levels), `churn_risk`, `discrepancy_severity` (100 each): both gates refuse.
  - Pooling all 800 `score` decisions raises `ValueError` by design (one rubric, two level counts).

## The ruling this plan publishes under

`claims.G3.status` **stays `not_measured`.** The criterion's negative test is "if vanilla multiclass set CP
reproduces the one-sided bound, the criterion fails"; a set-gate *refusal* on this population does not
discharge it, and the note already records the sharper finding that on the corner where the ordinal set gate
does certify, its coverage statement yields a one-sided bound on its own. Moving the row without the corner
population committed as records would be the over-claim this repository exists to refuse. Say this in the
document and in the ERRATA entry; do not word it as a near-miss or as progress toward `met`.

## Scope (one commit, then the gates)

1. `data/typed_decisions_provenance.json` — the pin: sha256, bytes, URL, revision used, the incomplete-`main`
   fact, the clamp warning, the per-question decision counts and level domains.
2. `data/records_typed_decisions_urgency.jsonl` — 400 Records built by the new tool from the staged
   `laya-evidence/task2/t125/staged_records_typed_decisions_urgency.jsonl` (sha256 of that file:
   `00a17550a874b6be020590fc6089b216546117ccce5d1bafb5e25ef21129ab60`). Shape must match the published ordinal
   artefact: `options` = ascending level names, `gold`/`predicted` = level names, `probs`, `case_id`, `seed`,
   `u`, `backend="laya-typed-decisions"`, `slices={"question","workflow"}`, `scores={"gold_score"}`.
3. `tools/build_typed_decisions.py` — a **stdlib-only, not-on-the-test-path, never-in-CI** producer, written
   in the two-stage shape `tools/build_records.py` already uses: the build layer reads a pinned JSON export of
   the parquet and writes Records; the docstring states the one-line `uv run --with pyarrow` command that
   produces that export and that it is deliberately outside CI. Refuse to overwrite without `--force`; refuse
   a source whose sha256 does not match the pin (read the pin, do not restate the digest as a literal in two
   places).
4. `tools/certify_ordinal_real.py` (or a `--out` mode on the existing severity surface — pick whichever keeps
   one owner per rubric) producing `data/cert_severity_typed_decisions.json`.
5. A NEW publication table `report.ORDINAL_REAL_CERTS = {"urgency": (records, cert, "under")}` plus
   `rederive_ordinal_real(expect, ...)` wired into `cmd_verify`, mirroring `rederive_severity`'s discipline:
   the direction comes from the table, not from the artefact; every published field gets its own comparison;
   the document is compared by whole bytes.
6. `docs/ORDINAL_REAL.md` rendered from the artefact by that producer (no typed figures), stating: the
   population, the refusal of the set gate on the same records, `ahat`, the bound with its denominator named,
   the measured violation rate, the clamp disclosure, and the explicit sentence that this does NOT move G3.
7. `cli.PUBLISHED_DOCS` gains the document; `claims.G3.artefacts` and `claims.G1.artefacts` must NOT list it
   as if it certified them — decide per the ruling and say why in the note.
8. Tests, red first (TDD: write each failing test, run it, quote the failure in the report): the table and the
   document agree; the direction is not read back off the artefact; a planted figure in the certificate drifts
   by name; `certify_score`'s refusal on these records is asserted as stored (so a future certification here
   cannot silently rewrite the claim); the producer refuses a mismatched sha256; the document is re-derivable
   byte-for-byte; `test_only_certificate_tables_publish_a_protocol_digest` still holds with the new stamped
   artefact declared in the right table.
9. Re-emit `protocol.json` (23rd emission, `frozen_at` 2026-10-24 unless told otherwise), restamp every
   declared artefact, re-render `cli.PUBLISHED_DOCS`, append a dated `docs/ERRATA.md` section (append-only),
   update README's G3/G1 bullets with the new measured half WITHOUT touching the five statuses.
10. Lane denominators WILL move (a new arm + a new document row). `docs/G5.md` must then be re-exported from
    the commit that moved them, and README/note denominators move with it.

## Constraints (repo Global Constraints, unchanged)

- Exit codes 0/2/3/4 only; no absolute machine path in any tracked file; the vendored `laya-0.3.20` tree is
  read-only (`PYTHONDONTWRITEBYTECODE=1` on anything that imports it); never relax an assertion to pass; never
  add `# noqa` or a lint exemption; `uv run --frozen` (`--no-sync` in a provisioned tree); `python3`, never
  bare `python`, never the PATH `pytest`; no test counts in commit messages; commit only owned paths with
  `git commit -F <file> -- <paths>`; `git status` before any command that can discard work, and never
  `git restore`/`checkout --`/`stash`/`clean` in a dirty tree.
- Do NOT push, open PRs, flip the repo public, or publish to PyPI. Do NOT run the R-41 simulation or the
  lanes — the controller does those. Work stays in `/Users/jackson/laya/autorate/.worktrees/freeze13` on
  branch `plan/freeze13-publication`.
- Interpreter for the repo (the worktree has no venv):
  `PYTHONPATH=<worktree>/src PYTHONDONTWRITEBYTECODE=1 /Users/jackson/laya/autorate/.venv/bin/python3`, with
  `/Users/jackson/laya/laya-evidence/task2/t118/bin` on PATH for console-script rows, and
  `AUTORATE_TRACKED_FILES` left UNSET for local suite runs (exporting it feeds path guards a whole manifest
  and they die with "File name too long").
- Gate: `ruff check src tests tools --select=E9,F63,F7,F82,F401,F811 --line-length=120`.

## Report contract

Write the full report to `laya-evidence/task2/t125/task-A-report.md` (never return it inline): what was built,
the RED output quoted for each new test before it was made green, the final `verify` counts, the files
touched, the commit (one commit, not pushed), and every ruling you had to make. If you find the measured
result above does not reproduce, STOP and say so in the report — do not adjust the certificate to match prose.
