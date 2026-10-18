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

MACHINE_PATH_RX = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")
SCRATCH_PATH_RX = re.compile(r"/(?:var/folders|private/tmp|tmp|private/var)/\S*")
LANE_RX = re.compile(r"re-derived (\d+) /(\d+) values")
CODE_RX = re.compile(r"^rc=(\d+)", re.MULTILINE)
DIGEST_RX = re.compile(r"protocol digest: `([0-9a-f]{64})`")
SHA_RX = re.compile(r"[Pp]roduced from commit `([0-9a-f]{7,40})`")

CONTRACT_CODES = {0, 2, 3, 4}

BLOCK_RX = re.compile(r"```\n\$ (?P<label>[^\n]*)\nrc=(?P<rc>\d+)  (?P<output>[^\n]*)\n```")
TARGET_RX = re.compile(r"(?:data/)?[A-Za-z0-9_.-]+\.(?:json|jsonl)")
LANES_HEADING = "## The lanes"
FALSIFICATIONS_HEADING = "## The falsifications"
AFTER_HEADING = "## What this transcript does not show"


def _blocks(text, start, stop):
    """The fenced blocks of ONE section, as (label, rc, output, trailing-lines).

    Section-scoped rather than document-scoped on purpose: the classifier this file used before sorted the
    blocks by whether their label quoted `autorate verify --protocol protocol.json`, so a plant whose label
    mentioned that command was counted as a lane. Review M7 named that a hazard when relabelling plant 2;
    the fix is to stop classifying by a quoted command and ask which section the block is in.
    """
    body = text.partition(start)[2].partition(stop)[0]
    out = []
    for match in BLOCK_RX.finditer(body):
        tail = body[match.end():].split("```", 1)[0]
        out.append((match.group("label"), int(match.group("rc")), match.group("output"),
                    [line.strip() for line in tail.splitlines() if line.strip()]))
    assert out, "no fenced blocks in the %r section -- this row would be comparing an empty list" % start
    return out


@pytest.fixture(scope="module")
def text():
    assert DOC.is_file(), "docs/G5.md is missing -- run `bash tools/g5_export.sh`"
    return DOC.read_text()


def _lane_section(text: str) -> str:
    """Only the lanes block, because the falsifications below it print a mismatched pair ON PURPOSE.

    Measured on the first real transcript: the stamped-digest tamper's line carries a numerator one below its
    denominator -- one published value disagrees with the freeze, which is the whole point of that plant --
    and a row that swept the whole document failed on it. That mismatch IS the falsification working, not a
    lane disagreeing with itself, so the equality claim is scoped to the section that reports the lanes -- and
    the gap assertion still needs two different denominators, which only the lanes produce.
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
    denominators are the two DIFFERENT numbers the lanes are known for, differing by exactly the comparisons
    only a corpus can make.
    """
    pairs = LANE_RX.findall(_lane_section(text))
    assert pairs, "no `re-derived N /N values` line in the transcript"
    for checked, total in pairs:
        assert checked == total, (checked, total)
    denominators = sorted({int(total) for _c, total in pairs})
    assert len(denominators) == 2, denominators
    # The gap comes from `cli.corpus_only_comparisons`, the gate's own count, and NOT from a formula written
    # here. This row used to derive it inline as digests + non-machine snapshot keys and comment the result as
    # "35 digests + non-machine keys"; `tests/test_verify_protocol.py` derived the same quantity a second time
    # and added `report.CONTAMINATION_CORPUS_ONLY_CHECKS`, because the contamination arm re-digests the
    # upstream file where the corpus is visible. Two owners, two answers, and the measured lanes (734 absent /
    # 771 present) agreed with the second: this row was licensing a 35-gap transcript that no longer described
    # the gate, and it would have refused an honest re-export of one that did.
    import json

    from autorate.cli import SNAPSHOT_MACHINE_KEYS, corpus_only_comparisons

    inv = json.loads((REPO / "data" / "inventory.md.json").read_text())
    derived = corpus_only_comparisons(inv)
    assert denominators[1] - denominators[0] == derived, (
        "the transcript's lanes differ by %d, this tree's gate adds %d corpus-only comparisons "
        "(%d `SOURCE.json` digests + %d non-machine snapshot keys + %d corpus-only contamination checks) -- "
        "run `bash tools/g5_export.sh` to re-transcribe the lanes the gate actually has"
        % (denominators[1] - denominators[0], derived, len(inv["digests"]),
           len([k for k in inv if k not in SNAPSHOT_MACHINE_KEYS]),
           derived - len(inv["digests"]) - len([k for k in inv if k not in SNAPSHOT_MACHINE_KEYS])))


