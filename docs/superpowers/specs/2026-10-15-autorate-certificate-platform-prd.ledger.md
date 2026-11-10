# Ledger — Autorate Portal PRD

Companion to [`2026-10-15-autorate-certificate-platform-prd.md`](2026-10-15-autorate-certificate-platform-prd.md).
This file is the executor's record: baselines captured, gates run, and what each exit code came from.
Readings live here; constraints live in the PRD. A value here is a value **at a date**, and the date is
always printed beside it.

The repository root is resolved with `git rev-parse --show-toplevel`; no absolute machine path is written
into this file, because `tests/test_cli.py::test_no_committed_file_carries_an_absolute_home_path` scans
every tracked file for one.

---

## 1. Baseline block — 2026-11-06 (PRD §0.4)

Captured before any file in this session was created or edited. Every exit code below was read from the
command that produced it (`cmd > log 2>&1; echo "NAME_EXIT=$?"`), never from a pipeline's last stage.

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
plan/b-inventory-fields

$ git rev-parse --short HEAD
dfaf33f
```

`B1A_EXIT=0` (branch) · `B1B_EXIT=0` (tip).

### B2 — working tree

```text
$ git status --short
```

Empty output, 0 lines. `B2_EXIT=0`. No other session's work was in the tree at capture time.

### B3 — the honesty gate

```text
$ uv run --frozen autorate verify --protocol protocol.json
claim G1 not_certifiable ≥3 decision tasks yield a certified `autorate(α=0.05)` with an upper risk bound
claim G2 measured_not_bounded The gate `laya`'s README instructs demonstrably violates its own implied error rate
claim G3 not_measured ≥1 ordinal guarantee that multiclass CP cannot express
claim G4 not_met Worst-slice certification refuses rather than averages
claim G5 certified Reproducible from a commit with no GPU, no network, no model
protocol: protocol.json ce43f8e29cc1 (frozen 2026-10-17)
inventory source: recomputed from the corpus
disclosure: corpus present: inventory, digests and the snapshot all re-derived; the frozen protocol rubric was enforced
re-derived 649 /649 values
```

`B3_EXIT=0`.

The two labels the product displays are the tool's own, not this file's reading of them:

| Label | Value at this baseline | Where it comes from |
|---|---|---|
| lane | **`corpus present`** | the `disclosure:` line, verbatim |
| denominator | **`649 /649`** | the `re-derived N /M values` line, verbatim |
| freeze | `protocol.json ce43f8e29cc1 (frozen 2026-10-17)` | `protocol:` line |

### B4 — command surface

```text
$ uv run --frozen autorate --help
usage: autorate [-h]
                {snapshot,export-feishu,certify,severity,compare,gate,report,audit,protocol,verify}
                ...
```

`B4_EXIT=0`. Ten subcommands, in the tool's own order:
`snapshot`, `export-feishu`, `certify`, `severity`, `compare`, `gate`, `report`, `audit`, `protocol`,
`verify`.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PRIVATE"}
```

`B5_EXIT=0`. Visibility **PRIVATE**; the repository has not been flipped.

### 1.1 What moved since the evidence snapshot's 2026-10-15 block

The PRD says a reading that disagrees with a sentence wins, and the snapshot is dated. Recorded here
rather than annotated there:

| Reading | Snapshot 2026-10-15 | This baseline 2026-11-06 |
|---|---|---|
| branch / tip | `plan/b-inventory-fields` / `7bdf2c2` | `plan/b-inventory-fields` / `dfaf33f` |
| `verify` denominator | `543 /543` | `649 /649` |
| freeze digest | `4e9e70366d26`, frozen 2026-10-15 | `ce43f8e29cc1`, frozen 2026-10-17 |
| LICENSE | absent | present |
| lane | `corpus present` | `corpus present` |

The denominators are **not** comparable across these two dates; §0.5's check is against B3 of the same
session, which is what the gate matrix uses.

### 1.2 Session scope

`M0` remainder only: **F8** — the in-repo composite GitHub Action and the status badge (PRD §7 M0 row,
§5 F8). Everything else in M0 is already settled or held:

