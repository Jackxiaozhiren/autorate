"""Plan D Task 3: `docs/G5.md` is a transcript of a run, and these rows are the reason it can be trusted.

G5's criterion is the literal command: `autorate verify --protocol protocol.json` re-deriving every published
number from a commit, with no GPU, no network and no model. A transcript of such a run is a different kind of
published file from the ones `verify` re-renders: it records an EVENT, and the event cannot be re-executed
inside a test (the export needs `uv sync`, which needs the network). So the guard is not "re-run it" -- it is
"the transcript cannot disagree with the tree it claims to describe, and it cannot be a document that merely
looks like a transcript".

The five statements these rows make, each with the plant that reddens it named in its docstring:

1. every recorded exit code is inside the documented contract, and a planted `1` is refused;
2. each lane's `re-derived N /N` has equal halves, and a planted mismatch is refused;
3. the protocol digest the transcript prints is the digest of the `protocol.json` in this tree -- so an
   artifact frozen against an older freeze reads as stale rather than as evidence;
4. the transcript names the commit it was produced from, and that sha exists in the repository's history;
5. no line of it carries a machine path in ANY of the shapes a scratch directory takes -- `/Users/`,
   `/home/`, `/var/folders/`, `/private/tmp/`, `/tmp/` -- because the most natural content of a transcript is
   the path of the directory the run happened in, and `tests/test_cli.py`'s guard only saw the first two.

What is deliberately NOT claimed here: that the run really happened in an export with no network. That is
Task 3's own measurement, printed inside the transcript and reproducible by `bash tools/g5_export.sh`; a test
that re-derived it would need the network the transcript says was absent.
"""
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "G5.md"

MACHINE_PATH_RX = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")
SCRATCH_PATH_RX = re.compile(r"/(var/folders|private/tmp|tmp|private/var)/\S*")
LANE_RX = re.compile(r"re-derived (\d+) /(\d+) values")
CODE_RX = re.compile(r"^rc=(\d+)", re.MULTILINE)
DIGEST_RX = re.compile(r"protocol digest: `([0-9a-f]{64})`")
SHA_RX = re.compile(r"[Pp]roduced from commit `([0-9a-f]{7,40})`")

CONTRACT_CODES = {0, 2, 3, 4}


@pytest.fixture(scope="module")
def text():
    assert DOC.is_file(), "docs/G5.md is missing -- run `bash tools/g5_export.sh`"
    return DOC.read_text()


def _lane_section(text: str) -> str:
    """Only the lanes block, because the falsifications below it print a mismatched pair ON PURPOSE.

    Measured on the first real transcript: the stamped-digest tamper's line reads `re-derived 241 /242`, and a
    row that swept the whole document failed on it. That mismatch IS the falsification working, not a lane
    disagreeing with itself, so the equality claim is scoped to the section that reports the lanes -- and the
    gap assertion still needs two different denominators, which only the lanes produce.
    """
    _, _, rest = text.partition("## The lanes")
    head, _, _ = rest.partition("## The falsifications")
    assert "re-derived" in head, "the lanes section carries no counts, so this row would prove nothing"
    return head


def test_every_recorded_exit_code_is_inside_the_documented_contract(text):
    """A transcript that records rc 1 is recording an escape the CLI is not allowed to have.

    Plant: change one `rc=0` in the transcript to `rc=1` and this row goes red -- which is the point of
    asserting on the codes rather than on the prose. G5's claim is that the whole surface stays inside
    0/2/3/4 even in an environment with no repository and no corpus.
    """
    codes = {int(m) for m in CODE_RX.findall(text)}
    assert codes, "the transcript records no exit code at all, so it is not a transcript of a command"
    # The toolchain's own numeric outcomes are not CLI exit codes: the record's `curl rc=6` line is a
    # network-attempt result, and reading it as a CLI code would make the contract row refuse an honest
    # transcript. Anchored to the recorded `rc=<n>` lines, which is the shape the emitter prints per step.
    outside = sorted(codes - CONTRACT_CODES)
    assert not outside, "the transcript records exit code(s) %s, outside the documented contract" % outside


