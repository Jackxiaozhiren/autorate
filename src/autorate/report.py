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


def _decision_clause(cert) -> str:
    """Say what one certificate actually says, at the denominator its own bound was computed on.

    Three published defects are what this shape avoids. The first version printed a fixed sentence per
    backend, so a regenerated artifact could assert the opposite of the counts inside it. The repair then
    quoted the zero-error counterfactual at `n_eval_cases`, which for laya is 32 while its bound was
    computed over its 2 automated cases -- so the row printed another row's number (0.089 where its own
    counterfactual is 0.776). And it spoke of "both rows refusing" unconditionally, which a certified row
    contradicts. Every figure is read from the certificate; the case bound and the record-denominator
    bound both belong to `certify_choice` and are never re-derived here.

    `automated_cases`/`n_eval_cases`/`erroneous_cases` are absent on the two earliest refusals
    (`n_below_min`, `no_gold_labels`), which return before the counters are recorded, so they default to
    zero rather than raising inside a published-artifact generator.
    """
    if cert.feasible:
        return ("it certifies: %d of its %d evaluation cases automate and none of them is wrong, so the "
                "exact case-level upper bound is %.3f against the %.3f budget, at an automation rate of "
                "%.3f." % (cert.meta.get("automated_cases", 0), cert.meta.get("n_eval_cases", 0),
                           cert.conditional_error_bound, cert.beta, cert.autorate))
    automated = cert.meta.get("automated_cases", 0)
    n_cases = cert.meta.get("n_eval_cases", 0)
    wrong = cert.meta.get("erroneous_cases", 0)
    if automated == 0:
        return ("not one evaluation case produced a single-label set (%d empty, %d multi-label of %d "
                "records), so there is nothing it may run unattended."
                % (cert.meta.get("empties", 0), cert.meta.get("multi_label", 0), cert.n_eval))
    carries = "carries" if wrong == 1 else "carry"
    bound = (cert.meta.get("at_requested_alpha") or {}).get("conditional_error_bound")
    if bound is None:
        return ("it automates %d of its %d evaluation cases and %d of those %s a wrong automated "
                "request, which the %.3f budget does not license."
                % (automated, n_cases, wrong, carries, cert.beta))
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
    """The record-denominator contrast, read from the certificate, or nothing at all.

    `certify_choice` already publishes the record-level figure as `closest_attempt`; recomputing it here
    gave a published number two owners, which is what R-20/R-31/R-44 delete. If the certificate carries
    none -- an early refusal, or a certified row, neither of which records an attempt -- the sentence is
    dropped rather than printed with a `nan` in it. The verdict word is derived from the comparison, not
    asserted.
    """
    attempt = cert.meta.get("closest_attempt") or {}
    record_bound = attempt.get("conditional_error_bound")
    automated = cert.meta.get("automated", 0)
    if record_bound is None or not automated:
        return ""
    where = "inside" if record_bound <= cert.beta else "above"
    # The trailing provenance sentence was dropped rather than kept: naming the source in prose would
    # need a seventh interpolation, and the sentence is a claim about this module, not about the corpus.
    return ("The record denominator is what flatters this corpus: %s's %d automated records would bound "
            "at %.3f, %s its %.3f budget, where the %d independent cases the corpus actually supplies put "
            "it at %.3f -- and the case is the unit a bound may divide by (R-44)."
            % (cert.backend, automated, record_bound, where, cert.beta,
               cert.meta.get("n_eval_cases", 0),
               (cert.meta.get("at_requested_alpha") or {}).get("conditional_error_bound", record_bound)))


def _pair_lead(*certs) -> str:
    """Name the pair's verdict honestly: two refusals, two certificates, or one of each."""
    refused = [c for c in certs if c is not None and not c.feasible]
    if len(refused) == len([c for c in certs if c is not None]):
        return "Both rows refuse at %s." % _budget_clause(*certs)
    if not refused:
        return "Both rows certify at %s." % _budget_clause(*certs)
    return "%d of %d rows refuse at %s." % (len(refused), len(certs), _budget_clause(*certs))


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
    it. Every figure below is read from `inv`, and the translation claim is asserted only when the
    per-language and pooled options actually report the same row count -- which is what translations of
    one utterance set must do -- so a future divergence silences the claim instead of repeating it.
    """
    def option(kind):
        return next((o for o in inv["corpus_options"] if o["id"] == kind), None)

    feishu, pooled, per_lang = option("feishu_zh"), option("massive_intent_all_languages"), \
        option("massive_intent_per_language")
    parts = ["The bound is computed on independent cases, not on rows:"]
    if feishu is not None:
        parts.append("feishu's %d archived lines are %d unique cases;"
                     % (inv["reader_lines_read"], feishu["n_independent"]))
    if pooled and per_lang and pooled["n_independent"] == per_lang["n_independent"]:
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
                         "| %d/%d | %d/%d |"
                         % (b, c.autorate, lo, hi, c.conditional_error_bound,
                            c.marginal_error_bound, c.refusal_rate, c.mean_set_size,
                            c.n_cal, c.n_eval, c.meta["n_cal_cases"],
                            c.meta["n_eval_cases"]))
        else:
            lines.append("| %s | **NOT_CERTIFIABLE** (%s) | - | - | - | - | - | - | %d/%d "
                         "| %s/%s |"
                         % (b, c.reason, c.n_cal, c.n_eval,
                            c.meta.get("n_cal_cases", "-"),
                            c.meta.get("n_eval_cases", "-")))
    lines += ["", "### Verbatim summaries", ""]
    for b in BACKENDS:
        lines.append("```")
        lines.append("%s: %s" % (b, certs[b].summary()))
        lines.append("```")
    lines += [
        "",
        "### What this does and does not establish",
        "",
        "- %s laya: %s jev: %s %s" % (
            _pair_lead(certs["laya"], certs["jev"]), _decision_clause(certs["laya"]),
            _decision_clause(certs["jev"]), _record_clause(certs["jev"])),
        _laya_point_or_problem(certs["laya"], scores),
        ("- The evaluation halves hold %d and %d RECORDS over %d and %d distinct cases (the "
         "corpus repeats each case %d times) and %d cases are in common, so the pair is a "
         "case-by-case comparison on identical inputs." if shared == len(ids["laya"])
         == len(ids["jev"]) else
         "- The evaluation halves hold %d and %d RECORDS over %d and %d distinct cases (the "
         "corpus repeats each case %d times) and only %d cases are in common, so the pair is "
         "a case-by-case comparison where they overlap and two marginal certificates "
         "elsewhere.") % (
            certs["laya"].n_eval, certs["jev"].n_eval, len(ids["laya"]), len(ids["jev"]),
            len(inv["repeats"]), shared),
        "- The bounds are per CASE: repeats of one case are one observation (laya's three "
        "per case are byte-identical), so %d records are %d cases and the denominators above "
        "say which is which. Per-slice certification, the ordinal `score` family and the "
        "`noul` budgets are Plan B, gated on a corpus with enough independent cases to bound "
        "them." % (certs["jev"].n_eval, certs["jev"].meta["n_eval_cases"]),
        "- Exchangeability is assumed within a backend and a question shape, not proven; the "
        "envelope on each certificate is the machine-readable statement of that limit.",
        "",
    ]
    return "\n".join(lines)


def write_report(text: str, out: Path) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


def read_certificate(path: Path) -> Certificate:
    return Certificate.from_dict(json.loads(Path(path).read_text()))
