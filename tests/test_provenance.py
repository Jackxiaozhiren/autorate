"""Task 1 (Plan C): the pinned MASSIVE corpus is checkable without trusting our download.

Two rules govern this whole file. (1) Nothing here touches the network: every byte-dependent check
runs against a cache planted in `tmp_path`, and an autouse fixture below replaces the module's socket
seam with a raiser so an accidental real request is a red test rather than a slow one. (2) Every
planted digest comes from `hashlib` in this file, never from `data/massive_provenance.json` -- a check
that compared the wrong field would still pass if both sides were the pinned constant.

The structure checks read the committed pin and must never skip; the one test that re-derives the
pinned numbers from real bytes is gated on a cache directory this repository does not carry, and
`test_the_skip_marker_is_the_cache_gate_and_nothing_else` polices that no other test hides behind it.
"""
import gzip
import hashlib
import json
import os
import sys
import urllib.error
from pathlib import Path

import pytest

import tools.fetch_massive as fetch_massive
from tools.fetch_massive import (FetchError, IntegrityError, ManifestError, fetch, main, resolve_url,
                                shared_id_set, verify_provenance)

PIN_PATH = Path(__file__).resolve().parents[1] / "data" / "massive_provenance.json"
REPO = PIN_PATH.parents[1]
CI_WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

# The house pattern for "needs data that is not in this repository" (tests/test_reader_feishu.py:31):
# key on one thing, name that thing in the reason, and never use it to hide a failure.
CACHE_ENV = os.environ.get("AUTORATE_MASSIVE_CACHE")
CACHE_DIR = Path(CACHE_ENV) if CACHE_ENV else None
cache_gated = pytest.mark.skipif(
    CACHE_DIR is None or not CACHE_DIR.is_dir(),
    reason="the 51 pinned shards are not vendored: this test re-hashes the real bytes, so it keys on "
           "AUTORATE_MASSIVE_CACHE naming an existing directory (it does not now)")

PIN_SHA = "0123456789abcdef" * 2 + "0123"           # a 40-hex revision, planted, never fetched
ROUTE = "https://datasets.example.invalid/datasets/test/dataset/resolve/<rev>/<path>"
SHARDS = ("test/aa.json.gz", "test/bb.json.gz", "test/cc.json.gz")

# The tests that must run on a machine with no corpus at all. A3 forbids a broad skip quietly
# swallowing them; `test_the_skip_marker_is_the_cache_gate_and_nothing_else` is the guard.
NEVER_SKIPS = (
    "test_the_manifest_is_self_describing_and_complete",
    "test_every_language_shares_the_same_item_ids",
    "test_the_pin_states_how_its_digests_were_obtained",
    "test_the_committed_pin_is_readable_by_the_tool_that_fetches_it",
    "test_every_pinned_path_resolves_under_the_pinned_revision",
    "test_the_pinned_manifest_against_an_empty_cache_reports_the_whole_list_missing",
    "test_a_planted_cache_that_matches_the_pin_passes",
    "test_the_transport_seam_is_the_only_way_to_a_socket",
    "test_main_exit_codes_are_only_ever_zero_two_three_or_four",
    "test_ci_polices_the_tools_root_this_file_imports",
)


# --------------------------------------------------------------------------- helpers

def sha(body: bytes) -> str:
    """The digest of planted bytes, computed here. Never `entry["sha256"]` copied from the pin."""
    return hashlib.sha256(body).hexdigest()


def jsonl_shard(ids, prefix="utterance") -> bytes:
    """A gzipped JSONL shard -- the shape the pinned paths have -- carrying `id` values."""
    body = "".join(json.dumps({"id": i, "text": "%s %s" % (prefix, i)}) + "\n" for i in ids)
    return gzip.compress(body.encode("utf-8"))


def shard_bodies(ids_by_shard):
    """Distinct bytes per shard, which is what the pin's "digests must be per file" rule requires.

    Three shards of identical text would share a digest and be refused before any test reached the
    behaviour it planted, so the shard's own path is in every row.
    """
    return {path: jsonl_shard(ids, prefix=path) for path, ids in ids_by_shard.items()}


def count(body: bytes) -> int:
    """Rows of a planted body, via the module's own failure taxonomy, so a broken body yields 0 here."""
    try:
        return sum(1 for line in gzip.decompress(body).splitlines() if line.strip())
    except fetch_massive.GZIP_FAILURES:
        return 0


def planted_manifest(bodies, **override):
    """A pin list built from `{rel_path: body}`, self-consistent by construction.

    `rows_total`, `bytes_total`, `n_files` and `distinct_row_counts` are derived from the entries, so
    the only way a test can plant a disagreement is to ask for one in `override` or after the call.
    """
    files = [{"path": path, "lang": path.rsplit("/", 1)[-1], "sha256": sha(body),
              "bytes": len(body), "rows": count(body) or 1}
             for path, body in sorted(bodies.items())]
    manifest = {
        "schema": "autorate-massive-pin/1", "dataset": "test/dataset", "license": "Apache-2.0",
        "revision": PIN_SHA, "resolve_route": ROUTE, "files": files,
        "n_files": len(files), "rows_total": sum(f["rows"] for f in files),
        "bytes_total": sum(f["bytes"] for f in files),
        "distinct_row_counts": sorted({f["rows"] for f in files}),
    }
    manifest.update(override)
    return manifest


def write_manifest(root, manifest) -> Path:
    path = Path(root) / "planted_provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest))
    return path


def plant(root, ids_by_shard=None):
    """Write three real `.json.gz` shards and return the cache and the manifest describing those bytes."""
    ids_by_shard = ids_by_shard or {p: ["u%d" % i for i in range(7)] for p in SHARDS}
    bodies = shard_bodies(ids_by_shard)
    cache = Path(root) / "cache"
    for path, body in bodies.items():
        target = cache / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return cache, planted_manifest(bodies)


