"""Split one scored artefact into per-language committed records, and PROVE the split is a partition.

    uv run --frozen python3 tools/split_records.py --in <records.jsonl> --out-dir data

The scored artefact this tool splits -- 8,922 rows over `en, de, sw` -- is a build product that
lives outside this repository, under a build cache and passed in as `--in`. It is deliberately not
named as a path here: the first copy of it was destroyed by a reboot, which is why no published
number may depend on reading it. The certificates
published under `data/` have to be re-derivable from bytes that live in this repository, so the
file has to be split and committed, and a split done by an ad-hoc shell pipeline would leave
`verify` unable to say where its inputs came from. This file is the owner of that step: it names
the producer of `data/records_massive_<lang>.jsonl`, and the claims it prints are the claims
`tests/test_split_records.py` plants defects against.

Three claims, in the order the brief asks for them:

    the multiset of `id`s across the files equals the multiset in the source
    no `id` appears twice
    every file's row count is stated

The first is not enough on its own, and that is the interesting part. Swap two lines between the
`en` file and the `de` file and the multisets still agree, no id repeats, and the per-file counts
are unchanged -- only a checker that re-derives each line's language from the line's own
`case_id` says the row is in the wrong file. So `check_written` reads the files back off disk and
re-derives everything, instead of trusting what it just wrote.

The lines are MOVED, not re-serialized. Every source row is already the scoring driver's canonical
form (`tools/build_records.py:1131` -- `json.dumps(rec, sort_keys=True)`), and the certificate is
a function of the doubles those bytes decode to, so a rewrite that reflowed a float or unescaped a
German umlaut would silently move a published bound. The tool therefore refuses a row that is not
canonical, that is blank, that is not a JSON object, or that the repository's own `Record`
contract will not read: a committed artefact is checked against the contract its consumer applies,
not against a paraphrase of it.

Two refusals are shape, not luck:
* a row whose `id` and `case_id` name different languages is one row with two subjects, and which
  file a reader would open depends on which field they believe;
* a `records_massive_<lang>.jsonl` already in the destination for a language the source does not
  carry is a leftover of an earlier split, and publishing beside it would put a file nothing
  produced into the evidence set.

Exit codes, and the class that reaches each. rc 1 is unreachable by construction: every failure
this tool can name has a class and every class has a clause.

    UsageRefusal (ValueError)      an input that is not there, an out-dir that is a file -> 2
    PartitionError (RuntimeError)  the source cannot be partitioned as proved -> 3
    WrittenDrift (ArithmeticError) what is on disk is not the partition that was justified -> 4
    OSError                        could not read or write -> 4

Stdlib and `autorate.records` only: this is the build side of the repository, and it must stay
runnable in an environment that has no torch and no model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Script mode (`python3 tools/split_records.py`) puts `tools/` on sys.path and not the repo
    # root; pytest's `pythonpath = ["."]` already puts it there, which makes this a no-op on the
    # test path. Same reason the sibling driver carries the same four lines.
    sys.path.insert(0, str(ROOT))

from autorate.records import Record

# The import sits below the sys.path insert because `tools/` is not a package on the script path:
# run as a script, this file imports the repository the same way its sibling driver imports
# `tools.fetch_massive`. The rule set CI selects (E9,F63,F7,F82,F401,F811) does not police import
# position, so this is a layout note rather than a lint exemption -- and the file carries no `noqa`.

EXIT_OK, EXIT_USAGE, EXIT_NOT_CERTIFIABLE, EXIT_DRIFT = 0, 2, 3, 4

CASE_HEAD = "massive"
DEFAULT_NAME_FORMAT = "records_massive_{lang}.jsonl"
# The sentence the published inventory uses to name the producer of its inputs. Kept as data so
# `inventory.py` quotes the same string this file prints, rather than restating it and giving the
# provenance two owners.
OWNER_SENTENCE = "split by `case_id` from one scored artefact by tools/split_records.py"
# `massive/<lang>/<index>`; the language is a segment, not a length, because MASSIVE carries both
# two- and three-letter codes and a `..` here would refuse a real shard.
_LANG_RX = re.compile(r"^[a-z][a-z0-9]*$")


class UsageRefusal(ValueError):
    """The operator's command is not executable: no input, a destination that is not a directory."""


class PartitionError(RuntimeError):
    """The source cannot be partitioned as this tool claims to. A refusal about the evidence -> 3."""


class WrittenDrift(ArithmeticError):
    """The bytes on disk are not the partition that was justified -- a published figure with no
    producer, which is what `main` already maps to the drift exit code."""


def split_owner() -> str:
    """The one owner of the sentence that names this tool. See `OWNER_SENTENCE`."""
    return OWNER_SENTENCE


