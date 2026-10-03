# Plan D — the frozen protocol, the report that emits its own numbers, and G5 on a clean export

Plan file: `docs/superpowers/plans/2026-10-03-autorate-plan-d-protocol-freeze-and-g5.md`
Spec: `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` (§2 G5, §10, §13 weeks 11–12)
Branch this plan lands on: `plan/d-protocol-freeze`, forked from the tip that carries B1–B3 and C.
Prerequisite for Tasks 2–6: Plan B1 Tasks 1–6, Plan B2, Plan B3. Prerequisite for Task 1: Plan B1
Task 5 (it defines `SHAPE_VERSION`) and Plan C Task 1 (it produces the pins). **Task 1 of this plan is
a predecessor of Plan C Task 4** — see §3, "the ordering ruling", which is the one thing in this plan
that changes another plan's schedule.

---

## 1. Why this plan exists, and what it would be to skip it

Every other plan in this repository adds a measurement. This plan adds the *claim* of a measurement,
which is a different object and the one the spec makes the release gate:

> **G5** — Reproducible from a commit with no GPU, no network, no model: `autorate verify --protocol
> protocol.json` re-derives every published number from per-case records alone; exit code + counts
> printed. (spec §2)

Three things are missing, and one of them is not a missing command.

**(a) The command in the gate does not exist.** `protocol.json` is not a file in this repository — the
only occurrences of that name are the spec sentence that promises it and this plan's own search
result. `autorate verify` accepts no arguments at all:

```
$ grep -rn "protocol" src/autorate/*.py | wc -l
0
$ grep -n "v = sub.add_parser" -A 2 src/autorate/cli.py
359:    v = sub.add_parser("verify", help="re-derive every published number")
360-    v.set_defaults(fn=cmd_verify)
```

**(b) `verify` as shipped is self-referential, and this is the substantive gap.** It re-derives each
certificate from the committed records — genuinely — but it takes the rubric *from the artifact it is
checking*:

```
fresh = certify_choice(records.get(backend, []), alpha=stored.alpha, beta=stored.beta,
                       delta=stored.delta, seed=stored.meta.get("seed", SEED))
```

So it proves *"this artifact is the fixed point of its own parameters"*, which is a real and useful
reproduction check, and it is not the claim the README makes next to it. A certificate published at
`seed=8` verifies green, because it asks for `seed=8`. Nothing in the tree says which rubric the
project *promised* to use, so nothing can catch a number produced after the rubric was moved to make
the number look better — the exact failure this whole design exists to prevent, left open at the
outermost layer. Two smaller consequences of the same lines: `method` is not passed, so a stored
`lac` certificate is re-derived with the `aps` default and the mismatch is caught by the field
comparison rather than honoured by the derivation; and `grid` is never passed, so the diagnostic grid
is silently whatever the module constant says today.

**(c) There is no technical report.** `docs/RESULTS.md` is a table of two certificates and an
inventory. §13's week 11–12 row promises a *technical report* whose "numbers [are] all re-derived by
the tool that emits them" — which is also the destination of the derived-prose rule already queued as
B1 Task 2d (`report.py:163-176` narrates "zero-error run at n=32" from hardcoded strings). Skipping
this plan does not lose a feature; it loses the ability to say "v1" while the release gate's own
command is unrunnable and its numbers have no frozen protocol behind them.

---

## 2. Measured facts this plan is written against

Each line was produced by a command that ran on 2026-10-03 against the tree at the B1 tip. A grep
that fails is not a grep that found nothing, so the failing form is recorded too.