- `LICENSE` — done (§13.8 item 3).
- A1/A2/A3/A5/A6 — settled (§12.3).
- git tag, PyPI release — held on A7 (no publishing credential on this machine).
- repository visibility — held on §0.2 carve-out (a) and the unadjudicated §8.3 item 1.
- `autorate-portal` scaffold — after A4.

### 1.3 Held, not executed, and why

- **Public flip** — not done. §8.3 item 1 ("read every sentence that asserts upstream's present state")
  is still unadjudicated, so the §0.2 (a) hold stands.
- **Exposure sweep** — the read-only sweep's report, `~/laya-evidence/exposure-sweep/report.md`,
  **does not exist** at 2026-11-06 (`ls` → `No such file or directory`). The sweep that §8.3 item 1 depends on has
  not been produced. Treating its absence as a pass would be the defect; it is recorded here as an open
  item with no owner in this session.
- **PyPI publish / tag** — not done; A7 (§12.3) has no credential, and the instrument is a
  project-scoped API token the owner creates.
- **`awesome-jev-tools`** — not touched; `docs/upstream/awesome-jev-entry.md` is a committed `OMITTED`
  decision record and §13.8 item 5 says a portal does not re-open it.
- **Upstream `NandhaKishorM/laya`** — no new issue or PR. #1263 was filed 2026-10-16; §0.2 (b)'s
  four-part instruction still governs any follow-up.

---

## 2. Gates — appended as they are run

Append-only from here: a later section may add readings, never rewrite the block above.

---

## 3. Milestone M1 opening — 2026-11-09 (PRD §0.4, §13.5)

Captured after the `autorate 0.1.2` PyPI release and its `v0.1.2` tag, before
any M1 source edit. Every exit code below was read from the command that
produced it. The 2026-11-06 block above is history, not ground truth.

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
integration/f8-into-main

$ git rev-parse --short HEAD
e9b0cf1
```

`B1A_EXIT=0` · `B1B_EXIT=0`. `origin/main` points at the same commit.

### B2 — working tree

```text
$ git status --short
```

`B2_EXIT=0`, `B2_LINES=0`. No other work in the tree.

### B3 — the honesty gate

```text
$ uv run --frozen autorate verify --protocol protocol.json
protocol: protocol.json ce43f8e29cc1 (frozen 2026-10-17)
inventory source: recomputed from the corpus
disclosure: corpus present: inventory, digests and the snapshot all re-derived;
            the frozen protocol rubric was enforced
re-derived 649 /649 values
```

`B3_EXIT=0`. Lane: **corpus present**. NIF reference denominator: **649 /649**.
The clean-clone corpus-absent run printed **612 /612 values**; both are
baseline facts.

### B4 — command surface

```text
$ uv run --frozen autorate --help
snapshot, export-feishu, certify, severity, compare, gate, report, audit,
protocol, verify
```

`B4_EXIT=0`, 10 subcommands.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PUBLIC"}
```

`B5_EXIT=0`. The 2026-11-06 block recorded `PRIVATE`; that reading is stale and
is left in place as history, corrected here by the newer reading.

### M1 scope and stop point

At the 2026-11-09 open, Section 7 assigned M1 to the `autorate-portal`
repository, which did not exist locally or under the owner's GitHub account at
that moment. Section 13.5 forbids carrying an earlier session's approval
forward, so creating that repository was put to the owner rather than assumed;
the owner approved it as a **public** repository and M1 was then implemented
there. No M1 source file was created in *this* repository: Section 7's
"the frozen repo is untouched" holds.

The M1 plan is committed in the portal repo at
`docs/superpowers/plans/2026-11-09-m1-evidence-packet.md`. The Section 13.2
report, the Section 13.1 gate logs and the packets themselves are readings, and
readings for M1 live in the external evidence directory recorded in Section 4
below rather than in this repository.

### Deviation registered, not hidden

This commit changes one file under `docs/` (this ledger), so
`git diff --name-only HEAD~1 -- data/ docs/` is not empty for this commit.
The byte-compared `data/` tree is untouched, `verify` still exits 0 at
**649 /649**, and no guard was relaxed. Section 13.5 requires the ledger
commit before source edits; Section 13.1's published-artefact gate is counted
as a deviation here rather than described as zero.

