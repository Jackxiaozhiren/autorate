"""The only module that prints: certify / compare / gate / report / verify / export-feishu."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .certify_choice import certify_choice
from .gate import Gate
from .inventory import corpus_label, inventory, write_inventory
from .records import Record
from .report import (ALPHA, BETA, CERTS, INVENTORY_JSON, RECORDS, SEED, build_report,
                     certify_all, load_records, read_certificate, write_report)

EXIT_CERTIFIED = 0
EXIT_NOT_CERTIFIABLE = 3
EXIT_USAGE = 2
EXIT_DRIFT = 4
RESULTS = Path("docs/RESULTS.md")
INVENTORY_MD = Path("data/inventory.md")
FROM_CORPUS = "recomputed from the corpus"
FROM_SNAPSHOT = "committed %s" % INVENTORY_JSON
# Written by the environment that can reach the corpus, so they cannot be compared
# anywhere else. They are excluded by name, not by luck: everything else in the
# snapshot must match what a fresh scan produces.
SNAPSHOT_MACHINE_KEYS = ("source", "audit_interpreter", "upstream_audit_stdout_tail",
                         "upstream_audit_stderr_tail")


def expect_snapshot_is_current(expect, inv: dict) -> None:
    """Police the committed snapshot from the only environment that can see its truth.

    A corpus-less `verify` reads this file, so a snapshot that drifted from the corpus
    would otherwise be published as fact forever and never contradict anyone.
    """
    path = Path(INVENTORY_JSON)
    if not path.exists():
        expect("%s committed" % INVENTORY_JSON, path.exists(), True)
        return
    committed = json.loads(path.read_text())
    for key in sorted(set(inv) | set(committed)):
        if key in SNAPSHOT_MACHINE_KEYS:
            continue
        expect("snapshot %s" % key, inv.get(key), committed.get(key))


def _records_from(path: Path, backend=None, mode=None) -> list:
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = Record.from_dict(json.loads(line))
        if backend and r.backend != backend:
            continue
        if mode and r.slices.get("mode") != mode:
            continue
        out.append(r)
    return out


def _default_corpus() -> Path:
    """Find the vendored corpus as a SIBLING of this repo, with no absolute literal.

    A hard-coded /Users/<name>/... default passes every local gate -- including a clean
    export re-run on the same disk, because the same disk is right here -- and only breaks
    in the one environment where the gate has teeth. `inventory._audit_python` already
    refuses to hardcode its interpreter for the same reason; this was the last literal left.
    """
    checkout = Path(__file__).resolve().parents[2].parent
    candidates = sorted(checkout.glob("laya*/research/benchmarks/feishu_zh"))
    return candidates[0] if candidates else None


def _root(args) -> Path:
    import os

    env = os.environ.get("AUTORATE_FEISHU_ROOT")
    if env:
        return Path(env)
    if getattr(args, "root", None):
        return Path(args.root)
    return _default_corpus()


def _require_root(args) -> Path:
    root = _root(args)
    if root is None or not (root / "data" / "manifest.json").exists():
        raise SystemExit(
            "no corpus found: pass --root or set AUTORATE_FEISHU_ROOT (looked for a "
            "sibling `laya*/research/benchmarks/feishu_zh`)")
    return root


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


def cmd_certify(args) -> int:
    recs = _records_from(Path(args.records), backend=args.backend, mode=args.mode)
    cert = certify_choice(recs, alpha=args.alpha, beta=args.beta, delta=args.delta,
                          seed=args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert.to_json())
    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


RUBRIC_FIELDS = ("alpha", "beta", "delta", "method", "seed")

NON_CHOICE_REASON = "qtype_not_covered"
# Every number a certificate publishes that verify re-derives. It is a named constant so
# the corpus-less lane can assert a count DERIVED from it instead of a typed one.
CERT_COMPARE_FIELDS = ("feasible", "reason", "backend", "autorate", "autorate_ci", "qhat",
                       "conditional_error_bound", "marginal_error_bound",
                       "refusal_rate", "mean_set_size", "n_cal", "n_eval", "envelope")


def _rubric(cert) -> dict:
    return {f: (cert.meta.get(f) if f == "seed" else getattr(cert, f)) for f in RUBRIC_FIELDS}


def cmd_compare(args) -> int:
    """Print only what was actually checked; `compare` has no authority to pair anything."""
    labels = (Path(args.files[0]).name, Path(args.files[1]).name)
    certs = tuple(read_certificate(Path(f)) for f in args.files)
    rubrics = [_rubric(c) for c in certs]
    off = [f for f in RUBRIC_FIELDS if rubrics[0][f] != rubrics[1][f]]
    if off:
        print("comparable: NO -- the two sides disagree on %s" % ", ".join(
            "%s (%s=%r, %s=%r)" % (f, labels[0], rubrics[0][f], labels[1], rubrics[1][f])
            for f in off))
    else:
        print("comparable: yes -- identical %s" % ", ".join(
            "%s=%s" % (f, rubrics[0][f]) for f in RUBRIC_FIELDS))
    backends = [c.backend for c in certs]
    ids = [set(c.meta.get("eval_ids", [])) for c in certs]
    if None in backends or backends[0] == backends[1] or not all(ids):
        print("halves not paired: subjects %r, evaluation ids named %r" % (
            backends, [len(x) for x in ids]))
    else:
        print("evaluation halves: %s has %d records over %d distinct request ids, %s has "
              "%d over %d, and they have %d request ids in common" % (
                  backends[0], certs[0].n_eval, len(ids[0]),
                  backends[1], certs[1].n_eval, len(ids[1]), len(ids[0] & ids[1])))
    for name, c in zip(labels, certs):
        print("  %s: %s" % (name, c.summary()))
        for line in c.envelope:
            print("    envelope:", line)
    return 0


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
    root = _root(argparse.Namespace())
    if root is not None and (root / "data" / "manifest.json").exists():
        return inventory(root), FROM_CORPUS
    cached = Path(INVENTORY_JSON)
    if not cached.exists():
        raise SystemExit("no corpus and no committed %s: nothing to verify against" % cached)
    return json.loads(cached.read_text()), FROM_SNAPSHOT


def cmd_snapshot(args) -> int:
    """Write the committed inventory from the corpus. `verify` polices whether it is stale."""
    root = _require_root(args)
    out = Path(args.out)
    write_inventory(inventory(root), out)
    print("wrote %s and %s from %s" % (out, str(out) + ".json", corpus_label(root)))
    return 0


def cmd_report(args) -> int:
    records = load_records(Path(RECORDS))
    inv, _ = _inventory()
    out = Path(args.out)
    write_report(build_report(inv, certify_all(records),
                              {b: len(rs) for b, rs in records.items()}), out)
    print("wrote %s" % out)
    return 0


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
        stored = read_certificate(Path(path))
        # the real comparison: re-derive the certificate from the committed records
        fresh = certify_choice(records.get(backend, []), alpha=stored.alpha,
                               beta=stored.beta, delta=stored.delta,
                               seed=stored.meta.get("seed", SEED))
        for field in CERT_COMPARE_FIELDS:
            expect("cert %s.%s" % (backend, field), getattr(fresh, field),
                   getattr(stored, field))
        expect("cert %s.summary" % backend, fresh.summary(), stored.summary())

    inv, source = _inventory()
    rebuilt = build_report(inv, certify_all(records),
                           {b: len(rs) for b, rs in records.items()})
    expect("docs/RESULTS.md byte-identical", rebuilt, RESULTS.read_text())

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
    n.add_argument("--root", help="corpus root; default: env or a sibling laya*/ checkout")
    n.add_argument("--out", default=str(INVENTORY_MD))
    n.set_defaults(fn=cmd_snapshot)

    e = sub.add_parser("export-feishu", help="archive responses -> records")
    e.add_argument("--root", help="corpus root; default: env or a sibling laya*/ checkout")
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

    v = sub.add_parser("verify", help="re-derive every published number")
    v.set_defaults(fn=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (OSError, ValueError) as exc:
        # OSError: an input path that is not there. ValueError: a stored certificate that
        # violates its own shape rules. Both are "the inputs are wrong", and both used to
        # escape as a traceback with rc 1 -- outside the documented 0/2/3/4 contract.
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
