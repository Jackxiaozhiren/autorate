"""Offline data inventory: which labelled per-case decision corpus exists, and whether n bounds.

Integrity is owned by upstream's own model-free audit; this module records its verdict
and transcribes -- without redefining -- the digests upstream pins in its own
`SOURCE.json`. Two refusals are the point of the module: publishing a corpus whose audit
failed, and quoting a bound that the sample size cannot support.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .records import SUM_TOL

MODES = ("choice", "four_noul")
BACKENDS = ("laya", "jev")
ALPHA_DEFAULT = 0.05


def bound_width(n: int, alpha: float = ALPHA_DEFAULT) -> float:
    """Width of the two-sided DKW-style interval on an automation-rate estimate.

    2 * sqrt(ln(2/alpha) / (2n)). It is the honest answer to "is this corpus big
    enough to certify anything", and it is why a refusal is a result.
    """
    if n <= 1:
        return float("inf")
    return 2.0 * math.sqrt(math.log(2.0 / alpha) / (2.0 * n))


def n_feasible(unique_n: int, alpha: float = ALPHA_DEFAULT, max_bound_width: float = 0.10) -> bool:
    return bound_width(unique_n, alpha) <= max_bound_width


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
    and is portable. tests/test_inventory.py guards the class.
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
            return str(venv)
    return sys.executable


def audit_command(root: Path) -> tuple[list[str], dict]:
    root = Path(root)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return [_audit_python(root), "audit.py"], env


def _scan_jsonl(path: Path) -> tuple[dict, set, list]:
    """One pass over a backend file, bucketed by `mode`.

    Each backend file holds both modes (192 choice + 192 four_noul = 384 lines), so
    counting lines per file and labelling them per mode is the same collapse the
    reader has to avoid: lines are not records.
    """
    by_mode: dict = {}
    ids: set = set()
    repeats: set = set()
    unclosed: list = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        by_mode[rec["mode"]] = by_mode.get(rec["mode"], 0) + 1
        ids.add(rec["id"])
        repeats.add(rec["repeat"])
        if rec["mode"] == "choice" and rec.get("status") == "ok":
            probs = [float(x) for x in rec["response"]["answers"]["category"]["probabilities"].values()]
            if abs(sum(probs) - 1.0) > SUM_TOL:
                # The tolerance has one owner (records.SUM_TOL) and the reader
                # quarantines the same lines, so inventory and reader cannot
                # disagree about what the corpus contains.
                unclosed.append({"id": rec["id"], "backend": path.parent.name,
                                 "repeat": rec["repeat"], "probs": probs,
                                 "probs_sum": round(sum(probs), 6)})
    return by_mode, ids, sorted(repeats), unclosed


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
    gold = per_ask_gold(root)
    manifest = json.loads((root / "data" / "manifest.json").read_text())
    per_mode: dict = {}
    ids: set = set()
    repeats: list = []
    unclosed: list = []
    for backend in BACKENDS:
        path = root / "results" / "v1" / backend / "raw.jsonl"
        by_mode, this_ids, this_reps, this_unclosed = _scan_jsonl(path)
        unclosed += this_unclosed
        for mode in MODES:
            # Separator is "/", not "|": these keys are rendered into a markdown table,
            # and a pipe inside a cell silently adds a column and breaks the table.
            per_mode["%s/%s" % (mode, backend)] = by_mode.get(mode, 0)
        if backend == "laya":  # uniqueness is asserted on one backend, not summed
            ids |= this_ids
            repeats = this_reps
    reader_stats: dict = {}
    try:
        read_archive(root, stats=reader_stats)
    except OSError as exc:
        reader_stats = {"error": str(exc)}
    cmd, env = audit_command(root)
    audit = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), env=env)
    return {
        "source": corpus_label(root),
        "lines_by_mode_backend": dict(sorted(per_mode.items())),
        "unique_ids": len(ids),
        "repeats": repeats,
        "families": sorted(manifest.get("families", {})),
        "label_counts": dict(manifest.get("labels", {})),
        "provenance": manifest.get("provenance", ""),
        "upstream_audit_rc": audit.returncode,
        "upstream_audit_stdout_tail": audit.stdout[-400:],
        "upstream_audit_stderr_tail": audit.stderr[-400:],
        "audit_interpreter": _interpreter_label(cmd[0]),
        "min_calibration_n": manifest.get("cases", len(ids)),
        "probs_not_closing": unclosed,
        "sum_tolerance": SUM_TOL,
        "per_ask_gold": gold,
        "reader_lines_by_mode": {k: v for k, v in sorted(
            reader_stats.get("lines_by_mode", {}).items())},
        "reader_quarantined": len(reader_stats.get("quarantined", [])),
        "reader_lines_read": reader_stats.get("lines_read"),
        "reader_lines_quarantined_only": reader_stats.get("lines_quarantined_only"),
        "digests": corpus_digests(root),
        "corpus_options": corpus_options(len(ids)),
        "gaps": [
            "research/results/eval_english_51_languages.json: per-case records omitted; "
            "regenerate with research/eval/laya_eval.py --langs all --out <path>",
            "mteb/amazon_massive_intent is not in the local HF dataset cache",
            "the archived corpus carries no randomisation draw (u), so APS ties resolve to 0 here",
        ] + ([] if gold["asks_with_gold"] else [
            "the four `noul` asks carry no per-ask ground truth anywhere in the fixtures "
            "(asks %s are not among the case keys %s); only the composite 4-way label is "
            "supervised, so a noul certificate on this corpus would certify invented labels"
            % (gold["asks"], gold["case_keys"]),
        ]) + ([] if not unclosed else [
            "%d archived choice line(s) publish probabilities that do not close to 1 within "
            "%g and are quarantined by the reader rather than absorbed by a wider tolerance: %s"
            % (len(unclosed), SUM_TOL,
               ", ".join("%s/%s/repeat=%s (sum %.4f)" % (u["backend"], u["id"], u["repeat"], u["probs_sum"])
                         for u in unclosed)),
        ]),
    }


MASSIVE_LANGUAGES_TOTAL = 51
MASSIVE_LANGUAGES_OPENED = ("de", "en", "sw")
MASSIVE_ROWS_PER_LANGUAGE = 2974


def corpus_options(feishu_unique_ids: Optional[int] = None) -> list:
    """Candidate corpora, with the bound computed on the number of INDEPENDENT cases.

    Three disclosures per row, because one of them was missing: `n_rows` counts what is in
    the files, `n_independent` counts what a bound may treat as a sample, and `basis` says
    whether each was opened or inferred. The first version multiplied three measured
    language files by a file listing and printed the product in a column labelled
    "measured", which flattered the bound by 51x: MASSIVE's 51 test files are translations
    of the same 2,974 utterances, so an automation rate estimated over them is a rate
    measured 2,974 ways, not 151,674 ways.
    """
    specs = (
        {"id": "feishu_zh",
         "unit": "unique labelled cases, each answered twice per backend over 3 repeats",
         "n_rows": None, "n_independent": feishu_unique_ids,
         "basis": "not scanned (no corpus on this machine)" if feishu_unique_ids is None
                  else "scanned from results/v1/{laya,jev}/raw.jsonl",
         "note": "the only corpus with real archived jev responses"},
        {"id": "massive_intent_per_language",
         "unit": "labelled decision rows (one utterance, one intent)",
         "n_rows": MASSIVE_ROWS_PER_LANGUAGE, "n_independent": MASSIVE_ROWS_PER_LANGUAGE,
         "basis": "test/%s.json.gz opened and counted" % ", ".join(MASSIVE_LANGUAGES_OPENED),
         "note": "each language file is a candidate Mondrian slice"},
        {"id": "massive_intent_all_languages",
         "unit": "(language, utterance) pairs -- NOT independent cases",
         "n_rows": MASSIVE_ROWS_PER_LANGUAGE * MASSIVE_LANGUAGES_TOTAL,
         "n_independent": MASSIVE_ROWS_PER_LANGUAGE,
         "basis": "%d of %d files opened; the rest counted from the repo listing, and the "
                  "rows are translations of the same utterances" % (
                      len(MASSIVE_LANGUAGES_OPENED), MASSIVE_LANGUAGES_TOTAL),
         "note": "Apache-2.0, ~3.2 MB total; the 51x is coverage, not sample size"},
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
        "Produced by `python -m autorate.cli snapshot` -- every number here is computed",
        "from the corpus or opened from a file, and the count basis is named per row.",
        "",
        "- corpus: `%s`" % d["source"],
        "- unique ids: **%d**   repeats: %s" % (d["unique_ids"], d["repeats"]),
        "- slice keys (families): %s" % ", ".join("`%s`" % f for f in d["families"]),
        "- label balance: %s" % d["label_counts"],
        "- upstream `audit.py` exit code: **%d** (interpreter `%s`)" % (
            d["upstream_audit_rc"], d["audit_interpreter"]),
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
    lines += ["", "Counts here are archive LINES per mode and backend, taken before any",
              "quarantine. The reader keeps only the lines whose probabilities close, so its",
              "own count can be smaller.", ""]
    for mode in MODES:
        present = sum(v for k, v in d["lines_by_mode_backend"].items() if k.startswith(mode + "/"))
        kept_n = kept.get(mode)
        if kept_n is None:
            lines.append("- %s: %d lines present, reader count not measured in this run"
                         % (mode, present))
        else:
            lines.append("- %s: **%d of %d** lines kept by the reader (%d quarantined)"
                         % (mode, kept_n, present, present - kept_n))
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
            "not opened" if o["n_independent"] is None else o["n_independent"],
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
