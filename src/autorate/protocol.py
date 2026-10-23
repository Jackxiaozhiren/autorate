"""The frozen protocol: one emitted document naming the rubric, the corpus and the criteria.

`protocol.json` is the object Plan D exists to produce. Everything the published numbers are measured
at -- the rubric, the certification unit, the record-contract shape, the corpus the digests belong to,
the criteria the project claims and the envelopes the artefacts actually carry -- lives in one file
whose bytes have a digest, and `certify --protocol` writes that digest into the artefact it produces.
Editing the document therefore changes the digest, which is what makes it a freeze rather than a
comment (plan §5).

Three rulings shape this module, and each is load-bearing enough that the code says it out loud:

* **Emitted, never typed** (ruling D-b). The document is produced by `autorate protocol`, because a
  hand-maintained protocol is a transcription risk and a protocol with a typo in `min_cal` would
  freeze a floor nobody implemented. Every value here comes from `certificate.PUBLISHED_RUBRIC` -- the
  one owner B1 Task 6 produced (R-130 / R-178 / R-187 / R-199) -- from the record-contract constants
  the code already declares, or from the committed artefacts. No rubric value is re-typed in the
  emitter body, and `tests/test_protocol.py` proves that structurally rather than by agreement.
* **`frozen_at` is provenance, not a computed value** (amendment §1 / R-188). The emitter takes it as
  an argument and never reads a clock or git: a clock would make every re-emission a different file,
  which is the drift check's own death, and a git read works in the tree and in CI and fails in the
  `git archive` export -- the one environment G5's measurement is taken in, because it has no `.git`.
  It stays INSIDE the digest, so a silent date change is drift and not metadata; what that gives up is
  stated in the freeze record: a normative-subset digest would let the timestamp move freely, and the
  plan's argument for the freeze is that editing the file breaks every certificate at once.
* **The rubric block describes the published CHOICE rule, not every rubric in the tree.** That
  limitation is a field of the document (`rubric_scope`), not a paragraph nobody has to read, because
  a reader who believed one mapping governed the ordinal and threshold certifiers would take a frozen
  protocol to constrain paths that still carry a second declaration. `docs/ERRATA.md` (2026-10-11)
  names what did not land; the field says the same thing where the loader and the G5 transcript show it.

Exit codes follow the published contract without adding one: `ProtocolError` is a `ValueError`, so
`cli.main`'s existing arm maps a refused protocol to 2 (usage: the document handed to the command is
not this build's protocol), and a table-declared artefact the tree cannot read stays
`PublishedArtefactUnavailable` at 4.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

from .certificate import N_CLAIMS, PUBLISHED_RUBRIC, SHAPE_VERSION
from .inventory import MASSIVE_PIN_LABEL, massive_pin
from .records import QTYPES
from .report import (CERTS, INVENTORY_JSON, MASSIVE_CERTIFICATES, RECORDS,
                     PublishedArtefactUnavailable, load_published, read_certificate,
                     UNPUBLISHED_SURFACES)

PROTOCOL_VERSION = 1

# The G5 note's exception list has one owner: `report.UNPUBLISHED_SURFACES`, the same tuple README's
# unpublished sentence is policed against. Written into the note as prose it went stale twice over -- it named
# `drift.py` after #110 gave it `data/drift_envelope.json`, and `contamination.py` after #107 gave it
# `data/contamination_probe.json` -- so the sentence is emitted from the owner, and a surface can only leave it
# by landing an artefact the gate re-derives rather than by someone remembering to edit a frozen string.
#
# A function of the tuple, not a constant: the day the tuple empties is the day the last tested surface gets its
# artefact, and a branch that only that day can reach has to be reachable by a test now. The note below calls this
# with the owner; the rows in `tests/test_verify_protocol.py` call it with zero, one, two and three surfaces.
def g5_exception_clause(surfaces) -> str:
    """The note's sentence about what the gate does NOT re-derive, spelled from the owner's tuple."""
    spoken = " and ".join("`%s`" % s for s in surfaces) if len(surfaces) < 3 else (
        ", ".join("`%s`" % s for s in surfaces[:-1]) + ", and `%s`" % surfaces[-1])
    if not surfaces:
        return ("every figure this build computes reaches a committed artefact the gate re-derives, so nothing "
                "this build publishes is absent from the denominators")
    if len(surfaces) == 1:
        return ("%s is the surface this build tests without publishing, so its figures are absent from both "
                "denominators rather than re-derived" % spoken)
    return ("%s are the surfaces this build tests without publishing, so their figures are absent from both "
            "denominators rather than re-derived" % spoken)


G5_EXCEPTION_CLAUSE = g5_exception_clause(UNPUBLISHED_SURFACES)

# The document's own field order, which is also its canonical order: `render_protocol` writes these
# keys in this sequence, so the bytes -- and therefore the digest -- do not depend on the ordering a
# text editor happened to leave behind.
PROTOCOL_KEYS = ("protocol_version", "frozen_at", "record_contract", "rubric", "decision_rule",
                 "rubric_scope", "corpus", "claims", "known_limits")

# The decision the published certificates license. `gate.Gate.decide` is the owner of the behaviour;
# this is the one sentence in the document that says which rule the rubric was measured under, and it
# is pinned by the loader so an edit is drift rather than prose.
DECISION_RULE = ("singleton certified set automates; anything else escalates (an empty certified set "
                 "or one carrying several labels) or abstains (a refused certificate, a record of "
                 "another subject, a record of another question type) -- `gate.Gate.decide` is the "
                 "owner of that behaviour")

# The honesty field. The owner this document freezes is complete for the published CHOICE path and
# stops there: `docs/ERRATA.md`'s 2026-10-11 section names what 6A did not land, and this sentence
# carries that into the artefact so the file cannot be read as governing the paths whose copies still
# exist. The loader requires it verbatim (a softening edit is the failure mode, not a typo), and
# `tests/test_protocol.py` checks the named copies against the source, so if a later round deletes a
# copy the sentence has to be rewritten rather than inherited.
RUBRIC_SCOPE = (
    "The `rubric` block is the published choice rule's rubric and nothing wider: it is "
    "`certificate.PUBLISHED_RUBRIC`, which `report.certify_all` and `autorate certify` read. It does "
    "not govern every rubric in this tree. `certify_score.py` and `certify_threshold.py` still "
    "declare their own `MIN_CAL`/`MIN_EVAL`/`DIAGNOSTIC_GRID`, the signature defaults of "
    "`certify_score`, `certify_threshold` and `severity.py` still write 0.05, and "
    "`tails.ALPHA_DEFAULT` remains; those copies are pinned against this owner by "
    "`test_the_two_out_of_fence_certifiers_still_declare_copies_that_agree_with_the_owner` rather "
    "than deleted. `seed` here is the published split (7); the certifiers' library default "
    "(`certificate.SPLIT_SEED_DEFAULT`, 0) is a different fact and the two are deliberately not "
    "collapsed, because the split is a shuffle over sorted case keys and a seed that changes re-rolls "
    "every bound measured on it.")

# --- the vocabulary the criteria are stated in ----------------------------------------------------
#
# R-197: this array is the first machine-readable home for spec §2's criteria, and the vocabulary has
# to be able to say *no*. `not_certifiable` is the CLI's own word (`EXIT_NOT_CERTIFIABLE`), because a
# criterion the tree measured and refused is that same first-class result, not an absent one.
CLAIM_STATUS_CERTIFIED = "certified"
CLAIM_STATUS_NOT_CERTIFIABLE = "not_certifiable"
CLAIM_STATUS_NOT_MET = "not_met"
CLAIM_STATUS_MEASURED_NOT_BOUNDED = "measured_not_bounded"
CLAIM_STATUS_NOT_MEASURED = "not_measured"
CLAIM_STATUSES = (CLAIM_STATUS_CERTIFIED, CLAIM_STATUS_NOT_CERTIFIABLE, CLAIM_STATUS_NOT_MET,
                  CLAIM_STATUS_MEASURED_NOT_BOUNDED, CLAIM_STATUS_NOT_MEASURED)

# spec §2's G1 threshold: THREE decision tasks. It is not `certificate.N_CLAIMS` (also 3, meaning the
# number of claims one feasible certificate makes), and reading one for the other would be the same
# collision in a new costume, so the criterion's count has its own name.
G1_MIN_CERTIFIED_TASKS = 3

# The criterion and measurement text, quoted from spec §2 rather than paraphrased: R-197 rules that
# these entries are what the criteria become machine-readable AS, so the wording is the one a reviewer
# can compare against the document that defines them.
SPEC_CLAIM_IDS = ("G1", "G2", "G3", "G4", "G5")

# The four criteria this freeze cannot state as satisfied, with the artefact each is evidenced by (or
# the honest empty list where none exists). G1 is absent here on purpose: its status is DERIVED from
# the published certificates, because the most misleading string this repository could carry is a G1
# row that reads as met while every certificate in `data/` refuses.
NON_G1_CLAIMS = (
    {
        "id": "G2",
        "criterion": "The gate `laya`'s README instructs demonstrably violates its own implied error "
                     "rate",
        "measurement": "at `confidence >= 0.85`, measured error among automated decisions vs the 15% "
                       "that sentence implies; report the multiple by which it misses",
        "status": CLAIM_STATUS_MEASURED_NOT_BOUNDED,
        "artefacts": ["docs/AUDIT.md"],
        "note": "measured, and re-derived by `autorate verify` as document bytes: on `laya` the "
                "instruction's own `confidence` row automates 2 of 64 cases with 1 wrong, so the "
                "measured error is 0.50 against the 0.15 the sentence implies (3.33x). The criterion "
                "asks for a demonstration, and the exact one-sided Clopper-Pearson bound on those 2 "
                "cases is 0.9747 -- above the implied rate -- so this corpus does not BOUND the gate "
                "it is asked to certify, which is what `NOT_INFORMATIVE` prints beside the row. The "
                "point estimate misses upward; the bound says the sample cannot carry the claim.",
    },
    {
        "id": "G3",
        "criterion": "≥1 ordinal guarantee that multiclass CP cannot express",
        "measurement": "the one-sided severity certificate (§6.4): `P(Y > â(X)) ≤ α`. If vanilla "
                       "multiclass set CP reproduces it, this criterion fails",
        "status": CLAIM_STATUS_NOT_MEASURED,
        "artefacts": ["data/cert_severity_ordinal.json", "data/g3_contrast.json", "docs/SEVERITY.md",
                      "docs/G3.md", "tests/test_g3_contrast.py"],
        "note": "the ordinal certificate is published and re-derived (`autorate severity`, "
                "`data/cert_severity_ordinal.json`, `docs/SEVERITY.md`, 19 comparisons in `verify`), and "
                "the contrast the criterion asks for has now been counted -- and it went against this "
                "row's original wording. Its measured half is published rather than only printed: "
                "`data/g3_contrast.json` holds the set gate's refusal beside the one-sided certificate over "
                "the same committed records, `docs/G3.md` renders that artefact, and `verify` re-measures "
                "both rows in either lane with `tools/g3_contrast.py`'s own builder. On the population "
                "where this repository's ordinal SET gate "
                "certifies (`shift = 0`, `error_rate = 0`; 4 of the 64 knob cells searched), the interval "
                "top is above the gold level in none of the 600 evaluated records (200 cases), so "
                "`P(Y > hi(X)) = 0` lies inside that "
                "certificate's own marginal bound of 0.014867 -- a number `tests/test_g3_contrast.py`'s "
                "builder computes in memory and prints, not a value any artefact under `data/` publishes, "
                "which is why the digit is named with its producer here rather than called published: "
                "a coverage claim over ordered "
                "intervals yields a one-sided bound by itself. The bare sentence 'multiclass CP cannot "
                "express one' is therefore false for the ordinal interval construction, and what survives "
                "is narrower -- the set certificate publishes no named reporting rule, no price and no "
                "override rate, and its certified set is empty on 36 evaluated records, so the reader who "
                "wants the one-sided number must derive it for a rule nobody certified; the severity "
                "artefact certifies a named rule and states both quantities beside its bound. Status stays "
                "`not_measured` because the criterion is worded as the wider claim, and this document "
                "records the narrowing rather than quietly re-defining the row to fit it.",
    },
    {
        "id": "G4",
        "criterion": "Worst-slice certification refuses rather than averages",
        "measurement": "per (language x option-count) bounds with a simultaneous multiple-testing "
                       "correction; must return `NOT_CERTIFIABLE` for the slices `laya` documents as "
                       "collapsed (e.g. Khmer: accuracy 0.000 at mean confidence 0.952)",
        "status": CLAIM_STATUS_NOT_MET,
        "artefacts": ["data/slices_language.json", "docs/SLICES.md", "tools/language_slices.py",
                      "tests/test_slice_surface.py", "data/pin_app_benchmark.json",
                      "data/contamination_probe.json", "docs/CONTAMINATION.md",
                      "tools/contamination_probe.py", "tools/contamination_pin.py"],
        "note": "measured, and short of its own wording -- which is why this row reads `not_met` and not "
                "`not_measured` any more. The behaviour the criterion describes is now a published artefact "
                "rather than terminal scrollback: `tools/language_slices.py` certifies the five committed "
                "MASSIVE record files (14,870 cases, one per row) as slices of the key the producer itself "
                "declares (`slices.language`), at the rubric this freeze owns, and `verify` recomputes that "
                "run from the same bytes -- 108 field comparisons plus 5 rubric rows. The published run "
                "refuses: 5 slices, 0 certified, `any_slice_refused` true. Its `run.worst_claim.worst` "
                "is not empty -- `run.worst_claim.worst.group` is `de` -- but that field is a tie-break, "
                "not a ranking: `run.worst_claim.metric` is `autorate`, and `autorate` is null in all four "
                "rows, so the artefact names a slice without demonstrating that it is the worst one. What "
                "this run therefore demonstrates is every slice refusing, not one slice beaten; every "
                "slice refused at the corrected budget (alpha and delta 0.05 / 5 = 0.01, and the "
                "artefact's own envelope does that family arithmetic: 5 x 3 x 0.01 = 0.1500, joint level "
                "0.85), and `n_min_violations` empty -- so the refusal is a bound failure, not a thin-slice "
                "floor. The pooled marginal certificate over the same records is published beside the "
                "slices and refuses too (`empty_feasible_set`, exact bound above the budget), which is the "
                "'rather than averages' half of the sentence: nothing in the artefact lets the pooled number "
                "stand in for the worst slice. Two things keep the row from `certified`. It is per-language "
                "only: `option_count` is 20 for every committed MASSIVE row -- measured across all four "
                "files, Khmer included -- so the (language x option-count) cross the measurement names would "
                "be the same five slices, and no cross-slice evidence exists to publish. And the ranking the "
                "criterion's word 'worst' asks for cannot be published from a run where nothing certifies. "
                "The slice the criterion names by example, Khmer, is no longer one of the gaps: "
                "`data/records_massive_km.jsonl` is committed and measured here, and it refuses like the "
                "other three; upstream's `accuracy 0.000 at mean confidence 0.952` is its own 100-case read, "
                "which this corpus neither replicates nor contradicts -- it is a fourth refusal at a "
                "different sample size, and the claim ledger records the line. What "
                "The criterion's second named output is published beside that run. "
                "`tools/contamination_probe.py` pools `data/pin_app_benchmark.json` -- upstream's own "
                "per-suite `in_training` declarations, 27 usable rows and 3 excluded by name because their "
                "rounded rate is not a whole number of cases -- into the two strata and writes the gap to "
                "`data/contamination_probe.json` and `docs/CONTAMINATION.md`. `verify` re-pools it and "
                "compares 29 quantities plus 4 budget values in both lanes, and re-digests the upstream file "
                "where the corpus is visible; the arithmetic is `contamination.from_counts`, the same one "
                "`stratified` uses. What it publishes is `delta_hat` = -0.235208 over a two-sided interval of "
                "[-0.262646, -0.207502]: the in-training stratum errs less, which is the direction a "
                "contamination signature predicts, and the interval is clear of zero. Its `claim` is false "
                "and stays false, because the two strata are different suites, so task difficulty is "
                "confounded with the flag and a gap between two aggregate rates does not show that any "
                "checkpoint was trained on any of these cases. What "
                "`NOT_CERTIFIABLE: reason=empty_feasible_set`, and `certify --groups language` over these "
                "records exits 3, which is `EXIT_NOT_CERTIFIABLE`. An earlier draft of this note claimed the "
                "opposite and was corrected by review, not by the author noticing; a later draft then denied "
                "that the artefact names any slice at all, and that denial is falsified by the same field it "
                "describes. `tests/test_slice_surface.py::test_the_frozen_g4_note_transcribes_the_worst_"
                "field_the_arm_compares` is the row that reads the note against `run.worst_claim.worst`, in "
                "both directions, so a sentence about this field has to agree with it.",
    },
    {
                "id": "G5",
        "criterion": "Reproducible from a commit with no GPU, no network, no model",
        "measurement": "`autorate verify --protocol protocol.json` re-derives every published number "
                       "from per-case records alone; exit code + counts printed",
        "status": CLAIM_STATUS_CERTIFIED,
        "artefacts": ["docs/G5.md", "tools/g5_export.sh", "tools/g5_transcript.py",
                      "tests/test_g5_transcript.py"],
        "note": "measured, and now published as a record rather than as a simulation I perform and "
                "delete. `tools/g5_export.sh` unpacks a `git archive` of commit 53ace1b into a scratch "
                "directory with its own HOME, asks that environment what it can see -- `.git` ABSENT, "
                "torch and transformers answered by the export's own interpreter, a deliberate HTTPS "
                "fetch failing -- and runs the criterion's literal command in both lanes, which "
                "`docs/G5.md` transcribes: absent-lane rc=0 at 805/805 values and "
                "corpus-present rc=0 at 842/842, the 37-check difference "
                "being the upstream digests, the snapshot keys, and the contamination arm's re-digest of "
                "the results file -- the comparisons only a corpus can recompute. Five "
                "falsifications are planted in the same export and restored byte-identically with the "
                "restore checked: a rubric value moved inside the frozen file, refused at rc=2 by the "
                "loader's freeze-consistency check before the drift comparison is even reached; the "
                "records file replaced by another valid, self-consistent records file, refused at rc=4 "
                "because the certificates built from it name no record for a backend the published table "
                "declares; the inventory snapshot reduced to an empty JSON array, refused at rc=4 as a "
                "named unusable artefact rather than a traceback; and one hex digit of a published "
                "certificate's stamped digest, refused at rc=4 because the meta block is compared "
                "whole; and one published figure inside the G3 contrast, refused at rc=4 by two lines -- the "
                "field the arm recomputes, and the document rendered from those bytes -- which is the plant "
                "the stamped-digest row cannot cover, because that artefact publishes no stamped digest and "
                "its arm re-measures both gates over the committed records. "
                "`tests/test_g5_transcript.py` is what keeps the record honest: it reads the digest "
                "of the commit the transcript names (not of the reader's tree, which is what made a "
                "transcript that re-freezes impossible to publish), refuses any recorded exit code outside "
                "the contract, requires each lane's two halves to agree and the two lanes to differ by the "
                "checks the corpus owns, counts the plant blocks against the sentence that counts them, "
                "and refuses the document if one line still names a machine path. What the row does not "
                "license: the no-network claim covers the gate steps, not the `uv sync` that provisions "
                "them; the corpus-present lane needs an archive that is not a committed file, so no runner "
                "reproduces that lane and it stays a local obligation; 'every published number' means the "
                "numbers this gate owns -- "
                + G5_EXCEPTION_CLAUSE
                + ". The "
                "record is a record OF a revision, so the revision is named twice rather than related: "
                "`docs/G5.md` opens by naming the commit it was produced from, which is the commit this note says "
                "the export unpacked, and the row named above polices EVERY commit the note ties to that "
                "document rather than only its first mention, because a restatement that goes stale is a "
                "false claim shipped into `docs/REPORT.md` verbatim, and the row above is what makes that pairing checked "
                "rather than remembered: it takes the digest from the named commit's own object, so a "
                "re-freeze cannot make the record lie and a transcript cannot be smuggled in from a branch "
                "that never landed. Nothing here turns on which document "
                "a reader is holding: `docs/REPORT.md` quotes this note verbatim, so a phrase that points at "
                "\"this document\" would name one file inside the protocol and another inside the report, and "
                "would be wrong from the next commit onward even in the protocol. The platform half is "
                "stated the same way. "
                "`.github/workflows/ci.yml` triggers on push and runs the criterion's literal command in "
                "both of its jobs -- `offline`, and the cross-libc matrix over ubuntu and macOS. The witness "
                "of any tip is that tip's own run, so it is read from the runner's log rather than asserted "
                "here: this note claims no result of a run it cannot see, and `tests/test_ci_workflow.py` is "
                "the row that refuses a workflow edited back to the unfrozen form."
    },
)

# The identity fields of the MASSIVE pin this project publishes. Named as a field list rather than
# picked ad hoc in the emitter: the pin's own per-shard digests stay in the file that owns them (the
# protocol pins THAT by digest), because transcribing 51 hashes into a second document is how a
# published figure gets two owners.
MASSIVE_PIN_FIELDS = ("dataset", "revision", "license", "n_files", "rows_total",
                      "distinct_ids", "distinct_row_counts", "id_sets_identical", "bytes_total")

# The fields of an inventory `corpus_options` row a protocol reader needs. `basis` and `note` are the
# artefact's own words for what was opened and what was not, which is exactly the disclosure a pinned
# build has to carry.
CORPUS_OPTION_FIELDS = ("id", "unit", "n_rows", "n_independent", "basis", "note")

TYPED_DECISIONS_OPTION = "typed_decisions"

# The rubric fields that must be probabilities, and the floors/counts that must be integers. Two
# separate clauses because the refusal has to name which kind of promise was broken.
RUBRIC_PROBABILITIES = ("alpha", "beta", "delta")
RUBRIC_INTEGERS = ("seed", "n_claims", "min_cal", "min_eval")
RUBRIC_STRINGS = ("method", "unit")

FROZEN_AT_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ProtocolError(ValueError):
    """The document is not this build's protocol, or names a promise this code does not keep.

    A `ValueError` subclass on purpose (the precedent is `records.MissingRecordField` and
    `groups.UndeclaredGroupKey`, both ruled in R-115): `cli.main` already maps `ValueError` to the
    usage exit code, so a refused protocol reaches a documented 2 instead of escaping as a traceback
    at rc 1, and the dedicated name keeps it greppable and separately testable in the error stream.

    It is raised at the checking site -- the loader -- and never absorbed by a wider catch. Nothing on
    the load path treats it as a value to work around: a protocol this build cannot read is not a
    protocol it may certify under.
    """


def file_digest(path) -> str:
    """sha256 of a file's bytes, hex, the same hashing definition upstream's `SOURCE.json` pins by."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical(doc) -> dict:
    """The document as its bytes should be: known keys, in the emitter's order.

    Two deliberate asymmetries, both about what the digest is FOR. Unknown TOP-LEVEL keys are dropped,
    so a key the loader never reads cannot be used to smuggle a changed promise past a digest check --
    and adding one is not drift, which is the round-trip property the freeze test asserts. Keys inside
    the `rubric` block are KEPT (ordered, with the owner's first), because a rubric key the owner does
    not declare is a value nothing implements, and the loader has to be able to refuse it rather than
    silently re-render it away.
    """
    if isinstance(doc, Protocol):
        doc = asdict(doc)
    if not isinstance(doc, Mapping):
        raise ProtocolError("the protocol document is a %s, not a mapping" % type(doc).__name__)
    out = {}
    for key in PROTOCOL_KEYS:
        if key in doc:
            out[key] = doc[key]
    rubric = out.get("rubric")
    if isinstance(rubric, Mapping):
        ordered = {k: rubric[k] for k in PUBLISHED_RUBRIC if k in rubric}
        for k in sorted(set(rubric) - set(PUBLISHED_RUBRIC)):
            ordered[k] = rubric[k]
        out["rubric"] = ordered
    return out


