# Errata

Corrections to numbers this project published and then measured differently. Kept as a
tracked file because the rule is that a quoted count must be the count the tool printed.

## 2026-10-01 — commit `e386c08` message quoted the wrong test count

The commit body says `45 passed overall`. The full-suite gate printed:

```
46 passed in 0.42s
```

The 45 was summed from an earlier focused run instead of read off the suite output. The
commit was not amended (history is preferred over message accuracy); this entry is the
correction, and the ledger repeats the measured number.

## 2026-10-01 — commit `a106cd2` quoted the wrong test count, again

The body says `62 passed`; the gate printed `63 passed in 0.56s` on that tree. This is the
second occurrence within minutes of the first entry, so it is a habit rather than a typo:
commit messages were being written from the most recent run I had seen rather than the one
the commit describes.

**Rule adopted (ledger R-16): commit messages no longer quote suite counts at all.** A count
in prose has no owner and goes stale the moment a test is added; the count that matters is the
one `pytest` prints when CI runs it, and any *number published as a result* must be produced
by the code that reports it (Constraint 12), which Task 9's `verify` enforces. Not amended;
this entry is the correction.


## 2026-10-01 — an entropy-confidence figure was wrong in both value and direction

Design prose stated that gating at `confidence >= 0.85` corresponds to `p_max >= ~0.93`
for a four-option question, implying the requirement loosens as the option count grows.

Measured by bisection over `autorate.records.entropy_confidence`:

| gate | k=2 | k=4 | k=10 | k=20 | k=51 |
|---|---|---|---|---|---|
| `confidence >= 0.85` | 0.9785 | 0.9609 | 0.9427 | 0.9319 | 0.9203 |
| `confidence >= 0.50` | 0.8900 | 0.8107 | 0.7379 | 0.6990 | 0.6611 |

So the `0.93` value belongs to **k=20**, the requirement is **stricter at small k**, and a
`0.93` answer over four options scores `0.7616` — it does not clear the documented gate.
Corrected in the plan's Task 4 test, added as spec §7.4, and now produced by
`tests/_thresholds.py::p_max_for_entropy` rather than quoted from prose. The table above is
byte-checked against that solver by
`tests/test_records.py::test_the_errata_table_matches_the_function_that_produced_it`,
which reads each cell here and requires agreement to 5e-5.

2026-10-04 note: until the Task 2 fix round 2 merged the suite's two copies of the bisection,
this entry named `tests/test_records.py::_pmax_reaching`, the local copy. The solver, the
figures and the guard test are unchanged; only the producing function's file and name moved,
and the parameters are keyword-only now so a transposed call cannot pass silently.

## 2026-10-01 — a controller commit silently reverted Task 2's spec narrowings

Commit `e386c08` (Task 4, written in the controller session) restored
`docs/superpowers/specs/…design.md` from a **second working copy** of the same document at
`<workspace>/laya/docs/…`. The Task 2 agents had edited the repository copy; the workspace
copy still held the pre-Task-2 text, so the copy-back reverted every narrowing that round had
made. Re-introduced at that commit and undetected by CI:

- the withdrawn acronym **KIGEL** and the name "Calibrated Errors" for a bound whose paper does
  not use them (ledger rows `kigel-acronym`, `two-way-bound-construction-source`);
- the invented venue **AISTATS 2023** for the ordinal CRC paper, which is UAI 2023
  (`ordinal-cp-aistats2023`);
- §1's unscoped "Nobody can answer it", "roughly four papers and no implementation", and
  the `~20k`-star figure (`ordinal-cp-literature-size`, `laya-star-count`);
- §14's "MAPIE is marginal-only, no two-way bound" (`mapie-risk-control-coverage`,
  `mapie-abstention-rate-example`, `mapie-exchangeability-tests`);
- the machine-local private path in §15/§17; and §17's quoted census line, gone entirely.

Found by the Task 2 re-review, not by any gate: the ledger gate reads only `docs/VERIFICATION.md`,
so a spec that re-publishes withdrawn claims passed CI. Two responses, both landed:

1. **Restored by merge, not rollback.** `df690fc`'s spec plus §7.4 (the only genuine later
   addition) — verified line by line, since a plain revert would have deleted §7.4 too.
