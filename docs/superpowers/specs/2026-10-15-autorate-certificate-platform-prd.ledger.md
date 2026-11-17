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

---

## 8. Milestone M3 closure — 2026-11-11 (PRD §13.5)

The owner approved the M3 stop point on 2026-11-11 with the instruction
"全部授权批准，我都听你的，请按照你的思路建议进行", delegating the seven
follow-ups in Section 9 of the M3 report. The readings below are what M3
proved; the narrative, the ten §13.2 sections, the liveness table, sixteen
deviations, three independent reviews and the disclosures are in
`~/laya-evidence/m3-2026-11-10/report-2026-11-10-m3-portal-core.md`
(sha256 `6b5caaea…`), beside `gate_table.log` (sha256 `41f5a2c8…`), the `gate/`
logs, `m3_gate_run.sh` (sha256 `25e30882…`) and `ci-43016752565.json`
(sha256 `46c98068…`). The report was not edited after the approval; the sha
above is the one the owner approved.

### Decisions taken (F1–F7)

| # | Decision | Value | Basis |
|---|---|---|---|
| F1 | The §4.4 endpoints M3 did not build (D1) | **Accepted as written**: M3 ships the subset the report names; runs, policies, claims and exports stay with M4/M5 | §7 assigns claim check and audit export to M4 and policies/monitor to M5. No endpoint was invented ahead of its milestone, and none was silently dropped: the report lists the subset |
| F2 | D2–D5, the schema and F1 readings | **Accepted as permanent** | D2 widens `membership.role` to the enum §4.5's matrix needs; D3's derived packet id prevents one tenant's ingest blocking another's; D4's digest is a hash, never a statistic; D5's verbatim-duplicate rule is the only one that does not refuse the frozen repository's own records artefact |
| F3 | Coverage floor (D10) | **None, on purpose, recorded as such.** Re-evaluate at M5 | §13.1 defines no coverage gate. A floor at today's 181 is a ratchet on a suite M4 will reshape. There was no guard to lower |
| F4 | §13.1 gate table and M3 | **Approved and closed 2026-11-11** | Owner's instruction above; §13.5 stop point; the third review returned no MUST FIX, and the gate rows — not an aggregate rc — are the verdict (D14) |
| F5 | The three independent reviews | **Accepted**: 4 MUST/6 SHOULD/2 NIT, then 10 findings (5 MUST), then MUST 0/SHOULD 4/NIT 2 with 86 claims checked; every named finding closed, the last six in the report's prose | Report §§11–13. No reviewer approved the milestone and none re-ran it; approval is the owner's, not the author's or a reviewer's |
| F6 | A per-group bound exists only in tests | **Accepted with the limitation named**: `data/slices_language.json` refuses all four groups, so the bound-rendering path is exercised by tests; the refusal path is exercised end-to-end over HTTP | The frozen tree publishes no feasible group bound. The first artefact that publishes one exercises the rendering path; nothing claims it happened here |
| F7 | D9, D13, D14, D15, D16 | **Accepted as written** | Each names its section and its reason: both published slice shapes and where the artefact is found; the group's own budget; a gate table with no aggregate rc; the companion panel built from published rows; the pinned denominator as a second check |

D6–D8, D11 and D12 are accepted under the same instruction; F7 names only the
five the report put to the owner. D12's disclosure is closed by this approval:
the M2 closure and the M3 opener shared one conversation window, the opener said
so before any source edit, and the substance was kept — baseline re-run, ledger
committed before source edits, a fresh approval at the gate.

### Readings that close M3

| Reading | Value at 2026-11-11 | Where it was read |
|---|---|---|
| tips | portal gate `d0400b4`, frozen `51e1294`; both trees clean; report-only review fixes moved neither tip | `gate_table.log` header, `git status` |
| portal CI | `43016752565`, three jobs success: `suite / plants / lint`, `frozen packet / AC1 / AC9 / AC10 / I6`, `parity 6.3 / committed artefacts render byte-equal` | `ci-43016752565.json`, `ci-43016752565.log` |
| NIF | `GATE_NIF_RC=0`, `re-derived 649 /649 values` | `gate/nif.log` |
| published artefacts | `GATE_PUBLISHED_DATA_CHANGED=0`; at the gate one `docs/` path, this ledger's opening | `gate_table.log`, `gate/published_delta.txt` |
| portal suite | 19 files / 181 tests, rc 0; the eight new files 76 passed; ruff and compileall rc 0 | `gate/suite.log`, `gate/collect_only.log`, `gate/new_files.log` |
| plants | `total=40 runtime_landed=40 red=40 restored=40 leftover_markers=[]`; CI reports the same total | `gate/plants.log`, CI log |
| leak test | `GATE_LEAK_HITS=7`, all seven the PRD's own "no longer" | `gate/leak.txt` |
| AC2 / AC3 / AC13 / AC14 | one `1 passed` each, rc 0 | `gate/ac2.log` … `gate/ac14.log` |
| F3 over HTTP | `GATE_F3_HTTP_RC=0`: four refusal rows, four denominators, two panels, no `no_slice_evidence`, the published correction printed | `gate/f3_http.log` |
| parity (§6.3) | 8 fixtures, 7 compared field by field, 1 rendered from its published shape; `PARITY SLICES=… rows=4 refusals=4`; published, quoted and live `612 /612` | `gate/parity.log` |
| `doctor` | uv rc 0, all required checks ok; container rc 3, `docker fail`, `container-network not-required` | `gate/doctor_uv.log`, `gate/doctor_container.log` |
| export lane | 146 tracked paths; `1227 passed, 31 skipped in 660.61s`; corpus-absent `verify` rc 0 at `612 /612` | `gate/export_pytest.log`, `gate/export_verify.log` |
| container (CI) | `byte-identical: yes`; `state: certified`, `argv[0] == "docker"`, `exit_code: 0`; 2 attempts, 2 certified rows; `AC4_MISMATCH_RC=4`, `SHAREABLE_REPLAY_RC=3` | `ci-43016752565.log` |
| liveness | I1 and I3 `ACTIVE (M3)`; I2 and I5 `ACTIVE (M2)`; I6 `ACTIVE (M1)`; I4 `UNPROVEN (M4)`, its §6.2 plant named and not counted among the 40 | report §5 |
| reviews | three read-only; the last checked 86 claims and returned MUST 0 / SHOULD 4 / NIT 2, all six closed in prose | report §§11–13 |
| report | 551 lines, sha256 `6b5caaea…`; `shasum -a 256 -c report.sha256` verifies | `report.sha256` |

### Correction, not annotation (Section 8.3)

The corrections a reader of this ledger needs are these; each replaced the
sentence or control it corrected rather than leaving a note beneath it.

