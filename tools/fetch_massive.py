"""Build-step tool for the pinned MASSIVE corpus (Plan C Task 1).

What this is: a fetcher that refuses to hand back bytes the pin does not describe, and a checker that
reports what a cache directory actually holds against what `data/massive_provenance.json` promises.
The pin is what lets a reader check this repository's numbers without trusting our download, so the
digest is compared before anything is written, and a fetch that cannot complete fails instead of
exiting 0 on a short list -- the first fetch loop here skipped `test/zh-TW.json.gz` and still returned
success, and that is the defect this module's contract exists to prevent.

Nothing here runs in `pytest`'s network path or in `autorate verify`: the suite drives the fetch
through the `transport` seam, which `_urlopen` only fills when no transport was passed. The pin's own
origin -- measured by hand on 2026-10-03 from a `datasets`-revision cache that is no longer on this
machine, and re-derived on 2026-10-05 by fetching all 51 shards from the pinned revision -- is stated
in the manifest's `provenance` block, not implied by this code.

Layout, so the failure modes are testable without a socket:
  resolve_url()      URL composition only, from the manifest's own `resolve_route` template
  require_manifest() the pin's promises about itself; a broken pin is refused before any I/O
  read_bytes()       redirect following (`curl -L` semantics) and HTTP failure reporting, no digests
  place()            digest comparison, then file placement -- a mismatch writes nothing
  fetch()            the completeness gate over all of it
  verify_provenance() what a cache directory holds, against what the pin promises; never downloads
  shared_id_set()    re-derives the `provenance.id_sets` claim from bytes on disk; never downloads
  _urlopen()         THE seam: the only function in this module that opens a socket, and it never
                     bypasses certificate verification

Exceptions, and the exit code each one gets. rc 1 is unreachable by construction -- and the
construction was tested against a live CDN on 2026-10-06, which is how `http.client.HTTPException`
joined the list: a truncated body raised `IncompleteRead`, that is neither an `OSError` nor a
`FetchError`, and it reached the shell as a traceback and exit 1:
  ManifestError  the pin file cannot be read, is not this schema, or disagrees with its own declared
                 totals -- our published numbers have no owner -> 4, the code the CLI already gives
                 `ArithmeticError` for the same defect (`autorate.inventory.massive_pin`)
  IntegrityError bytes arrived, or sit on disk, and are not the pinned bytes -> 3
  FetchError     the fetch or the check could not be completed: the host refused, a pinned path did
                 not come back, a redirect was abused, a cache is absent -> 4
Both refusals are `RuntimeError` subclasses, deliberately NOT `ValueError` ones, so no wider catch can
file a refusal under "the operator's input was wrong". argparse's own usage errors stay rc 2.

Exit codes, chosen so this tool never leaks rc 1 either: 0 did what was asked, 2 usage, 3 integrity
(bytes arrived but are not the pinned bytes), 4 could not complete (a path did not come back, the
cache is absent, the pin is broken, or the network refused).
"""
import argparse
import gzip
import hashlib
import http.client
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = ROOT / "data" / "massive_provenance.json"
SCHEMA_PREFIX = "autorate-massive-pin/"

TIMEOUT_S = 30.0
MAX_REDIRECTS = 20
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Anything else is not bytes. A 304 or a 5xx body would otherwise come back as if it were the file and
# reach `place()` as an empty or HTML payload; the digest catches that, but the status was a refusal.
SUCCESS_STATUSES = frozenset({200, 201, 202, 203, 206})
REQUIRED_MANIFEST_KEYS = ("schema", "resolve_route", "revision", "n_files", "rows_total",
                          "bytes_total", "files")
REQUIRED_ENTRY_KEYS = ("path", "sha256", "bytes", "rows")
# `gzip.decompress` raises a different family per way the body is wrong: BadGzipFile (OSError) for a
# plain file, EOFError for a truncated stream, zlib.error for a corrupt one, and `json.loads` adds
# ValueError for a body that gunzips but is not JSONL. Each is a finding about the bytes, so each is
# caught by name; an exception outside this tuple is a bug in this module and stays loud.
GZIP_FAILURES = (OSError, ValueError, EOFError, zlib.error)