| # | fact | the command that ran |
|---|---|---|
| D-1 | No `protocol.json` anywhere in the repo, and no `protocol` symbol in any module | `grep -rln "protocol\.json" --include='*.py' --include='*.md' --include='*.yml' .` → only `docs/superpowers/specs/2026-09-29-...md` and the B1 ledger; `grep -c protocol src/autorate/*.py` → 0 for every module |
| D-2 | `verify` has one call site, in CI, with no flags | `.github/workflows/ci.yml:19` → `uv run --frozen autorate verify \| tee /tmp/verify.log` |
| D-3 | The re-derivation rubric comes from the stored certificate; `method`/`grid` are not passed | `src/autorate/cli.py`, body of `cmd_verify` (quoted in §1b) |
| D-4 | The published rubric today is `alpha=0.05, beta=0.05, delta=0.05, seed=7, method=aps`, and those values live in code, not in a protocol | `src/autorate/report.py:23` `ALPHA = 0.05`, `:24` `BETA = 0.05`, `:25` `SEED = 7`; `certify_choice` defaults `delta=0.05, method="aps"`, `grid=None` → `DIAGNOSTIC_GRID` (`certify_choice.py:32` = `tuple(round(0.01*i,2) for i in range(1,30))`) |
| D-5 | The case-count floor is a module constant, not a protocol field | `certify_choice.py:30-31` → `MIN_CAL = 60`, `MIN_EVAL = 60` |
| D-6 | The number of simultaneous claims is fixed in `certificate.py` | `certificate.py:19` → `N_CLAIMS = 3` |
| D-7 | Every published artefact's path | `report.py:20-22` → `data/records_feishu.jsonl`, `data/cert_laya.json`, `data/cert_jev.json`, `data/inventory.md.json`; `cli.py:32-33` → `docs/RESULTS.md`, `data/inventory.md` |
| D-8 | The machine-dependent keys that a clean export must not compare | `cli.py:38-40` → `SNAPSHOT_MACHINE_KEYS = ("source", "audit_interpreter", "upstream_audit_stdout_tail", "upstream_audit_stderr_tail")` |
| D-9 | The corpus-less lane is already reachable, already discloses itself, and is already green | Measured in a `git archive` export of `645e975`, run with the export as cwd: `re-derived 34 /34 values`, exit **0**, with the corpus-absent disclosure quoted in `cmd_verify`'s `else` branch. The count is exactly the shipped formula in `tests/test_cli.py:77`, `2 * (len(CERT_COMPARE_FIELDS) + 1) + 2` = 34. An implementer's report quoting `61 /61` for this lane does not reproduce and is not used here |

D-9 carries a second, sharper consequence, measured the same way: overlaying B1 Task 2b's
`case_id` fix on that export leaves the lane at **34/34, exit 0, no drift** — because the committed
`data/records_feishu.jsonl` was exported before the fix and its rows carry no `case_id` for
`from_dict` to lose. The fix therefore moves no published number **until the records file itself is
re-exported from the archive**; re-certifying alone is a no-op. Two obligations follow, and they
belong to 2b rather than to this plan: the re-export is part of the fix, and the code, the records
file, both certificates and `docs/RESULTS.md` must land in **one** commit — any split leaves a HEAD
where the corpus-less lane is green while the corpus-present lane disagrees, which is the state a
reproduction gate exists to make impossible.
| D-10 | `docs/VERIFICATION.md` is a parsed gate, not prose | `tests/test_verification_table.py` parses it; a `verified` row must name a URL and the date it was opened |
| D-11 | The upstream channel is still empty — re-check it, do not cite this row | `gh search issues --author=<the author's handle> repo=<the upstream repo>` → `[]`, and the same for PRs, both re-run 2026-09-30 as recorded in spec §13. This plan *prepares* that channel; it does not use it (see §7) |

Why Task 3 waits for B1 Task 2b, stated precisely: the corpus-less lane is already green at HEAD, so
a clean-export proof would *run* — it would simply certify a records file whose `case_id` fidelity is
known-broken and a certificate pair this ledger already expects to move, which is a transcript of a
state its own author is about to publish an ERRATA row for.

---

## 3. The ordering ruling: a protocol is only frozen if it precedes the numbers

Ruling D-a (controller, this plan's authorship). **`protocol.json` is committed before the first
certificate it governs is produced, and any certificate whose rubric is not in the committed
protocol is refused by `verify` rather than tolerated.** Consequence: this plan's Task 1 sits
*between* two of Plan C's tasks — after **C Task 1** (the pin, because `corpus.pinned_builds` is
that task's provenance output and the protocol records its digests) and before **C Task 4** (the
inference-derived certificates that first populate `claims`). C Task 4 must therefore be dispatched
with the protocol digest as an input. Recorded against Plan C's ledger on the first execution turn of
this plan; Plan C's own text gets one cross-reference line, and no other change.

(Fixed on re-read: this section first said "before Plan C Task 5", and named Task 5 as the inference
run. Task 5 is `Make the new artifacts checkable where CI can see them`; the driver is Task 2 and G1's
certificates are Task 4. A cross-reference that points at the wrong task number is worse than none —
the same reason PF-B1-1 exists in the B1 ledger.)

Why it is a ruling and not a preference: the alternative ordering — run the inference, then freeze
whatever rubric happened to be in the code — produces a `protocol.json` that is a transcript of the
result. It would pass every check in this plan and be worthless, which is the definition of the
failure mode §12 of the spec spends a whole table on. The plan therefore states the enforceable half
and the disclosed half separately:

* **Enforceable by `verify`:** the rubric in an artifact equals the rubric in the committed protocol;
  the protocol's sha256 equals the digest recorded in the artifact; the numbers re-derive under that
  rubric. All three are mechanical and all three can go red.
* **Not enforceable, disclosed:** that the protocol was written before the measurement was seen. No
  hash proves intent. The published artefacts therefore carry the freeze date and the commit id of
  the protocol commit, and the technical report's evidence-boundary section says in one sentence that
  ordering is a process claim attested by git history, not a cryptographic guarantee. Writing a
  stronger sentence than that is the dishonesty this task is designed to avoid.

Ruling D-b. `protocol.json` is **emitted by a command**, never typed. `autorate protocol --out
protocol.json` reads the module defaults (D-4, D-5, D-6), the corpus digests from the inventory, and
the pins from Plan C's provenance file, and writes the document. A hand-maintained protocol is a
transcription risk — the same class as the hardcoded prose in `report.py` that B1 Task 2d is fixing —
and a protocol with a typo in `MIN_CAL` would freeze a floor nobody implemented. The freeze is then
the commit itself, and `verify --protocol` compares the committed file against what the code would
emit *today*, which catches the protocol drifting away from the implementation.

Ruling D-c. The name conflict between spec §10 (`cert.risk_bound`) and the shipped
`conditional_error_bound` / `marginal_error_bound` is settled **in the spec, not in the code** (this
closes queued item #35). Reason: `risk_bound` as written is one name for two numbers that the envelope
must label separately, and the shipped pair is what `compare`, `verify` and the CI artefacts already
carry; adding an alias would create a second owner for a published figure, which is precisely what
ledger rulings R-20 and R-31 deleted once. The amendment is a one-line edit to §10 with the reason
attached, made as an explicit spec change in the same commit that updates §13's checkboxes — never as
code that quietly won an argument with a document.

---

## 4. Global Constraints (inherited, restated because this plan touches the outer contract)

1. Exit codes are a published contract: `0` CERTIFIED / `2` USAGE / `3` NOT_CERTIFIABLE / `4` DRIFT
   (`cli.py:17-20`). `verify --protocol` reports a rubric mismatch as **4** — it is drift between a
   promise and an artefact — and a missing or unreadable protocol as **2**. No new code.
2. **No absolute machine path in any tracked file.** `tests/test_cli.py` fails the build on a
   username-shaped path, and Plan B1 proved that a single unguarded literal survives every local gate
   and reddens only CI. `protocol.json` records corpus identity by *digest and label*, never by
   location; `data/SOURCE.json`'s existing `label` convention is the model.
3. `uv run --frozen` for everything; the interpreter on PATH is `python3`, never bare `python`.
4. The vendored upstream checkout (`laya-0.3.20`, a sibling of this repository) is **read-only**.
5. An assertion is never relaxed to pass, and no `# noqa` or lint-exclude is used to clear a gate. If
   a gate is red, the artefact or the code changes — and if the *gate* is wrong, that is a ruling in
   the ledger, with the reason.
6. No test counts, suite sizes, or pass/fail totals in commit messages (R-16).
7. Before any push: the corpus-less simulation (R-41) — `AUTORATE_FEISHU_ROOT=/nonexistent uv run
   --frozen pytest -q -p no:randomly` plus `uv run --frozen autorate verify` with the corpus absent.
   This plan makes that lane a *demonstration*, so it has to be green to demonstrate.
8. Every new published number must be produced by the command that publishes it. This plan adds no
   number by hand.
9. Numbers already published are corrected through `docs/ERRATA.md` (append-only), not by overwriting
   prose; B1 Task 2b establishes the precedent for a moved bound.
10. A claim in `docs/VERIFICATION.md` is `verified` only with a URL opened on a recorded date, and
    `withdrawn` with a `dropped:`/`replaced:` note. Plan D adds exactly one row type (§6 Task 5): the
    clean-export run itself, whose "source" is the committed transcript.

---

## 5. The shape of `protocol.json`

Emitted by `autorate protocol`, validated by a loader, consumed by `certify` (which records the
digest) and by `verify` (which enforces it). Field order is fixed by the emitter so the file is
byte-stable and its digest is meaningful.

```
{
  "protocol_version": 1,
  "frozen_at": "YYYY-MM-DD",                // the commit date of the freeze, printed not typed
  "record_contract": {"shape_version": <SHAPE_VERSION from B1 Task 5>, "primitives": [...]},
  "rubric": {"alpha": 0.05, "beta": 0.05, "delta": 0.05, "seed": 7, "method": "aps",
             "grid": [0.01, ... 0.29], "n_claims": 3, "min_cal": 60, "min_eval": 60},
  "unit": "case",                           // R-36/R-44: the binomial denominator is the case
  "decision_rule": "singleton certified set automates; anything else escalates",
  "corpus": {"records_digest": "<sha256 of data/records_feishu.jsonl>",
             "inventory_digest": "<sha256 of data/inventory.md.json>",
             "source_labels": [...],         // digests + labels only: no path, ever
             "pinned_builds": {...}},        // Plan C's MASSIVE / typed-decisions pins
  "claims": [ {"id": "G1", "artifact": "data/cert_*.json", "bound": "conditional"}, ... ],
  "known_limits": [...]                     // copied from the certificates' envelopes
}
```

Three design points worth stating before an implementer meets them:

* `known_limits` and `claims` make the protocol the *only* place the envelope is written down once,
  so `verify` can check that a certificate's envelope is a subset of what the protocol allows. An
  envelope line that is not sanctioned by the protocol is drift.
* `claims` is what turns "re-derive every published number" from a loop over two files into a closed
  set. G1–G5 become named entries with the artefact each is stored in, and `verify` prints one line
  per claim plus the counts — which is the literal wording of G5.
* The digest of the protocol is recorded **inside** each artefact's `meta` at production time
  (`meta["protocol_digest"]`), and `verify` recomputes it. Editing `protocol.json` after the fact
  therefore breaks every certificate at once, which is the behaviour you want from a freeze: silent
  acceptance would mean the file is a comment.

---

## 6. Tasks

Each task: files, steps, the tests that make it falsifiable, and the gate that must exit 0 (or the
documented non-zero). Exact values live here so a dispatch brief can quote them verbatim.

### Task 1 — `protocol.py`: emit, load, digest; and freeze the document

**Files:** new `src/autorate/protocol.py`; `src/autorate/cli.py` (`protocol` subcommand +
`--protocol` accepted by `certify`); new `protocol.json` at the repo root; new
`tests/test_protocol.py`.

**Steps.**
1. `emit_protocol(inventory: dict, records_digest: str, frozen_at: str) -> dict`, drawing every value
   from the module constants (D-4–D-6) and the inventory, with no literals typed into the emitter
   body. `write_protocol(doc, path)` renders it with `sort_keys=False, indent=2` and a trailing
   newline so the bytes are stable; `protocol_digest(doc) -> str` is the sha256 of exactly those
   bytes.
2. `load_protocol(path)` validates and returns a frozen dataclass, and **raises `ProtocolError` (a
   `ValueError` subclass, so `main` maps it to `EXIT_USAGE`) for**: an unknown
   `protocol_version`; a `rubric` value outside `(0,1)` where it must be; `min_cal`/`min_eval` that
   disagree with `certify_choice.MIN_CAL`/`MIN_EVAL`; a `grid` that is not the module's; an
   `n_claims` that is not `certificate.N_CLAIMS`; a `unit` other than `"case"`; a `corpus` field
   holding a string that parses as an absolute path. That last check is the machine-path guard moved
   into the loader, so it fires on the producer's machine before CI ever sees the file.
3. `certify` gains `--protocol` (optional, default `protocol.json` when it exists): the digest is
   written into `meta`, and the rubric is taken from the protocol rather than the flag defaults when
   the flags are absent. Existing explicit flags still win, and when they contradict the protocol
   `certify` exits **2** naming both values — a protocol that can be silently overridden at the
   command line is not a freeze.
4. Produce `protocol.json` by running the command, commit it, and record the freeze in the ledger.

**Tests (all must be proved red against the pre-task code first).** Loading the committed
`protocol.json` returns a doc whose `rubric` equals the module defaults; `emit_protocol` re-emitted
against today's code is byte-identical to the committed file (this is the "protocol drifted from the
implementation" check, and it is the test that will fire the first time anyone changes a constant
without re-freezing); each validation clause above is exercised by a mutation — a `min_cal` of 40, a
`unit` of `"row"`, a `corpus.records_digest` replaced by an absolute path (built from pieces,
`"/" + "srv" + "/corpus/x.jsonl"`, the trick `tests/test_cli.py:450` uses so the test that
polices machine paths never becomes an offender under its own guard) — and each
mutation raises with its own name in the message; a doc with an added key round-trips to the same
digest, a doc with a changed value does not. **Negative control required:** delete the absolute-path
clause from `load_protocol` and show exactly the path test go red, then restore byte-identically.