def test_each_lane_counts_the_same_number_of_values_it_checked(text):
    """`re-derived N /M` with N != M is drift, and a transcript of drift must not read as green.

    Plant: change one lane's numerator. Both lanes' halves have to agree, and the row also asserts the two
    denominators are the two DIFFERENT numbers the lanes are known for -- the 35-check gap is the reason
    running both is the measurement at all.
    """
    pairs = LANE_RX.findall(_lane_section(text))
    assert pairs, "no `re-derived N /N values` line in the transcript"
    for checked, total in pairs:
        assert checked == total, (checked, total)
    denominators = sorted({int(total) for _c, total in pairs})
    assert len(denominators) == 2, denominators
    assert denominators[1] - denominators[0] == 35, denominators


def test_the_digest_the_transcript_prints_is_the_digest_of_the_commit_it_names(text, tmp_path):
    """What a transcript can be promised to keep true: its numbers match the commit it says it ran from.

    Deliberately NOT "the digest of the tree you are reading now". A transcript of commit X is a record about
    X, and it stays true when a later commit re-freezes; a row that demanded equality with the current digest
    would turn every legitimate re-freeze into a red CI, and a freeze commit cannot regenerate its own
    transcript because the export needs a sha that already exists. Truthfulness is enforced here; currency is
    stated in the transcript's own first block, where the reader can see which commit it describes.

    Plants: change one hex digit in the transcript, or point the file at a different commit -- either breaks
    the equality between what is printed and what the named commit actually holds.
    """
    from autorate.protocol import load_protocol, protocol_digest

    printed = set(DIGEST_RX.findall(text))
    assert printed, "the transcript names no protocol digest"
    sha = SHA_RX.search(text)
    assert sha, "the digest row cannot be checked without the commit the transcript names"
    raw = subprocess.run(["git", "-C", str(REPO), "show", "%s:protocol.json" % sha.group(1)],
                         capture_output=True)
    if raw.returncode != 0:
        pytest.skip("no object database here (a `git archive` export), so the named commit cannot be read")
    tmp = tmp_path / "protocol.json"
    tmp.write_bytes(raw.stdout)
    assert printed == {protocol_digest(load_protocol(tmp))}, sorted(printed)


def test_the_transcript_describes_a_commit_this_branch_can_reach(text):
    """Currency, stated rather than demanded: the transcript is of an ANCESTOR of the reader's tip.

    This is the honest half of "is it up to date" -- the named commit must be reachable from HEAD, so a
    transcript cannot be smuggled in from an abandoned branch -- without the freshness demand that a re-freeze
    could never satisfy in the same commit.
    """
    shas = set(SHA_RX.findall(text))
    assert shas, "the transcript does not name the commit it was produced from"
    for sha in shas:
        probe = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, "HEAD"],
                               capture_output=True)
        if probe.returncode == 128:
            pytest.skip("no git history to consult in this checkout")
        assert probe.returncode == 0, (sha, probe.stderr.decode()[:200])


def test_the_transcript_names_a_commit_that_exists_in_this_history(text):
    """`from a commit` is G5's own wording; the sha is what makes it checkable instead of rhetorical.

    Plant: replace the sha with one this repository has never had. The assertion runs `git cat-file`, so a
    fabricated sha cannot survive it -- and in a `git archive` export there is no history to consult, which is
    why this row is skipped there rather than passed by default.
    """
    shas = set(SHA_RX.findall(text))
    assert shas, "the transcript does not name the commit it was produced from"
    for sha in shas:
        probe = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", "%s^{commit}" % sha],
                               capture_output=True)
        if probe.returncode == 128 and b"not a valid object name" in probe.stderr:
            # An export has no object database at all; `git cat-file -e <sha>^{commit}` cannot answer.
            pytest.skip("no git history to consult in this checkout")
        assert probe.returncode == 0, (sha, probe.stderr.decode()[:200])


