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

2026-10-04 note (round 3): this entry's main paragraph says "The table above is byte-checked against
that solver", which overstates what the guard does. The accurate description is that it **re-derives the
table cell by cell and requires the two to agree as floats** to `<= 5e-5`. Measured on today's solver,
the ten published cells agree to between 2.8e-6 and 4.9e-5, so the check is doing real arithmetic at a
precision a byte comparison of 4-decimal text cannot express: comparing renderings instead would have
let a cell drift by up to half the last published digit and still match, which is a *weaker* gate than
the numbers here warrant. `verify` is this project's byte gate, and it gates a different artifact
(`docs/RESULTS.md`). The wording is retired by this note rather than edited above: the phrase sits inside
a dated entry, and published corrections in this file are append-only — no line was removed here, and
what is withdrawn is the claim, not the measurement it reports. Both halves of that sentence were written
by commit `0af1fcc` (fix round 2), not by the 2026-10-01 correction they describe, so the defect belongs
to the round that edited this entry. The same guard now also asserts each table row carries the gate plus
one cell for every k in {2, 4, 10, 20, 51}: before that, deleting the LAST published cell left the four
survivors zipped onto the right k, every assertion held, and the row silently stopped covering k=51.

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

2026-10-04 note: this entry's clause "laya's three records per case are byte-identical, so
the repeats were not three observations" states the reason correctly and the evidence
coarsely. Measured on `data/records_feishu.jsonl`, grouped by `case_id` over laya's 192
choice records: **0 of 64 groups** have identical rows — `meta`, `repeat` and `slices` carry
the repeat counter and its own elapsed time — while `probs`, `scores` and `gold` each agree
in **64 of 64** groups. The denominator is earned by the identity of the quantities a bound
reads, not by the identity of the row, so every sentence in this repository now says that
(`README.md`, `docs/RESULTS.md` via its generator, `certify_choice`'s docstring, and the
gate test's own comment). What changes is the wording's precision; nothing about the
denominator, the bounds or the refusals moves, and the measurement is owned by
`tests/test_report_prose.py::test_the_archive_measures_what_the_per_case_bullet_is_allowed_to_claim`
rather than remembered by the prose that uses it.

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

The 2026-10-04 entry titled "the repaired report still published another row's number" (two
entries above this one as written today — located by its title, because an adjacency claim
here has already gone stale once in this file) claimed that
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

## 2026-10-04 — a controller brief proposed replacing the errata guard's float tolerance with a byte comparison, and the arithmetic refutes it

A brief written to settle the round-3 concern ("the guard's `5e-5` is nearly saturated — the worst cell is
`4.8875e-5`, 2.2% headroom") instructed the guard to compare strings instead:
`f"{p_max_for_entropy(target=tau, k=k):.4f}" == quoted`, on the reasoning that the tolerance would then be
"exactly the published precision, with no slack to saturate".

That reasoning is wrong, and it was written before the equivalence was checked. Every published cell is on
the 4-decimal grid, so `round(solver, 4) == quoted` holds exactly when the solver lies in `quoted`'s
rounding basin — which *is* `|solver - quoted| <= 5e-5`. The two checks therefore tolerate the same drift
and differ only on exact midpoints. Converting buys nothing and loses the arithmetic the current check does,
so the guard is unchanged and the proposal is withdrawn here rather than implemented.

Two things the episode does establish, now stated in the guard's own docstring:

- the cells agree to between 2.8e-6 and 4.888e-5 because they are 4-decimal roundings, and that spread is
  the rounding half-step, not solver disagreement; the 2.2% "headroom" is therefore not fragility relative
  to a stricter form — no stricter form exists at this precision;
- what the guard can and cannot see follows from that same half-step: a solver change that leaves every
  published 4th decimal intact passes by construction, and one that moves a value past a midpoint reddens
  it, so the guard's drift sensitivity is set by where each cell happens to sit relative to a rounding
  boundary. Tightening that would mean republishing the cells at more digits, which is a decision about the
  published artifact and not a test change.

Measured before ruling: all ten cells satisfy the string comparison (`0` mismatches), which is the
consistency check that made the equivalence visible. No certificate, no bound, and no published figure
changes; `docs/ERRATA.md` and `tests/test_records.py`'s guard docstring are the only files touched for this.

2026-10-05 note (round 4): this row's sentence "The two checks therefore tolerate the same drift and
differ only on exact midpoints" is right about where they differ and silent about which way, and the
guard's docstring in `tests/test_records.py` went further and called them "the same test, not a stricter
one". Re-measured on the ten published cells, 60 probes at the two rounding-basin edges of each cell (the
edge itself plus one representable double each side): **9 disagreements, every one of them
float-passes-and-string-fails, zero in the other direction**. The examples are the edges themselves --
`0.97855`, `0.96085`, `0.94265`, `0.93185`, `0.92035`, `0.89005`, `0.81065`, `0.69895`, `0.66115` -- each
inside `|x - quoted| <= 5e-5` and each rendering to the wrong 4 decimals. So the string form is
*strictly stricter*, contained in the float form everywhere, and the two are the same test only away from
a midpoint. The same run confirms the rest of the row: all ten cells pass both forms (`0` mismatches),
the worst disagreement is `4.887545e-05` (97.75% of the `5e-5` ceiling), and the binding cell is
`tau=0.50, k=10` with `1.125e-6` of headroom.

One more argument the withdrawal had and this row did not: the string form is sensitive to the published
*text*, not only to the solver. `tau=0.50, k=2` computes `0.889972135562`; against a cell republished as
`0.89` -- the same number, two digits shorter, correctly rounded -- the float check passes and the string
check fails. Converting would therefore let a formatting decision pose as a solver disagreement, which is
exactly the fragility a published table must not acquire. The ruling is unchanged and the guard still
compares floats; only the strength of the sentence describing it is corrected here.

## 2026-10-05 — the MASSIVE rows' count basis moved from three files opened to all fifty-one

The entry above that ends "the file-opened upgrade to '51 of 51 opened and hashed' belongs to the
inventory itself" is the one this row discharges, and it moved two published table rows in
`docs/RESULTS.md` plus the snapshot beside them:

- `massive_intent_all_languages` read *"3 of 51 files opened; the rest counted from the repo listing"*;
  it now reads *"51 of 51 pinned shards opened, hashed and row-counted on 2026-10-05 at revision
  `940fd47a81eaa7f2cc7b129674d945d618ac38c2`; the digests live in `data/massive_provenance.json` and the
  bytes are not vendored"*.
- `massive_intent_per_language` read *"test/de, en, sw.json.gz opened and counted"*; it now reads the
  per-shard row count derived from the same list, because three named files was a description of one
  afternoon's work rather than of the corpus.

The claim is measured, not transcribed. Every shard in the pin list was fetched again over HTTPS from
the pinned revision with certificate verification on, hashed, gunzipped and counted: **51 of 51 digests,
byte lengths and row counts equal the values first recorded on 2026-10-03** (3,221,662 bytes, 151,674
rows, 2,974 per shard, one distinct row count). The id sets are the same across all 51 shards -- 2,974
distinct ids, 148,700 repeats -- which is the identity that makes 2,974, not 151,674, the number a bound
may sit on. That row-count claim had no owner before today: the figures lived in the inventory module as
three constants, and a fourth row could contradict them without anything noticing. They now live in
`data/massive_provenance.json`, whose loader refuses a list that disagrees with its own declared totals
(`n_files`, `rows_total`, `bytes_total`) with `ArithmeticError`, which is the exit code this repository
already reserves for a tool that cannot reproduce its own arithmetic.

Two findings that belong to the record rather than to the artefact:

- The network was the blocker, not the data. Through the local HTTP proxy the handshake for
  `huggingface.co` presents a certificate for `*.facebook.com` and verification fails; with the proxy
  bypassed the same URL returns a valid `CN=huggingface.co` chain and HTTP 200. Verification was not
  bypassed to obtain this result -- the proxy was. Plan C's fetcher can therefore run.
- An independent re-count found the row-count method only by failing first: counting rows as one JSON
  document per shard raises `Extra data: line 2 column 1` for all 51 files, because the shards are JSONL.
  The recorded figure was produced by line counting and survives it; the check that seemed obvious was the
  wrong one.

Reproduce with `uv run --frozen autorate snapshot --out data/inventory.md`, then
`uv run --frozen autorate report --out docs/RESULTS.md`, and read `## Is n big enough to certify?`; the
superseded wording is in `git show af6d09a:docs/RESULTS.md`. `uv run --frozen autorate verify` re-derives
the new basis in both arms (65/65 with the corpus, 34/34 without).

## 2026-10-05 — two spec sentences that the code and a measurement contradict (rows owed since the fixes landed)

The corrections were committed on 2026-10-05 in `92daefc` and `3a38659`; this file is where a published
document's defects are recorded, and no row was written when they were made. Both rows are recorded here
rather than restated in full -- the binding text is in the spec, which keeps the superseded sentence in
place under a dated correction marker so the change stays auditable.

- **§5.4 specified a family that cannot have both properties it required** (ledger R-68). Its construction
  -- the minimum-length contiguous span whose mass is at least `q`, ties broken leftmost then by the
  recorded `u` -- is contiguous but **not nested**: measured over 2,000 random ballots of 2-8 levels,
  3,333 of 17,788 adjacent `q` pairs violate nesting (smallest counterexample `p = [0.159, 0.381, 0.460]`,
  where `C` at `q = 0.159` is `[1]` and at `q = 0.381` is `[2]`). Reading the family through the score
  instead restores nesting but abandons contiguity: 3,057 of 14,540 sets are non-contiguous. So the
  sentence "nesting gives split-conformal validity unchanged" asserted a property of a family that does
  not have it. The nested *and* contiguous construction is the modal-anchored chain -- `s(x, y)` is the
  mass of the minimum-mass contiguous span containing both `y` and `argmax p(x)`, `C_alpha` its sublevel
  set -- measured on the same protocol at 0 non-contiguous sets in 32,304 and 0 nesting violations in
  141,120. Plan B2's Task 1 now builds that family. **These probe numbers come from a throwaway script,
  not from a committed test:** Plan B2 has not been executed, and its Task 1 is written to make contiguity
  and nesting properties the suite asserts. Until then the figures in this row are the controller's
  measurement, not the repository's.
- **§3's L1-source list called `laya_eval`'s per-case output "a conformal calibration stream, already
  emitted"** (ledger: the spec/Plan C contradiction about the same artefact). Three measurements refute it:
  the per-case dict reaches the output only when `--out` is passed, so nothing is emitted by default and no
  such file exists anywhere in the vendored tree; the committed `research/results/*.json` are aggregates;
  and the record carries three scalars derived from the distribution (`probability`, `p_gold`, `confidence`)
  but never the distribution, so §5.2's APS nonconformity cannot be reconstructed from it. The bullet now
  says what the field *can* feed -- a score-threshold rule (§6.4) and marginal-error bookkeeping -- and
  agrees with Plan C's own measured answer ("usable as an L1 source? **No.**").

Reproduce the second row from the source: `sed -n '244,266p;348p;368,372p'` on the vendored
`research/eval/laya_eval.py`, and `grep -rl "p_gold"` over the vendored tree returns nothing. The vendored
corpus is read-only; nothing here was written to it.