### Owner decisions still open

1. Any new upstream filing still requires the four-part instruction in
   `docs/upstream/SUBMISSION.md` (Section 0.2 (b), Section 13.7).
2. M2's pinned-distribution registry starts from the versions in Section 4
   below; widening it to older releases is a decision not yet taken.

The two M1 decisions this list used to hold - whether `autorate-portal` exists
and is public, and which `autorate` version the packet pins - were taken by the
owner on 2026-11-09 and are recorded as decisions in Section 4.

---

## 4. Milestone M1 closure — 2026-11-09

Owner approved the M1 stop point on 2026-11-09. The readings below are what M1
proved; the narrative, the liveness table, the seven deviations and the
disclosures are in `report-2026-11-09-m1-close.md` in the evidence directory
(`~/laya-evidence/m1-2026-11-09/`, sha256 `e9aa7f98…` at approval), next to the
gate table, the packets and the CI logs each figure is read from.

### Decisions taken

| Decision | Value | Date |
|---|---|---|
| `autorate-portal` created | yes, **public**, `Jackxiaozhiren/autorate-portal` | 2026-11-09 |
| pinned distribution | `autorate 0.1.2`, wheel sha256 `7709d3faa560417e…` | 2026-11-09 |
| M1 report accepted | `report-2026-11-09-m1-close.md`, ten §13.2 sections | 2026-11-09 |

### Readings that close M1

| Reading | Value at 2026-11-09 | Where it was read |
|---|---|---|
| portal commits | `0eb1c64`, `4c4ff1d`, `25e549b` | `git log` on the portal repo |
| portal CI | `42582581800`, `42584682718`, both jobs green | `gh run view --json` |
| portal tests | 49 collected, 49 passed | `gate/suite.log` |
| negative controls | 21 of 21 plants fired red and were restored, sha256 receipt | `logs_plants_v2.log` |
| AC1 | tampered byte → rc 4, did not index | `gate/ac1_verify.log` |
| AC9 | `certified 612 /612` in four runs: two backends (uv, container) on this machine, and the same two in CI | `logs_ac9_real_replay.log`, `ci_42584682718_full.log` |
| AC10 | Docker off `PATH` and PyPI unreachable → rc 3 `not-run`, `argv=[]`, `exit_code=null` | `logs_ac10_real_absence.log` |
| AC14 | fresh registry `created row` → `idempotent hit`, `FRESH_ROWS=1` | `gate/ac14_fresh.log` |
| I6 | pinned wheel hash swapped → rc 4, receipt `03b7af4c…` unchanged after restore | `gate/i6.log` |
| packet | full 33 artefacts / shareable 27, sha256 `03b7af4c…` / `148c22a9…` | `logs_t9_t10.log` |
| reproducibility | two clean checkouts, byte-identical, same sha256 as CI | `GATE_REBUILD_BYTE_IDENTICAL_RC=0` |
| privacy (§8.4) | full: 6 records files, 15015 rows, 0 named; shareable: 0 files, 0 rows | `GATE_PRIVACY` lines |
| packet scope | 33 of 146 tracked files at `e9b0cf1` (21 `data/`, 11 `docs/`, `protocol.json`) | `packet_scope.log` |

### Correction, not annotation (Section 8.3)

Four sentences in Section 3 above asserted a present state that stopped being
true the moment the owner approved: that `autorate-portal` did not exist, that
creating it was not executed, that no M1 source file was created, and that
AC1/AC9/AC10/AC14 were not proven. Section 8.3 says such a sentence is
*corrected or dropped, not annotated*, so those sentences were rewritten in
place here rather than left standing with a note beneath them; the previous
wording stays readable at `9bce245`. The same rule was applied to the two
resolved owner decisions above.

### Deviation, counted

This commit changes one file under `docs/`, so
`git diff --name-only e9b0cf1..HEAD -- data/ docs/` returns one path and
`git diff --name-only e9b0cf1..HEAD -- data/` returns **0**. `verify` still
exits 0 at **649 /649**; the packet is built from `e9b0cf1`, the release
commit, so no published artefact moved. Section 13.1's published-artefact row
therefore reads **1**, not 0 - the same single path as before, in the ledger
that Section 13.5 requires.