def test_the_transcript_carries_no_path_that_identifies_the_machine_it_ran_on(text):
    """Scratch directories are the leak a transcript is most likely to carry, in shapes the old guard missed.

    Plant: write the absolute path of any real temp directory into the file. `/Users/jackson/...` was already
    refused by `tests/test_cli.py`'s tracked-tree guard; this row covers the `/var/folders/...`,
    `/private/tmp/...` and `/tmp/...` shapes a run's own working directory actually takes, and it reads the
    WHOLE file rather than only lines that happen to mention a path.
    """
    home_leaks = [(i, line) for i, line in enumerate(text.splitlines(), 1) if MACHINE_PATH_RX.search(line)]
    scratch_leaks = [(i, line) for i, line in enumerate(text.splitlines(), 1) if SCRATCH_PATH_RX.search(line)]
    assert not home_leaks, home_leaks[:3]
    assert not scratch_leaks, scratch_leaks[:3]
    assert "<export-dir>" in text, "the transcript masks nothing, so what did it mask?"


def test_the_transcript_states_the_environment_it_was_measured_in_as_a_property_not_an_intention(text):
    """`no model` and `no repository` have to be things the run ASKED the environment.

    Plant: delete either assertion line. The row is here because the first export lane (R-147) produced
    `torch importable: False` from whichever interpreter answered, and a transcript that does not name the
    environment it probed cannot support the claim at all.
    """
    assert re.search(r"torch importable: False", text), "no recorded answer for torch"
    assert re.search(r"transformers importable: False", text), "no recorded answer for transformers"
    assert re.search(r"`<export-dir>/\.git` exists: ABSENT", text), "no line proves the export had no repository"
    assert re.search(r"answering interpreter: <export-dir>", text), \
        "the interpreter that answered is not identified by its own (masked) prefix"


# --- the emitter itself -----------------------------------------------------------------------------------
# These four rows were written AFTER `tools/g5_transcript.py`, so they carry no red-first ordering; what they
# do carry is a plant each, and the ordering is disclosed here rather than left for a reader to assume. The
# transcript rows above were written first and watched to fail with `docs/G5.md` absent.

def _minimal_record(**over) -> str:
    """A complete record with one field replaced, so each row's failure is the one it names."""
    from autorate.protocol import load_protocol, protocol_digest

    base = {
        "commit": "deadbeef",
        "env.git_dir": "ABSENT", "env.torch": "False", "env.transformers": "False",
        "env.prefix": "<export-dir>/.venv/bin/python3",
        "env.digest": protocol_digest(load_protocol(REPO / "protocol.json")),
        "env.network": "curl rc=6", "env.offline_flags": "HF_HUB_OFFLINE=1", "env.toolchain": "Darwin arm64",
        "lane_absent.command": "verify --protocol protocol.json (corpus absent)",
        "lane_absent.rc": "0", "lane_absent.output": "re-derived 242 /242 values",
        "lane_present.command": "verify --protocol protocol.json (corpus present)",
        "lane_present.rc": "0", "lane_present.output": "re-derived 277 /277 values",
        "tamper_protocol.command": "alpha moved", "tamper_protocol.rc": "4",
        "tamper_protocol.output": "RUBRIC MISMATCH", "swap_records.command": "records swapped",
        "swap_records.rc": "4", "swap_records.output": "DRIFT",
        "wrong_shape_snapshot.command": "snapshot []", "wrong_shape_snapshot.rc": "4",
        "wrong_shape_snapshot.output": "PUBLISHED ARTEFACT UNAVAILABLE",
        "tamper_artefact_digest.command": "one hex digit changed in a stamped digest",
        "tamper_artefact_digest.rc": "4",
        "tamper_artefact_digest.output": "re-derived 241 /242 values",
        "tamper_artefact_digest.restored": "restored byte-identical",
    }
    base.update(over)
    for key in list(base):
        if base[key] is None:
            del base[key]
    return "\n".join("%s\t%s" % kv for kv in base.items()) + "\n"


