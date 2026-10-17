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

2026-10-07 note (round 5, R-91): the note above corrected one sentence of this entry -- "differ only on
exact midpoints" -- and left standing the two sentences that state the same error more strongly. That is
not a retirement, so both are quoted here and refuted by name. Neither line above is edited; this file
records what was published.

- From the round-3 note of the 2026-10-01 entry "an entropy-confidence figure was wrong in both value and
  direction": *"comparing renderings instead would have let a cell drift by up to half the last published
  digit and still match, which is a **weaker** gate than the numbers here warrant"*. **Retired.** The
  string form is never looser than the float form anywhere the two were probed: over 60 probes at the two
  rounding-basin edges of the ten published cells every disagreement is float-passes-and-string-fails and
  there are zero in the other direction, so the string form is *contained in* the float form and calling
  it weaker had the relation backwards. Its magnitude was right -- half the last published digit of a
  4-decimal cell is the same `5e-5` the float check compares at, which is exactly why the two agree away
  from a midpoint -- and it is only the direction that is withdrawn.
- From this entry, two paragraphs above that note: *"the 2.2% "headroom" is therefore not fragility
  relative to a stricter form -- no stricter form exists at this precision"*. **Retired.** A stricter form
  does exist at this precision: it is the string comparison, and it is stricter at nine of the sixty
  probes. The 2.2% figure itself stands and was never the fragility of a tolerance running out -- it is
  `5e-5 - 4.8875446e-05 = 1.1245539e-06`, 2.2491% of the ceiling, the distance the binding cell
  (`tau=0.50, k=10`, published `0.7379`) happens to sit from a rounding boundary.

2026-10-07 note (round 5, R-87): the figures the 2026-10-05 note states in the present tense -- `60
probes`, `9 disagreements`, `zero in the other direction`, `0` mismatches across the ten cells, the nine
named edges, `4.887545e-05`, `97.75%`, `tau=0.50, k=10`, `1.125e-6`, `0.889972135562`,
`f"{0.96095:.4f}"` rendering `0.9609`, and the `0.89` republishing argument -- had no producer when they
were written. The only code beside them was the guard's `<= 5e-5`, which cannot see a single one: no
basin-edge probe, no min or max disagreement, no string form at all. They have a producer now, in the
repository and in the suite: `tests/test_records.py::test_the_string_form_is_strictly_stricter_at_the_ten_basin_edges`
reads this table's cells through the same reader the guard uses, sweeps each cell's two rounding-basin
edges at the edge itself plus one representable double either side, and asserts every value listed above;
the guard's own docstring points here instead of at a run. Option (a) of the ruling rather than (b): these
values carry a published claim about the guard's own drift sensitivity, so they are recomputed rather than
demoted to a dated record. `5e-5` is now one constant, `tests/test_records.py::HALF_STEP`, shared by the
comparison and by the edges it justifies -- previously a literal in one place and a magic number in the
other. The sweep also produced the recipe this entry left as a parenthetical: an edge is `quoted +/-
5e-5` computed in doubles, and the nine named edges are what those values render at five decimals.

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

## 2026-10-06 — a review's six findings, and the first live fetch that refuted one tool's own contract

The Task 1b review (`.superpowers/sdd/…/task-1b-review-report.md`) reported no blocker but six
majors; all six were re-measured against the code before anything changed, and the fixes are in
`202686c` and the commit that adds this row. Three of them were not the controller's own claims but
claims the artefact made about itself:

- **The shared line rule has an order** (M2). The scanner required its `LINE_KEYS` at parse time while
  the reader refuses a non-`ok` line before reading any field, so one line missing both `id` and
  `status` was `malformed_line` to the inventory and `lines_dropped_not_ok` to the reader. Measured
  before the fix: `lines_quarantined_only == {'malformed_line': 1}` beside
  `reader_lines_quarantined_only == {}` for the same bytes. The two published ledgers now agree on both
  shapes, and the assertion that was supposed to police their equality is now exercised on a non-`ok`
  line, which the whole planted corpus had hitherto omitted.
- **`present - kept` is not `quarantined`** (M1). The markdown subtracted the reader's kept-line count
  from the scanner's line count and labelled the remainder a quarantine, so a line the reader declined
  on its own rule was charged to its quarantine. The reader's three dispositions are now published and
  named separately: malformed / named-by-mode / refused / filtered.
- **A guard that compares a figure to itself** (M4). `report._denominator_note` asserted the MASSIVE
  translation claim while `pooled.n_independent == per_lang.n_independent` -- both produced by one
  expression in one module, so the equality could not have failed and the docstring's promise that "a
  future divergence silences the claim" described nothing. The claim now requires
  `rows_total == distinct_ids x n_files` with the independent count read from a field that was produced
  by comparing the shards' id sets, and `tests/test_report_prose.py` plants a 52nd shard with a
  different id count to show the sentence goes quiet.
- **The independent count had no owner** (M3). Both MASSIVE rows filled `n_independent` from
  `files[].rows`; the equality of "2,974 rows per shard" and "2,974 distinct utterances" is exactly the
  claim under dispute, so it is now a recorded measurement with its own field.
- **A repository data defect filed as the operator's mistake** (M5). Truncating the pin made
  `autorate snapshot` exit 2 (`JSONDecodeError` is a `ValueError`, mapped to EXIT_USAGE); deleting it
  made the same command exit 0 with the rows reading "not opened". Both now refuse as
  `ArithmeticError`, which this CLI already means as "cannot re-derive my own numbers" -> rc 4.

**The fetcher's rc-1 claim was false, and only a real network could show it.** `tools/fetch_massive.py`
documented that exit 1 is unreachable "by construction: every raise site is one of these three, or an
`OSError` from the filesystem". Its first live run stopped on two shards with
`http.client.IncompleteRead` -- a CDN closing a body early, neither an `OSError` nor a `FetchError` --
and the process died with a traceback and exit 1. That is now a named refusal at the seam
(`read_bytes`), with a test that plants the truncated read and asserts rc 4 with no traceback. Nothing
about the failure was visible to 71 offline tests built on a transport seam that only ever returned
clean bytes or an `HTTPError`: a seam that cannot deliver the ordinary network fault tests the mock, not
the transport.

The retry verified the corpus properly, and the pinned figures are now backed by the committed tool
rather than by a controller script: all 51 shards re-downloaded from revision
`940fd47a81eaa7f2cc7b129674d945d618ac38c2` with certificate verification on, **51 of 51 ok, 0
mismatched, 0 missing**, and `ids` reporting `distinct_id_sets: 1`, union = intersection = **2,974**
(`n_independent: 2974`). Consequently one published sentence moved: the MASSIVE basis now reads
"opened, hashed and row-counted on **2026-10-06**" where this file's 2026-10-05 row quoted
2026-10-05 -- the date is the most recent verification, not the first. No count changed; `verify`
re-derives 68 figures with the corpus present and 34 without.

Reproduce: `uv run --frozen python tools/fetch_massive.py fetch --dest <cache>` (bypass the local HTTP
proxy; verification is not bypassed), then `verify --cache <cache>` and `ids --cache <cache>`, or run
the gated test with `AUTORATE_MASSIVE_CACHE=<cache> uv run --frozen pytest tests/test_provenance.py`.

## 2026-10-06 — the 2026-10-05 row credited `verify` with a check it did not perform

This file's entry titled "the MASSIVE rows' count basis moved from three files opened to all
fifty-one" closes with "`uv run --frozen autorate verify` re-derives the new basis in both arms (65/65
with the corpus, 34/34 without)". That sentence was false when written, and it was false in the worst
way: not overstating a number, but crediting a gate with a comparison it never made. `grep -n
"corpus_options\|basis" src/autorate/cli.py` returned nothing -- the verification loop compared
certificates, digests, the report bytes and the inventory bytes, and no figure it read had come from
`data/massive_provenance.json`. In the corpus-less lane the inventory itself is transcribed from the
committed snapshot, so a pin edited on disk could not contradict anything; the 65 and 34 counts were
accurate, and the claim about them was not. A reviewer found it as a minor against the round.

The comparison now exists. `verify` re-derives each MASSIVE option's `n_rows`, `n_independent`,
`n_shards` and `basis` from the pin and expects them against the published table, in both lanes, which
takes the gate to 75 values with the corpus and 41 without. Falsified rather than asserted:
`tests/test_cli.py::test_verify_reds_when_the_pin_and_the_published_rows_disagree` drops one shard
from a copy of the pin, leaves that copy internally consistent (50 x 2,974 = 148,700 rows, and every
declared total matching its entries, so no loader check fires), and requires `verify` to exit 4
quoting both 148,700 and the published 151,674. The first version of that control ran the CLI in a
copied checkout and stayed green for the wrong reason: the pin path is resolved from the package's own
`data/`, not from the working directory, so the tampered file was never read. Both facts are worth
having -- which inputs a gate actually consults, and where those inputs live.

The superseded sentence is left in place above, since this file records what was published rather than
what is currently true.

## 2026-10-06 — the two ledgers published side by side disagreed about the shipped corpus's own line

Task 1b's first fix round closed review M1/M2 by making the scanner ask the reader's first question
first, and left the rest of M2's own table open. Re-measured against the shipped corpus at `5ec8639`,
the two quarantine ledgers the artefact publishes beside each other were **not** equal: the scanner
counted the `jev / lifecycle-01 / repeat=1` line in `lines_by_mode_backend["choice/jev"]` while the
reader quarantined it, so the artefact read `lines_quarantined_only: {}` next to
`reader_lines_quarantined_only: {"choice": 1}` -- and the comment over those two keys asserted they
mirrored each other. Two published numbers move with the reconciliation, both in the same direction
(the line is now named rather than bucketed, which is what the reader has always done with it):

- `lines_by_mode_backend["choice/jev"]`: **192 -> 191**. The 192 `choice` lines archived on jev have
  not changed; one of them is no longer counted *inside* the table.
- `lines_quarantined_only`: **{} -> {"choice": 1}**, now equal to `reader_lines_quarantined_only`.
- One new key, `lines_refused_not_ok` (**0** on this corpus, because all 768 archived lines carry
  `status: "ok"`): a line refused on its own `status` is now counted there rather than in the per-mode
  table, mirroring the reader, which declines a line before it reads a `mode`. Review M2's rows 3-5
  were this shape: `mode: "ranked"` with no `status` measured `{'ranked': 1}` from the scanner and
  `{}` from the reader, and a missing `mode` was published under the literal key `"None"`.
- `data/inventory.md` gained its first disclosure sentence of that line ("1 archive line(s) sit
  outside the per-mode counts (0 unreadable, 1 readable but refused by the line rule the reader
  owns) ... jev line 269 id=lifecycle-01"), and `docs/RESULTS.md`'s gap count moved **5 -> 6** as the
  same disclosure reached the report's first-clause list. The per-mode bullet still reads
  "383 of 384 lines kept by the reader (1 quarantined for this mode)" -- the denominator is now
  bucketed + named rather than the table alone, so the sentence did not have to move with them.

No other count moved: `unique_ids` 64, `reader_lines_read` 768, `records per backend` 960/959, and
every MASSIVE figure are what this file's earlier rows quoted. The keys the reconciliation touches
are re-derived, not transcribed: `uv run --frozen autorate snapshot --out data/inventory.md`
then `uv run --frozen autorate report --out docs/RESULTS.md` reproduce both artefacts byte for byte,
and `uv run --frozen autorate verify` re-derives **82** values with the corpus present and **47**
without (the corpus-less lane cannot see the counts, which is why the equality is also asserted
against the committed artefact itself, in
`tests/test_inventory.py::test_the_committed_snapshot_publishes_the_two_quarantine_ledgers_as_one_dict`).

One boundary is recorded rather than fixed: the scanner reproduces the reader for the shapes the
shared rule names, but not for a `four_noul` line's per-ask refusals ("carries no noul-typed answer",
"noul probability outside [0,1]"), because mirroring those would mean a second implementation of the
record-building rule -- the drift R-55 exists to prevent. This corpus contains no such line (measured:
its `four_noul` ledger is empty), and the divergence is pinned as data in
`tests/test_inventory.py::test_the_scanner_does_not_mirror_the_reader_s_per_ask_quarantine`.

## 2026-10-06 — two sentences in this file quoted a `verify` count the tip does not produce