def case_language(case_id: str) -> str:
    """The language segment of `massive/<lang>/<index>`, refusing anything else.

    Routing is done on `case_id` because that is the identity the certifier's split uses
    (`case_count.case_key`), so the field that decides the file is the field that decides the
    case -- a row that routes by one and groups by the other would put one case in two
    certificates.
    """
    parts = str(case_id).split("/")
    if len(parts) != 3 or parts[0] != CASE_HEAD or not _LANG_RX.match(parts[1] or "") \
            or not parts[2].isdigit():
        raise PartitionError("case_id %r is not `%s/<lang>/<index>`: this row cannot be routed "
                             "to a language file" % (case_id, CASE_HEAD))
    return parts[1]


def _segments(identifier: str) -> list:
    return str(identifier).split("/")


def _route_one(raw: str, number: int) -> tuple:
    """One source line -> (decoded row, language), or a `PartitionError` naming the line.

    Every check is a claim about the artefact this repository is about to commit, so each one is
    reported with its line number and, where the row states one, its id.
    """
    if not raw.strip():
        raise PartitionError("line %d is blank: a committed records file has exactly one canonical "
                             "record per line, and `load_records` would skip this one in silence"
                             % number)
    try:
        row = json.loads(raw)
    except ValueError as exc:
        raise PartitionError("line %d is not a canonical record line (%s)" % (number, exc)) from exc
    if not isinstance(row, dict):
        raise PartitionError("line %d is not a canonical record line: it decodes to a JSON %s, not "
                             "an object, and a committed record line is a mapping"
                             % (number, type(row).__name__))
    if json.dumps(row, sort_keys=True) != raw:
        raise PartitionError("line %d is not the producer's canonical form (sorted keys, "
                             "default escaping): it was edited after it was written, and the "
                             "certificate would be a function of bytes nobody can reproduce"
                             % number)
    try:
        Record.from_dict(row)
    except ValueError as exc:
        raise PartitionError("line %d is not a record the repository's own contract reads (%s)"
                             % (number, exc)) from exc
    lang = case_language(row["case_id"])
    # The row carries three statements of which language it belongs to. They have to agree, or the
    # file name, the case and the slice disagree about the subject of a certified number.
    id_parts = _segments(row["id"])
    if len(id_parts) < 3 or id_parts[1] != lang:
        raise PartitionError("line %d: id %r names language %r while its case_id %r names %r -- "
                             "one row cannot be two languages"
                             % (number, row["id"], id_parts[1] if len(id_parts) > 1 else None,
                                row["case_id"], lang))
    declared = (row.get("slices") or {}).get("language")
    if declared is not None and declared != lang:
        raise PartitionError("line %d: slices.language %r disagrees with the language its case_id "
                             "%r routes it to" % (number, declared, row["case_id"]))
    return row, lang


def route_lines(lines: Sequence[str]) -> tuple:
    """Partition the given lines by language and state the claims about the result.

    Returns `(per_language_lines, claims)`. The multiset comparison is computed from the routed
    lines against the source rather than assumed from the routing loop, so a defect in this
    function -- a line dropped on the way in, a line written twice -- is caught by the same
    numbers `check_written` reports about the artefacts on disk.
    """
    per_lang: dict = {}
    ids: list = []
    for number, raw in enumerate(lines, 1):
        row, lang = _route_one(raw, number)
        per_lang.setdefault(lang, []).append(raw)
        ids.append(row["id"])
    duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise PartitionError("an id appears twice in the source (%d id(s) do: %s); a partition of a "
                             "repeated id would publish one case in two certificates"
                             % (len(duplicates), _naming(duplicates)))
    routed_ids = [json.loads(raw)["id"] for rows in per_lang.values() for raw in rows]
    # Re-derive every routed line's language from the line's own `case_id` and compare it with the
    # bucket it was placed under. The loop above cannot misroute a line today, so this is not a
    # check that can fire on the current code: it is what makes `misrouted_lines` a measurement
    # rather than a literal, and it is the same statement `check_written` proves about the bytes on
    # disk. An empty list here therefore means "re-derived and agreed", not "never looked".
    misrouted = []
    for lang, rows in sorted(per_lang.items()):
        for raw in rows:
            row = json.loads(raw)
            if case_language(row["case_id"]) != lang:
                misrouted.append("%s (placed under %r)" % (row["id"], lang))
    claims = {
        "source_rows": len(lines),
        "languages": sorted(per_lang),
        "per_file_rows": {lang: len(rows) for lang, rows in sorted(per_lang.items())},
        "duplicate_ids": duplicates,
        "multiset_equal": Counter(routed_ids) == Counter(ids),
        "missing_ids": sorted((Counter(ids) - Counter(routed_ids)).elements()),
        "extra_ids": sorted((Counter(routed_ids) - Counter(ids)).elements()),
        "misrouted_lines": misrouted,
    }
    if not claims["multiset_equal"]:
        raise PartitionError("the routed lines are not the source's lines: missing %s, extra %s"
                            % (_naming(claims["missing_ids"]), _naming(claims["extra_ids"])))
    if misrouted:
        raise PartitionError("%d line(s) sit in a language bucket their own `case_id` does not "
                             "name (%s): the file a reader would open and the case the certifier "
                             "groups by would disagree"
                             % (len(misrouted), "; ".join(misrouted[:6])))
    return per_lang, claims


