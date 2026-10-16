"""Task 5's drift-envelope artefact: `data/drift_envelope.json` and `docs/DRIFT.md` must be re-derivable.

Plan B3 declared the drift envelope in `src/autorate/drift.py`'s constants and `tests/test_drift.py` re-runs
their measurements, so the two withdrawals were re-runnable but the gate never checked them and `data/`
published nothing. This file is the artefact's own guard: every envelope line in the published bytes is
compared to the tuple in the module, every published figure is recomputed here from the shipped functions,
and every refusal is planted through the producer's real entry point.

What each row can catch, stated in the row that owns it:

* an envelope edit in `drift.py` that the artefact and the document do not carry (rows 2 and 3 -- they read
  the module's tuple, not a remembered list, so a docstring edit reddens a row rather than going unread);
* a published figure that no longer comes from the arithmetic it names (rows 5, 6, 7, 8: mode 2 is
  re-derived at full scale from the recipes IN the artefact, mode 1 at the reduced trial count THIS FILE
  NAMES, with the artefact's own provenance pinned to 4000 so the two scales cannot be confused);
* a document that states a number the artefact does not hold, or holds a machine path or a timestamp
  (rows 4 and 9);
* a broken publication -- absent, wrong-shaped, truncated, or re-provenanced -- reaching an operator as a
  traceback instead of a named refusal at 0/2/3/4 (rows 10 to 15; no plant in this file may land on rc 1,
  and row 15 asserts that over every plant).

Written BEFORE `tools/drift_envelope.py`, so every row here was red on arrival; the RED output is in the
task report.
"""
import hashlib
import json
import math
import random
import re
from pathlib import Path

import pytest

from autorate.drift import (ACI_ENVELOPE, NOT_CERTIFIABLE_UNDER_DRIFT, SCORE_CEILING,
                            WEIGHTED_ENVELOPE, aci_regret_bound, aci_threshold, weighted_quantile)

REPO = Path(__file__).resolve().parents[1]
ARTEFACT_REL = Path("data/drift_envelope.json")
DOC_REL = Path("docs/DRIFT.md")

# The trial count THIS FILE re-derives mode 1 at. It is deliberately not the count the artefact publishes:
# the row below asserts both numbers, so "recomputed here at reduced scale" can never be read as "published
# at full scale". 400 is one tenth of the published 4000 and still gives a band ~3.2x wider than 3SE.
REDUCED_TRIALS = 400
PUBLISHED_TRIALS = 4000
# The number of decimals `WEIGHTED_ENVELOPE` writes its cited figures at; the row below reads the module's
# digits as text and the artefact's as numbers, so the comparison has to be made at that precision.
PUBLISHED_CITED_DECIMALS = 4


# ------------------------------------------------------------------ the artefact's own shape

def read_json(path: Path) -> dict:
    assert path.is_file(), "%s is missing -- run `python3 tools/drift_envelope.py --force`" % path
    loaded = json.loads(path.read_text())
    assert isinstance(loaded, dict), "%s is a JSON %s, not an artefact object" % (
        path, type(loaded).__name__)
    return loaded


def artefact() -> dict:
    return read_json(REPO / ARTEFACT_REL)


def _doc_text() -> str:
    assert (REPO / DOC_REL).is_file(), "%s is missing" % (REPO / DOC_REL)
    return (REPO / DOC_REL).read_text()


def _grid(count, modulus=100):
    """The same deterministic pseudo-uniform sequence `tests/test_drift.py` uses -- no RNG, re-runnable."""
    return [((i * 37) % modulus) / float(modulus) for i in range(count)]


def materialise(construction: dict) -> list:
    """Rebuild one published sequence from the recipe the artefact stores.

    The artefact stores recipes rather than 180,000 literals; a recipe whose materialised stream is not the
    stream that was measured is caught by the digest the same row compares.
    """
    kind = construction["kind"]
    rounds = int(construction["rounds"])
    if kind == "constant":
        return [float(construction["value"])] * rounds
    if kind == "alternating":
        values = [float(v) for v in construction["values"]]
        assert values, "an alternating recipe with no atoms"
        return [values[i % len(values)] for i in range(rounds)]
    if kind == "grid":
        return _grid(rounds, int(construction.get("modulus", 100)))
    raise AssertionError("unknown published sequence recipe %r" % (kind,))


