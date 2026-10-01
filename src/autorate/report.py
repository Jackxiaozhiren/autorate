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
        "The bound is computed on independent cases, not on rows: MASSIVE's 51 language",
        "files are translations of the same 2,974 utterances, and feishu's 384 archive",
        "lines are 64 cases repeated. Counting either as sample size flatters the bound.",
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
        "| backend | verdict | autorate | ci | conditional <= | marginal <= | refusal | mean set size | n_cal/n_eval |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for b in BACKENDS:
        c = certs[b]
        if c.feasible:
            lo, hi = c.autorate_ci
            lines.append("| %s | certified | %.3f | %.3f..%.3f | %.3f | %.3f | %.3f | %.2f | %d/%d |"
                         % (b, c.autorate, lo, hi, c.conditional_error_bound,
                            c.marginal_error_bound, c.refusal_rate, c.mean_set_size,
                            c.n_cal, c.n_eval))
        else:
            lines.append("| %s | **NOT_CERTIFIABLE** (%s) | - | - | - | - | - | - | %d/%d |"
                         % (b, c.reason, c.n_cal, c.n_eval))
    lines += ["", "### Verbatim summaries", ""]
    for b in BACKENDS:
        lines.append("```")
        lines.append("%s: %s" % (b, certs[b].summary()))
        lines.append("```")
    lines += [
        "",
        "### What this does and does not establish",
        "",
        "- The jev row is a **bound**, not a precision claim. With zero errors the exact "
        "one-sided bound is `clopper_pearson_upper(0, %d, %.2f)` = %.4f, i.e. the %.3f "
        "published above. It is a knife-edge: the same n gives %.4f with one error and %.4f "
        "with two, so the %.2f budget holds only while the model keeps making none." % (
            certs["jev"].n_eval, certs["jev"].delta,
            clopper_pearson_upper(0, certs["jev"].n_eval, certs["jev"].delta),
            certs["jev"].conditional_error_bound,
            clopper_pearson_upper(1, certs["jev"].n_eval, certs["jev"].delta),
            clopper_pearson_upper(2, certs["jev"].n_eval, certs["jev"].delta),
            certs["jev"].beta)
        if certs["jev"].feasible and certs["jev"].meta.get("errors_among_automated") == 0 else
        "- Both backends refuse at these budgets, or certify with errors above zero; the "
        "table and the summaries above carry the numbers either way.",
        "- The laya row is the project's point, not its problem: on a Chinese workplace "
        "corpus where the archived audit scores its choice answers %s, a certificate "
        "that refuses is the correct output. A published number here would be a number "
        "about nothing." % scores[("laya", "choice")],
        "- The evaluation halves hold %d and %d RECORDS over %d and %d distinct request "
        "ids (the corpus repeats each case three times), and %d request ids are in common. "
        "So the pair is a case-by-case comparison only where they overlap; the rest is two "
        "marginal certificates on the same corpus." % (
            certs["laya"].n_eval, certs["jev"].n_eval, len(ids["laya"]), len(ids["jev"]),
            shared),
        "- n_eval is ~96 because the corpus has 64 unique cases. Per-slice certification, "
        "the ordinal `score` family and the `noul` budgets are Plan B, gated on a corpus with "
        "enough records to bound them.",
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
