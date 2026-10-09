"""Build and re-derive the published results document.

Determinism is the product: the report contains no timestamp and nothing that is not
derived from the committed inputs (`data/inventory.md.json`, `data/records_feishu.jsonl`,
`data/cert_*.json`), so `verify` can compare it byte for byte in any environment --
including one that never saw the vendored corpus. Corpus provenance is pinned by the
digests in the upstream `SOURCE.json`, which is their owner; the inventory transcribes
them, and this module quotes the transcription rather than hashing anything itself.
"""
from __future__ import annotations

import json
from pathlib import Path

from .certificate import Certificate
from .certify_choice import certify_choice
from .records import Record
from .tails import clopper_pearson_upper

RECORDS = "data/records_feishu.jsonl"
CERTS = {"laya": "data/cert_laya.json", "jev": "data/cert_jev.json"}
INVENTORY_JSON = "data/inventory.md.json"
ALPHA = 0.05
BETA = 0.05
SEED = 7
# The budgets the archived corpus is certified at. beta is deliberately loose: the
# evaluation half is ~96 records, and a tighter budget would only be honest about a
# claim this corpus cannot make at all.
BACKENDS = ("laya", "jev")

# G1's published certificates: one artefact per held-out MASSIVE language, never pooled, because one
# gate over three corpora would assert exchangeability between a 0.4617-accuracy and a 0.0982-accuracy
# population. `verify` re-derives them and `report` publishes them, so the paths live once here rather
# than in a list inside each caller -- two lists that can disagree about what was certified is the
# defect this table exists to prevent, not a formatting choice.
MASSIVE_CERTIFICATES = {
    "massive/de": ("data/records_massive_de.jsonl", "data/cert_massive_de_laya.json"),
    "massive/en": ("data/records_massive_en.jsonl", "data/cert_massive_en_laya.json"),
    "massive/sw": ("data/records_massive_sw.jsonl", "data/cert_massive_sw_laya.json"),
}


class PublishedArtefactUnavailable(RuntimeError):
    """A file the publication tables declare is absent from this checkout, or there and unreadable.

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
    checkout does not hold, or holds but cannot open, raises, because a certificate the tool cannot read
    is not the same statement as a certificate that agrees with nothing -- and it raises as
    `PublishedArtefactUnavailable`, naming the table that declared the path, because "usage error" would
    blame the operator for a checkout this package wrote.
    """
    out = {}
    for label, (records_path, cert_path) in sorted(MASSIVE_CERTIFICATES.items()):
        stored = read_certificate(require_published(cert_path, "report.MASSIVE_CERTIFICATES"))
        rows = require_published(records_path, "report.MASSIVE_CERTIFICATES")
        out[label] = (load_records(rows).get(stored.backend, []), stored)
    return out


def rederive_massive(expect, fields) -> None:
    """Re-derive every published MASSIVE certificate from its committed records, field by field.

    This is the arm `cmd_verify` already runs over the two feishu certificates, widened to G1's three
    languages: read the artefact, run `certify_choice` over the rows that artefact was made from at the
    rubric stored *inside* it, and hand every comparison to `verify`'s own `expect`, so a drift leaves as
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
        fresh = certify_choice(records, alpha=stored.alpha, beta=stored.beta,
                               delta=stored.delta, seed=stored.meta.get("seed", SEED),
                               method=stored.method)
        for field in fields:
            expect("cert %s.%s" % (label, field), getattr(fresh, field), getattr(stored, field))
        expect("cert %s.summary" % label, fresh.summary(), stored.summary())


def _first_clause(gap: str) -> str:
    """The clause a published bullet quotes, with an explicit marker when it is cut."""
    head = gap.split(";")[0]
    return head[:78] + ("..." if len(head) > 78 else "")


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
        % (len(inv["gaps"]), "; ".join(_first_clause(g) for g in inv["gaps"])),
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
            lines.append("| %s | **NOT_CERTIFIABLE** (%s) | - | - | - | - | - | - | %d/%d "
                         "| %s/%s |"
                         % (b, c.reason, c.n_cal, c.n_eval,
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
