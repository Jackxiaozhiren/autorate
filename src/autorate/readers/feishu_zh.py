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
NOUL_ASKS = ("action", "related", "urgent", "value")


def _quarantine(obj: dict, backend: str, probs, reason: str) -> dict:
    """Name a record the contract refuses, instead of widening the contract or dropping it.

    Measured: exactly one archived line is affected — `jev / lifecycle-01 / repeat=1`,
    probabilities [0.0, 0.93, 0.01, 0.05] summing to 0.99. Upstream's own guard
    (`prompts.py:27`) tolerates abs(sum-1) > 0.01, so it passed there and fails here.
    """
    return {"id": obj.get("id"), "backend": backend, "mode": obj.get("mode"),
            "repeat": obj.get("repeat"), "probs": [float(x) for x in probs],
            "probs_sum": round(float(sum(probs)), 6), "tolerance": SUM_TOL, "reason": reason}


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
        a = answers[CHOICE_QUESTION]
        options = tuple(a["probabilities"].keys())          # published order, never sorted
        probs = tuple(float(a["probabilities"][k]) for k in options)
        if abs(sum(probs) - 1.0) > SUM_TOL:
            if quarantine is not None:
                quarantine.append(_quarantine(
                    obj, backend, probs, "probabilities do not close to 1 within tolerance"))
            return []
        out.append(Record(
            id=obj["id"], qtype="choice", backend=backend, repeat=repeat,
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
            quarantine.append(_quarantine(obj, backend, (), "mode %r is not readable by "
                                          "this reader" % obj.get("mode")))
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
        raise ValueError(
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
    lines_read = lines_kept = lines_dropped = lines_filtered = 0
    unaccounted: list = []
    lines_by_mode: dict = {}
    lines_quarantined_only: dict = {}
    for b in backends:
        path = root / "results" / "v1" / b / "raw.jsonl"
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            lines_read += 1
            if (repeat is not None and int(obj["repeat"]) != repeat) or (
                    mode is not None and obj["mode"] != mode):
                lines_filtered += 1
                continue
            if obj.get("status") != "ok":
                lines_dropped += 1
                continue
            before, q_before = len(records), len(quarantine)
            records.extend(records_from_line(obj, b, quarantine, gold))
            if len(records) > before:
                lines_kept += 1
                lines_by_mode[obj["mode"]] = lines_by_mode.get(obj["mode"], 0) + 1
            elif len(quarantine) > q_before:
                key = str(obj.get("mode"))
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
        stats["lines_quarantined_only"] = dict(sorted(lines_quarantined_only.items()))
        stats["lines_by_mode"] = dict(sorted(lines_by_mode.items()))
        stats["records_kept"] = len(records)
        stats["quarantined"] = list(quarantine)
    return records