class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self._body, self.status, self.headers = body, status, headers if headers is not None else {}

    def read(self):
        return self._body


def fake_transport(pages, calls=None):
    """A stand-in for `_urlopen`: keyed by exact URL, records what it was asked for.

    A URL that is not in `pages` answers 404, because a pinned path that does not come back is the
    defect this module's fetch contract exists to catch.
    """
    def transport(url):
        if calls is not None:
            calls.append(url)
        page = pages.get(url)
        if page is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return page if isinstance(page, FakeResponse) else FakeResponse(page)
    return transport


def url_of(rel_path, revision=PIN_SHA):
    return resolve_url(ROUTE, revision, rel_path)


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch):
    """A3: every test in this file runs offline. Reaching the network here is a bug, not a slow test.

    Tests that want the seam monkeypatch their own fake over this one; nothing may get a real socket.
    """
    def _blocked(*args, **kwargs):
        raise AssertionError("a provenance test reached the network")

    monkeypatch.setattr(fetch_massive, "_urlopen", _blocked)


def independent_cases(pin: dict) -> int:
    """What a bound may sit on, derived from the fields the pin owns.

    The plan writes this figure as `pin["independent_cases"]`. The committed pin carries no such key
    and `data/**` is not this task's file to edit (named as a handoff in the task report), so it is
    derived here from the three fields that determine it: one distinct row count, `n_files` shards,
    and a `rows_total` that is their product.
    """
    counts = pin["distinct_row_counts"]
    assert isinstance(counts, list) and len(counts) == 1, \
        "several row counts per shard means no single independent-case number exists"
    assert pin["n_files"] * counts[0] == pin["rows_total"], "rows_total is not n_shards x rows_per_shard"
    return counts[0]


# --------------------------------------------------------------------------- the committed pin

def test_the_manifest_is_self_describing_and_complete():
    d = json.loads(PIN_PATH.read_text())
    assert d["n_files"] == len(d["files"]) == 51, d["n_files"]
    assert d["revision"] == "940fd47a81eaa7f2cc7b129674d945d618ac38c2"
    assert {f["rows"] for f in d["files"]} == {2974}, "row counts drifted from the measured value"
    assert d["rows_total"] == sum(f["rows"] for f in d["files"])


def test_every_language_shares_the_same_item_ids():
    """The 51 files are translations of one 2,974-item set, not 51 samples (R-36)."""
    d = json.loads(PIN_PATH.read_text())
    assert len({f["sha256"] for f in d["files"]}) == 51, "digests must be per file"
    assert independent_cases(d) == 2974
    assert d["rows_total"] == 51 * 2974, "151,674 is a row count, never an n"


def test_the_pin_states_how_its_digests_were_obtained():
    """A1: a committed manifest whose origin is unstated is a number with no owner.

    Checked as fields plus the two words that carry the limit: the bytes are `not vendored`, so
    `reverified_on` is the only thing standing between this file and a claim nobody can re-derive.
    """
    d = json.loads(PIN_PATH.read_text())
    prov = d["provenance"]
    for key in ("first_recorded", "reverified_on", "method", "agreement", "transport_note",
                "id_sets", "bytes_retained"):
        assert isinstance(prov.get(key), str) and prov[key], "provenance.%s is missing or empty" % key
    assert "not vendored" in prov["bytes_retained"], prov["bytes_retained"]
    assert prov["agreement"].startswith("51 of 51"), prov["agreement"]
    assert str(d["n_files"]) in prov["id_sets"] and str(independent_cases(d)) in prov["id_sets"], \
        prov["id_sets"]
    # The template is what lets a reader with a network and no trust re-derive the digests.
    assert "<rev>" in d["resolve_route"] and "<path>" in d["resolve_route"], d["resolve_route"]
    assert d["resolve_route"].startswith("https://"), "a pin whose bytes are fetched over a plain scheme"
    assert d["license"] == "Apache-2.0" and d["dataset"] == "mteb/amazon_massive_intent"
    assert str(Path.home()) not in PIN_PATH.read_text(), "the pin names a machine"


def test_the_committed_pin_is_readable_by_the_tool_that_fetches_it():
    """The planted fixtures below only prove the validator if the real pin survives it too.

    Without this arm a validator that accepted a shape the committed file does not have would let every
    `verify_provenance` test pass while the inventory's own consumer disagreed about the same file.
    """
    assert fetch_massive.PROVENANCE_PATH == PIN_PATH, "the tool reads a different pin than the repo ships"
    manifest = fetch_massive.require_manifest(fetch_massive.load_manifest())
    assert manifest["schema"] == "autorate-massive-pin/1"
    assert len(manifest["files"]) == 51
    assert fetch_massive.load_manifest() == json.loads(PIN_PATH.read_text()), \
        "the loader is not reading the committed file"


def test_every_pinned_path_resolves_under_the_pinned_revision():
    manifest = fetch_massive.load_manifest()
    urls = [resolve_url(manifest["resolve_route"], manifest["revision"], f["path"])
            for f in manifest["files"]]
    assert len(set(urls)) == 51, urls
    for url, entry in zip(urls, manifest["files"]):
        assert url.endswith("/" + entry["path"]), url
        assert manifest["revision"] in url and url.startswith("https://"), url


def test_the_pinned_manifest_against_an_empty_cache_reports_the_whole_list_missing(tmp_path):
    """CI runs this against a corpus CI does not have: absent must be said, not failed or passed."""
    report = verify_provenance(tmp_path, fetch_massive.load_manifest())
    assert report["checked"] == 51 and report["ok"] == 0
    assert len(report["missing"]) == 51 and report["mismatched"] == []
    assert report["cache_present"] is True            # the directory exists; the shards do not