The F1 tamper control was replaced: an 8-byte replacement for a certificate
made the manifest's byte-count branch refuse first, so the sha256 check could
not fail. A one-byte flip of the same length is now the control, and the
refusal reason is pinned. D13 was rewritten twice — first because only the
denominator was called per group while the artefact publishes `alpha`, `beta`
and `delta` too, then because "after correction" misdescribed the values: the
per-group `beta` is 0.05, and only `run.corrected_*` is 0.0125. Its final
reading is the group's own budget, with the correction displayed and never
applied. Parity's "8 artefacts byte-equal" became 7 compared field by field
plus 1 rendered from its published shape, and the expected denominator is read
from the frozen README with `PINNED_REDERIVED` disclosed as a second check
(D16). `doctor.py`'s three duplicated definitions were removed. The gate script
stopped passing a second `-q` (`-o addopts= -q`), captured
`GATE_PUBLISHED_RC`, and carries no aggregate rc (D14). On the final pass the
runs 1–3 script hashes were relabelled **recorded readings** after the claimed
run-3 derivation failed to reproduce; only run 4's is checkable on disk
(report §13, S4). §5's I4 row was restored to §6.1's cross-freeze rule with
`UNPROVEN (M4)`, and §3's row 12 `rc` was marked as the CI job's success rather
than a code this machine captured.

Nothing above was closed with a skip, an xfail, an ignore or an exemption. The
suite went 172 → 177 → 181 and the plants 38 → 40 because the reviews found
behaviour that had no control on it.

### Deviation, counted

Since `386dc9e`, `git diff --name-only 386dc9e..HEAD -- data/ docs/` returns one
path, this ledger — the M3 opening (`51e1294`) and this closure both touch it —
and `-- data/` returns **0**. `verify` still exits 0 at **649 /649**; the packet
is built from `e9b0cf1`, so no published artefact moved. Section 13.1's
published-artefact row therefore still reads **1** at the closure: later commits
touch this same path rather than adding one. `verify` does not compare this
file.

### Stop point for the next session

Section 7's M4 row is F4 claim check, F5 audit export, badge-as-shareable and
the localization pass; its gate is AC5, AC6, AC7, AC8, AC11 and a P1 and a P2
walkthrough completed with an external reader; its rollback point is that
F4/F5 are additive views over M3's data. The external-reader walkthrough is the
long-lead item and needs a person outside this loop: the owner should name them
before M4's gate, not at it.

Recorded 2026-11-12: the owner states that **no external reader is named yet**
("目前还没有外部读者"). The P1/P2 walkthrough is therefore an open gate item,
not a formality to be filled in at the end. It cannot be satisfied by the
author, by any of the three reviewers, or by a CI job; M4 must not report its
gate as complete while the reader is unnamed. Naming one is the owner's act and
this ledger records it when it happens. This paragraph is a ledger-only commit:
`git diff --name-only 386dc9e..HEAD -- docs/` still returns one path (this file)
and `-- data/` still returns **0**, so no published artefact moved and `verify`
is unaffected.

M4 starts in a new session with B1–B5 re-captured at the new tip and committed
to this ledger before its first source edit. This session opens no M4 plan and
edits no source. The report above is frozen at the sha the owner approved.

This Section 8 commit is pushed to **both** remote branches, `main` and
`integration/f8-into-main`, so the next session's B1 and the CI checkout read
the closed milestone rather than the open one.

---

## 9. Milestone M4 opening — 2026-11-12 (PRD §0.4, §13.5)

The owner supplied the Section 13.5 resume opener with `This session: M4 only`
on 2026-11-12. Section 0.4 was re-run from scratch at the current HEAD
(`fd06bf9`), not copied from Section 7: HEAD has moved since the M3 opening, so
those readings are history, not ground truth. Every exit code below comes from
its own command, captured by `echo "NAME_EXIT=$?"` immediately after a redirect;
logs are in `~/laya-evidence/m4-2026-11-12/gate/`.

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
integration/f8-into-main

$ git rev-parse --short HEAD
fd06bf9
```

`B1A_EXIT=0` · `B1B_EXIT=0`. `git ls-remote origin 'refs/heads/*'` confirms
remote `main`, `integration/f8-into-main` and `HEAD` all resolve to `fd06bf9`.

### B2 — working tree

```text
$ git status --short
```

Empty output, 0 lines. `B2_EXIT=0`, `B2_LINES=0`. `git worktree list` shows no
other worktree holding a branch that this session will edit.

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

`B3_EXIT=0`. Lane **corpus present**; NIF reference denominator **649 /649**,
unchanged from the M3 opening. Section 0.4's hard rule is satisfied: the tree
reproduces its own published numbers.

The two labels the product displays are read off the tool's own output, not
inferred:

| Label | Value at this baseline | Where it comes from |
|---|---|---|
| lane | **`corpus present`** | the `disclosure:` line, verbatim |
| denominator | **`649 /649`** | the `re-derived N /M values` line, verbatim |
| freeze | `protocol.json ce43f8e29cc1 (frozen 2026-10-17)` | `protocol:` line |

### B3A — clean-clone lane, re-executed as the opener requires

The opener warns that a locally green tree has turned red in CI once, because
the frozen repo's CI reads an object database a shallow checkout lacks. The
corpus-absent reading was therefore re-executed rather than carried forward:

```text
$ git archive HEAD | tar -x -C <dir> ; git ls-files > <dir>/.tracked-files
M4_EXPORT_MANIFEST_LINES=146

$ env -u PYTHONPATH AUTORATE_FEISHU_ROOT=/nonexistent \
    AUTORATE_TRACKED_FILES=<dir>/.tracked-files \
    uv run --frozen autorate verify --protocol protocol.json
inventory source: committed data/inventory.md.json
disclosure: corpus absent: 9 `SOURCE.json` digests and the inventory snapshot are transcribed from the committed data/inventory.md.json, not recomputed
re-derived 612 /612 values
```

`M4_CLEAN_CLONE_VERIFY_RC=0`. This is an **additional** reading, not one of
Section 0.4's five; it establishes both lanes at this tip.

### B4 — command surface

```text
$ uv run --frozen autorate --help
snapshot, export-feishu, certify, severity, compare, gate, report, audit,
protocol, verify
```

`B4_EXIT=0`, 10 subcommands, unchanged. Section 7 puts all of M4 in the portal
repo; the frozen CLI surface gains nothing.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PUBLIC"}
```

`B5_EXIT=0`. Unchanged since the M3 opening.

### M4 scope, and what is deliberately not in it

Section 7's M4 row (verbatim deliverable): **F4 claim check, F5 audit export,
badge-as-shareable, localization pass** (Section 11's `Localization` row; the
second language is fixed by A6 as Simplified Chinese, `zh-Hans`). Gate:
**AC5, AC6, AC7, AC8, AC11; a P1 and a P2 walkthrough completed with an
external reader**. Rollback point: **F4/F5 are additive views over M3's data**.
Repository: the portal, not this one.

In §6.1 **I4** (no cross-freeze aggregation without a boundary) turns
`ACTIVE (M4)`: two packets at different `protocol_digest` values must not share
a trend axis unless the boundary is drawn and both digests are named. I1, I3
(`ACTIVE (M3)`), I2, I5 (`ACTIVE (M2)`) and I6 (`ACTIVE (M1)`) must not
regress. §6.2 forbids any skip/xfail/ignore/exemption to get green.

