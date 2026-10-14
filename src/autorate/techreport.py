"""The single technical report: one document, every figure emitted by the artefact that owns it.

`docs/RESULTS.md`, `docs/AUDIT.md`, `docs/SEVERITY.md`, `docs/RESPLIT.md`, `docs/SLICES.md`,
`data/inventory.md` and `protocol.json` each answer one reader's question, and a reviewer has to hold
seven files to see one project. `docs/REPORT.md` is that one file, and it obeys the rule the other six
already obey: **a document that contains a typed-in number is a document that can lie.** Every figure
below is read out of the artefact `verify` re-derives, so changing an artefact changes the sentence that
quotes it and no other sentence -- which is what `tests/test_techreport.py` measures rather than what
this docstring promises. `report.render_resplit` and `report.render_slices` are the shape copied.

Three properties the byte comparison depends on, each a way this repository has already been bitten:

* **No timestamp this run computed.** A date would make the file different on every machine and every
  day, which is the death of `verify`'s document arm. The only dates printed here are transcriptions of
  dates a committed artefact already states -- the freeze's own `frozen_at` and the claim ledger's
  `opened` column -- so they reproduce byte for byte.
* **No absolute machine path.** Every path printed is a repository-relative path a publication table
  declares, and `tests/test_cli.py`'s `MACHINE_PATH_RX` guard runs over the rendered text.
* **Nothing only the corpus-present lane can see.** The renderer takes the inventory the caller already
  resolved -- the fresh scan, or the committed snapshot when there is no corpus -- and the artefacts the
  tables declare, so both lanes produce the same bytes.

The claim rows come from `protocol.json`'s `claims` array and the related-work rows from
`docs/VERIFICATION.md`'s own cells, so neither list has a second owner here. A ledger row this document
cites that has been withdrawn, or that the ledger does not carry at all, is a
`PublishedArtefactUnavailable` refusal at exit 4 rather than a quietly deleted bullet: a citation that
outlived its evidence is the checkout's failure, and no argument can repair it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields
from pathlib import Path

from .certificate import N_CLAIMS, SHAPE_VERSION, Reason
from .conformal import METHODS
from .correction import JOINT_LEVEL_RULE
from .inventory import MASSIVE_PIN_LABEL, MASSIVE_PIN_PATH, massive_pin
from .protocol import MASSIVE_PIN_FIELDS, Protocol, protocol_digest, published_certificates
from .report import (CERTS, INVENTORY_JSON, MASSIVE_CERTIFICATES, PublishedArtefactUnavailable, RECORDS,
                     RESPLIT_JSON, SEVERITY_CERTS, SLICE_JSON, first_clause, load_published,
                     published_severity, read_resplit, read_slices)

REPORT_MD = Path("docs/REPORT.md")
LEDGER_MD = Path("docs/VERIFICATION.md")

# The ledger rows this document quotes, grouped by the role the citation plays in the argument, in the
# order it quotes them. These are the only sentences about other people's work in the report and every
# one of them is the ledger row's OWN words: the ids below select rows, they never author claims. The
# grouping is the only editorial move made here, which is why it is data in this module rather than
# prose spread through the renderers.
RELATED_WORK = (
    ("The reference implementation whose gate this project audits", (
        ("laya-readme-gating-instruction", "the instruction G2 measures"),
        ("laya-confidence-docstrings", "the two definitions the name `confidence` carries upstream"),
        ("laya-shipped-temperature", "the shipped temperature that sharpens the reported confidence"),
        ("laya-readme-collapse-table", "the collapsed slice G4 names by example"),
        ("laya-feishu-archived-pairs", "the archive these records were exported from"),
        ("laya-per-case-fields-parity", "what upstream publishes its per-case records as"),
        ("laya-vendored-tree-matches-tag", "the check that makes the vendored tree the tagged tree"),
    )),
    ("Conformal risk control and conformal tooling that already ship", (
        ("mapie-risk-control-coverage", "what the risk-control track actually covers"),
        ("mapie-abstention-rate-example", "the shipped abstention-rate control this project does not claim"),
        ("mapie-crc-disclaimer", "the clipped-variant disclaimer, in the library's own words"),
        ("mapie-exchangeability-tests", "assumption testing MAPIE owns, not this project"),
        ("two-way-bound-construction-source", "the conditional-risk construction the two-stage rule uses"),
        ("selective-crc-2512-12844", "select-then-control as published prior art"),
        ("cost-sensitive-crc-2607-27143", "Mondrian recovery under cost, measured across 15 datasets"),
    )),
    ("Ordinal conformal prediction, the immediate prior art", (
        ("ordinal-cp-neurips2023", "the contiguous minimal-cardinality set construction"),
        ("ordinal-crc-uai2023-two-losses", "the two ordinal-specific losses already controlled under CRC"),
        ("ordinal-cp-aaai-minlen", "the minimum-length ordinal interval, and its released code"),
        ("ordinal-cp-2606-24959", "the RPS nonconformity that yields median-centred intervals"),
    )),
    ("Neighbours in the same niche, read at pinned commits", (
        ("verdict-automation-guarantee", "a shipped conformal automation rule, and the guarantee it carries"),
        ("verdict-refusal-reporting", "what that project says when it will not commit"),
        ("open-medical-jev-auto-release", "Chow's rule on a caller-supplied cost ratio"),
        ("open-medical-jev-refusal-reporting", "a prose note beside the answer, and no bound"),
        ("jev-trust-per-domain-calibration", "per-domain ECE and Brier, with zero bound machinery"),
        ("openjev-verdict-2-refusal-reporting", "the same search in a same-named project"),
        ("openjev-verdict-2-confidence-channels", "a two-channel confidence decomposition, measured empirically"),
        ("poorjev-refusal-reporting", "the budget printed beside an infeasible result"),
        ("nibzard-no-threshold", "a community benchmark's own refusal to pick a threshold"),
    )),
    ("Dated observations, which any text re-quoting them has to re-open", (
        ("laya-star-count", "a star count, recorded as an observation with its date"),
        ("competitor-age-stars-packaging", "age, stars and packaging of the neighbours above"),
        ("justaskjev-ece0168", "two medians, with the denominator each was computed over"),
        ("jev-vendor-confidence-guidance", "the vendor's own guidance on threshold choice"),
        ("jev-api-limits", "the option ceiling the vendor's reference states"),
    )),
    ("Searches, recorded as tasks with the date they ran -- never as statements about the field", (
        ("ordinal-cp-literature-size", "the query that enumerated the ordinal literature behind §5.4"),
        ("awesome-jev-guarantee-scan", "the scan that found the neighbours above, with its own reach limit"),
    )),
)

# The ledger's own row shape. A row this parser cannot read is refused rather than partially quoted: a
# mis-split cell would put words in a citation's mouth, which is the one thing a document whose whole
# argument is provenance may not do. The tail is anchored at the end of the line, so `opened` and
# `status` are read from where the ledger format puts them instead of guessed at, and the lazy source
# group absorbs the `|` characters these rows quote inside their own claims -- the pipe before the source
# column is the boundary, and everything left of it after the id is the claim.
_ROW_ID = re.compile(r"^\|\s*id=(?P<id>[a-z0-9][a-z0-9-]*)\s*\|")
_ROW_TAIL = re.compile(r"\|\s*(?P<source>https?://.*?)\s*\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|"
                       r"\s*status:\s*(?P<status>[A-Za-z_]\w*)\s*\|\s*$")
_DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# The group whose rows are searches rather than findings, named by position so the closing section can
# print the dates those searches ran without re-typing any ids. `tests/test_techreport.py` pins that this
# is the last group and that its rows are the two the ledger records as queries.
SEARCHES_GROUP = len(RELATED_WORK) - 1

# The rows that opened the prior art the severity certificate's own summary names inside its sentence.
# The report does not restate that sentence's claims about other people's work; it points at these rows,
# so the artefact keeps its words and the ledger keeps the evidence.
SEVERITY_PRIOR_ART = ("ordinal-cp-neurips2023", "ordinal-cp-aaai-minlen", "ordinal-crc-uai2023-two-losses")

# How much of a row's own claim a bullet carries: long enough to be the claim, short enough to stay a
# bullet. `report.first_clause` marks where it cut, so the truncation is visible to the reader.
_LEDGER_WIDTH = 240
_BASIS_WIDTH = 120


@dataclass(frozen=True)
class ReportInputs:
    """Everything the renderer prints, already read.

    A record rather than a long argument list because the tests perturb one artefact at a time with
    `dataclasses.replace` and re-render, which is the only way to show that a sentence is a function of
    its input rather than a sentence the renderer remembered.
    """

    protocol: Protocol
    inventory: dict
    records: dict
    certificates: tuple
    severity: tuple
    resplit: dict
    slices: dict
    pin: dict
    ledger: tuple
    published_docs: tuple
    exit_codes: tuple

    def certificate_rows(self) -> tuple:
        """The published set artefacts as `(path, table that declares it, certificate)`.

        The table name is printed beside every row because the reader should be able to see which list
        in `report.py` the artefact belongs to; it is derived from those same tables, so a certificate
        that moved between them moves the label with it instead of keeping a stale one.
        """
        declared = {str(path): "report.CERTS" for path in CERTS.values()}
        declared.update({str(cert_path): "report.MASSIVE_CERTIFICATES"
                         for _label, (_records, cert_path) in MASSIVE_CERTIFICATES.items()})
        return tuple((path, declared[str(path)], cert) for path, cert in self.certificates)


def cited_ids() -> tuple:
    """Every ledger row this document quotes, flattened. One owner for the list; the tests read it."""
    return tuple(row_id for _title, rows in RELATED_WORK for row_id, _role in rows)


def read_ledger(path) -> tuple:
    """The claim ledger as `({id, claim, source, opened, status}, ...)`, in file order.

    Only the rows the file marks as ledger rows are returned, and every one of them must parse or this
    refuses. `tests/test_verification_table.py` owns the ledger's internal consistency; this owns the
    narrower thing the report needs -- that a bullet it renders is the row's own claim cell and nothing
    else's.
    """
    text = load_published(Path(path), "techreport.LEDGER_MD",
                          lambda p: p.read_text(encoding="utf-8"))
    rows = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.lstrip()
        matched = _ROW_ID.match(line)
        if not matched:
            continue
        tail = _ROW_TAIL.search(line)
        if not tail:
            raise PublishedArtefactUnavailable(
                "line %d of %s is a ledger row whose source, `opened` and `status` columns this parser"
                " cannot read, and docs/REPORT.md quotes the ledger by those three columns. This is not a"
                " usage error: no argument names the ledger, `techreport.LEDGER_MD` does."
                % (number, path))
        claim = line[matched.end():tail.start()].strip()
        if not claim:
            raise PublishedArtefactUnavailable(
                "line %d of %s holds ledger row `%s` with an empty claim column, so there is nothing for"
                " docs/REPORT.md to quote; the report refuses rather than printing a citation with no"
                " claim behind it." % (number, path, matched.group("id")))
        rows.append({"id": matched.group("id"), "claim": claim,
                     "source": tail.group("source").strip(),
                     "opened": tail.group("date"), "status": tail.group("status")})
    if not rows:
        raise PublishedArtefactUnavailable(
            "%s holds no ledger rows this parser can read, so the report has no source for any sentence"
            " about other people's work" % path)
    return tuple(rows)


def load_inputs(protocol, inventory, records, published_docs, exit_codes) -> ReportInputs:
    """The renderer's inputs, every one read through a publication table's own path.

    `protocol` is the freeze the caller resolved rather than a path this module re-declares, because
    `cli.PROTOCOL_JSON` owns that path and a second literal for it is a document that can disagree with
    the gate. `inventory` and `records` are what `verify` already resolved for its document arm, so this
    report cannot quote a different snapshot from the one the gate policed. `published_docs` and
    `exit_codes` come from `cli.py` for the same reason (R-168).
    """
    return ReportInputs(
        protocol=protocol,
        inventory=inventory,
        records=records,
        certificates=published_certificates(),
        severity=published_severity(),
        resplit=load_published(RESPLIT_JSON, "report.RESPLIT_JSON", read_resplit),
        slices=load_published(SLICE_JSON, "report.SLICE_JSON", read_slices),
        pin=load_published(MASSIVE_PIN_PATH, "inventory.MASSIVE_PIN_PATH", massive_pin),
        ledger=read_ledger(LEDGER_MD),
        published_docs=tuple(str(p) for p in published_docs),
        exit_codes=tuple(exit_codes),
    )


def _validate_citations(inputs: ReportInputs) -> None:
    """Every cited row exists and is `verified`; anything else is a named refusal at exit 4.

    Dropping the bullet would be the silent failure this project keeps paying for: a sentence about
    somebody else's work would survive its evidence being withdrawn, and only a reader who happened to
    know the field would notice.
    """
    by_id = {row["id"]: row for row in inputs.ledger}
    missing = [row_id for row_id in cited_ids() if row_id not in by_id]
    if missing:
        raise PublishedArtefactUnavailable(
            "%s declares no row `%s` (it holds %d rows), so docs/REPORT.md would be citing a source the"
            " ledger never opened. This is not a usage error: no argument names the ledger,"
            " `techreport.LEDGER_MD` does." % (LEDGER_MD, "`, `".join(missing), len(by_id)))
    stale = sorted((row_id, by_id[row_id]["status"]) for row_id in cited_ids()
                   if by_id[row_id]["status"] != "verified")
    if stale:
        raise PublishedArtefactUnavailable(
            "%s no longer carries row `%s` as `verified` -- its status is `%s` -- and docs/REPORT.md"
            " still quotes it. A claim about other people's work that has outlived its evidence is the"
            " checkout's failure and no argument repairs it: retire the citation in the same commit that"
            " changes the ledger row." % (LEDGER_MD, stale[0][0], stale[0][1]))


def _lead(inputs: ReportInputs) -> list:
    protocol = inputs.protocol
    rubric = protocol.rubric
    grid = rubric["grid"]
    return [
        "# autorate: technical report",
        "",
        "One document for a reviewer to hold. It is generated: `python -m autorate.cli report --full`",
        "writes it and `python -m autorate.cli verify` renders it again from the committed artefacts named",
        "below and compares the bytes. No figure in it is typed into a string literal in the renderer, no",
        "date here was computed by this run -- every date is a transcription of a committed artefact's own",
        "date, the freeze's `frozen_at` and the claim ledger's `opened` column -- and no absolute machine",
        "path appears, so a machine that never saw the corpus produces exactly these bytes.",
        "",
        "- protocol described: version %s, frozen %s, digest `%s` (the file is `cli.PROTOCOL_JSON`)"
        % (protocol.protocol_version, protocol.frozen_at, protocol_digest(protocol)),
        "- record contract: shape %s, primitives %s"
        % (protocol.record_contract["shape_version"],
           ", ".join("`%s`" % p for p in protocol.record_contract["primitives"])),
        "- rubric: %s" % ", ".join("`%s`=%s" % (k, rubric[k]) for k in rubric if k != "grid"),
        "- diagnostic grid: %s points, %s to %s -- evidence only, nothing on it was certified"
        % (len(grid), grid[0], grid[-1]),
        "- artefacts this document reads: %d set certificates, %d ordinal one, %d resplit tasks,"
        " %d slice rows declared as inputs, %d inventory gaps, %d ledger rows of which %d are quoted here"
        % (len(inputs.certificates), len(SEVERITY_CERTS), len(inputs.resplit["tasks"]),
           len(inputs.slices["inputs"]), len(inputs.inventory["gaps"]), len(inputs.ledger),
           len(cited_ids())),
        "",
    ]


def _what_a_certificate_is(inputs: ReportInputs) -> list:
    stored = _stored_fields()
    reasons = sorted(reason.value for reason in Reason)
    rows = inputs.certificate_rows()
    published = sorted({cert.reason for _p, _t, cert in rows if not cert.feasible and cert.reason})
    envelopes = [len(cert.envelope) for _p, _t, cert in rows]
    label, _records, severity, direction = inputs.severity
    return [
        "## What a certificate is",
        "",
        "A benchmark answers \"how good is the model\". A certificate answers the question an operator can",
        "be held to: what share of this model's decisions may run unattended while the probability that an",
        "automated decision is wrong stays at most `beta`, given the held-out data that actually exists.",
        "When the data cannot carry that claim the certificate says so, names the reason, and the command",
        "exits with the not-certifiable code: a number about nothing is the one output this project",
        "refuses to produce.",
        "",
        "- stored shape: `autorate.certificate.Certificate`, shape version %d, %d fields -- %s"
        % (SHAPE_VERSION, len(stored), ", ".join("`%s`" % name for name in stored)),
        "- derived, never stored, because each is a pure function of a stored field: `level` = "
        "`1 - N_CLAIMS * delta` = `1 - %d * %s`, and `refusal_rate` = `1 - autorate`"
        % (N_CLAIMS, inputs.protocol.rubric["delta"]),
        "- the decision a certificate licenses, in the freeze's own words: %s"
        % inputs.protocol.decision_rule,
        "- a refusal names one of a closed set of %d reasons (`certificate.Reason`): %s"
        % (len(reasons), ", ".join("`%s`" % reason for reason in reasons)),
        "- of those, the reasons this tree has actually published: %s"
        % (", ".join("`%s`" % reason for reason in published) or "none yet"),
        "- a certificate cannot be constructed without an envelope, so the disclaimer survives",
        "  serialization instead of living in a README someone has to remember to read. The %d set"
        " artefacts carry between %d and %d envelope lines each, and the ordinal one carries %d."
        % (len(envelopes), min(envelopes), max(envelopes), len(severity.envelope)),
        "- the ordinal certificate is a sibling shape, not a `Certificate`: it reports `ahat`=%s over %s"
        " calibration and %s evaluation records of the `%s` population, at direction `%s`, and the"
        " refusal reasons it can name are its own closed set"
        % (severity.ahat, severity.n_cal, severity.n_eval, label, direction),
        "",
    ]


def _stored_fields() -> list:
    """The certificate's field names, read off the dataclass rather than recopied from the README."""
    from .certificate import Certificate

    return [f.name for f in fields(Certificate)]


