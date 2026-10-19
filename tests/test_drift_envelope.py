"""Task 5's drift-envelope artefact: `data/drift_envelope.json` and `docs/DRIFT.md` must be re-derivable.

Plan B3 declared the drift envelope in `src/autorate/drift.py`'s constants and `tests/test_drift.py` re-runs
their measurements, so the two withdrawals were re-runnable but the gate never checked them and `data/`
published nothing. This file is the artefact's own guard: every envelope line in the published bytes is
compared to the tuple in the module, every published figure is recomputed here from the shipped functions,
and every refusal is planted through the producer's real entry point.

What each row can catch is stated in the row that owns it, and the rows are named rather than numbered:
an ordinal here goes stale the moment a row is inserted, and a stale ordinal is worse than none because it
sends a reader to the wrong function.

* an envelope edit in `drift.py` that the artefact and the document do not carry
  (`test_every_envelope_line_in_the_artefact_is_the_tuple_in_drift_py_verbatim` and
  `test_the_document_carries_every_envelope_line_byte_for_byte` -- they read the module's tuple and the
  artefact's stored copy, not a remembered list of words, so a docstring edit reddens a row rather than
  going unread);
* a published figure that no longer comes from the arithmetic it names
  (`test_the_mode2_realised_rates_and_the_bound_comparison_re_derive_from_the_artefacts_recipes`,
  `test_the_mode1_coverage_measurement_re_derives_at_a_reduced_scale_and_says_so`, and the full-scale rows
  beside them: mode 2 is re-derived at full scale from the recipes IN the artefact, mode 1 at the reduced
  trial count THIS FILE NAMES, with the artefact's own provenance pinned to 4000 so the two scales cannot
  be confused);
* a document that states a number the artefact does not hold, or holds a machine path or a timestamp
  (`test_the_document_states_both_withdrawals_in_plain_words_and_owns_every_figure_it_prints` and
  `test_no_tracked_byte_of_the_publication_names_a_machine_path_or_a_timestamp`);
* a stored float that carries more precision than the artefact declares for itself
  (`test_every_float_literal_in_the_published_artefact_sits_on_the_declared_grid`);
* a broken publication -- absent, wrong-shaped, truncated, re-provenanced, or quoted from a sentence the
  module does not state -- reaching an operator as a traceback instead of a named refusal at 0/2/3/4 (the
  rows from `test_a_broken_publication_refuses_by_name_at_the_declared_path_with_rc_4` through
  `test_a_source_constant_that_has_vanished_refuses_by_name_on_both_axes`;
  `test_no_plant_of_a_broken_publication_reaches_rc_1` then asserts the no-rc-1 property over every plant
  in this file, so a plant that only this header knows about is still walked);
* the publication escaping the repository's own gate -- logic parked in a script the gate cannot import, an
  artefact figure the arm does not re-derive, a document not in the published table (the rows under
  `# the wiring:` below, starting at
  `test_the_drift_logic_lives_in_the_package_and_the_tool_is_a_thin_cli_over_it`).

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

#: The command that republishes the pair, spelled once. `read_json`'s hint and
#: `test_the_hint_a_missing_artefact_prints_is_a_command_the_producer_accepts` both read it, so a hint that
#: drifts into a form the pair guard refuses is caught here rather than shipped.
PAIR_COMMAND = "python3 tools/drift_envelope.py --out %s --doc %s --force" % (ARTEFACT_REL, DOC_REL)


def read_json(path: Path) -> dict:
    assert path.is_file(), "%s is missing -- run `%s`" % (path, PAIR_COMMAND)
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


def _lines_missing_from(text: str, lines) -> list:
    """The published lines whose folded text is not in `text`.

    One owner for the comparison so the row that uses it and the plant that reddens it cannot disagree about
    what "carried" means. A re-wrap is allowed (both sides are folded); a dropped or reworded clause is not.
    """
    folded = " ".join(text.split())
    return [" ".join(line.split()) for line in lines if " ".join(line.split()) not in folded]


def test_the_document_carries_every_envelope_line_byte_for_byte():
    """The rendered prose cannot soften the withdrawal it is supposed to publish.

    The lines compared are the ARTEFACT's stored copies -- which `test_every_envelope_line_in_the_artefact_
    is_the_tuple_in_drift_py_verbatim` has already pinned to the module's tuples -- so the document is
    checked against the bytes the publication carries rather than against a second reading of the module.
    That is what makes `test_the_document_row_fails_when_the_artefact_carries_a_line_it_does_not_print`
    possible: the plant forges the artefact, and only a row that reads the artefact can notice.
    """
    doc = artefact()
    stored = list(doc["weighted_envelope"]) + list(doc["aci_envelope"])
    text = _doc_text()
    assert _lines_missing_from(text, stored) == [], [line[:80] for line in _lines_missing_from(text, stored)]
    forged = " ".join("the regret statement holds for every accepted sequence".split())
    assert forged not in " ".join(text.split())


def test_the_document_row_fails_when_the_artefact_carries_a_line_it_does_not_print():
    """The self-falsifier the header promised and
    `test_the_document_carries_every_envelope_line_byte_for_byte` did not deliver until it read the artefact.

    Appending one line to the artefact's stored envelope copy -- the plant the docstring named -- cannot
    redden a row that reads only the module and the document, because neither of those changes. Re-run
    against the previous version of this row it stayed green, which is the defect this row now closes:
    a guard that names a plant it cannot see is a comment, not a check.
    """
    import copy

    forged = copy.deepcopy(artefact())
    forged["weighted_envelope"].append("the finite-sample statement is restored under a declared ratio")
    missing = _lines_missing_from(_doc_text(), forged["weighted_envelope"] + forged["aci_envelope"])
    assert missing == [" ".join(forged["weighted_envelope"][-1].split())], missing
    # and the unforged artefact agrees, so the row above is not passing on an empty comparison
    assert _lines_missing_from(_doc_text(), artefact()["weighted_envelope"]
                               + artefact()["aci_envelope"]) == []


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

    The comparison is exact at the artefact's OWN declared grid (`provenance.published_decimals`, ledger
    R-121), not a tolerance on the raw double. A stored 16-digit `0.02877777777777778` publishes a libm fact
    as evidence, and `math` differs by one unit in the last place between Apple's and glibc's: the earlier
    form of this row compared raw values with `abs=1e-9`, which is why rounding at store time needed this
    change rather than being free. Exactness is kept -- it is the grid that is canonicalised, at the producer.
    """
    doc = artefact()
    alpha = float(doc["provenance"]["alpha"])
    gamma = float(doc["provenance"]["gamma"])
    decimals = int(doc["provenance"]["published_decimals"])
    rows = doc["mode2"]
    assert len(rows) == 4, [r["name"] for r in rows]
    for row in rows:
        scores = materialise(row["construction"])
        assert len(scores) == row["rounds"] == row["construction"]["rounds"], row["name"]
        assert _digest(scores) == row["sequence_digest_sha256"], (
            "%s: the stored recipe no longer materialises the sequence that was measured" % row["name"])
        realised, clipped = _long_run_rate(scores, alpha, gamma)
        assert round(realised, decimals) == row["realised_long_run_rate"], (row["name"], realised)
        bound = aci_regret_bound(len(scores), alpha, gamma)
        assert round(bound, decimals) == row["regret_bound"], (row["name"], bound)
        assert round(abs(realised - alpha), decimals) == row["deviation_from_alpha"], row["name"]
        assert row["deviation_from_alpha"] > row["regret_bound"], (row["name"], row["deviation_from_alpha"],
                                                                   row["regret_bound"])
        assert abs(realised - alpha) > bound, (row["name"], realised, bound)
        assert row["violates_bound"] is True, row
        assert row["clip_observable"] is clipped, row["name"]
    # the two controls in `tests/test_drift.py`'s row: there the inequality DOES hold, so the four above are
    # a falsification and not a blanket "nothing holds".
    assert len(doc["mode2_controls"]) == 2, [r["name"] for r in doc["mode2_controls"]]
    for row in doc["mode2_controls"]:
        scores = materialise(row["construction"])
        realised, clipped = _long_run_rate(scores, alpha, gamma)
        assert round(realised, decimals) == row["realised_long_run_rate"], (row["name"], realised)
        assert round(abs(realised - alpha), decimals) == row["deviation_from_alpha"], row["name"]
        assert round(aci_regret_bound(len(scores), alpha, gamma), decimals) == row["regret_bound"], row["name"]
        assert row["deviation_from_alpha"] <= row["regret_bound"], row
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
    decimals = int(doc["provenance"]["published_decimals"])
    bound = round(aci_regret_bound(rounds, alpha, gamma), decimals)
    assert bound == sweep["bound"], (bound, sweep["bound"])
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
# Every row below plants a broken publication and drives `autorate.drift_envelope.main` -- the real entry
# point, which `tools/drift_envelope.py` is a thin CLI over -- asserting the name it prints and the code it
# returns. Codes are 0/2/3/4 and nothing here may reach 1;
# `test_no_plant_of_a_broken_publication_reaches_rc_1` walks the whole matrix again for that.

# Every broken-publication shape this file can forge, and the name the producer has to print for it. The
# tuple is the subject of the rc-1 sweep and the dict is the expectation of the rc-4 row, so a plant added
# here is driven through both and cannot become an untested fixture.
#
# The last seven are the missing-subkey class: a top-level-valid artefact with exactly ONE subkey removed.
# Each of them read the module docstring's "Nothing escapes at 1" (`src/autorate/drift_envelope.py`, the text
# this file was written against as `tools/drift_envelope.py:49`) as a promise and reached the
# operator as a bare `KeyError` traceback at rc 1 on BOTH naming axes (measured before this file grew
# them), because the two catch-alls listed `ValueError, TypeError, ArithmeticError, OSError` and a `KeyError`
# is none of those. They are in the sweep precisely so that guard walks the shape it used to miss.
#
# The two after them are the two prose-and-precision defects the same sweep could not see: a stored withdrawal
# reason the module never states (`why-reworded`, MAJOR-2), and a figure stored at 16 digits instead of the
# grid the artefact itself declares (`raw-double`, MINOR-3 -- the value is exactly what `data/` held before
# the rounding, so the plant is the previous truth, not an invention).
PLANTS = ("missing", "list", "scalar", "empty", "no-envelope-key", "truncated-weighted",
          "truncated-aci", "seed-moved", "trials-moved", "sizes-moved", "doc-drift",
          "figure-moved", "recipe-moved",
          "mode1-no-trials", "mode1-no-envelope-cited", "mode2-no-construction",
          "mode2-recipe-no-value", "withdrawals-no-mode1", "check-no-agrees", "sweep-no-bound",
          "why-reworded", "raw-double", "why-other-line", "cited-figure-moved")

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
    "why-reworded": "WITHDRAWAL PROSE",
    "raw-double": "DRIFT",
    "why-other-line": "WITHDRAWAL PROSE",
    "cited-figure-moved": "DRIFT",
    "mode1-no-trials": "ARTEFACT SHAPE",
    "mode1-no-envelope-cited": "ARTEFACT SHAPE",
    "mode2-no-construction": "ARTEFACT SHAPE",
    "mode2-recipe-no-value": "ARTEFACT SHAPE",
    "withdrawals-no-mode1": "ARTEFACT SHAPE",
    "check-no-agrees": "ARTEFACT SHAPE",
    "sweep-no-bound": "ARTEFACT SHAPE",
}

#: The half of the refusal line that says WHICH quantity the guard is complaining about. `PLANT_REASON` names
#: the class of defect, and every disagreement line starts with the same `DRIFT:` prefix, so a figure plant
#: that only asserted its class could not tell "the gate caught my forged field" from "the gate printed a
#: generic disagreement about something else" -- the review's finding on the first `raw-double`.
PLANT_DETAIL = {
    "raw-double": "regret_bound",
    "cited-figure-moved": "envelope_cited_bound",
    "why-other-line": "withdrawals.mode1.why",
}
assert set(PLANTS) == set(PLANT_REASON), "the plant sweep and the plant expectation have diverged"

#: The subkey each missing-subkey plant deletes, and therefore the name the refusal has to print. Widening a
#: catch-all without naming what was missing would trade a traceback for a shrug, so the rc-4 row and the
#: rc-2 row both assert this string appears in the producer's own line, beside the path it was reading.
PLANT_SUBKEY = {
    "mode1-no-trials": "trials",
    "mode1-no-envelope-cited": "envelope_cited",
    "mode2-no-construction": "construction",
    "mode2-recipe-no-value": "value",
    "withdrawals-no-mode1": "mode1",
    "check-no-agrees": "agrees",
    "sweep-no-bound": "bound",
}
assert set(PLANT_SUBKEY) <= set(PLANTS), "a subkey plant that the rc-1 sweep would never walk"
assert all(PLANT_REASON[kind] == "ARTEFACT SHAPE" for kind in PLANT_SUBKEY), (
    "a missing subkey is a shape this build does not read, so it refuses under that name")


def _forge_artefact(kind: str, tmp: Path) -> Path:
    """Write a broken artefact of the named shape at a temp path and return that path."""
    import copy

    from autorate import drift_envelope

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
    elif kind == "why-reworded":
        # MAJOR-2's shape: a top-level-valid artefact whose quoted withdrawal reason is prose the module does
        # not contain. `render_document` would happily print it inside quotation marks, so the artefact has to
        # be checked against the tuple it claims to copy.
        doc["withdrawals"]["mode1"]["why"] = ("the shipped correction is the exchangeable case's: the test "
                                             "point's own target-regime weight is supplied as a constant")
    elif kind == "raw-double":
        # MINOR-3's shape, using the exact value `data/drift_envelope.json` stored before the rounding.
        doc["mode2"][0]["regret_bound"] = 0.02877777777777778
    elif kind == "why-other-line":
        # Membership is not identity: line 0 of the SAME tuple is prose the module states, and a guard that
        # only asked "is this one of the lines?" let another withdrawal's reason be published as this one's.
        # Measured on `2acf379`: that artefact plus its own rendered document answered rc 0 and
        # "re-derived 19 claims", because the module offers that line as the assumption, not the reason.
        doc["withdrawals"]["mode1"]["why"] = list(WEIGHTED_ENVELOPE)[0]
    elif kind == "cited-figure-moved":
        # The cited half of a published figure, which nothing compared until the `RECHECK_*` lists grew
        # the cited fields. This field is chosen so that ONLY that comparison can catch it:
        # `mode2[].envelope_cited_bound` is stored but never rendered, so the forged artefact's document
        # stays a byte-faithful render and the prose check cannot fire. The first version of this plant
        # forged `mode1[1].envelope_cited`, which the mode-1 table prints -- that artefact was refused
        # before the fix as well, by the DOCUMENT comparison, so the row proved nothing about the guard
        # it was written for. Measured on `66b5847`: rc 0 for this plant.
        doc["mode2"][0]["envelope_cited_bound"] = 0.9
    elif kind in PLANT_SUBKEY:
        _remove_subkey(doc, kind)
        # the whole point of this class is that the artefact still LOOKS like a publication: every
        # top-level key is there, and only one subkey of one row is gone. Asserted against the tool's own
        # REQUIRED_KEYS so a plant that deleted a top-level key cannot quietly become a different test.
        leftover = [key for key in drift_envelope.REQUIRED_KEYS if key not in doc]
        assert not leftover, "%s removed a top-level key: %s" % (kind, leftover)
    else:
        raise AssertionError("no such plant %r" % kind)
    path = tmp / ("%s.json" % kind)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return path


def _remove_subkey(doc: dict, kind: str) -> None:
    """Delete the one subkey `kind` names, in place, from an artefact copy."""
    if kind == "mode1-no-trials":
        del doc["mode1"][0]["trials"]
    elif kind == "mode1-no-envelope-cited":
        del doc["mode1"][0]["envelope_cited"]
    elif kind == "mode2-no-construction":
        del doc["mode2"][0]["construction"]
    elif kind == "mode2-recipe-no-value":
        del doc["mode2"][0]["construction"]["value"]
    elif kind == "withdrawals-no-mode1":
        del doc["withdrawals"]["mode1"]
    elif kind == "check-no-agrees":
        del doc["reproduction"]["checks"][0]["agrees"]
    elif kind == "sweep-no-bound":
        del doc["mode2_sweep"]["bound"]
    else:
        raise AssertionError("not a missing-subkey plant: %r" % kind)
    assert doc, "the plant emptied the artefact instead of removing one subkey"


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
    re-provenanced one are not conflated with a typo in a flag. A missing-subkey plant is asserted further:
    the line has to name the subkey it wanted and the file it was reading; a figure-or-prose plant has to name
    the quantity (`PLANT_DETAIL`), because the class prefix every disagreement line carries is not evidence
    that THIS defect was the one caught.
    """
    from autorate import drift_envelope

    if kind == "doc-drift":
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", REPO / ARTEFACT_REL)
        monkeypatch.setattr(drift_envelope, "DOC_PATH", _forge_doc(kind, tmp_path))
        forged = REPO / ARTEFACT_REL
    else:
        forged = _forge_artefact(kind, tmp_path)
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", forged)
        monkeypatch.setattr(drift_envelope, "DOC_PATH", REPO / DOC_REL)
    monkeypatch.chdir(REPO)
    rc = drift_envelope.main(["--check"])
    err = capsys.readouterr().err
    assert rc == 4, (kind, rc, err)
    assert PLANT_REASON[kind] in err, (kind, err)
    assert "Traceback" not in err, (kind, err)
    if kind in PLANT_SUBKEY:
        assert "'%s'" % PLANT_SUBKEY[kind] in err, (kind, err)
    if kind in PLANT_DETAIL:
        assert PLANT_DETAIL[kind] in err, (kind, err)
    if kind in PLANT_SUBKEY or kind in PLANT_DETAIL:
        assert str(forged) in err, (kind, err)


def test_an_operator_named_artefact_that_is_wrong_is_usage_rc_2_not_drift_rc_4(tmp_path, capsys):
    """The who-named-the-path axis: a path the operator typed is theirs, so a bad one is 2.

    The same forged bytes as the row above; only the naming differs -- including the two plants whose defect is
    a figure that no longer re-derives, because the defect's class names WHAT is wrong and who named the path
    decides whose fault it is. This is the distinction the exit table in `cli.py` draws everywhere else, and the
    reason a missing published artefact and a typo cannot share a code. Every missing-subkey plant is walked
    here too, since BLOCKER-1 was measured on this axis as well as the declared one.
    """
    from autorate import drift_envelope

    for kind in ("truncated-weighted", "seed-moved", "empty", "figure-moved", "recipe-moved"):
        forged = _forge_artefact(kind, tmp_path)
        assert drift_envelope.main(["--check", "--artefact", str(forged)]) == 2, (kind,
                                                                                  capsys.readouterr())
        assert PLANT_REASON[kind] in capsys.readouterr().err, (kind, PLANT_REASON[kind])
    missing = tmp_path / "no-such-file.json"
    assert drift_envelope.main(["--check", "--artefact", str(missing)]) == 2
    assert "does not exist" in capsys.readouterr().err
    for kind in sorted(set(PLANT_SUBKEY) | set(PLANT_DETAIL)):
        forged = _forge_artefact(kind, tmp_path)
        assert drift_envelope.main(["--check", "--artefact", str(forged)]) == 2, (kind,
                                                                                 capsys.readouterr())
        err = capsys.readouterr().err
        assert PLANT_REASON[kind] in err, (kind, err)
        if kind in PLANT_SUBKEY:
            assert "'%s'" % PLANT_SUBKEY[kind] in err, (kind, err)
        else:
            assert PLANT_DETAIL[kind] in err, (kind, err)
        assert str(forged) in err, (kind, err)
        assert "Traceback" not in err, (kind, err)


def test_the_hint_a_missing_artefact_prints_is_a_command_the_producer_accepts(tmp_path, monkeypatch,
                                                                              capsys):
    """MINOR-6 left a residue: the guard was fixed, the advice was not.

    The pair guard now refuses a run that writes the declared artefact without its document, and the hint this
    file prints for a missing artefact said `python3 tools/drift_envelope.py --force` -- the exact command the
    guard refuses at 2. An operator following the tool's own advice would be told their repair was a usage
    error. The row parses the command out of the message and drives it, so a hint that drifts from the guard
    reddens here instead of shipping.
    """
    from autorate import drift_envelope

    missing = tmp_path / "no-artefact.json"
    with pytest.raises(AssertionError) as caught:
        read_json(missing)
    message = str(caught.value)
    assert PAIR_COMMAND in message, message
    assert PAIR_COMMAND.split() == ["python3", "tools/drift_envelope.py", "--out", str(ARTEFACT_REL),
                                    "--doc", str(DOC_REL), "--force"], PAIR_COMMAND
    art = tmp_path / "art.json"
    doc = tmp_path / "doc.md"
    # The hint names the DECLARED paths, so running it verbatim here would rewrite the publication. What this
    # row can prove without doing that is that the command's SHAPE is accepted: the same flags, with the two
    # declared destinations mapped onto scratch files. A guard that started refusing this form would turn the
    # tool's own advice into a usage error, which is the drift this row exists to catch.
    argv = [str(art) if flag == str(ARTEFACT_REL) else str(doc) if flag == str(DOC_REL) else flag
            for flag in PAIR_COMMAND.split()[2:]]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", art)
    monkeypatch.setattr(drift_envelope, "DOC_PATH", doc)
    rc = drift_envelope.main(argv)
    err = capsys.readouterr().err
    assert "PAIR" not in err, (argv, err)
    assert rc in (0, 3), (argv, rc, err)
    assert art.is_file() and doc.is_file(), (argv, err)


def test_a_source_constant_that_has_vanished_refuses_by_name_on_both_axes(tmp_path, monkeypatch, capsys):
    """`AttributeError` is the other half of the escape: the envelope this artefact copies is not there.

    The declared module is read to check the committed bytes, so a `drift.py` that no longer holds
    `WEIGHTED_ENVELOPE` is the checkout's problem (4), and the identical defect while reading a path the
    operator named is theirs (2). It used to reach both as `AttributeError: module 'autorate.drift' has no
    attribute 'WEIGHTED_ENVELOPE'` at rc 1 -- the module docstring promises that code does not exist.
    """
    from autorate import drift_envelope
    from autorate import drift

    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", REPO / ARTEFACT_REL)
    monkeypatch.delattr(drift, "WEIGHTED_ENVELOPE")
    monkeypatch.chdir(REPO)
    assert drift_envelope.main(["--check"]) == 4, capsys.readouterr()
    err = capsys.readouterr().err
    assert "PUBLISHED SOURCE UNAVAILABLE" in err, err
    assert "WEIGHTED_ENVELOPE" in err, err
    assert "Traceback" not in err, err
    named = tmp_path / "named.json"
    named.write_text((REPO / ARTEFACT_REL).read_text())
    assert drift_envelope.main(["--check", "--artefact", str(named)]) == 2, capsys.readouterr()
    err = capsys.readouterr().err
    assert "PUBLISHED SOURCE UNAVAILABLE" in err and "WEIGHTED_ENVELOPE" in err, err
    assert str(named) in err, err
    assert "Traceback" not in err, err


def test_a_producer_that_builds_what_its_own_renderer_cannot_read_refuses_at_the_declared_pair(
        tmp_path, monkeypatch, capsys):
    """The publish path has the same contract: no unplanned exception may reach 1, and the destination picks.

    Two shapes are driven here. The first is a builder that returns an artefact missing the subkey the
    renderer subscripts -- `render_document`'s `doc["withdrawals"]["mode1"]` -- which is the same defect class
    BLOCKER-1 measured on the read path, at the site that WRITES. The second is a trial count the arithmetic
    cannot divide by, which the `--trials` scale guard only refuses on a publishing run. Both must be refused
    with the code the destination decides: 4 when the run would publish this build's own pair, 2 when the
    operator named somewhere else. Neither may write a byte.
    """
    import copy

    from autorate import drift_envelope

    committed = artefact()

    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", tmp_path / "art.json")
    monkeypatch.setattr(drift_envelope, "DOC_PATH", tmp_path / "doc.md")
    monkeypatch.chdir(tmp_path)
    # an arithmetic error no site named, on the route that bypasses the SCALE guard: the reduced-scale
    # `--trials` refusal only fires for a publishing run, and zero trials divide the mean by zero.
    rc = drift_envelope.main(["--out", str(tmp_path / "zero.json"), "--trials", "0"])
    err = capsys.readouterr().err
    assert rc == 2, (rc, err)
    assert "Traceback" not in err, err
    assert not (tmp_path / "zero.json").exists()

    def build_without_a_withdrawal_reason(trials):
        del trials
        doc = copy.deepcopy(committed)
        del doc["withdrawals"]["mode1"]
        return doc

    monkeypatch.setattr(drift_envelope, "build_artefact", build_without_a_withdrawal_reason)
    rc = drift_envelope.main(["--out", str(tmp_path / "art.json"), "--doc", str(tmp_path / "doc.md")])
    err = capsys.readouterr().err
    assert rc == 4, (rc, err)
    assert "'mode1'" in err and "Traceback" not in err, err
    assert not (tmp_path / "art.json").exists() and not (tmp_path / "doc.md").exists(), (
        "a refused publication wrote its artefact anyway")
    # the same defect aimed at a scratch path is the operator's: 2, still no traceback, still nothing written
    scratch = tmp_path / "scratch.json"
    rc = drift_envelope.main(["--out", str(scratch)])
    err = capsys.readouterr().err
    assert rc == 2, (rc, err)
    assert "'mode1'" in err and "Traceback" not in err, err
    assert not scratch.exists()


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
    from autorate import drift_envelope

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
    from autorate import drift_envelope

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
    from autorate import drift_envelope

    monkeypatch.chdir(REPO)
    out = tmp_path / "again.json"
    rc = drift_envelope.main(["--out", str(out)])
    assert rc == 0, (rc, capsys.readouterr())
    assert out.read_text() == (REPO / ARTEFACT_REL).read_text(), (
        "the producer does not reproduce its own committed bytes")
    assert drift_envelope.main(["--check"]) == 0, capsys.readouterr()
    assert "re-derived" in capsys.readouterr().out


def test_no_plant_of_a_broken_publication_reaches_rc_1(tmp_path, monkeypatch, capsys):
    """rc 1 is outside this project's contract, so every plant is re-run looking for it.

    A bare `ValueError` reaching the CLI is a defect, and the class of defect the exit-code table in
    `drift.py`'s docstring promises does not exist. Both naming axes are walked -- the declared path (each
    plant must be 4) and the operator-named path (each must be 2) -- plus every publish refusal. Read in
    process, an unplanned exception does not print a traceback: it propagates out of `main` and this row
    errors with that exception, which is the same defect the subprocess run showed as rc 1. Because these
    plants are here, the sweep walks a top-level-valid artefact with one subkey missing -- the shape whose
    absence let BLOCKER-1 through while this row stayed green.

    The subset check is the code assertion; the two lines after it are the ones that can fail on their own,
    so a refusal that lands on a documented code while printing nothing (or a traceback) is caught here and
    not only by the rows that name each plant. This replaces the `1 not in codes` line that the subset check
    already implied.
    """
    from autorate import drift_envelope

    outcomes = []

    def run(label: str, argv: list) -> int:
        code = drift_envelope.main(argv)
        outcomes.append((label, code, capsys.readouterr().err))
        return code

    monkeypatch.chdir(tmp_path)
    for kind in PLANTS:
        if kind == "doc-drift":
            monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", REPO / ARTEFACT_REL)
            monkeypatch.setattr(drift_envelope, "DOC_PATH", _forge_doc(kind, tmp_path))
            run("%s declared" % kind, ["--check"])
            monkeypatch.setattr(drift_envelope, "DOC_PATH", REPO / DOC_REL)
        forged = _forge_artefact(kind, tmp_path)
        monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", forged)
        run("%s declared" % kind, ["--check"])
        run("%s named" % kind, ["--check", "--artefact", str(forged)])
    run("pair-out named", ["--out", str(tmp_path / "art.json")])
    run("pair-doc named", ["--doc", str(tmp_path / "one.md")])
    run("scale named", ["--trials", "7"])
    run("scale-pair named", ["--out", str(tmp_path / "a.json"), "--doc",
                             str(tmp_path / "a.md"), "--trials", "7"])
    codes = {code for _, code, _ in outcomes}
    assert codes <= {0, 2, 3, 4}, sorted(codes)
    refusals = [(label, code, err) for label, code, err in outcomes if code != 0]
    assert all(err.strip() for _, _, err in refusals), sorted(label for label, _, err in refusals
                                                              if not err.strip())
    assert all("Traceback" not in err for _, _, err in refusals), sorted(
        label for label, _, err in refusals if "Traceback" in err)


# ---------------------------------------------------- MAJOR-2 / MINOR-3 / MINOR-6 (freeze-13 review round)

def _off_grid(value, decimals: int) -> bool:
    """True when a stored float is NOT the decimal the artefact declares for itself.

    The predicate is `value == round(value, decimals)` rather than a digit count of `repr`, because a float
    whose repr is exponential (`4.499999999999997e-05`) has no digits to count and is off the grid at six
    decimals, while `2.5e-05` is ON it -- which is why this is a comparison and not a digit count.
    `decimals` comes
    from the artefact's OWN `provenance.published_decimals`, so the gate asks the publication what precision
    it claims and holds it to that answer -- it does not import a second constant that can fall behind.
    """
    return isinstance(value, float) and value != round(value, decimals)


def _off_grid_paths(node, decimals: int, prefix: str = "") -> list:
    """Every path in the artefact whose float value is off the declared grid."""
    offenders = []
    if isinstance(node, dict):
        for key in sorted(node):
            offenders.extend(_off_grid_paths(node[key], decimals, "%s.%s" % (prefix, key)))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            offenders.extend(_off_grid_paths(item, decimals, "%s[%d]" % (prefix, index)))
    elif _off_grid(node, decimals):
        offenders.append("%s=%r" % (prefix or "$", node))
    return offenders


def test_every_float_literal_in_the_published_artefact_sits_on_the_declared_grid():
    """No published byte may carry more precision than the artefact declares.

    The tool's own comment has said six decimals since ledger R-121, and mode 1 honoured it while mode 2 and
    the sweep did not: `regret_bound` was stored as `0.02877777777777778` and `deviation_from_alpha` as
    `0.004499999999999997`. Those last bits are a libm fact, and this project has already been bitten once by
    publishing one -- the contamination interval differed by one unit in the last place between Apple's math
    library and glibc's, which is a platform fact masquerading as evidence.
    """
    doc = artefact()
    decimals = int(doc["provenance"]["published_decimals"])
    assert decimals > 0, decimals
    offenders = _off_grid_paths(doc, decimals)
    assert offenders == [], offenders


def test_the_grid_row_fails_on_a_stored_double_from_before_the_rounding():
    """The plant that proves the row above can fail: this is the byte `data/` actually held.

    Asserted in both directions, because a residue row that never finds an offender is indistinguishable from
    a residue row that cannot look.
    """
    import copy

    doc = copy.deepcopy(artefact())
    decimals = int(doc["provenance"]["published_decimals"])
    assert _off_grid_paths(doc, decimals) == []
    doc["mode2"][0]["regret_bound"] = 0.02877777777777778
    offenders = _off_grid_paths(doc, decimals)
    assert offenders == [".mode2[0].regret_bound=0.02877777777777778"], offenders
    del doc["mode2"][0]["regret_bound"]
    doc["mode2"][0]["deviation_from_alpha"] = 0.004499999999999997
    assert _off_grid_paths(doc, decimals), "the row fires on one field and not on its twin"


def test_every_stored_withdrawal_reason_is_a_line_the_module_itself_states():
    """The document quotes the module's reason, so the quotation must BE one of the module's lines.

    Before this row the artefact stored a paraphrase typed into `build_artefact` and `docs/DRIFT.md` printed
    it inside quotation marks after "the module states the reason as" -- sentences that do not occur anywhere
    in `src/autorate/drift.py` (MAJOR-2, measured by grepping the module for them). A quotation that is not a
    copy can outlive the sentence it claims to quote, which is exactly the failure this artefact's whole
    envelope-copy machinery exists to prevent for the tuple lines.
    """
    doc = artefact()
    folded = " ".join(_doc_text().split())
    for mode, name, lines in (("mode1", "WEIGHTED_ENVELOPE", WEIGHTED_ENVELOPE),
                              ("mode2", "ACI_ENVELOPE", ACI_ENVELOPE)):
        block = doc["withdrawals"][mode]
        assert block["reason_owner"] == "drift.%s" % name, block
        assert "owner" not in block, "the block is labelled as though the whole summary were the module's"
        assert block["why"] in list(lines), (mode, block["why"][:80])
        assert " ".join(block["why"].split()) in folded, (mode, block["why"][:80])
        assert 'the module states the reason verbatim' in folded, folded[:200]


def test_a_forced_run_at_the_default_out_that_writes_no_document_is_refused(tmp_path, monkeypatch, capsys):
    """`--force` with no `--doc` rewrites the published artefact and deliberately not its document.

    The pair guard keyed on the flags a reader typed, not on what the run writes: naming `--out data/...`
    explicitly was refused, while the same declared destination reached by DEFAULTING `--out` was not, so
    `python3 tools/drift_envelope.py --force` published new figures beside a document quoting the old ones --
    the state the guard's own message calls "exactly the drift this gate exists to catch" (MINOR-6). The
    refusal is exit 2 with both paths named; the paired form still writes both.
    """
    from autorate import drift_envelope

    art = tmp_path / "art.json"
    doc = tmp_path / "doc.md"
    art.write_text((REPO / ARTEFACT_REL).read_text())
    doc.write_text((REPO / DOC_REL).read_text())
    before = art.read_text(), doc.read_text()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(drift_envelope, "ARTEFACT_PATH", art)
    monkeypatch.setattr(drift_envelope, "DOC_PATH", doc)
    rc = drift_envelope.main(["--force"])
    err = capsys.readouterr().err
    assert rc == 2, (rc, err)
    assert "PAIR" in err, err
    assert str(ARTEFACT_REL) in err and str(DOC_REL) in err, err
    assert (art.read_text(), doc.read_text()) == before, "a refused publication rewrote the artefact"
    # the same destination, named as a pair, is accepted -- the refusal is the missing half, not the write
    rc = drift_envelope.main(["--out", str(art), "--doc", str(doc), "--force"])
    out_err = capsys.readouterr().err
    assert rc in (0, 3), (rc, out_err)
    assert json.loads(art.read_text())["producer"] == "tools/drift_envelope.py", art.read_text()[:200]
    assert doc.read_text().startswith("# B3's drift envelope, published"), doc.read_text()[:120]
    # and a scratch run with no document is still the honest exception
    scratch = tmp_path / "scratch.json"
    assert drift_envelope.main(["--out", str(scratch)]) in (0, 3), capsys.readouterr()
    assert scratch.is_file() and not (tmp_path / "scratch.md").exists()


# ------------------------------------------------------ the wiring: one owner for the logic, and the gate arm
#
# MAJOR-1 has an architectural root cause (§7): `tools/drift_envelope.py` owned the measurement drivers, the
# builder, the renderer AND the gate logic, so `autorate verify` had no library entry point to call and the
# published envelope could only be policed by this file. The rows below pin the two halves of the fix -- the
# logic living in the package so the gate can import it, and the gate's own arm re-deriving every quantity the
# producer re-derives -- and each names the plant that turns it red.

def test_the_drift_logic_lives_in_the_package_and_the_tool_is_a_thin_cli_over_it():
    """`tools/drift_envelope.py` must import the logic, not own it (MAJOR-1's root cause, §7).

    Asserted through `inspect.getsource` on the two REAL module objects and parsed as a tree, not by scanning
    the tool's text for a substring: a substring scan cannot tell a file that MENTIONS `build_artefact` from a
    file that DEFINES it, and the claim being pinned is about definitions. The strongest form is object
    identity -- the entry point the tool runs has to BE the package's function, so a second copy of the logic
    in the tool is impossible while this row is green, and a monkeypatch aimed at the package cannot miss.

    Red on arrival for this change: `autorate.drift_envelope` did not exist, so the import is the failure.
    """
    import ast
    import inspect
    from pathlib import Path

    from autorate import drift_envelope as logic

    from tools import drift_envelope as tool

    # The module the gate imports is this checkout's, not another tree's installed copy.
    assert Path(inspect.getfile(logic)).relative_to(REPO) == Path("src") / "autorate" / "drift_envelope.py"
    tool_tree = ast.parse(inspect.getsource(tool))
    owned = sorted(node.name for node in tool_tree.body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    assert owned == [], "%s defines %s; the logic belongs to autorate.drift_envelope" % (tool.__file__, owned)
    sources = sorted(node.module for node in ast.walk(tool_tree) if isinstance(node, ast.ImportFrom))
    assert "autorate.drift_envelope" in sources, sources
    assert tool.main is logic.main, "the tool runs a different `main` than the module the gate calls"
    for name in ("build_artefact", "render_document", "read_artefact", "check_envelope_copies",
                 "check_provenance", "rederive_and_compare", "measure_mode1", "measure_mode2",
                 "walk_mode2", "measure_mode2_sweep", "REQUIRED_KEYS", "PUBLISHED_DECIMALS",
                 "DriftEnvelopeUsage", "DriftEnvelopeState"):
        assert hasattr(logic, name), "the module the gate calls does not own %s" % name
        assert not hasattr(tool, name), "the thin tool still owns %s" % name


# ---------------------------------------------------------------- the gate's own arm, and its plants
#
# MAJOR-1 is closed by an arm in `report.py` that `cli.cmd_verify` calls: the published figures stop being
# evidence this file alone polices. The rows below drive THAT arm -- the same function the gate runs -- and
# each names the plant that turns it red. Two kinds of proof appear here and they are deliberately different:
# one row asserts the COMPLETE label set against the committed bytes (so every published figure is shown to be
# compared, at no runtime cost), and one row rebuilds the measurement once per comparison KIND (24 rebuilds at
# 0.6s each, measured) to show each of those comparisons can actually fail and by what name.
#
# A third row is not a plant at all: `test_the_arm_and_the_producer_name_the_same_quantity_for_the_same_plant`
# puts one defect through the producer's own `rederive_and_compare` and through the gate's arm and requires the
# same field out of both, which is what makes "the two surfaces agree at the same granularity" a checked
# sentence rather than a docstring.


def _drive_arm(monkeypatch, mutate=None):
    """Run the real `report.rederive_drift` against the committed artefact; return (labels, drift, rubric).

    `mutate` edits the artefact as the gate READS it and never touches the file on disk; the hook is
    `report.read_drift`, the seam `tests/test_g1_feasibility.py` uses for the ceiling arm. The two sinks are
    the gate's own `expect` and `expect_rubric`, so a rubric row this arm has no business making is visible
    here instead of being folded into a drift line.
    """
    import copy

    from autorate import report

    # `monkeypatch.setattr` on the same target twice would otherwise chain: the second drive would start from
    # an artefact the first drive had already mutated, and a row that plants one figure would report two.
    # `_undispatched` is the seam that keeps every drive reading the committed bytes.
    original = getattr(report.read_drift, "_undispatched", report.read_drift)

    def patched(path):
        doc = original(path)
        return mutate(copy.deepcopy(doc)) if mutate is not None else doc

    patched._undispatched = original
    monkeypatch.setattr(report, "read_drift", patched)
    labels, drift, mismatches = [], [], []

    def expect(label, actual, wanted):
        labels.append(label)
        if actual != wanted:
            drift.append(label)

    def expect_rubric(label, actual, wanted):
        labels.append(label)
        if actual != wanted:
            mismatches.append(label)

    report.rederive_drift(expect, expect_rubric)
    return labels, drift, mismatches


def _arm_expected_labels(doc):
    """Every label the arm owes, built from the producer's field lists and the artefact's own rows."""
    from autorate import drift_envelope

    row_fields = (drift_envelope.RECHECK_MODE2_RECIPE_FIELDS + drift_envelope.RECHECK_MODE2_FIELDS)
    labels = set()
    for claim in doc["reproduction"]["checks"]:
        for field in drift_envelope.RECHECK_CLAIM_FIELDS:
            labels.add("drift claim %s.%s" % (claim["id"], field))
    for row in doc["mode1"]:
        for field in drift_envelope.RECHECK_MODE1_FIELDS:
            labels.add("drift mode1 n=%s.%s" % (row["n"], field))
    for section in ("mode2", "mode2_controls"):
        for row in doc[section]:
            for field in row_fields:
                labels.add("drift %s %s.%s" % (section, row["name"], field))
    for field in drift_envelope.RECHECK_SWEEP_FIELDS:
        labels.add("drift mode2_sweep.%s" % field)
    return labels


#: One plant per comparison KIND the arm makes: (path into the stored artefact, the label that owns it,
#: a value the measurement cannot yield by accident). The first row or claim of each kind stands for the
#: kind; `_arm_expected_labels` above is what proves the other rows of the same kind are compared too.
def _arm_plants():
    from autorate import drift_envelope

    doc = artefact()
    plants = []
    for field in drift_envelope.RECHECK_MODE1_FIELDS:
        plants.append((("mode1", 0, field),
                       "drift mode1 n=%s.%s" % (doc["mode1"][0]["n"], field), 0.012345))
    for section in ("mode2", "mode2_controls"):
        recipe, figures = (drift_envelope.RECHECK_MODE2_RECIPE_FIELDS, drift_envelope.RECHECK_MODE2_FIELDS)
        for field in recipe + figures:
            value = (12345 if field == "rounds" else
                     "0" * 64 if field.endswith("digest_sha256") else 0.012345)
            plants.append(((section, 0, field),
                           "drift %s %s.%s" % (section, doc[section][0]["name"], field), value))
    for field in drift_envelope.RECHECK_SWEEP_FIELDS:
        plants.append((("mode2_sweep", field), "drift mode2_sweep.%s" % field,
                       12345 if field != "bound" else 0.012345))
    for field in drift_envelope.RECHECK_CLAIM_FIELDS:
        plants.append(((
            "reproduction", "checks", 0, field),
            "drift claim %s.%s" % (doc["reproduction"]["checks"][0]["id"], field),
            "planted-not-reproduced" if field == "agrees" else 0.012345))
    return plants


def test_the_arm_re_derives_every_published_quantity_the_producer_re_tests(monkeypatch):
    """Green only with the arm wired; red on arrival because `report.rederive_drift` did not exist.

    Three claims at once: the committed artefact reproduces under the arm with nothing failing; the arm's label
    set is EXACTLY the one built from the producer's own `RECHECK_*` lists and this artefact's own rows, so no
    published figure sits outside the gate and none is compared twice under one name; and the arm makes no
    rubric row, because the artefact publishes no freeze budget -- its alpha and seed belong to `drift.py`'s
    envelope, and a rubric line here would enforce a rule the freeze never made.
    """
    from autorate import drift_envelope
    from autorate.report import DRIFT_JSON

    doc = artefact()
    labels, drift, mismatches = _drive_arm(monkeypatch)
    assert drift == [], drift
    assert mismatches == [], sorted(labels)[:3]
    assert len(labels) == len(set(labels)), sorted(l for l in labels if labels.count(l) > 1)[:3]
    assert set(labels) == _arm_expected_labels(doc), sorted(set(labels) ^ _arm_expected_labels(doc))[:5]
    assert all(l.startswith("drift ") for l in labels), sorted(l for l in labels if not l.startswith("drift "))[:3]
    assert DRIFT_JSON == str(ARTEFACT_REL), (DRIFT_JSON, ARTEFACT_REL)
    for name in ("RECHECK_CLAIM_FIELDS", "RECHECK_MODE1_FIELDS", "RECHECK_MODE2_FIELDS",
                 "RECHECK_MODE2_RECIPE_FIELDS", "RECHECK_SWEEP_FIELDS"):
        assert getattr(drift_envelope, name), name


@pytest.mark.parametrize("plant_index", range(len(_arm_plants())))
def test_each_kind_of_comparison_the_arm_makes_can_fail_by_name(plant_index, monkeypatch):
    """The falsifier for the arm: perturb one stored quantity, and the ONLY named refusal is that field's.

    Written before the arm existed, so its RED is `AttributeError: module 'autorate.report' has no attribute
    'read_drift'`. Each plant is asserted as an exact one-element list rather than "something went red": a
    plant that reddened a neighbouring check while its own check passed would be the shape of an arm comparing
    the wrong thing, and that is precisely how a field list and a publication drift apart.
    """
    path, label, value = _arm_plants()[plant_index]

    def mutate(forged):
        target = forged
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return forged

    _labels, drift, _m = _drive_arm(monkeypatch, mutate)
    assert drift == [label], (path, drift)


def test_a_claim_the_arm_cannot_match_is_named_by_its_id_and_field(monkeypatch):
    """A dropped reproduction claim and a phantom one both refuse, in both directions.

    The producer's own guard answers this class with the sentence "claim X is not in the artefact"; the gate has
    to say the same thing in the form its reader acts on -- a `DRIFT:` line naming the claim and the field -- or
    an artefact that lost a claim would simply print a smaller denominator and stay green.
    """
    doc = artefact()
    dropped = doc["reproduction"]["checks"][3]["id"]
    phantom = "mode2 long-run rate: a sequence nobody publishes"

    def mutate(forged):
        assert [row["id"] for row in forged["reproduction"]["checks"]][3] == dropped
        del forged["reproduction"]["checks"][3]
        forged["reproduction"]["checks"].append({"id": phantom, "measured": 0.5, "agrees": True,
                                                 "envelope_states": 0.0, "tolerance": None,
                                                 "tolerance_basis": "planted"})
        return forged

    from autorate.drift_envelope import RECHECK_CLAIM_FIELDS
    expected = {"drift claim %s.%s" % (name, field)
                for name in (dropped, phantom)
                for field in RECHECK_CLAIM_FIELDS}
    _labels, drift, _m = _drive_arm(monkeypatch, mutate)
    assert set(drift) == expected, (sorted(set(drift) ^ expected)[:4], drift)
    assert len(drift) == len(expected), drift


def test_the_arm_and_the_producer_name_the_same_quantity_for_the_same_plant(monkeypatch):
    """The two surfaces agree at the same granularity, shown by putting one defect through both.

    `rederive_and_compare` is the producer's self-check and returns prose; `rederive_drift` is the gate's arm and
    returns labels. This is the only row that can show they cover the same ground: the same perturbed artefact
    goes through both, and the figure and field the producer names in its sentence have to be the figure and
    field the gate names in its label. A quantity added to one list and not the other reddens here.
    """
    import copy

    from autorate import drift_envelope

    doc = artefact()
    n = doc["mode1"][0]["n"]
    field = drift_envelope.RECHECK_MODE1_FIELDS[1]

    def move_row(forged):
        forged["mode1"][0][field] = 0.012345
        return forged

    producer_lines = drift_envelope.rederive_and_compare(move_row(copy.deepcopy(doc)), declared=True)
    _labels, row_drift, _m = _drive_arm(monkeypatch, move_row)
    assert row_drift == ["drift mode1 n=%s.%s" % (n, field)], row_drift
    assert len(producer_lines) == 1, producer_lines
    assert field in producer_lines[0] and str(n) in producer_lines[0], producer_lines

    claim_id = doc["reproduction"]["checks"][0]["id"]
    assert claim_id.startswith("mode1 "), claim_id

    def move_claim(forged):
        for row in forged["reproduction"]["checks"]:
            if row["id"] == claim_id:
                row["measured"] = 0.012345
        return forged

    producer_lines = drift_envelope.rederive_and_compare(move_claim(copy.deepcopy(doc)), declared=True)
    _labels, claim_drift, _m = _drive_arm(monkeypatch, move_claim)
    assert claim_drift == ["drift claim %s.measured" % claim_id], claim_drift
    assert len(producer_lines) == 1 and claim_id in producer_lines[0], producer_lines


def test_read_drift_refuses_an_artefact_that_is_not_a_drift_envelope_by_naming_the_key(tmp_path):
    """`report.read_drift` is the gate's shape guard, with one owner for the required-key list.

    The list is the producer's own `REQUIRED_KEYS`, so the gate cannot accept an artefact the producer refuses
    or refuse one the producer accepts, and a missing key answers with the key's name rather than a `KeyError`
    that reads as the gate failing. Every forgery is written to a copy under `tmp_path`: the committed bytes are
    never the subject of a test write, and a missing FILE is not this loader's refusal to make --
    `load_published` answers the filesystem through `require_published` first, which is why the last two
    assertions below expect the two different classes they do.
    """
    import copy

    from autorate import drift_envelope, report
    from autorate.report import read_drift

    committed = artefact()
    good = tmp_path / "artefact.json"
    good.write_text(json.dumps(committed, indent=2, sort_keys=True) + "\n")
    assert read_drift(good) == committed
    assert sorted(drift_envelope.REQUIRED_KEYS) == sorted(committed), (
        "the guard's key list and the published artefact's own keys have diverged")

    for key in drift_envelope.REQUIRED_KEYS:
        broken = copy.deepcopy(committed)
        del broken[key]
        path = tmp_path / ("missing-%s.json" % key)
        path.write_text(json.dumps(broken, indent=2, sort_keys=True) + "\n")
        with pytest.raises(ValueError) as caught:
            read_drift(path)
        assert key in str(caught.value), (key, str(caught.value))

    for name, payload in (("list.json", "[1, 2]\n"), ("string.json", '"not an artefact"\n'),
                          ("empty.json", "{}\n")):
        path = tmp_path / name
        path.write_text(payload)
        with pytest.raises(ValueError):
            read_drift(path)
    # An absent file is the CALLER's refusal, not the loader's: `load_published` never hands `read_drift` a
    # path it has not already opened, and the gate's arm for it is `PublishedArtefactUnavailable` at exit 4.
    with pytest.raises(OSError):
        read_drift(tmp_path / "never-written.json")
    assert report.DRIFT_PRODUCER == committed["producer"] == drift_envelope.PRODUCER, report.DRIFT_PRODUCER
    assert str(report.DRIFT_MD) == committed["document_path"] == drift_envelope.DOC_REL
    assert str(report.DRIFT_JSON) == committed["artefact_path"]


def test_an_artefact_naming_a_scale_the_producer_refuses_refuses_as_the_table_not_as_usage(monkeypatch):
    """A stored `trials_per_size` the module forbids is exit 4 with the path named, never rc 1 and never 2.

    `build_artefact` refuses a scale above the one the envelope states with `DriftEnvelopeUsage`, which is a
    `ValueError` -- and the CLI maps `ValueError` onto usage (2), whose only readable content is "an input this
    command was handed is wrong". Nobody handed this path: the publication table declared it. So the arm
    translates it into `PublishedArtefactUnavailable`, the class that owns "the committed state cannot
    reproduce what it publishes", and the sentence says which path and which field. The same arm also has to
    survive a top-level-valid artefact whose provenance lost the one subkey it reads -- the BLOCKER-1 defect
    class, re-planted against the gate instead of the producer.
    """
    from autorate import report

    def scale(forged):
        forged["provenance"]["trials_per_size"] = 999999
        return forged

    with pytest.raises(report.PublishedArtefactUnavailable) as caught:
        _drive_arm(monkeypatch, scale)
    message = str(caught.value)
    assert "data/drift_envelope.json" in message, message
    assert "not a usage error" in message, message
    assert "999999" in message, message

    def no_trials(forged):
        del forged["provenance"]["trials_per_size"]
        return forged

    with pytest.raises(report.PublishedArtefactUnavailable) as caught:
        _drive_arm(monkeypatch, no_trials)
    assert "trials_per_size" in str(caught.value), str(caught.value)
    # and the committed bytes still pass the same arm afterwards (the hook is undone by `monkeypatch`)
    _labels, drift, _m = _drive_arm(monkeypatch)
    assert drift == [], drift


def test_the_drift_document_is_a_published_row_ordered_before_the_report():
    """`docs/DRIFT.md` joins `cli.PUBLISHED_DOCS`, ahead of `REPORT_MD`, and renders from the artefact.

    Order is the substance of this row, not formatting: the table's own comment states that the order decides
    which rc-4 refusal a reader is told about, and `REPORT_MD` is last on purpose. So the drift document has to
    be in the table, before the report, and its render has to be the committed bytes -- which is what turns a
    stale `docs/DRIFT.md` into a named refusal in the gate rather than a sentence nobody re-reads.
    """
    from autorate import drift_envelope
    from autorate.cli import PUBLISHED_DOCS
    from autorate.report import DRIFT_MD, render_drift

    paths = [str(path) for path, _render in PUBLISHED_DOCS]
    assert str(DRIFT_MD) in paths, paths
    assert paths.index(str(DRIFT_MD)) < paths.index("docs/REPORT.md"), paths
    doc = read_json(REPO / ARTEFACT_REL)
    assert render_drift(doc) == (REPO / DOC_REL).read_text()
    assert drift_envelope.render_document(doc) == render_drift(doc), (
        "`report.render_drift` is not a pass-through to the producer's renderer, so the gate and the tool would "
        "disagree about what this document is")
    stale = json.loads(json.dumps(doc))
    stale["mode1"][0]["realised_miscoverage"] = 0.012345
    assert render_drift(stale) != (REPO / DOC_REL).read_text(), (
        "the renderer ignores that figure, so the byte comparison it feeds cannot fail")


def test_a_source_defect_in_the_envelope_lands_at_four_through_the_gate(tmp_path, monkeypatch, capsys):
    """The gate re-measures the artefact, so a defect in the source it measures must reach the gate at 4.

    `report.rederive_drift` calls `drift_envelope.build_artefact`, which reads `autorate.drift` again; the arm
    caught only the usage class, so `DriftEnvelopeState` -- a plain `RuntimeError`, and `cli.main` maps no
    `RuntimeError` -- walked out of `verify` as exit 1. The tool path already refuses the identical defect at 4
    (`test_a_source_constant_that_has_vanished_refuses_by_name_on_both_axes`), which is what made the gate's hole
    invisible: the class rule 1 forbids had one covered caller and one uncovered one.

    Plant: delete `WEIGHTED_ENVELOPE` from the declared module and drive `autorate verify`.
    """
    from autorate import cli, drift

    monkeypatch.delattr(drift, "WEIGHTED_ENVELOPE")
    monkeypatch.setenv("AUTORATE_FEISHU_ROOT", str(tmp_path / "no_corpus_here"))
    monkeypatch.chdir(REPO)
    rc = cli.main(["verify", "--protocol", "protocol.json"])
    captured = capsys.readouterr()
    assert rc == 4, (rc, (captured.err or captured.out)[-600:])
    assert "WEIGHTED_ENVELOPE" in (captured.err + captured.out), (captured.err + captured.out)[-600:]
    assert "Traceback" not in captured.err, captured.err[-600:]


def test_every_figure_the_drift_document_prints_is_compared_by_the_gate(tmp_path, monkeypatch):
    """#117: `verify` claims every published number re-derives, so the claim is measured leaf by leaf.

    How it measures rather than asserts: mutate ONE leaf of the committed artefact, re-render `docs/DRIFT.md`
    through the producer's own renderer, and ask whether the document's bytes moved. A leaf that moves the
    document is a published figure, and every published figure has to be compared against the re-measured
    artefact -- so the set of such leaves must be a subset of the fields the arm actually compares. That set is
    taken from `rederive_drift`'s own labels rather than from a list typed into this row, because a literal here
    would be a second owner of the coverage claim and would go stale exactly the way `owned["G5"]` did.

    Leaves that do NOT move the document are provenance, digests and the envelope's own wording: they are the
    producer's inputs and the module's text, and the document publishes no number read from them, so the gate
    owes them no comparison -- stated rather than left to a reader's guess.
    """
    import copy
    import json as _json

    from autorate import report

    doc = _json.loads((REPO / ARTEFACT_REL).read_text())
    base = report.render_drift(copy.deepcopy(doc))

    compared = set()
    report.rederive_drift(lambda label, actual, wanted: compared.add(label),
                          lambda label, actual, wanted: compared.add(label))

    def walk(o, path=()):
        if isinstance(o, dict):
            for key, value in o.items():
                yield from walk(value, path + (key,))
        elif isinstance(o, list):
            for index, value in enumerate(o):
                yield from walk(value, path + (index,))
        else:
            yield path, o

    published, skipped, wording, declared_excluded = [], [], 0, []
    for path, value in walk(doc):
        # A string leaf that reaches the document is WORDING, and wording has its own owners: the envelope-copy
        # check refuses a document whose sentences no longer match the module, and `PUBLISHED_DOCS` byte-compares
        # the rendered file. A number or a decision printed in the document is the class with no such owner: if
        # no arm compares it against the re-measured artefact, nothing checks that it is still the measurement.
        if isinstance(value, str):
            wording += 1
            continue
        probe = copy.deepcopy(doc)
        cursor = probe
        for step in path[:-1]:
            cursor = cursor[step]
        leaf = path[-1]
        if isinstance(value, bool):
            cursor[leaf] = not value
        elif isinstance(value, (int, float)):
            cursor[leaf] = value + 1
        else:
            continue
        try:
            moved = report.render_drift(probe) != base
        except Exception:
            # A renderer that refuses on the mutated value is itself a reaction to that field, so it counts as
            # published rather than being skipped -- silence here would hide the class this row hunts.
            moved = True
        if not moved:
            skipped.append("/".join(str(step) for step in path))
            continue
        # `provenance` is the measurement's own declared inputs -- the scale, the seeds, the sizes and the
        # constants the module states. No re-measurement can settle those from outside: the arm READS
        # `trials_per_size` and measures at it, so mutating it moves the measurement instead of contradicting
        # it. They are policed where policing exists -- against `autorate.drift`'s constants by
        # `read_module_provenance`, and against the module's wording by the envelope-copy check -- and the
        # exclusion below is asserted to be exactly that subtree, so no other figure can join it quietly.
        if path[0] == "provenance":
            declared_excluded.append("/".join(str(step) for step in path))
            continue
        fields = {str(step) for step in path if isinstance(step, str)}
        if not any(field in lab for lab in compared for field in fields):
            published.append("/".join(str(step) for step in path))
    assert not published, (
        "%d figure(s) the drift document prints are compared by no arm of `verify`: %s -- widen the producer's "
        "RECHECK_* lists (the tool path reads the same lists, so --check widens with the gate)"
        % (len(published), published[:12]))
    assert declared_excluded and all(p.startswith("provenance/") for p in declared_excluded), (
        "the excluded set left the provenance subtree, so figures are outside the guard's reach: %s"
        % [p for p in declared_excluded if not p.startswith("provenance/")][:6])
    assert wording, "no string leaf at all, so the wording/figure split this row draws has no subject"
    assert len(skipped) > 0, (
        "nothing was skipped, so the comparison set may as well be the whole artefact -- this row would then"
        " pass on an artefact whose every field is published")
