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


def records_from_line(obj: dict, backend: str, quarantine: Optional[list] = None) -> list:
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
        for ask, a in answers.items():
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
                gold=_ask_gold(ask, obj),
                predicted="true" if p_true >= 0.5 else "false",
                slices={**base_slices, "ask": ask},
                scores={"reported_confidence": confidence, "noul": p_true,
                        # upstream sets confidence to P(yes): a confident "no" and a
                        # low-confidence answer arrive as the same number.
                        "noul_confounded_with_yes": confidence == p_true,
                        "act_probability": (a.get("action") or {}).get("act_probability")},
                seed=0, u=0.0, meta=meta,
            ))
    return out


def _ask_gold(ask: str, obj: dict) -> Optional[str]:
    """Per-ask ground truth does not exist in this corpus (ledger R-14).

    `data/cases.jsonl` carries only the composite 4-way `expected`, and
    `prompts.py:34` folds the four asks into that label. Returning None keeps the
    records gateable and uncalibratable; inventing bits from `expected` would
    manufacture an accuracy figure out of a policy.
    """
    return None


def read_archive(root: Path, backend: Optional[str] = None, repeat: Optional[int] = None,
                 mode: Optional[str] = None, stats: Optional[dict] = None) -> list:
    root = Path(root)
    backends = [backend] if backend else list(BACKENDS)
    records: list = []
    quarantine: list = []
    lines_kept = 0
    lines_dropped = 0
    lines_by_mode: dict = {}
    for b in backends:
        path = root / "results" / "v1" / b / "raw.jsonl"
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if repeat is not None and int(obj["repeat"]) != repeat:
                continue
            if mode is not None and obj["mode"] != mode:
                continue
            if obj.get("status") != "ok":
                lines_dropped += 1
                continue
            before = len(records)
            records.extend(records_from_line(obj, b, quarantine))
            if len(records) > before:
                lines_kept += 1
                lines_by_mode[obj["mode"]] = lines_by_mode.get(obj["mode"], 0) + 1
    if stats is not None:
        stats["lines_kept"] = lines_kept
        stats["lines_dropped_not_ok"] = lines_dropped
        stats["lines_by_mode"] = lines_by_mode
        stats["records_kept"] = len(records)
        stats["quarantined"] = list(quarantine)
    return records