EXIT_OK, EXIT_USAGE, EXIT_INTEGRITY, EXIT_INCOMPLETE = 0, 2, 3, 4


class FetchError(RuntimeError):
    """A fetch or check that did not complete. A refusal, so it must never be caught and dropped."""


class IntegrityError(FetchError):
    """Bytes came back, or sit on disk, and are not the bytes the pin describes."""


class ManifestError(RuntimeError):
    """The pin itself is unreadable, foreign, or disagrees with its own declared counts.

    Not a `FetchError`: a broken manifest is not a download that failed, and it is not the operator's
    usage error either. `main` maps it to the incomplete/drift code, which is what
    `autorate.inventory.massive_pin` already raises `ArithmeticError` for.
    """


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand 3xx responses back to `read_bytes`, which owns the hop, the way `curl -L` does.

    Leaving the hop to urllib would make the redirect path untestable and would drop the loop guard.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _urlopen(url):
    """The seam: the one line that opens a socket. TLS verification stays on -- there is no insecure path."""
    return urllib.request.build_opener(_NoRedirect()).open(url, timeout=TIMEOUT_S)


def load_manifest(path=None) -> dict:
    """The pin, as written down. A file that will not parse is a `ManifestError`, not a traceback."""
    manifest_path = PROVENANCE_PATH if path is None else Path(path)
    try:
        text = manifest_path.read_text()
    except OSError as exc:
        raise ManifestError("the pin %s could not be read: %s: %s"
                            % (manifest_path, type(exc).__name__, exc)) from exc
    try:
        return json.loads(text)
    except ValueError as exc:                              # json.JSONDecodeError is a ValueError
        raise ManifestError("the pin %s is not JSON: %s" % (manifest_path, exc)) from exc


def resolve_url(template: str, revision: str, rel_path: str) -> str:
    """Compose the raw-file URL from the manifest's own template. No socket, no guessing."""
    return template.replace("<rev>", revision).replace("<path>", rel_path.lstrip("/"))


def digest_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def count_rows(body: bytes) -> int:
    """Non-empty lines of the gzipped JSONL. Raises whatever a body that is not gzip deserves."""
    return sum(1 for line in gzip.decompress(body).splitlines() if line.strip())


def shard_ids(body: bytes, id_key: str):
    """(the id values of one shard, the reason it gave none). Reads rows, never trusts a count.

    The id-set claim is the one that makes 2,974 and not 151,674 the number a bound may sit on, so an
    empty result comes back as a reason rather than as a set: `set()` compared with `set()` is
    "identical", which would pass the very claim this function exists to test.
    """
    ids, missing_key = [], 0
    for line in gzip.decompress(body).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict) and isinstance(row.get(id_key), (str, int)):
            ids.append(str(row[id_key]))
        else:
            missing_key += 1
    if not ids:
        return set(), "no row carries a `%s` value (%d row(s) read)" % (id_key, missing_key)
    if missing_key:
        return set(), "%d row(s) of %d carry no `%s`" % (missing_key, missing_key + len(ids), id_key)
    return set(ids), None


def _tls_failure_hint(exc: BaseException) -> str:
    """Name the certificate mismatch as a possible cause, because on this network it is the usual one."""
    for candidate in (exc, getattr(exc, "reason", None)):
        if isinstance(candidate, ssl.SSLCertVerificationError):
            return ("certificate verification failed -- the presented certificate does not match the "
                    "host, which here has meant a TLS-intercepting device on the path. Verification is "
                    "not bypassed; a fetch that cannot verify is a fetch that failed.")
    return "the host did not answer"