def test_a_record_whose_lane_gap_is_not_the_corpus_only_count_refuses_the_document(tmp_path):
    """The check above runs on a file that already exists; the writer is where a stale gap stops.

    Plant: take the fixture's record and move the present lane back to the undercounted 35-gap. The emitter
    must refuse -- and `main` must leave no document behind, because the whole reason the exit-code contract
    lives in the renderer is that a red test downstream of an overwrite is a transcript that got committed.

    The plant is the exact historical defect, so this row is the reason a second owner of the formula cannot
    come back: the number the transcript carries has to be the number the gate adds.
    """
    import json

    from tools import g5_transcript
    from autorate.cli import corpus_only_comparisons

    inv = json.loads((REPO / "data" / "inventory.md.json").read_text())
    derived = corpus_only_comparisons(inv)
    under = _minimal_record(**{"lane_present.output": "re-derived %d /%d values" % (242 + 35, 242 + 35)})
    record = _write(tmp_path, under)
    out = tmp_path / "G5.md"
    rc = g5_transcript.main(["--record", str(record), "--out", str(out)])
    assert derived != 35, "this tree adds 35 corpus-only comparisons, so the plant falsifies nothing"
    assert rc == 2, (rc, "a record whose lanes differ by the OLD undercount rendered anyway")
    assert not out.exists(), "the emitter wrote a transcript whose lanes are not the gate's"



def _history_available() -> bool:
    """Can this checkout answer questions about commits at all?

    One probe, consulted by every row that reads history, because the three of them each used to guess at
    their own skip condition from the failure MESSAGE -- and in a `git archive` export git says `not a git
    repository`, while for a sha the object database has never seen it says `Not a valid object name` with a
    capital N. A row that matched the lowercase spelling was dead code in a checkout and RED in the export,
    which is the opposite of what its docstring promised. Capability is the only thing worth gating on:
    present repository means the assertions run and a fabricated sha is RED, absent repository means the
    reader has no object database to consult and the row is SKIPPED.
    """
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--git-dir"],
                          capture_output=True).returncode == 0


def test_the_digest_the_transcript_prints_is_the_digest_of_the_commit_it_names(text, tmp_path):
    """What a transcript can be promised to keep true: its numbers match the commit it says it ran from.

    Deliberately NOT "the digest of the tree you are reading now". A transcript of commit X is a record about
    X, and it stays true when a later commit re-freezes; a row that demanded equality with the current digest
    would turn every legitimate re-freeze into a red CI, and a freeze commit cannot regenerate its own
    transcript because the export needs a sha that already exists. Truthfulness is enforced here; currency is
    stated in the transcript's own first block, where the reader can see which commit it describes.

    Plants: change one hex digit in the transcript, or point the file at a different commit -- either breaks
    the equality between what is printed and what the named commit actually holds. A sha the object database
    does not know is RED here, not skipped: `git show` failing is the finding, and only the absence of a
    repository to ask is a reason to say nothing.
    """
    from autorate.protocol import load_protocol, protocol_digest

    printed = set(DIGEST_RX.findall(text))
    assert printed, "the transcript names no protocol digest"
    sha = SHA_RX.search(text)
    assert sha, "the digest row cannot be checked without the commit the transcript names"
    if not _history_available():
        pytest.skip("no object database here (a `git archive` export), so the named commit cannot be read")
    raw = subprocess.run(["git", "-C", str(REPO), "show", "%s:protocol.json" % sha.group(1)],
                         capture_output=True)
    assert raw.returncode == 0, (sha.group(1), raw.stderr.decode()[:200])
    tmp = tmp_path / "protocol.json"
    tmp.write_bytes(raw.stdout)
    assert printed == {protocol_digest(load_protocol(tmp))}, sorted(printed)