def _digest(values) -> str:
    return hashlib.sha256(repr(values).encode()).hexdigest()


def _long_run_rate(scores, alpha, gamma) -> tuple:
    """(average error over the whole sequence, whether any round sat on a clip) -- streamed."""
    total = 0
    count = 0
    clipped = False
    for step in aci_threshold(scores, alpha, gamma):
        total += step.err
        count += 1
        if step.lam in (0.0, 1.0):
            clipped = True
    return total / float(count), clipped


def _mode1_at(reduced_trials: int, sizes) -> dict:
    """The declared-ratio Monte-Carlo of `tests/test_drift.py:539-570`, at a stated number of trials.

    Same stream, same seed derivation (`random.Random(seed + n)`), same estimator, same closed-form coverage:
    only `trials` differs, and the caller names it.
    """
    provenance = artefact()["provenance"]
    seed = int(provenance["seed"])
    alpha = float(provenance["alpha"])
    out = {}
    for n in sizes:
        rng = random.Random(seed + n)
        misses = []
        for _ in range(reduced_trials):
            cal = [rng.random() for _ in range(n)]
            q, _flag = weighted_quantile(cal, [10.0 * s ** 9 for s in cal], alpha)
            misses.append(1.0 - q ** 10)
        mean = math.fsum(misses) / reduced_trials
        se = math.sqrt(math.fsum((m - mean) ** 2 for m in misses) / (reduced_trials - 1) / reduced_trials)
        out[n] = (mean, se)
    return out


# --------------------------------------------------------------------------------- the rows


def test_the_artefact_and_its_document_exist_and_name_the_producer_that_wrote_them():
    """The publication exists, is shaped like a publication, and attributes itself.

    Green only once `tools/drift_envelope.py` has run; red on arrival because `data/` held nothing. A
    producer key that names some other file, or a document that names no command, is the defect this row
    watches: `docs/DRIFT.md` is only evidence if a reader can re-run what wrote it.
    """
    doc = artefact()
    assert doc["producer"] == "tools/drift_envelope.py", doc["producer"]
    for key in ("provenance", "mode1", "mode2", "mode2_controls", "mode2_sweep",
                "weighted_envelope", "aci_envelope", "withdrawals", "reproduction"):
        assert key in doc, sorted(doc)
    text = _doc_text()
    assert "tools/drift_envelope.py" in text, text[:400]
    assert str(ARTEFACT_REL) in text and str(DOC_REL) in text, text[:400]


def test_every_envelope_line_in_the_artefact_is_the_tuple_in_drift_py_verbatim():
    """A docstring edit that changes an envelope line reddens this row.

    Compared against the imported tuples, line for line, in order -- not against a remembered list of words.
    This is the whole point of the artefact: the withdrawal lives in prose, so the prose must be a COPY of
    the module's bytes and any divergence must be loud.
    """
    doc = artefact()
    assert doc["weighted_envelope"] == list(WEIGHTED_ENVELOPE), (
        "data/drift_envelope.json's weighted envelope is not drift.WEIGHTED_ENVELOPE")
    assert doc["aci_envelope"] == list(ACI_ENVELOPE), (
        "data/drift_envelope.json's ACI envelope is not drift.ACI_ENVELOPE")
    assert doc["not_certifiable_under_drift"] == NOT_CERTIFIABLE_UNDER_DRIFT
    assert len(doc["weighted_envelope"]) == len(WEIGHTED_ENVELOPE)
    assert len(doc["aci_envelope"]) == len(ACI_ENVELOPE)


def test_the_document_carries_every_envelope_line_byte_for_byte():
    """The rendered prose cannot soften the withdrawal it is supposed to publish.

    Each tuple line is compared as the folded text, so a re-wrap in the renderer is allowed and a dropped or
    reworded clause is not. Turned red by one plant: fold a forged extra line into the artefact's envelope
    copy and the document no longer contains it.
    """
    text = " ".join(_doc_text().split())
    for line in WEIGHTED_ENVELOPE + ACI_ENVELOPE:
        assert " ".join(line.split()) in text, line[:80]
    forged = " ".join("the regret statement holds for every accepted sequence".split())
    assert forged not in text


