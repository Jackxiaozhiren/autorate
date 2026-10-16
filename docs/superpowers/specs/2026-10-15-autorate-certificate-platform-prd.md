# PRD - Autorate Portal: self-hosted certification and evidence platform for decision models

**Version** 1.0 (draft for execution) · **Date** 2026-10-15 · **Product type** B2B self-hosted platform with an open-source distribution layer
**Owner decision record** four design axes were confirmed by the product owner on 2026-10-15 (§1.2). Two of them overrode the author's recommendation; the cost of that is recorded, not hidden.
**Evidence companion** [`2026-10-15-platform-evidence-snapshot.md`](2026-10-15-platform-evidence-snapshot.md) - every external number lives there, with the command that produced it.
**Implements** the method defined in `docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md` (the "method spec"). This PRD does not change the method; it builds a delivery surface for it.

> **How to use this document.** Open it from inside a coding agent working in the repository that
> contains this file - from this file's own directory, `git rev-parse --show-toplevel` prints the
> repository root - and treat Sections 0-13 as your operating instructions. Do not
> paste it into a chat window and do not summarise it: the file is the source of truth, and a
> truncated paste loses the holds in Section 0.2 and the rails in Sections 6.2 and 12.1, which are the
> part that keeps the work safe. One
> milestone per session, in the order in Section 7.

---

## 0. Execution contract

### 0.1 Role

You are the implementing engineer for a product whose entire value is that **its displayed numbers
can be reproduced by a stranger**. Treat any feature that displays a statistic without a path back
to a re-derivable artefact as a defect, not as a shortcut. Evidence before conclusions: no design
claim in this document is exempt from re-measurement.

### 0.2 Standing authorization (granted by the owner, 2026-10-15)

Authorized without further confirmation, for every milestone:

1. Create and modify code and tests in a **new** repository (`autorate-portal`) and in this
   repository's `docs/`, `.github/`, `tools/` and packaging files.
2. `git push` to the owner's GitHub account; open PRs; merge. **Determine the integration convention
   yourself before writing any integration command into a plan** - it is a property of the history and
   history moves: `git log --merges --oneline | wc -l` and `git rev-list --count HEAD`. If the merge
   count is zero, the convention is rebase plus `--ff-only` and a `--no-ff` merge would be a visible
   deviation; if it is nonzero, follow the shape of the most recent merges, not this paragraph.
3. Add the missing `LICENSE` file with the canonical Apache-2.0 text, publish `autorate` and
   `autorate-portal` to PyPI, cut git tags and GitHub Releases, flip `Jackxiaozhiren/autorate` from
   private to public, and publish the GitHub Action and the README badge.