def _mechanism(inputs: ReportInputs) -> list:
    rubric = inputs.protocol.rubric
    run = inputs.slices["run"]
    quantile_lines = []
    for path, table, cert in inputs.certificate_rows():
        if table != "report.CERTS":
            continue
        index = math.ceil((1.0 - cert.alpha) * (cert.n_cal + 1))
        # A refused certificate holds no set size, so the clause about it is written only when the
        # artefact carries one: printing `qhat=None` would put the renderer's own gap in the document.
        published = (", published `qhat`=%s" % cert.qhat if cert.qhat is not None
                     else ", and this artefact publishes no `qhat` at all")
        quantile_lines.append("    - `%s`: `ceil((1 - %s) * (%d + 1))` = %d of %d calibration scores%s"
                              % (path, cert.alpha, cert.n_cal, index, cert.n_cal, published))
    unit_lines = ["- `%s`: %s" % (path, cert.meta["unit_note"])
                  for path, _table, cert in inputs.certificate_rows() if cert.meta.get("unit_note")]
    methods = ", ".join("`%s` -> `%s`" % (name, METHODS[name].__name__) for name in sorted(METHODS))
    return [
        "## The mechanism",
        "",
        "The parts, each with one owner in this tree. The report names the owner and quotes the value;",
        "it never re-runs the arithmetic and never restates a bound, because a restated bound is a bound",
        "with two owners and a gate that cannot see which one moved.",
        "",
        "- **Nonconformity.** `conformal.METHODS` maps every name the certifier accepts to its score "
        "function: %s. The published rubric runs `%s`, and the other name is the declared comparison "
        "arm -- it exists so that a claim about set size is measured rather than asserted, and it is not "
        "a second publication." % (methods, rubric["method"]),
        "- **The split quantile.** `conformal.split_quantile` fixes the set size on the calibration half "
        "at the finite-sample-corrected index, and reports `vacuous_quantile` rather than clipping when "
        "that index runs past the sample. Selecting the size on the cases later held out to test it is "
        "snooping, so the published artefacts do not do it:",
    ] + quantile_lines + [
        "- **Clopper-Pearson.** Every error bound here is `tails.clopper_pearson_upper(k, n, delta)`, an "
        "exact one-sided binomial bound from inverting the binomial tail, and the width behind "
        "`autorate_ci` is `tails.bound_width`. The bounds themselves are quoted from the artefacts "
        "below, stored at %d decimals by `certificate.canonicalise_bound`: the last bits of a "
        "transcendental are not the same number on every C library, and a published figure only one "
        "machine can reproduce certifies nothing." % _published_decimals(),
        "- **The union bound.** One feasible certificate publishes %d bounds -- the conditional error "
        "bound, the marginal error bound and the automation-rate interval -- each tested at `delta`=%s, "
        "so its joint level is %s. A group-conditional run divides the budgets by the number of slices "
        "the data produced, and by nothing else; the rule it publishes is `correction.JOINT_LEVEL_RULE`, "
        "quoted verbatim below." % (N_CLAIMS, rubric["delta"], _joint_level(rubric)),
        "",
        "> %s" % JOINT_LEVEL_RULE,
        "",
        "G4's published run has %s slices at `n_claims`=%s, so `alpha` and `delta` become %s each, and "
        "the joint level the artefact states beside them is %s."
        % (run["n_groups"], run["n_claims"], run["corrected_alpha"], run["level"]),
        "",
        "- **The unit.** `%s`: the certification unit is the case, never the archive row. Each artefact "
        "states the denominator it used in its own words, and the report quotes that field rather than "
        "writing a second justification for it:" % rubric["unit"],
    ] + unit_lines + [
        "",
        "### What this rubric does not govern",
        "",
        "The freeze carries its own scope limitation as a field, and a report that restated the rubric",
        "without it would be the misreading the field exists to prevent:",
        "",
        "> %s" % inputs.protocol.rubric_scope,
        "",
        "### The evidence base, and how big it is",
        "",
        "The bound is computed on independent cases, not on rows, so the count a reader divides by is the",
        "`n_independent` column below -- quoted from the inventory `verify` polices, with each option's",
        "own recorded basis beside it rather than a paraphrase of it.",
        "",
        "| corpus option | unit | n_independent | n_rows | count basis |",
        "|---|---|---|---|---|",
    ] + [
        "| `%s` | %s | %s | %s | %s |"
        % (option["id"], option["unit"],
           "not opened" if option["n_independent"] is None else option["n_independent"],
           "-" if option["n_rows"] is None else option["n_rows"],
           first_clause(option["basis"], ";", _BASIS_WIDTH))
        for option in inputs.inventory["corpus_options"]
    ] + [
        "",
        "The archived corpus behind the first pair holds %s unique cases, repeated %s, over %d slice keys;"
        " %d archive lines were read to build it, and %d provenance digests and %d recorded gaps travel"
        " with it."
        % (inputs.inventory["unique_ids"],
           ", ".join(str(r) for r in inputs.inventory["repeats"]), len(inputs.inventory["families"]),
           inputs.inventory["reader_lines_read"], len(inputs.inventory["digests"]),
           len(inputs.inventory["gaps"])),
        "",
    ]