def test_the_document_states_both_withdrawals_in_plain_words_and_owns_every_figure_it_prints():
    """The two sentences this artefact exists to publish, in words a reader does not have to decode.

    Mode 1: the finite-sample statement is WITHDRAWN. Mode 2: the REGRET statement is withdrawn. Asserted on
    the document's own text, and asserted again negatively -- the document must not grant either one back.
    """
    text = _doc_text()
    folded = " ".join(text.split()).lower()
    assert "finite-sample" in folded and "withdraw" in folded, folded[:400]
    assert "regret" in folded and "withdraw" in folded, folded[:400]
    for granted in ("the finite-sample bound holds", "the regret bound holds for every",
                    "guaranteed within the regret bound"):
        assert granted not in folded, granted


def test_the_mode2_realised_rates_and_the_bound_comparison_re_derive_from_the_artefacts_recipes():
    """Every published mode-2 number recomputed here from the shipped recursion, at full scale.

    This part is fast, so the row re-derives rather than trusting: each stored recipe is materialised, run
    through `aci_threshold`, and its rate, deviation and `aci_regret_bound` comparison are checked against the
    stored figures -- with the violation direction (each deviation EXCEEDS the bound) as a separate assertion,
    because that inequality is the withdrawn sentence's falsification. The stored digest is recomputed too, so
    a recipe edited away from the sequence that was measured cannot pass.
    """
    doc = artefact()
    alpha = float(doc["provenance"]["alpha"])
    gamma = float(doc["provenance"]["gamma"])
    rows = doc["mode2"]
    assert len(rows) == 4, [r["name"] for r in rows]
    for row in rows:
        scores = materialise(row["construction"])
        assert len(scores) == row["rounds"] == row["construction"]["rounds"], row["name"]
        assert _digest(scores) == row["sequence_digest_sha256"], (
            "%s: the stored recipe no longer materialises the sequence that was measured" % row["name"])
        realised, clipped = _long_run_rate(scores, alpha, gamma)
        assert realised == pytest.approx(row["realised_long_run_rate"], abs=1e-9), row["name"]
        bound = aci_regret_bound(len(scores), alpha, gamma)
        assert bound == pytest.approx(row["regret_bound"], abs=1e-9), row["name"]
        assert abs(realised - alpha) == pytest.approx(row["deviation_from_alpha"], abs=1e-9)
        assert abs(realised - alpha) > bound, (row["name"], realised, bound)
        assert row["violates_bound"] is True, row
        assert row["clip_observable"] is clipped, row["name"]
    # the two controls in `tests/test_drift.py`'s row: there the inequality DOES hold, so the four above are
    # a falsification and not a blanket "nothing holds".
    assert len(doc["mode2_controls"]) == 2, [r["name"] for r in doc["mode2_controls"]]
    for row in doc["mode2_controls"]:
        scores = materialise(row["construction"])
        realised, clipped = _long_run_rate(scores, alpha, gamma)
        assert realised == pytest.approx(row["realised_long_run_rate"], abs=1e-9), row["name"]
        assert abs(realised - alpha) <= aci_regret_bound(len(scores), alpha, gamma), row["name"]
        assert row["violates_bound"] is False and row["clip_observable"] is clipped, row


def test_the_mode2_sweep_counts_and_the_clip_mechanism_re_derive_from_the_artefact():
    """The mechanism claim (0 violations without a clip, some clipped sequences still hold) re-run.

    `ACI_ENVELOPE` states the 400-sequence sweep's counts, and the withdrawal explains itself with the clip.
    Re-derived here at the scale the artefact names, from the seed the artefact names: an unclipped violation
    appearing, or every clipped sequence violating, both redden this row and the envelope sentence beside it.
    """
    doc = artefact()
    sweep = doc["mode2_sweep"]
    seed, sequences, rounds = int(sweep["seed"]), int(sweep["sequences"]), int(sweep["rounds"])
    alpha = float(doc["provenance"]["alpha"])
    gamma = float(doc["provenance"]["gamma"])
    assert sequences == 400 and rounds == 2000 and seed == int(doc["provenance"]["seed"]), sweep
    rng = random.Random(seed)
    bound = aci_regret_bound(rounds, alpha, gamma)
    assert bound == pytest.approx(sweep["bound"], abs=1e-9), (bound, sweep["bound"])
    violations = violated_unclipped = held_clipped = clipped_total = 0
    for k in range(sequences):
        kind = k % 8
        if kind == 0:
            scores = [rng.random() for _ in range(rounds)]
        elif kind == 1:
            scores = [min(1.0, max(0.0, rng.gauss(0.9, 0.05))) for _ in range(rounds)]
        elif kind == 2:
            scores = [min(1.0, max(0.0, rng.gauss(0.5, 0.2))) for _ in range(rounds)]
        elif kind == 3:
            scores = [rng.choice((0.0, 1.0)) for _ in range(rounds)]
        elif kind == 4:
            scores = [rng.choice((0.99, 0.01)) for _ in range(rounds)]
        elif kind == 5:
            scores = [1.0] * rounds
        elif kind == 6:
            scores = [0.0] * rounds
        else:
            scores = _grid(rounds)
        realised, clipped = _long_run_rate(scores, alpha, gamma)
        violated = abs(realised - alpha) > bound
        violations += 1 if violated else 0
        violated_unclipped += 1 if (violated and not clipped) else 0
        held_clipped += 1 if (clipped and not violated) else 0
        clipped_total += 1 if clipped else 0
    assert violated_unclipped == 0 == sweep["violated_without_clip"], (violated_unclipped, sweep)
    assert violations == sweep["violations"] > 0, (violations, sweep)
    assert held_clipped == sweep["held_clipped"] > 0, (held_clipped, sweep)
    assert clipped_total == sweep["clipped"], (clipped_total, sweep)


