"""G2 measured: the gate the reference README instructs, against the error rate it implies.

Spec §2 row G2 asks for one comparison and one number: at `confidence >= 0.85`, the measured
error among automated decisions versus "the 15% that sentence implies", and "the multiple by
which it misses". This module produces that, and nothing in it is typed: every published figure
is emitted here from the committed records, `autorate audit` renders it to `docs/AUDIT.md`, and
`tests/test_audit.py` holds those committed bytes against this renderer, so a G2 figure edited by
hand has to get past a gate that reads the file in git rather than a fresh render compared to
another fresh render. `autorate verify` does NOT re-derive this artefact yet: the two byte-compared
files it owns are `docs/RESULTS.md` and `data/inventory.md`, and the audit arm is the second gate,
still owed. Until it lands, "published and re-derivable" for G2 means this suite, this revision.

Spec §7.3 asks for something more than the one number, and the artefact prints it too: the
risk-coverage frontier, one block per field per backend, swept over `DEFAULT_GRID` plus whatever
gate the run was asked about. Every cell of those blocks is `frontier`'s own output and `frontier`
gets its bounds from `_bound`, which is this module's only call of
`tails.clopper_pearson_upper`; the renderer reads `row["curve"]` and computes nothing, and
`check_audit` re-derives each point from the counts beside it (see the curve arm there). The point
that the §2 row is about -- `lambda == gate` -- is the headline row recomputed by the same producer,
so a frontier and a table that disagree is drift, not a drafting slip.

Three things about the corpus decide the shape of the output (all measured against
`data/records_feishu.jsonl`, not read off a plan):

1. **Most of the archive cannot be audited at all.** 1,536 of the 1,919 rows are `qtype=noul`
   and carry `gold is None`. Scoring an automated noul decision as wrong-by-inequality
   (`predicted != gold`, with `gold` None) marks 100% of them wrong: row level that is
   1139/1139 = **1.0000**, which is 6.67x the implied error and looks like the strongest finding
   in the project while being an artifact of grading unlabelled answers. So the audit restricts
   itself to records it can actually compare, and publishes the excluded count and the reason in
   its own output -- an invisible filter would leave the next reader unable to tell "the corpus
   is small" from "the corpus was quietly halved". `case_count.count_outcome` refuses such a row
   outright (it raises rather than guessing), which is the reason the filter is a precondition
   here rather than a courtesy.
2. **The denominator is a decision, and the same convention is not the same number twice.** The
   certification unit is the case, so `automated_cases`/`erroneous_cases` come from
   `count_outcome` -- whose rule is that a case automates only when EVERY record in it automates
   (running a case unattended means running all of it). The row figure is printed beside it: for
   `jev` at `max(p) >= 0.85` they diverge hard (180 automated rows, 59 automated cases), while
   for `laya` row and case rates coincide at 0.5556 because each case's three repeats carry the
   same probability vector. Coincidence is not identity, so the collapse conventions that a
   reader might have assumed (the case's highest-field row, its first row, its lowest `repeat`)
   are MEASURED here by handing `count_outcome` one row per case, not quoted from `scales.py`,
   whose figures were computed over an all-qtype population.
3. **A point estimate on nine cases is not a certificate.** Five wrong out of nine bounds at
   0.8312 one-sided, and the README's gate on `laya`'s published `confidence` bounds at 0.9747
   on two automated cases: the corpus cannot bound the gate it is being asked to certify. The
   interval is therefore published BESIDE the point estimate, and `multiple` is never printed
   alone. Both ends come from `tails.clopper_pearson_upper`, which owns that arithmetic; the
   two-sided upper endpoint is the same owner called at `delta / 2` (the standard CP inversion),
   never a reimplemented bisection. Both are ceiled onto the 12-decimal grid
   `certificate.canonicalise_bound` owns before this module publishes them (ledger R-121): that
   call is a transcendental, its last bits differ between Apple libm and glibc, and the bound is
   the figure `informative` -- and so rc 0 versus rc 3 -- is decided against, so a bound only one
   C library can write would let the same records buy a different exit code on a different
   machine. Every other figure here is a quotient, sum or difference over values the records
   already carry, and IEEE 754 requires + - * / to be correctly rounded, so those agree bit for
   bit everywhere and are left exactly as computed. No numeric figure from the plan's prose is quoted here: R-72
   corrected the sketch's "at n=2 the bound is ~0.92" to this module's 0.9747, and 0.923 is
   reproducible from `tails` at neither `delta` nor `delta / 2` -- `binom_cdf(1, 2, 0.923)` is
   0.148, so a bound there would be a number this tool never computes.

Upstream defines the name `confidence` twice -- `laya/common.py:273` (`answer_confidence(p, k) =
max(p)`, its docstring calling it the quantity every calibration figure in that repository is
computed on) and `laya/common.py:289` (`confidence_from_probs(p, k) = 1 - H(p)/log k`, its docstring
calling that one not calibrated) -- and the gate this artefact is about reads the response key
`confidence`, which `laya/agent.py:684` fills from the second. So the row that answers the README's
own sentence verbatim is `confidence`, and the `answer_confidence` row is the same instruction read
as `p_max = max(probs)`: a different quantity, and this artefact publishes both, named as themselves,
because choosing one without saying which is the slip the two definitions make possible (open
obligation #31 in the ledger; the artefact itself cites upstream, not the ledger). Every row names
the definition it used, the record key or formula it read, and -- for the key that is a name rather
than a quantity -- the verdict `scales.scale_attribution` reaches for the slice that number came
from. Attribution is per `(backend, qtype)` slice because that module refuses a batch spanning
slices, and a row over more than one slice says so instead of averaging verdicts.

Exit-code arms this module serves (the mapping itself lives in `cli.main`): an unusable
population or an unusable gate is `ValueError` -> rc 2 (nothing to audit is the operator's
mistake, and a row automating nothing is NOT -- that is a result); a corpus that bounds nothing
is rc 3, the refusal §5.5 makes a product; and an audit whose own arithmetic contradicts itself
is `AuditDriftError`, an `ArithmeticError`, -> rc 4.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from .case_count import Verdict, case_key, count_outcome
from .certificate import canonicalise_bound
from .records import max_confidence
from .scales import scale_attribution
from .tails import clopper_pearson_upper

# The gate and level G2 names, and the level every other bound in this repository is published at.
DEFAULT_GATE = 0.85
DEFAULT_DELTA = 0.05

# The grid `frontier` sweeps and the artefact prints, in the one place both read it: a second
# literal would let the curve and the sentence describing it disagree about which grid ran.
DEFAULT_GRID = (0.0, 0.3, 0.6, 0.85, 0.99)

# The exclusion reasons are published buckets, so they are named here once. A record is auditable
# only when BOTH halves of the comparison exist: `gold` to compare against and `predicted` as the
# answer the automated decision would submit. `count_outcome` raises on either being absent under
# an `auto` verdict, which would reach the operator as rc 2 for what is really a shape of the data.
NO_GOLD = "gold is None: an unlabelled answer has nothing to compare with, so wrong-by-inequality is an artifact"
NO_ANSWER = "predicted is None: the record states no answer, so an automated decision would submit nothing"

CASE_RULE = "count_outcome: a case automates only when every one of its records automates"
# The collapses a reader might have assumed instead. Each is a RECORD SELECTION -- one row per
# case -- so `count_outcome` still owns the counting; only which row stands for the case changes.
COLLAPSES = ("max_field_row", "first_row", "lowest_repeat")


class AuditDriftError(ArithmeticError):
    """The audit contradicts itself.

    It is an `ArithmeticError` because `cli.main` already maps that family to `EXIT_DRIFT`, for
    exactly this reason: `tails` refusing to publish a bound beaten by its own data and the reader
    refusing to return when the line accounting does not conserve are both "our arithmetic did not
    reproduce", not "your inputs are wrong". A data defect must never reach rc 1, and a defect of
    ours must never be billed to the operator as rc 2.
    """


def _field_confidence(record) -> Optional[float]:
    return (record.scores or {}).get("reported_confidence")


def _field_answer_confidence(record) -> Optional[float]:
    # `records.max_confidence` is the owner of this quantity; a local `max(r.probs)` would be a
    # second definition of the number the README's gating sentence is about.
    return max_confidence(record.probs) if record.probs else None


def _field_act_probability(record) -> Optional[float]:
    return (record.scores or {}).get("act_probability")


# The three fields the reference README offers a caller to gate on, in the order the audit prints
# them. Each entry names how the value is obtained, because "confidence" is not one of the
# archive's record keys and `scores["reported_confidence"]` is not one quantity across slices.
FIELDS: dict = {
    "confidence": {
        "get": _field_confidence,
        "source": "record key scores['reported_confidence']",
        # Upstream publishes this number and #31 records that its definition is contested, so the
        # row carries the owner's attribution verdict instead of a definition this tool asserts.
        "definition": "the confidence value upstream itself published for the record's slice",
        "attributable": True,
    },
    "answer_confidence": {
        "get": _field_answer_confidence,
        "source": "records.max_confidence(record.probs)",
        "definition": "mass on the reported answer, p_max = max(probs)",
        "attributable": False,
    },
    "act_probability": {
        "get": _field_act_probability,
        "source": "record key scores['act_probability']",
        # Carried, not attributed: it is upstream's own act/branch decision probability, not a
        # confidence scale, and it is on this list because the README offers it as a gate.
        "definition": "upstream's carried act probability (not a confidence scale; not attributed)",
        "attributable": False,
    },
}
FIELD_ORDER = ("confidence", "answer_confidence", "act_probability")

# Where upstream defines the two things its own name `confidence` stands for, cited by location and
# not by a private task id: a published artefact is read by people who do not have the ledger, and
# which of the two a README sentence means is a fact about upstream's code that any reader can open.
UPSTREAM_ANSWER_CONFIDENCE = "laya/common.py:273 (`answer_confidence(p, k) = max(p)`)"
UPSTREAM_ENTROPY_CONFIDENCE = ("laya/common.py:289 "
                               "(`confidence_from_probs(p, k) = 1 - H(p)/log k`)")
UPSTREAM_GATE_SENTENCE = ("laya/README.md:567-581, `Automated Confidence Gating`: "
                          "`conf = answers[...][\"confidence\"]` then `if conf >= 0.85: "
                          "route_automatically(dept)`")
UPSTREAM_ANSWER_BUILDER = ("laya/agent.py:684, where the response's `confidence` key is set to "
                           "`round(confidence_from_probs(p, k), 4)` and `answer_confidence` is set "
                           "beside it")
# This repository's own carrying step, so the chain from upstream's key to the audited column is
# openable at both ends rather than asserted here. The table's `read as` column names the same key
# in the reader's own words.
LOCAL_RECORD_KEY = ("`readers/feishu_zh.py`, which stores the archive's `confidence` under the "
                    "record key `scores[\"reported_confidence\"]`")


def _checked_fields(fields: Sequence) -> tuple:
    """Every field name handed over must be one this module knows, at every entry point.

    The inherited code refused an unknown name in `audit_fields` with a `ValueError` (rc 2) but
    indexed `FIELDS[field]` directly in `frontier` and `table[FIELD_ORDER[0]]` in `render_audit`,
    which raise `KeyError`. `KeyError` is a `LookupError`, not one of the types `main` catches, so
    an undeclared key left the command as rc 1 with a traceback -- outside the documented
    0/2/3/4 contract. R-115's precedent rules that at the raising site rather than by widening
    `main`'s catch, so all three entry points now ask the same question here.
    """
    names = tuple(fields)
    unknown = sorted({f for f in names if f not in FIELDS})
    if unknown:
        raise ValueError("the audit knows no field %r; it measures %s"
                         % (", ".join(unknown), ", ".join(FIELD_ORDER)))
    return names


def _verdict_for(get: Callable, gate: float) -> Callable:
    """The threshold rule G2 names, expressed as the verdict contract `count_outcome` requires.

    `decide` is not a bool: an `auto` verdict must name the label it submits (R-66), so the record's
    own `predicted` is what an automated decision would BE, and the field value travels as
    `measure` so `mean_measure` means what its name says. A record carrying no value for the field
    is a refusal, not a zero: inventing `0.0` would silently automate nothing while reporting a
    measured mean over values that never existed.
    """

    def decide(record) -> Verdict:
        value = get(record)
        if value is None:
            return Verdict("refuse", None, None)
        if value >= gate:
            return Verdict("auto", record.predicted, value)
        return Verdict("refuse", None, value)

    return decide


def _partition(records: Sequence) -> tuple:
    """Split the handed-over rows into auditable and excluded, naming every exclusion reason.

    Returns `(audited, excluded_counts, excluded_rows)`. The counts are a published figure: an
    exclusion that is not counted is the quiet filter this module exists to avoid.
    """
    audited: list = []
    counts: dict = {}
    dropped: list = []
    for r in records:
        if r.gold is None:
            counts[NO_GOLD] = counts.get(NO_GOLD, 0) + 1
            dropped.append(r)
        elif r.predicted is None:
            counts[NO_ANSWER] = counts.get(NO_ANSWER, 0) + 1
            dropped.append(r)
        else:
            audited.append(r)
    return audited, counts, dropped


def _slice_attribution(records: Sequence) -> tuple:
    """Attribute each `(backend, qtype)` slice once, and name them.

    `scale_attribution` takes one slice and raises on a batch spanning two, because the same key
    name carries a different field per qtype. So each slice is asked separately and the row names
    every slice it aggregated over -- a row spanning two slices reports both verdicts rather than
    averaging them into a word neither slice said.
    """
    keys = sorted({(r.backend, r.qtype) for r in records})
    verdicts = {}
    for backend, qtype in keys:
        slice_records = [r for r in records if r.backend == backend and r.qtype == qtype]
        attribution = scale_attribution(slice_records)
        verdicts["%s/%s" % (backend, qtype)] = {
            "verdict": attribution["verdict"],
            "n_rows_measured": attribution["n"],
            "n_rows_handed_over": attribution["n_rows"],
            # The mixture beside the aggregate word: `jev: neither` is false for 97 of jev's 191
            # attributable rows, so a published row that printed only the verdict would be an
            # over-claim of exactly the kind docs/ERRATA.md exists to correct.
            "row_mixture": {k: attribution[k]
                            for k in ("both", "answer_only", "entropy_only", "neither")},
            "max_dev_answer": attribution["max_dev_answer"],
            "max_dev_entropy": attribution["max_dev_entropy"],
        }
    names = ["%s (%s)" % (key, verdicts[key]["verdict"]) for key in sorted(verdicts)]
    if len(verdicts) == 1:
        scale = next(iter(verdicts.values()))["verdict"]
    else:
        scale = "not attributable across slices: " + ", ".join(names)
    return scale, verdicts


def _collapse_selection(records: Sequence, mode: str, get: Callable) -> list:
    """One row per case under the named convention, for `count_outcome` to count.

    `max_field_row` picks the case's row carrying the highest value OF THE FIELD BEING GATED, not
    the highest `p_max`: the invariant `check_audit` asserts (a collapsed population can only
    automate at least as many cases as the all-rows rule) holds for the field the gate reads and
    would be coincidence for a different one.
    """
    groups: dict = {}
    for index, r in enumerate(records):
        groups.setdefault(case_key(r), []).append((index, r))
    picked = []
    for key in sorted(groups):
        items = groups[key]
        if mode == "max_field_row":
            chosen = max(items, key=lambda ir: (get(ir[1]) if get(ir[1]) is not None else -1.0,
                                                -ir[0]))
        elif mode == "first_row":
            chosen = items[0]
        elif mode == "lowest_repeat":
            chosen = min(items, key=lambda ir: (ir[1].repeat, ir[0]))
        else:
            raise AuditDriftError("unknown collapse convention %r" % (mode,))
        picked.append(chosen[1])
    return picked


def _rate(numerator: Optional[int], denominator: Optional[int]) -> Optional[float]:
    if not denominator:
        return None
    return numerator / denominator


def _bound(k: Optional[int], n: Optional[int], delta: float, two_sided: bool = False):
    """The exact upper endpoint, from `tails` and nowhere else, at the published precision.

    `two_sided` is the standard Clopper-Pearson inversion of the upper endpoint of a two-sided
    `1 - delta` interval: the same owner called at `delta / 2`. It is not a second implementation
    and it is not the plan's 0.923.

    This is the one site in the module that turns a transcendental into a published number -- the
    CP columns of every row, the same two on the curve, and the `informative` flag that chooses rc
    0 over rc 3 are all downstream of it -- so it is the one site that carries R-121's canonical
    ceiling. `clopper_pearson_upper` inverts a binomial tail through `math.log`/`math.exp`, whose
    last bits are not identical between Apple libm and glibc; a full-precision double taken from
    one of them is not a number the other re-derives. Ceilling onto `certificate`'s 12-decimal
    grid here means every bound this module publishes, and every comparison made against one, is
    the same double on any C library. It is idempotent, so the stored and re-derived value agree,
    and monotone, so `bound_two_sided >= bound` and `bound >= measured_error` both survive the
    trip. Nothing else here is rounded: `measured_error`, `multiple`, `coverage`, `mean_value` and
    `implied_error` are quotients, sums and differences of integers, and IEEE 754 requires those to
    be correctly rounded, so they already agree bit for bit everywhere.
    """
    if not n:
        return None
    return canonicalise_bound(clopper_pearson_upper(k or 0, n, delta / 2 if two_sided else delta))


def audit_fields(records: Sequence, gate: float = DEFAULT_GATE,
                 delta: float = DEFAULT_DELTA, fields: Sequence = FIELD_ORDER,
                 grid: Sequence = DEFAULT_GRID) -> dict:
    """Measure every offered field as a gate on the records it can be measured against.

    One population in, one row per field out. The population must be ONE backend: `case_key` is
    upstream's `request_sha256`, and the archived harness sent the same requests to both backends,
    so the 1,919 rows of the committed file hold only 128 distinct case keys across BOTH backends.
    Pooling backends would therefore divide by a denominator that is half the one that exists --
    the case is the unit a bound may divide by, and getting it wrong here is the error R-44 exists
    to police, so it is refused rather than corrected silently.
    """
    if not 0.0 < gate < 1.0:
        raise ValueError("gate must be a probability in (0,1); got %r. implied_error = 1 - gate "
                         "is the number the comparison is against, so a gate of 1 implies an "
                         "error rate of 0 and a multiple of infinity" % (gate,))
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1); got %r" % (delta,))
    handed = list(records)
    if not handed:
        raise ValueError("no records handed to the audit: there is nothing to measure")
    names = sorted({r.backend for r in handed})
    if len(names) > 1:
        raise ValueError("audit_fields takes one backend; the population mixed %r. The archive "
                         "pairs the same requests across backends, so case keys are shared and a "
                         "pooled count would merge two backends' observations into one case."
                         % (names,))
    fields = _checked_fields(fields)

    audited, excluded, excluded_rows = _partition(handed)
    if not audited:
        raise ValueError(
            "nothing to audit: all %d rows handed over were excluded (%s). An audit over a "
            "population with no label-comparable record returns a rate by invention, so it is a "
            "usage error, not a result" % (len(handed), "; ".join(sorted(excluded))))
    scale, slices = _slice_attribution(audited)
    n_excluded = sum(excluded.values())
    implied_error = 1.0 - gate
    # The grid the artefact sweeps, with the gate this run published added to it. `--gate 0.5` is an
    # operator's question and the frontier owes it a point: on a grid that does not name the gate the
    # printed curve would not contain the row the table above it is about, and a reader would get a
    # frontier and a headline that cannot be compared. The default grid already carries 0.85, so this
    # union changes nothing about the published artefact's points; it only guarantees the property.
    sweep = tuple(sorted(set(grid) | {gate}))

    rows: dict = {}
    for name in fields:
        spec = FIELDS[name]
        get = spec["get"]
        counts = count_outcome(audited, _verdict_for(get, gate))
        automated_cases = counts["automated_cases"]
        erroneous_cases = counts["erroneous_cases"]
        measured_error = _rate(erroneous_cases, automated_cases)
        # `count_outcome.mean_measure` averages the records whose verdict CARRIED a measure, so the
        # denominator of that mean is the rows carrying the field -- not the automated ones, and not
        # the rows the backend never published it for. Naming the carrying count is what keeps the
        # mean from being read as an automation figure.
        carrying = [r for r in audited if get(r) is not None]
        missing = len(audited) - len(carrying)
        # The row denominator printed beside the case denominator, never blended into it: rows of
        # one case are not independent observations, so a bound may only be computed on the cases.
        bound = _bound(erroneous_cases, automated_cases, delta)
        bound_two_sided = _bound(erroneous_cases, automated_cases, delta, two_sided=True)
        rows[name] = {
            "gate": gate,
            "delta": delta,
            "n_rows_handed_over": len(handed),
            "n_records": len(audited),
            "n_cases": counts["n_cases"],
            "excluded_unlabelled": sum(1 for r in excluded_rows if r.gold is None),
            "excluded_no_answer": sum(1 for r in excluded_rows if r.gold is not None
                                      and r.predicted is None),
            "excluded_reasons": dict(excluded),
            "n_records_carrying_field": len(carrying),
            "n_records_missing_field": missing,
            "automated_cases": automated_cases,
            "erroneous_cases": erroneous_cases,
            "refused_cases": counts["refused_cases"],
            "automated_rows": counts["automated"],
            "erroneous_rows": counts["errors"],
            "mean_value": counts["mean_measure"] if carrying else None,
            "measured_error": measured_error,
            "measured_error_rows": _rate(counts["errors"], counts["automated"]),
            "implied_error": implied_error,
            "multiple": None if measured_error is None else measured_error / implied_error,
            "multiple_rows": (None if _rate(counts["errors"], counts["automated"]) is None
                              else _rate(counts["errors"], counts["automated"]) / implied_error),
            "bound": bound,
            "bound_two_sided": bound_two_sided,
            "informative": None if bound is None else bool(bound <= implied_error),
            "backend": names[0],
            "slices": sorted(slices),
            "attribution": slices,
            "attributed_scale": scale if spec["attributable"] else
                                 "definitional, not attributed: this tool computes it from probs",
            "definition": spec["definition"],
            "source": spec["source"],
            "case_rule": CASE_RULE,
            # Measured, not quoted: the same population collapsed three other ways, each one row
            # per case, counted by the same owner. Where these differ from `automated_cases` the
            # convention is doing the work, and the reader gets to see it.
            "automated_cases_by_collapse": {
                mode: count_outcome(_collapse_selection(audited, mode, get),
                                    _verdict_for(get, gate))["automated_cases"]
                for mode in COLLAPSES},
        }
        # §7.3's curve beside the single point, from the one producer of it (`frontier`), so the
        # artefact never offers one gate as if it were the whole risk-coverage trade-off. `delta`
        # travels with the sweep because the artefact prints the bounds: a curve computed at 0.05
        # under a header that says 0.10 would be two rubrics in one artefact, which is the thing
        # `check_audit` refuses at the table level and refuses here at the curve level.
        rows[name]["curve"] = [
            {"lambda": point["lambda"], "delta": point["delta"],
             "implied_error": point["implied_error"], "n_cases": point["n_cases"],
             "automated_cases": point["automated_cases"],
             "erroneous_cases": point["erroneous_cases"], "coverage": point["coverage"],
             "measured_error": point["measured_error"], "bound": point["bound"]}
            for point in frontier(audited, (name,), sweep, delta)]
        if rows[name]["informative"] is False:
            # Spec §7.3: the tool never returns a number for a field that cannot support one. Here
            # the honest rendering is the point estimate WITH the refusal to bound it, so the note
            # travels in the data rather than being added by whoever writes the prose.
            rows[name]["note"] = (
                "NOT_INFORMATIVE: the exact one-sided upper bound %s on %d automated case%s "
                "is above the %.2f error rate the gate's own sentence implies, so this corpus "
                "cannot bound the gate it is being asked to certify" % (
                    "%.4f" % bound if bound is not None else "n/a",
                    automated_cases, "" if automated_cases == 1 else "s", implied_error))
        elif not automated_cases and not carrying:
            # The other empty arm, told apart from the first on purpose: `jev` publishes no
            # `act_probability` at all, so `>= 0.85` cannot automate anything because there is no
            # number to compare. Reading that as "this gate automates nothing" would credit jev
            # with a measured refusal rate on a field the backend never sent.
            rows[name]["note"] = (
                "NOT_APPLICABLE: this backend carries no value for %s on any of the %d audited "
                "rows, so the gate has nothing to read and no error rate exists to report" % (
                    spec["source"], len(audited)))
        elif not automated_cases:
            # Two shapes empty the case denominator, and the inherited code printed the same
            # sentence for both: "every one of the audited rows carries a value below the gate".
            # That is false for the second one, where ROWS do clear the gate and only the case rule
            # (`count_outcome`: a case automates when EVERY one of its records does) declines to
            # carry any of them forward. Measured, and stated at its true reach: on the committed
            # archive this arm never fires, because at every threshold some case clears in full
            # (a sweep of every midpoint between the values jev publishes found no aggregate of this
            # shape), though the per-case spread that creates it is there -- 25 jev cases carry more
            # than one `max(p)` and 28 carry more than one published `confidence`. Two rows of one
            # case, which is the shape the archive does not supply and the test does, produce it;
            # `tests/test_audit.py` names that fixture. A published artefact that describes the data
            # as something it is not is the failure this repository spends its ERRATA rows on, so the
            # two arms are told apart even while only the second one occurs here.
            if counts["automated"]:
                rows[name]["note"] = (
                    "ROWS_NOT_CASES: %d of the %d audited rows clear the gate, but no case has "
                    "EVERY one of its rows clearing it, so under the published case rule nothing "
                    "runs unattended and no case-level error rate exists to report; the row figure "
                    "above is the part of this that did automate" % (
                        counts["automated"], len(audited)))
            else:
                rows[name]["note"] = (
                    "NOTHING_AUTOMATED: every one of the %d audited rows carries a value below the "
                    "gate, so the rule runs nothing unattended here and there is no error rate to "
                    "report; that is a measured result, not a missing one" % len(audited))
    check_audit({"_": rows})
    return rows


def frontier(records: Sequence, fields: Sequence = FIELD_ORDER,
             grid: Sequence = DEFAULT_GRID, delta: float = DEFAULT_DELTA) -> list:
    """Risk-coverage as data: one row per `(field, lambda)`, spec §7.3's curve without the prose.

    A single point at one gate is the shape of claim this project exists to refuse, so the curve is
    emitted instead -- and `render_audit` prints it, which is what makes that sentence a description
    rather than a promise. Each `lambda` re-runs the whole comparison at that threshold;
    `count_outcome` does the counting for all of them and `_bound` (that is,
    `tails.clopper_pearson_upper`) is the only producer of the bound, at the `delta` the CALLER
    passed. `delta` is a parameter and never a default read inside the body, because a curve bounded
    at 0.05 under a header that says 0.10 is two rubrics in one artefact, and `check_audit` refuses
    two rubrics.

    The point at the published gate is the headline row recomputed, not a second figure: the caller
    that asks for the whole grid gets the same `automated_cases`, `erroneous_cases` and `bound` at
    `lambda == gate` that `audit_fields` prints in the table, because both come from this function
    over the same population.
    """
    handed = list(records)
    if not handed:
        raise ValueError("no records handed to the frontier: there is nothing to measure")
    names = sorted({r.backend for r in handed})
    if len(names) > 1:
        raise ValueError("frontier takes one backend; the population mixed %r" % (names,))
    fields = _checked_fields(fields)
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1); got %r" % (delta,))
    audited, excluded, _ = _partition(handed)
    if not audited:
        raise ValueError("nothing to audit: all %d rows handed over were excluded (%s)"
                         % (len(handed), "; ".join(sorted(excluded))))
    out = []
    for field in fields:
        for lam in grid:
            spec = FIELDS[field]
            counts = count_outcome(audited, _verdict_for(spec["get"], lam))
            automated = counts["automated_cases"]
            erroneous = counts["erroneous_cases"]
            out.append({
                "backend": names[0], "field": field, "lambda": lam,
                "delta": delta,
                "implied_error": 1.0 - lam,
                "n_rows_handed_over": len(handed), "n_records": len(audited),
                "excluded_unlabelled": sum(1 for r in handed if r.gold is None),
                "n_cases": counts["n_cases"], "automated_cases": automated,
                "automated_rows": counts["automated"],
                "erroneous_cases": erroneous,
                "coverage": _rate(automated, counts["n_cases"]),
                "measured_error": _rate(erroneous, automated),
                "bound": _bound(erroneous, automated, delta),
            })
    # A threshold family is monotone by construction: raising lambda can only shrink the set of
    # records that clear it. If the emitted curve is not monotone, this module's own arithmetic
    # contradicts the rule it implements, which is drift rather than a finding.
    for field in fields:
        pts = sorted((p for p in out if p["field"] == field), key=lambda p: p["lambda"])
        autom = [p["automated_cases"] for p in pts]
        if autom != sorted(autom, reverse=True):
            raise AuditDriftError("the frontier for %r is not monotone in the gate: %r. A rule of "
                                  "the form value >= lambda automates a subset as lambda rises, so "
                                  "a curve that automates more at a higher gate contradicts the "
                                  "rule it was computed from" % (field, autom))
    return out


def _same(published, recomputed, tolerance: float = 1e-12) -> bool:
    """Both None, or both numbers inside `tolerance`. `None` is a published value, not a gap."""
    if published is None or recomputed is None:
        return published is None and recomputed is None
    return abs(published - recomputed) <= tolerance


def check_audit(audits) -> None:
    """Re-derive the audit's own arithmetic and refuse to publish a contradiction.

    Every check here is a relationship between figures the module just computed, so this is the
    arm of the exit-code map that means "the audit disagrees with itself" (rc 4) rather than "the
    operator's inputs are wrong" (rc 2). It runs at the end of `audit_fields` on its own rows and
    again in `cmd_audit` across the whole set, so a row edited into the artefact by anything other
    than this module cannot leave the command quietly.

    It is deliberately re-derivation over the KEY UNION of what the artefact prints, not over the
    case partition alone. The inherited version policed the case figures and the exclusion
    accounting and left every row-level column -- `automated_rows`, `erroneous_rows`,
    `measured_error_rows`, `multiple_rows`, `n_records_carrying_field`, `mean_value` -- and
    `informative` itself unchecked; tampering each of those through this module's own output passed
    `check_audit` silently. `informative` is the worst of them, because `cmd_audit` chooses rc 0 or
    rc 3 on it, so an unchecked copy of that flag turns a refusal into a green exit code. A gate
    that re-derives some of the printed columns licenses the rest.
    """
    rows = []
    if isinstance(audits, dict):
        for backend, table in audits.items():
            for field, row in table.items():
                rows.append((backend, field, row))
    gates = {row["gate"] for _, _, row in rows}
    deltas = {row["delta"] for _, _, row in rows}
    if len(gates) > 1 or len(deltas) > 1:
        raise AuditDriftError("one audit published two different rubrics: gates %r, deltas %r"
                              % (sorted(gates), sorted(deltas)))
    for backend, field, row in rows:
        label = "%s/%s" % (backend, field)
        automated = row["automated_cases"]
        erroneous = row["erroneous_cases"]
        n_cases = row["n_cases"]
        if automated + row["refused_cases"] != n_cases:
            raise AuditDriftError("%s: the case partition does not close: %d automated + %d refused "
                                  "!= %d cases. count_outcome defines refusal as the complement, so "
                                  "a gap here means a verdict this counter does not know"
                                  % (label, automated, row["refused_cases"], n_cases))
        if not 0 <= erroneous <= automated <= n_cases:
            raise AuditDriftError("%s: the counts are out of order: %d erroneous, %d automated, "
                                  "%d cases. an error cannot exceed the decisions it lives in"
                                  % (label, erroneous, automated, n_cases))
        if row["n_records"] + sum(row["excluded_reasons"].values()) != row["n_rows_handed_over"]:
            raise AuditDriftError("%s: %d audited + %d excluded != %d rows handed over. an "
                                  "excluded row that is not counted is the quiet filter this "
                                  "command exists to make visible"
                                  % (label, row["n_records"],
                                     sum(row["excluded_reasons"].values()),
                                     row["n_rows_handed_over"]))
        if row["excluded_unlabelled"] + row["excluded_no_answer"] != sum(
                row["excluded_reasons"].values()):
            raise AuditDriftError("%s: the exclusion reasons do not add up to the named buckets"
                                  % label)
        collapse = row["automated_cases_by_collapse"]
        if set(collapse) != set(COLLAPSES):
            raise AuditDriftError("%s: the collapse table holds %r but the audit defines %r. A "
                                  "convention that stopped being measured is not a convention that "
                                  "was equal to the published one -- the inherited code read this "
                                  "key with a `.get` default that made its absence look like "
                                  "agreement" % (label, sorted(collapse), sorted(COLLAPSES)))
        for collapse_name, cases in collapse.items():
            if not 0 <= cases <= n_cases:
                raise AuditDriftError("%s: collapse %r reports %d automated cases over %d"
                                      % (label, collapse_name, cases, n_cases))
        # §7.3's curve, now that the artefact prints it. The published columns are re-derived here
        # rather than trusted, because the renderer reads `row["curve"]` verbatim: a point whose
        # bound was computed at a different `delta` from the row's, or whose at-gate point disagrees
        # with the headline above it, would reach the reader with no other gate in the module able
        # to see it. `bound` is re-derived from `tails` through `_bound`, the same owner that wrote
        # it, so this is a re-computation of the same quantity by the same producer, not a second
        # implementation of Clopper-Pearson.
        curve = row.get("curve")
        if curve is not None:
            for point in curve:
                if point["delta"] != row["delta"]:
                    raise AuditDriftError(
                        "%s: the curve point at lambda %r is bounded at delta %r while the row "
                        "publishes delta %r. One artefact cannot carry two rubrics: the header, the "
                        "table and the frontier are the same run or they are nothing" % (
                            label, point["lambda"], point["delta"], row["delta"]))
                if point["automated_cases"] > point["n_cases"]:
                    raise AuditDriftError("%s: the curve point at lambda %r automates %d cases over "
                                          "%d" % (label, point["lambda"], point["automated_cases"],
                                                  point["n_cases"]))
                if not _same(point["coverage"], _rate(point["automated_cases"], point["n_cases"])):
                    raise AuditDriftError("%s: the curve point at lambda %r publishes coverage %r, "
                                          "which is not its own automated cases over its own cases"
                                          % (label, point["lambda"], point["coverage"]))
                point_rate = _rate(point["erroneous_cases"], point["automated_cases"])
                if not _same(point["measured_error"], point_rate):
                    raise AuditDriftError("%s: the curve point at lambda %r publishes measured_error "
                                          "%r, not erroneous over automated = %r"
                                          % (label, point["lambda"], point["measured_error"],
                                             point_rate))
                if point_rate is not None:
                    want = _bound(point["erroneous_cases"], point["automated_cases"], row["delta"])
                    if not _same(point["bound"], want, tolerance=0.0):
                        raise AuditDriftError("%s: the curve point at lambda %r publishes bound %r "
                                              "where `tails` at this row's delta answers %r" % (
                                                  label, point["lambda"], point["bound"], want))
                if point["bound"] is not None and point_rate is not None and not (
                        point["bound"] >= point_rate):
                    raise AuditDriftError("%s: the curve point at lambda %r bounds %r below the rate "
                                          "%r it claims to bound" % (
                                              label, point["lambda"], point["bound"], point_rate))
            at_gate = [p for p in curve if p["lambda"] == row["gate"]]
            if not at_gate:
                raise AuditDriftError("%s: the published grid %r does not include the gate %r, so "
                                      "the artefact prints a frontier this row cannot be found on"
                                      % (label, [p["lambda"] for p in curve], row["gate"]))
            point = at_gate[0]
            if (point["automated_cases"], point["erroneous_cases"], point["n_cases"]) != (
                    automated, erroneous, n_cases):
                raise AuditDriftError("%s: the headline row says %d of %d cases automate with %d "
                                      "wrong while the curve's own point at the same gate says %d of "
                                      "%d with %d. One rule, one population, one producer: those "
                                      "cannot differ" % (
                                          label, automated, n_cases, erroneous,
                                          point["automated_cases"], point["n_cases"],
                                          point["erroneous_cases"]))
            if not _same(point["bound"], row["bound"], tolerance=0.0):
                raise AuditDriftError("%s: the table publishes bound %r and the curve publishes %r "
                                      "at the same gate and the same delta" % (
                                          label, row["bound"], point["bound"]))
        # The row-level figures, re-derived over their whole set, not just the case-level ones.
        # G2's premise asks for the row figure BESIDE the case figure, so those numbers are
        # published, and a gate that re-derives four of the printed columns licenses the rest: the
        # inherited `check_audit` policed the case partition and left every row column unchecked.
        if not 0 <= row["automated_rows"] <= row["n_records"]:
            raise AuditDriftError("%s: %d automated rows over %d audited rows"
                                  % (label, row["automated_rows"], row["n_records"]))
        if not 0 <= row["erroneous_rows"] <= row["automated_rows"]:
            raise AuditDriftError("%s: %d erroneous rows cannot exceed the %d rows that automated"
                                  % (label, row["erroneous_rows"], row["automated_rows"]))
        row_rate = _rate(row["erroneous_rows"], row["automated_rows"])
        if not _same(row["measured_error_rows"], row_rate):
            raise AuditDriftError("%s: published row rate %r is not erroneous_rows / automated_rows"
                                  " = %r" % (label, row["measured_error_rows"], row_rate))
        wanted_rows_multiple = None if row_rate is None else row_rate / row["implied_error"]
        if not _same(row["multiple_rows"], wanted_rows_multiple):
            raise AuditDriftError("%s: published row multiple %r is not the row rate over the "
                                  "implied error" % (label, row["multiple_rows"]))
        if row["n_records_carrying_field"] + row["n_records_missing_field"] != row["n_records"]:
            raise AuditDriftError("%s: %d rows carry the field + %d do not != %d audited rows. The "
                                  "carrying count is the denominator of `mean_value`, so it may not "
                                  "be free" % (label, row["n_records_carrying_field"],
                                               row["n_records_missing_field"], row["n_records"]))
        if (row["mean_value"] is None) != bool(row["n_records_carrying_field"] == 0):
            raise AuditDriftError("%s: a mean over %d carrying rows is %r"
                                  % (label, row["n_records_carrying_field"], row["mean_value"]))
        if automated:
            for key in ("bound", "bound_two_sided"):
                if not isinstance(row[key], float):
                    # Ask this before the comparisons below: `None >= float` raises `TypeError`,
                    # which is not in `main`'s catch tuple, so a missing bound on a populated
                    # denominator would reach the operator as rc 1 instead of rc 4.
                    raise AuditDriftError("%s: %d automated cases but no %s -- a bound is computed "
                                          "iff the denominator is populated, so the two disagreeing "
                                          "means one of them was dropped" % (label, automated, key))
            if abs(row["measured_error"] - erroneous / automated) > 1e-12:
                raise AuditDriftError("%s: published measured_error %.6f is not erroneous_cases "
                                      "/ automated_cases = %.6f"
                                      % (label, row["measured_error"], erroneous / automated))
            if abs(row["multiple"] - row["measured_error"] / row["implied_error"]) > 1e-12:
                raise AuditDriftError("%s: published multiple %.6f is not measured_error / "
                                      "implied_error" % (label, row["multiple"]))
            if not row["bound"] >= row["measured_error"]:
                raise AuditDriftError("%s: the bound %.6f is below the rate %.6f it claims to "
                                      "bound" % (label, row["bound"], row["measured_error"]))
            if not row["bound_two_sided"] >= row["bound"]:
                raise AuditDriftError("%s: the two-sided upper endpoint %.6f is tighter than the "
                                      "one-sided bound %.6f, which the inversion cannot produce"
                                      % (label, row["bound_two_sided"], row["bound"]))
            # `informative` is not decoration: `cmd_audit` returns rc 0 or rc 3 on it. A published
            # flag that does not follow from the bound it names would let the command certify a gate
            # the corpus does not bound, silently and with a green exit code.
            if row["informative"] is not bool(row["bound"] <= row["implied_error"]):
                raise AuditDriftError("%s: `informative` is %r while the bound %.6f against the "
                                      "implied error %.6f says %r. This figure chooses the exit code"
                                      % (label, row["informative"], row["bound"],
                                         row["implied_error"],
                                         bool(row["bound"] <= row["implied_error"])))
            if collapse["max_field_row"] < automated:
                raise AuditDriftError("%s: collapsing each case to its highest-field row automates "
                                      "FEWER cases (%d) than requiring every row to clear the gate "
                                      "(%d); the max collapse is a superset of that rule by "
                                      "construction" % (label, collapse["max_field_row"], automated))
        else:
            if row["measured_error"] is not None or row["multiple"] is not None:
                raise AuditDriftError("%s: nothing automated, yet an error rate and a multiple are "
                                      "published; a rate over an empty denominator is invented, not "
                                      "measured" % label)
            if row["bound"] is not None or row["bound_two_sided"] is not None or (
                    row["informative"] is not None):
                raise AuditDriftError("%s: an empty automated denominator, yet a bound or an "
                                      "informativeness flag is published (%r, %r, %r)"
                                      % (label, row["bound"], row["bound_two_sided"],
                                         row["informative"]))


def _fmt(value, spec: str = "%.4f") -> str:
    return "-" if value is None else (spec % value)


def _multiple_of(row) -> str:
    """The row's own `multiple`, formatted. A formatter, not a calculator: the figure is the
    producer's (`audit_fields` divides the rate by the implied error), and an empty denominator
    renders as the dash the table already uses rather than as a number this function invented."""
    return "-" if row["multiple"] is None else "%.2fx" % row["multiple"]


def _row_phrase(backend: str, row) -> str:
    """One row's published verdict in one phrase, with its own denominator and its own bound.

    The `informative` word is the row's, not a sentence this renderer writes: jev's `confidence`
    row bounds under the implied error and laya's does not, so a blanket "neither is certified"
    would be a claim about the corpus that the corpus contradicts -- which is the defect class this
    file exists to catch, one column over from the one it was written for.
    """
    informative = row["informative"]
    return "`%s` %s on %d of %d automated cases (%d wrong), one-sided bound %s, informative: %s" % (
        backend, _multiple_of(row), row["automated_cases"], row["n_cases"],
        row["erroneous_cases"], _fmt(row["bound"]),
        "-" if informative is None else ("yes" if informative else "**NO**"))


def _curve_of(backend: str, field: str, row) -> list:
    """The row's own frontier, or a refusal naming the row that has none.

    `audit_fields` writes `curve` on every row it produces, so a row arriving here without one is a
    table this module did not make -- and the inherited code would have answered that with a
    `KeyError`, which is a `LookupError`, which `cli.main` does not catch: rc 1, outside the
    documented 0/2/3/4 contract. The refusal is a `ValueError` (rc 2) for the same reason
    `_table_fields` refuses an unknown field name.
    """
    curve = row.get("curve")
    if not curve:
        raise ValueError("the audit produced %s/%s with no risk-coverage curve to print; every row "
                         "this module writes carries the sweep `frontier` made for it"
                         % (backend, field))
    return curve


def _grid_of(audits: dict, tables: dict) -> tuple:
    """The `lambda` grid the run swept, read back off the curves it is about to print.

    Named from the data and not from `DEFAULT_GRID`, because the sentence that tells the reader which
    grid ran must not be able to disagree with the tables the same run prints.
    """
    lambdas = sorted({point["lambda"] for b in sorted(audits) for f in tables[b]
                      for point in _curve_of(b, f, audits[b][f])})
    if not lambdas:
        raise ValueError("render_audit received rows carrying no risk-coverage curve to print")
    return tuple(lambdas)


def _table_fields(table: dict) -> tuple:
    """The fields a rendered table actually holds, in the published order.

    The renderer used to walk `FIELD_ORDER` and index `FIELD_ORDER[0]` unconditionally, so a table
    produced for a subset of the fields died with `KeyError: 'confidence'` -- rc 1, outside the
    exit-code contract, for a call the module's own signature invites. Rendering the rows that
    exist is the fix; a row whose name this module does not know is the opposite case, and it is
    refused rather than printed under a column nobody can name.
    """
    unknown = sorted(set(table) - set(FIELD_ORDER))
    if unknown:
        raise ValueError("the audit produced a field it cannot render: %r; it names %s"
                         % (", ".join(unknown), ", ".join(FIELD_ORDER)))
    present = tuple(f for f in FIELD_ORDER if f in table)
    if not present:
        raise ValueError("render_audit received a table with no field rows")
    return present


def render_audit(audits: dict) -> str:
    """Render G2 as the artefact `autorate audit` commits.

    Deterministic and free of machine paths and timestamps, so a re-run is byte-comparable and
    `tests/test_audit.py` can hold the committed file against this function.
    """
    tables = {b: _table_fields(audits[b]) for b in sorted(audits)}
    rows = [(b, f, audits[b][f]) for b in sorted(audits) for f in tables[b]]
    if not rows:
        raise ValueError("render_audit received no audited rows")
    gate = rows[0][2]["gate"]
    delta = rows[0][2]["delta"]
    grid_text = ", ".join("%.2f" % lam for lam in _grid_of(audits, tables))
    confidence_bullet = (
        "- which `confidence`: upstream defines the name twice -- %s, its docstring calling it the "
        "quantity its calibration figures are computed on, and %s, its docstring calling that one "
        "not calibrated. The sentence this artefact is about reads the response key `confidence`, "
        "and it is the second of the two that fills that key: %s. Which scale the carried value is "
        "actually on is measured per slice by `scales.scale_attribution` and printed with each "
        "backend below, so each row names both the definition it was read as and the attribution "
        "verdict for its own slice."
        % (UPSTREAM_ANSWER_CONFIDENCE, UPSTREAM_ENTROPY_CONFIDENCE, UPSTREAM_ANSWER_BUILDER))
    curve_bullet = (
        "- risk-coverage curve: spec \u00a77.3 asks for the frontier, not one gate, so each field "
        "below prints the sweep `frontier` made over `lambda` at this run's own `delta = %.2f`, "
        "bounded by `tails.clopper_pearson_upper` like the table above it. The grid is %s."
        % (delta, grid_text))
    lines = [
        "# Audit: the gate the README instructs, measured against what it implies",
        "",
        "Produced by `autorate audit` from the committed records file. Every number "
        "here is emitted by that command and re-derived by `tests/test_audit.py` from the same "
        "records; none is typed, and this file carries no timestamp, so a re-run is byte-comparable.",
        "",
        "**G2 (\u00a72):** at `confidence >= %.2f`, the measured error among automated decisions "
        "against the %.0f%% that sentence implies, and the multiple by which it misses."
        % (gate, 100 * (1.0 - gate)),
        "",
        "- gate compared against: `%.2f` (upstream's own gating figure), so the implied error rate "
        "is `1 - gate = %.2f`" % (gate, 1.0 - gate),
        "- bound level: exact Clopper-Pearson, one-sided at `delta = %.2f`, plus the two-sided "
        "upper endpoint (the same owner called at `delta / 2`); owned by "
        "`tails.clopper_pearson_upper`, never recomputed here" % delta,
        "- certification unit: the CASE, never the row. `%s`" % CASE_RULE,
        confidence_bullet,
        curve_bullet,
        "",
    ]
    for backend_name in sorted(audits):
        table = audits[backend_name]
        table_fields = tables[backend_name]
        first = table[table_fields[0]]
        excluded_total = sum(first["excluded_reasons"].values())
        lines += [
            "## `%s`" % backend_name,
            "",
            "- rows handed over: **%d**; audited: **%d**; **excluded: %d**" % (
                first["n_rows_handed_over"], first["n_records"], excluded_total),
        ]
        for reason, count in sorted(first["excluded_reasons"].items()):
            lines.append("  - %d rows excluded because %s" % (count, reason))
        if not excluded_total:
            lines.append("  - no row was excluded: the population handed over was already "
                         "label-comparable")
        lines.append("- slices audited: %s (%d cases across the audited population)" % (
            ", ".join("`%s` %d rows" % (slice_name,
                                       first["attribution"][slice_name]["n_rows_handed_over"])
                      for slice_name in first["slices"]),
            first["n_cases"]))
        lines += [
            "",
            "| field | read as | attributed scale | cases automated | of those, wrong | measured "
            "error | implied | multiple | CP upper (1-sided) | CP upper (2-sided) | informative |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for field in table_fields:
            row = table[field]
            informative = row["informative"]
            # `source` says where the number came from; `definition` says what it is. The header
            # above promises each field "names the definition it was read as", and the inherited
            # renderer printed only the source, leaving `definition` computed, stored in the row and
            # never published -- an artefact describing itself more generously than it was written.
            lines.append("| `%s` | %s -- %s | %s | %d of %d | %d | %s | %.2f | %s | %s | %s | %s |" % (
                field, row["source"], row["definition"], row["attributed_scale"],
                row["automated_cases"], row["n_cases"], row["erroneous_cases"],
                _fmt(row["measured_error"]), row["implied_error"],
                "-" if row["multiple"] is None else "%.2fx" % row["multiple"],
                _fmt(row["bound"]), _fmt(row["bound_two_sided"]),
                "-" if informative is None else ("yes" if informative else "**NO**"),
            ))
        lines += ["", "Row-level figures beside them, because the denominators are not the same "
                      "number twice:"]
        for field in table_fields:
            row = table[field]
            lines.append(
                "- `%s`: %d of %d ROWS automate, %d of those wrong (row rate %s, multiple %s); "
                "%d of the audited rows carry the field, and their mean value is %s." % (
                    field, row["automated_rows"], row["n_records"], row["erroneous_rows"],
                    _fmt(row["measured_error_rows"]),
                    "-" if row["multiple_rows"] is None else "%.2fx" % row["multiple_rows"],
                    row["n_records_carrying_field"], _fmt(row["mean_value"])))
            if row.get("note"):
                lines.append("  - `%s`: %s" % (field, row["note"]))
            collapses = row["automated_cases_by_collapse"]
            if any(c != row["automated_cases"] for c in collapses.values()):
                lines.append(
                    "  - `%s`: the case convention moves the count. Published (`%s`): %d cases. "
                    "Collapsing each case to one row first: %s. The rate in the table is the "
                    "published convention; the others are measured here, not quoted." % (
                        field, CASE_RULE, row["automated_cases"],
                        ", ".join("%s = %d" % (c, collapses[c]) for c in COLLAPSES)))
            # §7.3's frontier, printed from the row's own curve: every cell below is `frontier`'s
            # figure, bounded by `tails.clopper_pearson_upper` at this run's `delta`, and nothing here
            # is recomputed. A single gate is the shape of claim this project exists to refuse, which
            # is why the sweep is in the artefact rather than only in the data structure.
            lines += [
                "",
                "  Risk-coverage curve for `%s` -- the same population re-measured at every "
                "`lambda` on the grid, at this run's `delta = %.2f`. The unit is the CASE, and every "
                "ratio names the denominator it divides:" % (field, row["delta"]),
                "",
                "| lambda | implied error (`1 - lambda`) | automated cases (of %d cases) | "
                "of those, wrong | coverage (automated / %d cases) | measured error "
                "(wrong / automated cases) | CP upper (1-sided, `delta = %.2f`) |" % (
                    row["n_cases"], row["n_cases"], row["delta"]),
                "|---|---|---|---|---|---|---|",
            ]
            for point in _curve_of(backend_name, field, row):
                lines.append("| `%s`%s | %s | %d | %d | %s | %s | %s |" % (
                    "%.2f" % point["lambda"],
                    " **(the gate above)**" if point["lambda"] == row["gate"] else "",
                    _fmt(point["implied_error"], "%.2f"), point["automated_cases"],
                    point["erroneous_cases"], _fmt(point["coverage"]),
                    _fmt(point["measured_error"]), _fmt(point["bound"])))
            lines.append("")
            lines.append(
                "  - `%s`: the curve is a description of this rule on this corpus, not a "
                "certificate of any point on it. Where the last column sits above the implied error "
                "the corpus cannot bound that threshold either, and the row above says so by name."
                % field)
        lines.append("")
        for slice_name in first["slices"]:
            evidence = first["attribution"][slice_name]
            lines.append(
                "- attribution `%s`: **%s** over %d measured rows of %d handed over; worst row "
                "distance to `max(p)` %s, to the entropy scale %s; per-row mixture "
                "both=%d answer_only=%d entropy_only=%d neither=%d. The verdict is the batch's "
                "worst case, so the mixture is the part that may be read per row." % (
                    slice_name, evidence["verdict"], evidence["n_rows_measured"],
                    evidence["n_rows_handed_over"], _fmt(evidence["max_dev_answer"], "%.6f"),
                    _fmt(evidence["max_dev_entropy"], "%.6f"), evidence["row_mixture"]["both"],
                    evidence["row_mixture"]["answer_only"],
                    evidence["row_mixture"]["entropy_only"],
                    evidence["row_mixture"]["neither"]))
        lines.append("")
    worst = max(((b, f, r) for b, f, r in rows if r["multiple"] is not None),
                key=lambda item: item[2]["multiple"], default=None)
    lines += [
        "## What this does and does not establish",
        "",
        "- Both halves are results. Where the measured error exceeds the implied error the gate "
        "misses its own sentence, and the multiple says by how much. Where the bound sits above "
        "the implied error the corpus cannot bound the gate at all, and `NOT_INFORMATIVE` is "
        "printed instead of a certificate.",
    ]
    # Which row answers the sentence the README actually wrote -- the gap MAJ-2 names: three
    # multiples printed side by side with nothing saying which one the gate in that sentence is
    # about. The numbers are read off the rows, never typed here; the two definitions are named by
    # their upstream locations, not by a private task id; and whether either row is bounded is the
    # rows' own `informative` verdict, because a blanket refusal sentence about jev would be false.
    literal = [(b, audits[b]["confidence"]) for b in sorted(audits) if "confidence" in audits[b]]
    intended = [(b, audits[b]["answer_confidence"]) for b in sorted(audits)
                if "answer_confidence" in audits[b]]
    if literal and intended:
        lines.append(
            "- Which row answers the README: its own instruction (%s) reads the response key "
            "`confidence`, which reaches this corpus as %s, and upstream fills that key from %s -- "
            "the second of the two definitions it publishes under one name, the first being %s. So "
            "the row that answers that sentence verbatim is **`confidence`**: %s. The "
            "**`answer_confidence`** row is the same instruction read as `p_max = max(probs)` -- "
            "upstream's calibrated quantity, a different number on a different scale: %s. Quoting "
            "either multiple as the other is the definition slip the two definitions make possible, "
            "and this artefact publishes both rows precisely so a headline can name which one it "
            "means. Which of them this corpus bounds is the `informative` column's answer above, "
            "row by row." % (
                UPSTREAM_GATE_SENTENCE, LOCAL_RECORD_KEY, UPSTREAM_ENTROPY_CONFIDENCE,
                UPSTREAM_ANSWER_CONFIDENCE,
                "; ".join(_row_phrase(b, r) for b, r in literal),
                "; ".join(_row_phrase(b, r) for b, r in intended)))
    if worst is not None:
        _, wide_field, wide = worst
        lines.append(
            "- A multiple is a point estimate and needs its interval before it is anything else: "
            "the widest miss above is `%s` at %.2fx, which is %d wrong out of %d automated cases, "
            "whose exact one-sided upper bound is %s and whose two-sided upper endpoint is %s. "
            "Neither bound is quoted as a certificate of the other." % (
                wide_field, wide["multiple"], wide["erroneous_cases"], wide["automated_cases"],
                _fmt(wide["bound"]), _fmt(wide["bound_two_sided"])))
    lines += [
        "- Nothing here certifies a deployment: this measures a rule the reference README "
        "instructs, on archived responses. The certified bounds live on the certificates, which "
        "`autorate report` publishes and `autorate verify` re-derives.",
        "",
    ]
    return "\n".join(lines)
