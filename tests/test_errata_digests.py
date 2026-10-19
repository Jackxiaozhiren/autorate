"""Every full digest `docs/ERRATA.md` states has to be one this repository actually computed.

The sixteenth round's ERRATA entry wrote the round's protocol digest as
`50941330a77e40d1a26f7c1e0f9a5f9b4ce9f5e9a7b0e2f7c4a5f7c0c0a9ea5d`. Its first twelve hex digits are that
emission's; the remaining fifty-two belong to no digest this repository has ever produced -- the real tail is
`eda819df4964d6fd4cc40a5c204fc48054b2d1e4156a0331b982`. It was typed from memory rather than read out of the
emission log, and it passed every gate: the digit-residue row reads `protocol.json`'s notes, not ERRATA, and it
bounds digits, not hex. A digest is the project's load-bearing identifier -- stamped into seven artefacts,
recomputed by `verify`, quoted as the witness of a freeze -- so a prose digest that matches nothing is a claim
about an emission that never happened.

The census is closed rather than pattern-shaped: the valid set is what `protocol.protocol_digest` returns for
each committed revision of `protocol.json` (`--full-history`, so a merge-simplified revision keeps its own digest
legal), plus the working tree's own so the round being written can cite its emission before it is committed,
unioned with `protocol.file_digest` over the bytes this repository publishes FROM -- `data/` and `protocol.json`,
not every tracked file, or the guard would accept the sha256 of its own source as legal prose. The scan set is
enumerated, not listed: every tracked markdown the publication table does not render is hand-written, so a new
hand-typed document joins the census without anyone remembering to add it. Two files are waived with a stated
reason because their hashes are upstream `laya` revisions this checkout has no object database to recompute, and
the waiver is refused if the file stops holding a hash or starts quoting a digest this repository can compute.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from autorate import cli
from autorate.protocol import file_digest, protocol_digest

REPO = Path(cli.__file__).resolve().parents[2]
FULL_SHA = re.compile(r"\b[0-9a-f]{64}\b")

# Hand-written documents this repository publishes, enumerated from the tables rather than remembered: a tracked
# markdown file that `cli.PUBLISHED_DOCS` does NOT render is typed by a human, so a digest in it is a claim the
# census can check. A new hand-typed document therefore falls into the scan by itself -- review MINOR-7's hole was
# that a fixed list would never look at one, which is how the retyped digest in ERRATA stayed invisible in the
# first place.
#
# Two files state hashes this repository cannot recompute, and saying so is what keeps the census honest: their
# token is an upstream `laya` revision, and the object database that would verify it is not in this checkout. An
# exemption that stops holding a token is refused below, so the reason cannot outlive the fact.
UPSTREAM_HASH_EXEMPTIONS = {
    "docs/upstream/SUBMISSION.md": "the upstream laya revision this branch submits against",
    "docs/upstream/patch/README.md": "the same upstream revision, restated for the patch reader",
}


def _hand_written_markdown():
    published = {str(path) for path, _render in cli.PUBLISHED_DOCS}
    return sorted(rel for rel in _tracked_files() if rel.endswith(".md") and rel not in published)


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def _history_available():
    """One probe, consulted before any row that reads commits -- the same reason as in `test_g5_transcript.py`:
    a `git archive` export says `not a git repository` and an unknown sha says `Not a valid object name`, and a
    row that keyed on either message would be dead in one environment and red in the other."""
    return _git("rev-parse", "--git-dir").returncode == 0


def _tracked_files():
    manifest = os.environ.get("AUTORATE_TRACKED_FILES")
    if manifest:
        return [line.strip() for line in Path(manifest).read_text().splitlines() if line.strip()]
    out = _git("ls-files")
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.split()
    pytest.fail("nothing to scan: AUTORATE_TRACKED_FILES is unset and `git ls-files` returned no paths")


def _emitted_digests():
    """`protocol_digest` recomputed from every committed revision of `protocol.json`, plus this tree's.

    `--full-history` because the sentence claims EVERY committed revision: the default `git log -- <path>`
    simplifies the list when a merge leaves the file's content unchanged on one side, and a simplified-away
    emission would drop its own digest out of the legal set -- a false red on a document citing a value the
    repository really did emit.
    """
    log = _git("log", "--full-history", "--format=%H", "--", "protocol.json")
    assert log.returncode == 0, log.stderr[:200]
    digests = set()
    for rev in log.stdout.split():
        raw = _git("show", "%s:protocol.json" % rev)
        assert raw.returncode == 0, (rev, raw.stderr[:200])
        digests.add(protocol_digest(json.loads(raw.stdout)))
    digests.add(protocol_digest(json.loads((REPO / "protocol.json").read_text())))
    return digests


PUBLISHED_SOURCE_DIRS = ("data",)


def _on_disk_digests():
    """Hashes of the bytes this repository publishes FROM, so an entry may cite one as evidence.

    Deliberately narrower than "every tracked file": a guard that accepts the sha256 of anything in the tree
    would also accept a digest of the guard's own source, and the census is about protocol digests, not about
    whatever a file happens to hash to. The exclusion is reported by the row that uses it so the appetite is
    visible rather than implied.
    """
    tracked = _tracked_files()
    legal = [rel for rel in tracked if rel.split("/", 1)[0] in PUBLISHED_SOURCE_DIRS or rel == "protocol.json"]
    return {file_digest(REPO / rel) for rel in legal if (REPO / rel).is_file()}


def _excluded_tracked_files():
    tracked = _tracked_files()
    return sorted(rel for rel in tracked
                  if not (rel.split("/", 1)[0] in PUBLISHED_SOURCE_DIRS or rel == "protocol.json"))



def _unbacked(text, emitted, on_disk):
    """The full digests a document states that no digest function in this repository can produce."""
    return sorted({tok for tok in FULL_SHA.findall(text) if tok not in emitted and tok not in on_disk})


def _near_misses(unbacked, emitted):
    """Unbacked digests sharing a prefix with a real emission -- the exact shape of a truncated re-typing."""
    return {tok: sorted(e[:16] + "..." for e in emitted if e[:12] == tok[:12])
            for tok in unbacked if any(e[:12] == tok[:12] for e in emitted)}


def _stated_digests(rel):
    return set(FULL_SHA.findall((REPO / rel).read_text()))


def test_the_census_reads_every_hand_written_document_not_a_remembered_pair():
    """The scan set is enumerated from the tables, so a document nobody remembered cannot escape it.

    Three halves. The set: every tracked `.md` that `cli.PUBLISHED_DOCS` does not render is hand-written, so
    README, ERRATA, `docs/VERIFICATION.md` and a file added next week all land in the scan by construction --
    review MINOR-7's hole was a fixed list, and a fixed list is how the retyped digest in ERRATA stayed invisible
    while a guard existed for digests. The exemptions: a declared reason must still be a hand-written tracked file
    AND must still hold a hash, or the reason has outlived the fact and the row says so. The reach: a planted
    digest appended to each scanned document's own text is caught by the same call the release row makes, so the
    file walk -- not just the extractor -- is proven.
    """
    hand = _hand_written_markdown()
    published_md = sorted(str(path) for path, _render in cli.PUBLISHED_DOCS if str(path).endswith(".md"))
    assert published_md, (
        "`cli.PUBLISHED_DOCS` renders no markdown, so the subtraction that defines a hand-written document has "
        "no content and the census would read the producer-rendered files too")
    for expected in ("README.md", "docs/ERRATA.md", "docs/VERIFICATION.md", "docs/G5.md"):
        assert expected in hand, "%s is not in the hand-written set %s" % (expected, hand)
    assert not (set(published_md) & set(hand)), sorted(set(published_md) & set(hand))

    for rel, reason in UPSTREAM_HASH_EXEMPTIONS.items():
        assert reason, "exemption %s carries no reason, which is an ignore list" % rel
        assert rel in hand, "exemption %s names no hand-written tracked document" % rel
        assert _stated_digests(rel), (
            "exemption %s (%s) holds no full digest any more, so the file is being waived for a fact that is "
            "gone -- delete the exemption" % (rel, reason))

    emitted, on_disk = _emitted_digests(), _on_disk_digests()
    planted = "\ndigest " + "f" * 64 + " claimed by nobody\n"
    for rel in hand:
        if rel in UPSTREAM_HASH_EXEMPTIONS:
            continue
        hits = _unbacked((REPO / rel).read_text() + planted, emitted, on_disk)
        assert "f" * 64 in hits, (
            "the census does not refuse a planted digest read through %s: %s" % (rel, hits))
    assert _excluded_tracked_files(), (
        "the on-disk half of the legal set excludes no tracked file, which means any sha256 in the tree becomes "
        "legal prose -- the narrowing this row exists to police")


def test_every_full_digest_a_hand_written_document_states_is_one_the_repository_computed():
    """RED for the sixteenth round's entry: a digest whose tail belongs to no emission this tree has made."""
    if not _history_available():
        pytest.skip("no object database here (a `git archive` export), so earlier emissions cannot be recomputed")
    emitted, on_disk = _emitted_digests(), _on_disk_digests()
    scanned = [rel for rel in _hand_written_markdown() if rel not in UPSTREAM_HASH_EXEMPTIONS]
    stated = set()
    for rel in scanned:
        stated.update(_stated_digests(rel))
    assert len(stated & emitted) >= 7, (
        "the census expects at least seven hand-quoted emission digests, and sees %d of %d: if the set shrank, "
        "this row has stopped policing the documents it was written for" % (len(stated & emitted), len(stated)))
    unbacked = sorted(tok for tok in stated if tok not in emitted and tok not in on_disk)
    assert not unbacked, (
        "%s state a full digest no digest function in this repository produces: %s -- near misses among them "
        "%s -- so those sentences cite an emission that never happened; read the value out of the freeze log "
        "instead of retyping it" % (scanned, unbacked, _near_misses(unbacked, emitted)))
    for rel in UPSTREAM_HASH_EXEMPTIONS:
        toks = _stated_digests(rel)
        assert not (toks & emitted), (
            "%s is waived as an upstream-hash document but quotes %s, which this repository can recompute -- "
            "move it into the scan" % (rel, sorted(toks & emitted)))


