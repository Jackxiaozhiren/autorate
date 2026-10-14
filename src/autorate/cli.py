"""The only module that prints: certify / compare / gate / report / verify / export-feishu / audit."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .audit import DEFAULT_DELTA, DEFAULT_GATE, audit_fields, check_audit, render_audit
# The published rubric (#62): `verify` and `certify` default to these numbers, and the CLI is a
# consumer, not an owner. `DEFAULT_DELTA` comes from `audit` because the audit sub-command prints the
# audit's own help sentence; every other rubric flag reads `certificate` directly.
from .certificate import ALPHA, BETA, DELTA, METHOD, SEED
from .certify_choice import certify_choice
from .gate import Gate
from .inventory import corpus_label, inventory, write_inventory
from .protocol import emit_protocol, file_digest, load_protocol, protocol_digest, write_protocol
from .readers.feishu_zh import ReaderContractError
from .records import Record
from .report import (CERTS, INVENTORY_JSON, PublishedArtefactUnavailable, RECORDS, RESPLIT_JSON,
                     RESPLIT_MD, SEVERITY_CERTS,
                     SEVERITY_LABEL, SEVERITY_RECORDS, SLICE_JSON, SLICE_MD,
                     build_report, certify_all, load_published,
                     load_records, published_severity, read_certificate, read_inventory_snapshot,
                     read_resplit, read_slices, rederive_massive, rederive_resplit, rederive_severity,
                     rederive_slices, render_resplit, render_severity, render_slices,
                     write_report)
from .severity import DIRECTIONS, certify_severity
from .techreport import REPORT_MD, load_inputs, render_report

EXIT_CERTIFIED = 0
EXIT_NOT_CERTIFIABLE = 3
EXIT_USAGE = 2
EXIT_DRIFT = 4

# What each published code MEANS, stated once beside the codes that own it. The technical report prints
# this table instead of writing its own sentence about the exit contract, so a code added here appears
# there and a code retired here cannot survive in a document nobody re-reads. The values are the
# constants above, never re-typed.
EXIT_CODE_MEANINGS = (
    (EXIT_CERTIFIED, "certified: the certificate holds, or every published number reproduced"),
    (EXIT_USAGE, "usage: an input this command was handed is wrong, whether the operator named its path "
                 "or a default supplied it"),
    (EXIT_NOT_CERTIFIABLE, "not certifiable: the run measured and refused. A result, printed and "
                           "written, not a crash"),
    (EXIT_DRIFT, "drift: the committed state cannot reproduce what it publishes -- a number that "
                 "disagrees, or a published artefact this repository's own tables declare and this run "
                 "cannot read"),
)


class UsageError(ValueError):
    """The inputs are wrong: no corpus to read, no snapshot to fall back to.

    It used to be `SystemExit("<text>")`, which Python exits with **1** for -- a code the
    README does not document and which no test could pin. Carrying ValueError means
    `main`'s existing mapping turns it into EXIT_USAGE and the contract closes.
    """


RESULTS = Path("docs/RESULTS.md")
AUDIT_MD = Path("docs/AUDIT.md")
# G3's published document, named beside the other two because this file is where the commands that emit
# them are declared. `autorate severity --doc` writes it and `verify` re-renders it byte for byte, so the
# ordinal guarantee is legible to a reader instead of living only in a JSON artefact.
SEVERITY_MD = Path("docs/SEVERITY.md")
INVENTORY_MD = Path("data/inventory.md")
# The frozen protocol document, named here because this file is where the commands that read and write
# it are declared. `certify --protocol` takes a path from the operator; the DEFAULT stays `None`, and
# this constant is the table Task 2's `verify` will read as its own default (R-200's Design G) --
# naming it now is what keeps a later round from inventing a second spelling of the path.
PROTOCOL_JSON = Path("protocol.json")
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
    committed = load_published(path, "report.INVENTORY_JSON", read_inventory_snapshot)
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
    # Which branch produced the verdict, read from the artefact's own `n_min_violations` list rather than from
    # `reason`: a certifier CAN refuse the population it was handed with `n_below_min` too (a slice
    # holding 140 cases of which 10 are labelled passes the floor and then has 10 cases split), and
    # that refusal is stated in terms of the cases it could read, not the cases on disk.
    by_floor = {row["group"] for row in cert.n_min_violations}
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
    if cert.n_min_violations:
        print("  refused by size (below %d cases, the two halves of the split this rule certifies "
              "on): %s" % (cert.meta["min_cases_per_slice"],
                           ", ".join("%s(n=%d)" % (row["group"], row["n"])
                                     for row in cert.n_min_violations)))
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
      `--protocol` adds two more ways to land here: the document named cannot be read as this build's
      protocol (`ProtocolError`, a `ValueError`), or a rubric flag contradicts it (R-199's freeze,
      stated below).
    - **rc 4** -- an invariant of our own arithmetic failed (`ArithmeticError`), which is not the
      operator's mistake and not a refusal about the data.
    """
    protocol = load_protocol(Path(args.protocol)) if args.protocol else None
    rubric = _certify_rubric(args, protocol)
    recs = _records_from(Path(args.records), backend=args.backend, mode=args.mode)
    groups = _slice_keys(getattr(args, "groups", None))
    cert = certify_choice(recs, groups=groups, **rubric)
    if protocol is not None:
        # The freeze travels INSIDE the artefact. `meta` is one of `CERT_COMPARE_FIELDS`, so a
        # certificate stamped under a protocol and the same certificate re-derived without the stamp
        # disagree loudly -- which is why Task 1 stamps only when the flag is on its own command line,
        # and why the published artefacts get theirs in Task 2, in the commit that also re-exports them
        # (R-200: a half-moved HEAD is a red HEAD).
        cert = replace(cert, meta={**cert.meta, "protocol_digest": protocol_digest(protocol)})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert.to_json())
    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    if groups is not None:
        _print_slices(cert)
    if protocol is not None:
        print("  protocol: %s (version %d, frozen %s) digest %s"
              % (args.protocol, protocol.protocol_version, protocol.frozen_at,
                 protocol_digest(protocol)))
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