2. **`tests/test_verification_table.py` now reads the spec**: it must quote the census line the
   gate emits, and any line mentioning a withdrawn identifier must cite the ledger row that
   withdrew it. Demonstrated against the real damage: pointing a scratch tree at `e386c08`'s spec
   reddens exactly those two tests. Word-list policing was tried first and abandoned — it cannot
   tell a correction from a use, which is why the rule is "cite the row" instead.

The hazard itself is gone: the two copies were collapsed to one file, with the workspace path now a
symlink into the repository, so there is no longer a stale twin to copy backwards.


## 2026-10-02 — the first certified number was computed on the wrong denominator

`docs/RESULTS.md` published a jev row reading `autorate 1.000`, `conditional error <=
0.031`. A whole-branch review found the denominator behind it was wrong, and the number
went with it.

What was measured afterwards, on the same committed inputs:

- the split was over archive **records**, so repeats of one case landed on both sides: 44
  of the 53 distinct cases in jev's evaluation half were also in its calibration half, and
  the quantile was fixed on the cases later held out to test it;
- the bound divided by 96 records where the corpus supplies 64 independent cases, and laya's
  three records per case are byte-identical, so the repeats were not three observations;
- at the case denominator, a zero-error run over 32 evaluation cases bounds at **0.089**,
  above the 0.050 budget. The row is a refusal, not a certification.

Both backends now refuse on this corpus, which is what the project's own n-feasibility
table (`data/inventory.md`, width 0.3395 at n=64, "feasible at 0.10: no") had said all
along. The certificate pair is still the deliverable — two refusals with their reasons and
their observations — and the pair is now genuinely paired: both evaluation halves cover the
same 32 cases.

**Rule adopted (ledger R-44): the unit of certification is the case, and the bound's
denominator is stated next to every published rate.** The record counts stay on the
certificate because they are what the gate acts on, but they are never the `n`.

## 2026-10-03 — `Record.from_dict` dropped `case_id`, so the case denominator was not the one published

The row above is correct about the unit and wrong about two numbers it quotes, because the round trip
that produced them lost the field that carries the unit. `to_dict` wrote `case_id`; `from_dict` never
read it back, so every record loaded from the committed artifact came home with `case_id = None` and
`certify_choice.case_key` fell through to the record `id`. The partition over cases was unchanged — same
64 groups — but the seeded split sorts those keys before shuffling, so the key strings re-rolled the
permutation and 13 of 32 cases swapped halves. The held-out set became a different set of cases.

What the published pair says now, regenerated from the same committed records (no re-export: all 1919
rows already carried `case_id`; the defect was on read):

- **jev** — `conditional_error_bound` **0.089 → 0.140**. It automates 32 of 32 evaluation cases and
  **1** of them carries a wrong automated request, where the stale row reported 0 errors. The
  `errors: 0` figure that made "a zero-error run over 32 cases" a description rather than a
  counterfactual was itself an artefact of the lost key.
- **laya** — it no longer automates nothing. On the re-rolled half it automates **2 of 32** cases, 1 of
  them wrong, so its case-level bound is **0.975**. The reason code is unchanged
  (`empty_feasible_set`), and the refusal still holds at the 0.050 budget.
- Both evaluation halves still cover the same 32 cases, so the pair remains genuinely paired.
- The zero-error bound over n=32 is still **0.089** — but as the counterfactual it always was: even had
  that one request been right, this corpus could not support a 5% claim.

Two published sentences were also refuted by the artifacts printed beside them, which is the same defect
class in prose: the report asserted "not one evaluation case produced a single-label set" for laya while
its own counts showed 2 automated cases, and it interpolated a zero-error bound while naming the actual
error count. Both clauses are now derived from the certificate -- `report._refusal_clause` and
`report._budget_clause`, plus the record-denominator clause rendered from the certificate's own counts —
pinned by `tests/test_report_prose.py`, including a control
that the old hardcoded prose *passed*, which is why it is kept and labelled as insufficient.

**Rule adopted (ledger R-51): a field a published number depends on must survive the round trip that
produces the number, and the round trip needs a test that carries that field — the existing `to_dict` /
`from_dict` tests compared `None == None` and could not see it.** A rate whose denominator is rebuilt by
a lossy read is not the denominator the bound claims.

## 2026-10-04 — the repaired report still published another row's number