def test_mode1_is_recomputed_here_at_the_reduced_scale_named_in_this_file_and_published_at_4000():
    """The two scales, side by side and never blurred.

    This row re-runs the declared-ratio Monte-Carlo at `REDUCED_TRIALS` (400) and compares it to the
    artefact's published figure inside a band that is honest about the scale difference -- 6 reduced-scale
    standard errors plus 0.01, the same shape `tests/test_drift.py:539-570` asserts at. It then pins the
    artefact's own provenance to `PUBLISHED_TRIALS` (4000) and to the sizes the envelope names, so the
    reduced recomputation cannot be read as a re-derivation of the published number: the tolerance is ~3.2x
    wider than the published figure's own 3SE, and the row says so in numbers rather than in a comment.
    """
    doc = artefact()
    provenance = doc["provenance"]
    assert int(provenance["trials_per_size"]) == PUBLISHED_TRIALS, provenance["trials_per_size"]
    sizes = [int(row["n"]) for row in doc["mode1"]]
    assert sizes == [25, 100], sizes
    assert list(provenance["sizes"]) == sizes, provenance["sizes"]
    reduced = _mode1_at(REDUCED_TRIALS, sizes)
    for row in doc["mode1"]:
        assert int(row["trials"]) == PUBLISHED_TRIALS, row
        mean, se = reduced[int(row["n"])]
        tolerance = 6.0 * se + 0.01
        assert abs(mean - row["realised_miscoverage"]) < tolerance, (
            "n=%d: recomputed at %d trials gives %.6f, the artefact publishes %.6f at %d trials "
            "(band %.6f)" % (row["n"], REDUCED_TRIALS, mean, row["realised_miscoverage"],
                             row["trials"], tolerance))
        # the published figure's own band is tighter than this row's, which is what keeps the two scales
        # visibly different instead of mutually covering.
        assert row["three_se"] < tolerance, (row["three_se"], tolerance)
        assert row["realised_miscoverage"] > 1.5 * float(provenance["alpha"]), row