Named out of scope so it cannot be skipped silently: M5's policies, monitor,
in-browser verifier and the `--format json` freeze round; any change to `data/`
or to a file `verify` byte-compares (§0.5 NIF); any endpoint that computes a
bound (I1 / §3.4 NG7); §0.2 carve-out (a) irreversible public exposure and
(b) outbound messages to named third parties. M3's approval is **not** carried
forward: the Section 13.1 gate table needs a fresh owner approval for M4.

### Open gate row, recorded at the opening

The owner's opener states that **no external reader is named** and that the
P1/P2 walkthrough is "not yours to close". Section 8 records the same fact,
dated 2026-11-12. It is carried as an **open row** in the Section 13.1 gate
table: it cannot be satisfied by the author, by any reviewer, or by CI, and no
substitute or softened reading is proposed. It blocks **approval**, not the
work: this session builds M4 to the gate and stops there. Naming an external
reader is the owner's act; this ledger records it when it happens.

### Deviation, counted

This commit changes one file under `docs/` (this ledger), so
`git diff --name-only fd06bf9..HEAD -- data/ docs/` returns one path and
`-- data/` returns **0**. `verify` still exits 0 at **649 /649**; no published
artefact moved. Section 13.1's published-artefact row is counted as 1 here,
not described as zero — the same single path M1, M2 and M3 registered.

### Stop point

Section 13.5: stop for the owner's approval at the Section 13.1 gate table,
with the Section 13.2 report and liveness table. This block is the baseline M4
will be read against; it claims nothing proven.

## 9A. Owner waiver — P1/P2 external reader gate row, 2026-11-15

The Section 9 opening carried one row OPEN: the P1/P2 walkthrough "with an
external reader". Section 8 recorded the fact on 2026-11-12; the Section 13.1
gate table recorded it again at `318f80d` (`gate/p1p2_waiver.log` quotes the
line). On 2026-11-15 the owner stated that no reader exists outside the
developer, and then authorised the coding agent to execute the walkthrough in
that role. The exact words are quoted in `gate/p1p2_waiver.log` (W1) and are
not paraphrased here.

What the owner waived is one clause: that the walkthrough be completed and
signed by an external reader. What was not waived is that a walkthrough be
executed and recorded, that the record say in its own text that the executor
is neither external nor independent, and that no PASS be claimed for a waived
criterion. The row's disposition is therefore **waived-by-owner**, not
satisfied. The earlier table is not rewritten: it still prints OPEN, because
that is what it printed at `972c107`, and a log is not rewritten.

The record is `walkthrough/results-2026-11-15/P1-P2-sheet.md`: twelve rows,
verbatim screen text, six screenshots, one bundle dump. Its executor is an AI
agent — not a person, not outside this loop, and not independent: it wrote part
of the reader-facing text and knew the expected verdicts. It found six defects
(F1–F6, listed in `report-addendum-2026-11-15-p1p2-waiver.md` §A4); two of
them, F1 and F2, mean a reader cannot tell what the one `certified` row
actually publishes. That is the kind of thing an independent reader was
supposed to catch, and it is recorded here as the cost of the waiver, not as a
result the waiver produced.

Deviation, counted the same way M1–M3 counted theirs: this commit changes one
path under `docs/` (this ledger), `git diff --name-only <base>..HEAD -- data/`
returns 0, and no published artefact moves. It is D12 in the Section 13.2
report, recorded in an addendum so the report's own bytes stay at
`f1e87ac9…`. The Section 13.1 table is re-run at this commit rather than
carried forward, because the frozen tip moved; those readings live in the
evidence directory and the table names its own files.

Residual risk, stated once: no independent reader has seen this build, so the
author's blind spots are unmeasured. The waiver accepts that risk; it does not
measure it. If a real external reader appears later, the same handout can be
run again and this waiver superseded.

M4 is **not** approved by this entry. Approval is still the owner's act at the
Section 13.1 gate table.

---

## 10. Milestone M4 closure — 2026-11-16 (PRD §13.5)

The owner approved the M4 stop point on 2026-11-15 at 23:18 CST (15:18Z) with the
instruction **"批准，授权，请按照你的思路建议进行"**, delegating the D1–D12 rulings recorded in
`gate/m4_approval.log` (sha256 `ffec5c447da593d7eba165ad5a505aa01a46d9052f7f6e2820aeb92070ec2a56`).
The readings below are what M4 proved; the narrative, the ten §13.2 sections, the liveness
table, twelve deviations and three independent reviews are in
`~/laya-evidence/m4-2026-11-12/report-2026-11-13-m4-audience-features.md` (sha256
`f1e87ac9a7bf34504f73d49fd85864d8ad919b371dbce7d206d9c67b1b5ecdd4`), beside
`gate/gate_table.6a18500.log` (sha256
`49f8d1806b2f017bb5e919fa71de6dae4f9b1531f0977bbffec163081339a622`), the `gate/` logs,
`gate/p1p2_waiver.log` (sha256
`d4fc8756ba54210f410cb7d94a46d8ca7d8777beaf98cd07d76c7dfff7bf62b2`), the addendum
`report-addendum-2026-11-15-p1p2-waiver.md` (sha256 `e199a4ec…`) and
`walkthrough/results-2026-11-15/P1-P2-sheet.md`. The report was not edited after the
approval; the sha above is the one the owner approved. The gate table was not edited after
its run (`TABLE_EDITED_AFTER_RUN=no`), and the approval names that table's sha rather than a
summary of it.

**Row 13 of the approved table is waived-by-owner, not satisfied.** The table prints
`GATE_P1_P2_WALKTHROUGH=WAIVED-BY-OWNER … NOT a PASS`; the approval log records
`ROW_13_DISPOSITION=waived-by-owner (the reader clause was waived, not satisfied)` and
`EXTERNAL_READER_SATISFIED=no`. No external reader has seen this build. The substitute
walkthrough was executed by an AI agent that wrote part of the reader-facing text and knew
the expected verdicts, so it is neither external nor independent, and its six findings are
what that executor noticed rather than what a reader would have noticed. The approval
accepts that residual risk; it does not measure it, and no PASS is claimed for the row.

### Decisions taken (D1–D12)