The row above is accurate about the certificates and the cause. It is not accurate about one sentence of
the report it shipped beside them: for laya, `docs/RESULTS.md` read *"a zero-error run over the same
n=32 would still have bounded at 0.089"*, where laya automates **2** of its 32 evaluation cases, its
bound was computed over those 2, and the counterfactual at its own denominator is
`clopper_pearson_upper(0, 2, 0.05)` = **0.776**. The 0.089 is jev's figure, at jev's denominator.

How it survived: the fix that introduced the sentence quoted the counterfactual at `n_eval_cases`, and
every test written alongside it patched jev and asserted on jev's clause. The misattributed laya clause
rendered in all eight of them and nothing read it — a test suite that asserts on the half of the output
it just changed.

Corrected now, and the discipline recorded with it: the counterfactual shares the denominator of the
bound it qualifies; the record-denominator figure is read from the certificate's own `closest_attempt`
instead of being recomputed in the report, because the recomputation gave a published number two owners
and produced the identical 0.0485 that the artifact already carries; the verdict word (`inside`/`above`)
is derived from the comparison; a missing bound drops the sentence instead of printing `nan`; and the
lead-in says what the rows did (`Both rows certify` / `N of M rows refuse`) rather than asserting a
refusal. `tests/test_report_prose.py` now asserts the shipped **laya** clause directly, 8 of its 11
tests fail against the commit that introduced the error, and one of them builds a real early-refusal
certificate rather than zeroing the counters that the defect is about their absence.

Nothing in the certificates, the README, or the numbers above changes: this is a sentence in the
generated narrative, not a bound.

Reproduce the corrected sentence with `uv run --frozen autorate report --out docs/RESULTS.md` and read
the `### What this does and does not establish` bullet; reproduce the superseded one from commit
`12c87d7` the same way. (The command is named here because the row above mine omitted it, which its own
brief required -- an omission in my same-day row, supplemented rather than rewritten.)

## 2026-10-04 — the report's denominator paragraph typed four numbers it did not own

`docs/RESULTS.md` stated, in prose: "MASSIVE's 51 language files are translations of the same 2,974
utterances, and feishu's 384 archive lines are 64 cases repeated."

Two of those claims were stronger than this repository's evidence at the time it printed them:

- the inventory it sat above records the MASSIVE option's basis as **"3 of 51 files opened; the rest
  counted from the repo listing"**, so "51 language files are" read as though all 51 had been opened
  when the artifact said three;
- `384` is one backend's line count; the archive holds **768** lines across both backends for 64 cases,
  so the sentence mixed denominators with the number it used to argue them.

Neither figure was wrong in intent — 51 files and 2,974 rows per file are real, and each was counted by
hand later on 2026-10-03, when all 51 pinned shards were re-hashed against their recorded digests and
the id sets proved identical (union = intersection = 2,974). But a number typed into prose has no owner,
which is how it stayed behind the artifact it described. The paragraph now reads its figures from
`data/inventory.md.json`, quotes each option's own recorded basis instead of restating it, and asserts
the translation claim only while the per-language and pooled options report the same row count — if they
ever disagree, the sentence stops claiming rather than repeating. The file-opened upgrade to "51 of 51
opened and hashed" belongs to the inventory itself, which is where the claim will then have an owner.

Reproduce with `uv run --frozen autorate report --out docs/RESULTS.md`, and read `## Is n big enough to
certify?`; the superseded wording is in `git show b9f237b:docs/RESULTS.md`.

## 2026-10-04 — the same-day fix-round row under-counted its own failures

The row above this one ("the repaired report still published another row's number") claimed that
`tests/test_report_prose.py` stood at 11 tests of which **7** failed against `12c87d7`, the commit that
introduced the misattributed counterfactual. Re-measured in the next round: **8 failed, 3 passed**. The
figure in that row now carries the measured number; **this note supersedes the 7 the row first carried**,
and no other claim in it changes.

The measurement is reproducible without touching a worktree: take the 11-test file at `d1cc88a` and run it
against `12c87d7`'s `src/autorate/report.py` in the current tree. That swap is the whole difference,
because `git diff --stat 12c87d7 0af1fcc -- data/ src/autorate/` touches only `cli.py`, `report.py` and
`scales.py` — every certificate, record and fixture the tests read is byte-identical across the three
commits. The count was stated in the row because the row's claim is that the suite *could see* the defect;
stating it from memory is the same error class as stating a number that was never run.

Nothing in the certificates, the report's figures, or the sentences above changes: this is a count of
tests in a narrative row, not a bound.
