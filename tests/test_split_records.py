"""Plan C Task 4: the split helper that turns one scored artefact into three committed ones.

The brief asks for a partition-preserving split, proved rather than asserted, because `verify`
has to be able to say where its inputs came from: the multiset of `id`s across the per-language
files equals the multiset in the source, no `id` appears twice, and every file's row count is
stated. Three claims, so three planted defects -- one per claim -- each driven to its red here:

    duplicate id in the source      breaks "no id appears twice"
    a line moved between files      breaks the routing claim the multiset cannot see
    a line deleted after writing    breaks "the multiset equals the source's"

The middle plant is the one that matters. `sorted(ids) == sorted(ids)` is symmetric: swap two
lines between `en` and `de` and the multisets still agree, no id repeats, and only a checker that
re-derives each line's language from its own `case_id` says the line is in the wrong file. So
`check_written` reads the files back from disk and re-derives everything, and these tests plant
into the artefact rather than into the fixture's in-memory copy.

Two more refusals the tool owes a committed artefact: a line whose `id` and `case_id` name
different languages (one row, two subjects -- which file would a reader believe?), and a line
that is not the producer's canonical JSON (a hand-edit, which is the same defect class as the
digit guard `verify` exists to catch).

Nothing here reads the scored artefact these files were split from: it is a build product that
lives outside the repository, not a test input, and a test that needed it would be red on every
machine except the one that ran the 42-minute pass. The committed
artefacts it produced are checked in `test_the_committed_split_is_the_partition_the_tool_proved`,
which reads only tracked files. Paths are arguments and fixtures are `tmp_path` -- no absolute
machine path enters this file or the tool it drives.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from autorate.records import Record
from tools.split_records import (DEFAULT_NAME_FORMAT, PartitionError, WrittenDrift,
                                case_language, check_written, main, route_lines)

REPO = Path(__file__).resolve().parents[1]
SPLITTER = REPO / "tools" / "split_records.py"


def _row(lang, index, backend="laya", utterance=None, gold="alarm_set"):
    """One row in the shape the scoring driver writes: canonical, sorted keys, `ensure_ascii`."""
    case_id = "massive/%s/%d" % (lang, index)
    return json.dumps({
        "backend": backend,
        "case_id": case_id,
        "gold": gold,
        "id": "%s/%s" % (case_id, backend),
        "meta": {"calibration_status": "clamped by upstream to [0.5, 5]", "regime": "clamped",
                 "revision": "940fd47a81eaa7f2cc7b129674d945d618ac38c2",
                 "source": "tools/build_records.py", "utterance": utterance or ("say %s %d"
                                                                               % (lang, index))},
        "options": ["alarm_set", "alarm_remove", "takeaway_order", "music_settings"],
        "predicted": gold,
        "probs": [0.7, 0.1, 0.1, 0.1],
        "qtype": "choice",
        "repeat": 1,
        "scores": {"answer_confidence": 0.7, "confidence": 0.7, "p_gold": 0.7},
        "seed": 13,
        "slices": {"language": lang, "mode": "choice", "option_count": 4, "regime": "clamped"},
        "u": 0.25,
    }, sort_keys=True)


def _source(tmp_path, rows, name="rec_full.jsonl"):
    path = tmp_path / name
    path.write_text("".join(r + "\n" for r in rows))
    return path


def _run(*argv):
    return subprocess.run([sys.executable, str(SPLITTER), *argv],
                          capture_output=True, text=True)


# ------------------------------------------------------------------ the routing, in memory
def test_every_line_is_routed_by_its_own_case_id_and_moved_verbatim():
    rows = [_row("en", 0), _row("de", 0), _row("en", 1), _row("sw", 42)]
    routed, claims = route_lines(rows)
    assert sorted(routed) == ["de", "en", "sw"], routed
    # The lines are MOVED, not re-serialized: byte identity with the source is what lets the
    # certificate be re-derived from the same doubles the driver wrote.
    assert routed["en"] == [rows[0], rows[2]]
    assert routed["de"] == [rows[1]] and routed["sw"] == [rows[3]]
    assert claims["source_rows"] == 4 and claims["duplicate_ids"] == []


def test_the_case_id_grammar_is_the_one_the_driver_writes():
    assert case_language("massive/en/0") == "en"
    # 2-letter here, but the grammar is "the second segment", not "two letters": a 3-letter
    # MASSIVE code (`afr`, `swe`) is the same shape and must not be refused.
    assert case_language("massive/afr/17179") == "afr"
    for bad in ("en/0", "massive//0", "other/en/0", "massive/en", "", "massive/EN/0"):
        with pytest.raises(PartitionError, match="case_id"):
            case_language(bad)


def test_partition_claims_state_the_three_numbers_the_brief_asks_for():
    rows = [_row("en", i) for i in range(3)] + [_row("de", i) for i in range(2)]
    routed, claims = route_lines(rows)
    assert claims["per_file_rows"] == {"de": 2, "en": 3}
    assert claims["multiset_equal"] is True
    assert claims["missing_ids"] == [] and claims["extra_ids"] == []
    assert claims["misrouted_lines"] == []
    # The claim is a multiset statement, so a duplicate in the source cannot satisfy it quietly.
    dup_rows = rows + [rows[0]]
    with pytest.raises(PartitionError, match="appears twice"):
        route_lines(dup_rows)


def test_a_record_the_repos_own_contract_refuses_is_refused_before_anything_is_written():
    """The routed line must still be a `Record`: the contract is the producer's, not this file's."""
    broken = json.dumps({**json.loads(_row("en", 0)), "probs": [0.7, 0.1, 0.1, 0.5]},
                        sort_keys=True)
    with pytest.raises(PartitionError, match="not a record"):
        route_lines([_row("en", 1), broken])


# ------------------------------------------------------------------ the plants, one per claim
def test_plant_one_a_duplicate_id_is_refused_and_nothing_is_written(tmp_path):
    """Breaks "no id appears twice"."""
    rows = [_row("en", 0), _row("en", 1), _row("de", 0)]
    src = _source(tmp_path, rows + [rows[0]])
    out = tmp_path / "data"
    p = _run("--in", str(src), "--out-dir", str(out))
    assert p.returncode == 3, (p.returncode, p.stdout, p.stderr)
    assert "appears twice" in p.stderr, p.stderr
    assert not out.exists() or list(out.iterdir()) == [], "a refusal wrote artefacts anyway"


def test_plant_two_a_line_moved_between_files_breaks_the_routing_not_the_multiset(tmp_path):
    """Breaks "each file holds exactly the lines its name claims" -- invisible to set arithmetic."""
    rows = [_row("en", 0), _row("en", 1), _row("de", 0)]
    src = _source(tmp_path, rows)
    out = tmp_path / "data"
    assert main(["--in", str(src), "--out-dir", str(out)]) == 0
    en, de = out / "records_massive_en.jsonl", out / "records_massive_de.jsonl"
    en.write_text(rows[1] + "\n")
    de.write_text(rows[0] + "\n" + rows[2] + "\n")     # en/0 parked in de's file
    with pytest.raises(WrittenDrift) as excinfo:
        check_written(src, out)
    message = str(excinfo.value)
    assert "records_massive_de.jsonl" in message, message
    assert "massive/en/0/laya" in message, message
    # ...and the multiset claim the swap leaves intact is reported as intact, which is why the
    # routing check had to exist: a checker that only compared id multisets passes this defect.
    ids_files = [json.loads(l)["id"] for f in (en, de) for l in f.read_text().splitlines()]
    assert sorted(ids_files) == sorted(json.loads(r)["id"] for r in rows)


def test_plant_three_a_deleted_line_breaks_the_multiset_against_the_source(tmp_path):
    """Breaks "the ids across the files equal the ids in the source"."""
    rows = [_row("en", 0), _row("en", 1), _row("de", 0)]
    src = _source(tmp_path, rows)
    out = tmp_path / "data"
    assert main(["--in", str(src), "--out-dir", str(out)]) == 0
    en = out / "records_massive_en.jsonl"
    en.write_text(rows[0] + "\n")                      # massive/en/1 is gone
    with pytest.raises(WrittenDrift) as excinfo:
        check_written(src, out)
    assert "massive/en/1/laya" in str(excinfo.value), str(excinfo.value)
    assert "2" in str(excinfo.value) and "3" in str(excinfo.value), "no counts in the refusal"


def test_a_row_whose_id_and_case_id_name_different_languages_is_refused(tmp_path):
    """One row, two subjects: the file a reader opens would depend on which field they trust."""
    row = json.dumps({**json.loads(_row("en", 0)), "id": "massive/de/0/laya"}, sort_keys=True)
    src = _source(tmp_path, [row, _row("de", 0)])
    p = _run("--in", str(src), "--out-dir", str(tmp_path / "data"))
    assert p.returncode == 3, (p.returncode, p.stderr)
    assert "case_id" in p.stderr and "id" in p.stderr, p.stderr


@pytest.mark.parametrize("tamper", [
    "key order",          # a hand-edit that reorders keys is not the producer's canonical form
    "blank line",         # `load_records` skips blank lines; a committed artefact must not have one
    "not an object",
])
def test_a_line_that_is_not_the_producers_canonical_record_is_refused(tmp_path, tamper):
    rows = [_row("en", 0), _row("de", 0)]
    if tamper == "key order":
        # `_row` already dumps with `sort_keys=True`, so re-dumping the same dict with
        # `sort_keys=False` yields byte-identical bytes: that plant would prove nothing about the
        # tool and would report green while testing nothing. Make the order actually differ by
        # moving a key to the front, so the refusal below is a claim about these bytes.
        moved = json.loads(rows[0])
        moved = {"u": moved.pop("u"), **moved}
        row = json.dumps(moved, sort_keys=False)
        assert row != rows[0], "the plant did not change the bytes"
    elif tamper == "blank line":
        row = "\n"
    else:
        row = "[1, 2]"
    src = _source(tmp_path, [row] + rows[1:])
    p = _run("--in", str(src), "--out-dir", str(tmp_path / "data"))
    assert p.returncode == 3, (tamper, p.returncode, p.stdout, p.stderr)
    assert "canonical" in p.stderr or "not a record" in p.stderr, p.stderr


def test_a_leftover_file_for_a_language_the_source_does_not_not_have_is_refused(tmp_path):
    """A stale `records_massive_fr.jsonl` beside a fresh split would be published as part of it."""
    rows = [_row("en", 0), _row("de", 0)]
    src = _source(tmp_path, rows)
    out = tmp_path / "data"
    out.mkdir()
    (out / "records_massive_fr.jsonl").write_text(_row("fr", 0) + "\n")
    p = _run("--in", str(src), "--out-dir", str(out))
    assert p.returncode == 3, (p.returncode, p.stderr)
    assert "records_massive_fr.jsonl" in p.stderr, p.stderr
    assert not (out / "records_massive_en.jsonl").exists(), "it wrote the new files anyway"


def test_a_missing_input_is_usage_and_not_a_traceback(tmp_path):
    p = _run("--in", str(tmp_path / "absent.jsonl"), "--out-dir", str(tmp_path / "data"))
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "USAGE" in p.stderr, p.stderr


# ------------------------------------------------------------------ determinism and the artefacts
def test_two_runs_over_the_same_bytes_write_the_same_bytes(tmp_path):
    rows = [_row("en", i) for i in range(4)] + [_row("de", 0), _row("sw", 3)]
    src = _source(tmp_path, rows)
    digests = []
    for name in ("out1", "out2"):
        out = tmp_path / name
        assert main(["--in", str(src), "--out-dir", str(out)]) == 0
        digests.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(out.iterdir())})
    assert digests[0] == digests[1], digests
    assert sorted(digests[0]) == ["records_massive_de.jsonl", "records_massive_en.jsonl",
                                 "records_massive_sw.jsonl"]


def test_the_written_summary_states_the_count_of_every_file_it_wrote(tmp_path, capsys):
    rows = [_row("en", i) for i in range(3)] + [_row("de", i) for i in range(2)]
    src = _source(tmp_path, rows)
    out = tmp_path / "data"
    rc = main(["--in", str(src), "--out-dir", str(out)])
    printed = capsys.readouterr().out
    assert rc == 0, printed
    assert "en 3" in printed and "de 2" in printed, printed
    assert "8,922".replace(",", "") not in printed, "the fixture is not 8,922 rows"
    assert "source rows 5" in printed, printed


# --------------------------------------------------------------------- the committed artefacts
def test_the_committed_split_is_the_partition_the_tool_proved(tmp_path):
    """The committed per-language files must pass the same checker the tool runs after writing.

    No build-product input and no skip: the source they were split from is a build product and stays
    outside the repository, so what can be re-proved here is the half of the claim that lives on
    disk -- the files are mutually disjoint in ids, one record per case, every line canonical,
    every line a `Record`, and every language covering the SAME case index set (they are
    translations of one utterance set, which is what makes the certificates comparable
    case by case and what forbids pooling them).

    The name list below is a membership witness, not a count: it is what a corpus that joined the
    publication has to be edited into, so that adding or dropping a language is a decision somebody
    took in the open rather than a set that quietly re-formed. Task #68 made it four, because
    `data/records_massive_km.jsonl` is now published evidence and the partition claim covers it like it
    covers the other three -- and the four-way case-index identity below is the measured answer to
    "is Khmer the same 2,974 utterances", which is the precondition for putting it in the same run.
    """
    files = sorted((REPO / "data").glob(DEFAULT_NAME_FORMAT.format(lang="*")))
    assert [f.name for f in files] == ["records_massive_de.jsonl", "records_massive_en.jsonl",
                                       "records_massive_km.jsonl",
                                       "records_massive_sw.jsonl"], files
    by_lang = {}
    for path in files:
        lang = re.match(r"records_massive_(\w+)\.jsonl$", path.name).group(1)
        lines = path.read_text().splitlines()
        assert lines and all(line.strip() for line in lines), "%s carries a blank line" % path
        rows = [json.loads(line) for line in lines]
        assert all(json.dumps(row, sort_keys=True) == line
                   for row, line in zip(rows, lines)), "%s holds a re-serialized row" % path
        for row in rows:
            Record.from_dict(row)                      # the contract, not a paraphrase of it
            assert case_language(row["case_id"]) == lang, row["id"]
            assert row["id"] == "%s/laya" % row["case_id"], row["id"]
        assert len({r["id"] for r in rows}) == len(rows), "duplicate id inside one file"
        assert len({r["case_id"] for r in rows}) == len(rows), "two records for one case"
        by_lang[lang] = {r["case_id"].rsplit("/", 1)[1] for r in rows}
    assert len({frozenset(ids) for ids in by_lang.values()}) == 1, \
        "the languages cover different cases: %s" % sorted(by_lang)
    assert sorted(by_lang) == ["de", "en", "km", "sw"], sorted(by_lang)
    all_ids = [json.loads(line)["id"] for path in files for line in path.read_text().splitlines()]
    assert len(all_ids) == len(set(all_ids)), "one id appears in two language files"


def test_the_tool_exposes_its_claims_as_a_module_and_not_only_as_a_stdout_table():
    """`verify`'s prose must be able to name this tool as the owner of its inputs."""
    from tools.split_records import OWNER_SENTENCE, split_owner

    assert OWNER_SENTENCE == split_owner()
    assert "tools/split_records.py" in OWNER_SENTENCE and "--in" not in OWNER_SENTENCE, \
        OWNER_SENTENCE