**Gate:** `uv run --frozen ruff check src tests --select=E9,F63,F7,F82,F401,F811 --line-length=120`
→ 0; `uv run --frozen pytest -q -p no:randomly` → 0; `uv run --frozen autorate protocol --out
/tmp/reemit.json && diff <(cat /tmp/reemit.json) protocol.json` → empty.

### Task 2 — `verify --protocol`: make the gate check the promise, not the artifact's own word

**Files:** `src/autorate/cli.py` (`cmd_verify`, the `verify` parser); `tests/test_cli.py` (or a new
`tests/test_verify_protocol.py` if the first exceeds ~900 lines — the file's own size is a measured
input to this choice, not a guess).

**Steps.**
1. `verify` gains `--protocol PATH` (optional). With it: the rubric for every re-derivation comes from
   the protocol, `method` and `grid` are passed through (closing D-3's two silent holes), each stored
   certificate's `meta["protocol_digest"]` must equal the recomputed digest, and a certificate whose
   own `alpha`/`beta`/`delta`/`seed`/`method` differ from the protocol is reported as a **rubric
   mismatch** — a distinct line in the output, not folded into the existing `DRIFT:` strings, because
   "the number does not reproduce" and "the number was produced under a rule we never promised" are
   different failures with different repairs.
1a. Compare `sha256(data/records_feishu.jsonl)` against the protocol's `corpus.records_digest`, in
   **both** lanes. This is the only guard that needs no corpus, and therefore the only one that can
   catch a published records file produced by a reader no longer matching the code beside it — the
   gap measured in §2 D-9, where the corpus-less lane reports a clean 34/34 over records no protocol
   ever blessed. A records file is a published number's parent; treating it as outside the freeze is
   how a corpus and a contract drift apart unnoticed.
2. Without it, behaviour is unchanged. That keeps today's CI line working until Task 3 replaces it,
   and it keeps the flag's effect *observable*: the same tree must be able to go from green to red by
   adding the flag alone.
3. Print one line per `claims` entry from the protocol, then the counts, then the disclosure — the
   disclosure sentence is the existing corpus-absent one, extended with "…and the protocol rubric was
   enforced" or "…was not enforced (no --protocol given)". Exit 4 on any failure, 0 otherwise.
4. `compare` also learns to refuse two certificates whose `protocol_digest` differs — that is the
   case where a "before/after" table would be comparing two protocols while claiming to compare two
   backends.

**Tests.** A certificate re-derived at `seed=8` and stored with `seed=8` verifies **0** without
`--protocol` and exits **4** with it, naming seed. This is the whole point of the task and it is the
test that proves §1b was real rather than rhetorical. A certificate stored without a
`protocol_digest` exits 4 with "produced without a protocol"; a protocol edited to a different
`beta` while the artifacts stay put makes every certificate report a digest mismatch (and the count
of mismatches is asserted, so a partial enforcement cannot pass); `method="lac"` under an `aps`
protocol is caught by the rubric comparison *and*, once honoured, a lac artifact re-derived as lac
reproduces (which is the assertion that closes D-3's other half); the no-flag path is byte-identical
to the shipped output for the current tree, asserted by comparing captured stdout. **Negative
control:** reorder the new clause so the missing-digest check runs after the value checks, and show
the missing-digest test still reds — the check must not be reachable only when nothing else failed.

**Gate:** the four gates from Task 1, plus both lanes of the same command, reported separately —
`uv run --frozen autorate verify --protocol protocol.json` (corpus present) and
`AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen autorate verify --protocol protocol.json`, each
with its exit code, before and after B1 Task 2b lands.

Why the split, because it is the strongest argument this plan has: measured on a `git archive` export,
overlaying 2b's `case_id` fix leaves the **corpus-less** lane at `34 /34`, exit **0** — no drift, no
signal. Its input is the committed `data/records_feishu.jsonl`, and that file was exported by the
*old* reader, so a machine without the corpus cannot see that the published records were produced by
a different contract than the code beside them. Only the corpus-present lane, which re-reads the
archive, goes red. Today nothing closes that gap on a clean machine. `--protocol` closes it by one
check that needs no corpus at all: `sha256(data/records_feishu.jsonl)` against the protocol's
`corpus.records_digest`. **So Task 2's own gate is that this digest check turns the corpus-less lane
red for a records file the protocol did not bless** — demonstrated by touching one row of a copy, and
reported as exit **4** with the digest named. A `verify` that cannot fail on the machine that runs it
in CI is not a reproduction gate.

### Task 3 — G5 on a clean export, with the transcript committed

**Files:** `tools/g5_export.sh` (new); `docs/G5.md` (new, generated); `.github/workflows/ci.yml`.

**Steps.**
1. `git archive HEAD | tar -x -C <scratch>` — the export, not the working tree, is the subject under
   test (a lesson already paid for: an uncommitted foreign file is not what CI checks out).
2. Inside the export, with `HOME`, `XDG_*` and `AUTORATE_FEISHU_ROOT` pointed at the scratch dir so no
   machine state leaks in and no store is written to the real config: create a fresh venv (`uv sync
   --frozen --extra dev`), then run the suite, `autorate verify --protocol protocol.json`, and
   `autorate report --out <inside-export>` and diff it against the committed report.
3. No network is *assumed* unavailable; it is **asserted** — the script sets `no_proxy`/`NO_PROXY`
   (both spellings, because the local proxy on this machine breaks loopback otherwise) and the
   transcript records that a deliberate `curl` to a non-resolving host failed. A proof of "no network"
   that never tried the network is not a proof.
4. Write `docs/G5.md` from the run: the command lines, the exit codes, the `re-derived N /N` counts,
   the environment labels (interpreter version, uv version, OS — from the export's own commands, never
   transcribed), and the machine-dependent keys that were excluded by name (D-8) with a sentence
   saying why. It is generated output, and `verify` polices its freshness the way it polices the
   inventory: the file carries the digest of the protocol and of the artifacts it observed, and a
   transcript whose digests no longer match the tree is reported as stale rather than trusted.
5. CI: change the last step to `uv run --frozen autorate verify --protocol protocol.json`. A second
   job that runs the export script is optional and should be declined on the first pass — it costs a
   dependency install per push and the local lane already covers the code path (decide again only if
   the export lane catches something the working-tree lane cannot).

**Tests.** `tests/test_g5_transcript.py` parses `docs/G5.md` and asserts: every recorded exit code is
in {0,2,3,4}; the final `verify` line's two counts are equal; the protocol digest in the transcript
equals the digest of the committed `protocol.json`; no line in the file matches the machine-path
pattern; and the run date is not later than the commit date of the file that reports it. **A test that
asserts nothing here is worse than none** — the guard is that removing the digest assertion from the
transcript makes this file red, proved as a negative control.

**Gate:** `bash tools/g5_export.sh` exits 0 and writes a transcript that the new test accepts;
`uv run --frozen pytest -q` still 0 on the working tree.

### Task 4 — the technical report, every number emitted by its producer

**Files:** new `src/autorate/techreport.py`; `docs/REPORT.md` (generated); `src/autorate/cli.py`
(`autorate report --full` or a `tech-report` subcommand — whichever keeps `report`'s default output
byte-identical, since `verify` compares that file).

**Depends on:** B1 Task 2d (derived prose in `report.py`). If Task 2d has not landed, the mechanism
here is the same one and the two must not implement two renderers — check the ledger before starting.

**Steps.**
1. The report is assembled from `Certificate` objects, the inventory dict, the protocol doc, and the
   Plan C/B2/B3 artifacts. **No number in it is typed into a string literal.** The pattern is the one
   B1 Task 2d establishes: build the sentence from the values, so a changed value changes the
   sentence, and a test can prove that by changing the value.
2. Structure: what a certificate is · the mechanism (APS/LAC, split quantile, Clopper–Pearson, the
   union bound over `N_CLAIMS`) · the four gates as named claims with their artifacts · every refusal
   and what it refused · the envelope and known limits, copied from the protocol · reproduction (§G5)
   · related work, citing only rows of `docs/VERIFICATION.md` that are `verified`.
3. The claims section is generated from the protocol's `claims` array, so G1–G5's status is a property
   of the same file `verify` enforces — one owner for the list, which is the rule §12 of the spec keeps
   having to re-learn.
4. Every sentence that could be read as a claim about other people's work carries its ledger row id.
   The "none found" rows are written as *search tasks with a date*, per spec §12's warning that a
   negative in that column describes the search, not the field.

**Tests.** Re-rendering is byte-stable (two calls, one diff); each published figure appears in the
rendered text with the exact value from its artifact; the report contains no claim id that is absent
from `docs/VERIFICATION.md`; the absolute-path guard runs over the rendered text; a certificate with
one number perturbed changes exactly the sentences that quote it (assert the count of changed lines >
0, so a report that ignores its inputs cannot pass).

**Gate:** `uv run --frozen autorate report --full --out /tmp/r.md && diff /tmp/r.md docs/REPORT.md` →
empty; all Task 1 gates; and `verify` still exits 0, which is the check that adding a report did not
disturb the artifacts.

### Task 5 — spec amendments, the ledger's open naming questions, and README v1

**Files:** `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` (§10, §13);
`README.md`; `docs/VERIFICATION.md`; `docs/ERRATA.md`.

**Steps.**
1. Apply ruling D-c: §10's `cert.risk_bound` line is amended to the two shipped names, with a one-line
   note stating that the rename happened in Plan A Task 8 and is now recorded rather than implied —
   closing the hole the B1 spec-surface audit found (`risk_bound` appears zero times in
   `certificate.py` while a plan line claimed it was covered).
2. Tick §13's week 11–12 row against what actually shipped, and where something did not ship, say so
   in the row rather than ticking it. A plan that marks its own homework is the failure this repository
   has twice documented in itself.
3. README: the top-level command block becomes `autorate verify --protocol protocol.json`; the
   reproduction section points at `docs/G5.md` and the export script; the boundary section states the
   corpus-less disclosure sentence verbatim as the tool prints it, so prose and tool cannot disagree.
4. Add the `VERIFICATION.md` row for the clean-export run (source: the committed transcript, opened
   the day it ran) and, if Task 5 cites any new external work, its row too — with the URL actually
   opened, per §10's rule that a snippet is not `verified`.
5. Append (never rewrite) any ERRATA row for numbers this plan moved. `verify --protocol` is expected
   to move none: the protocol freezes the rubric that produced the current artifacts, and if it cannot,
   that is a finding to publish, not to patch around.

**Tests.** `tests/test_verification_table.py` still passes with the new rows; `tests/test_cli.py`'s
machine-path guard covers `README.md`, `docs/`, and `protocol.json` — extend its file list explicitly
and show it red on a planted path (a guard whose file list silently omits the newest published file is
the exact blind spot already recorded once in this project's memory).

**Gate:** all four lanes, plus `uv run --frozen autorate verify --protocol protocol.json` → **0**.

### Task 6 — the upstream channel: prepared artefacts, and a red line that stays a red line

**Files:** new `docs/upstream/` with `issue.md`, `patch/` (the 4-finding patch against a clean
`v0.3.20` checkout), `pr-description.md`, `awesome-jev-entry.md`, and `SUBMISSION.md`.

**Steps.**
1. Re-run the emptiness check before writing anything (`gh search issues`/`prs` for the author in the
   upstream repo) and record the dated output in `SUBMISSION.md`. Do not reuse spec §13's 2026-09-30
   result — other contributors merged within 2026-09-23…25, so the state moves.
2. Reproduce the guardrail anecdote's *numbers* if B1 Task 4's audit makes that possible; if any of the
   three conditions in spec §7.1's bullet is unmet (patch on a clean checkout, the 39 prompts
   committed as per-case records, both ranges re-derived by `verify`), the artefact states that the
   claim stays `withdrawn` and the report does not quote it. A prepared PR that softens a withdrawn
   claim is the one outcome worse than not filing it.
3. Write `SUBMISSION.md` with: the two-PR order from §13 (patch first, the §7 audit and adapter second
   as a separate PR), the exact commands a reviewer would run, and a **DO NOT SUBMIT WITHOUT EXPLICIT
   HUMAN APPROVAL** line naming what approval would look like. This plan produces the text and stops.
   The repository stays private, no issue is opened, no PR is pushed — those are the red lines the
   standing authorization does not cover.
4. `awesome-jev` entry: only if the upstream `laya` README actually lists a Jev-compatible ecosystem
   and the entry's every claim is backed by a `VERIFICATION.md` row. Spec §14's own evidence already
   dented the assumption that this is a vacancy; re-measure or omit.

**Tests.** A new test walks `docs/upstream/` and asserts: no machine-absolute path, no secret-shaped
string, no claim id that is not `verified` in the ledger, and — for the patch — that it applies to the
vendored tree *in a scratch copy* (`git apply --check`) without ever writing to the read-only corpus.

**Gate:** the checks run in a scratch copy; `AUTORATE_FEISHU_ROOT=/nonexistent uv run --frozen pytest
-q -p no:randomly` → 0; nothing in this task touches a remote.

---

## 7. Out of scope for Plan D, stated so a later session does not re-open it

Model inference of any kind (Plan C owns it); the ordinal score certificate and G3 (B2); Mondrian,
simultaneous correction, ACI and the contamination probe (B3); `NOT_CERTIFIABLE`'s fifth `Reason` and
`SHAPE_VERSION` (B1 Task 5, which this plan's Task 1 *consumes* — check the ledger for its value
before emitting the protocol, since `record_contract.shape_version` is not guessable); making the
repository public; submitting anything upstream.

## 8. Pre-flight scan for this plan (run before Task 1 is dispatched)

| id | pair checked | what was found | ruling |
|---|---|---|---|
| PF-D-1 | Task 1 ↔ Task 2 | Both edit `cli.py`. Task 1 adds the `protocol` subcommand and `--protocol` to `certify`; Task 2 adds `--protocol` to `verify` and rewrites `cmd_verify`. Disjoint functions, same file — sequential dispatch only, never parallel. | Accepted; tasks are sequential in the SDD loop by rule |
| PF-D-2 | Task 1 ↔ Plan B1 Task 5 | `record_contract.shape_version` needs a value B1 Task 5 defines. If Task 1 runs first it will invent one. | **Task 1 must not start until B1 Task 5 has landed**, or the field is emitted as `null` with the loader accepting `null` only while no shape version exists — decide from the ledger at dispatch, and record which branch was taken |
| PF-D-3 | Task 3 ↔ B1 Task 2b | Measured: the corpus-less lane is already 34/34 green at HEAD and stays green under 2b's code change, while the corpus-present lane goes red — because the published records file predates the fix. So 2b must re-export the records and land code + records + both certificates + `docs/RESULTS.md` in one commit, or a HEAD exists where the two lanes disagree. | Task 3 sequenced after 2b and after B1 Task 6; the single-commit obligation is carried into 2b's review, and the transcript records both lanes' counts rather than one |
| PF-D-4 | Task 4 ↔ B1 Task 2d | Two tasks can each build a derived-prose renderer for the same sentences. | One mechanism. Whichever lands second imports the first and deletes its duplicate; the brief must name the existing function by path, verified by grep in the dispatch turn |
| PF-D-5 | Task 2 ↔ the shipped `compare` semantics | `compare` currently refuses on rubric disagreement between two artifacts. Adding a protocol digest makes a *third* reason to refuse. Its exit code is already `EXIT_USAGE` for "not comparable". | Digest mismatch is `EXIT_USAGE` in `compare` (an operator error) and `EXIT_DRIFT` in `verify` (a published-number error). Different commands, different meanings; both pinned in tests |
| PF-D-6 | Task 5 ↔ the machine-path guard | The guard enumerates files to scan. New tracked artefacts (`protocol.json`, `docs/G5.md`, `docs/REPORT.md`, `docs/upstream/*`) are outside its current list, so the guard would stay green over a path literal in exactly the files this plan adds. | Task 5 Step 5 extends the list **and** proves the extension can fire. Recorded here so the reviewer treats an unextended list as Important, not polish |
| PF-D-7 | Task 6 ↔ Global Constraint 4 | `git apply` against the vendored checkout would write into a read-only corpus. | Scratch copy only, `--check` first, and the test asserts the vendored tree's mtimes and digests are unchanged after the task runs |
| PF-D-8 | Task 3 ↔ the local proxy | Loopback and TLS on this machine are proxied; an "offline" proof that silently used the proxy is not offline, and `uv sync` can fail on a proxy rather than on a missing network. | `no_proxy` **and** `NO_PROXY` set in the export script, the deliberate failure probe recorded in the transcript, and any TLS/proxy failure disclosed in the transcript rather than retried away |

## 9. Definition of done for this plan

`autorate verify --protocol protocol.json` exits 0 on a `git archive` export with no corpus, no
network and no model, prints one line per named claim plus `re-derived N /N`, and the transcript of
that run is committed and policed for staleness. `protocol.json` was emitted, not typed, and freezing
it moved no published number — or the numbers it moved are in ERRATA. `docs/REPORT.md` contains no
typed number and no claim id that `docs/VERIFICATION.md` does not carry as `verified`. §10 and §13 of
the spec agree with the code, by amendment rather than by drift. `docs/upstream/` is complete and
unsubmitted, with the re-measured emptiness check on file.