def _published_decimals() -> int:
    from .certificate import PUBLISHED_DECIMALS

    return PUBLISHED_DECIMALS


def _joint_level(rubric: dict) -> str:
    """`1 - N_CLAIMS * delta`, stated with the operands it is made from so the reader can rebuild it."""
    return "%d - %d * %s = %s" % (1, N_CLAIMS, rubric["delta"], 1.0 - N_CLAIMS * rubric["delta"])


def _claims(inputs: ReportInputs) -> list:
    lines = [
        "## The five gates, as the freeze states them",
        "",
        "One owner for this list: `protocol.json`'s `claims` array, in the order the emitter writes it.",
        "The statuses below are properties of the same document `verify` enforces, so a status that moves",
        "in the freeze moves here and nothing else can disagree with it. The ids are the criteria spec §2",
        "names: %s." % ", ".join("`%s`" % row["id"] for row in inputs.protocol.claims),
        "",
    ]
    for row in inputs.protocol.claims:
        artefacts = row["artefacts"]
        lines += [
            "### %s -- `%s`" % (row["id"], row["status"]),
            "",
            "- criterion: %s" % row["criterion"],
            "- measurement: %s" % row["measurement"],
            "- artefacts: %d -- %s" % (len(artefacts),
                                       ", ".join("`%s`" % a for a in artefacts)
                                       or "the row states none, and that is the finding"),
        ]
        for name in ("certified_tasks", "published_certificates", "refusal_reasons"):
            if name not in row:
                continue
            value = row[name]
            lines.append("- `%s`: %s" % (name, ", ".join("`%s`" % v for v in value)
                                         if isinstance(value, list) else value))
        lines += ["- note: %s" % row["note"], ""]
    return lines