def read_bytes(url: str, transport=None) -> bytes:
    """Follow redirects until bytes come back. Compares nothing and writes nothing -- that is `place()`.

    `transport` is the seam: pass a callable that takes a URL and returns an object with `.status`
    (or `.code`), `.headers` and `.read()`, or raises `urllib.error.HTTPError`, to exercise this
    without a network. Left as `None` it resolves `_urlopen` at call time, so a test can replace the
    socket itself rather than only the layer above it.
    """
    transport = _urlopen if transport is None else transport
    current = url
    visited = []
    while True:
        visited.append(current)
        try:
            response = transport(current)
            body = response.read()
            headers = response.headers
            status = getattr(response, "status", None)
            if status is None:
                status = getattr(response, "code", None)
        except urllib.error.HTTPError as exc:      # a 3xx reaches us this way when urllib is not auto-following
            body, headers, status = None, exc.headers, exc.code
        except http.client.HTTPException as exc:
            # Measured, not hypothetical: a CDN closed two of the 51 shards early on 2026-10-06 and
            # the resulting `IncompleteRead` was neither an OSError nor a FetchError, so it escaped
            # both clauses below and killed the process with a traceback and exit 1 -- the one exit
            # code this tool's contract says no reachable input produces.
            raise FetchError("the body of %s did not arrive complete: %s: %s"
                             % (current, type(exc).__name__, exc)) from exc
        except OSError as exc:
            raise FetchError("could not read %s: %s: %s"
                             % (current, type(exc).__name__, _tls_failure_hint(exc))) from exc
        try:
            status = int(status)
        except (TypeError, ValueError) as exc:
            raise FetchError("HTTP status %r for %s is not a status; refusing to guess what came back"
                             % (status, current)) from exc

        if status in REDIRECT_STATUSES:
            location = headers.get("Location") if headers is not None else None
            if not location:
                raise FetchError("HTTP %d for %s gave no Location to follow" % (status, current))
            current = urllib.parse.urljoin(current, location)
            if current in visited:
                raise FetchError("redirect loop back to %s from %s" % (current, url))
            if len(visited) > MAX_REDIRECTS:
                raise FetchError("gave up after %d redirects from %s" % (MAX_REDIRECTS, url))
            continue
        if status not in SUCCESS_STATUSES:
            raise FetchError("HTTP %d for %s: a pinned path that does not come back is a failure, "
                             "not a file to skip" % (status, current))
        return body


def place(dest, rel_path: str, body: bytes, entry: dict) -> Path:
    """Digest first, write second. On a mismatch nothing is created under `dest` at all."""
    digest = digest_of(body)
    if digest != entry["sha256"]:
        raise IntegrityError("%s: sha256 %s is not the pinned %s (%d B arrived, pin says %d B)"
                             % (rel_path, digest, entry["sha256"], len(body), entry["bytes"]))
    target = Path(dest) / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return target