def _naming(ids: Sequence[str], limit: int = 6) -> str:
    """A list of ids an operator can act on, with the truncation declared."""
    shown = ", ".join(repr(i) for i in list(ids)[:limit])
    return "(%s%s)" % (shown, "; ..." if len(ids) > limit else "")


def rows_phrase(counts: dict) -> str:
    """One owner for the third claim: `de 2, en 3` for every file this partition covers.

    Both the write and the `--check` arm print it, so the sentence that states each file's row count
    has one shape in this tool rather than two that a reader has to reconcile.
    """
    return ", ".join("%s %d" % (lang, counts[lang]) for lang in sorted(counts))


def name_for(lang: str, name_format: str = DEFAULT_NAME_FORMAT) -> str:
    """The file a language's rows go to, as a bare name -- the caller supplies the directory."""
    if "{lang}" not in name_format:
        raise UsageRefusal("--name-format %r has no `{lang}` slot, so every language would be "
                           "written to the same file" % name_format)
    name = name_format.format(lang=lang)
    if "/" in name or name != Path(name).name:
        raise UsageRefusal("--name-format %r would write outside --out-dir (%r); the directory is "
                           "named by --out-dir and by nothing else" % (name_format, name))
    return name


def _name_pattern(name_format: str) -> re.Pattern:
    """The set of file names this tool owns in the destination, for the leftover scan."""
    if "{lang}" not in name_format:
        raise UsageRefusal("--name-format %r has no `{lang}` slot" % name_format)
    head, _, tail = name_format.partition("{lang}")
    return re.compile(r"^%s([a-z][a-z0-9]*)%s$" % (re.escape(head), re.escape(tail)))


def _existing_owned(out_dir: Path, name_format: str) -> dict:
    """{language: path} for every file in `out_dir` this tool would consider its own output."""
    pattern = _name_pattern(name_format)
    found = {}
    for path in sorted(out_dir.iterdir()) if out_dir.is_dir() else []:
        match = pattern.match(path.name)
        if match:
            found[match.group(1)] = path
    return found


def plan(source_path: Path) -> tuple:
    """Read the source and route it, returning `(lines, per_language_lines, claims)`."""
    source_path = Path(source_path)
    lines = source_path.read_text().splitlines()
    per_lang, claims = route_lines(lines)
    return lines, per_lang, claims


