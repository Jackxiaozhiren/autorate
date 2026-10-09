"""The only module that prints: certify / compare / gate / report / verify / export-feishu / audit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import DEFAULT_DELTA, DEFAULT_GATE, audit_fields, check_audit, render_audit
from .certify_choice import certify_choice
from .gate import Gate
from .inventory import corpus_label, inventory, write_inventory
from .readers.feishu_zh import ReaderContractError
from .records import Record
from .report import (ALPHA, BETA, CERTS, INVENTORY_JSON, PublishedArtefactUnavailable, RECORDS, SEED,
                     build_report, certify_all, load_published, load_records, read_certificate,
                     read_json, rederive_massive, write_report)

EXIT_CERTIFIED = 0
EXIT_NOT_CERTIFIABLE = 3
EXIT_USAGE = 2
EXIT_DRIFT = 4


class UsageError(ValueError):
    """The inputs are wrong: no corpus to read, no snapshot to fall back to.

    It used to be `SystemExit("<text>")`, which Python exits with **1** for -- a code the
    README does not document and which no test could pin. Carrying ValueError means
    `main`'s existing mapping turns it into EXIT_USAGE and the contract closes.
    """


RESULTS = Path("docs/RESULTS.md")
AUDIT_MD = Path("docs/AUDIT.md")
INVENTORY_MD = Path("data/inventory.md")
FROM_CORPUS = "recomputed from the corpus"
FROM_SNAPSHOT = "committed %s" % INVENTORY_JSON
# Written by the environment that can reach the corpus, so they cannot be compared
# anywhere else. They are excluded by name, not by luck: everything else in the
# snapshot must match what a fresh scan produces.
SNAPSHOT_MACHINE_KEYS = ("source", "audit_interpreter", "upstream_audit_stdout_tail",
                         "upstream_audit_stderr_tail")

# Every column of a MASSIVE row that `corpus_options` computes FROM the pin, named once so the
# gate and the test that counts the gate read the same list. The first four are the pin's own
# fields; the last three are derived from `n_independent` by `tails.bound_width`/`tails.n_feasible`
# and are the figures the table exists to publish. They were not compared until R-83: measured at
# `5ec8639`, a checkout publishing `bound_width_at_0.05 = 0.0100` (true `0.0498`) and
# `feasible_at_0.10 = False` (true `True`) on both MASSIVE rows passed `verify` with
# "re-derived 41 /41 values" and rc 0, because the two byte-comparisons re-render the snapshot from
# the snapshot itself and the pin arm stopped at the inputs. In the corpus-absent lane the bound
# column therefore had no producer at all -- and that is the lane CI runs.
PIN_DERIVED_KEYS = ("n_rows", "n_independent", "n_shards", "basis",
                    "bound_width_at_0.05", "feasible_at_0.10", "feasible_at_0.25")


def expect_snapshot_is_current(expect, inv: dict) -> None:
    """Police the committed snapshot from the only environment that can see its truth.

    A corpus-less `verify` reads this file, so a snapshot that drifted from the corpus
    would otherwise be published as fact forever and never contradict anyone.
    """
    path = Path(INVENTORY_JSON)
    if not path.exists():
        expect("%s committed" % INVENTORY_JSON, path.exists(), True)
        return
    committed = load_published(path, "report.INVENTORY_JSON", read_json)
    for key in sorted(set(inv) | set(committed)):
        if key in SNAPSHOT_MACHINE_KEYS:
            continue
        expect("snapshot %s" % key, inv.get(key), committed.get(key))


def _records_from(path: Path, backend=None, mode=None) -> list:
    out = []
    for number, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            # Refused here, at the site that decides "a line becomes a record", rather than by
            # `Record.from_dict`: a list answers its field check by accident (`"id" in [1, 2, 3]` is
            # legal Python, and the loader round `746f10f` turns it into `MissingRecordField`), but
            # `null` answers it with `TypeError: argument of type 'NoneType' is not iterable`, which
            # `cli.main` does not and must not catch -- measured as rc 1 through this very function
            # before the guard landed. rc 1 is outside the documented 0/2/3/4 contract, and a
            # hand-edited or truncated export is the operator's input, not ours.
            raise UsageError("%s line %d is a JSON %s, not a record object: this file is read as one "
                             "record per line, and a row that is not a mapping has no fields to read "
                             "(a blank line is skipped; a `null`, a number, a string or a list is a "
                             "refusal)" % (path, number, type(row).__name__))
        r = Record.from_dict(row)
        if backend and r.backend != backend:
            continue
        if mode and r.slices.get("mode") != mode:
            continue
        out.append(r)
    return out


# One owner for the third resolution path's shape: `_default_corpus` globs it, `_root` names it as a
# source, and the refusal quotes it, so a message can never describe a search the resolver did not do.
SIBLING_GLOB = "laya*/research/benchmarks/feishu_zh"
SIBLING_SOURCE = "the sibling `%s` default" % SIBLING_GLOB
ROOT_HELP = ("corpus root; AUTORATE_FEISHU_ROOT overrides it, then this flag, then a sibling "
             "`%s` checkout" % SIBLING_GLOB)


def _default_corpus() -> Path:
    """Find the vendored corpus as a SIBLING of this repo, with no absolute literal.

    A hard-coded /Users/<name>/... default passes every local gate -- including a clean
    export re-run on the same disk, because the same disk is right here -- and only breaks
    in the one environment where the gate has teeth. `inventory._audit_python` already
    refuses to hardcode its interpreter for the same reason; this was the last literal left.
    """
    checkout = Path(__file__).resolve().parents[2].parent
    candidates = sorted(checkout.glob(SIBLING_GLOB))
    return candidates[0] if candidates else None


def _root(args) -> tuple:
    """Resolve the corpus root AND the source that won it, as one value -- never one alone.

    Precedence is environment -> flag -> sibling, and that order is this repository's own harness
    contract: the corpus-absent lane (the tests, the export lane, the README's reproduction
    section) is *defined* by exporting `AUTORATE_FEISHU_ROOT=/nonexistent` for a whole process, and
    `tests/test_inventory.py` pins env-over-flag as the shape a lane may rely on. R-131's defect was
    therefore never the order: it was that the order was invisible. `_require_root` had only a path
    to go on, so it instructed the operator to `pass --root` when they had just done exactly that and
    claimed a sibling search it had not performed -- a refusal with the right exit code and the wrong
    diagnosis. Carrying the source with the path is what makes the two impossible to separate again.
    """
    import os

    env = os.environ.get("AUTORATE_FEISHU_ROOT")
    if env:
        return Path(env), "AUTORATE_FEISHU_ROOT"
    if getattr(args, "root", None):
        return Path(args.root), "--root"
    return _default_corpus(), SIBLING_SOURCE


def _no_corpus(root, source, flag) -> UsageError:
    """The refusal, naming the source that answered and the path it actually tried.

    Three shapes, because the advice differs and the operator's next action differs:
    the environment outvoted an explicit flag (say it was overridden, and how to stop it), a source
    was given and simply is not a corpus (say which one and where), or nothing was given at all
    (only then is "pass --root" honest, and only then was the sibling default even consulted).
    """
    if source == SIBLING_SOURCE:
        return UsageError(
            "no corpus found: neither --root nor AUTORATE_FEISHU_ROOT was given, and the sibling "
            "default `%s` matched nothing beside this checkout" % SIBLING_GLOB)
    if source == "AUTORATE_FEISHU_ROOT" and flag:
        return UsageError(
            "no corpus found: AUTORATE_FEISHU_ROOT points at %s, which has no data/manifest.json, "
            "and the --root you passed (%s) was overridden by it -- unset AUTORATE_FEISHU_ROOT to "
            "use the flag" % (root, Path(flag)))
    return UsageError("no corpus found: %s points at %s, which has no data/manifest.json"
                      % (source, root))


def _require_root(args) -> Path:
    root, source = _root(args)
    if root is not None and (root / "data" / "manifest.json").exists():
        return root
    raise _no_corpus(root, source, getattr(args, "root", None))


def cmd_export_feishu(args) -> int:
    from .readers.feishu_zh import read_archive

    stats: dict = {}
    recs = read_archive(_require_root(args), backend=args.backend, repeat=args.repeat,
                        mode=args.mode, stats=stats)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r.to_dict(), sort_keys=True, ensure_ascii=False) + "\n"
                           for r in recs))
    print("exported %d records from %d archive lines to %s (by mode %s, dropped_not_ok=%d)"
          % (stats["records_kept"], stats["lines_kept"], out, stats["lines_by_mode"],
             stats["lines_dropped_not_ok"]))
    for q in stats.get("quarantined", []):
        print("quarantined: %s/%s repeat=%s probs_sum=%s" % (
            q["backend"], q["id"], q["repeat"], q["probs_sum"]))
    return 0


def _slice_keys(values):
    """The `--groups` text, as the tuple of names the Mondrian surface asks for.

    Always a tuple, never a bare string: `groups.py` refuses a string because it iterates characters
    -- `--groups family` arriving as `"family"` would ask for the keys 'f', 'a', 'm' -- and a CLI that
    handed the operator's text straight through would be producing the one input shape its own
    contract refuses. Repeated flags accumulate, so `--groups language --groups option_count` is the
    two-key slice the spec writes as (language x option-count).
    """
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    keys = []
    for value in values:
        for part in str(value).split(","):
            name = part.strip()
            if not name:
                raise UsageError("--groups states an empty slice key (%r): a group has to be nameable "
                                 "in the artefact that publishes it" % (value,))
            keys.append(name)
    if not keys:
        raise UsageError("--groups was given no slice key; a split conditioned on nothing is the "
                         "MARGINAL, and the marginal already has a command (certify without "
                         "--groups)")
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise UsageError("--groups names %s twice: the second declaration would ask for the same "
                         "partition again and the slice count that divides the budgets would be wrong "
                         "by it" % ", ".join(repr(d) for d in duplicates))
    return tuple(keys)


def _print_slices(cert) -> None:
    """The per-slice verdict lines, so the artefact cannot be read as one pooled number.

    Printed from the certificates themselves and the worst-of-G artefact, in census order. A slice
    refused by the size floor is named with its case count, because §8.1's whole claim is that the
    thin slices are refused BY NAME -- a summary that only counts them is the averaging this tool is
    supposed to refuse. A verdict produced by the certifier is named with the cases THAT RULE WAS
    HANDED, and the difference is stated in words on the same line, so the count and the reason
    cannot describe two different populations (G2/F-5).
    """
    claim = cert.worst_claim
    by_group_name = {row["group"]: row for row in claim["refusals"]}
    # Which branch produced the verdict, read from the artefact's own size-floor list rather than from
    # `reason`: a certifier CAN refuse the population it was handed with `n_below_min` too (a slice
    # holding 140 cases of which 10 are labelled passes the floor and then has 10 cases split), and
    # that refusal is stated in terms of the cases it could read, not the cases on disk.
    by_floor = {row["group"] for row in cert.refused_by_size}
    rows = {row["group"]: row for row in cert.slice_census}
    for name, slice_cert in cert.per_group.items():
        held = cert.slice_cases[name]
        n_cases = held if name in by_floor else cert.slice_eligible_cases[name]
        gap = ""
        if n_cases != held:
            # Each number keeps its OWN unit: the difference is in cases (the certification unit) and
            # the drop counts are per record, so one sentence naming both is the only version that
            # cannot be read as a case count of unlabelled rows. `wrong_qtype` is the other cause a
            # slice can lose cases to, and attributing it to labels would be a false confession.
            row = rows[name]
            causes = []
            if row["skipped_no_gold"]:
                causes.append("%d records carry no gold label" % row["skipped_no_gold"])
            if row["skipped_wrong_qtype"]:
                causes.append("%d records answer another question type" % row["skipped_wrong_qtype"])
            gap = " -- %d of the slice's %d cases never reached the rule (%s)" % (
                held - n_cases, held, ", ".join(causes))
        if slice_cert.feasible:
            print("  slice %s (n=%d cases): autorate %.3f, conditional error <= %.3f, level %.4f%s"
                  % (name, n_cases, slice_cert.autorate, slice_cert.conditional_error_bound,
                     slice_cert.level, gap))
        else:
            why = by_group_name.get(name, {}).get("why", slice_cert.meta.get("detail", "refused"))
            print("  slice %s (n=%d cases): NOT CERTIFIED -- %s%s" % (name, n_cases, why, gap))
    if cert.refused_by_size:
        print("  refused by size (below %d cases, the two halves of the split this rule certifies "
              "on): %s" % (cert.meta["min_cases_per_slice"],
                           ", ".join("%s(n=%d)" % (row["group"], row["n"])
                                     for row in cert.refused_by_size)))
    print("  worst-of-%d over %s: slice %s; joint level %.4f = 1 - %d claims x delta %.3f, with "
          "alpha/delta corrected to %.6f per slice"
          % (claim["n_groups"], ", ".join(repr(g) for g in cert.groups),
             claim["worst"]["group"], cert.level, cert.n_claims, cert.delta, cert.corrected_delta))


def cmd_certify(args) -> int:
    """Records -> certificate, marginal or group-conditional, and the exit code says which.

    - **rc 0** -- the certificate a deployment acts on is feasible. Without `--groups` that is the
      one marginal certificate; with it, EVERY slice certified, because the thing being claimed is
      the worst of them.
    - **rc 3** -- the run measured and refused: a marginal refusal, or one slice below the size floor
      or over budget. The simultaneous claim does not exist, which is a result, not a crash.
    - **rc 2** -- `--groups` names a key the records never declare (`UndeclaredGroupKey`), states an
      empty or repeated key, or the rubric is not a probability. `main`'s `ValueError` arm maps all
      of these, and the group-key refusal is a dedicated subclass precisely so this path needs no new
      catch: R-115 ruled that `cli.main` gains no `KeyError` arm, because `KeyError` is ordinary dict
      access everywhere here and catching it centrally would turn unrelated bugs into an exit 2 with
      a helpful-looking message. Before that ruling the typo `--groups langauge` exited **1**.
    - **rc 4** -- an invariant of our own arithmetic failed (`ArithmeticError`), which is not the
      operator's mistake and not a refusal about the data.
    """
    recs = _records_from(Path(args.records), backend=args.backend, mode=args.mode)
    groups = _slice_keys(getattr(args, "groups", None))
    cert = certify_choice(recs, alpha=args.alpha, beta=args.beta, delta=args.delta,
                          seed=args.seed, method=args.method, groups=groups)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert.to_json())
    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    if groups is not None:
        _print_slices(cert)
    # The exit code is `cert.feasible`, and for a group run that property IS the conjunction over the
    # slices: a deployment acts on the worst-of-G statement, so answering 0 because the marginal
    # certificate certified while a slice has no bound at all is the averaging spec 8.1 refuses. rc 3
    # is then the refusal of the simultaneous claim, not a crash, and rc 0 means every slice certified.
    code = EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE
    if cert.meta.get("diagnostic_curve"):
        print("  diagnostic sweep: %d coverage levels in meta.diagnostic_curve of %s "
              "(evidence only; nothing on it was certified)"
              % (len(cert.meta["diagnostic_curve"]), args.out))
    print("wrote %s" % args.out)
    return code


RUBRIC_FIELDS = ("alpha", "beta", "delta", "method", "seed")

# Every number a certificate publishes that verify re-derives, named so the corpus-less
# lane can assert a count DERIVED from it rather than typed. `method` and `meta` are on the
# list because the first version omitted them: a certificate edited to "method": "lac"
# verified 56/56 green and the gate then automated with a rule nobody measured, and
# `meta.eval_ids` -- which `compare` prints a pairing claim from -- was free to invent.
CERT_COMPARE_FIELDS = ("feasible", "reason", "backend", "method", "meta", "autorate",
                       "autorate_ci", "qhat", "conditional_error_bound",
                       "marginal_error_bound", "refusal_rate", "mean_set_size", "n_cal",
                       "n_eval", "envelope")


def _rubric(cert) -> dict:
    return {f: (cert.meta.get(f) if f == "seed" else getattr(cert, f)) for f in RUBRIC_FIELDS}


def cmd_compare(args) -> int:
    """Print only what was actually checked; `compare` has no authority to pair anything."""
    labels = (Path(args.files[0]).name, Path(args.files[1]).name)
    certs = tuple(read_certificate(Path(f)) for f in args.files)
    not_comparable = False
    rubrics = [_rubric(c) for c in certs]
    off = [f for f in RUBRIC_FIELDS if rubrics[0][f] != rubrics[1][f]]
    if off:
        print("comparable: NO -- the two sides disagree on %s" % ", ".join(
            "%s (%s=%r, %s=%r)" % (f, labels[0], rubrics[0][f], labels[1], rubrics[1][f])
            for f in off))
        not_comparable = True
    else:
        print("comparable: yes -- identical %s" % ", ".join(
            "%s=%s" % (f, rubrics[0][f]) for f in RUBRIC_FIELDS))
    backends = [c.backend for c in certs]
    ids = [set(c.meta.get("eval_ids", [])) for c in certs]
    if None in backends or backends[0] == backends[1] or not all(ids):
        print("halves not paired: subjects %r, evaluation ids named %r" % (
            backends, [len(x) for x in ids]))
        not_comparable = True
    else:
        print("evaluation halves: %s has %d records over %d distinct request ids, %s has "
              "%d over %d, and they have %d request ids in common" % (
                  backends[0], certs[0].n_eval, len(ids[0]),
                  backends[1], certs[1].n_eval, len(ids[1]), len(ids[0] & ids[1])))
    for name, c in zip(labels, certs):
        print("  %s: %s" % (name, c.summary()))
        for line in c.envelope:
            print("    envelope:", line)
    return EXIT_USAGE if not_comparable else 0


def cmd_gate(args) -> int:
    cert = read_certificate(Path(args.cert))
    gate = Gate(cert)
    recs = _records_from(Path(args.records))
    if args.backend:
        recs = [r for r in recs if r.backend == args.backend]
    print("envelope carried by every decision below:")
    for line in gate.decide(recs[0])["envelope"] if recs else []:
        print("  ", line)
    for r in recs[: args.limit]:
        d = gate.decide(r)
        print("%s/%s: action=%s set=%s label=%s why=%s qhat=%s method=%s" % (
            r.backend, r.id, d["action"], d["set"], d.get("label"), d.get("why"),
            d.get("qhat"), d.get("method")))
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


def _inventory() -> tuple:
    """Recompute the inventory when the corpus is on this machine; else read its committed copy.

    The fallback is what makes `verify` runnable on a machine that has never seen the
    vendored tree -- which is the whole point of a reproduction gate, and the CI case.
    The label is disclosure only: it never enters the report body, so the report stays
    byte-identical either way, and it tells `verify` which of its checks are real
    re-derivations rather than transcriptions of the committed snapshot.
    """
    root, _ = _root(argparse.Namespace())
    if root is not None and (root / "data" / "manifest.json").exists():
        return inventory(root), FROM_CORPUS
    cached = Path(INVENTORY_JSON)
    if not cached.exists():
        raise UsageError("no corpus and no committed %s: nothing to verify against" % cached)
    return load_published(cached, "report.INVENTORY_JSON", read_json), FROM_SNAPSHOT


def cmd_snapshot(args) -> int:
    """Write the committed inventory from the corpus. `verify` polices whether it is stale."""
    root = _require_root(args)
    out = Path(args.out)
    write_inventory(inventory(root), out)
    print("wrote %s and %s from %s" % (out, str(out) + ".json", corpus_label(root)))
    return 0


def _rendered_inventory(inv: dict) -> str:
    """What `write_inventory` would render from these inputs, written to a scratch file.

    The committed markdown is a published artefact and the snapshot beside it is what a
    corpus-less `verify` reads, so the pair has to be checked against each other wherever
    they are -- the renderer needs no corpus, only the dict.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "inventory.md"
        write_inventory(inv, out)
        return out.read_text()