---

## 5. Milestone M2 opening — 2026-11-09 (PRD §0.4, §13.5)

Captured at the M1-closure tip, before any M2 source edit. The two opening
blocks above are history, not ground truth.

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
integration/f8-into-main

$ git rev-parse --short HEAD
b55cb53
```

`B1A_EXIT=0` · `B1B_EXIT=0`. `origin/main` points at the same commit.

### B2 — working tree

```text
$ git status --short
```

Empty output, 0 lines. `B2_EXIT=0`, `B2_LINES=0`.

### B3 — the honesty gate

```text
$ uv run --frozen autorate verify --protocol protocol.json
protocol: protocol.json ce43f8e29cc1 (frozen 2026-10-17)
inventory source: recomputed from the corpus
disclosure: corpus present: inventory, digests and the snapshot all re-derived;
            the frozen protocol rubric was enforced
re-derived 649 /649 values
```

`B3_EXIT=0`. Lane **corpus present**; NIF reference denominator **649 /649**,
identical to the M1 opening. M1 changed no `data/` file, so the clean-clone
corpus-absent reading of 2026-11-09 (**612 /612**) stands too.

### B4 — command surface

```text
$ uv run --frozen autorate --help
snapshot, export-feishu, certify, severity, compare, gate, report, audit,
protocol, verify
```

`B4_EXIT=0`, 10 subcommands. M2 adds nothing here: Section 7 puts the runner in
the portal repo, not on the frozen chain.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PUBLIC"}
```

`B5_EXIT=0`. Unchanged since the M1 opening.

### M2 scope, and what is deliberately not in it

Section 7's M2 row: a **job runner** that captures argv, exit code and stdout
hash; a **pinned-distribution registry**; and **`doctor`**. Repository: the
portal, not this one. Two invariants turn `ACTIVE (M2)` in Section 6.1 — I2
(the triple travels with the number, enforced at emit time in the renderer) and
I5 (run rows carry argv plus exit code). AC4's mismatch path must be provable.

Named as out of scope so it cannot be skipped silently: no database, no HTTP
API, no auth (M3); no policies or monitor (M5); no change to any file under
`data/` or to any compared artefact (NIF). The frozen chain gains nothing here.

### Stop point (reached 2026-11-09, satisfied 2026-11-10)

Section 13.5's stop at the Section 13.1 gate table was reached on 2026-11-09
and the owner approved it on 2026-11-10. The closure is Section 6 below. This
block remains the baseline the M2 gate was read against; it claims nothing
proven.

---

## 6. Milestone M2 closure — 2026-11-10 (PRD §13.5)

The owner approved the M2 stop point on 2026-11-10 with the instruction
"批准，请按照你的思路建议进行", delegating the six follow-ups in Section 9 of
the M2 report. The readings below are what M2 proved; the narrative, the ten
§13.2 sections, the liveness table, seven deviations and the disclosures are in
`~/laya-evidence/m2-2026-11-09/report-2026-11-09-m2-replay-engine.md`
(sha256 `e417d15e…`), beside `gate_table.log` (sha256 `5d01eb8f…`), the `gate/`
logs, `ci_42610673606_full.log` and the independent review
`review-2026-11-10-m2-independent.md` (sha256 `9fe2017a…`).

### Decisions taken (F1–F6)