| # | Decision | Value | Basis |
|---|---|---|---|
| D1 | AC5 is demonstrated on a **synthetic** certificate | **Accepted as written** | No certificate in `data/cert_*.json` is `feasible=true` with a non-null `autorate`; F4 rule 4 forbids printing an unpublished point estimate, so the `bounded_refutes` branch needs a labelled fixture. Against the real packet every claim is `cannot_be_bounded`, and a test asserts it |
| D2 | `cannot_be_bounded` names no required sample size | **Accepted** | `data/g1_feasibility.json` publishes no `n_min`/`required_n`; the code reads the missing pool inputs and the size ladder it does publish, then says the artefact states no required sample. Inventing one is the failure F4 rule 3 names |
| D3 | The audit lane is quoted as Markdown, never parsed into a bound | **Accepted** | `docs/AUDIT.md` is the lane's only artefact; five exact sentences are read from the packet's bytes and carried as labels, so a packet that lacks them says so |
| D4 | The localization artifact is the rendered HTML pair, not PNG | **Accepted** | HTML is byte-comparable and diffable; a PNG's pixels follow the runner's font stack and would make the gate unstable. A PNG requirement, if wanted, is an M5 item |
| D5 | axe pass and manual keyboard pass | **Settled on the walkthrough side**: the keyboard pass ran (13 controls, all outline solid, recorded in the 12-row table); axe remains `not-run` and is recorded as `not-run`, never as a pass | Report D5; `walkthrough/results-2026-11-15/P1-P2-sheet.md`. One of the two was done, so the conditional acceptance closes only that half |
| D6 | The gate table has no aggregate exit code | **Accepted** | The rows are the verdict; an aggregate rc lets a failing row hide behind a wrapper's status, which is the failure M3's first run demonstrated |
| D7 | The local container reading is a named `not-run`; the clean-machine row is CI's | **Accepted** | This machine has no Docker daemon (`doctor --backend container` rc 3). CI run `43546775573`'s `headSha` equals the portal tip, so the row is witnessed elsewhere rather than waived here |
| D8 | AC7's recorded-mismatch trigger was corrected twice | **Accepted** | The `db.Run` query at `97736d8` could not fire (no product path inserts that row, and a mismatch's replay `exit_code` is 0); the row is now the run-store JSONL observation. The table at `1148056` is archived and not cited |
| D9 | The frozen repo gained one ledger-only commit, `972c107` | **Accepted** | §0.4/§13.5 require the baseline committed before source edits; `-- data/` returns 0 paths and `verify` still reads `649 /649`. The published-artefact row is counted as 1, not described as zero |
| D10 | Badge bytes are buildable only with `READ_CERTIFICATES` | **Accepted** | The build reads a project's packet context; the artefact it returns carries only the triple, the denominator, the closed-vocabulary state and `records_rows: 0`. Public shareability belongs to the artefact, not to an unauthenticated endpoint |
| D11 | §5's `generic_aap` versus §4.3's `aap` | **`aap` kept**; the PRD wording change is deferred to the next revision of the PRD, not made here | The PRD sits on the chain `verify` compares, so M4 may not edit it; an alias would need a heading mapping invented for it. A caller following §5 gets a named 422 rather than a silently different bundle |
| D12 | The P1/P2 reader waiver | **Accepted as recorded** (Section 9A, `gate/p1p2_waiver.log` W1) | The waiver removes the reader blocker; it does not approve M4, does not close W-F1–W-F6 and does not convert row 13 into a PASS |

R-F4–R-F8 are **deferred to the M5 backlog**, and this approval closes none of them: AC5
against a real feasible certificate, a machine-readable form of the audit lane, the PNG
question, the coverage floor, and `project_id` on run rows. The walkthrough's defects are
split: **W-F1 and W-F2 are M5 entry conditions** (see the stop point); W-F3–W-F6 are M5
backlog. The report's follow-ups and the walkthrough's defects are different lists — R-F*
and W-F* in the approval log — and are not interchangeable.

### Readings that close M4

| Reading | Value at 2026-11-16 | Where it was read |
|---|---|---|
| approved tips | portal `318f80d`, frozen `6a18500`; both trees clean | gate table header; portal `git status` 0 lines, frozen B2 0 lines |
| closure baseline | B1 `integration/f8-into-main` / `6a18500`, remote `main`, `integration/f8-into-main` and `HEAD` all `6a18500`; B2 0 lines; B4 10 subcommands; B5 `{"stargazerCount":1,"visibility":"PUBLIC"}` | `gate/closeout-6a18500/b1a.log` … `b5.log`, each exit in its own `*.exit` |
| B3 | rc 0, lane **corpus present**, `re-derived 649 /649 values`, protocol `ce43f8e29cc1` frozen 2026-10-17 | `gate/closeout-6a18500/b3.log` |
| B3A | rc 0, lane **corpus absent**, `inventory source: committed data/inventory.md.json`, `re-derived 612 /612 values`, 146 manifest lines | `gate/closeout-6a18500/b3a.log`, `b3a_manifest.txt` |
| portal CI | run `43546775573` headSha `318f80d`, three jobs success: `suite / plants / lint`, `frozen packet / AC1 / AC9 / AC10 / I6`, `parity 6.3 / committed artefacts render byte-equal` | gate table row 12; `gate/ci_runs.json` |
| frozen repo CI at the approved tip | run `43726509623` headSha `6a18500`, conclusion success: `offline`, `cross-libc-verify (macos-latest)`, `cross-libc-verify (ubuntu-latest)` | `gh run view 43726509623`; `gate/p1p2_waiver.log` REVISION 2; addendum A8 |
| NIF | `GATE_NIF_RC=0`, `re-derived 649 /649 values` | `gate_table.6a18500.log` row 1 |
| published artefacts | `GATE_PUBLISHED_DATA_CHANGED=0`; `GATE_PUBLISHED_DATA_DOCS_CHANGED=1`, the one path this ledger | gate table; `gate/published_delta.txt` |
| portal suite | 28 files / 259 tests, `GATE_SUITE_RC=0`; the nine new M4 files 78 passed; ruff, compileall and yaml/toml rc 0 | `gate/suite.log`, `gate/new_files.log` |
| plants | `total=55 runtime_landed=55 red=55 restored=55 leftover_markers=[]` | `gate/plants.log`; CI run `43546775573` |
| leak test | `GATE_LEAK_HITS=7`, all seven the PRD's own phrase `no longer` | `gate/leak.txt` |
| AC5 / AC6 / AC7 / AC7 over HTTP / AC8 / AC11 | one named reading each, rc 0 | `gate/ac5.log` … `gate/ac11.log` |
| I4 | `ACTIVE (M4)`; two digests without a boundary draw no trend, with one both are named | report §5; `gate/plants.log` |
| parity (§6.3) | 11 fixtures, 7 compared field by field, 1 rendered from its published shape; `612 /612` published, quoted and live; `PARITY VERIFY_RC=0` | `gate/parity.log` |
| `doctor` | uv rc 0, required checks all ok; container rc 3, `docker` failed — a named `not-run` | `gate/rebuild-6a18500/doctor_uv.log`, `doctor_container.log` |
| export lane | 146 tracked paths; `1227 passed, 31 skipped in 865.34s`; corpus-absent `verify` rc 0 at `612 /612` | `gate/export_pytest.log`, `gate/export_verify.log` |
| walkthrough | waived-by-owner; 12 rows, 6 screenshots, 1 bundle dump; executor AI, not human, not external, independence none | `walkthrough/results-2026-11-15/P1-P2-sheet.md`, `gate/p1p2_waiver.log` |
| reviews | three read-only: 1 BLOCKING + 3 non-blocking; 2 BLOCKING; then 1 BLOCKING + 2 MAJOR + 6 MINOR, re-review `APPROVE` | report §§11–13, `review-3.md` |
| report | 515 lines, sha256 `f1e87ac9…`; unchanged since approval | `report-2026-11-13-m4-audience-features.md` |

### Correction, not annotation (Section 8.3)

Six corrections replaced the sentence or the control they corrected rather than leaving a
note beneath it.