def cmd_report(args) -> int:
    records = load_records(Path(RECORDS))
    inv, _ = _inventory()
    out = Path(args.out)
    write_report(build_report(inv, certify_all(records),
                              {b: len(rs) for b, rs in records.items()}), out)
    print("wrote %s" % out)
    return 0


def cmd_audit(args) -> int:
    """Emit G2: the gate the reference README instructs, measured against what it implies.

    Offline, on committed inputs only (`data/records_feishu.jsonl`), no corpus and no inference.

    Which arm each failure is, because the map is the product:

    - **rc 2 (usage)** -- `load_records` cannot open the file, the named backend is not in it, the
      gate or delta is not a probability, or every row of the population was excluded. The last one
      is the arm a naive implementation gets wrong: 1,536 of the 1,919 archived rows carry
      `gold is None`, so an audit that iterates all of them reports a rate by invention. Nothing to
      audit is the operator's question, not an answer about the corpus.
    - **rc 3 (not certifiable)** -- the audit ran, measured everything it could, and NO published
      row is informative: on every field the exact upper bound sits above the error rate the gate's
      own sentence implies, so the corpus cannot bound the gate. `autorate audit laya` lands here
      today, and that is §5.5's refusal-as-product, not a crash.
    - **rc 4 (drift)** -- `audit.AuditDriftError`, an `ArithmeticError`: the audit's own figures
      contradict each other (a case partition that does not close, an excluded row that was not
      counted, a bound below the rate it bounds, a frontier that is not monotone in its own gate).
      `main` already maps that family here for the two sibling invariants; this is the third.
    - **rc 1 is unreachable from a data defect.** A record the counter cannot score would surface
      as `ValueError` -> 2, and a rate over an empty denominator is published as a named note
      instead of a number, so there is no path from "the archive is awkward" to a traceback.
    """
    records = load_records(Path(args.records))
    if args.backend:
        if args.backend not in records:
            raise UsageError("no records for backend %r in %s (it holds: %s)" % (
                args.backend, args.records, ", ".join(sorted(records)) or "nothing"))
        wanted = [args.backend]
    else:
        wanted = sorted(records)
    if not wanted:
        raise UsageError("no records to audit in %s: an audit over an empty file measures nothing"
                         % args.records)
    audits = {b: audit_fields(records[b], gate=args.gate, delta=args.delta) for b in wanted}
    check_audit(audits)
    text = render_audit(audits)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    for backend in wanted:
        first = next(iter(audits[backend].values()))
        print("%s: %d rows handed over, %d audited, %d excluded (%s)" % (
            backend, first["n_rows_handed_over"], first["n_records"],
            sum(first["excluded_reasons"].values()),
            "; ".join("%d: %s" % (count, reason)
                      for reason, count in sorted(first["excluded_reasons"].items()))
            or "no exclusions"))
        for field in sorted(audits[backend]):
            row = audits[backend][field]
            print("  %s/%s: %d of %d cases automated, %d wrong -> measured %s vs implied %.2f"
                  " = %s; CP upper %s (one-sided) / %s (two-sided); informative: %s%s" % (
                      backend, field, row["automated_cases"], row["n_cases"],
                      row["erroneous_cases"],
                      "n/a" if row["measured_error"] is None else "%.4f" % row["measured_error"],
                      row["implied_error"],
                      "n/a" if row["multiple"] is None else "%.2fx" % row["multiple"],
                      "-" if row["bound"] is None else "%.4f" % row["bound"],
                      "-" if row["bound_two_sided"] is None else "%.4f" % row["bound_two_sided"],
                      "-" if row["informative"] is None else ("yes" if row["informative"] else "NO"),
                      (" -- " + row["note"]) if row.get("note") else ""))
    print("wrote %s" % out)
    # rc 3 vs rc 0: a refusal is a result, so it must be loud in the exit code. Informative means
    # the audit produced at least one bound that actually sits under the implied error rate; if
    # every row failed that test, no gate on this corpus is bounded and nothing was certified.
    informative = any(row["informative"] for table in audits.values() for row in table.values())
    return EXIT_CERTIFIED if informative else EXIT_NOT_CERTIFIABLE


