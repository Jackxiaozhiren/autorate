"""Offline data inventory: which labelled per-case decision corpus exists, and whether n bounds.

Integrity is owned by upstream's own model-free audit; this module records its verdict
and transcribes -- without redefining -- the digests upstream pins in its own
`SOURCE.json`. Two refusals are the point of the module: publishing a corpus whose audit
failed, and quoting a bound that the sample size cannot support.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .records import SUM_TOL
# R-55: the unreadable-archive-line rule has ONE owner, and it is the reader. Importing it here
# is the point of the task -- a second `try/except (ValueError, KeyError, TypeError)` in this
# module would be a second owner of the same rule, and two owners drift invisibly until one
# guard names a line the other one crashes on.
from .readers.feishu_zh import (MALFORMED_LINE, PROBS_NOT_CLOSING, choice_probabilities,
                                error_label, mode_bucket_key, parse_archive_line,
                                quarantine_line_entry, unreadable_mode_reason)
# The interval arithmetic has one home (tails.py); this module reads it and publishes it,
# so the inventory's feasibility verdict and the certificate's interval cannot drift apart.
from .tails import bound_width, n_feasible

MODES = ("choice", "four_noul")
BACKENDS = ("laya", "jev")
# The keys this module's own pass indexes straight off a line, required on the `ok` branch only --
# which is where the reader indexes them too. Each caller names what IT reads (the reader asks for
# none at parse time), but both must ask AFTER the reader's first question, `status == "ok"`, or one
# defective line is `malformed_line` to this pass and `lines_dropped_not_ok` to that one, and the two
# ledgers the artefact prints beside each other disagree (R-75, and R-80 for the order itself).
LINE_KEYS = ("mode", "id", "repeat")
# How many offending lines the artefact names. The counts are never bounded -- a truncated list
# is a disclosure limit, not a loss of the count, and the gap sentence says which is which.
UNREADABLE_DISCLOSURE_LIMIT = 10


def _interpreter_label(path: str) -> str:
    """Name the audit interpreter by its tail, not by an absolute path."""
    if path == sys.executable:
        return "sys.executable"
    return "/".join(Path(path).parts[-4:])


def corpus_label(root: Path) -> str:
    """A repo-relative label for where the corpus lives, never an absolute path.

    An absolute `/Users/<name>/...` literal in a committed artefact passes every local
    gate, survives a clean-clone re-run on the same disk, and only shows up in the one
    environment nobody can see. A checkout-relative label carries the same information
    and is portable. tests/test_cli.py guards the class.
    """
    root = Path(root).resolve()
    return "/".join(root.parts[-4:])


def _audit_python(root: Path) -> str:
    """Interpreter for upstream's audit, derived from the corpus root where possible.

    No hardcoded absolute path: an absolute literal passes every local gate and only
    breaks in an environment nobody can see.
    """
    override = os.environ.get("AUTORATE_AUDIT_PYTHON")
    if override:
        return override
    # <laya checkout>/research/benchmarks/feishu_zh  ->  <laya checkout>/.venv/bin/python.
    # Walk up to three levels and take the nearest, rather than indexing parents[2]:
    # a shallower --root (or a test pointing at a nonexistent one) raised IndexError out
    # of the CLI, which is rc 1 -- outside the documented exit-code contract.
    for parent in (root, *list(root.parents)[:3]):
        venv = parent / ".venv" / "bin" / "python"
        if venv.exists():
            return str(venv.resolve())
    return sys.executable


def audit_command(root: Path) -> tuple[list[str], dict]:
    root = Path(root)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return [_audit_python(root), "audit.py"], env


def _scan_jsonl(path: Path) -> tuple:
    """One pass over a backend file, bucketed by `mode`, with every other line counted or named.

    Each backend file holds both modes (192 choice + 192 four_noul = 384 lines), so
    counting lines per file and labelling them per mode is the same collapse the
    reader has to avoid: lines are not records.

    R-55: the unreadable-line rule is the reader's, not a copy of it. A second `try/except`
    set for one rule drifts, and the drift is invisible until a line shape passes one guard and
    crashes the other -- which is how one unparseable line came to exit 1 (outside the published
    0/2/3/4 contract) here while the reader carried on. Every line this pass reads therefore
    ends in exactly one of three places: `by_mode`, `outside` with the reader's reason, or the
    refused count for a line the reader declines before reading anything from it.

    R-75 and R-80: and the ORDER is part of the rule, asked in the reader's order.

    1. Can the line be parsed at all? No -> `outside`, `malformed_line`.
    2. Is `status` `ok`? No -> `lines_refused_not_ok`, and the `mode` is NEVER consulted. The
       reader's own first line is `if obj.get("status") != "ok": return []`, so a refused line that
       this pass named was a line filed in the quarantine ledger by one pass and absent from it by
       the other -- review M2's rows 3-5, which the first fix left open (`mode: "ranked"` with no
       `status` measured `{'ranked': 1}` here and `{}` for the reader, and an absent mode published
       under the literal key `"None"`).
    3. Does the line carry the keys this pass indexes blind (`LINE_KEYS`)? No -> `outside`,
       `malformed_line` -- on this branch only, because it is the only branch where the reader
       reads those fields at all.
    4. Is the `mode` one this contract buckets? No -> `outside`, named by the reader's
       `unreadable_mode_reason`, keyed by the reader's `mode_bucket_key`.
    5. For a `choice` line, does the published vector close within `SUM_TOL`? No -> the reader
       quarantines it under that reason and keeps no record, so this pass must neither count it in
       `by_mode` nor invent a second reason for it (R-80's shape (b), which is the shipped corpus's
       own single line): it goes to `outside` with the reader's own `PROBS_NOT_CLOSING`, and the
       probabilities stay disclosed as detail in `unclosed`.
    """
    by_mode: dict = {}
    ids: set = set()
    repeats: set = set()
    unclosed: list = []
    outside: list = []
    refused_not_ok = 0
    lines_read = 0
    backend = path.parent.name
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        lines_read += 1              # before parsing: an unread line is still a line seen
        obj, error = parse_archive_line(line)
        if error:
            outside.append(quarantine_line_entry(obj, backend, line_no, MALFORMED_LINE, error))
            continue
        if obj.get("status") != "ok":
            # Counted, not named: the reader drops it here and never reads its `mode`, so neither
            # pass may file it in a quarantine ledger. It still stands for an archived line of
            # this backend, which is why it has a counter rather than vanishing.
            refused_not_ok += 1
            continue
        # The reader indexes these fields next, on this branch only; asking for them the same way
        # the reader does is what keeps ONE failure string for one defective line.
        obj, error = parse_archive_line(line, LINE_KEYS)
        if error:
            outside.append(quarantine_line_entry(obj, backend, line_no, MALFORMED_LINE, error))
            continue
        mode = obj.get("mode")
        if mode not in MODES:
            outside.append(quarantine_line_entry(obj, backend, line_no,
                                                 unreadable_mode_reason(mode)))
            continue
        if mode == "choice":
            # The same accessor the record builder uses, so the two cannot disagree about which
            # probability vector a line published -- and, unlike the builder, it never raises.
            _, probs, failure = choice_probabilities(obj)
            if failure is not None:
                outside.append(quarantine_line_entry(obj, backend, line_no, MALFORMED_LINE,
                                                     error_label(failure)))
                continue
            if abs(sum(probs) - 1.0) > SUM_TOL:
                # The tolerance has one owner (records.SUM_TOL) and the reader quarantines the
                # same lines under the same words (`PROBS_NOT_CLOSING`), so the two published
                # ledgers cannot disagree about what the corpus contains -- and the line is out of
                # the per-mode counts, because the reader keeps no record for it.
                unclosed.append({"id": obj["id"], "backend": backend,
                                 "repeat": obj["repeat"], "probs": list(probs),
                                 "probs_sum": round(sum(probs), 6)})
                outside.append(quarantine_line_entry(obj, backend, line_no, PROBS_NOT_CLOSING))
                continue
        by_mode[mode] = by_mode.get(mode, 0) + 1
        # A line missing a key may still be counted, and this pass must not invent a crash for it:
        # `obj["id"]` here was the rc-1 shape the 0/2/3/4 contract forbids.
        if "id" in obj:
            ids.add(obj["id"])
        if "repeat" in obj:
            repeats.add(obj["repeat"])
    return by_mode, ids, sorted(repeats), unclosed, outside, refused_not_ok, lines_read


def assert_line_conservation(lines_read: int, lines_by_mode: dict, lines_quarantined_only: dict,
                             lines_malformed: int, lines_malformed_by_backend: dict,
                             lines_refused_not_ok: int) -> None:
    """lines read = lines counted per mode + lines named outside those counts + refused lines.

    Asserted by inventory itself rather than only by a test, for the reason Task 1 gave the
    reader: a future branch that drops a line without a counter must raise, not shrink the
    corpus quietly. Two refusals, because two failures let that happen: buckets that do not
    cover every line read, and one quantity published under names that disagree -- the total,
    the bucket it belongs to and the per-backend split of the same lines.

    R-80 adds the third place a line can legitimately land: refused on its own `status`, before
    either pass reads a `mode` from it. It is counted, never named, because naming it is what put
    one line in the scanner's quarantine ledger and in nobody's.
    """
    bucketed = sum(lines_by_mode.values())
    named = sum(lines_quarantined_only.values())
    if bucketed + named + lines_refused_not_ok != lines_read:
        raise ArithmeticError(
            "inventory line accounting does not conserve: %d read, %d accounted (%d counted per "
            "mode, %d named outside the mode counts, %d refused for their `status`)" % (
                lines_read, bucketed + named + lines_refused_not_ok, bucketed, named,
                lines_refused_not_ok))
    malformed_total = lines_quarantined_only.get(MALFORMED_LINE, 0)
    if lines_malformed != malformed_total or sum(lines_malformed_by_backend.values()) != malformed_total:
        raise ArithmeticError(
            "inventory line accounting does not match its own buckets: %d malformed published, "
            "%d under `%s`, %d across backends -- one quantity may not have three owners" % (
                lines_malformed, malformed_total, MALFORMED_LINE,
                sum(lines_malformed_by_backend.values())))


def corpus_digests(root: Path) -> list:
    """The digests upstream pins in its own `SOURCE.json`, recomputed against the files.

    Upstream owns the expected values and the hashing definition (raw bytes, sha256);
    this only transcribes them next to what the bytes actually hash to, so a fixture
    that changed under the archive is visible rather than quoted from a stale record.
    """
    source = Path(root) / "SOURCE.json"
    if not source.exists():
        return []
    entries = json.loads(source.read_text()).get("files", [])
    out = []
    for e in entries:
        f = Path(root) / e["path"]
        actual = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
        out.append({"path": e["path"], "expected": e["sha256"], "actual": actual,
                    "match": actual == e["sha256"]})
    return out


def inventory(root: Path) -> dict:
    # One owner for both measurements: the reader decides what a record's gold may be and
    # keeps its own line counters, so the inventory transcribes instead of re-deriving.
    from .readers.feishu_zh import per_ask_gold, read_archive

    root = Path(root)
    ask_gold_measurement = per_ask_gold(root)
    manifest = json.loads((root / "data" / "manifest.json").read_text())
    per_mode: dict = {}
    ids: set = set()
    repeats: list = []
    unclosed: list = []
    outside: list = []
    lines_scanned = 0
    lines_refused = 0
    for backend in BACKENDS:
        path = root / "results" / "v1" / backend / "raw.jsonl"
        (by_mode, this_ids, this_reps, this_unclosed, this_outside, this_refused,
         this_lines) = _scan_jsonl(path)
        unclosed += this_unclosed
        outside += this_outside
        lines_refused += this_refused
        lines_scanned += this_lines
        for mode in MODES:
            # Separator is "/", not "|": these keys are rendered into a markdown table,
            # and a pipe inside a cell silently adds a column and breaks the table.
            per_mode["%s/%s" % (mode, backend)] = by_mode.get(mode, 0)
        if backend == "laya":  # uniqueness is asserted on one backend, not summed
            ids |= this_ids
            repeats = this_reps
    # Every count of the lines outside the per-mode table is DERIVED from that one list, so no
    # quantity gets a second counter (Task 1's review parked exactly that duplication). The bucket
    # keys come from the reader's own `mode_bucket_key` (R-81), and the reasons come from the
    # reader too -- `malformed_line` plus its failure string for a line neither pass can read,
    # `unreadable_mode_reason` for a mode this contract cannot bucket, and `PROBS_NOT_CLOSING` for
    # a `choice` line whose published vector does not close. That is what lets a test compare the
    # two dicts as data instead of comparing prose, and it is the agreement R-80 had to create:
    # before it, the shipped corpus's one unclosing line was counted per mode by this pass and
    # quarantined by the reader, so the published pair read `{}` beside `{'choice': 1}`.
    quarantined_only: dict = {}
    malformed_by_backend: dict = {}
    lines_malformed = 0
    for entry in outside:
        unreadable = entry["reason"] == MALFORMED_LINE
        key = MALFORMED_LINE if unreadable else mode_bucket_key(entry["mode"])
        quarantined_only[key] = quarantined_only.get(key, 0) + 1
        if unreadable:
            lines_malformed += 1
            malformed_by_backend[entry["backend"]] = \
                malformed_by_backend.get(entry["backend"], 0) + 1
    # Both backends publish a count even when nobody was hurt: an absent key is
    # indistinguishable from a backend that was never scanned.
    malformed_by_backend = {b: malformed_by_backend.get(b, 0) for b in BACKENDS}
    reader_stats: dict = {}
    try:
        read_archive(root, stats=reader_stats)
    except OSError as exc:
        reader_stats = {"error": str(exc)}
    if "lines_read" in reader_stats and reader_stats["lines_read"] != lines_scanned:
        # The two passes read the same files, so a disagreement here is this module losing a
        # line, not the corpus being odd -- and a corpus whose counters disagree is precisely
        # the drift this task was queued for.
        raise ArithmeticError(
            "inventory counted %d archive lines where the reader counted %d for the same files; "
            "the two passes must read the same corpus before either count means anything" % (
                lines_scanned, reader_stats["lines_read"]))
    assert_line_conservation(lines_read=lines_scanned, lines_by_mode=per_mode,
                             lines_quarantined_only=quarantined_only,
                             lines_malformed=lines_malformed,
                             lines_malformed_by_backend=malformed_by_backend,
                             lines_refused_not_ok=lines_refused)
    cmd, env = audit_command(root)
    if not massive_pin():
        # An artefact written in this checkout without its own pin list would publish MASSIVE rows
        # that say "not opened" while the corpus they describe is pinned -- the absence is a broken
        # tree, not a finding about the corpus, and rc 0 with a refusal sentence in a table cell is
        # how it used to leave. `corpus_options` still renders the absent-pin case (a library outside
        # this repository has no pin), but the command that writes the published artefact refuses.
        raise ArithmeticError(
            "%s is missing or unreadable from this checkout, so the MASSIVE rows have no owner"
            % MASSIVE_PIN_LABEL)
    audit = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), env=env)
    return {
        "source": corpus_label(root),
        "lines_by_mode_backend": dict(sorted(per_mode.items())),
        # Counted and named, never silently dropped: the archive lines the per-mode table above
        # does not cover. `lines_outside_mode_counts` is bounded for disclosure, the counts are
        # not -- an operator reading this artefact is owed the total as well as the samples.
        "lines_malformed": lines_malformed,
        "lines_malformed_by_backend": dict(sorted(malformed_by_backend.items())),
        "lines_quarantined_only": dict(sorted(quarantined_only.items())),
        # R-80: a line refused on its own `status` is counted here and named nowhere, exactly as
        # the reader drops it before reading its `mode`. It is published rather than left inside
        # the conservation identity, because the per-mode table above no longer covers it and a
        # reader of the artefact is owed the line that went missing from that total.
        "lines_refused_not_ok": lines_refused,
        "lines_outside_mode_counts": outside[:UNREADABLE_DISCLOSURE_LIMIT],
        "unique_ids": len(ids),
        "repeats": repeats,
        "families": sorted(manifest.get("families", {})),
        "label_counts": dict(manifest.get("labels", {})),
        "provenance": manifest.get("provenance", ""),
        "upstream_audit_rc": audit.returncode,
        "upstream_audit_stdout_tail": audit.stdout[-400:],
        "upstream_audit_stderr_tail": audit.stderr[-400:],
        "audit_interpreter": _interpreter_label(cmd[0]),
        # What upstream's own manifest DECLARES, with no fallback to our recount: the
        # old `min_calibration_n` published the corpus's total case count under a
        # floor-shaped name and substituted `len(ids)` when the manifest said nothing.
        # The calibration half is the certifier's (`n_cal_cases`), and the floor is
        # `certify_choice.MIN_CAL`; neither quantity is owned here.
        "manifest_declared_cases": manifest.get("cases"),
        "probs_not_closing": unclosed,
        "sum_tolerance": SUM_TOL,
        "per_ask_gold": ask_gold_measurement,
        "reader_lines_by_mode": {k: v for k, v in sorted(
            reader_stats.get("lines_by_mode", {}).items())},
        "reader_quarantined": len(reader_stats.get("quarantined", [])),
        # R-75 (review M1): the reader's own dispositions, published rather than derived by
        # subtraction. `reader_quarantined` counts lines it quarantined; a line it REFUSED because
        # `status != "ok"` and a line it FILTERED by language are neither, and the markdown used to
        # call the difference between "lines present" and "lines kept" a quarantine -- so an honest
        # artefact needed these three numbers of its own.
        "reader_lines_malformed": reader_stats.get("lines_malformed"),
        "reader_lines_dropped_not_ok": reader_stats.get("lines_dropped_not_ok"),
        "reader_lines_filtered": reader_stats.get("lines_filtered"),
        "reader_lines_read": reader_stats.get("lines_read"),
        "reader_lines_quarantined_only": reader_stats.get("lines_quarantined_only"),
        "digests": corpus_digests(root),
        "corpus_options": corpus_options(len(ids)),
        "gaps": [
            "research/results/eval_english_51_languages.json: per-case records omitted; "
            "regenerate with research/eval/laya_eval.py --langs all --out <path>",
            "mteb/amazon_massive_intent is not in the local HF dataset cache",
            "the archived corpus carries no randomisation draw (u), so APS ties resolve to 0 here",
        ] + ([] if ask_gold_measurement["asks_with_gold"] else [
            "the four `noul` asks carry no per-ask ground truth anywhere in the fixtures "
            "(asks %s are not among the case keys %s); only the composite 4-way label is "
            "supervised, so a noul certificate on this corpus would certify invented labels"
            % (ask_gold_measurement["asks"], ask_gold_measurement["case_keys"]),
        ]) + ([] if not unclosed else [
            "%d archived choice line(s) publish probabilities that do not close to 1 within "
            "%g and are quarantined by the reader rather than absorbed by a wider tolerance: %s"
            % (len(unclosed), SUM_TOL,
               ", ".join("%s/%s/repeat=%s (sum %.4f)" % (u["backend"], u["id"], u["repeat"], u["probs_sum"])
                         for u in unclosed)),
        ]) + ([] if not outside else [
            # Named here as well as in the list, because a reader of the markdown is owed the
            # total: the list below is bounded for disclosure, the count is not. The second half
            # is no longer "whose `mode` this contract cannot bucket" -- R-80 moved the shipped
            # corpus's unclosing `choice` line in here, and its mode IS bucketable, so the split
            # is by disposition: unreadable, or readable and refused by the line rule the reader
            # owns. The reason each line carries is in the list.
            "%d archive line(s) sit outside the per-mode counts (%d unreadable, %d readable but "
            "refused by the line rule the reader owns); the first %d are named in "
            "`lines_outside_mode_counts` with backend, line number and reason: %s"
            % (len(outside), lines_malformed, len(outside) - lines_malformed,
               min(len(outside), UNREADABLE_DISCLOSURE_LIMIT),
               ", ".join("%s line %d id=%s (%s)" % (e["backend"], e["line_no"], e["id"],
                                                    e["reason"])
                         for e in outside[:UNREADABLE_DISCLOSURE_LIMIT])),
        ]) + ([] if not lines_refused else [
            # Counted, not named (R-80): the reader declines these before it reads a `mode`, so
            # neither pass may file them in a quarantine ledger, and the per-mode table does not
            # cover them either. Without this clause the line totals of the table above silently
            # stop adding up.
            "%d archive line(s) carry no `status` of `ok`: this pass counts them in "
            "`lines_refused_not_ok` rather than in the per-mode table, mirroring the reader, "
            "which refuses a line before it reads its `mode` (its own count for the same lines "
            "is `reader_lines_dropped_not_ok`)" % lines_refused,
        ]),
    }


MASSIVE_PIN_PATH = Path(__file__).resolve().parents[2] / "data" / "massive_provenance.json"
# Named as the artefact reads it, because the published basis sentence has to point a reader at
# the file that owns the number rather than at a constant in a module they cannot open.
MASSIVE_PIN_LABEL = "data/massive_provenance.json"


def _is_digest(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value)


def _pin_entry_label(index: int, entry) -> str:
    """Names one `files[]` entry the way an operator can act on it: position and pinned path."""
    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
        return "entry %d (`%s`)" % (index, entry["path"])
    return "entry %d" % index


def _require_pin_entry(index: int, entry) -> None:
    """R-82 (review MA-1): a pin ENTRY that is the wrong shape is a refusal, never a crash.

    `massive_pin` used to assume `json.loads` had returned a dict and that every `files[]` element
    was a dict carrying `rows` and `bytes`, because the sums below indexed them that way. Measured at
    `5ec8639`: a pin of `null` raised `AttributeError` and an entry stripped of `rows` raised
    `KeyError`, and neither class is in `main`'s mapping, so `autorate snapshot` died with a traceback
    and rc 1 -- outside the published 0/2/3/4 contract, on the tracked file M5 was filed for. This is
    the fetcher's own discipline (`tools/fetch_massive.require_manifest` checks entries before
    indexing them) applied to the loader that publishes the numbers.

    `sha256` is policed by `_is_digest` because a digest is the only field of an entry that a reader
    can check against bytes: a truncated or non-hex one is not a shard that was "not hashed yet", it
    is a pin that cannot mean anything. The message names the entry -- the committed list holds 51 of
    them, and an operator has to be able to find the wrong line.
    """
    if not isinstance(entry, dict):
        raise ArithmeticError(
            "%s %s is a JSON %s, not an object; every entry in its `files` list must carry `path`, "
            "`rows`, `bytes` and `sha256`" % (MASSIVE_PIN_LABEL, _pin_entry_label(index, entry),
                                              type(entry).__name__))
    for key in ("path", "rows", "bytes", "sha256"):
        value = entry.get(key)
        if key in ("path",):
            usable = isinstance(value, str) and bool(value)
        elif key == "sha256":
            usable = _is_digest(value)
        else:
            usable = isinstance(value, int) and not isinstance(value, bool)
        if not usable:
            raise ArithmeticError(
                "%s %s carries no usable `%s` (found %r); every entry in the pin's `files` list "
                "must carry a non-empty `path`, integer `rows` and `bytes`, and a 64-hex `sha256`"
                % (MASSIVE_PIN_LABEL, _pin_entry_label(index, entry), key, value))


def massive_pin(path: Optional[Path] = None) -> dict:
    """The committed MASSIVE pin list -- the owner of every figure this project prints about it.

    Returns `{}` when the file cannot be opened, because a library used outside this repository
    has no pin and `inventory()` refuses that case rather than publishing around it. A file that
    exists but is not JSON is a different failure: it is not the operator's mistake, so the parse
    error is re-raised as the refusal `main` already maps to EXIT_DRIFT rather than left as a
    `ValueError` (which would exit 2 and blame whoever ran the command).

    A pin whose entries disagree with their own declared totals raises for the same reason: the
    same quantity published under two values is drift, and `main` maps `ArithmeticError` to that
    exit code rather than to a usage error. So does a pin of the wrong SHAPE -- a JSON list, a
    non-object entry, an entry without `rows` (R-82): those used to escape as `AttributeError` /
    `KeyError` and exit 1, which is not in the published set at all.
    """
    pin_path = Path(path) if path is not None else MASSIVE_PIN_PATH
    try:
        raw = pin_path.read_text()
    except OSError:
        return {}
    try:
        pin = json.loads(raw)
    except ValueError as exc:
        raise ArithmeticError("%s is not readable JSON (%s); the MASSIVE figures have no owner"
                              % (MASSIVE_PIN_LABEL, exc)) from exc
    if not isinstance(pin, dict):
        raise ArithmeticError(
            "%s is a JSON %s, not an object; the MASSIVE figures have no owner"
            % (MASSIVE_PIN_LABEL, type(pin).__name__))
    files = pin.get("files")
    if not isinstance(files, list):
        raise ArithmeticError(
            "%s carries no `files` list; its counts have no owner" % MASSIVE_PIN_LABEL)
    for index, entry in enumerate(files):
        _require_pin_entry(index, entry)
    declared = pin.get("n_files")
    if declared != len(files):
        raise ArithmeticError(
            "%s declares n_files=%r while its `files` list holds %d" % (
                MASSIVE_PIN_LABEL, declared, len(files)))
    for key, want in (("rows_total", sum(f["rows"] for f in files)),
                      ("bytes_total", sum(f["bytes"] for f in files))):
        if pin.get(key) != want:
            raise ArithmeticError(
                "%s declares %s=%r where its %d entries sum to %d" % (
                    MASSIVE_PIN_LABEL, key, pin.get(key), len(files), want))
    rows_of_entries = sorted({f["rows"] for f in files})
    if pin.get("distinct_row_counts") != rows_of_entries:
        raise ArithmeticError(
            "%s declares distinct_row_counts=%r while its entries report %r" % (
                MASSIVE_PIN_LABEL, pin.get("distinct_row_counts"), rows_of_entries))
    # `distinct_ids` is NOT derived from `files[].rows`: it was measured by comparing the id sets
    # across shards, and keeping it a separate field is what lets the pooled row's `n_independent`
    # disagree with the row count instead of silently reusing it. What can be checked is the
    # arithmetic the pin's own identity claim implies: if every shard holds the same id set and the
    # same row count, then rows_total == distinct_ids x n_files.
    if pin.get("id_sets_identical") is True:
        expect = pin.get("distinct_ids")
        if expect is None or declared * expect != pin.get("rows_total"):
            raise ArithmeticError(
                "%s declares distinct_ids=%r with id_sets_identical true, but %d x that is not "
                "rows_total=%r" % (MASSIVE_PIN_LABEL, expect, declared, pin.get("rows_total")))
    return pin


def massive_pinned_shards(pin: dict) -> tuple:
    """(shards this list carries, shards the pin declares), both counted from the artefact.

    The pair, not a single number, is the disclosure: `50 of 51` means a shard is missing from the
    list that the pin says belongs in it, which is a different finding from `51 of 51` with a
    digest missing, and the basis sentence names the second separately. Reachability is honest to
    state: `massive_pin` refuses a file whose `n_files` disagrees with its list, so a truncated
    committed pin never renders `50 of 51` -- it exits 4 instead. The pair exists because
    `massive_pooled_basis` is a pure function of a dict, and the shape this project publishes for
    a partial pin list is the sentence above, not a silent 51.
    """
    return len(pin.get("files") or []), (pin.get("n_files") or 0)


def massive_pooled_basis(pin: dict) -> str:
    """The basis sentence for the pooled MASSIVE row, built from the pin and nothing else.

    O-6: this row said "3 of 51 files opened; the rest counted from the repo listing" while every
    pinned shard had in fact been opened, hashed and row-counted -- an understatement, but an
    understatement is still a number nobody could re-derive. It is now a rendering of the list.
    """
    listed, declared = massive_pinned_shards(pin)
    if not listed:
        return ("no shard is listed in %s, so this row cannot state a measured count"
                % MASSIVE_PIN_LABEL)
    files = pin.get("files") or []
    digestless = listed - sum(1 for f in files if _is_digest(f.get("sha256")))
    clause = "" if not digestless else "; %d listed shard(s) carry no digest" % digestless
    if pin.get("id_sets_identical") is not True:
        clause += ("; the shards' id sets are not recorded as identical, so this row cannot state "
                   "an independent case count")
    provenance = pin.get("provenance") or {}
    # The most recent verification, not the first one: `reverified_on` records the controller's
    # manual re-hash and `tool_verified_on` records the committed fetcher doing the same job. A
    # published sentence that keeps naming the older date understates what now backs it.
    verified_on = provenance.get("tool_verified_on") or provenance.get("reverified_on") \
        or "an unrecorded date"
    return ("%d of %d pinned shards opened, hashed and row-counted on %s at revision %s; the "
            "digests live in %s and the bytes are not vendored%s" % (
                listed, declared, verified_on,
                pin.get("revision", "an unpinned revision"), MASSIVE_PIN_LABEL, clause))


def _massive_rows_per_shard(pin: dict):
    """The single per-shard row count, or None when the shards do not all agree.

    2,974 is only a per-language count while every shard reports the same one; if a shard ever
    differs, the pooled row stops being 51 x a constant and the row must say it has no count
    rather than print a product of a stale one.
    """
    rows = sorted({f["rows"] for f in (pin.get("files") or [])})
    return rows[0] if len(rows) == 1 else None


def corpus_options(feishu_unique_ids: Optional[int] = None, pin: Optional[dict] = None) -> list:
    """Candidate corpora, with the bound computed on the number of INDEPENDENT cases.

    Three disclosures per row, because one of them was missing: `n_rows` counts what is in
    the files, `n_independent` counts what a bound may treat as a sample, and `basis` says
    whether each was opened or inferred. The first version multiplied three measured
    language files by a file listing and printed the product in a column labelled
    "measured", which flattered the bound by 51x: MASSIVE's 51 test files are translations
    of the same 2,974 utterances, so an automation rate estimated over them is a rate
    measured 2,974 ways, not 151,674 ways.

    That identity is a *measurement recorded in the pin*, not a derivation this function makes:
    `distinct_ids` was obtained by comparing the id sets of all 51 shards (`tools/fetch_massive.py
    ids`), and `n_independent` reads that field while `n_rows` reads `rows_total`. They agree at
    2,974 x 51 = 151,674 because the shards hold the same utterances, and if a future pin ever
    breaks that, the pooled row reports no independent count rather than reusing a row count --
    which is the difference between a bound on a sample and a bound on a translation table.
    """
    pin = massive_pin() if pin is None else pin
    per_shard = _massive_rows_per_shard(pin)
    listed, declared = massive_pinned_shards(pin)
    independent = pin.get("distinct_ids") if pin.get("id_sets_identical") is True else None
    specs = (
        {"id": "feishu_zh",
         "unit": "unique labelled cases, each answered twice per backend over 3 repeats",
         "n_rows": None, "n_independent": feishu_unique_ids,
         "basis": "not scanned (no corpus on this machine)" if feishu_unique_ids is None
                  else "scanned from results/v1/{laya,jev}/raw.jsonl",
         "note": "the only corpus with real archived jev responses"},
        {"id": "massive_intent_per_language",
         "unit": "labelled decision rows (one utterance, one intent)",
         "n_rows": per_shard, "n_independent": per_shard,
         "basis": ("each of the %s pinned test shards opened and counted, %s rows per shard"
                   % (MASSIVE_PIN_LABEL, per_shard)) if per_shard is not None else
                  ("%s does not report one row count shared by every shard" % MASSIVE_PIN_LABEL),
         "note": "each language file is a candidate Mondrian slice"},
        {"id": "massive_intent_all_languages",
         "unit": "(language, utterance) pairs -- NOT independent cases",
         "n_rows": pin.get("rows_total"), "n_independent": independent, "n_shards": declared,
         "basis": massive_pooled_basis(pin),
         # m-8: the sentence is built as a whole, because the old shape spliced a noun phrase into
         # "%s of pinned bytes" and the falsy arm read "no byte total pinned of pinned bytes". The
         # loader has policed `bytes_total` against the entries since `b964af0`, so that arm is now
         # reachable only for a caller that hands `corpus_options` a hand-built pin -- which is
         # exactly the caller a broken sentence used to be cheapest for. Pinned bytes for the
         # committed pin read "3.2 MB of pinned bytes", byte for byte as before this rewrite.
         "note": "Apache-2.0, %s; the extra shards are translations of the same utterances, so the "
                 "row multiple is coverage, not sample size"
                 % ("%.1f MB of pinned bytes" % (pin["bytes_total"] / 1e6)
                    if pin.get("bytes_total") else "no byte total pinned")},
        {"id": "typed_decisions", "unit": "labelled decisions", "n_rows": None,
         "n_independent": None,
         "basis": "dataset card size category 1K<n<10K only; no file opened",
         "note": "candidate contamination probe (public train 300 / test 100)"},
    )
    out = []
    for s in specs:
        n = s["n_independent"]
        width = None if n is None else round(bound_width(n), 4)
        out.append({**s,
                    "bound_width_at_0.05": width,
                    "feasible_at_0.10": None if n is None else bool(
                        n_feasible(n, max_bound_width=0.10)),
                    "feasible_at_0.25": None if n is None else bool(
                        n_feasible(n, max_bound_width=0.25))})
    return out


def _count_phrase(count, noun: str) -> str:
    """A count with its noun agreeing in number, or the absence named as an absence.

    m-7: the artefact printed `%d malformed line` for any n, so three unreadable lines read
    "3 malformed line". The count itself is a reader counter and may be absent when the reader
    could not be opened, which is not the same statement as zero.
    """
    if count is None:
        return "not measured"
    return "%d %s%s" % (count, noun, "" if count == 1 else "s")


def _independent_cell(option: dict) -> str:
    """How a bound-table row says it has no independent-case count (m-4).

    "not opened" was one string for two different findings. For `typed_decisions` it is true -- no
    file of that corpus was opened, and its basis says so. For a MASSIVE row it was self-
    contradicting: measured, a pin with `id_sets_identical: false` rendered
    "| massive_intent_all_languages | not opened | 151674 | 51 of 51 pinned shards opened, hashed
    and row-counted on ... |", one cell denying what the cell beside it asserts, with rc 0. The
    figure is not un-opened there, it is un-measured AS AN ID SET, which is what the row now says.
    """
    if option["n_independent"] is not None:
        return str(option["n_independent"])
    return ("not measured (id sets not pinned)" if option["id"].startswith("massive")
            else "not opened")


def write_inventory(d: dict, out: Path) -> None:
    """Render the inventory. A corpus whose own integrity gate failed is not published."""
    if d["upstream_audit_rc"] != 0:
        raise ValueError(
            "upstream audit.py exited %d; refusing to inventory a corpus that fails its "
            "own integrity gate. stderr tail: %s" % (d["upstream_audit_rc"], d["upstream_audit_stderr_tail"][:200])
        )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Offline data inventory",
        "",
        "Produced by `uv run --frozen autorate snapshot` -- every number here is computed",
        "from the corpus or opened from a file, and the count basis is named per row.",
        "",
        "- corpus: `%s`" % d["source"],
        "- unique ids: **%d**   repeats: %s" % (d["unique_ids"], d["repeats"]),
        "- slice keys (families): %s" % ", ".join("`%s`" % f for f in d["families"]),
        "- label balance: %s" % ", ".join("%s=%d" % kv for kv in sorted(
            d["label_counts"].items())),
        "- upstream `audit.py` exit code: **%d** (the interpreter that ran it is recorded "
        "in `%s.json`, because it is a path on one machine and stale for every other "
        "reader)" % (d["upstream_audit_rc"], out.name),
        "- provenance: %s" % d["provenance"],
    ]
    if d["digests"]:
        bad = [x["path"] for x in d["digests"] if not x["match"]]
        lines.append("- upstream `SOURCE.json` file digests: **%d/%d match**%s" % (
            len(d["digests"]) - len(bad), len(d["digests"]),
            "" if not bad else "; MISMATCH: " + ", ".join(bad)))
    else:
        lines.append("- upstream `SOURCE.json` file digests: none recorded by that file")
    lines += [
        "",
        "## Archive lines per mode x backend",
        "",
        "| key | archive lines |",
        "|---|---|",
    ]
    for k, v in sorted(d["lines_by_mode_backend"].items()):
        lines.append("| %s | %d |" % (k, v))

    kept = d.get("reader_lines_by_mode", {})
    quarantined_by_mode = d.get("reader_lines_quarantined_only", {})
    lines += ["", "Counts here are archive LINES per mode and backend, for the lines this pass",
              "could bucket: a line it could not read, or one the shared line rule refused, is",
              "counted beside the table rather than inside it, which is what the reader does with",
              "the same bytes. The reader keeps only the lines it turns into records, so its own",
              "count can still be smaller; what it did with the rest is named on its own line",
              "below rather than netted into a single difference.", ""]
    for mode in MODES:
        present = sum(v for k, v in d["lines_by_mode_backend"].items() if k.startswith(mode + "/"))
        kept_n = kept.get(mode)
        # Both ledgers now come from the same rule (R-80/R-81), and the line a pass names rather
        # than buckets is in neither table, so the denominator this bullet quotes is the bucketed
        # count plus the named one -- the archive lines that carry this mode, whichever way they
        # left the pass. Quoting only the table would print "383 of 383 kept (1 quarantined)".
        quarantined_n = quarantined_by_mode.get(mode, 0)
        if kept_n is None:
            lines.append("- %s: %d lines present, reader count not measured in this run"
                         % (mode, present))
        else:
            # Read from the reader's own per-mode ledger. The subtraction this line used to print --
            # `present - kept` labelled "quarantined" -- charged a refused line to the quarantine.
            lines.append("- %s: **%d of %d** lines kept by the reader (%d quarantined for this mode)"
                         % (mode, kept_n, present + quarantined_n, quarantined_n))
    refused_n = d.get("lines_refused_not_ok")
    if refused_n:
        # m-7's attribution, closed per line: these are the lines neither ledger names, so the
        # table above does not add up without saying where they went.
        lines.append("- scanner: %d line(s) carried no `status` of `ok` and are counted in "
                     "`lines_refused_not_ok` -- outside the table above, and named in no "
                     "quarantine ledger, exactly as the reader drops them" % refused_n)
    lines.append("- reader dispositions: %s, %s named by mode, %s refused "
                 "(status not ok), %s filtered"
                 % (_count_phrase(d.get("reader_lines_malformed"), "malformed line"),
                    sum(v for k, v in quarantined_by_mode.items() if k != MALFORMED_LINE),
                    d.get("reader_lines_dropped_not_ok"), d.get("reader_lines_filtered")))
    lines.append("")
    lines += ["", "## Can this corpus support a bound?", ""]
    lines.append(
        "Bound width for an automation-rate estimate is `2*sqrt(ln(2/alpha)/(2n))`. "
        "At `alpha=0.05` the committed corpus gives **%.4f** for n=%d, which is why "
        "`autorate certify` is expected to refuse on it rather than publish a number."
        % (bound_width(d["unique_ids"]), d["unique_ids"])
    )
    lines += ["", "The bound is computed on `n_independent`, never on `n_rows`: rows that are",
              "repeats or translations of the same case do not add sample size.", "",
              "| corpus | n_independent | n_rows | count basis | bound width @0.05 | feasible @0.10 |",
              "|---|---|---|---|---|---|"]
    for o in d["corpus_options"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            o["id"],
            _independent_cell(o),
            "-" if o["n_rows"] is None else o["n_rows"],
            o["basis"],
            "-" if o["bound_width_at_0.05"] is None else "%.4f" % o["bound_width_at_0.05"],
            "-" if o["feasible_at_0.10"] is None else ("yes" if o["feasible_at_0.10"] else "no"),
        ))
    lines += ["", "| corpus | unit | note |", "|---|---|---|"]
    for o in d["corpus_options"]:
        lines.append("| %s | %s | %s |" % (o["id"], o["unit"], o["note"]))

    lines += ["", "## Known gaps", ""] + ["- %s" % g for g in d["gaps"]] + [""]
    out.write_text("\n".join(lines))
    Path(str(out) + ".json").write_text(json.dumps(d, indent=2, sort_keys=True))