# ------------------------------------------------- the certificates the committed rows produce
def _drift_labels(report_module, fields, table=None):
    """Run the re-derivation arm and collect only the labels it says disagree.

    `verify` owns the counting and the exit code; this helper is the same call with a sink that keeps
    the failures, because the thing being asserted here is *which* label fires, not how many checks ran.

    The arm is handed the freeze's digest as its stamp because Plan D Task 2 re-exported the published
    artefacts with `certify --protocol`: a caller that re-derived without stamping would report every
    certificate as drifted on `meta` and the row would be measuring its own harness. The digest is
    recomputed from `protocol.json` rather than read off the artefact under test, so it can disagree.
    """
    from dataclasses import replace

    from autorate.protocol import load_protocol, protocol_digest

    digest = protocol_digest(load_protocol(REPO / "protocol.json"))
    if table is not None:
        report_module.MASSIVE_CERTIFICATES = table
    seen = []
    report_module.rederive_massive(lambda label, actual, published:
                                   None if actual == published else seen.append(label), fields,
                                   stamp=lambda cert: replace(cert, meta={**cert.meta,
                                                                          "protocol_digest": digest}))
    return seen


def test_the_committed_certificates_rederive_from_the_committed_records(monkeypatch):
    """G1's four artefacts must be a function of the bytes committed beside them, field by field.

    Counting and reporting those comparisons is `cmd_verify`'s job, and `cli.py` is not this lane's file
    (see the report's `OUT-OF-FENCE` note), so the arm is run here directly instead of left unguarded:
    this row is the proof that `data/cert_massive_*.json` are what the tool writes and not hand-authored
    numbers. The field list is read from `cli.py` rather than retyped, so a field the gate stops
    comparing has to leave this row's coverage in the open rather than in a comment.
    """
    from autorate import report as report_module
    from autorate.cli import CERT_COMPARE_FIELDS
    from autorate.report import MASSIVE_CERTIFICATES, massive_certificates

    monkeypatch.chdir(REPO)
    assert _drift_labels(report_module, CERT_COMPARE_FIELDS) == [], "published drift"
    published = massive_certificates()
    assert sorted(published) == ["massive/de", "massive/en", "massive/km", "massive/sw"], \
        sorted(published)
    assert sorted(MASSIVE_CERTIFICATES) == sorted(published), "the table and the artefacts disagree"
    for label, (records, cert) in published.items():
        # A selection that found no rows would re-derive a `no_gold_labels` refusal and so would NOT
        # match quietly above -- but the population is pinned anyway, because "the arm compared nothing"
        # and "the arm compared the right 2,974 rows" look identical in a green run.
        assert len(records) == 2974, (label, len(records))
        assert cert.n_cal == cert.n_eval == 1487, (label, cert.n_cal, cert.n_eval)
        assert cert.backend == "laya" and cert.meta["n_eval_cases"] == 1487, label
        # The verdict is G1's result, so it is asserted as stored, not paraphrased: three refusals.
        assert cert.feasible is False, (label, cert.feasible)
        assert cert.reason == "empty_feasible_set", (label, cert.reason)
        # ...and the budgets it refuses at are the pre-registered ones. A re-certification at a looser
        # beta would still satisfy every line above EXCEPT these, which is why they are here (R-143).
        assert (cert.alpha, cert.beta, cert.delta) == (0.05, 0.05, 0.05), label
        assert cert.method == "aps" and cert.meta["seed"] == 7, label