def test_the_pinned_manifest_against_an_absent_cache_says_so(tmp_path):
    report = verify_provenance(tmp_path / "no-such-cache", fetch_massive.load_manifest())
    assert report["cache_present"] is False and report["ok"] == 0
    assert len(report["missing"]) == 51 and report["checked"] == 51


# --------------------------------------------------------------------------- planted caches

def test_a_planted_cache_that_matches_the_pin_passes(tmp_path):
    cache, manifest = plant(tmp_path)
    report = verify_provenance(cache, manifest)
    assert report["cache_present"] is True
    assert (report["checked"], report["ok"]) == (3, 3), report
    assert report["missing"] == [] and report["mismatched"] == []


def test_a_missing_shard_is_reported_missing_not_counted_as_a_pass(tmp_path):
    cache, manifest = plant(tmp_path)
    (cache / "test/bb.json.gz").unlink()
    report = verify_provenance(cache, manifest)
    assert report["missing"] == ["test/bb.json.gz"], report
    assert report["ok"] == 2 and report["checked"] == 3
    assert report["mismatched"] == [], "an absent file is not a contradiction of the pin"


def test_a_wrong_digest_is_named_and_its_rows_are_not_published(tmp_path):
    cache, manifest = plant(tmp_path)
    (cache / "test/aa.json.gz").write_bytes(jsonl_shard(["other"], prefix="test/aa.json.gz"))
    report = verify_provenance(cache, manifest)
    assert [m["path"] for m in report["mismatched"]] == ["test/aa.json.gz"], report
    entry = report["mismatched"][0]
    assert entry["sha256_ok"] is False and entry["rows"] is None, entry
    assert entry["rows_expected"] == manifest["files"][0]["rows"]
    assert report["ok"] == 2


