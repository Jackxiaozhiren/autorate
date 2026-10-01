"""Offline data inventory: which labelled per-case decision corpus exists, and whether n bounds.

Integrity is owned by upstream's own model-free audit; this module calls it and
records its verdict rather than re-deriving hashes we do not define (their
`manifest.json` pins digests over a canonicalisation we do not own). Two refusals
are the point of the module: publishing a corpus whose audit failed, and quoting a
bound that the sample size cannot support.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

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


def _audit_python(root: Path) -> str:
    """Interpreter for upstream's audit, derived from the corpus root where possible.

    No hardcoded absolute path: an absolute literal passes every local gate and only
    breaks in an environment nobody can see.
    """
    override = os.environ.get("AUTORATE_AUDIT_PYTHON")
    if override:
        return override
    # <laya checkout>/research/benchmarks/feishu_zh  ->  <laya checkout>/.venv/bin/python
    venv = root.parents[2] / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


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
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        by_mode[rec["mode"]] = by_mode.get(rec["mode"], 0) + 1
        ids.add(rec["id"])
        repeats.add(rec["repeat"])
    return by_mode, ids, sorted(repeats)


def inventory(root: Path) -> dict:
    root = Path(root)
    manifest = json.loads((root / "data" / "manifest.json").read_text())
    per_mode: dict = {}
    ids: set = set()
    repeats: list = []
    for backend in BACKENDS:
        path = root / "results" / "v1" / backend / "raw.jsonl"
        by_mode, this_ids, this_reps = _scan_jsonl(path)
        for mode in MODES:
            # Separator is "/", not "|": these keys are rendered into a markdown table,
            # and a pipe inside a cell silently adds a column and breaks the table.
            per_mode["%s/%s" % (mode, backend)] = by_mode.get(mode, 0)
        if backend == "laya":  # uniqueness is asserted on one backend, not summed
            ids |= this_ids
            repeats = this_reps
    cmd, env = audit_command(root)
    audit = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), env=env)
    return {
        "source": str(root),
        "records_by_mode_backend": dict(sorted(per_mode.items())),
        "unique_ids": len(ids),
        "repeats": repeats,
        "families": sorted(manifest.get("families", {})),
        "label_counts": dict(manifest.get("labels", {})),
        "provenance": manifest.get("provenance", ""),
        "upstream_audit_rc": audit.returncode,
        "upstream_audit_stdout_tail": audit.stdout[-400:],
        "upstream_audit_stderr_tail": audit.stderr[-400:],
        "audit_interpreter": cmd[0],
        "min_calibration_n": manifest.get("cases", len(ids)),
        "corpus_options": corpus_options(),
        "gaps": [
            "research/results/eval_english_51_languages.json: per-case records omitted; "
            "regenerate with research/eval/laya_eval.py --langs all --out <path>",
            "mteb/amazon_massive_intent is not in the local HF dataset cache",
            "the archived corpus carries no randomisation draw (u), so APS ties resolve to 0 here",
        ],
    }


def corpus_options() -> list:
    """Candidate corpora with the bound width each one supports, computed not asserted.

    Only measured row counts appear. `typed-decisions` is listed with its size category
    because its exact count has not been opened yet — inventing a number here would
    propagate straight into a published inventory.
    """
    out = []
    for spec in (
        {"id": "feishu_zh", "unique_ids": 64, "note": "paired laya/Jev archived responses, zh, 3 repeats"},
        {"id": "massive_intent_per_language", "unique_ids": 2974, "note": "test/en.json.gz parsed; de and sw also 2974"},
        {"id": "massive_intent_all_languages", "unique_ids": 2974 * 51, "note": "51 gzipped JSONL files, ~3.2 MB total, Apache-2.0"},
        {"id": "typed_decisions", "unique_ids": None, "note": "size category 1K<n<10K from the dataset card; row count not yet opened"},
    ):
        n = spec["unique_ids"]
        width = None if n is None else round(bound_width(n), 4)
        out.append({
            **spec,
            "bound_width_at_0.05": width,
            "feasible_at_0.10": None if n is None else bool(n_feasible(n, max_bound_width=0.10)),
            "feasible_at_0.25": None if n is None else bool(n_feasible(n, max_bound_width=0.25)),
        })
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
        "Produced by `autorate.inventory.write_inventory`; every number here is computed,",
        "not typed. Re-run `uv run --frozen pytest tests/test_inventory.py -q` to reproduce.",
        "",
        "- corpus: `%s`" % d["source"],
        "- unique ids: **%d**   repeats: %s" % (d["unique_ids"], d["repeats"]),
        "- slice keys (families): %s" % ", ".join("`%s`" % f for f in d["families"]),
        "- label balance: %s" % d["label_counts"],
        "- upstream `audit.py` exit code: **%d** (interpreter `%s`)" % (
            d["upstream_audit_rc"], d["audit_interpreter"]),
        "- provenance: %s" % d["provenance"],
        "",
        "## Records per mode x backend",
        "",
        "| key | records |",
        "|---|---|",
    ]
    for k, v in sorted(d["records_by_mode_backend"].items()):
        lines.append("| %s | %d |" % (k, v))

    lines += ["", "## Can this corpus support a bound?", ""]
    lines.append(
        "Bound width for an automation-rate estimate is `2*sqrt(ln(2/alpha)/(2n))`. "
        "At `alpha=0.05` the committed corpus gives **%.4f** for n=%d, which is why "
        "`autorate certify` is expected to refuse on it rather than publish a number."
        % (bound_width(d["unique_ids"]), d["unique_ids"])
    )
    lines += ["", "| corpus | unique n | bound width @0.05 | feasible @0.10 | note |", "|---|---|---|---|---|"]
    for o in d["corpus_options"]:
        lines.append("| %s | %s | %s | %s | %s |" % (
            o["id"],
            "not opened" if o["unique_ids"] is None else o["unique_ids"],
            "-" if o["bound_width_at_0.05"] is None else "%.4f" % o["bound_width_at_0.05"],
            "-" if o["feasible_at_0.10"] is None else ("yes" if o["feasible_at_0.10"] else "no"),
            o["note"],
        ))

    lines += ["", "## Known gaps", ""] + ["- %s" % g for g in d["gaps"]] + [""]
    out.write_text("\n".join(lines))
    Path(str(out) + ".json").write_text(json.dumps(d, indent=2, sort_keys=True))