# The rubric fields `certify` takes as flags, each with the name that owns its default. The pairs are
# the imported owner names, not numbers: `test_every_cli_rubric_flag_defaults_to_the_owner_name_and_not_a_literal`
# is what keeps the second half of each pair honest, and the flag defaults stay the owner's values so a
# run with no `--protocol` behaves exactly as it did before the freeze existed.
CERTIFY_RUBRIC_FLAGS = (("alpha", ALPHA), ("beta", BETA), ("delta", DELTA), ("seed", SEED),
                        ("method", METHOD))

# The ordinal gate's own flags, and its own comparison list. `certify_severity` takes neither `beta` nor
# `method`: a severity certificate has no automated subset to condition on (the rule answers every case)
# and no nonconformity to choose (one loss family per direction), which is precisely why the surface is a
# verb of its own rather than a `--measure` flag on `certify` -- see `cmd_severity`.
SEVERITY_RUBRIC_FLAGS = (("alpha", ALPHA), ("delta", DELTA), ("seed", SEED))
SEVERITY_RUBRIC_FIELDS = ("alpha", "delta", "seed")
# What `verify` re-derives of the severity shape, named here for the same reason as the set list: one
# owner, read by the gate and by the test that counts it. `direction` is on the list although the
# publication table also declares it -- the artefact states the rule it claims to be, and both statements
# are compared. `meta` is compared whole, as it is on the set side, which is what makes an unstamped
# severity artefact drift rather than pass.
SEVERITY_COMPARE_FIELDS = ("feasible", "reason", "direction", "alpha", "delta", "backend", "ahat",
                           "bound", "price_bound", "override_bound", "measured_violation", "n_cal",
                           "n_eval", "envelope", "meta")


def _rubric_or_freeze(args, protocol, flags) -> dict:
    """Resolve rubric flags, and refuse a command line that argues with the protocol it was given.

    `CERTIFY_RUBRIC_FLAGS` and `SEVERITY_RUBRIC_FLAGS` are different lists, because the two gates take
    different numbers; the RULE is the same and lives here, so the ordinal surface cannot quietly grow a
    second, weaker copy of the freeze check. With no `--protocol`, every value is the flag's own default
    (the owner's name) or whatever the operator typed. With one, the protocol's rubric is the rule and a
    flag may only restate it: `load_protocol` has already refused a document whose rubric disagrees with
    `certificate.PUBLISHED_RUBRIC`, so the two agree by construction, and a flag carrying a different
    number is the operator asking for a measurement the freeze does not license. Silently letting it win
    would make the protocol a suggestion, which is the one thing a freeze is not (brief step 3). So the
    contradiction exits 2, naming BOTH values and which flag and which document said each.
    """
    out = {}
    for name, owner in flags:
        typed = getattr(args, name)
        if protocol is None:
            out[name] = owner if typed is None else typed
            continue
        stated = protocol.rubric[name]
        if typed is not None and typed != stated:
            raise UsageError(
                "--%s was given %r, but the protocol at %s states %r for `%s`: the frozen rubric is "
                "not overridable at the command line. Drop the flag to certify under the protocol, or "
                "re-freeze it (%s) under the number you mean -- the values disagree, so this run wrote "
                "nothing" % (name, typed, args.protocol, stated, name, protocol_digest(protocol)))
        out[name] = stated
    return out


def _certify_rubric(args, protocol) -> dict:
    """The set gate's five rubric values, under the freeze when one was given (see `_rubric_or_freeze`)."""
    return _rubric_or_freeze(args, protocol, CERTIFY_RUBRIC_FLAGS)