def test_a_truncated_body_fails_on_digest_before_any_row_count(tmp_path):
    cache, manifest = plant(tmp_path)
    body = (cache / "test/cc.json.gz").read_bytes()
    (cache / "test/cc.json.gz").write_bytes(body[: len(body) // 2])
    report = verify_provenance(cache, manifest)
    assert [m["path"] for m in report["mismatched"]] == ["test/cc.json.gz"], report
    assert report["mismatched"][0]["sha256_ok"] is False


def test_a_plain_body_under_a_gz_name_is_a_mismatch_not_a_crash(tmp_path):
    """The gzipped-vs-plain arm: the digest can match while the container is wrong."""
    dirpath = tmp_path / "cache" / "test"
    dirpath.mkdir(parents=True)
    body = b'{"id": "u0", "text": "plain, not gzipped"}\n'
    (dirpath / "aa.json.gz").write_bytes(body)
    report = verify_provenance(tmp_path / "cache", planted_manifest({"test/aa.json.gz": body}))
    assert report["ok"] == 0, report
    assert report["mismatched"][0]["sha256_ok"] is True, "the digest is of exactly these bytes"
    assert "BadGzipFile" in report["mismatched"][0]["reason"], report["mismatched"]


def test_a_truncated_gzip_stream_is_a_mismatch_not_a_crash(tmp_path):
    dirpath = tmp_path / "cache" / "test"
    dirpath.mkdir(parents=True)
    body = jsonl_shard(["u%d" % i for i in range(40)])[:30]
    (dirpath / "aa.json.gz").write_bytes(body)
    report = verify_provenance(tmp_path / "cache", planted_manifest({"test/aa.json.gz": body}))
    assert report["ok"] == 0 and report["mismatched"], report
    assert "EOFError" in report["mismatched"][0]["reason"], report


def test_a_corrupt_deflate_stream_is_a_mismatch_not_a_crash(tmp_path):
    dirpath = tmp_path / "cache" / "test"
    dirpath.mkdir(parents=True)
    good = jsonl_shard(["u%d" % i for i in range(40)])
    body = good[:14] + b"\xff" * 6 + good[20:]
    (dirpath / "aa.json.gz").write_bytes(body)
    report = verify_provenance(tmp_path / "cache", planted_manifest({"test/aa.json.gz": body}))
    assert report["ok"] == 0 and report["mismatched"], report
    assert report["mismatched"][0]["sha256_ok"] is True, report
    # `zlib.error`'s class name is `error`; naming it is what says the failure was caught, not raised.
    assert report["mismatched"][0]["reason"].split(":", 1)[0] == "error", report


def test_a_digest_matched_shard_with_the_wrong_row_count_is_reported(tmp_path):
    cache, manifest = plant(tmp_path)
    # Re-describe one shard with a row count its bytes do not carry, leaving its digest correct.
    entry = [f for f in manifest["files"] if f["path"] == "test/bb.json.gz"][0]
    entry["rows"] = entry["rows"] + 1
    manifest["rows_total"] = sum(f["rows"] for f in manifest["files"])
    manifest["distinct_row_counts"] = sorted({f["rows"] for f in manifest["files"]})
    report = verify_provenance(cache, manifest)
    assert [m["path"] for m in report["mismatched"]] == ["test/bb.json.gz"], report
    wrong = report["mismatched"][0]
    assert wrong["sha256_ok"] is True and wrong["rows"] == 7 and wrong["rows_expected"] == 8, wrong
    assert wrong["reason"] == "row count is not the pinned count", wrong


def test_a_directory_where_a_shard_should_be_is_reported_not_raised(tmp_path):
    cache, manifest = plant(tmp_path)
    path = cache / "test/aa.json.gz"
    path.unlink()
    path.mkdir()
    report = verify_provenance(cache, manifest)
    assert [m["path"] for m in report["mismatched"]] == ["test/aa.json.gz"], report
    assert "IsADirectoryError" in report["mismatched"][0]["reason"], report


def test_the_verify_report_carries_the_keys_the_plan_names(tmp_path):
    """The plan's return shape is the interface a reader of this repository expects."""
    cache, manifest = plant(tmp_path)
    (cache / "test/aa.json.gz").write_bytes(jsonl_shard(["x"], prefix="test/aa.json.gz"))
    report = verify_provenance(cache, manifest)
    assert {"checked", "ok", "missing", "mismatched", "cache_present"} == set(report), report
    assert {"path", "sha256_ok", "rows"} <= set(report["mismatched"][0]), report["mismatched"]
    assert report["checked"] == len(manifest["files"]) == 3


# --------------------------------------------------------------------------- the fetcher's seam

def test_the_transport_seam_is_the_only_way_to_a_socket(monkeypatch, tmp_path):
    """A7: `fetch` is exercised through the seam and `_urlopen` is never reached.

    The autouse fixture already refuses a real socket; this asserts the seam was asked for exactly one
    URL per pinned path, so a pass arm cannot be green because nothing was fetched at all.
    """
    bodies = shard_bodies({p: ["u%d" % i for i in range(3)] for p in SHARDS})
    manifest = planted_manifest(bodies)
    calls = []
    monkeypatch.setattr(fetch_massive, "_urlopen",
                        lambda *a, **k: pytest.fail("_urlopen must not be reached by an offline test"))
    transport = fake_transport({url_of(p): b for p, b in bodies.items()}, calls=calls)
    placed = fetch(PIN_SHA, tmp_path / "dest", manifest=manifest, transport=transport)
    assert placed == sorted(SHARDS), placed
    assert calls == sorted(url_of(p) for p in SHARDS), calls


def test_a_fetch_places_every_pinned_file_and_then_verifies(monkeypatch, tmp_path):
    """The default transport is the module-level seam, resolved at call time -- so this patches it."""
    bodies = shard_bodies({p: ["u%d" % i for i in range(3)] for p in SHARDS})
    manifest = planted_manifest(bodies)
    monkeypatch.setattr(fetch_massive, "_urlopen",
                        fake_transport({url_of(p): b for p, b in bodies.items()}))
    dest = tmp_path / "dest"
    assert fetch(PIN_SHA, dest, manifest=manifest) == sorted(SHARDS)
    assert verify_provenance(dest, manifest)["ok"] == 3, "placed bytes must survive their own pin"
    for path in SHARDS:
        assert (dest / path).read_bytes() == bodies[path]


def test_a_mismatched_digest_raises_and_writes_nothing(monkeypatch, tmp_path):
    """A7's required arm: bytes the pin does not describe must never reach `dest`."""
    bodies = shard_bodies({p: ["u%d" % i for i in range(3)] for p in SHARDS})
    manifest = planted_manifest(bodies)
    pages = {url_of(SHARDS[0]): jsonl_shard(["tampered"], prefix="rejected")}
    monkeypatch.setattr(fetch_massive, "_urlopen", fake_transport(pages))
    dest = tmp_path / "dest"
    with pytest.raises(IntegrityError, match="is not the pinned"):
        fetch(PIN_SHA, dest, manifest=manifest)
    assert not dest.exists(), "a rejected body was written to disk anyway"


def test_the_integrity_abort_names_what_it_already_placed(monkeypatch, tmp_path):
    bodies = shard_bodies({p: ["u%d" % i for i in range(3)] for p in SHARDS})
    manifest = planted_manifest(bodies)
    pages = {url_of(SHARDS[0]): bodies[SHARDS[0]],
             url_of(SHARDS[1]): jsonl_shard(["nope"], prefix="rejected")}
    monkeypatch.setattr(fetch_massive, "_urlopen", fake_transport(pages))
    dest = tmp_path / "dest"
    with pytest.raises(IntegrityError, match="aborted with 1 of 3 pinned files placed"):
        fetch(PIN_SHA, dest, manifest=manifest)
    assert (dest / SHARDS[0]).exists()
    assert not (dest / SHARDS[1]).exists()


def test_a_short_fetch_names_the_missing_path_and_refuses_to_succeed(monkeypatch, tmp_path):
    """The 2026-10-03 defect: the loop skipped one language and exited 0."""
    bodies = shard_bodies({p: ["u%d" % i for i in range(3)] for p in SHARDS})
    manifest = planted_manifest(bodies)
    pages = {url_of(p): b for p, b in bodies.items()}
    pages.pop(url_of("test/bb.json.gz"))                    # that pinned path does not come back
    monkeypatch.setattr(fetch_massive, "_urlopen", fake_transport(pages))
    dest = tmp_path / "dest"
    with pytest.raises(FetchError, match="placed 2 of 3 pinned files") as exc:
        fetch(PIN_SHA, dest, manifest=manifest)
    assert "test/bb.json.gz" in str(exc.value), exc.value
    assert (dest / "test/bb.json.gz").exists() is False
    assert (dest / "test/aa.json.gz").read_bytes() == bodies["test/aa.json.gz"]


def test_a_manifest_with_a_short_list_is_refused_before_any_socket(tmp_path):
    """The same hole from the other side: fetching a 50-entry list would place 50 and report success.

    `n_files` is what the completeness gate counts against, so a list one entry shorter than its own
    declared count must never reach the transport at all.
    """
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}))
    manifest["files"] = manifest["files"][:-1]              # n_files stays 3
    calls = []
    with pytest.raises(ManifestError, match="n_files"):
        fetch(PIN_SHA, tmp_path / "dest", manifest=manifest,
              transport=fake_transport({}, calls=calls))
    assert calls == [], "the transport was reached with a manifest that had already been refused"


