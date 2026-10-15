"""Task #90: the slice producer's `main()` refuses with the exit codes its own docstring promises.

`tools/language_slices.py` publishes the G4 slice artefact. Its docstring closes with a contract: "0 when the
document is written ..., 2 for the refusals above and for an existing `--out` without `--force`. Nothing
escapes un-mapped: the refusals are this file's own exception types." Task #86 wired that contract, and
measurement confirms every arm already answers correctly -- a duplicate `case_id` inside a declared input
returns rc 2 naming the id and both files, a missing declared input returns rc 2, a `--doc` at the wrong
paths returns rc 2 and writes nothing.

None of it was tested at the entry point. `tests/test_slice_surface.py` drives `refuse_missing_inputs()` and
`check_rows()` directly, which proves the two helpers and leaves `main()`'s mapping unpoliced: deleting the
`except (SliceInputRefusal, report.PublishedArtefactUnavailable)` block, or flipping a `return 2` to
`return 0`, left the suite green. `docs/ERRATA.md` says so out loud at the disclosure that closes task #86 --
"the rows written to close it were reverted rather than shipped half-right, so `tools/language_slices.py`'s
refusals are still unasserted through its own command". Those are the gaps this file closes. Six rows drive the
real `main(argv)`, each docstring naming the production change that reddens it, a seventh pins three measured
shapes that escape `main` entirely, and an eighth pins the clause that keeps a refusal this file has no class
for inside the same contract.

Three rules this file holds itself to.

*Assert the sentence, not only the number.* Four distinct refusals here all answer 2, so `rc == 2` alone is
satisfied by whichever guard happened to fire first -- measured in the making of this file, where a scratch
tree with the wrong layout returned 2 from the missing-input arm while the row was aiming at the duplicate-id
arm. Every row therefore asserts the refusal's own words AND that the arm it targets is the one that spoke,
and the rows that aim at a guard placed *after* an earlier one build a scratch checkout in which the earlier
guard is satisfied.

*Nothing under `data/` or `docs/` is written.* The producer resolves `report.SLICE_RECORDS` against the
working directory, so a refusal is provoked by pointing a scratch tree's `data/` at copied rows, never by
deleting a committed file. A missing declared input is provoked by patching the table itself, which is the
only way to test it without touching the tree.

Two different things are pinned here, and they were red and green in different orders.

*Rows 1, 2 and 6 are green on arrival* -- the behaviour exists, and what is new is that it can no longer be
deleted silently. All three were proven falsifiable by mutating a scratch copy of the producer and running
this file against it: dropping the overwrite guard (row 1), dropping the `--doc` path guard (row 2), and
`return 2` -> `return 0` in `refuse_missing_inputs` (row 6's control is the run that shows the guards are
guards rather than unconditional refusals). Row 8 arrived the same way, for the same reason, and was
falsified by deleting the blanket clause it polices.

*Rows 3, 4, 5 and 7 were written red* and are the contract R-272 adopts: a defect in bytes at a
table-declared path is the checkout's failure, so it exits 4, not the operator's usage error at 2. Measured
before that ruling these four shapes all answered 2 (rows 3-5) or escaped at 1 (row 7's three shapes:
`AttributeError`, `records.MissingRecordField`, `groups.UndeclaredGroupKey`). Their message assertions were
written first and did not change when the code did -- only the expected number did, which is the test that
the sentence, not the number, is what the row is guarding.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autorate import cli, report
from autorate.cli import EXIT_DRIFT, EXIT_USAGE

REPO = Path(cli.__file__).resolve().parents[2]
PRODUCER_PATH = REPO / "tools" / "language_slices.py"
# The declared inputs, read from the table rather than restated, so a row cannot aim at a file the producer
# no longer asks for. `DE` is the one each scratch checkout mutates.
DE, EN, SW = report.SLICE_RECORDS
PRE_EXISTING = "PRE-EXISTING CONTENT THAT A REFUSED RUN MUST NOT REPLACE\n"


def _load(path):
    """Import the producer by path.

    It is a tool in `tools/`, not a module in `src/autorate`, so the package's own import machinery does not
    reach it; `tests/test_slice_surface.py` gets here through `pythonpath = ["."]` and `from tools import ...`.
    Loading by path instead keeps this file working when the repo root is not on `sys.path` and gives each row
    a fresh module, which is what lets a mutated scratch copy be driven by the same code.
    """
    spec = importlib.util.spec_from_file_location("language_slices_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def producer():
    return _load(PRODUCER_PATH)


def _scratch_checkout(root):
    """Lay the three declared inputs out under `root/data/`, one committed row each, and return those rows.

    The producer reads its inputs as repo-relative strings, so a scratch tree that wants `main()` to get past
    `refuse_missing_inputs()` has to carry the same `data/<name>` spelling. One row per file is enough: both
    guards this file aims at run over the rows before anything is certified, and a full 2,974-row copy per row
    would make the suite read the corpus three times to prove a refusal that fires on the second line.
    """
    rows = {}
    for rel in report.SLICE_RECORDS:
        with (REPO / rel).open() as handle:
            line = handle.readline().rstrip("\n")
        rows[rel] = json.loads(line)
        _write(root / rel, [rows[rel]])
    return rows


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _rebind(row, language):
    """The row, restating one slice language while its `case_id` keeps its own."""
    return dict(row, slices=dict(row["slices"], language=language))


def _without_language(row):
    """The row, stating nothing for the slice key its `case_id` already spells."""
    return dict(row, slices={k: v for k, v in row["slices"].items() if k != report.SLICE_GROUP_KEY})


def _assert_named_refusal(err, needle):
    assert needle in err, err
    assert "Traceback" not in err, err


def test_an_existing_out_without_force_is_refused_and_left_untouched(producer, tmp_path, monkeypatch, capsys):
    """RED if: the `if out.exists() and not args.force` guard is dropped, or its `return 2` becomes `return 0`.

    Measured against a scratch copy with that guard deleted: the same argv answered rc 0 and replaced the
    file's bytes, which is the whole defect the guard exists to stop -- the published artefact is a tracked
    file, and a re-run that silently rewrites it is a re-run that silently rewrites the evidence.

    The `--force` arm is in the same row on purpose. Without it, rc 2 would also be printed by a `--out` the
    producer cannot reach at all (a directory, a path outside the repo, a typo), and the row would pass while
    testing nothing.
    """
    monkeypatch.chdir(REPO)
    target = tmp_path / "slices_language.json"
    target.write_text(PRE_EXISTING)

    assert producer.main(["--out", str(target)]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert str(target) in err, err                       # the path the operator named
    assert "--force" in err, err                          # and the flag that would have made it legal
    _assert_named_refusal(err, "already exists")
    assert target.read_text() == PRE_EXISTING, "the refused run replaced the file it said it would not touch"

    # control: the identical call with --force writes the artefact, so the guard above is the only thing that
    # stopped it, and `--out` really is reachable from a scratch directory.
    assert producer.main(["--out", str(target), "--force"]) == 0
    assert target.read_text() != PRE_EXISTING
    assert "run" in json.loads(target.read_text()), "the forced run wrote something that is not the artefact"


def test_a_document_is_only_written_by_the_run_at_the_declared_paths(producer, tmp_path, monkeypatch, capsys):
    """RED if: the `args.doc is not None and (...)` guard is dropped or narrowed to check only `--doc`.

    Measured against a scratch copy with the check removed: rc 0, and `docs/SLICES.md`'s own text was written
    beside an artefact at the operator's path -- a document whose first line says it was
    "Written by `python3 tools/language_slices.py --out data/slices_language.json`", quoting figures from a
    run that wrote somewhere else entirely. That misattribution is what the guard exists to stop, and it is
    invisible to `verify`, which re-derives the artefact and never learns which path produced the document.

    Asserts both declared paths appear in the refusal and that NEITHER file was written: the guard runs before
    anything is read, certified or written, so its own promise ("Nothing was written") is checkable.
    """
    monkeypatch.chdir(REPO)
    out = tmp_path / "someone_elses_artefact.json"
    doc = tmp_path / "SLICES.md"

    assert producer.main(["--out", str(out), "--doc", str(doc)]) == EXIT_USAGE
    err = capsys.readouterr().err
    _assert_named_refusal(err, "--doc publishes")
    assert str(report.SLICE_MD) in err, err               # the declared document path
    assert str(report.SLICE_JSON) in err, err             # the declared artefact path it quotes
    assert str(out) in err and str(doc) in err, err        # and what this run actually named
    assert not out.exists() and not doc.exists(), "the refusal said 'Nothing was written' and wrote both"


def test_a_declared_input_the_table_names_and_the_checkout_lacks_is_refused(
        producer, tmp_path, monkeypatch, capsys):
    """RED if: `refuse_missing_inputs()`'s `return 2` becomes `return 0`, or `main` stops honouring its code.

    Measured against a scratch copy with that one literal flipped, and the measurement is the interesting
    part: the run still exits 2, because `build_document()` raises its own `SliceInputRefusal` on the same
    absent file and the `except` tuple maps it. What the operator loses is the sentence -- instead of being
    told which table declares the input, how many the run needs, and that nothing was written, they get
    `<path>: declared input is missing`, which names neither the owning table nor the fact that the other two
    files were left unread. So this row cannot assert rc alone (both arms answer 2) and does not: it asserts
    the table's own words, and those are what the flipped literal takes away.

    Provoked by patching the table, not by deleting a committed file: `data/records_massive_*.jsonl` are the
    evidence, and a test that removed one to make a guard fire would be editing the repository to prove
    something about the repository.
    """
    monkeypatch.chdir(REPO)
    absent = "data/records_massive_zz_that_is_not_committed.jsonl"
    assert not (REPO / absent).exists(), "the scratch fixture only refuses if the path really is absent"
    monkeypatch.setattr(report, "SLICE_RECORDS", (DE, absent, SW))
    out = tmp_path / "artefact.json"

    assert producer.main(["--out", str(out)]) == EXIT_DRIFT
    err = capsys.readouterr().err
    _assert_named_refusal(err, absent)                    # the file that is not there, named
    assert "Nothing was written" in err, err
    # the two files the checkout does hold are NOT reported missing -- a refusal that listed all three would
    # send the operator looking for files that are present.
    assert DE not in err and SW not in err, err
    assert not out.exists()


def test_a_case_id_repeated_inside_a_declared_input_is_refused_and_named(
        producer, tmp_path, monkeypatch, capsys):
    """RED if: the `except (SliceInputRefusal, ...)` block is deleted, or `check_rows` stops tracking ids.

    Measured against a scratch copy with the handler unwrapped (`doc = build_document()`): the same fixture
    died on an un-mapped traceback instead of printing the refusal. A repeated id is one observation counted
    twice, and a per-slice denominator built from it claims more independent cases than the corpus holds --
    the refusal has to name the id, because the file holds 2,974 rows and "one of them was wrong" is not
    actionable.

    Two legs, because the guard and the mapping are different claims: `check_rows` on a scratch file with one
    line copied twice proves the refusal exists and says *which* id; `main` on the same scratch checkout
    proves the refusal reaches the operator at rc 2 rather than as a traceback.
    """
    rows = _scratch_checkout(tmp_path)
    line = json.dumps(rows[DE], sort_keys=True)
    assert rows[DE]["case_id"] == "massive/de/0", rows[DE]["case_id"]
    dup_path = tmp_path / DE
    _write(dup_path, [rows[DE], rows[DE]])                 # the same committed row, twice
    assert dup_path.read_text().count("\n") == 2

    # leg 1: the check function itself, on the scratch file of records
    raw = json.loads(line)
    with pytest.raises(producer.SliceInputRefusal, match="also appears in") as caught:
        producer.check_rows([(dup_path, [raw, dict(raw)])])
    assert "id 'massive/de/0/laya'" in str(caught.value), caught.value
    assert str(dup_path) in str(caught.value), caught.value

    # leg 2: the same defect through the entry point, with the earlier guards satisfied
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "artefact.json"
    assert producer.main(["--out", str(out)]) == EXIT_DRIFT
    err = capsys.readouterr().err
    _assert_named_refusal(err, "id 'massive/de/0/laya' also appears in")
    assert DE in err, err                                   # names the declared file, as the table spells it
    assert not out.exists()


def test_a_row_whose_declared_language_contradicts_its_case_id_is_refused(
        producer, tmp_path, monkeypatch, capsys):
    """RED if: the `parts[1] != stated` branch is dropped, or the `except` tuple stops catching its refusal.

    MEASURED, not assumed: this is rc 2 with a named row, not an escape. The contradiction is against `sw`
    rather than a nonsense language on purpose -- `sw` is a slice this run publishes, so the row describes two
    real subjects and which slice it lands in depends on which field the tool believes. `split_records.py`
    proves the claim for the split direction; the merge direction inherits it, re-derived from the row's own
    bytes rather than from the filename it happens to sit in.
    """
    rows = _scratch_checkout(tmp_path)
    contradicting = _rebind(rows[DE], "sw")
    assert contradicting["case_id"].split("/")[1] == "de", contradicting["case_id"]
    assert rows[EN]["slices"]["language"] == "en" and rows[SW]["slices"]["language"] == "sw", rows
    # `sw` is a slice this run really publishes, so the scratch tree now holds one row that describes two
    # subjects; every other row still agrees with itself, so this refusal can only be about the contradiction.
    _write(tmp_path / DE, [contradicting])

    monkeypatch.chdir(tmp_path)
    out = tmp_path / "artefact.json"
    assert producer.main(["--out", str(out)]) == EXIT_DRIFT
    err = capsys.readouterr().err
    _assert_named_refusal(err, "two subjects")
    assert "massive/de/0" in err and "'de'" in err and "'sw'" in err, err
    assert "slices.language = 'sw'" in err, err             # the key and the value it contradicts, spelled out
    assert DE in err, err
    assert not out.exists(), "the refused run wrote an artefact built on a row that names two slices"


def test_the_success_path_publishes_an_artefact_whose_run_block_carries_the_group_results(
        producer, tmp_path, monkeypatch, capsys):
    """RED if: `out.write_text` or the `run = certify_choice(...)` line goes, or the document loses a block.

    The one row that has to reach rc 0, and the only one that proves every guard above is a *guard* rather
    than an unconditional refusal -- measured against the scratch copies, the two `return 2`s this file aims at
    first were both reached by runs that would otherwise have written the artefact.

    Structure only. `n_groups`, `level`, `qhat` and the rest belong to `verify`'s re-derivation arm
    (`tests/test_slice_surface.py`), and a producer test that restates them duplicates a number the gate
    already owns and will disagree with on the next corpus change.
    """
    monkeypatch.chdir(REPO)
    out = tmp_path / "slices_language.json"

    assert producer.main(["--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("wrote %s" % out), captured.out
    assert "Traceback" not in captured.err, captured.err
    assert out.is_file(), "rc 0 with no artefact is the loudest failure this tool can produce"

    doc = json.loads(out.read_text())
    assert doc["producer"] == producer.PRODUCER == "tools/language_slices.py"
    assert doc["group_key"] == report.SLICE_GROUP_KEY
    assert doc["backend"] == report.SLICE_BACKEND
    assert [row["path"] for row in doc["inputs"]] == sorted(report.SLICE_RECORDS)
    for row in doc["inputs"]:
        assert set(report.SLICE_INPUT_FIELDS) <= set(row), row

    run = doc["run"]
    assert run["groups"] == [doc["group_key"]], run["groups"]
    assert run["n_groups"] == len(run["per_group"]) > 0, run["n_groups"]
    for group, cert in run["per_group"].items():
        missing = [f for f in report.SLICE_GROUP_FIELDS if f not in cert]
        assert not missing, "%s: %s" % (group, missing)
    assert run["thinnest"] in run["per_group"], run["thinnest"]
    assert set(report.SLICE_POOLED_FIELDS) <= set(run["pooled"]), sorted(run["pooled"])
    # `SLICE_WORST_FIELDS` is not a subset of the stored block: the `group` the gate compares is DERIVED by
    # `report.worst_of` from the nested `worst` certificate, so the artefact stores the group one level down.
    # Asserting the stored shape here, because a row that asked for `group` at the top level would fail on
    # correct bytes and teach the next reader to delete the field list.
    claim = run["worst_claim"]
    assert {"joint_level", "joint_level_risk", "level", "metric", "worst"} <= set(claim), sorted(claim)
    assert claim["worst"]["group"] in run["per_group"], claim["worst"].get("group")
    assert set(report.SLICE_COMPARE_FIELDS) <= set(run), sorted(run)
    assert isinstance(run["feasible"], bool) and isinstance(run["any_slice_refused"], bool)
    assert isinstance(run[report.SLICE_N_MIN_KEY], list)
    assert len(run["envelope"]) > 0, "the run publishes no envelope, so a reader cannot see its budget"
    assert report.SLICE_RUBRIC_FIELDS == tuple(sorted(doc["rubric"])), sorted(doc["rubric"])


def test_a_declared_input_that_is_wrong_shaped_is_refused_by_name_at_four(producer, tmp_path, monkeypatch,
                                                                          capsys):
    """R-272: a declared input this build cannot read is the checkout's failure, so it is exit 4, named.

    This row replaces a characterisation pin. The measurement that produced the pin found three shapes that
    escaped `main` entirely and exited 1 -- outside the 0/2/3/4 contract this file's own docstring states:

    * `slices` a bare string instead of a mapping, which died on `check_rows`'s `.get` as an `AttributeError`;
    * a line that parses as JSON but is not a `Record` (`autorate.records.MissingRecordField`), raised inside
      `report.slice_inputs()`;
    * a row that states no value for the slice key at all (`ValueError` from `groups.by_group`, which is
      `groups.UnplacedCase` since task #98 named it).

    Three different fixes, one per refusing layer, and none of them a widened catch:
    `check_rows` refuses the non-mapping `slices` by name at its own raise site (catching `AttributeError`
    centrally would land a genuine bug inside a refusal -- the failure B1 Task 1 recorded when a widened
    `except ValueError` swallowed a policy refusal); `records.MissingRecordField` and
    `groups.UndeclaredGroupKey` are named in `main`'s tuple BY CLASS; and the third shape -- a committed case
    that states no value for a key the other rows DO declare -- reached `groups.py:163` and raised a bare
    `ValueError` with no class to name, so it was converted at the producer's own call site and kept the
    certifier's words. Giving that shape its own class belongs to every caller of `by_group` and was filed,
    not silently done here; task #98 closed that filing, so the shape now arrives as `groups.UnplacedCase`
    and `build_document` keys on the class. The sentence this row asserts is that clause's, which is what
    makes deleting it visible here instead of silent -- row 8 asserts the other clause's sentence.
    All of this is safe only because `SliceInputRefusal` is now a `RuntimeError`, so
    no `except ValueError` in this file can swallow a refusal the file raises on purpose.

    RED if any of the three stops being refused: the first by name, the others by the mapping. Asserting a
    named refusal also means asserting the absence of a traceback, because rc 4 printed over a stack is the
    same un-mapped escape in a different costume, and that no artefact was written.
    """
    rows = _scratch_checkout(tmp_path)
    # `row_identity` differs per shape because the layer that refuses differs: `check_rows` holds the parsed
    # row and names its `id`, the loader holds only what the line states (this one says `id: "x"` and is
    # refused by that id, not by its `case_id`), and the certifier works in cases. A blanket "the refusal must
    # name the case" assertion would have failed on the loader's honest message, so each row is asked for the
    # identity its own refusing layer can actually print.
    shapes = (
        ("slices-is-a-string", dict(rows[DE], slices="de"), "not a mapping", "'massive/de/0/laya'"),
        ("line-is-not-a-record", {"id": "x", "case_id": "massive/de/0", "backend": "laya",
                                   "gold": "alarm_set", "slices": {"language": "de"}},
         "MissingRecordField", "record 'x'"),
        ("no-slice-value", _without_language(rows[DE]), "the certifier refused these rows", "massive/de/0"),
    )
    for leaf, row, needle, row_identity in shapes:
        root = tmp_path / leaf
        _scratch_checkout(root)
        _write(root / DE, [row])
        monkeypatch.chdir(root)
        out = root / "artefact.json"

        assert producer.main(["--out", str(out)]) == EXIT_DRIFT, (leaf, "a wrong-shaped declared input is "
               "the checkout's failure, not the operator's: no flag of theirs names these paths")
        err = capsys.readouterr().err
        assert err.strip(), (leaf, "exit 4 with no message tells the reader nothing about the row")
        assert "Traceback" not in err, (leaf, err[-300:])
        assert needle in err, (leaf, err)
        assert "DECLARED INPUT UNREADABLE" in err, (leaf, err)
        assert DE in err, (leaf, "the refusal must name which declared file it could not read: %s" % err)
        assert row_identity in err, (leaf, "a refusal about committed rows must name the row: %s" % err)
        assert not out.exists(), (leaf, "the refused run wrote an artefact built on bytes it called unreadable")

        # and from a real process: the file's bottom line is `sys.exit(main())`, and rc 1 is what this
        # shape used to produce, so the contract is only held if the process itself says 4
        proc = subprocess.run([sys.executable, str(PRODUCER_PATH), "--out", str(out)],
                              cwd=str(root), capture_output=True, text=True)
        assert proc.returncode == EXIT_DRIFT, (leaf, proc.returncode, proc.stderr[-300:])
        assert "Traceback" not in proc.stderr, (leaf, proc.stderr[-300:])


def test_a_refusal_this_file_has_no_class_for_still_lands_on_four_and_not_on_one(
        producer, tmp_path, monkeypatch, capsys):
    """RED if `build_document`'s blanket `except ValueError` clause is deleted, or narrowed to exactly the
    four classes it now names: an unclassified `ValueError` would then leave `build_document`, match nothing
    in `main`'s tuple, and reach the operator as rc 1 -- the code this file's docstring forbids, and the
    escape `bdc1aad` measured and closed.

    Task #98 gave the three placement refusals `groups.by_group` raises their own classes, so the first
    clause keys on the class and this clause keys on the absence of one. Two clauses, two sentences, and
    each is asserted only here: the wrong-shape row above pins the sentence the class-keyed clause prints,
    this row pins the sentence the blanket clause prints AND asserts the other sentence is absent. Neither
    clause can therefore be deleted with the suite green, which is the gap this file's own opening records
    about task #86 -- helpers driven directly, `main`'s mapping unpoliced.

    The certifier is replaced rather than the rows crafted, because the shape this clause guards is a
    `ValueError` this file has no name for, which by construction is none of the four named classes and no
    record set produces it. The process leg is not repeated here: a monkeypatch does not cross into the
    child, and the real-process half of the rc-1 contract is asserted in the row above.
    """
    _scratch_checkout(tmp_path)
    monkeypatch.chdir(tmp_path)

    def _unnamed_refusal(*args, **kwargs):
        raise ValueError('a refusal no class here covers')

    monkeypatch.setattr(producer, "certify_choice", _unnamed_refusal)
    out = tmp_path / "artefact.json"

    assert producer.main(["--out", str(out)]) == EXIT_DRIFT, (
        "a refusal about bytes at a declared path is the checkout's failure even when this file cannot "
        "name it: no operator flag repairs it and rc 1 is outside the published contract")
    err = capsys.readouterr().err
    assert "a refusal no class here covers" in err, (err, "the certifier's own words must survive")
    assert "ValueError" in err, (err, "an unnamed refusal has to be reported as unnamed")
    assert "refusal this file has no class for" in err, err
    assert "the certifier refused these rows" not in err, (
        err, "the class-keyed clause did not speak, so this refusal came from the blanket one")
    assert "Traceback" not in err, err
    assert not out.exists(), "the refused run wrote an artefact built on a batch it called unreadable"