| # | Decision | Value | Basis |
|---|---|---|---|
| F1 | Container-backed AC4/AC9 evidence | Accepted as **CI-only** for M2–M4; M3's container exit gate runs in CI. Provisioning an egress runner remains an option, not a condition | §5.11 AC4/AC9 need Docker and PyPI egress. This machine's containers return `[Errno 101]`, so the local container attempt is recorded as `refused` (rc 4, `exit_code: 1`) and never as a pass, and `doctor` reports `container-network fail`. CI `42610673606` supplies `argv[0]=docker`, AC4 rc 4 and two container `certified` replays. **No gate was waived**: the missing half is supplied elsewhere, not forgiven |
| F2 | `started_at` on the run row | **Add the field as M3's first source task**; §4.3 is not edited | §0.5 bars M1–M4 from changing files `verify` compares, and the PRD sits on that chain. A field on `RunRow` changes no invariant-carrying field. Deferred out of this session deliberately: the approved gate table is bound to `a1a1cc0` / `9d8e145` and no source edit may silently move that tip |
| F3 | Coverage floor | **None, on purpose, recorded as such.** Re-evaluate at M5 | §13.1 defines no coverage gate. A floor set at today's number is a ratchet on a suite M3 will reshape. This neither adds nor removes a guard: there was none to lower |
| F4 | §13.1 gate table and M2 | **Approved and closed 2026-11-10** | Owner's instruction above; §13.5 stop point; the independent reviewer had already judged the report a valid input to this approval |
| F5 | Independent review | **Confirmed**: 1 MUST FIX + 3 SHOULD FIX, all four CLOSED on the closure pass; the non-blocking `REPRO_RC` provenance was also supplied | `review-2026-11-10-m2-independent.md` (Closure verification) and `gate/export_present_repro_rc.txt`. The reviewer explicitly did not approve M2 and did not re-run the milestone; approval was the owner's, not the author's or reviewer's |
| F6 | The counted `docs/` deviation (D7) | **Accepted as M1 §4 did. No §7 freeze round** | The single path is this ledger, which is not a byte-compared artefact. `GATE_PUBLISHED_DATA_CHANGED=0`, `verify` still prints `re-derived 649 /649 values`, and the packet is built from `e9b0cf1`. §7's freeze round is triggered by a change that would *move* a published artefact; none moved here. This is a counted exception under §13.1, not an §0.5 NIF breach |

### Readings that close M2

| Reading | Value at 2026-11-10 | Where it was read |
|---|---|---|
| tips | portal gate `a1a1cc0`, closure `9d8e145` (two doc-only commits, pushed); frozen `230e40b`, both trees clean | `gate_table.log` header, `git log` |
| portal CI | `42610673606` and `42799336470` (the doc-only tip), both jobs success | `ci_42610673606_full.log`, `ci_42799336470_full.log`, `gate/ci_42799336470_result.json` |
| NIF | `GATE_NIF_RC=0`, `re-derived 649 /649 values` | `gate/nif.log` |
| published artefacts | `GATE_PUBLISHED_DATA_CHANGED=0`; `GATE_PUBLISHED_DATA_DOCS_CHANGED=1`, the one path is the ledger | `gate_table.log`, `gate/published_delta.txt` |
| portal suite | 11 files / 99 tests, `GATE_SUITE_RC=0`; `GATE_NEW_FILES_RC=0` with 50 dots across five files; ruff and compileall rc 0 | `gate/suite.log`, `gate/collect_only.log`, `gate/new_files.log` |
| plants | `total=31 runtime_landed=31 red=31 restored=31`, locally and in CI | `gate/plants.log`, `ci_42610673606_full.log` |
| leak test | `GATE_LEAK_HITS=7`, all seven the PRD's own phrase "no longer" | `gate/leak.txt` |
| AC4 | `mismatch` rc 4, both digests named, `611 /612` vs `612 /612`; CI's container copy rc 4 with `argv[0]=docker` | `gate/ac4*`, CI log |
| AC9 | two attempts, two rows, both `certified 612 /612`; CI two container `certified` | `gate/ac9*`, `gate/runs.jsonl` |
| AC10 | `not-run` rc 3, `argv: []`, `exit_code: null`; CI `SHAREABLE_REPLAY_RC=3` | `gate/ac10*`, CI log |
| container attempt | `refused` rc 4, `exit_code: 1` — never a pass | `gate/container_attempt.log` |
| run store | `GATE_RUNS_ROWS=5` for five attempts | `gate/runs.jsonl`, `gate/runs_list.log` |
| `doctor` | uv rc 0 all ok; container rc 3 `container-network fail`; no-docker rc 3 | `gate/doctor_*` |
| export lane | 146 tracked paths; `GATE_EXPORT_RC=0`, `1227 passed, 31 skipped in 539.23s`; corpus-absent `verify` rc 0 at `612 /612` | `gate/export_pytest.log`, `gate/export_verify.log` |
| liveness | I2 and I5 `ACTIVE (M2)`, I6 `ACTIVE (M1)`; I1/I3/I4 `UNPROVEN`; parity `N/A` (§6.3) | report §5 |