AC7's recorded-mismatch trigger was corrected twice. It was first keyed to a byte mismatch
against the manifest, then at `97736d8` to a `db.Run` row — a row no product path inserts,
whose `exit_code` on a mismatch is the replay process's own 0 — and finally at `05a2423` to
the run-store JSONL row with `state == "mismatch"`. The gate table run at `1148056` is
archived as `gate/gate_table.at-1148056.log` and is not cited; the table at `97736d8` is
superseded by the one this section closes.

F4's comparator was narrowed. At `97736d8` any published field could be compared with the
certified `autorate`, so a claim on `bound`, `n_cal` or `alpha` would have been answered with
a bounded verdict about a different quantity. `claims.RATE_FIELD` now admits only
`autorate`, and a claim whose unit differs from the certified unit — or a certificate that
states none — is `cannot_be_bounded` with no number.

The deciding row was replaced. `latest_row` took the last line whatever its state, so a later
`not-run` or `refused` row lifted a recorded mismatch and the export proceeded; AC7 was
bypassable by one ordinary command. `engine.deciding_row` returns the last row that
**observed** the source (`certified` or `mismatch`); `not-run` and `refused` neither block nor
clear.

A pin-matching guard was added during the third review's re-review and then removed at
`318f80d`: matching the row's wheel against the packet's pin let a one-field edit to
`distribution.sha256` re-seal a blocked packet and export 200. The removal is the correction;
the test asserts the fail-closed reading the reviewer asked for, and the removal narrows the
reviewed surface rather than extending it.

CI's five acceptance-criterion lines ended with a literal `echo "M4_AC*_RC=0"` — a constant
wearing an exit code's name. At `97736d8` each command appends its own rc to a file and a
harness asserts the five names and values before the step exits.

The walkthrough's own record carried a wrong reading into three reader-facing documents:
"seven certificates, all refusal". `README.md`'s table, `smoke-test.md` and
`reader-script.md`'s owner table all said it, and it is false: the frozen packet publishes
six `feasible=false` / `empty_feasible_set` rows and one `certified` row (`severity_ordinal`,
`synthetic-ordinal`, `bound=0.045180414995`, `n_cal=n_eval=600`, no `autorate` key). The
accurate fixed fact is "no certificate publishes `autorate`", not "no certificate is
certified"; `smoke-test.md` records the correction as C1 and the reader-facing text was
rewritten.

Nothing above was closed with a skip, an xfail, an ignore or an exemption. The suite went
181 → 259 and the plants 40 → 55 because the reviews found guards that could not fire, not
because a threshold was moved.

### Deviation, counted

This commit changes one file under `docs/`, so
`git diff --name-only fd06bf9..HEAD -- data/ docs/` returns one path (this ledger, now
carrying the M4 opening `972c107`, the waiver `6a18500` and this closure) and
`git diff --name-only fd06bf9..HEAD -- data/` returns **0**. `verify` still exits 0 at
**649 /649**; no published artefact moved. Section 13.1's published-artefact row therefore
reads **1**, not 0 — the same counted exception M1, M2 and M3 registered, and the one D9
accepts. `verify` does not compare this file.

### Stop point for the next session

Section 7's M5 row is **F6** monitor and drift, **F7** policies and enforcement, **F9** the
self-contained HTML viewer and share link, and **F10** administration; the Pyodide certificate
self-checker reusing the *published* `verify` module; and the frozen repo's `--format json`
as **one freeze round**, approved before it is run. Its gate is **AC12**, the browser
checker's verdict equalling the container replay's for the same packet, and the freeze round
passing with denominators unchanged and a recorded justification for adding a compared field
or not. Rollback point: the browser checker must degrade to "replay required" if the wheel
cannot be fetched.

M5 inherits two **entry conditions**, not backlog items: **W-F1** and **W-F2**. The one
`certified` row's detail renders `bound: not published by this certificate` while the
handout and the artefact say that row publishes a different quantity, `bound`; and the detail
group panel shows `n_cal=1487` for every row (`jev` publishes 95, `severity_ordinal` 600)
without naming its dataset. Together they mean a reader cannot tell what the one certified
row actually publishes, which is the claim M4 exists to make readable. They are fixed before
M5 is called done, not after.

The rest of the walkthrough's findings are M5 backlog: W-F3 (zh-Hans translates buttons and
header cells only; verdict and detail body remain English), W-F4 (`known_limits[1]` says no
certificate exists, contradicting the certified row), W-F5 (`gaps: []` is ambiguous between
"no gap" and "not stated") and W-F6 (the 14th Tab lands on `BODY` with `outline: none`).
R-F4–R-F8 are also deferred: AC5 against a real feasible certificate, a machine-readable
audit lane, the PNG question, the coverage floor, and `project_id` on run rows.

M5 starts in a new session with Section 0.4 re-run at the new tip and committed here before
its first source edit. **M4's approval is not carried forward**: §13.5 requires M5's own
baseline and its own approval at the Section 13.1 gate table. This session opens no M5 plan
and edits no portal source. The report stays frozen at the sha the owner approved.

M4 now consists of the four audience features at portal `318f80d`; the gate rows AC5, AC6,
AC7, AC8 and AC11 plus parity, NIF and the suite green at frozen `6a18500`; one row
waived-by-owner; twelve recorded deviations; three read-only reviews; a report at the
approved sha; and the two walkthrough findings M5 must fix before it closes.

One reading is taken **after** this push — the frozen repo's CI on the commit that carries
this section — and is appended in the follow-up ledger commit that changes only this file,
together with whether `report.sha256` verifies. A file cannot contain the result of a run its
own push triggers, and writing a predicted run id here would be the summary that reads better
than the record.

This Section 10 commit is pushed to **both** remote branches, `main` and
`integration/f8-into-main`, so the next session's B1 and the CI checkout read the closed
milestone rather than the open one.

### Closure reading taken after the push

The frozen repo's CI on the commit that carries Section 10 — `eddbfe4`, the parent of the
commit that adds this paragraph — is run **43800958117**, conclusion **success**, with
`offline`, `cross-libc-verify (macos-latest)` and `cross-libc-verify (ubuntu-latest)` all
completed success. It was read with `gh run view` after the push, not predicted, and it is
recorded here the way `gate/p1p2_waiver.log` REVISION 2 recorded run `43726509623`: as a
reading of a named commit, beside the table, not inside it.

This paragraph is the follow-up commit Section 10 promised. It changes only this ledger file,
adds no source or data path, and moves no published artefact. The run it records belongs to
its parent commit; this commit's own push triggers a further run, whose result cannot be
written into the file that would cause it — so the chain stops at this line, by construction
rather than by omission.

---

## 11. Milestone M5 opening — 2026-11-16 (PRD §0.4, §13.5)

The owner authorised this session with the two words **「授权M5」** on 2026-11-16, against the
Section 13.5 opener whose body reads `This session: M5 only (Section 7)`. Section 0.4 was
re-run from scratch at the current HEAD rather than copied from Section 10: HEAD has moved,
and the opener's own warning is that a stored baseline is history, not ground truth. Every
exit code below comes from its own command, written by `printf`/`echo` immediately after that
command's own redirect. Logs and their SHA-256s are in `~/laya-evidence/m5-2026-11-16/gate/`
(`baseline.sha256` covers `b1a.log b1b.log b2.log b3.log b3a.log b4.log b5.log`).