def test_the_transcript_describes_a_commit_this_branch_can_reach(text):
    """Currency, stated rather than demanded: the transcript is of an ANCESTOR of the reader's tip.

    This is the honest half of "is it up to date" -- the named commit must be reachable from HEAD, so a
    transcript cannot be smuggled in from an abandoned branch -- without the freshness demand that a re-freeze
    could never satisfy in the same commit.

    Plant: name a commit this branch cannot reach. It must EXIST for this row to bite (a fabricated sha is
    what the `cat-file` row below refuses, and `merge-base` cannot distinguish the two -- it answers 128 for
    both an unknown sha and no repository, which is why the skip is gated on the probe above and not on
    git's message).
    """
    shas = set(SHA_RX.findall(text))
    assert shas, "the transcript does not name the commit it was produced from"
    if not _history_available():
        pytest.skip("no object database here (a `git archive` export), so ancestry cannot be asked")
    for sha in shas:
        probe = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", sha, "HEAD"],
                               capture_output=True)
        assert probe.returncode == 0, (sha, probe.stderr.decode()[:200])


def test_the_transcript_names_a_commit_that_exists_in_this_history(text):
    """`from a commit` is G5's own wording; the sha is what makes it checkable instead of rhetorical.

    Plant: replace the sha with one this repository has never had. The assertion runs `git cat-file`, and in
    a checkout with an object database a fabricated sha is RED -- earlier this row matched git's lowercase
    `not a valid object name`, which the tool never prints (it capitalises it), so the skip was dead code and
    the row only went red by a case-sensitivity accident. The skip is now gated on the capability probe, so
    the one environment that legitimately cannot answer -- a `git archive` export, which is exactly what the
    pre-push gate runs -- is the only one that stays quiet.
    """
    shas = set(SHA_RX.findall(text))
    assert shas, "the transcript does not name the commit it was produced from"
    if not _history_available():
        pytest.skip("no object database here (a `git archive` export), so the sha cannot be asked about")
    for sha in shas:
        probe = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", "%s^{commit}" % sha],
                               capture_output=True)
        assert probe.returncode == 0, (sha, probe.stderr.decode()[:200])


def test_a_fabricated_sha_is_red_rather_than_skipped_when_history_can_answer():
    """The negative control for the three rows above: their skip must not be an escape hatch.

    A guard that skips on the case it exists to catch is a comment, not a check -- that is precisely how the
    first version of these rows behaved (measured: an invented sha reached `pytest.skip`, and the export run
    went the other way and reddened a row whose docstring promised it would skip there). So this row feeds
    the two history rows a transcript of a commit this repository has never had and requires an assertion
    failure, in a checkout that CAN answer. It is skipped only where the rows themselves are skipped, so it
    can never be green by vacuity in an environment where nothing is checkable.
    """
    if not _history_available():
        pytest.skip("no object database here, so neither this row nor the rows it controls can answer")
    invented = "Produced from commit `%s` by `bash tools/g5_export.sh`\n" % "0123456789abcdef0123456789abcdef01234567"
    invented += "- protocol digest: `%s`\n" % ("0" * 64)
    with pytest.raises(AssertionError):
        test_the_transcript_names_a_commit_that_exists_in_this_history(invented)
    with pytest.raises(AssertionError):
        test_the_transcript_describes_a_commit_this_branch_can_reach(invented)