def test_the_rederivation_arm_bites_on_a_tampered_published_digit(tmp_path, monkeypatch):
    """Two plants, because a re-derivation that cannot fail is a second copy of the artefact.

    The copies live in `tmp_path` and the table is patched to point at them: the committed bytes are
    hashed before and after the row, so "we proved the guard bites" cannot have been paid for by editing
    the evidence. This is also the in-tree demonstration that the one line `cmd_verify` still owes would
    do its job -- the labels below are exactly what that arm would hand to `expect`, and `verify` would
    print them to stderr and exit 4.
    """
    import shutil

    from autorate import report as report_module
    from autorate.cli import CERT_COMPARE_FIELDS

    committed = {p: hashlib.sha256((REPO / "data" / p).read_bytes()).hexdigest()
                 for p in [f + ".jsonl" for f in ("records_massive_de", "records_massive_en",
                                                  "records_massive_sw")]
                 + ["cert_massive_de_laya.json", "cert_massive_en_laya.json",
                    "cert_massive_sw_laya.json"]}
    lane = tmp_path / "data"
    lane.mkdir()
    table = {}
    for lang in ("de", "en", "sw"):
        records = lane / ("records_massive_%s.jsonl" % lang)
        cert = lane / ("cert_massive_%s_laya.json" % lang)
        shutil.copy(REPO / "data" / records.name, records)
        shutil.copy(REPO / "data" / cert.name, cert)
        table["massive/" + lang] = (str(records), str(cert))
    monkeypatch.setattr(report_module, "MASSIVE_CERTIFICATES", table)
    monkeypatch.chdir(tmp_path)

    # 1. the control: the same function over byte-identical copies reports nothing, so any red below is
    #    the plant and not the plumbing.
    assert _drift_labels(report_module, CERT_COMPARE_FIELDS, table) == []

    # 2. plant the published Clopper-Pearson bound, one place below the last digit `verify` prints.
    en = json.loads((lane / "cert_massive_en_laya.json").read_text())
    bound = en["meta"]["closest_attempt"]["conditional_error_bound"]
    en["meta"]["closest_attempt"]["conditional_error_bound"] = bound * 1.0001
    (lane / "cert_massive_en_laya.json").write_text(json.dumps(en))
    drifts = _drift_labels(report_module, CERT_COMPARE_FIELDS, table)
    assert drifts == ["cert massive/en.meta"], drifts

    # 3. plant the reason a refusal is published under. Two labels fire, and the second one is the point:
    #    `summary()` carries the reason as text, so a gate that compared only fields would still catch it
    #    -- and a gate that compared only the summary would name nothing.
    de = json.loads((lane / "cert_massive_de_laya.json").read_text())
    de["reason"] = "no_gold_labels"
    (lane / "cert_massive_de_laya.json").write_text(json.dumps(de))
    drifts = _drift_labels(report_module, CERT_COMPARE_FIELDS, table)
    assert "cert massive/de.reason" in drifts and "cert massive/de.summary" in drifts, drifts
    assert "cert massive/en.meta" in drifts, "the first plant stopped being visible: a shared sink?"

    # 4. nothing in the repository moved.
    for path, digest in committed.items():
        assert hashlib.sha256((REPO / "data" / path).read_bytes()).hexdigest() == digest, path
