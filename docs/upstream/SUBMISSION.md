# SUBMISSION.md — the upstream channel is prepared, and stopped

**DO NOT SUBMIT WITHOUT EXPLICIT HUMAN APPROVAL.** Concretely, approval would have to be the
repository owner's own written instruction — in this project's own words, addressed to this work — that
names all four of: (1) the target repository and the exact text of `issue.md` as it should be filed,
(2) the branch, fork and PR that `pr-description.md` describes, (3) the person who will answer review
comments afterwards, and (4) the date the owner considers the re-measurements fresh enough to act on.
A coding agent's plan, a task in a plan document, a green test suite, or the existence of this directory
is not that instruction. Nothing in Plan D Task 6 grants it, and Plan D §7 lists "submitting anything
upstream" as out of scope for the plan.

This task produced text and stopped. In this session: **no issue is opened**, **no PR is pushed** or
created, **no fork** or branch was created on any remote, no comment, label, review or reaction was
posted, and no remote write of any kind ran — not a `git push`, not a clone with write intent, not a
label or a comment on anything. The only outbound traffic was
read-only: `gh api` GETs against `api.github.com`, two `curl` GETs of public PyPI artifact URLs, and the
local file reads quoted below. `gh search issues` / `gh search prs` were tried first and failed on this
machine; that failure is recorded rather than smoothed over.

---

## 1. What is in this directory

| file | what it is | state |
|---|---|---|
| `issue.md` | the issue text, reduced to the one finding still live at the current release | drafted, not filed |
| `patch/laya-0.3.20-fixes.patch` | the four-finding diff against a clean `v0.3.20` checkout, sha256 `e1aad33a46a62a2066037f74a41228cad0384e47bfe69827d952486e095b5c76` | checked with `git apply --check`, never applied |
| `patch/README.md` | the diff's provenance, the tag blobs it expects, per-finding upstream status | — |
| `pr-description.md` | PR 1 of the two-PR order, and why it must be rebased before it could be filed | drafted, not filed |
| `awesome-jev-entry.md` | a decision record: **OMITTED**, no entry is proposed, with the three measurements behind it | omitted |
| `SUBMISSION.md` | this file | — |
| `../../tests/test_upstream_artifacts.py` | the gate that walks this directory on every test session | green |

## 2. The order, from spec §13

1. **patch first** — the self-contained packaging fix, as its own contribution, per
   `pr-description.md`.
2. **the §7 confidence-semantics audit and the `laya` adapter second, as a second, separate PR.**

Spec §13's reason for the split is still true and was re-measured: the `laya` `research/eval/` lane is
occupied by contributors who merge fast (`id=laya-research-eval-contributors`), so the channel works by
consumption rather than competition. The second PR is **not drafted here**: the re-measurement in §5
below changed its opening facts, and a draft written against a tree that has since moved would be the
same mistake this task exists to avoid.

## 3. Spec §7.1's three reproduction conditions, measured one by one

The condition list is the one attached to the guardrail anecdote: the fix patch applied to a clean
`v0.3.20` checkout; the 39 prompts and their labels committed as per-case records; both ranges re-derived
by `autorate verify`. Each was measured in this tree, not inherited from the spec.

| condition | verdict | the measurement |
|---|---|---|
| `patch_on_clean_checkout` | **met** | `git apply --check --verbose -p1` over a scratch copy of the tag archive exits `rc=0` on all four files (§6); the four target blobs equal the tag's own, read from the contents API and re-computed locally (§6) |
| `prompts_committed_as_records` | **not met** | every committed record file under `data/` was streamed line by line looking for the guardrail question id or a guard-set record id: `records_feishu.jsonl` (1919 lines), `records_massive_{de,en,sw}.jsonl` (2974 each), `records_ordinal_synthetic.jsonl` (1200) — zero hits. The prompts and labels live only in the author's off-tree note, which this repository deliberately does not cite |
| `ranges_rederived_by_verify` | **not met** | `harm_severity` and `guard_questions` occur zero times in `protocol.json` and zero times across `src/autorate/`; the gate that does run, `autorate verify --protocol protocol.json`, exits 0 printing `re-derived 248 /248 values` over claims `G1`–`G5`, none of which is a guardrail range |