def test_mode1_cited_figures_are_read_from_the_module_bytes_and_reproduce_inside_three_se():
    """The artefact's `envelope_cited` numbers are parsed from `WEIGHTED_ENVELOPE`, not retyped.

    Checked three ways: every cited figure in the artefact appears as the same digits in the module's tuple;
    the measurement reproduces inside the 3SE the envelope itself states; and the vacuous share the envelope
    names for n=25 is published beside its measured value. A `drift.py` edit that moves 0.0933 without moving
    the measurement reddens the second assertion; an artefact that quotes a figure the tuple does not carry
    reddens the first.
    """
    doc = artefact()
    joined = " ".join(WEIGHTED_ENVELOPE)
    module_digits = set(re.findall(r"\d\.\d{4}", joined))
    for row in doc["mode1"]:
        # the module states its figures as digits inside prose, the artefact stores them as numbers: compared
        # at the precision the envelope writes them at, which is the whole content of "read from the bytes".
        cited_text = format(row["envelope_cited"], "." + str(PUBLISHED_CITED_DECIMALS) + "f")
        assert cited_text in module_digits, (row["n"], cited_text, module_digits)
        assert row["three_se"] == pytest.approx(row["standard_error"] * 3.0, abs=5e-7), row
        assert abs(row["realised_miscoverage"] - row["envelope_cited"]) <= row["three_se"], (
            "n=%d: measured %.6f against the envelope's %.4f and its own 3SE %.4f -- the withdrawal's "
            "figure no longer reproduces" % (row["n"], row["realised_miscoverage"],
                                             row["envelope_cited"], row["three_se"]))
    stated_3se = re.search(r"3SE (\d\.\d{4})", joined)
    assert stated_3se, joined
    n100 = [r for r in doc["mode1"] if r["n"] == 100][0]
    assert abs(n100["three_se"] - float(stated_3se.group(1))) < 5e-4, (n100, stated_3se.group())
    vac_cited = re.search(r"(\d\.\d{4}) of those n=25", joined)
    assert vac_cited, joined
    n25 = [r for r in doc["mode1"] if r["n"] == 25][0]
    assert n25["vacuous_share_cited_in_envelope"] == float(vac_cited.group(1)), n25
    assert n25["vacuous_share"] == pytest.approx(
        n25["vacuous_trials"] / float(PUBLISHED_TRIALS), abs=1e-12), n25


def test_the_artefact_quotes_the_provenance_and_constants_it_actually_read():
    """Nothing in the provenance block was typed by hand from memory.

    The module constants are compared to the imported values, the seed/trials/sizes/alpha/gamma to the numbers
    `tests/test_drift.py` runs, and the two named functions to the callables that produced the figures. A
    constant changed in `drift.py` without the artefact being re-run is drift this row names.
    """
    from autorate.drift import TEST_POINT_WEIGHT, aci_threshold as shipped_aci, weighted_quantile as shipped_wq

    doc = artefact()
    constants = doc["provenance"]["module_constants"]
    assert constants["SCORE_CEILING"] == SCORE_CEILING, constants
    assert constants["TEST_POINT_WEIGHT"] == TEST_POINT_WEIGHT, constants
    for key in ("aci_threshold", "aci_regret_bound", "weighted_quantile"):
        assert key in doc["provenance"]["produced_by"], doc["provenance"]
    assert doc["provenance"]["produced_by"]["weighted_quantile"] == shipped_wq.__name__
    assert doc["provenance"]["produced_by"]["aci_threshold"] == shipped_aci.__name__
    assert int(doc["provenance"]["seed"]) == 20261008, doc["provenance"]
    assert doc["provenance"]["target_density"] == "10*s^9", doc["provenance"]
    assert doc["provenance"]["test_points_stated_by_envelope"] == 2000, doc["provenance"]


def test_no_tracked_byte_of_the_publication_names_a_machine_path_or_a_timestamp():
    """Both files are tracked-tree material, so they are scanned the way `tests/test_cli.py` scans.

    Patterns are built from pieces so this file is not the offender it looks for. The guards' bite is proved
    on a forged line rather than assumed: the same pattern must hit a planted path and a planted date.
    """
    artefact_text = (REPO / ARTEFACT_REL).read_text()
    doc_text = _doc_text()
    path_rx = re.compile("/" + "(Users|home|var/folders)/[A-Za-z0-9._-]+/")
    date_rx = re.compile("20" + r"\d\d-\d\d-\d\d")
    assert not path_rx.search(artefact_text), path_rx.search(artefact_text).group(0)
    assert not path_rx.search(doc_text), path_rx.search(doc_text).group(0)
    assert not date_rx.search(artefact_text + doc_text), date_rx.search(doc_text)
    assert path_rx.search("seen in /" + "Users/someone/x/data.json\n")
    assert date_rx.search("written 20" + "26-01-01\n")


# ----------------------------------------------------------------- refusals through the entry point
#
# Every row below plants a broken publication and drives `tools/drift_envelope.main` -- the real entry point,
# not a helper -- asserting the name it prints and the code it returns. Codes are 0/2/3/4 and nothing here
# may reach 1; `test_no_plant_of_a_broken_publication_reaches_rc_1` walks the whole matrix again for that.

