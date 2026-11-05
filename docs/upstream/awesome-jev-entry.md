# `awesome-jev` entry — OMITTED: no entry is proposed

> **Status: this file is a decision record, not a draft.** `OMITTED` here means no line of text in this
> repository is shaped to be pasted into an awesome-list, so there is nothing to submit and nothing to
> soften. `SUBMISSION.md` carries the same conclusion in one row; this file carries the measurement that
> produced it.

## What the plan asked

Plan D Task 6 makes this artefact conditional on two premises, both of which have to hold:

1. the upstream `laya` README actually lists a Jev-compatible ecosystem, and
2. every claim the entry would make is backed by a `verified` row in `docs/VERIFICATION.md`.

Spec §14 already warned that the vacancy assumption behind premise 2 is the one this repository has been
wrong about before — the row `id=awesome-jev-empty-section`, whose ledger status is `withdrawn`, once
called a populated section empty — so both premises were re-measured here rather than inherited.

## Premise 1 — measured true

The upstream README does list a Jev-compatible ecosystem, at the tag and on the default branch:

- `## Community Tools`, which at `v0.3.20` names five projects and one of them
  (`stuntd`) is described in the README as running `laya` behind the Jev API (`POST /v1/systemone`);
- `## Self-Hosting: HTTP Server (Jev-compatible)`, which documents the wire-protocol compatibility and
  points at a third-party Jev client;
- the same `## Community Tools` section is present, unchanged in its five entries, in the `main` README
  fetched on 2026-10-14.

So premise 1 does not fail, and no omission is excused by it.

## Premise 2 — measured false, three times over

**The entry's differentiating claim is not a claim this tree supports.** An entry has to say what the
project does. The only sentence worth printing would be about a certificate that travels with an answer,
and the repository's own frozen protocol says that does not exist yet: `protocol.json` records `G1` as
`not_certifiable` and `G4` as `not_met`, and its `known_limits` carry the line *"no certificate exists,
so no action is certified"*. `docs/VERIFICATION.md` has no `verified` row describing any shipped
`autorate` surface — every verified row in it is about `laya`, MAPIE, the competitor repositories, or the
papers the design cites. Writing the entry would mean minting a claim with no ledger row behind it, which is
the failure the ledger exists to stop.

**The claims that do have rows describe a `laya` that has moved.** Two verified rows could support an
entry's framing — `id=laya-confidence-docstrings` and `id=laya-readme-gating-instruction` — and both are
verified *at the `v0.3.20` tag*. Re-measured on 2026-10-14: `main` no longer prints the literal threshold
the first row's companion sentence quotes (PR #378, merged 2026-09-24, "docs: stop presenting a
confidence threshold as permission to act"; upstream issue #394, closed), the two docstrings have been
rewritten to say what the gate's conditionality is, and the router gate now resolves through a
`_gate_confidence` helper that prefers `answer_confidence`. A row verified at a tag is a row about that
tag; an awesome-list entry would have restated it as a statement about current upstream, and that is
exactly the decay `docs/VERIFICATION.md`'s "still owed" section warns about for pinned-SHA citations.

**It is not a vacancy, and it has grown since the last count.** The scan recorded in
`id=awesome-jev-guarantee-scan` found 24 entries under `cobanov/awesome-jev`'s "Evaluation and
calibration" and 76 across `yibie/awesome-jev`'s two relevant sections on 2026-09-30. Re-counted the same
way on 2026-10-14 from the two READMEs fetched through the contents API: **26** entries in the first
section and **96** across the second list's two sections (43 in "Evaluation & Benchmarking", 53 in
"Calibration & Research"), with five of those lines carrying guarantee-shaped language. A repository
search for the name `awesome-jev` returns 116 repositories. The `yibie` list already carries `laya`
itself, and still describes one same-niche project with "conformal abstention" in its entry text — a
claim this ledger withdrew after reading that project's code (`id=poorjev-conformal-abstention`, whose
ledger status is `withdrawn`). An entry added here would sit in a section that is neither empty nor
careful, and would be asked to justify itself against neighbours whose own descriptions this repository
has already disproved.

## Decision

Omitted. No entry is proposed, no list is contacted, and nothing was opened against either repository.
What would change this, in order:

1. a shipped, `verify`-re-derived certificate surface — i.e. `G1` and `G4` moving off
   `not_certifiable` / `not_met` and the "no certificate exists" limit leaving `protocol.json`;
2. a ledger row opened at the primary source for whatever the entry claims about `autorate` itself,
   because there is no such row today;
3. a re-measurement of `laya`'s fields and README on the day the entry is written, not inherited from
   the `v0.3.20` rows.

Until then the honest artefact is this record, and the search that produced it is reproducible from the
commands in `SUBMISSION.md`.
