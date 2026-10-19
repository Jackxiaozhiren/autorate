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
each committed revision of `protocol.json` (plus the working tree's own, so the round being written can cite
its own emission before it is committed), together with `protocol.file_digest` over every tracked file, so an
entry that quotes a corpus or artefact hash stays legal. The claim surface is ERRATA and README: the
producer-rendered documents cannot drift from their own bytes, and `docs/VERIFICATION.md` records upstream
revisions whose hashes this repository has no object database to recompute -- both facts are asserted below
rather than left to the reader.
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
CLAIM_SURFACES = ("docs/ERRATA.md", "README.md")


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
    """`protocol_digest` recomputed from every committed revision of `protocol.json`, plus this tree's."""
    log = _git("log", "--format=%H", "--", "protocol.json")
    assert log.returncode == 0, log.stderr[:200]
    digests = set()
    for rev in log.stdout.split():
        raw = _git("show", "%s:protocol.json" % rev)
        assert raw.returncode == 0, (rev, raw.stderr[:200])
        digests.add(protocol_digest(json.loads(raw.stdout)))
    digests.add(protocol_digest(json.loads((REPO / "protocol.json").read_text())))
    return digests


def _on_disk_digests():
    return {file_digest(REPO / rel) for rel in _tracked_files() if (REPO / rel).is_file()}


def _unbacked(text, emitted, on_disk):
    """The full digests a document states that no digest function in this repository can produce."""
    return sorted({tok for tok in FULL_SHA.findall(text) if tok not in emitted and tok not in on_disk})


def _near_misses(unbacked, emitted):
    """Unbacked digests sharing a prefix with a real emission -- the exact shape of a truncated re-typing."""
    return {tok: sorted(e[:16] + "..." for e in emitted if e[:12] == tok[:12])
            for tok in unbacked if any(e[:12] == tok[:12] for e in emitted)}


def test_the_claim_surface_is_the_documents_a_human_types_by_hand():
    """The scope of the row above is itself a claim, so it is measured rather than asserted in a docstring.

    Plant: give one of these documents a full digest that no producer emitted; the census row has to see it.
    """
    counts = {}
    for rel in ("docs/VERIFICATION.md", "docs/REPORT.md", "docs/G5.md"):
        counts[rel] = len(FULL_SHA.findall((REPO / rel).read_text()))
    assert counts["docs/VERIFICATION.md"] == 0, (
        "docs/VERIFICATION.md now carries %d full digests; they are upstream revisions this repository cannot "
        "recompute, so widen the census by reading the file and naming the exclusion, not by dropping the row"
        % counts["docs/VERIFICATION.md"])
    assert counts["docs/REPORT.md"] and counts["docs/G5.md"], (
        "the producer-rendered documents stopped carrying digests, so the sentence explaining why they are "
        "excluded is no longer true: %s" % counts)
    planted = "digest ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff and that one"
    assert _unbacked(planted, set(), set()) == ["f" * 64], "the census cannot see a planted digest at all"


def test_every_full_digest_the_errata_entries_state_is_one_the_repository_computed():
    """RED for the sixteenth round's entry: a digest whose tail belongs to no emission this tree has made."""
    if not _history_available():
        pytest.skip("no object database here (a `git archive` export), so earlier emissions cannot be recomputed")
    emitted, on_disk = _emitted_digests(), _on_disk_digests()
    stated = set()
    for rel in CLAIM_SURFACES:
        stated.update(FULL_SHA.findall((REPO / rel).read_text()))
    assert len(stated & emitted) >= 7, (
        "the census expects at least seven hand-quoted emission digests, and sees %d of %d: if the set shrank, "
        "this row has stopped policing the document it was written for" % (len(stated & emitted), len(stated)))
    unbacked = _unbacked("\n".join((REPO / rel).read_text() for rel in CLAIM_SURFACES), emitted, on_disk)
    assert not unbacked, (
        "%s state a full digest no digest function in this repository produces: %s -- near misses among them "
        "%s -- so those sentences cite an emission that never happened; read the value out of the freeze log "
        "instead of retyping it" % (list(CLAIM_SURFACES), unbacked, _near_misses(unbacked, emitted)))


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