def test_the_transcript_carries_no_path_that_identifies_the_machine_it_ran_on(text):
    """Scratch directories are the leak a transcript is most likely to carry, in shapes the old guard missed.

    Plant: write the absolute path of any real temp directory into the file. The login-home shape was
    already refused by `tests/test_cli.py`'s tracked-tree guard -- named here as its account-name-free
    spelling, `/<Users>/<someone>/x`, because writing the real one would make this row the leak it hunts
    (see `test_the_recorder_files_themselves_carry_no_path_shape`) -- and this row covers the
    `/var/folders/...`, `/private/tmp/...` and `/tmp/...` shapes a run's own working directory actually
    takes, reading the WHOLE file rather than only the lines that happen to mention a path.
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


RECORDER_FILES = ("tools/g5_export.sh", "tools/g5_transcript.py",
                  "tests/test_g5_transcript.py", "docs/G5.md")

# The scratch root WITH a segment after it. `tests/test_cli.py:34` already carries `var/folders` in its
# login-home pattern; this is that same "an instantiated directory, not a shape being named" rule written out
# for the roots the tracked-tree scan deliberately leaves alone (`tests/test_cli.py:27-31 gives the reason:
# `/tmp/...` is how CI writes its own logs). Those roots are policed HERE and not there because these four
# files are the export's runner: a temp root with a directory under it is not prose about a shape, it is the
# path of a run. Prose that names a shape without instantiating it (`/var/folders/` with nothing after) is
# what this file itself has to say to describe the defect, so the pattern requires the segment.
SCRATCH_SEGMENT_RX = re.compile(r"/(?:var/folders|private/tmp|private/var|tmp)/[A-Za-z0-9._-]+/")


def test_the_recorder_files_themselves_carry_no_path_shape():
    """The gate hole this round fell into: an untracked file is a file no tracked-tree guard ever scanned.

    `tests/test_cli.py`'s `_path_offenders` takes its subject from `git ls-files` (or the export's manifest),
    so while these four files were new they were invisible to it: the commit that added them carried three
    path-shaped literals, and the first time anything said so was the pre-push export gate, after the bytes
    existed. A guard whose subject is "what git happens to track" cannot be the owner of "nothing in this
    deliverable may name a machine".

    So this row reads these four files BY PATH, whether or not git tracks them, with the two patterns the
    tracked-tree guard bites on: the login-home shape at `tests/test_cli.py:34` and the scratch shape above.
    (The emitter is stricter still -- `LEAK_RX` in `tools/g5_transcript.py` refuses the generated document on
    a bare temp root too -- and stays that way, because a transcript has no reason to name a shape.)

    Plant: put any account name or scratch directory into any of the four -- the row's first RED measured the
    round's own tree and named the file, the line and the shape.
    """
    offenders = []
    for rel in RECORDER_FILES:
        path = REPO / rel
        assert path.is_file(), "%s is missing -- this row would pass by reading nothing" % rel
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            for rx, name in ((MACHINE_PATH_RX, "login-home shape"),
                             (SCRATCH_SEGMENT_RX, "scratch shape")):
                hit = rx.search(line)
                if hit:
                    offenders.append((rel, i, name, hit.group(0)))
    assert not offenders, ("the recorder carries the shape it hunts: %s" % offenders[:4])


def test_each_plant_block_is_followed_by_a_restore_line_naming_its_own_file(text):
    """The restore evidence is read here, not just rendered: four plants, four files, four receipts.

    Review M5: the emitter printed "Each file is restored byte-identically afterwards" from a template while
    the restore lines themselves came in through `.get`, so a run interrupted between plant and restore -- or
    one whose `restore_check` wrote `RESTORE FAILED` -- still published the blanket sentence, and no row read
    the receipts at all. The emitter now refuses (rows below); this row is the other half: the document that
    did get written has to carry, under each plant block, the restore line FOR THAT PLANT'S OWN FILE, named
    by the same path the block's label names.

    Plant: delete one restore line, or hand-write the same line under all four blocks -- both fail.
    """
    from tools.g5_transcript import FALSIFICATIONS

    blocks = _blocks(text, FALSIFICATIONS_HEADING, AFTER_HEADING)
    assert len(blocks) == len(FALSIFICATIONS), (len(blocks), len(FALSIFICATIONS))
    targets = []
    for label, _rc, _output, trailing in blocks:
        found = TARGET_RX.search(label)
        assert found, "the plant label names no file, so its restore cannot be attributed: %r" % label
        target = found.group(0)
        targets.append(target)
        receipts = [line for line in trailing if "restored byte-identical" in line]
        assert len(receipts) == 1, (label, trailing)
        assert target in receipts[0], (target, receipts[0])
    assert len(set(targets)) == len(targets), targets


def test_the_four_plant_blocks_carry_four_distinct_outcomes(text):
    """Four defects, four different refusals -- a collapse is the symptom this round already shipped once.

    Review M7(ii): no row required the plant blocks to differ, and the run before this one published plant 3
    answering with plant 1's rubric error (and an earlier one put plants 2 and 3 on the same raise site). rc
    alone is not the claim: plants 2, 3 and 4 are all 4, and what distinguishes them is the clause the refusal
    states before it starts explaining itself. The two lanes are compared too, because a plant that quietly
    became "the gate ran fine" is a plant that did not fire.

    Plant: make two blocks print the same rc and the same first clause.
    """
    from tools.g5_transcript import FALSIFICATIONS

    lanes = [(rc, output.split(" -- ")[0].strip()) for _l, rc, output, _t in
             _blocks(text, LANES_HEADING, FALSIFICATIONS_HEADING)]
    plants = [(rc, output.split(" -- ")[0].strip()) for _l, rc, output, _t in
              _blocks(text, FALSIFICATIONS_HEADING, AFTER_HEADING)]
    assert len(plants) == len(FALSIFICATIONS), plants
    assert len(set(plants)) == len(plants), plants
    for plant in plants:
        assert plant not in lanes, (plant, lanes)


# --- the emitter itself -----------------------------------------------------------------------------------
# These four rows were written AFTER `tools/g5_transcript.py`, so they carry no red-first ordering; what they
# do carry is a plant each, and the ordering is disclosed here rather than left for a reader to assume. The
# transcript rows above were written first and watched to fail with `docs/G5.md` absent.

def _minimal_record(**over) -> str:
    """A complete record with one field replaced, so each row's failure is the one it names.

    The present lane's total is DERIVED from `cli.corpus_only_comparisons`, not typed: this fixture is the
    emitter's input, and a fixture that remembered a gap would go silently stale the same way the committed
    transcript did -- it would then be refusing to render for a reason that has nothing to do with the plant
    a row is asking about.
    """
    import json

    from autorate.cli import corpus_only_comparisons
    from autorate.protocol import load_protocol, protocol_digest

    gap = corpus_only_comparisons(json.loads((REPO / "data" / "inventory.md.json").read_text()))
    base = {
        "commit": "deadbeef",
        "env.git_dir": "ABSENT", "env.torch": "False", "env.transformers": "False",
        "env.prefix": "<export-dir>/.venv/bin/python3",
        "env.digest": protocol_digest(load_protocol(REPO / "protocol.json")),
        "env.network": "curl rc=6", "env.offline_flags": "HF_HUB_OFFLINE=1", "env.toolchain": "Darwin arm64",
        "lane_absent.command": "verify --protocol protocol.json (corpus absent)",
        "lane_absent.rc": "0", "lane_absent.output": "re-derived 242 /242 values",
        "lane_present.command": "verify --protocol protocol.json (corpus present)",
        "lane_present.rc": "0", "lane_present.output": "re-derived %d /%d values" % (242 + gap, 242 + gap),
        "tamper_protocol.command": "alpha moved", "tamper_protocol.rc": "4",
        "tamper_protocol.output": "RUBRIC MISMATCH",
        "tamper_protocol.target": "protocol.json",
        "tamper_protocol.restored": "protocol.json restored byte-identical",
        "swap_records.command": "records swapped", "swap_records.rc": "4", "swap_records.output": "DRIFT",
        "swap_records.target": "data/records_feishu.jsonl",
        "swap_records.restored": "data/records_feishu.jsonl restored byte-identical",
        "wrong_shape_snapshot.command": "snapshot []", "wrong_shape_snapshot.rc": "4",
        "wrong_shape_snapshot.output": "PUBLISHED ARTEFACT UNAVAILABLE",
        "wrong_shape_snapshot.target": "data/inventory.md.json",
        "wrong_shape_snapshot.restored": "data/inventory.md.json restored byte-identical",
        "tamper_artefact_digest.command": "one hex digit changed in a stamped digest",
        "tamper_artefact_digest.rc": "4",
        "tamper_artefact_digest.output": "re-derived 241 /242 values",
        "tamper_artefact_digest.target": "data/cert_laya.json",
        "tamper_artefact_digest.restored": "data/cert_laya.json restored byte-identical",
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

    Plant: put a scratch-directory path into `env.prefix`. `main` must exit 2 and leave no `docs/G5.md`
    behind -- a redacted-with-warning transcript is still a transcript that names a machine.

    The planted path is assembled from pieces, the way `tests/test_cli.py:1299` and `:1333` assemble theirs:
    this file hunts a shape, and typing one here -- least of all a real per-user hash prefix -- would make
    the row that catches the leak be the leak. `abcdef` is a made-up segment.
    """
    from tools import g5_transcript

    planted = "/" + "var/folders/" + "zz" + "/" + "abcdef" + "/T/g5-export"
    assert SCRATCH_PATH_RX.search(planted), planted
    record = _write(tmp_path, _minimal_record(**{"env.prefix": planted}))
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
    assert len(_blocks(text, FALSIFICATIONS_HEADING, AFTER_HEADING)) == int(prose.group(1)), prose.group(1)


