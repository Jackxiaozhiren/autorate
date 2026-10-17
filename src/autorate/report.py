"""Build and re-derive the published results document.

Determinism is the product: the report contains no timestamp and nothing that is not
derived from the committed inputs (`data/inventory.md.json`, `data/records_feishu.jsonl`,
`data/cert_*.json`), so `verify` can compare it byte for byte in any environment --
including one that never saw the vendored corpus. Corpus provenance is pinned by the
digests in the upstream `SOURCE.json`, which is their owner; the inventory transcribes
them, and this module quotes the transcription rather than hashing anything itself.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Optional

# ALPHA, BETA and SEED are IMPORTED, not declared here (#62): they are the published rubric, and
# this module renders documents about it rather than owning it. `tests/test_correction.py` and
# `tests/test_mondrian.py` keep reading them off this module, and the AST guard
# `test_no_module_inside_the_fence_redeclares_a_rubric_name_it_could_import` is what keeps that
# reuse honest: an import keeps working, a re-typed literal goes red.
from .certificate import ALPHA, BETA, Certificate, canonicalise_bound, SEED
from .certify_choice import certify_choice
from .records import Record
from .severity import SeverityCertificate, certify_severity
from .tails import bound_width, clopper_pearson_upper, n_feasible

RECORDS = "data/records_feishu.jsonl"
# The rubric keys an ARM publishes and re-derives, in the spelling the artefacts record. One owner for the
# NAME LIST (R-168, and #62's close-out): `certificate.PUBLISHED_RUBRIC` owns the published VALUES, and its
# mapping order is alpha, beta, delta, seed, method -- so this is a list of names held here deliberately
# rather than `tuple(PUBLISHED_RUBRIC)`, which would silently compare a different set of rows. The three
# arms alias it below; an arm that needs a different field set must say so in its own name, because the
# alternative -- a second literal -- is what let `("alpha", "beta", "delta", "method", "seed")` be typed
# three times in this one file while the guard that looks for duplicates only scanned modules inside the
# fence, never the owner (`tests/test_cli.py`'s report-internal row now covers this file).
PUBLISHED_RUBRIC_FIELDS = ("alpha", "beta", "delta", "method", "seed")

CERTS = {"laya": "data/cert_laya.json", "jev": "data/cert_jev.json"}
INVENTORY_JSON = "data/inventory.md.json"
# The budgets the archived corpus is certified at. beta is deliberately loose: the
# evaluation half is ~96 records, and a tighter budget would only be honest about a
# claim this corpus cannot make at all.
BACKENDS = ("laya", "jev")

# G1's published certificates: one artefact per held-out MASSIVE language, never pooled, because one gate
# over the corpora would assert exchangeability between a 0.4617-accuracy, a 0.0982-accuracy and a
# 0.0615-accuracy population. `verify` re-derives them and `report` publishes them, so the paths live once
# here rather than in a list inside each caller -- two lists that can disagree about what was certified is
# the defect this table exists to prevent, not a formatting choice. `massive/km` joined on task #68's round:
# spec §2's G4 column names Khmer as the collapsed slice the worst-slice certification must refuse, and a
# criterion whose example is not in the evidence is a criterion nobody checked.
MASSIVE_CERTIFICATES = {
    "massive/de": ("data/records_massive_de.jsonl", "data/cert_massive_de_laya.json"),
    "massive/en": ("data/records_massive_en.jsonl", "data/cert_massive_en_laya.json"),
    "massive/km": ("data/records_massive_km.jsonl", "data/cert_massive_km_laya.json"),
    "massive/sw": ("data/records_massive_sw.jsonl", "data/cert_massive_sw_laya.json"),
}

# G3's published artefact: the one-sided severity certificate, in its own table because it is its own
# shape (`SeverityCertificate`, not `Certificate`) and is read by a different loader. The third element of
# each row is the direction THIS PUBLICATION declares, and it is not read back out of the artefact: a
# re-derivation that took `direction` from the stored bytes would happily re-derive a tampered artefact
# into agreement with itself, which is the fixed-point hole the set arm closes by supplying the rubric.
#
# The records file is SYNTHETIC ORDINAL DATA WITH KNOWN ANSWERS, and that is a measured constraint, not a
# stylistic one: none of the five committed records files in this checkout carries a single
# `qtype="score"` record (`data/records_feishu.jsonl` is `choice`+`noul`, the four MASSIVE files are all
# `choice`), and `severity.certify_severity` refuses a population with no ordinal record by name. So no
# corpus this repository can see produces a severity certificate, and the ordinal guarantee is published
# over the population `tests/_records.build_ordinal` owns -- the same population `tests/test_severity.py`
# measures the expressiveness claim on, at the same parameters, pinned byte for byte by
# `test_the_committed_ordinal_records_file_is_the_owner_generator_output`. What the lane can reproduce:
# BOTH of them, because nothing here reads the vendored corpus.
SEVERITY_RECORDS = "data/records_ordinal_synthetic.jsonl"
SEVERITY_CERT_JSON = "data/cert_severity_ordinal.json"
SEVERITY_LABEL = "ordinal"
SEVERITY_CERTS = {SEVERITY_LABEL: (SEVERITY_RECORDS, SEVERITY_CERT_JSON, "under")}


class PublishedArtefactUnavailable(RuntimeError):
    """A file the publication tables declare is absent, there and unopenable, or there and unreadable.

    The first two are raised by `require_published` and the third by `load_published`; they share a class
    because the sentence they carry is the same one, and it is about who owns the path, not about what the
    filesystem or the parser reported.

    It is a `RuntimeError` and not an `OSError` on purpose: `cli.main` maps `OSError` and `ValueError`
    onto the usage exit code, and usage is the false statement here. No argument selected this path --
    the table did -- so the tree, not the operator, is what disagrees with the published numbers. The
    CLI gives it its own arm and its own code for that reason; a class raised anywhere else would
    escape as rc 1, outside the documented 0/2/3/4 contract.
    """


def require_published(path, table: str) -> Path:
    """The Path for an artefact a publication table names, or a refusal that says which table.

    `verify`'s contract is to re-derive what this repository publishes, so an artefact it cannot read
    is the loudest form of that contract failing -- louder than a digit that disagrees, because nothing
    about it can be reproduced. The read stays strict (this is not a fallback-to-empty situation); only
    the attribution is being repaired, which is the sentence `docs/ERRATA.md` disclosed on 2026-10-08.

    The file is opened rather than stat-ed, because a directory in its place and a mode that refuses
    the read are the same misattribution as an absent artefact: measured on a stat-only guard they
    reached the `OSError` arm and reported a usage error for the table's own path. Nothing is read
    through this handle -- the caller still owns the parse.
    """
    p = Path(path)
    try:
        with p.open("rb"):
            pass
    except FileNotFoundError as exc:
        raise PublishedArtefactUnavailable(
            "%s is declared published by %s and is not in this checkout, so the numbers re-derived "
            "from it cannot be reproduced at all. This is not a usage error -- no argument selected "
            "this path, the table did -- and it is not a value that disagrees either: the artefact "
            "itself is absent." % (p, table)) from exc
    except OSError as exc:
        raise PublishedArtefactUnavailable(
            "%s is declared published by %s and cannot be opened (%s), so the numbers re-derived "
            "from it cannot be reproduced at all. This is not a usage error -- no argument selected "
            "this path, the table did -- and the errno is the whole of what this run knows about the "
            "path: the read failed, and a certificate this checkout cannot read certifies nothing."
            % (p, table, exc)) from exc
    return p


def read_json(path):
    """The committed JSON at a published path, as one call, so the guard can be handed it."""
    return json.loads(Path(path).read_text())


# The shape this build's own readers demand of the committed inventory snapshot, declared once. Every name
# below is measured rather than chosen: a survey at `da2a401` mutated ONE property of the committed
# `data/inventory.md.json` at a time and ran `verify` corpus-less, and these are exactly the keys whose
# removal raised a `KeyError` or a `TypeError` out of a renderer, while the unmodified control printed
# `re-derived 96 /96 values` and exited 0.
#
# The keys that are NOT here are not accidents. `n_shards`, `feasible_at_0.25` and the five
# `reader_lines_*` counters are read with `.get()` or not read at all, so removing one leaves a value that
# disagrees rather than a crash, and the byte comparison already answers that at `4`. Demanding them would
# make the loader refuse a checkout whose snapshot this build can read -- a contract is the minimum the
# readers need, not the maximum the producer happens to write.
INVENTORY_TOP_KEYS = ("corpus_options", "digests", "families", "gaps", "label_counts",
                      "lines_by_mode_backend", "provenance", "reader_lines_read", "repeats",
                      "source", "unique_ids", "upstream_audit_rc", "upstream_audit_stdout_tail")
INVENTORY_DIGEST_KEYS = ("match",)
INVENTORY_OPTION_KEYS = ("basis", "bound_width_at_0.05", "feasible_at_0.10", "id", "n_independent",
                         "n_rows", "note", "unit")


def _require_rows(doc, list_key, row_keys):
    """Every row of one snapshot list must be a mapping carrying the keys the renderers index."""
    rows = doc[list_key]
    if not isinstance(rows, list):
        raise ValueError("%s must be a list, found %s" % (list_key, type(rows).__name__))
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("%s[%d] must be a JSON object, found %s" % (list_key, i,
                                                                        type(row).__name__))
        missing = sorted(set(row_keys) - set(row))
        if missing:
            raise ValueError("%s[%d] has no %s, which this build indexes"
                             % (list_key, i, ", ".join(missing)))


def read_inventory_snapshot(path):
    """The committed inventory snapshot, rejected before a renderer can crash on its shape.

    `json.loads` accepts anything JSON, and this file is not read by a gate that then asks a question of
    the value: `verify` hands it to the renderers as the inventory itself whenever no corpus is present,
    and they index it. Measured, ten one-property mutations of the committed file left `verify` exiting
    `1` with a bare `TypeError: list indices must be integers or slices, not str` or `KeyError: 'digests'`
    naming no file -- the same misattribution round 3 and round 4 retired for the decode failures, arriving
    through the contents rather than through the bytes, and the one exit code the contract forbids outright.

    So the shape is refused here, as a `ValueError`, which is the signal `load_published` already answers
    with the named refusal and exit `4`. A wrong shape is not an access failure and not an operator's
    input: no argument selects this path, `report.INVENTORY_JSON` does.
    """
    doc = read_json(path)
    if not isinstance(doc, dict):
        raise ValueError("a JSON object was expected at this path, found %s" % type(doc).__name__)
    missing = sorted(set(INVENTORY_TOP_KEYS) - set(doc))
    if missing:
        raise ValueError("no %s, which this build indexes" % ", ".join(missing))
    _require_rows(doc, "digests", INVENTORY_DIGEST_KEYS)
    _require_rows(doc, "corpus_options", INVENTORY_OPTION_KEYS)
    return doc


def load_published(path, table: str, load):
    """A table-declared artefact, put through both arms of the attribution repair.

    `require_published` answers the filesystem: nothing at the path, or the path refusing the open. This
    answers the contents. A published certificate whose JSON will not parse, a records file whose line is
    not a record, a document that is not text, a snapshot whose shape this build does not accept -- in
    each case the bytes were read, so nothing about the failure is an access failure, and each raised a
    `ValueError` from a loader that also serves operator-supplied paths where "usage error" is the truth.
    The wrap belongs here and not inside `read_certificate` or `load_records` for exactly that reason:
    those functions cannot tell whose path they were handed, and the exit code has to.

    Measured before this arm existed, a corrupted `data/cert_laya.json` left `verify` printing
    `JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)` and
    exiting 2 -- a message that names no file, about a file no argument named. The refusal quotes the
    reader's own words for the same reason the access rows quote the errno: what this run knows is that
    the read gave up, and where it gave up.

    It therefore does not name the mechanism. "does not parse" was the first wording and it over-reached
    in the same direction round 2 retired: the tamper that empties a certificate's `envelope` parses
    perfectly, and what refuses it is this build's own shape rules -- measured, the parenthetical reads
    "every certificate needs a non-empty envelope of assumptions". A decode failure, a parser complaint
    and a rejected shape are three different claims, and the refusal states none of them as fact.

    One asymmetry to keep in mind when adding a site: `load` is applied to the guarded `Path`, so
    `read_certificate`, `load_records`, `Path.read_text` and `read_inventory_snapshot` all fit it -- and
    any `ValueError` a loader raises is absorbed here and re-raised as drift. That is right for a SHAPE
    refusal and wrong for a POLICY one, and the two are now both live: `read_inventory_snapshot` raises a
    `ValueError` by design, because a snapshot whose keys this build indexes are missing is the
    checkout's own defect, and `test_the_shape_contract_demands_exactly_the_keys_this_build_indexes`
    pins that list in both directions. A refusal that means "the caller handed me a bad input" must never
    be raised by a wrapped loader, because this arm would promote it to exit `4` and say the tree is
    broken when the argument is; such a refusal belongs in a function this table does not call, and the
    rows that pin an operator-supplied path at `2` are the ones that would fire if that line were crossed.
    """
    try:
        return load(require_published(path, table))
    except ValueError as exc:
        raise PublishedArtefactUnavailable(
            "%s is declared published by %s, was read here, and what was found is not the artefact that "
            "table publishes (%s), so the numbers re-derived from it cannot be reproduced. This is not a "
            "usage error -- no argument selected this path, the table did, and no argument can repair it: "
            "the bytes at a published path belong to this checkout, not to the caller. What is in "
            "parentheses is the reader's own report of where it gave up, which may be a decode failure, a "
            "parser's complaint or a shape this build does not accept; the refusal does not guess which."
            % (path, table, exc)) from exc


def load_records(path: Path) -> dict:
    by_backend: dict = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = Record.from_dict(json.loads(line))
        by_backend.setdefault(r.backend, []).append(r)
    return by_backend


def certify_all(records: dict) -> dict:
    return {b: certify_choice(rs, alpha=ALPHA, beta=BETA, seed=SEED)
            for b, rs in records.items()}


def massive_certificates() -> dict:
    """`{label: (records, stored certificate)}` for every published MASSIVE artefact, read from the tree.

    One owner for the read path, so the gate's re-derivation below and anything that quotes these
    artefacts cannot end up opening two different sets of files. The read is strict: an artefact this
    checkout does not hold, or holds but cannot open, or holds as bytes that do not parse, raises, because
    a certificate the tool cannot read is not the same statement as a certificate that agrees with nothing
    -- and it raises as `PublishedArtefactUnavailable`, naming the table that declared the path, because
    "usage error" would blame the operator for a checkout this package wrote.
    """
    out = {}
    for label, (records_path, cert_path) in sorted(MASSIVE_CERTIFICATES.items()):
        stored = load_published(cert_path, "report.MASSIVE_CERTIFICATES", read_certificate)
        rows = load_published(records_path, "report.MASSIVE_CERTIFICATES", load_records)
        out[label] = (rows.get(stored.backend, []), stored)
    return out


def rederive_massive(expect, fields, rubric=None, stamp=None) -> None:
    """Re-derive every published MASSIVE certificate from its committed records, field by field.

    This is the arm `cmd_verify` already runs over the two feishu certificates, widened to G1's three
    languages: read the artefact, run `certify_choice` over the rows that artefact was made from at the
    rubric stored inside it (or the rubric a frozen protocol supplies, when the caller passes one), and
    hand every comparison to `verify`'s own `expect`, so a drift leaves as
    exit 4 naming `cert massive/en.<field>` instead of as a complaint about a document.

    Two differences from the feishu arm, both narrower rather than looser. `method` is taken from the
    certificate instead of left at `certify_choice`'s default -- a `lac` artefact re-derived under `aps`
    would be an accident waiting for the default to move, and the feishu arm only gets away with the
    default because both of its artefacts happen to store it. `seed` comes from `meta.seed`, as it does
    there. Nothing in this function chooses a rubric: the rubric is whatever the published artefact says
    it was, so the gate cannot re-derive a certificate into existence by picking better numbers (R-143).

    Rows are selected by the backend the certificate itself declares, which is the filter
    `certify --backend laya` applied when the artefact was written, so the gate and the producer read the
    same population. An empty selection is not special-cased: `certify_choice([])` returns a
    `no_gold_labels` refusal, so a records file that stopped carrying that backend shows up as drift on
    `reason`, `n_cal` and `n_eval` rather than as an exception.
    """
    for label, (records, stored) in massive_certificates().items():
        chosen = rubric or {"alpha": stored.alpha, "beta": stored.beta, "delta": stored.delta,
                            "seed": stored.meta.get("seed", SEED), "method": stored.method}
        kwargs = {"alpha": chosen["alpha"], "beta": chosen["beta"], "delta": chosen["delta"],
                  "seed": chosen["seed"], "method": chosen["method"]}
        if chosen.get("grid") is not None:
            kwargs["grid"] = tuple(chosen["grid"])
        fresh = certify_choice(records, **kwargs)
        if rubric is not None:
            # The producer echoes `alpha`/`beta`/`seed` into `meta`, which the gate compares by whole-dict
            # equality: a caller handing in a protocol has to move those three as well, or every tree reads
            # red for a reason it did not ask for. `delta` is a top-level field and never appears in `meta`.
            fresh = replace(fresh, meta={**fresh.meta, "alpha": chosen["alpha"],
                                         "beta": chosen["beta"], "seed": chosen["seed"]})
        if stamp is not None:
            fresh = stamp(fresh)
        for field in fields:
            expect("cert %s.%s" % (label, field), getattr(fresh, field), getattr(stored, field))
        expect("cert %s.summary" % label, fresh.summary(), stored.summary())


def read_severity_certificate(path: Path) -> SeverityCertificate:
    """The severity shape's reader, kept beside the set shape's and bound to neither.

    `read_certificate` is `Certificate.from_dict` and cannot read this artefact -- the two shapes refuse
    each other by version (see `severity.SEVERITY_SHAPE_VERSION`). A wrong shape here raises
    `SeverityShapeMismatch`, a `ValueError`, which `load_published` answers at exit 4 for a table-declared
    path. No shipped command takes a severity artefact path today -- `severity` reads records and writes an
    artefact, and `gate`/`compare` still read the set shape -- so this refusal has exactly one door in this
    build, and it is the 4 below rather than a 2 the operator can be sent to.
    """
    return SeverityCertificate.from_dict(json.loads(Path(path).read_text()))


def severity_certificates() -> dict:
    """`{label: (records, stored certificate, published direction)}` for every ordinal artefact.

    The read goes through `load_published` for both files, so an absent or unreadable records file is the
    table's own failure at exit 4 -- the same attribution repair `massive_certificates` carries. The
    direction travels with the row because the publication, not the artefact, owns it: a re-derivation that
    took the rule off the bytes could not contradict them.
    """
    out = {}
    for label, (records_path, cert_path, direction) in sorted(SEVERITY_CERTS.items()):
        stored = load_published(cert_path, "report.SEVERITY_CERTS", read_severity_certificate)
        rows = load_published(records_path, "report.SEVERITY_CERTS", load_records)
        out[label] = (rows.get(stored.backend, []), stored, direction)
    return out


def published_severity() -> tuple:
    """The one ordinal artefact this tree publishes, as `(label, records, certificate, direction)`.

    It refuses rather than guessing if the table grows a second row: `docs/SEVERITY.md` is a document about
    ONE certificate, and a renderer that silently picked `sorted(table)[0]` would publish the first
    artefact's figures under a heading that says it quotes the publication. The refusal is a named exit 4
    -- the checkout, not an argument, is what no longer matches what it publishes.
    """
    rows = sorted(severity_certificates().items())
    if len(rows) != 1:
        raise PublishedArtefactUnavailable(
            "docs/SEVERITY.md renders one ordinal certificate and report.SEVERITY_CERTS now holds %d "
            "(%s), so this document has no single artefact to quote. It is not a usage error -- no "
            "argument selected the table -- and it is not a value that disagrees: the publication and its "
            "renderer have to be widened together."
            % (len(rows), ", ".join(label for label, _row in rows) or "nothing"))
    return (rows[0][0],) + rows[0][1]


def rederive_severity(expect, expect_rubric, fields, rubric_fields, rubric=None, stamp=None) -> None:
    """Re-derive G3's published certificate from its committed records, field by field.

    The same arm `cmd_verify` runs over the set artefacts, with the two differences the shapes force:
    `direction` comes from the publication table (see `SEVERITY_CERTS`) rather than from the stored bytes,
    because a re-derivation that read the rule off the artefact could not contradict it; and the rubric the
    caller supplies is the freeze's `alpha`/`delta`/`seed` -- the ordinal gate has no `beta` and no
    `method`, and inventing those here would state a rule that never ran.

    `expect_rubric` is a second callback rather than a folded-in comparison because the two failures are
    repaired differently -- re-export, or re-freeze -- and `cmd_verify` keeps them on separate prefixes for
    that reason (`RUBRIC MISMATCH:` versus `DRIFT:`, rulings R-20/R-31). `alpha` and `delta` are also in
    `fields`, so a rubric disagreement lands twice: once naming the freeze as the standard and once naming
    the field. Both lists are handed in rather than copied, so the gate and the denominator that counts it
    read one owner (R-168).

    The re-derivation chooses no rubric of its own when the caller supplies none: `chosen` falls back to
    what the artefact says it was measured at, which is R-143's rule for the set side restated here.
    """
    for label, (records, stored, direction) in severity_certificates().items():
        chosen = rubric or {"alpha": stored.alpha, "delta": stored.delta,
                            "seed": stored.meta.get("seed", SEED)}
        for name in rubric_fields:
            published = stored.meta.get("seed") if name == "seed" else getattr(stored, name)
            expect_rubric("cert %s.%s" % (label, name), published, chosen[name])
        fresh = certify_severity(records, alpha=chosen["alpha"], delta=chosen["delta"],
                                 direction=direction, seed=chosen["seed"])
        if rubric is not None:
            # The producer echoes `alpha`/`delta`/`seed` into `meta` (`severity._intake`) and this gate
            # compares `meta` whole, so a caller handing in a protocol has to keep those three in step.
            # Measured at this tip: the echo branch is the identity -- `certify_severity` is called with
            # `chosen` two lines above, and `_intake` writes back exactly what it was given -- so no test
            # can force it to fire and the ordinal side of R-225 is NOT what this line covers. It stays as an
            # explicit belt: if the producer ever stops echoing, the whole-dict comparison goes red here
            # rather than at every frozen tree reading the artefact. The owner of those three values is
            # `_intake`, and `severity.py`'s `meta` is compared against it by `certify`/`severity`'s own rows.
            fresh = replace(fresh, meta={**fresh.meta, "alpha": chosen["alpha"],
                                         "delta": chosen["delta"], "seed": chosen["seed"]})
        if stamp is not None:
            fresh = stamp(fresh)
        for field in fields:
            expect("cert %s.%s" % (label, field), getattr(fresh, field), getattr(stored, field))
        expect("cert %s.summary" % label, fresh.summary(), stored.summary())


def _verdict_cell(cert) -> str:
    """The one rendering of a certificate's verdict, shared by every document that states one.

    #38: `docs/RESULTS.md` narrates each refusal twice -- in its summary table and again in the verbatim
    `summary()` block printed directly beneath -- and a byte-compare against a renderer that formats the
    verdict in two places re-derives a drifted wording instead of refusing it. One function, both sites.
    """
    return "**certified**" if cert.feasible else "**NOT_CERTIFIABLE** (%s)" % cert.reason


def render_severity(label: str, cert: SeverityCertificate) -> str:
    """G3's published document, written entirely out of one artefact.

    Derived prose (B1 Task 2d's rule): every figure below is read off `cert`, and a sentence whose value the
    artefact does not carry is not written here. The header names the command that emits the file and the
    command that re-checks it; it carries no timestamp and no machine path, so both lanes reproduce the same
    bytes -- which is what lets the corpus-less lane, and CI, byte-compare this document at all. The
    `label` selects the table row the paths are quoted from, so the document names the artefact the gate
    re-derived rather than a path this function remembered.
    """
    records_path, cert_path, direction = SEVERITY_CERTS[label]
    meta = cert.meta
    verdict = _verdict_cell(cert)
    lines = [
        "# Published ordinal guarantee (G3)",
        "",
        "Every number in this file is emitted by `python -m autorate.cli severity` and re-checked",
        "by `python -m autorate.cli verify`, which re-derives the certificate from the records file",
        "named below. None of them is typed, and the document carries no timestamp, so a re-run is",
        "byte-comparable -- in the corpus-present lane and in the corpus-absent one alike.",
        "",
        "## The certificate",
        "",
        "- artefact: `%s`, direction `%s` (the publication names the rule, and `verify` re-derives"
        " at it rather than reading it back out of the artefact)" % (cert_path, direction),
        "- certified from: `%s`" % records_path,
        "- verdict: %s" % verdict,
        "- risk target `alpha`: %.3f, tested at `delta`: %.3f, split `seed`: %s"
        % (cert.alpha, cert.delta, meta.get("seed")),
        "- reported level `ahat`: %s, over a rubric of %s levels" % (cert.ahat, meta.get("rubric_levels")),
        "- records calibration/evaluation: %d/%d, cases calibration/evaluation: %s/%s"
        % (cert.n_cal, cert.n_eval, meta.get("n_cal_cases"), meta.get("n_eval_cases")),
    ]
    if meta.get("protocol_digest"):
        lines.append("- produced under the frozen protocol: `meta.protocol_digest` = `%s`"
                     % meta["protocol_digest"])
    lines += ["", "## Verbatim summary", "", "```", cert.summary(), "```", "",
              "## Envelope", ""]
    lines += ["- %s" % line for line in cert.envelope]
    lines.append("")
    return "\n".join(lines)


RESPLIT_JSON = "data/resplit_200.json"
RESPLIT_MD = Path("docs/RESPLIT.md")
# The rubric keys the experiment records and the gate compares, one list so the arm and the denominator that
# counts it read one owner (R-168). `seed` is in the artefact's own `rubric` block, as `cli.RUBRIC_FIELDS`
# spells it for the certificates.
RESPLIT_RUBRIC_FIELDS = PUBLISHED_RUBRIC_FIELDS


def read_resplit(path: Path) -> dict:
    """The resplit experiment's document, read as the mapping the producer wrote and nothing looser.

    A `ValueError` here is answered by `load_published` with the named refusal at exit 4, because the path is
    declared by this table rather than typed by an operator: an absent or unreadable experiment file means a
    published G1 column cannot be reproduced, which is the checkout's failure, not the caller's (`#74`'s rule,
    applied to the newest artefact).
    """
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ValueError("the resplit experiment document is a JSON %s, not an object"
                         % type(doc).__name__)
    missing = sorted({"resplits", "rubric", "tasks", "rows"} - set(doc))
    if missing:
        raise ValueError("the resplit experiment document is missing %s" % missing)
    return doc


def resplit_invariants(doc: dict) -> list:
    """The statements the experiment document must satisfy about itself, as (label, actual, wanted) triples.

    These are comparisons of the artefact's own quantities against quantities the same artefact carries -- the
    gate's job here is to make an internally inconsistent experiment file a drift it can name, because a
    violation rate whose denominator does not match the certificate count would otherwise be a number with no
    producer. The expensive part (the seeded re-splits of every published decision task, plus a synthetic control, ~6
    minutes) stays the producer's: `tools/resplit_experiment.py` is the only writer, and re-running it
    reproduced these bytes exactly, so the digest that pins the experiment is its own, recorded in
    `docs/ERRATA.md` rather than asserted as a re-derivation.
    """
    out = []
    resplits = doc["resplits"]
    rows = doc["rows"]
    for task in sorted(doc["tasks"], key=lambda t: str(t["label"])):
        label = task["label"]
        issued = task["certificates_issued"]
        refused = sum(task["refusal_reasons"].values())
        out.append(("resplit %s: splits accounted for" % label, issued + refused, resplits))
        out.append(("resplit %s: rows per task" % label,
                    sum(1 for r in rows if r["label"] == label), resplits))
        out.append(("resplit %s: violations within the certified denominator" % label,
                    task["violations"] <= issued, True))
        rate = task["violation_rate"]
        expected = None if issued == 0 else task["violations"] / issued
        out.append(("resplit %s: violation rate is the ratio it claims" % label, rate, expected))
        out.append(("resplit %s: rate's denominator is the certificate count" % label,
                    task["violations_denominator"], issued))
        bounds = [task["bound_min"], task["bound_median"], task["bound_max"]]
        if all(b is not None for b in bounds):
            out.append(("resplit %s: the bound order holds" % label,
                        bounds[0] <= bounds[1] <= bounds[2], True))
    out.append(("resplit: every row names a published task",
                sorted({r["label"] for r in rows}) == sorted(str(t["label"]) for t in doc["tasks"]), True))
    return out


def rederive_resplit(expect, expect_rubric, rubric) -> None:
    """G1's second column, checked from the committed experiment file: invariants first, rubric second.

    `expect` is the gate's drift callback and `expect_rubric` its mismatch callback, both handed in rather than
    copied (`cmd_verify` owns the prefixes, and a second list of checks inside the gate could disagree with the
    list that counts them -- R-168). The rubric rows compare the experiment's own recorded rubric with the
    freeze: a rate measured at a budget nobody promised is not the number G1's column asked for, and the
    disagreement is reported as the freeze's word, not as a reproduction failure.
    """
    doc = load_published(RESPLIT_JSON, "report.RESPLIT_JSON", read_resplit)
    for label, actual, wanted in resplit_invariants(doc):
        expect(label, actual, wanted)
    recorded = doc["rubric"]
    for key in RESPLIT_RUBRIC_FIELDS:
        expect_rubric("resplit rubric.%s" % key, recorded.get(key), rubric[key])


def render_resplit(doc: dict, rubric: dict) -> str:
    """G1's second column as derived prose: every figure is read from the artefact, none is typed.

    The header names the command that writes the file and the gate that re-checks it, carries no timestamp and
    no machine path so both lanes byte-compare it, and states what the experiment does NOT show: the five
    published tasks certify in none of the splits, so the empirical rate is undefined for them and only the
    synthetic control -- labelled synthetic, and never cited as G1 evidence -- produces a number.
    """
    lines = [
        "# The 200-resplit experiment (G1's second column)",
        "",
        "Written by `python -m tools.resplit_experiment` and re-checked by `python -m autorate.cli",
        "verify`, which reads the artefact below and refuses it at exit 4 if it is absent or inconsistent.",
        "No figure here is typed: each is read out of `data/resplit_200.json`, and the document carries no",
        "timestamp so a re-run is byte-comparable in both lanes.",
        "",
        "- splits per task: %d" % doc["resplits"],
        "- rubric the experiment ran at: alpha %.3f, beta %.3f, delta %.3f, method `%s`, seed %s"
        % (rubric["alpha"], rubric["beta"], rubric["delta"], rubric["method"], rubric["seed"]),
        "- tasks: %d (the %d published decision tasks this repository certifies, plus one synthetic control"
        " whose labels are known)" % (len(doc["tasks"]), len(doc["tasks"]) - 1),
        "",
        "| task | splits certified | refusals | violations / certificates | empirical violation rate |",
        "|---|---|---|---|---|",
    ]
    for task in sorted(doc["tasks"], key=lambda t: str(t["label"])):
        refusals = ", ".join("%s:%d" % (reason, count)
                             for reason, count in sorted(task["refusal_reasons"].items())) or "-"
        rate = "undefined (no certificates)" if task["violation_rate"] is None \
            else "%.3f" % task["violation_rate"]
        lines.append("| `%s` | %d of %d | %s | %d / %d | %s |"
                     % (task["label"], task["certificates_issued"], doc["resplits"], refusals,
                        task["violations"], task["violations_denominator"], rate))
    lines += [
        "",
        "The rate is the empirical check G1's own column names: a violation is a certified split whose",
        "gold set escapes the bound that split published. It is undefined where no certificate exists -- no",
        "number is imputed, and a `0.000` appears only for a population that does certify. The %d"
        " published tasks refuse in every split at this rubric, which is why the criterion's first column"
        % (len(doc["tasks"]) - 1),
        "(`>=3 certified decision tasks`) is unmet and why this table is evidence about the refusal, not",
        "against it. The synthetic row is a control on the machinery, labelled synthetic in the artefact's",
        "own `label`, and is not cited as a decision task G1 counts.",
        "",
    ]
    return "\n".join(lines)


# --- G4's worst-slice run: the same certifier, on the slices the producer declares -------------------

SLICE_JSON = "data/slices_language.json"
SLICE_MD = Path("docs/SLICES.md")
SLICE_GROUP_KEY = "language"
SLICE_BACKEND = "laya"
# The committed MASSIVE record files this run is a function of, named in the order the producer
# concatenates them (sorted, so the artefact does not depend on a shell glob's mood). These are the inputs
# `verify` re-reads, which is why the list lives beside the artefact that quotes it rather than in the tool.
# Nothing here may be counted by a reader of this comment: the group count that every corrected budget
# divides by is `len(SLICE_RECORDS)` as the certifier computes it from the DATA, and `tests/` reads the
# same length -- the trio this tuple carried until task #68 is the set a fixture must not get to freeze.
SLICE_RECORDS = ("data/records_massive_de.jsonl",
                 "data/records_massive_en.jsonl",
                 "data/records_massive_km.jsonl",
                 "data/records_massive_sw.jsonl")
SLICE_RUBRIC_FIELDS = PUBLISHED_RUBRIC_FIELDS
# Four field lists, one owner each: the arm and the denominator that counts it read these (`R-168`), and an
# operator tampering with one published value has to be named by exactly one label.
# `worst_claim` and `n_min_violations` are in here because they ARE G4: the first names the slice whose
# refusal the criterion is about, the second says whether the size floor rather than a bound did the
# refusing. `thinnest` is neither -- it is the fewest-case slice with an alphabetical tie-break -- so a list
# that stopped at it would re-derive everything except the two claims being published.
SLICE_COMPARE_FIELDS = ("feasible", "any_slice_refused", "n_groups", "n_claims", "level",
                        "corrected_alpha", "corrected_beta", "corrected_delta", "thinnest",
                        "alpha", "beta", "delta", "groups")
# The joint worst-of-G claim, in the fields a reader of `docs/SLICES.md` is being asked to trust. These are
# named rather than compared as one `worst_claim` dictionary because that dictionary carries tuples and
# nested rows: a whole-mapping comparison drifts on JSON's list-versus-tuple round-trip, which is a
# representation fact about the file, not a disagreement about the claim. `n_min_violations` gets the same
# treatment as one joined row, so an artefact that hid a size-floor refusal is named.
SLICE_WORST_FIELDS = ("group", "joint_level", "joint_level_risk", "level", "metric")
SLICE_GROUP_FIELDS = ("feasible", "reason", "n_cal", "n_eval", "qhat", "autorate",
                      "conditional_error_bound", "marginal_error_bound")
SLICE_CENSUS_FIELDS = ("cases", "records", "eligible_cases", "kept",
                       "skipped_no_gold", "skipped_wrong_qtype")
SLICE_POOLED_FIELDS = ("feasible", "reason", "n_cal", "n_eval", "qhat", "autorate",
                       "conditional_error_bound", "marginal_error_bound")
SLICE_INPUT_FIELDS = ("rows", "digest")
# The spec's own name for the size-floor refusals (§10:208, and :214 makes the key non-optional in the
# output shape), spelled once so the loader's presence check, the arm's comparison label and the document's
# bullet all read the same string: a fourth spelling anywhere else is a fourth owner of a published field
# name. `certify_choice.GroupsCertificate` owns the field itself; this is the artefact-side name for it.
SLICE_N_MIN_KEY = "n_min_violations"
# The name the field carried before B3 Task 5 landed this name and this shape change together (the deferral
# R-149/2 recorded). It is declared ONLY so `read_slices` can refuse an artefact that carries it: no read in
# this build falls back to it, because a silent fallback would let a stale artefact verify green, and a shape
# change is a shape change.
SLICE_RETIRED_N_MIN_KEY = "refused_by_size"


def read_slices(path: Path) -> dict:
    """The slice experiment's document, read as the mapping its producer wrote and nothing looser.

    Shape only, and `ValueError` on purpose: `load_published` turns that into the named refusal at exit 4 for
    a table-declared artefact. The checks that a *value* is wrong belong to `rederive_slices`, which is the
    one holding the recomputation -- a reader here would need a second copy of the certifier to say more.
    What this function does police is the shape spec §10:214 mandates: the size-floor refusals arrive under
    `SLICE_N_MIN_KEY`, and a document without that key is refused rather than defaulted.
    """
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ValueError("the slice experiment document is a JSON %s, not an object"
                         % type(doc).__name__)
    missing = sorted({"backend", "group_key", "inputs", "producer", "rubric", "run"} - set(doc))
    if missing:
        raise ValueError("the slice experiment document is missing %s" % missing)
    run = doc["run"]
    if not isinstance(run, dict):
        raise ValueError("the slice experiment's `run` is a %s, not the certification document"
                         % type(run).__name__)
    absent = sorted(set(SLICE_COMPARE_FIELDS) - set(run))
    if absent:
        raise ValueError("the slice experiment's `run` is missing %s" % absent)
    # Spec §10:214: the key is not optional in the output shape, so its absence is refused HERE rather than
    # defaulted. The requirement is PRESENCE and not non-emptiness -- `[]` is the fact that no slice fell
    # below the size floor, which is what the committed artefact states -- and the retired name is checked
    # only to be named in the refusal, never read as a fallback: an artefact written before the rename is
    # stale, and forgiving it would let the floor go unrun.
    if SLICE_N_MIN_KEY not in run:
        raise ValueError(
            "the slice experiment's `run` carries no %r key, which spec §10:214 makes non-optional in the "
            "output shape: an empty list is the fact that no slice was refused by the size floor, so the "
            "key's absence is a shape violation and not a result%s -- regenerate it with `python3 "
            "tools/language_slices.py --out %s --doc %s --force`"
            % (SLICE_N_MIN_KEY,
               (", and it carries %r in its place: that is the name this field had before the rename that "
                 "changed its shape, and this build reads one name with no fallback to the other"
                % SLICE_RETIRED_N_MIN_KEY) if SLICE_RETIRED_N_MIN_KEY in run else "",
               SLICE_JSON, SLICE_MD))
    if not isinstance(doc["inputs"], list):
        raise ValueError("the slice experiment's `inputs` is a %s, not a list of the files it read"
                         % type(doc["inputs"]).__name__)
    # The budgets are handed to the certifier as keywords, so a rubric block carrying a name the certifier
    # does not take would answer with `TypeError` -- an unmapped exit 1 on a path `verify` walks in both
    # lanes. Refusing the shape here is the difference between exit 4 and a traceback.
    extra = sorted(set(doc["rubric"]) - set(SLICE_RUBRIC_FIELDS))
    if extra:
        raise ValueError("the slice experiment records budget keys %s, which the certifier does not take"
                         % extra)
    gap = sorted(set(SLICE_RUBRIC_FIELDS) - set(doc["rubric"]))
    if gap:
        raise ValueError("the slice experiment records no value for %s" % gap)
    # Shape, not just presence. Six of these arms exist because each nested value is read further down -- as a
    # mapping to index, a list to join, or a row to look a key up in -- and a JSON type that arrives from a
    # tampered or stale file answers with `TypeError`/`AttributeError`, which `main` cannot map: exit 1 on the
    # path whose whole contract is 0/2/3/4. `_row_list` refuses the shape where it is read, so the gate's
    # answer is the named refusal at exit 4 that `docs/SLICES.md` promises.
    _named_list(run.get("groups"), "run.groups", strings=True)
    _named_list(run.get("envelope"), "run.envelope", strings=True)
    for name, value in (("inputs", doc["inputs"]),
                        ("run.slice_census", run.get("slice_census")),
                        ("run.%s" % SLICE_N_MIN_KEY, run[SLICE_N_MIN_KEY])):
        _row_list(value, name, ("group",) if name != "inputs" else SLICE_INPUT_FIELDS)
    if not isinstance(run.get("per_group"), dict) or any(
            not isinstance(cert, dict) for cert in run["per_group"].values()):
        raise ValueError("the slice experiment's `per_group` is not a mapping of slice name to certificate")
    for name in ("worst_claim", "pooled"):
        if name in run and not isinstance(run[name], dict):
            raise ValueError("the slice experiment's `run.%s` is a %s, not the mapping the run publishes"
                             % (name, type(run[name]).__name__))
    return doc


def _named_list(value, label: str, strings: bool = False) -> None:
    """Refuse a list-shaped field that is not a list (or not a list of strings, where it says so)."""
    if not isinstance(value, list):
        raise ValueError("the slice experiment's `%s` is a %s, not a list" % (label, type(value).__name__))
    if strings and any(not isinstance(item, str) for item in value):
        raise ValueError("the slice experiment's `%s` holds a %s, not strings"
                         % (label, next(type(i).__name__ for i in value if not isinstance(i, str))))


def _row_list(value, label: str, keys) -> None:
    """Refuse rows that are not mappings carrying the keys the arm looks up by name."""
    if not isinstance(value, list):
        raise ValueError("the slice experiment's `%s` is a %s, not a list of rows"
                         % (label, type(value).__name__))
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("the slice experiment's `%s` holds a %s, not a row object"
                             % (label, type(row).__name__))
        absent = sorted(set(keys) - set(row))
        if absent:
            raise ValueError("the slice experiment's `%s` has a row missing %s" % (label, absent))


def slice_inputs() -> tuple:
    """`(records, per-file rows-and-digests)` for the committed files this run is a function of.

    Read through `load_records`, the same reader the MASSIVE certificates use, so the slice arm certifies the
    doubles the published certificates were built from. A declared file that is absent is `require_published`'s
    named refusal; a declared file that carries no rows for `SLICE_BACKEND` is a refusal raised here, because
    certifying a silently-empty pool would publish a bound over nobody.
    """
    records, inputs = [], []
    for rel in sorted(SLICE_RECORDS):
        path = require_published(Path(rel), "report.SLICE_RECORDS")
        by_backend = load_records(path)
        if SLICE_BACKEND not in by_backend:
            raise PublishedArtefactUnavailable(
                "%s is declared published by report.SLICE_RECORDS and carries no rows for backend %r "
                "(it holds %s); the slice run is certified over that backend, so this is the checkout's "
                "failure and no argument selected the path" % (rel, SLICE_BACKEND, sorted(by_backend)))
        rows = by_backend[SLICE_BACKEND]
        records.extend(rows)
        inputs.append({"path": rel, "rows": len(rows),
                       "digest": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records, inputs


def rederive_slices(expect, expect_rubric, rubric=None) -> None:
    """G4's run, recomputed from every committed MASSIVE record file and compared field by field.

    This arm re-runs the certifier rather than auditing the artefact's arithmetic, because the run costs
    seconds; a published slice certificate the certifier disagrees with is drift with a field name on it. The
    budgets come from the freeze when one is in hand -- `rederive_massive`'s rule -- so that editing the
    artefact's own `rubric` block cannot quietly redefine what the recomputation is measured at: that edit is
    the freeze's disagreement, and it prints as `RUBRIC MISMATCH`.

    Every nested read is `.get`, never `[...]`. A tampered or stale artefact that lacks a slice has to answer
    with a named drift, and `KeyError` would leave `main` unmapped at exit 1 -- the contract this surface is
    held to (R-115's class of escape).
    """
    doc = load_published(SLICE_JSON, "report.SLICE_JSON", read_slices)
    published = doc["run"]
    chosen = dict(doc["rubric"])
    if rubric:
        chosen.update({k: rubric[k] for k in SLICE_RUBRIC_FIELDS if k in rubric})
    records, inputs = slice_inputs()
    fresh = certify_choice(records, groups=[SLICE_GROUP_KEY], **chosen).to_dict()

    for name in SLICE_COMPARE_FIELDS:
        expect("slice %s" % name, fresh.get(name), published.get(name))

    names = sorted(set(fresh.get("per_group", {})) | set(published.get("per_group", {})))
    for group in names:
        for field in SLICE_GROUP_FIELDS:
            expect("slice per_group.%s.%s" % (group, field),
                   fresh.get("per_group", {}).get(group, {}).get(field),
                   published.get("per_group", {}).get(group, {}).get(field))

    def census_of(cert):
        out = {}
        for row in cert.get("slice_census", []) or []:
            out[str(row.get("group"))] = row
        return out

    fresh_census, published_census = census_of(fresh), census_of(published)
    for group in sorted(set(fresh_census) | set(published_census)):
        for field in SLICE_CENSUS_FIELDS:
            expect("slice census.%s.%s" % (group, field),
                   fresh_census.get(group, {}).get(field), published_census.get(group, {}).get(field))

    for field in SLICE_POOLED_FIELDS:
        expect("slice pooled.%s" % field,
               fresh.get("pooled", {}).get(field), published.get("pooled", {}).get(field))

    expect("slice envelope", list(fresh.get("envelope", [])), list(published.get("envelope", [])))

    def worst_of(cert):
        claim = cert.get("worst_claim") or {}
        claim = claim if isinstance(claim, dict) else {}
        worst = claim.get("worst")
        out = dict(claim)
        out["group"] = _group_of(worst) if worst is not None else None
        return out

    fresh_worst, published_worst = worst_of(fresh), worst_of(published)
    for name in SLICE_WORST_FIELDS:
        expect("slice worst_claim.%s" % name, fresh_worst.get(name), published_worst.get(name))
    expect("slice %s" % SLICE_N_MIN_KEY, _join_groups(fresh.get(SLICE_N_MIN_KEY)),
           _join_groups(published.get(SLICE_N_MIN_KEY)))

    recorded_inputs = {str(row.get("path")): row for row in doc["inputs"]}
    for row in inputs:
        for field in SLICE_INPUT_FIELDS:
            expect("slice inputs.%s.%s" % (row["path"], field), row[field],
                   recorded_inputs.get(row["path"], {}).get(field))

    for key in SLICE_RUBRIC_FIELDS:
        expect_rubric("slice rubric.%s" % key, doc["rubric"].get(key), rubric[key] if rubric else None)


def _group_of(row) -> str:
    """The slice name a `n_min_violations` entry carries, whether it is a row or a bare name."""
    return str(row.get("group")) if isinstance(row, dict) else str(row)


def _join_groups(rows) -> str:
    return ", ".join(_group_of(row) for row in rows or [])


def _null_metric_count(run: dict) -> int:
    """How many slices carry no value for the metric the joint claim ranked them on."""
    return sum(1 for cert in run["per_group"].values() if cert.get("autorate") is None)


def _worst_sentence(run: dict) -> str:
    """The worst-slice line, with the metric's own coverage stated so a tie-break cannot read as a ranking.

    The branch is derived from the run, not chosen by the author: all-null says the field names a tie-break,
    none-null says the metric separated the slices, and a partial population says which slices it could not
    see. `docs/SLICES.md` is byte-compared, so without this the document could keep the old phrasing after a
    run started certifying.
    """
    metric = run["worst_claim"]["metric"]
    nulls, total = _null_metric_count(run), len(run["per_group"])
    head = "- worst slice of the joint claim: `%s`, ranked on `%s`; `%s` is null in %d of the %d slices" % (
        _worst_group(run), metric, metric, nulls, total)
    if nulls == total and total:
        return head + ", so the field names a tie-break and not a measured worst"
    if nulls == 0:
        return head + ", so every slice carries the metric this run ranked"
    return head + ", so the ranking below is made only over the slices that carry it"


def _worst_group(run: dict) -> str:
    """The slice the joint worst-of-G claim names, read defensively: the claim is a mapping of shape
    `worst_claim.worst.group`, and a run that has not got that far says so rather than raising."""
    worst = (run.get("worst_claim") or {}).get("worst")
    if isinstance(worst, dict):
        return str(worst.get("group"))
    return str(worst)


def render_slices(doc: dict) -> str:
    """G4's run as derived prose: every figure is read out of the artefact, and none is typed.

    No timestamp and no machine path, so both lanes byte-compare it. The framing sentences are allowed to say
    what the numbers do NOT cover -- the criterion's own example slice has no per-case rows here -- because a
    reader who cannot see the boundary of a published claim has only the claim.
    """
    run = doc["run"]
    per_group = run.get("per_group", {})
    lines = [
        "# The language-slice certification (G4)",
        "",
        "Written by `python3 tools/language_slices.py --out data/slices_language.json` and re-checked by",
        "`python -m autorate.cli verify`, which recomputes this run from the committed record files named",
        "below and refuses the artefact at exit 4 if it is absent or unreadable.",
        "",
        "G4 asks for a behaviour: with a simultaneous correction over the slices, the **worst slice must",
        "refuse**, and the pooled bound must not be allowed to average that refusal away. This is that run.",
        "",
        "- group key: `%s`, backend `%s`" % (doc["group_key"], doc["backend"]),
        "- slices: %d (%s), claims per slice: %d" % (run["n_groups"], ", ".join(run["groups"]), run["n_claims"]),
        "- budgets as certified: alpha=%s beta=%s delta=%s" % (run["alpha"], run["beta"], run["delta"]),
        "- corrected per slice: alpha=%s delta=%s (beta is not divided, and says so below)"
        % (run["corrected_alpha"], run["corrected_delta"]),
        "- joint level: %s" % run["level"],
        "- thinnest slice by case count: `%s`" % run["thinnest"],
        _worst_sentence(run),
        "- the run certifies: %s; any slice refused: %s" % (run["feasible"], run["any_slice_refused"]),
        "- slices refused by the size floor (`%s`): %d (%s)"
        % (SLICE_N_MIN_KEY, len(run.get(SLICE_N_MIN_KEY, [])),
           _join_groups(run.get(SLICE_N_MIN_KEY, [])) or "none"),
        "",
        "## Per slice",
        "",
        "| slice | feasible | reason | n_cal | n_eval | qhat | autorate |",
        "|---|---|---|---|---|---|---|",
    ]
    for group in sorted(per_group):
        cert = per_group[group]
        lines.append("| %s | %s | %s | %s | %s | %s | %s |"
                     % (group, cert.get("feasible"), cert.get("reason"), cert.get("n_cal"),
                        cert.get("n_eval"), cert.get("qhat"), cert.get("autorate")))
    pooled = run.get("pooled", {})
    lines += [
        "",
        "## The pooled (marginal) certificate over the same records",
        "",
        "Published beside the slices, never in place of them: it answers a different question, and a reader",
        "who wants the worst-case permission has to read the slice rows above.",
        "",
        "- feasible: %s, reason: %s" % (pooled.get("feasible"), pooled.get("reason")),
        "- denominator: n_cal=%s n_eval=%s, qhat=%s, autorate=%s"
        % (pooled.get("n_cal"), pooled.get("n_eval"), pooled.get("qhat"), pooled.get("autorate")),
        "- exact bounds: conditional=%s marginal=%s"
        % (pooled.get("conditional_error_bound"), pooled.get("marginal_error_bound")),
        "",
        "## Inputs this run is a function of",
        "",
        "| path | rows | sha256 |",
        "|---|---|---|",
    ]
    for row in doc["inputs"]:
        lines.append("| %s | %s | %s |" % (row["path"], row["rows"], row["digest"]))
    lines += ["", "## Assumptions the run states about itself", ""]
    for line in run.get("envelope", []):
        lines.append("- %s" % line)
    lines += [
        "",
        "## What this does not show",
        "",
        "The criterion names its example slice by name, and that slice is in this run: it is certified at",
        "the divided budget like every other slice, and it refuses here rather than being quoted from",
        "upstream's README. What the run still does not show is the second axis the criterion names. This",
        "is a run over the one key the producer declares, so a cross of (language x option-count) is not",
        "published here, and a table that pretended to condition on the count would be an overclaim about",
        "a quantity that does not vary across these records. And the accuracy and mean-confidence figures",
        "the criterion quotes beside its example are upstream's measurement on its own sample: this",
        "artefact publishes a refusal, a denominator and a bound-or-no-bound per slice, and it is not the",
        "owner of anyone's accuracy. The reconciliation of those two readings is `docs/ERRATA.md`'s.",
        "",
    ]
    return "\n".join(lines)


# --- G1's feasibility ceiling: which automated size could certify at all, at this rubric -------------
#
# Spec §2's G1 asks for ">=3 decision tasks certified at `autorate(alpha = 0.05)`". This tree publishes the
# scored decision tasks its own certificates name, certifies none of them, and `data/resplit_200.json` shows
# no seeded split certifying for any of them. The stronger statement -- that **no automated size certifies on this evidence base
# at this budget** -- existed only in an untracked scratch probe, and this project has already ruled that a
# simulation performed and deleted is not evidence (`docs/G5.md` is that ruling's artifact). Everything below
# is the ceiling turned into committed bytes with a producer, a document rendered from them, and a `verify`
# arm that recomputes every figure from `tails.py` and the published certificates.
#
# Two owners are respected here and neither is this file's opinion. `tails.py` owns the arithmetic
# (`clopper_pearson_upper`, `bound_width`, `n_feasible`) and `certificate.canonicalise_bound` owns the
# precision a published bound is stored at; `inventory.corpus_options` owns the two feasibility bars this arm
# quotes, so the ceiling is stated in the same currency as `data/inventory.md`.

G1_FEASIBILITY_JSON = "data/g1_feasibility.json"
G1_FEASIBILITY_MD = Path("docs/FEASIBILITY.md")
G1_FEASIBILITY_PRODUCER = "tools/g1_feasibility.py"
G1_FEASIBILITY_RUBRIC_FIELDS = PUBLISHED_RUBRIC_FIELDS
# The probe's size ladder, kept because a reader needs a scale beside the per-task rows: 100, 300 and 1,000
# automated decisions. The probe's fourth row (2,974) is NOT declared here -- it is `n_eval + n_cal` of the
# three MASSIVE certificates, so the arm re-derives that size from the artefacts rather than remembering it.
G1_FEASIBILITY_SIZES = (100, 300, 1000)
G1_FEASIBILITY_SIZES_BASIS = "declared by report.G1_FEASIBILITY_SIZES (the probe's scale)"
# Rates and widths are published at the precision the existing published documents render them at: six
# decimals for a bound or a rate (`docs/RESULTS.md`), four for a DKW width (`inventory.py`'s own
# `round(bound_width(n), 4)`). Neither is a tolerance: the comparison the gate makes is between two numbers
# produced the same way from the same inputs.
G1_FEASIBILITY_RATE_DECIMALS = 6
G1_FEASIBILITY_WIDTH_DECIMALS = 4
# The reference ladder: what a gate that automates `n` decisions may get wrong and still clear alpha.
G1_FEASIBILITY_REFERENCE_FIELDS = ("n", "size_from", "k_max", "cp_k_max", "cp_k_max_plus_1",
                                   "largest_certifiable_error_rate", "required_observed_accuracy",
                                   "cp_zero_errors", "bound_width", "feasible_at_0.10", "feasible_at_0.25")
# One row per scored corpus. Every column names the unit it is computed over: `_records` is the record
# denominator at the refusal's diagnostic `closest_attempt` grid point, `_cases` is the case denominator at
# the requested alpha -- the certificate's own unit (R-44). The two systems sit beside each other in
# `meta.at_requested_alpha`, which publishes record counts (`automated`, `errors`) and a CASE bound under
# one name (ledger #37); this table refuses to inherit that mixing, which is why each unit's bound is
# recomputed from that unit's own counts.
G1_FEASIBILITY_ROW_FIELDS = ("task", "artefact", "table", "feasible", "reason",
                             "closest_attempt_published", "row_refusal",
                             "n_eval_records", "n_cal_records", "automated_records", "errors_records",
                             "grid_alpha", "k_max_records", "cp_k_max_records", "cp_k_max_plus_1_records",
                             "published_closest_bound", "recomputed_closest_bound",
                             "n_eval_cases", "n_cal_cases", "automated_cases", "errors_cases",
                             "k_max_cases", "cp_k_max_cases", "cp_k_max_plus_1_cases",
                             "published_case_bound", "recomputed_case_bound",
                             "bound_width_records", "bound_width_cases",
                             "feasible_at_0.10_records", "feasible_at_0.10_cases",
                             "feasible_at_0.25_records", "feasible_at_0.25_cases",
                             "pool_is_automated_set", "oracle_ceiling_records", "oracle_ceiling_cases",
                             "missing_pool_input")
# The sentence a row carries when the pool's error count is not one of the artefact's fields. Named here
# because `read_g1_feasibility`'s contract is that a `null` ceiling always arrives with a reason, and a
# reason a reader cannot grep for is a null that will later be imputed.
G1_FEASIBILITY_NO_POOL_ERRORS = ("meta.errors_among_automated counts the errors INSIDE the automated set, "
                                 "not the errors of the evaluated pool; no published field of this "
                                 "certificate gives the pool count, so the oracle ceiling is not computable "
                                 "from these bytes")
G1_FEASIBILITY_NO_GOLD = "no gold labels in this offline cache"


def g1_bound(k: int, n: Optional[int], alpha: float, delta: float) -> Optional[float]:
    """One published-precision upper bound, or `None` where there is no denominator to bound a rate with.

    The ceil is `certificate.canonicalise_bound`, the same mechanism `certify_choice`, `audit` and `severity`
    apply before a Clopper-Pearson double crosses into a committed artefact. It is reached through this
    module's name so the ceiling's central predicate is visibly the published-precision comparison and not a
    bare `==` on a raw float: `data/cert_massive_en_laya.json` stores `0.064239163974` where this machine's
    libm answers `0.064239163973131` (tails.py documents the last-ULP drift, ledger R-121). A raw equality
    would call that published artefact drift; a looser tolerance would pass a tampered one.
    """
    if n is None or n <= 0:
        return None
    return canonicalise_bound(clopper_pearson_upper(k, n, delta))


def g1_k_max(n: Optional[int], alpha: float, delta: float) -> Optional[int]:
    """The largest error count whose upper bound still clears `alpha` at an automated size of `n`.

    The gate's own pass condition, as the committed refusals use it: `certify_choice` refuses when
    `canonicalise_bound(clopper_pearson_upper(err, auto, delta)) > beta`. Bisection, not a scan: the bound is
    non-decreasing in `k`, so `2 * ceil(log2(n))` evaluations answer the question instead of `n` -- which is
    what keeps this arm affordable inside a gate CI runs on two lanes.

    `None` is a result and not a crash: at `n = 0` there is no automated denominator, and at a small `n` even
    a zero-error run fails (`g1_bound(0, 32, .)` is 0.089, so `jev`'s 32 cases have no certifiable error
    count at all). Both answer `None`, and the row publishes it rather than a `0` that would read as
    "zero errors are allowed".
    """
    if n is None or n <= 0:
        return None
    if g1_bound(0, n, alpha, delta) >= alpha:
        return None
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if g1_bound(mid, n, alpha, delta) < alpha:
            lo = mid
        else:
            hi = mid - 1
    return lo


def g1_rate(value: Optional[float]) -> Optional[float]:
    """A rate or bound at the precision this repository publishes rates at, and never a looser compare."""
    return None if value is None else round(value, G1_FEASIBILITY_RATE_DECIMALS)


def g1_width(n: Optional[int], alpha: float) -> Optional[float]:
    """`tails.bound_width`, at the four decimals `inventory.py` renders its width column with."""
    if n is None or n <= 1:
        return None
    return round(bound_width(n, alpha), G1_FEASIBILITY_WIDTH_DECIMALS)


def g1_bars(n: Optional[int], alpha: float) -> tuple:
    """Inventory's own two feasibility bars, from `tails.n_feasible` and nothing else."""
    if n is None or n <= 1:
        return None, None
    return (bool(n_feasible(n, alpha=alpha, max_bound_width=0.10)),
            bool(n_feasible(n, alpha=alpha, max_bound_width=0.25)))


def g1_oracle_ceiling(pool: Optional[int], errors: Optional[int],
                      alpha: float, delta: float) -> Optional[int]:
    """The largest automated size a PERFECT gate could certify: the ceiling, not an achievement.

    For a pool of `pool` decisions carrying `errors` errors, an oracle that automates `n_a` of them cannot
    move more than `pool - n_a` errors out of the automated set, so it retains at least
    `max(0, errors - (pool - n_a))`; that many must fit inside `g1_k_max(n_a)`. The answer is the largest
    `n_a` that satisfies it, and 0 states that no positive automated size certifies -- which is a different
    claim from `None`, reserved for a row whose pool error count is not published at all.

    The scan is bounded, not linear in the pool: retained errors can only be positive while
    `n_a > pool - errors`, and at or below that size the question collapses to whether a zero-error run
    clears alpha -- a predicate monotone in `n_a`, so one more evaluation answers it.
    """
    if pool is None or errors is None or pool <= 0:
        return None
    for n_a in range(pool, max(pool - errors, 1) - 1, -1):
        retained = max(0, errors - (pool - n_a))
        k = g1_k_max(n_a, alpha, delta)
        if k is not None and retained <= k:
            return n_a
    zero_size = pool - errors
    if zero_size > 0 and g1_k_max(zero_size, alpha, delta) is not None:
        return zero_size
    return 0


def g1_reference_row(n: int, size_from: str, alpha: float, delta: float) -> dict:
    """One ladder row: what an automated set of `n` may get wrong and still clear alpha at this rubric."""
    k = g1_k_max(n, alpha, delta)
    rate = None if k is None or not n else round(k / n, G1_FEASIBILITY_RATE_DECIMALS)
    bar_010, bar_025 = g1_bars(n, alpha)
    return {"n": n, "size_from": size_from, "k_max": k,
            "cp_k_max": None if k is None else g1_bound(k, n, alpha, delta),
            "cp_k_max_plus_1": None if k is None else g1_bound(k + 1, n, alpha, delta),
            "largest_certifiable_error_rate": rate,
            "required_observed_accuracy": None if rate is None else g1_rate(1.0 - rate),
            "cp_zero_errors": g1_rate(g1_bound(0, n, alpha, delta)),
            "bound_width": g1_width(n, alpha),
            "feasible_at_0.10": bar_010, "feasible_at_0.25": bar_025}


def g1_reference_rows(certificates: dict, alpha: float, delta: float) -> list:
    """The declared ladder, plus every published task's own full pool size.

    `n_eval + n_cal` is the labelled population the certificate split into halves, and it is the only size in
    this table that is not an input: reading it from the artefacts means a fourth language joining
    `report.MASSIVE_CERTIFICATES` adds a ladder row by itself, and a pool whose halves were edited reddens the
    row that quotes them. Sizes are deduplicated -- the three MASSIVE tasks share 2,974 -- and every
    contributing artefact is named in `size_from`.
    """
    pools: dict = {}
    for task, (_path, _table, cert) in sorted(certificates.items()):
        size = cert.n_eval + cert.n_cal
        pools.setdefault(size, []).append(task)
    rows = [g1_reference_row(n, G1_FEASIBILITY_SIZES_BASIS, alpha, delta)
            for n in sorted(G1_FEASIBILITY_SIZES)]
    rows += [g1_reference_row(size, "n_eval + n_cal of %s" % ", ".join(sorted(
        str(CERTS.get(task) or MASSIVE_CERTIFICATES[task][1]) for task in names)), alpha, delta)
        for size, names in sorted(pools.items())]
    rows.sort(key=lambda row: row["n"])
    return rows


def g1_task_row(task: str, artefact: str, table: str, cert, alpha: float, delta: float) -> dict:
    """One published certificate, read as a ceiling: both denominators, neither compared against the other.

    Nothing in here re-runs the certifier or reads a corpus -- the inputs are the bytes of the committed
    artefact and the rubric the freeze promised, which is what lets BOTH `verify` lanes reproduce it.
    """
    meta = cert.meta
    closest = meta.get("closest_attempt")
    at_requested = meta.get("at_requested_alpha")
    row = {name: None for name in G1_FEASIBILITY_ROW_FIELDS}
    row.update({"task": task, "artefact": artefact, "table": table,
                "feasible": cert.feasible, "reason": cert.reason,
                "n_eval_records": cert.n_eval, "n_cal_records": cert.n_cal,
                "n_eval_cases": meta.get("n_eval_cases"), "n_cal_cases": meta.get("n_cal_cases"),
                "automated_cases": meta.get("automated_cases"),
                "errors_cases": meta.get("erroneous_cases"),
                "published_case_bound": (at_requested or {}).get("conditional_error_bound")})
    row["bound_width_cases"] = g1_width(row["n_eval_cases"], alpha)
    row["feasible_at_0.10_cases"], row["feasible_at_0.25_cases"] = g1_bars(row["n_eval_cases"], alpha)
    k_cases = g1_k_max(row["automated_cases"], alpha, delta)
    row["k_max_cases"] = k_cases
    if k_cases is not None:
        row["cp_k_max_cases"] = g1_bound(k_cases, row["automated_cases"], alpha, delta)
        row["cp_k_max_plus_1_cases"] = g1_bound(k_cases + 1, row["automated_cases"], alpha, delta)
    row["recomputed_case_bound"] = g1_bound(row["errors_cases"], row["automated_cases"], alpha, delta)

    if not isinstance(closest, dict):
        # A refusal with no diagnostic attempt (`certify_score.py`'s ordinal certificates publish
        # `closest_attempt: None`) says so as a refusal. The case-unit columns above are still this
        # artefact's bytes; the record-unit ones, and anything built from them, stay null.
        row["closest_attempt_published"] = False
        row["row_refusal"] = ("meta.closest_attempt is %s, so this artefact publishes no automated size at a "
                              "diagnostic grid point; the record-unit ceiling is not computable from these "
                              "bytes" % ("absent" if closest is None and "closest_attempt" not in meta
                                         else "null"))
        return row
    automated = closest.get("automated")
    errors = closest.get("errors")
    row["closest_attempt_published"] = True
    row["automated_records"] = automated
    row["errors_records"] = errors
    row["grid_alpha"] = closest.get("grid_alpha")
    row["published_closest_bound"] = closest.get("conditional_error_bound")
    row["recomputed_closest_bound"] = g1_bound(errors, automated, alpha, delta)
    row["bound_width_records"] = g1_width(row["n_eval_records"], alpha)
    row["feasible_at_0.10_records"], row["feasible_at_0.25_records"] = g1_bars(row["n_eval_records"], alpha)
    k_records = g1_k_max(automated, alpha, delta)
    row["k_max_records"] = k_records
    if k_records is not None:
        row["cp_k_max_records"] = g1_bound(k_records, automated, alpha, delta)
        row["cp_k_max_plus_1_records"] = g1_bound(k_records + 1, automated, alpha, delta)

    # The oracle column needs the errors of the POOL. A certificate publishes the errors inside the automated
    # set, so the pool count is available exactly when the automated set IS the pool -- a condition read off
    # this artefact's own two denominators, in both units, rather than assumed from a grid point that
    # happens to sit at full automation.
    pool_is_set = (automated == row["n_eval_records"]
                   and row["automated_cases"] == row["n_eval_cases"]
                   and row["automated_cases"] is not None)
    row["pool_is_automated_set"] = pool_is_set
    if pool_is_set:
        row["oracle_ceiling_records"] = g1_oracle_ceiling(row["n_eval_records"], errors, alpha, delta)
        row["oracle_ceiling_cases"] = g1_oracle_ceiling(row["n_eval_cases"], row["errors_cases"],
                                                        alpha, delta)
    else:
        row["missing_pool_input"] = G1_FEASIBILITY_NO_POOL_ERRORS
    return row


def g1_typed_decisions_row(alpha: float, delta: float) -> dict:
    """The one corpus where the wall is the error rate rather than the bound width -- and it is not scored.

    `typed_decisions` is the inventory's own row, and the inventory publishes no independent-case count for
    it (`n_independent: null`, basis "dataset card size category only; no file opened"), because this
    machine's cache holds the checkpoint but no gold labels. So every computed column is null with the
    missing input named. The scratch probe's figures for this corpus (2,000 held-out decisions, a published
    accuracy of 0.766, an oracle ceiling of 1,597) are QUOTED from upstream `BENCHMARKS.md` and are therefore
    kept out of these bytes entirely: this row publishes only what committed bytes say, which is nothing.
    """
    from .inventory import corpus_options, massive_pin

    declared = {option["id"]: option
                for option in corpus_options(None, pin=massive_pin())}.get("typed_decisions")
    row = {name: None for name in G1_FEASIBILITY_ROW_FIELDS}
    n_independent = None if declared is None else declared.get("n_independent")
    row.update({"task": "typed_decisions", "artefact": INVENTORY_JSON,
                "table": "inventory.corpus_options", "row_refusal": G1_FEASIBILITY_NO_GOLD,
                "missing_pool_input": G1_FEASIBILITY_NO_GOLD,
                "closest_attempt_published": None,
                "bound_width_cases": g1_width(n_independent, alpha)})
    row["feasible_at_0.10_cases"], row["feasible_at_0.25_cases"] = g1_bars(n_independent, alpha)
    return row


def g1_published_certificates() -> dict:
    """`{task: (artefact_path, table_name, certificate)}` for every published decision task, from the tables.

    `massive_certificates()` is reused rather than re-read here: it is the one path that opens the MASSIVE
    artefacts through `load_published`, so this arm cannot end up walking a different set of files from the
    one the report prints and `verify` re-derives.
    """
    out = {backend: (path, "report.CERTS",
                     load_published(path, "report.CERTS", read_certificate))
           for backend, path in sorted(CERTS.items())}
    for label, (_rows, cert) in sorted(massive_certificates().items()):
        out[label] = (MASSIVE_CERTIFICATES[label][1], "report.MASSIVE_CERTIFICATES", cert)
    return out


def build_g1_feasibility(rubric: dict) -> dict:
    """The whole ceiling document: the rubric it is measured at, the ladder, and one row per corpus.

    One owner for the arithmetic, called by the producer that writes these bytes AND by
    `rederive_g1_feasibility`, which is what makes the committed file a re-derivation rather than a
    transcription. A document that only audited its own sums would let a stale ceiling pass; this one is
    recomputed from `tails.py` and the certificates every time the gate runs.
    """
    alpha, delta = rubric["alpha"], rubric["delta"]
    certificates = g1_published_certificates()
    rows = [g1_task_row(task, path, table, cert, alpha, delta)
            for task, (path, table, cert) in sorted(certificates.items())]
    rows.append(g1_typed_decisions_row(alpha, delta))
    return {"producer": G1_FEASIBILITY_PRODUCER,
            "rubric": {key: rubric[key] for key in G1_FEASIBILITY_RUBRIC_FIELDS},
            "reference": g1_reference_rows(certificates, alpha, delta),
            "rows": rows}


def read_g1_feasibility(path: Path) -> dict:
    """The ceiling document, read as the mapping its producer wrote and nothing looser.

    Shape only, and `ValueError` on purpose -- `load_published` turns that into the named refusal at exit 4
    for a path this table declares rather than an operator named (`read_slices`' ruling, inherited). The
    checks that a *value* is wrong belong to `rederive_g1_feasibility`, which is the one holding the
    recomputation; what this function can honestly police is that the mapping and its rows are shaped so
    the arm and the renderer can index them without a `TypeError` escaping at rc 1.
    """
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ValueError("the G1 feasibility document is a JSON %s, not an object" % type(doc).__name__)
    missing = sorted({"producer", "rubric", "reference", "rows"} - set(doc))
    if missing:
        raise ValueError("the G1 feasibility document is missing %s" % missing)
    extra = sorted(set(doc["rubric"]) - set(G1_FEASIBILITY_RUBRIC_FIELDS))
    if extra:
        raise ValueError("the G1 feasibility document records budget keys %s, which this build does not read"
                         % extra)
    gap = sorted(set(G1_FEASIBILITY_RUBRIC_FIELDS) - set(doc["rubric"]))
    if gap:
        raise ValueError("the G1 feasibility document records no value for %s" % gap)
    if not isinstance(doc["reference"], list) or not isinstance(doc["rows"], list):
        raise ValueError("the G1 feasibility document's `reference` and `rows` must both be lists of rows")
    for name, value, keys in (("reference", doc["reference"], G1_FEASIBILITY_REFERENCE_FIELDS),
                              ("rows", doc["rows"], G1_FEASIBILITY_ROW_FIELDS)):
        for i, row in enumerate(value):
            if not isinstance(row, dict):
                raise ValueError("the G1 feasibility document's `%s`[%d] is a %s, not a row object"
                                 % (name, i, type(row).__name__))
            absent = sorted(set(keys) - set(row))
            if absent:
                raise ValueError("the G1 feasibility document's `%s`[%d] is missing %s"
                                 % (name, i, absent))
    return doc


def rederive_g1_feasibility(expect, expect_rubric, rubric=None) -> None:
    """G1's ceiling, recomputed from `tails.py` and the published certificates, field by field.

    The arm calls the producer's own builder -- `build_g1_feasibility` -- because one owner for the
    arithmetic is what makes the committed file a re-derivation rather than a transcription: a stale
    ladder row, a moved `k_max`, or an oracle ceiling that contradicts the certificates' bytes is drift
    with a field name on it, printed by the gate in BOTH lanes (nothing here reads the corpus). The
    budgets come from the freeze when one is in hand, `rederive_slices`' rule: editing the artefact's own
    `rubric` block cannot redefine what the recomputation is measured at, it prints as `RUBRIC MISMATCH`.

    Every nested read is `.get`, never `[...]` -- a stale artefact that lost a ladder row or a task row
    has to answer with a named drift, not with a `KeyError` leaving `main` unmapped at exit 1 (R-115's
    class of escape).
    """
    doc = load_published(G1_FEASIBILITY_JSON, "report.G1_FEASIBILITY_JSON", read_g1_feasibility)
    chosen = dict(doc["rubric"])
    if rubric:
        chosen.update({k: rubric[k] for k in G1_FEASIBILITY_RUBRIC_FIELDS if k in rubric})
    fresh = build_g1_feasibility(chosen)

    expect("g1 producer", fresh.get("producer"), doc.get("producer"))

    fresh_reference = {row.get("n"): row for row in fresh.get("reference", [])}
    published_reference = {row.get("n"): row for row in doc.get("reference", [])}
    for n in sorted(set(fresh_reference) | set(published_reference), key=str):
        for field in G1_FEASIBILITY_REFERENCE_FIELDS:
            if field in ("n", "size_from"):
                continue  # `n` is the key the rows are matched on; `size_from` quotes the
                # publication tables' own paths, which a scratch checkout re-points at copies -- the
                # same caller-owned-pointer class as `artefact` below, and the same reason it cannot
                # be a reproduction claim there.
            expect("g1 reference %s.%s" % (n, field),
                   fresh_reference.get(n, {}).get(field), published_reference.get(n, {}).get(field))

    fresh_rows = {row.get("task"): row for row in fresh.get("rows", [])}
    published_rows = {row.get("task"): row for row in doc.get("rows", [])}
    for task in sorted(set(fresh_rows) | set(published_rows)):
        for field in G1_FEASIBILITY_ROW_FIELDS:
            if field in ("task", "artefact", "table"):
                continue  # `task` is the key the rows are matched on; `artefact` and `table` are the
                # reader's own pointers -- every scratch checkout re-points `report.CERTS` and
                # `report.MASSIVE_CERTIFICATES` at copies (test_verify_protocol's `_certs` and
                # `_massive`), and a comparison of the caller's path against the published relative
                # name would report the harness as drift. No gate is lost by it: the document renders
                # these two columns into its per-task headers, so a tampered path in the artefact
                # reddens the `docs/FEASIBILITY.md byte-identical` row, which compares bytes the
                # artefact owns rather than a path the reader was handed.
            expect("g1 %s.%s" % (task, field),
                   fresh_rows.get(task, {}).get(field), published_rows.get(task, {}).get(field))

    for key in G1_FEASIBILITY_RUBRIC_FIELDS:
        expect_rubric("g1 rubric.%s" % key, doc["rubric"].get(key), rubric[key] if rubric else None)


def _g1_cell(value) -> str:
    """One artefact value as the ceiling document prints it: `null` is stated as `null`, never imputed."""
    if value is None:
        return "null"
    return "%s" % value


def render_g1_feasibility(doc: dict) -> str:
    """G1's ceiling as derived prose: every figure is read out of the artefact, and none is typed.

    No timestamp and no machine path, so both lanes byte-compare it. Three sentences this renderer is
    itself the owner of, because the artefact cannot render them wrong: a bound taken from
    `meta.closest_attempt` is always printed labelled a diagnostic (no certificate here issued a bound,
    and the document must never read as claiming one), every `null` arrives with the field that would
    have supplied it, and the probe's upstream-quoted figures are named as excluded rather than repeated.
    """
    rubric = doc["rubric"]
    rows = doc.get("rows", [])
    scored = [row for row in rows if row.get("table") != "inventory.corpus_options"]
    unscored = [row for row in rows if row.get("table") == "inventory.corpus_options"]
    certifying = sorted(str(row.get("task")) for row in rows if row.get("feasible") is True)
    lines = [
        "# The G1 feasibility ceiling",
        "",
        "Written by `python3 %s --out %s --doc %s --force` and re-checked by" % (
            G1_FEASIBILITY_PRODUCER, G1_FEASIBILITY_JSON, G1_FEASIBILITY_MD),
        "`python -m autorate.cli verify`, which recomputes every figure below from `src/autorate/tails.py`",
        "and the published certificates -- in both lanes, because nothing here reads the corpus -- and",
        "refuses the artefact at exit 4 if it is absent or unreadable. The document carries no timestamp",
        "and no machine path, so the two lanes byte-compare the same bytes.",
        "",
        "G1 asks for at least three decision tasks certified at `autorate(alpha)` for the freeze's",
        "published alpha. This tree scores %d and certifies none; `data/resplit_200.json` shows no seeded"
        " split certifying for any of them. The stronger statement -- that **no automated size"
        % len(scored),
        "certifies on this evidence base at this budget** -- lived in an untracked scratch probe until",
        "this arm, and by this repository's own ruling (`docs/G5.md` is that ruling's artefact) a",
        "simulation performed and deleted is not evidence. Everything below is re-derived from committed",
        "bytes on every `verify` run.",
        "",
        "- rubric the ceiling is measured at: alpha=%s beta=%s delta=%s method `%s`, seed %s"
        % (_g1_cell(rubric.get("alpha")), _g1_cell(rubric.get("beta")), _g1_cell(rubric.get("delta")),
           _g1_cell(rubric.get("method")), _g1_cell(rubric.get("seed"))),
        "- producer: `%s`" % _g1_cell(doc.get("producer")),
        "- scored decision tasks read from their certificates: %d; corpora carried as refusals: %d"
        % (len(scored), len(unscored)),
        "- tasks that certify at their published size: %s" % (", ".join(certifying) if certifying else "none"),
        "",
        "The gate's own pass condition, as the committed refusals were produced by it: a task certifies",
        "only if `clopper_pearson_upper(errors, automated, delta) < alpha` once the bound is canonicalised",
        "onto `certificate.PUBLISHED_DECIMALS` -- the stored precision the artefacts answer at (the last",
        "ULP of the raw double is a platform fact, ledger R-121, so this arm never compares raw doubles).",
        "`k_max(n)` below is the largest error count that still clears alpha at an automated size of `n`;",
        "`k_max = null` means the size has no certifiable error count at all -- even a zero-error run",
        "fails there -- which is a result, never a zero.",
        "",
        "## The size ladder: what an automated set of n may get wrong and still clear alpha",
        "",
        "| n | k_max | cp(k_max) | cp(k_max + 1) | largest certifiable error rate | required observed accuracy | cp(0 errors) | bound width | feasible @0.10 | feasible @0.25 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in doc.get("reference", []):
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % tuple(
            _g1_cell(row.get(f)) for f in
            ("n", "k_max", "cp_k_max", "cp_k_max_plus_1", "largest_certifiable_error_rate",
             "required_observed_accuracy", "cp_zero_errors", "bound_width",
             "feasible_at_0.10", "feasible_at_0.25")))
    lines += [
        "",
        "Sizes and where each one comes from (`size_from`, read, not remembered):",
        "",
    ]
    for row in doc.get("reference", []):
        lines.append("- `n = %s` -- %s" % (_g1_cell(row.get("n")), _g1_cell(row.get("size_from"))))
    lines += [
        "",
        "The widths and the two bars are `inventory.py`'s own currency: `bound_width(n)` from",
        "`tails.bound_width` at four decimals, and `feasible_at_0.10` / `feasible_at_0.25` from",
        "`tails.n_feasible` against the inventory's declared bars -- so this ladder and",
        "`data/inventory.md` state size in the same units and cannot quietly disagree.",
        "",
        "## Per task",
        "",
        "Each row reads the certificate's own bytes. The record unit is the refusal's diagnostic",
        "`meta.closest_attempt` grid point (its counts, its stored bound); the case unit is the",
        "certificate's own unit, R-44, taken from `meta.automated_cases` and `meta.erroneous_cases`",
        "at `meta.at_requested_alpha`. A `k_max` from one unit is never compared against an error",
        "count from the other, and the two denominators are different quantities on purpose: `en`",
        "automates 628 of 1,487 records but 709 of 1,487 cases.",
        "",
    ]
    for row in rows:
        lines += _g1_task_lines(row)
    lines += [
        "## What this ceiling is, and what it is not",
        "",
        "- It is size arithmetic at the freeze's rubric over published counts: the same",
        "  `build_g1_feasibility` the producer wrote these bytes with, re-run by `verify` and compared",
        "  field by field, so a stale ceiling is drift the gate names rather than a sentence in a file.",
        "- It is not the empirical column. G1's second column is the 200-resplit violation rate,",
        "  owned by `data/resplit_200.json` and `docs/RESPLIT.md`; this arm publishes the closed-form",
        "  ceiling beside it, not a re-run of the sweep.",
        "- The bounds printed for the scored tasks are the refusals' DIAGNOSTIC values. Every one of",
        "  these certificates published `conditional_error_bound: null` and `autorate: null` -- nothing",
        "  certified, and no row above may be read as a certificate bound.",
        "- A `null` column names the field that would have supplied it (`missing_pool_input`,",
        "  `row_refusal`); this project does not impute zeros, and `data/resplit_200.json`'s",
        "  rate-over-a-zero-denominator shape is the precedent.",
        "- The scratch probe quoted upstream figures for `typed_decisions` (a held-out accuracy read",
        "  from `BENCHMARKS.md`). No committed byte of this repository states them, so the artefact",
        "  carries none of them and this document only names their exclusion. What the oracle ceiling",
        "  needs and the certificates do not publish is the error count of the evaluated POOL; the",
        "  published counts are the errors INSIDE the automated set, so the ceiling is a number",
        "  exactly where the artefact states the automated set is the pool (`jev`) -- and null with",
        "  the missing field named everywhere else.",
        "",
    ]
    return "\n".join(lines)


def _g1_task_lines(row: dict) -> list:
    """One task's published lines, built from its row's own fields -- including the refusal sentences."""
    header = "### `%s` (%s, %s)" % (_g1_cell(row.get("task")), _g1_cell(row.get("artefact")),
                                    _g1_cell(row.get("table")))
    lines = [header, ""]
    if row.get("table") == "inventory.corpus_options" or not row.get("closest_attempt_published"):
        # A corpus walked as a refusal, or a certificate whose diagnostic attempt was never published:
        # the refusal sentence is the row, because every computed column would be an imputation.
        lines.append("- published verdict: `%s`" % _g1_cell(row.get("row_refusal")))
        if row.get("missing_pool_input") is not None:
            lines.append("- missing input: %s" % row.get("missing_pool_input"))
        if row.get("table") == "inventory.corpus_options":
            lines.append("- this corpus is the one where the wall is the error rate rather than the bound")
            lines.append("  width -- and it is not scored here: no gold labels, so every computed column")
            lines.append("  is null with its missing input named above, and nothing else is claimed.")
        lines.append("")
        return lines
    lines.append("- published verdict: feasible=%s, reason=`%s` -- the certificate issued no bound"
                 % (_g1_cell(row.get("feasible")), _g1_cell(row.get("reason"))))
    def errors(n):
        # m-7's count-noun rule, applied here: the artefact says `1 errors` no more than the
        # inventory says `3 malformed line`; the count is read, the noun agrees with it.
        return "null" if n is None else "%s error%s" % (n, "" if n == 1 else "s")
    lines.append("- records unit (diagnostic `meta.closest_attempt`, grid alpha %s): %s of %s evaluated"
                 " (%s calibration), %s; k_max at that size = %s"
                 % (_g1_cell(row.get("grid_alpha")), _g1_cell(row.get("automated_records")),
                    _g1_cell(row.get("n_eval_records")), _g1_cell(row.get("n_cal_records")),
                    errors(row.get("errors_records")), _g1_cell(row.get("k_max_records"))))
    lines.append("- cases unit (the certificate's own unit, R-44): %s of %s evaluated"
                 " (%s calibration), %s; k_max at that size = %s"
                 % (_g1_cell(row.get("automated_cases")), _g1_cell(row.get("n_eval_cases")),
                    _g1_cell(row.get("n_cal_cases")), errors(row.get("errors_cases")),
                    _g1_cell(row.get("k_max_cases"))))
    lines.append("- the diagnostic bounds reproduce from the artefact's own digits at the certificate's"
                 " stored precision: records %s (recomputed %s), cases %s (recomputed %s) -- diagnostic"
                 " values beside a refusal, NOT certificate bounds; the certificate published null"
                 % (_g1_cell(row.get("published_closest_bound")),
                    _g1_cell(row.get("recomputed_closest_bound")),
                    _g1_cell(row.get("published_case_bound")),
                    _g1_cell(row.get("recomputed_case_bound"))))
    lines.append("- inventory bars at this task's own sizes: records bound_width=%s feasible@0.10=%s"
                 " @0.25=%s; cases bound_width=%s feasible@0.10=%s @0.25=%s"
                 % (_g1_cell(row.get("bound_width_records")),
                    _g1_cell(row.get("feasible_at_0.10_records")),
                    _g1_cell(row.get("feasible_at_0.25_records")),
                    _g1_cell(row.get("bound_width_cases")),
                    _g1_cell(row.get("feasible_at_0.10_cases")),
                    _g1_cell(row.get("feasible_at_0.25_cases"))))
    if row.get("pool_is_automated_set"):
        lines.append("- oracle ceiling (the largest automated size a perfect gate could certify):"
                     " %s records, %s cases -- a number because this artefact states the automated"
                     " set IS the evaluated pool"
                     % (_g1_cell(row.get("oracle_ceiling_records")),
                        _g1_cell(row.get("oracle_ceiling_cases"))))
    else:
        lines.append("- oracle ceiling: %s records, %s cases -- null, because %s"
                     % (_g1_cell(row.get("oracle_ceiling_records")),
                        _g1_cell(row.get("oracle_ceiling_cases")),
                        row.get("missing_pool_input")))
    lines.append("")
    return lines


def first_clause(text: str, sep: str = ";", width: int = 78) -> str:
    """The clause a published bullet quotes, with an explicit marker when it is cut.

    `sep` and `width` are parameters rather than a second helper because `docs/REPORT.md` quotes a
    different artefact's clauses -- the claim ledger's rows, which are sentences long and semicolon-poor
    -- and a copy of this function with its own limits is two owners of one formatting rule. A caller
    that wants a width cap and no clause boundary passes `sep=None`. The defaults are
    `docs/RESULTS.md`'s own behaviour, unchanged: the gaps line it renders is byte-compared, so an
    edited default would move a published document.
    """
    head = text if sep is None else text.split(sep)[0]
    return head[:width] + ("..." if len(head) > width else "")


def _audit_scores(inv: dict) -> tuple:
    """Parse upstream's own audit lines: "jev / choice: 64/64; 0 failed requests; ...".

    The score is upstream's verdict, so the number is read from its output rather than
    recomputed here -- and a line that does not parse is an error, not a fallback.
    """
    out = {}
    for line in inv["upstream_audit_stdout_tail"].splitlines():
        head, _, rest = line.partition(":")
        who, _, mode = head.partition(" / ")
        score = rest.split(";")[0].strip()
        if who and mode and score:
            out[(who.strip(), mode.strip())] = score
    missing = [(b, m) for b in ("laya", "jev") for m in ("choice", "four_noul")
               if (b, m) not in out]
    if missing:
        raise ValueError("the archived audit output does not carry %s; refusing to "
                         "quote a score that is not there" % missing)
    return out


def _budget_clause(*certs) -> str:
    """Name the budgets the rows actually carry, collapsing the shared case into `alpha=beta`."""
    pairs = sorted({(c.alpha, c.beta) for c in certs if c is not None})
    if len(pairs) == 1:
        a, b = pairs[0]
        return "alpha=beta=%.2f" % a if a == b else "alpha=%.2f, beta=%.2f" % (a, b)
    return "row-specific budgets (" + ", ".join("alpha=%.2f/beta=%.2f" % p for p in pairs) + ")"


def _case_cell(cert, key: str) -> str:
    """One table cell for a case counter: the number, or "-" when the run never recorded one."""
    value = cert.meta.get(key)
    return "-" if value is None else "%d" % value


def _reached_case_stage(cert) -> bool:
    """Whether this certificate ever counted a case.

    `n_below_min` and `no_gold_labels` return in `certify_choice` (lines 150-158) before the counters are
    recorded at line 167, so their `meta` carries neither `automated_cases` nor `n_eval_cases`. The
    absence is the fact: the honest output is to say the reason and stop, not to default to zeros, which
    is how a refusal about sample size ended up narrating label shape.
    """
    return all(k in cert.meta for k in ("automated_cases", "n_eval_cases", "erroneous_cases"))


def _stage_clause(cert) -> str:
    """The narrative for a certificate that never got to a case count: name the reason, not a shape."""
    if cert.feasible:
        return ("it certifies a case-level bound of %.3f against the %.3f budget, but this certificate "
                "carries no case counters, so the run it describes cannot be stated here."
                % (cert.conditional_error_bound, cert.beta))
    return ("it refused as %s before any case was counted, so there is no evaluation-case figure to "
            "narrate (the certificate's own detail: %s)."
            % (cert.reason, cert.meta.get("detail", "")))


def _at_requested_alpha(cert):
    """One owner for the requested-coverage read: `(case bound, automated cases, erroneous cases)`.

    `at_requested_alpha` is written on exactly one path (`certify_choice.py:218-220`), so a refusal that
    never reached it -- or an early refusal, which never reached the case stage either -- has nothing to
    quote here, and this returns None rather than a default. Two call sites read it, and giving them
    separate `.get` chains is what let their fallbacks diverge: the record clause used to substitute the
    record bound into the case slot.
    """
    at = cert.meta.get("at_requested_alpha") or {}
    bound = at.get("conditional_error_bound")
    automated_cases = cert.meta.get("automated_cases")
    erroneous_cases = cert.meta.get("erroneous_cases")
    if bound is None or automated_cases is None or erroneous_cases is None:
        return None
    return bound, automated_cases, erroneous_cases


def _decision_clause(cert) -> str:
    """Say what one certificate actually says, at the denominator its own bound was computed on.

    Four published defects are what this shape avoids. The first version printed a fixed sentence per
    backend, so a regenerated artifact could assert the opposite of the counts inside it. The repair then
    quoted the zero-error counterfactual at `n_eval_cases`, which for laya is 32 while its bound was
    computed over its 2 automated cases -- so the row printed another row's number (0.089 where its own
    counterfactual is 0.776). And it spoke of "both rows refusing" unconditionally, which a certified row
    contradicts. Every figure is read from the certificate; the case bound and the record-denominator
    bound both belong to `certify_choice` and are never re-derived here.

    The feasible branch is the same defect class in the opposite direction. `certify_choice` admits a row
    when `cond_hi <= beta`, and a row with errors can satisfy that at a loose budget: at alpha=0.50,
    beta=0.95 the shipped laya records certify 15 of 32 cases with 9 of them erroneous, and the sentence
    used to insist "and none of them is wrong" three words after printing the count that refutes it.
    """
    if not _reached_case_stage(cert):
        return _stage_clause(cert)
    automated = cert.meta["automated_cases"]
    n_cases = cert.meta["n_eval_cases"]
    wrong = cert.meta["erroneous_cases"]
    carries = "carries" if wrong == 1 else "carry"
    if cert.feasible:
        if wrong == 0:
            return ("it certifies: %d of its %d evaluation cases automate and none of them is wrong, so "
                    "the exact case-level upper bound is %.3f against the %.3f budget, at an automation "
                    "rate of %.3f."
                    % (automated, n_cases, cert.conditional_error_bound, cert.beta, cert.autorate))
        # "inside" is not a guess about the row: `certify_choice` admits a feasible certificate only when
        # this same bound is <= beta (certify_choice.py:211), so the budget that licensed the row is the
        # one the bound is already measured against, and naming the errors is what beta permits.
        return ("it certifies: %d of its %d evaluation cases automate and %d of those %s a wrong "
                "automated request, so the exact case-level upper bound is %.3f -- inside the %.3f "
                "budget that licenses them, at an automation rate of %.3f."
                % (automated, n_cases, wrong, carries, cert.conditional_error_bound, cert.beta,
                   cert.autorate))
    if automated == 0:
        return ("not one evaluation case produced a single-label set (%d empty, %d multi-label of %d "
                "records), so there is nothing it may run unattended."
                % (cert.meta.get("empties", 0), cert.meta.get("multi_label", 0), cert.n_eval))
    requested = _at_requested_alpha(cert)
    if requested is None:
        return ("it automates %d of its %d evaluation cases and %d of those %s a wrong automated "
                "request, which the %.3f budget does not license."
                % (automated, n_cases, wrong, carries, cert.beta))
    # `automated` and `wrong` are already this row's case figures (the stage check guarantees them), so
    # only the bound is taken from the owner: `requested[0]` is the case-level bound the certifier
    # recorded at the requested coverage, never a substitute for a figure that is missing.
    bound = requested[0]
    if wrong == 0:
        return ("it automates %d of its %d evaluation cases with zero errors, yet the exact case-level "
                "upper bound on that run is %.3f -- above the %.3f budget."
                % (automated, n_cases, bound, cert.beta))
    # The counterfactual shares the bound's denominator or it is not about this row: the case bound is
    # computed over the automated cases, so `n_eval_cases` would quote a different experiment.
    zero_error = clopper_pearson_upper(0, automated, cert.delta)
    return ("it automates %d of its %d evaluation cases and %d of those %s a wrong automated request, so "
            "the exact case-level upper bound is %.3f -- above the %.3f budget; even had that request "
            "been right, a zero-error run over those same %d automated cases would still have bounded at "
            "%.3f, so this corpus cannot support a %.0f%% claim at any error count."
            % (automated, n_cases, wrong, carries, bound, cert.beta, automated, zero_error,
               100 * cert.beta))


def _record_clause(cert) -> str:
    """The record-denominator contrast, with every figure on the denominator of its own experiment.

    `certify_choice` already publishes the record-level figure as `closest_attempt`; recomputing it here
    gave a published number two owners, which is what R-20/R-31/R-44 delete. If the certificate carries
    none -- an early refusal, or a certified row, neither of which records an attempt -- the sentence is
    dropped rather than printed with a `nan` in it. The verdict word is derived from the comparison.

    The count now comes from `closest_attempt` itself, together with its error count, its bound and its
    grid point: the previous version took the count from `cert.meta["automated"]` (records at the
    *requested* alpha) and the bound from the grid row, so laya's sentence read "laya's 6 automated
    records would bound at 0.775" when 0.775 is CP(21, 33) at grid alpha=0.26. Naming the grid point was
    chosen over returning "" where the two counts differ, so a row whose points differ (laya: 6 vs 33)
    still states a true contrast instead of losing the sentence -- and the case figure comes from the one
    owner, `_at_requested_alpha`, with its own case denominator, with nothing substituted when absent.
    """
    attempt = cert.meta.get("closest_attempt") or {}
    record_bound = attempt.get("conditional_error_bound")
    record_auto = attempt.get("automated")
    record_errors = attempt.get("errors")
    grid_alpha = attempt.get("grid_alpha")
    requested = _at_requested_alpha(cert)
    if (record_bound is None or not record_auto or record_errors is None
            or grid_alpha is None or requested is None):
        return ""
    case_bound, case_auto, case_errors = requested
    where = "inside" if record_bound <= cert.beta else "above"
    # The trailing provenance sentence was dropped rather than kept: naming the source in prose would
    # need a seventh interpolation, and the sentence is a claim about this module, not about the corpus.
    return ("The record denominator is what flatters this corpus: at its own grid point alpha=%.3f, %s's "
            "%d automated records, %d of them wrong, would bound at %.3f, %s its %.3f budget, while at "
            "the certified alpha=%.3f its %d automated cases, %d of them wrong, bound at %.3f -- and the "
            "case is the unit a bound may divide by (R-44)."
            % (grid_alpha, cert.backend, record_auto, record_errors, record_bound, where, cert.beta,
               cert.alpha, case_auto, case_errors, case_bound))


def _rows_subject(count: int, verb: str) -> str:
    """Subject and verb for a lead that must agree with the rows it was handed.

    "Both rows refuse" was printed for a single certificate, and "%d of %d rows refuse" read wrong for
    one refusal out of two: the lead is about the pair, so it has to count the pair.
    """
    if count == 1:
        return "The row %s" % ("refuses" if verb == "refuse" else "certifies")
    noun = "Both rows" if count == 2 else "%d rows" % count
    return "%s %s" % (noun, verb)


def _pair_lead(*certs) -> str:
    """Name the pair's verdict honestly: two refusals, two certificates, or one of each."""
    rows = [c for c in certs if c is not None]
    refused = [c for c in rows if not c.feasible]
    budget = _budget_clause(*rows)
    if len(refused) == len(rows):
        return "%s at %s." % (_rows_subject(len(rows), "refuse"), budget)
    if not refused:
        return "%s at %s." % (_rows_subject(len(rows), "certify"), budget)
    return "%d of %d rows %s at %s." % (len(refused), len(rows),
                                        "refuses" if len(refused) == 1 else "refuse", budget)


def _laya_point_or_problem(cert, scores) -> str:
    """The rhetorical bullet, printed only if the row actually refuses.

    It used to be unconditional, so a certificate that ever automated something on this corpus would
    have published "a certificate that refuses is the correct output" about a row that did not refuse.
    """
    if cert.feasible:
        return ("- The laya row certifies on this corpus, where the archived audit scores its choice "
                "answers %s; the paired comparison in `autorate compare` is what carries the claim."
                % scores[("laya", "choice")])
    return ("- The laya row is the project's point, not its problem: on a Chinese workplace "
            "corpus where the archived audit scores its choice answers %s, a certificate "
            "that refuses is the correct output. A published number here would be a number "
            "about nothing." % scores[("laya", "choice")])


def _denominator_note(inv: dict) -> str:
    """Why the sample size is the case count, in the figures the inventory actually holds.

    These four numbers used to be typed into the sentence, and the typing had already cost the project
    twice: the prose said "MASSIVE's 51 language files" beside an inventory whose own recorded basis says
    3 of 51 were opened, so prose and artifact had drifted in opposite directions and nothing could see
    it. Every figure below is read from `inv`, and the sentence is asserted only while four things hold:
    an independent count was recorded at all, a shard count was recorded, the pooled rows are that count
    times that shard count, and the per-language shards report the same count as the pooled row.

    Where the valve actually lives (R-83, review MA-4): the second and third conditions are the loader's
    own invariant re-printed here, not a cross-check. `massive_pin` refuses -- `ArithmeticError`, which
    `main` maps to exit 4, before any row is rendered -- a pin whose `n_files` is not the length of its
    own `files` list and whose `n_files x distinct_ids` is not its `rows_total`, so for every pin it
    accepts the product holds by construction. Measured: over 128 loader-accepted pin shapes, none made
    the shard-count test or the equation the only conjunct that failed. What silences this sentence on
    real data are the first and the fourth -- `n_independent` is None when the pin does not record the
    shards' id sets as identical, and the per-language count is None when the pinned shards do not all
    report one row count, a shape the loader accepts because it polices the SET of row counts rather
    than that the set has a single member. The shard test and the equation stay as the defence for a
    dict that never went through the loader -- a committed `data/inventory.md.json` edited or left stale,
    whose live counterpart `verify` re-derives from the pin itself (`cli.py`, `PIN_DERIVED_KEYS`) rather
    than from the artefact.
    """
    def option(kind):
        return next((o for o in inv["corpus_options"] if o["id"] == kind), None)

    feishu, pooled, per_lang = option("feishu_zh"), option("massive_intent_all_languages"), \
        option("massive_intent_per_language")
    parts = ["The bound is computed on independent cases, not on rows:"]
    if feishu is not None:
        parts.append("feishu's %d archived lines are %d unique cases;"
                     % (inv["reader_lines_read"], feishu["n_independent"]))
    if (pooled and per_lang and pooled.get("n_independent") is not None and pooled.get("n_shards")
            and pooled["n_rows"] == pooled["n_independent"] * pooled["n_shards"]
            and per_lang["n_independent"] == pooled["n_independent"]):
        parts.append("MASSIVE's per-language and pooled options both report %d independent rows, which "
                     "is what translations of one utterance set must give;" % pooled["n_independent"])
    parts.append("counting rows instead of cases flatters the bound. Each option's own count basis is "
                 "in the table below, quoted from the inventory rather than restated here.")
    return " ".join(parts)


def build_report(inv: dict, certs: dict, counts: dict) -> str:
    """The published report, from the certificates and counts the caller brought.

    `certs` is keyed by whatever backends the records actually declare, while this function's sentences are
    about the declared pair (`BACKENDS`) -- so the pair is checked once, here, before any lookup. Without it
    a records file whose rows name no published backend answered `autorate verify` with `KeyError: 'laya'`,
    which `main` cannot map, so the gate exited 1 on a table-declared input: the same class #74 settled for
    absent and unreadable artefacts, reached from the marginal path instead of the severity one.
    """
    missing = [b for b in BACKENDS if b not in certs]
    if missing:
        raise PublishedArtefactUnavailable(
            "%s is declared published by report.RECORDS and the certificates built from it name no record "
            "for backend %s (they carry %s); report.BACKENDS declares the pair every published sentence "
            "here is about, so this is the checkout's failure and no argument can repair it -- the path was "
            "chosen by the table, not by the caller"
            % (RECORDS, ", ".join(missing), ", ".join(sorted(certs)) or "no backends at all"))
    digests = inv["digests"]
    scores = _audit_scores(inv)
    ids = {b: set(certs[b].meta.get("eval_ids", [])) for b in BACKENDS}
    shared = len(ids["laya"] & ids["jev"])
    lines = [
        "# Published results",
        "",
        "Every number in this file is emitted by `python -m autorate.cli report` and",
        "re-checked by `python -m autorate.cli verify`. None is typed, and the document",
        "carries no timestamp so a re-run is byte-comparable.",
        "",
        "## Corpus",
        "",
        "- archive: upstream `research/benchmarks/feishu_zh` (MIT, Adkid-Zephyr; "
        "`results/v1/{laya,jev}/raw.jsonl`)",
        "- unique cases: **%d**, repeats %s, slice keys: %s" % (
            inv["unique_ids"], inv["repeats"], ", ".join(inv["families"])),
        "- upstream `audit.py` exit code: **%d** (values as recorded in "
        "`data/inventory.md.json`)" % inv["upstream_audit_rc"],
        "- records per backend (lines are counted separately, above): %s" % ", ".join(
            "%s=%d" % (b, counts[b]) for b in BACKENDS if b in counts),
        "- upstream's own scores on it (read from its stdout, not recomputed here): %s" % (
            ", ".join("%s/%s = %s" % (b, m, scores[(b, m)])
                      for b in BACKENDS for m in ("choice", "four_noul"))),
    ]
    if digests:
        bad = [d["path"] for d in digests if not d["match"]]
        lines += [
            "- provenance digests (owner: upstream `SOURCE.json`): **%d/%d match**%s" % (
                len(digests) - len(bad), len(digests),
                "" if not bad else "; MISMATCH: " + ", ".join(bad)),
        ]
    lines += [
        "- gaps: %d recorded, first clause each (full text in `data/inventory.md.json`): %s"
        % (len(inv["gaps"]), "; ".join(first_clause(g) for g in inv["gaps"])),
        "",
        "## Is n big enough to certify?",
        "",
        _denominator_note(inv),
        "",
        "| corpus | n_independent | n_rows | count basis | bound width at alpha=0.05 | feasible at 0.10 |",
        "|---|---|---|---|---|---|",
    ]
    for o in inv["corpus_options"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            o["id"],
            "not opened" if o["n_independent"] is None else o["n_independent"],
            "-" if o["n_rows"] is None else o["n_rows"],
            o["basis"],
            "-" if o["bound_width_at_0.05"] is None else "%.4f" % o["bound_width_at_0.05"],
            "-" if o["feasible_at_0.10"] is None else ("yes" if o["feasible_at_0.10"] else "no"),
        ))
    lines += [
        "",
        "## Certificates at coverage %.2f (alpha=%.2f), beta=%.2f, seed=%d" % (
            1.0 - ALPHA, ALPHA, BETA, SEED),
        "",
        "| backend | verdict | autorate (cases) | ci | conditional <= | marginal <= | "
        "refusal | mean set size | records cal/eval | cases cal/eval |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in BACKENDS:
        c = certs[b]
        if c.feasible:
            lo, hi = c.autorate_ci
            lines.append("| %s | certified | %.3f | %.3f..%.3f | %.3f | %.3f | %.3f | %.2f "
                         "| %d/%d | %s/%s |"
                         % (b, c.autorate, lo, hi, c.conditional_error_bound,
                            c.marginal_error_bound, c.refusal_rate, c.mean_set_size,
                            c.n_cal, c.n_eval,
                            # Both rows read the case counters the same way now: the earliest refusals
                            # never record them, and a hard index here raised `KeyError` inside a
                            # published-artifact generator (item 2). "-" is the honest cell for a
                            # figure the certificate does not carry.
                            _case_cell(c, "n_cal_cases"), _case_cell(c, "n_eval_cases")))
        else:
            lines.append("| %s | %s | - | - | - | - | - | - | %d/%d "
                         "| %s/%s |"
                         % (b, _verdict_cell(c), c.n_cal, c.n_eval,
                            _case_cell(c, "n_cal_cases"), _case_cell(c, "n_eval_cases")))
    lines += ["", "### Verbatim summaries", ""]
    for b in BACKENDS:
        lines.append("```")
        lines.append("%s: %s" % (b, certs[b].summary()))
        lines.append("```")
    lines += ["", "### What this does and does not establish", ""]
    # `rstrip` because the record clause is legitimately empty (a certified row records no attempt, an
    # early refusal records no case figure), and a published bullet must not end in a dangling space.
    lines.append(("- %s laya: %s jev: %s %s" % (
        _pair_lead(certs["laya"], certs["jev"]), _decision_clause(certs["laya"]),
        _decision_clause(certs["jev"]), _record_clause(certs["jev"]))).rstrip())
    lines.append(_laya_point_or_problem(certs["laya"], scores))
    lines.append(("- The evaluation halves hold %d and %d RECORDS over %d and %d distinct cases (the "
                  "corpus repeats each case %d times) and %d cases are in common, so the pair is a "
                  "case-by-case comparison on identical inputs." if shared == len(ids["laya"])
                  == len(ids["jev"]) else
                  "- The evaluation halves hold %d and %d RECORDS over %d and %d distinct cases (the "
                  "corpus repeats each case %d times) and only %d cases are in common, so the pair is "
                  "a case-by-case comparison where they overlap and two marginal certificates "
                  "elsewhere.") % (
                      certs["laya"].n_eval, certs["jev"].n_eval, len(ids["laya"]), len(ids["jev"]),
                      len(inv["repeats"]), shared))
    # The per-CASE bullet states jev's record count as jev's case count, so it can only be printed from
    # jev's own counters: the earliest refusals never record them, and indexing the key raised inside the
    # generator. Dropping the sentence is the honest shape -- quoting laya's case count in jev's place
    # would be the misattribution this document has already been corrected for once.
    jev_cases = certs["jev"].meta.get("n_eval_cases")
    if jev_cases is not None:
        # The coarse form of this clause -- "laya's three per case are byte-identical" -- is refuted by the
        # archive it cites: 0 of 64 groups have identical rows, because `meta`, `repeat` and `slices` carry
        # the repeat counter and its own elapsed time. What earns the case denominator is the identity of
        # the quantities a bound reads, and that is 64 of 64. A claim about this corpus, so it is pinned by
        # tests/test_report_prose.py, which measures all four shapes from `data/records_feishu.jsonl`
        # rather than remembering them.
        lines.append("- The bounds are per CASE: repeats of one case are one observation (laya's three per "
                     "case carry byte-identical probability vectors, scores and gold labels, though not "
                     "identical rows -- `meta`, `repeat` and `slices` differ), so %d records are %d cases "
                     "and the denominators above say which is which. Per-slice certification, the ordinal "
                     "`score` family and the `noul` budgets are Plan B, gated on a corpus with enough "
                     "independent cases to bound them." % (certs["jev"].n_eval, jev_cases))
    lines.append("- Exchangeability is assumed within a backend and a question shape, not proven; the "
                 "envelope on each certificate is the machine-readable statement of that limit.")
    lines.append("")
    return "\n".join(lines)


def write_report(text: str, out: Path) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


def read_certificate(path: Path) -> Certificate:
    return Certificate.from_dict(json.loads(Path(path).read_text()))


# --- G4's contamination gap: the pinned strata, the interval, and the document that quotes them -------

CONTAMINATION_PIN = "data/pin_app_benchmark.json"
CONTAMINATION_JSON = "data/contamination_probe.json"
CONTAMINATION_MD = Path("docs/CONTAMINATION.md")
CONTAMINATION_PRODUCER = "tools/contamination_probe.py"
CONTAMINATION_RUBRIC_FIELDS = ("delta", "pieces", "min_cases_per_stratum", "max_interval_width")
CONTAMINATION_STRATA_FIELDS = ("errors", "cases", "rows", "pointers", "declared_in_training")
CONTAMINATION_PIN_ROW_FIELDS = ("suite", "variant", "n", "accuracy", "errors", "in_training", "pointer")
CONTAMINATION_HEADLINE_FIELDS = ("delta_hat", "interval", "R_in", "R_out", "excludes_zero", "worse", "sign")
# The two comparisons the corpus-absent lane cannot make, named here rather than only inside the arm, because
# the corpus-present denominator that `verify` prints is derived from the absent one plus these: a check that
# exists in one place cannot drift from the count it is cited to explain.
CONTAMINATION_CORPUS_ONLY_CHECKS = ("contamination pin.recomputed_digest",
                                    "contamination pin.recomputed_bytes")


def read_contamination(path: Path) -> dict:
    """Load the probe artefact or refuse its shape, before any number in it is compared.

    Same posture as the other published-artefact loaders: a missing key is named with the key, because the
    alternative is a `KeyError` that reads like the gate failing rather than the artefact being wrong.
    """
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ValueError("the contamination artefact must be a JSON object, found %s"
                         % type(doc).__name__)
    absent = sorted(set(("producer", "pin", "rubric", "strata", "probe", "claim", "what_this_is"))
                    - set(doc))
    if absent:
        raise ValueError("the contamination artefact is missing %s" % absent)
    for name, stratum in doc["strata"].items():
        missing = sorted(set(CONTAMINATION_STRATA_FIELDS) - set(stratum))
        if missing:
            raise ValueError("the contamination artefact's stratum %r is missing %s" % (name, missing))
    missing_rubric = sorted(set(CONTAMINATION_RUBRIC_FIELDS) - set(doc["rubric"]))
    if missing_rubric:
        raise ValueError("the contamination artefact records no budget value for %s" % missing_rubric)
    return doc


def read_contamination_pin(path: Path) -> dict:
    """The pinned upstream rows, shape-checked before the arm pools them.

    The pin is what lets the corpus-absent lane re-derive the gap at all, so a pin that lost its `rows` or
    its `source` is refused here rather than producing a gap out of nothing.
    """
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list) or not doc["rows"]:
        raise ValueError("the contamination pin must carry a non-empty `rows` list, found %r"
                         % (type(doc.get("rows")).__name__ if isinstance(doc, dict) else type(doc).__name__,))
    missing = sorted(set(("producer", "source", "excluded")) - set(doc))
    if missing:
        raise ValueError("the contamination pin is missing %s" % missing)
    for row in doc["rows"]:
        absent = sorted(set(CONTAMINATION_PIN_ROW_FIELDS) - set(row))
        if absent:
            raise ValueError("a pinned row is missing %s" % absent)
    return doc


def render_contamination(record: dict) -> str:
    """G4's `delta_hat` as derived prose: every figure is read out of the artefact, and none is typed.

    No timestamp and no machine path, so both lanes byte-compare the same bytes. The interpretation paragraph is
    built from `worse` rather than written twice, because the direction is the one sentence a reader could
    otherwise believe even after the data said the opposite.
    """
    probe, headline = record["probe"], record.get("headline")
    lines = ["# The contamination gap (G4's second named output)",
             "",
             "Written by `python3 %s --out %s --doc %s --force` and re-checked by `python -m autorate.cli"
             % (CONTAMINATION_PRODUCER, CONTAMINATION_JSON, CONTAMINATION_MD),
             "verify`, which pools the pinned rows again and refuses a disagreement. The pin is committed, so",
             "both lanes produce these bytes; what the corpus-absent lane cannot do is re-digest the upstream",
             "file the pin came from, and the document says that rather than implying otherwise.",
             "",
             "Spec section 9 defines this quantity: run the same model over the strata its own harness",
             "declares in-training and held-out, publish the gap with a two-sided interval, and label it a",
             "diagnostic with an interpretation rule -- not a proof of leakage. `claim` is false in the",
             "artefact because no aggregate gap licenses a leakage finding, and the two strata are carried by",
             "different suites, which means task difficulty is confounded with the flag.",
             "",
             "- pin: `%s` from `%s`, sha256 `%s`, %d bytes, %d rows, %d interval pieces"
             % (record["pin"]["path"], record["pin"]["source"]["path"], record["pin"]["source"]["sha256"],
                record["pin"]["source"]["bytes"], record["pin"]["rows"], record["rubric"]["pieces"]),
             "- budget it answers at: delta=%s, floor %s cases per stratum, ceiling %s interval width"
             % (record["rubric"]["delta"], record["rubric"]["min_cases_per_stratum"],
                record["rubric"]["max_interval_width"])]
    for name in sorted(record["strata"]):
        stratum = record["strata"][name]
        lines.append("- `%s` (`in_training=%s`): %d pinned rows, %d errors over %d cases"
                     % (name, stratum["declared_in_training"], stratum["rows"], stratum["errors"],
                        stratum["cases"]))
    excluded = record["pin"]["excluded"]
    lines.append("- excluded from the pin by name: %d row(s)%s"
                 % (len(excluded), "" if not excluded else " -- "
                    + ", ".join("`%s`" % e["pointer"] for e in excluded)
                    + ", each publishing a rounded rate whose `accuracy x n` is not a whole number"))
    lines.append("")
    if headline is None:
        return "\n".join(lines + ["The probe ran and refused. The refusal is the result:", "", "```",
                                  probe["refusal"], "```", "",
                                  "Nothing is pooled away and nothing is printed as a measurement of nothing.",
                                  ""])
    lines += ["| quantity | value |", "|---|---|",
              "| `R_in` (in-training error rate) | %s |" % headline["R_in"],
              "| `R_out` (held-out error rate) | %s |" % headline["R_out"],
              "| `delta_hat = R_in - R_out` | %s |" % headline["delta_hat"],
              "| two-sided interval | [%s, %s] |" % (headline["interval"][0], headline["interval"][1]),
              "| interval excludes zero | %s |" % headline["excludes_zero"],
              "| stratum with the higher rate | `%s` |" % headline["worse"],
              "| sign | `%s` |" % headline["sign"],
              "| `claim` | %s |" % record["claim"],
              "",
              "The interpretation rule, stated because the number without it would be read as a finding:",
              "",
              "> %s" % probe["interpretation"],
              "",
              "Read as: the %s stratum errs more, across %d in-training rows and %d held-out ones; %s. The two"
              % ("held-out" if headline["worse"] == "in_stratum" else "in-training",
                 record["strata"]["in_stratum"]["rows"], record["strata"]["out_stratum"]["rows"],
                 "that is the direction a contamination signature predicts"
                 if headline["worse"] == "in_stratum"
                 else "that is the opposite of the direction a contamination signature predicts"),
              "strata are different suites, so the gap is confounded with task difficulty: it bounds a",
              "difference between two aggregate rates and does not show that any checkpoint was trained on any",
              "of these cases.",
              "",
              "## Reproducing it",
              "",
              "```",
              "AUTORATE_FEISHU_ROOT=<corpus> python3 tools/contamination_pin.py --out %s" % CONTAMINATION_PIN,
              "python3 %s --out %s --doc %s --force" % (CONTAMINATION_PRODUCER, CONTAMINATION_JSON,
                                                        CONTAMINATION_MD),
              "```", ""]
    return "\n".join(lines)


def rederive_contamination(expect, expect_rubric, rubric=None) -> None:
    """G4's gap, pooled again from the committed pin and compared field by field with the artefact.

    The arm calls the producer's own `build`, because a re-derivation that re-implements the pooling would be a
    second arithmetic and could agree with a stale artefact for its own reasons. The upstream file's digest is
    recomputed only where the corpus is visible -- the same split `verify` prints for the inventory snapshot,
    and the reason the two lanes carry different denominators.
    """
    doc = load_published(Path(CONTAMINATION_JSON), "report.CONTAMINATION_JSON", read_contamination)
    pin = load_published(Path(CONTAMINATION_PIN), "report.CONTAMINATION_PIN", read_contamination_pin)
    pooled = contamination_strata(pin)
    rebuilt = build_contamination(pin)
    for name in sorted(pooled):
        for key in ("errors", "cases", "rows"):
            expect("contamination strata.%s.%s" % (name, key), doc["strata"][name][key], pooled[name][key])
        expect("contamination strata.%s.pointers" % name, len(doc["strata"][name]["pointers"]),
               len(pooled[name]["pointers"]))
    for key in CONTAMINATION_RUBRIC_FIELDS:
        expect_rubric("contamination rubric.%s" % key, doc["rubric"][key], rebuilt["rubric"][key])
    expect("contamination pin.rows", doc["pin"]["rows"], len(pin["rows"]))
    expect("contamination pin.sha256", doc["pin"]["source"]["sha256"], pin["source"]["sha256"])
    expect("contamination pin.bytes", doc["pin"]["source"]["bytes"], pin["source"]["bytes"])
    expect("contamination pin.excluded", len(doc["pin"]["excluded"]), len(pin.get("excluded", [])))
    expect("contamination claim", doc["claim"], rebuilt["claim"])
    for side in ("in", "out"):
        expect("contamination R_%s" % side, doc["probe"]["R_%s" % side], rebuilt["probe"]["R_%s" % side])
    expect("contamination delta_hat", doc["probe"]["delta_hat"], rebuilt["probe"]["delta_hat"])
    expect("contamination interval", list(doc["probe"]["interval"]), list(rebuilt["probe"]["interval"]))
    expect("contamination interval_width", doc["probe"]["interval_width"],
           rebuilt["probe"]["interval_width"])
    expect("contamination worse", doc["probe"]["worse"], rebuilt["probe"]["worse"])
    expect("contamination sign", doc["probe"]["sign"], rebuilt["probe"]["sign"])
    expect("contamination excludes_zero", doc["probe"]["excludes_zero"], rebuilt["probe"]["excludes_zero"])
    expect("contamination interpretation", doc["probe"]["interpretation"], rebuilt["probe"]["interpretation"])
    for key in CONTAMINATION_HEADLINE_FIELDS:
        expect("contamination headline.%s" % key, doc["headline"][key], rebuilt["headline"][key])
    root = _corpus_root_for_contamination()
    if root is not None:
        import hashlib

        raw = (root / "research/results/app_benchmark_results.json").read_bytes()
        expect(CONTAMINATION_CORPUS_ONLY_CHECKS[0], doc["pin"]["source"]["sha256"],
               hashlib.sha256(raw).hexdigest())
        expect(CONTAMINATION_CORPUS_ONLY_CHECKS[1], doc["pin"]["source"]["bytes"], len(raw))


def _corpus_root_for_contamination():
    """The checkout the pin came from, or None where no corpus is visible (the CI lane).

    Resolved the way every other corpus path in this build is -- environment first, then the sibling
    default -- because a lane difference that depends on *how* the corpus was named would make the printed
    denominator a fact about the invocation rather than about the tree.
    """
    import os

    from autorate.cli import _default_corpus

    env = os.environ.get("AUTORATE_FEISHU_ROOT")
    default = _default_corpus()
    root = Path(env) if env else (Path(default) if default is not None else None)
    return root.parents[2] if root is not None and (root / "data" / "manifest.json").is_file() else None


class ContaminationRefusal(ValueError):
    """The pin answered, but not with two strata that can be pooled and bounded."""


CONTAMINATION_STRATA_KEYS = {"in_stratum": True, "out_stratum": False}


def contamination_strata(pin: dict) -> dict:
    """Pool the pinned rows into the two declared strata, refusing a row that cannot be pooled.

    Every operand keeps the JSON pointer it came from, so a reader who distrusts a pooled total can go and
    look at the individual rows that produced it.
    """
    rows = pin.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ContaminationRefusal("the pin carries no rows to pool; it was written by %s and re-read here"
                                   % pin.get("producer"))
    totals = {name: {"errors": 0, "cases": 0, "rows": 0, "pointers": []} for name in CONTAMINATION_STRATA_KEYS}
    for row in rows:
        for key in ("errors", "n", "in_training", "pointer"):
            if key not in row:
                raise ContaminationRefusal("a pinned row is missing %r: %s" % (key, sorted(row)))
        name = next(n for n, flag in CONTAMINATION_STRATA_KEYS.items() if flag is row["in_training"])
        totals[name]["errors"] += int(row["errors"])
        totals[name]["cases"] += int(row["n"])
        totals[name]["rows"] += 1
        totals[name]["pointers"].append(row["pointer"])
    for name, pooled in totals.items():
        if not pooled["rows"]:
            raise ContaminationRefusal("no pinned row declared %s, so the strata are not real" % name)
    return totals


def build_contamination(pin: dict, root: Path = None) -> dict:
    """The probe's record: gap, strata, interval, exclusion census, and what it does not license.

    `from_counts` is the arithmetic owner and `claim` stays False in every branch, because an aggregate gap
    is a diagnostic. Nothing here reads the corpus: the pin is the committed input, which is what lets the
    corpus-absent lane rebuild these bytes and compare them.
    """
    from .contamination import (MAX_STRATUM_INTERVAL_WIDTH, MIN_CASES_PER_STRATUM, N_PIECES,
                            PROBE_DELTA, from_counts)

    pooled = contamination_strata(pin)
    try:
        probe = from_counts(
            in_stratum={"errors": pooled["in_stratum"]["errors"], "cases": pooled["in_stratum"]["cases"]},
            out_stratum={"errors": pooled["out_stratum"]["errors"],
                         "cases": pooled["out_stratum"]["cases"]},
            delta=PROBE_DELTA)
    except ValueError as refusal:
        probe = {"refusal": str(refusal)}
    record = {"producer": CONTAMINATION_PRODUCER,
              "pin": {"path": str(CONTAMINATION_PIN), "source": pin["source"],
                      "rows": len(pin["rows"]), "excluded": pin.get("excluded", [])},
              "rubric": {key: probe_value for key, probe_value in (
                  ("delta", probe.get("delta", PROBE_DELTA)),
                  ("pieces", probe.get("n_pieces", N_PIECES)),
                  ("min_cases_per_stratum", MIN_CASES_PER_STRATUM),
                  ("max_interval_width", MAX_STRATUM_INTERVAL_WIDTH))},
              "strata": {name: {"errors": pooled[name]["errors"], "cases": pooled[name]["cases"],
                                "rows": pooled[name]["rows"], "pointers": sorted(pooled[name]["pointers"]),
                                "declared_in_training": CONTAMINATION_STRATA_KEYS[name]}
                         for name in sorted(pooled)},
              "probe": probe, "claim": False,
              "what_this_is": ("a diagnostic gap between two aggregate rates published by the harness that "
                               "ran the suites, not a certificate and not a per-case re-scoring")}
    if "refusal" not in probe:
        record["headline"] = {"delta_hat": canonicalise_bound(probe["delta_hat"]),
                             "interval": [canonicalise_bound(b) for b in probe["interval"]],
                             "R_in": canonicalise_bound(probe["R_in"]),
                             "R_out": canonicalise_bound(probe["R_out"]),
                             "excludes_zero": probe["excludes_zero"], "worse": probe["worse"],
                             "sign": probe["sign"]}
    return record
