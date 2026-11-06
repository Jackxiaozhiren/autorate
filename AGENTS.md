# autorate — instructions for a coding agent

The project publishes certificates, not scores. A number that cannot be re-derived from committed bytes is a
defect, and "the bound is useless at this sample size" is a result the project ships rather than a reason to
stay quiet (spec §14). Everything below is copied from the `Global Constraints` sections of
`docs/superpowers/plans/*.md` and from the tests that enforce it; a rule with no owner is not stated here, and
`tests/test_agents_instructions.py` fails the build if this file cites a guard that does not exist or drops a
rule the gate enforces.

## The contract

1. **Exit codes are a published contract: `0` certified / `2` usage / `3` not-certifiable / `4` drift. Nothing
   escapes as rc 1.** Owners: the `EXIT_*` constants in `src/autorate/cli.py`, and the planted-input rows
   `test_no_reachable_planted_input_leaks_rc_1`,
   `test_no_groups_value_a_user_can_type_reaches_rc_1`,
   `test_every_operator_triggerable_failure_is_rc_2_and_never_rc_1`,
   `test_a_worker_that_raises_an_unnamed_exception_is_rc_4_not_rc_1`. A defect in bytes at a path the
   publication tables declare exits **4**; a defect in an argument an operator typed exits **2** (ledger
   R-272).
2. **No absolute machine path in any tracked file.** Enforced by
   `tests/test_cli.py::test_no_committed_file_carries_an_absolute_home_path`. Corpus identity is recorded by
   digest and label, never by location; a scratch path in a transcript is masked (`docs/G5.md` writes
   `<export-dir>`), and on macOS a temp root has two spellings that both have to be masked.
3. **The vendored corpus is read-only.** `laya-0.3.20` is a sibling checkout of this repository, resolved by
   `autorate.cli._default_corpus()`, never by a literal path. Importing it drops `.pyc` files beside its
   sources, so `PYTHONDONTWRITEBYTECODE=1` goes on every invocation that touches it. A test that needs a corpus
   of its own builds one under `tmp_path`.
4. **Offline forever.** The unit suite and `autorate verify` never need a GPU, a model, the network or a
   download. Runtime dependencies are `numpy>=1.24` and nothing else: adding scipy, statsmodels or MAPIE is a
   spec-level decision, not a task-level convenience, and `torch`/`transformers` belong to the vendored
   environment, never to this `pyproject.toml` (spec §11.5). Anything that fetches belongs to the pinned build
   step, not to the gate.

## Numbers

5. **One owner per published number, and a number is produced by the command that publishes it.** Derived
   values are not stored. The certification unit is the **case**: a row count is never an independent-case
   count (R-36, R-44), and where both units appear in one artefact each names its own denominator.