def require_manifest(manifest: dict) -> dict:
    """Every promise the pin makes about itself, checked before anything is checked against it.

    `n_files` is the count's one owner: the 51 is pinned in the manifest and asserted by
    `tests/test_provenance.py`, not hardcoded again here, so an upstream change moves one number. A
    short or self-contradicting list may not be fetched or verified against, because either tool would
    then report a figure no reader can re-derive -- the O-6 defect, one layer down.

    Every way a manifest can be broken that this function detects is reported together, and no shape
    that reaches here is allowed to raise anything but `ManifestError`: the entries a caller will later
    index are all checked for the keys and types the indexing needs.
    """
    if not isinstance(manifest, dict):
        raise ManifestError("the pin is a %s, not an object, so its counts have no owner"
                            % type(manifest).__name__)
    schema = manifest.get("schema")
    if not isinstance(schema, str) or not schema.startswith(SCHEMA_PREFIX):
        raise ManifestError("this tool reads %s* pins; this one declares schema %r" % (SCHEMA_PREFIX, schema))
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            raise ManifestError("the pin declares no %r key, so nothing here can be checked against it" % key)
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise ManifestError("the pin's `files` is not a non-empty list; its counts have no owner")

    problems, seen, digests, rows = [], set(), set(), set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ManifestError("a `files` entry is a %s, not an object" % type(entry).__name__)
        for key in REQUIRED_ENTRY_KEYS:
            if key not in entry:
                raise ManifestError("entry %r carries no %r" % (entry.get("path", entry), key))
        rel_path = entry["path"]
        unsafe = (not isinstance(rel_path, str) or not rel_path or rel_path.startswith("/")
                  or "\x00" in rel_path)
        if not unsafe and ".." in Path(rel_path).parts:
            unsafe = True
        if unsafe:
            # Refused before the index: an absolute or escaping path would write outside the cache dir.
            problems.append("path %r is not a file inside the cache directory" % (rel_path,))
        elif rel_path in seen:
            problems.append("duplicate path %s" % rel_path)
        else:
            seen.add(rel_path)
        digest = entry["sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            problems.append("%s: sha256 %r is not 64 hex characters" % (rel_path, digest))
        elif digest in digests:
            problems.append("digest reused on %s: digests must be per file" % rel_path)
        else:
            digests.add(digest)
        for key in ("bytes", "rows"):
            if type(entry[key]) is not int or entry[key] < 1:
                problems.append("%s: %s %r is not a positive count" % (rel_path, key, entry[key]))
        if type(entry["rows"]) is int:
            rows.add(entry["rows"])

    declared = manifest["n_files"]
    if type(declared) is not int or declared != len(files):
        problems.append("n_files %r does not match the %d entries it describes" % (declared, len(files)))
    for key, want in (("rows_total", sum(e["rows"] for e in files if type(e["rows"]) is int)),
                      ("bytes_total", sum(e["bytes"] for e in files if type(e["bytes"]) is int))):
        if type(manifest[key]) is not int or manifest[key] != want:
            problems.append("%s %r is not the sum of the entries (%d)" % (key, manifest[key], want))
    if "distinct_row_counts" in manifest and manifest["distinct_row_counts"] != sorted(rows):
        problems.append("distinct_row_counts %r is not the set of the entries' rows %r"
                        % (manifest["distinct_row_counts"], sorted(rows)))
    if problems:
        raise ManifestError("the pin cannot be used as a reference: %s" % "; ".join(problems))
    return manifest


def fetch(revision: str, dest, manifest: dict | None = None, transport=None) -> list:
    """Fetch every file the manifest describes into `dest`, verifying each body before it is written.

    Refuses rather than half-succeeds: a path that does not come back is collected and the fetch then
    fails naming it, and the placed set must equal the pin's own list -- the 2026-10-03 loop that
    skipped one language and exited 0 is the defect this gate exists to catch. Only digest-verified
    bytes ever land in `dest`; a mismatch aborts at once, naming the verified subset that came before
    it rather than leaving the reader to discover what is in the directory.
    """
    manifest = require_manifest(load_manifest() if manifest is None else manifest)
    template = manifest["resolve_route"]
    transport = _urlopen if transport is None else transport
    entries = manifest["files"]
    placed, failures = [], []
    for entry in entries:
        rel_path = entry["path"]
        try:
            body = read_bytes(resolve_url(template, revision, rel_path), transport=transport)
        except FetchError as exc:
            failures.append("%s: %s" % (rel_path, exc))
            continue
        try:
            place(dest, rel_path, body, entry)
        except IntegrityError as exc:
            raise IntegrityError("%s -- aborted with %d of %d pinned files placed"
                                 % (exc, len(placed), manifest["n_files"])) from exc
        placed.append(rel_path)

    expected = manifest["n_files"]
    if len(placed) != expected or sorted(placed) != sorted(entry["path"] for entry in entries):
        short = [entry["path"] for entry in entries if entry["path"] not in set(placed)]
        raise FetchError("fetch placed %d of %d pinned files: a short fetch is a failed fetch, not a "
                         "partial success. Missing: %s%s"
                         % (len(placed), expected, ", ".join(short),
                            (" | " + "; ".join(failures)) if failures else ""))
    return placed


def verify_provenance(cache_dir, manifest: dict | None = None) -> dict:
    """Check what is on disk against what the manifest promises. Never downloads.

    A cache that is not there is reported as absent rather than raised: CI can and will run this
    against a corpus it does not have, and "nothing was checked because nothing is here" must not read
    as a pass or as a refutation of the pin either. Row counting is skipped once the digest disagrees
    -- counting rows of bytes that are not the pinned bytes would publish a second number about a file
    nobody should be quoting.
    """
    manifest = require_manifest(load_manifest() if manifest is None else manifest)
    cache = Path(cache_dir)
    cache_present = cache.is_dir()
    missing, mismatched, ok = [], [], 0
    for entry in manifest["files"]:
        path = cache / entry["path"]
        if not cache_present or not path.exists():
            missing.append(entry["path"])
            continue
        try:
            body = path.read_bytes()
        except OSError as exc:                       # a directory or an unreadable file is a finding
            mismatched.append({"path": entry["path"], "sha256_ok": False, "rows": None,
                               "rows_expected": entry["rows"],
                               "reason": "could not be read: %s: %s" % (type(exc).__name__, exc)})
            continue
        digest = digest_of(body)
        if digest != entry["sha256"]:
            mismatched.append({"path": entry["path"], "sha256_ok": False, "rows": None,
                               "rows_expected": entry["rows"], "reason": "sha256 is not the pinned sha256"})
            continue
        try:
            rows = count_rows(body)
        except GZIP_FAILURES as exc:      # digest-matched bytes that will not gunzip: a mismatch, not a crash
            mismatched.append({"path": entry["path"], "sha256_ok": True, "rows": None,
                               "rows_expected": entry["rows"],
                               "reason": "%s: %s" % (type(exc).__name__, exc)})
            continue
        if rows != entry["rows"]:
            mismatched.append({"path": entry["path"], "sha256_ok": True, "rows": rows,
                               "rows_expected": entry["rows"],
                               "reason": "row count is not the pinned count"})
        else:
            ok += 1
    return {"checked": len(manifest["files"]), "ok": ok, "missing": missing,
            "mismatched": mismatched, "cache_present": cache_present}


def shared_id_set(cache_dir, manifest: dict | None = None, id_key: str = "id") -> dict:
    """Re-derive the pin's `provenance.id_sets` claim from bytes on disk. Never downloads.

    `identical` is True only when every pinned shard was read, gunzipped and yielded the same non-empty
    id set; anything that stops the check makes it None rather than a vacuous True. `n_independent` is
    the size of that shared set and is the only number here a bound may sit on; `rows_total` is a row
    count.
    """
    manifest = require_manifest(load_manifest() if manifest is None else manifest)
    cache = Path(cache_dir)
    cache_present = cache.is_dir()
    sets, missing, unreadable = [], [], []
    for entry in manifest["files"]:
        path = cache / entry["path"]
        if not cache_present or not path.exists():
            missing.append(entry["path"])
            continue
        try:
            ids, reason = shard_ids(path.read_bytes(), id_key)
        except GZIP_FAILURES as exc:
            unreadable.append({"path": entry["path"], "reason": "%s: %s" % (type(exc).__name__, exc)})
            continue
        if reason:
            unreadable.append({"path": entry["path"], "reason": reason})
            continue
        sets.append(set(ids))

    complete = bool(cache_present) and not missing and not unreadable and len(sets) == len(manifest["files"])
    distinct = len({frozenset(s) for s in sets}) if complete else None
    union = set().union(*sets) if complete else None
    intersection = set(sets[0]).intersection(*sets[1:]) if complete else None
    identical = distinct == 1 if complete else None
    return {"cache_present": cache_present, "id_key": id_key, "shards": manifest["n_files"],
            "checked": len(sets), "identical": identical, "distinct_id_sets": distinct,
            "union_ids": None if union is None else len(union),
            "intersection_ids": None if intersection is None else len(intersection),
            "n_independent": None if not identical else len(union),
            "missing": missing, "unreadable": unreadable}


def _is_revision(value) -> bool:
    """A pinned revision is a git sha, and it is spliced into a URL path segment -- so check both."""
    return (isinstance(value, str) and 0 < len(value) <= 40
            and all(c in "0123456789abcdef" for c in value.lower()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.fetch_massive",
                                     description="Fetch or check the pinned MASSIVE corpus.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_url = sub.add_parser("url", help="print the exact pinned URL for one path (no network)")
    p_url.add_argument("path")
    p_url.add_argument("--revision", default=None)
    p_url.add_argument("--manifest", default=None)

    p_fetch = sub.add_parser("fetch", help="download every pinned file, verifying before writing")
    p_fetch.add_argument("--dest", required=True)
    p_fetch.add_argument("--revision", default=None)
    p_fetch.add_argument("--manifest", default=None)

    p_verify = sub.add_parser("verify", help="check a cache directory against the pin (never downloads)")
    p_verify.add_argument("--cache", required=True)
    p_verify.add_argument("--manifest", default=None)

    p_ids = sub.add_parser("ids", help="re-derive the shared-id-set claim from a cache (never downloads)")
    p_ids.add_argument("--cache", required=True)
    p_ids.add_argument("--manifest", default=None)
    p_ids.add_argument("--id-key", default="id")
    return parser


def _dispatch(args) -> int:
    manifest = require_manifest(load_manifest(args.manifest))
    if not _is_revision(manifest["revision"]):
        raise ManifestError("the pin's own revision %r is not a hex commit sha" % (manifest["revision"],))
    operator_gave_revision = getattr(args, "revision", None) is not None
    revision = args.revision if operator_gave_revision else manifest["revision"]
    if not _is_revision(revision):
        # Operator input, so this one is a usage error; the pinned value failing the same test above
        # is a data defect and goes to the drift code.
        print("usage: --revision must be a hex commit sha, not %r" % (revision,), file=sys.stderr)
        return EXIT_USAGE
    if operator_gave_revision:
        print("note: fetching revision %s, which is not the pinned %s -- the digests below will not "
              "match unless the tree is identical" % (revision, manifest["revision"]), file=sys.stderr)

    if args.command == "url":
        if args.path not in {entry["path"] for entry in manifest["files"]}:
            print("usage: %s is not a pinned path" % args.path, file=sys.stderr)
            return EXIT_USAGE
        print(resolve_url(manifest["resolve_route"], revision, args.path))
        return EXIT_OK
    if args.command == "fetch":
        placed = fetch(revision, Path(args.dest), manifest=manifest)
        print("fetched and verified %d files into %s" % (len(placed), args.dest))
        return EXIT_OK
    if args.command == "verify":
        report = verify_provenance(Path(args.cache), manifest)
        print(json.dumps(report, indent=2, sort_keys=True))
        if not report["cache_present"]:
            print("cache absent: nothing was checked, so nothing here verifies the pin", file=sys.stderr)
            return EXIT_INCOMPLETE
        if report["mismatched"]:
            return EXIT_INTEGRITY
        if report["missing"]:
            return EXIT_INCOMPLETE
        return EXIT_OK
    result = shared_id_set(Path(args.cache), manifest, id_key=args.id_key)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["identical"] is None:
        return EXIT_INCOMPLETE
    return EXIT_OK if result["identical"] else EXIT_INTEGRITY


def main(argv=None) -> int:
    """Map every reachable outcome onto 0 / 2 / 3 / 4. An rc 1 is an exception this tool failed to name.

    Every transport failure is converted to `FetchError` at the seam that sees it (`read_bytes`), so
    this map is deliberately short: a new exception class reaching here is a bug, and rc 1 says so.
    The order of the two clauses is the contract: `IntegrityError` is a `FetchError` subclass, so
    catching `FetchError` first would file "the bytes are not the pinned bytes" under "could not
    complete" and lose the distinction the exit codes exist to carry.
    """
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except IntegrityError as exc:
        print("INTEGRITY: %s" % exc, file=sys.stderr)
        return EXIT_INTEGRITY
    except (ManifestError, FetchError, OSError) as exc:
        print("COULD NOT COMPLETE: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_INCOMPLETE


if __name__ == "__main__":
    sys.exit(main())