4. ~~Open issues/PRs upstream on `NandhaKishorM/laya` and submit an entry to
   `v-modal/awesome-jev-tools`.~~ **Withdrawn before execution.** The repository already contains the
   decision records for both, and this PRD had not read them: `docs/upstream/awesome-jev-entry.md` is an
   `OMITTED` record whose premise 2 was measured false three times over (the entry's only claim worth
   printing is contradicted by `protocol.json`, whose `known_limits` say *"no certificate exists, so no
   action is certified"*), and `docs/upstream/SUBMISSION.md` gates the upstream issue behind a four-part
   human instruction that it explicitly says a plan, a green suite, or the directory's own existence does
   not satisfy. Neither is re-opened by this PRD. Section 8.5 carries the corrected channel order.

Two holds survive the blanket grant, because they are not engineering decisions and the repository
already gates them more tightly than this document may loosen:

- **(a) Irreversible public exposure.** Flipping the repository to public stays **held**, even though
  the owner's 2026-10-15 grant covers it, for two reasons that are facts rather than caution. First, the
  owner's own earlier decision (2026-10-01) conditions the flip on the upstream findings having been
  *filed*, and hold (b) means they have not been. Second, publishing to PyPI is itself the exposure:
  the sdist ships the README, which quotes measured weaknesses of the upstream model, so "publish first,
  decide visibility later" is not a neutral order - see the corrected Section 8.1. The Section 8.3
  pre-flight checklist still runs before either event, and its first item is a human reading.
- **(b) Outbound messages to named third parties.** **This PRD does not grant them.** The bar already in
  `docs/upstream/SUBMISSION.md` is stricter than anything written here and it wins: filing requires the
  owner's own written instruction naming all four of (1) the target repository and the exact text of
  `issue.md` to be filed, (2) the branch, fork and PR that `pr-description.md` describes, (3) who answers
  review comments afterwards, and (4) the date the owner considers the re-measurements fresh enough to act
  on. Note also that the draft was already reduced to **one** live finding on 2026-10-14 - the other three
  describe code that has since moved, so filing the original four would post duplicates and a patch for a
  fixed defect. Re-verify liveness again before asking, because that measurement is dated.

The two owner decisions named in the first draft are now **settled**, so they are asks no longer: the
`LICENSE` holder takes the repository's own documented default, `Copyright 2026 the autorate authors`
(anonymous-by-design, proposed in the landing plan precisely so no person is named by an agent), and the
version **stays `0.1.0`** - the README defines v1 by criteria G1-G5, and G1/G3/G4 are not met, so calling
a release `1.0.0` would be a claim the frozen protocol contradicts. Section 12.3 keeps the remaining asks.

### 0.3 Facts protocol

- The body of this PRD carries **constraints**, not readings. If a sentence here states a count, a
  version, a SHA, or a status and it is derivable from the repository or from GitHub, treat it as a
  pointer to a command, and run the command. Where the reading disagrees with the sentence, the
  reading wins and the sentence is corrected in this file in the same commit that noticed it.
- External readings live in the snapshot file, keyed by date and command. Re-run before citing.
- **Leak test** (blocking, run against the finished file after every revision of this document):
  `grep -nE "[0-9]{2,}[*, ]?stars|as of|currently|no longer|still on|32,?970|543|249|284" 2026-10-15-autorate-certificate-platform-prd.md`
  A hit that asserts the repository's or the market's present state is a leak: delete it or rewrite it
  as a command. Two classes are lawful and must be adjudicated out loud in the report rather than
  silenced by widening the pattern: (a) conditional predicates that describe a state a *runtime* can
  enter ("whose source artefact no longer re-derives"), and (b) this law's own definition above.
  A pattern that indicts its own honest negations gets an exemption class, never an ignore flag.

### 0.4 Phase 0: capture the baseline before touching anything

Run these five, capture each exit code from the command itself, and write the block into
`docs/superpowers/specs/2026-10-15-autorate-certificate-platform-prd.ledger.md` (create it; commit
it before any source file changes). A pipeline's exit code is not its stages' exit code: redirect to
a log and `echo "NAME_EXIT=$?"` immediately after each command.

```bash
cd "$(git rev-parse --show-toplevel)"
git rev-parse --abbrev-ref HEAD; git rev-parse --short HEAD            # B1 identity
git status --short                                                      # B2 must be empty of others' work
uv run --frozen autorate verify --protocol protocol.json               # B3 the honesty gate
uv run --frozen autorate --help                                        # B4 the command surface
gh repo view --json visibility,stargazerCount                          # B5 the adoption blocker
```

Hard rule: if B3 does not exit `0`, **stop and report**. Do not build a product surface on a tree
that cannot reproduce its own published numbers - the platform would then be a way to distribute
uncertified claims, which is the exact failure this project exists to prevent.

Read the label off the tool's own output rather than assuming it: `verify` prints which lane it ran
(`corpus present` / `corpus absent`) and prints `re-derived N /M values`. Both are baseline facts,
and the product in Section 4 displays them.

### 0.5 Non-interference with the frozen chain (blocking rule)

This repository freezes a protocol and byte-compares published artefacts. The rule this PRD obeys:

> **NIF** - Nothing in milestones M1-M4 may change a file that `verify` compares, add a compared
> field, or add a published document, without being sequenced as a freeze round and agreed by the
> owner first.
> `check:` after your change, `uv run --frozen autorate verify --protocol protocol.json` still exits
> `0`, `git diff --name-only HEAD~1 -- data/ docs/` is empty, and the `re-derived N /M` denominators
> are **unchanged** from B3.
> `precondition:` you are editing this repo, not `autorate-portal`. If you need a change in the
> frozen surface (e.g. a `--format json` flag), you have hit the boundary: stop, write the request
> as a freeze-round item, and continue in `autorate-portal` instead.

`precondition` breach is not a judgment call. The project's own history shows why: a claim-note
digit is a value the loader reads, so correcting one sentence costs a re-freeze.

---

## 1. Why this product exists, and what was rejected

### 1.1 The market gap, stated as a test rather than a claim

Three observations, each re-derivable by a command in the snapshot:

1. The uncertainty/conformal-prediction ecosystem ships **libraries and no product surface**: the
   top results of `gh search repos --topic conformal-prediction --sort stars` are MAPIE, lists,
   notebooks, and research toolkits. Searching for a CP dashboard returns only near-zero-star
   one-project Streamlit apps.
2. The tools that *did* reach tens of thousands of stars in evaluation split cleanly by data shape:
   **trace stores became web platforms** (Langfuse, Phoenix, Evidently, MLflow), because their data
   is a continuous stream needing a queryable store; **one-shot verifiers stayed CLI plus badge**
   (OpenSSF Scorecard ships a CLI, an action and a badge with no first-party dashboard - snapshot
   Section 1.2, re-derive with `gh repo view ossf/scorecard --json stargazerCount`).
3. A maintained *standalone viewer for a machine-readable artefact* does not sustain a project:
   every `gh search repos "sbom viewer"` hit is near-zero stars. The viewer survives only as a
   feature of the producer.

So: the certification lane has no delivery surface, and copying the trace-platform shape is the
wrong answer for the *artefact* alone. The product decision below takes the platform shape - the
owner's call - and constrains it so it stays a delivery surface for certified artefacts rather than
becoming a second place where numbers can be manufactured.

### 1.2 The four axes, as answered

| Axis | Owner's answer (2026-10-15) | Author's recommendation | Cost accepted, and the mitigation |
|---|---|---|---|
| Surface | Self-hosted multi-user **web platform** (Langfuse-style) | Zero-backend three-layer (HTML packet + Action + badge) | Highest build cost, and it puts a database between the user and a re-derivable artefact. Mitigation: Section 4's invariants (I1-I6) make the platform a *reader and replayer* of evidence, never a calculator, so the platform's own state is always traceable to a packet. |
| Audience | **Business and compliance** primary | Developers plus evidence consumers | These users cannot produce the evidence themselves; the funnel cold-starts on an engineer. Mitigation: F1 ingest is drag-a-file and the packet is a file an engineer can make in one command; every business-facing screen is labelled with the packet that produced it. |
| Permission | Full authorization through release | Adoption work autonomous, published numbers untouchable | The grant is honored (Section 8) with two carve-outs that are not engineering decisions: irreversible public exposure, and outbound messages to named third parties. |
| Sequencing | Parallel with freeze work; do not touch the published surface first | same | Accepted. Consequence encoded as rule **NIF** (Section 0.5) and as the reason `--format json` and the in-browser verifier moved to M5. |

### 1.3 Rejected alternatives, and what would make each correct

- **CLI plus documents only.** Correct if the audience is engineers alone. Rejected by the audience
  answer, and it fails the actual job: a compliance officer will not run `uv run --frozen`.
- **Static HTML certificate, no server.** Cheapest honest surface and still worth building (it is
  F9 inside this product rather than the product). Rejected as *the* answer because a business
  audience needs history, per-team access, and re-verification on a schedule, which a file cannot
  provide.
- **SaaS hosting by this project.** Rejected outright: it would put the project in the position of
  holding other teams' benchmark data and selling them assurance about it, which is a conflict of
  interest with the method's neutrality claim. See Section 3.4, non-goal NG6.

### 1.4 Competitive check you must run yourself before writing any positioning copy

The snapshot deliberately does **not** claim the space is empty. Commercial AI-governance suites
(Credo AI, Holistic AI, Modulos, trail and similar) appear in the same search results and target
the same compliance persona. Before Section 8's product copy is written, run:
`gh search repos "ai governance" --sort stars --limit 20`, plus one web search per named vendor, and
answer in the ledger: *which of them can produce a finite-sample bound with a stated denominator,
re-derivable by a stranger from a pinned wheel?* If the answer is "several", differentiation is the
re-derivability contract, not the dashboard, and the copy must say that.

---

## 2. Who it is for, and what it saves

### 2.1 Personas

Each persona names the trait, the scene, the job, and the concrete artifact they demand. `[to
measure: yours]` marks a number the executor must collect from a real deployment before it is used
in any pitch or business case; do not fill it with an invented value.

| # | Persona | Trait | Scene | Job to be done | Artifact they trust |
|---|---|---|---|---|---|
| P1 | Automation / support ops lead | Non-technical owner of an AI-deflection or auto-triage flow; budget holder for per-resolution pricing | Quarterly review of "how much can we safely automate"; vendor renegotiation | Know, with a number they can defend upward, what share of decisions may run unattended and what the error budget is | One screen: certified automation share, error budget, worst slice, and the date it was re-derived |
| P2 | AI governance / compliance officer | Owns ISO/IEC 42001 or internal AI-policy evidence; not a statistician | Preparing for a certification audit or an internal model-risk review | Attach evidence of *measured* performance and *documented limitations* to a control, without depending on a vendor's slide | An export bundle mapped to Annex IV / 42001 control lines, each with a source packet |
| P3 | Procurement / due-diligence reviewer | Evaluates a vendor's claimed rate; skeptical, time-poor | Reading a proposal that says "66% automated resolution" | Turn a marketing number into a question about its denominator and get a bounded answer or a clear "cannot be bounded" | The claim-vs-evidence view (F4), printable, showing the bound and its sampling error |
| P4 | Platform / ML engineer | Builds the router, triage or guardrail; lives in a terminal; the only persona who can *produce* evidence | CI on every model or threshold change | Make the gate mechanical instead of vibes: one command in, exit code decides, no hand-tuned confidence threshold | The CLI, the GitHub Action, the badge, the packet file |
| P5 | Independent auditor / assurance provider | Professional scepticism; may sell an agreed-upon-procedures engagement on AI accuracy today | Testing a client's performance claim | Re-derive the client's number without trusting the client's environment | `verify --protocol` against the pinned distribution, plus the packet's hashes |

P4 is retained as a first-class persona against the audience answer, and this is load-bearing
rather than a hedge: every business-facing screen is downstream of a packet P4 produced. The product
plan must therefore keep P4's path one command long, or P1-P3 have nothing to look at.

### 2.2 Value, expressed as mechanisms

1. **Money exposed by an unverified automation claim is computable.** With monthly automated
   resolutions `R` at price `p` per resolution (constants in snapshot Section 4) and true accuracy
   `a`, `R x p x (1 - a)` is what is paid for wrong outcomes. With a certificate - "at error budget
   `alpha`, at most `A` decisions are automated" - the exposure becomes bounded by `A x alpha`
   before pricing, which is the number a buyer can act on. The portal's job is to make `a` and the
   bound reproducible rather than vendor-asserted.
2. **Threshold calibration stops being a meeting.** The common deployment rule is a typed
   threshold on a `confidence` field. This project's own published audit lane measured that such a
   rule can miss at multiples of the rate its own documentation implies, and that same-named fields
   across two backends are not the same quantity (a fact the tool publishes; read it from
   `docs/AUDIT.md` and `verify`, do not quote it here). The product replaces "what should the
   threshold be?" with "what is my error budget, and what share certifies under it?"
3. **Evidence assembly for an audit stops being a document-scraping project.** F7 exports a bundle
   whose lines map to Annex IV / 42001 headings, each line carrying its source packet.
4. **Re-verification becomes scheduled, not manual.** F6 (Monitor) re-runs the tool against current
   traffic and reports drift with the tool's own exit code `4` semantics rather than a dashboard
   opinion.

### 2.3 Value to users beyond the buying organization

- A reviewer at a company evaluating an AI vendor can produce a bounded answer with a named
  denominator, which raises the price of unbounded claims.
- Because the worst-slice guarantee is a first-class object (F3), a deployment that averages well
  while failing one language group cannot be presented as working. That is a fairness outcome, not
  a cosmetic one, and it is why "worst-slice" belongs on the business screen rather than in a
  research appendix.
- The refusal path is a supported output, not a broken state: when the data cannot bound the claim,
  the product says so, which is the opposite of the incentive that produced this project's own
  zero-of-five published certificates.

### 2.4 Social value stated with its counter-metric

| Claim | Mechanism | Counter-metric that must also move (Section 9) |
|---|---|---|
| Automation becomes defensible rather than aspirational | Every share shown carries budget, denominator, bound, packet | CM1: count of displayed numbers with no packet provenance must stay **0** |
| Time saved on evidence assembly | F7 export replaces hand-built audit packs | CM2: exported lines whose source artefact no longer re-derives; must be 0 at export time |
| Less hidden subgroup harm | F3 refuses pooled-only presentation | CM3: screens showing a pooled number with no slice companion |
| Claims stay falsifiable after publication | packet + pinned wheel + `verify` | CM4: packets whose replay disagrees with the stored view (this is a *bug class*, and the plant test in Section 6.3 exists to prove it can fire) |

---

## 3. Product definition

### 3.1 Name and shape

**Autorate Portal.** Distribution `autorate-portal` on PyPI; console script `autorate-portal`;
import package `autorate_portal`; one container, one port, SQLite by default and PostgreSQL by
environment variable. Naming is an owner ask (Section 12, A3) - if it changes, only this line and
the CLI names change.

### 3.2 The four objects

| Object | Definition | Owner of truth |
|---|---|---|
| **Evidence Packet** | A content-addressed bundle of committed artefacts: `protocol.json`, every published certificate and generated document, a `manifest.json` with per-file SHA-256, the source pin (`autorate==<version>` plus the PyPI SHA-256, plus the git revision the release was cut from), the argv that produced the artefacts, and the exit code each command returned. A packet is **a bundler of what the CLI already writes** - it is not a new serializer, which is what keeps it off the frozen surface (rule NIF). | `manifest.json` |
| **Certificate view** | One decision task's `certify` output, rendered with `feasible`, the refusal reason, `autorate`, the bound, the unit the bound divides, and the group-conditional companion if present. Refusal renders as refusal (I3). | the packet's `data/*.json` |
| **Policy** | An operational rule derived from a certificate: which slices may auto-execute, at what budget, under which packet. A policy names its packet; when the packet is superseded the policy is *stale*, and staleness is visible. | the portal's DB, with the packet id recorded |
| **Monitor run** | A scheduled replay: the pinned distribution re-runs `verify` and/or `certify` against current records, and the result is stored as argv + exit code + artefact hashes. Drift is the tool's exit `4`, reported as such. | the run record |

### 3.3 Three surfaces, one product

| Surface | Audience | Ships in |
|---|---|---|
| `autorate` CLI (exists) | P4, P5 | unchanged during M1-M4 (NIF) |
| Portal web app (new repo) | P1, P2, P3, P4, P5 | M3-M5 |
| GitHub Action + badge + packet viewer (new) | P4 in CI, P3 as a public claim | M0, M5 |

### 3.4 Non-goals

- **NG1** Not a leaderboard or benchmark site. `fstandhartinger/jevbench` already occupies
  "benchmark and leaderboard for AI decision models"; competing there abandons the thesis.
- **NG2** Not a trace/observability store. No spans, no prompt logs, no per-request storage.
- **NG3** Not an inference host. The portal never loads a model. Records come from a packet or an
  ingest that already has gold labels.
- **NG4** Not a general experiment tracker (that is MLflow's).
- **NG5** Not a BI tool. It renders artefacts; it does not chart arbitrary columns.
- **NG6** No first-party SaaS holding customer data (Section 1.3).
- **NG7** No computed statistics in the web tier (I1). This is a non-goal *and* an invariant because
  it is where a normal dashboard would put them.

---

## 4. Architecture

### 4.1 Invariants (absolute; each has a falsification, Section 6)

- **I1 - the portal never computes a statistic.** No bound, no rate, no mean, no aggregation is
  calculated in the web tier or its ORM layer. Every number is read from a packet artefact or from a
  replay run produced by the pinned distribution. The only arithmetic permitted is *counting*
  (rows, packets, bytes) and *percent-of-total* of an already-published pair, labelled as such.
- **I2 - no number without its triple.** Any rendered statistic carries, in the same component, the
  denominator it divides, the budget/rubric it was computed under, and the packet id plus protocol
  digest it came from. A screen that cannot show all three renders the number as unavailable.
- **I3 - a refusal renders as a refusal.** Exit `3` (`not_certifiable`) and `NOT_INFORMATIVE` states
  are first-class render states with their own visual identity. Mapping a refusal to a zero, an
  em-dash, a blank chart, or a neutral "no data" card is a defect by definition. The product's first
  honest screen, on this repository's own packets, is a refusal set - the design must be good at
  showing that, because the alternative is a product that only looks useful when the answer is
  flattering.
- **I4 - no cross-freeze aggregation without a boundary.** Two numbers under different protocol
  digests never share an axis or a delta unless the boundary is drawn and both digests are named.
  Trends chart within one digest.
- **I5 - history is replay, not inference.** The portal stores what the tool said at a revision; it
  never derives "what it would have said" from stored summaries.
- **I6 - the chain to a stranger is closed.** A packet is verifiable by someone who has the packet,
  network access to PyPI, and Docker, with no access to the producing organization. If that claim
  cannot be demonstrated in CI, the product does not have its differentiator.

### 4.2 Stack decision

FastAPI app serving a REST API and a built single-page client from one process; SQLAlchemy models on
SQLite (default file location) with PostgreSQL via one environment variable; `uv` for install;
Alembic for migrations; Pydantic for the packet manifest contract; the replay engine shells out to
the pinned distribution inside a container (Docker or Podman) or, for the CLI-only path, an isolated
`uv` environment.

Rejected: a Langfuse-shaped topology (web plus worker plus PostgreSQL plus ClickHouse plus Redis plus
object store). It is the right shape for a trace store and the wrong shape for a product whose
adoption test is "one `docker run`, then drag a file in". Precedent for the chosen shape - single
process, SQLAlchemy back end with SQLite as the default store - is read from MLflow's and Phoenix's
own configuration source in snapshot Section 2.

### 4.3 Data model (columns that carry the invariants)

```
org(id,name) -> project(id,org_id,name) -> packet(id,project_id,manifest_sha256,protocol_digest,
   source_version,source_sha256,source_revision,created_by,ingested_at,bytes,retention_until)
artifact(id,packet_id,path,sha256,kind)                 -- kind: certificate|document|records|protocol|transcript
certificate_summary(id,artifact_id,task,backend,feasible,reason,autorate,bound,
   bound_unit,n_cal,n_eval,n_claims,alpha,beta,delta)     -- every field sourced; NULL allowed only where
                                                          -- the artefact itself omits it, and then rendered absent
run(id,project_id,argv,exit_code,started_at,digest_then,stdout_sha256,packet_id_in)
policy(id,project_id,name,packet_id,slices,budget,state[active|stale|superseded],stale_because)
monitor_result(id,run_id,verdict,drift_detail_artifact_id)
user(id,email,display) -> membership(user_id,org_id,role[viewer|producer|compliance|admin])
api_token(id,user_id,project_id,hash,scopes,created_at,last_used_at)
export_bundle(id,project_id,kind[annex_iv|iso_42001|aap],packet_ids,manifest_sha256)
```

**I1 enforcement at the schema level:** `certificate_summary` is populated *only* by the packet
parser or by a run's captured output; there is no code path that writes a bound from application
arithmetic. A migration or ORM event that adds such a path is the plant target in Section 6.3.

**Tenant isolation:** every query is scoped by `project_id` derived from the session or token; no
cross-project aggregate endpoint exists at all (not "restricted" - absent). Records files inside a
packet may contain customer conversations, so packets are org-private by default and the
public-share path in F9 shares a *rendered view*, not the records artefacts (see Section 8.4).

### 4.4 API surface (minimum for M3-M4)

```
POST   /api/v1/packets                 multipart packet bundle -> ingest, hash, parse, index
GET    /api/v1/packets/{id}            manifest + provenance
GET    /api/v1/packets/{id}/artifacts/{artifactId}   raw artefact download
GET    /api/v1/certificates?project=   summaries, never computed
GET    /api/v1/certificates/{id}/slices             group-conditional companion
POST   /api/v1/runs                    {argv, packet_id} -> replay job; 202 with run id
GET    /api/v1/runs/{id}               exit code, stdout hash, diff-vs-stored summary
GET    /api/v1/runs/{id}/report        machine-readable parity report (I6 evidence)
POST   /api/v1/policies | GET /api/v1/policies/{id}.well-known  SDK pull, no auth for read-only public policy docs
POST   /api/v1/claims/check            P3 path: vendor claim text -> matched evidence or "cannot bound"
POST   /api/v1/exports/{kind}          Annex IV / 42001 / auditor bundle
GET    /healthz | /version             version + pinned autorate version
```

Auth: session cookie for humans, project-scoped API tokens for automation. Roles per Section 4.5.
Every mutating endpoint writes an audit row (actor, project, target, timestamp).

### 4.5 Permission matrix

| Capability | viewer (P1/P3) | producer (P4) | compliance (P2) | admin | auditor (P5) |
|---|---|---|---|---|---|
| Read certificate and slice views | yes | yes | yes | yes | within granted project |
| Download raw artefacts of a packet | protocol + digests only | yes | yes | yes | yes |
| Ingest a packet | no | yes | no | yes | no |
| Start a replay run | no | yes | yes (read-only replay) | yes | yes |
| Create/edit a policy | no | yes | no | yes | no |
| Export an audit bundle | no | no | yes | yes | yes |
| Manage members, retention, secrets | no | no | no | yes | no |

### 4.6 Deployment and operations

- One container; volume for SQLite plus the packet store; environment for `AUTHORATE_DB_URL`,
  `AUTHORATE_SECRET_KEY`, token hash salt, retention days. No outbound calls except PyPI at replay
  time (an air-gapped option: vendor the pinned wheel into the packet; F1 accepts an embedded wheel
  and hashes it).
- `autorate-portal doctor` prints: version, DB backend, pinned `autorate` version resolvable, Docker
  or `uv` availability, and one self-test replay against a fixture packet. This command is the first
  thing a new user runs and the thing CI asserts on.
- Backwards compatibility: the packet manifest carries `manifest_version`; the parser refuses an
  unknown version with a named error rather than parsing leniently (this mirrors the rule already
  enforced in the frozen repo's reader contract, where a malformed input is a named refusal mapped
  to a distinct exit code).

### 4.7 Recorded deviation from the PRD template

The generic PRD template forbids naming a database or a framework. This PRD names them, on purpose:
for an agent-executed product, **I1 is an architectural constraint, not an implementation
preference** - a "how to implement" that is left open is how a dashboard ends up computing a bound in
a SQL `AVG` and shipping an uncertifiable number. The template's other red lines are honored: no
invented business data (Section 2.1 marks what must be measured), no UI cosmetics (Section 5 specifies
information hierarchy and states, not colors), and every role's view is covered.

---

## 5. Functional specification

Format per feature: description, story, priority, business rules (exhaustive), interaction flow,
exceptions. Acceptance criteria in Section 5.11.

### F1 Packet ingest and registry - P0 (M3)
**Story:** as P4, I want to drop a packet file so my team can read what my CI produced.
**Rules.** (1) A packet is accepted only if `manifest.json` parses, every listed path exists in the
bundle, every SHA-256 matches, and `protocol_digest` is present. (2) Any mismatch is a named refusal
with the offending path and both hashes; the packet is not partially indexed. (3) Records artefacts
are stored but never rendered row-level to `viewer` (Section 4.5). (4) Re-ingesting a packet with the
same `manifest_sha256` is idempotent. (5) A packet whose embedded wheel hash differs from the
distributed wheel is accepted with `unverified_provenance` and rendered with that badge.
**Flow.** Projects > Ingest > drop `.tar`/`.zip` > progress (hash, unpack, parse, index) >
result is the certificate view of that packet; failures land on the same screen with the named
refusal.
**Exceptions.** (a) Bundle larger than configured cap -> refuse with the byte count and the cap.
(b) Path traversal in an entry (`..`) -> refuse the whole packet, log the actor. (c) Duplicate id
inside a records artefact -> the packet's own tool refused to produce it; if seen, mark
`inconsistent_bundle` and block the certificate view rather than showing a partial one.

### F2 Certificate view with refusal semantics - P0 (M3)
**Story:** as P1, I want one screen that tells me what may run unattended and how sure that is.
**Rules.** (1) Header shows task, backend, `feasible`, and for a refusal the reason verbatim from the
artefact - never a paraphrase. (2) When `feasible`, show `autorate`, `alpha`, `beta`, the bound, the
bound's **unit** (case or record, read from the artefact, per the frozen repo's own denominator
discipline), and `n_cal`/`n_eval`. (3) When the artefact publishes both one-sided and two-sided
bounds, show both, labelled. (4) If the artefact contains `closest_attempt` or an equivalent
diagnostic block, render it only under an explicitly labelled "selected on the evaluation half;
nothing on it was certified" disclosure, matching the artefact's own `diagnostic_note`. Selecting a
near-miss into a headline is the defect this project's rulings exist to prevent. (5) Numbers come
from the parsed artefact; the client formats, never recalculates.
**Flow.** Open project > Certificates table (task, status badge, budget, bound+unit, packet,
ingested) > row opens the view > "why not certifiable" panel for refusals > provenance drawer.
**Exceptions.** (a) Field missing from artefact -> render "not published by this certificate" (never
0). (b) Artefact kind unrecognised -> view disabled with reason. (c) Stored summary disagrees with a
fresh replay -> banner "provenance mismatch" naming both digests, and the number is struck through.

### F3 Worst-slice view - P0 (M3)
**Story:** as P1/P2, I want to see whether a working average hides a failing group.
**Rules.** (1) A pooled certificate and its group-conditional companion are shown **side by side**; a
pooled number with no companion is labelled `no_slice_evidence`. (2) Slices are enumerated from the
artefact's declared keys, and each slice states its own denominator. (3) Where the simultaneous claim
refuses, that refusal is the headline for the companion panel. (4) If slice values look like repeated
views of the same underlying cases - which is a real property of multilingual corpora - the view
states the shared-item structure instead of implying independent samples; read the structure from the
artefact, and if it does not state it, print `independence not established`. (5) No Bonferroni or
other correction is applied in the portal (I1); the artefact's correction is displayed.
**Exceptions.** (a) Single-value slice key (a degenerate dimension) -> excluded with a note naming it.
(b) Slice count above a rendering cap -> top-N by smallest `n` plus "and K more", never truncated
silently.

### F4 Claim versus evidence - P0 (M4) - the business-facing killer feature
**Story:** as P3, someone says "we automate 66% of resolutions safely"; I want to know what that can
and cannot support.
**Rules.** (1) Input: a free-text or structured claim (share, the field it thresholds, the unit, the
population). (2) The check compares the claim against an ingested certificate or the audit lane's
artefact, and returns one of exactly three verdicts: `bounded_supports`, `bounded_refutes`,
`cannot_be_bounded`, each with the bound, the denominator and the reason. (3) A verdict of
`cannot_be_bounded` must explain what additional data would bound it, reading the need from the
artefact's published feasibility arithmetic where present; if absent, it says so instead of
inventing a sample size. (4) Never output a point estimate the packet did not publish. (5) Every
verdict is exportable with its provenance line (I2).
**Flow.** Home > "Check a claim" > three fields > verdict card > "send this to procurement" export.
**Exceptions.** (a) Claim names a field the packet never measured (e.g. a differently-defined
`confidence`) -> `cannot_be_bounded` plus the comparability statement, because same-named fields are
not the same quantity. (b) No packet in project -> route to F1 with the one command P4 needs.
(c) Claim share exceeds the certified `autorate` -> `bounded_refutes` with both numbers and units.

### F5 Evidence export for auditors - P0 (M4)
**Story:** as P2, I need performance and limitations evidence attached to a control, with a source I
can re-open a year later.
**Rules.** (1) Bundle kinds: `annex_iv`, `iso_42001`, `generic_aap`. (2) Each bundle line names the
source artefact path, its SHA-256, the protocol digest and the packet id - a line without a source
fails the build of the bundle. (3) `known_limits` from `protocol.json` is rendered as its own section
and cannot be omitted from a bundle (the mapping is present, not configurable away). (4) A bundle is
deterministic: same packet plus same template yields byte-identical output, and the export records
its own hash. (5) Exports are logged with actor and target.
**Exceptions.** (a) Source artefact no longer re-derives at export time -> export blocked with the
run id that showed the mismatch. (b) Requested bundle kind has no mapping for a required heading ->
emit the heading with `no evidence published`, which is honest and is also what an auditor expects to
see for a real gap.

### F6 Monitor and drift - P1 (M5)
**Story:** as P4, I want to know when the world moved and my certificate stopped describing it.
**Rules.** (1) A monitor is a scheduled replay (F-M2 engine), not an in-app calculation. (2) Verdict
vocabulary is the CLI's: exit `0` holds, `3` not certifiable, `4` drift, `2` usage - a usage error is
surfaced as a configuration bug, not as a red KPI. (3) Alert copy quotes the tool's own summary line.
(4) Frequency is per project, with a hard rule that a monitor run never mutates a stored summary: it
writes a `run` and a `monitor_result` only.
**Exceptions.** (a) Replay environment unavailable -> `not_run`, with the doctor output; never
`green`. (b) Replay exceeds timeout -> `not_run` plus partial stdout hash. (c) New records ingest
whose ids collide with an existing calibration pool's case ids -> refused with the collision named,
because a key-domain change silently re-rolls a seeded split, and a re-rolled split changes published
bounds.

### F7 Policies and enforcement - P1 (M5)
**Story:** as P1, I want the automation rule to be a versioned object, not code in a router.
**Rules.** (1) A policy names its packet and budget. (2) `GET /api/v1/policies/{id}.well-known`
returns the machine-readable policy an SDK or gateway fetches, shaped like the CLI's `gate` output
(`action`, `label` per decision). (3) A policy is `stale` when its packet's protocol digest is
superseded in the project or a monitor reported drift; staleness appears in the SDK payload, so a
router can refuse to act on stale policy by configuration. (4) Editing a policy creates a version;
nothing is overwritten. (5) No policy may express a budget the source certificate does not publish.
**Exceptions.** (a) SDK requests a stale policy with `strict=1` -> 409 with the reason. (b) Policy
references a slice value absent from the artefact -> creation refused, naming the value.

### F8 Distribution: GitHub Action and badge - P0 (M0)
**Story:** as P4, I want the gate in CI and the result on the README so a stranger sees it before
they ask me.
**Rules.** (1) Action inputs: `ref` or `version` of the pinned distribution, `alpha`, `beta`, `path`
to `protocol.json`, `fail_on` (default: exit `4` fails, exit `3` is a reported result - because
`not_certifiable` is an outcome, not a broken pipeline; the choice is configurable and the default is
documented in the action README). (2) The step prints the tool's `re-derived N /M values` line
verbatim into the job summary. (3) Badge states the honest status vocabulary (`certified`,
`not-certifiable`, `drift`, `not-run`), never a boolean. (4) PR comment for a diff of bound vs
previous bound with both denominators. (5) The action shells out; it implements no statistics.
**Exceptions.** (a) Shallow checkout breaking a `git show <rev>:protocol.json` read - this already
bites once in the frozen repo's own CI, so the action must use full history or read from the working
tree, and assert which it did. (b) Runner without network to PyPI -> `not-run`, not pass.

### F9 Self-contained HTML packet viewer and share link - P1 (M5)
**Story:** as P3, I was sent a file, not a URL.
**Rules.** (1) One HTML file, no backend, no CDN: `autorate-portal packet html packet.tar -o cert.html`
embeds the parsed artefacts plus the manifest hashes and renders Sections 5's F2/F3 semantics.
(2) It shows the reproduction command and the pinned version, so the reader can escalate to a replay.
(3) A share link in the portal renders the same view but never exposes records artefacts; it carries
an expiry and the packet id in the URL title for auditability. (4) The HTML is generated from the
same component contract as the web view - one renderer, two targets - because two renderers drift,
and a drifted copy of a certificate is a misrepresentation.
**Exceptions.** (a) Artefact too large to embed -> link out to the download and state which artefacts
were omitted. (b) Packet with `unverified_provenance` -> the badge is rendered into the HTML, so the
shareable copy cannot lose it.

### F10 Administration - P1 (M5)
Orgs, projects, members, roles, tokens with scopes and last-used, retention policy, deletion
(tombstone plus byte removal), audit log export, and a "pinned distribution" registry so an operator
can pin or upgrade the `autorate` version replays use. Self-hosted means the operator, not this
project, holds keys; default configuration must not require any credential from the project.

### 5.11 Acceptance criteria (Given/When/Then; each maps to Section 6 tests)

| # | Given | When | Then |
|---|---|---|---|
| AC1 | a bundle with one tampered artefact byte | ingest | refused, named path, both hashes, nothing indexed (`packet.*` rc 4 analogue) |
| AC2 | a packet whose certificates all refuse | open the certificate view | every row renders a refusal reason from the artefact; no zero, no blank, no "no data" |
| AC3 | a certificate publishing `autorate` with a case-level bound | read the number | unit, budget, `n_cal`/`n_eval`, packet id, protocol digest all visible in the same component |
| AC4 | a stored summary and a fresh replay disagree | view the certificate | mismatch banner names both digests; number struck through; export blocked |
| AC5 | a claim of a share above the certified value | check the claim | `bounded_refutes` with both numbers and units |
| AC6 | a claim on a field the packet never measured | check the claim | `cannot_be_bounded` plus the comparability statement |
| AC7 | an Annex IV export where the source no longer re-derives | build the bundle | blocked, with the run id |
| AC8 | two freezes in one project | open the trend | boundary drawn and both digests named, or the trend is not drawn |
| AC9 | a clean machine, a packet, Docker, PyPI access | run `autorate-portal verify-packet` | exit 0 and a report showing `re-derived N /N` matching the packet's stored N |
| AC10 | no Docker, no network | run the same | `not-run` with the reason; never a pass |
| AC11 | a policy whose packet got superseded | SDK fetch | `state: stale` in the payload; `strict=1` returns 409 |
| AC12 | a records file whose case ids collide with the calibration pool | ingest | refused naming the collision and the split-rollback consequence |
| AC13 | viewer role | request a records artefact | 403, and the denial is logged |
| AC14 | same packet re-ingested twice | list packets | one row, no duplicate artefacts |

---

## 6. Honesty requirements and how each is proven to be able to fail

A guard that cannot fail is decoration. Each invariant below gets a **plant**: a deliberately broken
input that must turn the corresponding check red, run in CI, and then reverted with a receipt that
the tree is back to its prior hash. Plants are proven *before* the feature is called done.

### 6.1 Invariant to enforcement map

| Inv | Enforcement | Plant that must make it red | Status |
|---|---|---|---|
| I1 no computation in app tier | static rule over `autorate_portal/**`: the only permitted numeric imports are formatting and hashing; ORM has no aggregate write | add a temporary `AVG`/`sum` that writes `certificate_summary.bound` | ACTIVE (M3) |
| I2 triple travels with the number | renderer contract: a statistic component refuses to render without `(denominator, rubric, packet)` - enforce at **emit** time in the renderer, not in a downstream test | drop `bound_unit` from a fixture artefact and assert the view renders "unavailable", not the number | ACTIVE (M2) |
| I3 refusal renders as refusal | state enum in the renderer with no numeric fallback; `NOT_CERTIFIABLE` and `NOT_INFORMATIVE` strings pass through verbatim | feed an all-refusal packet and assert no zero and no empty card | ACTIVE (M3) |
| I4 no cross-freeze aggregation | query layer rejects a series whose runs span two `protocol_digest` values without a boundary marker | seed two packets at different digests and open a trend | ACTIVE (M4) |
| I5 replay not inference | `run` rows carry argv plus exit code; no endpoint derives a bound from a summary | unit test that a replay's argv contains the pinned `autorate` invocation | ACTIVE (M2) |
| I6 stranger-verifiable | `verify-packet` in CI on a clean container with no repo access | swap the pinned wheel hash and expect rc!=0 | ACTIVE (M1) |

`Status` is a **liveness table** and is a required output of Phase 0 of every milestone: a rule whose
plant has not been run in this milestone's CI is `UNPROVEN` and may not be cited as satisfied. A rule
whose precondition no longer holds (e.g. I1's static rule after a renderer refactor) is `VOID` and
must be rewritten or deleted the same commit that voids it - not left as decoration.

### 6.2 Anti-decorative-control rules

- A negative control asserts the *removal landed* and the guarded comparison *fires*: prove both, and
  record the observed counts, not a boolean.
- A plant that fails to redden is a finding about the plant's mechanism, and it is reported with that
  mechanism. Do not delete the plant and do not weaken the invariant; explain why it did not fire.
- No new gate may be keyed to `HEAD` for a value it is validating in the change under test.
- Never add a `skip`, `xfail`, an ignore-list entry, or an exemption flag to get green. If a check
  cannot pass in an environment, that environment must produce a named `not-run` state.

### 6.3 Parity tests (the product's own integrity, not a style preference)

For each committed artefact in the frozen repository, a CI job ingests it and asserts the portal's
rendered values are **byte-equal after formatting** to the artefact's own values, and that
`verify`'s `re-derived N /M` line quoted in the UI matches a live run in the same job. Any missing
artefact in the CI fixture set fails with its name printed - a fixture list built by glob silently
passes on absence, which is the failure mode this exists to prevent.

---

## 7. Milestones

Each milestone ships working, testable software and produces its own implementation plan via
`superpowers:writing-plans` (`docs/superpowers/plans/YYYY-MM-DD-<milestone>.md`), one plan per
milestone, tasks at test-cycle size. This PRD is the spec; the plans are the task lists.

**Reordering note, stated rather than hidden:** the approved outline put `--format json` in M0. It
moved to M5 because Section 4's packet is a *bundler* of existing artefacts, so no CLI change is
needed for M1-M4 - and `cli.py` sits on the frozen chain, where NIF applies. Publishing moved to M0
because a GitHub Action and a pinned-wheel replay both require a resolvable release.

| ID | Deliverable | Repo | Gate (definition of done) | Rollback point |
|---|---|---|---|---|
| **M0** Publish path | `LICENSE` (canonical Apache-2.0 text, fetched and proven byte-exact against a trusted copy - never retyped) **[done; recorded in 13.8]**; in-repo GitHub Action + badge, built against the private repo **[unblocked]**; git tag + PyPI release **[BLOCKED on A4 and A7 - see the corrected order in 8.1]**; `autorate-portal` scaffold repo **[blocked on A3 being executed as a public repo, so after A4]** | both | `autorate verify --protocol protocol.json` from the **installed** package exits 0 and prints the same denominators as B3; action runs on a real PR and prints `re-derived N /M`; badge renders; `verify` denominators unchanged from B3 | a PyPI release is forever: tag before publishing, and record the wheel SHA-256 in the ledger |
| **M1** Evidence Packet | manifest contract (Pydantic), `autorate-portal packet build|verify|html`, one packet built from this repo's committed artefacts, `verify-packet` replay in a container | portal | AC1, AC9, AC10, AC14 pass; I6 plant fires; packet builds reproducibly from a clean checkout of the pinned revision | packet contract is additive; the frozen repo is untouched |
| **M2** Replay engine | job runner with argv/exit-code/stdout-hash capture, pinned-distribution registry, `doctor` | portal | AC4 (mismatch path) provable; run rows always carry argv; no endpoint computes a bound | engine is the only place with execution rights; if it fails, views degrade to "not run" |
| **M3** Portal core | auth, orgs/projects, F1 ingest, F2 certificate view, F3 slice view, provenance drawer | portal | AC2, AC3, AC13, AC14; the frozen repo's committed artefacts render correctly end-to-end; parity job (6.3) green | read-only deployment first (no policies yet) |
| **M4** Audience features | F4 claim check, F5 audit export, badge-as-shareable, localization pass (Section 11's `Localization` row; second language fixed by A6) | portal | AC5, AC6, AC7, AC8, AC11; a P1 and a P2 walkthrough completed with an external reader | F4/F5 are additive views over M3's data |
| **M5** Enforcement, monitor, in-browser verifier, `--format json` | F6, F7, F9, F10; Pyodide certificate self-checker reusing the *published* `verify` module; the frozen repo's `--format json` as one freeze round | portal + **frozen repo** | AC12; browser checker's verdict equals the container replay's for the same packet; freeze round for `--format json` passes with denominators **unchanged** and a recorded justification for adding a compared field or not | the browser checker must degrade to "replay required" if the wheel cannot be fetched |

**Sequencing rules.** M5's frozen-repo items go through a freeze round; nothing in M0-M4 touches
`data/` or the byte-compared `docs/`. If a milestone needs a change that would move a published
artefact, it is re-planned as a freeze round and the owner is asked, per the approved axis answer.

---

## 8. Release, distribution, and public exposure

### 8.1 The order that is load-bearing

**Corrected 2026-10-15, after the first draft's order turned out to be wrong in execution.** The draft
read `LICENSE -> tag -> PyPI -> Action + badge -> portal -> visibility -> upstream`, on the theory that
visibility should come last. Writing M0 exposed the flaw: **a PyPI release is itself the irreversible
public exposure** - the sdist ships the README, and the README quotes measured weaknesses of the upstream
model - and a package whose `project_urls` point at a private repository is incoherent for the only person
the badge is for. So visibility is not the last step; it is the *gate* that PyPI, the marketplace action
and the share links all sit behind.

`LICENSE` (done, no dependency) -> in-repo Action + badge, built and tested against the private repo
-> **owner's four-part instruction on the upstream filing** (hold (b)) -> upstream issue filed ->
**repository visibility** -> PyPI release -> tag -> portal M1-M4.

The PyPI arrow needs a publishing credential. Check for one before planning around it:
`ls ~/.pypirc; env | grep -icE "TWINE|PYPI"; python3 -c "import importlib.util as u; print(u.find_spec('twine'))"`.
None was present when this section was written, and the right instrument is a project-scoped API token,
not a username and password.

Nothing in that chain after `LICENSE` may be inferred as authorized: each arrow is either a human
decision or a credential the owner must create.

### 8.2 Pre-flight for any publish (blocking)

- **Two-stage credential scan, not one.** The naive pattern `grep -rniE "(token|secret|passwd|password|
  api[_-]?key|BEGIN [A-Z]+ PRIVATE KEY)"` measured **10 matching tracked files** on 2026-10-15 and **zero
  real credentials**: the hits are MASSIVE dataset utterances ("keep playing secret garden", "chamber of
  secrets f\u00fcr mich"), token *counts* (`state_tokens`, `input_tokens`), and the repo's own guard names
  (`test_no_artefact_carries_a_secret_shaped_string`). Reading only stage one and demanding "zero hits
  before a flip" therefore sends the executor hunting for secrets that do not exist, or worse, tempts an
  ignore list. Stage two is the decision: `grep -nE "(api[_-]?key|secret|token|password)[\"' ]*[:=][\"'
  ]*[A-Za-z0-9_\-]{12,}"` over `git ls-files` - assignment-shaped, high-entropy - which returned empty, and
  that emptiness is the pass condition. Add a GitHub secret-scanning pass on the pushed branch. Any real
  hit is removed from history, not deleted in a follow-up commit.
- No absolute path literal that names a machine - an operator's home directory or a per-user macOS temp
  shape - in tracked files. This project has been bitten by exactly that twice (a CI failure, and this
  document's own first draft, which the export lane caught), so the check runs against the **pushed
  object**, not the working copy, and it needs the manifest recipe in Section 13.1 to have a subject
  outside a git checkout.
- `git status` after the last `git add`: verify the committed object with `git show --stat`, not the
  working file. A directory glob has previously shipped half a change.
- Gates run **after** commit for new files: a pre-commit gate never scanned the new file, so run each
  guard with the new paths given explicitly, and report the exit code of each.

### 8.3 Pre-flight before flipping to public (owner-reading item, carve-out (a))

1. Read every sentence in `docs/`, `README.md` and the portal's copy that describes the upstream
   model or vendor, and confirm each is (i) attributed, (ii) current against the upstream's present
   code, and (iii) free of any figure that `verify` does not re-derive. Where upstream has since
   fixed a finding, the sentence is corrected or dropped before exposure - not annotated.
2. Confirm `ERRATA` is append-only and no dated entry was rewritten.
3. Confirm the privacy rule in Section 8.4 is implemented before any share link is enabled.
4. Present items 1-3 as a checklist result and **stop**: hold (a) in Section 0.2 keeps the flip itself
   outside this document's authority until the upstream filing is resolved, because the 2026-10-01
   decision conditions visibility on findings having been filed first.

### 8.4 Data and privacy rules for shared artefacts

Records files can contain real customer conversations and gold labels. Therefore: public shares
expose certificates, bounds, denominators and digests - never records rows. Packet bundles are
org-private by default; an explicitly marked "shareable" bundle excludes records and states that it
does. Retention defaults to a bounded number of days for records artefacts, configurable per project.

### 8.5 Adoption channels, in cost order

1. ~~`awesome-jev-tools` entry.~~ **Withdrawn.** `docs/upstream/awesome-jev-entry.md` is a committed
   `OMITTED` decision record, and nothing in this PRD overturns it: the entry's only claim worth printing
   would assert a certificate that travels with an answer, while `protocol.json` records G1 as
   `not_certifiable`, G4 as `not_met`, and `known_limits` says *"no certificate exists, so no action is
   certified"*. A portal that displays refusals beautifully is still not a certificate, so shipping M1-M5
   does **not** re-open this channel. What re-opens it is a `verified` row in `docs/VERIFICATION.md`
   describing a shipped `autorate` surface that certifies something. Until then the honest move is to
   quote that list's own adoption checklist in our README rather than ask to be listed in it.
   Re-derive the record before repeating any of this:
   `sed -n '1,40p' docs/upstream/awesome-jev-entry.md`.
2. GitHub Action marketplace listing (P4 finds gates in the marketplace before they find blogs).
3. `laya` ecosystem integration docs: the Node/TypeScript and local-runtime projects are the largest
   untapped P4 population; a packet built by any runtime is the same packet, so the portal is
   language-agnostic - say this once, in the README, with the manifest contract as proof.
4. Upstream `laya` issue/PR (carve-out (b): print the payload, re-verify against the current tree).
5. Compliance-audience channels via F5's export mapping (Annex IV, 42001) rather than via a
   benchmark argument.

---

## 9. Success metrics

North-star: **packets that were re-derived by someone other than their producer, per week** - it is
the only metric that rises when the product's differentiator is actually used.

| Tier | Metric | Definition | Target at +90 days |
|---|---|---|---|
| Driver | `ingest_to_first_view_seconds` | median from packet drop to rendered certificate view | one command's worth: <= 30 s |
| Driver | projects with >= 1 monitor run | `run` rows with `kind=monitor` per project | 25% of active projects |
| Driver | actions installed | installs of the composite action | tracked, no target set before a baseline exists |
| Driver | export bundles built | `export_bundle` rows by kind | 1 per active compliance project |
| Health | `doctor` success rate | doctor exit 0 / runs | >= 95% |
| Health | replay failure taxonomy | runs by exit code, `not-run` separated from `4` | `not-run` reported, never folded into pass |
| **Counter** | CM1 numbers without provenance | rendered statistics missing any member of the I2 triple | **0** (blocking release metric) |
| **Counter** | CM2 stale export lines | bundle lines whose source failed to re-derive at build | **0** |
| **Counter** | CM3 pooled-without-slice screens | views showing a pooled figure and no companion or `no_slice_evidence` label | 0 |
| **Counter** | CM4 provenance mismatches | stored summary vs replay disagreements per week | reported with cause, not suppressed |
| Integrity | claim-check verdict distribution | share of `cannot_be_bounded` | **no target** - a product tuned to make this rarer has been captured. Tracked and reviewed. |
| Adoption | external packet producers | orgs distinct from the owner's | tracked; the honest floor is that a refusal-heavy first screen costs conversion (see R1) |

Targets marked "tracked, no target" are refusals to invent a number before a baseline exists; that is
a deliberate feature of this PRD, and any revision that fills them must cite a measurement.

---

## 10. Instrumentation

Events (server-side, product analytics for a self-hosted product must be **opt-in per project**, off
by default; a deployment that phones home is disqualified for the compliance persona):
`packet_ingested {bytes, artifact_count, manifest_version, outcome, refusal_code}`,
`certificate_viewed {task, status, has_slice_companion}`,
`claim_checked {verdict, matched_artifact_present}`,
`export_built {kind, line_count, blocked}`, `run_completed {exit_code, duration_ms, lane_label}`,
`policy_fetched {state}`, `doctor_ran {ok, missing[]}`.
Attributes are ids and enums only: no record content, no customer text, no email. Every event names
its denominator source so a count in the UI is derivable from the event table, not from a second
pipeline.

---

## 11. Non-functional requirements

| Category | Requirement | Acceptance |
|---|---|---|
| Deployment | one `docker run`, SQLite default, Postgres by env var; no external service is mandatory | `docker run` then `doctor` rc 0, from a clean machine, in CI |
| Cold start | a new user with a packet sees a certificate view in <= 3 actions | walkthrough test, AC1-AC3 |
| Performance | a project with 200 packets and 1,000 artefacts renders the certificate list in < 1.5 s server-side; no N+1 | load fixture in CI with a named threshold |
| Availability | a failed replay never shows a stale number as current | I2/I5 tests, AC4 |
| Security | tokens hashed, scoped, last-used tracked; path traversal refused; audit log for mutations | Section 5 exceptions, AC13 |
| Secrets | no credential from this project is required for any feature | doctor asserts |
| Accessibility | WCAG 2.1 AA for the P1/P2/P3 views: keyboard-only walkthrough, contrast, status not signalled by colour alone (refusal vs certified must differ in text as well as hue) | axe pass plus a manual keyboard pass on F2/F3/F4 |
| Localization | the primary audience is international: at minimum English plus one second language shipped through one message catalog, no string concatenation for numbers, and unit words translated (a bound's unit mistranslated is a wrong claim) | catalog completeness test; screenshots of F2 in both languages in CI artifacts |
| Compatibility | Chrome/Safari current; the HTML viewer (F9) opens from `file://` with no network | test in both modes |
| Reproducibility | the HTML viewer and export bundle are deterministic for a given packet | double-build byte compare |
| Observability | every run stores argv, exit code, stdout hash | schema, AC10 |

---

## 12. Risks, dependencies, and owner asks

### 12.1 Risks

| ID | Risk | Severity | Mitigation | Early signal |
|---|---|---|---|---|
| R1 | **The honest first screen is a refusal set.** On this repository's own artefacts, a new user sees `not_certifiable` more often than a number, and a product that opens with refusals loses the business persona. | High | Make the refusal itself the deliverable in F2/F4 copy ("here is what can be proven, here is what cannot, and here is the sample size that would change it"); lead P1 screens with the audit lane, which does produce a decisive result on public claims; publish the feasibility ceiling as a first-class view. **Never** soften a claim or hide a refusal to fix conversion - that trades the product's only moat for a metric. | `ingest_to_first_view_seconds` fine, but day-7 return visits near zero |
| R2 | Platform drift from the CLI: a portal feature implies a capability the tool does not have. | High | NIF plus 6.3 parity job; the renderer contract reads only artefacts | a UI value with no artefact path |
| R3 | Scope creep into SaaS / trace store / leaderboard. | High | NG1-NG7; any feature request that needs per-request storage is refused by name in the plan | roadmap items referencing "traces" |
| R4 | Records data (customer conversations) in a multi-tenant store. | High | Section 8.4, role matrix, org-private default, retention | any `viewer` read path to records |
| R5 | Replay engine unavailable in air-gapped installs, so numbers freeze. | Medium | vendor the pinned wheel in the packet; `not-run` state, never stale-as-current | `not-run` rate climbing |
| R6 | Publishing a version with a defect is irreversible on PyPI. | Medium | tag first, yank policy documented, wheel sha recorded in the ledger | - |
| R7 | The frozen repo's CI is the same CI that gates the portal's fixture generation; a red round blocks M3's parity job. | Medium | portal fixtures are committed artefacts, regenerated only by an explicit job, not by every CI run | fixtures rebuilt in an unrelated PR |
| R8 | Another session is mid-freeze in this repo while you work; a shared dirty tree. | Medium | `git status` at B2, `git commit -- <paths>` with explicit paths, never `-A`; re-check `git worktree list` before editing anything under `docs/` | a file you did not touch appears in your diff |
| R9 | A long implementer run dies on quota or turn caps mid-milestone. | Medium | one milestone per session, ledger committed early, worktree per task, report to disk before any claim | a dispatch that reports success with no report file |
| R10 | Positioning copy overclaims relative to commercial governance suites. | Medium | Section 1.4's check runs before copy ships | any sentence containing "only", "first", "nobody" |

### 12.2 Dependencies

Docker or an isolated `uv` environment for replays (I6's whole basis); PyPI availability; a public
repository for the action's marketplace listing; the method spec and its rulings for every semantic
question; `awesome-jev-tools` inclusion rules; and one named external reader per persona group for
the usability pass in Section 13.2.

### 12.3 Owner asks - settled 2026-10-15 under the owner's delegation, and the two that cannot be

The owner delegated these ("follow your own recommendation"), so they are decided here with the reason
attached, and any of them is reversible by one sentence:

- **A1 SETTLED** - `LICENSE` holder = `Copyright 2026 the autorate authors`. This is the repository's own
  documented default, recorded in the landing plan precisely so that no agent names a person in a legal
  attribution; the first draft of this section wrongly pointed at a `COPYRIGHT RIGHTS` line in
  `docs/REPORT.md` Appendix A that does not exist (grep proved the tree's only occurrences were in this
  document). Change it to a personal or entity name before the PyPI release if you prefer; after the
  release the appendix line becomes history.
- **A2 SETTLED** - the version **stays `0.1.0`**. The README defines v1 by criteria G1-G5, and the frozen
  protocol prints G1 `not_certifiable`, G3 `not_measured`, G4 `not_met`. Cutting `1.0.0` would make the
  package version contradict the document it ships with, which is the one thing this project's method is
  not allowed to do. `1.0.0` is earned when the criteria are met, not when the portal exists.
- **A3 SETTLED** - `autorate-portal` as the distribution, repository and console-script name; the import
  package is `autorate_portal`. It is separable from `autorate` on purpose: the platform's web
  dependencies must never enter the frozen repo's `numpy`-only floor.
- **A5 SETTLED: no.** No hosted demo instance in v1. A demo is an operational commitment that turns this
  project into the party holding evidence about other parties, which is the conflict of interest
  Section 1.3 rejects; the self-contained HTML viewer (F9) is the shareable surface instead.
- **A6 SETTLED** - second language is Simplified Chinese (`zh-Hans`), shipped through one message
  catalog. Reason is concrete rather than demographic: the corpus this repository already certifies
  against includes a Chinese workplace benchmark, so the localization can be verified against real
  artefacts instead of translated lorem.
- **A4 NOT MINE TO DECIDE, and not yours to delegate blind.** Public visibility of
  `Jackxiaozhiren/autorate` is gated by your own 2026-10-01 decision (file the upstream findings first,
  then go public for citability) and by the four-part instruction `docs/upstream/SUBMISSION.md` demands.
  Answering those four items is what unblocks the chain; see Section 13.7.
- **A7 (new) NOT MINE TO DECIDE** - PyPI credentials. No publishing credential exists on this machine as
  of 2026-10-15 (`~/.pypirc` absent, no `TWINE_*`/`PYPI_*` env, `twine` not installed). Creating one is an
  account action, and it should be an API token scoped to the project, not a username/password.

---

## 13. Verification, reporting, and handoff

### 13.1 Gate matrix per milestone (count these in your report; do not describe them)

| Gate | Command | Must be |
|---|---|---|
| Frozen-repo non-interference | `uv run --frozen autorate verify --protocol protocol.json` | rc 0 and denominator line **identical to B3** for M0-M4; for M5's freeze round, unchanged unless the round was approved to change it |
| Published-artefact untouched | `git diff --name-only HEAD~1 -- data/ docs/` | empty (M0 except the `LICENSE` addition) |
| New-file coverage | each guard re-run **after** commit with explicit paths | rc 0 |
| Corpus-absent export lane (the only view that sees a new tracked file the way CI does) | `git archive HEAD \| tar -x -C <dir>`; then **`git ls-files > <dir>/.tracked-files`** (without the manifest the path guard refuses loudly with "nothing to scan" - that is the design, not a defect); then `AUTORATE_TRACKED_FILES=<dir>/.tracked-files uv run --frozen pytest` | 0 failed. Measured on 2026-10-15: `1117 passed, 35 skipped` at the fixed tip, after the same lane had caught one failure at the unfixed one |
| Portal suite | `uv run --frozen pytest -q` in the portal repo | 0 failures; the coverage floor never lowered |
| Invariant plants | Section 6.1's plant per ACTIVE row | each observed red, then reverted with a hash receipt |
| Parity | Section 6.3 job | byte-equal after formatting |
| Clean-machine reproducibility | fresh clone or container, `doctor` then AC9 | rc 0 |
| Leak test | Section 0.3 command | no unlabelled hits |
| Exit-code hygiene | every cited exit code taken from its own command with `echo "NAME_EXIT=$?"` | asserted in the test harness, not in prose |

### 13.2 Report format (mandatory sections; a report missing one is incomplete, not "mostly done")

`Milestone` / `Baseline block (B1-B5 verbatim)` / `Commands run with exit codes` / `AC ids proven, and
how` / `Liveness table (ACTIVE, UNPROVEN, VOID) with the plant evidence` / `Deviations from this PRD
with the reason and the section number` / `Numbers re-derived vs numbers transcribed` / `Deliberately
not done` / `Follow-ups with a named owner` / `Files added, and which guards were pointed at them`.

Externalize the review of each milestone to a fresh reviewer with the diff and this document's
section list, and have the report land on disk at a unique path before it is summarized in chat.

### 13.3 Self-review of this document (run before executing it)

1. **Coverage**: every Section 5 feature maps to at least one milestone in Section 7 and one AC in
   5.11 - a feature with no milestone is a plan gap, and a plan with no AC is unverifiable.
2. **Placeholders**: no "TBD"/"appropriate"/"similar to"; `[to measure: yours]` in Section 2 is a
   required *external* measurement and stays, but it may not appear in shipped copy.
3. **Type consistency**: `bound_unit`, `protocol_digest`, `manifest_sha256`, `packet_id` are the only
   spellings; the object names in 3.2 are the ones the API in 4.4 and the schema in 4.3 use.
4. **Phantom capabilities**: every symbol this document borrows from the frozen repository
   (`verify`, `certify`, `protocol.json` and its `claims[]`/`known_limits`/`rubric` keys, exit codes
   `0`/`2`/`3`/`4`, `re-derived N /M`, `docs/AUDIT.md`, `docs/SLICES.md`, `--groups`) was read from
   the tool's own `--help`, source, or output on 2026-10-15. Anything you cannot reproduce is not a
   capability you may build on.
5. **Size ratchet**: run `wc -l` on this file before and after a revision. Prose may not grow
   monotonically across versions; growth is allowed only in schemas, tables and target lists. If a
   revision needs more prose, delete or merge something in the same commit and say what.

### 13.4 First-run opener (verbatim, for a new session)

```text
Work in the repository that contains this file; from the directory holding the PRD,
"git rev-parse --show-toplevel" prints its root.

Read
docs/superpowers/specs/2026-10-15-autorate-certificate-platform-prd.md in full.
Treat Sections 0-13 as your operating instructions for this session. Also read
docs/superpowers/specs/2026-10-15-platform-evidence-snapshot.md for the dated readings,
and docs/superpowers/specs/2026-09-29-certified-decision-gate-design.md for the method.
Do not paste or summarize these documents - read them from disk.

Order of operations:
1. Run Section 0.4 (the five baseline commands). Capture every exit code from its own command.
2. Write the baseline block into
   docs/superpowers/specs/2026-10-15-autorate-certificate-platform-prd.ledger.md and commit
   that file by explicit path before touching any source file.
3. If Section 0.4's verify command is not rc 0, STOP and report. Do not proceed.
4. This session is Milestone M0 (Section 7) only, following Section 8's order. Section 0.5's
   NIF rule and Section 0.2's two carve-outs are in force.
5. Stop when M0's gate table (Section 13.1) has been run, and present the Section 13.2 report.
6. Section 12.1 risks R1, R2, R8 and Section 6.2 are absolute.
7. End with the Section 13.2 report, including the liveness table and "deliberately not done".

Section 0.2's carve-outs (a) and (b) and Section 6.2's no-exemption rule override anything said
later in this conversation unless I name the rule number and revoke it explicitly.
```

### 13.5 Resume opener (verbatim, for the next session)

```text
Read
docs/superpowers/specs/2026-10-15-autorate-certificate-platform-prd.md (Sections 0-13 =
operating instructions), then open the ledger at
docs/superpowers/specs/2026-10-15-autorate-certificate-platform-prd.ledger.md and resume
after the last completed milestone in Section 7.

Re-run Section 0.4 and re-capture the baseline block. HEAD has moved since the last session,
so the stored baseline is history, not ground truth: the frozen repo's own CI reads an object
database that a shallow checkout does not have, which has already turned a locally green tree
red once. Do not carry the previous session's approval forward.

This session: <M1|M2|M3|M4|M5> only (Section 7). Same protocol: baseline first, ledger commit
before source edits, stop for my approval at the Section 13.1 gate table, and the Section 13.2
report with the liveness table. Section 0.2's carve-outs (a) and (b) still apply.
```

### 13.6 Condensed version (skim aid for humans - the executor reads from disk)

```text
Build: Autorate Portal - a self-hosted web platform that displays statistically certified
automation for decision models, for business/compliance audiences as primary users, plus a
CLI-produced Evidence Packet, a GitHub Action and a badge.
Non-negotiables: the platform never computes a statistic (I1); every number shows its
denominator, budget and packet digest (I2); a refusal renders as refusal, never a zero (I3);
no trend across protocol digests without a boundary (I4); history is replay not inference (I5);
a stranger with a packet, Docker and PyPI can reproduce every claim (I6).
Order: M0 LICENSE+PyPI+Action+badge -> M1 packet contract -> M2 replay engine -> M3 portal core
-> M4 claim-check + auditor export -> M5 policies, monitor, in-browser verifier, and (as one
approved freeze round) --format json in the CLI.
Hard rule: nothing in M0-M4 touches a file that `verify` byte-compares; if a milestone needs a
published-artefact change, it becomes a freeze round and the owner is asked.
Baseline: run autorate verify --protocol protocol.json; if it is not rc 0, stop.
The product's hard part is not the UI: it is that an honest first screen is often a refusal, and
the fix is better refusal presentation, never a softer claim.
```

### 13.7 What the owner must answer to unblock the release chain

Written 2026-10-15 because the first draft of this document wrongly treated these as authorized.
`docs/upstream/SUBMISSION.md` requires the owner's own written instruction naming all four items below;
it states explicitly that a plan document, a green test suite, or the existence of that directory is not
the instruction. Each item is pre-filled with this document's recommendation, so answering "all four as
proposed" is sufficient - but item 4 must be re-measured, not copied, because its freshness is dated.

| # | What to answer | Recommendation |
|---|---|---|
| 1 | Target repository, and the exact text to file | `NandhaKishorM/laya`, filing `docs/upstream/issue.md` **as reduced**, i.e. the single live finding (`tests/test_packaging.py` cannot run from the published sdist). Do not file the original four: three describe code that has since moved |
| 2 | Branch / fork / PR | none in round one. The patch (`docs/upstream/patch/`, sha256 recorded beside it) is attached to the issue as a proposal, and a PR follows only if the maintainer asks - `pr-description.md` already says it must be rebased first |
| 3 | Who answers review comments afterwards | only the owner can say. If nobody commits to responding, the issue should not be opened, because an unanswered bug report against an active repository ages into noise and costs the credibility this project's thesis depends on |
| 4 | The date the re-measurements are fresh enough to act on | re-run the liveness check first: fetch current upstream `main` and confirm `tests/test_packaging.py` still reads repository files absent from the sdist. The existing measurement is dated 2026-10-14 and upstream moved the day this document was written |

Until items 1-4 come back, the executable surface of this PRD is: **M1's packet contract against the
private repo's committed artefacts, the in-repo Action and badge, and the portal scaffold under
`autorate-portal` only once item 4 permits the repository to go public.** PyPI, the tag, public
visibility, and any awesome-list interaction are not in that set.

### 13.8 Amendment log (dated, append-only)

What execution found wrong in this document, in the round that wrote it. Corrections go here rather than
silently editing the body, because the body's earlier wording was read by a human and approved.

**2026-10-15, same day as approval.** Commits `883b737` (this document plus the evidence snapshot) and
`5ea04aa` (path literals).

1. **Two phantom citations, both inherited rather than measured.** The body asserted a `COPYRIGHT RIGHTS`
   line in `docs/REPORT.md` Appendix A; `grep -rniE "copyright|rights reserved"` proved the tree's only
   occurrences were inside this document. It also asserted the repository had zero merge commits; on
   2026-10-15 the count was nonzero against 226 commits, so Section 0.2 now tells the executor to derive
   the convention rather than trust the sentence. Fix: both rewritten into commands.
2. **Three machine path literals in a tracked document**, caught only by the corpus-absent export lane,
   because the corpus-present suite had run *before* the commit while the files were still untracked - the
   new-file blind spot in its exact recorded form. Fix `5ea04aa`: the document resolves the repo root with
   `git rev-parse --show-toplevel`; the absolute path stays in the chat opener. Section 13.1 gains the
   manifest recipe so a future session cannot repeat it.
3. **`LICENSE` added** from the fetched canonical Apache-2.0 text, with provenance proved rather than
   asserted: identical to the on-disk copy, containing the vendored `laya-0.3.20/LICENSE` as a contiguous
   substring at offset 1, and a single-line delta on line 190 (the appendix placeholder replaced by the
   repository's own documented default holder, `Copyright 2026 the autorate authors`). No licence wording
   was typed by hand or memory.
4. **Section 8.1's ordering was wrong, found while executing M0.** The draft put PyPI before repository
   visibility; publishing is itself the irreversible exposure (the sdist carries the README, which quotes
   measured upstream weaknesses) and a package pointing at a private repo is incoherent for the badge's
   audience. Rewritten: visibility is a gate, not a last step, and it sits behind Section 13.7.
5. **Section 0.2 was too generous, twice.** Grant item 4 proposed submitting an `awesome-jev-tools` entry;
   `docs/upstream/awesome-jev-entry.md` is a committed `OMITTED` decision record whose premise 2 was
   measured false three times over, and shipping a portal does not repair it - only a `verified` row about
   a certifying shipped surface does. Carve-out (b) proposed "print the payload, then send" where
   `SUBMISSION.md` demands a four-part human instruction. Both corrected: the stricter existing bar wins,
   and Section 13.7 asks the owner to resolve it.
6. **Section 8.2's credential scan was unsatisfiable as written.** Its one-stage pattern matched 10
   tracked files that contain no credentials (dataset utterances, token counts, the names of the repo's own
   guards), so "zero hits before a flip" would have sent the executor hunting phantoms or tempted an ignore
   list. Now a two-stage scan whose pass condition is the emptiness of the assignment-shaped stage, with
   the measured false positives named.
7. **Two broken internal references** (`Section 11.4`, `Section 12's rails`) repointed; A1/A2/A3/A5/A6
   settled under the owner's delegation and recorded in Section 12.3 with the reason each is reversible by
   one sentence.