def test_a_lane_that_did_not_exit_zero_is_refused_rather_than_rendered(tmp_path):
    """The criterion's own command has to have SUCCEEDED, and the renderer is where that is decided.

    Review M1: the contract row accepted 0/2/3/4 for every block and nothing distinguished a lane's exit
    code from a plant's, so a transcript whose two lanes read `rc=2` and `rc=4` -- a refusing gate -- passed
    all eight rows and still said "each with its own exit code". A record of a red run is not a reproduction
    transcript, and the point at which that becomes un-writable has to be the writer, not a test that runs
    after the tracked file was overwritten.

    Plant: any non-zero rc on either lane prefix, for each of the four codes the contract allows.
    """
    from tools.g5_transcript import TranscriptRefusal

    for prefix in ("lane_absent", "lane_present"):
        for code in ("2", "3", "4"):
            with pytest.raises(TranscriptRefusal, match=prefix):
                _render(tmp_path, _minimal_record(**{"%s.rc" % prefix: code}))


def test_a_recorded_exit_code_outside_the_contract_is_refused_rather_than_rendered(tmp_path):
    """The emitter must not be able to publish a contract violation -- that was the root of B1.

    `docs/G5.md` shipped an `rc=1` once because `tools/g5_transcript.py` rendered any `\\d+` it was handed and
    only a downstream test noticed, after the tracked file had already been written. The refusal is in
    `_step` now, so the document cannot exist; `main` answers it with exit 2 and writes nothing.

    Plant: rc 1 on a lane and on a falsification; a value that is not a bare number at all.
    """
    from tools import g5_transcript
    from tools.g5_transcript import TranscriptRefusal

    for prefix in ("lane_present", "swap_records"):
        with pytest.raises(TranscriptRefusal, match=prefix):
            _render(tmp_path, _minimal_record(**{"%s.rc" % prefix: "1"}))
    with pytest.raises(TranscriptRefusal, match="not an exit code"):
        _render(tmp_path, _minimal_record(**{"tamper_protocol.rc": "rc=1"}))
    with pytest.raises(TranscriptRefusal, match="not an exit code"):
        _render(tmp_path, _minimal_record(**{"tamper_protocol.rc": "0 or 4"}))
    record = _write(tmp_path, _minimal_record(**{"tamper_artefact_digest.rc": "7"}))
    out = tmp_path / "G5.md"
    assert g5_transcript.main(["--record", str(record), "--out", str(out)]) == 2
    assert not out.exists(), "the emitter published a record whose exit code is outside the contract"