### B1 — identity

```text
$ git rev-parse --abbrev-ref HEAD
integration/f8-into-main

$ git rev-parse --short HEAD
f5eb3cd
```

`B1A_EXIT=0` · `B1B_EXIT=0`. `git ls-remote origin` resolves remote `main`,
`integration/f8-into-main` and `HEAD` all to `f5eb3cd39c00582edf67680311939a04b437e3cf`
(`B1_REMOTE_EXIT=0`). The locality that matters: the tree M5 will read is the tree the
remote reports, at the commit Section 10 closed M4 on.

### B2 — working tree

```text
$ git status --short
```

Empty output, 0 lines. `B2_EXIT=0`, `B2_LINES=0`. No other worktree holds a branch this
session will edit.

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

`B3_EXIT=0`, and `grep -c '^re-derived 649 /649 values$'` returns `1` with
`B3_RELINE_GREP_EXIT=0`. Lane **corpus present**; denominator **649 /649**, identical to the
M4 opening and to Section 10's closure reading. Section 0.4's hard rule is satisfied: the
tree reproduces its own published numbers, so M5 may be built on it.

| Label | Value at this baseline | Where it comes from |
|---|---|---|
| lane | **`corpus present`** | the `disclosure:` line, verbatim |
| denominator | **`649 /649`** | the `re-derived N /M values` line, verbatim |
| freeze | `protocol.json ce43f8e29cc1 (frozen 2026-10-17)` | `protocol:` line |

### B3A — clean-clone lane, re-executed rather than carried

The opener repeats the reason: the frozen repo's CI reads an object database a shallow
checkout lacks, which has already turned a locally green tree red once. Re-executed at this
tip:

```text
$ git archive HEAD | tar -x -C <dir> ; git ls-files > <dir>/.tracked-files
M5_EXPORT_MANIFEST_LINES=146

$ env -u PYTHONPATH AUTORATE_FEISHU_ROOT=/nonexistent \
    AUTORATE_TRACKED_FILES=<dir>/.tracked-files \
    uv run --frozen autorate verify --protocol protocol.json
inventory source: committed data/inventory.md.json
disclosure: corpus absent: 9 `SOURCE.json` digests and the inventory snapshot are transcribed from the committed data/inventory.md.json, not recomputed -- this run cannot see whether that snapshot went stale; the frozen protocol rubric was enforced
re-derived 612 /612 values
```

`M5_CLEAN_CLONE_VERIFY_RC=0`, 146 tracked paths. Both lanes hold at `f5eb3cd`. This is an
additional reading, not one of Section 0.4's five.

### B4 — command surface

```text
$ uv run --frozen autorate --help
snapshot, export-feishu, certify, severity, compare, gate, report, audit,
protocol, verify
```

`B4_EXIT=0`, 10 subcommands. The surface M5 will extend is this one: the freeze round adds a
flag to `verify`, not a subcommand, and the flag must not change any denominator.

### B5 — adoption blocker

```text
$ gh repo view --json visibility,stargazerCount
{"stargazerCount":1,"visibility":"PUBLIC"}
```

`B5_EXIT=0`. Unchanged since the M4 opening.

### M5 scope, and what is deliberately not in it

Section 7's M5 row, verbatim deliverable: **F6** monitor and drift, **F7** policies and
enforcement, **F9** self-contained HTML packet viewer and share link, **F10** administration;
the **Pyodide certificate self-checker** reusing the *published* `verify` module; and the
frozen repo's **`--format json`** as **one freeze round**. Repository: **portal + frozen repo**.
Gate: **AC12**; the browser checker's verdict equal to the container replay's for the same
packet; the freeze round passing with denominators **unchanged** and a **recorded
justification for adding a compared field or not**. Rollback point: the browser checker must
degrade to **"replay required"** if the wheel cannot be fetched.

The freeze round is authorised in **name and scope only**: `--format json` on `verify`, one
round, denominators unchanged unless the round is explicitly approved to change them. §0.5
NIF is not suspended for anything else — no other file `verify` compares, no other compared
field, no other published document. If the round turns out to require a second change to the
compared surface, that second change is a new request to the owner, not part of this
authorisation.

Two **entry conditions**, inherited from Section 10 and not backlog: **W-F1** — the one
`certified` row's detail renders `bound: not published by this certificate` while the handout
and the artefact say that row publishes `bound` — and **W-F2** — the detail group panel shows
`n_cal=1487` for every row (`jev` publishes 95, `severity_ordinal` 600) without naming its
dataset. Both are fixed before M5 is called done. Backlog carried into M5: W-F3–W-F6 and
R-F4–R-F8, as Section 10 lists them.

In §6.1, the six invariants are **carried, not inherited as proven**: at this opening every
row is `UNPROVEN at M5` until its plant is run in *this* milestone's CI, per §6.1's own rule
that a rule whose plant has not run in this milestone is `UNPROVEN` and may not be cited as
satisfied. I1 (M3), I2 (M2), I3 (M3), I4 (M4), I5 (M2) and I6 (M1) must not regress; the
liveness table the Section 13.2 report carries starts from this sentence, not from the
previous report's table. §6.2 still forbids any skip/xfail/ignore/exemption to get green.

Named out of scope so it cannot be skipped silently: §0.2 carve-outs **(a)** irreversible
public exposure and **(b)** outbound messages to named third parties; any endpoint that
computes a bound (I1 / §3.4 NG7); any change to `data/` or to a byte-compared published
document outside the one authorised freeze round; and any F8 distribution work (that is M0's
and is already recorded as unblocked/blocked there).

### Deviation, counted

This commit changes one file under `docs/` (this ledger). `git diff --name-only f5eb3cd..HEAD
-- data/` is read after the commit and returns **0**; `-- data/ docs/` returns **1**; `verify`
is then re-run on the committed tree and still exits 0 at **649 /649** — read, not assumed,
and recorded in the M5 evidence directory rather than asserted here. No published artefact
moves, and M4's approved report stays frozen at
`f1e87ac9a7bf34504f73d49fd85864d8ad919b371dbce7d206d9c67b1b5ecdd4`.

### Stop point

Section 13.5 restated for M5: baseline first (this section), ledger commit **before** the
first source edit, stop for the owner's approval at the Section 13.1 gate table with the
Section 13.2 report and liveness table. This block is the baseline M5 will be read against;
it claims nothing built and nothing proven. M4's approval is not carried forward.

---

## 12. Milestone M5 closeout — 2026-11-17 (gate table, report, stop point)

The Section 0.4 baseline in Section 11 was committed at `0db1fd8` before the first source
edit, as the opener required. M5 was then built in the portal (T1–T8, T10) and in the
frozen repo (T9), the Section 13.1 gate table was run at the final tips, and the Section
13.2 report was frozen to disk. Approval is the owner's act and is the one open row;
**M4's approval is not carried forward**.

### Implementation commits (read, not assumed)