def test_redirects_are_followed_until_bytes_arrive(tmp_path):
    body = jsonl_shard(["u0", "u1"])
    first = url_of("test/aa.json.gz")
    cdn = "https://cdn.example.invalid/940fd47/test/aa.json.gz"
    final = first + "?final=1"
    pages = {first: FakeResponse(b"", 302, {"Location": cdn}),
             cdn: FakeResponse(b"", 303, {"Location": final}),
             final: FakeResponse(body)}
    calls = []
    assert fetch_massive.read_bytes(first, transport=fake_transport(pages, calls=calls)) == body
    assert calls == [first, cdn, final], calls


def test_a_relative_redirect_location_is_resolved_against_the_current_url(tmp_path):
    first = url_of("test/aa.json.gz")
    body = jsonl_shard(["u0"], prefix="mirror")
    mirror = ("https://datasets.example.invalid/datasets/test/dataset/resolve/%s/mirror/aa.json.gz"
              % PIN_SHA)
    pages = {first: FakeResponse(b"", 301, {"Location": "../mirror/aa.json.gz"}), mirror: body}
    assert fetch_massive.read_bytes(first, transport=fake_transport(pages)) == body


def test_a_redirect_without_a_location_is_a_failure():
    url = url_of("test/aa.json.gz")
    with pytest.raises(FetchError, match="gave no Location"):
        fetch_massive.read_bytes(url, transport=fake_transport({url: FakeResponse(b"", 307, {})}))


def test_a_redirect_loop_is_a_failure():
    a, b = url_of("test/aa.json.gz"), url_of("test/bb.json.gz")
    pages = {a: FakeResponse(b"", 302, {"Location": b}), b: FakeResponse(b"", 302, {"Location": a})}
    with pytest.raises(FetchError, match="redirect loop"):
        fetch_massive.read_bytes(a, transport=fake_transport(pages))


def test_too_many_redirects_is_a_failure():
    start = url_of("test/aa.json.gz")

    def hop(index):
        return start if index == 0 else "%s?hop=%d" % (start, index)

    pages = {hop(i): FakeResponse(b"", 302, {"Location": hop(i + 1)})
             for i in range(fetch_massive.MAX_REDIRECTS + 3)}
    with pytest.raises(FetchError, match="gave up after"):
        fetch_massive.read_bytes(start, transport=fake_transport(pages))


@pytest.mark.parametrize("status", [304, 401, 403, 429, 500, 503])
def test_a_status_that_is_not_bytes_is_refused_rather_than_returned(status):
    """A 304 or a 5xx body would otherwise reach `place()` as if it were the pinned file."""
    url = url_of("test/aa.json.gz")
    with pytest.raises(FetchError, match="does not come back"):
        fetch_massive.read_bytes(url,
                                 transport=fake_transport({url: FakeResponse(b"<!doctype html>", status)}))


def test_a_response_without_a_status_is_refused_not_guessed():
    class NoStatus:
        headers = {}

        def read(self):
            return b""

    with pytest.raises(FetchError, match="is not a status"):
        fetch_massive.read_bytes(url_of("test/aa.json.gz"), transport=lambda url: NoStatus())


def test_a_tls_verification_failure_names_the_certificate_and_stays_a_refusal():
    """A2: on this network the usual failure is an intercepting device. Verification is never bypassed."""
    inner = fetch_massive.ssl.SSLCertVerificationError(
        1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: host name not certificate")

    def transport(_url):
        raise urllib.error.URLError(inner)

    with pytest.raises(FetchError) as exc:
        fetch_massive.read_bytes(url_of("test/aa.json.gz"), transport=transport)
    message = str(exc.value)
    assert "certificate verification failed" in message, message
    assert "not bypassed" in message, message
    for forbidden in ("--insecure", "verify=False", "without verification"):
        assert forbidden not in message, message


def test_a_host_that_simply_did_not_answer_is_named_as_that():
    def transport(_url):
        raise OSError("no route to host")

    with pytest.raises(FetchError, match="the host did not answer") as exc:
        fetch_massive.read_bytes(url_of("test/aa.json.gz"), transport=transport)
    assert type(exc.value) is FetchError, "a plain socket failure must not read as an integrity finding"


def test_the_redirect_handler_refuses_to_let_urllib_own_the_hop():
    """`_NoRedirect` is what keeps the hop testable; if it ever returned a request, the seam is a lie."""
    handler = fetch_massive._NoRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, url_of("test/aa.json.gz")) is None


# --------------------------------------------------------------------------- manifest refusals

@pytest.mark.parametrize("mutate,expect", [
    (lambda m: m.update(n_files=2), "n_files"),
    (lambda m: m.update(rows_total=1), "rows_total"),
    (lambda m: m.update(bytes_total=m["bytes_total"] + 1), "bytes_total"),
    (lambda m: m.update(distinct_row_counts=[1, 2]), "distinct_row_counts"),
])
def test_a_manifest_that_disagrees_with_its_own_totals_is_refused(mutate, expect):
    """The three guards `autorate.inventory.massive_pin` raises `ArithmeticError` for, plus one.

    A refusal here is what keeps a published total from surviving underneath an edited list.
    """
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}))
    mutate(manifest)
    with pytest.raises(ManifestError, match=expect):
        fetch_massive.require_manifest(manifest)


def test_a_reused_digest_or_duplicate_path_is_refused():
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}))
    manifest["files"][1]["sha256"] = manifest["files"][0]["sha256"]
    with pytest.raises(ManifestError, match="digests must be per file"):
        fetch_massive.require_manifest(manifest)

    manifest = planted_manifest(shard_bodies({p: ["u%d" % i] for i, p in enumerate(SHARDS)}))
    manifest["files"][1]["path"] = manifest["files"][0]["path"]
    with pytest.raises(ManifestError, match="duplicate path"):
        fetch_massive.require_manifest(manifest)