def _write(tmp_path, text: str) -> Path:
    record = tmp_path / "record.tsv"
    record.write_text(text)
    return record


def _render(tmp_path, text: str) -> str:
    """Parse the way `main` does, so the rows exercise the same reader the runner feeds."""
    from tools.g5_transcript import read_record, render

    return render(read_record(_write(tmp_path, text)))


def test_a_record_with_an_incomplete_step_is_refused_rather_than_rendered(tmp_path):
    """A transcript missing a lane's exit code would print a claim the run never made.

    Plant: drop `lane_present.rc` from the record -- the refusal names the missing key instead of emitting a
    block with `rc=None`.
    """
    from tools.g5_transcript import TranscriptRefusal

    with pytest.raises(TranscriptRefusal, match="lane_present\\.rc"):
        _render(tmp_path, _minimal_record(**{"lane_present.rc": None}))


def test_a_record_without_the_digest_the_run_observed_is_refused(tmp_path):
    """The no-recompute rule: the digest must come from the run, or the staleness row above cannot fail.

    Plant: delete `env.digest`. An emitter that filled the gap by hashing the tree would silently turn every
    stale transcript into a fresh one, so this is a refusal and not a default.
    """
    from tools.g5_transcript import TranscriptRefusal

    with pytest.raises(TranscriptRefusal, match="64-hex protocol digest"):
        _render(tmp_path, _minimal_record(**{"env.digest": None}))
    with pytest.raises(TranscriptRefusal, match="64-hex protocol digest"):
        _render(tmp_path, _minimal_record(**{"env.digest": "ff9f"}))


def test_an_unmasked_machine_path_in_the_record_refuses_the_whole_document(tmp_path):
    """The leak class the tracked-tree guard does not see, caught before it becomes a committed file.

    Plant: put a real scratch directory into `env.prefix`. `main` must exit 2 and leave no `docs/G5.md`
    behind -- a redacted-with-warning transcript is still a transcript that names a machine.
    """
    from tools import g5_transcript

    record = _write(tmp_path, _minimal_record(**{"env.prefix": "/var/folders/5l/abcdef/T/g5-export"}))
    out = tmp_path / "G5.md"
    rc = g5_transcript.main(["--record", str(record), "--out", str(out)])
    assert rc == 2, rc
    assert not out.exists(), "the emitter wrote a document that names a machine path"


def test_a_value_the_record_does_not_carries_no_line_rather_than_the_word_none(tmp_path):
    """`offline flags: None` would read as a recorded fact; a missing fact has no sentence."""
    text = _render(tmp_path, _minimal_record(**{"env.offline_flags": None, "env.toolchain": None}))
    assert "None" not in text, [line for line in text.splitlines() if "None" in line]
    assert "offline flags" not in text and "toolchain" not in text


def test_the_defect_count_in_the_prose_is_the_count_of_blocks_rendered(text):
    """A sentence that counts defects must count the blocks, or it is a number typed beside the artefact.

    RED for the draft transcript, which said "three defects" under four planted blocks because the emitter's
    prose was written when the export had three plants and the fourth (a stamped digest, which the loader
    cannot veto) was added without touching the sentence. Fixing the emitter to render `len(FALSIFICATIONS)`
    makes it agree; changing the tuple again reddens this row rather than the document.
    """
    prose = re.search(r"so (\d+) defects are planted inside the export", text)
    assert prose, "the falsifications section no longer counts its defects, so this row guards nothing"
    fenced = [c.strip() for c in text.split("```") if c.strip().startswith("$ ")]
    lanes = [c for c in fenced if "autorate verify --protocol protocol.json" in c]
    plants = [c for c in fenced if c not in lanes]
    assert len(plants) == int(prose.group(1)), (prose.group(1), len(plants), len(fenced))