def render_protocol(doc) -> str:
    """The document's bytes, exactly: `sort_keys=False`, two-space indent, one trailing newline.

    `ensure_ascii=False` because this is a published document a human reads, and the criteria quote
    spec §2's own characters; UTF-8 is what `write_protocol` encodes and what `load_protocol` decodes,
    so the digest is not at the mercy of a locale.
    """
    return json.dumps(_canonical(doc), indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def protocol_digest(doc) -> str:
    """sha256 of the canonical bytes -- the digest `certify --protocol` stamps and `verify` recomputes.

    Content-addressed rather than text-addressed: a reordered file or an unread added key keeps the
    digest, and any change to a value the loader reads moves it. That is the property the freeze needs,
    because the promise lives in the values. `frozen_at` is inside it by ruling (amendment §1), so
    moving the date moves the digest.
    """
    return hashlib.sha256(render_protocol(doc).encode("utf-8")).hexdigest()


def write_protocol(doc, path) -> Path:
    """Write the document's canonical bytes, creating the directory the caller named."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(render_protocol(doc).encode("utf-8"))
    return p


def require_frozen_at(value) -> str:
    """The freeze date, or a refusal naming the field and the format.

    One function for both arms -- the command that takes the date as an argument and the loader that
    reads it back -- because a format one of them forgave would be a document the other refuses.
    """
    if not isinstance(value, str) or not FROZEN_AT_RX.match(value):
        raise ProtocolError(
            "`frozen_at` is not a YYYY-MM-DD date (%r): the freeze date is provenance stated by the "
            "operator, never a value this tool computes" % (value,))
    return value


# --- what the published tree says, read rather than remembered ------------------------------------

def published_certificates() -> tuple:
    """`(path, Certificate)` for every SET certificate this tree publishes, from the tables that own them.

    `report.CERTS` and `report.MASSIVE_CERTIFICATES` are the one owner of THIS list -- the same two
    tables `verify` re-derives and `report` renders -- so the protocol cannot end up with a third list
    that disagrees about which set artefacts exist. The list is not the whole of what is published:
    `report.SEVERITY_CERTS` owns the ordinal severity artefact and `report.RESPLIT_JSON` owns the
    resplit experiment, and neither belongs here because G1's criterion counts decision tasks the set
    gate certifies. Reading `published_certificates` as "everything published" would let the severity
    certificate be counted as a decision task it never made.
    """
    out = [(path, load_published(path, "report.CERTS", read_certificate))
           for path in sorted(CERTS.values())]
    out += [(cert_path, load_published(cert_path, "report.MASSIVE_CERTIFICATES", read_certificate))
            for _label, (_records_path, cert_path) in sorted(MASSIVE_CERTIFICATES.items())]
    return tuple(out)


def g1_status(certified_tasks: int) -> str:
    """G1's status as a function of the count the artefacts carry, so the file cannot over-state it.

    Zero certified tasks is the refusing state R-197 rules must exist; a count under the criterion's
    threshold is a different finding (measured, some tasks certified, still short of three) and gets
    its own word rather than borrowing the refusal's.
    """
    if certified_tasks == 0:
        return CLAIM_STATUS_NOT_CERTIFIABLE
    if certified_tasks < G1_MIN_CERTIFIED_TASKS:
        return CLAIM_STATUS_NOT_MET
    return CLAIM_STATUS_CERTIFIED


def _g1_claim(certs: tuple) -> dict:
    """G1, derived from the published certificates instead of typed beside them."""
    paths = [path for path, _cert in certs]
    feasible = [path for path, cert in certs if cert.feasible]
    reasons = sorted({cert.reason for _path, cert in certs if not cert.feasible and cert.reason})
    return {
        "id": "G1",
        "criterion": "≥3 decision tasks yield a certified `autorate(α=0.05)` with an upper risk bound",
        "measurement": "200-resplit Monte-Carlo per task; report the empirical violation rate of the "
                       "claimed bound, not just the bound",
        "status": g1_status(len(feasible)),
        "artefacts": paths,
        "certified_tasks": len(feasible),
        "published_certificates": len(certs),
        "refusal_reasons": reasons,
        "note": "every certificate this tree publishes refuses, so G1's certified task count is zero "
                "and the criterion is not met. The refusals are the artefacts named above, and "
                "`verify` re-derives them rather than transcribing them. The 200-resplit measurement the "
                "criterion's second column names is now published -- `tools/resplit_experiment.py` is its "
                "producer, `data/resplit_200.json` and `docs/RESPLIT.md` its record, and `verify` "
                "compares 42 quantities the artefact asserts about itself plus its rubric against this "
                "freeze -- and what it shows is a refusal pattern: all seven decision tasks certify in 0 "
                "of 200 splits, so their violation rate is published as undefined over a zero denominator "
                "rather than imputed as 0.000, and the only rate in the table belongs to a synthetic "
                "control that tests the machinery and is labelled as such. Published beside it is the "
                "ceiling itself: `tools/g1_feasibility.py` writes `data/g1_feasibility.json` and "
                "`docs/FEASIBILITY.md`, `verify` recomputes every figure in both lanes from "
                "`src/autorate/tails.py` and the published certificates, and what the table states is how "
                "wide the bound is at each pool size this checkout can actually build and what error rate "
                "would therefore be certifiable there -- which is why this row prints `not_certifiable` as a "
                "measured claim about the evidence rather than as an absence of an answer. Spec §14 "
                "anticipated exactly this shape of result (\"bound width is a first-class output; 'the "
                "bound is useless here' *is* a certification result\"), and the same section's kill criterion "
                "for this criterion is not evaluable on this tree rather than fired: its condition compares a "
                "worst-group certified `autorate` with 0.30, and with nothing certified there is no certified "
                "`autorate` to put in that comparison -- the same refusal that keeps the violation rate "
                "undefined. Both halves of the pivot are published now: the audit multiple G2 measures, "
                "and the contamination gap section 9 defines, which the eleventh freeze publishes as "
                "`data/contamination_probe.json` with its interval and its `claim = False`. So the "
                "headline this project publishes is the audit multiple G2 measures and the worst-slice "
                "refusal G4 names, not a certified automation rate. Nothing in this row licenses reading G1 "
                "as met.",
    }


def _option_row(inventory: dict, option_id: str) -> dict:
    row = next((o for o in inventory["corpus_options"] if o.get("id") == option_id), None)
    if row is None:
        raise ProtocolError(
            "the inventory carries no `%s` corpus_options row, so this document cannot state which "
            "evidence base that id names (it holds: %s)"
            % (option_id, ", ".join(sorted(str(o.get("id")) for o in inventory["corpus_options"]))))
    return {k: row[k] for k in CORPUS_OPTION_FIELDS if k in row}


def _pinned_builds(inventory: dict) -> dict:
    """The pinned builds, each named by label and pinned BY DIGEST.

    The MASSIVE pin file owns 51 shard digests and their row and byte counts; `massive_pin` is the
    loader that polices them against each other, so the protocol reads the pin through that loader and
    then identifies the file rather than copying it. `typed_decisions` has no pin to read: the
    inventory's own row says no file was opened, and that sentence is what gets frozen.

    `pin_label`, `pin_digest` and the identity fields are read from ONE resolved path, resolved when
    this runs rather than at import: a pin whose fields came from one file and whose digest came from
    another would be a frozen document describing a build it never hashed.
    """
    from .inventory import MASSIVE_PIN_PATH

    pin = massive_pin(MASSIVE_PIN_PATH)
    if not pin:
        raise PublishedArtefactUnavailable(
            "%s is the owner of every MASSIVE figure this document records and is not readable here, "
            "so the pinned build has no identity to freeze. This is not a usage error -- the path "
            "comes from `inventory.MASSIVE_PIN_PATH`, and no argument selects it."
            % MASSIVE_PIN_LABEL)
    massive = {field: pin[field] for field in MASSIVE_PIN_FIELDS}
    massive["pin_label"] = MASSIVE_PIN_LABEL
    massive["pin_digest"] = file_digest(MASSIVE_PIN_PATH)
    massive["shard_digests"] = (
        "%d per-shard sha256 values are owned by %s; this document pins that file by digest instead "
        "of transcribing them, because a published figure may not have a second owner"
        % (len(pin["files"]), MASSIVE_PIN_LABEL))
    return {"massive_intent": massive, TYPED_DECISIONS_OPTION: _option_row(inventory,
                                                                           TYPED_DECISIONS_OPTION)}


def emit_protocol(inventory: dict, records_digest: str, frozen_at: str) -> dict:
    """The protocol document, built from the owners and the artefacts -- and from no typed value.

    `inventory` is the committed snapshot (`data/inventory.md.json`), read through
    `report.read_inventory_snapshot`; `records_digest` is the caller's measurement of
    `data/records_feishu.jsonl`, taken as an argument so a test can falsify the field by changing it;
    `frozen_at` is the operator's provenance (amendment §1). The inventory digest, the source labels,
    the pinned builds, the known limits and G1's status are read here from the tree's own files.
    """
    if not isinstance(inventory, dict):
        raise ProtocolError("emit_protocol needs the inventory mapping, got %s"
                            % type(inventory).__name__)
    certs = published_certificates()
    rubric = dict(PUBLISHED_RUBRIC)
    rubric["grid"] = list(rubric["grid"])
    limits = sorted({line for _path, cert in certs for line in cert.envelope})
    return {
        "protocol_version": PROTOCOL_VERSION,
        "frozen_at": require_frozen_at(frozen_at),
        "record_contract": {"shape_version": SHAPE_VERSION, "primitives": list(QTYPES)},
        "rubric": rubric,
        "decision_rule": DECISION_RULE,
        "rubric_scope": RUBRIC_SCOPE,
        "corpus": {
            "records_owner": RECORDS,
            "records_digest": records_digest,
            "inventory_owner": INVENTORY_JSON,
            "inventory_digest": file_digest(INVENTORY_JSON),
            "provenance": inventory["provenance"],
            "source_labels": [{"label": row["path"], "sha256": row["expected"]}
                              for row in inventory["digests"]],
            "pinned_builds": _pinned_builds(inventory),
        },
        "claims": [_g1_claim(certs)] + [dict(row) for row in NON_G1_CLAIMS],
        "known_limits": limits,
    }


# --- the loader ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Protocol:
    """A validated protocol. Frozen because a certificate stamped against it must not be able to
    renegotiate the rubric it was measured at by editing the object in memory."""

    protocol_version: int
    frozen_at: str
    record_contract: dict
    rubric: dict
    decision_rule: str
    rubric_scope: str
    corpus: dict
    claims: tuple
    known_limits: tuple

    def claim(self, claim_id: str) -> dict:
        """One criterion's entry, or a refusal that names the ids the document does carry."""
        for row in self.claims:
            if row["id"] == claim_id:
                return row
        raise ProtocolError("the protocol states no claim %r (it carries: %s)"
                            % (claim_id, ", ".join(str(r["id"]) for r in self.claims)))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def _absolute(value: str) -> bool:
    """Does this string PARSE as an absolute path, in either flavour, or as a home-relative one?

    Checked by parsing rather than by matching this machine's username, because the defect class is a
    location that only exists on the producer's disk: it passes every local gate and reddens the one
    environment that never saw that disk (R-115, and the guard in `tests/test_cli.py`).
    """
    return (value.startswith("~") or PurePosixPath(value).is_absolute()
            or PureWindowsPath(value).is_absolute())


def _walk_strings(node, trail: str):
    """Every key and string value under a subtree, with the path that led to it."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield "%s.%s" % (trail, key), key
            for found in _walk_strings(value, "%s.%s" % (trail, key)):
                yield found
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            for found in _walk_strings(value, "%s[%d]" % (trail, index)):
                yield found
    elif isinstance(node, str):
        yield trail, node


def _check_shape(doc) -> None:
    """Every structural refusal, BEFORE any check that assumes a parsed mapping.

    The order is the contract, not an implementation detail: `corpus` and `rubric` value checks index
    mappings, and a document whose shape is bad used to be reported as a document whose VALUES are bad
    -- or as a `TypeError` naming nothing. So the shape gate runs first and a malformed-with-bad-values
    document is refused for being malformed (proved by a test that mutates both at once).
    """
    _require(isinstance(doc, Mapping), "the protocol document is a %s, not a JSON mapping"
             % type(doc).__name__)
    missing = [k for k in PROTOCOL_KEYS if k not in doc]
    _require(not missing, "the document has no %s" % ", ".join(missing))
    _require(isinstance(doc["protocol_version"], int) and not isinstance(doc["protocol_version"], bool),
             "`protocol_version` is not an integer (%r)" % (doc["protocol_version"],))
    _require(isinstance(doc["frozen_at"], str), "`frozen_at` is not a string")
    contract = doc["record_contract"]
    _require(isinstance(contract, Mapping),
             "`record_contract` is a %s, not a mapping" % type(contract).__name__)
    _require("shape_version" in contract, "`record_contract` has no `shape_version`")
    _require(isinstance(contract.get("primitives"), list),
             "`record_contract.primitives` is not a list")
    _require(isinstance(doc["rubric"], Mapping),
             "`rubric` is a %s, not a mapping" % type(doc["rubric"]).__name__)
    for key in ("decision_rule", "rubric_scope"):
        _require(isinstance(doc[key], str), "`%s` is not a string" % key)
    _require(isinstance(doc["corpus"], Mapping),
             "`corpus` is a %s, not a mapping" % type(doc["corpus"]).__name__)
    _require(isinstance(doc["claims"], list) and doc["claims"],
             "`claims` is not a non-empty list of criteria")
    for index, row in enumerate(doc["claims"]):
        _require(isinstance(row, Mapping), "`claims[%d]` is a %s, not a mapping"
                 % (index, type(row).__name__))
        absent = [k for k in ("id", "criterion", "measurement", "status", "artefacts", "note")
                  if k not in row]
        _require(not absent, "`claims[%d]` has no %s" % (index, ", ".join(absent)))
        _require(isinstance(row["artefacts"], list),
                 "`claims[%d].artefacts` is not a list" % index)
    _require(isinstance(doc["known_limits"], list) and doc["known_limits"],
             "`known_limits` is not a non-empty list")
    _require(all(isinstance(line, str) and line for line in doc["known_limits"]),
             "`known_limits` carries an empty or non-string line")


def _check_values(doc) -> None:
    """Every refusal that compares a stated promise with the owner that implements it."""
    if doc["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError(
            "unknown protocol_version %r: this build emits and reads version %d"
            % (doc["protocol_version"], PROTOCOL_VERSION))
    require_frozen_at(doc["frozen_at"])

    contract = doc["record_contract"]
    if contract["shape_version"] != SHAPE_VERSION:
        # R-196: the version is imported and never `null`, and a loader that forgave its absence
        # would be a permanent hole for the shape mismatch the tag exists to catch.
        raise ProtocolError(
            "`record_contract.shape_version` is %r, not the %d this build writes certificates at "
            "(`certificate.SHAPE_VERSION`): a missing or null shape version is a refusal, never a "
            "default" % (contract["shape_version"], SHAPE_VERSION))
    if list(contract["primitives"]) != list(QTYPES):
        raise ProtocolError(
            "`record_contract.primitives` is %s, not the decision primitives `records.QTYPES` "
            "declares (%s)" % (contract["primitives"], ", ".join(QTYPES)))

    rubric = doc["rubric"]
    extra = sorted(set(rubric) - set(PUBLISHED_RUBRIC))
    absent = sorted(set(PUBLISHED_RUBRIC) - set(rubric))
    if extra or absent:
        raise ProtocolError(
            "the rubric block does not match its owner: %s -- `certificate.PUBLISHED_RUBRIC` declares "
            "%s and nothing else"
            % ("; ".join(filter(None, ["carries no %s" % ", ".join(absent),
                                       "carries keys no owner implements: %s" % ", ".join(extra)])),
               ", ".join(PUBLISHED_RUBRIC)))
    for name in RUBRIC_PROBABILITIES:
        value = rubric[name]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 < value < 1.0:
            raise ProtocolError(
                "rubric.%s is %r, which is not a probability in the open interval (0,1)"
                % (name, value))
        if value != PUBLISHED_RUBRIC[name]:
            raise ProtocolError(
                "rubric.%s is %r, not the %r `certificate.PUBLISHED_RUBRIC` owns: the protocol that "
                "freezes a number nobody implements is the defect R-187 was written for"
                % (name, value, PUBLISHED_RUBRIC[name]))
    for name in RUBRIC_INTEGERS:
        value = rubric[name]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProtocolError("rubric.%s is %r, not an integer" % (name, value))
        if value != PUBLISHED_RUBRIC[name]:
            raise ProtocolError(
                "rubric.%s is %r, not the owner's %r" % (name, value, PUBLISHED_RUBRIC[name]))
    for name in RUBRIC_STRINGS:
        value = rubric[name]
        if not isinstance(value, str):
            raise ProtocolError("rubric.%s is %r, not a string" % (name, value))
        if value != PUBLISHED_RUBRIC[name]:
            raise ProtocolError(
                "rubric.%s is %r, not the owner's %r -- the certification unit is the CASE, never the "
                "row (R-36/R-44)" % (name, value, PUBLISHED_RUBRIC[name]))
    grid = rubric["grid"]
    if not isinstance(grid, (list, tuple)) or [float(g) for g in grid] != \
            list(PUBLISHED_RUBRIC["grid"]):
        raise ProtocolError(
            "rubric.grid is not the owner's diagnostic sweep (`certificate.DIAGNOSTIC_GRID`, %d "
            "points from %.2f to %.2f): %r. `audit.DEFAULT_GRID` is the audit's risk-coverage "
            "frontier, a different object with a different denominator, and is never a substitute"
            % (len(PUBLISHED_RUBRIC["grid"]), PUBLISHED_RUBRIC["grid"][0],
               PUBLISHED_RUBRIC["grid"][-1], grid))
    if rubric["n_claims"] != N_CLAIMS:
        raise ProtocolError("rubric.n_claims is %r, not certificate.N_CLAIMS (%d)"
                            % (rubric["n_claims"], N_CLAIMS))

    if doc["decision_rule"] != DECISION_RULE:
        raise ProtocolError(
            "`decision_rule` is not the sentence this build's gate implements: an edited decision "
            "rule is a different protocol, not a comment on this one")
    if doc["rubric_scope"] != RUBRIC_SCOPE:
        raise ProtocolError(
            "`rubric_scope` is not the scope sentence the owner carries: this document's rubric "
            "governs the published choice rule, and the wording that says so is part of the freeze")

    for trail, value in _walk_strings(doc["corpus"], "corpus"):
        if _absolute(value):
            raise ProtocolError(
                "%s is %r, which parses as an absolute path: the protocol records corpus identity by "
                "digest and label only, because a machine path in a tracked file is green on the "
                "producer's disk and unresolvable everywhere else" % (trail, value))

    ids = [row["id"] for row in doc["claims"]]
    if len(ids) != len(set(ids)):
        raise ProtocolError("`claims` states an id twice: %s" % ", ".join(sorted(ids)))
    if set(ids) != set(SPEC_CLAIM_IDS):
        raise ProtocolError("`claims` does not cover spec §2's criteria: it carries %s, the spec names %s"
                            % (", ".join(sorted(map(str, ids))), ", ".join(SPEC_CLAIM_IDS)))
    for row in doc["claims"]:
        if row["status"] not in CLAIM_STATUSES:
            raise ProtocolError(
                "claims.%s carries status %r, outside the vocabulary this freeze states itself in "
                "(%s): a criterion has to be able to say no, in words a machine can check"
                % (row["id"], row["status"], ", ".join(CLAIM_STATUSES)))
        # G1's status is a function of its count, in the FILE as well as at emission, so flipping the
        # word while leaving `certified_tasks: 0` is refused rather than believed.
        if "certified_tasks" in row and row["status"] != g1_status(row["certified_tasks"]):
            raise ProtocolError(
                "claims.%s says status %r while its `certified_tasks` is %r: the status has to agree "
                "with the count it is a sentence about, so G1 cannot be flipped to %r by editing the "
                "word" % (row["id"], row["status"], row["certified_tasks"],
                          CLAIM_STATUS_CERTIFIED))


def load_protocol(path) -> Protocol:
    """Read, validate, and hand back the freeze -- refusing a document this build does not implement.

    The clauses, each proved by a mutation in `tests/test_protocol.py` that raises with its own name in
    the message: an unknown `protocol_version`; a rubric probability outside (0,1); `min_cal`,
    `min_eval`, `n_claims`, `unit`, `method` or `seed` disagreeing with `certificate.PUBLISHED_RUBRIC`
    (the ONE owner, per R-187/R-199 -- never `certify_choice`'s copies, never a typed literal); a
    `grid` that is not the owner's sweep, including the audit's frontier; a null or foreign
    `shape_version` (R-196); a normative sentence rewritten; a `corpus` field holding a string that
    parses as an absolute path (the machine-path guard, moved here so it fires on the producer's
    machine before CI sees the file); and a claim stated in a status outside the vocabulary, or a G1
    status its own count contradicts (R-197).

    Shape first, values second: `_check_shape` runs before anything indexes a mapping.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    _check_shape(doc)
    _check_values(doc)
    return Protocol(protocol_version=doc["protocol_version"], frozen_at=doc["frozen_at"],
                    record_contract=dict(doc["record_contract"]), rubric=dict(doc["rubric"]),
                    decision_rule=doc["decision_rule"], rubric_scope=doc["rubric_scope"],
                    corpus=dict(doc["corpus"]),
                    claims=tuple(dict(row) for row in doc["claims"]),
                    known_limits=tuple(doc["known_limits"]))