def test_a_real_digest_with_a_fabricated_tail_is_refused():
    """The census fires on the failure mode that actually occurred, and accepts the value it replaced.

    Plant: take the sixteenth emission's digest and rebuild the tail from a different emission's digits, the way
    a retyped string does. Same predicate as the release row, opposite verdict on the true value -- which is
    what makes the twelve-digit prefix proof that neither half is decorative.
    """
    if not _history_available():
        pytest.skip("no object database here, so the planted defect cannot be keyed to a real emission")
    emitted = _emitted_digests()
    sixteenth = next(d for d in emitted if d.startswith("50941330a77e"))
    other = next(d for d in emitted if d != sixteenth)
    planted = sixteenth[:12] + other[12:]
    assert planted not in emitted and planted[:12] == sixteenth[:12], (
        "the plant must differ from every real emission while sharing the prefix the document got right")
    hits = _unbacked("digest %s" % planted, emitted, _on_disk_digests())
    assert hits == [planted], "the census accepted the fabricated tail: %s" % hits
    assert not _unbacked("digest %s" % sixteenth, emitted, _on_disk_digests()), (
        "the census refused the true digest too, so it would refuse any value and prove nothing")
    assert _near_misses(hits, emitted)[planted], (
        "the report could not name which emission the prefix belongs to, so a truncated re-typing would be "
        "reported as a bare unknown hash")