def test_a_falsification_with_no_restore_evidence_is_refused(tmp_path):
    """A plant whose file never came back leaves the export tampered, and the sentence said nothing failed.

    Review M5: `render()` printed "Each file is restored byte-identically afterwards" from the template while
    the restore line came from `flat.get(...)`, so an interrupted run -- plant applied, restore never checked
    -- published the promise anyway. Each falsification now has to carry its own receipt, naming its own file.

    Plant: delete one `<prefix>.restored`, and separately delete one `<prefix>.target`.
    """
    from tools.g5_transcript import FALSIFICATIONS, TranscriptRefusal

    for prefix in FALSIFICATIONS:
        with pytest.raises(TranscriptRefusal, match="%s.restored" % prefix):
            _render(tmp_path, _minimal_record(**{"%s.restored" % prefix: None}))
    with pytest.raises(TranscriptRefusal, match="swap_records.target"):
        _render(tmp_path, _minimal_record(**{"swap_records.target": None}))


def test_a_restore_line_that_reports_failure_or_wrong_file_is_refused(tmp_path):
    """`RESTORE FAILED` under a sentence that says every file came back is the document lying about itself.

    Plants: a receipt that reports the failure the runner records, a receipt that reports neither success nor
    failure, and a receipt for the wrong file.
    """
    from tools.g5_transcript import TranscriptRefusal

    with pytest.raises(TranscriptRefusal, match="RESTORE FAILED"):
        _render(tmp_path, _minimal_record(**{
            "swap_records.restored": "RESTORE FAILED (copy back) for data/records_feishu.jsonl"}))
    with pytest.raises(TranscriptRefusal, match="restored byte-identical"):
        _render(tmp_path, _minimal_record(**{"swap_records.restored": "wrote the file back, probably"}))
    with pytest.raises(TranscriptRefusal, match="names no file the record"):
        _render(tmp_path, _minimal_record(**{
            "swap_records.restored": "data/cert_jev.json restored byte-identical"}))