def cmd_severity(args) -> int:
    """Records -> the one-sided severity certificate (G3), and the exit code says which verdict.

    A verb of its own, not a `--measure` flag on `certify`, and the dispatch rule is the code: `certify`
    and `audit` each own a subparser whose flags are THAT gate's rubric (`certify` takes `--beta` and
    `--method` and `--groups`; `audit` takes `--gate` and `--delta` and `--records`). The ordinal gate has
    no automated subset to condition a risk on and no nonconformity to choose, so hanging it off `certify`
    would publish two flags that certify nothing and a `--groups` that silently does nothing -- the same
    misattribution this file keeps deleting.

    - **rc 0** -- the one-sided bound certified: `P(Y > ahat(X)) <= alpha` (or the over-call mirror) at the
      confidence the artefact states.
    - **rc 3** -- the run measured and refused: `no_gold_labels`, or `n_below_min` because no level in the
      family can be bounded by a sample this short. A result, printed and written, not a crash.
    - **rc 2** -- a records path that is not there or not a record, a budget that is not a probability, a
      `--delta` loose enough that `correction.joint_level` refuses to derive a level from it, a direction
      outside the closed set, a population carrying no `score` record or spanning two backends or two
      rubric widths, `--direction both_sides_sum` refused by its own measured curve, or a rubric flag that
      contradicts the `--protocol` document it was handed. A stored severity artefact is not in this list:
      this command reads records and writes an artefact, and no other command reads a severity artefact, so
      there is no typed path over which a wrong-shaped certificate can arrive -- its refusal is the rc-4 arm
      below, reached through `verify`, which is the door the publication declares.
    - **rc 4** -- two kinds, neither of them the operator's input: a table-declared severity artefact that
      is absent or unreadable or wrong-shaped (`PublishedArtefactUnavailable`, reached by `verify`), and an
      invariant of our own arithmetic (`ArithmeticError`, the search-and-scan disagreement).

    A refusal never exits 1, which is why `SeverityShapeMismatch` is a `ValueError` subclass and why the
    shape guards refuse a JSON string in a numeric slot by name instead of letting the comparison answer
    with a `TypeError` no arm maps. That sentence was false for four slots until the loader grew its own
    guards: a missing `envelope` answered `KeyError`, a string `n_cal` answered `TypeError` inside
    `summary()`'s `%d`, a list `backend` answered `TypeError: unhashable type` at the records lookup, and a
    top-level JSON array answered `AttributeError` on `.get` -- all four exit 1, and all four are now refused
    by name at 4 and walked through `main(["verify"])` by a test.
    """
    protocol = load_protocol(Path(args.protocol)) if args.protocol else None
    rubric = _rubric_or_freeze(args, protocol, SEVERITY_RUBRIC_FLAGS)
    if args.doc:
        # Checked before anything is read, certified or written, because this refusal's own sentence says
        # "Nothing was written" and its help says the same: the guard ran after `out.write_text`, so a
        # refused run left an artefact on disk while telling the operator it had not.
        #
        # The published document quotes the artefact at the table's own paths, so it may only be written by
        # the run that produces that artefact. Two reasons, one rule: a document naming the published paths
        # while carrying figures from somebody else's records is the misattribution this file keeps
        # deleting, and a path the operator typed would land inside a tracked file -- the machine-path
        # defect class `protocol._absolute` polices on the freeze's side.
        #
        # All three values the table row declares are compared, `direction` included: it is the element the
        # table exists to carry (see `report.SEVERITY_CERTS`), and a run at the published paths with
        # `--direction over` used to pass, rewriting the artefact as an over-call certificate above a
        # document whose own bullet still named `under` -- the pair disagreeing with the publication while
        # agreeing with each other, which is the one thing `verify`'s document arm cannot see.
        published_records, published_cert, published_direction = SEVERITY_CERTS[SEVERITY_LABEL]
        if (str(args.records) != published_records or str(args.out) != published_cert
                or args.direction != published_direction):
            raise UsageError(
                "--doc publishes %s, which quotes the ordinal artefact at its declared paths and rule, so "
                "it requires the run that produces them: --records %s --out %s --direction %s (this run "
                "named --records %s --out %s --direction %s). Nothing was written"
                % (args.doc, published_records, published_cert, published_direction,
                   args.records, args.out, args.direction))
    recs = _records_from(Path(args.records))
    cert = certify_severity(recs, direction=args.direction, **rubric)
    if protocol is not None:
        # The same stamp the set artefacts carry, so `meta` -- which `verify` compares whole -- says which
        # freeze this guarantee was measured under. Stamped here, at the command, and not inside the
        # certifier: a library default must stay unstamped for every other caller (R-200).
        cert = replace(cert, meta={**cert.meta, "protocol_digest": protocol_digest(protocol)})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert.to_json())
    print(cert.summary())
    for line in cert.envelope:
        print("  envelope:", line)
    if protocol is not None:
        print("  protocol: %s (version %d, frozen %s) digest %s"
              % (args.protocol, protocol.protocol_version, protocol.frozen_at,
                 protocol_digest(protocol)))
    if args.doc:
        doc = Path(args.doc)
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(render_severity(SEVERITY_LABEL, cert))
        print("wrote %s" % args.doc)
    print("wrote %s" % args.out)
    return EXIT_CERTIFIED if cert.feasible else EXIT_NOT_CERTIFIABLE