**Verdict: two of three conditions are unmet, so the claim stays `withdrawn` — the row is
`id=guard-preset-overlap`, whose ledger status is `withdrawn` — and the report does not quote it.** No
figure from that observation appears in any file in `docs/upstream/`; `tests/test_upstream_artifacts.py`
scans for the literals themselves, and a plant of one of them into `pr-description.md` reddens that row
without editing the published directory.

Two things follow, and they are recorded rather than caveated:

- the prepared patch's new test fixtures in `tests/test_langchain.py` carry the author's measured model
  outputs as mock values, and those values *are* the withdrawn observation's numbers. The diff is
  therefore under the same embargo as the claim; `patch/README.md` says so, and this file does not
  reproduce them.
- `pr-description.md` and `issue.md` argue from code a reviewer can open (line numbers, blobs, two sdist
  listings) rather than from the anecdote. If the reproduction is ever finished, what changes is §7.1's
  condition table above, not the prose.

## 4. The emptiness re-check (spec §13 forbids reusing 2026-09-30)

All times UTC, all 2026-10-14, all through `gh api` GETs authenticated as the author.

The plan's literal commands were tried first and did not run:

```
$ gh search issues --author=Jackxiaozhiren --repo NandhaKishorM/laya --json number,title,state,url
2026-10-14T03:00:04Z
rc=1  Post "https://api.github.com/graphql": EOF
$ gh search prs --author=Jackxiaozhiren --repo NandhaKishorM/laya --json number,title,state,url
rc=1  Post "https://api.github.com/graphql": EOF
```

That is a transport failure, not an empty result, so the check was re-run against the REST search
endpoint the ledger row itself names (`search/issues`, filtered by `type:`), which is what the rest of
this section reports:

```
$ gh api "search/issues?q=author:Jackxiaozhiren+repo:NandhaKishorM/laya+type:issue" --jq .total_count
2026-10-14T03:00:53Z
rc=0  0
$ gh api "search/issues?q=author:Jackxiaozhiren+repo:NandhaKishorM/laya+type:issue" --jq .items
rc=0  []
$ gh api "search/issues?q=author:Jackxiaozhiren+repo:NandhaKishorM/laya+type:pr" --jq .total_count
rc=0  0
```

A `0` from a broken query reads exactly like a `0` from a working one, so the same endpoint was run
without the author clause as a positive control, and the author account was resolved separately:

```
$ gh api "search/issues?q=repo:NandhaKishorM/laya+type:issue" --jq .total_count
2026-10-14T03:01:19Z
rc=0  190
$ gh api "search/issues?q=repo:NandhaKishorM/laya+type:pr" --jq .total_count
rc=0  956
$ gh api users/Jackxiaozhiren --jq .login,.created_at
rc=0  Jackxiaozhiren  2022-05-01T13:59:03Z
$ gh api rate_limit --jq .resources.core.remaining,.resources.search.remaining
rc=0  4947  30
```

**Result: zero issues and zero PRs by the author on `NandhaKishorM/laya` as of 2026-10-14T03:00:53Z**,
with the query proven non-vacuous against the same endpoint (190 issues, 956 PRs by anyone), and with
30 search requests left in the hour. `id=laya-research-eval-contributors` is the 2026-09-30 row this
replaces for the "still unsubmitted" statement; the row itself is untouched, and the star count in
`id=laya-star-count` is a dated observation that this session re-opened without adopting — the transcript
in §5 prints what the API returned today, and no artefact in this directory quotes either number.

## 5. The upstream state, re-measured (this is what changed the artefacts)

