"""Reader for the only offline labelled per-case decision corpus we have (spec 3, L1 source 2).

Reads what the archive holds and marks what it does not. Two shapes matter: the option
order is whatever the backend published (the two backends disagree on the same case), and
a `four_noul` line is four records whose labels the fixtures never supervise.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..records import NOUL_SLOTS, SUM_TOL, Record

BACKENDS = ("laya", "jev")
MODES = ("choice", "four_noul")
CHOICE_QUESTION = "category"
# One owner for the name, because it is both the quarantine reason and the line-accounting
# bucket: an unreadable line has no readable `mode` to key on, so the conservation identity
# in `read_archive` closes over it under this label rather than a mode label.
MALFORMED_LINE = "malformed_line"
# The reader's own words for the one archived `choice` line whose published probabilities do not
# close (ledger R-28: `jev / lifecycle-01 / repeat=1`). It is a constant because the inventory
# scanner files the SAME line under the SAME reason (R-80): the two passes publish their quarantine
# ledgers beside each other, and a line the reader refuses for a reason the scanner paraphrases is
# two owners of one rule -- the defect class R-55 was raised for.
PROBS_NOT_CLOSING = "probabilities do not close to 1 within tolerance"


def _quarantine(obj: dict, backend: str, probs, reason: str) -> dict:
    """Name a record the contract refuses, instead of widening the contract or dropping it.

    Measured: exactly one archived line is affected — `jev / lifecycle-01 / repeat=1`,
    probabilities [0.0, 0.93, 0.01, 0.05] summing to 0.99. Upstream's own guard
    (`prompts.py:27`) tolerates abs(sum-1) > 0.01, so it passed there and fails here.
    """
    return {"id": obj.get("id"), "backend": backend, "mode": obj.get("mode"),
            "repeat": obj.get("repeat"), "probs": [float(x) for x in probs],
            "probs_sum": round(float(sum(probs)), 6), "tolerance": SUM_TOL, "reason": reason}


class ReaderContractError(RuntimeError):
    """The corpus contradicts this reader's own contract, so reading it must stop (R-14).

    Deliberately NOT a `ValueError`: `read_archive` catches `ValueError` to quarantine a line
    it cannot read and carry on, and a policy refusal is not an unreadable line -- filing it
    under `malformed_line` would absorb the one error this class exists to name, and the run
    would exit 0 on a corpus it refused to certify. It is raised so that it escapes the
    per-line guard, and `cli.main` maps it to `EXIT_USAGE`: loud, non-zero, never mislabelled,
    and rc 1 stays unreachable.
    """


def error_label(exc: Exception) -> str:
    """One owner for the name an unreadable line carries: the exception type and its message."""
    return "%s: %s" % (type(exc).__name__, exc)


def parse_archive_line(line: str, required_keys=()) -> tuple:
    """R-55: the one owner of the unreadable-archive-line rule.

    Parses one raw line, requires each key in `required_keys` -- a caller names the fields its
    own pass indexes blind, so the rule stays single-owned while the two passes differ in what
    they read from a readable line -- and returns `(obj, error)`. `error` is `""` when the line
    is readable; otherwise it is the failure named by type and message, and `obj` is whatever
    parsed (`{}` when nothing did), because the id of a line that only half-read is still the
    join key to `data/cases.jsonl`.

    The catch set lives here and nowhere else: two `try/except` sets for one rule drift, and
    the drift is invisible until a line shape passes one guard and crashes the other. That is
    exactly how one unparseable line came to exit 1 out of the inventory scanner.
    `ReaderContractError` is a `RuntimeError`, so no caller of this function can absorb a
    policy refusal into the quarantine bucket.
    """
    obj: dict = {}
    try:
        parsed = json.loads(line)
        if not isinstance(parsed, dict):
            # Name the shape here, in the branch that knows how to record it. Left to the reads
            # below, a JSON `null` / `123` / `"x"` / `[...]` raises AttributeError -- outside
            # the catch set and outside the CLI's mapping.
            raise TypeError("line is a JSON %s, not an object" % type(parsed).__name__)
        obj = parsed
        for key in required_keys:
            if key not in obj:
                raise KeyError(key)
    except (ValueError, KeyError, TypeError) as exc:
        return obj, error_label(exc)
    return obj, ""


def unreadable_mode_reason(mode) -> str:
    """The one sentence naming a line whose `mode` neither this reader nor the inventory buckets.

    Shared because the two passes must file the same shape under the same words: a mode string
    this contract does not read is a defect to name, not a line to drop, and it was already
    visible that a line dropped by one pass and bucketed by the other is a corpus disagreement.
    """
    return "mode %r is not readable by this reader" % mode


# The namespace a colliding mode string is published under. Chosen so it can never equal
# `MALFORMED_LINE`: the prefix is added to the whole string, and a mode that already starts with it
# gets prefixed again (`mode:mode:x`), so no archive value can land on the internal bucket name.
MODE_BUCKET_PREFIX = "mode:"


def mode_bucket_key(mode) -> str:
    """R-81 (review MA-6): ONE function chooses the ledger key of an unbucketable `mode`.

    Both passes used to publish `str(mode)` for a readable line whose mode this contract cannot
    bucket, and `malformed_line` for a line neither pass could read. Those are two names for two
    different rules, and nothing said the first could not spell the second: one archive line with
    `"mode": "malformed_line"` measured at `5ec8639` merged into the internal bucket, the
    inventory's own conservation check then refused ("0 malformed published, 1 under
    `malformed_line`"), and the shipped `autorate snapshot` exited 4 for a corpus that is merely
    strange rather than broken.

    That is the exit-code contract inverted: corpus CONTENT must never be able to select rc 4, which
    this project reserves for a tool that cannot reproduce its own arithmetic. So a mode string that
    equals the internal label is namespaced, and every other key stays the plain mode string -- the
    shipped corpus's `{'choice': 1}` is published exactly as it read before. One function, here,
    called by both passes: the key is part of the line rule, and the line rule has one owner (R-55).
    """
    text = str(mode)
    return MODE_BUCKET_PREFIX + text if text == MALFORMED_LINE else text


def choice_probabilities(obj: dict) -> tuple:
    """`(options, probs, failure)` for a `choice` line: the vector exactly as it was published.

    Returns the failure instead of raising it, because the two callers reading this vector owe
    their callers different policies and must still share one shape rule (R-55):
    `records_from_line` re-raises so `read_archive`'s per-line guard names the line, while the
    inventory scanner may not raise at all -- rc 1 is outside the exit-code contract.

    The option order is the backend's, never sorted: the two backends present the same case in
    different orders, so a sorted vector would silently re-key the probabilities.
    """
    try:
        answers = obj["response"]["answers"][CHOICE_QUESTION]
        options = tuple(answers["probabilities"].keys())          # published order, never sorted
        probs = tuple(float(answers["probabilities"][k]) for k in options)
    except (ValueError, KeyError, TypeError) as exc:
        return (), (), exc
    return options, probs, None


def quarantine_line_entry(obj: dict, backend: str, line_no: int, reason: str,
                          error: str = "") -> dict:
    """One published shape for a line the per-mode counts do not cover (R-55: one owner).

    Both classes come through here: an unreadable line (`reason` is `MALFORMED_LINE`, `error`
    names the exception) and a readable line whose `mode` this contract cannot bucket
    (`reason` is `unreadable_mode_reason`). The line's own bytes stay out either way -- an
    archive line can carry content no reader should republish.
    """
    entry = _quarantine(obj, backend, (), reason)
    entry.update({"line_no": line_no, "error": error})
    return entry


def _meta(obj: dict) -> dict:
    diag = obj.get("diagnostics") or {}
    return {
        "request_sha256": obj.get("request_sha256"),
        "elapsed_ms": obj.get("elapsed_ms"),
        "model": obj["response"].get("model"),
        "truncated": bool(diag.get("state_truncated") or diag.get("instructions_truncated")),
        # The archive recorded no APS draw, so ties resolve to the first slot. Stating
        # it here beats letting a certifier assume a draw that was never taken.
        "u_source": "absent_from_archive",
    }


def per_ask_gold(root: Path) -> dict:
    """Whether the binary asks have ground-truth bits anywhere in the corpus fixtures.

    Owned by the reader because it decides what a record's `gold` may be. Measured, not
    asserted: the ask names come from the manifest and the label keys from `cases.jsonl`;
    if the two never intersect, no per-ask gold exists and a `noul` certificate on this
    corpus would be certifying invented labels (ledger R-14).
    """
    root = Path(root)
    manifest = json.loads((root / "data" / "manifest.json").read_text())
    asks = sorted(manifest.get("asks", {}))
    case_keys: set = set()
    for line in (root / "data" / "cases.jsonl").read_text().splitlines():
        if line.strip():
            case_keys |= set(json.loads(line))
    return {"asks": asks, "case_keys": sorted(case_keys),
            "asks_with_gold": sorted(set(asks) & case_keys),
            "composite_label_available": "expected" in case_keys}


def records_from_line(obj: dict, backend: str, quarantine: Optional[list] = None,
                      asks_with_gold=()) -> list:
    if obj.get("status") != "ok":
        return []
    answers = obj["response"]["answers"]
    repeat = int(obj["repeat"])
    meta = _meta(obj)
    base_slices = {"family": obj.get("family"), "mode": obj.get("mode"),
                   "repeat": repeat, "language": "zh"}
    out: list = []
    if obj["mode"] == "choice":
        # One owner for reading the published vector (R-55): the inventory scanner reads the
        # same shape from the same line, and it must not be able to raise. Re-raising here
        # keeps `read_archive`'s per-line guard naming the line exactly as it did before.
        options, probs, failure = choice_probabilities(obj)
        if failure is not None:
            raise failure
        a = answers[CHOICE_QUESTION]
        if abs(sum(probs) - 1.0) > SUM_TOL:
            if quarantine is not None:
                quarantine.append(_quarantine(obj, backend, probs, PROBS_NOT_CLOSING))
            return []
        out.append(Record(
            id=obj["id"], qtype="choice", backend=backend, repeat=repeat,
            case_id=obj.get("request_sha256"),
            options=options, probs=probs, gold=obj.get("expected"),
            predicted=a.get("choice"), slices=base_slices,
            scores={"reported_confidence": a.get("confidence"),
                    "act_probability": (a.get("action") or {}).get("act_probability")},
            seed=0, u=0.0, meta=meta,
        ))
    elif obj["mode"] == "four_noul":
        noul_asks = [k for k in answers if answers[k].get("type") == "noul"]
        if not noul_asks:
            # A line whose mode promises four binary asks and delivers none is a defect
            # to name, not a line to drop: absorbing it silently shrinks the sample that
            # every later bound is computed over.
            if quarantine is not None:
                quarantine.append(_quarantine(
                    obj, backend, (), "four_noul line carries no noul-typed answer"))
            return out
        for ask, a in sorted(answers.items()):
            if a.get("type") != "noul":
                continue
            p_true = float(a["noul"])
            confidence = a.get("confidence")
            if not 0.0 <= p_true <= 1.0:
                if quarantine is not None:
                    quarantine.append(_quarantine(
                        obj, backend, (p_true,), "noul probability outside [0,1]"))
                continue
            out.append(Record(
                id="%s#%s" % (obj["id"], ask), qtype="noul", backend=backend, repeat=repeat,
                case_id=obj.get("request_sha256"),  # the four asks of one case are one case
                options=NOUL_SLOTS, probs=(p_true,),
                gold=_ask_gold(ask, obj, asks_with_gold),
                predicted="true" if p_true >= 0.5 else "false",
                slices={**base_slices, "ask": ask},
                scores={"reported_confidence": confidence, "noul": p_true,
                        # upstream sets confidence to P(yes): a confident "no" and a
                        # low-confidence answer arrive as the same number.
                        "noul_confounded_with_yes": confidence == p_true,
                        "act_probability": (a.get("action") or {}).get("act_probability")},
                seed=0, u=0.0, meta=meta,
            ))
    else:
        if quarantine is not None:
            quarantine.append(_quarantine(obj, backend, (),
                                          unreadable_mode_reason(obj.get("mode"))))
    return out


def _ask_gold(ask: str, obj: dict, asks_with_gold=()) -> Optional[str]:
    """Per-ask ground truth does not exist in this corpus (ledger R-14).

    `data/cases.jsonl` carries only the composite 4-way `expected`, and
    `prompts.py:34` folds the four asks into that label. Returning None keeps the
    records gateable and uncalibratable; inventing bits from `expected` would
    manufacture an accuracy figure out of a policy.

    `asks_with_gold` is the measured set, so the tripwire can actually fire: if the
    fixtures start supervising an ask, this reader must join it from `cases.jsonl`
    rather than silently keep returning None.
    """
    if ask in asks_with_gold:
        # A refusal, not a parse failure: `ReaderContractError` escapes `read_archive`'s
        # per-line guard so it cannot be counted as one more malformed line.
        raise ReaderContractError(
            "ask %r is now supervised in the corpus fixtures, but this reader still "
            "returns gold=None for noul records; join it from data/cases.jsonl instead "
            "of guessing it from the composite `expected` label" % ask)
    return None


def read_archive(root: Path, backend: Optional[str] = None, repeat: Optional[int] = None,
                 mode: Optional[str] = None, stats: Optional[dict] = None) -> list:
    root = Path(root)
    backends = [backend] if backend else list(BACKENDS)
    gold = per_ask_gold(root)["asks_with_gold"] if (root / "data" / "manifest.json").exists() else ()
    records: list = []
    quarantine: list = []
    lines_read = lines_kept = lines_dropped = lines_filtered = lines_malformed = 0
    unaccounted: list = []
    lines_by_mode: dict = {}
    lines_quarantined_only: dict = {}
    for b in backends:
        path = root / "results" / "v1" / b / "raw.jsonl"
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            lines_read += 1          # before parsing: an unread line is still a line seen
            # `q_before` is this line's snapshot of the shared list: `records_from_line`
            # appends as it goes, so a line that quarantines one ask and then fails on the next
            # would publish two entries for the one line the conservation identity counts.
            # The parse-and-shape rule is the shared one (R-55), so the scanner that counts
            # these same files cannot disagree about which lines it could not read. This pass asks
            # for no keys here, and the sentence's precondition is the one the scanner mirrors
            # (R-80): it holds for a line this pass goes on to READ, i.e. one whose `status` is
            # `ok` -- a line missing `mode` AND missing `status` is dropped below as not-ok and
            # never reaches the named failure at all. The old claim that any line missing `mode`
            # "reaches the same named failure one read further down" was refuted by that shape:
            # it is why the scanner, not the reader, had to move (review M2's rows 3-5).
            obj, error = parse_archive_line(line)
            q_before = len(quarantine)
            if not error:
                try:
                    # The filters read `repeat` and `mode` straight out of the line, so they
                    # are inside the same guard: a line missing either key is malformed, and a
                    # filtered read must not become the one place rc 1 can still escape.
                    if (repeat is not None and int(obj["repeat"]) != repeat) or (
                            mode is not None and obj["mode"] != mode):
                        lines_filtered += 1
                        continue
                    if obj.get("status") != "ok":
                        lines_dropped += 1
                        continue
                    before = len(records)
                    records.extend(records_from_line(obj, b, quarantine, gold))
                except (ValueError, KeyError, TypeError) as exc:
                    # A line this contract cannot read is named, not dropped and not fatal:
                    # rc 1 is not in the exit-code set, and a malformed line in a corpus we
                    # downloaded (Plan C) is ordinary, not exceptional. The bytes stay out --
                    # an archive line can carry content no reader should republish.
                    # `ReaderContractError` is a RuntimeError and is deliberately NOT caught:
                    # a refusal to certify this corpus is not a line that cannot be read.
                    del quarantine[q_before:]      # drop the failed call's orphaned entries
                    error = error_label(exc)
            if error:
                quarantine.append(quarantine_line_entry(obj, b, line_no, MALFORMED_LINE, error))
                lines_malformed += 1
                lines_quarantined_only[MALFORMED_LINE] = \
                    lines_quarantined_only.get(MALFORMED_LINE, 0) + 1
                continue
            if len(records) > before:
                lines_kept += 1
                lines_by_mode[obj["mode"]] = lines_by_mode.get(obj["mode"], 0) + 1
            elif len(quarantine) > q_before:
                key = mode_bucket_key(obj.get("mode"))
                lines_quarantined_only[key] = lines_quarantined_only.get(key, 0) + 1
            else:
                unaccounted.append({"id": obj.get("id"), "backend": b,
                                    "mode": obj.get("mode"), "repeat": obj.get("repeat")})
    accounted = lines_kept + lines_dropped + lines_filtered + sum(
        lines_quarantined_only.values()) + len(unaccounted)
    if accounted != lines_read:
        raise ArithmeticError(
            "line accounting does not conserve: %d read, %d accounted (%d kept, %d not-ok, "
            "%d filtered, %d quarantined-only, %d unaccounted)" % (
                lines_read, accounted, lines_kept, lines_dropped, lines_filtered,
                sum(lines_quarantined_only.values()), len(unaccounted)))
    if unaccounted:
        raise ValueError(
            "%d archive line(s) produced neither a record nor a quarantine entry and would "
            "have vanished silently: %s" % (len(unaccounted), unaccounted[:3]))
    if stats is not None:
        stats["lines_read"] = lines_read
        stats["lines_kept"] = lines_kept
        stats["lines_filtered"] = lines_filtered
        stats["lines_dropped_not_ok"] = lines_dropped
        stats["lines_malformed"] = lines_malformed
        stats["lines_quarantined_only"] = dict(sorted(lines_quarantined_only.items()))
        stats["lines_by_mode"] = dict(sorted(lines_by_mode.items()))
        stats["records_kept"] = len(records)
        stats["quarantined"] = list(quarantine)
    return records
