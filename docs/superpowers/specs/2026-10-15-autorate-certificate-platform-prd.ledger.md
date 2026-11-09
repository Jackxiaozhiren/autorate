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

Section 7 assigns M1 to the `autorate-portal` repository, which does not exist
locally or under the owner's GitHub account at 2026-11-09. Section 13.5 says the
previous session's approval is not carried forward, so creating that repository
is an owner decision and was not executed. No M1 source file was created.

The M1 implementation plan and the Section 13.2 report (including the liveness
table, the deviation register and the Section 13.1 gate matrix) are held in the
external evidence directory, not in this repository, because Section 7 puts
them in the portal repo once it exists. AC1, AC9, AC10 and AC14 are **not
proven**; I6 is ACTIVE for M1 but **UNPROVEN** in this session.

### Deviation registered, not hidden

This commit changes one file under `docs/` (this ledger), so
`git diff --name-only HEAD~1 -- data/ docs/` is not empty for this commit.
The byte-compared `data/` tree is untouched, `verify` still exits 0 at
**649 /649**, and no guard was relaxed. Section 13.5 requires the ledger
commit before source edits; Section 13.1's published-artefact gate is counted
as a deviation here rather than described as zero.

### Owner decisions still open

1. Whether `autorate-portal` is created, and whether it is public.
2. The pinned `autorate` distribution version and wheel SHA-256 for M1's packet.
3. Any new upstream filing still requires the four-part instruction in
   `docs/upstream/SUBMISSION.md` (Section 0.2 (b), Section 13.7).