```
$ gh api "repos/NandhaKishorM/laya/git/ref/tags/v0.3.20" --jq .object.sha,.object.type
2026-10-14T03:01:22Z
rc=0  412531034634775c2c102fac8d160e84203cfae4  tag
$ gh api repos/NandhaKishorM/laya --jq .stargazers_count,.pushed_at,.default_branch
rc=0  32785  2026-10-12T09:30:04Z  main
$ gh api "repos/NandhaKishorM/laya/tags?per_page=8" --jq ".[].name"
2026-10-14T03:10:16Z
rc=0  v0.4.6 v0.4.5 v0.4.4 v0.4.3 v0.4.2 v0.4.1 v0.4.0 v0.3.29
$ gh api repos/NandhaKishorM/laya/releases/latest --jq .tag_name,.published_at
2026-10-14T03:18:06Z
rc=0  v0.4.6  2026-10-12T09:34:48Z
```

The tag is annotated, and dereferencing it is what ties the scratch copy to a commit rather than to a
filename:

```
$ gh api "repos/NandhaKishorM/laya/git/tags/412531034634775c2c102fac8d160e84203cfae4" --jq .object.sha
2026-10-14T03:01:57Z
rc=0  23a17522aa4942da6cce53a995a275760320b691
```

Three of the four findings are already upstream, and each was pinned to the commit or PR that took it:

```
$ gh api "repos/NandhaKishorM/laya/commits?path=pyproject.toml&per_page=40" --jq … | grep -i onnx
2026-10-14T03:10:16Z
rc=0  1c3360d5 2026-09-25T04:35:55Z  fix(packaging): the onnx extra must declare onnxscript
      5f22d218 2026-09-27T18:50:07Z  Merge pull request #504 from PerryLink/fix/onnx-extra-onnxscript
      9d955671 2026-09-27T19:27:17Z  release: 0.3.21, ONNX batch/long parity, opt-in abstention, …
$ gh api "repos/NandhaKishorM/laya/commits?path=laya/integrations/langchain.py&per_page=40" --jq … | head
rc=0  e0e8154c 2026-09-27T19:01:28Z  Merge pull request #598 from gRain-is-grainy/fix/guardrail-score-threshold
      4e552251 2026-09-29T20:56:55Z  fix(integrations): gate thresholds on answer_confidence, never entropy confidence
      93bf34a6 2026-09-30T08:47:09Z  fix(integrations): keep the abstention gate fail-closed via core's _gate_confidence
      0a06f662 2026-10-01T18:05:13Z  fix(integrations): gate a LayaTaskGuard score question on its upper-half probability
$ gh api "repos/NandhaKishorM/laya/pulls/504" --jq .state,.merged,.user.login,.title
2026-10-14T03:18:06Z  rc=0  closed merged=true PerryLink  fix(packaging): the onnx extra must declare onnxscript
$ gh api "repos/NandhaKishorM/laya/pulls/598" --jq .state,.merged,.user.login,.title
rc=0  closed merged=true gRain-is-grainy  fix(integrations): gate a guardrail score question on its upper-half probability
$ gh api "repos/NandhaKishorM/laya/pulls/378" --jq .state,.merged,.user.login,.title,.merged_at
rc=0  closed merged=true PerryLink  docs: stop presenting a confidence threshold as permission to act  2026-09-24T16:24:27Z
$ gh api "repos/NandhaKishorM/laya/issues/394" --jq .number,.title,.state,.user.login,.created_at
2026-10-14T03:09:05Z
rc=0  394  A confidence threshold does not transfer across option counts: at 20 options the gate at
      0.85 selects below model accuracy  closed  PerryLink  2026-09-24T14:32:37Z
```

The `main` tree itself was read through the contents API, not from memory:
`2026-10-14T03:08Z–03:21Z`, `pyproject.toml` (its `onnx` extra now declares `onnxscript`),
`laya/integrations/langchain.py` (a `_score_violation_probability` gate for `score` questions and a
`_gate_confidence` helper preferring `answer_confidence`), `laya/common.py` (both confidence docstrings
rewritten, one of them citing upstream issue #394), `tests/test_packaging.py` (`.venv` and `.hf-cache`
now pruned) and the default-branch README (114149 bytes, headed "What's new in 0.4.6", the literal
threshold gone from the gating example, `## Community Tools` unchanged in its five entries).