The row above ("the two ledgers published side by side disagreed about the shipped corpus's own
line") moved the gate's own totals, and re-reading this file found a second, older case of the same
defect: a published present-tense sentence about the gate that the artefacts at the same commit
contradict. Both are named here rather than edited in place, because this file records what was
published.

- The 2026-10-06 row titled "a review's six findings, and the first live fetch that refuted one
  tool's own contract" states, two paragraphs from its end: *"No count changed; `verify` re-derives
  68 figures with the corpus present and 34 without."* Those were the counts on the tree that row
  described. The next row in this file ("the 2026-10-05 row credited `verify` with a check it did
  not perform") superseded only the 2026-10-05 row's 65/34 sentence and never named this one, so
  68/34 survived as the file's most recent-looking statement of the gate while the tip printed 75
  and 41.
- That 75/41 is now also stale, twice over. Adding the three bound columns to the pin arm (R-83)
  took the corpus-less lane from 41 to 47; publishing `lines_refused_not_ok` as a snapshot key and
  naming the shipped corpus's unclosing line took the corpus-present lane from 75 to 82.

Measured on this commit, both rc 0: `uv run --frozen autorate verify` re-derives **82 /82** values
with the corpus present, and `AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen autorate verify`
re-derives **47 /47** without. The counts are not typed here either:
`tests/test_cli.py::test_verify_runs_and_agrees_where_the_corpus_does_not_exist` derives the 47 from
`CERT_COMPARE_FIELDS` and `autorate.cli.PIN_DERIVED_KEYS`, which is the list the gate itself
iterates, so a column the arm stops comparing has to widen a test before it can narrow the gate.

## 2026-10-07 — README credited `verify` with re-deriving the two bound columns the pin arm did not reach

`README.md:86` says `docs/RESULTS.md` is emitted by `autorate report` and that "`autorate verify`
re-derives every value in it". That sentence is true of this commit. It was not true when the pin arm
was added, and this is the third member of the family the 2026-10-06 row "the 2026-10-05 row credited
`verify` with a check it did not perform" names: prose crediting the gate with a comparison it never
made, while every figure it did quote stayed correct.

The window, read out of the commits rather than remembered:

- `106f4f0` (2026-10-06 11:03) added the pin arm: `verify` began re-deriving each MASSIVE row's
  `n_rows`, `n_independent`, `n_shards` and `basis` from `data/massive_provenance.json`. It stopped at
  the inputs. The same published rows also carry `bound width at alpha=0.05` and `feasible at 0.10`, and
  `corpus_options` computes both FROM those inputs -- `tails.bound_width(n)` and `tails.n_feasible(n)` at
  `src/autorate/inventory.py:640-644` -- so a pin with intact counts and mis-transcribed bound columns
  left the corpus-less gate at rc 0 with every comparison it does make satisfied. The README sentence
  covered those columns in the present tense and nothing did.
- `d3e66ca` (2026-10-06 11:55) widened the arm to those columns through `PIN_DERIVED_KEYS`, which is the
  list the gate iterates. From that commit the README sentence is true of the whole published table.

Measured further back than the ruling's window, and recorded because it is the same defect and a narrower
one would have been a courtesy to nobody: those two columns entered the generated document at `6aed7ae`
(2026-10-01), the same commit that wrote the README sentence, and `verify` consulted the pin not at all
until `106f4f0`. So the over-claim runs from 2026-10-01 to `d3e66ca` -- not merely the fifty-two minutes
between the two 2026-10-06 commits. What `106f4f0` changed is that re-deriving them became possible at
all; the columns had been unowned for five days.

Confirmed rather than assumed. `uv run --frozen pytest -p no:randomly -q
tests/test_cli.py::test_verify_reds_when_a_transcribed_bound_column_is_wrong`, run in a `git archive`
export of this lane's `2494301` -- a committed tree, so no other lane's uncommitted work was in it --
exits 0. The test carries both arms itself: the tampered copy -- both MASSIVE rows' bound width
set to `0.01` against a true `0.0498`, `feasible at 0.10` set false -- must exit 4 naming both columns
and must NOT be caught by a byte comparison, and the same tree re-rendered through the repository's own
writers with the true numbers restored must exit 0. Without the second arm the first would only prove
the markdown disagrees with itself.

The README sentence was not hedged and no hedge belongs in it: the gate re-derives those values today,
and a claim qualified for a defect that no longer exists is its own inaccuracy. The disclosure lives
here, in the file that records what was published rather than what is currently true.

## 2026-10-07 — "re-derives every published number" held on the machine that wrote the artefacts and red on the runner

The disclosure this owes is not that a number was wrong. It is that `README.md:86`'s sentence -- and G5's
literal measurement, "`autorate verify` re-derives every published number" -- carried an unstated premise:
that a double stored by one C library is reproduced bit for bit by another. `verify` compares re-derived
certificate values with `==`, which is an exact gate only if the committed bytes are reproducible exactly,
and two published field families are not. `conditional_error_bound` and `marginal_error_bound` come from
`tails.clopper_pearson_upper`, inverting a binomial tail through `math.log` and `math.exp`, and the last
bits of those transcendentals differ between Apple libm and glibc.

- Measured on the runner at `351845e`: the recomputed `cert laya.meta` bound was `0.7884344428029711`
  where the artefact stored `0.7884344428029715`. Four units in the last place of a double -- 4e-16 -- red
  in CI, green locally, and ten seeded reruns of the whole suite in a clean export were green each time --
  although that evidence does not show what it appears to: `pytest-randomly` is not a dependency of this
  project (absent from `uv.lock` and both venvs), so `--randomly-seed` changed nothing and the ten reruns
  were ten copies of one deterministic order. What actually left the platform as the only variable was the
  artifact diff itself, which named the field and the four units, together with the fact that test order is
  not a variable here at all (ledger R-121, re-measured and corrected as R-140).
- Measured across the three byte-compared surfaces before fixing anything (ledger R-122): the drift could
  not move a reading a reader sees. Re-measured on this commit's artefacts, `docs/RESULTS.md`'s longest
  fraction is 3 decimals and `data/inventory.md`'s is 3, while `data/cert_laya.json` stored 16. So the
  exposure was the stored artefact's bytes, not a published figure -- which is also why the fix moves
  artefact bytes and no rendered number.

`4185f87` canonicalises at the producer instead of loosening the comparison everywhere:
`certificate.PUBLISHED_DECIMALS = 12` and `CANONICALISED_BOUND_FIELDS = ("conditional_error_bound",
"marginal_error_bound")`, mapped as a ceiling onto that grid so the published upper bound is never rounded
down, and taken from the nearest value rather than `math.ceil(x * 1e12) / 1e12` so the mapping is
idempotent -- the producer rounds, the artefact stores what it rounded, and the gate compares those two.
Named fields only: the certificate's other floats are quotients of integers or correctly-rounded sums, and
IEEE 754 requires `+ - * /` to be exactly rounded, so they already agreed on the runner (25 of the 28
diagnostic-curve points matched, and every mismatch was a bound). A blanket tolerance would have absorbed a
genuinely changed automation rate as cheerfully as it absorbs a libm difference, which is what the ruling
forbade.

Measured after, on the committed artefacts: `data/cert_laya.json`'s bound fields are stored at 12 decimals
(`0.974679434481`, `0.77499233523`) where they were stored at 16 (`0.9746794344808963`,
`0.7749923352291154`); the `observed_*` ratios and `qhat` keep full precision, deliberately and by name.
`docs/RESULTS.md` does not move. The artefacts were regenerated through `autorate certify`, not edited.

What the sentence means now, stated rather than implied: `verify` re-derives every published number **to the
precision the number is published at**. That is what a reader needs from a reproduction claim and what a
byte-exact double was never actually promising. The gate still bites -- `tests/test_certify_choice.py`
carries the pair that distinguishes a fix from a blinder, `test_verify_absorbs_a_last_bit_libm_drift_and_stays_green`
and `test_verify_reds_when_a_bound_moves_in_the_tenth_decimal`, plus
`test_a_stored_bound_the_producer_cannot_write_is_still_drift` for the stored side, while
`tests/test_certificate_shape.py::test_the_canonical_field_list_is_exactly_the_bounds_the_shape_publishes`
makes widening the field list a deliberate two-file edit and
`test_the_canonical_form_is_idempotent_a_ceiling_and_swamps_the_libm_drift` pins the mapping's own property.

No published figure in this project changed, and none of the sentences above is a correction of a number:
the CI failures were real, the local greens were real, and the gap between them was the unstated premise.

## 2026-10-08 — three certificates were published while `verify` re-derived two of them

G1's three MASSIVE certificates (`data/cert_massive_{en,de,sw}_laya.json`) were committed and CI-witnessed
at `72edd91`, and every published sentence about them was true: each refused at the pre-registered rubric,
each reproduced digit for digit by a second CLI run, and a probe over the committed records re-derived all
48 values they carry. What none of that did was make the gate re-derive them. `cmd_verify` had one
certificate loop, over `CERTS`, and G1's artefacts were not in it -- so this file's own headline claim,
that `verify` re-derives every published number, was true for two artefacts and untested for three, and the
denominator it printed (`47 /47` corpus-absent, `82 /82` corpus-present) was the measure of the gap rather
than of the gate.

The fix is the arm, not the assertion. `report.py` now owns the table (`MASSIVE_CERTIFICATES`: which records
file each certificate was made from, in the same module that prints them), and `verify` calls
`rederive_massive(expect, CERT_COMPARE_FIELDS)` beside the loop it already ran. The field list is passed in
rather than copied because `CERT_COMPARE_FIELDS` has one owner, in `cli.py`; the rubric is read out of each
artefact rather than chosen by the gate, so a re-derivation cannot certify a refusal into a pass by picking
better numbers.

Measured after, both rc 0: corpus-absent `re-derived 95 /95 values`, corpus-present `re-derived 130 /130`.
The gap between the two lanes is still exactly 35 checks -- the 9 upstream `SOURCE.json` digests and the 26
snapshot keys -- because everything the widening added is corpus-independent, which is what the pin arm was
already for. `README.md` now quotes 95 and 130; the rows above this one keep the figures they measured, and
were written to be read as dated.

Two tests had to be completed, and what they proved is worth more than the edit. Both built a scratch
checkout from a hand-kept list of published file names (`records_feishu.jsonl`, `cert_laya.json`,
`cert_jev.json`, …). Once the gate read the third table, each died on a `FileNotFoundError` for
`data/cert_massive_de_laya.json` *before* it could reach the refusal it was asserting -- a usage error and a
drift, respectively. A fixture that remembers which artefacts exist is a second owner of the publication
list, and the failure mode of a second owner is exactly this: it goes red on the wrong thing. Both now stage
through `tests/test_cli.py::stage_published`, which reads `CERTS` and `MASSIVE_CERTIFICATES`, and the
assertions they carry were not touched.

Disclosed rather than fixed, because it is not this change's to make: with a published certificate absent,
`verify` surfaces a bare `FileNotFoundError` mapped onto the usage exit code, instead of naming the missing
artefact. The two feishu certificates have always behaved that way; the arm inherits it. A named refusal
belongs with the queued work on the gate's error surface, not here.

## 2026-10-09 — `verify` counted three published documents and opened two of them

`docs/AUDIT.md` is a published table of Clopper-Pearson bounds, measured errors and multiples, and the
repository's own claim is that `autorate verify` re-derives every published number. It did not open this
one: `cmd_verify` carried two hand-written byte-comparisons -- `docs/RESULTS.md` and `data/inventory.md`
-- and the audit artefact sat outside the gate while its first line asserted, in print, that
`tests/test_audit.py` was what re-derived it. That sentence was true and beside the point. The suite
re-renders the file to catch a renderer that moved; the gate is the thing a reader is told re-derives the
numbers, and a published document whose re-derivation owner is misnamed states a fact no reader can check.

The fix is a table with one owner, because the defect class is a hand-kept list. `PUBLISHED_DOCS` in
`cli.py` now names every published document together with the function that renders it, `cmd_verify` loops
over that table, and the test that counts the gate counts `len(PUBLISHED_DOCS)` rather than the literal `2`
it used to hold. `docs/AUDIT.md` was regenerated from its producer (`autorate audit`, rc 0), which changed
one line: the file now says `verify` byte-compares it in both lanes.

Both arms were falsified, and the second falsification is the reason both exist. Tampering a bound in a
scratch copy reddens the gate at rc 4 naming `docs/AUDIT.md byte-identical`. Narrowing `PUBLISHED_DOCS`
in memory -- deleting the audit row, leaving the loop untouched -- leaves `verify` printing `95 /95`, rc 0:
a denominator derived from the table it is derived from cannot see a document removed from it. What catches
that is the separate membership pin in `test_cli.py`, which names the three documents independently of the
count. One assertion notices a row that stopped being checked; the other notices a document that stopped
existing.

Measured after, both rc 0: corpus-absent `re-derived 96 /96 values`, corpus-present `re-derived 131 /131`.
The gap between the lanes is still exactly 35 checks -- the 9 upstream `SOURCE.json` digests and the 26
snapshot keys -- because the row the widening added reads only the committed records file, which is the
same corpus-independent reason the pin arm exists. `README.md` now quotes 96 and 131 and lists
`docs/AUDIT.md` among what a 96 run proves; the rows above this one keep the figures they measured.

## 2026-10-09 — a missing published certificate reported a usage error for a file nobody passed

The 2026-10-08 entry above disclosed this rather than fixing it, and the disclosure is still accurate
about what the tool did: with a published certificate absent, `verify` surfaced a bare
`FileNotFoundError` and `cli.main` mapped it onto the usage exit code. Fixed here, because this is a
`cli.py` lane and `cli.py` is fenced one lane at a time.

The attribution was the defect, not the non-zero exit. `2` is the code README gives to an input the
command was handed, and the only inputs `verify` takes are the ones in its own tables --
`report.CERTS`, `report.MASSIVE_CERTIFICATES`, `cli.PUBLISHED_DOCS`. A checkout missing
`data/cert_massive_de_laya.json` is not a mistake the operator made; it is the committed state
contradicting what it publishes, which is the sentence `4` already carries. So the refusal is a
dedicated exception class (`report.PublishedArtefactUnavailable`, a `RuntimeError` and pointedly not an
`OSError`, because the tuple that maps `OSError` onto `2` is what swallowed the honest statement in the
first place), raised by `report.require_published` at the four read paths a published artefact has, and
mapped by its own arm in `main` onto `4`. The message names the path, names the table that declared it,
and says what is not being claimed: no argument selected this path, and no value disagreed -- the
artefact itself is absent.

Three boundaries, each pinned by a test rather than by intention. `read_certificate` was NOT widened: a
certificate path that came from `--cert` or from `compare` is the operator's to fix and still exits `2`
(`test_a_certificate_path_the_operator_supplied_is_still_a_usage_error`, green on arrival, and it goes
red if the refusal is moved into the shared reader). `data/records_feishu.jsonl` is read by `verify`
straight from `report.RECORDS` and stays `2` on the same grounds -- it is `audit --records`' default, so
its missing-file sentence belongs to the audit command, and the row that pins it is
`test_the_default_records_path_is_still_a_usage_error`, also green on arrival. And
`data/inventory.md.json` keeps its usage-error
refusal in `_inventory`: with no corpus and no snapshot there is nothing to verify against, which is a
different statement from a published artefact that is missing from a checkout that publishes it. The
test that had pinned that behaviour is unchanged.

Red first on the feishu certificate: the assertion read `assert 2 == 4` with stderr
`FileNotFoundError: [Errno 2] No such file or directory: 'data/cert_laya.json'`. The other three read
paths were covered after the fix, so each is falsified by a mutation instead: reverting one site to a
bare `Path` reddens exactly its own row (`data/cert_laya.json`, `data/cert_massive_de_laya.json`,
`data/records_massive_sw.jsonl`, `docs/RESULTS.md`), mapping the arm onto `EXIT_USAGE` reddens the test,
deleting the arm at all escapes as `rc 1`, and widening `read_certificate` reddens the boundary test.
Seven arms, each restored byte-identically by sha256.

No published number moved: the gate's denominators are a function of artefacts being present, and on a
complete tree this lane adds no comparison and removes none.

The first review of this change found the same misattribution one step further along, and the guard was
widened rather than the prose caveated. A stat-only check refuses an absent file and then hands off, so
an artefact that is present but unopenable still reached the `OSError` arm and still called the table's
own path a usage error: with a directory standing in for `data/cert_laya.json` the gate exited `2` on
`IsADirectoryError: [Errno 21] Is a directory`, and with the file at mode `000` it exited `2` on
`PermissionError: [Errno 13] Permission denied`. Both were measured before the guard changed, and both
are rows of `test_a_published_artefact_that_cannot_be_opened_is_the_same_drift_not_a_usage_error` now.
`require_published` therefore opens the file it vouches for instead of only stat-ing it -- it reads
nothing through the handle, the caller still owns the parse -- and the class and the printed label are
`PublishedArtefactUnavailable` / `PUBLISHED ARTEFACT UNAVAILABLE` rather than `Absent` / `MISSING`,
because a message that says "the file has gone" is false for a file the OS will not open. The two
refusals are pinned apart by their own message assertions, one on each side: the absent rows require `is
not in this checkout` and the unopenable rows require `cannot be opened`, so collapsing the two branches
into one cannot pass either. The permission row skips itself where the environment can read a mode-000
file (a runner executing as root cannot produce the condition, and a row asserting a refusal the OS will
not raise is a red that proves nothing); on this machine it ran.

The second pass was falsified the same way as the first, four arms, each restored byte-identically by
sha256 and followed by a green control over all four rows: reverting the guard to a bare `exists()`
reddens the unopenable row, collapsing the two refusal branches reddens an absent row, wiring
`require_published` over the `report.RECORDS` read reddens the boundary row, and mapping the arm onto
`EXIT_USAGE` reddens both refusal rows. One of those arms needed a second attempt: the `RECORDS` read
appears twice in `cli.py` -- in `cmd_report` as well as `cmd_verify` -- and an anchor that matched only
the first planted the mutation in a file the row never opens, so it reported a gate that had not turned
red. The anchor now names the line after it.

The re-review of that round caught the new message overreaching in the opposite direction. It closed with
"the artefact is present", which is true of a mode-000 file and false of a directory standing in the
artefact's place -- there the path is occupied by something that is not the artefact. The refusal now
asserts only what the errno supports, and the rows that print it assert that too: `[Errno` must appear,
`is not in this checkout` must not, and neither may the presence claim. That last assertion was watched
red on the sentence it replaces, and the README clause "absent from the checkout, or present and
unopenable" went with it for the same reason -- it is now "because nothing is at its path, or because the
path itself refuses the open". A refusal about a checkout the tool cannot read is itself a published
statement, and gets the same honesty test as the numbers.

The fourth pass found the guard's remaining blind spot by asking the opposite question: not "what if the
path refuses?" but "what if the file is there and wrong?". Measured on a scratch checkout before this
change, a `data/cert_laya.json` holding `{not a certificate` left `verify` printing `JSONDecodeError:
Expecting property name enclosed in double quotes: line 1 column 2 (char 1)` and exiting `2` -- a message
that names no file, about a file no argument named -- and a corrupt `data/records_massive_sw.jsonl` did
the same. `load_published(path, table, load)` therefore wraps the read rather than the open, and it is
wired at all four sites that read a table-declared artefact: the feishu certificate loop and the document
loop in `cmd_verify`, and both reads of `report.massive_certificates()`. A site left unwired is the same
bug wearing a different filename, so the sites are enumerated rather than sampled. The refusal says "was
read here, and does not parse", quotes the parser's own words in parentheses, and claims nothing the
observation does not support -- it does not say the artefact is present, which is round 2's finding, and
it does not say the file could not be opened, which is false for bytes that were opened, read and then
rejected.

The wrap lives at the sites and not inside `read_certificate` or `load_records` for the reason the whole
chain keeps returning to: those functions cannot tell whose path they were handed, and whose path owns the
answer is what the exit code encodes. That placement is pinned, not prose. The row
`test_a_malformed_artefact_on_a_path_the_operator_supplied_is_still_a_usage_error` expects `2` and the
label absent for a malformed `--cert` argument and a malformed `audit --records` default, and of the six
falsification arms it is reddened by exactly one: the arm that moves the wrap into `read_certificate`.
The other five leave it green, so the row discriminates where the guard sits and not merely that a guard
exists.

Re-attributing a ruling already in this file, and saying so rather than editing history: the row written
as `test_a_stored_certificate_that_violates_its_shape_is_a_usage_error` tampered a committed certificate
down to `"envelope": []` and expected `2`. It was correct when the guard covered only access, because an
empty envelope was a `ValueError` from the parser and the parser was outside the guard. Under the content
arm the same tamper is a published artefact that does not parse, so it is `4` -- the tree, not the
operator, is what disagrees with the published numbers -- and the row's name and assertions changed to
say that, keeping its `2` where `2` still belongs by reaching the same broken bytes through `gate --cert`,
a path the operator typed. No assertion was dropped in the re-write: the old row's every claim survives on
one of the two paths, and the two paths are what make the claim precise.

Round 4 re-attributes two claims made above in round 3, in the same way -- by leaving the sentences standing
and recording what was found afterwards, rather than editing the entry into looking wiser than it was.

The first is the site count. "All four sites that read a table-declared artefact" was the enumeration this
entry gave, and it was four short: `report.INVENTORY_JSON` is read at two more places, `cli.py`'s
`expect_snapshot_is_current` and `_inventory`, and neither argument selects those paths. The reviewer found
it by asking the question the paragraph above had asked of the open, but of the *count*: which reads does
the guard not touch? Measured on a scratch checkout before the fix, a committed `data/inventory.md.json`
holding `{not json` left `verify` printing `JSONDecodeError: Expecting property name enclosed in double
quotes: line 1 column 2 (char 1)` and exiting `2` -- the same false attribution, a file no argument named
described as an input the command was handed, and the reason the earlier rounds kept enumerating rather
than sampling: a list is checkable and an impression is not. The count is now six, and it is derived from
the source (`grep -c` of the wrap's call sites) rather than remembered here.

The second is the wording of the refusal. It said the artefact "does not parse", and that over-reached in the
direction of the parser: the corruption this guard catches is not always a parse failure. Measured on the
same tamper round 3 retired to `4` -- a committed certificate with `"envelope": []` -- the bytes parse
perfectly, and what the run prints is the shape refusal, "every certificate needs a non-empty envelope of
assumptions". A document whose bytes are not UTF-8 prints a decode error. The message therefore now says
that what was found "is not the artefact that table publishes", quotes the reader's own words in
parentheses, and states plainly that it does not guess which of the three it was. The parenthetical is the
evidence; the sentence around it is only allowed to claim that a read completed and was rejected. The rows
that pin the message pin the absence too -- `assert "does not parse" not in ...` -- so the retired
over-claim cannot come back as a regression.

The paragraph above also credited the boundary row with pinning "a malformed `audit --records` default" for
the content arm. What existed at that moment was a `verify` run against a malformed default records file; the
README's own residual names `audit`, and the row did not run it. Round 4 adds the `audit` block, which was
green on arrival -- the residue of a claim that had outrun its pin, not a defect that had been hiding. What
is still *not* pinned is `compare`'s malformed-content case: it reaches the same unwrapped `load_records`,
so `compare` is asserted for the access form (an absent certificate is `2`, in
`test_a_certificate_path_the_operator_supplied_is_still_a_usage_error`) and not for the content form, and
the boundary row now says so in its docstring instead of leaving a reader to find out from a green suite.

With the sixth site wired, the README's residual shrinks from two table-declared paths to one:
`data/records_feishu.jsonl`, because `audit --records` takes it as a default an operator can name and
repair. `data/inventory.md.json` splits rather than moving wholesale: a *missing* snapshot alongside no
corpus is still `2`, because "nothing to verify against" is a true statement about an absence and the
`UsageError` that makes it is raised before the wrap, exactly where the brief fences it; a snapshot that is
present and will not load is `4`, like any other published artefact. That split is the third falsification
arm's job -- routing the absence through the content guard reddens the `2` row, and only that row.

The falsification pass found the round's last gap by making a prediction about its own instrument. Arm D6
wraps `audit`'s records read in the guard, and the pass expected that to redden both the content row and
`test_the_default_records_path_is_still_a_usage_error`; the second stayed green, because that row runs
`verify`. So the README's residual names a command whose access behaviour no row policed -- measured, `audit`
with `data/records_feishu.jsonl` unlinked prints `FileNotFoundError: [Errno 2] No such file or directory:
'data/records_feishu.jsonl'` and exits `2`, which is the right attribution but was, until this paragraph,
only a habit. The row now runs `audit` too, and D6 reddens both rows. Nothing published was wrong; the pin
that made it non-negotiable was missing, and it was the instrument's failed expectation that exposed it
rather than a review of the prose.

## 2026-10-11 — the content arm documented a shape rule it did not have, and ten snapshots escaped as rc 1

Round 4's `load_published` docstring listed four content failures the arm answers, the fourth being "a
snapshot whose shape this build does not accept". The loader behind it was `read_json`, which is
`json.loads`: it accepts anything JSON and hands the result to the renderers, and the renderers index. So the
claim was the one item on that list with no mechanism, and the round's re-review found what that costs -- a
committed `data/inventory.md.json` that parses but has the wrong shape leaves `verify` at `1`, the one exit
code this project's contract forbids outright.

Measured twice before the repair, each time mutating ONE property of the committed snapshot at a time and
running the corpus-less lane, with the unmodified file in the same table as a control -- it printed
`re-derived 96 /96 values` and exited `0`. The plant tables live in the task report; the numbers are quoted
here because they are what the contract is made of.

The coarse pass (`f17b-shape-survey.py`) planted ten shapes and all ten exited `1`: the top level as an array
(`TypeError: list indices must be integers or slices, not str`), as a string, and as an empty object
(`KeyError: 'digests'` from `report.build_report`); `digests` as a string, as a list of empty objects
(`KeyError: 'match'`), and as a list of strings; `unique_ids` and `upstream_audit_stdout_tail` removed; and
`corpus_options` as a list of empty objects (`KeyError: 'id'`) or as a string.

The key-by-key pass (`f17c-rowkey-survey.py`) then removed one key at a time from every place this build reads,
and its three counts are what set the boundary: **24 plants exited `1`, 7 exited `4`, and 15 exited `0`** (the
16th zero line is the control). The `1`s are thirteen top-level keys, eight fields of a `corpus_options` row,
one field of a `digests` row, and the mutations that make a row not a mapping. The `4`s -- removed, and answered
as drift instead of crashing -- are `reader_lines_by_mode`, `reader_lines_dropped_not_ok`,
`reader_lines_filtered`, `reader_lines_malformed`, `reader_lines_quarantined_only`, and the two option fields
`n_shards` and `feasible_at_0.25`. The `0`s are the twelve top-level keys nothing here reads
(`audit_interpreter`, `lines_malformed`, `lines_malformed_by_backend`, `lines_outside_mode_counts`,
`lines_quarantined_only`, `lines_refused_not_ok`, `manifest_declared_cases`, `per_ask_gold`,
`probs_not_closing`, `reader_quarantined`, `sum_tolerance`, `upstream_audit_stderr_tail`) plus the three
`digests` fields `path`, `actual` and `expected`, which the corpus-less lane never reaches.

**A sentence in this entry's first draft was wrong and is retracted here.** It said that removing `families`
and `gaps` "did not crash" and put them in the same class as those five `reader_lines_*` counters. Measured, and
contradicted by the coarse pass's own list above, both are indexed with `[...]` and their absence raises
`KeyError` -- which is why they belong to the thirteen required keys. It is corrected rather than left standing,
because a boundary paragraph that disagrees with the counts in its own entry is worse than one that admits the
error, and because the code was right while the prose about it was not.

In the corpus-present lane (`f17d-present-lane-survey.py`) every `digests`-row mutation exits `4`, because
`expect_snapshot_is_current` compares the whole value before anything indexes into it; only a top level that is
not a mapping reached `1` there. So the shape contract is exactly the keys whose absence crashes: thirteen at
the top level, `match` in a digest row, eight in a corpus-option row. Declaring more would refuse a checkout
this build can read; declaring fewer leaves rc 1.

The repair puts that contract in `report.py` as `read_inventory_snapshot`, wired at the two sites that read
the committed snapshot through `load_published`, so a shape refusal is raised where the shape is known and
becomes exit `4` with the named refusal. `_inventory`'s absent-snapshot `UsageError` is untouched: an absence
is a different statement, and that path has a default the operator can supply.

Two findings about the instruments came out of the falsification pass and belong here rather than in a commit
message. First, the row that checks the contract derives both of its directions from the same production
list, so it can only prove the list is self-consistent: the first pass planted `sum_tolerance` into the
required tuple -- demanding a key the build tolerates -- and all three rows stayed green. The row now also
asserts the list against the measured names above, which is what makes an over-reach visible. Second, the
arm that unwires the corpus-present leg left the end-to-end row green, because the corpus-less lane reads the
snapshot through `_inventory` and never reaches `expect_snapshot_is_current` at all -- the ordering fact round
4 recorded in that row's own docstring, restated as a wrong prediction this pass caught.

Corrections to the 2026-10-09 entry, which this file keeps as written above: the recipe it cited to count the
wired sites returns seven lines, not six, because the pattern matches `def load_published` alongside the six
calls -- the correct statement is six call sites, seven matching lines. Its claim that "the rows that pin the
message pin the absence too" is true of three of the four boundary rows; the corpus-present leg row asserts
the content refusal only, and no absence. And it numbers the D4 arm as "the third"; it is the fourth.

One disclosure the round-4 brief left unreconciled: `test_verify_without_a_corpus_or_a_snapshot_is_a_usage_error`
was edited although the brief fenced that file region byte-unchanged. The edit strengthens the row (it adds
assertions about the refusal the round wired), it does not relax one, and the boundary rows that keep the
absent case at `2` are unchanged. The README's `4` clause now names the snapshot shape among the content
failures, and its `2` residual says what it covers for every command rather than for `audit` alone.

Post-repair, the same three plants re-run in the corpus-present lane, because the paragraph above describes
the behaviour before the loader existed and a reader needs the current attribution: a top-level array and an
empty mapping now both exit `4` with the named refusal naming `data/inventory.md.json` and
`report.INVENTORY_JSON` -- the empty mapping used to reach `4` as *drift*, which was the right code for the
wrong reason, since a document with none of the thirteen keys this build indexes is not a value that
disagrees -- while a snapshot that carries all of them with different contents still exits `4` as
`DRIFT: snapshot corpus_options: recomputed …`. The shape arm answers shape and the comparison still answers
values; neither swallowed the other.

## 2026-10-11 -- #62's rubric owner is one mapping, and two of its copies live outside the fence

`task-6-controller-amendments.md` item 9 states that "#62's owner must cover four more names than R-130
listed", and the sentence as written reads as though widening the owner were enough to finish the job. It
is not, and the gap belongs in this file rather than in a commit message.

What landed: `certificate.PUBLISHED_RUBRIC` is now the single declaration of alpha, beta, delta, seed,
method, unit, n_claims, min_cal, min_eval and grid, and every module inside item 7's fence binds those
names by import -- `report.py` no longer declares ALPHA/BETA/SEED, `audit.py` no longer declares
`DEFAULT_DELTA`, `certify_choice.py` no longer declares `MIN_CAL`/`MIN_EVAL`/`DIAGNOSTIC_GRID`, and the
CLI's `--delta` and `--method` no longer carry literals of their own. The binding *form* is what the new
rows check, through the parsed source, because a value comparison between two modules that agree cannot
distinguish an import from a re-typed literal -- and at this rubric alpha, beta and delta are the same
number, so a value guard is green on arrival by construction.

What did not: `certify_score.py:69-70` and `:75` and `certify_threshold.py:65-66` still declare their own
`MIN_CAL`/`MIN_EVAL`/`DIAGNOSTIC_GRID`, and the signature defaults of `certify_score`, `certify_threshold`
and `severity.py` still write `0.05`, beside `tails.ALPHA_DEFAULT`. Those files are not in the fence, so
the correct move was to report rather than widen. Before anything was deleted the duplicates were measured
against each other: the two `DIAGNOSTIC_GRID` expressions agree value-for-value at 29 points and are two
distinct tuple objects, and all three `MIN_CAL`/`MIN_EVAL` pairs are 60/60 -- which is why removing a copy
could not move a number, and also why a copy nobody policed could.
`test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner` pins the
remaining copies against the owner, and it and its negative control
`test_the_out_of_fence_pin_fires_when_a_copy_diverges` call the SAME function,
`_assert_rubric_copies_agree`: the control walks the pin's whole comparison table, diverges one copy at
a time by patching that module attribute in memory -- planting there would edit the fenced files -- and
requires the resulting `AssertionError` to name the module and the name it patched and no other,
asserting as it goes that the patch landed (`getattr` differs before and after) and that it was
reverted. The pin also compares its table against the two modules' parsed declarations, so a copy
cannot leave the table silently, and `METHOD` is disclosed there rather than pinned because each gate's
`METHOD` is its own rule name (`ordinal`, `threshold`) and not the rubric's `method` (`aps`). The
duplication is thereby visible instead of inherited, and the control has been seen to fail: neutering
the shared comparison leaves the pin green and reddens the control. Measured 2026-10-12 by the
controller, on this tree, with both plants: neutering `_assert_rubric_copies_agree` reddens exactly
`test_the_out_of_fence_pin_fires_when_a_copy_diverges` and leaves all three pins green; neutering
`_assert_signature_defaults_agree` reddens exactly the two signature-default controls and again leaves the
pins green; `tests/test_cli.py` was restored byte-identical after each, by a harness that resolves the
mutation sites from the file it patches and refuses to conclude anything from a row it cannot see. The harness that made that measurement was itself wrong on its first run --
it passed `-q` and `-v` together, which cancel to verbosity 0 and print no per-row lines, and its fallback
labelled every row it could not see as passing -- so the green verdict it reported described the reader,
not the code, and the reader was rewritten before anything was concluded from it.

Two copies this entry recorded as unpinned are now pinned, by the same shape and for the same reason:
`certify_score.py:191` and `certify_threshold.py:279` default `alpha`, `beta` and `delta` to `0.05`,
and `test_certify_scores_out_of_fence_signature_defaults_agree_with_the_owner` and
`test_certify_thresholds_out_of_fence_signature_defaults_agree_with_the_owner` compare each live
signature's defaults against `PUBLISHED_RUBRIC`, one row per file so a divergence names which certifier
moved. Each has its own control --
`test_certify_scores_signature_default_pin_fires_when_a_default_diverges` and
`test_certify_thresholds_signature_default_pin_fires_when_a_default_diverges` -- which patches
`__defaults__` in memory (`inspect.signature` reads that tuple, so the patch is the same state a file
edit produces), calls that pin's comparison, and requires the failure to name the parameter it moved.
`seed` is excluded on purpose: the certifiers default to `certificate.SPLIT_SEED_DEFAULT` (0) while the
published seed is 7, and `tests/test_certify_choice.py` already pins the pair apart. Still unpinned:
`severity.py:426-427`, `:526`, `:563`, `:576` and `tails.ALPHA_DEFAULT`; that deferral is owned by task
#72, and naming its owner in this tracked file rather than only in a gitignored ledger is what turns
"recorded not touched" above into a commitment someone else has to discharge.

Amendment, same day, by fix round `task-6a-fix1`. The first paragraph above replaces four lines that
read, verbatim: "`test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner`
now pins the remaining copies against the owner, with
`test_the_out_of_fence_pin_fires_when_a_copy_diverges` as its negative control (patched in memory,
since planting there would edit the fenced files), so the duplication is visible instead of inherited."
The amendment was needed because that sentence claimed more than the row it described delivered.
Measured on this tree before the rewrite: `MIN_CAL = 61` planted at `certify_score.py:69` reddened the
pin (rc 1) and left the control passing at rc 0, because the control asserted facts about its own
monkeypatch and never called the comparisons it claimed to falsify. That plant is this round's own
measurement and is preserved with its work product: the round ended before it filed a report, so its diff
is the record of what it saw, and the rewrites it produced are what the following paragraph measures
directly. The four claims the replaced lines
carried -- that the pin pins the surviving copies against the owner, that its control patches in
memory, that the reason is the fence, and that the aim is duplication made visible rather than
inherited -- are each restated in the first paragraph above, and no number was deleted with them, so
the amendment loses no claim. The sentence at the head of this entry that "a value guard is green on
arrival by construction" is unchanged and still explains why the in-fence rows check binding form; the
four rows added by this round are value guards on files the fence cannot re-bind, which is why they are
green on arrival by design, and the difference between such a pin and a decoration is that a control
now calls it.

Two claims this round also re-measured, both holding. `audit.DEFAULT_GRID` is the audit's risk-coverage
frontier and not the certifier's diagnostic sweep: substituting it for the rubric's grid leaves every name
plausible while changing which curve a certificate publishes, so it is asserted as a separation and as a
behaviour (the refusal's `diagnostic_grid_size`), and the plant that swaps them reddens. And `seed` is 7 in
the published rubric and 0 in `split_cal`/`certify_choice` by design; collapsing the pair re-rolls the
partition -- the two seeds were checked to hand back halves of equal size and different membership on the
committed corpus -- so the library default kept its own name rather than joining the mapping.

Nothing published moved. Both `verify` lanes print the denominators they printed at `c8ec8f8` (`96 /96`
without the corpus, `131 /131` with it), no `data/*.json` was regenerated or touched, and the two audit
sentences that now read the unit from the mapping render byte-identically -- the byte comparison over
`docs/AUDIT.md` is what says so, not the edit.

## 2026-10-12 -- Plan D Task 2: the freeze moves inside the published certificates

`autorate certify --protocol protocol.json` writes `meta.protocol_digest`, and the five published
certificates were re-exported with it in the same commit as the code that stamps them. The reason for the
single commit is the comparison itself: `verify` checks `meta` by whole-dict equality, so a revision where
the stamping code had landed and the artefacts had not -- or the reverse -- is a revision where `verify`
exits 4. There is no such revision on this branch.

**No published number moved, and the re-export was measured for that rather than assumed.** The shipped
command run without `--protocol` reproduced all five committed artefacts byte for byte, so the re-export
could not have moved a figure by construction; the stamped re-export then added exactly one key to each
`meta`, and removing that key in memory returns a document equal to the published one field by field. All
five carry the same digest, `012cbed36442`. And `autorate protocol --out` still emits the committed
`protocol.json` byte for byte after the stamp, which is what shows the freeze digests the corpus and the
pin but not the certificates it stamps -- a document that digested its own artefacts could not be frozen
before them, and the stamp would chase its own output. `SHAPE_VERSION` stays 2 deliberately: the shape
check in `certificate.py` diffs top-level dataclass field names, so a key added inside `meta` is invisible
to it, and the enforcement point for this change is `CERT_COMPARE_FIELDS`, not a schema version.

**The denominators moved, and the movement is added checks rather than moved numbers.** `verify` printed
`96 /96` without the corpus and `131 /131` with it before this change; it prints `108 /108` and `143 /143`
after, in both command shapes (`verify`, `verify --protocol protocol.json`) and both lanes. The twelve new
rows are two published feishu certificates compared over `RUBRIC_FIELDS`, and the two digests in
`CORPUS_DIGESTS`. New output lines: `claim G1` through `claim G5` with the status each criterion carries,
and a `protocol:` line naming the document read, its digest and its frozen date. The gate's own denominator
test counts those rows from `RUBRIC_FIELDS` and `CORPUS_DIGESTS` instead of a literal, so a comparison that
disappears has to shrink the expectation in the open.

**`corpus.records_digest` is the check the freeze exists for.** Every other corpus-less comparison asks
whether a published file reproduces from the inputs lying beside it, so replacing
`data/records_feishu.jsonl` wholesale and regenerating its certificates in the same commit answers all of
them -- the design spec's own D-12 case. Two rows compare against bytes the freeze named in advance, and
they run in both lanes: the records digest and the inventory-snapshot digest, which is the staleness the
corpus-less lane structurally cannot see.

**A rubric mismatch arrives from an artefact, not from a document, and that took a red test to learn.**
`load_protocol` already refuses a `protocol.json` whose rubric disagrees with
`certificate.PUBLISHED_RUBRIC`, so a mutated protocol is a usage error (exit 2) before the gate reads it.
The `RUBRIC MISMATCH:` arm therefore answers the case the loader cannot see: a published certificate
carrying an alpha, a method or a seed the freeze never licensed. Its sentence keeps its own prefix because
the two failures get repaired differently -- a mismatch by re-certifying at the promised rule, a drift by
re-exporting. `alpha` shows why the arm is needed: it is not in `CERT_COMPARE_FIELDS`, so before this
change a certificate certified at a different alpha reached the gate only obliquely, through the summary
sentence that happens to quote it. Editing a published certificate's `meta.seed` now fails twice by design,
once as a mismatch and once as drift on the `meta` dict.

**`compare` states every reason it will not pair two certificates.** The protocol-digest refusal used to
return before the rubric check, so a pair differing in both heard only about the protocol and the existing
`comparable: NO` sentence was silently unreachable. Both are printed now, and the affirmative line is
withheld whenever any refusal fired, so one command cannot issue a refusal and a pass together.

**Falsification, and a defect found in this round's own code.** Two of the new rows were red for reasons
that are this document's business: `load_protocol` hands back a frozen `Protocol` rather than the JSON
mapping, so four subscripted reads in `cmd_verify` raised `TypeError` -- exit code 1, which this project's
contract forbids -- and the digest list, first frozen as file paths at import time, could not see a lane
that re-points `RECORDS`, which turned the D-12 control green when it should have been red. Both are
fixed, and the tests that caught them are the record: the digest arm resolves its path from the module
attribute when the check runs. Several existing rows went red because a scratch checkout that copies
`data/` and `docs/` has no `protocol.json`; the fixtures were completed to read the path from
`cli.PROTOCOL_JSON`, which is the same lesson `stage_published` already carries for the certificate tables.
No assertion was relaxed and no guard widened to accommodate this change.

## 2026-10-12 -- README: the reproduction prose went stale under the gate, and the criteria are now named

`README.md`'s Reproduction section stated `re-derived 96 /96 values` absent and `131 /131` present, and said
"every CI run is a 96 run". Task 2's rubric and digest rows moved those readings to `108 /108` and
`143 /143`, measured in both command shapes and in the `git archive` export; the gap between the lanes is
still exactly 35 checks (9 `SOURCE.json` digests + 26 snapshot keys), which is the sentence the earlier
entries above record. The dated entries that measured 96 and 131 keep their figures: they are records of
runs, and this paragraph is the correction to the current prose.

The README now names G1–G5 and states what this tree can show for each, with every status read from the one
place that owns it -- `protocol.json`, printed verbatim by `autorate verify` -- rather than kept as a second
copy in prose. Three claims in the old text were replaced because measurement contradicted them:

- "Not covered yet, and gated on a corpus large enough to bound them: the ordinal `score` family and its
  one-sided severity certificate, ... group-conditional (Mondrian) ... drift-adaptive ... contamination".
  The corpus is not what is missing there. `severity.py`, `certify_groups`, `correction.py`, `drift.py` and
  `contamination.py` are committed and tested; what is missing is a command surface, a committed artefact and
  a `verify` row for each. Attributing the gap to data size would have excused the project from building the
  surface, so the README now separates "written and tested" from "published as evidence".
- Per-ask `noul` budgets were listed in the same breath as the above. They are different in kind: no
  certifier for `noul` exists at all.
- G1's missing 200-resplit violation rate is now stated with its evidence rather than as a bare absence:
  every certifier in `src/` calls the split once, at the seed it is handed, and nothing sweeps seeds, so the
  criterion's second column has no producer.

**Two false statements found inside the frozen document, recorded rather than edited.** `protocol.json`'s G3
note says "there is no `certify_severity` in `src/`" -- false: `severity.py:426` defines it, and it was
false at the freeze date too. Its G5 note says "`verify` has no `--protocol` at this freeze, so the command
as written cannot be run" -- false as of Task 2, which wired the flag. Both are corrected by re-emitting the
document, and re-emitting changes `protocol_digest`, which is carried inside all five published certificates
under a `meta` the gate compares whole: so the fix is a deliberate re-freeze with its own date, a new digest
and a re-export of five artefacts in one commit -- the same mechanics as above, with numbers measured not to
move. That is not done here, for two reasons: a freeze is a dated act, and silently renegotiating the text a
published digest covers is the misattribution this project keeps removing; and Task 72 is in flight on the
adjacent files, so a second re-freeze would collide with the artefact it is about to publish. Opened as an
explicit follow-up instead, so no reader can take G3's or G5's note as current.

## 2026-10-12 -- #72 items 1 and 2: G3 acquires a command, an artefact and a gate arm; item 3 is still open

**Provenance first.** A dispatched implementer for #72 died with 491 lines uncommitted in the working tree
and four of its own test rows red. The controller adopted that work rather than discarding it, finished the
test file, and re-measured everything it claims. Nothing in this entry rests on the dead round's assertions:
every number below came from a run made today, and each of the four red rows is recorded with the
measurement that showed it was the test, not the product, that was wrong.

**What landed.** `autorate severity <records> --direction {under,over,both_sides_sum}` produces a one-sided
ordinal certificate -- `P(Y > ahat(X)) <= alpha` for the report rule `max(modal, ahat)`, with the mirror for
over-calls, the price of the rule stated beside it rather than inside it, and the joint level derived by
`correction.joint_level` from the three claims it counts. The artefact has a serialisation shape of its own
(`severity.SEVERITY_SHAPE_VERSION`, tagged in `shape`), because reusing the set shape's version number for a
different field set would be a false statement about the bytes; the two shapes refuse each other in both
directions. Three files join the publication: `data/records_ordinal_synthetic.jsonl`, its certificate
`data/cert_severity_ordinal.json`, and `docs/SEVERITY.md`, which `verify` byte-compares through
`cli.PUBLISHED_DOCS`. The stamp rule reaches the new artefact the same way it reaches the five set ones:
`--protocol protocol.json` writes `meta.protocol_digest`, `verify` compares `meta` whole, and a table-declared
artefact that is absent or wrong-shaped is a named refusal at exit 4, not a usage error at 2.

**Denominators, per lane, before and after, from one run.** `verify` re-derived `108 /108` corpus-absent and
`143 /143` corpus-present at `734313c`; it now re-derives `128 /128` and `163 /163`, both at exit 0. The
twenty added comparisons are identical in both lanes and are named by the rows that produce them: fifteen
`cert ordinal.<field>` -- `feasible`, `reason`, `direction`, `alpha`, `delta`, `backend`, `ahat`, `bound`,
`price_bound`, `override_bound`, `measured_violation`, `n_cal`, `n_eval`, `envelope`, `meta` -- one
`cert ordinal.summary`, three rubric rows (`cert ordinal.alpha`, `.delta`, `.seed` -- the ordinal gate has no
`beta` and no `method`, so inventing them would state a rule that never ran), and `docs/SEVERITY.md
byte-identical`. **No published number moved:** the five set certificates and every figure in
`docs/RESULTS.md` are untouched, and the claim lines still print `claim G3 not_measured`.

**Why G3 still reads `not_measured` with a published certificate in the tree.** The criterion is not
"an ordinal certificate exists"; it is "an ordinal guarantee multiclass CP cannot express", and that is the
brief's item 3 -- a control showing the set gate silent or wrong in a named direction on the same data,
writable so that the opposite result is reachable and would delete the README's G3 sentence rather than
reword it. Publishing the guarantee without the control would let a document claim a capability the tree has
only demonstrated half of, so the status stays as the freeze states it and item 3 stays open. This is also the
reason #89's re-freeze has not landed: G3's note in `protocol.json` is still false against the tree, and a
re-freeze written before item 3 reports would freeze the wrong sentence again.

**Four test-side corrections, each with the measurement that forced it.**
1. The exit-code sweep wrote two different populations to one filename, so the second write replaced the
   certified 1200-record population with a 60-record one and the sweep measured `{2, 3}` while asserting
   `{0, 2, 3}` -- the certified arm never ran. The helper now names its file and refuses to overwrite one,
   and the row pins the exit code per arm (`0` certified, `3` too few records, then `2` four times over: the
   non-monotone direction, the unparseable direction, the non-integer seed, the budget the owner refuses, the
   absent records file) instead of a set the collision could satisfy.
2. The denominator row patched `cli.SEVERITY_CERTS` and not `report.SEVERITY_CERTS`, while the arm's loop
   lives in `report`; it measured `(128, 127)` -- a delta of one row where twenty were added. Both owners are
   patched now, exactly as every other helper in this file and in `test_verify_protocol.py` already does.
3. An `ahat` edit was asserted to move `meta`; it does not. Enumerated the artefact's `meta` at the tip:
   twenty-one keys -- the split ids, the counters, the rubric echo (`alpha`, `delta`, `seed`, `direction`), the
   rule, the candidate domain, the unit note and the stamp -- and none of them is `ahat`, so the field the
   tamper moved is not a field `meta` states. Measured set: `cert ordinal.ahat`, `cert ordinal.summary`,
   `docs/SEVERITY.md byte-identical`.
4. A removed stamp was asserted to be one drift line; measured two -- `cert ordinal.meta` and the document,
   which states the digest on its own line. The summary does not move, because it quotes no digest.
Both rows now assert the exact set through one `_drift_labels` helper, so a third unattributable line fails
them; the helper splits on the gate's own separator because a drift line's value can be an entire rendered
document, and counting its inner newlines would report drift that never happened.

**Falsification, and the bound on what it proved.** Three plants, each restored byte-identically (hashes
checked before and after). A plant that stops `severity.summary()` quoting `ahat` dropped
`cert ordinal.summary` and reddened the edit row -- that member is load-bearing. A plant that stops
`docs/SEVERITY.md`'s own `ahat` bullet did *not* redden it, because the figure reaches the prose a second time
through the verbatim summary block: the tamper is caught twice over, and neither site alone is what the row
relies on. A plant that suppresses the document's digest bullet did *not* redden the stamp row, because the
committed document states a line a stampless artefact cannot reproduce, so that arm refuses either way. The
rows' docstrings now say this explicitly: they prove the tamper is attributable by name in both places and
that nothing else moves, not that any single bullet is the only route to the second refusal.

**Adding an arm to the gate moves the fixtures that build a checkout.** Seven rows of `tests/test_cli.py` went
red the moment the ordinal artefact became published, all from one cause: the scratch-checkout helper copied
"every artefact the tables say is published" and did not know about `SEVERITY_CERTS` (a table of triples, of
which the first two are paths and the third is a rule), so every refusal test named the absent ordinal file
instead of the tamper it planted, and one row that expects usage error 2 got drift 4. The fixes are three, and
all three raise the bar rather than lowering it: the staging helper reads the new table, the denominator
formula gains a term derived from `len(SEVERITY_CERTS) * (len(SEVERITY_COMPARE_FIELDS) + 1 +
len(SEVERITY_RUBRIC_FIELDS))`, and the independent literal that names which documents `verify` owns gained
`docs/SEVERITY.md` -- that literal is the tripwire this repository added when a document left the gate
silently, so editing it is the intended cost of adding a document, not a way around it.

**Two small production items in the same commit.** `report.py`'s import of `SEVERITY_N_CLAIMS` was unused --
checked before deleting that no module imports the name *from* `report` (`tests/test_severity.py` takes it
from its owner, `severity.py`), so the import went rather than the claim. And the `--direction` help text read
"arteffact"; corrected after checking that no tracked file quotes the misspelling, so the fix moves no
document.

**The README moved in this same commit, and that belongs on the record.** Its reproduction prose quoted
`108 /108` and `143 /143`, and its G3 bullet stated that "the shipped program cannot yet produce one: there
is no command surface, no committed artefact, and no `verify` row for it". All three of those clauses became
false the moment this commit's own files landed, and no test reads the README, so nothing would have said so:
the denominators are now `128 /128` and `163 /163` (the 35-check gap between the lanes is unchanged, and is
still the 9 `SOURCE.json` digests plus the 26 snapshot keys), "five published certificates" becomes six, and
the byte-compared document list gains `docs/SEVERITY.md`. G3's bullet now says what exists -- a command, an
artefact, a gate row -- and why the status stays `not_measured`: the criterion is the contrast, and the
control that would establish it is item 3, unwritten. It also records the way that control can go against us:
`certify_score` certifies intervals of ordered levels, and an interval's top endpoint bounds
`P(Y > hi(X))` through the set gate's own coverage statement, so the honest reading of the experiment may be
that G3 fails and the claim is deleted. `docs/SEVERITY.md` itself needed no edit, because every figure in it
is read from the artefact it describes.

**Fix round, same day, from the independent review.** A reviewer agent read the brief, the controller's
amendments and the whole diff, and returned changes requested. Four of its findings were real defects in the
shipped program and are fixed here, in the order that matters:

- **Four exit codes escaped as 1.** `SeverityCertificate.from_dict` read four slots before the dataclass could
  check them, so a published artefact with `envelope` removed answered `KeyError`, a `n_cal` holding a JSON
  string answered `TypeError` inside `summary()`'s `%d`, a `backend` holding a list answered
  `TypeError: unhashable type` at the records lookup, and a document that is a top-level JSON array answered
  `AttributeError` on `.get`. `cli.main` maps none of those, so each was rc 1 -- the one number this
  project's contract forbids -- on the door whose whole purpose is to name the artefact at 4. Every claim
  above was reproduced by hand before being fixed, and again through `main(["verify"])` afterwards. The
  loader now refuses a non-object, requires every field `to_dict` writes (the two dataclass defaults were
  what let `envelope` be absent *and* read), and guards the four slots by name. The rc-1 escape was
  invisible to the suite because the adopted shape rows fed the loader only documents with every key present:
  the new parametrised row walks the tampered copies through the shipped command, so it asserts the exit
  code rather than the exception.
- **The `--doc` guard ran after the artefact was written.** Its refusal ends "Nothing was written" and its
  help says the same; measured, a refused run left its `--out` file on disk. The check now happens before
  anything is read, certified or written, so both sentences are true.
- **The `--doc` guard compared two of the three values the table row declares.** `direction` -- the element
  the severity table exists to carry -- was unchecked, so `--direction over` at the published paths exited
  0 and rewrote the published certificate as an over-call certificate under a document whose own bullet
  still named `under`: artefact and prose agreed with each other and disagreed with the publication, which is
  precisely what `verify`'s byte comparison of the document cannot see. All three values are compared now.
- **Two whole production additions had no test that could fail on them.** `certificate.py`'s new clause (the
  one that names the severity fields and says `autorate severity` is their producer) survived being emptied
  to `[]`, and no row passed `--doc` at all, so the guard, its write and its message were dead to the suite.
  The cross-shape row now asserts the clause's own words, and three `--doc` rows exist: the published pair
  reproduced byte for byte in a staged copy, and the two refusals above.

Three of the review's sentences about this tree were stale when they arrived -- the README tense and the
ERRATA append had already been corrected by the time its report landed, and `report.read_severity_certificate`
no longer claims a typed door -- and each was re-measured against the tree rather than accepted or dismissed.
Two claims the review found overstated are corrected in prose, because they were not the code's fault: the
loader's docstring said every refusal is named when four were not (now true, and the docstring enumerates the
slots guarded by hand), and `cmd_severity`'s rc-2 list promised a door no command opens -- this build reads no
severity artefact from an operator-typed path, so the shape refusal has exactly one door, at 4, and the help
text and the two docstrings now say so. One measured finding is recorded rather than "fixed": the meta-echo
branch in `rederive_severity` is provably the identity at this tip (`certify_severity` is called with the same
values it re-states, and `_intake` echoes what it was given), so its comment no longer claims to close R-225's
ordinal side; it stays as a declared belt, and the owner of those three values is named as `_intake`.

Parked with rulings, none of them load-bearing for a published number: the derived document prints the word
`None` for three `meta` keys a refused certificate does not carry (latent -- the published row is feasible, and
the fix is the delete-the-sentence rule, not a hand-tuned value); the decimal-only prose guard is blind to the
integers it claims to police, so a hand-typed `600` in `render_severity` would pass it; the exit-code sweep's
`set(codes) <= {0,2,3,4}` is implied by the per-arm list above it and adds nothing; the ordinal arm's
`rederive_severity` duplicates `rederive_massive` rather than sharing it, which is where the four new guards
had to be written twice; and `protocol.py`'s "the tables are the one owner of what is published" sentence
still enumerates five artefacts now that a sixth exists. Each is opened as its own follow-up, and the
denominators did not move with this fix round: `verify` still reads `128 /128` absent and `163 /163` present,
because the guards close doors the gate never opened.

**#72 item 3, partly measured, and the claim kept inside what the measurement shows.** A first contrast is
committed in `tests/test_g3_contrast.py`. On the published ordinal population, at this freeze's own rubric,
`certify_score` -- the ordinal *set* gate -- refuses with `empty_feasible_set` and publishes nothing
(`qhat`, `autorate`, both error bounds and `mean_set_size` are all absent), while `certify_severity` certifies
the one-sided bound, reports its measured held-out violation rate and states the always-report rule's price.
The set gate refuses on all four population variants the file walks, and every number the rows assert is read
from the certificate objects rather than typed. The row that keeps the other two from being decoration measures
the generator's own liveness: the probabilities change with `temp` (four distinct digests), the reported
rule's statistics do not between `temp` 2.0, 6.0 and 12.0 because the argmax pattern saturates once the ballot
is sharp, and `temp` 0.3 moves the bound, the reported level and the measured rate. Two things follow, and both
are recorded rather than smoothed over. First, an invariance across configurations was a bug signature until it
was measured: the saturation is real, but it means the published population's temperature is not the binding
knob -- `shift` and `error_rate` are -- which is a fact about how that envelope should be read. Second, the
criterion is still not met: for an interval set a coverage claim bounds `P(Y > hi(X))` directly, so "cannot
express" needs a population where the set gate certifies and its published fields still fail to bound the
one-sided risk of the rule it deploys, and no population in this family lets it certify. `claim G3` therefore
stays `not_measured`, the README says so in those terms, and the open question is written down instead of being
answered by the silence of a refusal.

**#87: the 200-resplit column is published, and its undefined rates stay undefined.** The experiment G1's own
criterion names was run at the freeze's rubric -- 200 seeded re-splits of the five scored decision tasks plus
one synthetic control whose answers are known -- and its document is now committed as `data/resplit_200.json`
(422,463 bytes, 1,200 per-split rows) with `docs/RESPLIT.md` rendered from those bytes and added to
`cli.PUBLISHED_DOCS`, so both lanes byte-compare it. The outcome is a refusal pattern, not a certificate: every
published task certifies in **0 of 200** splits, so its `violation_rate` is `null` with a zero denominator, and
the only `0.000` in the table belongs to the synthetic control (200 of 200 splits certify, 0 violations of 200
certificates). No rate is imputed anywhere, which is the vacuity this project has refused twice already: a
column of zeroes over no certificates would read as evidence of safety.

What the gate now checks and what it deliberately does not. `verify` compares 32 quantities the artefact
asserts about itself -- certificates plus refusals against the split count, rows per task against the split
count, violations against the certificate denominator, the recorded rate against the ratio it claims, the bound
order where bounds exist -- and 5 rubric rows comparing the experiment's recorded `alpha`/`beta`/`delta`/
`method`/`seed` with the freeze, so a rate measured at a budget nobody promised is a mismatch rather than a
pass. That takes the corpus-absent gate from `128 /128` to `166 /166` -- the 32 invariant comparisons, 5 rubric
rows and the document row -- and the corpus-present lane from `163 /163` to `201 /201`, measured in
the same run, since none of those comparisons reads the corpus. The gate does NOT
re-run the experiment: six minutes of Monte-Carlo does not belong in a check CI runs on two arms, and a second
implementation of the seeded split would make the gate a competing owner of the producer's randomness. The
producer's determinism is recorded instead: re-running `tools/resplit_experiment.py` at this revision produced
**byte-identical** bytes to the committed artefact (timed at 349 s of CPU, ~6 minutes wall), so the artefact can
be regenerated and checked by anybody who doubts it, with one command.

One test in this batch was wrong before it was right, and the correction is worth keeping: the
missing-artefact row also moved the severity table aside, then asserted that the refusal named the resplit file.
It named the severity copy instead -- the row had manufactured a second absent artefact and blamed the one it
was studying. The row now re-points the resplit path alone, and states why in its docstring.

**One scope sentence this repository wrote, and then measured wrong.** The #87/G3 prose said the ordinal set
gate "certifies nothing in this family" -- a claim drawn from the four populations walked at `shift = 0.1`. A
64-cell search over the generator's live knobs refutes it as a universal: `certify_score` certifies in 4 cells,
all of them `error_rate = 0` with `shift = 0` (temperatures 1.4, 2.0, 4.0, 8.0), where it publishes
`autorate` 0.41-0.47, a conditional bound of 0.0314-0.0359 and a marginal bound of 0.014867, and the severity
gate certifies the same marginal figure at `measured = 0`. That coincidence is not evidence either way -- both
gates are quoting the Clopper-Pearson upper bound for zero errors in 200 cases -- so it neither supports nor
refutes G3; it makes the question answerable. The README and `tests/test_g3_contrast.py` are corrected to say
exactly that, and the one-sided count on a certifying population remains unperformed, which is why
`claim G3` still prints `not_measured`.

**G3's wording met its measurement, and the bare claim did not survive.** The corner of the ordinal generator
where the set gate certifies (`shift = 0`, `error_rate = 0`, one of the 4 cells of R-245) was counted on the
evaluation half the severity artefact itself names: the interval's top endpoint is above the gold level in no
case, so `P(Y > hi(X)) = 0` lies inside the set certificate's published marginal bound of 0.014867. A coverage
statement over ordered intervals therefore *does* yield a one-sided bound, and the README's bare sentence that
multiclass conformal prediction "cannot express" one is false for that construction -- the claim is narrowed in
`README.md` and pinned by `tests/test_g3_contrast.py` instead of being left to drift. What the set certificate
still does not carry is the price of taking that rule: it moves the reported level above the model's own modal
level on a large fraction of non-empty cases, and leaves 36 records with an empty certified set and so with no
top endpoint to report at all, while publishing no `price_bound` or `override_bound` field. The surviving
difference is narrower than the original: a bound one must read off a rule nobody certified, whose abstentions
are uncounted, against a bound certified for a named rule with its override rate and its abstention price
stated beside it.

Two process facts, recorded because they are the reason the above is trustworthy. A patch script in this round
wrote a fragment over `tests/test_g3_contrast.py` and destroyed it; the file was restored from the committed
revision (byte-identical to `HEAD`, suite green afterwards), so nothing uncommitted was lost beyond the row
that had not yet been written. And the first version of the new row asserted `len(eval_ids) == n_eval_cases`,
which the data contradicts -- 600 records against 200 cases, three repeats each -- so the row now states the two
denominators separately rather than flattening the distinction the guarantee depends on.

## 2026-10-13 -- the freeze re-emitted so G3, G5 and G1 say what the tree does (#89)

`protocol.json` is the owner of the five criterion statuses and of the notes that explain them, and three of
those notes had become false against the tree they describe. Editing the notes is a change to a value the
loader reads, so the digest moves, and a moved digest invalidates every artefact stamped with the old one:
this is the re-freeze the previous two sections kept deferring, and it is the reason they were written as
prose pointing at `#89` rather than as the document's own words.

**What was wrong, and what the note now states.**
- **G3** named no artefact and said `certify_severity` does not exist in `src/` -- false since `7a2669e`. It
  now names `data/cert_severity_ordinal.json`, `docs/SEVERITY.md` and `tests/test_g3_contrast.py`, and carries
  the measurement that refuted its own wording: on the corner where the set gate certifies, the interval top is
  above the gold level in 0 of the 600 evaluated records and `P(Y > hi(X)) = 0` sits inside that certificate's
  published marginal bound (re-read from the object at `0.014867039231272057`), so a coverage claim over
  ordered intervals *is* a one-sided bound. The status stays `not_measured` because the criterion is the wider
  sentence, and the note now records the narrowing instead of leaving it in working-tree prose.
- **G5** said `verify` has no `--protocol` at this freeze, so "the command as written cannot be run" -- false
  since the flag landed and has been measured in every `git archive` export since. The note now says the flag
  exists and is measured in a clean export, and keeps the two things that are actually missing: `docs/G5.md`
  as the published transcript, and the fact that "every published number" is wider than today's gate because
  the G4 slice and drift/contamination figures are not published at all.
- **G1** said the 200-resplit measurement "is not part of this freeze either" -- false since `baa902c`. The
  note now names its producer and its two artefacts and states what it shows: 0 of 200 splits certify for all
  five published tasks, so their rates are published as undefined over a zero denominator rather than imputed.

**No published number moved, and the check that says so was itself tested.** Byte-comparing a re-export against
a committed artefact stopped being the right control when the artefacts began carrying `meta.protocol_digest`:
a plain re-export writes no digest, so all six files differ by exactly that one key and the control reads
`DIFFERS` while every number is untouched. The replacement walks both documents key by key and names every
differing path except that single slot; it reports `NO NUMBER MOVED` for all six (five set certificates plus
the ordinal severity one). It was falsified before it was cited: adding a field the artefact does not have is
named as `bogus_new_field`, and moving one stored scalar by `5e-4` is named as `alpha` -- so the empty result
above is a measurement, not a silence.

**The freeze is a fixed point.** After re-exporting the six stamped artefacts, `autorate protocol --out
protocol.json` -- which reuses the date already in the file and reads the certificates back for G1's counts
and the envelope lines -- reproduces the same bytes and the same digest (`4d06ffa482eb…`, previously
`012cbed36442…`). The first emission of this round was superseded inside the same working tree
(`dddd18faf0a3…`), because the G3 note was still being corrected after it: a freeze's digest is a function of
its own prose, which is exactly the coupling amendment §1 chose, and it is why the notes get finalised before
the file is emitted rather than after. That matters because the document quotes values derived from the
artefacts while the artefacts quote the document's digest: a second emission that differed would mean no
digest could ever match both, and `verify --protocol` would be unpassable rather than merely red. `frozen_at`
moves to 2026-10-13 by
ruling (amendment §1: the date is inside the digest and is operator provenance, never computed), so the
`2026-10-11` citations elsewhere in this file and in `protocol.py`'s comments stay as they are -- they name a
dated section, not the current freeze.

**One correction that is not a claim change.** `protocol.published_certificates()` documented `report.CERTS`
and `report.MASSIVE_CERTIFICATES` as "the one owner of what is published". Since `SEVERITY_CERTS` and
`RESPLIT_JSON` joined the publication tables that sentence is false, and a reader who trusted it would count
the severity certificate as a decision task G1 never made. The docstring now names its own scope: it returns
the *set* certificates G1's criterion is stated over, and the ordinal severity artefact and the resplit record
are published by their own owners and enter the gate through their own arms. No behaviour changed. Related and
now stated in the README: `data/resplit_200.json` carries no digest -- measured, `protocol_digest` appears
nowhere in it -- because `verify` compares the rubric block it recorded against the freeze (`expect_rubric`,
five fields) instead of looking for a stamp. So "every published certificate is stamped" is true of six and
must not be read as "every published artefact is stamped".

**Process.** `autorate verify` re-derives 166 /166 corpus-less and 201 /201 corpus-present with the new
digest in place, and `verify --protocol protocol.json` agrees in both lanes. The first control run of this
round used the byte comparison above and printed `rc=3 DIFFERS` five times; the honest reading of that run is
that the control was wrong, not that the re-export moved a number -- the failure was recorded before the
replacement existed, which is why the replacement ships with its own falsification.

## 2026-10-13 -- G4's worst-slice refusal becomes a published run, and a blocker note of mine was wrong

**The premise I had recorded was false, and it had been filed as a dependency on somebody else.** Task #86
carried the note "the `language` key is absent from every committed records file, so `certify --groups
language` must refuse at 2 by design; publishing a slice artefact needs a language-stamped combined file from
a named producer". That was measured against a **top-level** `language` field. The committed MASSIVE rows
declare their slices in `slices`: line 1 of `data/records_massive_de.jsonl` carries
`"slices": {"language": "de", "mode": "choice", "option_count": 20, "regime": "clamped"}`, and `groups.py`
conditions on exactly that mapping -- an undeclared key raises `UndeclaredGroupKey`, which is why the refusal I
had predicted never happens. Nothing outside this repository was needed: the run is a function of three files
that are already committed, and it costs six seconds.

The correction matters beyond the task list. A blocker sentence that reads as an external dependency ("needs a
named producer for a combined file") is a reason to stop working, and I had stopped. The defect was not the
data and not the gate; it was that I queried the wrong shape and wrote the negative result down as a fact
about the corpus rather than about my own probe.

**What is published now.** `tools/language_slices.py` certifies the three committed record files -- 8,922
cases, one per row -- as slices of `slices.language` at this freeze's rubric, and writes
`data/slices_language.json` beside `docs/SLICES.md`. The run refuses, which is the whole claim G4 makes: 3
slices, 0 certified, `any_slice_refused` true, worst slice `de`, each slice refused at the corrected budget
(alpha and delta 0.05 / 3 = 0.016667, joint level 0.85), and `refused_by_size` empty -- a bound failure, not the
size floor. The pooled marginal certificate over the same records is written into the same artefact beside the
slices and refuses too, so the pooled number cannot be read as an average of the slices. `verify` recomputes
the run from those three files rather than auditing its arithmetic: 70 field comparisons (13 top-level, 8 per
slice, 6 per census row, 8 pooled, the envelope as one value, and rows-plus-digest per input file) and 5
rubric rows, so a stale slice artefact is drift with a field name on it. The denominators move by 76 in each
lane -- 166 to 242 corpus-less, 201 to 277 corpus-present -- and the inter-lane gap stays 35, because the run
depends only on committed bytes.

**Two refusals the producer owes and the rows prove.** A declared input that is missing stops the run before
anything certifies: certifying 2 of 3 languages and publishing it as a language-slice run would describe a
population differently than it is. And a row whose `case_id` names one language while its own `slices` says
another is two subjects in one row -- which slice it lands in would depend on which field the tool believed --
so `check_rows` re-derives the language from the row's bytes, never from the filename it happens to sit in.
`tools/split_records.py` already proves that claim for the split direction; this is the merge direction
inheriting it. Duplicate ids across files are refused for the same reason a per-slice denominator built from
them would claim more independent cases than the corpus holds.

**G4's status moves to `not_met`, and why not further.** The criterion's behaviour is demonstrated on the
slices this repository scored, so `not_measured` would now assert less than the tree does -- the same mistake
R-170 obliges a commit to fix in the same revision that makes it true. `certified` would assert more: the
row's own measurement text names a (language x option-count) cross, and every committed MASSIVE row has
`option_count` 20, so a two-key run is the same three slices and there is no cross evidence to publish; it
names the literal word `NOT_CERTIFIABLE`, while the run emits `empty_feasible_set` reported as NOT CERTIFIED;
and it names Khmer by example, whose figures this project measured but has not published per-case rows for.
`not_met` is R-197's word for measured-and-short, and the three gaps are listed in the frozen note rather than
smoothed over.

**A third re-freeze, because the same rule cuts both ways.** Changing that note changes a value the loader
reads, so the digest moves again: `4d06ffa482eb` to `ff9f16fd2b67`, with `frozen_at` unchanged at 2026-10-13.
The six stamped artefacts and `docs/SEVERITY.md` are re-exported in this same commit, the field control reports
no number moved for all six, and re-emitting the freeze under the stamped tree reproduces the same bytes. Two
freezes in one day is churn, and it is the churn a claim change costs by design: the alternative -- editing a
published note under a digest that no longer describes it -- is the R-234 defect this file has now recorded
three times.

## 2026-10-13 -- review of #86 found two blockers and three false claims; what this file got wrong is here

The independent review of `03f1198` measured, and was right: `verify` died with `TypeError` at exit 1 on a
published artefact carrying a non-empty `refused_by_size` (that list holds rows, and `render_slices` joined it
as names), and six further tampers on the same artefact -- `groups`, `envelope`, `per_group`, `slice_census`,
`inputs`, a row missing a key -- also reached exit 1, while `docs/SLICES.md` promised exit 4. Both are fixed:
`read_slices` now refuses the nested *shapes* it reads further down, not only their presence, and
`slice_inputs` answers a table-declared file with no published backend through `PublishedArtefactUnavailable`
rather than the usage exit. The gate re-derives 283 /283 corpus-present after the change (was 277): the
comparison list gained `worst_claim`'s five fields and `refused_by_size`, because the arm had been
re-deriving everything about the run **except the two fields G4 is a claim about**.

**Three sentences in this file and the frozen document were false, and none of them were the reviewer's
invention to fix.** (a) The G4 note and the README both said the run's refusal word is NOT CERTIFIED and "not
the literal `NOT_CERTIFIABLE`". Measured: each refused slice's `summary()` prints
`NOT_CERTIFIABLE: reason=empty_feasible_set`, and `certify --groups language` over these records exits 3 =
`EXIT_NOT_CERTIFIABLE`. The gap that remains is the (language x option-count) cross and the absent Khmer
slice -- two, not three. (b) Both texts said Khmer's figures were "measured" by this project;
`docs/VERIFICATION.md` records them as a quote of the upstream README's own line, and `docs/SLICES.md` said so
in its own words. (c) This file claimed the producer's two refusals were "proved by the rows": the row called
`refuse_missing_inputs` with an argument `main()` never passes, so deleting the real guard left all eleven rows
green, and the duplicate-id refusal had no row at all. (a) and (b) are corrected above, in current prose and in
the frozen note. (c) is recorded as unfinished: the rows written to close it were reverted rather than shipped
half-right, so `tools/language_slices.py`'s refusals are still unasserted through its own command, and the
producer's malformed-line and backend-absent paths still answer rc 1. The two blockers and the rc-1 path in
`verify` are fixed; the test-surface debt is open and named here instead of being claimed as done.

**Also corrected in code, not prose:** `inputs[].rows` had two owners (all JSON lines in the producer, the
backend's Records in the gate) that agreed only because every committed row is `laya`; the producer now calls
`report.slice_inputs`, so the artefact's own input table is the same value the gate re-derives.

The record itself, as `docs/G5.md` transcribes it: commit `56b3f76`, protocol digest `8bcc0336dee0c5a7bacb5f83a7b5679e62b39eb6cac37b8e2dad55179feb6bfd`, absent lane
`rc=0` at `248/248` values, corpus-present lane `rc=0` at
`283/283` values -- the `35`-check gap is the nine upstream `SOURCE.json` digests and the
snapshot keys a corpus-less run can only transcribe -- and four falsifications returning
`rc=2`, `rc=4`, `rc=4`, `rc=4`.

## 2026-10-13 -- G5's transcript is a published file, and the two things that made it possible


G5 asks for a literal command's result: `autorate verify --protocol protocol.json` re-deriving every
published number from a commit, with no GPU, no network and no model, exit code and counts printed. The
mechanism had existed since Plan D Task 2 and the corpus-less reproduction had been run on every pre-push
simulation, but a simulation I perform and delete is not evidence: nothing recorded what the export printed,
so the README could only point at the absence. `tools/g5_export.sh` is the recorder, `tools/g5_transcript.py`
the renderer, `docs/G5.md` the record, and `tests/test_g5_transcript.py` the guard that keeps the record from
drifting away from the tree that cites it.

Two facts worth recording because each one changed the design rather than merely the text.

**A transcript must be checked against the revision it names, not against the reader's tree.** The first
version of the digest row compared the recorded digest with the `protocol.json` in the working tree. That is
unsatisfiable in the order the work has to happen: the export can only run against a commit that already
exists, so any commit that re-freezes -- which is every commit that corrects a claim note, and there were four
today -- reddens the transcript in the very commit that publishes it. The row now asserts the printed digest
equals the digest of the `protocol.json` at the named commit (immutable: lying about it means editing a commit
that no longer matches), plus reachability from HEAD (a transcript cannot be smuggled in from an abandoned
branch). Currency is a sentence in the document, where a reader sees which commit it describes; the
`--ignore`-style alternative of recomputing at render time was rejected because it makes the guard unable to
fail.

**macOS has two spellings of the same scratch directory, and masking one is not masking.** `mktemp -d` yields
`/var/folders/<a>/<b>/T/g5-XXXXXX`; the interpreter inside it reports `sys.prefix` resolved through
`/private/var/folders/...`. The first transcript therefore carried the machine in a line the emitter exists to
police, and `tools/g5_transcript.py` refused the document at exit 2 and wrote nothing -- which is the design
working, not failing: there is no path by which it redacts and publishes. The runner now masks both spellings,
and `tests/test_cli.py`'s tracked-tree guard gained the `/var/folders` class it had never covered (with
`/tmp` deliberately excluded: measured, including it named a plan document's `/tmp/falsify/` and CI's own
`tee /tmp/pytest.log`, which are honest prose rather than machine-identifying paths).

What the transcript does not license, written in its own last section: the no-network claim covers the gate
steps, not the `uv sync` that provisions them; the corpus-present lane is a local obligation, because the
archive is not a committed file; and CI's first witness of the `--protocol` form begins with the push that
follows this, not before it.

## 2026-10-14 -- the field spec §10 names, and a CI that could not see the commit a record names

Two corrections that share a shape: a claim was true of an artefact the reader cannot check, and a gate was
true of an object database it did not have.

**§10's `n_min_violations` is now the field's name.** The Mondrian result carried the thin-slice refusals as
`refused_by_size` (rows of `group`, `n`, `floor`, `reason`), a superset of the spec's string example, with the
rename deferred by ruling so that the name and the shape would change together. They change here: the key is
the spec's, presence is validated at serialization (an empty list is the fact that no slice was refused by
size; a missing key is refused), and there is no compatibility alias reading either name -- a stale artefact
must fail rather than be tolerated. Measured on a planted stale-key artefact, `verify` exits 4 with the named
refusal and the export's restore was verified byte-identical, so the shape change is a refusal and not a
traceback. The published slice artefact and its document were regenerated by `tools/language_slices.py` in
this commit; the two denominators `verify` prints are unchanged, because the rename moves labels and not
comparisons. Dated entries above that quote `refused_by_size` are left as written: they record what was true
at their date, and the append-only rule for dated records outranks the tidy prose.

**The reproduction transcript's rows needed history the runner did not have.** CI failed on the tip while the
same tree passed locally and inside the pre-push `git archive` export, for a reason that only exists on the
platform: `actions/checkout` defaults to a shallow clone, so the runner's object database held one commit and
`git show <named>:protocol.json` answered "Not a valid object name" for the revision `docs/G5.md` describes.
Reproduced with a `file://` clone at depth 1 (one object, the identical fatal) and unshallowed (208 objects,
the object present). The fix is `fetch-depth: 0`, not a skip: a row that abstains when the history is missing
would leave the G5 note citing a platform witness that was never produced. A guard row now reads the workflow
and names any checkout step that regresses to a shallow fetch, so the next such edit fails where the cause is.
## 2026-10-14 -- Plan D Task 4: `docs/REPORT.md` joins the gate, and the denominators move by one

`autorate report --full` writes `docs/REPORT.md` from `src/autorate/techreport.py`, the document joins
`cli.PUBLISHED_DOCS`, and `verify` byte-compares it in both lanes. The two lines the gate printed, measured
on this tree:

```
re-derived 249 /249 values          # corpus absent, rc 0
re-derived 284 /284 values          # corpus present, rc 0
```

They were `248 /248` and `283 /283`. One document row each, which is the whole of the movement: the arm is
a byte comparison and not a field list, so `tests/test_cli.py`'s denominator formula absorbed it through
`len(PUBLISHED_DOCS)` without a term being added, and the inter-lane gap stays 35. `README.md` now carries
these numbers, including the `242` it had kept as a stale second mention of the absent lane -- one figure,
three spellings, and only `249` is what the command prints.

**Five defects the parked renderer carried, and the row that caught each.** The task's implementer died
mid-work with the module written and the document never emitted, so nothing had yet run the renderer
against a byte comparison.

1. The ordinal bullet printed the `Record` objects `report.published_severity()` hands back instead of the
   records *path* -- one line of 322,756 characters, 322 kB of a 42 kB document. The figure-coverage row
   could not see it: its assertion read `records_path in text` and, once the object is not a `Path`, the
   quickest repair was `str(records_path) in text`, which the buggy line satisfies by construction. The
   assertion now names `report.SEVERITY_CERTS[label][0]`, the path the table declares, and it was red
   before the renderer was changed.
2. The pinned-build sentence reached the page as `Read from \`%s\`` -- a two-element list where the author
   meant one string with a `%` substitution, so the template printed verbatim and the sentence lost the file
   it was pointing at.
3. The split-quantile bullets printed `published \`qhat\`=None` for both feishu artefacts. A refused
   certificate holds no set size; the clause is now written only when the artefact carries one, which is the
   rule the rest of the tree already obeys (the inventory table prints `not opened` for the same reason).
4. Fixing (2) by substituting `inventory.MASSIVE_PIN_PATH` put an absolute machine path into the document --
   that constant is resolved from the package location so the loader works from any directory. The
   machine-path guard row caught it on the rendered text, and the sentence prints `MASSIVE_PIN_LABEL`, the
   repository-relative name, as the published basis sentences already do.
5. `read_ledger` opened `docs/VERIFICATION.md` with a bare `Path.read_text`, so an absent ledger escaped as
   `FileNotFoundError`, which `cli.main` maps to exit 2 -- the operator blamed for a path the module
   declared. It now goes through `load_published` and refuses at 4 naming `techreport.LEDGER_MD`, pinned at
   module level and in the gate's own missing-artefact case list.

**One assertion that was never running.** The coverage row's last loop tested `row["id"] in
techreport.RELATED_WORK`, and that table is a tuple of `(group title, rows)` pairs, so a bare id was
compared against tuples, was never a member, and every quoted row's `opened` date went unchecked while the
row printed green. It reads `techreport.cited_ids()` now.

**A fixture that refused on the wrong file.** `tests/test_cli.py`'s missing- and unreadable-artefact case
lists staged the artefacts the documents are rendered *from* but not the documents themselves, so a scratch
tree lacked `data/inventory.md` as well as the planted defect and the gate refused on whichever table entry
came first. Right exit code, wrong witness, and it stayed invisible while the only document case was the
table's first row. `stage_documents` now copies what `cli.PUBLISHED_DOCS` declares, read from the table, and
the two new tail-of-table cases (`docs/REPORT.md`, `docs/VERIFICATION.md`) name the file they plant.

## 2026-10-14 -- the spec's own API block, who owns an exit code, and the README's two denominators

Three corrections that share one shape: a claim that was checked by a person instead of by a command.

**Spec section 10 now says what the objects are.** Rulings D-c and D-e were recorded in the ledger and never
written into the document, so it still printed `cert.risk_bound` -- a field no shape carries, since
`certificate.Certificate` owns `conditional_error_bound` and `marginal_error_bound` and the name was retired
by R-20/R-31 -- and one `certify` entry that does not exist. Re-reading the dataclasses for the amendment
surfaced a third divergence neither ruling covered: `n_min_violations` belongs to
`certify_choice.GroupsCertificate` while the bounds belong to `Certificate`, and the old block printed them
side by side as though a single object had all of them. `tests/test_verification_table.py` now polices every
`object.field` attribution in that block against the shipped dataclasses. Two things about the guard are
load-bearing: it strips comments before attributing, because the amendment's own header line names
`cert.risk_bound` in order to say it was retired, and a guard that scanned it would fail the sentence that
fixes the defect it polices; and it carries its own negative control, which plants the retired name into a
code line and re-attributes `grouped.n_min_violations` to `cert`, requiring the predicate to name exactly
those two. Both plants were run, not asserted.

**The slice producer's exit codes are keyed to who named the path** (ledger R-272). `tools/language_slices.py`
answered 2 for six refusal shapes, four of which complain about bytes at paths in `report.SLICE_RECORDS`
that no operator flag can name or repair. Those four now answer 4, the code that already means "the checkout
cannot reproduce what it publishes"; the two refusals about an argument the operator typed (an existing
`--out` without `--force`, and a `--doc` at undeclared paths) stay at 2. `SliceInputRefusal` moved from
`ValueError` to `RuntimeError` for the reason `PublishedArtefactUnavailable` documents -- a `ValueError` base
would fall into the usage mapping -- and that move is what lets the file name `records.MissingRecordField` and
`groups.UndeclaredGroupKey` in its handler without a widened `except ValueError` that could swallow a refusal
raised on purpose (the failure B1 Task 1 recorded). One measured shape had no class to name: a committed case
that states no value for a key the other rows do declare reaches `groups.py:163` and raises a bare
`ValueError`, so it is converted at the producer's own call site and keeps the certifier's words; giving it a
class is a fix for every caller of `by_group` and is filed, not quietly done here.

Two disclosures that belong with this change rather than beside it. `tests/test_slice_surface.py`'s
existing assertion that `refuse_missing_inputs` returns 2 moved to 4: the number changed because the policy
did, and its message assertions are untouched, which is the test that the ruling moved an attribution rather
than a claim about behaviour. And `groups.py`'s module docstring still says an `UndeclaredGroupKey` is "a
`ValueError`, so the CLI exits 2" -- true of `autorate.cli`, which reads an operator-supplied corpus, and no
longer a general truth about the class, since the same class exits 4 from a tool whose inputs the publication
table declared.

**`README.md`'s denominators are now policed, both of them.** The absent-lane count has been quoted stale
twice in one document -- a `242` survived in a sentence about what the run *cannot* prove after every other
mention had moved -- and both lanes changed again when `docs/REPORT.md` joined the byte-compared documents, so
the gate now prints `249 /249` without the corpus and `284 /284` with it. Neither figure is a field any
artefact owns, so nothing re-derived them until now: `tests/test_verify_protocol.py` runs the absent lane,
derives the present lane from the committed snapshot (`9` `SOURCE.json` digests plus the `26` snapshot keys a
corpus-less run cannot recompute), checks that derivation against a real second run whenever this machine can
see the corpus -- which it did, printing "measured directly" -- and refuses any lane-shaped number that names
neither lane. Proven able to fail by planting `242` back into the document: the row went red naming both real
denominators, and the file was restored byte-identically, with the restore checked. `docs/G5.md`'s `248/248`
and `283/283` are deliberately outside the guard's reach: they are a record of the commit that transcript
names, and the spaced `N /N values` form that quotes a command is what the row reads, while the archive's
`N/N` is a citation of a measurement at another revision.

## 2026-10-14 -- the field name `confidence` is carried by two of upstream's harnesses, on two scales

`docs/AUDIT.md` already disclosed that `laya/common.py` defines the name twice -- `:273` as
`answer_confidence(p, k) = max(p)`, `:289` as `confidence_from_probs(p, k) = 1 - H(p)/log k` -- and that the
runtime's response key is filled by the second. What had not been published is that upstream's *evaluation
harness* disagrees with its own runtime about the same key: `research/eval/laya_eval.py:265` writes each case
record's `confidence` as `round(float(probs.max()), 6)`, which is the first definition, while the archived
corpus this repository audits carries the second under that name. Measured, not inferred:
`scales.scale_attribution` reports `laya/choice` as `entropy_only` over 192 of 192 rows, worst row distance
to the entropy scale `0.000223` -- so the archive's values are not on the answer scale at all.

The consequence is the reason this project exists: a file's field name does not say which quantity it holds,
only the program that wrote the file does, and a threshold lifted from one harness's documentation and applied
to another harness's output is comparing two different numbers. The published artefact now states both surfaces
with their file and line, and the `attributed scale` column beside each backend is the measurement that tells
a reader which quantity they are actually holding.

Landed as a derived sentence, not as prose typed into a document: the constant is `audit.UPSTREAM_EVAL_HARNESS`,
`render_audit` emits it, `docs/AUDIT.md` was regenerated by `autorate audit` in the same commit, and
`tests/test_audit.py::test_the_audit_names_the_second_harness_that_carries_the_name` requires both the rendered
text and the committed document to carry the citation, the expression `probs.max()`, and the words "two
harnesses". It was written red first -- its first run failed on the citation assertion, which is where pytest
stops -- and `verify` still prints
`249 /249` without the corpus and `284 /284` with it, both rc 0 -- the audit's prose is a byte-compared document,
so a sentence that drifted from the renderer would have refused rather than shipped.

## 2026-10-14 -- a noul `confidence` is the answer scale, not P(yes): what the reader's comment claimed

`src/autorate/readers/feishu_zh.py` carried the comment "upstream sets confidence to P(yes): a confident
'no' and a low-confidence answer arrive as the same number", and the flag beside it,
`noul_confounded_with_yes`, was presented as the thing that comment describes. Measured against the
committed archive through the reader itself, over all 768 laya `four_noul` asks:

- **768 of 768** satisfy `reported_confidence == max(P(true), P(false))` -- the answer scale over both
  slots;
- **759** additionally satisfy `reported_confidence == P(true)`, because for those the affirmative *is* the
  larger slot;
- **9** do not: there the published number is `P(false)`, and the flag is False.

So upstream's field is `max(p, 1-p)`, and the flag marks the coincidence that `P(true) >= 0.5`. The comment
was wrong in a way that is hard to notice from data, because the wrong reading and the right reading differ on
9 rows out of 768 -- and those 9 are the only evidence either way, which is why they are now asserted rather
than commented. The flag's *computation* was never wrong; what was wrong is that a reader could take its name
and its comment for a semantic property of the ask ("confounded with yes") when it is a statement about which
slot happened to be larger. `tests/test_reader_feishu.py::test_a_noul_confidence_is_the_answer_scale_and_the_flag_only_marks_that_coincidence`
builds both cases with a published confidence of 0.6213 -- once at `P(true) = 0.6213`, once at
`P(true) = 0.3787` -- so the two hypotheses get different answers and the row can tell them apart. It was
proved able to fail by planting `confidence == max(p_true, 1 - p_true)` into the reader: the row reddened on
the second fixture, and the reader was restored byte-identically with the restore checked.

Two things deliberately not done. The flag's **name is kept**: it is written into the committed corpus (1,536
occurrences in `data/records_feishu.jsonl`), whose digest `protocol.json` pins as `corpus.records_digest`, so
renaming it would move a frozen value and re-stamp every artefact built on that corpus -- that is a freeze
round's decision with an errata entry of its own, not a comment fix. And the same false claim appears in the
Plan A plan document at `docs/superpowers/plans/2026-09-29-autorate-plan-a-foundation-and-choice-certification.md:1001`
and `:1080`; plan text is dated, so it is left as written and named here instead of being quietly rewritten.

## 2026-10-15 -- the seventh freeze: two digits in the frozen notes, a deictic phrase, and a run id the re-export made false

Three sentences that had stopped being true, each corrected against a measurement taken on this tree rather
than against a remembered number.

**G4's note claimed its own arm smaller than it is.** The note said the worst-slice run is re-derived by
"70 field comparisons plus 5 rubric rows". Driving `report.rederive_slices` with counting callbacks, at the
rubric this freeze owns, answers **76 and 5**: `report.SLICE_N_MIN_KEY` joined the compared fields at
`2ac5e7b` and the sentence was not re-derived with it. `docs/REPORT.md` quotes claim notes verbatim, so the
false digit was published in the technical report as well. This is the same defect the sixth freeze corrected
for G3's "20 comparisons", arriving the same way -- a comparison added to an arm after the note was written.
The existing row did not see it because it searched for `(\d+) comparisons`, which matches the G3 spelling
and cannot match "76 field comparisons plus": one spelling policed, two in use.

**G5's note carried a phrase whose referent depends on which file the reader is holding.** It closed with
"the transcript describes commit 56b3f76, the commit it was unpacked from, which is this document's parent".
Inside `protocol.json` that meant the parent of the commit publishing the freeze; `docs/REPORT.md` quotes the
note verbatim, so a reader there resolves "this document" to the report, whose parent is a different commit.
It was also decaying: 56b3f76 was the parent of `b0dfe8b`, the commit that published `docs/G5.md`, and by this
round it sat fourteen commits below the tip. The note now names commits instead of relating them, and names
the workflow and its two jobs instead of predicting a CI run.

**The reproduction record was re-exported, and doing so found a fourth defect.** `docs/G5.md` described commit
56b3f76; the criterion is about reproducing this project from a commit, so the record was regenerated from
commit `9e6363a` by `tools/g5_export.sh` -- both lanes rc=0 at **249/249** absent and **284/284** present, four
plants back inside 0/2/3/4 and restored byte-identically. The emitter had CI run `38400305544` written into
its prose, so the fresh transcript printed "CI's own witness of this command at the commit named above is run
38400305544" about a commit that run never saw: a true sentence at the revision it was written for, made false
by the first re-export. `tools/g5_transcript.py` no longer names a run at all -- it names `.github/workflows/
ci.yml` and its jobs, and leaves run-level evidence to `tests/test_ci_workflow.py`, which is where it was read
from.

**README's limits section was two publications behind the tree.** It listed the group-conditional (Mondrian)
surface among the libraries with "no committed artefact that `verify` re-derives", after
`data/slices_language.json` and `docs/SLICES.md` landed and became that arm; and it said the G3 contrast
control "has not been run", in the same file whose G3 bullet documents `tests/test_g3_contrast.py` eighty
lines above it. Both now read what the tree does: the Mondrian surface left the unpublished list, and G3's status is
explained by the criterion's wording having lost rather than by a missing control.

Three rows in `tests/test_verify_protocol.py` carry the corrections: the slices arm's own count against the
note's digit; the set of notes that state an arm's size against the rows that police them; and a
transcription-fidelity row that reads the recorded denominators out of `docs/G5.md`'s own rc=0 blocks and
requires both the note and README to match them, refuses the deictic construction, and refuses a run id in the
record. The first and third were red on the real defect before the fix (`70 != 76`; the note's `248/248`
against a record printing `249 /249`). All three were then proved able to fail again by planting, in one run:
the digit removed from the note reddened the first two rows for the reasons each names, a fabricated run id
reddened the third, and both files came back byte-identically with `cmp` checked. The parser leg earns its own
note: a first version keyed on the command line alone read a planted `rc=4  re-derived 248 /249` block as the
clean absent lane, which is why only an `rc=0` count is a lane.

One honest disclosure about the prose guard. The rewritten note first kept the bad phrase as an *example* of
what it was avoiding. Both the freeze script's precondition grep and the new row rejected it, and that is the
right outcome: a text guard cannot tell a mention from a use, so the note states the rule without quoting the
construction, and the guard stays strict rather than learning to parse disclaimers.

Deliberately not in this freeze. Tasks #68 (the Khmer slice corpus) and #97 (G1's feasibility arm) both change
the publication tables and so move both denominators. Folding an unreviewed corpus publication into a
corrective re-freeze would have made one commit carry a documentation fix and new evidence at once, and the
fixed-point proof would have been measured against two moving targets; each gets its own round. The seventh
digest is `efea041b6dee8693ea302efa8d564a534ea786d7267ec1593f655c460973434a`, carried by the six stamped
artefacts and printed by `docs/REPORT.md` and `docs/SEVERITY.md`.

The first emission of this freeze went red, and the guard that caught it was right. Naming CI's two jobs in
the G5 note put the token `cross-libc-verify` into `docs/REPORT.md`, and `tests/test_techreport.py`'s
stray-citation scan treats any token with two hyphens in that document as a cited id the verification ledger
must have opened; it had not. The fix reworded the note to say "the cross-libc matrix over ubuntu and macOS"
-- the same fact, without a token the scan cannot resolve -- rather than adding an exemption to the scan,
because a guard that learns to skip one more class of string is a guard with a new blind spot, and this
repository has already paid twice for exemptions written to clear a green. Re-emitting cost a second digest:
`b8491e9a2d2b...` was this round's first emission, superseded inside the round and never pushed.

## 2026-10-15 -- the three placement refusals in `groups.py` have classes; what that costs a reader

Dispatch #98, closing the gap ledger R-272 filed instead of fixing (`bdc1aad`, recorded in this file as
"giving it a class is a fix for every caller of `by_group` and is filed, not quietly done here").
`groups._grouped_by_case` refused three shapes with a bare `ValueError`: a slice value that cannot be a dict
key, one case carrying two values for the same declared key, and a case that states nothing for a key the
other rows state. Those are now `UnhashableSliceValue`, `CaseLeakage` and `UnplacedCase`, raised at the same
three sites with the same three messages -- the wording is unchanged, because rows in
`tests/test_groups.py` assert the sentences.

**What a reader pays, per class.** A caller that caught `ValueError` keeps working: all three keep
`ValueError` as their base, because `cli.main` maps `ValueError` to exit 2 and these are refusals of an
input record set that cannot be partitioned -- the usage class, which is the reasoning the existing comment
at the leakage site gave for rejecting `ArithmeticError`, extended to the other two. Re-parenting one of
them to `RuntimeError`, the shape `report.PublishedArtefactUnavailable` uses for "the checkout cannot
reproduce what it publishes", would move an exit code, so the base is pinned by a row of its own rather than
left to a reader's good intentions. A caller that used to catch `Exception` and print a traceback now has a
name to key on, and the name reaches the operator: the slice producer's refusal for the third shape reads
`DECLARED INPUT UNREADABLE (SliceInputRefusal): the certifier refused these rows: UnplacedCase: case
massive/de/0 states no value ...` where it used to print the word `ValueError` in that position.

**What the producer stopped doing.** `build_document` converted that shape at its own call site precisely
because there was no class to key on. It now keys on the class -- one clause names `UndeclaredGroupKey` and
the three placement classes, and a second, deliberately blanket `except ValueError` follows it for refusals
this file has no name for. The two clauses print different sentences, and that difference is what makes both
of them visible: the wrong-shape row in `tests/test_slice_producer_cli.py` asserts the class-keyed sentence,
and a new row asserts the blanket sentence while asserting the other one absent. Either clause can therefore
still be seen going: narrowing the class tuple reddens the wrong-shape row
(`assert 'the certifier refused these rows' in '... the certifier refused the batch with a refus...'`), and
narrowing the blanket clause lets an unclassified `ValueError` leave `build_document`, match nothing in
`main`'s tuple, and reach the operator as rc 1 -- the code this file's own docstring forbids, and the escape
`bdc1aad` measured and closed. That the blanket clause went unasserted until now is the same gap this file
records about task #86: a handler nobody drives can be deleted in silence.

**Falsification, the way this file's other entries do it.** Seven mutations of a scratch copy, one property
each, every file restored byte-identically with `cmp` and an empty `git status` confirmed after each run,
against the control that all six target rows pass unmutated (`6 passed`, exit `0`). Each of the three raise
sites put back to a bare `ValueError` reddened its row with the original exception propagating (exit `1`);
the site-184 mutation reddened the producer's wrong-shape row as well, which is the class keying showing. A
base class changed to `RuntimeError` reddened the pin with `assert False` on `issubclass(..., ValueError)`,
and collapsing `UnplacedCase` under `CaseLeakage` reddened the same pin on its pairwise half -- so "the three
classes are three" is a guard, not a comment.

One thing this round did not touch, and says so rather than fixing it quietly: the 2026-10-14 entry above
quotes `groups.py:163`, and that line is now `:184`. The old entry is kept as written, per this file's own
rule that corrections are appended rather than retconned.

## 2026-10-15 -- the eighth freeze: G1's ceiling becomes published evidence, and both denominators move with it

Four things moved together, because a claim note, an arm and a denominator that disagree is the defect this
file exists to record.

**G1's `not_certifiable` is now a measured statement.** `tools/g1_feasibility.py` writes
`data/g1_feasibility.json` and `docs/FEASIBILITY.md`; `verify` recomputes every figure in both lanes from
`src/autorate/tails.py` and the published certificates -- **253 field comparisons plus 5 rubric rows** for
this arm alone, which is why the denominators moved from 249/284 to **508 /508** corpus-absent and
**543 /543** corpus-present (the 35-check gap is unchanged: the same nine `SOURCE.json` digests and 26
snapshot keys). What the table states is the width of the exact one-sided bound at each pool size this
checkout can build, and the error rate that would therefore be certifiable at `alpha = 0.05` -- so the row no
longer rests on "we could not", it rests on a recomputable number. Spec §14 called that shape a result
("bound width is a first-class output; 'the bound is useless here' *is* a certification result"), and §14's
kill criterion for G1 has fired: no real task certifies at the published alpha. README, the G1 claim note and
`docs/FEASIBILITY.md` all say the row is unmet; none of them reads it as a certificate.

**The third ungated digit in three arms, now gated.** G3's note said 20 comparisons against 19, G4's said 70
field comparisons against 76, and G1's says `verify` "compares 32 quantities ... plus its rubric" -- measured
by driving `report.rederive_resplit` with counting callbacks, exactly 32 and 5. The existing rows searched
`(\d+) comparisons` and `(\d+) field comparisons plus`, and neither pattern matches a digit followed by
"quantities", so a fourth row now re-derives G1's digit and the set row's regex covers the third spelling --
otherwise a note can state a size in a shape nobody polices. Both new legs were proved load-bearing by
planting: the digit changed to 31 reddened the row naming 31 against 32; removing the count from the note
reddened the set row, which reported `['G3', 'G4']` against the `['G1', 'G3', 'G4']` its own list claims, and
the row guarding its own premise failed with "the G1 note no longer counts the resplit arm". `protocol.json`
was restored byte-identically with the restore checked.

**The rubric's field names have one owner inside the module that owns them.** `report.py` carried the literal
`("alpha", "beta", "delta", "method", "seed")` three times -- `RESPLIT_RUBRIC_FIELDS`, `SLICE_RUBRIC_FIELDS`
and `G1_FEASIBILITY_RUBRIC_FIELDS` -- while the guard that refuses re-declaration scanned only modules inside
the fence, never the fence's owner. They now alias `report.PUBLISHED_RUBRIC_FIELDS`, and
`tests/test_cli.py::test_the_rubric_field_names_have_one_owner_inside_the_module_that_owns_them` parses the
owner module's AST and refuses a second rubric-shaped literal. Parsing, not grepping: a substring scan is
answered by a comment or a rewrapped line. Proven able to fail by re-typing one alias, which reported the two
literal names; restored byte-identically.

**Two clauses of the seventh freeze's own note, fixed here rather than in another round.** The G5 note said
"every tip is witnessed by its own run" -- an unearned universal, since a run exists for a pushed tip and says
nothing about its result -- so it now points at the runner's log instead of asserting a witness, and at
`tests/test_ci_workflow.py` as the row that refuses a workflow edited back to the unfrozen form. The same note
named `tests/test_g5_transcript.py` twice with two framings; it is stated once now. These ride inside this
emission because re-digesting for two sentences would otherwise cost a whole round.

The eighth digest is `4e9e70366d26666267766549bebfd8fa649352d1c52a9f2b4ca61fe50e597c8f`; the six stamped
artefacts were re-stamped by enumerating the publication tables, the emission is a fixed point of this tree,
and both lanes re-derive at rc=0 with no drift line.
## 2026-10-15 -- the slice the criterion names by example was not in the evidence; Khmer joins as a fourth corpus

**The sentence that required this, verbatim.** spec §2's G4 row, measurement column: "per (language x
option-count) bounds with a simultaneous multiple-testing correction; must return `NOT_CERTIFIABLE` for the
slices `laya` documents as collapsed (e.g. **Khmer**: accuracy 0.000 at mean confidence 0.952)". The published
artefact held `run.per_group == ['de','en','sw']`, so the one example the criterion names was absent from the
evidence for the criterion, and `docs/SLICES.md` and `README.md` both said so out loud. Upstream's own
sentences are at `laya-0.3.20/README.md:358` and `:855`. `data/records_massive_km.jsonl` closes the gap:
2,974 per-case Khmer rows, byte-copied from the repaired build and `cmp`-verified, `slices.language == "km"`
on every row and every `case_id` inside the `massive/km/...` segment.

**The group count is not a cosmetic change, so nothing was carried over.** `report.SLICE_RECORDS` grew from
three paths to four, and the correction divides by the group count the DATA produces: `0.05 / 3 = 0.016667`
becomes `0.05 / 4 = 0.0125` per slice. `de`, `en` and `sw` were re-certified at the tighter budget rather than
re-printed from the old artefact, and the re-run is what says where the labels land:

    slices over 'language': 4 groups, 3 claims per group, corrected alpha=0.0125 delta=0.0125, joint level 0.85
    de / en / km / sw, each: NOT CERTIFIED -- empty_feasible_set
    thinnest: de;  worst slice of the joint claim: de;  any slice refused: True;  the run certifies: False
    refused by the size floor (`n_min_violations`): 0
    pooled: n_cal=5948 n_eval=5948, 1010 automated cases, 107 wrong, exact bound 0.123

`km` is NOT the thinnest slice. All four corpora hold 2,974 rows over 2,974 cases at `n_cal=n_eval=1487`, so
the case counts tie and `thinnest` keeps its alphabetical tie-break on `de`; the joint worst-of-`G` claim is
`de` for the same reason, because no slice in this run publishes a bound or an `autorate` the ranking could
read. The prediction in the build notes was that `km` at 0.0615 accuracy would become the worst slice, and the
measurement refutes it: at `empty_feasible_set` the accuracy never reaches the ranking. The budget tightened
and the labels did not move -- that is the finding, and the tie is the reason it holds.

**The reconciliation, with the n each side actually used.** Upstream's headline for Khmer is `0.000` accuracy
at mean confidence `0.952`, and its own result files say what their n was: 100 cases
(`research/results/cpu_51_language_sweep.json`, unclamped `mean_confidence` 0.9515). This tree measures the
same checkpoint over the full split: **183 correct of 2,974 rows = 0.0615, mean max probability 0.6865** --
and 0.6865 is the CLAMPED regime the committed records carry, while 0.952 is upstream's UNCLAMPED reading
(0.9355 unclamped at n=2,974 in the build log). Two differences, not one: the denominator and the regime. The
probability that a 100-case draw contains zero of the 183 correct cases is `0.9385^100 = 1.75e-3` with
replacement and `C(2791,100)/C(2974,100) = 1.56e-3` without it. The upstream `1.6e-4` quoted in the build
notes is an order of magnitude out -- right mantissa, wrong exponent -- and this file corrects it rather than
restating it. So `0.000` is not a contradiction of `0.0615` and not an agreement either: it is a 100-case
measurement that does not extend to the 2,974-case split, where the model gets 183 right. The `en` row needs
no probability argument for the same point: upstream's suite says 0.8200 at n=100, the committed split says
0.7260 at n=2,974.

**What the marginal certificate for Khmer says.** `autorate certify data/records_massive_km.jsonl --backend
laya` writes `data/cert_massive_km_laya.json` as NOT_CERTIFIABLE, `empty_feasible_set`: at coverage 0.950 it
automates 11 of 1,487 cases, 5 of them carry a wrong automated request, exact case-level upper bound 0.729
against the 0.050 budget. Beside `de` (0 of 1,487), `en` (709, 43 wrong, 0.078) and `sw` (39, 13 wrong,
0.477), it is the fourth collapsed slice this repository scores rather than quotes.

**Every consumer that moved, and what the round deliberately left undone.** The publication tables
(`report.MASSIVE_CERTIFICATES`, `report.SLICE_RECORDS`), the slice artefact and `docs/SLICES.md`,
`data/resplit_200.json` and `docs/RESPLIT.md` (`published_tasks()` reads the certificate table, so G1's second
column went from five decision tasks to six and the sweep was re-run rather than described), `docs/REPORT.md`,
and README's two denominators. `src/autorate/techreport.py` needed no edit: every count it prints is read
from the tables, which is the point of the tables. What is NOT stamped and NOT frozen here, on purpose:
`data/cert_massive_km_laya.json` carries no `meta.protocol_digest`, `protocol.json` and `src/autorate/protocol.py`
are untouched, and so the gate now prints one named drift in each lane -- `re-derived 285 /286 values`
corpus-absent (was 249 /249) and `320 /321` corpus-present (was 284 /284), both rc 4, both from the same
`DRIFT: cert massive/km.meta` line. Each lane's total grew by 37, and the two parts of that are different
reasons: 32 comparisons come from the Khmer corpus itself (16 for the certificate's fields and summary, 16 for
the fourth slice's group, census and input rows), and 5 come from `resplit_invariants`, which adds five
self-consistency rows per task and just got a sixth decision task. The inter-lane gap is unchanged at 35
checks, and the slice arm's own count moved from 76 field comparisons to 92. The re-freeze, the
stamp, and the two claim notes that this round makes false -- G4's "three committed MASSIVE record files
(8,922 cases ... 0.05 / 3 = 0.016667)" and G1's "five tasks, zero certify" -- are the controller's act, in the
round that re-stamps the now-seven stamped artefacts. `tools/restamp.py` refuses a declared artefact that
carries no digest on disk, so that round has to CREATE this certificate under the new freeze rather than only
re-stamp it; the refusal is correct and the requirement is worth naming before somebody meets it.

**The vacuity this round actually removed, because it was in a fixture line.**
`tests/test_slice_producer_cli.py` opened with `DE, EN, SW = report.SLICE_RECORDS`. A fixed-length
destructure of a publication table takes the trio's arity as a fact about the tree: declaring the fourth
corpus raised `ValueError: too many values to unpack (expected 3)` at IMPORT and reddened all eight rows in
the file for a reason that was not a defect in the producer, the artefact or the data. It is now a lookup
against the same table, and the rows that care about the COUNT read `len(report.SLICE_RECORDS)`. Two rows were
added: one asserts the run's slice set against the table in both directions, with the group count and the
census total against the corpus line count; one asserts the criterion's own example is present in the
published artefact and refuses there -- written RED against the three-slice artefact, and the only guard
against Khmer being unpublished again. `tests/test_slice_surface.py` likewise lost its `== 3` and
`== ["de","en","sw"]` literals to the same derivation.

## 2026-10-16 -- the ninth freeze: Khmer joins the evidence, and a frozen sentence named a worst slice the artefact never computed

**What moved.** `data/records_massive_km.jsonl` (2,974 per-case rows) and
`data/cert_massive_km_laya.json` are published, so `report.SLICE_RECORDS` and
`report.MASSIVE_CERTIFICATES` each carry four languages and the published certificates are seven, not six.
`verify` now re-derives **578 /578** values with the corpus absent and **613 /613** with it present; the gap is
still the 35 checks only a corpus can recompute. The ninth digest is
`358d17bd02b159e4520b9bd5651cd2d9952bbece86b98c9d1541049d5c84f5aa`, frozen 2026-10-16, and the seven stamped
artefacts were re-stamped to it by the derived list in `task2/t96/restamp.py`, not by a typed one.

**Two digits in the frozen notes were false against this tree, and both are arm-measured now.**
`claims.G4.note` said "76 field comparisons plus 5 rubric rows"; driving `report.rederive_slices` with counting
callbacks makes **92** field comparisons and 5 rubric rows. `claims.G1.note` said `verify` "compares 32
quantities"; driving `report.rederive_resplit` makes **37** (the row asserts the 37 against the note and the
rubric labels against `report.RESPLIT_RUBRIC_FIELDS`, so "plus its rubric" is the row's own accounting, not a
number in the sentence). `data/g1_feasibility.json` was re-emitted and prints `0 of 6 scored tasks certify`;
the note's "all five decision tasks" and the README's "Five decision tasks" are six, because Khmer is now a
scored task in the 200-resplit table, which has seven rows -- six real and the labelled synthetic control.

**The claim note said something the artefact does not contain, and this round is where it was caught.**
`claims.G4.note` read: "3 slices, 0 certified, `any_slice_refused` true, **the worst slice named `de`**". No
field of `data/slices_language.json` names a worst slice: `run.worst_claim` carries `n_groups`, the corrected
budgets, `any_slice_refused` and a `groups` list ordered de, en, sw -- `groups[0]` is `de` because that is the
sorted order, and every group's `autorate`, `qhat` and `conditional_error_bound` are null, because a refused
slice publishes no rate. So `de` was never the worst; it was the first. The sentence was measured by asking
the artefact for a field that could support it and finding none, which is the same defect class as the
transcribed denominators in R-275 and R-288: prose that reads as an observation but is an inference from
ordering. The note now states what the run demonstrates -- every slice refuses, and with nothing certified the
ranking `worst` asks for has no value to rank -- and the README says the same.

**One cause was a branch, not a producer.** `plan/b3-task68-khmer` was cut from `fe8a085`, before the eighth
freeze existed, so its author re-emitted the slice and resplit artefacts and had no way to know
`tools/g1_feasibility.py` also reads the certificate set; the merged tree therefore drifted on 24
`g1 massive/km.*` fields (`re-derived 554 /578`), all of them "published None" until the arm was re-run. The
Khmer certificate itself drifted first because it had been emitted through bare `certify` and carried no
`meta.protocol_digest` at all; it was re-produced through `certify --protocol` against the freeze the other six
already carried rather than patched with a key, because the stamp is the thing `verify` compares.

**Provenance re-checked, not inherited.** The Khmer rows' `cmp` against the off-tree build was re-run here
(rc=0), all 2,974 rows carry `slices.language == "km"` and a `massive/km/...` case_id, and the digest the slice
artefact records for the file (`dd302722ed49cef8…`) equals the file's own sha256. `slices.option_count` is 20 on
every Khmer row, so the degeneracy the G4 note claims is measured rather than assumed.


## 2026-10-16 — the whole-branch review's two blockers, and a correction to the ninth freeze's own entry

A whole-branch review of `6f06fa3` (report at `task2/final-review/review-6f06fa3.md` in the evidence tree)
found two published-prose defects that every gate on this tree was unable to see, and both were fixed in the
tenth freeze. They are recorded here because the rule this file exists for is that a published sentence must
not be corrected in place without saying what it said.

**G4's note denied a field the same note counts.** The ninth freeze's note said the published run had "no
slice named as the worst" and that "the artefact names no worst at all". `data/slices_language.json`
`run.worst_claim.worst` is not empty: its `group` is `de`, its `metric` is `autorate`, and
`report.SLICE_WORST_FIELDS` makes `worst.group` one of the 92 field comparisons the note itself cites. The
correction the ninth freeze made -- removing a draft that named `de` as the worst slice -- was right, and the
sentence written in its place went to the opposite falsehood. The tenth freeze's note states the field and
then states what it is not: a tie-break, not a ranking, because the metric that would have ranked the slices
is null in all four rows. `tests/test_slice_surface.py::test_the_frozen_g4_note_transcribes_the_worst_field_the_arm_compares`
reads the note against the field in both directions.

**Two generated documents typed a task count their own tables derive.** `docs/RESPLIT.md` said "The five
published tasks refuse in every split" under its own line "`- tasks: 7 (the 6 published decision tasks …)`",
and `docs/FEASIBILITY.md` said "This tree scores five … for all five" above its own "- scored decision tasks
read from their certificates: 6". The words came from `render_resplit` and `render_g1_feasibility`, so the
byte-compare arm re-derived the error on every run and could not fail -- a guard that reproduces its own
document certifies the document, not the truth. Both renderers now interpolate the count they already derive
(`len(doc["tasks"]) - 1`, `len(scored)`), and the two rows that assert the prose count equal the derived count
went red on the committed bytes first. The ceiling document's cross-reference to the resplit result dropped its
typed "0 of 200 … all five" for a numberless sentence, because that figure belongs to an artefact the ceiling
renderer does not read.

**A correction to a dated entry, appended rather than edited.** The ninth freeze's entry above stated that
"`run.worst_claim` carries `n_groups`, the corrected budgets, `any_slice_refused` and a `groups` list ordered
de, en, sw". Measured on the committed bytes: `worst_claim` carries 21 keys -- `alpha`, `any_slice_refused`,
`beta`, `corrected_alpha`, `corrected_beta`, `corrected_delta`, `delta`, `groups`, `groups_declared`,
`joint_level`, `joint_level_inputs`, `joint_level_note`, `joint_level_risk`, `joint_level_rule`, `level`,
`metric`, `n_claims`, `n_groups`, `refusals`, `slices_without_the_metric`, `worst` -- and `groups` has four
entries in the order `de, en, km, sw`. The entry omitted the one key (`worst`) that decided the question it
was cited to settle, and described the four-slice artefact with a three-slice list.

**G3's "published marginal bound" was not published.** The note called `0.014867` "that certificate's own
published marginal bound". No file under `data/` carries it: the contrast certificate is built in memory by
`tests/test_g3_contrast.py` and written to no path, and the only assertion touching it (`over_hi / n <=
score.marginal_error_bound`) is true for any value of the bound, so the digit could not go red. The wording now
names the builder and says the number is computed, not published. The digits in that family -- `4` of `64` knob
cells, `600` records / `200` cases, `36` empty sets, `0.014867` -- and G2's audit multiples are listed in
`DECLARED_UNOWNED_NOTE_DIGITS` in `tests/test_verify_protocol.py`, which is the inventory that the new residue
row refuses to let grow.

**G5's network line named a cause its probe never tested.** `docs/G5.md` records "attempted a DNS-failing HTTPS
fetch, and it failed as required (curl rc=35)". `tools/g5_export.sh` gave every non-zero curl code that
sentence; rc=35 is an SSL-connect failure, not name resolution. Re-measured on this machine, the same URL
returns 6 (`curl: (6) Could not resolve host`), which is the failure the sentence describes -- so the recorded
35 was real on the machine that ran the export and was simply mislabelled by the script. The script now branches
on the code: 6 gets the name-resolution sentence, any other non-zero code gets a sentence that says plainly that
it is not a name-resolution failure. `docs/G5.md` is a transcript of the run that produced it and is not
re-written here; re-exporting it at its own frozen revision is the follow-up that would replace this paragraph
with a line that agrees with its own code.

**G1's §14 kill criterion was reported as fired when it is not evaluable.** The criterion's condition compares a
worst-group certified `autorate` with 0.30, and no slice certifies, so there is no certified `autorate` to put
in the comparison -- the same zero-denominator refusal the note invokes four sentences earlier for the violation
rate. The note now says the condition is not evaluable, and that the pivot it names is only half published:
G2's audit is, Plan B3's contamination layer is not.

## 2026-10-16 -- ledger #37/#71: one bound name carried two denominators, and the artefact's own note claimed only one

**What the artefact used to claim.** `data/cert_jev.json` publishes
`meta.at_requested_alpha = {"automated": 96, "errors": 1, "conditional_error_bound": 0.139849460275}`. The two
counts are RECORD counts; the bound beside them is `clopper_pearson_upper(1, 32, 0.05)`, computed over the 32
automated CASES. On the same artefact `meta.closest_attempt.conditional_error_bound` is `0.048462071706`, which
is over 1 error in those 96 records. One field name, two denominators, no key saying which -- and
`meta.unit_note` read "96 evaluation records over 32 distinct cases: the bounds use the case denominator,
because repeats of one case are one observation", which is true of the three headline bounds and false of every
`meta.diagnostic_curve` row and of its `closest_attempt` copy. The prose was the part that misled a reader who
trusted the artefact rather than the code. Each row also divided `automated` by `len(ev)` to publish
`observed_automation_rate` without naming that divisor anywhere on the row.

**What it names now.** Every diagnostic curve row of the two set gates (`certify_choice.py`, `certify_score.py`)
carries `bound_unit` and `evaluated_records`, and `at_requested_alpha` carries `automated_cases` and
`errors_cases` beside the record counts with `bound_unit: "case"`. `closest_attempt` is one of those rows, so it
inherits the naming rather than being special-cased. The two spellings have exactly one owner,
`certificate.BOUND_UNIT_RECORD` and `BOUND_UNIT_CASE`, which the producers import. `meta.unit_note` states the
split -- headline bounds over cases, curve rows and `closest_attempt` over records -- from the same two counts it
quoted before, with no new number typed into it. The change is additive and inside `meta`, so `SHAPE_VERSION`
stays 2: the shape check diffs the top-level serialized field set, and a key added inside `meta` is invisible to
it.

**What did not move, measured rather than asserted.** Each artefact was re-emitted to a scratch directory and
compared field by field with the committed bytes before anything was copied into `data/`: 61 added keys for
`laya` and `jev`, 48 for `de`, 57 for `en`, 59 for `km`, 55 for `sw`, and exactly one changed value per file --
`meta.unit_note`. No bound, rate, count, quantile or interval moved. `docs/REPORT.md` re-renders with the new
note on its six artefact lines and nothing else; `docs/RESULTS.md`, `data/inventory.md`, `docs/AUDIT.md`,
`docs/SEVERITY.md`, `docs/RESPLIT.md`, `docs/SLICES.md` and `docs/FEASIBILITY.md` re-emit byte for byte. All four
`verify` invocations exit 0: `re-derived 578 /578 values` with the corpus absent and `re-derived 613 /613 values`
with it present, each without `--protocol` and with `--protocol protocol.json`. Neither published denominator
moved, so this row owes no freeze round and the gap is still the 35 corpus-only checks.

**What is still stale, named rather than quietly left.** `data/slices_language.json` embeds the per-slice and
pooled certificate `meta` this same producer writes, and its ten `unit_note` strings are still the old
single-unit sentence with none of the new keys -- that artefact was emitted before this change landed. The gate
cannot see it: `report.SLICE_GROUP_FIELDS` and `report.SLICE_POOLED_FIELDS` compare named headline fields and
never `meta`, so `verify` stays green over a stale embedded note. Re-emitting it belongs to
`python3 tools/language_slices.py --out data/slices_language.json` and the `docs/SLICES.md` re-render, both
owned by another round, so they are not touched here. `certify_threshold.py` keeps its own style on purpose --
each of its rows already publishes the operands of both bounds and two unit-named bound keys, which is the
standard this naming follows -- and `data/cert_severity_ordinal.json` keeps the single-unit sentence because it
publishes no curve and every bound it carries is over cases, so nothing there contradicts its note.
## 2026-10-17 — the residue guard was red under the eleventh freeze, and a `§` pointer needed no owner

**The eleventh freeze shipped a red guard.** `test_no_frozen_note_states_a_quantity_digit_that_neither_a_row_nor_the_inventory_owns`
failed at `242aac4` in both lanes, measured on the tree as committed:

    AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir  -> FAILED: G4 states digit(s) ['0.207502', '0.235208',
                                                       '0.262646', '27', '29'] that no row re-derives
    AUTORATE_FEISHU_ROOT=<the vendored corpus>    -> FAILED: the same five digits

The contamination additions were computed into the local name `g4_owned` *after* `owned = {…}` had already
bound `owned["G4"]` to the earlier set, so every digit the eleventh freeze put into G4's note -- the arm's `29`
field checks and `4` budget values, the `27` pinned rows, `delta_hat` and both interval ends -- had no owner.
The row the tenth freeze wrote to stop ungated digits was itself the thing that let them through, and this
round's "green" was quoted from the export of `b9be801`, which predates the contamination block: a suite run on
an older tree is not evidence about the tree it was quoted for. The block now runs before the dictionary is
built. The pre-fix red above is the row's own falsification -- it goes from failing to passing with no change to
the note, the artefacts, or the protocol digest (`25e76b21af4c…`, unchanged: no claim note moved, so this round
is a correction and not a tenth re-emission).

**A note could point at a spec section that does not exist.** The residue rule treats a digit next to a section
sign as structural, so `§14` was never a candidate for ownership: a note citing `§99` would have been waived, not
checked. Both spellings -- `section 9` and `§9` -- are now policed against the spec's own top-level headings by
`test_every_spec_section_pointer_in_the_frozen_notes_names_a_real_section`, and the residue row subtracts a
pointer only where the heading exists, so a renumbered spec reddens the note that cites it rather than quietly
exempting the pointer. Measured on the committed bytes, G1 carries two pointers, `9` (Contamination
stratification) and `14` (Risks, and what would make us stop), and the spec has 17 top-level sections.

**A new published artefact reddened seven rows that build a scratch checkout.** The same run that found the
guard defect above found this one: `tests/test_cli.py` and `tests/test_inventory.py` in the corpus-visible lane
returned 9 failures against 1169 passes and 2 skips. Seven were real. Freeze 11 added
`data/contamination_probe.json`, `data/pin_app_benchmark.json` and `docs/CONTAMINATION.md` to the gate's tables
and left behind the rows that fabricate a partial checkout to plant a *different* defect: `stage_published(work)`
copies the artefacts the tables declare, and its table list predated the contamination pair, so
`test_verify_without_a_corpus_or_a_snapshot_is_a_usage_error`, `test_a_missing_published_artefact_is_a_named_drift_not_a_usage_error`,
`test_a_published_artefact_that_does_not_parse_is_the_same_drift_not_a_usage_error`, the two inventory-snapshot
drift rows, `test_verify_reds_when_a_transcribed_bound_column_is_wrong` and
`test_verify_runs_and_agrees_where_the_corpus_does_not_exist` all refused on
`PUBLISHED ARTEFACT UNAVAILABLE: data/contamination_probe.json` -- the right exit code for the wrong witness,
because the planted tamper never got to speak. The fixture now reads the pair from `report.CONTAMINATION_JSON`
and `report.CONTAMINATION_PIN` the way it reads every other table, and the agreement row's independent
membership literal gained `docs/CONTAMINATION.md` plus the arm's comparison terms (its own count of 612 in the
absent lane, derived from the strata, the whole-value and probe-block comparisons, the headline fields and the
rubric, not typed). The other two failures were the probe, not the tree: they need the `autorate` console script
on PATH to run the shipped entry point, and the run that reported them launched pytest without it -- re-run with
`.venv/bin` on PATH, both pass. What is disclosed here is the class: every one of these rows was green in CI
because CI cannot see them failing, and the round that published the arm reported its suite from an export of an
earlier commit.

The resolver that closed the lane difference was itself landed incomplete: it wrapped `cli._default_corpus()` in
`Path` unconditionally, and that resolver answers `None` where no sibling corpus exists -- a fresh clone, the
`git archive` export, CI without the variable set. The corpus-less export caught it as a `TypeError`, which is an
rc 1 out of `verify`, and the branch that returns `None` for that case went in beside the row that now asserts it
(`test_the_resolver_returns_nothing_rather_than_raising_where_no_corpus_exists`, red as a crash before the fix).
Nothing published carried the defect: it was caught between two commits on the same round, before the push.

## 2026-10-17 — the twelfth freeze: #37's naming lands, and the slice artefact was the last holder of the retired sentence

**The round's evidence.** `protocol.json` was emitted at `frozen_at` 2026-10-17 with digest
`ce43f8e29cc1f2ddeeec0132d3d2392225c95bb844c27f964eeeb01d43062d69`, and all seven stamped artefacts were
re-emitted by their own shipped commands rather than edited: `autorate certify` for the two marginal
certificates and the four MASSIVE ones (rc 3 each -- every one is a published refusal), `autorate severity
--direction under` for the ordinal certificate. Measured against the committed bytes before anything was
installed, each of the seven differed in exactly one leaf, `meta.protocol_digest`. The emission is a fixed
point (a second `autorate protocol` produced the same bytes), and re-emitting the protocol after the
artefacts moved produced the same file again, so no note stated a count the re-emission changed. `verify`
answers `re-derived 612 /612 values` with the corpus absent and `649 /649` with it present, in both the bare
and the `--protocol` shape, all rc 0; the lane gap is still 37 and neither published denominator moved.

**Review M1 was real and is now closed.** `data/slices_language.json` embedded ten certificate `meta` blocks
written by the same producer that #37 changed, and after that branch landed they were the only published place
still carrying the retired sentence: the committed artefact had `bound_unit` 0 times and `evaluated_records` 0
times while holding 261 record-denominator bounds. `verify` compares the slice arm's `run` fields and never
those embedded metas, so the gate stayed green over the artefact that disagreed with its own producer.
Re-running `tools/language_slices.py --out data/slices_language.json --doc docs/SLICES.md --force` emits 261
`bound_unit` keys, all ten notes naming both denominators, and the run block moved with them. `docs/SLICES.md`
did not change a byte -- nothing in the document reads a certificate `meta` -- which is the reason the
artefact and its document could hold opposite statements about the same certification.

**Review M2 was real, and its blast radius was bigger than the review measured.**
`certify_threshold.py` published "the bounds use the case denominator" while every one of its curve rows and
its `closest_attempt` copy carries `conditional_error_bound` over cases beside `record_conditional_error_bound`
over records. The note now names both keys, and the row that polices it (`test_the_threshold_gate_keeps_its_own_style_and_is_not_renamed_into_the_new_one`)
failed first by quoting the producer's own words: "195 evaluation records over 65 distinct cases: the bounds use
the case denominator, ...". The review's claim that no committed artefact carries that sentence was wrong: the
phrase also appears in `data/cert_severity_ordinal.json`, written by `severity.py:545`. That one is not a
defect and was not touched -- all three of the severity gate's bounds are Clopper-Pearson over cases
(`severity.py:347,498,499`) and it publishes no record-denominator bound, so its sentence is true, and a
repo-wide guard on the phrase would have indicted an honest statement.

**What the same measurement could not settle, and is therefore filed rather than fixed.** The ordinal
artefact's own case counts are `n_cal_cases = n_eval_cases`, so recomputing its three bounds from a pair inside
the object reproduces them from either denominator: the artefact cannot evidence which one its note means. That
is the same defect class as the two ratios #71 already carries, so it is recorded there, not papered over with a
guard that cannot fail.

**Two probe defects found and fixed inside this round, neither of them a repository bug.** A linked worktree has
no interpreter of its own, so `-m autorate.cli` resolved through the main checkout's editable install and the
first pass re-emitted the six certificates from a producer without #37's naming -- its own key comparison caught
it ("keys disappeared: .../bound_unit"), which is why the chain now prints `autorate.__file__` and refuses when
it is not this tree. And `restamp.py` refuses a disk whose stamped artefacts disagree about which freeze they
carry, so re-emitting six of seven certificates left the seventh at the eleventh digest and the re-stamp
correctly stopped; the seventh is now produced in the chain as well.