Portal `autorate-portal`, `318f80d..21c5c9c`, ten commits: plan `1da8730`; W-F1/W-F2
`d0d4c02`; AC12 `8b848ec`; F6 `50eca97`; F7 `c2539a0`; F9 `4b773ac`; F10 `e6cad3f`;
T8 `eee869d`; the §6.2 plant retarget `f274389`; and the gate fix `21c5c9c`.
Frozen `autorate`, `f5eb3cd..1792bf1`, two commits: this ledger's opening `0db1fd8` and
the single authorised freeze round `1792bf1` (`verify --format json`, text byte-identical,
no compared field added). Both repos were pushed: `1792bf1` to frozen `main` and
`integration/f8-into-main`; `21c5c9c` to portal `main`. A first push attempt on 2026-11-16
failed with CONNECT 502 / HTTP2 framing (recorded in `gate/t9_push_*.log`); the retry on
2026-11-17 succeeded, with rc 0 captured per command.

### Gate table readings (Section 13.1)

Run at `PORTAL_TIP=f274389`, `FROZEN_TIP=1792bf1`; verbatim stdout in
`~/laya-evidence/m5-2026-11-16/gate/gate_run.stdout`, each rc captured from its own command.

| Gate | Reading | rc |
|---|---|---|
| Frozen non-interference | `re-derived 649 /649 values`, identical to B3 | 0 |
| Freeze round (M5 only) | JSON `re_derived="649 /649"`, `exit_code:0`; text byte-identical to baseline sha `b31e3412…` | 0 |
| Published-artefact untouched | `0` data paths, `1` docs path (the opening ledger) since `f5eb3cd`; T9 touched only `src/`, `tests/` | 0 |
| New-file coverage | `47 passed`, `47` collected (nine M5 test files) | 0 |
| Portal suite | `302 passed` in `36` files (after gate fix `303 passed`) | 0 |
| Frozen verify-focused tests | `99 passed` | 0 |
| Invariant plants | `total=55 runtime_landed=55 red=55 restored=55 leftover_markers=[]` | 0 |
| Corpus-absent lane | `1230 passed, 31 skipped`; `612 /612`; `147` tracked lines | 0 |
| Leak test | `7` hits, all adjudicated in the report's §7/§6 (D8), unchanged from M4 | 0 |
| Clean machine | CI run `44065676777`, headSha `21c5c9c`, three jobs all `success` | 0 |
| Owner approval | **OPEN** — this report, a reviewer, the author and CI cannot close it | n/a |

Two gate rows were **red on the first run and corrected, not annotated**: `GATE_RUFF_RC=1`
(7 unused F401 imports) and `GATE_PARITY_RC=1` (parity's `artefact_values` did not read the
artefact's third `bound` shape that W-F1 added to `ingest`, so it compared the portal
against `None`). Both were fixed in `21c5c9c` — imports removed; parity reads the same
three shapes with a regression test — and re-verified: ruff `All checks passed!`, parity
`PARITY OK … denominators 612 /612`, full suite `303 passed`, CI green. No skip, xfail,
ignore or exemption was added (§6.2). The first-run red readings are kept in the gate log
and shown in the report; they are not silently rewritten.

### Report frozen

`~/laya-evidence/m5-2026-11-16/report-2026-11-17-m5-enforcement-monitor-verifier.md`,
sha256 `8719e225cccc9eb87b7f0e0fa5b57eb3d4099f6332dde4a93b8a7675474177b6`
(`report.sha256`, verified OK). It carries all §13.2 sections: baseline B1–B5 verbatim,
commands with exit codes, AC12/checker-verdict/W-F1/W-F2/F6/F7/F9/F10/T9 proven, the
liveness table (I1–I6 all ACTIVE on this milestone's re-run; two plants rewritten under
§6.2, none void, none unproven), deviations D1–D8, re-derived vs transcribed numbers,
deliberately-not-done, follow-ups and added-file guards.

### Deviation, counted

Since `f5eb3cd` this ledger gained one docs commit (this one) and the freeze round added
one frozen source + one frozen test file. `git diff --name-only f5eb3cd..HEAD -- data/`
returns **0**; the freeze round changed no published artefact and no compared field;
`verify` still exits 0 at **649 /649**. M4's approved report stays frozen at
`f1e87ac9a7bf34504f73d49fd85864d8ad919b371dbce7d206d9c67b1b5ecdd4`.

### Stop point

The Section 13.1 gate table has been run at the final tips (`autorate-portal 21c5c9c`,
`autorate 1792bf1`), both pushed and CI-validated. Work stops here for the owner's
approval of this table, which no report, reviewer, author or CI can supply. M4's approval
is not carried forward.

---

## 13. M5 owner approval and terminal state — 2026-11-17 (PRD §13.5)

The owner approved the M5 stop point on 2026-11-17 at 18:42 CST (10:42Z) with the verbatim
instruction **"批准，执行"**, recorded in
`~/laya-evidence/m5-2026-11-16/gate/m5_approval.log` (sha256
`7fe7c5c660e258637a263992357e90e1f5356555cf62c87cf41f567790878ddf`). The approval names
the gate table `gate/gate_run.stdout` (sha256
`f61648f99f32a8aebcb706e355362a77bedd92dae4da30204cf2ee0a6a884445`) and the frozen report
`report-2026-11-17-m5-enforcement-monitor-verifier.md` (sha256
`8719e225cccc9eb87b7f0e0fa5b57eb3d4099f6332dde4a93b8a7675474177b6`) — the exact bytes the
owner approved. Neither the report nor the gate table was edited after approval. Section
12's gate-table transcription keeps the `Owner approval … OPEN` row as it was printed at
run time; a log is not rewritten. This section is where that row is closed.

**Scope of the approval.** The Section 13.1 gate table at portal `21c5c9c` / frozen
`1792bf1`, all rows: NIF `649 /649`; the freeze round (JSON `re_derived="649 /649"`, text
byte-identical, no compared field added); the two first-run red rows (ruff F401, parity's
third `bound` shape) corrected in `21c5c9c` and re-verified green; AC12; the browser/checker
verdict equality; W-F1/W-F2; F6/F7/F9/F10; 55/55 plants; parity `612 /612`; the CI
clean-machine row (run `44065676777`, three jobs success); and the approval row now closed.

### Decisions taken (report D1–D8)

| # | Decision | Value | Basis |
|---|---|---|---|
| D1 | ruff row red on first gate run (7 F401) | **Accepted as fixed** | imports removed in `21c5c9c`; ruff `All checks passed!`; no ignore/exemption added (§6.2) |
| D2 | parity row red on first gate run (third `bound` shape) | **Accepted as fixed** | `tools/parity.py` reads the artefact's plain `bound` like `ingest`; regression test added; parity `PARITY OK … 612 /612`; no compared field added to the frozen repo |
| D3 | gate table has no aggregate exit code | **Accepted** | rows are the verdict; an aggregate rc lets a failing row hide |
| D4 | two frozen commits since opening (`0db1fd8`, `1792bf1`) | **Accepted** | opening ledger committed before first source edit; one authorised freeze round; `data/` delta 0; `verify` still `649 /649` |
| D5 | corpus-absent lane manifest is 147 lines | **Accepted** | the freeze round added one frozen test file; both lanes hold (`649 /649` and `612 /612`) |
| D6 | container reading is a named `not-run`; clean machine is CI's | **Accepted** | no Docker daemon (rc 3); CI run `44065676777` headSha equals portal tip, three jobs success |
| D7 | two plants retargeted, not deleted (§6.2) | **Accepted** | `html-exclusion-disclosure` → `render.py`, `m4-ac11-staleness-swallowed` → `policies.py`; both landed at runtime and reddened |
| D8 | leak test's 7 hits | **Accepted** | all seven are the PRD's own phrase `no longer`; PRD not edited to shrink the count |