RUBRIC_FIELDS = ("alpha", "beta", "delta", "method", "seed")

# The digests the freeze names in advance, as (the comparison `verify` prints, the key inside the
# protocol's `corpus` block, the NAME of the module attribute holding the file). One list so the gate's
# corpus arm and the denominator that counts it cannot drift apart -- the failure R-168 keeps re-finding
# is a check list remembered twice. The third element is a name rather than a path on purpose: resolved
# when the check runs, so the row follows the constant's owner (and a lane that re-points `RECORDS` at a
# different file is seen by the digest arm, not only by the re-derivation).
CORPUS_DIGESTS = (("corpus.records_digest", "records_digest", "RECORDS"),
                  ("corpus.inventory_digest", "inventory_digest", "INVENTORY_JSON"))

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
    stamps = [ct.meta.get("protocol_digest") for ct in certs]
    same_protocol = stamps[0] == stamps[1]
    if not same_protocol:
        def shown(value):
            return "produced without a protocol" if value is None else value[:12]
        print("not comparable: the two certificates were frozen under different protocols (%s=%s, %s=%s);"
              " a before/after table here would compare two rules while claiming to compare two backends"
              % (labels[0], shown(stamps[0]), labels[1], shown(stamps[1])), file=sys.stderr)
        not_comparable = True
    rubrics = [_rubric(c) for c in certs]
    off = [f for f in RUBRIC_FIELDS if rubrics[0][f] != rubrics[1][f]]
    if off:
        print("comparable: NO -- the two sides disagree on %s" % ", ".join(
            "%s (%s=%r, %s=%r)" % (f, labels[0], rubrics[0][f], labels[1], rubrics[1][f])
            for f in off))
        not_comparable = True
    elif same_protocol:
        # Only a pair the protocol arm did not already refuse may hear "yes": two sentences from one
        # command, one of them an affirmative, is the misattribution this file keeps deleting.
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
    # The shape loader, not `json.loads`: on this lane the committed snapshot IS the inventory every
    # renderer indexes, so a document of the wrong shape used to reach `build_report` and raise a bare
    # `KeyError: 'digests'` at rc 1 -- the attribution repair's own defect class, arriving through the
    # contents. The absent case above stays a `UsageError`: that sentence is about a missing input, and
    # this site has a flag-free default the operator can supply, which rc 2's meaning covers.
    return load_published(cached, "report.INVENTORY_JSON", read_inventory_snapshot), FROM_SNAPSHOT


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
    """Write one of the two published documents, from the inputs and from nothing typed.

    `--full` selects the single technical report (`docs/REPORT.md`) instead of the results table
    (`docs/RESULTS.md`), and the DEFAULT stays the results table: `verify` byte-compares that file, so a
    command whose no-flag output changed would break the gate for every reader who never heard of the
    new flag. Both outputs go through the same `write_report`, so both create the directory they name.
    """
    records = load_records(Path(RECORDS))
    inv, _ = _inventory()
    full = getattr(args, "full", False)
    out = Path(args.out or (REPORT_MD if full else RESULTS))
    text = (_render_techreport_doc(inv, records) if full else
            build_report(inv, certify_all(records), {b: len(rs) for b, rs in records.items()}))
    write_report(text, out)
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
    # G3's document, rendered from the published severity artefact rather than from a fresh re-derivation
    # of the records: the certificate has its own re-derivation arm (which is what catches a stale
    # artefact), and this row's job is that the PROSE cannot drift from the artefact it quotes. The
    # artefact is read through `load_published`, so an absent or wrong-shaped document is exit 4 -- no
    # argument selected that path, the table did.
    (SEVERITY_MD, lambda inv, records: _render_severity_doc()),
    (RESPLIT_MD, lambda inv, records: _render_resplit_doc()),
    (SLICE_MD, lambda inv, records: _render_slice_doc()),
    # Plan D Task 4's single technical report. LAST in the table on purpose: the rc-4 rows in
    # `tests/test_cli.py` plant one absent or unreadable published artefact at a time and assert the
    # refusal names it, and a document that is read first would mask the ones behind it. Order is not a
    # formatting choice here -- it decides which failure a reader is told about.
    (REPORT_MD, lambda inv, records: _render_techreport_doc(inv, records)),
)