def write_split(source_path: Path, out_dir: Path,
                name_format: str = DEFAULT_NAME_FORMAT) -> dict:
    """Write the partition, then prove it from the bytes on disk. Refuses to write what it cannot prove.

    Returns the summary: the claims from the plan, plus the file names, row counts and sha256 of
    what was written. Nothing here is inferred from the writer's own memory -- `check_written`
    re-reads the files it names.
    """
    source_path, out_dir = Path(source_path), Path(out_dir)
    if not source_path.is_file():
        raise UsageRefusal("--in %s is not a file" % source_path)
    if out_dir.exists() and not out_dir.is_dir():
        raise UsageRefusal("--out-dir %s exists and is not a directory" % out_dir)
    _, per_lang, claims = plan(source_path)
    if out_dir.is_dir():
        leftovers = sorted(set(_existing_owned(out_dir, name_format)) - set(per_lang))
        if leftovers:
            raise PartitionError(
                "%s already carry the language(s) %s, which this source does not: an artefact of "
                "an earlier split would be published beside the certificates as part of this "
                "partition" % (out_dir, ", ".join(
                    "%s (`%s`)" % (lang, name_for(lang, name_format)) for lang in leftovers)))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for lang, rows in sorted(per_lang.items()):
        path = out_dir / name_for(lang, name_format)
        path.write_text("".join(row + "\n" for row in rows))
        written[lang] = {"path": str(path), "rows": len(rows),
                         "bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    checked = check_written(source_path, out_dir, name_format)
    return {"source": str(source_path), "out_dir": str(out_dir), "claims": claims,
            "written": written, "checked": checked}


def check_written(source_path: Path, out_dir: Path,
                  name_format: str = DEFAULT_NAME_FORMAT) -> dict:
    """Re-derive the partition from the files on disk and compare it with the source's.

    The findings are collected rather than raised at the first difference, so one run names every
    defect a tamper left -- and a reader fixing a corrupted artefact does not have to rediscover
    them one at a time.
    """
    source_path, out_dir = Path(source_path), Path(out_dir)
    if not source_path.is_file():
        raise UsageRefusal("--in %s is not a file" % source_path)
    if not out_dir.is_dir():
        raise UsageRefusal("--out-dir %s is not a directory" % out_dir)
    _, per_lang, claims = plan(source_path)
    found = _existing_owned(out_dir, name_format)
    findings = []
    for lang in sorted(set(per_lang) - set(found)):
        findings.append("no file for language %r: `%s` is missing, so the partition does not cover "
                        "the %d rows it claims" % (lang, name_for(lang, name_format),
                                                   len(per_lang[lang])))
    for lang in sorted(set(found) - set(per_lang)):
        findings.append("`%s` holds language %r, which this source carries no rows for"
                        % (found[lang].name, lang))
    read_ids: list = []
    counts = {}
    for lang, path in sorted(found.items()):
        rows = path.read_text().splitlines()
        counts[lang] = len(rows)
        if lang not in per_lang:
            continue
        for number, raw in enumerate(rows, 1):
            row, line_lang = _route_one(raw, number)
            read_ids.append(row["id"])
            if line_lang != lang:
                findings.append("`%s` line %d: id %r is routed by its own case_id to %r, not to "
                                "the file it sits in" % (path.name, number, row["id"], line_lang))
    if Counter(read_ids) != Counter(json.loads(raw)["id"] for raw in
                                    source_path.read_text().splitlines()):
        missing = sorted((Counter(json.loads(r)["id"] for r in source_path.read_text().splitlines())
                          - Counter(read_ids)).elements())
        extra = sorted((Counter(read_ids) - Counter(
            json.loads(r)["id"] for r in source_path.read_text().splitlines())).elements())
        findings.append("the ids across the files (%d rows over %s) are not the source's ids "
                        "(%d rows): missing %s, extra %s" % (
                            len(read_ids), ", ".join("%s=%d" % kv for kv in sorted(counts.items())),
                            claims["source_rows"], _naming(missing), _naming(extra)))
    if findings:
        raise WrittenDrift("%d defect(s) in the written partition: %s"
                           % (len(findings), " | ".join(findings)))
    return {"per_file_rows": counts, "multiset_equal": True,
            "duplicate_ids": [], "source_rows": claims["source_rows"]}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="split_records", description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="source", required=True,
                    help="the scored artefact to split (a path you pass; never a default)")
    ap.add_argument("--out-dir", dest="out_dir", required=True,
                    help="the directory to write the per-language files into")
    ap.add_argument("--name-format", dest="name_format", default=DEFAULT_NAME_FORMAT,
                    help="file name template; must carry `{lang}` (default %s)"
                         % DEFAULT_NAME_FORMAT)
    ap.add_argument("--check", action="store_true",
                    help="re-derive and compare the files that are already there; write nothing")
    return ap


def main(argv=None) -> int:
    """Map every reachable outcome onto 0 / 2 / 3 / 4. An rc 1 is a failure this tool did not name."""
    args = build_parser().parse_args(argv)
    try:
        if args.check:
            checked = check_written(Path(args.source), Path(args.out_dir), args.name_format)
            print("checked %s: %s (partition proved: ids equal the source's, no id twice, "
                  "each line in the file its own case_id names)"
                  % (args.out_dir, rows_phrase(checked["per_file_rows"])))
            return EXIT_OK
        summary = write_split(Path(args.source), Path(args.out_dir), args.name_format)
        claims = summary["claims"]
        for lang, info in sorted(summary["written"].items()):
            print("wrote %s: %d rows, %d bytes, sha256 %s"
                  % (info["path"], info["rows"], info["bytes"], info["sha256"]))
        print("per-file rows: %s" % rows_phrase(claims["per_file_rows"]))
        print("source rows %d, languages %d (%s), partition proved"
              % (claims["source_rows"], len(claims["languages"]), ", ".join(claims["languages"])))
        return EXIT_OK
    except UsageRefusal as exc:
        print("USAGE: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except PartitionError as exc:
        print("NOT CERTIFIABLE: %s" % exc, file=sys.stderr)
        return EXIT_NOT_CERTIFIABLE
    except (WrittenDrift, OSError) as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