The freeze round's recorded justification — **no compared field added** — is accepted:
`--format json` serialises the comparisons the text path already performs; the text output
is byte-identical (sha `b31e3412…`) and the denominator is unchanged. W-F1/W-F2 are closed;
AC12 and the checker verdict equality are accepted. Report D1–D8 are M5's list and are not
the ledger's M4 D1–D12.

### Readings that close M5 (Section 0.4 re-run at the approved tips)

Re-captured in `gate/closeout-21c5c9c/` (`baseline.sha256` covers b1a/b1b/b1_remote/b2/
b2_portal/b3/b3a/b4/b5; each exit code from its own command, in `closeout.stdout`):

| Reading | Value at 2026-11-17 | Where it was read |
|---|---|---|
| approved tips at gate | portal `21c5c9c`, frozen `1792bf1`; both trees clean | gate table header; b2/b2_portal 0 lines |
| final frozen tip | `023baa4` (docs-only closure ledger after `1792bf1`); remote `main`, `integration/f8-into-main` and `HEAD` all `023baa4` | b1b.log, b1_remote.log |
| B1 | branch `integration/f8-into-main`, tip `023baa4` | b1a.log, b1b.log |
| B2 | frozen 0 lines, portal 0 lines | b2.log, b2_portal.log |
| B3 | rc 0, corpus present, `re-derived 649 /649 values`, one exact line | b3.log (sha `b31e3412…`, identical to the opening) |
| B3A | rc 0, corpus absent, `re-derived 612 /612 values`, 147 manifest lines | b3a.log (sha `9eb4aaca…`, identical to the opening) |
| B4 | rc 0, 10 subcommands (`--format json` is a flag) | b4.log (sha `93a3fe04…`, identical to the opening) |
| B5 | `{"stargazerCount":1,"visibility":"PUBLIC"}` | b5.log |
| NIF after docs-only closure | `data/` delta since `1792bf1` = 0; since opening `f5eb3cd` = 0 | post_data_paths.txt, data_delta.txt |
| report sha unchanged | `8719e225…` at closeout, equal to the approved sha | report_sha_check.log |

The byte-identical B3/B3A/B4/B5 logs across the opening (`f5eb3cd`) and the final closure
tip (`023baa4`) are the non-interference evidence: the closing ledger commits touched only
`docs/`, and no published artefact, compared field or denominator moved.

### Terminal state of the milestone sequence

PRD Section 7 defines six milestones, M0 through M5; **M5 is the last row**. With this
approval, every milestone gate table in the sequence has been run and approved in its own
session, each with its own Section 0.4 baseline and its own owner approval (no approval was
carried forward): M1 `b1b.log`-lineage at `e9aa7f98…`, M2, M3, M4 (ledger Section 10), and
M5 (this section). No further milestone is defined by the PRD; this approval does not open
one.

This is a statement about the **milestone gates**, not a claim that every item in Section
7 is shipped. The M0 row still carries sub-items blocked on owner-external decisions:
the git tag and PyPI release remain **BLOCKED on A4/A7**, and the `autorate-portal` scaffold
release remains **blocked on A3** (Section 7, M0; correction order in §8.1). Those are not
M5 deliverables and are not unblocked by this approval. The deferred backlog likewise stays
open with its owner: R-F4–R-F8 (M4 → M5) and the M5 follow-ups F1–F6 in report §9 are
recorded, not silently closed. F1 (approve this table) and F2 (accept D1–D8) are closed by
this instruction; F3–F6 remain jackson's.

### Stop point

The Section 13.1 gate table is approved; the Section 13.5 stop for M5 is discharged and
work is complete at the milestone level. The report stays frozen at `8719e225…`, the gate
table at `f61648f9…`; neither was edited after approval. No outbound message to a named
third party and no irreversible public exposure (§0.2 (a)/(b)) was undertaken by this
approval. M0's release blockers and the deferred backlog are the only open items, each with
owner jackson.

---

## 14. Verification-type closeout of deferred follow-ups — 2026-11-17 (post-approval, docs-only)

Owner instruction "继续推进", resolved to verification-type closeout: execute the
verifiable backlog items, add **real** evidence, change no product code, touch no release and
no external action. Full record in
`/Users/jackson/laya-evidence/m5-2026-11-16/f5-addendum-2026-11-17.md`
(sha `8265b25e…`, evidence sha manifest `f5-browser-check/SHA256SUMS.txt`). This section is
docs-only: the approved gate table `f61648f9…` and report `8719e225…` were not edited,
`data/` did not change, `verify` still `649 /649`, and no milestone was reopened.

- **F5 (T8 checker in a real browser) — DONE.** Checker rebuilt with the product's own
  `build_checker` and real published pin (wheel `7709d3fa…`, rule sha `79e7e1b5…`), served
  over localhost and opened in ego-browser v2.2.1 **real Chromium**. Rule layer: real-browser
  `publishedVerdict` equals the Node execution of the same `verifier.mjs` on **6/6** decision
  inputs; recorded in `f5-record.json`, not asserted. End-to-end `autorateCheck` returned
  `replay required` on all six: `fetchWheel()` hashes the PyPI **JSON metadata** bytes against
  the **wheel** sha, so the digest cannot match — the checker's designed "never a pass from an
  unverified wheel" degradation, recorded as an observation, not relabelled a defect and not
  fixed (no source change). Screenshot `ego-checker.png` retained. Browser space and server
  both closed.
- **F7 (new, owner jackson) — opened by this run.** Decide whether `PIN.source` should point
  at a byte source whose digest can equal the wheel sha (needs wheel-CORS/hosting work) or
  whether "always `replay required` on this machine" is the intended v1 posture. No product
  decision was made here.
- **F3 (P1/P2 external-reader walkthrough) — NOT RUN, precondition absent.** The owner's own
  2026-11-15 decision recorded `not-run` and stop; no reader outside the execution loop has
  been named, and the owner may not act as the reader. An agent cannot manufacture an
  independent reader. No results sheet, no signature, no `p1p2_addendum.log`; gate row 72
  stays `OPEN` verbatim. Only the owner naming a reader unblocks it.
- **R-F4 (AC5 against a real feasible certificate) — NOT RUN, precondition absent.** All seven
  published certificates have `autorate: null`; the one `feasible: true` certificate publishes
  `bound`, not `autorate`, so no real artefact exists for AC5's "share above the certified
  autororate" comparison. A fixture re-run presented as real would be the mislabelling the
  method forbids; no reading was invented.

Stop point unchanged: the milestone gates remain approved and discharged; the four items
above are follow-ups with owner jackson, not open gate rows.