def _render_resplit_doc() -> str:
    """G1's second column, rendered out of the committed experiment file and nothing else.

    The rubric the prose prints is the one the artefact recorded, not the gate's copy: `verify` compares the
    two as rubric mismatches, so a document that quotes a budget the freeze never promised shows up as a
    disagreement the reader can name rather than a sentence that quietly drifted.
    """
    doc = load_published(RESPLIT_JSON, "report.RESPLIT_JSON", read_resplit)
    return render_resplit(doc, doc["rubric"])


def _render_slice_doc() -> str:
    """G4's slice run, rendered out of the committed artefact and nothing else.

    The document quotes the artefact's own budgets rather than the freeze's, for the same reason
    `_render_resplit_doc` does: the two are compared as rubric mismatches, so a prose sentence that drifts
    away from the artefact it describes stays attributable.
    """
    doc = load_published(SLICE_JSON, "report.SLICE_JSON", read_slices)
    return render_slices(doc)


def _render_techreport_doc(inv, records) -> str:
    """Plan D Task 4's single technical report, rendered out of the artefacts and nothing else.

    The freeze it describes is the one `cli.PROTOCOL_JSON` declares -- read through `load_published`, so
    an absent or unreadable protocol is the named refusal at exit 4 rather than a traceback -- and its
    own digest is printed in the document, so a reader can tell which freeze the report is a reading of.
    The two tables the report quotes rather than remembers are this file's: `PUBLISHED_DOCS` (resolved
    when the render runs, so a document added to the table appears in the document) and
    `EXIT_CODE_MEANINGS`.
    """
    protocol = load_published(PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol)
    return render_report(load_inputs(protocol, inv, records,
                                     tuple(path for path, _render in PUBLISHED_DOCS),
                                     EXIT_CODE_MEANINGS))


def _render_severity_doc() -> str:
    """What `docs/SEVERITY.md` should hold: the published ordinal artefact, rendered.

    One owner for the read, shared by `verify`'s byte comparison and by `autorate severity --doc`, so the
    document a command writes and the document the gate expects cannot be produced by two different
    readings of the same artefact.
    """
    label, _records, cert, _direction = published_severity()
    return render_severity(label, cert)


def _verify_protocol(args):
    """Resolve the freeze `verify` enforces: the flag selects a document, the tree supplies the default.

    Design G (Plan D R-200). `cmd_verify` reads the committed `protocol.json` whether or not `--protocol` was
    typed, so `verify` and `verify --protocol protocol.json` agree on a frozen tree and the flag's effect is
    proved by pointing it at a *different* document -- a mutated copy or an older freeze. The default is a
    table-declared published artefact, so its absence or an unreadable shape is a named refusal at exit 4 and
    never a usage error: nobody typed a path, so the checkout is what failed, not the operator. A path the
    operator did name is theirs: missing there is exit 2.
    """
    stated = getattr(args, "protocol", None)
    if stated:
        path = Path(stated)
        if not path.is_file():
            raise ValueError("--protocol %s does not exist" % path)
        doc = load_protocol(path)
    else:
        doc = load_published(PROTOCOL_JSON, "cli.PROTOCOL_JSON", load_protocol)
    return doc, protocol_digest(doc)