6. **A digit in prose must be re-derived by something, and the row that re-derives it is named by
   location.** Whatever `cli.PUBLISHED_DOCS` lists is written by the command named beside it and byte-compared by
   `verify`, so it carries no hand-typed figure. Figures in `protocol.json`'s claim notes are compared by rows in
   `tests/test_verify_protocol.py` that drive the arm each note quotes and count its comparisons; the
   corpus-absent/corpus-present pair belongs to `docs/G5.md`, and
   `test_the_g5_transcript_is_the_only_owner_of_its_digits_and_every_quoter_transcribes_it` in
   `tests/test_verify_protocol.py` refuses any quoter that disagrees with that transcript. The slice-run figures
   in `README.md`'s G4 bullet are
   compared by `tests/test_readme_slices.py` against `data/slices_language.json`; until that row landed this rule
   asserted a coverage `README.md` did not have, which is how eight positions contradicted the artefact across two
   rounds and nothing looked at the copy. The same row now polices that bullet's other two arms too -- the five
   marginal certificates' counts, read out of each certificate's own `meta.detail`, and the contamination arm's
   rows, bound and interval, with its comparison count measured by driving `report.rederive_contamination` with the
   corpus pinned invisible -- the only deterministic lane, since the arm adds two upstream re-digest comparisons
   when a checkout is visible -- and a census over the whole bullet refuses any number token no owner computes, with
   one live exemption covering three tokens in one sentence (upstream's quoted Khmer read), which dies if that
   sentence is reworded. The row's reach is that bullet and no further. `README.md`'s G1 bullet has its own row in
   `tests/test_readme_g1.py`: a census whose owners are read from `data/resplit_200.json`, `protocol.json`'s rubric
   and the spec's own numbered headings, with `test_the_g1_census_catches_a_number_no_owner_computes` forging an
   invented figure. Section numbers are citations, not measurements, so that census strips them before counting
   tokens and checks each one against a heading that exists; it does not claim to check that a cited section says
   what the sentence says. Figures in `README.md`'s other bullets, and the hand-typed ones in
   `docs/VERIFICATION.md` and the plans, are policed by their own rows or not at all, and a guard is never
   credited with a reach it does not have.
7. **Corrections go through `docs/ERRATA.md`, which is append-only**, and through a re-freeze when they touch a
   frozen sentence. Never overwrite dated evidence to make it read well now; a moved bound gets a dated row, not
   an edit (the precedent is B1 Task 2b).
8. **A re-freeze carries one change.** The emission must be a fixed point of one tree, so mixing a new corpus
   with a sentence repair makes the fixed-point proof chase two moving targets (R-273, R-298).

## Working rules

9. `uv run --frozen` for everything, and `uv sync --frozen` rather than a plain `uv run`, which silently
   re-locks a stale `uv.lock` and dirties the tree. `--no-sync` inside an already-provisioned tree; a fresh
   worktree needs `uv run --frozen --extra dev` once or pytest is simply not installed and the suite reads
   broken.
10. The interpreter on PATH is `python3`; bare `python` exits 127 here. Never a `pytest` from PATH -- it
    resolves to a different interpreter than the project's. `requires-python` is a published promise and cannot
    name a version nothing has executed: `3.10` and `3.11` were run on a clean `git archive` export, both synced
    with `uv sync --frozen`, and both refused at rc=4 over a last-place difference in a certificate `meta`, so the
    floor is the version the gate runs, and
    `test_the_declared_python_floor_is_the_interpreter_the_gate_actually_runs` fails the build the moment the
    package metadata, `.python-version`, `ci.yml` and the running interpreter stop agreeing.
11. Lint is the project's own invocation and rule selection:
    `uv run --frozen --extra dev ruff check src tests tools --select=E9,F63,F7,F82,F401,F811 --line-length=120`.
    No `# noqa` and no per-file exclusion to clear a gate, and never relax an assertion to make a check pass:
    if the gate is wrong that is a ruling in the ledger with a reason, not a quieter test.
    `tests/test_cli.py::test_no_source_file_suppresses_the_linter_and_the_config_declares_no_per_file_exempt`
    refuses both -- an inline waiver anywhere in the tree, and a `per-file-ignores` section. A re-export belongs in
    `__all__`, which the linter reads as a use, not in a comment.
11b. A suite run needs the shipped console script on `PATH`: `uv run --frozen pytest` provides it, a bare
    `.venv/bin/python3 -m pytest` from another checkout does not, and the rows that drive `autorate` as a process
    (the rc-1 sweep and the refusal battery in `tests/test_inventory.py`) assert rather than skip, which is the
    behaviour wanted -- a contract sweep that degrades to calling a function certifies a different surface.
12. **A test that is green on arrival proves nothing.** Write the failing assertion first and keep the RED
    output. For every guard added, plant the defect it exists to catch, record the exit code, then restore
    byte-identically and prove the restore with `cmp`.
13. **Before any push: the corpus-less simulation (R-41).** `git archive` the commit, unpack it outside the
    repository with its own `HOME`, and run the suite and `autorate verify` there with the corpus absent. CI can
    only ever witness that lane, so a local corpus-present run proves something CI cannot, and vice versa.
14. **No test counts, suite sizes or pass/fail totals in a commit message** (R-16). CI's own output is the
    honest place for a count.
15. Deliverable prose -- code comments, docs, commit messages -- is English; the conversation with the human
    partner is Chinese.

## Where the reasoning lives

`.superpowers/sdd/<plan>/progress.md` holds every ruling (`R-<n>`) with why it went that way and what it costs
if it is wrong, and it is the recovery map when a session loses its place. `docs/ERRATA.md` is the dated record
of numbers that moved. `docs/VERIFICATION.md` is the evidence ledger for external claims: `verified` only with a
URL opened on a recorded date, `withdrawn` with a `dropped:`/`replaced:` note.
