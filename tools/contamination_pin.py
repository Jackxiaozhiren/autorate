"""Pin upstream's per-suite benchmark results so the contamination gap can be re-derived offline.

The probe this feeds (``tools/contamination_probe.py``) has to answer in the corpus-absent lane, where no
file under the vendored checkout exists at all. So the numbers it needs -- ``n``, ``accuracy`` and the
``in_training`` declaration per suite and variant -- are extracted here, once, in the lane that can see the
corpus, and committed as ``data/pin_app_benchmark.json`` with the digest and byte length of the file they
came from. That is the same two-lane shape ``data/inventory.md.json`` already uses, and it carries the same
limit: in the corpus-absent lane the digest is transcribed, not recomputed, and the probe says so.

Exit codes follow the published contract: 0 on a written pin, 2 on a bad argument or a corpus file that is
present but does not answer, 4 when the corpus path cannot be read at all. Nothing escapes as 1.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RESULT_RELPATH = "research/results/app_benchmark_results.json"
PIN_PATH = "data/pin_app_benchmark.json"
PIN_PRODUCER = "tools/contamination_pin.py"
COUNT_KEYS = ("n", "accuracy")
ROW_FIELDS = ("variant", "suite", "n", "accuracy", "errors", "in_training", "pointer")


class PinRefusal(ValueError):
    """The corpus answered, but not in a shape the probe may publish."""


MARKER = Path("data") / "manifest.json"


def corpus_root() -> tuple:
    """(checkout root, how it was found), resolved exactly the way every other corpus path is.

    The environment, then the sibling default `cli._default_corpus` reaches; the corpus itself is the
    `feishu_zh` benchmark directory, so the checkout is three levels up. A path that has no
    `data/manifest.json` is not a corpus and is refused by name, because a pin built from a directory that
    merely exists would be a digest of nothing.
    """
    import os

    from autorate.cli import _default_corpus

    env = os.environ.get("AUTORATE_FEISHU_ROOT")
    if env:
        root, source = Path(env), "AUTORATE_FEISHU_ROOT"
    else:
        root, source = Path(_default_corpus()), "the sibling default"
    if not (root / MARKER).is_file():
        raise FileNotFoundError("%s (%s)" % (root, source))
    return root.parents[2], source


def _flag(variant: dict, pointer: str):
    """The variant's own declaration, or the one nested inside it -- named by where it was found."""
    if "in_training" in variant:
        return variant["in_training"], pointer
    for key, value in variant.items():
        if isinstance(value, dict) and "in_training" in value:
            return value["in_training"], "%s/%s" % (pointer, key)
    return None, pointer


def extract(doc: dict) -> tuple:
    """(rows, excluded): one row per usable (suite, variant), and a named census of the ones that are not."""
    rows, excluded = [], []
    suites = doc.get("suites")
    if not isinstance(suites, dict) or not suites:
        raise PinRefusal("the results file has no non-empty `suites` mapping to read strata from")
    for suite, variants in sorted(suites.items()):
        if not isinstance(variants, dict):
            raise PinRefusal("suite %r is not a mapping of variant to figures" % (suite,))
        for variant, figures in sorted(variants.items()):
            if not isinstance(figures, dict):
                raise PinRefusal("%s/%s is not a mapping of figures" % (suite, variant))
            pointer = "/suites/%s/%s" % (suite, variant)
            n, accuracy = figures.get("n"), figures.get("accuracy")
            if n is None and accuracy is None:
                continue
            flag, flag_pointer = _flag(figures, pointer)
            if n is None or accuracy is None:
                raise PinRefusal("%s: carries `n` or `accuracy` but not both" % pointer)
            if not isinstance(n, int) or isinstance(n, bool):
                raise PinRefusal("%s: `n` is %r, not a whole number of cases" % (pointer, n))
            if not isinstance(flag, bool):
                raise PinRefusal("%s: no `in_training` declaration was found (looked at %s), so the row "
                                 "belongs to neither stratum" % (pointer, flag_pointer))
            correct = accuracy * n
            if abs(correct - round(correct)) > 1e-9:
                # A rounded aggregate cannot become a count, and inventing one would move the stratum's
                # denominator. The row is set aside with the reason, so the probe publishes a census of what
                # it could not use instead of quietly dividing by a smaller total.
                excluded.append({"pointer": pointer, "n": n, "accuracy": accuracy,
                                 "reason": "accuracy x n is not a whole number of cases"})
                continue
            # `accuracy` counts the right answers, so the probe's numerator is what is LEFT after them.
            # Reading the product as the error count would have inverted the sign of the gap it publishes.
            errors = n - int(round(correct))
            rows.append({"suite": suite, "variant": variant, "n": n, "accuracy": accuracy,
                         "errors": int(round(errors)), "in_training": flag, "pointer": flag_pointer})
    if not rows:
        raise PinRefusal("no (suite, variant) row carried a count, a rate and a declaration")
    for row in rows:
        if set(row) != set(ROW_FIELDS):
            raise PinRefusal("a pinned row carries %s, not the fields the probe reads (%s)"
                             % (sorted(row), sorted(ROW_FIELDS)))
    return rows, excluded


def build(root: Path) -> dict:
    path = root / RESULT_RELPATH
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    rows, excluded = extract(doc)
    return {"producer": PIN_PRODUCER,
            "excluded": excluded,
            "source": {"path": RESULT_RELPATH, "sha256": hashlib.sha256(raw).hexdigest(),
                       "bytes": len(raw),
                       "lane_note": "recomputed by `autorate verify` only in the corpus-present lane; "
                                    "transcribed from these bytes when the corpus is absent"},
            "rows": rows}


def main(argv=None) -> int:
    from autorate.cli import EXIT_CERTIFIED, EXIT_DRIFT, EXIT_USAGE

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    force = "--force" in argv
    if out is None:
        sys.stderr.write("USAGE: contamination_pin.py --out %s --force\n" % PIN_PATH)
        return EXIT_USAGE
    if str(out) != PIN_PATH and not force:
        sys.stderr.write("USAGE: the pin is a published file; --out %s names another path, and `verify` "
                         "reads %s. Pass --force only for a scratch run.\n" % (out, PIN_PATH))
        return EXIT_USAGE
    try:
        root, _source = corpus_root()
        doc = build(root)
    except FileNotFoundError as missing:
        sys.stderr.write("PUBLISHED ARTEFACT UNAVAILABLE: no corpus was found at %s, so %s cannot be "
                         "re-pinned. Run this in the corpus-present lane.\n" % (missing, PIN_PATH))
        return EXIT_DRIFT
    except (PinRefusal, json.JSONDecodeError) as problem:
        sys.stderr.write("PIN REFUSED: %s\nNothing was written.\n" % problem)
        return EXIT_USAGE

    text = json.dumps(doc, sort_keys=True, indent=2) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    in_rows = [r for r in doc["rows"] if r["in_training"]]
    out_rows = [r for r in doc["rows"] if not r["in_training"]]
    print("pinned %d rows from %s (digest %s): %d in-training over %d cases, %d held-out over %d cases"
          % (len(doc["rows"]), RESULT_RELPATH, doc["source"]["sha256"][:12],
             len(in_rows), sum(r["n"] for r in in_rows),
             len(out_rows), sum(r["n"] for r in out_rows)))
    if doc["excluded"]:
        print("  excluded %d row(s) whose aggregate rate is not a whole number of cases: %s"
              % (len(doc["excluded"]), ", ".join(r["pointer"] for r in doc["excluded"])))
    return EXIT_CERTIFIED


if __name__ == "__main__":
    sys.exit(main())