def _stamp(cert, digest):
    """The certificate as `verify` re-derives it under a freeze: the same numbers, plus the digest.

    The stamp happens here rather than inside the certifier for the reason R-200 records: `CERT_COMPARE_FIELDS`
    compares `meta` whole, so the artefacts and the re-derivation must gain the key in the same commit, and the
    certifier's own default behaviour has to stay unstamped for every other caller.
    """
    return replace(cert, meta={**cert.meta, "protocol_digest": digest})


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

    protocol, digest = _verify_protocol(args)
    # A frozen `Protocol`, not the JSON mapping: fields are attributes, only their contents are dicts.
    rubric = protocol.rubric
    mismatches = []

    def expect_rubric(label, actual, wanted):
        """Count the comparison like any other, but keep its failure on its own line.

        "This number does not reproduce" and "this number was produced under a rule nobody promised" get
        repaired differently -- re-export, or re-freeze -- so folding the second into the `DRIFT:` prefix
        would be a single word for two failures, which is what R-20/R-31 keep deleting here.
        """
        nonlocal total
        total += 1
        if actual == wanted:
            bump_checked()
        else:
            mismatches.append("%s: published %r, the frozen protocol says %r"
                              % (label, actual, wanted))

    def bump_checked():
        nonlocal checked
        checked += 1

    records = load_records(Path(RECORDS))
    for backend, path in sorted(CERTS.items()):
        stored = load_published(path, "report.CERTS", read_certificate)
        expect_rubric("cert %s.alpha" % backend, stored.alpha, rubric["alpha"])
        expect_rubric("cert %s.beta" % backend, stored.beta, rubric["beta"])
        expect_rubric("cert %s.delta" % backend, stored.delta, rubric["delta"])
        expect_rubric("cert %s.method" % backend, stored.method, rubric["method"])
        expect_rubric("cert %s.seed" % backend, stored.meta.get("seed"), rubric["seed"])
        # the real comparison: re-derive from the committed records at the rubric the freeze promised,
        # not the one the artefact happens to carry -- a protocol that disagrees has to be able to make
        # this arm red, which is what closes D-3's `method` and `grid` holes.
        fresh = _stamp(certify_choice(records.get(backend, []), alpha=rubric["alpha"],
                                      beta=rubric["beta"], delta=rubric["delta"],
                                      seed=rubric["seed"], method=rubric["method"],
                                      grid=tuple(rubric["grid"])), digest)
        for field in CERT_COMPARE_FIELDS:
            expect("cert %s.%s" % (backend, field), getattr(fresh, field),
                   getattr(stored, field))
        expect("cert %s.summary" % backend, fresh.summary(), stored.summary())

    # G1's published artefacts re-derive the same way, from `report.py`'s table, because that is the
    # file that also prints them -- a second list of artefacts inside the gate could disagree with the
    # list the document is built from. The field list is handed in rather than copied for the same
    # reason: `CERT_COMPARE_FIELDS` has one owner, and it is this file.
    rederive_massive(expect, CERT_COMPARE_FIELDS, rubric=rubric,
                     stamp=lambda cert: _stamp(cert, digest))

    # G3's artefact, from its own table and its own field list: a different shape, read by a different
    # loader, with the direction declared by the publication instead of read back off the bytes. Same
    # freeze, same stamp, both lanes -- the records file is committed, so the corpus-less run re-derives
    # the ordinal guarantee exactly as the corpus-present one does.
    rederive_severity(expect, expect_rubric, SEVERITY_COMPARE_FIELDS, SEVERITY_RUBRIC_FIELDS,
                      rubric=rubric, stamp=lambda cert: _stamp(cert, digest))
    # G1's empirical violation-rate column. The experiment itself is six minutes of re-splitting and belongs
    # to `tools/resplit_experiment.py`; the gate checks what the committed artefact says about itself, and
    # that the rubric it recorded is the rubric this freeze promised.
    rederive_resplit(expect, expect_rubric, rubric)
    # G4's worst-slice refusal. The run costs seconds rather than minutes, so this arm recomputes the
    # certification from the three committed record files and compares the published fields, which makes a
    # stale slice artefact a drift with a field name on it instead of a sentence in a document.
    rederive_slices(expect, expect_rubric, rubric)

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

    corpus = protocol.corpus
    # The two checks in this gate that are not fixed points. Everything else asks whether the published
    # files reproduce from the inputs lying beside them, so a records file swapped wholesale with its
    # certificates regenerated in the same commit satisfies all of them (spec 2 D-12). These compare
    # against bytes the freeze named in advance, which is why they run in BOTH lanes.
    for label, key, owner in CORPUS_DIGESTS:
        expect(label, file_digest(globals()[owner]), corpus[key])

    for claim in protocol.claims:
        print("claim %s %s %s" % (claim["id"], claim["status"], claim["criterion"]))
    print("protocol: %s %s (frozen %s)" % (getattr(args, "protocol", None) or PROTOCOL_JSON,
                                           digest[:12], protocol.frozen_at))
    print("inventory source: %s" % source)
    print("disclosure: %s; the frozen protocol rubric was enforced" % disclosure)
    print("re-derived %d /%d values" % (checked, total))
    for f in failures:
        print("DRIFT:", f, file=sys.stderr)
    for f in mismatches:
        print("RUBRIC MISMATCH:", f, file=sys.stderr)
    return EXIT_DRIFT if (failures or mismatches) else 0


def _frozen_at_in_place(out: Path) -> str:
    """The date the document at `out` already states, or the refusal that says one is needed.

    This is the command's ONLY fall-back, and it is what makes the freeze checkable in the one
    environment that has neither a clock to trust nor a `.git` to read: `autorate protocol --out
    protocol.json` re-emits the committed bytes inside a `git archive` export (amendment §1 / R-188).
    The first freeze therefore stays a deliberate act -- a date this tool computed would make every
    re-emission a different file, which is the drift check's own death.

    The read is deliberately lenient (`json`, not `load_protocol`): the file is being ASKED what date it
    states, not validated. What gets written is validated on the way out, by `emit_protocol` calling the
    same `protocol.require_frozen_at` the loader uses, so the two arms cannot disagree about the format.
    """
    if not out.exists():
        raise UsageError(
            "no --frozen-at was given and %s holds nothing, so there is no stated date to reuse. The "
            "freeze date is provenance, never a computed value: pass --frozen-at YYYY-MM-DD, or point "
            "--out at the document whose date you are re-emitting" % out)
    try:
        stated = json.loads(out.read_text(encoding="utf-8")).get("frozen_at")
    except ValueError as exc:
        raise UsageError(
            "no --frozen-at was given and %s could not be read for one (%s): pass --frozen-at "
            "YYYY-MM-DD" % (out, exc)) from exc
    if not isinstance(stated, str) or not stated:
        raise UsageError(
            "no --frozen-at was given and %s states no `frozen_at` to reuse; pass --frozen-at "
            "YYYY-MM-DD" % out)
    return stated


