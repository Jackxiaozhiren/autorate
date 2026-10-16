# Platform evidence snapshot — 2026-10-15

**Companion to** [`2026-10-15-autorate-certificate-platform-prd.md`](2026-10-15-autorate-certificate-platform-prd.md).
This file carries *telemetry*. The PRD body carries *constraints*. A reading that lives in the
PRD body is a defect: re-measure, and if the reading disagrees with the body, the body is wrong.

**How to use this snapshot.** Every line is a value observed on **2026-10-15** by the command
printed beside it. Before citing any value in a design argument, a spec, a README, or a PR
description, re-run the command and compare. Values decay: two reads of the same repository
counted one star apart within one minute on 2026-10-15 (see §1.1), and a repository's star count
is the least load-bearing example — the load-bearing ones are §3 (this repo's own gate output)
and §4 (the frozen protocol digest and claim statuses).

**Precedence rule.** `PRD §0.3` states it. Restated here because the executor reads this file
first: a stale citation in the PRD is corrected in the PRD, not annotated around.

---

## 1. Landscape readings (public GitHub, `gh` v2, authenticated as the repo owner)

Command shape for every row in §1.1–§1.3:
`gh repo view <slug> --json stargazerCount,forkCount,description,url`

### 1.1 Decision-model ecosystem

| Reading | Value (2026-10-15) | Slug |
|---|---|---|
| stars, forks | 32,970 / 2,960 | `NandhaKishorM/laya` |
| stars | 9,168 | `jaredpalmer/kev` |
| stars | 6,938 (`gh repo view`); 6,937 (`gh search repos`, one minute earlier) | `mizorewww/laya-mlx` |
| stars | 1,586 | `mizorewww/laya-coreml` |
| stars | 1,315 | `ollaya-dev/ollaya` |
| stars | 930 | `receptron/laya` (Node.js / TypeScript runtime) |
| stars | 742 | `v-modal/awesome-jev-tools` |
| stars | 422 | `PostHog/jeeves` |
| stars | 274 | `fstandhartinger/jevbench` — described as "benchmark and **leaderboard** for AI decision models" |
| stars | 52 | `apolinario/decision-index` |
| stars | not read | `gbesse/decision-claim-card` — README read instead, see §1.4 |

`gh repo view NandhaKishorM/laya --json stargazerCount,forkCount,updatedAt` also returned
`updatedAt = 2026-10-15T08:38:42Z`, i.e. the backend ecosystem is active on the day of writing.

### 1.2 Evaluation / observability tools, and what shape they ship

| Reading | Value | Slug | Shape observed |
|---|---|---|---|
| stars | 35,850 | `langfuse/langfuse` | self-hosted web platform |
| stars | 28,395 | `mlflow/mlflow` | self-hosted server + web UI |
| stars | 26,007 | `promptfoo/promptfoo` | CLI, plus `promptfoo view` local viewer |
| stars | 18,881 | `confident-ai/deepeval` | library + pytest plugin |
| stars | 11,842 | `Arize-ai/phoenix` | self-hosted web app |
| stars | 7,990 | `evidentlyai/evidently` | library + HTML reports + service |
| stars | 7,518 | `open-compass/opencompass` | evaluation platform |
| stars | 7,299 | `NVIDIA-NeMo/Guardrails` | toolkit |
| stars | 5,754 | `ossf/scorecard` | CLI + GitHub Action + badge, **no first-party dashboard** |
| stars | 1,602 | `scikit-learn-contrib/MAPIE` | library, **no UI** |
| stars | 1,325 | `valeman/awesome-conformal-prediction` | list |
| stars | 584 / 479 / 411 / 259 | `henrikbostrom/crepes` / `ml-stat-Sustech/TorchCP` / `deel-ai/puncc` / `yromano/cqr` | libraries, **no UI** |
| stars | 451 | `tensorflow/model-card-toolkit` | JSON schema → generated HTML/Markdown document |

### 1.3 Searches that returned *absence* (each is a claim about the gap, so each needs its command)

| Question | Command | Result |
|---|---|---|
| Does the conformal-prediction ecosystem ship a UI? | `gh search repos --topic conformal-prediction --sort stars --limit 20` | Top 20 are libraries, notebooks and one awesome-list. No product UI. |
| Any conformal-prediction dashboard? | `gh search repos "conformal prediction streamlit OR gradio dashboard" --sort stars --limit 12` | Highest hit 5 stars; remainder 0–3, all single-project student/toy repos. |
| Any generic "model evaluation dashboard"? | `gh search repos "model evaluation dashboard" --sort stars --limit 15` | Highest hit 1 star; Streamlit/Plotly boilerplate. Treated as saturated commodity, not a precedent. |
| Any maintained SBOM/artifact viewer? | `gh search repos "sbom viewer" --sort stars --limit 8` | Highest hit 2 stars. **Reading: a standalone viewer for a machine-readable artefact does not sustain a product; it survives as a feature of the producer.** |
| Any provenance-attestation viewer? | `gh search repos "provenance attestation verify" --sort stars --limit 8` | Empty result set. |
| Any third-party AI-accuracy attestation tool? | web search, see §5 | The offering is a *professional service* (accounting/audit firms), not software. |

### 1.4 Neighbour README readings (behaviour, not popularity)

- `v-modal/awesome-jev-tools` README (fetched via
  `gh api repos/v-modal/awesome-jev-tools/readme -H "Accept: application/vnd.github.raw"`):
  its adoption checklist asks, verbatim, *"Do the numbers have a source?"*, *"Is there a runnable
  check?"*, *"How much of the repository is code?"*, *"Is there a license?"* and states
  *"Inclusion is not an endorsement. We do not verify that a project compiles … or that its
  published numbers reproduce."* Category counts on 2026-10-15: Infra/SDKs 249,
  Classification & Routing 109, Related Practices 97, Verification & Guardrails 96, CLI & Pipelines
  80, Agent Decisions 80, Domain Tools 79, Evaluation & Benchmarking 58, Calibration & Research 48,
  Browser & OS Action 48, Data & Search 44, Context GC 36, Scoring & Ranking 29, Creative Tools 24,
  Code Navigation 14, Finance & Trading 6, Content Moderation 7, Adaptive & Realtime UI 3,
  Compliance & Legal 2, Data Labeling & Curation 4, Robotics & Physical 4, Voice & Conversation 4,
  Scientific Pipelines 0 (marked "still being seeded").
  **Re-derive:** `gh api repos/v-modal/awesome-jev-tools/readme -H "Accept: application/vnd.github.raw" | grep -E "^- \[.*\] — .* entries"`.
- `gbesse/decision-claim-card` README: reads a published benchmark result JSON and *"renders a small
  Markdown evidence card in English, French or Spanish"*, while declaring its own limit:
  *"it does not rerun the model or establish an independent ranking. No confidence interval is
  computed from incomplete aggregate data."* **Re-derive:** `gh api repos/gbesse/decision-claim-card/readme -H "Accept: application/vnd.github.raw"`.

## 2. Reference architectures (how big a self-hosted platform has to be)

| System | Observed architecture | Source read on 2026-10-15 |
|---|---|---|
| Langfuse | **2 containers** (Web, Worker) + **4 backing services**: PostgreSQL (transactions), ClickHouse (traces/observations/scores), Redis/Valkey (queue, cache, API-key cache), S3/blob (raw events). SSO; orgs + projects multi-tenancy. | `WebFetch https://langfuse.com/self-hosting` |
| MLflow | **1 lightweight FastAPI tracking server** serving the REST API + the web UI; backend store via SQLAlchemy supporting `sqlite` (default), `postgresql`, `mysql`, `mssql`; separate artifact store. | `https://mlflow.org/docs/latest/self-hosting/architecture/overview/` and `.../backend-store/` |
| Phoenix | Single app process; *"By default, Phoenix uses an SQLite database and stores it in the working directory"*, PostgreSQL optional (incl. read replica). | `gh api repos/Arize-ai/phoenix/contents/src/phoenix/config.py -H "Accept: application/vnd.github.raw"` → lines 170–206 |
| promptfoo | CLI is the product; results are viewed with `promptfoo view` (local web viewer over local state) and shared; docs site carries the viewer screenshot. | `gh api repos/promptfoo/promptfoo/readme` grep for `view` / `Share results` |
| Fairlearn dashboard | Was a **Jupyter notebook widget**; the current assessment docs describe the widget as retired. | `https://fairlearn.org/main/user_guide/assessment/index.html` |
| Aequitas | Self-described as a bias-audit toolkit *"for machine learning developers, analysts, and **policymakers**"* — i.e. a non-engineer audience view is a validated product shape. | `https://dssg.github.io/aequitas/`, `https://github.com/dssg/aequitas` |

**Reading for the PRD:** the SQLite-default single-process shape (MLflow / Phoenix) is what an
adoptable self-hosted platform looks like; the 4-service shape (Langfuse) is what a *trace store*
needs. The product decision in `PRD §4` follows this, and the deviation it forces on the generic
PRD template is recorded in `PRD §4.7`.

## 3. This repository, at the baseline the PRD was written against

Every row re-derived by the command in the right column.

| Reading | Value (2026-10-15) | Command |
|---|---|---|
| branch / tip | `plan/b-inventory-fields` / `7bdf2c2` | `git rev-parse --abbrev-ref HEAD; git rev-parse --short HEAD` |
| `verify --protocol` output | `re-derived 543 /543 values`, **rc 0**, lane self-labels **`corpus present`** | `uv run --frozen autorate verify --protocol protocol.json > /tmp/prd-verify-absent.log 2>&1; echo "VERIFY_EXIT=$?"` |
| freeze digest | `protocol: protocol.json 4e9e70366d26 (frozen 2026-10-15)` → the eighth freeze is **published** at this tip | same as above |
| claim statuses | `G1 not_certifiable`, `G2 measured_not_bounded`, `G3 not_measured`, `G4 not_met`, `G5 certified` | same as above |
| CLI surface | 10 subcommands: `snapshot export-feishu certify severity compare gate report audit protocol verify`; `--help` rc 0 | `uv run --frozen autorate --help` |
| `--format json` | **absent** on every subcommand | `uv run --frozen autorate certify --help` |
| artefact formats produced | JSON, JSONL, Markdown only. **No HTML. No CSV.** | `ls data/ docs/` |
| packaging | `version = "0.1.0"`, `requires-python = ">=3.10"`, `license = { text = "Apache-2.0" }`, `dependencies = ["numpy>=1.24"]`, console script `autorate = "autorate.cli:main"` | `grep -nE "version\|requires-python\|license\|dependencies\|autorate =" pyproject.toml` |
| LICENSE file | **does not exist** (`no matches found: LICENSE*`) | `ls LICENSE*` |
| README | 296 lines | `wc -l README.md` |
| tracked docs | `docs/*.md` 10, `docs/superpowers/specs/*.md` 1, `docs/superpowers/plans/*.md` 6 | `ls docs/*.md \| wc -l` etc. |
| repo scale | 226 commits on HEAD; 26 files in `src/`, 12,181 lines | `git rev-list --count HEAD; find src -name "*.py" \| wc -l; wc -l src/autorate/*.py \| tail -1` |
| `protocol.json` top-level keys | `claims corpus decision_rule frozen_at known_limits protocol_version record_contract rubric rubric_scope`; `claims[]` fields `id criterion measurement status artefacts certified_tasks published_certificates refusal_reasons note` | `python3 -c "import json;d=json.load(open('protocol.json'));print(sorted(d));print(list(d['claims'][0]))"` |
| worktrees | 17 under `.worktrees/`; main tree clean at `7bdf2c2`; no `pytest`/`uv run` process at the time of writing | `git worktree list; git status --short; pgrep -fl "pytest\|uv run"` |
| visibility | repository `Jackxiaozhiren/autorate` is **private**; not on PyPI (no publish step in `.github/workflows/`) | `gh repo view --json visibility`; `ls .github/workflows/` |

## 4. Demand-side readings (the numbers the value model is parameterised over)

These are market prices and published claims, not this project's measurements. They are used only
as named constants in `PRD §2.4` formulas, and each must be re-read at the URL when used.

| Reading | Value | Source |
|---|---|---|
| price per *automated resolution*, Intercom Fin | $0.99 per outcome | https://www.tommasomariaricci.com/blog/ai-for-customer-service-guide-2026 |
| price per automated resolution, Zendesk AI agents | $1.50 committed volume / $2.00 pay-as-you-go | same page |
| published resolution-rate band for mature AI-support deployments | ~50–76% of conversations | https://www.lorikeetcx.ai/articles/resolution-rate-ai-customer-support-benchmarks-2026 |
| vendor-side guidance band | 60–80%, "best-in-class exceeding 80%" | https://fin.ai/learn/ai-resolution-rate |
| benchmark pages that separate **vendor-claimed vs independently verified** figures | exists and is a marketed distinction | https://aissist.io/industries/ai-customer-service-benchmark-2026 |
| practitioner statement of the denominator problem | *"'Resolved' on the vendor's screen often means 'the customer stopped talking to the bot.'"* | https://www.linkedin.com/posts/brandonburdin_a-claims-automation-lead-told-me-their-ai-activity-7505604053834346496-G0R- |
| measurement-definition risk acknowledged by a vendor | "why the definition matters most" | https://www.notch.cx/post/ai-customer-support-resolution-rate-benchmarks |
| third-party AI-accuracy assurance sold as a **service** | "AI Agreed-Upon Procedures (AUP) validate model accuracy, governance" | https://sensiba.com/resources/insights/ai-accuracy-building-enterprise-trust-through-third-party-attestation/ |
| EU AI Act obligation relevant to a certificate | Art. 11 + Annex IV technical documentation, incl. performance and limitations | https://www.euaiact.com/article/11 , https://artificialintelligenceact.com/annex-iv-technical-documentation-referred-to-in-article-111/ |
| NIST AI RMF obligation | MEASURE 2.3 — *"AI system performance or assurance criteria are measured qualitatively or quantitatively and demonstrated"* | https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf |
| ISO/IEC 42001 | first AI management-system standard (2023), 38 controls; audits examine *evidence of implementation, not just documentation* | https://www.konfirmity.com/blog/iso-42001 , https://github.com/sunilp/ai-governance-framework/blob/main/framework/compliance/iso-42001-mapping.md |
| open-source exemption does not cover high-risk AI systems | stated by Linux Foundation's AI Act explainer | https://linuxfoundation.eu/newsroom/ai-act-explainer |

## 5. What is *not* in this snapshot, deliberately

- **No claim that a certification platform is absent from the market.** §1.3 shows absence of UI in
  the CP-library lane and absence of a maintained standalone artefact viewer; it does not survey
  commercial AI-governance suites (Credo AI, Holistic AI, Modulos, trail, etc. appear in §4's search
  results as paid governance platforms). `PRD §1.4` requires the executor to run that competitive
  check itself before asserting differentiation.
- **No statement of this project's own error-rate figures** (the audit multiples, the case bounds).
  Those are published artefacts re-derived by `verify`; the PRD points at them by name only, because
  a number quoted here would be a second owner of the same value.
- **No version, SHA, or count in the PRD body.** If the body needs one, it is a command to run.

## 6. Snapshot maintenance

- Append a dated section; do not overwrite a previous one. Corrections go in a new dated block with
  the command that contradicted the old reading.
- This file is documentation, not a gate input: no test reads it, and nothing here may be cited as
  evidence that a claim about the product is true. `verify` is the only owner of published numbers.