@pytest.mark.parametrize("bad_path", ["/etc/passwd", "../outside.json.gz", "test/../../x.json.gz", ""])
def test_a_path_that_is_not_inside_the_cache_directory_is_refused(bad_path):
    """A manifest is data, and `place()` splices its paths onto `dest`."""
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}))
    manifest["files"][0]["path"] = bad_path
    with pytest.raises(ManifestError, match="not a file inside the cache directory"):
        fetch_massive.require_manifest(manifest)


@pytest.mark.parametrize("document,expect", [
    ("{not json at all", "is not JSON"),
    ("[1, 2, 3]", "not an object"),
    ('{"schema": "other-tool/9"}', "reads autorate-massive-pin"),
    ('{"schema": "autorate-massive-pin/1"}', "declares no 'resolve_route'"),
    ('{"schema": "autorate-massive-pin/1", "resolve_route": "x", "revision": "' + PIN_SHA + '"}',
     "declares no 'n_files'"),
])
def test_a_pin_that_cannot_be_read_is_refused_without_a_traceback(tmp_path, document, expect):
    path = tmp_path / "pin.json"
    path.write_text(document)
    with pytest.raises(ManifestError, match=expect):
        fetch_massive.require_manifest(fetch_massive.load_manifest(path))
    with pytest.raises(ManifestError, match="could not be read"):
        fetch_massive.require_manifest(fetch_massive.load_manifest(tmp_path / "absent.json"))


def test_entries_the_code_would_index_are_checked_before_anything_indexes_them():
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}))
    for mutate, expect in (
        (lambda m: m["files"][0].pop("rows"), "carries no 'rows'"),
        (lambda m: m["files"][0].update(sha256="deadbeef"), "not 64 hex characters"),
        (lambda m: m["files"][0].update(bytes="60"), "is not a positive count"),
        (lambda m: m["files"][0].update(rows=0), "is not a positive count"),
        (lambda m: m.update(files=["test/aa.json.gz"]), "not an object"),
        (lambda m: m.update(files=[]), "not a non-empty list"),
    ):
        broken = json.loads(json.dumps(manifest))
        mutate(broken)
        with pytest.raises(ManifestError, match=expect):
            fetch_massive.require_manifest(broken)


def test_a_pinned_revision_that_is_not_a_sha_is_a_data_defect_not_a_usage_error(tmp_path):
    manifest = planted_manifest(shard_bodies({p: ["u0"] for p in SHARDS}), revision="main-line")
    path = write_manifest(tmp_path, manifest)
    assert main(["url", "test/aa.json.gz", "--manifest", str(path)]) == 4


# --------------------------------------------------------------------------- the id-set claim