# Every broken-publication shape this file can forge, and the name the producer has to print for it. The
# tuple is the subject of the rc-1 sweep and the dict is the expectation of the rc-4 row, so a plant added
# here is driven through both and cannot become an untested fixture.
PLANTS = ("missing", "list", "scalar", "empty", "no-envelope-key", "truncated-weighted",
          "truncated-aci", "seed-moved", "trials-moved", "sizes-moved", "doc-drift",
          "figure-moved", "recipe-moved")

PLANT_REASON = {
    "missing": "ARTEFACT UNAVAILABLE",
    "list": "ARTEFACT SHAPE",
    "scalar": "ARTEFACT SHAPE",
    "empty": "ARTEFACT SHAPE",
    "no-envelope-key": "ARTEFACT SHAPE",
    "truncated-weighted": "ENVELOPE TRUNCATED",
    "truncated-aci": "ENVELOPE TRUNCATED",
    "seed-moved": "PROVENANCE",
    "trials-moved": "PROVENANCE",
    "sizes-moved": "PROVENANCE",
    "doc-drift": "DOCUMENT",
    "figure-moved": "DRIFT",
    "recipe-moved": "DRIFT",
}
assert set(PLANTS) == set(PLANT_REASON), "the plant sweep and the plant expectation have diverged"


def _forge_artefact(kind: str, tmp: Path) -> Path:
    """Write a broken artefact of the named shape at a temp path and return that path."""
    import copy

    if kind == "missing":
        return tmp / "not_written.json"
    if kind in ("list", "scalar", "empty"):
        path = tmp / ("%s.json" % kind)
        payload = [artefact()] if kind == "list" else (3 if kind == "scalar" else {})
        path.write_text(json.dumps(payload) + "\n")
        return path
    doc = copy.deepcopy(artefact())
    if kind == "no-envelope-key":
        del doc["weighted_envelope"]
    elif kind == "truncated-weighted":
        doc["weighted_envelope"] = doc["weighted_envelope"][:-1]
    elif kind == "truncated-aci":
        doc["aci_envelope"] = doc["aci_envelope"][:1]
    elif kind == "seed-moved":
        doc["provenance"]["seed"] = 20261009
    elif kind == "trials-moved":
        doc["provenance"]["trials_per_size"] = 2000
    elif kind == "sizes-moved":
        doc["provenance"]["sizes"] = [50, 100]
    elif kind == "figure-moved":
        doc["mode1"][1]["realised_miscoverage"] = 0.0700
    elif kind == "recipe-moved":
        doc["mode2"][0]["construction"]["value"] = 0.999
    elif kind == "doc-drift":
        # the artefact stays the committed truth; only the document is forged
        return REPO / ARTEFACT_REL
    else:
        raise AssertionError("no such plant %r" % kind)
    path = tmp / ("%s.json" % kind)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return path


def _forge_doc(kind: str, tmp: Path) -> Path:
    """The `doc-drift` plant: a document that is no longer a render of the committed artefact.

    One mode-1 table row is deleted. The plant asserts it removed a line, so a document whose shape changed
    cannot turn this into a no-op guard.
    """
    assert kind == "doc-drift", kind
    path = tmp / "DRIFT.md"
    lines = (REPO / DOC_REL).read_text().splitlines()
    first_n = str(artefact()["mode1"][0]["n"])
    keep = [line for line in lines if not line.startswith("| %s " % first_n)]
    assert len(keep) == len(lines) - 1, "the document has no mode-1 row for n=%s to drop" % first_n
    path.write_text("\n".join(keep) + "\n")
    return path


@pytest.mark.parametrize("kind", PLANTS)
def test_a_broken_publication_refuses_by_name_at_the_declared_path_with_rc_4(kind, tmp_path, monkeypatch,
                                                                            capsys):
    """A table-declared artefact this run cannot honour is the checkout's fault, not the operator's: 4.

    Each plant is forged from the committed bytes, installed at the path the build DECLARES (the module
    constant is redirected -- the tracked file is never touched), and driven through `main`. The printed name
    is asserted, so "refused" is never a bare traceback, and the code is asserted, so a missing artefact and a
    re-provenanced one are not conflated with a typo in a flag.
    """
    from tools import drift_envelope

    if kind == "doc-drift":
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", REPO / ARTEFACT_REL)
        monkeypatch.setattr(drift_envelope, "DOC_PATH", _forge_doc(kind, tmp_path))
    else:
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", _forge_artefact(kind, tmp_path))
        monkeypatch.setattr(drift_envelope, "DOC_PATH", REPO / DOC_REL)
    monkeypatch.chdir(REPO)
    rc = drift_envelope.main(["--check"])
    err = capsys.readouterr().err
    assert rc == 4, (kind, rc, err)
    assert PLANT_REASON[kind] in err, (kind, err)
    assert "Traceback" not in err, (kind, err)