def cmd_protocol(args) -> int:
    """Write the frozen protocol document -- from the committed inputs, so its bytes are reproducible.

    Every input is a file this checkout publishes: the inventory snapshot at `report.INVENTORY_JSON`,
    the records at `report.RECORDS`, the MASSIVE pin through `inventory.massive_pin`, and the published
    certificates. The corpus is never scanned and the clock is never read, which is what makes the same
    command produce the same bytes in the corpus-present lane, the corpus-absent lane and a clean export
    -- the three places the drift check has to hold. It is emitted by a command and never typed
    (ruling D-b): a protocol with a typo in `min_cal` would freeze a floor nobody implemented.

    The rubric values come from `certificate.PUBLISHED_RUBRIC`, one owner for the whole block (R-187 /
    R-199), and the printed lines include the `rubric_scope` sentence, because a command whose output
    reads as though one mapping governed every certifier in the tree is the misreading this field
    exists to prevent.
    """
    out = Path(args.out)
    frozen_at = args.frozen_at or _frozen_at_in_place(out)
    inv = load_published(Path(INVENTORY_JSON), "report.INVENTORY_JSON", read_inventory_snapshot)
    doc = emit_protocol(inv, file_digest(Path(RECORDS)), frozen_at)
    write_protocol(doc, out)

    rubric = dict(doc["rubric"])
    grid = rubric.pop("grid")
    g1 = next(row for row in doc["claims"] if row["id"] == "G1")
    print("wrote %s" % out)
    print("protocol_version %d, frozen_at %s (%s), digest %s"
          % (doc["protocol_version"], doc["frozen_at"],
             "from --frozen-at" if args.frozen_at else "reused from %s" % out,
             protocol_digest(doc)))
    print("  rubric: %s, grid=%d points (%.2f..%.2f)"
          % (", ".join("%s=%s" % kv for kv in rubric.items()), len(grid), grid[0], grid[-1]))
    print("  record contract: shape %d, primitives %s"
          % (doc["record_contract"]["shape_version"], ", ".join(doc["record_contract"]["primitives"])))
    print("  corpus: records %s, inventory %s, %d source labels"
          % (doc["corpus"]["records_digest"], doc["corpus"]["inventory_digest"],
             len(doc["corpus"]["source_labels"])))
    for row in doc["claims"]:
        print("  claim %s: %s" % (row["id"], row["status"]))
    print("  G1: %d of %d published certificates certify, refusal reasons: %s"
          % (g1["certified_tasks"], g1["published_certificates"],
             ", ".join(g1["refusal_reasons"]) or "none"))
    print("  known limits: %d envelope lines, read from the published certificates"
          % len(doc["known_limits"]))
    print("  scope: %s" % doc["rubric_scope"])
    return 0


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
    c.add_argument("--delta", type=float, default=DELTA)
    c.add_argument("--seed", type=int, default=SEED)
    c.add_argument("--method", default=METHOD, choices=("aps", "lac"),
                   help="the nonconformity that sizes the set; lac is the comparison arm")
    c.add_argument("--protocol", default=None,
                   help="the frozen protocol document to certify under: its digest is written into "
                        "meta, its rubric is the rule, and a rubric flag that contradicts it exits 2 "
                        "naming both values. There is NO default -- `certify` never reads "
                        "`protocol.json` unless this flag names it, because the artefacts published "
                        "before the freeze carry no stamp and `verify` compares `meta` whole (R-200).")
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

    s = sub.add_parser(
        "severity", help="G3: records -> the one-sided ordinal severity certificate "
                         "(P(Y > ahat(X)) <= alpha, or the over-call mirror) -- the statement the "
                         "multiclass set gates cannot make")
    s.add_argument("records", nargs="?", default=SEVERITY_RECORDS,
                   help="the ordinal records to certify (default: the committed ordinal population, %s)"
                        % SEVERITY_RECORDS)
    s.add_argument("--direction", required=True, choices=DIRECTIONS,
                   help="which one-sided family to certify. `under` floors the report at "
                        "max(modal, ahat) and bounds P(Y > ahat(X)); `over` clips it at "
                        "min(modal, ahat) and bounds P(Y < ahat(X)); `both_sides_sum` is spec 6.1's naive "
                        "weighted loss, in the closed set ONLY so the monotonicity precondition has "
                        "something to refuse -- it exits 2 naming the curve it measured. No default: the "
                        "direction is which guarantee is being claimed, and the published ordinal "
                        "artefact's is declared by report.SEVERITY_CERTS, not invented here.")
    s.add_argument("--alpha", type=float, default=ALPHA,
                   help="the RISK target, not a confidence: the bound on P(Y > ahat(X)) is certified "
                        "against it (default %s, the published rubric's owner)" % ALPHA)
    s.add_argument("--delta", type=float, default=DELTA,
                   help="the level each published bound is tested at (default %s); the joint level is "
                        "derived from it by correction.joint_level, never restated here" % DELTA)
    s.add_argument("--seed", type=int, default=SEED,
                   help="the split the two halves are cut on (default %s, the published split)" % SEED)
    s.add_argument("--protocol", default=None,
                   help="the frozen protocol document to certify under: its digest is written into "
                        "meta, its rubric is the rule, and a rubric flag that contradicts it exits 2 "
                        "naming both values. There is NO default -- `severity` never reads "
                        "`protocol.json` unless this flag names it, because `verify` compares `meta` "
                        "whole and an unstamped artefact is a different statement (R-200).")
    s.add_argument("--out", default="cert.json",
                   help="where to write the certificate (default cert.json, which is gitignored; the "
                        "published artefact is written by naming report.SEVERITY_CERTS's path)")
    s.add_argument("--doc", default=None,
                   help="also publish the document quoting this artefact's figures "
                        "(docs/SEVERITY.md). Only allowed for the run that produces the published "
                        "artefact -- --records, --out and --direction must all name what "
                        "report.SEVERITY_CERTS declares, or the document would quote published paths and a "
                        "published rule over somebody else's numbers. Exits 2 otherwise, writing nothing: "
                        "the check runs before any file is opened.")
    s.set_defaults(fn=cmd_severity)

    m = sub.add_parser("compare", help="two certificates side by side")
    m.add_argument("files", nargs=2)
    m.set_defaults(fn=cmd_compare)

    g = sub.add_parser("gate", help="apply a certificate to records")
    g.add_argument("records")
    g.add_argument("--cert", required=True)
    g.add_argument("--backend")
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(fn=cmd_gate)

    r = sub.add_parser("report", help="write the published report from the inputs: docs/RESULTS.md, or "
                                     "the single technical report with --full")
    r.add_argument("--out", default=None,
                   help="where to write (default docs/RESULTS.md, or docs/REPORT.md with --full)")
    r.add_argument("--full", action="store_true",
                   help="write `docs/REPORT.md` -- one document that assembles the certificate shape, the "
                        "mechanism, the five gates as the freeze states them, every refusal, the envelope "
                        "and known limits, reproduction and the cited related work. Like every published "
                        "document it is generated from the artefacts, carries no timestamp and no machine "
                        "path, and `verify` byte-compares it; the default output is unchanged, because "
                        "`docs/RESULTS.md` is byte-compared too.")
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

    f = sub.add_parser(
        "protocol", help="emit the frozen protocol document (protocol.json) from the tree's own "
                         "constants, digests and published certificates")
    f.add_argument("--out", default=str(PROTOCOL_JSON),
                   help="where to write it (default %s)" % PROTOCOL_JSON)
    f.add_argument("--frozen-at", dest="frozen_at", default=None,
                   help="the freeze date, YYYY-MM-DD: provenance the operator states. Required unless "
                        "--out already holds a document whose own date is reused; never read from a "
                        "clock or from git, because a computed date makes the re-emission the drift "
                        "check depends on impossible")
    f.set_defaults(fn=cmd_protocol)

    v = sub.add_parser("verify", help="re-derive every published number")
    v.add_argument("--protocol", default=None,
                   help="which freeze to enforce (default %s, read as a published artefact)"
                        % PROTOCOL_JSON)
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
        # OSError: an input path is not there. ValueError: bytes this build cannot read. Both are "the
        # input this command was handed is wrong", and both used to escape as a traceback with rc 1,
        # outside the documented 0/2/3/4 contract. A failure on a path a publication table declares
        # normally belongs to `PublishedArtefactUnavailable` above, at 4 -- with one exception held by
        # ruling rather than oversight: `data/records_feishu.jsonl` is table-declared and still lands
        # here, because every command that reads it does so through a default the operator could name
        # and repair (`verify` and `report` with no flag, and `audit --records`), which is what 2 means.
        # README states that residual, and the rows keeping it at 2 are in `tests/test_cli.py`.
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