def test_planted_shards_that_share_one_id_set_report_one_independent_count(tmp_path):
    ids = ["u%d" % i for i in range(11)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    result = shared_id_set(cache, manifest)
    assert result["identical"] is True, result
    assert result["distinct_id_sets"] == 1 and result["checked"] == 3
    assert result["union_ids"] == result["intersection_ids"] == result["n_independent"] == 11
    assert result["n_independent"] != manifest["rows_total"], "a row count is not an n"


def test_planted_shards_with_a_drifted_id_set_are_not_reported_identical(tmp_path):
    ids = ["u%d" % i for i in range(11)]
    per_shard = {p: list(ids) for p in SHARDS}
    per_shard["test/cc.json.gz"] = ids[:-1] + ["zz-extra"]
    cache, manifest = plant(tmp_path, per_shard)
    result = shared_id_set(cache, manifest)
    assert result["identical"] is False, result
    assert result["distinct_id_sets"] == 2 and result["n_independent"] is None
    assert result["union_ids"] == 12 and result["intersection_ids"] == 10, result


def test_an_unreadable_id_field_stops_the_claim_instead_of_vacuously_passing(tmp_path):
    ids = ["u%d" % i for i in range(5)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    (cache / "test/bb.json.gz").write_bytes(gzip.compress(b'{"text": "no id here"}\n'))
    result = shared_id_set(cache, manifest)
    assert result["identical"] is None, result
    assert result["n_independent"] is None
    assert [u["path"] for u in result["unreadable"]] == ["test/bb.json.gz"], result
    assert "`id`" in result["unreadable"][0]["reason"], result


def test_a_shard_that_is_not_gzipped_stops_the_id_claim_too(tmp_path):
    ids = ["u%d" % i for i in range(5)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    (cache / "test/bb.json.gz").write_bytes(b'{"id": "u0"}\n')
    result = shared_id_set(cache, manifest)
    assert result["identical"] is None and result["checked"] == 2, result
    assert "BadGzipFile" in result["unreadable"][0]["reason"], result


def test_a_partial_cache_never_claims_the_id_sets_are_identical(tmp_path):
    ids = ["u%d" % i for i in range(5)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    (cache / "test/cc.json.gz").unlink()
    result = shared_id_set(cache, manifest)
    assert result["identical"] is None and result["n_independent"] is None
    assert result["missing"] == ["test/cc.json.gz"], result
    assert result["checked"] == 2 and result["shards"] == 3


def test_an_absent_cache_reports_nothing_and_claims_nothing(tmp_path):
    ids = ["u%d" % i for i in range(5)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    result = shared_id_set(tmp_path / "not-a-cache", manifest)
    assert result["cache_present"] is False and result["identical"] is None
    assert result["checked"] == 0 and len(result["missing"]) == 3


def test_the_id_key_is_a_named_assumption_not_a_guess(tmp_path):
    ids = ["u%d" % i for i in range(4)]
    cache, manifest = plant(tmp_path, {p: list(ids) for p in SHARDS})
    assert shared_id_set(cache, manifest)["identical"] is True
    asked_elsewhere = shared_id_set(cache, manifest, id_key="utterance_id")
    assert asked_elsewhere["identical"] is None, asked_elsewhere
    assert len(asked_elsewhere["unreadable"]) == 3, asked_elsewhere


# --------------------------------------------------------------------------- exit codes

def _arm(root, name, mutate_cache=None):
    """A planted cache plus the pin file that describes the bytes it was built with."""
    cache, manifest = plant(Path(root) / name)
    if mutate_cache:
        mutate_cache(cache)
    return cache, write_manifest(Path(root) / name, manifest)


def test_main_exit_codes_are_only_ever_zero_two_three_or_four(monkeypatch, tmp_path):
    """The contract sweep for this tool: rc 1 stays unreachable, and no data defect is a usage error.

    Each arm is a reachable input -- bad usage, a broken pin, an absent or partial cache, a cache that
    contradicts the pin, and a fetch whose bytes do not match. Exit codes are asserted exactly, so an
    arm that would silently return 1 is named before it can hide.
    """
    cache, manifest = plant(tmp_path / "good")
    good_pin = write_manifest(tmp_path / "good", manifest)
    served = {url_of(p): (cache / p).read_bytes() for p in SHARDS}
    monkeypatch.setattr(fetch_massive, "_urlopen", fake_transport(served))

    wrong_sha = json.loads(json.dumps(manifest))
    wrong_sha["files"][0]["sha256"] = sha(b"bytes nobody pinned")
    disagreeing = json.loads(json.dumps(manifest))
    disagreeing["rows_total"] += 1
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json")

    tampered, tampered_pin = _arm(tmp_path, "tampered", mutate_cache=lambda c: (
        c / "test/aa.json.gz").write_bytes(jsonl_shard(["nope"], prefix="tampered")))
    partial, partial_pin = _arm(tmp_path, "partial",
                                mutate_cache=lambda c: (c / "test/bb.json.gz").unlink())
    drifted, drifted_pin = _arm(tmp_path, "drifted", mutate_cache=lambda c: (
        c / "test/cc.json.gz").write_bytes(jsonl_shard(["u0", "u1", "elsewhere"], prefix="drifted")))

    arms = [
        (0, ["url", "test/aa.json.gz", "--manifest", str(good_pin)]),
        (2, ["url", "test/zz.json.gz", "--manifest", str(good_pin)]),
        (2, ["url", "test/aa.json.gz", "--revision", "not-a-sha", "--manifest", str(good_pin)]),
        (2, ["url", "test/aa.json.gz", "--revision", "../elsewhere", "--manifest", str(good_pin)]),
        (0, ["fetch", "--dest", str(tmp_path / "fetched"), "--manifest", str(good_pin)]),
        (3, ["fetch", "--dest", str(tmp_path / "rejected-dest"),
             "--manifest", str(write_manifest(tmp_path / "wrongsha", wrong_sha))]),
        (4, ["fetch", "--dest", str(tmp_path / "otherrev"), "--revision", "deadbeef",
             "--manifest", str(good_pin)]),
        (4, ["fetch", "--dest", str(tmp_path / "corrupt"), "--manifest", str(corrupt)]),
        (4, ["fetch", "--dest", str(tmp_path / "nothere"), "--manifest", str(tmp_path / "absent.json")]),
        (0, ["verify", "--cache", str(cache), "--manifest", str(good_pin)]),
        (3, ["verify", "--cache", str(tampered), "--manifest", str(tampered_pin)]),
        (4, ["verify", "--cache", str(partial), "--manifest", str(partial_pin)]),
        (4, ["verify", "--cache", str(tmp_path / "no-cache"), "--manifest", str(good_pin)]),
        (4, ["verify", "--cache", str(cache), "--manifest", str(corrupt)]),
        (4, ["verify", "--cache", str(cache),
             "--manifest", str(write_manifest(tmp_path / "disagree", disagreeing))]),
        (0, ["ids", "--cache", str(cache), "--manifest", str(good_pin)]),
        (3, ["ids", "--cache", str(drifted), "--manifest", str(drifted_pin)]),
        (4, ["ids", "--cache", str(partial), "--manifest", str(partial_pin)]),
        (4, ["ids", "--cache", str(cache), "--manifest", str(good_pin), "--id-key", "utterance_id"]),
    ]
    for want, argv in arms:
        code = main(argv)
        assert code == want, (argv, "got rc %r, wanted %r" % (code, want))
        assert code != 1, argv
    assert len(arms) >= 15, "a sweep this small would not cover the reachable outcomes"
    assert (tmp_path / "fetched" / "test/aa.json.gz").read_bytes() == (cache / "test/aa.json.gz").read_bytes()
    assert not (tmp_path / "rejected-dest").exists(), "a rejected fetch placed bytes"
    assert (tmp_path / "otherrev").exists() is False


def test_main_refuses_usage_rather_than_traceback_for_no_command():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2, exc.value.code


def test_main_refuses_a_fetch_without_a_destination():
    with pytest.raises(SystemExit) as exc:
        main(["fetch"])
    assert exc.value.code == 2, exc.value.code


def test_the_pinned_url_is_printed_from_the_pin_and_nothing_else(capsys):
    """A reader with no trust gets the exact URL the pin describes, composed by this tool."""
    manifest = fetch_massive.load_manifest()
    assert main(["url", "test/zh-TW.json.gz"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == resolve_url(manifest["resolve_route"], manifest["revision"], "test/zh-TW.json.gz")
    assert "<rev>" not in out and "<path>" not in out, out
    assert out.startswith("https://") and out.endswith("/test/zh-TW.json.gz"), out


def test_main_reports_an_absent_cache_as_four_and_says_why(tmp_path, capsys):
    assert main(["verify", "--cache", str(tmp_path / "nothing-here")]) == 4
    assert "nothing was checked" in capsys.readouterr().err, "an unchecked pin must not read as a pass"


# --------------------------------------------------------------------------- the guard on this file

def test_the_skip_marker_is_the_cache_gate_and_nothing_else():
    """A3: the manifest-only checks must run everywhere, so no skip may reach them.

    Asserted over this module's own test objects rather than over a run: a module-level or
    class-level skip is invisible to the tests it silences.
    """
    module = sys.modules[__name__]
    skipped = set()
    for name, obj in vars(module).items():
        if not name.startswith("test_") or not callable(obj):
            continue
        marks = [m.name for m in getattr(obj, "pytestmark", [])]
        if "skip" in marks or "skipif" in marks:
            skipped.add(name)
    assert skipped == {"test_a_reader_who_has_the_bytes_can_re_derive_every_pinned_number"}, skipped
    for name in NEVER_SKIPS:
        assert hasattr(module, name), "NEVER_SKIPS names a test that no longer exists: %s" % name
        assert name not in skipped, name


def test_the_no_socket_fixture_is_not_decorative():
    """The autouse guard has to be able to fire, or every offline claim in this file is unproven."""
    with pytest.raises(AssertionError, match="reached the network"):
        fetch_massive._urlopen(url_of("test/aa.json.gz"))


def test_ci_polices_the_tools_root_this_file_imports():
    """`tools/` is a third source root, and an unpoliced root is this repository's known blind spot.

    `tests/test_toolchain.py` runs whatever CI's `ruff check` line says, so if `tools` were dropped
    from it the lint gate would go quiet about this module and nothing here would notice. Read from the
    workflow rather than restated, with the control arm showing the predicate fires on the omission.
    """
    text = CI_WORKFLOW.read_text()
    lint = [line for line in text.splitlines() if "ruff check" in line]
    assert len(lint) == 1, lint                    # the shape tests/test_toolchain.py:47 depends on
    assert " src tests tools" in lint[0], lint[0]
    compiled = [line for line in text.splitlines() if "compileall" in line]
    assert len(compiled) == 1, compiled
    assert " src tests tools" in compiled[0], compiled[0]
    dropped = lint[0].replace(" src tests tools", " src tests")
    assert " src tests tools" not in dropped, "the predicate above cannot fail"


def test_no_source_path_bypasses_certificate_verification():
    """A2 as a gate, not a sentence: this module must have no way to turn verification off."""
    source = Path(fetch_massive.__file__).read_text()
    for forbidden in ("verify=False", "CERT_NONE", "_create_unverified", "check_hostname = False",
                      "--insecure"):
        assert forbidden not in source, forbidden
    # Control: the predicate catches the bypass it exists to catch.
    mutated = source.replace("build_opener(_NoRedirect())", "build_opener(_NoRedirect(), verify=False)")
    assert "verify=False" in mutated, "the guard above cannot fail"
    assert "build_opener" in source and "timeout=TIMEOUT_S" in source, "the seam no longer opens a socket"


@cache_gated
def test_a_reader_who_has_the_bytes_can_re_derive_every_pinned_number():
    """The claim the pin makes about itself, checked against the real shards, not a planted stand-in.

    This is the only test here that reads the corpus bytes, and they are not in this repository (see
    `provenance.bytes_retained`), so it keys on `AUTORATE_MASSIVE_CACHE`. The re-hash is why the
    fetcher exists: the committed file is the reference and the bytes are the check against it.
    """
    manifest = fetch_massive.load_manifest()
    report = verify_provenance(CACHE_DIR, manifest)
    assert report["cache_present"] is True and report["checked"] == 51, report
    assert report["missing"] == [] and report["mismatched"] == [], report
    assert report["ok"] == 51
    ids = shared_id_set(CACHE_DIR, manifest)
    assert ids["identical"] is True, ids
    assert ids["n_independent"] == 2974, ids


def test_a_connection_that_stops_mid_body_is_a_refusal_not_a_traceback(monkeypatch, tmp_path, capsys):
    """The first live fetch refuted this tool's own rc-1 claim, so the refutation is now a test.

    `main`'s docstring says rc 1 is unreachable "by construction: every raise site below is one of
    these three, or an `OSError` from the filesystem". It was wrong: `http.client.IncompleteRead` --
    raised when a CDN closes the body early, which is what happened to two of the 51 shards on
    2026-10-06 -- is an `HTTPException`, neither an `OSError` nor a `FetchError`, so it escaped both
    clauses and the process died with a traceback and exit 1, outside the published contract. A
    partial read is the ordinary case a fetcher exists to survive, not a crash. The gzip family is
    already handled by name (`GZIP_FAILURES` covers `EOFError` and `zlib.error`); this is the same
    hole on the transport side, where the bytes come from.
    """
    import http.client

    from tools.fetch_massive import FetchError, main, read_bytes

    class _Truncating:
        headers = {}

        def read(self):
            raise http.client.IncompleteRead(b"x" * 128, 8961)

    with pytest.raises(FetchError, match="IncompleteRead"):
        read_bytes("https://example.invalid/a", transport=lambda url: _Truncating())

    monkeypatch.setattr(fetch_massive, "_urlopen", lambda *a, **k: _Truncating())
    rc = main(["fetch", "--dest", str(tmp_path / "dest")])
    assert rc == 4, rc
    err = capsys.readouterr().err
    assert "Traceback" not in err, err
    assert "COULD NOT COMPLETE" in err, err