# Every published document `verify` re-renders and compares byte for byte, named once so the gate
# cannot disagree with the list the documents are written from. A hand-kept list of published files
# inside the gate would be a second owner of the publication list -- the defect class R-168 was
# written for -- so the test that counts the gate counts `len(PUBLISHED_DOCS)` rather than a literal,
# and the label printed on a failure is the path itself.
PUBLISHED_DOCS = (
    (RESULTS, lambda inv, records: build_report(
        inv, certify_all(records), {b: len(rs) for b, rs in records.items()})),
    (INVENTORY_MD, lambda inv, records: _rendered_inventory(inv)),
    # Called with no gate and no delta on purpose: the committed `docs/AUDIT.md` was written by
    # `autorate audit` under `audit_fields`' own defaults, so re-deriving it means re-deriving the
    # default row, not inventing a third parameter set for the gate to own.
    (AUDIT_MD, lambda inv, records: render_audit(
        {b: audit_fields(rs) for b, rs in sorted(records.items())})),
)


def cmd_verify(args) -> int:
    """Recompute every published number from committed inputs and fail on drift."""
    checked = total = 0
    failures = []

    def expect(label, actual, wanted):
        nonlocal checked, total
        total += 1
        if actual == wanted:
            checked += 1
        else:
            failures.append("%s: recomputed %r, published %r" % (label, actual, wanted))

    records = load_records(Path(RECORDS))
    for backend, path in sorted(CERTS.items()):
        stored = load_published(path, "report.CERTS", read_certificate)
        # the real comparison: re-derive the certificate from the committed records
        fresh = certify_choice(records.get(backend, []), alpha=stored.alpha,
                               beta=stored.beta, delta=stored.delta,
                               seed=stored.meta.get("seed", SEED))
        for field in CERT_COMPARE_FIELDS:
            expect("cert %s.%s" % (backend, field), getattr(fresh, field),
                   getattr(stored, field))
        expect("cert %s.summary" % backend, fresh.summary(), stored.summary())

    # G1's published artefacts re-derive the same way, from `report.py`'s table, because that is the
    # file that also prints them -- a second list of artefacts inside the gate could disagree with the
    # list the document is built from. The field list is handed in rather than copied for the same
    # reason: `CERT_COMPARE_FIELDS` has one owner, and it is this file.
    rederive_massive(expect, CERT_COMPARE_FIELDS)

    inv, source = _inventory()
    for path, render in PUBLISHED_DOCS:
        expect("%s byte-identical" % path, render(inv, records),
               load_published(path, "cli.PUBLISHED_DOCS", Path.read_text))

    if source == FROM_CORPUS:
        for d in inv["digests"]:
            expect("corpus digest %s" % d["path"], d["actual"], d["expected"])
        expect_snapshot_is_current(expect, inv)
        disclosure = "corpus present: inventory, digests and the snapshot all re-derived"
    else:
        disclosure = (
            "corpus absent: %d `SOURCE.json` digests and the inventory snapshot are "
            "transcribed from the committed %s, not recomputed -- this run cannot see "
            "whether that snapshot went stale" % (len(inv["digests"]), INVENTORY_JSON))

    # The MASSIVE rows are derived from a committed file, not from the corpus, so this arm of the
    # gate is where they can be re-derived in BOTH lanes -- which is the point of the sentence in
    # `docs/ERRATA.md` that claims `verify` re-derives the basis. Read from the pin, never from the
    # snapshot, so a pin edited on disk cannot agree with a snapshot that was written before it.
    # R-83: and every column `corpus_options` computes from the pin is in `PIN_DERIVED_KEYS`, bound
    # width included. The recomputation is not reimplemented here -- `corpus_options(None, pin=pin)`
    # is the one owner of the interval arithmetic, so the gate compares its output with the table.
    from .inventory import corpus_options as _corpus_options
    from .inventory import massive_pin as _massive_pin

    pin = _massive_pin()
    recomputed = {o["id"]: o for o in _corpus_options(None, pin=pin)}
    published = {o["id"]: o for o in inv["corpus_options"]}
    for opt_id in sorted(recomputed):
        if not opt_id.startswith("massive"):
            continue          # feishu's counts are corpus-derived; the absent arm cannot see them
        for key in PIN_DERIVED_KEYS:
            if key not in recomputed[opt_id]:
                continue
            expect("pin option %s.%s" % (opt_id, key), recomputed[opt_id].get(key),
                   published.get(opt_id, {}).get(key))

    print("inventory source: %s" % source)
    print("disclosure: %s" % disclosure)
    print("re-derived %d /%d values" % (checked, total))
    for f in failures:
        print("DRIFT:", f, file=sys.stderr)
    return EXIT_DRIFT if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autorate")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("snapshot", help="corpus -> committed data/inventory.md(.json)")
    n.add_argument("--root", help=ROOT_HELP)
    n.add_argument("--out", default=str(INVENTORY_MD))
    n.set_defaults(fn=cmd_snapshot)

    e = sub.add_parser("export-feishu", help="archive responses -> records")
    e.add_argument("--root", help=ROOT_HELP)
    e.add_argument("--out", required=True)
    e.add_argument("--backend")
    e.add_argument("--mode")
    e.add_argument("--repeat", type=int)
    e.set_defaults(fn=cmd_export_feishu)

    c = sub.add_parser("certify", help="records -> certificate")
    c.add_argument("records")
    c.add_argument("--backend")
    c.add_argument("--mode")
    c.add_argument("--alpha", type=float, default=ALPHA)
    c.add_argument("--beta", type=float, default=BETA)
    c.add_argument("--delta", type=float, default=0.05)
    c.add_argument("--seed", type=int, default=SEED)
    c.add_argument("--method", default="aps", choices=("aps", "lac"),
                   help="the nonconformity that sizes the set; lac is the comparison arm")
    c.add_argument("--groups", action="append", metavar="KEY[,KEY...]",
                   help="group-conditional (Mondrian) certification over these declared slice keys "
                        "(spec 8.1): one certificate per slice at alpha/n_groups and delta/n_groups, "
                        "a worst-of-n_groups claim, and the slices too small to bound refused BY "
                        "NAME. Repeatable, or comma-separated, so '--groups language,option_count' "
                        "and '--groups language --groups option_count' are the same run. The keys "
                        "must be declared by the records themselves -- a slice key nobody set is a "
                        "refusal (exit 2), not an empty group.")
    c.add_argument("--out", default="cert.json")
    c.set_defaults(fn=cmd_certify)

    m = sub.add_parser("compare", help="two certificates side by side")
    m.add_argument("files", nargs=2)
    m.set_defaults(fn=cmd_compare)

    g = sub.add_parser("gate", help="apply a certificate to records")
    g.add_argument("records")
    g.add_argument("--cert", required=True)
    g.add_argument("--backend")
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(fn=cmd_gate)

    r = sub.add_parser("report", help="write docs/RESULTS.md from the inputs")
    r.add_argument("--out", default=str(RESULTS))
    r.set_defaults(fn=cmd_report)

    a = sub.add_parser(
        "audit", help="G2: measure the gate the reference README instructs against the error "
                      "rate its own sentence implies, on committed records only (offline)")
    a.add_argument("backend", nargs="?", help="audit one backend; default: every backend in the "
                                              "records file, each audited on its own cases")
    a.add_argument("--gate", type=float, default=DEFAULT_GATE,
                   help="the threshold the README instructs (default %.2f); the implied error "
                        "rate is 1 - gate" % DEFAULT_GATE)
    a.add_argument("--delta", type=float, default=DEFAULT_DELTA,
                   help="level of the exact Clopper-Pearson bounds (default %.2f)" % DEFAULT_DELTA)
    a.add_argument("--records", default=RECORDS, help="committed records file (default %s)" % RECORDS)
    a.add_argument("--out", default=str(AUDIT_MD))
    a.set_defaults(fn=cmd_audit)

    v = sub.add_parser("verify", help="re-derive every published number")
    v.set_defaults(fn=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except ReaderContractError as exc:
        # I-2: the reader refusing a corpus condition (R-14) is not a line it could not
        # parse. It is a RuntimeError, so the tuple below would not see it and it would
        # escape as rc 1; mapping it here keeps the refusal loud and non-zero, and keeps it
        # out of the quarantine accounting entirely.
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE
    except PublishedArtefactUnavailable as exc:
        # A file that this package's own publication tables declare, which the checkout either does not
        # hold or cannot open. It is not EXIT_USAGE: the operator passed no path, so nothing they typed
        # is wrong -- what is wrong is the committed state, and the code for "the repository cannot
        # reproduce what it publishes" is EXIT_DRIFT. Falling through the tuple below instead was the
        # disclosure in `docs/ERRATA.md` (2026-10-08): a bare `FileNotFoundError` printed an errno and a
        # relative path and let `verify` call a missing certificate a usage error. A directory standing
        # in the artefact's place did the same through `IsADirectoryError`, which is why the guard opens
        # the file rather than only stat-ing it.
        # The refusal is deliberately not delivered through `expect`: a run that cannot open the
        # artefact has no comparisons to count, and printing a `re-derived` total from a tree that
        # never reached the arithmetic would publish a denominator this run did not earn.
        # `data/inventory.md.json` stays a usage error (`_inventory`'s own raise, pinned by
        # test_verify_without_a_corpus_or_a_snapshot_is_a_usage_error): there the environment supplies
        # nothing at all to verify against, which is a different statement from this one.
        print("PUBLISHED ARTEFACT UNAVAILABLE: %s" % exc, file=sys.stderr)
        return EXIT_DRIFT
    except ArithmeticError as exc:
        # Both raise sites protected by this clause are invariants about our own arithmetic:
        # `tails` refuses to publish a Clopper-Pearson bound beaten by its own data, and the reader
        # refuses to return when the line accounting does not conserve. Neither is the operator's
        # mistake, so neither belongs in EXIT_USAGE -- and adding ArithmeticError to the tuple below
        # would tell a user their inputs are wrong precisely when the numbers are what is wrong.
        # They also are not a refusal about the data (EXIT_NOT_CERTIFIABLE is). A tool that cannot
        # reproduce its own arithmetic is the failure EXIT_DRIFT already names.
        print("INVARIANT: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_DRIFT
    except (OSError, ValueError) as exc:
        # OSError: an input path that is not there. ValueError: bytes an operator-supplied path --
        # `--cert`, `compare`, the `--records` default -- hands over that this build cannot read. Both
        # are "the input this command was handed is wrong", and both used to escape as a traceback with
        # rc 1, outside the documented 0/2/3/4 contract. The same failure on a path a publication table
        # declares is NOT here: `PublishedArtefactUnavailable` above owns it, at 4.
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