### Correction, not annotation (Section 8.3)

Five sentences were rewritten in place rather than left standing with a note
beneath them. Section 5's "Stop point" now says the stop was reached and
satisfied; it had said "stop for the owner's approval" in the present tense.
The M2 plan's export-lane row named only `AUTORATE_TRACKED_FILES`, which ran the
wrong lane (`b044191`); the same paragraph then repeated a miscount,
`1256 passed, 7 skipped`, which the re-executed lane disproved —
`1255 passed, 3 skipped in 684.16s` (`9d8e145`). The report's two occurrences
of that number were corrected the same way. Four gate tables were discarded,
not annotated: `gate_table_v1.log` (AC4 rc 125 before `--image`),
`gate_table_v4_corrupt.log` (a script rewritten while running produced a
spliced line), `gate_table_v5_prelane_fix.log` (corpus-present export lane;
`GATE_COLLECTED=11` was a file count wearing a test-count name) and
`gate_table_v6_docker_down.log` (the container row degraded to `not-run`, the
same reading as AC10, so it proved nothing). They remain in the evidence
directory because deleting them would hide the corrections.

### Deviation, counted

This commit changes one file under `docs/`, so
`git diff --name-only 230e40b..HEAD -- data/ docs/` returns one path (this
ledger) and `git diff --name-only 230e40b..HEAD -- data/` returns **0**.
`verify` still exits 0 at **649 /649**; the packet is built from `e9b0cf1`, so
no published artefact moved. Section 13.1's published-artefact row therefore
reads **1**, not 0 — the same counted exception M1's Section 4 registers and
the one F6 accepts.

### Stop point for the next session

Section 13.5's resume opener says "This session: <M1|M2|M3|M4|M5> only" and
"Do not carry the previous session's approval forward", and it requires the
Section 0.4 baseline to be **re-run** because the stored baseline is history.
This session therefore ends here: no M3 plan file, no portal source edit, no
`data/` change. M3 starts in a new session with B1–B5 re-captured and committed
to this ledger before its first source edit. Its Section 7 row is auth,
orgs/projects, F1 ingest, F2 certificate view, F3 slice view and the
provenance drawer; its gate is AC2, AC3, AC13, AC14 and a green parity job
(§6.3), with a read-only deployment first. F2's `started_at` is the first
source task.

This Section 6 commit was fast-forwarded onto **both** remote branches: `main`,
which is the default branch CI checks out, and `integration/f8-into-main`. The
first push reached only the latter, leaving `main` at `230e40b` — a state in
which the next session's B1 and the CI checkout would have read the still-open
M2 baseline. Both branches now carry the closure, and remote `HEAD` resolves to
it.

---

## 7. Milestone M3 opening — 2026-11-10 (PRD §0.4, §13.5)

The owner supplied the Section 13.5 resume opener verbatim with
`This session: M3 only` on 2026-11-10. Section 0.4 was re-run from scratch at
the current HEAD (`386dc9e`), not copied from Section 5: HEAD has moved by two
commits since the M2 opening, so those readings are history. Every exit code
below comes from its own command, captured by `echo "NAME_EXIT=$?"` immediately
after a redirect; logs are in `~/laya-evidence/m3-2026-11-10/gate/`.

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
integration/f8-into-main

$ git rev-parse --short HEAD
386dc9e
```

`B1A_EXIT=0` · `B1B_EXIT=0`. `git ls-remote` confirms remote `main`,
`integration/f8-into-main` and `HEAD` all resolve to `386dc9e`.

### B2 — working tree

```text
$ git status --short
```

Empty output, 0 lines. `B2_EXIT=0`, `B2_LINES=0`.

### B3 — the honesty gate

```text
$ uv run --frozen autorate verify --protocol protocol.json
protocol: protocol.json ce43f8e29cc1 (frozen 2026-10-17)
inventory source: recomputed from the corpus
disclosure: corpus present: inventory, digests and the snapshot all re-derived;
            the frozen protocol rubric was enforced