Two consequences for the artefacts, both already written into them:

1. `issue.md` no longer reports the three taken findings; it reports the one that still describes the
   release, which is that `tests/test_packaging.py` cannot run from the published sdist.
2. `pr-description.md` carries a rebase requirement, because a `v0.3.20` diff against `main` is not a
   contribution anyone could merge.

## 6. The patch, checked in a scratch copy — the read-only corpus was never touched

The vendored `laya-0.3.20` tree is read-only and already carries the author's patch in `pyproject.toml`
and `laya/integrations/langchain.py`, so it is *not* a clean checkout; PF-D-7's constraint was honoured
by working entirely on copies. `<scratch>` is the scratch root this session used
(`<scratch>` under the evidence directory named by the plan); nothing under the corpus received a write.

```
# the tag archive's own embedded commit, and the four target files staged out of it
2026-10-14T03:39:11Z
$ unzip -q laya-0.3.20.zip -d <scratch>            # archive comment: 23a17522aa4942da6cce53a995a275760320b691
$ cd <scratch>/laya-0.3.20 && git hash-object pyproject.toml laya/integrations/langchain.py \
      tests/test_langchain.py tests/test_packaging.py
ee375c7114df2d2465f46664eec14042553ff107
f7e5cb9bb42c6804d38a380e79bdfb52a79c70db
ad12bf45175613626776ecd8244c26fc4a19f451
5a133cb95db194309461fe189f87c1fc9ff2092c

$ cd <scratch> && git apply --check --verbose -p1 <repo>/docs/upstream/patch/laya-0.3.20-fixes.patch
2026-10-14T03:39:49Z
rc=0
Checking patch pyproject.toml...
Checking patch laya/integrations/langchain.py...
Checking patch tests/test_langchain.py...
Checking patch tests/test_packaging.py...

$ # read-only proof, taken after the check:
$ cd <scratch>/laya-0.3.20 && git hash-object pyproject.toml laya/integrations/langchain.py \
      tests/test_langchain.py tests/test_packaging.py
2026-10-14T03:39:49Z   … the four digests are unchanged, and equal the tag's blobs listed in §5 of
```

`--check` writes nothing by design; the digest re-read is there because the claim being guarded is
"never touched the corpus", not "tried not to". `tests/test_upstream_artifacts.py` re-runs this staging
and check on every test session and re-reads the source fingerprints afterwards.

The surviving finding was reproduced the same way, inside a copy of the **published** artifact rather
than against the corpus:

```
$ cp -R <sdist-extract>/laya-0.4.6 <scratch>/run-sdist && cd <scratch>/run-sdist
$ python3 tests/test_packaging.py
2026-10-14T03:43:43Z
rc=1
Traceback (most recent call last):
  File "<scratch>/run-sdist/tests/test_packaging.py", line 196, in <module>
    workflow = read(os.path.join(".github", "workflows", "ci.yml"))
  File "<scratch>/run-sdist/tests/test_packaging.py", line 32, in read
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
FileNotFoundError: [Errno 2] No such file or directory: '<scratch>/run-sdist/.github/workflows/ci.yml'
```

The two sdists were fetched from the registry (read-only GET, `2026-10-14T03:11:33Z` and `03:11:52Z`) and
listed without extracting: `laya-0.3.20.tar.gz` (275028 bytes, uploaded 2026-09-24) and
`laya-0.4.6.tar.gz` (1163178 bytes, uploaded 2026-10-12) both contain zero `scripts/` entries, zero
`.github/` entries and zero compose files.

## 7. The `awesome-jev` decision