def test_an_operator_named_artefact_that_is_wrong_is_usage_rc_2_not_drift_rc_4(tmp_path, capsys):
    """The who-named-the-path axis: a path the operator typed is theirs, so a bad one is 2.

    The same forged bytes as the row above; only the naming differs. This is the distinction the exit table in
    `cli.py` draws everywhere else, and the reason a missing published artefact and a typo cannot share a code.
    """
    from tools import drift_envelope

    for kind in ("truncated-weighted", "seed-moved", "empty"):
        forged = _forge_artefact(kind, tmp_path)
        assert drift_envelope.main(["--check", "--artefact", str(forged)]) == 2, (kind,
                                                                                  capsys.readouterr())
        assert PLANT_REASON[kind] in capsys.readouterr().err, (kind, PLANT_REASON[kind])
    missing = tmp_path / "no-such-file.json"
    assert drift_envelope.main(["--check", "--artefact", str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_the_producer_refuses_to_publish_the_document_without_the_artefact_or_vice_versa(tmp_path,
                                                                                        monkeypatch,
                                                                                        capsys):
    """`--out` and `--doc` are one publication: exactly one of them, at a published path, is a refusal at 2.

    The document quotes the artefact at its declared path, so prose written beside somebody else's bytes is a
    misattribution -- the rule `tools/g1_feasibility.py` inherits and states in its own words. Asserted on both
    sides: `--doc` with no `--out`, `--out` at the DECLARED artefact path with no `--doc` (that run would leave
    the committed document stale), the pair off its declared paths, and the accepted forms -- a scratch
    artefact alone, and the declared pair together -- so the guard cannot be a dead condition.
    """
    from tools import drift_envelope

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", tmp_path / "art.json")
    monkeypatch.setattr(drift_envelope, "DOC_PATH", tmp_path / "doc.md")
    assert drift_envelope.main(["--doc", str(tmp_path / "only.md")]) == 2
    err = capsys.readouterr().err
    assert "PAIR" in err and "--out" in err, err
    assert not (tmp_path / "only.md").exists(), "a refused publication wrote the document anyway"
    assert drift_envelope.main(["--out", str(tmp_path / "art.json")]) == 2
    assert "PAIR" in capsys.readouterr().err
    assert not (tmp_path / "art.json").exists(), "a refused publication wrote the artefact anyway"
    assert drift_envelope.main(["--out", str(tmp_path / "elsewhere.json"),
                                "--doc", str(tmp_path / "doc.md")]) == 2
    assert "PAIR" in capsys.readouterr().err
    # a scratch artefact on its own is the honest exception: it publishes nothing anyone can misquote.
    assert drift_envelope.main(["--out", str(tmp_path / "scratch.json")]) in (0, 3)
    assert (tmp_path / "scratch.json").is_file() and not (tmp_path / "scratch.md").exists()
    # the paired form at the declared paths writes both, and the second run refuses without --force.
    rc = drift_envelope.main(["--out", str(tmp_path / "art.json"), "--doc", str(tmp_path / "doc.md")])
    assert rc in (0, 3), rc
    assert (tmp_path / "art.json").is_file() and (tmp_path / "doc.md").is_file()
    assert drift_envelope.main(["--out", str(tmp_path / "art.json"),
                               "--doc", str(tmp_path / "doc.md")]) == 2
    assert "already exists" in capsys.readouterr().err
    assert drift_envelope.main(["--out", str(tmp_path / "art.json"),
                               "--doc", str(tmp_path / "doc.md"), "--force"]) in (0, 3)


def test_a_reduced_trial_count_may_never_be_published_beside_the_envelopes_figures(tmp_path, monkeypatch,
                                                                                  capsys):
    """Cost control, refused rather than hidden: `--trials` below the published scale cannot write a pair.

    The artefact keeps the full 4000 trials because that is the number the envelope states. A reduced run is
    allowed only into a scratch artefact that is not published -- there its provenance honestly says 400 -- and
    refused when it would write the declared artefact or name a document, because that document quotes 0.0933.
    Both directions are asserted: the refusal, and the accepted scratch run with its own provenance, so the
    guard is about the scale reaching publication and not about the flag's existence.
    """
    from tools import drift_envelope

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", tmp_path / "art.json")
    monkeypatch.setattr(drift_envelope, "DOC_PATH", tmp_path / "doc.md")
    assert drift_envelope.main(["--trials", "400"]) == 2
    assert "SCALE" in capsys.readouterr().err.upper()
    assert not (tmp_path / "art.json").exists() and not (tmp_path / "doc.md").exists()
    assert drift_envelope.main(["--out", str(tmp_path / "art.json"), "--doc",
                                str(tmp_path / "doc.md"), "--trials", "400"]) == 2
    assert "SCALE" in capsys.readouterr().err.upper()
    scratch = tmp_path / "scratch.json"
    assert drift_envelope.main(["--out", str(scratch), "--trials", "400"]) in (0, 3)
    reduced = json.loads(scratch.read_text())
    assert int(reduced["provenance"]["trials_per_size"]) == 400, reduced["provenance"]
    assert [row["trials"] for row in reduced["mode1"]] == [400, 400], reduced["mode1"]
    assert reduced["weighted_envelope"] == list(WEIGHTED_ENVELOPE)
    # and the same flag at the published scale is accepted, so the refusal is the scale, not the flag.
    assert drift_envelope.main(["--out", str(tmp_path / "art.json"), "--doc", str(tmp_path / "doc.md"),
                                "--trials", str(PUBLISHED_TRIALS)]) in (0, 3)


def test_the_producer_writes_the_committed_bytes_and_check_re_derives_them_at_rc_0(tmp_path, monkeypatch,
                                                                                   capsys):
    """The determinism the publication depends on: a fresh run reproduces the committed artefact byte for byte.

    The full mode-1 Monte-Carlo at 4000 trials, the four mode-2 sequences at their published lengths and the
    400-sequence sweep are re-run here, so this row also measures what a re-derivation costs (the producer
    prints it, and the report quotes it). A producer that emits a different artefact each run is not a
    re-derivation, and the byte comparison is what catches it.
    """
    from tools import drift_envelope

    monkeypatch.chdir(REPO)
    out = tmp_path / "again.json"
    rc = drift_envelope.main(["--out", str(out)])
    assert rc == 0, (rc, capsys.readouterr())
    assert out.read_text() == (REPO / ARTEFACT_REL).read_text(), (
        "the producer does not reproduce its own committed bytes")
    assert drift_envelope.main(["--check"]) == 0, capsys.readouterr()
    assert "re-derived" in capsys.readouterr().out


def test_no_plant_of_a_broken_publication_reaches_rc_1(tmp_path, monkeypatch):
    """rc 1 is outside this project's contract, so every plant is re-run looking for it.

    A bare `ValueError` reaching the CLI is a defect, and the class of defect the exit-code table in
    `drift.py`'s docstring promises does not exist. Both naming axes are walked -- the declared path (each
    plant must be 4) and the operator-named path (each must be 2) -- plus every publish refusal.
    """
    from tools import drift_envelope

    codes = set()
    monkeypatch.chdir(tmp_path)
    for kind in PLANTS:
        if kind == "doc-drift":
            monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", REPO / ARTEFACT_REL)
            monkeypatch.setattr(drift_envelope, "DOC_PATH", _forge_doc(kind, tmp_path))
            codes.add(drift_envelope.main(["--check"]))
            monkeypatch.setattr(drift_envelope, "DOC_PATH", REPO / DOC_REL)
        forged = _forge_artefact(kind, tmp_path)
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", forged)
        codes.add(drift_envelope.main(["--check"]))
        codes.add(drift_envelope.main(["--check", "--artefact", str(forged)]))
    codes.add(drift_envelope.main(["--out", str(tmp_path / "art.json")]))
    codes.add(drift_envelope.main(["--doc", str(tmp_path / "one.md")]))
    codes.add(drift_envelope.main(["--trials", "7"]))
    codes.add(drift_envelope.main(["--out", str(tmp_path / "a.json"), "--doc",
                                   str(tmp_path / "a.md"), "--trials", "7"]))
    assert codes <= {0, 2, 3, 4}, sorted(codes)
    assert 1 not in codes, sorted(codes)