def _refusals(inputs: ReportInputs) -> list:
    rows = inputs.certificate_rows()
    certified = [path for path, _t, cert in rows if cert.feasible]
    label, _records, severity, direction = inputs.severity
    doc, slices = inputs.resplit, inputs.slices
    run = slices["run"]
    lines = [
        "## Every refusal, and what it refused",
        "",
        "This is the half of the record a summary usually drops, so it is printed artefact by artefact.",
        "Each line names the file it quotes and then that file's own summary sentence, verbatim: the",
        "digits in the sentence are the digits in the artefact, and `verify` re-derives the artefact from",
        "the committed records beside it.",
        "",
        "| artefact | declared by | subject | verdict | reason | coverage | beta | n_cal | n_eval |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for path, table, cert in rows:
        lines.append("| `%s` | `%s` | `%s` | %s | %s | %s | %s | %s | %s |"
                     % (path, table, cert.backend,
                        "certified" if cert.feasible else "**refused**",
                        "`%s`" % cert.reason if cert.reason else "-",
                        1.0 - cert.alpha, cert.beta, cert.n_cal, cert.n_eval))
    lines += [
        "",
        "Verbatim, because the summary is the certifier's own sentence and not this document's:",
        "",
    ]
    lines += ["- `%s`: %s" % (path, cert.summary()) for path, _table, cert in rows]
    lines += [
        "",
        "%d of the %d published set certificates certify. The reasons named above are the whole of what"
        " the rest refused, and each refusal travels inside its artefact with the budget pair that made"
        " it, its case counts and its envelope."
        % (len(certified), len(rows)),
        "",
        "### The ordinal certificate (G3)",
        "",
        "- artefact `%s`, certified from `%s`, at direction `%s`: the publication table"
        " `report.SEVERITY_CERTS` names the rule and `verify` re-derives at it, rather than reading the"
        " rule back out of the bytes it is checking"
        % (SEVERITY_CERTS[label][1], SEVERITY_CERTS[label][0], direction),
        "- verdict: %s" % ("certified" if severity.feasible else "`%s`" % severity.reason),
        "- `%s`: %s" % (SEVERITY_CERTS[label][1], severity.summary()),
        "- its population is synthetic ordinal data with known answers, and the artefact states that in"
        " %d envelope lines of its own: no committed records file in this checkout carries a `score`"
        " record, which is why the ordinal guarantee is measured on a synthetic population at all."
        % len(severity.envelope),
        "",
        "### The resplit experiment (G1's second column)",
        "",
        "%s splits per task, and what came out of them. A task that issued no certificate has no"
        " violation rate to report, and the artefact leaves it undefined instead of imputing a zero:"
        % doc["resplits"],
        "",
        "| task | certified | refusals | violations / denominator | rate |",
        "|---|---|---|---|---|",
    ]
    for task in sorted(doc["tasks"], key=lambda row: str(row["label"])):
        refusals = ", ".join("`%s`:%d" % (reason, count)
                             for reason, count in sorted(task["refusal_reasons"].items())) or "-"
        lines.append("| `%s` | %d of %s | %s | %d / %d | %s |"
                     % (task["label"], task["certificates_issued"], doc["resplits"], refusals,
                        task["violations"], task["violations_denominator"],
                        "undefined (no certificates)" if task["violation_rate"] is None
                        else task["violation_rate"]))
    lines += [
        "",
        "### The slice run (G4)",
        "",
        "Slices are named by the key the producer declares (`%s`), refused by name, and the pooled"
        " certificate is published beside them rather than in place of them." % slices["group_key"],
        "",
        "| slice | feasible | reason | n_cal | n_eval |",
        "|---|---|---|---|---|",
    ]
    for group in sorted(run["per_group"]):
        cert = run["per_group"][group]
        lines.append("| `%s` | %s | %s | %s | %s |"
                     % (group, cert["feasible"], cert["reason"], cert["n_cal"], cert["n_eval"]))
    lines += [
        "",
        "- worst slice of the joint claim: `%s` on metric `%s`; any slice refused: %s"
        % (run["worst_claim"]["worst"]["group"], run["worst_claim"]["metric"],
           run["any_slice_refused"]),
        "- slices refused by the size floor rather than by a bound: %d" % len(run["refused_by_size"]),
        "- pooled over the same records: feasible=%s, reason=%s, n_eval=%s"
        % (run["pooled"]["feasible"], run["pooled"]["reason"], run["pooled"]["n_eval"]),
        "- inputs this run is a function of, with the digests that pin it: %s"
        % ", ".join("`%s` (%s rows, `%s`)" % (row["path"], row["rows"], row["digest"])
                    for row in slices["inputs"]),
        "",
        "### The gate the reference README instructs (G2)",
        "",
        "G2's measurement is `docs/AUDIT.md`, written by `autorate audit` from the committed records and",
        "byte-compared by `verify`. Its verdict is the freeze's row above, quoted in the claims section",
        "rather than restated here, and that row reads: `%s`." % _status_of(inputs, "G2"),
        "",
        "### What a refusal costs the caller",
        "",
        "A refusal is a result, so it is loud in the exit code and never in a traceback. The codes this",
        "project publishes, read from `cli.py`'s constants:",
        "",
    ]
    lines += ["- `%d` -- %s" % (code, meaning) for code, meaning in inputs.exit_codes]
    lines += [
        "",
        "A published artefact this checkout cannot read -- nothing at its path, the path refusing the",
        "open, or bytes that are not the artefact the table declares -- is a named refusal at the drift",
        "code and not a usage error: no argument selected that path, the publication table did, and no",
        "argument can repair it. Nothing is allowed to escape as code 1.",
        "",
    ]
    return lines


def _status_of(inputs: ReportInputs, claim_id: str) -> str:
    return inputs.protocol.claim(claim_id)["status"]


def _envelope(inputs: ReportInputs) -> list:
    protocol = inputs.protocol
    pin = inputs.pin
    corpus_pinned = protocol.corpus["pinned_builds"]["massive_intent"]
    return [
        "## The envelope and known limits, copied from the protocol",
        "",
        "A certificate read without its envelope is invalid output, so the assumptions travel inside the",
        "artefact. `protocol.json`'s `known_limits` block is the union of the envelope lines the published",
        "set certificates actually carry, sorted -- %d lines, quoted rather than paraphrased:"
        % len(protocol.known_limits),
        "",
    ] + ["- %s" % line for line in protocol.known_limits] + [
        "",
        "What those lines do not cover is stated by the artefacts that do, each in its own envelope:",
        "the ordinal certificate in %d lines, naming the population it was measured on and the rule it"
        % len(inputs.severity[2].envelope),
        "certifies, and the slice run in %d, saying which budgets were divided, which were not, and what"
        % len(inputs.slices["run"]["envelope"]),
        "the pooled certificate may not stand in for. Those documents are `docs/SEVERITY.md` and",
        "`docs/SLICES.md`, each byte-compared by `verify`.",
        "",
        "### The pinned build behind the MASSIVE figures",
        "",
        "Read from `%s` through `inventory.massive_pin`, which polices its counts against each other"
        " before anything is printed:" % MASSIVE_PIN_LABEL,
        "",
    ] + ["- `%s`: %s" % (name, pin[name]) for name in MASSIVE_PIN_FIELDS] + [
        "",
        "The id sets across the shards are identical (`id_sets_identical`: %s) and the per-shard row"
        % pin["id_sets_identical"],
        "counts collapse to %d distinct value (%s), which is why a bound may sit on %s independent"
        % (len(pin["distinct_row_counts"]),
           ", ".join(str(n) for n in pin["distinct_row_counts"]), pin["distinct_ids"]),
        "utterances and not on %s rows." % pin["rows_total"],
        "That is the difference between a certificate and a restatement of the same sentence %d times."
        % pin["n_files"],
        "",
        "This report prints no per-shard digest: `%s` owns the %d of them, and the freeze pins that file"
        % (MASSIVE_PIN_LABEL, len(pin["files"])),
        "by its own digest (`%s`) instead of transcribing it, because a published figure with two owners"
        % corpus_pinned["pin_digest"],
        "is two figures.",
        "",
    ]


def _reproduction(inputs: ReportInputs) -> list:
    corpus = inputs.protocol.corpus
    counts = {backend: len(rs) for backend, rs in sorted(inputs.records.items())}
    return [
        "## Reproduction (G5)",
        "",
        "`autorate verify --protocol protocol.json` is the claim. It needs no GPU, no network, no model",
        "and no corpus: every input is a committed file, and the two lanes the command can run in print",
        "different denominators on purpose -- the corpus-absent lane transcribes the inventory snapshot it",
        "cannot contradict and says so in its own disclosure line.",
        "",
        "- documents `verify` byte-compares (`cli.PUBLISHED_DOCS`, %d of them, this file among them): %s"
        % (len(inputs.published_docs), ", ".join("`%s`" % doc for doc in inputs.published_docs)),
        "- the records every table above is built on: `%s` (%s)"
        % (RECORDS, ", ".join("%s=%d rows" % item for item in counts.items())),
        "- the inventory the document arm read: `%s`" % INVENTORY_JSON,
        "- digests the freeze named in advance, which are the two checks in that gate that are not fixed",
        "  points: `%s` -> `%s`, and `%s` -> `%s`"
        % (corpus["records_owner"], corpus["records_digest"], corpus["inventory_owner"],
           corpus["inventory_digest"]),
        "- the corpus is not a committed file: it is a sibling `laya*/research/benchmarks/feishu_zh`",
        "  checkout, resolved from the environment, then the flag, then the sibling glob. No source file",
        "  carries an absolute path to it, and a test fails the build if one reappears.",
        "",
        "G5's own row states what is still owed, and this document quotes it instead of settling it:",
        "",
        "> %s" % inputs.protocol.claim("G5")["note"],
        "",
    ]


def _related_work(inputs: ReportInputs) -> list:
    by_id = {row["id"]: row for row in inputs.ledger}
    statuses = [row["status"] for row in inputs.ledger]
    lines = [
        "## Related work, cited only where the ledger opened it",
        "",
        "`%s` holds %d rows: %d `verified`, %d `withdrawn`. Only a `verified` row is quotable here as a"
        " claim about somebody else's work, and every bullet below IS that row's own claim cell -- cut to"
        " %d characters with a visible marker, with the row id, the date the source was opened and the"
        " status printed beside it. A row this document cites that the ledger does not carry, or that has"
        " left `verified` since, makes the renderer refuse instead of printing the sentence, so %d ids"
        " are re-checked against the ledger on every render."
        % (LEDGER_MD, len(inputs.ledger), statuses.count("verified"), statuses.count("withdrawn"),
           _LEDGER_WIDTH, len(cited_ids())),
        "",
    ]
    for title, rows in RELATED_WORK:
        lines.append("### %s" % title)
        lines.append("")
        for row_id, role in rows:
            row = by_id[row_id]
            lines.append("- `%s` (%s) -- opened %s, status `%s`: %s"
                         % (row_id, role, row["opened"], row["status"],
                            first_clause(row["claim"], None, _LEDGER_WIDTH)))
        lines.append("")
    searches = [row_id for row_id, _role in RELATED_WORK[SEARCHES_GROUP][1]]
    lines += [
        "### Why a null result is written as a task",
        "",
        "The last group above is not a finding about the field; it is a record of a search, and the only",
        "date attached to it is the date the ledger says that search ran (%s)."
        % ", ".join("`%s` opened %s" % (row_id, by_id[row_id]["opened"]) for row_id in searches),
        "A `none found` in this repository therefore means \"not found by this search on this date\",",
        "never \"does not exist\"; the row's own claim cell, quoted above, is what states its scope.",
        "",
        "The severity summary quoted in the refusal section names prior art inside its own sentence. This",
        "document does not restate that sentence: the rows which opened those sources are cited above --"
        " %s -- so the summary stays the artefact's and the evidence stays the ledger's."
        % ", ".join("`%s`" % row_id for row_id in SEVERITY_PRIOR_ART),
        "",
    ]
    return lines


def render_report(inputs: ReportInputs) -> str:
    """`docs/REPORT.md`, assembled from the artefacts and from nothing else.

    The order is the plan's: what a certificate is, the mechanism, the five gates as named claims, every
    refusal, the envelope and known limits copied from the protocol, reproduction, related work. Each
    section builder is private and takes the whole record, because a section that took one artefact would
    have to re-read the others to write its own lead sentence -- and two readings of one table is how a
    published document comes to disagree with itself.
    """
    _validate_citations(inputs)
    lines: list = []
    for section in (_lead, _what_a_certificate_is, _mechanism, _claims, _refusals, _envelope,
                    _reproduction, _related_work):
        lines += section(inputs)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def dates_in(text: str) -> tuple:
    """Every date-shaped token in a rendered document, in order of appearance."""
    return tuple(_DATE_RX.findall(text))


def transcribed_dates(inputs: ReportInputs) -> tuple:
    """The dates this report may print, because a committed artefact already states them.

    The guard's whole question is whether a date was computed or copied, and this is where copying is
    legal: the freeze's `frozen_at`, and every `opened` column in the ledger. A date in the rendered text
    outside this set is a date this run invented, which makes the byte comparison un-reproducible.
    """
    out = {inputs.protocol.frozen_at}
    out.update(row["opened"] for row in inputs.ledger)
    return tuple(sorted(out))