re-derived 649 /649 values
```

`B3_EXIT=0`. Lane **corpus present**; NIF reference denominator **649 /649**,
unchanged from the M2 opening.

### B3A — clean-clone lane, measured not inferred

The opener warns that a locally green tree has turned red in CI once, because
the frozen repo's CI reads an object database a shallow checkout lacks. So the
corpus-absent reading was re-executed rather than carried forward:

```text
$ git archive HEAD | tar -x -C <dir> ; git ls-files > <dir>/.tracked-files
M3_EXPORT_MANIFEST_LINES=146

$ env -u PYTHONPATH AUTORATE_FEISHU_ROOT=/nonexistent \
    AUTORATE_TRACKED_FILES=<dir>/.tracked-files \
    uv run --frozen autorate verify --protocol protocol.json
inventory source: committed data/inventory.md.json
disclosure: corpus absent: 9 SOURCE.json digests and the inventory snapshot are
            transcribed from the committed data/inventory.md.json, not recomputed
re-derived 612 /612 values
```

`M3_CLEAN_CLONE_VERIFY_RC=0`. This is an **additional** reading, not one of
Section 0.4's five; it establishes both lanes at this tip.

### B4 — command surface

```text
$ uv run --frozen autorate --help
snapshot, export-feishu, certify, severity, compare, gate, report, audit,
protocol, verify
```

`B4_EXIT=0`, 10 subcommands, unchanged. Section 7 puts all of M3 in the portal
repo; the frozen CLI surface gains nothing.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PUBLIC"}
```

`B5_EXIT=0`. Unchanged.

### M3 scope, and what is deliberately not in it

Section 7's M3 row (verbatim deliverable): **auth, orgs/projects, F1 ingest,
F2 certificate view, F3 slice view, provenance drawer**; gate **AC2, AC3, AC13,
AC14**, the frozen repo's committed artefacts rendering correctly end-to-end,
and the **parity job (§6.3) green**; rollback point **read-only deployment
first (no policies yet)**. Stack is fixed by §4.2: FastAPI + SQLAlchemy on
SQLite (PostgreSQL by one env var) + Alembic + Pydantic, one process, one port.

Two invariants turn `ACTIVE (M3)` in §6.1 — **I1** (no statistic computed in the
app tier; the static rule and the ORM-aggregate plant) and **I3** (a refusal
renders as a refusal, verbatim). I2 and I5 are `ACTIVE (M2)` and must not
regress; I6 stays `ACTIVE (M1)`; I4 stays `UNPROVEN (M4)`. §6.2 forbids any
skip/xfail/ignore/exemption to get green.

The first source task is the **follow-up** named F2 in Section 6 — add
`started_at` to the M2 `RunRow` — not functional feature F2 (the certificate
view). No invariant-carrying field changes.

Named out of scope so it cannot be skipped silently: M4's claim check, auditor
export and localization; M5's policies, monitor, in-browser verifier and the
`--format json` freeze round; any change to `data/` or to a file `verify`
byte-compares (§0.5 NIF); any endpoint that computes a bound (I1 / §3.4 NG7);
§0.2 carve-out (a) irreversible public exposure and (b) outbound messages to
named third parties.

### Session boundary, disclosed

Section 13.5 says `This session: … only` and `Do not carry the previous
session's approval forward`. From the executor's side, M2's closure (Section 6)
and this M3 opener arrived in the **same conversation window**, with a context
compaction between them; the formal one-milestone-per-session boundary is
therefore under tension. It is handled by substance, not by silence: this pass
does M3 only; **M2's approval is not carried forward** (the Section 13.1 gate
table needs a fresh owner approval for M3); Section 0.4 was re-run rather than
copied; this ledger block is committed before any source edit; and the pass
stops at the Section 13.1 gate table. If the owner judges the formal boundary
binding, the correct remedy is to refuse this milestone's gate table and reopen
M3 in a fresh window, not to edit this record.

### Stop point

Section 13.5: stop for the owner's approval at the Section 13.1 gate table,
with the Section 13.2 report and liveness table. This block is the baseline M3
will be read against; it claims nothing proven.