def test_a_plant_that_did_not_land_is_refused(tmp_path):
    """A falsification that never fired is not evidence, and a note about it may not be published as one.

    Review M6: `sed -i '' 's/"alpha": 0.05/"alpha": 0.07/'` no-ops silently the moment the frozen value or its
    spacing moves, and the digest-flipping heredoc's exit code was discarded -- either way the step recorded
    `rc=0`, the transcript printed a "defect" that changed nothing, and every row stayed green. The runner now
    `cmp`s the target against its backup after each plant and records the note below; the emitter refuses on
    it, so a plant that did not fire cannot become a document.

    Plant: put the note on any falsification.
    """
    from tools.g5_transcript import FALSIFICATIONS, TranscriptRefusal

    for prefix in FALSIFICATIONS:
        with pytest.raises(TranscriptRefusal, match="PLANT DID NOT LAND"):
            _render(tmp_path, _minimal_record(**{
                "%s.note" % prefix: "PLANT DID NOT LAND for data/records_feishu.jsonl"}))


def test_the_restore_sentence_is_a_count_read_off_the_record(tmp_path):
    """The blanket claim became a count, and the count is the number of receipts the record actually holds.

    Review M5 asked for the sentence to be derived from the restore evidence rather than asserted
    unconditionally. Because a missing or failed receipt now refuses the document, the published pair is
    always `N of N` -- which is the point: it is computed from `len(FALSIFICATIONS)` receipts that each passed
    the check, and a run that restored three of four never reaches the sentence at all.

    Plant: drop one receipt and the refusal fires before any count is printed.
    """
    from tools.g5_transcript import FALSIFICATIONS, TranscriptRefusal

    rendered = _render(tmp_path, _minimal_record())
    found = re.search(r"(\d+) of (\d+) (?:files|planted files) came back byte-identical", rendered)
    assert found, [line for line in rendered.splitlines() if "byte-identical" in line]
    assert found.group(2) == str(len(FALSIFICATIONS)), found.group(0)
    assert found.group(1) == found.group(2), found.group(0)
    assert "Each file is restored byte-identically" not in rendered
    with pytest.raises(TranscriptRefusal):
        _render(tmp_path, _minimal_record(**{"tamper_protocol.restored": None}))


def test_two_plants_answering_identically_are_refused(tmp_path):
    """Four blocks that say the same thing are one block, and the transcript would claim four checks.

    Review M7(ii) measured the run where plant 3 published plant 1's rubric error: same class of outcome,
    different defect, one symptom counted twice. The document row
    (`test_the_four_plant_blocks_carry_four_distinct_outcomes`) reads the published blocks; this row is the
    same rule at emit time, so the record cannot produce a document that the row would later have to redden.

    Plant: give `swap_records` the answer `tamper_protocol` gave -- same rc, same first clause.
    """
    from tools.g5_transcript import TranscriptRefusal

    with pytest.raises(TranscriptRefusal, match="same code and the same first clause"):
        _render(tmp_path, _minimal_record(**{"swap_records.output": "RUBRIC MISMATCH",
                                             "swap_records.rc": "4"}))
    # ...and the collapse does not have to be with plant 1: any two plants on one outcome are the same defect
    with pytest.raises(TranscriptRefusal, match="same code and the same first clause"):
        _render(tmp_path, _minimal_record(**{"wrong_shape_snapshot.output": "DRIFT"}))