**Omitted — no entry is proposed.** Premise 1 (the upstream `laya` README lists a Jev-compatible
ecosystem) measured **true** on 2026-10-14: `## Community Tools` names five projects, one of them serving
the Jev API, and the section is present on both the tag and `main`. Premise 2 (every claim backed by a
`verified` ledger row) measured **false** three ways: the differentiating claim would describe a shipped
certificate that `protocol.json` says does not exist; the two rows that could frame it are verified *at
the tag*, and the tree they describe has moved (PR #378, issue #394, rewritten docstrings); and the
sections are not a vacancy — re-counted on 2026-10-14 from the fetched READMEs, `cobanov/awesome-jev`
carries 26 entries under "Evaluation and calibration" and `yibie/awesome-jev` carries 96 across its two
relevant sections, against the 24 and 76 recorded on 2026-09-30 by `id=awesome-jev-guarantee-scan`, with
116 repositories now matching the name. `awesome-jev-entry.md` holds the full record.

One query in that re-measurement failed and is recorded as failed: the
`repos/<r>/readmes/README.md` form returned `404 Not Found` at `2026-10-14T03:20:01Z` for both lists. It
was not a missing repository — `repos/<r>` resolved both at `03:20:49Z` with `main` as the default branch
— and the contents API path fetched the READMEs at `03:21:29Z`. A 404 from the wrong endpoint is not
evidence of absence, so it is written here as the wrong endpoint rather than as "the list is gone".

## 8. What a reviewer would run, start to finish

`<repo>` is this checkout; `<scratch>` is any empty directory you own. Nothing in this list needs the
corpus, a model, a GPU, or network except where a command says `gh api`.

```sh
cd <repo>
export PYTHONDONTWRITEBYTECODE=1 NO_PROXY='*' no_proxy='*'

# 1. the artefact gate: paths, secrets, citations, the withdrawal sentences, the §7.1 measurements,
#    and the patch check inside a scratch copy.
uv run --frozen --extra dev python3 -m pytest -q tests/test_upstream_artifacts.py

# 2. the same gate in the corpus-absent lane, which is how the repository ships it.
AUTORATE_FEISHU_ROOT=/nonexistent-corpus-dir uv run --frozen --extra dev python3 -m pytest -q

# 3. the condition-(c) measurement by hand: the gate re-derives every published value (read the
#    denominator from the line it prints -- it moves when an arm is added) and names no guardrail range.
uv run --frozen autorate verify --protocol protocol.json          # exit 0

# 4. the emptiness re-check, which must be re-run the day anything is filed.
gh api "search/issues?q=author:Jackxiaozhiren+repo:NandhaKishorM/laya+type:issue" --jq .total_count
gh api "search/issues?q=author:Jackxiaozhiren+repo:NandhaKishorM/laya+type:pr"    --jq .total_count

# 5. the patch check, in a copy.
mkdir -p <scratch> && unzip -q laya-0.3.20.zip -d <scratch>
cd <scratch>/laya-0.3.20 && git apply --check --verbose -p1 <repo>/docs/upstream/patch/laya-0.3.20-fixes.patch
```

## 9. Re-run before anything is filed

Everything in §4, §5, §6 and §7 is a dated snapshot of a moving tree, and this repository has already
recorded what happens when a snapshot is reused: the plan forbids reusing spec §13's 2026-09-30 result
because other contributors merge within days, and two of this session's findings are exactly that effect
(0.3.21 took the `onnx` fix two days after the note was written; 0.4.6 is six releases further). Before
submission, re-run §4 and §5, re-run §6 against whatever tag the maintainer is on, and re-measure §7. If
the re-run contradicts a line in this file, the re-run wins and this file is amended rather than
silently rewritten.

## 10. Hygiene this directory was written to hold

No machine-absolute path appears anywhere in `docs/upstream/`: the two roots a reader would expect —
the account home and the scratch directory — are printed as `<repo>` and `<scratch>`, and a traceback
was edited to that convention rather than pasted raw. No token-shaped string appears; the queries were
made with an authenticated client whose credential is never written down, and `gh auth status` output was
not transcribed. Every `id=` citation in these files resolves to a row in `docs/VERIFICATION.md`; a row
that is not `verified` is cited only on a line that says so in the ledger's own word. `tests/cli`'s
committed-tree guard cannot see an untracked directory, so `tests/test_upstream_artifacts.py` scans this
one directly, and it is the file to read if a claim here looks too tidy.
